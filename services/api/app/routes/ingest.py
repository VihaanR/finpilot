"""Upload and ingestion endpoints (DESIGN.md section 6)."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from typing import Any, AsyncIterator

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sse_starlette.sse import EventSourceResponse

from ..config import settings
from ..deps import get_store
from ..ingest import pipeline
from ..ingest.banks import BANK_HINTS, hint_for
from ..store import demo

router = APIRouter(prefix="/api", tags=["ingest"])


@router.get("/banks/password-hints")
def password_hints() -> dict[str, Any]:
    return {
        "banks": [
            {
                "bank_code": h.bank_code,
                "bank_name": h.bank_name,
                "formats": list(h.formats),
                "example": h.example,
            }
            for h in BANK_HINTS
        ],
        "note": "Passwords are used in memory to decrypt the file and are never stored.",
    }


@router.get("/banks/password-hints/{bank_code}")
def password_hint(bank_code: str) -> dict[str, Any]:
    hint = hint_for(bank_code)
    return {
        "bank_code": hint.bank_code,
        "bank_name": hint.bank_name,
        "formats": list(hint.formats),
        "example": hint.example,
    }


async def _read_upload(file: UploadFile) -> tuple[bytes, str]:
    data = await file.read()
    limit = settings.max_upload_mb * 1024 * 1024
    if len(data) > limit:
        raise HTTPException(
            status_code=413,
            detail="File is larger than {0} MB.".format(settings.max_upload_mb),
        )
    if not data:
        raise HTTPException(status_code=422, detail="That file is empty.")
    return data, file.filename or "statement"


@router.post("/ingest")
async def ingest_stream(
    file: UploadFile = File(...),
    password: str | None = Form(default=None),
    account_id: str | None = Form(default=None),
) -> EventSourceResponse:
    """Ingest a statement, streaming progress as SSE.

    Errors arrive as an `error` event rather than an HTTP status, because the
    stream has already begun by the time parsing fails. The final `done` event
    carries `ok`, so the client always knows how it ended.
    """
    data, filename = await _read_upload(file)
    store = get_store()

    async def stream() -> AsyncIterator[dict[str, str]]:
        for event in pipeline.run(
            store,
            data=data,
            filename=filename,
            password=password,
            account_id=account_id,
        ):
            payload = dict(event)
            result = payload.pop("result", None)
            if result is not None:
                payload["result"] = asdict(result)
            yield {"event": payload["stage"], "data": json.dumps(payload)}
            await asyncio.sleep(0)

    return EventSourceResponse(stream())


@router.post("/ingest/sync")
async def ingest_sync(
    file: UploadFile = File(...),
    password: str | None = Form(default=None),
    account_id: str | None = Form(default=None),
) -> dict[str, Any]:
    """Non-streaming ingest, for tests and clients without an SSE reader."""
    data, filename = await _read_upload(file)
    result = pipeline.ingest(
        get_store(), data=data, filename=filename, password=password, account_id=account_id
    )
    if result.errors:
        raise HTTPException(
            status_code=422,
            detail={"code": result.errors[0], "message": "Could not read that statement."},
        )
    return asdict(result)


@router.post("/demo/reset")
def reset_demo() -> dict[str, Any]:
    """Restore the clean 14-month demo state (T12 acceptance criterion)."""
    return demo.load(get_store(), reset=True)
