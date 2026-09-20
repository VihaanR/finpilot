"""Demo dataset loading.

Seeds the store by pushing `seed/output/*.csv` through the real ingestion
pipeline rather than inserting rows directly. That costs a second of startup
and buys something worth more: the demo account proves the upload path works.
If ingestion breaks, the demo breaks, and we find out before a judge does.

`seed/output/` is git-ignored, so a fresh clone regenerates it first. The
as-of date is pinned because seed determinism is per `(seed, as-of)` — an
unpinned run produces a different 14-month window tomorrow.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..ingest.pipeline import ingest
from .db import Store

REPO_ROOT = Path(__file__).resolve().parents[4]
SEED_DIR = REPO_ROOT / "seed"
OUTPUT_DIR = SEED_DIR / "output"

DEMO_SEED = 42
DEMO_AS_OF = "2026-09-19"

CONSENT_VERSION = "1.0.0"
#: Scopes the vault can grant or revoke independently. Revoking `ai_processing`
#: must leave the deterministic engine working (DESIGN.md 10.2).
CONSENT_SCOPES = ("data_processing", "ai_processing")

_STATEMENTS = ("hdfc_savings", "icici_credit", "sbi_savings")


def ensure_generated(*, seed: int = DEMO_SEED, as_of: str = DEMO_AS_OF) -> None:
    if all((OUTPUT_DIR / (name + ".csv")).exists() for name in _STATEMENTS):
        return
    subprocess.run(
        [sys.executable, str(SEED_DIR / "generate.py"),
         "--seed", str(seed), "--as-of", as_of],
        cwd=str(REPO_ROOT),
        check=True,
        capture_output=True,
    )


def _metadata() -> dict[str, Any]:
    path = OUTPUT_DIR / "seed.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load(store: Store, *, reset: bool = True) -> dict[str, Any]:
    """Populate the store with the 14-month demo ledger."""
    ensure_generated()
    if reset:
        store.erase_everything()

    meta = _metadata()
    accounts = {a["key"]: a for a in meta.get("accounts", [])}

    summary: dict[str, Any] = {"documents": [], "inserted": 0, "duplicates": 0}
    for key in _STATEMENTS:
        csv_path = OUTPUT_DIR / (key + ".csv")
        if not csv_path.exists():
            continue
        spec = accounts.get(key, {})
        account_id = store.upsert_account(
            bank_code=str(spec.get("bank_code", "UNKNOWN")),
            display_name=str(spec.get("display_name", key.replace("_", " ").title())),
            account_type=str(spec.get("account_type", "SAVINGS")),
            last4=spec.get("last4"),
            opening_balance_paise=int(spec.get("opening_balance_paise", 0)),
        )
        result = ingest(
            store,
            data=csv_path.read_bytes(),
            filename=csv_path.name,
            account_id=account_id,
        )
        summary["documents"].append(
            {
                "filename": csv_path.name,
                "adapter": result.adapter,
                "confidence": result.confidence,
                "inserted": result.inserted,
                "duplicates": result.duplicates,
            }
        )
        summary["inserted"] += result.inserted
        summary["duplicates"] += result.duplicates

    for goal in meta.get("goals", []):
        store.upsert_goal(
            name=str(goal["name"]),
            target_paise=int(goal["target_paise"]),
            current_paise=int(goal["current_paise"]),
            target_date=str(goal["target_date"]),
            priority=int(goal.get("priority", 0)),
            monthly_contribution_paise=int(goal.get("monthly_contribution_paise", 0)),
        )
    for budget in meta.get("budgets", []):
        store.upsert_budget(
            category_slug=str(budget["category_slug"]),
            limit_paise=int(budget["limit_paise"]),
            period_start=str(budget["starts_on"]),
        )

    for scope in CONSENT_SCOPES:
        store.set_consent(version=CONSENT_VERSION, scope=scope, granted=True)

    summary["transactions"] = store.transaction_count()
    summary["accounts"] = len(store.accounts())
    summary["goals"] = len(store.goals())
    summary["budgets"] = len(store.budgets())
    return summary
