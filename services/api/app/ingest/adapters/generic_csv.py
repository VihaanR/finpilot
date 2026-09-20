"""Generic CSV/XLSX adapter (DESIGN.md 6.1).

This is the workhorse. Bank PDF layouts change without notice, but every Indian
bank exports a CSV, and those CSVs differ mostly in what they call their
columns. So rather than one adapter per bank, this one recognises the *shapes*:

- separate withdrawal and deposit columns (HDFC, ICICI, SBI, Axis, Kotak)
- a single signed amount column
- a single amount column plus a Dr/Cr indicator

Dates are read Indian-first: `03/04/2026` is 3 April, not 4 March. Getting that
backwards silently reorders someone's year, so the ambiguous case is resolved
by looking at the whole column rather than each cell alone.

When the header cannot be mapped confidently, `detect()` returns a low score
and the caller offers the manual column-mapper described in DESIGN.md 6.1.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime

from ..normalize import to_paise
from .base import ParseError, RawRow

_DATE_HEADERS = ("date", "txn date", "transaction date", "value date", "posting date", "tran date")
_NARRATION_HEADERS = (
    "narration", "description", "particulars", "remarks", "transaction details",
    "details", "transaction remarks", "narrative",
)
_DEBIT_HEADERS = ("withdrawal", "debit", "withdrawal amt", "withdrawals", "dr", "paid out")
_CREDIT_HEADERS = ("deposit", "credit", "deposit amt", "deposits", "cr", "paid in")
_AMOUNT_HEADERS = ("amount", "transaction amount", "amt", "value")
_BALANCE_HEADERS = ("balance", "closing balance", "running balance", "available balance")
_INDICATOR_HEADERS = ("type", "dr/cr", "drcr", "indicator", "transaction type")

_NUMERIC_RE = re.compile(r"\d")


def _clean_header(value: str) -> str:
    text = re.sub(r"\(.*?\)", " ", value or "")
    text = re.sub(r"[^a-z0-9/\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _match_header(cleaned: str, candidates: tuple[str, ...]) -> bool:
    return any(cleaned == c or cleaned.startswith(c + " ") or cleaned == c.replace(" ", "") for c in candidates)


def _find(headers: list[str], candidates: tuple[str, ...]) -> int | None:
    for index, header in enumerate(headers):
        if _match_header(header, candidates):
            return index
    for index, header in enumerate(headers):
        # Whole words only: a bare substring test lets "cr" match "description".
        if any(re.search(r"\b" + re.escape(c) + r"\b", header) for c in candidates):
            return index
    return None


_DATE_FORMATS = (
    "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y",
    "%Y-%m-%d", "%Y/%m/%d",
    "%d-%b-%Y", "%d %b %Y", "%d-%b-%y", "%d %B %Y",
    "%m/%d/%Y", "%m-%d-%Y",
)


def _parse_date(value: str, *, day_first: bool) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    text = text.split(" ")[0] if len(text.split(" ")) > 1 and ":" in text else text
    formats = _DATE_FORMATS if day_first else ("%m/%d/%Y", "%m-%d-%Y") + _DATE_FORMATS
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _column_is_day_first(values: list[str]) -> bool:
    """Decide DD/MM vs MM/DD across the whole column, not cell by cell.

    If any cell has a first component above 12 it cannot be a month, which
    settles the question for every other cell. Indian statements are the
    overwhelming majority here, so ambiguity defaults to day-first.
    """
    for value in values:
        parts = re.split(r"[/-]", (value or "").strip())
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            if int(parts[0]) > 12:
                return True
            if int(parts[1]) > 12:
                return False
    return True


def _read_amount(cell: str) -> int:
    text = (cell or "").strip()
    if not text or not _NUMERIC_RE.search(text):
        return 0
    negative = text.startswith("-") or (text.startswith("(") and text.endswith(")"))
    value = to_paise(text.lstrip("-(").rstrip(")"))
    return -value if negative else value


def _sniff_rows(text: str) -> list[list[str]]:
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return [row for row in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in row)]


def _locate_header(rows: list[list[str]]) -> int:
    """Indian bank CSVs often carry several preamble lines before the header."""
    best_index, best_score = 0, -1
    for index, row in enumerate(rows[:25]):
        cleaned = [_clean_header(c) for c in row]
        score = 0
        if _find(cleaned, _DATE_HEADERS) is not None:
            score += 2
        if _find(cleaned, _NARRATION_HEADERS) is not None:
            score += 2
        if _find(cleaned, _DEBIT_HEADERS) is not None or _find(cleaned, _AMOUNT_HEADERS) is not None:
            score += 1
        if score > best_score:
            best_index, best_score = index, score
    return best_index


class GenericCsvAdapter:
    name = "generic_csv"
    version = "1.0.0"

    def _map(self, text: str) -> tuple[list[list[str]], int, dict[str, int | None]]:
        rows = _sniff_rows(text)
        if not rows:
            raise ParseError("EMPTY_FILE", "The file contains no rows.")
        header_index = _locate_header(rows)
        headers = [_clean_header(c) for c in rows[header_index]]
        mapping = {
            "date": _find(headers, _DATE_HEADERS),
            "narration": _find(headers, _NARRATION_HEADERS),
            "debit": _find(headers, _DEBIT_HEADERS),
            "credit": _find(headers, _CREDIT_HEADERS),
            "amount": _find(headers, _AMOUNT_HEADERS),
            "balance": _find(headers, _BALANCE_HEADERS),
            "indicator": _find(headers, _INDICATOR_HEADERS),
        }
        return rows, header_index, mapping

    def detect(self, text: str, filename: str) -> float:
        if not text.strip():
            return 0.0
        try:
            _, _, mapping = self._map(text)
        except (ParseError, csv.Error):
            return 0.0
        score = 0.0
        if mapping["date"] is not None:
            score += 0.35
        if mapping["narration"] is not None:
            score += 0.35
        if mapping["debit"] is not None and mapping["credit"] is not None:
            score += 0.25
        elif mapping["amount"] is not None:
            score += 0.15
        if filename.lower().endswith((".csv", ".tsv", ".txt")):
            score += 0.05
        return min(score, 1.0)

    def parse(self, text: str) -> list[RawRow]:
        rows, header_index, mapping = self._map(text)
        if mapping["date"] is None or mapping["narration"] is None:
            raise ParseError(
                "UNMAPPED_COLUMNS",
                "Could not find a date and a description column.",
                hint="Use the column mapper to point at them.",
            )
        if mapping["debit"] is None and mapping["credit"] is None and mapping["amount"] is None:
            raise ParseError(
                "UNMAPPED_COLUMNS",
                "Could not find an amount column.",
                hint="Use the column mapper to point at it.",
            )

        body = rows[header_index + 1 :]
        date_col = mapping["date"]
        day_first = _column_is_day_first(
            [r[date_col] for r in body if len(r) > date_col]
        )

        parsed: list[RawRow] = []
        skipped = 0
        for row in body:
            def cell(key: str) -> str:
                index = mapping[key]
                return row[index] if index is not None and index < len(row) else ""

            txn_date = _parse_date(cell("date"), day_first=day_first)
            narration = cell("narration").strip()
            if txn_date is None or not narration:
                skipped += 1
                continue

            debit = _read_amount(cell("debit"))
            credit = _read_amount(cell("credit"))
            if debit or credit:
                is_credit = credit > 0
                amount = credit if is_credit else abs(debit)
            else:
                signed = _read_amount(cell("amount"))
                if signed == 0:
                    skipped += 1
                    continue
                indicator = cell("indicator").strip().upper()
                if indicator.startswith("CR") or indicator == "CREDIT":
                    is_credit = True
                elif indicator.startswith("DR") or indicator == "DEBIT":
                    is_credit = False
                else:
                    is_credit = signed > 0
                amount = abs(signed)

            balance_cell = cell("balance")
            balance = _read_amount(balance_cell) if balance_cell.strip() else None

            parsed.append(
                RawRow(
                    txn_date=txn_date,
                    raw_narration=narration,
                    amount_paise=abs(amount),
                    is_credit=is_credit,
                    balance_paise=balance,
                )
            )

        if not parsed:
            raise ParseError(
                "NO_ROWS_PARSED",
                "Found a header but no readable transaction rows ({0} skipped).".format(skipped),
            )
        return parsed
