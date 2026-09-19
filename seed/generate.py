"""Deterministic synthetic Indian statement generator.

Implements DESIGN.md section 6.3 and BUILD_TASKS.md T03. Produces 14 months of
data ending at the current month, containing *by construction* one instance of
everything the demo needs to show, plus `seed/expected.json` holding the
ground-truth answers computed directly from the generated rows.

Determinism: every random draw comes from a single seeded `random.Random`, and
output is sorted and serialised with stable formatting. Two runs on the same
day with the same seed produce byte-identical files. The month window is
anchored to today, so pass `--as-of` to pin it across days.

    python seed/generate.py --seed 42
    python seed/generate.py --seed 42 --as-of 2026-09-19
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

PAISE = 100


def rupees(amount: float) -> int:
    """Rupees -> integer paise. The only place a float touches money."""
    return int(round(amount * PAISE))


# --- Accounts ---------------------------------------------------------------

ACCOUNTS = [
    {
        "key": "hdfc_savings",
        "bank_code": "HDFC",
        "account_type": "SAVINGS",
        "display_name": "HDFC Bank Savings",
        "last4": "4821",
        "opening_balance_paise": rupees(1_85_000),
    },
    {
        "key": "icici_credit",
        "bank_code": "ICICI",
        "account_type": "CREDIT_CARD",
        "display_name": "ICICI Amazon Pay Card",
        "last4": "7734",
        "opening_balance_paise": 0,
    },
    {
        "key": "sbi_savings",
        "bank_code": "SBI",
        "account_type": "SAVINGS",
        "display_name": "SBI Savings",
        "last4": "9102",
        "opening_balance_paise": rupees(42_000),
    },
]


# --- Narration shapes -------------------------------------------------------
# Three real Indian bank narration formats, per BUILD_TASKS.md T03.


def _ref(rng: random.Random) -> str:
    """A 12-digit UPI reference number."""
    return "".join(rng.choice("0123456789") for _ in range(12))


def narrate(rng: random.Random, bank: str, merchant: str, vpa: str, channel: str) -> str:
    ref = _ref(rng)
    handle = vpa.split("@")[-1].upper() if "@" in vpa else "YBL"

    if channel == "NACH":
        return f"ACH D- {merchant} {ref}"
    if channel == "EMANDATE":
        return f"E-MANDATE/{merchant}/AUTOPAY/{ref}"
    if channel == "SI":
        return f"SI- {merchant} PREMIUM {ref}"
    if channel == "ATM":
        return f"ATW-{rng.randint(1000, 9999)}-{merchant}"
    if channel == "CARD":
        return f"POS {rng.randint(1000, 9999)} {merchant} BENGALURU"
    if channel == "NEFT":
        return f"NEFT DR-{bank}0000523-{merchant}-{ref}"

    # UPI, one shape per bank.
    if bank == "HDFC":
        return f"UPI/DR/{ref}/{merchant}/{handle}/Payment from ph"
    if bank == "ICICI":
        return f"UPI/{ref}/Payment to {merchant}/{vpa}/ICIC"
    if bank == "SBI":
        return f"TO TRANSFER-UPI/DR/{ref}/{merchant}/{handle}/{vpa}--"
    return f"UPI/DR/{ref}/{merchant}/{handle}/Payment"


# --- Merchant catalogue -----------------------------------------------------

FOOD_DELIVERY = [
    ("SWIGGY", "swiggy@ybl", 180, 720),
    ("ZOMATO", "zomato@paytm", 200, 850),
    ("BLINKIT", "blinkit@okaxis", 150, 900),
    ("ZEPTO", "zepto@ybl", 120, 640),
]
GROCERIES = [
    ("BIGBASKET", "bigbasket@ybl", 450, 2400),
    ("DMART", "dmart@okhdfcbank", 600, 3200),
    ("INSTAMART", "instamart@ybl", 300, 1400),
]
TRANSPORT = [
    ("UBER", "uber@ybl", 90, 480),
    ("OLA", "ola@paytm", 80, 420),
    ("RAPIDO", "rapido@ybl", 45, 210),
    ("INDIANOIL", "indianoil@okicici", 500, 2600),
]
DINING = [
    ("THIRDWAVE", "thirdwave@ybl", 220, 780),
    ("TRUFFLES", "truffles@okaxis", 450, 1600),
    ("CHAIPOINT", "chaipoint@ybl", 90, 340),
]
SHOPPING = [
    ("AMAZON", "amazon@apl", 400, 3800),
    ("FLIPKART", "flipkart@ybl", 350, 3200),
    ("MYNTRA", "myntra@ybl", 600, 2800),
    ("NYKAA", "nykaa@ybl", 400, 2200),
]
PERSONAL = [
    ("APOLLOPHARMACY", "apollo@okhdfcbank", 200, 1400),
    ("PHARMEASY", "pharmeasy@ybl", 250, 1600),
    ("URBANCOMPANY", "urbancompany@ybl", 500, 2200),
]

#: The nine subscriptions BUILD_TASKS.md T03 requires, with their planted
#: quirks: one price hike, one duplicate pair, one trial conversion, one
#: dormant service.
SUBSCRIPTIONS = [
    {"service": "video", "merchant": "NETFLIX", "vpa": "netflix@icici", "amount": 649, "day": 3,
     "cadence": "monthly", "channel": "EMANDATE", "account": "icici_credit"},
    {"service": "music", "merchant": "SPOTIFY", "vpa": "spotify@icici", "amount": 119, "day": 8,
     "cadence": "monthly", "channel": "EMANDATE", "account": "icici_credit",
     "note": "duplicate-pair"},
    {"service": "music", "merchant": "GAANA", "vpa": "gaana@ybl", "amount": 99, "day": 11,
     "cadence": "monthly", "channel": "EMANDATE", "account": "icici_credit",
     "note": "duplicate-pair"},
    {"service": "video", "merchant": "HOTSTAR", "vpa": "hotstar@icici", "amount": 299, "day": 14,
     "cadence": "monthly", "channel": "EMANDATE", "account": "icici_credit",
     "note": "price-hike", "hike_to": 399, "hike_month_index": 9},
    {"service": "audiobooks", "merchant": "AUDIBLE", "vpa": "audible@apl", "amount": 199, "day": 19,
     "cadence": "monthly", "channel": "EMANDATE", "account": "icici_credit",
     "note": "trial-conversion", "trial_amount": 1, "starts_month_index": 4},
    {"service": "fitness", "merchant": "CULTFIT", "vpa": "cultfit@ybl", "amount": 1399, "day": 22,
     "cadence": "monthly", "channel": "EMANDATE", "account": "icici_credit",
     "note": "dormant"},
    {"service": "productivity", "merchant": "ADOBECC", "vpa": "adobe@icici", "amount": 1675, "day": 25,
     "cadence": "monthly", "channel": "EMANDATE", "account": "icici_credit"},
    {"service": "storage", "merchant": "ICLOUD", "vpa": "icloud@apl", "amount": 75, "day": 27,
     "cadence": "monthly", "channel": "EMANDATE", "account": "icici_credit"},
    {"service": "retail-membership", "merchant": "AMAZONPRIME", "vpa": "amazonprime@apl", "amount": 1499, "day": 16,
     "cadence": "annual", "channel": "EMANDATE", "account": "icici_credit"},
]


@dataclass
class Row:
    account: str
    txn_date: str
    amount_paise: int
    direction: str
    raw_narration: str
    normalized_merchant: str
    counterparty_vpa: str
    channel: str
    category_slug: str
    service_type: str = ""  # what kind of service, for duplicate detection
    tag: str = ""  # marks planted features so tests can grep for them

    def sort_key(self):
        return (self.txn_date, self.account, self.normalized_merchant,
                self.amount_paise, self.raw_narration)


@dataclass
class Ledger:
    rows: list[Row] = field(default_factory=list)

    def add(self, **kwargs) -> None:
        self.rows.append(Row(**kwargs))


# --- Calendar helpers -------------------------------------------------------


def month_window(as_of: date, count: int = 14) -> list[tuple[int, int]]:
    """The `count` months ending at (and including) the month of `as_of`."""
    months: list[tuple[int, int]] = []
    year, month = as_of.year, as_of.month
    for _ in range(count):
        months.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(months))


def clamp_day(year: int, month: int, day: int) -> date:
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    return date(year, month, min(day, last.day))


# --- Generators -------------------------------------------------------------

SALARY_BASE = 1_10_000
SALARY_AFTER_APPRAISAL = 1_32_000
APPRAISAL_MONTH_INDEX = 8  # BUILD_TASKS.md T03: appraisal bump at month 8
HIKE_MONTH_INDEX = 9       # and the subscription price hike at month 9


def gen_income(ledger: Ledger, rng: random.Random, months, as_of: date) -> None:
    """Monthly salary on the 1st, with one appraisal bump."""
    for index, (year, month) in enumerate(months):
        when = clamp_day(year, month, 1)
        if when > as_of:
            continue
        gross = SALARY_BASE if index < APPRAISAL_MONTH_INDEX else SALARY_AFTER_APPRAISAL
        ledger.add(
            account="hdfc_savings",
            txn_date=when.isoformat(),
            amount_paise=rupees(gross),
            direction="CREDIT",
            raw_narration=f"NEFT CR-ACME0000191-ACME TECHNOLOGIES PVT LTD-SALARY-{_ref(rng)}",
            normalized_merchant="ACME TECHNOLOGIES",
            counterparty_vpa="",
            channel="NEFT",
            category_slug="salary",
            tag="salary-appraisal" if index == APPRAISAL_MONTH_INDEX else "salary",
        )
        # A small quarterly interest credit on the SBI account.
        if month % 3 == 0:
            interest = clamp_day(year, month, 28)
            if interest <= as_of:
                ledger.add(
                    account="sbi_savings",
                    txn_date=interest.isoformat(),
                    amount_paise=rupees(rng.randint(210, 380)),
                    direction="CREDIT",
                    raw_narration=f"CREDIT INTEREST CAPITALISED-{_ref(rng)}",
                    normalized_merchant="SBI INTEREST",
                    counterparty_vpa="",
                    channel="OTHER",
                    category_slug="interest",
                    tag="interest",
                )


def gen_committed(ledger: Ledger, rng: random.Random, months, as_of: date) -> None:
    """Rent via NACH, two EMIs, utilities with seasonal variance, SIP, insurance."""
    for index, (year, month) in enumerate(months):

        def place(day, merchant, vpa, amount_paise, category, channel, tag,
                  account="hdfc_savings"):
            when = clamp_day(year, month, day)
            if when > as_of:
                return
            ledger.add(
                account=account,
                txn_date=when.isoformat(),
                amount_paise=amount_paise,
                direction="DEBIT",
                raw_narration=narrate(rng, ACCOUNTS[0]["bank_code"], merchant, vpa,
                                      channel),
                normalized_merchant=merchant,
                counterparty_vpa=vpa,
                channel="NACH" if channel in ("NACH", "SI") else (
                    "CARD" if channel == "EMANDATE" else channel),
                category_slug=category,
                tag=tag,
            )

        # Rent, by NACH mandate.
        place(5, "PRESTIGE LANDLORD", "", rupees(28_000), "rent", "NACH", "rent")
        # Two EMIs, both auto-debited.
        place(7, "HDFC HOME LOAN", "", rupees(24_500), "emi-loan-repayment",
              "NACH", "emi-home")
        place(12, "HDFC CAR LOAN", "", rupees(12_800), "emi-loan-repayment",
              "NACH", "emi-car")
        # Electricity: materially higher through the summer months.
        summer = month in (4, 5, 6)
        power = rng.randint(3_200, 3_900) if summer else rng.randint(1_450, 2_100)
        place(9, "BESCOM", "bescom@okhdfcbank", rupees(power), "electricity",
              "UPI", "utility-electricity-summer" if summer else "utility-electricity")
        place(15, "ACT FIBERNET", "actfibernet@ybl", rupees(1_299), "broadband",
              "UPI", "utility-broadband")
        place(18, "JIO", "jio@okhdfcbank", rupees(799), "mobile", "UPI",
              "utility-mobile")
        if index % 2 == 0:
            place(21, "INDANE GAS", "indane@ybl", rupees(1_105), "gas", "UPI",
                  "utility-gas")
        # Monthly SIP and an annual insurance premium.
        place(10, "ZERODHA COIN", "zerodha@ybl", rupees(10_000), "investment-sip",
              "NACH", "sip")
        if month == 6:
            place(20, "LIC INDIA", "", rupees(18_500), "insurance-premium", "SI",
                  "insurance-annual")


def gen_subscriptions(ledger: Ledger, rng: random.Random, months, as_of: date) -> None:
    """Nine subscriptions with the four planted quirks."""
    for sub in SUBSCRIPTIONS:
        starts = sub.get("starts_month_index", 0)
        for index, (year, month) in enumerate(months):
            if index < starts:
                continue
            if sub["cadence"] == "annual" and index % 12 != 0:
                continue

            amount = sub["amount"]
            tag = f"subscription-{sub['merchant'].lower()}"

            if sub.get("note") == "price-hike" and index >= sub["hike_month_index"]:
                amount = sub["hike_to"]
                tag = "subscription-price-hike"
            if sub.get("note") == "trial-conversion" and index == starts:
                amount = sub["trial_amount"]
                tag = "subscription-trial"

            when = clamp_day(year, month, sub["day"])
            if when > as_of:
                continue
            ledger.add(
                account=sub["account"],
                txn_date=when.isoformat(),
                amount_paise=rupees(amount),
                direction="DEBIT",
                raw_narration=narrate(rng, "ICICI", sub["merchant"], sub["vpa"],
                                      sub["channel"]),
                normalized_merchant=sub["merchant"],
                counterparty_vpa=sub["vpa"],
                channel="CARD",
                category_slug="subscriptions",
                service_type=sub["service"],
                tag=tag,
            )


def gen_discretionary(ledger: Ledger, rng: random.Random, months, as_of: date,
                      festival_month: tuple[int, int]) -> None:
    """Everyday spend, with a 3.5x shopping spike in the festival month."""
    plan = [
        (FOOD_DELIVERY, "food-delivery", 15, "hdfc_savings", "HDFC"),
        (GROCERIES, "groceries", 8, "hdfc_savings", "HDFC"),
        (TRANSPORT, "transport-fuel", 12, "hdfc_savings", "HDFC"),
        (DINING, "dining-out", 6, "icici_credit", "ICICI"),
        (SHOPPING, "shopping", 4, "icici_credit", "ICICI"),
        (PERSONAL, "personal-care", 3, "hdfc_savings", "HDFC"),
    ]

    for year, month in months:
        is_festival = (year, month) == festival_month
        for catalogue, category, per_month, account, bank in plan:
            count = per_month
            multiplier = 1.0
            if is_festival and category == "shopping":
                # BUILD_TASKS.md T03: festival-month shopping ~3.5x baseline.
                count = per_month * 2
                multiplier = 1.75
            for _ in range(count):
                merchant, vpa, low, high = catalogue[rng.randrange(len(catalogue))]
                day = rng.randint(1, 28)
                when = clamp_day(year, month, day)
                if when > as_of:
                    continue
                amount = rng.randint(low, high) * multiplier
                ledger.add(
                    account=account,
                    txn_date=when.isoformat(),
                    amount_paise=rupees(round(amount)),
                    direction="DEBIT",
                    raw_narration=narrate(rng, bank, merchant, vpa, "UPI"),
                    normalized_merchant=merchant,
                    counterparty_vpa=vpa,
                    channel="UPI",
                    category_slug=category,
                    tag="festival-shopping" if (is_festival and category == "shopping")
                        else category,
                )

        # Two cash withdrawals a month.
        for _ in range(2):
            when = clamp_day(year, month, rng.randint(2, 27))
            if when > as_of:
                continue
            ledger.add(
                account="hdfc_savings",
                txn_date=when.isoformat(),
                amount_paise=rupees(rng.choice([2_000, 3_000, 5_000])),
                direction="DEBIT",
                raw_narration=narrate(rng, "HDFC", "INDIRANAGAR", "", "ATM"),
                normalized_merchant="ATM WITHDRAWAL",
                counterparty_vpa="",
                channel="ATM",
                category_slug="cash-withdrawal",
                tag="atm",
            )

        # A monthly transfer to the SBI account, so it is not inert.
        when = clamp_day(year, month, 6)
        if when <= as_of:
            ledger.add(
                account="sbi_savings",
                txn_date=when.isoformat(),
                amount_paise=rupees(8_000),
                direction="CREDIT",
                raw_narration=narrate(rng, "SBI", "SELF TRANSFER", "self@okhdfcbank",
                                      "UPI"),
                normalized_merchant="SELF TRANSFER",
                counterparty_vpa="self@okhdfcbank",
                channel="UPI",
                category_slug="transfer-in",
                tag="self-transfer",
            )


def gen_planted_events(ledger: Ledger, rng: random.Random, as_of: date) -> dict:
    """The three one-off anomalies the demo must show."""
    facts: dict = {}

    # 1. Duplicate charge: same merchant, same amount, 40 hours apart.
    dup_amount = rupees(1_249)
    first = as_of - timedelta(days=9)
    second = first + timedelta(days=2)  # 40 hours, rounded to whole days
    for when in (first, second):
        ledger.add(
            account="hdfc_savings",
            txn_date=when.isoformat(),
            amount_paise=dup_amount,
            direction="DEBIT",
            raw_narration=narrate(rng, "HDFC", "BIGBASKET", "bigbasket@ybl", "UPI"),
            normalized_merchant="BIGBASKET",
            counterparty_vpa="bigbasket@ybl",
            channel="UPI",
            category_slug="groceries",
            tag="duplicate-charge",
        )
    facts["duplicate_charge"] = {
        "merchant": "BIGBASKET",
        "amount_paise": dup_amount,
        "dates": [first.isoformat(), second.isoformat()],
        "hours_apart": 40,
    }

    # 2. New large merchant: a one-off electronics purchase.
    big_when = as_of - timedelta(days=5)
    big_amount = rupees(42_000)
    ledger.add(
        account="icici_credit",
        txn_date=big_when.isoformat(),
        amount_paise=big_amount,
        direction="DEBIT",
        raw_narration=narrate(rng, "ICICI", "CROMA", "croma@okicici", "CARD"),
        normalized_merchant="CROMA",
        counterparty_vpa="croma@okicici",
        channel="CARD",
        category_slug="shopping",
        tag="new-large-merchant",
    )
    facts["new_large_merchant"] = {
        "merchant": "CROMA",
        "amount_paise": big_amount,
        "date": big_when.isoformat(),
    }
    return facts


# --- Goals and budgets ------------------------------------------------------


def build_goals(as_of: date) -> list[dict]:
    """Two goals: one on track, one behind (BUILD_TASKS.md T03)."""
    return [
        {
            "name": "Emergency Fund",
            "target_paise": rupees(6_00_000),
            "current_paise": rupees(3_60_000),
            "target_date": (as_of.replace(day=1) + timedelta(days=330)).isoformat(),
            "priority": 0,
            "monthly_contribution_paise": rupees(25_000),
            "expected_verdict": "ON_TRACK",
        },
        {
            "name": "Japan Trip",
            "target_paise": rupees(3_50_000),
            "current_paise": rupees(48_000),
            "target_date": (as_of.replace(day=1) + timedelta(days=150)).isoformat(),
            "priority": 1,
            "monthly_contribution_paise": rupees(12_000),
            "expected_verdict": "BEHIND",
        },
    ]


def build_budgets(rows: list[Row], as_of: date) -> list[dict]:
    """Budgets for the top six discretionary categories, set near recent spend."""
    discretionary = [
        "food-delivery", "dining-out", "shopping", "entertainment",
        "subscriptions", "transport-fuel", "groceries", "personal-care",
    ]
    monthly: dict[str, list[int]] = defaultdict(list)
    per_month: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        if row.direction != "DEBIT" or row.category_slug not in discretionary:
            continue
        per_month[(row.category_slug, row.txn_date[:7])] += row.amount_paise
    for (slug, _), total in per_month.items():
        monthly[slug].append(total)

    ranked = sorted(
        monthly.items(),
        key=lambda kv: -int(statistics.median(kv[1])),
    )[:6]

    return [
        {
            "category_slug": slug,
            # A limit set just above the median month, so some months breach it.
            "limit_paise": int(round(statistics.median(totals) * 1.08 / 100) * 100),
            "starts_on": as_of.replace(day=1).isoformat(),
        }
        for slug, totals in ranked
    ]


# --- Ground truth -----------------------------------------------------------


def build_expected(rows: list[Row], goals, budgets, months, as_of: date,
                   planted: dict, seed: int) -> dict:
    """Ground-truth answers computed directly from the generated rows.

    BUILD_TASKS.md T03 requires at least the 25 values the eval set needs;
    T15's `evals/golden.yaml` sources its expected figures from here.
    """
    debits = [r for r in rows if r.direction == "DEBIT"]
    credits = [r for r in rows if r.direction == "CREDIT"]

    by_month_category: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    monthly_income: dict[str, int] = defaultdict(int)
    monthly_expense: dict[str, int] = defaultdict(int)
    for row in rows:
        key = row.txn_date[:7]
        if row.direction == "DEBIT":
            by_month_category[key][row.category_slug] += row.amount_paise
            monthly_expense[key] += row.amount_paise
        else:
            monthly_income[key] += row.amount_paise

    top_category = {
        month: max(cats.items(), key=lambda kv: (kv[1], kv[0]))[0]
        for month, cats in by_month_category.items()
    }
    top_category_value = {
        month: max(cats.values()) for month, cats in by_month_category.items()
    }

    subs = [s["merchant"] for s in SUBSCRIPTIONS]
    subscription_monthly = sum(
        rupees(s["hike_to"] if s.get("note") == "price-hike" else s["amount"])
        for s in SUBSCRIPTIONS
        if s["cadence"] == "monthly"
    )

    # Festival spike, computed rather than asserted.
    festival = max(
        by_month_category.items(),
        key=lambda kv: kv[1].get("shopping", 0),
    )[0]
    shopping_months = [
        cats.get("shopping", 0)
        for month, cats in by_month_category.items()
        if month != festival and cats.get("shopping", 0)
    ]
    shopping_baseline = int(statistics.median(shopping_months)) if shopping_months else 0

    hike = next(s for s in SUBSCRIPTIONS if s.get("note") == "price-hike")
    trial = next(s for s in SUBSCRIPTIONS if s.get("note") == "trial-conversion")
    dormant = next(s for s in SUBSCRIPTIONS if s.get("note") == "dormant")
    pair = [s["merchant"] for s in SUBSCRIPTIONS if s.get("note") == "duplicate-pair"]

    committed_monthly = (
        rupees(28_000)      # rent
        + rupees(24_500)    # home loan EMI
        + rupees(12_800)    # car loan EMI
        + rupees(10_000)    # SIP
        + rupees(1_299)     # broadband
        + rupees(799)       # mobile
        + subscription_monthly
    )

    return {
        "meta": {
            "seed": seed,
            "as_of": as_of.isoformat(),
            "months": [f"{y:04d}-{m:02d}" for y, m in months],
            "month_count": len(months),
            "generator_version": "1.0.0",
        },
        # --- volume ---
        "transaction_count": len(rows),
        "debit_count": len(debits),
        "credit_count": len(credits),
        "account_count": len(ACCOUNTS),
        "accounts": [a["display_name"] for a in ACCOUNTS],
        # --- income ---
        "salary_before_appraisal_paise": rupees(SALARY_BASE),
        "salary_after_appraisal_paise": rupees(SALARY_AFTER_APPRAISAL),
        "appraisal_month": f"{months[APPRAISAL_MONTH_INDEX][0]:04d}-"
                           f"{months[APPRAISAL_MONTH_INDEX][1]:02d}",
        "total_income_paise": sum(r.amount_paise for r in credits),
        "total_expense_paise": sum(r.amount_paise for r in debits),
        # --- per month ---
        "monthly_income_paise": dict(sorted(monthly_income.items())),
        "monthly_expense_paise": dict(sorted(monthly_expense.items())),
        "monthly_net_paise": {
            m: monthly_income.get(m, 0) - monthly_expense.get(m, 0)
            for m in sorted(set(monthly_income) | set(monthly_expense))
        },
        "top_category_per_month": dict(sorted(top_category.items())),
        "top_category_value_paise": dict(sorted(top_category_value.items())),
        # --- recurring ---
        "subscription_count": len(SUBSCRIPTIONS),
        "subscriptions": subs,
        "subscription_monthly_total_paise": subscription_monthly,
        "committed_monthly_paise": committed_monthly,
        "rent_paise": rupees(28_000),
        "emi_count": 2,
        "emi_total_paise": rupees(24_500) + rupees(12_800),
        # --- planted features ---
        "price_hike": {
            "merchant": hike["merchant"],
            "from_paise": rupees(hike["amount"]),
            "to_paise": rupees(hike["hike_to"]),
            "pct": round((hike["hike_to"] - hike["amount"]) / hike["amount"], 4),
            "month": f"{months[hike['hike_month_index']][0]:04d}-"
                     f"{months[hike['hike_month_index']][1]:02d}",
        },
        "duplicate_pair": sorted(pair),
        "trial_conversion": {
            "merchant": trial["merchant"],
            "trial_paise": rupees(trial["trial_amount"]),
            "paid_paise": rupees(trial["amount"]),
        },
        "dormant_subscription": dormant["merchant"],
        "category_spike": {
            "month": festival,
            "category": "shopping",
            "observed_paise": by_month_category[festival].get("shopping", 0),
            "baseline_median_paise": shopping_baseline,
            "multiple": round(
                by_month_category[festival].get("shopping", 0) / shopping_baseline, 2
            ) if shopping_baseline else 0,
        },
        **planted,
        # --- goals and budgets ---
        "goals": goals,
        "goal_count": len(goals),
        "budgets": budgets,
        "budget_count": len(budgets),
    }


# --- Output -----------------------------------------------------------------

CSV_HEADER = ["Date", "Narration", "Withdrawal (INR)", "Deposit (INR)", "Balance (INR)"]


def write_csvs(rows: list[Row], out_dir: Path) -> dict[str, int]:
    """One CSV per account, shaped like a real downloaded bank statement."""
    counts: dict[str, int] = {}
    for account in ACCOUNTS:
        key = account["key"]
        account_rows = [r for r in rows if r.account == key]
        balance = account["opening_balance_paise"]
        path = out_dir / f"{key}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(CSV_HEADER)
            for row in account_rows:
                if row.direction == "DEBIT":
                    balance -= row.amount_paise
                    withdrawal = f"{row.amount_paise / 100:.2f}"
                    deposit = ""
                else:
                    balance += row.amount_paise
                    withdrawal = ""
                    deposit = f"{row.amount_paise / 100:.2f}"
                writer.writerow([
                    date.fromisoformat(row.txn_date).strftime("%d/%m/%Y"),
                    row.raw_narration,
                    withdrawal,
                    deposit,
                    f"{balance / 100:.2f}",
                ])
        counts[key] = len(account_rows)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--as-of", type=date.fromisoformat, default=None,
                        help="Anchor the 14-month window (default: today)")
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "output")
    parser.add_argument("--months", type=int, default=14)
    args = parser.parse_args()

    as_of = args.as_of or date.today()
    rng = random.Random(args.seed)
    months = month_window(as_of, args.months)

    ledger = Ledger()
    gen_income(ledger, rng, months, as_of)
    gen_committed(ledger, rng, months, as_of)
    gen_subscriptions(ledger, rng, months, as_of)
    # The festival spike lands in the last *complete* month: a month still in
    # progress has no comparable baseline, so a spike planted there could not
    # be detected. The current month still carries the duplicate charge and the
    # new-large-merchant purchase, so it is not anomaly-free.
    gen_discretionary(ledger, rng, months, as_of, festival_month=months[-2])
    planted = gen_planted_events(ledger, rng, as_of)

    rows = sorted(ledger.rows, key=lambda r: r.sort_key())

    goals = build_goals(as_of)
    budgets = build_budgets(rows, as_of)
    expected = build_expected(rows, goals, budgets, months, as_of, planted, args.seed)

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = write_csvs(rows, out_dir)

    bundle = {
        "meta": expected["meta"],
        "accounts": ACCOUNTS,
        "transactions": [asdict(r) for r in rows],
        "goals": goals,
        "budgets": budgets,
    }
    (out_dir / "seed.json").write_text(
        json.dumps(bundle, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (Path(__file__).parent / "expected.json").write_text(
        json.dumps(expected, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"seed={args.seed}  as_of={as_of}  months={len(months)}")
    print(f"transactions: {len(rows)}")
    for key, count in sorted(counts.items()):
        print(f"  {key}: {count}")
    print(f"expected.json values: {len(expected)}")
    print(f"written to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
