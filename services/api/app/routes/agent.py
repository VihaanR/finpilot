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
from ..agent.money import MAX_GOAL_PAISE, parse_indian_amount
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


@router.post("/agent/act")
async def act(payload: dict[str, Any] = Body(...)) -> EventSourceResponse:
    """Same as `/agent/ask`, but the model may stage changes.

    Separate from `/agent/ask` rather than a flag on it so the read-only chat
    surface keeps its exact behaviour — the eval goldens run through `/ask`,
    and `/chat` should not be able to offer to delete anything.

    Nothing here writes. The `done` event carries staged actions; applying one
    is a second, explicit call to `/agent/actions/apply`.
    """
    question = str(payload.get("question", "")).strip()
    if not question:
        raise HTTPException(status_code=422, detail="Tell me what you'd like to do.")
    if len(question) > 2000:
        raise HTTPException(status_code=422, detail="That request is too long.")
    _require_consent()

    snapshot = get_snapshot()

    async def stream() -> AsyncIterator[dict[str, str]]:
        for event in loop.run(question, snapshot, mode="act"):
            kind = event.pop("type")
            yield {"event": kind, "data": json.dumps(event)}

    return EventSourceResponse(stream())


def _apply_create_goal(store: Any, params: dict[str, Any]) -> dict[str, Any]:
    name = str(params.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=422, detail="A goal needs a name.")

    # Re-derived here rather than trusted. The client echoes the action back
    # because the staging registry is per-request and gone once the stream
    # closes, so `target_paise` arriving in the body is a *claim*, not a fact.
    try:
        target_paise = parse_indian_amount(
            params.get("amount_value"), str(params.get("amount_unit", ""))
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if target_paise > MAX_GOAL_PAISE:
        raise HTTPException(status_code=422, detail="That target is implausibly large.")

    target_date = params.get("target_date")
    if target_date:
        try:
            target_date = date.fromisoformat(str(target_date)).isoformat()
        except ValueError:
            raise HTTPException(status_code=422, detail="Target date must be YYYY-MM-DD.") from None
    else:
        # `goals.project` needs a horizon to report a verdict against. Five
        # years is a neutral default for an undated aspiration, and the user
        # can see it on the goal afterwards.
        target_date = date(get_snapshot().as_of.year + 5, 12, 31).isoformat()

    goal_id = store.upsert_goal(
        name=name,
        target_paise=target_paise,
        current_paise=0,
        target_date=target_date,
        priority=int(params.get("priority") or 0),
        monthly_contribution_paise=0,
    )
    return {"goal_id": goal_id, "name": name, "target_paise": target_paise, "target_date": target_date}


def _apply_delete_transaction(store: Any, params: dict[str, Any]) -> dict[str, Any]:
    txn_id = str(params.get("txn_id", "")).strip()
    if not txn_id:
        raise HTTPException(status_code=422, detail="Which transaction?")
    if not store.transaction_exists(txn_id):
        raise HTTPException(status_code=404, detail="No such transaction, or it is already removed.")
    reason = str(params.get("reason") or "removed by agent")[:200]
    store.soft_delete_transaction(txn_id, reason=reason)
    return {"txn_id": txn_id, "reason": reason, "reversible": True}


#: The only things an approved action can do. Mirrors `TOOLS`, but for writes.
EXECUTORS = {
    "create_goal": _apply_create_goal,
    "delete_transaction": _apply_delete_transaction,
}


@router.post("/agent/actions/apply")
def apply_actions(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Execute actions the user approved.

    Deterministic: the model is not involved, and every parameter is
    re-validated from scratch. A per-action result is returned rather than
    failing the batch, so approving two things and having one fail still
    applies the other and says which broke.
    """
    _require_consent()
    raw = payload.get("actions")
    if not isinstance(raw, list) or not raw:
        raise HTTPException(status_code=422, detail="No actions to apply.")
    if len(raw) > 10:
        raise HTTPException(status_code=422, detail="Too many actions at once.")

    store = get_store()
    results: list[dict[str, Any]] = []
    for item in raw:
        action_id = str((item or {}).get("id", ""))
        kind = str((item or {}).get("kind", ""))
        params = (item or {}).get("params") or {}
        executor = EXECUTORS.get(kind)
        if executor is None:
            results.append({"id": action_id, "ok": False, "error": f"Unknown action: {kind}"})
            continue
        try:
            detail = executor(store, params)
        except HTTPException as exc:
            results.append({"id": action_id, "ok": False, "error": str(exc.detail)})
        except Exception as exc:  # noqa: BLE001 - one bad action must not 500 the batch
            results.append({"id": action_id, "ok": False, "error": f"{type(exc).__name__}: {exc}"})
        else:
            results.append({"id": action_id, "ok": True, "kind": kind, "result": detail})

    applied = sum(1 for r in results if r["ok"])
    return {
        "results": results,
        "applied": applied,
        "message": "Applied {0} change{1}.".format(applied, "" if applied == 1 else "s"),
    }


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
        "actions": answer.actions,
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
