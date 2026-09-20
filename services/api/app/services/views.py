"""View assembly: engine output shaped for the API.

The engine returns frozen dataclasses in paise. The routes return JSON. This
module is the only place that converts between them, so there is exactly one
definition of what "a radar row" or "the dashboard" means.

Money stays integer paise all the way out to the browser. Formatting to
Rs 1,234.56 happens once, in the `Money` component (DESIGN.md 5.1).
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, is_dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Any, Sequence

from ..engine import anomaly, budget, cashflow, goals as goals_engine, recurrence, simulate
from ..engine.types import (
    AfaBand,
    Anomaly,
    Cadence,
    Direction,
    Goal,
    MandateChannel,
    RecurringSeries,
    Scenario,
    SeriesStatus,
    Txn,
)
from ..models.taxonomy import display_name, group_of, is_income_slug
from ..store.db import Store

#: Seven days, where RBI requires one. The gap is the product's clearest claim
#: (DESIGN.md 10.1), so it is a named constant rather than a literal.
PRE_DEBIT_BANNER_DAYS = 7
RADAR_HORIZON_DAYS = 30


def jsonable(value: Any) -> Any:
    """Frozen dataclasses, enums and dates -> JSON-safe primitives."""
    if is_dataclass(value) and not isinstance(value, type):
        return {k: jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


# --- Snapshot ---------------------------------------------------------------


class Snapshot:
    """One computation of everything, reused across a request.

    Recurrence and anomaly detection are the expensive steps; running them once
    per request rather than once per endpoint keeps the dashboard a single pass
    over the ledger.
    """

    def __init__(self, store: Store, *, as_of: date | None = None) -> None:
        self.store = store
        self.txns: tuple[Txn, ...] = store.engine_txns()
        self.as_of = as_of or (max(t.txn_date for t in self.txns) if self.txns else date.today())
        self.acknowledged = store.acknowledged()
        self.dismissed = store.dismissed()
        self.goals: tuple[Goal, ...] = store.goals()
        self.budgets = store.budgets()

        raw_series = recurrence.detect(self.txns, as_of=self.as_of)
        self.series: tuple[RecurringSeries, ...] = tuple(
            _with_acknowledgement(s, s.key in self.acknowledged) for s in raw_series
        )
        self.anomalies: tuple[Anomaly, ...] = tuple(
            a
            for a in anomaly.detect(self.txns, self.series, period=self.as_of)
            if anomaly_key(a) not in self.dismissed
        )

    @property
    def balance_paise(self) -> int:
        """Spendable cash only.

        A credit card's running balance is money *owed*, not money held, and
        the statement reports it as a growing negative. Summing it with savings
        would net a liability against cash and understate Safe-to-Spend by the
        whole card outstanding.
        """
        return sum(
            int(a["current_balance_paise"])
            for a in self.store.accounts()
            if str(a["account_type"]).upper() != "CREDIT_CARD"
        )

    @property
    def card_outstanding_paise(self) -> int:
        """Owed on credit cards, as a positive number."""
        return sum(
            abs(int(a["current_balance_paise"]))
            for a in self.store.accounts()
            if str(a["account_type"]).upper() == "CREDIT_CARD"
        )

    @property
    def active_series(self) -> list[RecurringSeries]:
        return [s for s in self.series if s.status == SeriesStatus.ACTIVE]

    def safe_to_spend(self):
        return cashflow.safe_to_spend(
            self.series,
            self.goals,
            current_balance_paise=self.balance_paise,
            as_of=self.as_of,
            txns=self.txns,
        )


def _with_acknowledgement(series: RecurringSeries, acknowledged: bool) -> RecurringSeries:
    if series.acknowledged == acknowledged:
        return series
    return RecurringSeries(
        **{**{f: getattr(series, f) for f in series.__dataclass_fields__},
           "acknowledged": acknowledged}
    )


def anomaly_key(item: Anomaly) -> str:
    """Stable identity for dismissal, without persisting the anomaly itself.

    The transaction digest is load-bearing, not decoration: two category spikes
    in the same month share a type, a period and a null series key, so without
    it they collide and dismissing one dismisses both.
    """
    digest = hashlib.sha256("|".join(sorted(item.txn_ids)).encode()).hexdigest()[:8]
    return "{0}:{1}:{2}:{3}".format(
        item.type.value, item.series_key or "", item.period_start.isoformat(), digest
    )


# --- Radar badges -----------------------------------------------------------

_TOOLTIPS = {
    "SILENT": (
        "Under RBI rules, recurring debits up to Rs 15,000 need no OTP. "
        "This will debit without asking you."
    ),
    "HIGH_LIMIT": (
        "Insurance, SIP and credit-card mandates can debit up to Rs 1,00,000 "
        "without additional authentication."
    ),
    "DORMANT": (
        "This mandate has been charging for months and the only activity with "
        "this merchant is the debit itself."
    ),
}

#: A subscription whose *only* relationship with the user is the auto-debit.
#: Bank data carries no usage signal, so this is the closest observable proxy:
#: many charges, no other interaction. Stated plainly in the tooltip rather
#: than dressed up as knowledge we do not have.
#:
#: Restricted to subscriptions on purpose. Rent, EMIs, SIPs and utility
#: mandates are *also* pure auto-debits with no side activity — that is what a
#: mandate is — so applying this test to them would label the user's entire
#: fixed-cost base dormant and say nothing.
DORMANT_MIN_OCCURRENCES = 6
DORMANT_CATEGORIES = frozenset({"subscriptions"})


def badges_for(
    series: RecurringSeries,
    *,
    all_series: Sequence[RecurringSeries],
    txns: Sequence[Txn],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    if series.afa_band == AfaBand.SILENT:
        out.append({"code": "SILENT", "label": "Silent", "tone": "warn",
                    "tooltip": _TOOLTIPS["SILENT"]})
    elif series.afa_band == AfaBand.HIGH_LIMIT:
        out.append({"code": "HIGH_LIMIT", "label": "High limit", "tone": "warn",
                    "tooltip": _TOOLTIPS["HIGH_LIMIT"]})

    rise = _price_rise(series)
    if rise:
        old, new, effective, pct = rise
        out.append({
            "code": "PRICE_UP",
            "label": "Price up {0}%".format(pct),
            "tone": "alert",
            "tooltip": "Went from Rs {0:,} to Rs {1:,} on {2}.".format(
                old // 100, new // 100, effective.strftime("%d %b %Y")
            ),
        })

    twin = _duplicate_twin(series, all_series)
    if twin is not None:
        out.append({
            "code": "DUPLICATE",
            "label": "Duplicate",
            "tone": "alert",
            "tooltip": "Also active: {0} at Rs {1:,} a month.".format(
                twin.normalized_merchant, twin.median_amount_paise // 100
            ),
        })

    trial = _trial_conversion(series, txns)
    if trial is not None:
        first_amount, converted_on = trial
        out.append({
            "code": "TRIAL_TO_PAID",
            "label": "Trial to paid",
            "tone": "warn",
            "tooltip": "Started at Rs {0:,} and moved to Rs {1:,} on {2}.".format(
                first_amount // 100,
                series.median_amount_paise // 100,
                converted_on.strftime("%d %b %Y"),
            ),
        })

    if _is_dormant(series, txns):
        out.append({"code": "DORMANT", "label": "Dormant", "tone": "muted",
                    "tooltip": _TOOLTIPS["DORMANT"]})

    return out


def _price_rise(series: RecurringSeries) -> tuple[int, int, date, int] | None:
    if len(series.price_history) < 2:
        return None
    first, last = series.price_history[0], series.price_history[-1]
    if last.amount_paise <= first.amount_paise or first.amount_paise <= 0:
        return None
    pct = round((last.amount_paise - first.amount_paise) * 100 / first.amount_paise)
    return first.amount_paise, last.amount_paise, last.effective_from, pct


def _duplicate_twin(
    series: RecurringSeries, all_series: Sequence[RecurringSeries]
) -> RecurringSeries | None:
    if series.status != SeriesStatus.ACTIVE or not series.service_type:
        return None
    for other in all_series:
        if other.key == series.key or other.status != SeriesStatus.ACTIVE:
            continue
        if other.service_type == series.service_type:
            return other
    return None


def _trial_conversion(
    series: RecurringSeries, txns: Sequence[Txn]
) -> tuple[int, date] | None:
    members = sorted(
        (t for t in txns if t.id in set(series.txn_ids)), key=lambda t: t.txn_date
    )
    if len(members) < 3:
        return None
    first = members[0]
    # "Much less than the median" rather than "different": a trial is an order
    # of magnitude below the real price, not a rounding difference.
    if first.amount_paise * 4 > series.median_amount_paise:
        return None
    return first.amount_paise, members[1].txn_date


def _is_dormant(series: RecurringSeries, txns: Sequence[Txn]) -> bool:
    if series.status != SeriesStatus.ACTIVE:
        return False
    if (series.category_slug or "") not in DORMANT_CATEGORIES:
        return False
    if series.occurrence_count < DORMANT_MIN_OCCURRENCES:
        return False
    member_ids = set(series.txn_ids)
    for txn in txns:
        if txn.id in member_ids:
            continue
        if txn.normalized_merchant == series.normalized_merchant:
            return False
    return True


# --- Revoke kit -------------------------------------------------------------

_REVOKE_STEPS: dict[MandateChannel, tuple[str, ...]] = {
    MandateChannel.UPI_AUTOPAY: (
        "Open your UPI app (GPay, PhonePe, Paytm or your bank app).",
        "Go to Autopay or Mandates.",
        "Find the mandate for this merchant.",
        "Choose Pause or Revoke.",
    ),
    MandateChannel.NACH: (
        "Log in to your bank's net banking.",
        "Open e-Mandate or NACH mandate management.",
        "Locate the mandate for this merchant and cancel it.",
        "Cancellation takes effect after the current cycle, so check the next due date.",
    ),
    MandateChannel.CARD_EMANDATE: (
        "Log in to your card issuer's portal or app.",
        "Open Manage standing instructions or Recurring payments.",
        "Cancel the instruction for this merchant.",
    ),
    MandateChannel.SI: (
        "Log in to your bank's net banking.",
        "Open Standing Instructions.",
        "Cancel the instruction for this merchant.",
    ),
    MandateChannel.MANUAL: (
        "This one is not an automatic mandate — you pay it yourself.",
        "To stop it, cancel directly with the merchant.",
    ),
    MandateChannel.UNKNOWN: (
        "We could not tell which rail this mandate uses.",
        "Check your UPI app's Autopay list and your bank's e-Mandate page.",
    ),
}


def revoke_kit(series: RecurringSeries) -> dict[str, Any]:
    steps = _REVOKE_STEPS.get(series.mandate_channel, _REVOKE_STEPS[MandateChannel.UNKNOWN])
    email = (
        "Subject: Cancellation of recurring payment - {merchant}\n\n"
        "Hello,\n\n"
        "I want to cancel the recurring payment set up on my account with "
        "{merchant}, currently charged at Rs {amount:,} {cadence}.\n\n"
        "Please confirm the cancellation in writing and tell me the date of the "
        "final charge.\n\n"
        "Thank you."
    ).format(
        merchant=series.normalized_merchant.title(),
        amount=series.median_amount_paise // 100,
        cadence=series.cadence.value.lower().replace("_", "-"),
    )
    return {"channel": series.mandate_channel.value, "steps": list(steps), "email_template": email}


# --- Leak Score -------------------------------------------------------------

#: Deductions from 100, each capped. Weighted by how much money the problem
#: actually costs: a duplicate subscription is a standing charge, while an
#: unacknowledged silent mandate is mostly an awareness gap.
#:
#: The caps are what make the score mean anything. Silent mandates are an
#: inventory, not an alert list — a household with rent, two EMIs, a SIP and
#: nine subscriptions legitimately has twenty of them, and an uncapped
#: per-item deduction would pin every real user at zero and make the gauge
#: useless for showing improvement.
LEAK_WEIGHTS = {
    "duplicate_subscription": 12,
    "unacknowledged_silent": 3,
    "recent_price_hike": 8,
    "dormant_series": 5,
}
LEAK_CAPS = {
    "duplicate_subscription": 36,
    "unacknowledged_silent": 15,
    "recent_price_hike": 24,
    "dormant_series": 15,
}
PRICE_HIKE_LOOKBACK_DAYS = 182


def leak_score(snapshot: Snapshot) -> dict[str, Any]:
    active = snapshot.active_series
    txns = snapshot.txns

    seen_types: set[str] = set()
    duplicates = 0
    for series in active:
        if series.service_type and series.service_type in seen_types:
            duplicates += 1
        elif series.service_type:
            seen_types.add(series.service_type)

    unacknowledged = sum(
        1 for s in active if s.afa_band == AfaBand.SILENT and not s.acknowledged
    )
    cutoff = snapshot.as_of - timedelta(days=PRICE_HIKE_LOOKBACK_DAYS)
    hikes = sum(
        1
        for s in snapshot.series
        if (rise := _price_rise(s)) is not None and rise[2] >= cutoff
    )
    dormant = sum(1 for s in active if _is_dormant(s, txns))

    def deduct(reason_key: str, count: int) -> int:
        return min(count * LEAK_WEIGHTS[reason_key], LEAK_CAPS[reason_key])

    contributions = [
        {"reason": "Duplicate subscriptions", "count": duplicates,
         "deduction": deduct("duplicate_subscription", duplicates)},
        {"reason": "Silent mandates you have not acknowledged", "count": unacknowledged,
         "deduction": deduct("unacknowledged_silent", unacknowledged)},
        {"reason": "Price rises in the last 6 months", "count": hikes,
         "deduction": deduct("recent_price_hike", hikes)},
        {"reason": "Dormant subscriptions", "count": dormant,
         "deduction": deduct("dormant_series", dormant)},
    ]
    total = min(sum(c["deduction"] for c in contributions), 100)
    score = max(0, 100 - total)

    if score >= 80:
        band, label = "good", "Tight"
    elif score >= 55:
        band, label = "fair", "Some leaks"
    else:
        band, label = "poor", "Leaking"

    return {
        "score": score,
        "band": band,
        "label": label,
        "contributions": [c for c in contributions if c["count"]],
    }


# --- Radar ------------------------------------------------------------------


def radar(snapshot: Snapshot) -> dict[str, Any]:
    obligations = cashflow.upcoming(
        snapshot.series, days=RADAR_HORIZON_DAYS, as_of=snapshot.as_of
    )
    by_key = {s.key: s for s in snapshot.series}

    weeks: dict[int, list[dict[str, Any]]] = {}
    for item in obligations:
        series = by_key.get(item.series_key)
        if series is None:
            continue
        offset = (item.due_date - snapshot.as_of).days
        week = max(0, offset // 7)
        weeks.setdefault(week, []).append(
            {
                "series_key": series.key,
                "merchant": series.normalized_merchant,
                "category_slug": series.category_slug,
                "category_name": display_name(series.category_slug or "uncategorised"),
                "due_date": item.due_date.isoformat(),
                "days_away": offset,
                "amount_paise": item.amount_paise,
                "cadence": series.cadence.value,
                "mandate_channel": series.mandate_channel.value,
                "afa_band": series.afa_band.value,
                "acknowledged": series.acknowledged,
                "within_banner": offset <= PRE_DEBIT_BANNER_DAYS,
                "badges": badges_for(series, all_series=snapshot.series, txns=snapshot.txns),
                "revoke_kit": revoke_kit(series),
                "txn_ids": list(series.txn_ids),
            }
        )

    imminent = [row for rows in weeks.values() for row in rows if row["within_banner"]]
    return {
        "as_of": snapshot.as_of.isoformat(),
        "horizon_days": RADAR_HORIZON_DAYS,
        "banner_days": PRE_DEBIT_BANNER_DAYS,
        "weeks": [
            {
                "week": week,
                "starts_on": (snapshot.as_of + timedelta(days=week * 7)).isoformat(),
                "items": sorted(rows, key=lambda r: r["due_date"]),
                "total_paise": sum(r["amount_paise"] for r in rows),
            }
            for week, rows in sorted(weeks.items())
        ],
        "banner": {
            "count": len(imminent),
            "total_paise": sum(r["amount_paise"] for r in imminent),
            "items": sorted(imminent, key=lambda r: r["due_date"]),
        },
        "series": [
            {
                **jsonable(series),
                "category_name": display_name(series.category_slug or "uncategorised"),
                "badges": badges_for(series, all_series=snapshot.series, txns=snapshot.txns),
                "revoke_kit": revoke_kit(series),
            }
            for series in snapshot.series
        ],
        "leak_score": leak_score(snapshot),
    }


# --- Dashboard --------------------------------------------------------------


def dashboard(snapshot: Snapshot) -> dict[str, Any]:
    as_of = snapshot.as_of
    month_start = as_of.replace(day=1)
    summary = cashflow.monthly_summary(snapshot.txns, month=month_start)
    breakdown = cashflow.category_breakdown(
        snapshot.txns, start=month_start, end=as_of
    )
    sts = snapshot.safe_to_spend()

    trend: list[dict[str, Any]] = []
    cursor = month_start
    for _ in range(6):
        month = cashflow.monthly_summary(snapshot.txns, month=cursor)
        trend.append(
            {
                "month": cursor.isoformat(),
                "income_paise": month.income_paise,
                "expense_paise": month.expense_paise,
                "net_paise": month.net_paise,
            }
        )
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    trend.reverse()

    return {
        "as_of": as_of.isoformat(),
        "accounts": snapshot.store.accounts(),
        "balance_paise": snapshot.balance_paise,
        "safe_to_spend": jsonable(sts),
        "month": {
            "month": summary.month.isoformat(),
            "income_paise": summary.income_paise,
            "expense_paise": summary.expense_paise,
            "net_paise": summary.net_paise,
            "savings_rate_pct": summary.savings_rate_pct,
            "txn_count": summary.txn_count,
        },
        "trend": trend,
        "categories": [
            {
                "category_slug": slug,
                "category_name": display_name(slug),
                "group": group_of(slug),
                "amount_paise": amount,
                "txn_ids": list(txn_ids),
            }
            for slug, amount, txn_ids in breakdown
            if not is_income_slug(slug)
        ],
        "anomalies": [
            {**jsonable(item), "key": anomaly_key(item)} for item in snapshot.anomalies
        ],
        "leak_score": leak_score(snapshot),
        "budgets": [
            {**jsonable(status), "category_name": display_name(status.category_slug)}
            for status in budget.status(snapshot.budgets, snapshot.txns, as_of=as_of)
        ],
        "transaction_count": snapshot.store.transaction_count(),
    }


# --- Goals and simulation ---------------------------------------------------


def goals_view(snapshot: Snapshot) -> dict[str, Any]:
    projections = goals_engine.project(snapshot.goals, snapshot.txns, as_of=snapshot.as_of)
    surplus = cashflow.monthly_surplus(snapshot.txns, as_of=snapshot.as_of)
    cancellable = [
        {
            "series_key": s.key,
            "merchant": s.normalized_merchant,
            "category_slug": s.category_slug,
            "category_name": display_name(s.category_slug or "uncategorised"),
            "monthly_paise": simulate.monthly_equivalent_paise(s),
            "cadence": s.cadence.value,
            "service_type": s.service_type,
        }
        for s in snapshot.active_series
        if s.direction == Direction.DEBIT
    ]
    return {
        "as_of": snapshot.as_of.isoformat(),
        "monthly_surplus_paise": surplus,
        "goals": [jsonable(p) for p in projections],
        "cancellable_series": sorted(
            cancellable, key=lambda c: c["monthly_paise"], reverse=True
        ),
        "categories": sorted(
            {
                s["category_slug"]
                for s in cancellable
                if s["category_slug"]
            }
        ),
    }


def run_simulation(snapshot: Snapshot, scenario: Scenario) -> dict[str, Any]:
    result = simulate.simulate(
        snapshot.txns,
        snapshot.series,
        snapshot.goals,
        scenario,
        current_balance_paise=snapshot.balance_paise,
        as_of=snapshot.as_of,
    )
    return jsonable(result)
