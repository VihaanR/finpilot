"""FinPilot API entrypoint.

Render start command:
    uvicorn app.main:app --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .deps import get_store
from .routes import data, ingest, insights, vault
from .store import demo

app = FastAPI(
    title="FinPilot API",
    description=(
        "Personal finance decision support. Deterministic engine first, "
        "agent second: the language model never computes a number."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data.router)
app.include_router(ingest.router)
app.include_router(insights.router)
app.include_router(vault.router)


@app.on_event("startup")
def seed_demo_if_empty() -> None:
    """Load the demo ledger on first boot so the app is never empty.

    Set `FINPILOT_SKIP_DEMO=1` to start with a blank store.
    """
    if os.environ.get("FINPILOT_SKIP_DEMO"):
        return
    store = get_store()
    if store.transaction_count() == 0:
        demo.load(store, reset=False)


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness probe.

    Also the target of the keep-alive ping described in USER.md section 8b,
    which stops Render's free tier cold-starting on a judge's first request.
    """
    return {"status": "ok"}
