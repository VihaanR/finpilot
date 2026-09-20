"""Shared request dependencies."""

from __future__ import annotations

import os
from datetime import date
from functools import lru_cache
from pathlib import Path

from .services.views import Snapshot
from .store.db import DEFAULT_DB_PATH, Store

#: Pinned because seed determinism is per (seed, as-of date): the 14-month
#: window is anchored to "today", so an unpinned demo drifts overnight and the
#: eval harness stops matching `seed/expected.json`.
DEMO_AS_OF = date(2026, 9, 19)


@lru_cache(maxsize=1)
def get_store() -> Store:
    path = os.environ.get("FINPILOT_DB_PATH")
    return Store(Path(path) if path else DEFAULT_DB_PATH)


def get_snapshot() -> Snapshot:
    return Snapshot(get_store(), as_of=DEMO_AS_OF)


def reset_store_cache() -> None:
    get_store.cache_clear()
