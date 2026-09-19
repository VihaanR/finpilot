"""Recurrence detection tests.

Covers the four cases BUILD_TASKS.md T06 names explicitly: a clean monthly
series is detected, three random transactions to one merchant are rejected, a
price hike does not split the series, and the RBI AFA band flips at Rs 15,000.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.engine import recurrence
from app.engine.types import (
    AfaBand,
    Cadence,
    Direction,
    MandateChannel,
    SeriesStatus,
    rupees,
)

from .conftest import monthly_run, txn


class TestCleanSeries:
    def test_detects_a_clean_monthly_series(self):
        txns = monthly_run(
            start=date(2025, 10, 5), count=12, amount_rupees=199, merchant="NETFLIX"
        )
        found = recurrence.detect(txns, as_of=date(2026, 9, 10))

        assert len(found) == 1
        got = found[0]
        assert got.normalized_merchant == "NETFLIX"
        assert got.cadence is Cadence.MONTHLY
        assert got.occurrence_count == 12
        assert got.median_amount_paise == rupees(199)
        assert got.status is SeriesStatus.ACTIVE

    def test_clean_series_is_high_confidence(self):
        txns = monthly_run(
            start=date(2025, 10, 5), count=12, amount_rupees=199, merchant="NETFLIX"
        )
        found = recurrence.detect(txns, as_of=date(2026, 9, 10))
        assert found[0].confidence > 0.9

    def test_next_expected_is_one_cadence_after_last_seen(self):
        txns = monthly_run(
            start=date(2025, 10, 5), count=12, amount_rupees=199, merchant="NETFLIX"
        )
        found = recurrence.detect(txns, as_of=date(2026, 9, 10))
        got = found[0]
        assert got.next_expected_date == got.last_seen + timedelta(days=30)

    def test_real_calendar_dates_still_detect_as_monthly(self):
        """Same day each month gives gaps of 28-31, which must read as MONTHLY."""
        dates = [date(2025, m, 5) for m in range(1, 13)]
        txns = [txn(on=d, amount_rupees=499, merchant="SPOTIFY") for d in dates]
        found = recurrence.detect(txns, as_of=date(2025, 12, 20))

        assert len(found) == 1
        assert found[0].cadence is Cadence.MONTHLY
        assert found[0].occurrence_count == 12


class TestRejection:
    def test_rejects_three_random_transactions_to_same_merchant(self):
        txns = [
            txn(on=date(2026, 1, 7), amount_rupees=1_200, merchant="AMAZON"),
            txn(on=date(2026, 2, 23), amount_rupees=4_750, merchant="AMAZON"),
            txn(on=date(2026, 5, 3), amount_rupees=890, merchant="AMAZON"),
        ]
        assert recurrence.detect(txns, as_of=date(2026, 6, 1)) == []

    def test_rejects_same_amount_at_wildly_irregular_intervals(self):
        """Equal amounts are not enough; the cadence must be regular too."""
        txns = [
            txn(on=date(2026, 1, 3), amount_rupees=500, merchant="RANDOMCO"),
            txn(on=date(2026, 1, 9), amount_rupees=500, merchant="RANDOMCO"),
            txn(on=date(2026, 4, 28), amount_rupees=500, merchant="RANDOMCO"),
            txn(on=date(2026, 5, 2), amount_rupees=500, merchant="RANDOMCO"),
        ]
        found = recurrence.detect(
            txns, as_of=date(2026, 6, 1), include_probable=False
        )
        assert found == []

    def test_single_transaction_is_never_a_series(self):
        txns = [txn(on=date(2026, 3, 1), amount_rupees=999, merchant="ONEOFF")]
        assert recurrence.detect(txns, as_of=date(2026, 4, 1)) == []

    def test_two_tight_occurrences_are_probable_not_active(self):
        txns = monthly_run(
            start=date(2026, 7, 4), count=2, amount_rupees=349, merchant="NEWSUB"
        )
        found = recurrence.detect(txns, as_of=date(2026, 9, 10))
        assert len(found) == 1
        assert found[0].status is SeriesStatus.PROBABLE
        assert found[0].confidence <= 0.5


class TestPriceHike:
    """A hike must change the amount, not fracture the series."""

    def _hiked(self):
        before = monthly_run(
            start=date(2025, 10, 5), count=8, amount_rupees=199, merchant="HOTSTAR"
        )
        after = monthly_run(
            start=date(2026, 6, 5), count=4, amount_rupees=249, merchant="HOTSTAR"
        )
        return before + after

    def test_price_hike_keeps_one_series(self):
        found = recurrence.detect(self._hiked(), as_of=date(2026, 9, 10))
        assert len(found) == 1
        assert found[0].occurrence_count == 12

    def test_price_hike_records_both_levels(self):
        found = recurrence.detect(self._hiked(), as_of=date(2026, 9, 10))
        history = found[0].price_history
        assert len(history) == 2
        assert history[0].amount_paise == rupees(199)
        assert history[1].amount_paise == rupees(249)

    def test_median_amount_is_the_current_price_not_the_old_one(self):
        """Safe-to-Spend must commit the amount that will actually debit."""
        found = recurrence.detect(self._hiked(), as_of=date(2026, 9, 10))
        assert found[0].median_amount_paise == rupees(249)

    def test_price_rise_is_flagged(self):
        found = recurrence.detect(self._hiked(), as_of=date(2026, 9, 10))
        assert recurrence.had_price_rise(found[0]) is True

    def test_flat_series_is_not_flagged_as_a_rise(self):
        flat = monthly_run(
            start=date(2025, 10, 5), count=12, amount_rupees=199, merchant="NETFLIX"
        )
        found = recurrence.detect(flat, as_of=date(2026, 9, 10))
        assert recurrence.had_price_rise(found[0]) is False

    def test_trial_to_paid_conversion_is_one_series(self):
        trial = [txn(on=date(2026, 1, 12), amount_rupees=1, merchant="AUDIBLE")]
        paid = monthly_run(
            start=date(2026, 2, 11), count=7, amount_rupees=199, merchant="AUDIBLE"
        )
        found = recurrence.detect(trial + paid, as_of=date(2026, 9, 10))
        assert len(found) == 1
        assert recurrence.is_trial_conversion(found[0]) is True


class TestAfaBand:
    """DESIGN.md R1: the RBI e-mandate silent ceiling is Rs 15,000."""

    def test_silent_at_14999(self):
        band = recurrence.derive_afa_band(rupees(14_999), "subscriptions")
        assert band is AfaBand.SILENT

    def test_requires_afa_at_15001(self):
        band = recurrence.derive_afa_band(rupees(15_001), "subscriptions")
        assert band is AfaBand.REQUIRES_AFA

    def test_exactly_at_the_ceiling_is_still_silent(self):
        assert recurrence.derive_afa_band(rupees(15_000), "rent") is AfaBand.SILENT

    def test_high_limit_category_above_the_silent_ceiling(self):
        band = recurrence.derive_afa_band(rupees(50_000), "insurance-premium")
        assert band is AfaBand.HIGH_LIMIT

    def test_high_limit_category_above_one_lakh_requires_afa(self):
        band = recurrence.derive_afa_band(rupees(1_00_001), "investment-sip")
        assert band is AfaBand.REQUIRES_AFA

    def test_detected_series_carries_the_band(self):
        txns = monthly_run(
            start=date(2025, 10, 5), count=6, amount_rupees=14_999, merchant="GYMCO"
        )
        found = recurrence.detect(txns, as_of=date(2026, 4, 10))
        assert found[0].afa_band is AfaBand.SILENT


class TestMandateChannel:
    def test_nach_marker(self):
        assert (
            recurrence.infer_mandate_channel(["ACH D- HDFC HOME LOAN EMI"])
            is MandateChannel.NACH
        )

    def test_upi_autopay_marker(self):
        assert (
            recurrence.infer_mandate_channel(["UPI-MANDATE/NETFLIX/AUTOPAY"])
            is MandateChannel.UPI_AUTOPAY
        )

    def test_card_emandate_marker(self):
        assert (
            recurrence.infer_mandate_channel(["E-MANDATE HDFC CARD SPOTIFY"])
            is MandateChannel.CARD_EMANDATE
        )

    def test_standing_instruction_marker(self):
        assert (
            recurrence.infer_mandate_channel(["SI- LIC PREMIUM DEBIT"])
            is MandateChannel.SI
        )

    def test_unknown_when_no_marker(self):
        assert (
            recurrence.infer_mandate_channel(["POS 1234 SWIGGY BANGALORE"])
            is MandateChannel.UNKNOWN
        )


class TestCadenceAndStatus:
    def test_weekly_cadence(self):
        txns = monthly_run(
            start=date(2026, 6, 1),
            count=10,
            amount_rupees=250,
            merchant="MILKMAN",
            step_days=7,
        )
        found = recurrence.detect(txns, as_of=date(2026, 8, 10))
        assert found[0].cadence is Cadence.WEEKLY

    def test_annual_cadence(self):
        txns = monthly_run(
            start=date(2021, 4, 2),
            count=5,
            amount_rupees=12_000,
            merchant="LICINDIA",
            category="insurance-premium",
            step_days=365,
        )
        found = recurrence.detect(txns, as_of=date(2025, 6, 1))
        assert found[0].cadence is Cadence.ANNUAL

    def test_series_lapses_when_long_overdue(self):
        txns = monthly_run(
            start=date(2025, 1, 5), count=6, amount_rupees=199, merchant="GONESUB"
        )
        found = recurrence.detect(txns, as_of=date(2026, 9, 10))
        assert found[0].status is SeriesStatus.LAPSED

    def test_credit_series_detected_for_salary(self):
        txns = monthly_run(
            start=date(2025, 10, 1),
            count=12,
            amount_rupees=1_50_000,
            merchant="ACME PAYROLL",
            direction=Direction.CREDIT,
            category="salary",
        )
        found = recurrence.detect(txns, as_of=date(2026, 9, 10))
        assert len(found) == 1
        assert found[0].direction is Direction.CREDIT

    def test_credits_excluded_when_asked(self):
        txns = monthly_run(
            start=date(2025, 10, 1),
            count=12,
            amount_rupees=1_50_000,
            merchant="ACME PAYROLL",
            direction=Direction.CREDIT,
        )
        assert recurrence.detect(txns, include_credits=False) == []

    def test_detection_is_deterministic(self):
        txns = monthly_run(
            start=date(2025, 10, 5), count=12, amount_rupees=199, merchant="NETFLIX"
        ) + monthly_run(
            start=date(2025, 10, 9), count=12, amount_rupees=499, merchant="SPOTIFY"
        )
        first = recurrence.detect(txns, as_of=date(2026, 9, 10))
        second = recurrence.detect(list(reversed(txns)), as_of=date(2026, 9, 10))
        assert [s.key for s in first] == [s.key for s in second]


class TestDuplicatePairs:
    def test_two_music_services_are_a_duplicate_pair(self):
        txns = monthly_run(
            start=date(2025, 10, 5), count=12, amount_rupees=199, merchant="SPOTIFY"
        ) + monthly_run(
            start=date(2025, 10, 9), count=12, amount_rupees=149, merchant="GAANA"
        )
        found = recurrence.detect(txns, as_of=date(2026, 9, 10))
        pairs = recurrence.find_duplicate_pairs(found)
        assert len(pairs) == 1
        assert {pairs[0][0].normalized_merchant, pairs[0][1].normalized_merchant} == {
            "SPOTIFY",
            "GAANA",
        }

    def test_different_categories_are_not_a_duplicate_pair(self):
        txns = monthly_run(
            start=date(2025, 10, 5),
            count=12,
            amount_rupees=199,
            merchant="SPOTIFY",
            category="subscriptions",
        ) + monthly_run(
            start=date(2025, 10, 9),
            count=12,
            amount_rupees=149,
            merchant="BESCOM",
            category="utilities",
        )
        found = recurrence.detect(txns, as_of=date(2026, 9, 10))
        assert recurrence.find_duplicate_pairs(found) == []
