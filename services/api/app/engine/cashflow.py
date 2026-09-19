"""Cash-flow, committed spend and Safe-to-Spend.

Implements DESIGN.md section 8.3. `safe_to_spend` is the literal answer to the
problem statement's "How much of my budget is already committed?" (coverage
matrix row 11d), so it returns the full forward schedule and citations rather
than a bare number: the UI renders a runway, and the agent cites the
individual obligations it summed.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta

from .types import (
    Citation,
    Direction,
    Goal,
    MonthlySummary,
    Obligation,
    RecurringSeries,
    SafeToSpend,
    SeriesStatus,
    Txn,
)

#: Default forward window for the radar and obligation schedule.
DEFAULT_HORIZON_DAYS = 30


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _add_months(value: date, months: int) -> date:
    total = value.month - 1 + months
    year = value.year + total // 12
    month = total % 12 + 1
    if month == 12:
        next_first = date(year + 1, 1, 1)
    else:
        next_first = date(year, month + 1, 1)
    last_day = (next_first - timedelta(days=1)).day
    return date(year, month, min(value.day, last_day))


def _occurrences(
    series: RecurringSeries, *, start: date, until: date
) -> list[date]:
    """Expected dates for a series within [start, until].

    `next_expected_date` is defined in DESIGN.md section 8.1 as
    `last_seen + median_gap`, which may already be in the past for a series
    detected from stale data. Rolling forward belongs here, in the forward
    projection, rather than mutating the detected series.
    """
    step = max(1, int(round(series.median_gap_days)))
    cursor = series.next_expected_date
    while cursor < start:
        cursor = cursor + timedelta(days=step)
    dates: list[date] = []
    while cursor <= until:
        dates.append(cursor)
        cursor = cursor + timedelta(days=step)
    return dates


def upcoming(
    series: Sequence[RecurringSeries],
    *,
    days: int = DEFAULT_HORIZON_DAYS,
    as_of: date | None = None,
) -> list[Obligation]:
    """Forward schedule of expected debits over the next `days` days.

    Satisfies coverage-matrix row 6, "identify upcoming recurring obligations".
    """
    reference = as_of or date.today()
    horizon = reference + timedelta(days=days)

    obligations: list[Obligation] = []
    for item in series:
        if item.status is not SeriesStatus.ACTIVE:
            continue
        if item.direction is not Direction.DEBIT:
            continue
        for due in _occurrences(item, start=reference, until=horizon):
            obligations.append(
                Obligation(
                    series_key=item.key,
                    normalized_merchant=item.normalized_merchant,
                    category_slug=item.category_slug,
                    due_date=due,
                    amount_paise=item.median_amount_paise,
                    afa_band=item.afa_band,
                    mandate_channel=item.mandate_channel,
                    acknowledged=item.acknowledged,
                )
            )
    obligations.sort(key=lambda o: (o.due_date, o.normalized_merchant))
    return obligations


def next_income(
    series: Sequence[RecurringSeries], *, as_of: date | None = None
) -> tuple[date | None, int]:
    """(date, amount_paise) of the next expected income credit.

    The salary series is the largest active recurring CREDIT. Picking by
    amount rather than by cadence avoids mistaking a small recurring refund
    or interest credit for the pay cheque.
    """
    reference = as_of or date.today()
    credits = [
        s
        for s in series
        if s.direction is Direction.CREDIT and s.status is SeriesStatus.ACTIVE
    ]
    if not credits:
        return None, 0
    salary = max(credits, key=lambda s: s.median_amount_paise)
    step = max(1, int(round(salary.median_gap_days)))
    cursor = salary.next_expected_date
    while cursor <= reference:
        cursor = cursor + timedelta(days=step)
    return cursor, salary.median_amount_paise


def safe_to_spend(
    series: Sequence[RecurringSeries],
    goals: Sequence[Goal] = (),
    *,
    current_balance_paise: int,
    as_of: date | None = None,
    txns: Sequence[Txn] = (),
) -> SafeToSpend:
    """Committed spend and a safe daily allowance until the next pay day.

    Follows DESIGN.md section 8.3 exactly:

        committed   = sum of obligations due strictly before next_income_date
        goal_due    = sum of monthly contributions not yet funded this month
        discretionary = balance - committed - goal_due
        safe_daily  = max(0, discretionary // days_remaining)
    """
    reference = as_of or date.today()
    income_date, income_paise = next_income(series, as_of=reference)

    # With no detected salary series there is no pay-day anchor. Fall back to
    # the end of the current month so the figure stays meaningful rather than
    # undefined, and report next_income_date as None so the UI can say so.
    horizon_end = income_date or _add_months(_month_start(reference), 1)

    window_days = max(1, (horizon_end - reference).days)
    all_obligations = upcoming(series, days=window_days, as_of=reference)
    # "due strictly before next_income_date"
    obligations = tuple(o for o in all_obligations if o.due_date < horizon_end)
    committed = sum(o.amount_paise for o in obligations)

    month_start = _month_start(reference)
    funded_this_month: set[str] = set()
    for txn in txns:
        if txn.direction is Direction.DEBIT and txn.txn_date >= month_start:
            funded_this_month.add(txn.normalized_merchant)
    goal_due = sum(
        g.monthly_contribution_paise
        for g in goals
        if g.current_paise < g.target_paise and g.name not in funded_this_month
    )

    discretionary = current_balance_paise - committed - goal_due
    days_remaining = max(1, (horizon_end - reference).days)
    safe_daily = max(0, discretionary // days_remaining)

    by_series: dict[str, list[Obligation]] = defaultdict(list)
    for obligation in obligations:
        by_series[obligation.series_key].append(obligation)
    series_txn_ids = {s.key: s.txn_ids for s in series}
    citations = tuple(
        Citation(
            label=f"{group[0].normalized_merchant} x{len(group)}",
            value_paise=sum(o.amount_paise for o in group),
            txn_ids=series_txn_ids.get(key, ()),
        )
        for key, group in sorted(
            by_series.items(), key=lambda kv: -sum(o.amount_paise for o in kv[1])
        )
    )

    return SafeToSpend(
        as_of=reference,
        next_income_date=income_date,
        next_income_paise=income_paise,
        current_balance_paise=current_balance_paise,
        committed_paise=committed,
        goal_due_paise=goal_due,
        discretionary_paise=discretionary,
        days_remaining=days_remaining,
        safe_daily_paise=safe_daily,
        obligations=obligations,
        citations=citations,
    )


def monthly_summary(txns: Sequence[Txn], *, month: date) -> MonthlySummary:
    """Income, expense, net and per-category totals for one month.

    Satisfies coverage-matrix row 5, "summarise monthly income and expenses".
    """
    start = _month_start(month)
    end = _add_months(start, 1)
    in_month = [t for t in txns if start <= t.txn_date < end]

    income = sum(t.amount_paise for t in in_month if t.direction is Direction.CREDIT)
    expense = sum(t.amount_paise for t in in_month if t.direction is Direction.DEBIT)
    net = income - expense

    by_category: dict[str, int] = defaultdict(int)
    for txn in in_month:
        if txn.direction is Direction.DEBIT:
            by_category[txn.category_slug] += txn.amount_paise

    savings_rate = round((net / income) * 100, 2) if income else 0.0

    return MonthlySummary(
        month=start,
        income_paise=income,
        expense_paise=expense,
        net_paise=net,
        savings_rate_pct=savings_rate,
        by_category_paise=dict(sorted(by_category.items(), key=lambda kv: -kv[1])),
        txn_count=len(in_month),
    )


def category_breakdown(
    txns: Sequence[Txn], *, start: date, end: date
) -> list[tuple[str, int, tuple[str, ...]]]:
    """(category_slug, total_paise, txn_ids) ranked by spend, for citations."""
    by_category: dict[str, list[Txn]] = defaultdict(list)
    for txn in txns:
        if txn.direction is Direction.DEBIT and start <= txn.txn_date <= end:
            by_category[txn.category_slug].append(txn)
    rows = [
        (slug, sum(t.amount_paise for t in group), tuple(t.id for t in group))
        for slug, group in by_category.items()
    ]
    rows.sort(key=lambda r: -r[1])
    return rows


def monthly_surplus(txns: Sequence[Txn], *, as_of: date, months: int = 3) -> int:
    """Median of (income - expense) over the last `months` complete months.

    DESIGN.md section 8.5's `projected_surplus`. Median, not mean, so one
    festival month does not drag the projection down (section 8.2's rule
    applied consistently).
    """
    from .stats import median_int

    current_month = _month_start(as_of)
    nets: list[int] = []
    for offset in range(1, months + 1):
        month = _add_months(current_month, -offset)
        summary = monthly_summary(txns, month=month)
        if summary.txn_count == 0:
            continue
        nets.append(summary.net_paise)
    if not nets:
        return 0
    return median_int(nets)
