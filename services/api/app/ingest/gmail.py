"""Gmail OAuth + message fetch for the "Connect Gmail" vault panel.

Single stored connection: FinPilot has no login (USER.md), so there is one
Gmail account connected for the whole deployment, not one per visitor. The
refresh token lives in `email_connections` (store/db.py) at the same trust
level as the rest of `finpilot.db` — it is never returned by any API
response, only a masked email address and a last-synced timestamp are
(routes/email.py).

Scope is `gmail.readonly`, the narrowest Gmail grants — no message is ever
modified, labelled or deleted. Implemented directly over Gmail's REST API
with `httpx` (already a dependency) rather than pulling in
`google-api-python-client`, which this one read-only search + get flow does
not need.
"""

from __future__ import annotations

import base64
import html as html_lib
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from ..config import settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

#: The one sender this feature parses (brainstorming decision: one verified
#: format, graceful skip on everything else, not a broad inbox scan).
ALERT_SENDER_QUERY = "from:alerts@hdfcbank.bank.in"


class GmailError(Exception):
    pass


def build_auth_url(state: str) -> str:
    if not settings.google_oauth_client_id:
        raise GmailError("Gmail is not configured on this deployment.")
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return AUTH_URL + "?" + urlencode(params)


def exchange_code(code: str) -> dict[str, Any]:
    response = httpx.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=15.0,
    )
    if response.status_code != 200:
        raise GmailError("Google did not accept the authorization code.")
    return response.json()


def refresh_access_token(refresh_token: str) -> str:
    response = httpx.post(
        TOKEN_URL,
        data={
            "refresh_token": refresh_token,
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "grant_type": "refresh_token",
        },
        timeout=15.0,
    )
    if response.status_code != 200:
        raise GmailError("Gmail token refresh failed — the connection may need reconnecting.")
    return str(response.json()["access_token"])


def fetch_email_address(access_token: str) -> str:
    response = httpx.get(
        API_BASE + "/profile",
        headers={"Authorization": "Bearer " + access_token},
        timeout=15.0,
    )
    if response.status_code != 200:
        raise GmailError("Could not read the Gmail profile.")
    return str(response.json()["emailAddress"])


@dataclass(frozen=True)
class FetchedEmail:
    message_id: str
    internal_date_ms: str
    text: str


def _strip_html(fragment: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", fragment, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _decode_part(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _extract_text(payload: dict[str, Any]) -> str:
    """Depth-first walk for the first text/html or text/plain part."""
    mime_type = payload.get("mimeType", "")
    body = payload.get("body") or {}
    if mime_type in ("text/html", "text/plain") and body.get("data"):
        decoded = _decode_part(str(body["data"]))
        return _strip_html(decoded) if mime_type == "text/html" else decoded
    for part in payload.get("parts") or []:
        text = _extract_text(part)
        if text:
            return text
    return ""


def fetch_alert_messages(
    access_token: str, *, after_ms: str | None = None, max_results: int = 25
) -> list[FetchedEmail]:
    query = ALERT_SENDER_QUERY
    if after_ms:
        # Gmail's `after:` operator is date-granular; a same-day re-fetch is
        # harmless because insert_transactions dedupes on content, not on
        # which sync run saw a message first.
        query += " after:{0}".format(int(after_ms) // 1000)
    headers = {"Authorization": "Bearer " + access_token}
    listing = httpx.get(
        API_BASE + "/messages",
        params={"q": query, "maxResults": max_results},
        headers=headers,
        timeout=15.0,
    )
    if listing.status_code != 200:
        raise GmailError("Gmail search failed.")
    message_ids = [m["id"] for m in listing.json().get("messages", [])]

    out: list[FetchedEmail] = []
    for message_id in message_ids:
        detail = httpx.get(
            API_BASE + "/messages/" + message_id,
            params={"format": "full"},
            headers=headers,
            timeout=15.0,
        )
        if detail.status_code != 200:
            continue
        payload = detail.json()
        text = _extract_text(payload.get("payload") or {})
        if text:
            out.append(
                FetchedEmail(
                    message_id=message_id,
                    internal_date_ms=str(payload.get("internalDate", "0")),
                    text=text,
                )
            )
    return out
