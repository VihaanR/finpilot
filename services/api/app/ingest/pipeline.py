"""End-to-end ingestion (DESIGN.md section 6).

    bytes -> type detect -> decrypt -> adapter -> normalise -> classify
          -> dedupe -> insert -> recompute

Written as a generator of progress events so the SSE route can forward each
stage straight to the UI without the pipeline knowing anything about HTTP. The
same generator drives the offline demo seeding, which means the demo exercises
the real upload path rather than a shortcut around it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

from ..engine.types import Direction
from ..enrich.rules import UserRule, classify
from ..models.taxonomy import slugs
from ..store.db import Store
from .adapters.base import ParseError, RawRow
from .banks import detect_bank
from .normalize import NormalizedRow, normalize
from .pdf import extract_text
from .registry import parse as parse_statement

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"  # xlsx


@dataclass
class IngestResult:
    document_id: str | None = None
    adapter: str = ""
    confidence: float = 0.0
    parsed: int = 0
    inserted: int = 0
    duplicates: int = 0
    uncategorised: int = 0
    low_confidence: bool = False
    bank_code: str | None = None
    errors: list[str] = field(default_factory=list)


def _event(stage: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"stage": stage, "message": message, **extra}


def sniff_kind(data: bytes, filename: str) -> str:
    """Magic bytes, not the extension (DESIGN.md section 6)."""
    if data.startswith(PDF_MAGIC):
        return "pdf"
    if data.startswith(ZIP_MAGIC):
        return "xlsx"
    return "text"


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _xlsx_to_csv(data: bytes) -> str:
    import io
    import pandas as pd

    frame = pd.read_excel(io.BytesIO(data), dtype=str)
    return frame.to_csv(index=False)


def run(
    store: Store,
    *,
    data: bytes,
    filename: str,
    password: str | None = None,
    account_id: str | None = None,
    account_name: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield progress events; the final event carries the `IngestResult`."""
    result = IngestResult()

    yield _event("received", "Reading {0}".format(filename), filename=filename)

    kind = sniff_kind(data, filename)
    try:
        if kind == "pdf":
            yield _event("decrypt", "Checking whether the PDF is protected")
            extracted = extract_text(data, password)
            text = extracted.text
            yield _event(
                "extract",
                "Read {0} page(s) of text".format(extracted.page_count),
                pages=extracted.page_count,
            )
        elif kind == "xlsx":
            text = _xlsx_to_csv(data)
            yield _event("extract", "Converted the spreadsheet")
        else:
            text = _decode(data)
            yield _event("extract", "Read the file")
    except ParseError as exc:
        result.errors.append(exc.code)
        yield _event("error", exc.message, code=exc.code, hint=exc.hint)
        yield _event("done", exc.message, result=result, ok=False)
        return

    result.bank_code = detect_bank(text, filename)

    yield _event("detect", "Choosing a parser")
    try:
        outcome = parse_statement(text, filename)
    except ParseError as exc:
        result.errors.append(exc.code)
        yield _event("error", exc.message, code=exc.code, hint=exc.hint)
        yield _event("done", exc.message, result=result, ok=False)
        return

    result.adapter = outcome.adapter_name
    result.confidence = outcome.confidence
    result.parsed = len(outcome.rows)
    result.low_confidence = outcome.is_low_confidence
    yield _event(
        "parsed",
        "{0} read {1} rows".format(outcome.adapter_name, len(outcome.rows)),
        adapter=outcome.adapter_name,
        confidence=outcome.confidence,
        rows=len(outcome.rows),
        low_confidence=outcome.is_low_confidence,
    )

    target_account = account_id or store.upsert_account(
        bank_code=result.bank_code or "UNKNOWN",
        display_name=account_name or _account_label(result.bank_code, filename),
    )

    yield _event("normalise", "Normalising narrations")
    user_rules = tuple(
        UserRule(
            pattern=str(r["pattern"]),
            match_type=str(r["match_type"]),
            category_slug=str(r["category_slug"]),
            merchant=str(r["merchant"]),
        )
        for r in store.user_rules()
    )

    allowed = set(slugs())
    prepared: list[tuple[NormalizedRow, str, str, float, str | None]] = []
    uncategorised = 0
    for row in outcome.rows:
        normalized = normalize(
            txn_date=row.txn_date.isoformat(),
            raw_narration=row.raw_narration,
            amount_paise=row.amount_paise,
            direction=Direction.CREDIT if row.is_credit else Direction.DEBIT,
            balance_paise=row.balance_paise,
        )
        decision = classify(
            normalized_merchant=normalized.normalized_merchant,
            raw_narration=normalized.raw_narration,
            counterparty_vpa=normalized.counterparty_vpa,
            channel=normalized.channel,
            direction=normalized.direction,
            user_rules=user_rules,
        )
        slug = decision.category_slug if decision.category_slug in allowed else "uncategorised"
        if not decision.is_confident:
            slug = "uncategorised"
            uncategorised += 1
        prepared.append(
            (normalized, slug, decision.source, decision.confidence, decision.service_type)
        )

    result.uncategorised = uncategorised
    yield _event(
        "categorise",
        "Categorised {0} of {1} rows".format(len(prepared) - uncategorised, len(prepared)),
        uncategorised=uncategorised,
    )

    yield _event("dedupe", "Checking for rows already stored")
    inserted, duplicates = store.insert_transactions(
        account_id=target_account, document_id=None, rows=prepared
    )
    result.inserted = inserted
    result.duplicates = duplicates

    document_id = store.record_document(
        filename=filename,
        bank_code=result.bank_code,
        adapter_name=outcome.adapter_name,
        adapter_version=outcome.adapter_version,
        confidence=outcome.confidence,
        row_count=len(outcome.rows),
        inserted_count=inserted,
        duplicate_count=duplicates,
    )
    result.document_id = document_id

    store.conn.execute(
        "update transactions set document_id = ? where document_id is null and account_id = ?",
        (document_id, target_account),
    )
    store.conn.commit()

    message = (
        "Added {0} transactions".format(inserted)
        if inserted
        else "No new transactions — this statement was already imported"
    )
    yield _event(
        "stored", message, inserted=inserted, duplicates=duplicates, document_id=document_id
    )
    yield _event("done", message, result=result, ok=True)


def _account_label(bank_code: str | None, filename: str) -> str:
    stem = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
    if bank_code:
        return "{0} — {1}".format(bank_code, stem.title() or "Statement")
    return stem.title() or "Imported Account"


def ingest(
    store: Store,
    *,
    data: bytes,
    filename: str,
    password: str | None = None,
    account_id: str | None = None,
    account_name: str | None = None,
) -> IngestResult:
    """Blocking convenience wrapper: drains the generator, returns the result."""
    final = IngestResult()
    for event in run(
        store,
        data=data,
        filename=filename,
        password=password,
        account_id=account_id,
        account_name=account_name,
    ):
        if event["stage"] == "done":
            final = event["result"]
    return final


def ingest_parsed_rows(
    store: Store,
    *,
    rows: list[RawRow],
    adapter_name: str,
    adapter_version: str,
    confidence: float,
    filename: str,
    bank_code: str | None,
    account_id: str | None = None,
    account_name: str | None = None,
) -> IngestResult:
    """normalise -> classify -> dedupe -> insert -> record, for rows a caller

    has already parsed itself rather than obtained from `registry.parse`.

    `ingest/gmail.py` is the one caller: a Gmail alert is parsed by a single
    fixed adapter (`HdfcEmailAdapter`), never through the registry, because
    the registry's last resort is an LLM call on anything deterministic
    adapters decline — appropriate for a statement upload, wasteful and
    inappropriate for an inbox full of already-known-sender emails. A row
    that doesn't match the fixed adapter is meant to be skipped, not guessed
    at by a model.
    """
    result = IngestResult(
        adapter=adapter_name,
        confidence=round(confidence, 3),
        parsed=len(rows),
        bank_code=bank_code,
    )
    if not rows:
        return result

    target_account = account_id or store.upsert_account(
        bank_code=bank_code or "UNKNOWN",
        display_name=account_name or _account_label(bank_code, filename),
    )

    user_rules = tuple(
        UserRule(
            pattern=str(r["pattern"]),
            match_type=str(r["match_type"]),
            category_slug=str(r["category_slug"]),
            merchant=str(r["merchant"]),
        )
        for r in store.user_rules()
    )

    allowed = set(slugs())
    prepared: list[tuple[NormalizedRow, str, str, float, str | None]] = []
    uncategorised = 0
    for row in rows:
        normalized = normalize(
            txn_date=row.txn_date.isoformat(),
            raw_narration=row.raw_narration,
            amount_paise=row.amount_paise,
            direction=Direction.CREDIT if row.is_credit else Direction.DEBIT,
            balance_paise=row.balance_paise,
        )
        decision = classify(
            normalized_merchant=normalized.normalized_merchant,
            raw_narration=normalized.raw_narration,
            counterparty_vpa=normalized.counterparty_vpa,
            channel=normalized.channel,
            direction=normalized.direction,
            user_rules=user_rules,
        )
        slug = decision.category_slug if decision.category_slug in allowed else "uncategorised"
        if not decision.is_confident:
            slug = "uncategorised"
            uncategorised += 1
        prepared.append(
            (normalized, slug, decision.source, decision.confidence, decision.service_type)
        )

    result.uncategorised = uncategorised

    inserted, duplicates = store.insert_transactions(
        account_id=target_account, document_id=None, rows=prepared
    )
    result.inserted = inserted
    result.duplicates = duplicates

    document_id = store.record_document(
        filename=filename,
        bank_code=bank_code,
        adapter_name=adapter_name,
        adapter_version=adapter_version,
        confidence=result.confidence,
        row_count=len(rows),
        inserted_count=inserted,
        duplicate_count=duplicates,
    )
    result.document_id = document_id

    store.conn.execute(
        "update transactions set document_id = ? where document_id is null and account_id = ?",
        (document_id, target_account),
    )
    store.conn.commit()
    return result
