"""Cash-flow tests.

BUILD_TASKS.md T06 requires Safe-to-Spend arithmetic checked against a
hand-computed fixture. The numbers below are worked out in the docstring of
`TestSafeToSpend` so a reviewer can verify them without running the code.
"""

from __future__ import annotations

from datetime import date

from app.engine import cashflow
from app.engine.types import Direction, Goal, rupees

from .conftest import series, txn

AS_OF = date(2026, 9, 10)


def _ledger():
    """Salary on the 25th, rent on the 15th, one subscription on the 20th."""
    return [
        series(
            merchant="ACME PAYROLL",
            amount_rupees=1_00_000,
            category="salary",
            direction=Direction.CREDIT,
            next_expected=date(2026, 9, 25),
            key="k-salary",
        ),
        series(
            merchant="LANDLORD",
            amount_rupees=25_000,
            category="rent",
            next_expected=date(2026, 9, 15),
            key="k-rent",
        ),
        series(
            merchant="NETFLIX",
            amount_rupees=199,
            category="subscriptions",
            next_expected=date(2026, 9, 20),
            key="k-netflix",
        ),
    ]


class TestSafeToSpend:
    """Hand-computed fixture.

        next income      = 25 Sep 2026 (the only CREDIT series)
        obligations      = rent Rs 25,000 (15 Sep) + Netflix Rs 199 (20 Sep)
        committed        = Rs 25,199          = 25,19,900 paise
        balance          = Rs 80,000          = 80,00,000 paise
        goal_due         = 0 (no goals)
        discretionary    = 80,00,000 - 25,19,900 = 54,80,100 paise
        days_remaining   = 25 Sep - 10 Sep    = 15
        safe_daily       = 54,80,100 // 15    = 3,65,340 paise  (Rs 3,653.40)
    """

    def _result(self):
        return cashflow.safe_to_spend(
            _ledger(), [], current_balance_paise=rupees(80_000), as_of=AS_OF
        )

    def test_next_income_date(self):
        assert self._result().next_income_date == date(2026, 9, 25)

    def test_committed_total(self):
        assert self._result().committed_paise == 2_519_900

    def test_discretionary(self):
        assert self._result().discretionary_paise == 5_480_100

    def test_days_remaining(self):
        assert self._result().days_remaining == 15

    def test_safe_daily(self):
        assert self._result().safe_daily_paise == 365_340

    def test_obligations_are_listed_for_the_drawer(self):
        obligations = self._result().obligations
        assert len(obligations) == 2
        assert [o.normalized_merchant for o in obligations] == ["LANDLORD", "NETFLIX"]

    def test_citations_cover_every_obligation(self):
        result = self._result()
        assert sum(c.value_paise for c in result.citations) == result.committed_paise

    def test_goal_contributions_reduce_discretionary(self):
        goal = Goal(
            id="g1",
            name="Emergency Fund",
            target_paise=rupees(5_00_000),
            current_paise=rupees(1_00_000),
            target_date=date(2027, 6, 1),
            monthly_contribution_paise=rupees(10_000),
        )
        result = cashflow.safe_to_spend(
            _ledger(), [goal], current_balance_paise=rupees(80_000), as_of=AS_OF
        )
        assert result.goal_due_paise == rupees(10_000)
        assert result.discretionary_paise == 5_480_100 - rupees(10_000)

    def test_safe_daily_never_negative(self):
        result = cashflow.safe_to_spend(
            _ledger(), [], current_balance_paise=rupees(100), as_of=AS_OF
        )
        assert result.safe_daily_paise == 0

    def test_no_income_series_still_returns_a_figure(self):
        no_salary = [s for s in _ledger() if s.direction is Direction.DEBIT]
        result = cashflow.safe_to_spend(
            no_salary, [], current_balance_paise=rupees(80_000), as_of=AS_OF
        )
        assert result.next_income_date is None
        assert result.days_remaining > 0


class TestUpcoming:
    def test_lists_obligations_in_date_order(self):
        found = cashflow.upcoming(_ledger(), days=30, as_of=AS_OF)
        assert [o.due_date for o in found] == sorted(o.due_date for o in found)

    def test_excludes_credit_series(self):
        found = cashflow.upcoming(_ledger(), days=30, as_of=AS_OF)
        assert all(o.normalized_merchant != "ACME PAYROLL" for o in found)

    def test_horizon_is_respected(self):
        found = cashflow.upcoming(_ledger(), days=7, as_of=AS_OF)
        assert all(o.due_date <= date(2026, 9, 17) for o in found)

    def test_rolls_a_stale_expected_date_forward(self):
        """A series detected from old data must still project into the future."""
        stale = series(
            merchant="OLDSUB",
            amount_rupees=299,
            category="subscriptions",
            next_expected=date(2026, 7, 3),
        )
        found = cashflow.upcoming([stale], days=30, as_of=AS_OF)
        assert found
        assert all(o.due_date >= AS_OF for o in found)


class TestMonthlySummary:
    def _rows(self):
        return [
            txn(on=date(2026, 8, 1), amount_rupees=1_00_000,
                direction=Direction.CREDIT, merchant="ACME", category="salary"),
            txn(on=date(2026, 8, 5), amount_rupees=25_000, merchant="LANDLORD",
                category="rent"),
            txn(on=date(2026, 8, 9), amount_rupees=5_000, merchant="SWIGGY",
                category="food-delivery"),
            txn(on=date(2026, 9, 2), amount_rupees=1_000, merchant="SWIGGY",
                category="food-delivery"),
        ]

    def test_income_and_expense(self):
        summary = cashflow.monthly_summary(self._rows(), month=date(2026, 8, 1))
        assert summary.income_paise == rupees(1_00_000)
        assert summary.expense_paise == rupees(30_000)
        assert summary.net_paise == rupees(70_000)

    def test_savings_rate(self):
        summary = cashflow.monthly_summary(self._rows(), month=date(2026, 8, 1))
        assert summary.savings_rate_pct == 70.0

    def test_excludes_other_months(self):
        summary = cashflow.monthly_summary(self._rows(), month=date(2026, 8, 1))
        assert summary.txn_count == 3

    def test_category_totals_are_ranked(self):
        summary = cashflow.monthly_summary(self._rows(), month=date(2026, 8, 1))
        assert list(summary.by_category_paise) == ["rent", "food-delivery"]

    def test_empty_month_is_zero_not_an_error(self):
        summary = cashflow.monthly_summary(self._rows(), month=date(2026, 1, 1))
        assert summary.income_paise == 0
        assert summary.savings_rate_pct == 0.0


class TestMonthlySurplus:
    def test_median_of_the_last_three_complete_months(self):
        rows = []
        for month, expense in ((6, 50_000), (7, 60_000), (8, 40_000)):
            rows.append(
                txn(on=date(2026, month, 1), amount_rupees=1_00_000,
                    direction=Direction.CREDIT, merchant="ACME", category="salary")
            )
            rows.append(
                txn(on=date(2026, month, 5), amount_rupees=expense,
                    merchant="VARIOUS", category="shopping")
            )
        # nets are 50,000 / 40,000 / 60,000 -> median 50,000
        assert cashflow.monthly_surplus(rows, as_of=AS_OF) == rupees(50_000)

    def test_no_history_is_zero(self):
        assert cashflow.monthly_surplus([], as_of=AS_OF) == 0


class TestCategoryBreakdown:
    def test_ranked_with_transaction_ids(self):
        rows = [
            txn(on=date(2026, 9, 1), amount_rupees=5_000, merchant="SWIGGY",
                category="food-delivery"),
            txn(on=date(2026, 9, 2), amount_rupees=3_000, merchant="ZOMATO",
                category="food-delivery"),
            txn(on=date(2026, 9, 3), amount_rupees=1_000, merchant="BESCOM",
                category="utilities"),
        ]
        found = cashflow.category_breakdown(
            rows, start=date(2026, 9, 1), end=date(2026, 9, 30)
        )
        assert found[0][0] == "food-delivery"
        assert found[0][1] == rupees(8_000)
        assert len(found[0][2]) == 2
