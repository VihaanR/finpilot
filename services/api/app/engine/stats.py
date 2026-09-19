"""Robust statistics primitives.

DESIGN.md section 8.2 requires median and MAD throughout, never mean and
standard deviation, because a single festival month destroys a mean-based
baseline. Everything here is pure and integer-safe: functions that return
money return `int` paise.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence

#: Scale factor making MAD a consistent estimator of sigma for normal data.
#: The 0.6745 in DESIGN.md section 8.2's robust-z formula.
MAD_TO_SIGMA = 0.6745

#: When every observation is identical the MAD is 0 and the robust z-score is
#: undefined. DESIGN.md is silent, so we take the simplest defensible option:
#: treat the spread as 1% of the median rather than dividing by zero. A truly
#: flat history with one different value is then a genuine outlier, which is
#: the behaviour we want, without producing an infinite score.
DEGENERATE_MAD_FRACTION = 0.01


def median_float(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("median of an empty sequence is undefined")
    return float(statistics.median(values))


def median_int(values: Sequence[int]) -> int:
    """Median of integer paise, rounded to the nearest paisa.

    `statistics.median` averages the two middle values for even-length input,
    which can yield a half-paisa. Money must stay integral, so we round.
    """
    if not values:
        raise ValueError("median of an empty sequence is undefined")
    return int(round(statistics.median(values)))


def mad(values: Sequence[float], center: float | None = None) -> float:
    """Median absolute deviation about the median (or a supplied center)."""
    if not values:
        raise ValueError("MAD of an empty sequence is undefined")
    mid = median_float(values) if center is None else center
    return median_float([abs(v - mid) for v in values])


def mad_int(values: Sequence[int], center: int | None = None) -> int:
    if not values:
        raise ValueError("MAD of an empty sequence is undefined")
    mid = median_int(values) if center is None else center
    return int(round(median_float([abs(v - mid) for v in values])))


def robust_z(observed: float, baseline: Sequence[float]) -> float:
    """Robust z-score of `observed` against `baseline`.

    z = 0.6745 * (observed - median) / MAD, per DESIGN.md section 8.2.
    Returns 0.0 when the baseline is degenerate and the observation matches it.
    """
    if not baseline:
        return 0.0
    mid = median_float(baseline)
    spread = mad(baseline, center=mid)
    if spread == 0:
        if observed == mid:
            return 0.0
        spread = abs(mid) * DEGENERATE_MAD_FRACTION
        if spread == 0:
            # A baseline of all zeros; any non-zero observation is a spike.
            return float("inf") if observed > 0 else float("-inf")
    return MAD_TO_SIGMA * (observed - mid) / spread


def percentile(values: Sequence[float], pct: float) -> float:
    """Linear-interpolated percentile. `pct` is 0-100.

    Implemented here rather than pulled from numpy so the engine stays free of
    heavyweight imports and behaves identically on every platform.
    """
    if not values:
        raise ValueError("percentile of an empty sequence is undefined")
    if not 0 <= pct <= 100:
        raise ValueError("pct must be between 0 and 100")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * (pct / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return float(ordered[low]) * (1 - weight) + float(ordered[high]) * weight


def percentile_int(values: Sequence[int], pct: float) -> int:
    return int(round(percentile(values, pct)))


def ceil_div(numerator: int, denominator: int) -> int:
    """Integer ceiling division, correct for negative numerators.

    Used wherever a required contribution is computed: rounding a shortfall
    down would understate what the user must set aside.
    """
    if denominator == 0:
        raise ZeroDivisionError("ceil_div by zero")
    return -((-numerator) // denominator)
