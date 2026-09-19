"""Fixtures and factories for the engine tests.

Everything here builds engine value types directly. No database, no network,
no fixtures loaded from disk: the engine is pure, so its tests are too.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from datetime import date, timedelta

import pytest

from app.engine.types import (
    Cadence,
    Channel,
    Direction,
    Goal,
    MandateChannel,
    PricePoint,
    RecurringSeries,
    SeriesStatus,
    Txn,
    rupees,
)

_ids = itertools.count(1)


def txn(
    *,
    on: date,
    amount_rupees: int | None = None,
    amount_paise: int | None = None,
    merchant: str = "TESTCO",
    direction: Direction = Direction.DEBIT,
    category: str = "subscriptions",
    narration: str | None = None,
    channel: Channel = Channel.UPI,
    txn_id: str | None = None,
) -> Txn:
    """Build one transaction. Amount may be given in whole rupees or paise."""
    if (amount_rupees is None) == (amount_paise is None):
        raise ValueError("pass exactly one of amount_rupees or amount_paise")
    paise = amount_paise if amount_paise is not None else rupees(amount_rupees)
    return Txn(
        id=txn_id or f"t{next(_ids)}",
        txn_date=on,
        amount_paise=paise,
        direction=direction,
        raw_narration=narration or f"UPI/DR/412345678901/{merchant}/YBL/Payment",
        normalized_merchant=merchant,
        category_slug=category,
        channel=channel,
    )


def monthly_run(
    *,
    start: date,
    count: int,
    amount_rupees: int,
    merchant: str = "NETFLIX",
    direction: Direction = Direction.DEBIT,
    category: str = "subscriptions",
    narration: str | None = None,
    step_days: int = 30,
) -> list[Txn]:
    """A clean run of `count` occurrences spaced `step_days` apart."""
    return [
        txn(
            on=start + timedelta(days=step_days * i),
            amount_rupees=amount_rupees,
            merchant=merchant,
            direction=direction,
            category=category,
            narration=narration,
        )
        for i in range(count)
    ]


def series(
    *,
    merchant: str = "RENT",
    amount_rupees: int = 25_000,
    next_expected: date,
    direction: Direction = Direction.DEBIT,
    category: str = "rent",
    cadence: Cadence = Cadence.MONTHLY,
    gap_days: float = 30.0,
    status: SeriesStatus = SeriesStatus.ACTIVE,
    mandate: MandateChannel = MandateChannel.NACH,
    acknowledged: bool = False,
    key: str | None = None,
    price_history: Sequence[PricePoint] = (),
    txn_ids: Sequence[str] = ("tx-a", "tx-b", "tx-c"),
    first_seen: date | None = None,
    last_seen: date | None = None,
) -> RecurringSeries:
    """Hand-built series, for tests that check arithmetic rather than detection."""
    from app.engine.recurrence import amount_tolerance, derive_afa_band

    paise = rupees(amount_rupees)
    seen_last = last_seen or (next_expected - timedelta(days=int(gap_days)))
    return RecurringSeries(
        normalized_merchant=merchant,
        category_slug=category,
        direction=direction,
        cadence=cadence,
        median_amount_paise=paise,
        amount_tolerance_paise=amount_tolerance(paise),
        median_gap_days=gap_days,
        gap_mad=0.5,
        occurrence_count=len(txn_ids),
        first_seen=first_seen or (seen_last - timedelta(days=int(gap_days) * 2)),
        last_seen=seen_last,
        next_expected_date=next_expected,
        confidence=0.95,
        mandate_channel=mandate,
        afa_band=derive_afa_band(paise, category),
        status=status,
        txn_ids=tuple(txn_ids),
        price_history=tuple(price_history),
        acknowledged=acknowledged,
        key=key or f"key-{merchant.lower()}",
    )


@pytest.fixture
def as_of() -> date:
    """A fixed reference date, so every projection in the suite is exact."""
    return date(2026, 9, 10)


@pytest.fixture
def goal_on_track() -> Goal:
    """Shortfall Rs 3,00,000 at Rs 50,000/month lands six months out."""
    return Goal(
        id="g-emergency",
        name="Emergency Fund",
        target_paise=rupees(5_00_000),
        current_paise=rupees(2_00_000),
        target_date=date(2027, 3, 15),
        priority=0,
        monthly_contribution_paise=rupees(50_000),
    )


@pytest.fixture
def goal_behind() -> Goal:
    """Same arithmetic, but the target date is three months too early."""
    return Goal(
        id="g-laptop",
        name="New Laptop",
        target_paise=rupees(1_20_000),
        current_paise=rupees(20_000),
        target_date=date(2026, 12, 15),
        priority=1,
        monthly_contribution_paise=rupees(10_000),
    )
