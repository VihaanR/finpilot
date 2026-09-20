"""Gmail-connected transaction ingestion — the Data Vault "Connect Gmail" panel.

Turns a bank transaction-alert email into a transaction through the same
normalise -> classify -> dedupe -> insert steps every other ingestion source
uses (`ingest/pipeline.py::ingest_parsed_rows`). No LLM call is involved —
the parser is a fixed regex against one verified HDFC template
(`ingest/adapters/hdfc_email.py`) — so this never touches the AI disclosure
log, only the storage inventory.

Single-owner model, matching the rest of FinPilot: there is no login, so one
Gmail connection exists for the whole deployment (USER.md needs
`GOOGLE_OAUTH_CLIENT_ID`/`GOOGLE_OAUTH_CLIENT_SECRET` set for `/connect` to
work at all).
"""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from ..config import settings
from ..deps import get_store
from ..ingest import gmail
from ..ingest.adapters.hdfc_email import HdfcEmailAdapter
from ..ingest.banks import detect_bank
from ..ingest.pipeline import ingest_parsed_rows

router = APIRouter(prefix="/api/email", tags=["email"])

_ADAPTER = HdfcEmailAdapter()
_ACCOUNT_NAME = "HDFC Bank — Email Alerts"


def _vault_redirect_url() -> str:
    origins = settings.allowed_origins_list
    base = origins[0] if origins else "http://localhost:3000"
    return base.rstrip("/") + "/vault"


def _mask(email_address: str) -> str:
    if "@" not in email_address:
        return "•••"
    name, domain = email_address.split("@", 1)
    return "{0}{1}@{2}".format(name[:1], "•" * max(len(name) - 1, 3), domain)


@router.get("/status")
def status() -> dict[str, Any]:
    connection = get_store().email_connection()
    if not connection:
        return {"connected": False, "configured": bool(settings.google_oauth_client_id)}
    return {
        "connected": True,
        "configured": True,
        "email_address": _mask(str(connection["email_address"])),
        "last_synced_at": connection["last_synced_at"],
    }


@router.post("/connect")
def connect() -> dict[str, str]:
    state = secrets.token_urlsafe(16)
    try:
        url = gmail.build_auth_url(state)
    except gmail.GmailError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"auth_url": url}


@router.get("/callback")
def callback(code: str = "", error: str = "") -> RedirectResponse:
    target = _vault_redirect_url()
    if error or not code:
        return RedirectResponse(url=target + "?email_error=" + (error or "missing_code"))
    try:
        tokens = gmail.exchange_code(code)
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            raise gmail.GmailError(
                "Google did not return a refresh token — disconnect any existing "
                "FinPilot access at myaccount.google.com/permissions and try again."
            )
        access_token = str(tokens["access_token"])
        email_address = gmail.fetch_email_address(access_token)
    except gmail.GmailError as exc:
        return RedirectResponse(url=target + "?email_error=" + str(exc))
    get_store().set_email_connection(
        email_address=email_address, refresh_token=str(refresh_token)
    )
    return RedirectResponse(url=target + "?email_connected=1")


@router.post("/disconnect")
def disconnect() -> dict[str, bool]:
    get_store().clear_email_connection()
    return {"connected": False}


@router.post("/sync")
def sync() -> dict[str, Any]:
    store = get_store()
    connection = store.email_connection()
    if not connection:
        raise HTTPException(status_code=409, detail="No Gmail account is connected.")

    try:
        access_token = gmail.refresh_access_token(str(connection["refresh_token"]))
        messages = gmail.fetch_alert_messages(
            access_token, after_ms=connection["last_message_internal_date"]
        )
    except gmail.GmailError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    inserted = duplicates = skipped = 0
    latest_internal_date = connection["last_message_internal_date"] or "0"
    account_id: str | None = None

    for message in messages:
        rows = _ADAPTER.parse(message.text)
        if not rows:
            skipped += 1
        else:
            if account_id is None:
                account_id = store.upsert_account(
                    bank_code=detect_bank(message.text) or "HDFC",
                    display_name=_ACCOUNT_NAME,
                )
            result = ingest_parsed_rows(
                store,
                rows=rows,
                adapter_name=_ADAPTER.name,
                adapter_version=_ADAPTER.version,
                confidence=0.9,
                filename="gmail:{0}.txt".format(message.message_id),
                bank_code=detect_bank(message.text) or "HDFC",
                account_id=account_id,
                account_name=_ACCOUNT_NAME,
            )
            inserted += result.inserted
            duplicates += result.duplicates
        if int(message.internal_date_ms) > int(latest_internal_date):
            latest_internal_date = message.internal_date_ms

    store.mark_email_synced(last_message_internal_date=latest_internal_date)
    return {
        "fetched": len(messages),
        "inserted": inserted,
        "duplicates": duplicates,
        "skipped": skipped,
    }
