"""Deterministic Indian-amount parsing for staged agent actions.

The model is forbidden from computing a number (DESIGN.md 9.1, and the
system prompt says so verbatim). "50L" -> paise is a computation, so the
model passes the tokens it heard — ``value=50, unit="lakh"`` — and this
module does the arithmetic.

Keeping it here rather than inline in the tool means it is testable without
a model, a snapshot, or a store, which is the same reason the engine is pure.
"""

from __future__ import annotations

#: Paise per unit. Indian scale: 1 lakh = 100 thousand, 1 crore = 100 lakh.
_UNITS: dict[str, int] = {
    "rupee": 100,
    "thousand": 100_000,
    "lakh": 10_000_000,
    "crore": 1_000_000_000,
}

#: What the user actually says, mapped onto the canonical unit.
_ALIASES: dict[str, str] = {
    "rupees": "rupee",
    "rs": "rupee",
    "inr": "rupee",
    "k": "thousand",
    "thousands": "thousand",
    "l": "lakh",
    "lac": "lakh",
    "lacs": "lakh",
    "lakhs": "lakh",
    "cr": "crore",
    "crores": "crore",
}

#: ₹1,000 crore. A ceiling that is absurd for a personal savings goal but
#: still lets any real one through — it exists so a misheard "50 crore crore"
#: fails loudly instead of being stored.
MAX_GOAL_PAISE = 1_000_000_000_000


def canonical_unit(unit: str) -> str:
    """Normalise a unit token, raising on anything unrecognised."""
    key = (unit or "").strip().lower()
    key = _ALIASES.get(key, key)
    if key not in _UNITS:
        raise ValueError(f"Unknown amount unit: {unit!r}")
    return key


def parse_indian_amount(value: float, unit: str) -> int:
    """Convert ``value`` of ``unit`` into integer paise.

    >>> parse_indian_amount(50, "lakh")
    500000000
    >>> parse_indian_amount(1, "crore")
    1000000000
    """
    key = canonical_unit(unit)
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Amount is not a number: {value!r}") from None
    if amount != amount or amount in (float("inf"), float("-inf")):
        raise ValueError(f"Amount is not finite: {value!r}")
    if amount <= 0:
        raise ValueError(f"Amount must be positive, got {value!r}")
    return int(round(amount * _UNITS[key]))
