"""The adapter contract (DESIGN.md 6.1).

An adapter's only job is to turn one statement's bytes into `RawRow`s. It does
not normalise, categorise, dedupe or touch a database. That separation is what
lets the registry try several adapters cheaply and pick the one that claims the
document most confidently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class RawRow:
    """One statement line, parsed but not yet interpreted.

    `amount_paise` is always positive; `is_credit` carries the direction. That
    mirrors `engine.types.Txn` so the conversion downstream is mechanical.
    """

    txn_date: date
    raw_narration: str
    amount_paise: int
    is_credit: bool
    balance_paise: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.amount_paise, int) or isinstance(self.amount_paise, bool):
            raise TypeError("amount_paise must be int paise")
        if self.amount_paise < 0:
            raise ValueError("amount_paise is always positive; use is_credit for sign")


class ParseError(Exception):
    """The adapter recognised the document but could not read it."""

    def __init__(self, code: str, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


@runtime_checkable
class StatementAdapter(Protocol):
    name: str
    version: str

    def detect(self, text: str, filename: str) -> float:
        """Confidence in [0.0, 1.0] that this adapter should parse `text`."""
        ...

    def parse(self, text: str) -> list[RawRow]:
        ...
