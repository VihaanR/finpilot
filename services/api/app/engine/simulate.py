"""What-if scenario simulation.

Implements DESIGN.md section 8.6. Pure function of the current ledger plus a
scenario, so it is fully reproducible: the same inputs always give the same
before/after diff. Powers both the What-If Simulator (section 10.4) and the
Budget Guard interstitial (section 10.5).

The before and after branches deliberately call the same `goals.project`, so
the two halves of the diff cannot drift apart as the projection logic evolves.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import replace
from datetime import date

from .cashflow import monthly_summary, monthly_surplus, safe_to_spend
from .goals import add_months, project
from .stats import median_int
from .types import (
    Direction,
    Goal,
    GoalDiff,
    RecurringSeries,
    Scenario,
    SimulationResult,
    Txn,
)

#: Days used to express any cadence as a monthly-equivalent amount.
DAYS_PER_MONTH = 30

#: Months of history used for the per-category baseline.
CATEGORY_BASELINE_MONTHS = 3


def monthly_equivalent_paise(series: RecurringSeries) -> int:
    """A series' cost expressed per month, whatever its cadence.

    An annual Rs 12,000 mandate is Rs 1,000/month of committed spend; without
    this normalisation, cancelling it would appear to free up Rs 12,000 a month.
    """
    if series.median_gap_days <= 0:
        return series.median_amount_paise
    return int(round(series.median_amount_paise * DAYS_PER_MONTH / series.median_gap_days))


def monthly_category_spend(
    txns: Sequence[Txn], *, as_of: date, months: int = CATEGORY_BASELINE_MONTHS
) -> dict[str, int]:
    """Median monthly spend per category over the last `months` months."""
    current = as_of.replace(day=1)
    per_month: dict[str, list[int]] = defaultdict(list)
    for offset in range(1, months + 1):
        month = add_months(current, -offset)
        summary = monthly_summary(txns, month=month)
        if summary.txn_count == 0:
            continue
        for slug, total in summary.by_category_paise.items():
            per_month[slug].append(total)
    return {slug: median_int(values) for slug, values in per_month.items() if values}


def simulate(
    txns: Sequence[Txn],
    series: Sequence[RecurringSeries],
    goals: Sequence[Goal],
    scenario: Scenario,
    *,
    current_balance_paise: int,
    as_of: date | None = None,
) -> SimulationResult:
    """Before/after diff across every goal for a hypothetical change.

    The scenario may cancel recurring series, change per-category spending by
    a percentage, and add one-off purchases. Money freed or spent lands on the
    highest-priority unfunded goal, which is the same allocation rule
    `goals.allocate` uses, so the simulator and the dashboard agree.
    """
    reference = as_of or date.today()

    surplus_before = monthly_surplus(txns, as_of=reference)
    projections_before = project(goals, txns, as_of=reference, surplus_paise=surplus_before)

    # --- cancelled series free up their monthly-equivalent cost ---
    cancelled = {s.key for s in series if s.key in set(scenario.cancel_series)}
    cancelled_monthly = sum(
        monthly_equivalent_paise(s) for s in series if s.key in cancelled
    )

    # --- percentage changes per category ---
    baseline_spend = monthly_category_spend(txns, as_of=reference)
    category_delta = 0
    for slug, pct in scenario.category_pct_change.items():
        spend = baseline_spend.get(slug, 0)
        # pct is signed: -0.30 means "cut this category 30%", which raises
        # the surplus by 30% of what the category currently costs.
        category_delta += int(round(-pct * spend))

    surplus_after = surplus_before + cancelled_monthly + category_delta

    # --- one-off purchases compete with the top-priority unfunded goal ---
    one_off_total = sum(o.amount_paise for o in scenario.one_off)
    goals_after: list[Goal] = list(goals)
    if one_off_total:
        ordered = sorted(goals, key=lambda g: (g.priority, g.target_date, g.id))
        unfunded = [g for g in ordered if g.current_paise < g.target_paise]
        if unfunded:
            top = unfunded[0]
            goals_after = [
                replace(g, current_paise=max(0, g.current_paise - one_off_total))
                if g.id == top.id
                else g
                for g in goals
            ]

    projections_after = project(
        goals_after, txns, as_of=reference, surplus_paise=surplus_after
    )

    before_by_id = {p.goal_id: p for p in projections_before}
    diffs: list[GoalDiff] = []
    for after in projections_after:
        before = before_by_id.get(after.goal_id)
        if before is None:
            continue
        if before.projected_eta and after.projected_eta:
            delta = (
                (after.projected_eta.year - before.projected_eta.year) * 12
                + after.projected_eta.month
                - before.projected_eta.month
            )
        else:
            delta = 0
        diffs.append(
            GoalDiff(
                goal_id=after.goal_id,
                name=after.name,
                eta_before=before.projected_eta,
                eta_after=after.projected_eta,
                months_delta=delta,
            )
        )

    # --- Safe-to-Spend, before and after ---
    sts_before = safe_to_spend(
        series,
        goals,
        current_balance_paise=current_balance_paise,
        as_of=reference,
        txns=txns,
    )
    remaining_series = [s for s in series if s.key not in cancelled]
    sts_after = safe_to_spend(
        remaining_series,
        goals_after,
        current_balance_paise=current_balance_paise - one_off_total,
        as_of=reference,
        txns=txns,
    )

    return SimulationResult(
        goals=tuple(diffs),
        monthly_surplus_before_paise=surplus_before,
        monthly_surplus_after_paise=surplus_after,
        monthly_surplus_delta_paise=surplus_after - surplus_before,
        safe_daily_before_paise=sts_before.safe_daily_paise,
        safe_daily_after_paise=sts_after.safe_daily_paise,
        safe_daily_delta_paise=sts_after.safe_daily_paise - sts_before.safe_daily_paise,
        cancelled_monthly_paise=cancelled_monthly,
        narration_facts={
            "cancelled_count": len(cancelled),
            "one_off_total_paise": one_off_total,
            "category_delta_paise": category_delta,
        },
    )
