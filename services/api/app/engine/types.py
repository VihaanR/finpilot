"""Shared value types for the analytics engine.

DESIGN.md section 8: the engine is pure. Nothing in this package imports
`anthropic`, `supabase`, SQLAlchemy or any database module. Callers adapt
persisted rows into these frozen dataclasses and adapt the results back.

DESIGN.md section 5.1, invariant 1: money is BIGINT paise everywhere. Every
money field below is an `int`. Formatting to rupees happens once, at the
render boundary, and never in here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

# --- Money ------------------------------------------------------------------

PAISE_PER_RUPEE = 100


def rupees(amount: int) -> int:
    """Whole rupees -> paise. For readability in constants and tests only."""
    return amount * PAISE_PER_RUPEE


#: RBI e-mandate framework (DESIGN.md R1). Recurring debits at or below
#: Rs 15,000 require no additional factor of authentication after setup.
AFA_SILENT_CEILING_PAISE = rupees(15_000)

#: Rs 1,00,000 ceiling for insurance premiums, mutual-fund SIPs and
#: credit-card bill mandates.
AFA_HIGH_LIMIT_CEILING_PAISE = rupees(1_00_000)

#: The three categories RBI granted the higher e-mandate ceiling to.
HIGH_LIMIT_CATEGORY_SLUGS = frozenset(
    {"insurance-premium", "investment-sip", "credit-card-payment"}
)

UNCATEGORISED_SLUG = "uncategorised"


# --- Enums ------------------------------------------------------------------


class Direction(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class Channel(str, Enum):
    UPI = "UPI"
    NEFT = "NEFT"
    IMPS = "IMPS"
    CARD = "CARD"
    NACH = "NACH"
    ACH = "ACH"
    ATM = "ATM"
    CASH = "CASH"
    CHEQUE = "CHEQUE"
    OTHER = "OTHER"


class Cadence(str, Enum):
    WEEKLY = "WEEKLY"
    FORTNIGHTLY = "FORTNIGHTLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    HALF_YEARLY = "HALF_YEARLY"
    ANNUAL = "ANNUAL"


#: Canonical day-count per cadence, per the DESIGN.md section 8.1 set
#: {7, 14, 30, 91, 182, 365}.
CADENCE_DAYS: dict[Cadence, int] = {
    Cadence.WEEKLY: 7,
    Cadence.FORTNIGHTLY: 14,
    Cadence.MONTHLY: 30,
    Cadence.QUARTERLY: 91,
    Cadence.HALF_YEARLY: 182,
    Cadence.ANNUAL: 365,
}


class MandateChannel(str, Enum):
    UPI_AUTOPAY = "UPI_AUTOPAY"
    NACH = "NACH"
    CARD_EMANDATE = "CARD_EMANDATE"
    SI = "SI"
    MANUAL = "MANUAL"
    UNKNOWN = "UNKNOWN"


class AfaBand(str, Enum):
    #: Debits with no OTP. The thing Mandate Radar exists to surface.
    SILENT = "SILENT"
    HIGH_LIMIT = "HIGH_LIMIT"
    REQUIRES_AFA = "REQUIRES_AFA"


class SeriesStatus(str, Enum):
    ACTIVE = "ACTIVE"
    #: Exactly two tight occurrences: surfaced but flagged, per section 8.1.
    PROBABLE = "PROBABLE"
    LAPSED = "LAPSED"
    CANCELLED = "CANCELLED"


class AnomalyType(str, Enum):
    CATEGORY_SPIKE = "category_spike"
    NEW_LARGE_MERCHANT = "new_large_merchant"
    DUPLICATE_CHARGE = "duplicate_charge"
    PRICE_HIKE = "price_hike"
    SILENT_MANDATE = "silent_mandate"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PaceVerdict(str, Enum):
    ON_PACE = "ON_PACE"
    AHEAD = "AHEAD"
    OVER = "OVER"
    PROJECTED_OVER = "PROJECTED_OVER"


class GoalVerdict(str, Enum):
    ON_TRACK = "ON_TRACK"
    BEHIND = "BEHIND"
    AHEAD = "AHEAD"
    #: No projected surplus at all: the goal never lands on current behaviour.
    UNREACHABLE = "UNREACHABLE"


# --- Inputs -----------------------------------------------------------------


@dataclass(frozen=True)
class Txn:
    """One ledger row, already normalised and categorised by the ingest tier."""

    id: str
    txn_date: date
    amount_paise: int  # always positive; `direction` carries the sign
    direction: Direction
    raw_narration: str
    normalized_merchant: str
    category_slug: str = UNCATEGORISED_SLUG
    channel: Channel = Channel.OTHER
    account_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.amount_paise, int) or isinstance(self.amount_paise, bool):
            raise TypeError(
                f"amount_paise must be int paise, got {type(self.amount_paise).__name__}"
            )
        if self.amount_paise < 0:
            raise ValueError("amount_paise is always positive; use `direction` for sign")


@dataclass(frozen=True)
class Goal:
    id: str
    name: str
    target_paise: int
    current_paise: int
    target_date: date
    priority: int = 0  # lower number = funded first
    monthly_contribution_paise: int = 0


@dataclass(frozen=True)
class Budget:
    category_slug: str
    limit_paise: int
    period_start: date


@dataclass(frozen=True)
class PricePoint:
    effective_from: date
    amount_paise: int


# --- Engine outputs ---------------------------------------------------------


@dataclass(frozen=True)
class RecurringSeries:
    normalized_merchant: str
    category_slug: str | None
    direction: Direction
    cadence: Cadence
    median_amount_paise: int
    amount_tolerance_paise: int
    median_gap_days: float
    gap_mad: float
    occurrence_count: int
    first_seen: date
    last_seen: date
    next_expected_date: date
    confidence: float
    mandate_channel: MandateChannel
    afa_band: AfaBand
    status: SeriesStatus
    txn_ids: tuple[str, ...]
    price_history: tuple[PricePoint, ...] = ()
    acknowledged: bool = False
    #: Stable identity so the UI, simulator and anomaly layer can refer to a
    #: series without a database round-trip.
    key: str = ""


@dataclass(frozen=True)
class Citation:
    label: str
    value_paise: int
    txn_ids: tuple[str, ...]

    @property
    def txn_count(self) -> int:
        return len(self.txn_ids)


@dataclass(frozen=True)
class Anomaly:
    type: AnomalyType
    severity: Severity
    period_start: date
    period_end: date
    txn_ids: tuple[str, ...]
    explanation: str
    metric: dict[str, float | int | str] = field(default_factory=dict)
    series_key: str | None = None


@dataclass(frozen=True)
class Obligation:
    """A single forward-dated expected debit from a recurring series."""

    series_key: str
    normalized_merchant: str
    category_slug: str | None
    due_date: date
    amount_paise: int
    afa_band: AfaBand
    mandate_channel: MandateChannel
    acknowledged: bool


@dataclass(frozen=True)
class SafeToSpend:
    as_of: date
    next_income_date: date | None
    next_income_paise: int
    current_balance_paise: int
    committed_paise: int
    goal_due_paise: int
    discretionary_paise: int
    days_remaining: int
    safe_daily_paise: int
    obligations: tuple[Obligation, ...]
    citations: tuple[Citation, ...] = ()


@dataclass(frozen=True)
class MonthlySummary:
    month: date  # first day of the month
    income_paise: int
    expense_paise: int
    net_paise: int
    savings_rate_pct: float
    by_category_paise: dict[str, int]
    txn_count: int


@dataclass(frozen=True)
class BudgetStatus:
    category_slug: str
    limit_paise: int
    spent_paise: int
    remaining_paise: int
    pct_used: float
    days_elapsed: int
    days_in_period: int
    projected_spend_paise: int
    pace: PaceVerdict
    txn_ids: tuple[str, ...]


@dataclass(frozen=True)
class GoalProjection:
    goal_id: str
    name: str
    target_paise: int
    current_paise: int
    shortfall_paise: int
    target_date: date
    months_remaining: int
    required_monthly_paise: int
    allocated_monthly_paise: int
    projected_eta: date | None
    months_delta: int  # negative = early, positive = late
    verdict: GoalVerdict


@dataclass(frozen=True)
class GoalDiff:
    goal_id: str
    name: str
    eta_before: date | None
    eta_after: date | None
    months_delta: int  # negative = the change pulls the goal earlier


@dataclass(frozen=True)
class OneOff:
    amount_paise: int
    on_date: date
    category_slug: str = UNCATEGORISED_SLUG


@dataclass(frozen=True)
class Scenario:
    cancel_series: tuple[str, ...] = ()  # series keys
    category_pct_change: dict[str, float] = field(default_factory=dict)
    one_off: tuple[OneOff, ...] = ()


@dataclass(frozen=True)
class SimulationResult:
    goals: tuple[GoalDiff, ...]
    monthly_surplus_before_paise: int
    monthly_surplus_after_paise: int
    monthly_surplus_delta_paise: int
    safe_daily_before_paise: int
    safe_daily_after_paise: int
    safe_daily_delta_paise: int
    cancelled_monthly_paise: int
    narration_facts: dict[str, int | str] = field(default_factory=dict)
