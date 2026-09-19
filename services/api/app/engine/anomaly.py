"""Anomaly detection.

Implements DESIGN.md section 8.2: five types, robust statistics throughout,
and a plain-English explanation built from a fixed template per type. Fixed
templates matter because these strings reach the user directly and must never
be model-generated prose about a number the model did not compute.

Where history is too short to establish a baseline the detector returns an
explicit `insufficient_history` marker rather than inventing one.
"""

from __future__ import annotations

import itertools
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from .recurrence import find_duplicate_pairs, had_price_rise
from .stats import median_int, percentile_int, robust_z
from .types import (
    Anomaly,
    AnomalyType,
    Direction,
    RecurringSeries,
    SeriesStatus,
    Severity,
    Txn,
)

#: DESIGN.md section 8.2: |z| > 3 fires, z > 5 is HIGH.
SPIKE_Z_THRESHOLD = 3.0
SPIKE_Z_HIGH = 5.0

#: DESIGN.md section 8.2: category_spike needs >= 3 months of history.
MIN_MONTHS_FOR_BASELINE = 3

#: Trailing window for the spike baseline.
BASELINE_MONTHS = 6

#: DESIGN.md section 8.2: same merchant, same amount, within 72 hours.
DUPLICATE_WINDOW_HOURS = 72

#: A merchant debit above this percentile of the user's debits is "large".
LARGE_MERCHANT_PERCENTILE = 90.0

PRICE_HIKE_THRESHOLD = 0.10


@dataclass(frozen=True)
class InsufficientHistory:
    """Returned instead of a fabricated baseline (DESIGN.md section 8.2)."""

    reason: str = "insufficient_history"
    months_available: int = 0
    months_required: int = MIN_MONTHS_FOR_BASELINE


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _month_end(value: date) -> date:
    first = _month_start(value)
    if first.month == 12:
        return first.replace(year=first.year + 1, month=1) - timedelta(days=1)
    return first.replace(month=first.month + 1) - timedelta(days=1)


def _format_rupees(paise: int) -> str:
    """Indian-format rupees for explanation templates only.

    This is a render-boundary helper confined to human-readable explanation
    strings. Every stored and returned money value stays integer paise.
    """
    rupees_whole = abs(paise) // 100
    digits = str(rupees_whole)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        digits = ",".join(parts + [tail])
    return f"Rs {digits}"


# --- 1. Category spike ------------------------------------------------------


def detect_category_spikes(
    txns: Sequence[Txn], *, period: date, baseline_months: int = BASELINE_MONTHS
) -> list[Anomaly] | InsufficientHistory:
    """Robust-z spike detection per category for the month containing `period`.

    Returns `InsufficientHistory` when fewer than three complete prior months
    of data exist, rather than a baseline drawn from one or two months.
    """
    observed_month = _month_start(period)
    debits = [t for t in txns if t.direction is Direction.DEBIT]

    by_month_category: dict[tuple[date, str], list[Txn]] = defaultdict(list)
    for txn in debits:
        by_month_category[(_month_start(txn.txn_date), txn.category_slug)].append(txn)

    prior_months = sorted(
        {m for (m, _) in by_month_category if m < observed_month}, reverse=True
    )
    if len(prior_months) < MIN_MONTHS_FOR_BASELINE:
        return InsufficientHistory(months_available=len(prior_months))

    window = prior_months[:baseline_months]
    categories = {c for (_, c) in by_month_category}

    anomalies: list[Anomaly] = []
    for category in sorted(categories):
        observed_txns = by_month_category.get((observed_month, category), [])
        if not observed_txns:
            continue
        observed_total = sum(t.amount_paise for t in observed_txns)
        baseline = [
            float(sum(t.amount_paise for t in by_month_category.get((m, category), [])))
            for m in window
        ]
        z = robust_z(float(observed_total), baseline)
        if abs(z) <= SPIKE_Z_THRESHOLD:
            continue
        baseline_median = median_int([int(b) for b in baseline])
        multiple = observed_total / baseline_median if baseline_median else 0.0
        direction_word = "higher" if z > 0 else "lower"
        anomalies.append(
            Anomaly(
                type=AnomalyType.CATEGORY_SPIKE,
                severity=Severity.HIGH if abs(z) > SPIKE_Z_HIGH else Severity.MEDIUM,
                period_start=observed_month,
                period_end=_month_end(observed_month),
                txn_ids=tuple(t.id for t in observed_txns),
                explanation=(
                    f"You spent {_format_rupees(observed_total)} on {category} in "
                    f"{observed_month.strftime('%B %Y')}, {multiple:.1f} times your "
                    f"usual {_format_rupees(baseline_median)}. That is unusually "
                    f"{direction_word} against the last {len(window)} months."
                ),
                metric={
                    "z": round(z, 3),
                    "observed_paise": observed_total,
                    "baseline_paise": baseline_median,
                    "category_slug": category,
                    "months_in_baseline": len(window),
                },
            )
        )
    return anomalies


# --- 2. New large merchant --------------------------------------------------


def detect_new_large_merchants(
    txns: Sequence[Txn], *, period: date, percentile_cut: float = LARGE_MERCHANT_PERCENTILE
) -> list[Anomaly]:
    """First-ever transaction for a merchant, above p90 of the user's debits."""
    debits = sorted(
        (t for t in txns if t.direction is Direction.DEBIT), key=lambda t: t.txn_date
    )
    if not debits:
        return []
    threshold = percentile_int([t.amount_paise for t in debits], percentile_cut)

    observed_month = _month_start(period)
    seen: set[str] = set()
    anomalies: list[Anomaly] = []
    for txn in debits:
        first_time = txn.normalized_merchant not in seen
        seen.add(txn.normalized_merchant)
        if not first_time:
            continue
        if _month_start(txn.txn_date) != observed_month:
            continue
        if txn.amount_paise <= threshold:
            continue
        anomalies.append(
            Anomaly(
                type=AnomalyType.NEW_LARGE_MERCHANT,
                severity=Severity.MEDIUM,
                period_start=txn.txn_date,
                period_end=txn.txn_date,
                txn_ids=(txn.id,),
                explanation=(
                    f"{_format_rupees(txn.amount_paise)} to {txn.normalized_merchant} "
                    f"on {txn.txn_date.strftime('%d %b %Y')} is your first payment to "
                    f"this merchant, and it is larger than 90% of what you normally "
                    f"spend (above {_format_rupees(threshold)})."
                ),
                metric={
                    "amount_paise": txn.amount_paise,
                    "threshold_paise": threshold,
                    "merchant": txn.normalized_merchant,
                },
            )
        )
    return anomalies


# --- 3. Duplicate charge ----------------------------------------------------


def detect_duplicate_charges(
    txns: Sequence[Txn], *, window_hours: int = DUPLICATE_WINDOW_HOURS
) -> list[Anomaly]:
    """Same merchant, same amount, inside a 72-hour window."""
    window_days = window_hours / 24.0
    by_merchant: dict[str, list[Txn]] = defaultdict(list)
    for txn in txns:
        if txn.direction is Direction.DEBIT:
            by_merchant[txn.normalized_merchant].append(txn)

    anomalies: list[Anomaly] = []
    for merchant, group in sorted(by_merchant.items()):
        ordered = sorted(group, key=lambda t: t.txn_date)
        for a, b in itertools.combinations(ordered, 2):
            if a.amount_paise != b.amount_paise:
                continue
            gap_days = (b.txn_date - a.txn_date).days
            if gap_days > window_days:
                continue
            anomalies.append(
                Anomaly(
                    type=AnomalyType.DUPLICATE_CHARGE,
                    severity=Severity.HIGH,
                    period_start=a.txn_date,
                    period_end=b.txn_date,
                    txn_ids=(a.id, b.id),
                    explanation=(
                        f"{merchant} charged {_format_rupees(a.amount_paise)} twice "
                        f"within {int(round(gap_days * 24))} hours "
                        f"({a.txn_date.strftime('%d %b')} and "
                        f"{b.txn_date.strftime('%d %b %Y')}). This may be a duplicate "
                        f"charge worth disputing."
                    ),
                    metric={
                        "amount_paise": a.amount_paise,
                        "gap_hours": int(round(gap_days * 24)),
                        "merchant": merchant,
                    },
                )
            )
    return anomalies


# --- 4. Price hike ----------------------------------------------------------


def detect_price_hikes(
    series: Sequence[RecurringSeries], *, threshold: float = PRICE_HIKE_THRESHOLD
) -> list[Anomaly]:
    """A recurring series whose current price level rose more than 10%."""
    anomalies: list[Anomaly] = []
    for item in series:
        if not had_price_rise(item, threshold=threshold):
            continue
        previous = item.price_history[-2]
        current = item.price_history[-1]
        pct = (current.amount_paise - previous.amount_paise) / previous.amount_paise
        anomalies.append(
            Anomaly(
                type=AnomalyType.PRICE_HIKE,
                severity=Severity.MEDIUM,
                period_start=previous.effective_from,
                period_end=current.effective_from,
                txn_ids=item.txn_ids,
                explanation=(
                    f"{item.normalized_merchant} went from "
                    f"{_format_rupees(previous.amount_paise)} to "
                    f"{_format_rupees(current.amount_paise)} "
                    f"({pct * 100:.0f}% more) from "
                    f"{current.effective_from.strftime('%d %b %Y')}. "
                    f"You have not been asked to re-authorise it."
                ),
                metric={
                    "previous_paise": previous.amount_paise,
                    "current_paise": current.amount_paise,
                    "pct_change": round(pct, 4),
                    "merchant": item.normalized_merchant,
                },
                series_key=item.key,
            )
        )
    return anomalies


# --- 5. Silent mandate ------------------------------------------------------


def detect_silent_mandates(series: Sequence[RecurringSeries]) -> list[Anomaly]:
    """Active SILENT-band series the user has not acknowledged.

    This is the anomaly Mandate Radar exists for: under RBI's e-mandate
    framework these debit with no OTP, so the only thing standing between the
    user and a forgotten charge is knowing it exists.
    """
    anomalies: list[Anomaly] = []
    for item in series:
        if item.status is not SeriesStatus.ACTIVE:
            continue
        if item.direction is not Direction.DEBIT:
            continue
        if item.afa_band.value != "SILENT" or item.acknowledged:
            continue
        anomalies.append(
            Anomaly(
                type=AnomalyType.SILENT_MANDATE,
                severity=Severity.MEDIUM,
                period_start=item.last_seen,
                period_end=item.next_expected_date,
                txn_ids=item.txn_ids,
                explanation=(
                    f"{item.normalized_merchant} will take "
                    f"{_format_rupees(item.median_amount_paise)} on "
                    f"{item.next_expected_date.strftime('%d %b %Y')} without asking "
                    f"you. Under RBI rules, recurring debits up to Rs 15,000 need no "
                    f"OTP once the mandate is set up."
                ),
                metric={
                    "amount_paise": item.median_amount_paise,
                    "merchant": item.normalized_merchant,
                    "mandate_channel": item.mandate_channel.value,
                },
                series_key=item.key,
            )
        )
    return anomalies


# --- Duplicate subscriptions (feeds the radar DUPLICATE badge) --------------


def detect_duplicate_subscriptions(
    series: Sequence[RecurringSeries],
) -> list[Anomaly]:
    """Two active series in the same category with comparable amounts."""
    anomalies: list[Anomaly] = []
    for a, b in find_duplicate_pairs(series):
        combined = a.median_amount_paise + b.median_amount_paise
        anomalies.append(
            Anomaly(
                type=AnomalyType.DUPLICATE_CHARGE,
                severity=Severity.MEDIUM,
                period_start=min(a.first_seen, b.first_seen),
                period_end=max(a.last_seen, b.last_seen),
                txn_ids=tuple(a.txn_ids) + tuple(b.txn_ids),
                explanation=(
                    f"Two {a.category_slug} subscriptions are active: "
                    f"{a.normalized_merchant} ({_format_rupees(a.median_amount_paise)}) "
                    f"and {b.normalized_merchant} "
                    f"({_format_rupees(b.median_amount_paise)}), "
                    f"{_format_rupees(combined)} a month combined. "
                    f"Review whether both are needed."
                ),
                metric={
                    "combined_paise": combined,
                    "merchant_a": a.normalized_merchant,
                    "merchant_b": b.normalized_merchant,
                },
                series_key=a.key,
            )
        )
    return anomalies


# --- Orchestration ----------------------------------------------------------


def detect(
    txns: Sequence[Txn],
    series: Sequence[RecurringSeries] = (),
    *,
    period: date | None = None,
) -> list[Anomaly]:
    """Run every detector and return anomalies ordered by severity then date.

    `period` selects the month analysed for the month-scoped detectors
    (category spike, new large merchant). Defaults to the latest transaction.
    """
    if not txns and not series:
        return []
    reference = period or (max(t.txn_date for t in txns) if txns else date.today())

    found: list[Anomaly] = []

    spikes = detect_category_spikes(txns, period=reference)
    if isinstance(spikes, list):
        found.extend(spikes)

    found.extend(detect_new_large_merchants(txns, period=reference))
    found.extend(detect_duplicate_charges(txns))
    found.extend(detect_price_hikes(series))
    found.extend(detect_silent_mandates(series))
    found.extend(detect_duplicate_subscriptions(series))

    order = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
    found.sort(key=lambda a: (order[a.severity], a.period_start, a.type.value))
    return found
