"""Budget Guard telemetry from the browser extension (DESIGN.md 10.5).

The extension used to be a dead end. It intercepted an over-budget checkout,
wrote a cooldown into `chrome.storage.local`, and the web app never learned
that any of it happened — two halves of one product with no shared memory.
This is the seam that joins them: the extension reports what it stopped, the
dashboard shows it, and the agent can answer questions about it.

Deliberately minimal and non-identifying. An event records the retailer, what
the user chose, and the two amounts that were compared. It does **not** record
the URL, the cart contents, or what was being bought — the extension already
holds that locally and it is none of the server's business.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from ..deps import get_store

router = APIRouter(prefix="/api", tags=["guard"])

#: What the user did when the interstitial appeared.
OUTCOMES = {"wait", "continue", "dismiss"}

#: The two retailers the extension runs on.
SITES = {"amazon.in", "flipkart.com"}


@router.post("/guard/events")
def record_event(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    site = str(payload.get("site", "")).strip().lower()
    outcome = str(payload.get("outcome", "")).strip().lower()
    if site not in SITES:
        raise HTTPException(status_code=422, detail=f"Unknown site: {site}")
    if outcome not in OUTCOMES:
        raise HTTPException(status_code=422, detail=f"Unknown outcome: {outcome}")
    try:
        cart = int(payload.get("cart_paise") or 0)
        discretionary = int(payload.get("discretionary_paise") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Amounts must be integer paise.") from None
    if cart < 0 or discretionary < 0:
        raise HTTPException(status_code=422, detail="Amounts cannot be negative.")

    event_id = get_store().record_guard_event(
        site=site, outcome=outcome, cart_paise=cart, discretionary_paise=discretionary
    )
    return {"id": event_id, "recorded": True}


@router.get("/guard/events")
def list_events(limit: int = 20) -> dict[str, Any]:
    events = get_store().guard_events(limit=max(1, min(limit, 100)))
    stopped = [e for e in events if e["outcome"] in ("wait", "dismiss")]
    return {
        "events": events,
        "count": len(events),
        # "Stopped" means the user did not go through with it. Overspend
        # avoided is the sum of those carts, which is the only figure here
        # worth putting in front of someone.
        "stopped_count": len(stopped),
        "avoided_paise": sum(int(e["cart_paise"]) for e in stopped),
    }
