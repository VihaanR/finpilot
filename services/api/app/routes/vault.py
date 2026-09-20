"""Data Vault — the DPDP consent ledger (DESIGN.md 10.2, 12).

Erase and export are real operations, not stubs. The whole point of this page
is that the rights it describes actually work when a judge clicks them.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from ..config import settings
from ..deps import get_store
from ..privacy.redact import redact
from ..store.demo import CONSENT_SCOPES, CONSENT_VERSION

router = APIRouter(prefix="/api/vault", tags=["vault"])

#: Modelled on the Account Aggregator artefact structure (DESIGN.md 10.2).
#: Third parties must name who actually receives data — this is a user-facing
#: privacy claim, so it names the real providers, not a generic "AI provider".
CONSENT_ARTEFACT: dict[str, Any] = {
    "version": CONSENT_VERSION,
    "purpose": "Personal finance analysis and insight generation",
    "data_types": [
        "Transaction records",
        "Account metadata",
        "Uploaded bills",
        "HDFC transaction-alert emails (if Gmail is connected)",
    ],
    "processing": [
        "Categorisation",
        "Recurrence detection",
        "Anomaly detection",
        "AI-generated summaries",
    ],
    "third_parties": [
        {
            "name": "Groq",
            "role": "Chat and monthly summary — AI processing on redacted text",
            "region": "Global",
        },
        {
            "name": "Google",
            "role": "Gemini API — bulk categorisation and embeddings on redacted text",
            "region": "Global",
        },
        {
            "name": "Supabase",
            "role": "Storage",
            "region": "India region where available",
        },
        {
            "name": "Google (Gmail API)",
            "role": (
                "Read-only access to HDFC transaction-alert emails, only if "
                "you connect an account from this page. No AI processing — "
                "a fixed parser, not a model, reads these emails."
            ),
            "region": "Global",
        },
    ],
    "retention": "{0} days from upload, then automatic deletion".format(
        settings.retention_days
    ),
    "frequency": "On demand, per your action",
    "revocation": "Any time, from the Data Vault — takes effect immediately",
}

_REDACTION_EXAMPLE = "UPI/DR/412345678901/SWIGGY/YBL/Payment from 9876543210"


@router.get("")
def vault() -> dict[str, Any]:
    store = get_store()
    redacted, mapping = redact(_REDACTION_EXAMPLE)
    return {
        "consent_artefact": CONSENT_ARTEFACT,
        "consents": store.consents(),
        "scopes": {scope: store.consent_granted(scope) for scope in CONSENT_SCOPES},
        "disclosures": store.disclosures(),
        "storage_inventory": store.storage_inventory(),
        "retention_days": settings.retention_days,
        "redaction_example": {
            "before": _REDACTION_EXAMPLE,
            "after": redacted,
            "field_types": mapping.field_types,
            "note": (
                "Account numbers, IFSC codes, phone numbers and names are "
                "tokenised before any text leaves this server. Merchant names "
                "are kept, because they are the signal the model needs."
            ),
        },
        "ai_configured": bool(settings.groq_api_key),
    }


@router.post("/consent")
def set_consent(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Grant or revoke a consent scope.

    Revoking `ai_processing` disables AI features while the deterministic
    engine keeps working — the graceful-degradation demonstration.
    """
    scope = str(payload.get("scope", "")).strip()
    if scope not in CONSENT_SCOPES:
        raise HTTPException(status_code=422, detail="Unknown scope: {0}".format(scope))
    granted = bool(payload.get("granted", True))
    store = get_store()
    store.set_consent(version=CONSENT_VERSION, scope=scope, granted=granted)
    return {
        "scope": scope,
        "granted": granted,
        "scopes": {s: store.consent_granted(s) for s in CONSENT_SCOPES},
    }


@router.get("/export")
def export() -> dict[str, Any]:
    """DPDP right to portability. Everything held, as JSON."""
    return get_store().export_everything()


@router.post("/erase")
def erase(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """DPDP right to erasure. Cascades and actually deletes.

    Requires the typed confirmation so a mis-click cannot destroy a ledger.
    """
    if str(payload.get("confirm", "")).strip().upper() != "DELETE":
        raise HTTPException(
            status_code=422, detail='Type DELETE to confirm erasure.'
        )
    store = get_store()
    deleted = store.erase_everything()
    return {
        "deleted": deleted,
        "remaining": store.storage_inventory(),
        "message": "Everything has been deleted.",
    }
