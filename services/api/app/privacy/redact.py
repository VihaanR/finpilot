"""PII redaction (DESIGN.md 12.1).

Runs on all text leaving the system, without exception. Two design choices are
worth stating because they look like omissions otherwise:

**Merchant names are not redacted.** They are the entire signal a classifier
needs. Redacting "SWIGGY" would leave the model guessing at a string of
placeholder tokens and would make tier-2 classification useless.

**The reverse map is request-scoped and never persisted.** It exists so a
response mentioning `<ACCT_1>` can be rendered back with the real value for the
user who owns it. Storing it would recreate the exposure redaction removes.

Ordering matters: the longest and most specific patterns run first, so a
16-digit card number is not first consumed by the account-number rule. Each
distinct value gets a stable index within one redaction pass, so the same
account number appearing twice reads as `<ACCT_1>` both times.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- Validators -------------------------------------------------------------


def luhn_valid(digits: str) -> bool:
    if not digits.isdigit() or not 13 <= len(digits) <= 19:
        return False
    total, parity = 0, len(digits) % 2
    for index, char in enumerate(digits):
        value = int(char)
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)


def verhoeff_valid(digits: str) -> bool:
    """Aadhaar checksum. Rejects the 12-digit numbers that are merely numbers."""
    if not digits.isdigit() or len(digits) != 12:
        return False
    check = 0
    for index, char in enumerate(reversed(digits)):
        check = _VERHOEFF_D[check][_VERHOEFF_P[index % 8][int(char)]]
    return check == 0


# --- Patterns ---------------------------------------------------------------

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")
_IFSC_RE = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
_PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
_PHONE_RE = re.compile(r"(?:\+91[\s-]?|\b0)?\b[6-9]\d{9}\b")
_LONG_DIGITS_RE = re.compile(r"\b\d{9,19}\b")
_REF12_RE = re.compile(r"\b\d{12}\b")

#: Order is deliberate. Email first, so an address is not shredded by the phone
#: rule; IFSC and PAN before the digit rules, since both mix letters and digits.
FIELD_ORDER = (
    "EMAIL",
    "IFSC",
    "PAN",
    "CARD",
    "AADHAAR",
    "ACCT",
    "REF",
    "PHONE",
    "NAME",
)


@dataclass
class RedactionMap:
    """Request-scoped only. Never persisted (DESIGN.md 12.1)."""

    forward: dict[str, str] = field(default_factory=dict)  # real value -> token
    reverse: dict[str, str] = field(default_factory=dict)  # token -> real value
    counts: dict[str, int] = field(default_factory=dict)  # field type -> count

    def token_for(self, kind: str, value: str) -> str:
        if value in self.forward:
            return self.forward[value]
        index = self.counts.get(kind, 0) + 1
        self.counts[kind] = index
        token = "<{0}_{1}>".format(kind, index)
        self.forward[value] = token
        self.reverse[token] = value
        return token

    @property
    def field_types(self) -> list[str]:
        """Field *names* only — what `ai_disclosures` is allowed to record."""
        return [kind for kind in FIELD_ORDER if self.counts.get(kind)]

    @property
    def total_redacted(self) -> int:
        return sum(self.counts.values())


def redact(text: str, *, account_holder: str | None = None) -> tuple[str, RedactionMap]:
    """Replace every PII pattern with a stable token.

    Returns the redacted text and the request-scoped map needed to render the
    real values back to the user who owns them.
    """
    mapping = RedactionMap()
    if not text:
        return "", mapping

    def swap(kind: str):
        def replace(match: re.Match[str]) -> str:
            return mapping.token_for(kind, match.group(0))

        return replace

    result = _EMAIL_RE.sub(swap("EMAIL"), text)
    result = _IFSC_RE.sub(swap("IFSC"), result)
    result = _PAN_RE.sub(swap("PAN"), result)

    def digits(match: re.Match[str]) -> str:
        value = match.group(0)
        if luhn_valid(value):
            return mapping.token_for("CARD", value)
        if verhoeff_valid(value):
            return mapping.token_for("AADHAAR", value)
        if len(value) == 12:
            return mapping.token_for("REF", value)
        return mapping.token_for("ACCT", value)

    result = _LONG_DIGITS_RE.sub(digits, result)
    result = _PHONE_RE.sub(swap("PHONE"), result)

    if account_holder and account_holder.strip():
        pattern = re.compile(re.escape(account_holder.strip()), re.I)
        result = pattern.sub(lambda _: mapping.token_for("NAME", account_holder), result)

    return result, mapping


def restore(text: str, mapping: RedactionMap) -> str:
    """Render tokens back to their real values for the owning user."""
    for token, value in mapping.reverse.items():
        text = text.replace(token, value)
    return text


def contains_long_digit_run(text: str, minimum: int = 9) -> bool:
    """Assertion helper for the T05/T07 criteria: nothing 9+ digits leaves."""
    return re.search(r"\d{" + str(minimum) + r",}", text) is not None
