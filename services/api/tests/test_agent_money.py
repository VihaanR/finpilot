"""Indian-amount parsing (app/agent/money.py).

This is the conversion the model is explicitly forbidden from doing, so it is
worth its own file. Getting "50L" wrong by a factor of a hundred is the one
arithmetic mistake in this feature that a user would actually act on.
"""

from __future__ import annotations

import pytest

from app.agent.money import canonical_unit, parse_indian_amount


@pytest.mark.parametrize(
    ("value", "unit", "paise"),
    [
        (1, "rupee", 100),
        (40_000, "rupees", 4_000_000),
        (5, "thousand", 500_000),
        (50, "lakh", 500_000_000),
        (1, "crore", 1_000_000_000),
        (1.5, "lakh", 15_000_000),
        (0.5, "crore", 500_000_000),
    ],
)
def test_converts_to_paise(value: float, unit: str, paise: int) -> None:
    assert parse_indian_amount(value, unit) == paise


@pytest.mark.parametrize(
    ("spoken", "canonical"),
    [("L", "lakh"), ("l", "lakh"), ("lakhs", "lakh"), ("lac", "lakh"),
     ("Cr", "crore"), ("crores", "crore"), ("k", "thousand"), ("Rs", "rupee")],
)
def test_accepts_how_people_actually_write_it(spoken: str, canonical: str) -> None:
    assert canonical_unit(spoken) == canonical


def test_result_is_always_an_int() -> None:
    """Money is int paise everywhere; a float here would poison the store."""
    result = parse_indian_amount(1.5, "lakh")
    assert isinstance(result, int)


@pytest.mark.parametrize(
    ("value", "unit"),
    [(0, "lakh"), (-5, "lakh"), (50, "bananas"), (50, ""), (float("inf"), "lakh")],
)
def test_rejects_rather_than_guesses(value: float, unit: str) -> None:
    with pytest.raises(ValueError):
        parse_indian_amount(value, unit)
