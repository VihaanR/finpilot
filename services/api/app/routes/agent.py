"""Chat and monthly summary (DESIGN.md 9).

`POST /api/agent/ask` streams the tool-use loop as SSE so the UI can name the
tool it is running in plain language while the user waits. The final `done`
event carries the citation list, which is what `CitationChip` resolves against.

Consent is checked before any model call. Revoking the AI scope disables chat
while the deterministic engine keeps working (DESIGN.md 10.3) — that is a
promise the vault page makes to the user, so it is enforced here rather than
in the browser.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, AsyncIterator

from fastapi import APIRouter, Body, HTTPException
from sse_starlette.sse import EventSourceResponse

from ..agent import llm, loop, summary as summary_agent
from ..deps import get_snapshot, get_store

router = APIRouter(prefix="/api", tags=["agent"])

#: The consent scope the vault toggles. Chat is gated on it; the engine is not.
AI_SCOPE = "ai_processing"

#: The four PS questions (DESIGN.md 13, rows 11a-11d), surfaced as the chat
#: suggestion chips so the UI and the eval harness ask the same things.
SUGGESTED_QUESTIONS = (
    "Where did I spend the most last month?",
    "How much of my budget is already committed?",
    "Which subscriptions am I paying for without realising?",
    "Can I afford a ₹40,000 phone this month?",
)


def _require_consent() -> None:
    store = get_store()
    if not store.consent_granted(AI_SCOPE):
        raise HTTPException(
            status_code=403,
            detail=(
                "AI processing consent has been revoked. The dashboard, radar, goals "
                "and simulator still work — they are computed locally."
            ),
        )


@router.get("/agent/suggestions")
def suggestions() -> dict[str, Any]:
    return {
        "questions": list(SUGGESTED_QUESTIONS),
        "available": llm.available(),
        "consent": get_store().consent_granted(AI_SCOPE),
    }


@router.post("/agent/ask")
async def ask(payload: dict[str, Any] = Body(...)) -> EventSourceResponse:
    """Answer a question, streaming tool progress then the answer.

    Errors arrive as an `error` event rather than an HTTP status, because the
    stream has already begun by the time a model call can fail. The final
    `done` event always fires, so the client knows how it ended.
    """
    question = str(payload.get("question", "")).strip()
    if not question:
        raise HTTPException(status_code=422, detail="Ask me something.")
    if len(question) > 2000:
        raise HTTPException(status_code=422, detail="That question is too long.")
    _require_consent()

    snapshot = get_snapshot()

    async def stream() -> AsyncIterator[dict[str, str]]:
        for event in loop.run(question, snapshot):
            kind = event.pop("type")
            yield {"event": kind, "data": json.dumps(event)}

    return EventSourceResponse(stream())


@router.post("/agent/ask/sync")
def ask_sync(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Non-streaming answer. The eval harness and tests use this."""
    question = str(payload.get("question", "")).strip()
    if not question:
        raise HTTPException(status_code=422, detail="Ask me something.")
    _require_consent()

    answer = loop.ask(question, get_snapshot())
    return {
        "question": question,
        "answer": answer.text,
        "citations": answer.citations,
        "tools_used": answer.tools_used,
        "declined": answer.declined,
        "uncited_figures": list(answer.audit.uncited) if answer.audit else [],
        "unknown_citation_ids": list(answer.audit.unknown_ids) if answer.audit else [],
        "error": answer.error,
    }


@router.post("/summary/generate")
def generate_summary(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """The month's summary (DESIGN.md 9.6).

    The engine's figures are returned whether or not narration succeeds, so
    the page renders something useful even with no key and no quota.
    """
    _require_consent()
    month_raw = payload.get("month")
    month = date.fromisoformat(str(month_raw) + "-01") if month_raw else None

    result = summary_agent.generate(get_snapshot(), month=month)
    return {
        "month": result.month,
        "text": result.text,
        "facts": result.facts,
        "declined": result.declined,
        "error": result.error,
    }
