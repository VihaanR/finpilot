"""Goal projection.

Implements DESIGN.md section 8.5 and coverage-matrix rows 8 and 9. The engine
reports arithmetic and a verdict. It never says what to do about it: that is
the advice boundary of DESIGN.md section 3.1, enforced here by simply not
having an opinion to express.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta

from .cashflow import monthly_surplus
from .stats import ceil_div
from .types import Goal, GoalProjection, GoalVerdict, Txn

#: Cap on how far out an ETA is projected before we call it unreachable.
MAX_PROJECTION_MONTHS = 600


def _month_start(value: date) -> date:
    return value.replace(day=1)


def add_months(value: date, months: int) -> date:
    total = value.month - 1 + months
    year = value.year + total // 12
    month = total % 12 + 1
    if month == 12:
        next_first = date(year + 1, 1, 1)
    else:
        next_first = date(year, month + 1, 1)
    last_day = (next_first - timedelta(days=1)).day
    return date(year, month, min(value.day, last_day))


def months_between(start: date, end: date) -> int:
    """Whole months from `start` to `end`. Negative when `end` precedes it."""
    return (end.year - start.year) * 12 + (end.month - start.month)


def allocate(
    goals: Sequence[Goal], surplus_paise: int
) -> dict[str, int]:
    """Split the monthly surplus across goals by priority.

    Each unfunded goal first receives its planned monthly contribution, in
    priority order, as far as the surplus stretches. Anything left over is
    pushed onto the highest-priority goal still short of its target, so that
    freeing up money (cancelling a subscription, say) actually moves an ETA
    rather than disappearing into an unallocated remainder. That behaviour is
    what makes the What-If Simulator in DESIGN.md section 10.4 meaningful.
    """
    ordered = sorted(goals, key=lambda g: (g.priority, g.target_date, g.id))
    unfunded = [g for g in ordered if g.current_paise < g.target_paise]

    allocation = {g.id: 0 for g in goals}
    remaining = max(0, surplus_paise)

    for goal in unfunded:
        if remaining <= 0:
            break
        take = min(goal.monthly_contribution_paise, remaining)
        allocation[goal.id] = take
        remaining -= take

    if remaining > 0 and unfunded:
        allocation[unfunded[0].id] += remaining

    return allocation


def project(
    goals: Sequence[Goal],
    txns: Sequence[Txn] = (),
    *,
    as_of: date | None = None,
    surplus_paise: int | None = None,
) -> list[GoalProjection]:
    """Project every goal's ETA and verdict.

    `surplus_paise` overrides the computed median surplus. The simulator uses
    that to re-run the same arithmetic under a modified scenario, so both
    paths share one implementation and cannot drift apart.
    """
    reference = as_of or date.today()
    surplus = (
        surplus_paise
        if surplus_paise is not None
        else monthly_surplus(txns, as_of=reference)
    )
    allocation = allocate(goals, surplus)

    projections: list[GoalProjection] = []
    for goal in sorted(goals, key=lambda g: (g.priority, g.target_date, g.id)):
        shortfall = max(0, goal.target_paise - goal.current_paise)
        months_remaining = max(0, months_between(reference, goal.target_date))
        required_monthly = (
            ceil_div(shortfall, months_remaining) if months_remaining > 0 else shortfall
        )
        allocated = allocation.get(goal.id, 0)

        if shortfall == 0:
            eta: date | None = reference
            months_needed = 0
        elif allocated <= 0:
            eta = None
            months_needed = MAX_PROJECTION_MONTHS
        else:
            months_needed = ceil_div(shortfall, allocated)
            if months_needed > MAX_PROJECTION_MONTHS:
                eta = None
            else:
                eta = add_months(_month_start(reference), months_needed)

        if eta is None:
            verdict = GoalVerdict.UNREACHABLE
            months_delta = MAX_PROJECTION_MONTHS
        else:
            months_delta = months_between(goal.target_date, eta)
            if months_delta >= 1:
                verdict = GoalVerdict.BEHIND
            elif months_delta <= -1:
                verdict = GoalVerdict.AHEAD
            else:
                verdict = GoalVerdict.ON_TRACK

        projections.append(
            GoalProjection(
                goal_id=goal.id,
                name=goal.name,
                target_paise=goal.target_paise,
                current_paise=goal.current_paise,
                shortfall_paise=shortfall,
                target_date=goal.target_date,
                months_remaining=months_remaining,
                required_monthly_paise=required_monthly,
                allocated_monthly_paise=allocated,
                projected_eta=eta,
                months_delta=months_delta,
                verdict=verdict,
            )
        )
    return projections
