"""The Gemini function-calling loop (DESIGN.md 9.2).

Automatic function calling is deliberately **disabled**. The SDK will happily
run the tool loop itself, but then the citations produced along the way are
buried inside the SDK's transcript and the guardrails never see the final
text. Driving the loop by hand costs about forty lines and buys the two things
the architecture is built on: every citation is captured, and every answer is
audited before it reaches the user.

The loop emits events rather than returning a string, so the route can stream
progress over SSE and the caller can collect the whole thing when it wants a
single answer (the eval harness does).
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Iterator

from ..config import settings
from ..services.views import Snapshot
from . import guardrails, llm
from .prompts import SYSTEM_PROMPT
from .tools import TOOL_DECLARATIONS, CitationRegistry, ToolContext, dispatch

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
}


@dataclass
class AgentAnswer:
    text: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    declined: bool = False
    audit: guardrails.CitationAudit | None = None
    error: str | None = None


#: Transient upstream conditions worth a second attempt. 503 is the free tier
#: shedding load under a demand spike, and not retrying it means a judge's
#: first question fails for reasons unrelated to the product.
#:
#: **429 is deliberately absent.** The free tier's binding limit is
#: GenerateRequestsPerDayPerProjectPerModel: 20 requests per *day* for
#: gemini-3.8-flash, measured 20 Sep 2026 -- not the per-minute limit the docs
#: describe. A 429 therefore usually means the day's budget is gone, and each
#: retry spends another request of the twenty to be told so again. Retrying a
#: quota error makes the shortage worse and can never fix it.
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
            return client.models.generate_content(**kwargs)
        except Exception as exc:
            last = exc
            if delay is None or _status_of(exc) not in _RETRY_STATUSES:
                raise
            logger.warning(
                "gemini call failed (%s), retrying in %.0fs (attempt %d)",
                _status_of(exc), delay, attempt + 1,
            )
            time.sleep(delay)
    raise last  # pragma: no cover - the loop above always returns or raises


def _friendly_error(exc: Exception) -> str:
    """What to show the user. The detail goes to the log, not the browser."""
    logger.exception("gemini call failed")
    status = _status_of(exc)
    if status == 429:
        retry_after = re.search(r"retry in ([\d.]+)s", str(exc))
        when = f" Try again in about {float(retry_after.group(1)):.0f}s." if retry_after else ""
        return (
            "I've used up the Gemini free-tier quota for now." + when + " "
            "The dashboard, radar, goals and simulator are computed locally and still work."
        )
    if status in _RETRY_STATUSES:
        return (
            "Gemini is temporarily unavailable upstream. This usually clears in a "
            "moment — the dashboard and radar are computed locally and still work."
        )
    return "The model call failed. The dashboard and radar are computed locally and still work."


def _decl_to_sdk(types_mod: Any) -> Any:
    """Our plain-dict declarations as SDK function declarations."""
    return types_mod.Tool(
        function_declarations=[
            types_mod.FunctionDeclaration(
                name=d["name"], description=d["description"], parameters=d["parameters"]
            )
            for d in TOOL_DECLARATIONS
        ]
    )


def run(
    question: str,
    snapshot: Snapshot,
    *,
    document_text: str | None = None,
    max_iterations: int = llm.MAX_TOOL_ITERATIONS,
) -> Iterator[dict[str, Any]]:
    """Answer one question, yielding events as it goes.

    Events: ``{"type": "tool", ...}`` per tool call, ``{"type": "text", ...}``
    for the answer, and a final ``{"type": "done", ...}`` carrying the full
    citation list for the UI.
    """
    registry = CitationRegistry()
    ctx = ToolContext(snapshot=snapshot, citations=registry)
    answer = AgentAnswer()

    if not llm.available():
        answer.error = (
            "Chat needs a Gemini API key, which isn't configured. "
            "Everything else — the dashboard, radar, goals and simulator — is "
            "computed by the engine and works without it."
        )
        yield {"type": "error", "message": answer.error}
        yield {"type": "done", "citations": [], "tools_used": [], "error": answer.error}
        return

    from google.genai import types as gt

    client = llm.client()
    model = settings.gemini_model_chat

    # The question is user-authored and may carry PII; document text is
    # untrusted and is fenced before it is ever concatenated.
    payload = llm.prepare([question])
    llm.assert_clean(payload.texts)
    llm.disclose(snapshot.store, purpose="chat", model=model, payload=payload)
    prompt_text = payload.texts[0]
    if document_text:
        prompt_text = f"{prompt_text}\n\n{guardrails.wrap_untrusted(document_text)}"

    contents: list[Any] = [gt.Content(role="user", parts=[gt.Part(text=prompt_text)])]
    config = gt.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[_decl_to_sdk(gt)],
        automatic_function_calling=gt.AutomaticFunctionCallingConfig(disable=True),
    )

    final_text = ""
    for _ in range(max_iterations):
        try:
            response = _generate_with_retry(client, model=model, contents=contents, config=config)
        except Exception as exc:  # the SDK raises a family of transport errors
            answer.error = _friendly_error(exc)
            yield {"type": "error", "message": answer.error}
            break

        candidate = (response.candidates or [None])[0]
        parts = list(getattr(getattr(candidate, "content", None), "parts", None) or [])
        calls = [p.function_call for p in parts if getattr(p, "function_call", None)]

        if not calls:
            final_text = "".join(p.text for p in parts if getattr(p, "text", None))
            break

        contents.append(gt.Content(role="model", parts=parts))
        replies = []
        for call in calls:
            name = call.name
            args = dict(call.args or {})
            answer.tools_used.append(name)
            yield {"type": "tool", "name": name, "label": TOOL_LABELS.get(name, name)}
            result = dispatch(name, args, ctx)
            replies.append(gt.Part.from_function_response(name=name, response=result))
        contents.append(gt.Content(role="user", parts=replies))
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

    if final_text:
        yield {"type": "text", "text": final_text, "declined": answer.declined}
    yield {
        "type": "done",
        "citations": answer.citations,
        "tools_used": answer.tools_used,
        "declined": answer.declined,
        "uncited_figures": list(answer.audit.uncited) if answer.audit else [],
        "unknown_citation_ids": list(answer.audit.unknown_ids) if answer.audit else [],
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
            answer.error = event.get("error")
            answer.audit = guardrails.audit_citations(
                answer.text, {str(c["id"]) for c in answer.citations}
            )
    return answer
