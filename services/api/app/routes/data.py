"""Dashboard, transactions and reference data."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from ..deps import get_snapshot, get_store
from ..models.taxonomy import categories
from ..services import views

router = APIRouter(prefix="/api", tags=["data"])


@router.get("/dashboard")
def dashboard() -> dict[str, Any]:
    return views.dashboard(get_snapshot())


@router.get("/categories")
def category_list() -> dict[str, Any]:
    return {
        "categories": [
            {
                "slug": c.slug,
                "name": c.name,
                "icon": c.icon,
                "is_income": c.is_income,
                "parent_slug": c.parent_slug,
                "sort_order": c.sort_order,
            }
            for c in categories()
        ]
    }


@router.get("/transactions")
def transaction_list(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    category: str | None = None,
    search: str | None = None,
    since: str | None = None,
    ids: str | None = Query(None, description="Comma-separated transaction ids."),
) -> dict[str, Any]:
    """`ids` is what a CitationChip sends: show me exactly these rows."""
    store = get_store()
    id_list = [p for p in (ids or "").split(",") if p.strip()] if ids is not None else None
    rows = store.transactions(
        limit=limit,
        offset=offset,
        category_slug=category,
        search=search,
        since=since,
        ids=id_list,
    )
    return {"transactions": rows, "total": store.transaction_count(), "limit": limit, "offset": offset}


@router.patch("/transactions/{txn_id}/category")
def override_category(txn_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Tier-3 override. Retroactively re-categorises matching history.

    The returned count is what the UI shows as "Learned — N past transactions
    updated" (DESIGN.md section 7).
    """
    slug = str(payload.get("category_slug", "")).strip()
    valid = {c.slug for c in categories()}
    if slug not in valid:
        raise HTTPException(status_code=422, detail="Unknown category: {0}".format(slug))
    try:
        updated, merchant = get_store().override_category(txn_id, slug)
    except KeyError:
        raise HTTPException(status_code=404, detail="No such transaction") from None
    return {
        "updated_count": updated,
        "merchant": merchant,
        "category_slug": slug,
        "message": "Learned — {0} past transaction{1} updated.".format(
            updated, "" if updated == 1 else "s"
        ),
    }


@router.get("/documents")
def document_list() -> dict[str, Any]:
    return {"documents": get_store().documents()}


@router.get("/documents/{doc_id}")
def document_detail(doc_id: str) -> dict[str, Any]:
    """Reports which adapter parsed the document and how confidently."""
    document = get_store().document(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="No such document")
    return document


@router.get("/budgets")
def budget_list() -> dict[str, Any]:
    snapshot = get_snapshot()
    return {"budgets": views.dashboard(snapshot)["budgets"]}
