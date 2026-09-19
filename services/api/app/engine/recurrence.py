"""Recurring-series detection.

Implements DESIGN.md section 8.1. Pure: takes transactions, returns series.

The pipeline for each (merchant, direction) group is:

  1. cluster occurrences by amount, tolerance = max(Rs 10, 5% of cluster median)
  2. merge clusters that represent a *price change* of the same underlying
     series, so a price hike or a trial-to-paid conversion does not split one
     subscription into two (DESIGN.md section 8.1, "Price-hike detection", and
     the TRIAL->PAID badge in section 10.1)
  3. test cadence regularity with median gap and gap MAD
  4. infer mandate channel from narration markers and derive the AFA band
"""

from __future__ import annotations

import hashlib
import itertools
import re
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta

from .stats import median_float, median_int
from .types import (
    AFA_HIGH_LIMIT_CEILING_PAISE,
    AFA_SILENT_CEILING_PAISE,
    CADENCE_DAYS,
    HIGH_LIMIT_CATEGORY_SLUGS,
    AfaBand,
    Cadence,
    Direction,
    MandateChannel,
    PricePoint,
    RecurringSeries,
    SeriesStatus,
    Txn,
    rupees,
)

#: DESIGN.md section 8.1: tolerance = max(Rs 10, 5% of cluster median).
MIN_AMOUNT_TOLERANCE_PAISE = rupees(10)
AMOUNT_TOLERANCE_PCT = 5

#: DESIGN.md section 8.1: accept a cadence when gap_mad / median_gap < 0.25.
MAX_GAP_DISPERSION = 0.25

#: The MAD test alone is not sufficient. Because the MAD is itself a median,
#: gaps of [30, 30, 30, 200, 30, 5] yield median 30 and MAD 0 and sail through
#: it. A genuine mandate fires at *every* interval, so we additionally require
#: most gaps to sit near the median. Without this, a busy merchant like a food
#: delivery app produces dozens of phantom "subscriptions" purely by chance.
MIN_GAP_CONSISTENCY = 0.75

#: Share of a merchant's transactions, within the candidate series' own date
#: span, that the series must itself account for.
#:
#: This is the strongest single guard against phantom series. Netflix charges
#: Rs 649 and does nothing else, so its series is 100% of Netflix activity. A
#: food delivery app has hundreds of transactions, and any three of them can
#: land on near-equal gaps by chance; such a cluster accounts for ~2% of that
#: merchant's activity and is rejected here. The trade-off, accepted and
#: documented: a single merchant string carrying *both* a subscription and
#: ad-hoc purchases will not yield a series. Real normalisation separates
#: those (different VPA handles), so it does not arise in practice.
MIN_CLUSTER_DOMINANCE = 0.30

#: A two-occurrence PROBABLE pair has a single gap, so gap consistency is
#: trivially satisfied. These tighter bounds stop every coincidental pair of
#: similar charges being surfaced as a candidate subscription.
PROBABLE_AMOUNT_TOLERANCE_PCT = 2
PROBABLE_CADENCE_TOLERANCE = 0.15

#: DESIGN.md section 8.1: three occurrences make a series; exactly two with a
#: tight amount match are surfaced as PROBABLE.
MIN_OCCURRENCES = 3
PROBABLE_OCCURRENCES = 2

#: A new occurrence more than this far above the running level is a price
#: change, not noise (DESIGN.md section 8.1).
PRICE_CHANGE_THRESHOLD = 0.10

#: A series is LAPSED once it has missed roughly two expected occurrences.
LAPSE_GAP_MULTIPLE = 2.0


def amount_tolerance(median_amount_paise: int) -> int:
    """Amount tolerance for a cluster, in paise."""
    return max(
        MIN_AMOUNT_TOLERANCE_PAISE,
        (abs(median_amount_paise) * AMOUNT_TOLERANCE_PCT) // 100,
    )


# --- Mandate channel --------------------------------------------------------

#: Narration markers, in priority order. DESIGN.md section 8.1.
_MANDATE_PATTERNS: tuple[tuple[str, MandateChannel], ...] = (
    (r"UPI[-\s]?MANDATE|AUTOPAY|AUTO[-\s]?PAY", MandateChannel.UPI_AUTOPAY),
    (r"E[-\s]?MANDATE|EMANDATE", MandateChannel.CARD_EMANDATE),
    (r"\bN?ACH\b|\bACH\s*D-|\bACH-D\b|\bNACH\b", MandateChannel.NACH),
    (r"\bSI[-\s]|STANDING\s+INSTR", MandateChannel.SI),
)


def infer_mandate_channel(narrations: Sequence[str]) -> MandateChannel:
    """Infer how a series is authorised, from its narration markers."""
    blob = " ".join(narrations).upper()
    for pattern, channel in _MANDATE_PATTERNS:
        if re.search(pattern, blob):
            return channel
    return MandateChannel.UNKNOWN


def derive_afa_band(median_amount_paise: int, category_slug: str | None) -> AfaBand:
    """Map an amount and category onto an RBI e-mandate band (DESIGN.md R1).

    Order is as written in DESIGN.md section 8.1: the Rs 15,000 silent ceiling
    is tested first, so a small SIP is SILENT rather than HIGH_LIMIT.
    """
    if median_amount_paise <= AFA_SILENT_CEILING_PAISE:
        return AfaBand.SILENT
    if (
        category_slug in HIGH_LIMIT_CATEGORY_SLUGS
        and median_amount_paise <= AFA_HIGH_LIMIT_CEILING_PAISE
    ):
        return AfaBand.HIGH_LIMIT
    return AfaBand.REQUIRES_AFA


# --- Clustering -------------------------------------------------------------


def _cluster_by_amount(txns: Sequence[Txn]) -> list[list[Txn]]:
    """Greedy one-dimensional clustering of occurrences by amount."""
    ordered = sorted(txns, key=lambda t: t.amount_paise)
    clusters: list[list[Txn]] = []
    current: list[Txn] = [ordered[0]]
    for txn in ordered[1:]:
        centre = median_int([t.amount_paise for t in current])
        if abs(txn.amount_paise - centre) <= amount_tolerance(centre):
            current.append(txn)
        else:
            clusters.append(current)
            current = [txn]
    clusters.append(current)
    return clusters


def _gap_stats(txns: Sequence[Txn]) -> tuple[float, float] | None:
    """(median_gap_days, gap_mad) for date-ordered occurrences, or None."""
    ordered = sorted(txns, key=lambda t: t.txn_date)
    gaps = [
        float((b.txn_date - a.txn_date).days)
        for a, b in itertools.pairwise(ordered)
    ]
    if not gaps:
        return None
    median_gap = median_float(gaps)
    if median_gap <= 0:
        return None
    gap_mad = median_float([abs(g - median_gap) for g in gaps])
    return median_gap, gap_mad


def _gap_consistency(txns: Sequence[Txn]) -> float:
    """Fraction of successive gaps sitting within tolerance of the median gap.

    This is the discriminator between a real mandate and a busy merchant. A
    subscription fires at every interval, so nearly every gap matches. Random
    spending at one merchant produces a few matching gaps among many that do
    not, which the MAD test cannot see.
    """
    ordered = sorted(txns, key=lambda t: t.txn_date)
    gaps = [
        float((b.txn_date - a.txn_date).days)
        for a, b in itertools.pairwise(ordered)
    ]
    if not gaps:
        return 0.0
    median_gap = median_float(gaps)
    if median_gap <= 0:
        return 0.0
    within = sum(
        1 for g in gaps if abs(g - median_gap) <= MAX_GAP_DISPERSION * median_gap
    )
    return within / len(gaps)


def _is_regular(txns: Sequence[Txn]) -> bool:
    stats = _gap_stats(txns)
    if stats is None:
        return False
    median_gap, gap_mad = stats
    if (gap_mad / median_gap) >= MAX_GAP_DISPERSION:
        return False
    return _gap_consistency(txns) >= MIN_GAP_CONSISTENCY


def _is_dominant(cluster: Sequence[Txn], group: Sequence[Txn]) -> bool:
    """Does this cluster account for enough of the merchant's own activity?

    Measured only across the cluster's date span, so a subscription that
    started midway through the history is judged against the period it
    actually covers rather than the whole ledger.
    """
    first = min(t.txn_date for t in cluster)
    last = max(t.txn_date for t in cluster)
    in_span = [t for t in group if first <= t.txn_date <= last]
    if not in_span:
        return False
    return (len(cluster) / len(in_span)) >= MIN_CLUSTER_DOMINANCE


def _is_probable_pair(txns: Sequence[Txn]) -> bool:
    """Is a two-occurrence cluster a tight enough match to surface?

    DESIGN.md section 8.1 admits "clusters with exactly 2 occurrences and tight
    amount match". Tight is made explicit here: near-identical amounts, and a
    gap close to one of the canonical cadences rather than any arbitrary
    interval.
    """
    if len(txns) != PROBABLE_OCCURRENCES:
        return False
    first, second = sorted(txns, key=lambda t: t.txn_date)

    centre = median_int([t.amount_paise for t in txns])
    tight = max(
        MIN_AMOUNT_TOLERANCE_PAISE,
        (abs(centre) * PROBABLE_AMOUNT_TOLERANCE_PCT) // 100,
    )
    if abs(first.amount_paise - second.amount_paise) > tight:
        return False

    gap = (second.txn_date - first.txn_date).days
    if gap <= 0:
        return False
    cadence_days = CADENCE_DAYS[nearest_cadence(float(gap))]
    return abs(gap - cadence_days) <= PROBABLE_CADENCE_TOLERANCE * cadence_days


def _is_price_change(a: Sequence[Txn], b: Sequence[Txn]) -> bool:
    """Do two amount-clusters describe one series either side of a price change?

    Guards, all required:
      - temporally disjoint, so one level genuinely succeeds the other
      - at least one side already has two occurrences, so we extend an
        established pattern rather than inventing one from two singletons
      - the merged set has enough occurrences and a regular cadence
    """
    a_last = max(t.txn_date for t in a)
    b_first = min(t.txn_date for t in b)
    if a_last >= b_first:
        return False
    if max(len(a), len(b)) < PROBABLE_OCCURRENCES:
        return False
    merged = list(a) + list(b)
    if len(merged) < MIN_OCCURRENCES:
        return False
    return _is_regular(merged)


def _merge_price_changes(clusters: list[list[Txn]]) -> list[list[Txn]]:
    """Repeatedly merge cluster pairs that are price levels of one series."""
    working = [list(c) for c in clusters]
    merged_something = True
    while merged_something and len(working) > 1:
        merged_something = False
        for i, j in itertools.combinations(range(len(working)), 2):
            first, second = working[i], working[j]
            if min(t.txn_date for t in first) > min(t.txn_date for t in second):
                first, second = second, first
            if _is_price_change(first, second):
                rest = [c for k, c in enumerate(working) if k not in (i, j)]
                working = rest + [first + second]
                merged_something = True
                break
    return working


def _price_levels(txns: Sequence[Txn]) -> list[PricePoint]:
    """Segment a date-ordered series into successive price levels."""
    ordered = sorted(txns, key=lambda t: t.txn_date)
    levels: list[PricePoint] = []
    run: list[Txn] = [ordered[0]]
    for txn in ordered[1:]:
        centre = median_int([t.amount_paise for t in run])
        if centre and abs(txn.amount_paise - centre) > max(
            amount_tolerance(centre), int(abs(centre) * PRICE_CHANGE_THRESHOLD)
        ):
            levels.append(
                PricePoint(
                    effective_from=run[0].txn_date,
                    amount_paise=median_int([t.amount_paise for t in run]),
                )
            )
            run = [txn]
        else:
            run.append(txn)
    levels.append(
        PricePoint(
            effective_from=run[0].txn_date,
            amount_paise=median_int([t.amount_paise for t in run]),
        )
    )
    return levels


def nearest_cadence(median_gap_days: float) -> Cadence:
    """Nearest of {7, 14, 30, 91, 182, 365} days, per DESIGN.md section 8.1."""
    return min(
        CADENCE_DAYS,
        key=lambda cadence: abs(CADENCE_DAYS[cadence] - median_gap_days),
    )


def _confidence(
    occurrence_count: int, median_gap: float, gap_mad: float, amount_rel_mad: float
) -> float:
    """f(occurrence_count, gap_mad, amount_variance) from DESIGN.md section 8.1.

    DESIGN.md names the inputs but not the shape, so this is the simplest
    defensible blend: how many times we have seen it, how regular the timing
    is relative to the acceptance threshold, and how stable the amount is.
    """
    occurrence_factor = min(1.0, occurrence_count / 6.0)
    dispersion = (gap_mad / median_gap) if median_gap else 1.0
    regularity_factor = max(0.0, 1.0 - dispersion / MAX_GAP_DISPERSION)
    amount_factor = max(
        0.0, 1.0 - amount_rel_mad / (AMOUNT_TOLERANCE_PCT / 100.0)
    )
    score = 0.4 * occurrence_factor + 0.4 * regularity_factor + 0.2 * amount_factor
    return round(min(1.0, max(0.0, score)), 4)


def series_key(merchant: str, direction: Direction, first_seen: date) -> str:
    raw = f"{merchant}|{direction.value}|{first_seen.isoformat()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _build_series(
    cluster: Sequence[Txn], *, as_of: date, status_override: SeriesStatus | None = None
) -> RecurringSeries | None:
    ordered = sorted(cluster, key=lambda t: t.txn_date)
    stats = _gap_stats(ordered)
    if stats is None:
        return None
    median_gap, gap_mad = stats

    levels = _price_levels(ordered)
    current_level = levels[-1]
    # The amount that will actually debit next is the current price level, not
    # the median across the whole history. Safe-to-Spend and the AFA band both
    # depend on this being the forward-looking figure.
    median_amount = current_level.amount_paise

    amounts = [t.amount_paise for t in ordered]
    level_amounts = [
        t.amount_paise for t in ordered if t.txn_date >= current_level.effective_from
    ] or amounts
    level_centre = median_int(level_amounts)
    amount_rel_mad = (
        median_float([abs(a - level_centre) for a in level_amounts]) / level_centre
        if level_centre
        else 1.0
    )

    first_seen = ordered[0].txn_date
    last_seen = ordered[-1].txn_date
    next_expected = last_seen + timedelta(days=int(round(median_gap)))

    if status_override is not None:
        status = status_override
    elif (as_of - last_seen).days > LAPSE_GAP_MULTIPLE * median_gap:
        status = SeriesStatus.LAPSED
    else:
        status = SeriesStatus.ACTIVE

    category_slug = ordered[-1].category_slug
    direction = ordered[0].direction

    confidence = _confidence(len(ordered), median_gap, gap_mad, amount_rel_mad)
    if status is SeriesStatus.PROBABLE:
        confidence = round(min(confidence, 0.5), 4)

    return RecurringSeries(
        normalized_merchant=ordered[0].normalized_merchant,
        category_slug=category_slug,
        direction=direction,
        cadence=nearest_cadence(median_gap),
        median_amount_paise=median_amount,
        amount_tolerance_paise=amount_tolerance(median_amount),
        median_gap_days=round(median_gap, 4),
        gap_mad=round(gap_mad, 4),
        occurrence_count=len(ordered),
        first_seen=first_seen,
        last_seen=last_seen,
        next_expected_date=next_expected,
        confidence=confidence,
        mandate_channel=infer_mandate_channel([t.raw_narration for t in ordered]),
        afa_band=derive_afa_band(median_amount, category_slug),
        status=status,
        service_type=ordered[-1].service_type,
        txn_ids=tuple(t.id for t in ordered),
        price_history=tuple(levels),
        key=series_key(ordered[0].normalized_merchant, direction, first_seen),
    )


def detect(
    txns: Sequence[Txn],
    *,
    as_of: date | None = None,
    include_probable: bool = True,
    include_credits: bool = True,
) -> list[RecurringSeries]:
    """Detect recurring series across a ledger.

    Args:
        txns: the full transaction history to analyse.
        as_of: reference date for ACTIVE/LAPSED. Defaults to the latest txn.
        include_probable: surface two-occurrence tight matches as PROBABLE.
        include_credits: detect credit series too (salary, for cash-flow).

    Returns series sorted by descending confidence then merchant, so callers
    get a stable, deterministic order.
    """
    if not txns:
        return []
    reference = as_of or max(t.txn_date for t in txns)

    grouped: dict[tuple[str, Direction], list[Txn]] = defaultdict(list)
    for txn in txns:
        if not include_credits and txn.direction is Direction.CREDIT:
            continue
        if not txn.normalized_merchant:
            continue
        grouped[(txn.normalized_merchant, txn.direction)].append(txn)

    results: list[RecurringSeries] = []
    for group in grouped.values():
        if len(group) < PROBABLE_OCCURRENCES:
            continue
        clusters = _merge_price_changes(_cluster_by_amount(group))
        for cluster in clusters:
            if not _is_dominant(cluster, group):
                continue
            if len(cluster) >= MIN_OCCURRENCES:
                if not _is_regular(cluster):
                    continue
                series = _build_series(cluster, as_of=reference)
            elif (
                include_probable
                and len(cluster) == PROBABLE_OCCURRENCES
                and _is_probable_pair(cluster)
            ):
                series = _build_series(
                    cluster, as_of=reference, status_override=SeriesStatus.PROBABLE
                )
            else:
                continue
            if series is not None:
                results.append(series)

    results.sort(key=lambda s: (-s.confidence, s.normalized_merchant))
    return results


#: Categories where two concurrent series genuinely means paying twice for the
#: same thing. Deliberately narrow: two EMIs or two insurance premiums are
#: normal and must never be badged DUPLICATE.
DUPLICATE_CANDIDATE_CATEGORIES = frozenset(
    {"subscriptions", "entertainment", "fitness"}
)


def find_duplicate_pairs(
    series: Sequence[RecurringSeries],
    *,
    amount_ratio: float = 2.0,
    categories: frozenset[str] = DUPLICATE_CANDIDATE_CATEGORIES,
) -> list[tuple[RecurringSeries, RecurringSeries]]:
    """Active series in the same category with comparable amounts.

    Powers the DUPLICATE badge in DESIGN.md section 10.1 (two music services,
    in the seeded demo). Amounts are "similar" when neither is more than
    `amount_ratio` times the other. Only categories where paying twice is
    actually redundant are considered.
    """
    active = [
        s
        for s in series
        if s.status in (SeriesStatus.ACTIVE, SeriesStatus.PROBABLE)
        and s.direction is Direction.DEBIT
        and s.category_slug in categories
    ]
    pairs: list[tuple[RecurringSeries, RecurringSeries]] = []
    for a, b in itertools.combinations(active, 2):
        if a.normalized_merchant == b.normalized_merchant:
            continue
        # Prefer service_type when enrichment has supplied it: two music
        # services are a duplicate, Adobe CC and a gym membership are not,
        # even though all three sit in the `subscriptions` category.
        if a.service_type and b.service_type:
            if a.service_type != b.service_type:
                continue
        elif a.category_slug != b.category_slug:
            continue
        lo, hi = sorted((a.median_amount_paise, b.median_amount_paise))
        if lo > 0 and hi / lo <= amount_ratio:
            pairs.append((a, b))
    return pairs


def had_price_rise(series: RecurringSeries, *, threshold: float = PRICE_CHANGE_THRESHOLD) -> bool:
    """True when the current price level is materially above the previous one."""
    if len(series.price_history) < 2:
        return False
    previous = series.price_history[-2].amount_paise
    current = series.price_history[-1].amount_paise
    return previous > 0 and (current - previous) / previous > threshold


def is_trial_conversion(series: RecurringSeries, *, ratio: float = 0.5) -> bool:
    """True when the first level sits far below the settled price.

    Powers the TRIAL->PAID badge: DESIGN.md section 10.1 defines it as a first
    occurrence well below the median with subsequent ones at the median.
    """
    if len(series.price_history) < 2:
        return False
    first = series.price_history[0].amount_paise
    settled = series.price_history[-1].amount_paise
    return settled > 0 and first < settled * ratio
