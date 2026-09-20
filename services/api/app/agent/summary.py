"""Monthly summary generation (DESIGN.md 9.6).

Runs on Groq (`groq_model_summary`), same provider as chat — switched 20 Sep
2026 off Gemini's 20-requests/day free-tier wall.

The model receives **only pre-computed engine output**. It writes prose around
figures it did not produce and cannot change, which is the same guarantee the
chat loop makes, obtained here without a tool loop because the shape of a
monthly summary is known in advance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..config import settings
from ..engine import cashflow, goals as goals_engine
from ..models.taxonomy import display_name
from ..services.views import Snapshot
from . import guardrails, llm
from .prompts import SUMMARY_PROMPT


@dataclass
class Summary:
    month: str
    text: str
    facts: dict[str, Any]
    declined: bool = False
    error: str | None = None


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _prev_month(value: date) -> date:
    return (value.replace(day=1) - __import__("datetime").timedelta(days=1)).replace(day=1)


def collect_facts(snapshot: Snapshot, *, month: date | None = None) -> dict[str, Any]:
    """Everything the summary is allowed to mention, computed by the engine.

    Assembled separately from the prose call so it can be asserted in tests
    and rendered in the UI even when no key is configured.
    """
    target = _month_start(month or snapshot.as_of)
    previous = _prev_month(target)

    this = cashflow.monthly_summary(snapshot.txns, month=target)
    last = cashflow.monthly_summary(snapshot.txns, month=previous)

    movements = []
    for slug in set(this.by_category_paise) | set(last.by_category_paise):
        now = this.by_category_paise.get(slug, 0)
        before = last.by_category_paise.get(slug, 0)
        delta = now - before
        if delta:
            movements.append(
                {
                    "category": display_name(slug),
                    "this_month_paise": now,
                    "last_month_paise": before,
                    "delta_paise": delta,
                    "delta_pct": round(delta * 100.0 / before, 1) if before else None,
                }
            )
    movements.sort(key=lambda m: -abs(int(m["delta_paise"])))

    upcoming = cashflow.upcoming(snapshot.series, days=30, as_of=snapshot.as_of)
    projections = goals_engine.project(snapshot.goals, snapshot.txns, as_of=snapshot.as_of)

    return {
        "month": target.isoformat(),
        "month_label": target.strftime("%B %Y"),
        "headline": {
            "income_paise": this.income_paise,
            "expense_paise": this.expense_paise,
            "net_paise": this.net_paise,
            "savings_rate_pct": this.savings_rate_pct,
            "txn_count": this.txn_count,
        },
        "top_movements": movements[:3],
        "committed_next_month": [
            {
                "merchant": o.normalized_merchant,
                "amount_paise": o.amount_paise,
                "due_date": o.due_date.isoformat(),
                "silent": o.afa_band.value == "SILENT" and not o.acknowledged,
            }
            for o in upcoming
        ],
        "anomalies": [
            {"type": a.type.value, "severity": a.severity.value, "explanation": a.explanation}
            for a in snapshot.anomalies
        ][:8],
        "goals": [
            {
                "name": p.name,
                "verdict": p.verdict.value,
                "projected_eta": p.projected_eta.isoformat() if p.projected_eta else None,
                "months_delta": p.months_delta,
                "required_monthly_paise": p.required_monthly_paise,
            }
            for p in projections
        ],
    }


def generate(snapshot: Snapshot, *, month: date | None = None) -> Summary:
    """Write the month's summary. Degrades to facts-only without a key."""
    facts = collect_facts(snapshot, month=month)

    if not llm.available():
        return Summary(
            month=facts["month"],
            text="",
            facts=facts,
            error="Narration needs a Groq API key. The figures below are the engine's.",
        )

    model = settings.groq_model_summary
    body = json.dumps(facts, indent=2)
    payload = llm.prepare([body])
    llm.assert_clean(payload.texts)
    llm.disclose(snapshot.store, purpose="monthly_summary", model=model, payload=payload)

    try:
        response = llm.client().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SUMMARY_PROMPT},
                {"role": "user", "content": payload.texts[0]},
            ],
        )
        text = (response.choices[0].message.content or "").strip()
    except Exception as exc:
        return Summary(
            month=facts["month"],
            text="",
            facts=facts,
            error=f"Summary generation failed: {type(exc).__name__}",
        )

    text = llm.render_back(text, payload.mapping)
    verdict = guardrails.enforce_advice_boundary(text)
    return Summary(
        month=facts["month"], text=verdict.text, facts=facts, declined=verdict.declined
    )
