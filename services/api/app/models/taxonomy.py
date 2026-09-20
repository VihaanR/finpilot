"""The category taxonomy, read from the migration that seeds it.

DESIGN.md section 5.3 lives in `supabase/migrations/…_seed_categories.sql`.
The API needs the same list for display names, icons and income flags, and
keeping a second hand-written copy here would drift the moment either changed.
So this module parses the migration instead: one source of truth, and
`tests/test_taxonomy.py` fails the build if the parse stops finding 42 rows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_MIGRATION = (
    Path(__file__).resolve().parents[4]
    / "supabase"
    / "migrations"
    / "20260919000004_seed_categories.sql"
)

_ROW_RE = re.compile(
    r"\(\s*'([^']+)'\s*,\s*'([a-z0-9-]+)'\s*,\s*'([a-z0-9-]+)'\s*,"
    r"\s*(true|false)\s*,\s*(\d+)\s*,\s*(null|'[a-z0-9-]+')\s*\)",
    re.I,
)


@dataclass(frozen=True)
class Category:
    name: str
    slug: str
    icon: str
    is_income: bool
    sort_order: int
    parent_slug: str | None

    @property
    def is_group(self) -> bool:
        return self.parent_slug is None


@lru_cache(maxsize=1)
def categories() -> tuple[Category, ...]:
    text = _MIGRATION.read_text(encoding="utf-8")
    rows: list[Category] = []
    for name, slug, icon, is_income, sort_order, parent in _ROW_RE.findall(text):
        rows.append(
            Category(
                name=name,
                slug=slug,
                icon=icon,
                is_income=is_income.lower() == "true",
                sort_order=int(sort_order),
                parent_slug=None if parent.lower() == "null" else parent.strip("'"),
            )
        )
    return tuple(sorted(rows, key=lambda c: c.sort_order))


@lru_cache(maxsize=1)
def by_slug() -> dict[str, Category]:
    return {c.slug: c for c in categories()}


def slugs() -> list[str]:
    return [c.slug for c in categories()]


def display_name(slug: str) -> str:
    category = by_slug().get(slug)
    return category.name if category else slug.replace("-", " ").title()


def is_income_slug(slug: str) -> bool:
    category = by_slug().get(slug)
    return bool(category and category.is_income)


def group_of(slug: str) -> str:
    """The top-level group a leaf belongs to, or the slug itself if it is one."""
    category = by_slug().get(slug)
    if category is None:
        return "other"
    return category.parent_slug or category.slug
