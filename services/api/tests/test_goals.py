"""Goal projection tests.

BUILD_TASKS.md T06 requires ETA arithmetic checked against a hand-computed
fixture; the sums are spelled out in each docstring.
"""

from __future__ import annotations

from datetime import date

from app.engine import goals as goals_engine
from app.engine.types import Goal, GoalVerdict, rupees

AS_OF = date(2026, 9, 10)


class TestSingleGoal:
    """Hand-computed.

        shortfall        = Rs 5,00,000 - Rs 2,00,000 = Rs 3,00,000
        surplus          = Rs 50,000/month
        months needed    = ceil(3,00,000 / 50,000) = 6
        ETA              = Sep 2026 + 6 months      = 1 Mar 2027
        target date      = 15 Mar 2027 -> same month -> ON_TRACK
    """

    def test_eta_is_six_months_out(self, goal_on_track):
        [projection] = goals_engine.project(
            [goal_on_track], as_of=AS_OF, surplus_paise=rupees(50_000)
        )
        assert projection.projected_eta == date(2027, 3, 1)

    def test_verdict_on_track(self, goal_on_track):
        [projection] = goals_engine.project(
            [goal_on_track], as_of=AS_OF, surplus_paise=rupees(50_000)
        )
        assert projection.verdict is GoalVerdict.ON_TRACK
        assert projection.months_delta == 0

    def test_shortfall(self, goal_on_track):
        [projection] = goals_engine.project(
            [goal_on_track], as_of=AS_OF, surplus_paise=rupees(50_000)
        )
        assert projection.shortfall_paise == rupees(3_00_000)

    def test_required_monthly(self, goal_on_track):
        """6 months to the target date, so Rs 50,000/month is required."""
        [projection] = goals_engine.project(
            [goal_on_track], as_of=AS_OF, surplus_paise=rupees(50_000)
        )
        assert projection.months_remaining == 6
        assert projection.required_monthly_paise == rupees(50_000)

    def test_halving_the_surplus_doubles_the_wait(self, goal_on_track):
        [projection] = goals_engine.project(
            [goal_on_track], as_of=AS_OF, surplus_paise=rupees(25_000)
        )
        assert projection.projected_eta == date(2027, 9, 1)
        assert projection.verdict is GoalVerdict.BEHIND

    def test_no_surplus_is_unreachable_not_infinite(self, goal_on_track):
        [projection] = goals_engine.project(
            [goal_on_track], as_of=AS_OF, surplus_paise=0
        )
        assert projection.projected_eta is None
        assert projection.verdict is GoalVerdict.UNREACHABLE

    def test_already_funded_goal_is_on_track_today(self):
        funded = Goal(
            id="g-done",
            name="Done",
            target_paise=rupees(1_00_000),
            current_paise=rupees(1_00_000),
            target_date=date(2027, 1, 1),
        )
        [projection] = goals_engine.project(
            [funded], as_of=AS_OF, surplus_paise=rupees(10_000)
        )
        assert projection.shortfall_paise == 0
        assert projection.projected_eta == AS_OF


class TestTwoGoalsByPriority:
    """Hand-computed with a Rs 60,000 surplus.

        priority 0, Emergency Fund: takes its planned Rs 50,000
                    shortfall 3,00,000 / 50,000 = 6 months -> Mar 2027 (ON_TRACK)
        priority 1, New Laptop:     takes the remaining Rs 10,000
                    shortfall 1,00,000 / 10,000 = 10 months -> Jul 2027
                    target Dec 2026 -> 7 months late -> BEHIND
    """

    def test_priority_zero_is_funded_first(self, goal_on_track, goal_behind):
        first, second = goals_engine.project(
            [goal_on_track, goal_behind], as_of=AS_OF, surplus_paise=rupees(60_000)
        )
        assert first.goal_id == "g-emergency"
        assert first.allocated_monthly_paise == rupees(50_000)
        assert second.allocated_monthly_paise == rupees(10_000)

    def test_on_track_goal(self, goal_on_track, goal_behind):
        first, _ = goals_engine.project(
            [goal_on_track, goal_behind], as_of=AS_OF, surplus_paise=rupees(60_000)
        )
        assert first.projected_eta == date(2027, 3, 1)
        assert first.verdict is GoalVerdict.ON_TRACK

    def test_behind_goal_reports_the_month_delta(self, goal_on_track, goal_behind):
        _, second = goals_engine.project(
            [goal_on_track, goal_behind], as_of=AS_OF, surplus_paise=rupees(60_000)
        )
        assert second.projected_eta == date(2027, 7, 1)
        assert second.verdict is GoalVerdict.BEHIND
        assert second.months_delta == 7

    def test_leftover_surplus_accelerates_the_top_goal(self, goal_on_track):
        """Freed-up money must move an ETA, not vanish into a remainder."""
        [projection] = goals_engine.project(
            [goal_on_track], as_of=AS_OF, surplus_paise=rupees(1_00_000)
        )
        assert projection.allocated_monthly_paise == rupees(1_00_000)
        assert projection.projected_eta == date(2026, 12, 1)
        assert projection.verdict is GoalVerdict.AHEAD


class TestAllocate:
    def test_allocation_never_exceeds_the_surplus(self, goal_on_track, goal_behind):
        allocation = goals_engine.allocate(
            [goal_on_track, goal_behind], rupees(30_000)
        )
        assert sum(allocation.values()) == rupees(30_000)

    def test_funded_goals_receive_nothing(self):
        funded = Goal(
            id="g-done", name="Done", target_paise=rupees(1_000),
            current_paise=rupees(1_000), target_date=date(2027, 1, 1),
            monthly_contribution_paise=rupees(500),
        )
        allocation = goals_engine.allocate([funded], rupees(10_000))
        assert allocation["g-done"] == 0

    def test_negative_surplus_allocates_nothing(self, goal_on_track):
        allocation = goals_engine.allocate([goal_on_track], -rupees(5_000))
        assert allocation["g-emergency"] == 0


class TestMonthArithmetic:
    def test_months_between(self):
        assert goals_engine.months_between(date(2026, 9, 1), date(2027, 3, 1)) == 6

    def test_months_between_is_signed(self):
        assert goals_engine.months_between(date(2027, 3, 1), date(2026, 9, 1)) == -6

    def test_add_months_clamps_to_month_end(self):
        assert goals_engine.add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)

    def test_add_months_crosses_a_year(self):
        assert goals_engine.add_months(date(2026, 11, 15), 3) == date(2027, 2, 15)
