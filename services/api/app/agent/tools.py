"""The 11 agent tools (DESIGN.md 9.2).

Every tool is typed, hits the deterministic engine, and returns
``{data, citations}``. **No tool computes a figure itself** — each one calls
into ``app.engine`` (through the same ``Snapshot`` the dashboard uses) and
shapes the result. That is the load-bearing claim of section 9: the model
selects tools and writes prose; Python does the arithmetic.

Citations are the anti-hallucination architecture (DESIGN.md 9.3). Every
figure a tool returns is registered against the exact transaction ids that
sum to it, and the registry hands back a short id (``c1``, ``c2``, ...) that
the model is required to attach to the figure when it writes prose. A number
with no citation id did not come from here, and the UI renders it as
unverified.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable, Sequence

from ..engine import budget as budget_engine
from ..engine import cashflow, goals as goals_engine, simulate as simulate_engine
from ..engine.types import (
    Direction,
    OneOff,
    Scenario,
    SeriesStatus,
    Txn,
)
from ..models.taxonomy import display_name
from ..services.views import Snapshot, anomaly_key, jsonable

#: A tool may never hand back the whole ledger. The model pays for every token
#: of a tool result, and a 936-row dump would crowd out the conversation
#: without making any answer more correct — the citation carries the full id
#: list for the UI regardless of how many rows are echoed here.
MAX_ROWS = 25


class NoDataError(Exception):
    """Raised when a tool has no data for the requested period.

    The loop turns this into an explicit "I don't have data for that" turn
    rather than letting the model fill the silence (DESIGN.md 9.4, grounding).
    """


# --- Citations --------------------------------------------------------------


class CitationRegistry:
    """Assigns a stable short id to every figure produced during one request.

    Kept per-request rather than global so ids restart at ``c1`` for each
    question and stay short enough for the model to quote inline.
    """

    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []

    def add(self, label: str, value_paise: int, txn_ids: Sequence[str]) -> dict[str, Any]:
        """Register a figure and return the model-facing stub (no id list).

        The transaction ids stay in the registry for the UI to resolve; the
        model is told only how many there are, because it has no use for 27
        uuids and every one of them costs tokens.
        """
        ids = tuple(dict.fromkeys(txn_ids))  # de-duplicate, preserve order
        cid = f"c{len(self._items) + 1}"
        self._items.append(
            {
                "id": cid,
                "label": label,
                "value_paise": int(value_paise),
                "txn_ids": list(ids),
                "txn_count": len(ids),
            }
        )
        return {"id": cid, "label": label, "value_paise": int(value_paise), "txn_count": len(ids)}

    def as_list(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._items]

    def ids(self) -> set[str]:
        return {str(item["id"]) for item in self._items}


@dataclass(frozen=True)
class ToolResult:
    data: dict[str, Any]
    #: **Model-facing stubs, not the UI payload.** These deliberately omit
    #: ``txn_ids`` so the conversation does not carry hundreds of uuids the
    #: model has no use for. The full ids live in the request's
    #: `CitationRegistry`; the route must serialise `registry.as_list()` for
    #: the browser, or `CitationChip` will have nothing to open the drawer on.
    citations: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"data": jsonable(self.data), "citations": self.citations}


@dataclass
class ToolContext:
    """Everything a tool is allowed to touch."""

    snapshot: Snapshot
    citations: CitationRegistry


# --- Period parsing ---------------------------------------------------------


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _add_months(value: date, months: int) -> date:
    total = (value.year * 12 + value.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)


def parse_period(period: str | None, *, as_of: date) -> tuple[date, date]:
    """``"2026-09"`` or ``"2026-09-01"`` -> that month's inclusive bounds.

    ``None`` means the month containing ``as_of``. Anything else is rejected
    rather than guessed: a tool that silently reinterprets an unparseable
    period is a tool that answers a question nobody asked.
    """
    if not period:
        start = _month_start(as_of)
        return start, _add_months(start, 1) - timedelta(days=1)

    text = str(period).strip()
    try:
        if len(text) == 7:
            start = date.fromisoformat(text + "-01")
        else:
            start = _month_start(date.fromisoformat(text))
    except ValueError as exc:
        raise NoDataError(
            f"'{period}' is not a period I can read. Use YYYY-MM, for example 2026-09."
        ) from exc
    return start, _add_months(start, 1) - timedelta(days=1)


def _label_month(start: date) -> str:
    return start.strftime("%B %Y")


def _txn_row(txn: Txn) -> dict[str, Any]:
    return {
        "id": txn.id,
        "date": txn.txn_date.isoformat(),
        "merchant": txn.normalized_merchant,
        "amount_paise": txn.amount_paise,
        "direction": txn.direction.value,
        "category": display_name(txn.category_slug),
        "category_slug": txn.category_slug,
    }


def _in_window(txns: Sequence[Txn], start: date, end: date) -> list[Txn]:
    return [t for t in txns if start <= t.txn_date <= end]


# --- The 11 tools -----------------------------------------------------------


def query_transactions(
    ctx: ToolContext,
    *,
    start: str | None = None,
    end: str | None = None,
    category_slug: str | None = None,
    merchant: str | None = None,
    min_amount_paise: int | None = None,
    max_amount_paise: int | None = None,
    direction: str | None = None,
) -> ToolResult:
    """Filtered transactions, with the matched total as a citation."""
    snap = ctx.snapshot
    rows = list(snap.txns)

    if start:
        lo = date.fromisoformat(start)
        rows = [t for t in rows if t.txn_date >= lo]
    if end:
        hi = date.fromisoformat(end)
        rows = [t for t in rows if t.txn_date <= hi]
    if category_slug:
        rows = [t for t in rows if t.category_slug == category_slug]
    if merchant:
        needle = merchant.upper()
        rows = [t for t in rows if needle in t.normalized_merchant.upper()]
    if min_amount_paise is not None:
        rows = [t for t in rows if t.amount_paise >= int(min_amount_paise)]
    if max_amount_paise is not None:
        rows = [t for t in rows if t.amount_paise <= int(max_amount_paise)]
    if direction:
        want = Direction(direction.upper())
        rows = [t for t in rows if t.direction is want]

    if not rows:
        raise NoDataError("No transactions match those filters.")

    rows.sort(key=lambda t: t.txn_date, reverse=True)
    total = sum(t.amount_paise for t in rows)
    descriptor = merchant or (display_name(category_slug) if category_slug else "Matching transactions")
    citation = ctx.citations.add(descriptor, total, [t.id for t in rows])

    return ToolResult(
        data={
            "total_paise": total,
            "txn_count": len(rows),
            "citation_id": citation["id"],
            "transactions": [_txn_row(t) for t in rows[:MAX_ROWS]],
            "truncated": len(rows) > MAX_ROWS,
        },
        citations=[citation],
    )


def get_category_breakdown(ctx: ToolContext, *, period: str | None = None) -> ToolResult:
    """Totals per category for one month, ranked, each row cited."""
    snap = ctx.snapshot
    start, end = parse_period(period, as_of=snap.as_of)
    rows = cashflow.category_breakdown(snap.txns, start=start, end=end)
    if not rows:
        raise NoDataError(f"No spending recorded for {_label_month(start)}.")

    label = _label_month(start)
    out, cites = [], []
    for slug, total_paise, txn_ids in rows:
        citation = ctx.citations.add(f"{display_name(slug)}, {label}", total_paise, txn_ids)
        cites.append(citation)
        out.append(
            {
                "category": display_name(slug),
                "category_slug": slug,
                "total_paise": total_paise,
                "txn_count": citation["txn_count"],
                "citation_id": citation["id"],
            }
        )

    return ToolResult(
        data={"period": start.isoformat(), "period_label": label, "categories": out},
        citations=cites,
    )


def compare_periods(ctx: ToolContext, *, period_a: str, period_b: str) -> ToolResult:
    """Per-category deltas between two months, absolute and percentage."""
    snap = ctx.snapshot
    a_start, a_end = parse_period(period_a, as_of=snap.as_of)
    b_start, b_end = parse_period(period_b, as_of=snap.as_of)

    a_rows = {slug: (total, ids) for slug, total, ids in cashflow.category_breakdown(snap.txns, start=a_start, end=a_end)}
    b_rows = {slug: (total, ids) for slug, total, ids in cashflow.category_breakdown(snap.txns, start=b_start, end=b_end)}
    if not a_rows and not b_rows:
        raise NoDataError(
            f"No spending recorded in either {_label_month(a_start)} or {_label_month(b_start)}."
        )

    cites: list[dict[str, Any]] = []
    deltas = []
    for slug in sorted(set(a_rows) | set(b_rows)):
        a_total, a_ids = a_rows.get(slug, (0, ()))
        b_total, b_ids = b_rows.get(slug, (0, ()))
        delta = b_total - a_total
        # A category that appears for the first time has no baseline to be a
        # percentage of; None says so rather than reporting an infinite rise.
        pct = round(delta * 100.0 / a_total, 1) if a_total else None
        citation = ctx.citations.add(
            f"{display_name(slug)}, {_label_month(a_start)} vs {_label_month(b_start)}",
            delta,
            tuple(a_ids) + tuple(b_ids),
        )
        cites.append(citation)
        deltas.append(
            {
                "category": display_name(slug),
                "category_slug": slug,
                "period_a_paise": a_total,
                "period_b_paise": b_total,
                "delta_paise": delta,
                "delta_pct": pct,
                "citation_id": citation["id"],
            }
        )

    deltas.sort(key=lambda r: -abs(int(r["delta_paise"])))
    return ToolResult(
        data={
            "period_a": a_start.isoformat(),
            "period_a_label": _label_month(a_start),
            "period_b": b_start.isoformat(),
            "period_b_label": _label_month(b_start),
            "categories": deltas[:MAX_ROWS],
        },
        citations=cites,
    )


def list_recurring(ctx: ToolContext, *, status: str | None = None) -> ToolResult:
    """Recurring series with cadence, amount, mandate channel and AFA band."""
    snap = ctx.snapshot
    series = list(snap.series)
    if status:
        want = SeriesStatus(status.upper())
        series = [s for s in series if s.status is want]
    if not series:
        raise NoDataError("No recurring series match that status.")

    series.sort(key=lambda s: -s.median_amount_paise)
    rows, cites = [], []
    for s in series:
        citation = ctx.citations.add(
            f"{s.normalized_merchant}, {s.cadence.value.lower()}", s.median_amount_paise, s.txn_ids
        )
        cites.append(citation)
        rows.append(
            {
                "merchant": s.normalized_merchant,
                "series_key": s.key,
                "amount_paise": s.median_amount_paise,
                "cadence": s.cadence.value,
                "direction": s.direction.value,
                "status": s.status.value,
                "mandate_channel": s.mandate_channel.value,
                "afa_band": s.afa_band.value,
                "next_expected_date": s.next_expected_date.isoformat(),
                "acknowledged": s.acknowledged,
                "occurrence_count": s.occurrence_count,
                "citation_id": citation["id"],
            }
        )

    return ToolResult(data={"series_count": len(rows), "series": rows[:MAX_ROWS]}, citations=cites)


def get_upcoming_obligations(ctx: ToolContext, *, days: int = 30) -> ToolResult:
    """Forward schedule of expected debits over the next `days` days."""
    snap = ctx.snapshot
    obligations = cashflow.upcoming(snap.series, days=int(days), as_of=snap.as_of)
    if not obligations:
        raise NoDataError(f"Nothing is scheduled to debit in the next {int(days)} days.")

    by_key = {s.key: s for s in snap.series}
    total = sum(o.amount_paise for o in obligations)
    all_ids: list[str] = []
    rows, cites = [], []
    for o in obligations:
        ids = by_key[o.series_key].txn_ids if o.series_key in by_key else ()
        all_ids.extend(ids)
        citation = ctx.citations.add(
            f"{o.normalized_merchant}, due {o.due_date.isoformat()}", o.amount_paise, ids
        )
        cites.append(citation)
        rows.append(
            {
                "merchant": o.normalized_merchant,
                "due_date": o.due_date.isoformat(),
                "amount_paise": o.amount_paise,
                "afa_band": o.afa_band.value,
                "mandate_channel": o.mandate_channel.value,
                "acknowledged": o.acknowledged,
                "citation_id": citation["id"],
            }
        )

    total_citation = ctx.citations.add(f"Obligations, next {int(days)} days", total, all_ids)
    cites.append(total_citation)
    return ToolResult(
        data={
            "days": int(days),
            "total_paise": total,
            "total_citation_id": total_citation["id"],
            "count": len(rows),
            "obligations": rows[:MAX_ROWS],
        },
        citations=cites,
    )


def get_budget_status(ctx: ToolContext, *, period: str | None = None) -> ToolResult:
    """Per-category budget vs actual, with the pace verdict."""
    snap = ctx.snapshot
    start, _ = parse_period(period, as_of=snap.as_of)
    reference = snap.as_of if _month_start(snap.as_of) == start else start
    rows = budget_engine.status(snap.budgets, snap.txns, as_of=reference)
    if not rows:
        raise NoDataError("No budgets are set.")

    out, cites = [], []
    for r in rows:
        citation = ctx.citations.add(
            f"{display_name(r.category_slug)} spend, {_label_month(start)}", r.spent_paise, r.txn_ids
        )
        cites.append(citation)
        out.append(
            {
                "category": display_name(r.category_slug),
                "category_slug": r.category_slug,
                "limit_paise": r.limit_paise,
                "spent_paise": r.spent_paise,
                "remaining_paise": r.remaining_paise,
                "pct_used": r.pct_used,
                "projected_spend_paise": r.projected_spend_paise,
                "pace": r.pace.value,
                "citation_id": citation["id"],
            }
        )

    return ToolResult(
        data={"period_label": _label_month(start), "budgets": out}, citations=cites
    )


def get_goal_projection(ctx: ToolContext, *, goal_id: str | None = None) -> ToolResult:
    """ETA, required monthly contribution and verdict for each goal."""
    snap = ctx.snapshot
    projections = goals_engine.project(snap.goals, snap.txns, as_of=snap.as_of)
    if goal_id:
        projections = [p for p in projections if p.goal_id == goal_id]
    if not projections:
        raise NoDataError("No goals are set.")

    out, cites = [], []
    for p in projections:
        # A goal's balance is a stored position rather than a sum over rows,
        # so the citation carries no txn_ids. It still gets an id so the
        # figure is traceable to the engine call that produced it.
        citation = ctx.citations.add(f"{p.name}: saved so far", p.current_paise, ())
        cites.append(citation)
        out.append(
            {
                "goal_id": p.goal_id,
                "name": p.name,
                "target_paise": p.target_paise,
                "current_paise": p.current_paise,
                "shortfall_paise": p.shortfall_paise,
                "target_date": p.target_date.isoformat(),
                "required_monthly_paise": p.required_monthly_paise,
                "allocated_monthly_paise": p.allocated_monthly_paise,
                "projected_eta": p.projected_eta.isoformat() if p.projected_eta else None,
                "months_delta": p.months_delta,
                "verdict": p.verdict.value,
                "citation_id": citation["id"],
            }
        )

    return ToolResult(data={"goals": out}, citations=cites)


def detect_anomalies(ctx: ToolContext, *, period: str | None = None) -> ToolResult:
    """The five anomaly types with their plain-English explanations."""
    snap = ctx.snapshot
    items = list(snap.anomalies)
    if period:
        start, end = parse_period(period, as_of=snap.as_of)
        items = [a for a in items if a.period_start <= end and a.period_end >= start]
    if not items:
        raise NoDataError("No anomalies detected for that period.")

    out, cites = [], []
    for a in items:
        # The explanation is the engine's own fixed template, passed through
        # verbatim. The model may quote it; it may not improve on it.
        value = int(a.metric.get("amount_paise", 0) or 0)
        citation = ctx.citations.add(a.explanation[:80], value, a.txn_ids)
        cites.append(citation)
        out.append(
            {
                "type": a.type.value,
                "severity": a.severity.value,
                "explanation": a.explanation,
                "period_start": a.period_start.isoformat(),
                "anomaly_key": anomaly_key(a),
                "txn_count": citation["txn_count"],
                "citation_id": citation["id"],
            }
        )

    return ToolResult(data={"count": len(out), "anomalies": out[:MAX_ROWS]}, citations=cites)


def simulate_scenario(
    ctx: ToolContext,
    *,
    cancel_series: Sequence[str] = (),
    category_pct_change: dict[str, float] | None = None,
    one_off_amount_paise: int | None = None,
    one_off_category_slug: str | None = None,
) -> ToolResult:
    """The section 8.6 what-if engine: before/after ETA across every goal."""
    snap = ctx.snapshot
    one_off: tuple[OneOff, ...] = ()
    if one_off_amount_paise:
        one_off = (
            OneOff(
                amount_paise=int(one_off_amount_paise),
                on_date=snap.as_of,
                **({"category_slug": one_off_category_slug} if one_off_category_slug else {}),
            ),
        )

    scenario = Scenario(
        cancel_series=tuple(cancel_series or ()),
        category_pct_change={k: float(v) for k, v in (category_pct_change or {}).items()},
        one_off=one_off,
    )
    result = simulate_engine.simulate(
        snap.txns,
        snap.series,
        snap.goals,
        scenario,
        current_balance_paise=snap.balance_paise,
        as_of=snap.as_of,
    )

    citation = ctx.citations.add(
        "Monthly surplus after the change", result.monthly_surplus_after_paise, ()
    )
    return ToolResult(
        data={
            "monthly_surplus_before_paise": result.monthly_surplus_before_paise,
            "monthly_surplus_after_paise": result.monthly_surplus_after_paise,
            "monthly_surplus_delta_paise": result.monthly_surplus_delta_paise,
            "cancelled_monthly_paise": result.cancelled_monthly_paise,
            "safe_daily_before_paise": result.safe_daily_before_paise,
            "safe_daily_after_paise": result.safe_daily_after_paise,
            "citation_id": citation["id"],
            "goals": [
                {
                    "goal_id": g.goal_id,
                    "name": g.name,
                    "eta_before": g.eta_before.isoformat() if g.eta_before else None,
                    "eta_after": g.eta_after.isoformat() if g.eta_after else None,
                    "months_delta": g.months_delta,
                }
                for g in result.goals
            ],
        },
        citations=[citation],
    )


def get_safe_to_spend(ctx: ToolContext) -> ToolResult:
    """Committed vs discretionary, with the forward obligation schedule."""
    snap = ctx.snapshot
    sts = snap.safe_to_spend()
    by_key = {s.key: s for s in snap.series}

    committed_ids: list[str] = []
    for o in sts.obligations:
        committed_ids.extend(by_key[o.series_key].txn_ids if o.series_key in by_key else ())

    committed = ctx.citations.add("Committed before next income", sts.committed_paise, committed_ids)
    return ToolResult(
        data={
            "as_of": sts.as_of.isoformat(),
            "next_income_date": sts.next_income_date.isoformat() if sts.next_income_date else None,
            "next_income_paise": sts.next_income_paise,
            "current_balance_paise": sts.current_balance_paise,
            "committed_paise": sts.committed_paise,
            "committed_citation_id": committed["id"],
            "goal_due_paise": sts.goal_due_paise,
            "discretionary_paise": sts.discretionary_paise,
            "days_remaining": sts.days_remaining,
            "safe_daily_paise": sts.safe_daily_paise,
            "obligations": [
                {
                    "merchant": o.normalized_merchant,
                    "due_date": o.due_date.isoformat(),
                    "amount_paise": o.amount_paise,
                }
                for o in sts.obligations[:MAX_ROWS]
            ],
        },
        citations=[committed],
    )


def search_documents(ctx: ToolContext, *, query: str) -> ToolResult:
    """Search uploaded documents.

    DESIGN.md 9.2 specifies pgvector semantic search over bill and receipt
    text. No Supabase project is provisioned and the offline store keeps no
    chunk text, so this matches on document metadata only and says as much in
    ``semantic``. Reporting the limitation is the honest degradation; claiming
    a semantic hit we did not compute would be exactly the fabrication the
    citation architecture exists to prevent.
    """
    docs = ctx.snapshot.store.documents()
    needle = str(query).strip().lower()
    hits = [
        d for d in docs
        if needle in str(d.get("filename", "")).lower()
        or needle in str(d.get("bank_code") or "").lower()
    ]
    if not hits:
        raise NoDataError(
            "No uploaded document matches that. Document text search needs the "
            "pgvector index, which is not provisioned in this deployment."
        )
    return ToolResult(
        data={
            "semantic": False,
            "match_count": len(hits),
            "documents": [
                {
                    "id": d["id"],
                    "filename": d["filename"],
                    "bank_code": d.get("bank_code"),
                    "row_count": d.get("row_count"),
                    "status": d.get("status"),
                }
                for d in hits[:MAX_ROWS]
            ],
        }
    )


# --- Registry ---------------------------------------------------------------

_INT = {"type": "integer"}
_STR = {"type": "string"}

#: Gemini function declarations. Kept next to the implementations so a
#: parameter cannot be renamed in one place and not the other.
TOOL_DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "query_transactions",
        "description": "Filtered transactions by date range, category, merchant, amount range or direction. Returns the matched total and a sample of rows.",
        "parameters": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Inclusive start date, YYYY-MM-DD."},
                "end": {"type": "string", "description": "Inclusive end date, YYYY-MM-DD."},
                "category_slug": _STR,
                "merchant": {"type": "string", "description": "Substring match on merchant name."},
                "min_amount_paise": _INT,
                "max_amount_paise": _INT,
                "direction": {"type": "string", "enum": ["DEBIT", "CREDIT"]},
            },
        },
    },
    {
        "name": "get_category_breakdown",
        "description": "Spending totals per category for one month, ranked highest first. Use this for 'where did I spend the most'.",
        "parameters": {
            "type": "object",
            "properties": {"period": {"type": "string", "description": "Month as YYYY-MM. Defaults to the latest month with data."}},
        },
    },
    {
        "name": "compare_periods",
        "description": "Per-category spending deltas between two months, absolute and percentage.",
        "parameters": {
            "type": "object",
            "properties": {"period_a": {"type": "string", "description": "Baseline month, YYYY-MM."}, "period_b": {"type": "string", "description": "Comparison month, YYYY-MM."}},
            "required": ["period_a", "period_b"],
        },
    },
    {
        "name": "list_recurring",
        "description": "All detected recurring series with cadence, amount, mandate channel and AFA band. Use for questions about subscriptions and auto-debits.",
        "parameters": {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["ACTIVE", "PROBABLE", "LAPSED"]}},
        },
    },
    {
        "name": "get_upcoming_obligations",
        "description": "Forward schedule of expected debits over the next N days.",
        "parameters": {"type": "object", "properties": {"days": _INT}},
    },
    {
        "name": "get_budget_status",
        "description": "Per-category budget versus actual spend with a pace verdict.",
        "parameters": {"type": "object", "properties": {"period": {"type": "string", "description": "Month as YYYY-MM."}}},
    },
    {
        "name": "get_goal_projection",
        "description": "Each savings goal's ETA, required monthly contribution and verdict.",
        "parameters": {"type": "object", "properties": {"goal_id": _STR}},
    },
    {
        "name": "detect_anomalies",
        "description": "Unusual activity: category spikes, duplicate charges, price hikes, new large merchants and silent mandates.",
        "parameters": {"type": "object", "properties": {"period": {"type": "string", "description": "Month as YYYY-MM."}}},
    },
    {
        "name": "simulate_scenario",
        "description": "What-if: cancel recurring series, change category spending by a percentage, or add a one-off purchase, and see the effect on every goal's ETA. Use this for affordability questions.",
        "parameters": {
            "type": "object",
            "properties": {
                "cancel_series": {"type": "array", "items": _STR, "description": "Series keys from list_recurring."},
                "category_pct_change": {"type": "object", "description": "Map of category_slug to percentage change, e.g. -20 for a 20% cut."},
                "one_off_amount_paise": _INT,
                "one_off_category_slug": _STR,
            },
        },
    },
    {
        "name": "get_safe_to_spend",
        "description": "Committed spend before the next income date, discretionary remainder and the safe daily allowance.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "search_documents",
        "description": "Search uploaded statement and bill documents by filename or bank.",
        "parameters": {"type": "object", "properties": {"query": _STR}, "required": ["query"]},
    },
]

TOOLS: dict[str, Callable[..., ToolResult]] = {
    "query_transactions": query_transactions,
    "get_category_breakdown": get_category_breakdown,
    "compare_periods": compare_periods,
    "list_recurring": list_recurring,
    "get_upcoming_obligations": get_upcoming_obligations,
    "get_budget_status": get_budget_status,
    "get_goal_projection": get_goal_projection,
    "detect_anomalies": detect_anomalies,
    "simulate_scenario": simulate_scenario,
    "get_safe_to_spend": get_safe_to_spend,
    "search_documents": search_documents,
}

assert {d["name"] for d in TOOL_DECLARATIONS} == set(TOOLS), "declarations and implementations drifted"


def dispatch(name: str, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Run one tool call and return its JSON-safe result.

    Every failure mode returns a structured ``error`` rather than raising, so
    the loop can hand it back to the model as a tool response and let it
    recover — a tool that 500s mid-conversation ends the turn with nothing.
    """
    fn = TOOLS.get(name)
    if fn is None:
        return {"error": f"No such tool: {name}"}
    try:
        return fn(ctx, **(args or {})).as_dict()
    except NoDataError as exc:
        return {"error": str(exc), "no_data": True}
    except (TypeError, ValueError, KeyError) as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
