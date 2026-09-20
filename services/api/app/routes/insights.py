"""Mandate Radar, goals and the What-If simulator (DESIGN.md 10.1, 10.4)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from ..deps import get_snapshot, get_store
from ..engine.types import OneOff, Scenario, UNCATEGORISED_SLUG
from ..services import views

router = APIRouter(prefix="/api", tags=["insights"])


@router.get("/radar")
def radar() -> dict[str, Any]:
    return views.radar(get_snapshot())


@router.post("/radar/{series_key}/acknowledge")
def acknowledge(series_key: str, payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """"I know about this" — clears the series' silent_mandate anomaly.

    The radar is about *unknown* debits, not all debits (DESIGN.md 10.1).
    """
    store = get_store()
    known = {s.key for s in get_snapshot().series}
    if series_key not in known:
        raise HTTPException(status_code=404, detail="No such series")

    acknowledged = bool(payload.get("acknowledged", True))
    if acknowledged:
        store.acknowledge(series_key)
    else:
        store.unacknowledge(series_key)

    snapshot = get_snapshot()
    remaining = [
        a for a in snapshot.anomalies
        if a.series_key == series_key and a.type.value == "silent_mandate"
    ]
    return {
        "series_key": series_key,
        "acknowledged": acknowledged,
        "silent_mandate_cleared": not remaining,
        "leak_score": views.leak_score(snapshot),
    }


@router.post("/anomalies/{anomaly_key}/dismiss")
def dismiss(anomaly_key: str) -> dict[str, Any]:
    get_store().dismiss(anomaly_key)
    return {"anomaly_key": anomaly_key, "dismissed": True}


@router.get("/goals")
def goals() -> dict[str, Any]:
    return views.goals_view(get_snapshot())


@router.post("/simulate")
def simulate(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """Run a what-if scenario across every goal.

    Accepts `cancel_series` (keys), `category_pct_change` (slug -> percentage
    delta) and `one_off` entries.
    """
    cancel = tuple(str(k) for k in payload.get("cancel_series", []))

    pct_raw = payload.get("category_pct_change", {}) or {}
    try:
        pct = {str(k): float(v) for k, v in pct_raw.items()}
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="category_pct_change must be numbers") from None

    one_offs = []
    from datetime import date as _date

    for entry in payload.get("one_off", []) or []:
        try:
            one_offs.append(
                OneOff(
                    amount_paise=int(entry["amount_paise"]),
                    on_date=_date.fromisoformat(str(entry["on_date"])),
                    category_slug=str(entry.get("category_slug", UNCATEGORISED_SLUG)),
                )
            )
        except (KeyError, TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Malformed one_off entry") from None

    scenario = Scenario(
        cancel_series=cancel, category_pct_change=pct, one_off=tuple(one_offs)
    )
    return views.run_simulation(get_snapshot(), scenario)
