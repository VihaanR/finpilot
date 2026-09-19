"""Scenario simulation tests.

BUILD_TASKS.md T06 requires that cancelling a known series moves the goal ETA
by a hand-computed number of months. `TestCancelSeries` does exactly that.
"""

from __future__ import annotations

from datetime import date

from app.engine import simulate as sim
from app.engine.types import Direction, OneOff, Scenario, rupees

from .conftest import series, txn

AS_OF = date(2026, 9, 10)


def _ledger_txns():
    """Three complete months at Rs 1,00,000 in and Rs 50,000 out."""
    rows = []
    for month in (6, 7, 8):
        rows.append(
            txn(on=date(2026, month, 1), amount_rupees=1_00_000,
                direction=Direction.CREDIT, merchant="ACME", category="salary")
        )
        rows.append(
            txn(on=date(2026, month, 5), amount_rupees=25_000,
                merchant="LANDLORD", category="rent")
        )
        rows.append(
            txn(on=date(2026, month, 9), amount_rupees=10_000,
                merchant="SWIGGY", category="food-delivery")
        )
        rows.append(
            txn(on=date(2026, month, 12), amount_rupees=15_000,
                merchant="KIRANA", category="groceries")
        )
    return rows


def _ledger_series():
    return [
        series(
            merchant="ACME", amount_rupees=1_00_000, category="salary",
            direction=Direction.CREDIT, next_expected=date(2026, 9, 25),
            key="k-salary",
        ),
        series(
            merchant="LANDLORD", amount_rupees=25_000, category="rent",
            next_expected=date(2026, 9, 15), key="k-rent",
        ),
    ]


class TestCancelSeries:
    """Hand-computed.

        surplus before   = median(1,00,000 - 50,000) over Jun/Jul/Aug = Rs 50,000
        Emergency Fund shortfall = Rs 3,00,000
        before: 3,00,000 / 50,000 = 6 months -> 1 Mar 2027
        cancel rent (Rs 25,000/month) -> surplus after = Rs 75,000
        after:  3,00,000 / 75,000 = 4 months -> 1 Jan 2027
        months_delta = -2
    """

    def _run(self, goal_on_track):
        return sim.simulate(
            _ledger_txns(),
            _ledger_series(),
            [goal_on_track],
            Scenario(cancel_series=("k-rent",)),
            current_balance_paise=rupees(80_000),
            as_of=AS_OF,
        )

    def test_surplus_before(self, goal_on_track):
        assert self._run(goal_on_track).monthly_surplus_before_paise == rupees(50_000)

    def test_cancelled_monthly_total(self, goal_on_track):
        assert self._run(goal_on_track).cancelled_monthly_paise == rupees(25_000)

    def test_surplus_after(self, goal_on_track):
        assert self._run(goal_on_track).monthly_surplus_after_paise == rupees(75_000)

    def test_eta_moves_two_months_earlier(self, goal_on_track):
        [diff] = self._run(goal_on_track).goals
        assert diff.eta_before == date(2027, 3, 1)
        assert diff.eta_after == date(2027, 1, 1)
        assert diff.months_delta == -2

    def test_safe_to_spend_improves(self, goal_on_track):
        result = self._run(goal_on_track)
        assert result.safe_daily_after_paise > result.safe_daily_before_paise


class TestCadenceNormalisation:
    def test_annual_mandate_counts_as_one_twelfth_per_month(self):
        annual = series(
            merchant="LICINDIA", amount_rupees=12_000,
            category="insurance-premium", next_expected=date(2026, 10, 1),
            gap_days=365.0, key="k-lic",
        )
        # 12,00,000 paise * 30 / 365 = 98,630 paise (Rs 986.30). The engine
        # keeps the 30 paise rather than rounding to whole rupees.
        assert sim.monthly_equivalent_paise(annual) == 98_630

    def test_monthly_mandate_is_its_own_amount(self):
        monthly = series(
            merchant="LANDLORD", amount_rupees=25_000, category="rent",
            next_expected=date(2026, 10, 1), gap_days=30.0,
        )
        assert sim.monthly_equivalent_paise(monthly) == rupees(25_000)


class TestCategoryChange:
    """Food delivery costs Rs 10,000/month; cutting it 30% frees Rs 3,000."""

    def test_surplus_delta_matches_the_percentage_cut(self, goal_on_track):
        result = sim.simulate(
            _ledger_txns(),
            _ledger_series(),
            [goal_on_track],
            Scenario(category_pct_change={"food-delivery": -0.30}),
            current_balance_paise=rupees(80_000),
            as_of=AS_OF,
        )
        assert result.monthly_surplus_delta_paise == rupees(3_000)

    def test_increasing_a_category_reduces_the_surplus(self, goal_on_track):
        result = sim.simulate(
            _ledger_txns(),
            _ledger_series(),
            [goal_on_track],
            Scenario(category_pct_change={"food-delivery": 0.50}),
            current_balance_paise=rupees(80_000),
            as_of=AS_OF,
        )
        assert result.monthly_surplus_delta_paise == -rupees(5_000)

    def test_unknown_category_changes_nothing(self, goal_on_track):
        result = sim.simulate(
            _ledger_txns(),
            _ledger_series(),
            [goal_on_track],
            Scenario(category_pct_change={"not-a-category": -0.90}),
            current_balance_paise=rupees(80_000),
            as_of=AS_OF,
        )
        assert result.monthly_surplus_delta_paise == 0


class TestOneOffPurchase:
    """Hand-computed: a Rs 12,499 purchase competes with the top-priority goal.

        shortfall after = 3,00,000 + 12,499 = Rs 3,12,499
        months needed   = ceil(3,12,499 / 50,000) = 7  (vs 6 before)
        ETA moves Mar 2027 -> Apr 2027, one month later.
    """

    def test_one_off_delays_the_goal_by_one_month(self, goal_on_track):
        result = sim.simulate(
            _ledger_txns(),
            _ledger_series(),
            [goal_on_track],
            Scenario(one_off=(OneOff(amount_paise=rupees(12_499),
                                     on_date=date(2026, 9, 12),
                                     category_slug="shopping"),)),
            current_balance_paise=rupees(80_000),
            as_of=AS_OF,
        )
        [diff] = result.goals
        assert diff.eta_before == date(2027, 3, 1)
        assert diff.eta_after == date(2027, 4, 1)
        assert diff.months_delta == 1

    def test_one_off_is_recorded_for_the_narration(self, goal_on_track):
        result = sim.simulate(
            _ledger_txns(),
            _ledger_series(),
            [goal_on_track],
            Scenario(one_off=(OneOff(amount_paise=rupees(12_499),
                                     on_date=date(2026, 9, 12)),)),
            current_balance_paise=rupees(80_000),
            as_of=AS_OF,
        )
        assert result.narration_facts["one_off_total_paise"] == rupees(12_499)


class TestEmptyScenario:
    def test_no_change_moves_nothing(self, goal_on_track):
        result = sim.simulate(
            _ledger_txns(),
            _ledger_series(),
            [goal_on_track],
            Scenario(),
            current_balance_paise=rupees(80_000),
            as_of=AS_OF,
        )
        [diff] = result.goals
        assert diff.months_delta == 0
        assert result.monthly_surplus_delta_paise == 0

    def test_simulation_is_reproducible(self, goal_on_track):
        scenario = Scenario(cancel_series=("k-rent",))
        args = dict(current_balance_paise=rupees(80_000), as_of=AS_OF)
        first = sim.simulate(_ledger_txns(), _ledger_series(), [goal_on_track],
                             scenario, **args)
        second = sim.simulate(_ledger_txns(), _ledger_series(), [goal_on_track],
                              scenario, **args)
        assert first == second
