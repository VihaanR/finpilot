"""Engine invariants.

Two BUILD_TASKS.md T06 acceptance criteria are structural rather than
behavioural, so they are asserted here rather than left to review:

  - no engine function imports `google.genai`, `supabase` or any database module
  - every money value in every return type is an `int`
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
from datetime import date

import pytest

from app.engine import anomaly, budget, cashflow, goals, recurrence, simulate
from app.engine.types import Budget, Direction, OneOff, Scenario, rupees

from .conftest import monthly_run, series, txn

ENGINE_DIR = pathlib.Path(__file__).resolve().parents[1] / "app" / "engine"

#: DESIGN.md section 8: the engine is pure. These may never be imported.
FORBIDDEN_ROOTS = {
    # Runtime inference provider. `anthropic` stays listed so that if anyone
    # reintroduces it the engine still refuses to depend on a model vendor.
    "google",
    "google_genai",
    "anthropic",
    "supabase",
    "sqlalchemy",
    "psycopg",
    "psycopg2",
    "asyncpg",
    "databases",
    "alembic",
    "fastapi",
    "httpx",
    "requests",
}


def _engine_modules():
    return sorted(p for p in ENGINE_DIR.glob("*.py"))


def _imported_roots(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


class TestNoInfrastructureImports:
    @pytest.mark.parametrize(
        "path", _engine_modules(), ids=lambda p: p.name
    )
    def test_module_imports_no_database_or_llm_package(self, path):
        offending = _imported_roots(path) & FORBIDDEN_ROOTS
        assert offending == set(), f"{path.name} imports {sorted(offending)}"

    def test_engine_directory_is_not_empty(self):
        """Guards against the parametrised test vacuously passing."""
        assert len(_engine_modules()) >= 7


def _money_fields(value, path="result"):
    """Yield (path, value) for every `*_paise` field, recursively."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for field in dataclasses.fields(value):
            child = getattr(value, field.name)
            child_path = f"{path}.{field.name}"
            if field.name.endswith("_paise"):
                # A `*_paise` field may hold a container of money values
                # (by_category_paise is a dict of slug -> paise), so descend
                # into it rather than asserting the container itself is an int.
                if isinstance(child, dict):
                    for key, item in child.items():
                        yield f"{child_path}[{key!r}]", item
                elif isinstance(child, (list, tuple)):
                    for index, item in enumerate(child):
                        yield f"{child_path}[{index}]", item
                else:
                    yield child_path, child
            else:
                yield from _money_fields(child, child_path)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _money_fields(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}[{key!r}]"
            if isinstance(key, str) and key.endswith("_paise"):
                yield child_path, item
            else:
                yield from _money_fields(item, child_path)


def _assert_all_int(value):
    checked = 0
    for path, money in _money_fields(value):
        assert isinstance(money, int) and not isinstance(money, bool), (
            f"{path} is {type(money).__name__}, expected int paise"
        )
        checked += 1
    return checked


AS_OF = date(2026, 9, 10)


class TestMoneyIsAlwaysInteger:
    """A float anywhere in a currency path is the bug DESIGN.md 5.1 forbids."""

    def test_recurring_series(self):
        found = recurrence.detect(
            monthly_run(start=date(2025, 10, 5), count=12, amount_rupees=199,
                        merchant="NETFLIX"),
            as_of=AS_OF,
        )
        assert _assert_all_int(found) > 0

    def test_safe_to_spend(self):
        result = cashflow.safe_to_spend(
            [
                series(merchant="ACME", amount_rupees=1_00_000, category="salary",
                       direction=Direction.CREDIT,
                       next_expected=date(2026, 9, 25), key="k-salary"),
                series(merchant="LANDLORD", amount_rupees=25_000, category="rent",
                       next_expected=date(2026, 9, 15), key="k-rent"),
            ],
            [],
            current_balance_paise=rupees(80_000),
            as_of=AS_OF,
        )
        assert _assert_all_int(result) > 0

    def test_monthly_summary(self):
        rows = [
            txn(on=date(2026, 8, 1), amount_rupees=1_00_000,
                direction=Direction.CREDIT, merchant="ACME", category="salary"),
            txn(on=date(2026, 8, 5), amount_rupees=25_000, merchant="LANDLORD",
                category="rent"),
        ]
        result = cashflow.monthly_summary(rows, month=date(2026, 8, 1))
        assert _assert_all_int(result) > 0

    def test_budget_status(self):
        rows = budget.status(
            [Budget(category_slug="food-delivery", limit_paise=rupees(10_000),
                    period_start=date(2026, 9, 1))],
            [txn(on=date(2026, 9, 3), amount_rupees=2_500, merchant="SWIGGY",
                 category="food-delivery")],
            as_of=AS_OF,
        )
        assert _assert_all_int(rows) > 0

    def test_goal_projection(self, goal_on_track):
        rows = goals.project([goal_on_track], as_of=AS_OF,
                             surplus_paise=rupees(50_000))
        assert _assert_all_int(rows) > 0

    def test_anomalies(self):
        rows = [
            txn(on=date(2026, 9, 4), amount_rupees=1_299, merchant="BIGBASKET"),
            txn(on=date(2026, 9, 6), amount_rupees=1_299, merchant="BIGBASKET"),
        ]
        found = anomaly.detect_duplicate_charges(rows)
        assert _assert_all_int(found) > 0

    def test_simulation_result(self, goal_on_track):
        result = simulate.simulate(
            [
                txn(on=date(2026, m, 1), amount_rupees=1_00_000,
                    direction=Direction.CREDIT, merchant="ACME",
                    category="salary")
                for m in (6, 7, 8)
            ],
            [series(merchant="LANDLORD", amount_rupees=25_000, category="rent",
                    next_expected=date(2026, 9, 15), key="k-rent")],
            [goal_on_track],
            Scenario(cancel_series=("k-rent",),
                     one_off=(OneOff(amount_paise=rupees(1_000),
                                     on_date=date(2026, 9, 12)),)),
            current_balance_paise=rupees(80_000),
            as_of=AS_OF,
        )
        assert _assert_all_int(result) > 0

    def test_the_checker_actually_catches_a_float(self):
        """Negative control: prove the assertion above is not vacuous."""
        from app.engine.types import Citation

        bad = Citation(label="broken", value_paise=1234.5, txn_ids=())
        with pytest.raises(AssertionError):
            _assert_all_int(bad)


class TestTransactionGuards:
    def test_float_amount_is_rejected_at_construction(self):
        with pytest.raises(TypeError):
            txn(on=AS_OF, amount_paise=199.5, merchant="BADCO")

    def test_negative_amount_is_rejected(self):
        with pytest.raises(ValueError):
            txn(on=AS_OF, amount_paise=-100, merchant="BADCO")

    def test_bool_is_not_accepted_as_an_amount(self):
        with pytest.raises(TypeError):
            txn(on=AS_OF, amount_paise=True, merchant="BADCO")
