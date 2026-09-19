"""Anomaly detection tests.

BUILD_TASKS.md T06 requires each of the five DESIGN.md section 8.2 types to
fire on a constructed positive case and stay silent on a negative one.
"""

from __future__ import annotations

from datetime import date

from app.engine import anomaly, recurrence
from app.engine.anomaly import InsufficientHistory
from app.engine.types import AnomalyType, Severity, rupees

from .conftest import monthly_run, series, txn

SEPT = date(2026, 9, 15)
#: Spike detection refuses a month still in progress, so these tests observe
#: September from a vantage point where it has fully elapsed.
SEPT_COMPLETE = date(2026, 9, 30)
OCT = date(2026, 10, 10)

#: Six months of steady shopping, then the month under test.
_BASELINE = {
    date(2026, 3, 12): 4_800,
    date(2026, 4, 12): 5_200,
    date(2026, 5, 12): 4_900,
    date(2026, 6, 12): 5_100,
    date(2026, 7, 12): 5_000,
    date(2026, 8, 12): 5_050,
}


def _shopping_history(september_rupees: int):
    rows = [
        txn(on=on, amount_rupees=amount, merchant="DMART", category="shopping")
        for on, amount in _BASELINE.items()
    ]
    rows.append(
        txn(
            on=date(2026, 9, 12),
            amount_rupees=september_rupees,
            merchant="DMART",
            category="shopping",
        )
    )
    return rows


class TestCategorySpike:
    def test_fires_on_a_festival_month_spike(self):
        found = anomaly.detect_category_spikes(
            _shopping_history(40_000), period=SEPT, as_of=SEPT_COMPLETE
        )
        assert isinstance(found, list)
        spikes = [a for a in found if a.type is AnomalyType.CATEGORY_SPIKE]
        assert len(spikes) == 1
        assert spikes[0].severity is Severity.HIGH
        assert spikes[0].metric["category_slug"] == "shopping"

    def test_does_not_fire_on_a_normal_month(self):
        found = anomaly.detect_category_spikes(
            _shopping_history(5_100), period=SEPT, as_of=SEPT_COMPLETE
        )
        assert isinstance(found, list)
        assert [a for a in found if a.type is AnomalyType.CATEGORY_SPIKE] == []

    def test_explanation_names_the_figures(self):
        found = anomaly.detect_category_spikes(
            _shopping_history(40_000), period=SEPT, as_of=SEPT_COMPLETE
        )
        text = found[0].explanation
        assert "shopping" in text
        assert "40,000" in text

    def test_insufficient_history_is_explicit(self):
        """Fewer than three prior months must not produce a fabricated baseline."""
        rows = [
            txn(on=date(2026, 8, 12), amount_rupees=5_000, merchant="DMART",
                category="shopping"),
            txn(on=date(2026, 9, 12), amount_rupees=40_000, merchant="DMART",
                category="shopping"),
        ]
        found = anomaly.detect_category_spikes(
            rows, period=SEPT, as_of=SEPT_COMPLETE
        )
        assert isinstance(found, InsufficientHistory)
        assert found.reason == "insufficient_history"
        assert found.months_available == 1

    def test_month_in_progress_is_refused(self):
        """A part-month has no comparable baseline and must say so."""
        found = anomaly.detect_category_spikes(
            _shopping_history(40_000), period=SEPT, as_of=date(2026, 9, 12)
        )
        assert isinstance(found, InsufficientHistory)
        assert found.reason == "month_in_progress"

    def test_small_but_significant_change_is_not_a_spike(self):
        """Effect size gates significance: a 15% wobble is not a spike."""
        found = anomaly.detect_category_spikes(
            _shopping_history(5_800), period=SEPT, as_of=SEPT_COMPLETE
        )
        assert isinstance(found, list)
        assert [a for a in found if a.type is AnomalyType.CATEGORY_SPIKE] == []


class TestNewLargeMerchant:
    def _history(self, new_merchant_rupees: int):
        rows = monthly_run(
            start=date(2026, 1, 8),
            count=20,
            amount_rupees=500,
            merchant="KIRANA",
            category="groceries",
            step_days=12,
        )
        rows.append(
            txn(
                on=date(2026, 9, 9),
                amount_rupees=new_merchant_rupees,
                merchant="CROMA",
                category="shopping",
            )
        )
        return rows

    def test_fires_on_a_large_first_time_merchant(self):
        found = anomaly.detect_new_large_merchants(self._history(42_000), period=SEPT)
        assert len(found) == 1
        assert found[0].type is AnomalyType.NEW_LARGE_MERCHANT
        assert found[0].metric["merchant"] == "CROMA"

    def test_does_not_fire_on_a_small_first_time_merchant(self):
        found = anomaly.detect_new_large_merchants(self._history(300), period=SEPT)
        assert found == []

    def test_does_not_fire_for_an_established_merchant(self):
        """A large charge to a familiar merchant is not a *new* merchant."""
        rows = monthly_run(
            start=date(2026, 1, 8),
            count=20,
            amount_rupees=500,
            merchant="KIRANA",
            category="groceries",
            step_days=12,
        )
        rows.append(
            txn(on=date(2026, 9, 9), amount_rupees=42_000, merchant="KIRANA",
                category="groceries")
        )
        assert anomaly.detect_new_large_merchants(rows, period=SEPT) == []


class TestDuplicateCharge:
    def test_fires_on_the_same_charge_forty_hours_apart(self):
        rows = [
            txn(on=date(2026, 9, 4), amount_rupees=1_299, merchant="BIGBASKET"),
            txn(on=date(2026, 9, 6), amount_rupees=1_299, merchant="BIGBASKET"),
        ]
        found = anomaly.detect_duplicate_charges(rows)
        assert len(found) == 1
        assert found[0].severity is Severity.HIGH
        assert found[0].metric["amount_paise"] == rupees(1_299)

    def test_does_not_fire_outside_the_window(self):
        rows = [
            txn(on=date(2026, 9, 4), amount_rupees=1_299, merchant="BIGBASKET"),
            txn(on=date(2026, 9, 14), amount_rupees=1_299, merchant="BIGBASKET"),
        ]
        assert anomaly.detect_duplicate_charges(rows) == []

    def test_does_not_fire_on_different_amounts(self):
        rows = [
            txn(on=date(2026, 9, 4), amount_rupees=1_299, merchant="BIGBASKET"),
            txn(on=date(2026, 9, 5), amount_rupees=1_300, merchant="BIGBASKET"),
        ]
        assert anomaly.detect_duplicate_charges(rows) == []

    def test_does_not_fire_across_different_merchants(self):
        rows = [
            txn(on=date(2026, 9, 4), amount_rupees=1_299, merchant="BIGBASKET"),
            txn(on=date(2026, 9, 5), amount_rupees=1_299, merchant="BLINKIT"),
        ]
        assert anomaly.detect_duplicate_charges(rows) == []


class TestPriceHike:
    def _hiked_series(self):
        rows = monthly_run(
            start=date(2025, 10, 5), count=8, amount_rupees=199, merchant="HOTSTAR"
        ) + monthly_run(
            start=date(2026, 6, 5), count=4, amount_rupees=249, merchant="HOTSTAR"
        )
        return recurrence.detect(rows, as_of=date(2026, 9, 10))

    def test_fires_on_a_price_rise(self):
        found = anomaly.detect_price_hikes(self._hiked_series())
        assert len(found) == 1
        assert found[0].type is AnomalyType.PRICE_HIKE
        assert found[0].metric["previous_paise"] == rupees(199)
        assert found[0].metric["current_paise"] == rupees(249)

    def test_reports_the_percentage(self):
        found = anomaly.detect_price_hikes(self._hiked_series())
        assert found[0].metric["pct_change"] == round((249 - 199) / 199, 4)

    def test_does_not_fire_on_a_flat_series(self):
        flat = recurrence.detect(
            monthly_run(
                start=date(2025, 10, 5), count=12, amount_rupees=199,
                merchant="NETFLIX",
            ),
            as_of=date(2026, 9, 10),
        )
        assert anomaly.detect_price_hikes(flat) == []


class TestSilentMandate:
    def test_fires_on_an_unacknowledged_silent_series(self):
        rows = [
            series(
                merchant="NETFLIX",
                amount_rupees=499,
                category="subscriptions",
                next_expected=date(2026, 9, 20),
            )
        ]
        found = anomaly.detect_silent_mandates(rows)
        assert len(found) == 1
        assert found[0].type is AnomalyType.SILENT_MANDATE
        assert "without asking you" in found[0].explanation

    def test_does_not_fire_once_acknowledged(self):
        rows = [
            series(
                merchant="NETFLIX",
                amount_rupees=499,
                category="subscriptions",
                next_expected=date(2026, 9, 20),
                acknowledged=True,
            )
        ]
        assert anomaly.detect_silent_mandates(rows) == []

    def test_does_not_fire_above_the_silent_ceiling(self):
        rows = [
            series(
                merchant="LANDLORD",
                amount_rupees=25_000,
                category="rent",
                next_expected=date(2026, 9, 20),
            )
        ]
        assert anomaly.detect_silent_mandates(rows) == []


class TestOrchestration:
    def test_detect_runs_every_type_and_sorts_by_severity(self):
        rows = _shopping_history(40_000) + [
            txn(on=date(2026, 9, 4), amount_rupees=1_299, merchant="BIGBASKET"),
            txn(on=date(2026, 9, 6), amount_rupees=1_299, merchant="BIGBASKET"),
        ]
        found = anomaly.detect(
            rows,
            [
                series(
                    merchant="NETFLIX",
                    amount_rupees=499,
                    category="subscriptions",
                    next_expected=date(2026, 9, 20),
                )
            ],
            period=OCT,
        )
        types = {a.type for a in found}
        assert AnomalyType.CATEGORY_SPIKE in types
        assert AnomalyType.DUPLICATE_CHARGE in types
        assert AnomalyType.SILENT_MANDATE in types

        severities = [a.severity for a in found]
        assert severities == sorted(
            severities, key=lambda s: {Severity.HIGH: 0, Severity.MEDIUM: 1,
                                       Severity.LOW: 2}[s]
        )

    def test_empty_input_is_empty_output(self):
        assert anomaly.detect([], []) == []

    def test_all_five_types_can_fire_together(self):
        """The seed dataset must light up every detector; prove it is possible."""
        hiked = monthly_run(
            start=date(2025, 10, 5), count=8, amount_rupees=199, merchant="HOTSTAR"
        ) + monthly_run(
            start=date(2026, 6, 5), count=4, amount_rupees=249, merchant="HOTSTAR"
        )
        detected = recurrence.detect(hiked, as_of=date(2026, 9, 10))
        rows = (
            _shopping_history(40_000)
            + hiked
            + [
                txn(on=date(2026, 9, 4), amount_rupees=1_299, merchant="BIGBASKET"),
                txn(on=date(2026, 9, 6), amount_rupees=1_299, merchant="BIGBASKET"),
            ]
            + monthly_run(
                start=date(2026, 1, 8), count=20, amount_rupees=500,
                merchant="KIRANA", category="groceries", step_days=12,
            )
            + [txn(on=date(2026, 10, 9), amount_rupees=42_000, merchant="CROMA",
                   category="shopping")]
        )
        found = anomaly.detect(rows, detected, period=OCT)
        types = {a.type for a in found}
        assert types == {
            AnomalyType.CATEGORY_SPIKE,
            AnomalyType.NEW_LARGE_MERCHANT,
            AnomalyType.DUPLICATE_CHARGE,
            AnomalyType.PRICE_HIKE,
            AnomalyType.SILENT_MANDATE,
        }
