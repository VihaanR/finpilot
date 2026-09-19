"""FinPilot analytics engine.

DESIGN.md section 8. Pure, deterministic, unit-tested. Nothing in this package
imports `google.genai`, `supabase`, SQLAlchemy or any database module — that
isolation is what makes the engine testable without infrastructure, and it is
enforced by a test in `tests/test_purity.py`.

The agent layer calls into here for every number it states. The language model
never computes a figure itself (DESIGN.md section 9).
"""

from . import anomaly, budget, cashflow, goals, recurrence, simulate, stats
from .types import (
    AfaBand,
    Anomaly,
    AnomalyType,
    Budget,
    BudgetStatus,
    Cadence,
    Channel,
    Citation,
    Direction,
    Goal,
    GoalDiff,
    GoalProjection,
    GoalVerdict,
    MandateChannel,
    MonthlySummary,
    Obligation,
    OneOff,
    PaceVerdict,
    PricePoint,
    RecurringSeries,
    SafeToSpend,
    Scenario,
    SeriesStatus,
    Severity,
    SimulationResult,
    Txn,
    rupees,
)

__all__ = [
    # modules
    "anomaly",
    "budget",
    "cashflow",
    "goals",
    "recurrence",
    "simulate",
    "stats",
    # types
    "AfaBand",
    "Anomaly",
    "AnomalyType",
    "Budget",
    "BudgetStatus",
    "Cadence",
    "Channel",
    "Citation",
    "Direction",
    "Goal",
    "GoalDiff",
    "GoalProjection",
    "GoalVerdict",
    "MandateChannel",
    "MonthlySummary",
    "Obligation",
    "OneOff",
    "PaceVerdict",
    "PricePoint",
    "RecurringSeries",
    "SafeToSpend",
    "Scenario",
    "SeriesStatus",
    "Severity",
    "SimulationResult",
    "Txn",
    "rupees",
]
