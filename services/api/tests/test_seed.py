"""Seed-dataset tests.

Covers BUILD_TASKS.md T03 criterion 4 ("every planted feature is individually
greppable, a test asserts each one is present") and the two T06 acceptance
criteria that need the seed data rather than hand-built fixtures.

The window is pinned with a fixed `as_of` so these assertions stay stable as
real-world dates move. The generator is exercised in-memory; nothing here
touches the filesystem or requires `seed/output/` to exist.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from datetime import date

import pytest

from app.engine import anomaly, cashflow, recurrence
from app.engine.types import (
    AnomalyType,
    Channel,
    Direction,
    SeriesStatus,
    Severity,
    Txn,
)

SEED = 42
AS_OF = date(2026, 9, 19)

_SEED_DIR = pathlib.Path(__file__).resolve().parents[3] / "seed"


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "finpilot_seed_generate", _SEED_DIR / "generate.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gen():
    return _load_generator()


@pytest.fixture(scope="module")
def rows(gen):
    import random

    rng = random.Random(SEED)
    months = gen.month_window(AS_OF, 14)
    ledger = gen.Ledger()
    gen.gen_income(ledger, rng, months, AS_OF)
    gen.gen_committed(ledger, rng, months, AS_OF)
    gen.gen_subscriptions(ledger, rng, months, AS_OF)
    gen.gen_discretionary(ledger, rng, months, AS_OF, festival_month=months[-2])
    gen.gen_planted_events(ledger, rng, AS_OF)
    return sorted(ledger.rows, key=lambda r: r.sort_key())


@pytest.fixture(scope="module")
def txns(rows):
    return [
        Txn(
            id=f"t{i}",
            txn_date=date.fromisoformat(r.txn_date),
            amount_paise=r.amount_paise,
            direction=Direction(r.direction),
            raw_narration=r.raw_narration,
            normalized_merchant=r.normalized_merchant,
            category_slug=r.category_slug,
            channel=Channel(r.channel),
            service_type=r.service_type or None,
        )
        for i, r in enumerate(rows)
    ]


@pytest.fixture(scope="module")
def series(txns):
    return recurrence.detect(txns, as_of=AS_OF)


def tags(rows) -> set[str]:
    return {r.tag for r in rows}


# --- T03: volume and shape --------------------------------------------------


class TestVolume:
    def test_at_least_900_transactions(self, rows):
        assert len(rows) >= 900

    def test_at_least_two_accounts(self, rows):
        assert len({r.account for r in rows}) >= 2

    def test_fourteen_months_of_history(self, rows):
        months = {r.txn_date[:7] for r in rows}
        assert len(months) == 14

    def test_every_amount_is_integer_paise(self, rows):
        assert all(isinstance(r.amount_paise, int) for r in rows)

    def test_no_transaction_in_the_future(self, rows):
        assert all(date.fromisoformat(r.txn_date) <= AS_OF for r in rows)


class TestNarrationShapes:
    """T03 requires at minimum the HDFC, ICICI and SBI narration shapes."""

    def test_hdfc_upi_shape(self, rows):
        assert any(r.raw_narration.startswith("UPI/DR/") for r in rows)

    def test_icici_upi_shape(self, rows):
        assert any("/Payment to " in r.raw_narration for r in rows)

    def test_sbi_upi_shape(self, rows):
        assert any(r.raw_narration.startswith("TO TRANSFER-UPI/DR/") for r in rows)

    def test_nach_shape(self, rows):
        assert any(r.raw_narration.startswith("ACH D- ") for r in rows)

    def test_emandate_shape(self, rows):
        assert any(r.raw_narration.startswith("E-MANDATE/") for r in rows)

    def test_vpa_handles_present(self, rows):
        assert any(r.counterparty_vpa.endswith("@ybl") for r in rows)


# --- T03: every planted feature ---------------------------------------------


class TestPlantedFeatures:
    def test_salary_with_appraisal_bump(self, rows, gen):
        salary = [r for r in rows if r.category_slug == "salary"]
        amounts = {r.amount_paise for r in salary}
        assert gen.rupees(gen.SALARY_BASE) in amounts
        assert gen.rupees(gen.SALARY_AFTER_APPRAISAL) in amounts
        assert "salary-appraisal" in tags(rows)

    def test_rent_via_nach(self, rows):
        rent = [r for r in rows if r.tag == "rent"]
        assert rent
        assert all(r.raw_narration.startswith("ACH D- ") for r in rent)

    def test_two_emis(self, rows):
        assert {"emi-home", "emi-car"} <= tags(rows)

    def test_utilities_with_summer_variance(self, rows):
        summer = [r.amount_paise for r in rows
                  if r.tag == "utility-electricity-summer"]
        winter = [r.amount_paise for r in rows if r.tag == "utility-electricity"]
        assert summer and winter
        assert min(summer) > max(winter)

    def test_nine_subscriptions(self, rows, gen):
        merchants = {r.normalized_merchant for r in rows
                     if r.category_slug == "subscriptions"}
        assert len(merchants) == 9
        assert merchants == {s["merchant"] for s in gen.SUBSCRIPTIONS}

    def test_price_hike_planted(self, rows):
        assert "subscription-price-hike" in tags(rows)
        hotstar = sorted(
            (r for r in rows if r.normalized_merchant == "HOTSTAR"),
            key=lambda r: r.txn_date,
        )
        assert hotstar[0].amount_paise < hotstar[-1].amount_paise

    def test_trial_conversion_planted(self, rows):
        assert "subscription-trial" in tags(rows)
        audible = sorted(
            (r for r in rows if r.normalized_merchant == "AUDIBLE"),
            key=lambda r: r.txn_date,
        )
        assert audible[0].amount_paise == 100  # Rs 1 trial
        assert audible[-1].amount_paise == 19_900

    def test_duplicate_music_pair_planted(self, rows):
        music = {r.normalized_merchant for r in rows if r.service_type == "music"}
        assert music == {"SPOTIFY", "GAANA"}

    def test_dormant_subscription_planted(self, rows):
        cultfit = [r for r in rows if r.normalized_merchant == "CULTFIT"]
        assert cultfit
        assert all(r.category_slug == "subscriptions" for r in cultfit)

    def test_festival_category_spike_planted(self, rows):
        assert "festival-shopping" in tags(rows)

    def test_duplicate_charge_planted(self, rows):
        dupes = [r for r in rows if r.tag == "duplicate-charge"]
        assert len(dupes) == 2
        assert dupes[0].amount_paise == dupes[1].amount_paise
        gap = (date.fromisoformat(dupes[1].txn_date)
               - date.fromisoformat(dupes[0].txn_date)).days
        assert 0 < gap <= 3  # within the 72-hour window

    def test_new_large_merchant_planted(self, rows):
        big = [r for r in rows if r.tag == "new-large-merchant"]
        assert len(big) == 1
        assert big[0].normalized_merchant == "CROMA"
        assert big[0].amount_paise == 42_00_000

    def test_two_goals_one_on_track_one_behind(self, gen):
        goals = gen.build_goals(AS_OF)
        assert len(goals) == 2
        assert {g["expected_verdict"] for g in goals} == {"ON_TRACK", "BEHIND"}

    def test_budgets_for_six_categories(self, rows, gen):
        budgets = gen.build_budgets(rows, AS_OF)
        assert len(budgets) == 6
        assert all(isinstance(b["limit_paise"], int) for b in budgets)


# --- T06: engine behaviour on the seed --------------------------------------


class TestEngineOnSeed:
    def test_all_nine_subscriptions_are_detected(self, series):
        """The count BUILD_TASKS.md T06 and T11 care about."""
        subs = {
            s.normalized_merchant
            for s in series
            if s.category_slug == "subscriptions"
            and s.status in (SeriesStatus.ACTIVE, SeriesStatus.PROBABLE)
        }
        assert len(subs) == 9

    def test_committed_obligations_are_detected(self, series):
        """Rent, both EMIs, the SIP and the fixed utilities."""
        merchants = {
            s.normalized_merchant for s in series if s.status is SeriesStatus.ACTIVE
        }
        assert {
            "PRESTIGE LANDLORD",
            "HDFC HOME LOAN",
            "HDFC CAR LOAN",
            "ZERODHA COIN",
            "ACT FIBERNET",
            "JIO",
        } <= merchants

    def test_salary_credit_series_is_detected(self, series):
        salary = [s for s in series if s.direction is Direction.CREDIT
                  and s.normalized_merchant == "ACME TECHNOLOGIES"]
        assert len(salary) == 1
        assert salary[0].median_amount_paise == 1_32_000_00  # post-appraisal

    def test_price_hiked_item_is_flagged(self, series):
        hotstar = next(s for s in series if s.normalized_merchant == "HOTSTAR")
        assert recurrence.had_price_rise(hotstar)
        assert hotstar.median_amount_paise == 399_00
        assert len(hotstar.price_history) == 2

    def test_trial_conversion_is_flagged(self, series):
        audible = next(s for s in series if s.normalized_merchant == "AUDIBLE")
        assert recurrence.is_trial_conversion(audible)

    def test_duplicate_music_pair_is_flagged(self, series):
        pairs = recurrence.find_duplicate_pairs(series)
        flagged = {
            frozenset((a.normalized_merchant, b.normalized_merchant))
            for a, b in pairs
        }
        assert frozenset(("SPOTIFY", "GAANA")) in flagged

    def test_no_phantom_series_from_busy_merchants(self, series):
        """Food-delivery merchants must not masquerade as subscriptions.

        This is the regression guard for the over-firing the first version of
        the detector showed on this dataset: Swiggy and Zomato each produced
        several phantom "recurring series" purely by coincidence.
        """
        active = {
            s.normalized_merchant for s in series if s.status is SeriesStatus.ACTIVE
        }
        assert not ({"SWIGGY", "ZOMATO", "ZEPTO", "BLINKIT"} & active)

    def test_all_five_anomaly_types_fire(self, txns, series):
        found = anomaly.detect(txns, series, period=AS_OF)
        assert {a.type for a in found} == {
            AnomalyType.CATEGORY_SPIKE,
            AnomalyType.NEW_LARGE_MERCHANT,
            AnomalyType.DUPLICATE_CHARGE,
            AnomalyType.PRICE_HIKE,
            AnomalyType.SILENT_MANDATE,
        }

    def test_anomaly_volume_is_reviewable(self, txns, series):
        """A dashboard that shows 200 anomalies has shown the user nothing.

        Silent mandates are excluded from the cap deliberately: they are the
        Mandate Radar inventory, not alerts, and one per active silent series
        is exactly right. Everything else must stay small enough to read.
        """
        found = anomaly.detect(txns, series, period=AS_OF)
        alerts = [a for a in found if a.type is not AnomalyType.SILENT_MANDATE]
        assert len(alerts) <= 10, [a.explanation for a in alerts]

    def test_one_silent_mandate_per_unacknowledged_silent_series(self, txns, series):
        found = anomaly.detect(txns, series, period=AS_OF)
        silent = [a for a in found if a.type is AnomalyType.SILENT_MANDATE]
        expected = [
            s for s in series
            if s.status is SeriesStatus.ACTIVE
            and s.direction is Direction.DEBIT
            and s.afa_band.value == "SILENT"
            and not s.acknowledged
        ]
        assert len(silent) == len(expected)

    def test_exactly_one_price_hike_is_reported(self, txns, series):
        """The seed plants exactly one, on HOTSTAR."""
        found = anomaly.detect(txns, series, period=AS_OF)
        hikes = [a for a in found if a.type is AnomalyType.PRICE_HIKE]
        assert len(hikes) == 1
        assert hikes[0].metric["merchant"] == "HOTSTAR"

    def test_festival_spike_is_the_only_high_severity_category_spike(
        self, txns, series
    ):
        """Ranked by severity, not by z.

        A very regular category such as `subscriptions` has a tiny MAD, so a
        13% wobble scores a higher z than the festival month's genuine 4.4x.
        Severity folds in effect size, which is why it is the right ordering
        for anything a user sees.
        """
        found = anomaly.detect(txns, series, period=AS_OF)
        spikes = [a for a in found if a.type is AnomalyType.CATEGORY_SPIKE]
        high = [a for a in spikes if a.severity is Severity.HIGH]
        assert len(high) == 1
        assert high[0].metric["category_slug"] == "shopping"
        assert float(high[0].metric["observed_paise"]) > 3 * float(
            high[0].metric["baseline_paise"]
        )

    def test_safe_to_spend_is_coherent(self, series):
        result = cashflow.safe_to_spend(
            series, [], current_balance_paise=1_85_000_00, as_of=AS_OF
        )
        assert result.next_income_date is not None
        assert result.next_income_date > AS_OF
        assert result.committed_paise > 0
        assert result.discretionary_paise == (
            result.current_balance_paise - result.committed_paise
            - result.goal_due_paise
        )

    def test_upcoming_obligations_are_forward_dated(self, series):
        obligations = cashflow.upcoming(series, days=30, as_of=AS_OF)
        assert obligations
        assert all(o.due_date >= AS_OF for o in obligations)

    def test_silent_band_dominates_the_radar(self, series):
        """The product's core claim: most mandates debit without asking."""
        active_debits = [
            s for s in series
            if s.status is SeriesStatus.ACTIVE and s.direction is Direction.DEBIT
        ]
        silent = [s for s in active_debits if s.afa_band.value == "SILENT"]
        assert len(silent) > len(active_debits) / 2
