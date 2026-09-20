"""Adapter registry (DESIGN.md 6.1).

Adapters are tried in descending `detect()` confidence and the first one that
parses successfully wins. An adapter that raises is not fatal: the next
candidate gets a turn, which is what makes brittle bank-PDF layouts safe to
ship alongside a robust CSV path.

The winning adapter's name and confidence are reported back so
`GET /api/documents/{id}` can say exactly how a document was read. A parser
that cannot explain itself is one the user has no reason to trust.
"""

from __future__ import annotations

from dataclasses import dataclass

from .adapters.bank_pdf import HdfcPdfAdapter, IciciPdfAdapter
from .adapters.base import ParseError, RawRow, StatementAdapter
from .adapters.generic_csv import GenericCsvAdapter
from .adapters.llm_fallback import LlmFallbackAdapter

ADAPTERS: tuple[StatementAdapter, ...] = (
    GenericCsvAdapter(),
    HdfcPdfAdapter(),
    IciciPdfAdapter(),
    LlmFallbackAdapter(),
)

#: Below this, the UI offers the manual column mapper rather than trusting the
#: parse (DESIGN.md 6.1).
LOW_CONFIDENCE = 0.6


@dataclass(frozen=True)
class ParseOutcome:
    rows: list[RawRow]
    adapter_name: str
    adapter_version: str
    confidence: float

    @property
    def is_low_confidence(self) -> bool:
        return self.confidence < LOW_CONFIDENCE


def candidates(text: str, filename: str) -> list[tuple[float, StatementAdapter]]:
    scored = [(a.detect(text, filename), a) for a in ADAPTERS]
    return sorted(
        [(score, a) for score, a in scored if score > 0.0],
        key=lambda pair: pair[0],
        reverse=True,
    )


def parse(text: str, filename: str = "") -> ParseOutcome:
    ranked = candidates(text, filename)
    if not ranked:
        raise ParseError(
            "NO_ADAPTER",
            "No parser recognised this file.",
            hint="Upload a CSV export or a statement PDF from your bank.",
        )

    first_error: ParseError | None = None
    for score, adapter in ranked:
        try:
            rows = adapter.parse(text)
        except ParseError as exc:
            # NEEDS_PASSWORD and friends are about the file, not the adapter:
            # trying the next one cannot help and would bury the real answer.
            if exc.code in {"NEEDS_PASSWORD", "WRONG_PASSWORD", "CORRUPT_PDF"}:
                raise
            first_error = first_error or exc
            continue
        except Exception:
            continue
        if rows:
            return ParseOutcome(
                rows=rows,
                adapter_name=adapter.name,
                adapter_version=adapter.version,
                confidence=round(score, 3),
            )

    raise first_error or ParseError(
        "NO_ROWS_PARSED", "No parser could read transactions from this file."
    )
