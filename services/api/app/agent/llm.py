"""The single seam between FinPilot and Google Gemini.

Every outbound call goes through here, because redaction and disclosure are
not optional (DESIGN.md 12.1) and a second code path that talks to the model
directly is a second code path that can forget them.

Three guarantees this module exists to make:

1. **Nothing leaves unredacted.** `prepare` runs `privacy.redact` over every
   outbound string and returns the request-scoped map needed to render real
   values back to the user who owns them.
2. **Every call is disclosed.** `ai_disclosures` gains one row per call,
   recording field *names* and a count. Never values.
3. **No key is not a crash.** `available()` is false without a key and every
   caller degrades to the deterministic product rather than 500ing. The
   engine, the dashboard and the radar never needed the model anyway.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from ..config import settings
from ..privacy.redact import RedactionMap, contains_long_digit_run, redact, restore

#: Free-tier quota is per Cloud project and is not raised by a consumer
#: Google AI Plus plan (DESIGN.md 9.1). Six iterations is the section 9.2
#: ceiling; it also bounds the worst-case call count per question.
MAX_TOOL_ITERATIONS = 6


class LLMUnavailable(RuntimeError):
    """No API key, or the SDK is not installed."""


def available() -> bool:
    if not settings.gemini_api_key:
        return False
    try:
        import google.genai  # noqa: F401
    except ImportError:
        return False
    return True


def client() -> Any:
    if not settings.gemini_api_key:
        raise LLMUnavailable(
            "No GEMINI_API_KEY is configured. The deterministic engine still works; "
            "chat and narration need a key. See USER.md section 1."
        )
    try:
        from google import genai
    except ImportError as exc:  # pragma: no cover - the dependency is pinned
        raise LLMUnavailable("google-genai is not installed") from exc
    return genai.Client(api_key=settings.gemini_api_key)


@dataclass
class OutboundPayload:
    """What we are about to send, after redaction."""

    texts: tuple[str, ...]
    mapping: RedactionMap

    @property
    def field_types(self) -> list[str]:
        return self.mapping.field_types

    @property
    def redacted_count(self) -> int:
        return self.mapping.total_redacted


def prepare(texts: Sequence[str], *, account_holder: str | None = None) -> OutboundPayload:
    """Redact every outbound string against one shared map.

    One map across the whole payload rather than one per string, so the same
    account number appearing in two places gets the same token and the model
    can still reason about them being the same thing.
    """
    mapping = RedactionMap()
    out: list[str] = []
    for text in texts:
        redacted_text, part_map = redact(text or "", account_holder=account_holder)
        # Fold the per-call map into the shared one, re-tokenising so ids stay
        # unique and stable across the payload.
        for real, token in part_map.forward.items():
            kind = token.strip("<>").rsplit("_", 1)[0]
            shared = mapping.token_for(kind, real)
            redacted_text = redacted_text.replace(token, shared)
        out.append(redacted_text)
    return OutboundPayload(texts=tuple(out), mapping=mapping)


def assert_clean(texts: Iterable[str]) -> None:
    """The T05/T07 criterion: no 9+ digit run may appear in an outbound body.

    An assertion rather than a filter. If something slipped through the
    redactor, silently stripping it would hide a hole in the redactor; the
    call should fail loudly and be fixed.
    """
    for text in texts:
        if contains_long_digit_run(text):
            raise AssertionError("Outbound payload still contains a 9+ digit run after redaction")


def render_back(text: str, mapping: RedactionMap) -> str:
    """Put the user's own values back into the model's prose."""
    return restore(text, mapping)


def disclose(store: Any, *, purpose: str, model: str, payload: OutboundPayload) -> None:
    """Write the ai_disclosures row. Field names and a count, never values."""
    store.record_disclosure(
        purpose=purpose,
        model=model,
        field_types=payload.field_types,
        redacted_count=payload.redacted_count,
    )
