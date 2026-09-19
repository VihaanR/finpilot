"""Budget vs actual, with a pace verdict.

Implements DESIGN.md section 8.4 and coverage-matrix row 7, "compare actual
spending against budgets". The pace verdict distinguishes *already over* from
*on course to go over*, which is the difference between a post-mortem and a
warning a user can still act on.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta

from .types import Budget, BudgetStatus, Direction, PaceVerdict, Txn

#: Spending at or below this fraction of the linear pace counts as AHEAD.
AHEAD_MARGIN = 0.90


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _days_in_month(value: date) -> int:
    first = _month_start(value)
    if first.month == 12:
        next_first = date(first.year + 1, 1, 1)
    else:
        next_first = date(first.year, first.month + 1, 1)
    return (next_first - first).days


def status(
    budgets: Sequence[Budget],
    txns: Sequence[Txn],
    *,
    as_of: date | None = None,
) -> list[BudgetStatus]:
    """Per-category budget status for the month containing `as_of`."""
    reference = as_of or date.today()
    period_start = _month_start(reference)
    days_in_period = _days_in_month(reference)
    period_end = period_start + timedelta(days=days_in_period - 1)
    days_elapsed = min(days_in_period, max(1, (reference - period_start).days + 1))

    spend: dict[str, list[Txn]] = defaultdict(list)
    for txn in txns:
        if txn.direction is Direction.DEBIT and period_start <= txn.txn_date <= period_end:
            spend[txn.category_slug].append(txn)

    rows: list[BudgetStatus] = []
    for budget in budgets:
        matched = spend.get(budget.category_slug, [])
        spent = sum(t.amount_paise for t in matched)
        remaining = budget.limit_paise - spent
        pct_used = round((spent / budget.limit_paise) * 100, 2) if budget.limit_paise else 0.0
        projected = int(round(spent / days_elapsed * days_in_period))
        expected_by_now = budget.limit_paise * days_elapsed / days_in_period

        if spent > budget.limit_paise:
            pace = PaceVerdict.OVER
        elif projected > budget.limit_paise:
            pace = PaceVerdict.PROJECTED_OVER
        elif spent <= expected_by_now * AHEAD_MARGIN:
            pace = PaceVerdict.AHEAD
        else:
            pace = PaceVerdict.ON_PACE

        rows.append(
            BudgetStatus(
                category_slug=budget.category_slug,
                limit_paise=budget.limit_paise,
                spent_paise=spent,
                remaining_paise=remaining,
                pct_used=pct_used,
                days_elapsed=days_elapsed,
                days_in_period=days_in_period,
                projected_spend_paise=projected,
                pace=pace,
                txn_ids=tuple(t.id for t in matched),
            )
        )

    rows.sort(key=lambda r: -r.pct_used)
    return rows
