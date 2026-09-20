"""The Groq function-calling loop (DESIGN.md 9.2).

Driven by hand rather than through an SDK-managed agent loop, so citations
produced along the way are captured and every answer is audited before it
reaches the user — the two things the architecture is built on. Groq's chat
completions API is OpenAI-compatible: tool calls arrive on
`message.tool_calls`, and each tool's result goes back as its own
`role="tool"` message keyed by `tool_call_id`.

The loop emits events rather than returning a string, so the route can stream
progress over SSE and the caller can collect the whole thing when it wants a
single answer (the eval harness does).
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Iterator

from ..config import settings
from ..services.views import Snapshot
from . import guardrails, llm
from .prompts import system_prompt
from .tools import (
    ALL_TOOL_DECLARATIONS,
    TOOL_DECLARATIONS,
    ActionRegistry,
    CitationRegistry,
    ToolContext,
    dispatch,
)

logger = logging.getLogger(__name__)

#: Plain-language names for the tool-execution indicator (DESIGN.md 10, T10).
#: "Checking your recurring payments..." rather than "list_recurring".
TOOL_LABELS = {
    "query_transactions": "Looking through your transactions",
    "get_category_breakdown": "Adding up spending by category",
    "compare_periods": "Comparing the two months",
    "list_recurring": "Checking your recurring payments",
    "get_upcoming_obligations": "Checking what's due next",
    "get_budget_status": "Checking your budgets",
    "get_goal_projection": "Projecting your goals",
    "detect_anomalies": "Looking for anything unusual",
    "simulate_scenario": "Running the what-if",
    "get_safe_to_spend": "Working out what's safe to spend",
    "search_documents": "Searching your uploaded documents",
    "get_anomaly_transactions": "Finding the exact transactions",
    "propose_create_goal": "Setting up the goal",
    "propose_delete_transaction": "Preparing to remove that transaction",
}


@dataclass
class AgentAnswer:
    text: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    declined: bool = False
    #: Staged, unapplied changes. Always empty in ask mode.
    actions: list[dict[str, Any]] = field(default_factory=list)
    audit: guardrails.CitationAudit | None = None
    error: str | None = None


#: Transient upstream conditions worth a second attempt. 503 is the provider
#: shedding load under a demand spike, and not retrying it means a judge's
#: first question fails for reasons unrelated to the product.
#:
#: **429 is deliberately absent.** Groq's binding limit resets on a rolling
#: per-minute/per-day window, but a retry still spends a request to be told
#: the same thing, and the response already carries a usable `retry-after`.
_RETRY_STATUSES = (500, 502, 503, 504)
_RETRY_DELAYS = (1.0, 3.0, 7.0)


def _status_of(exc: Exception) -> int | None:
    for attr in ("code", "status_code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    match = re.search(r"\b(4\d{2}|5\d{2})\b", str(exc))
    return int(match.group(1)) if match else None


def _generate_with_retry(client: Any, **kwargs: Any) -> Any:
    """One model call, retried on transient upstream failures."""
    last: Exception | None = None
    for attempt, delay in enumerate((*_RETRY_DELAYS, None)):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as exc:
            last = exc
            if delay is None or _status_of(exc) not in _RETRY_STATUSES:
                raise
            logger.warning(
                "groq call failed (%s), retrying in %.0fs (attempt %d)",
                _status_of(exc), delay, attempt + 1,
            )
            time.sleep(delay)
    raise last  # pragma: no cover - the loop above always returns or raises


def _friendly_error(exc: Exception) -> str:
    """What to show the user. The detail goes to the log, not the browser."""
    logger.exception("groq call failed")
    status = _status_of(exc)
    if status == 429:
        retry_after = re.search(r"retry.{0,20}?([\d.]+)s", str(exc), re.IGNORECASE)
        when = f" Try again in about {float(retry_after.group(1)):.0f}s." if retry_after else ""
        return (
            "I've used up the Groq free-tier quota for now." + when + " "
            "The dashboard, radar, goals and simulator are computed locally and still work."
        )
    if status in _RETRY_STATUSES:
        return (
            "Groq is temporarily unavailable upstream. This usually clears in a "
            "moment — the dashboard and radar are computed locally and still work."
        )
    return "The model call failed. The dashboard and radar are computed locally and still work."


def _decl_to_sdk(declarations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Our plain-dict declarations as OpenAI-shaped tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": d["name"],
                "description": d["description"],
                "parameters": d["parameters"],
            },
        }
        for d in declarations
    ]


def run(
    question: str,
    snapshot: Snapshot,
    *,
    document_text: str | None = None,
    max_iterations: int = llm.MAX_TOOL_ITERATIONS,
    mode: str = "ask",
) -> Iterator[dict[str, Any]]:
    """Answer one question, yielding events as it goes.

    Events: ``{"type": "tool", ...}`` per tool call, ``{"type": "text", ...}``
    for the answer, and a final ``{"type": "done", ...}`` carrying the full
    citation list for the UI.
    """
    registry = CitationRegistry()
    # Act mode is the only thing that hands the model an ActionRegistry, and
    # `dispatch` uses its presence to decide whether the staging tools are
    # reachable at all. `/api/agent/ask` therefore cannot propose a change
    # even if a model tries to call one by name.
    acting = mode == "act"
    ctx = ToolContext(
        snapshot=snapshot,
        citations=registry,
        actions=ActionRegistry() if acting else None,
    )
    answer = AgentAnswer()

    # The advice boundary is checked on the question first, so the decline is
    # deterministic rather than dependent on how the model phrases a refusal
    # (DESIGN.md 9.4). It also short-circuits before any model call, which on
    # a 20/day free tier is not a small thing.
    if guardrails.is_advice_request(question):
        yield {"type": "text", "text": guardrails.ADVICE_DECLINE, "declined": True}
        yield {
            "type": "done",
            "citations": [],
            "tools_used": [],
            "declined": True,
            "uncited_figures": [],
            "unknown_citation_ids": [],
            "actions": [],
            "error": None,
        }
        return

    if not llm.available():
        answer.error = (
            "Chat needs a Groq API key, which isn't configured. "
            "Everything else — the dashboard, radar, goals and simulator — is "
            "computed by the engine and works without it."
        )
        yield {"type": "error", "message": answer.error}
        yield {
            "type": "done",
            "citations": [],
            "tools_used": [],
            "actions": [],
            "error": answer.error,
        }
        return

    client = llm.client()
    model = settings.groq_model_chat

    # The question is user-authored and may carry PII; document text is
    # untrusted and is fenced before it is ever concatenated.
    payload = llm.prepare([question])
    llm.assert_clean(payload.texts)
    llm.disclose(snapshot.store, purpose="chat", model=model, payload=payload)
    prompt_text = payload.texts[0]
    if document_text:
        prompt_text = f"{prompt_text}\n\n{guardrails.wrap_untrusted(document_text)}"

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt(snapshot.as_of, acting=acting)},
        {"role": "user", "content": prompt_text},
    ]
    tools = _decl_to_sdk(ALL_TOOL_DECLARATIONS if acting else TOOL_DECLARATIONS)

    final_text = ""
    for _ in range(max_iterations):
        try:
            response = _generate_with_retry(
                client, model=model, messages=messages, tools=tools, tool_choice="auto"
            )
        except Exception as exc:  # the SDK raises a family of transport errors
            answer.error = _friendly_error(exc)
            yield {"type": "error", "message": answer.error}
            break

        message = response.choices[0].message
        calls = list(message.tool_calls or [])

        if not calls:
            final_text = message.content or ""
            break

        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.function.name, "arguments": call.function.arguments},
                    }
                    for call in calls
                ],
            }
        )
        for call in calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            answer.tools_used.append(name)
            yield {"type": "tool", "name": name, "label": TOOL_LABELS.get(name, name)}
            result = dispatch(name, args, ctx)
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)}
            )
    else:
        # Six iterations without settling means the model is thrashing. Say so
        # rather than presenting a partial answer as a complete one.
        answer.error = "I couldn't settle on an answer within the tool limit."
        yield {"type": "error", "message": answer.error}

    # --- guardrails, in order -------------------------------------------
    if final_text:
        final_text = llm.render_back(final_text, payload.mapping)
        verdict = guardrails.enforce_advice_boundary(final_text)
        answer.declined = verdict.declined
        final_text = verdict.text
        answer.audit = guardrails.audit_citations(final_text, registry.ids())

    answer.text = final_text
    answer.citations = registry.as_list()
    answer.actions = ctx.actions.as_list() if ctx.actions else []

    if final_text:
        yield {"type": "text", "text": final_text, "declined": answer.declined}
    yield {
        "type": "done",
        "citations": answer.citations,
        "tools_used": answer.tools_used,
        "declined": answer.declined,
        "uncited_figures": list(answer.audit.uncited) if answer.audit else [],
        "unknown_citation_ids": list(answer.audit.unknown_ids) if answer.audit else [],
        "actions": answer.actions,
        "error": answer.error,
    }


def ask(question: str, snapshot: Snapshot, **kwargs: Any) -> AgentAnswer:
    """Collect the whole answer. Used by the eval harness and by tests."""
    answer = AgentAnswer()
    for event in run(question, snapshot, **kwargs):
        if event["type"] == "tool":
            answer.tools_used.append(event["name"])
        elif event["type"] == "text":
            answer.text = event["text"]
            answer.declined = bool(event.get("declined"))
        elif event["type"] == "done":
            answer.citations = event["citations"]
            answer.actions = event.get("actions", [])
            answer.error = event.get("error")
            answer.audit = guardrails.audit_citations(
                answer.text, {str(c["id"]) for c in answer.citations}
            )
    return answer
