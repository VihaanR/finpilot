"""Robust-statistics primitives (DESIGN.md section 8.2)."""

from __future__ import annotations

import pytest

from app.engine import stats


class TestMedian:
    def test_odd_length(self):
        assert stats.median_int([1, 5, 3]) == 3

    def test_even_length_rounds_to_whole_paise(self):
        assert stats.median_int([1, 2]) == 2  # 1.5 rounds half-to-even -> 2
        assert stats.median_int([2, 3]) == 2

    def test_empty_is_an_error_not_a_zero(self):
        with pytest.raises(ValueError):
            stats.median_int([])


class TestMad:
    def test_mad_of_a_flat_sequence_is_zero(self):
        assert stats.mad([5, 5, 5, 5]) == 0

    def test_mad_is_resistant_to_one_outlier(self):
        """The property the whole design rests on: one festival month
        must not move the baseline the way a standard deviation would."""
        steady = [100, 102, 98, 101, 99]
        with_outlier = steady + [10_000]
        assert stats.mad(with_outlier) <= stats.mad(steady) * 3


class TestRobustZ:
    def test_matches_the_design_formula(self):
        baseline = [100, 102, 98, 104, 96]
        # median 100, deviations [0, 2, 2, 4, 4] -> MAD 2
        assert stats.robust_z(100, baseline) == 0.0
        assert stats.robust_z(110, baseline) == pytest.approx(0.6745 * 10 / 2)

    def test_flat_baseline_with_a_matching_observation_is_zero(self):
        assert stats.robust_z(50, [50, 50, 50]) == 0.0

    def test_flat_baseline_with_a_deviation_does_not_divide_by_zero(self):
        z = stats.robust_z(500, [50, 50, 50])
        assert z > 3 and z != float("inf")

    def test_all_zero_baseline_is_infinite_not_an_error(self):
        assert stats.robust_z(100, [0, 0, 0]) == float("inf")

    def test_empty_baseline_is_zero(self):
        assert stats.robust_z(100, []) == 0.0


class TestPercentile:
    def test_median_is_the_fiftieth(self):
        assert stats.percentile([1, 2, 3, 4, 5], 50) == 3

    def test_p90_interpolates(self):
        assert stats.percentile([0, 10], 90) == pytest.approx(9.0)

    def test_single_value(self):
        assert stats.percentile([7], 90) == 7.0

    def test_out_of_range_is_rejected(self):
        with pytest.raises(ValueError):
            stats.percentile([1, 2], 101)


class TestCeilDiv:
    def test_exact_division(self):
        assert stats.ceil_div(100, 10) == 10

    def test_rounds_up_so_a_shortfall_is_never_understated(self):
        assert stats.ceil_div(101, 10) == 11

    def test_zero_denominator_raises(self):
        with pytest.raises(ZeroDivisionError):
            stats.ceil_div(1, 0)
