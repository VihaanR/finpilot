"""The eval harness (DESIGN.md §9.5, BUILD_TASKS.md T15).

Three layers, deliberately separated by what they cost:

**Offline (always runs).** The engine's figure must equal the ground truth in
`seed/expected.json`. This is the real regression harness — it catches an
engine change that silently moves a number, needs no API key, and runs in
about two seconds.

**Live (opt-in).** The agent must pick the right tool and the figure it
*cited* must equal the engine's. This is what proves the citation architecture
end to end, and it is what needs the model.

The split exists because the Gemini free tier allows roughly eight questions a
day per model id (see CLAUDE.md), and 25 questions at 2–3 calls each does not
fit. Marking the live subset is honest about that rather than shipping a suite
that cannot pass.

    pytest evals/                 # offline only
    pytest evals/ --live          # + the `live: true` subset
    pytest evals/ --live-all      # + every case (needs billing)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.agent import loop, tools as T
from app.services.views import Snapshot
from app.store import demo
from app.store.db import Store

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = yaml.safe_load((Path(__file__).parent / "golden.yaml").read_text(encoding="utf-8"))
EXPECTED = json.loads((ROOT / "seed" / "expected.json").read_text(encoding="utf-8"))
CASES = GOLDEN["cases"]


def lookup(path: str) -> Any:
    """Resolve a dotted path into seed/expected.json.

    Month keys contain dots of their own ("monthly_income_paise.2026-09"), so
    the walk is greedy on the remainder rather than a naive split.
    """
    node: Any = EXPECTED
    parts = path.split(".")
    while parts:
        for take in range(len(parts), 0, -1):
            key = ".".join(parts[:take])
            if isinstance(node, dict) and key in node:
                node = node[key]
                parts = parts[take:]
                break
        else:
            raise KeyError(f"{path} is not in seed/expected.json")
    return node


@pytest.fixture(scope="session")
def snapshot() -> Snapshot:
    store = Store(Path(__file__).parent / ".eval.db")
    demo.load(store, reset=True)
    snap = Snapshot(store)
    assert snap.as_of.isoformat() == GOLDEN["meta"]["as_of"], (
        "The eval set is pinned to a single as-of date; regenerate the seed "
        f"with --as-of {GOLDEN['meta']['as_of']} (see CLAUDE.md gotchas)."
    )
    return snap


# --- Layer 1: the engine against ground truth -------------------------------


def test_the_seed_matches_its_own_ground_truth(snapshot: Snapshot) -> None:
    assert len(snapshot.txns) == EXPECTED["transaction_count"]
    assert len(snapshot.goals) == EXPECTED["goal_count"]


@pytest.mark.parametrize(
    "case",
    [c for c in CASES if c.get("expect") or c.get("expect_count")],
    ids=lambda c: c["id"],
)
def test_ground_truth_value_exists(case: dict[str, Any]) -> None:
    """Every expectation path must resolve — a typo would silently pass."""
    path = case.get("expect") or case["expect_count"]
    assert lookup(path) is not None


def test_top_category_per_month_matches_the_engine(snapshot: Snapshot) -> None:
    """The figure behind eval case `top_category_*`, checked without the model."""
    ctx = T.ToolContext(snapshot=snapshot, citations=T.CitationRegistry())
    for month, expected_slug in EXPECTED["top_category_per_month"].items():
        result = T.dispatch("get_category_breakdown", {"period": month}, ctx)
        if "error" in result:
            continue  # months outside the ledger window
        top = result["data"]["categories"][0]
        assert top["category_slug"] == expected_slug, month
        assert top["total_paise"] == lookup(f"top_category_value_paise.{month}"), month


def test_monthly_totals_match_the_engine(snapshot: Snapshot) -> None:
    from app.engine import cashflow
    from datetime import date

    for month, expected_income in EXPECTED["monthly_income_paise"].items():
        summary = cashflow.monthly_summary(snapshot.txns, month=date.fromisoformat(month + "-01"))
        assert summary.income_paise == expected_income, f"income {month}"
        assert summary.expense_paise == EXPECTED["monthly_expense_paise"][month], f"expense {month}"
        assert summary.net_paise == EXPECTED["monthly_net_paise"][month], f"net {month}"


def test_subscriptions_match_ground_truth(snapshot: Snapshot) -> None:
    subs = [s for s in snapshot.series if s.category_slug == "subscriptions"]
    assert len(subs) == EXPECTED["subscription_count"]
    found = {s.normalized_merchant for s in subs}
    assert found == set(EXPECTED["subscriptions"]), found ^ set(EXPECTED["subscriptions"])


def test_planted_anomalies_are_all_detected(snapshot: Snapshot) -> None:
    """Each planted anomaly must appear, with its ground-truth figure."""
    blob = " ".join(a.explanation for a in snapshot.anomalies)
    assert EXPECTED["price_hike"]["merchant"] in blob
    assert EXPECTED["duplicate_charge"]["merchant"] in blob
    assert EXPECTED["new_large_merchant"]["merchant"] in blob

    kinds = {a.type.value for a in snapshot.anomalies}
    assert kinds == {
        "silent_mandate",
        "category_spike",
        "duplicate_charge",
        "price_hike",
        "new_large_merchant",
    }, "all five DESIGN.md §8.2 types must fire on the seed"


# --- Layer 2 and 3: the agent, live -----------------------------------------


def _live_cases(config: Any) -> list[dict[str, Any]]:
    if config.getoption("--live-all"):
        return CASES
    if config.getoption("--live"):
        return [c for c in CASES if c.get("live")]
    return []


@pytest.mark.live
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_agent_cites_the_engines_figure(
    case: dict[str, Any], snapshot: Snapshot, request: pytest.FixtureRequest
) -> None:
    """The figure the agent CITED must equal the figure the engine computed.

    Not "the agent's prose contains the right number" — the citation is the
    claim under test. A correct number with no citation behind it is exactly
    the failure mode the architecture exists to prevent.
    """
    if case not in _live_cases(request.config):
        pytest.skip("live case; pass --live (subset) or --live-all")

    answer = loop.ask(case["question"], snapshot)
    if answer.error and "quota" in answer.error.lower():
        pytest.skip(f"Gemini quota exhausted: {answer.error}")
    assert not answer.error, answer.error

    if case.get("expect_decline"):
        assert answer.declined, f"expected the scripted decline, got: {answer.text[:200]}"
        return

    if case.get("expect_no_data"):
        lowered = answer.text.lower()
        assert any(p in lowered for p in ("don't have", "do not have", "no data", "no transactions")), (
            f"expected an explicit no-data answer, got: {answer.text[:200]}"
        )
        return

    if case.get("expect_no_leak"):
        assert case["expect_no_leak"].lower() not in answer.text.lower(), (
            "the system prompt leaked into the answer"
        )

    # The model must never invent a citation id.
    assert answer.audit is not None
    assert not answer.audit.unknown_ids, f"invented citation ids: {answer.audit.unknown_ids}"

    if case.get("expect_tool"):
        # A case may name several acceptable tools: more than one route can be
        # correct, and pinning the agent to one of them tests the harness's
        # opinion rather than the product.
        wanted = case["expect_tool"]
        acceptable = wanted if isinstance(wanted, list) else [wanted]
        assert any(t in answer.tools_used for t in acceptable), (
            f"expected one of {acceptable}, used {answer.tools_used}"
        )

    if case.get("expect_count"):
        # A count is not a money figure, so it has no citation value to match.
        # It must still be the engine's number, stated in the answer.
        target = lookup(case["expect_count"])
        assert str(target) in re.findall("[0-9]+", answer.text), (
            f"expected the count {target} in the answer, got: {answer.text[:200]}"
        )

    if case.get("expect") and case.get("tolerance_paise", 0) is not None:
        target = lookup(case["expect"])
        cited = {c["value_paise"] for c in answer.citations}
        assert target in cited, (
            f"ground truth {target} paise was not among the cited figures {sorted(cited)[:8]}"
        )
