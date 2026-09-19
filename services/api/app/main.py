"""FinPilot API entrypoint.

Render start command:
    uvicorn app.main:app --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings

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


@app.get("/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness probe.

    Also the target of the keep-alive ping described in USER.md section 8b,
    which stops Render's free tier cold-starting on a judge's first request.
    """
    return {"status": "ok"}
