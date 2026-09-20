"""HDFC and ICICI PDF statement adapters (DESIGN.md 6.1).

Both banks lay their statements out as a date, a long narration, optional
reference columns, then amounts at the right margin. `pdfplumber` flattens that
to lines, so parsing is line-oriented: anchor on a leading date, take the
trailing numbers as amounts, and treat everything between as the narration.

The honest scoping note from DESIGN.md 6.1 applies. These layouts change
without notice. They are written to fail loudly and hand off to the generic CSV
path or the LLM fallback rather than to guess, and `detect()` is deliberately
conservative: an adapter that claims a document it cannot read is worse than
one that declines it.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from ..normalize import to_paise
from .base import ParseError, RawRow

#: A money token at the right margin: 1,23,456.78 with optional Cr/Dr suffix.
#: The grouped branch requires at least one comma. With `*` it also matched the
#: first three digits of an ungrouped number, splitting 110000.00 into 110 and
#: 000.00 and handing the balance column a zero.
_MONEY = r"(?:\(?-?(?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?\)?)"
_MONEY_RE = re.compile(_MONEY)
_LEADING_DATE_RE = re.compile(
    r"^\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}[\s-][A-Za-z]{3}[\s-]\d{2,4})\s+(.*)$"
)
_CR_MARKER_RE = re.compile(r"\b(CR|CREDIT)\b\.?\s*$", re.I)
_DR_MARKER_RE = re.compile(r"\b(DR|DEBIT)\b\.?\s*$", re.I)

_DATE_FORMATS = (
    "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y",
    "%d-%b-%Y", "%d %b %Y", "%d-%b-%y", "%d %b %y",
)

_CREDIT_HINTS = (
    "SALARY", "NEFT CR", "IMPS CR", "RTGS CR", "INTEREST", "REFUND",
    "REVERSAL", "CASHBACK", "DIVIDEND", "BY TRANSFER", "DEPOSIT",
)


def _parse_date(text: str) -> date | None:
    cleaned = text.strip().replace("  ", " ")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _money(token: str) -> int:
    negative = token.startswith("(") and token.endswith(")")
    value = to_paise(token.strip("()"))
    return -value if negative else value


class _LineStatementAdapter:
    """Shared line parser. Subclasses only supply detection signals."""

    name = "line_statement"
    version = "1.0.0"
    signals: tuple[str, ...] = ()

    def detect(self, text: str, filename: str) -> float:
        haystack = (text[:6000] + " " + filename).upper()
        if not any(signal in haystack for signal in self.signals):
            return 0.0
        score = 0.55
        dated_lines = sum(
            1 for line in text.splitlines()[:400] if _LEADING_DATE_RE.match(line)
        )
        if dated_lines >= 5:
            score += 0.30
        elif dated_lines >= 2:
            score += 0.15
        if _MONEY_RE.search(text):
            score += 0.05
        return min(score, 1.0)

    def parse(self, text: str) -> list[RawRow]:
        rows: list[RawRow] = []
        running_balance: int | None = None

        for line in text.splitlines():
            match = _LEADING_DATE_RE.match(line)
            if not match:
                continue
            txn_date = _parse_date(match.group(1))
            if txn_date is None:
                continue

            rest = match.group(2).strip()
            tokens = _MONEY_RE.findall(rest)
            if not tokens:
                continue

            explicit_credit = bool(_CR_MARKER_RE.search(rest))
            explicit_debit = bool(_DR_MARKER_RE.search(rest))

            # The last money token on the line is the running balance whenever
            # there are at least two; the one before it is the transaction.
            if len(tokens) >= 2:
                balance = _money(tokens[-1])
                amount = _money(tokens[-2])
            else:
                balance = None
                amount = _money(tokens[-1])

            narration = rest
            for token in tokens[-2:] if len(tokens) >= 2 else tokens[-1:]:
                narration = narration.replace(token, " ")
            narration = _CR_MARKER_RE.sub("", narration)
            narration = _DR_MARKER_RE.sub("", narration)
            narration = re.sub(r"\s+", " ", narration).strip(" -|")
            if not narration:
                continue

            if explicit_credit:
                is_credit = True
            elif explicit_debit:
                is_credit = False
            elif balance is not None and running_balance is not None:
                is_credit = balance > running_balance
            else:
                upper = narration.upper()
                is_credit = any(hint in upper for hint in _CREDIT_HINTS)

            if balance is not None:
                running_balance = balance

            rows.append(
                RawRow(
                    txn_date=txn_date,
                    raw_narration=narration,
                    amount_paise=abs(amount),
                    is_credit=is_credit,
                    balance_paise=balance,
                )
            )

        if not rows:
            raise ParseError(
                "NO_ROWS_PARSED",
                "No transaction rows were found in this statement layout.",
                hint="Try the CSV export from your bank.",
            )
        return rows


class HdfcPdfAdapter(_LineStatementAdapter):
    name = "hdfc_pdf"
    version = "1.0.0"
    signals = ("HDFC BANK", "HDFC0", "WE UNDERSTAND YOUR WORLD")


class IciciPdfAdapter(_LineStatementAdapter):
    name = "icici_pdf"
    version = "1.0.0"
    signals = ("ICICI BANK", "ICIC0", "KHAYAAL AAPKA")
