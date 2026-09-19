"""Budget pace tests (DESIGN.md section 8.4).

All cases sit on 10 September 2026: day 10 of a 30-day month, so the linear
pace allowance is exactly one third of the limit.
"""

from __future__ import annotations

from datetime import date

from app.engine import budget as budget_engine
from app.engine.types import Budget, PaceVerdict, rupees

from .conftest import txn

AS_OF = date(2026, 9, 10)
LIMIT = Budget(category_slug="food-delivery", limit_paise=rupees(10_000),
               period_start=date(2026, 9, 1))


def _spend(rupees_amount: int):
    return [
        txn(on=date(2026, 9, 3), amount_rupees=rupees_amount,
            merchant="SWIGGY", category="food-delivery")
    ]


class TestPaceVerdicts:
    def test_ahead_when_well_under_the_linear_pace(self):
        [row] = budget_engine.status([LIMIT], _spend(2_000), as_of=AS_OF)
        assert row.pace is PaceVerdict.AHEAD

    def test_on_pace_near_the_linear_allowance(self):
        [row] = budget_engine.status([LIMIT], _spend(3_200), as_of=AS_OF)
        assert row.pace is PaceVerdict.ON_PACE

    def test_projected_over_before_the_limit_is_breached(self):
        """The warning that still leaves the user time to act."""
        [row] = budget_engine.status([LIMIT], _spend(5_000), as_of=AS_OF)
        assert row.pace is PaceVerdict.PROJECTED_OVER
        assert row.spent_paise < row.limit_paise
        assert row.projected_spend_paise > row.limit_paise

    def test_over_once_the_limit_is_breached(self):
        [row] = budget_engine.status([LIMIT], _spend(11_000), as_of=AS_OF)
        assert row.pace is PaceVerdict.OVER
        assert row.remaining_paise < 0


class TestArithmetic:
    def test_spent_and_remaining(self):
        [row] = budget_engine.status([LIMIT], _spend(2_500), as_of=AS_OF)
        assert row.spent_paise == rupees(2_500)
        assert row.remaining_paise == rupees(7_500)

    def test_pct_used(self):
        [row] = budget_engine.status([LIMIT], _spend(2_500), as_of=AS_OF)
        assert row.pct_used == 25.0

    def test_period_days(self):
        [row] = budget_engine.status([LIMIT], _spend(2_500), as_of=AS_OF)
        assert row.days_in_period == 30
        assert row.days_elapsed == 10

    def test_projection_is_linear(self):
        """Rs 2,500 over 10 days projects to Rs 7,500 across 30."""
        [row] = budget_engine.status([LIMIT], _spend(2_500), as_of=AS_OF)
        assert row.projected_spend_paise == rupees(7_500)

    def test_transaction_ids_are_returned_for_citation(self):
        rows = _spend(2_500)
        [row] = budget_engine.status([LIMIT], rows, as_of=AS_OF)
        assert row.txn_ids == (rows[0].id,)


class TestScoping:
    def test_other_categories_are_ignored(self):
        rows = [
            txn(on=date(2026, 9, 3), amount_rupees=9_000, merchant="DMART",
                category="shopping")
        ]
        [row] = budget_engine.status([LIMIT], rows, as_of=AS_OF)
        assert row.spent_paise == 0

    def test_other_months_are_ignored(self):
        rows = [
            txn(on=date(2026, 8, 3), amount_rupees=9_000, merchant="SWIGGY",
                category="food-delivery")
        ]
        [row] = budget_engine.status([LIMIT], rows, as_of=AS_OF)
        assert row.spent_paise == 0

    def test_credits_are_ignored(self):
        from app.engine.types import Direction

        rows = [
            txn(on=date(2026, 9, 3), amount_rupees=9_000, merchant="SWIGGY",
                category="food-delivery", direction=Direction.CREDIT)
        ]
        [row] = budget_engine.status([LIMIT], rows, as_of=AS_OF)
        assert row.spent_paise == 0

    def test_rows_are_ranked_by_usage(self):
        budgets = [
            LIMIT,
            Budget(category_slug="shopping", limit_paise=rupees(10_000),
                   period_start=date(2026, 9, 1)),
        ]
        rows = _spend(2_000) + [
            txn(on=date(2026, 9, 4), amount_rupees=8_000, merchant="DMART",
                category="shopping")
        ]
        result = budget_engine.status(budgets, rows, as_of=AS_OF)
        assert [r.category_slug for r in result] == ["shopping", "food-delivery"]
