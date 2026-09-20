"""Tool-layer tests (T07, DESIGN.md 9.2 and 9.3).

These run against a real store loaded with the demo ledger rather than against
hand-built fixtures, because the property under test is precisely that a
citation resolves to rows that exist and sum to the figure claimed. A
hand-built fixture could satisfy the arithmetic while proving nothing about
the wiring.

Nothing here touches the network: `tools.py` imports no LLM client. The model
is not required to test what the model never computes.
"""

from __future__ import annotations

import pytest

from app.agent import tools as T
from app.services.views import Snapshot
from app.store import demo
from app.store.db import Store


@pytest.fixture(scope="module")
def snapshot(tmp_path_factory) -> Snapshot:
    store = Store(tmp_path_factory.mktemp("agent") / "tools.db")
    demo.load(store, reset=True)
    return Snapshot(store)


@pytest.fixture()
def ctx(snapshot) -> T.ToolContext:
    return T.ToolContext(snapshot=snapshot, citations=T.CitationRegistry())


# --- The registry -----------------------------------------------------------


def test_declarations_match_implementations() -> None:
    """A renamed parameter must not be able to drift from its declaration."""
    assert {d["name"] for d in T.TOOL_DECLARATIONS} == set(T.TOOLS)
    assert {d["name"] for d in T.ACT_TOOL_DECLARATIONS} == set(T.ACT_TOOLS)
    # DESIGN.md 9.2's original 11, plus `list_guard_events` once the browser
    # extension started reporting its intercepts back to the API.
    assert len(T.TOOLS) == 12
    assert len(T.ACT_TOOLS) == 3


def test_act_tools_are_unreachable_without_an_action_registry(ctx: T.ToolContext) -> None:
    """The read-only chat surface must not be able to stage a change.

    `/api/agent/ask` builds its context without an `ActionRegistry`, and that
    absence is what `dispatch` keys on — so a model that calls a staging tool
    by name on that endpoint gets "no such tool", not a staged action.
    """
    assert ctx.actions is None
    result = T.dispatch(
        "propose_create_goal",
        {"name": "Car", "amount_value": 50, "amount_unit": "lakh"},
        ctx,
    )
    assert "error" in result and "No such tool" in result["error"]


def test_act_tools_stage_without_mutating(snapshot) -> None:
    """Staging is not doing. Nothing reaches the store until apply."""
    ctx = T.ToolContext(
        snapshot=snapshot, citations=T.CitationRegistry(), actions=T.ActionRegistry()
    )
    before = len(snapshot.store.goals())
    result = T.dispatch(
        "propose_create_goal",
        {"name": "Car", "amount_value": 50, "amount_unit": "lakh"},
        ctx,
    )
    assert "error" not in result
    staged = ctx.actions.as_list()
    assert len(staged) == 1
    assert staged[0]["kind"] == "create_goal"
    # 50 lakh in paise, computed by Python and never by the model.
    assert staged[0]["params"]["target_paise"] == 500_000_000
    assert len(snapshot.store.goals()) == before, "staging must not write"


def test_propose_delete_rejects_an_invented_transaction_id(snapshot) -> None:
    ctx = T.ToolContext(
        snapshot=snapshot, citations=T.CitationRegistry(), actions=T.ActionRegistry()
    )
    result = T.dispatch(
        "propose_delete_transaction", {"txn_id": "not-a-real-id", "reason": "dupe"}, ctx
    )
    assert result.get("no_data") is True
    assert ctx.actions.as_list() == []


def test_citation_ids_are_sequential_and_unique(ctx: T.ToolContext) -> None:
    T.dispatch("get_category_breakdown", {}, ctx)
    T.dispatch("get_safe_to_spend", {}, ctx)
    ids = [c["id"] for c in ctx.citations.as_list()]
    assert ids == [f"c{i + 1}" for i in range(len(ids))]
    assert len(set(ids)) == len(ids)


def test_model_facing_citations_omit_txn_ids(ctx: T.ToolContext) -> None:
    """The conversation must not carry hundreds of uuids (see ToolResult)."""
    result = T.dispatch("get_category_breakdown", {}, ctx)
    assert result["citations"], "expected at least one citation"
    for stub in result["citations"]:
        assert "txn_ids" not in stub
        assert stub["txn_count"] >= 0
    # ...but the registry, which is what the UI receives, does carry them.
    assert all("txn_ids" in c for c in ctx.citations.as_list())


# --- The anti-hallucination property ---------------------------------------


def test_every_breakdown_citation_resolves_and_sums(ctx: T.ToolContext, snapshot) -> None:
    """DESIGN.md 9.3: a cited figure equals the sum of the rows behind it."""
    result = T.dispatch("get_category_breakdown", {}, ctx)
    full = {c["id"]: c for c in ctx.citations.as_list()}

    for row in result["data"]["categories"]:
        citation = full[row["citation_id"]]
        rows = snapshot.store.transactions(ids=citation["txn_ids"])
        assert len(rows) == citation["txn_count"], row["category"]
        assert sum(int(r["amount_paise"]) for r in rows) == row["total_paise"], row["category"]


def test_query_transactions_total_matches_its_citation(ctx: T.ToolContext, snapshot) -> None:
    result = T.dispatch("query_transactions", {"merchant": "SWIGGY"}, ctx)
    data = result["data"]
    citation = {c["id"]: c for c in ctx.citations.as_list()}[data["citation_id"]]
    rows = snapshot.store.transactions(ids=citation["txn_ids"])
    assert sum(int(r["amount_paise"]) for r in rows) == data["total_paise"]
    assert data["txn_count"] == len(rows)


def test_money_is_always_int(ctx: T.ToolContext) -> None:
    """The engine's paise discipline must survive the tool boundary."""
    for name, args in [
        ("get_category_breakdown", {}),
        ("get_safe_to_spend", {}),
        ("get_upcoming_obligations", {"days": 30}),
        ("list_recurring", {}),
    ]:
        result = T.dispatch(name, args, ctx)

        def walk(node) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key.endswith("_paise"):
                        assert isinstance(value, int), f"{name}.{key} is {type(value).__name__}"
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(result)


# --- Grounding: no data must say so ----------------------------------------


def test_empty_period_reports_no_data_rather_than_zero(ctx: T.ToolContext) -> None:
    """A fabricated zero is worse than an admission (DESIGN.md 9.4)."""
    result = T.dispatch("get_category_breakdown", {"period": "1999-01"}, ctx)
    assert result["no_data"] is True
    assert "1999" in result["error"]
    assert "data" not in result


def test_unparseable_period_is_refused_not_guessed(ctx: T.ToolContext) -> None:
    result = T.dispatch("get_category_breakdown", {"period": "last september"}, ctx)
    assert result["no_data"] is True
    assert "YYYY-MM" in result["error"]


def test_unknown_tool_returns_error_not_exception(ctx: T.ToolContext) -> None:
    assert "error" in T.dispatch("get_me_a_sandwich", {}, ctx)


def test_bad_arguments_do_not_raise(ctx: T.ToolContext) -> None:
    """A malformed tool call must be recoverable inside the loop."""
    result = T.dispatch("get_upcoming_obligations", {"days": "soon"}, ctx)
    assert "error" in result


# --- Individual tools -------------------------------------------------------


def test_safe_to_spend_arithmetic_holds(ctx: T.ToolContext) -> None:
    data = T.dispatch("get_safe_to_spend", {}, ctx)["data"]
    assert (
        data["discretionary_paise"]
        == data["current_balance_paise"] - data["committed_paise"] - data["goal_due_paise"]
    )
    assert data["safe_daily_paise"] >= 0


def test_list_recurring_filters_by_status(ctx: T.ToolContext) -> None:
    active = T.dispatch("list_recurring", {"status": "ACTIVE"}, ctx)["data"]
    assert active["series_count"] == 23, "the seed's ACTIVE count, per the T06 correction note"
    assert all(s["status"] == "ACTIVE" for s in active["series"])


def test_detect_anomalies_spans_the_five_types(ctx: T.ToolContext) -> None:
    data = T.dispatch("detect_anomalies", {}, ctx)["data"]
    kinds = {a["type"] for a in data["anomalies"]}
    assert kinds, "expected anomalies on the seed"
    assert kinds <= {
        "silent_mandate",
        "category_spike",
        "duplicate_charge",
        "price_hike",
        "new_large_merchant",
    }


def test_compare_periods_delta_is_b_minus_a(ctx: T.ToolContext) -> None:
    data = T.dispatch("compare_periods", {"period_a": "2026-08", "period_b": "2026-09"}, ctx)["data"]
    for row in data["categories"]:
        assert row["delta_paise"] == row["period_b_paise"] - row["period_a_paise"]


def test_compare_periods_reports_no_pct_without_a_baseline(ctx: T.ToolContext) -> None:
    """A category new this month has no baseline; None beats an infinite rise."""
    data = T.dispatch("compare_periods", {"period_a": "2026-08", "period_b": "2026-09"}, ctx)["data"]
    for row in data["categories"]:
        if row["period_a_paise"] == 0:
            assert row["delta_pct"] is None


def test_simulate_cancelling_series_frees_monthly_money(ctx: T.ToolContext, snapshot) -> None:
    subs = [s for s in snapshot.series if s.category_slug == "subscriptions" and s.key]
    assert subs, "the seed plants subscriptions"
    keys = [s.key for s in subs[:3]]
    data = T.dispatch("simulate_scenario", {"cancel_series": keys}, ctx)["data"]
    assert data["cancelled_monthly_paise"] > 0
    assert data["monthly_surplus_after_paise"] > data["monthly_surplus_before_paise"]


def test_search_documents_does_not_claim_semantic_search(ctx: T.ToolContext) -> None:
    """No pgvector is provisioned; the tool must say so rather than imply it."""
    result = T.dispatch("search_documents", {"query": "hdfc"}, ctx)
    assert result["data"]["semantic"] is False
    miss = T.dispatch("search_documents", {"query": "zzzz"}, ctx)
    assert miss["no_data"] is True
