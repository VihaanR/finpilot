"""Pydantic schemas for the API boundary.

These are the wire shapes. Money crosses the wire as integer paise under a
`*_paise` name so the client cannot mistake it for rupees; formatting happens
once in the browser, in `components/ui/Money.tsx` (DESIGN.md 5.1, 11.3).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Reference data ---------------------------------------------------------


class CategoryOut(ORMModel):
    id: uuid.UUID
    parent_id: uuid.UUID | None = None
    name: str
    slug: str
    icon: str | None = None
    is_income: bool = False
    sort_order: int = 0


# --- Accounts and documents -------------------------------------------------


class AccountOut(ORMModel):
    id: uuid.UUID
    bank_code: str
    account_type: Literal["SAVINGS", "CURRENT", "CREDIT_CARD"]
    display_name: str
    last4: str | None = None
    current_balance_paise: int
    balance_as_of: date | None = None


class DocumentOut(ORMModel):
    id: uuid.UUID
    kind: Literal["STATEMENT", "BILL", "RECEIPT"]
    filename: str
    status: Literal["PENDING", "PARSED", "FAILED", "NEEDS_PASSWORD"]
    #: Which adapter parsed this, and how confident it was. Surfaced in the UI
    #: because the product never claims universal bank coverage.
    parser_name: str | None = None
    parser_version: str | None = None
    parser_confidence: float | None = None
    rows_extracted: int = 0
    error: str | None = None
    created_at: datetime
    parsed_at: datetime | None = None


class PasswordHint(BaseModel):
    bank_code: str
    bank_name: str
    #: One or more formats; SBI genuinely has three depending on source.
    formats: list[str]


class IngestError(BaseModel):
    code: Literal["NEEDS_PASSWORD", "NO_TEXT_LAYER", "UNSUPPORTED", "MALFORMED"]
    message: str
    bank_code: str | None = None
    hint: PasswordHint | None = None


# --- Transactions -----------------------------------------------------------


class TransactionOut(ORMModel):
    id: uuid.UUID
    account_id: uuid.UUID | None = None
    txn_date: date
    amount_paise: int
    direction: Literal["DEBIT", "CREDIT"]
    raw_narration: str
    normalized_merchant: str | None = None
    counterparty_vpa: str | None = None
    channel: str
    balance_paise: int | None = None
    category_id: uuid.UUID | None = None
    category_slug: str | None = None
    category_source: Literal["RULE", "LLM", "USER"] | None = None
    category_confidence: float | None = None


class CategoryOverrideIn(BaseModel):
    category_slug: str


class CategoryOverrideOut(BaseModel):
    """Response to a tier-3 override.

    `updated_count` drives the "Learned - N past transactions updated"
    confirmation that makes the product feel intelligent (DESIGN.md 7, tier 3).
    """

    transaction_id: uuid.UUID
    category_slug: str
    updated_count: int
    rule_id: uuid.UUID


# --- Engine outputs ---------------------------------------------------------


class CitationOut(BaseModel):
    label: str
    value_paise: int
    txn_ids: list[uuid.UUID] = Field(default_factory=list)
    txn_count: int = 0


class PricePointOut(BaseModel):
    effective_from: date
    amount_paise: int


class RecurringSeriesOut(ORMModel):
    id: uuid.UUID | None = None
    series_key: str | None = None
    normalized_merchant: str
    category_slug: str | None = None
    direction: Literal["DEBIT", "CREDIT"]
    cadence: Literal[
        "WEEKLY", "FORTNIGHTLY", "MONTHLY", "QUARTERLY", "HALF_YEARLY", "ANNUAL"
    ]
    median_amount_paise: int
    median_gap_days: float | None = None
    occurrence_count: int
    first_seen: date | None = None
    last_seen: date | None = None
    next_expected_date: date | None = None
    confidence: float | None = None
    mandate_channel: str
    afa_band: Literal["SILENT", "HIGH_LIMIT", "REQUIRES_AFA"]
    status: Literal["ACTIVE", "PROBABLE", "LAPSED", "CANCELLED"]
    acknowledged_at: datetime | None = None
    price_history: list[PricePointOut] = Field(default_factory=list)
    #: Radar badges, already derived so the client renders rather than decides.
    badges: list[str] = Field(default_factory=list)


class ObligationOut(BaseModel):
    series_key: str
    normalized_merchant: str
    category_slug: str | None = None
    due_date: date
    amount_paise: int
    afa_band: Literal["SILENT", "HIGH_LIMIT", "REQUIRES_AFA"]
    mandate_channel: str
    acknowledged: bool = False


class SafeToSpendOut(BaseModel):
    as_of: date
    next_income_date: date | None = None
    next_income_paise: int = 0
    current_balance_paise: int
    committed_paise: int
    goal_due_paise: int
    discretionary_paise: int
    days_remaining: int
    safe_daily_paise: int
    obligations: list[ObligationOut] = Field(default_factory=list)
    citations: list[CitationOut] = Field(default_factory=list)


class MonthlySummaryOut(BaseModel):
    month: date
    income_paise: int
    expense_paise: int
    net_paise: int
    savings_rate_pct: float
    by_category_paise: dict[str, int] = Field(default_factory=dict)
    txn_count: int


class AnomalyOut(ORMModel):
    id: uuid.UUID | None = None
    type: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    period_start: date | None = None
    period_end: date | None = None
    txn_ids: list[uuid.UUID] = Field(default_factory=list)
    explanation: str
    metric: dict[str, Any] = Field(default_factory=dict)
    series_key: str | None = None
    dismissed_at: datetime | None = None


class BudgetStatusOut(BaseModel):
    category_slug: str
    limit_paise: int
    spent_paise: int
    remaining_paise: int
    pct_used: float
    days_elapsed: int
    days_in_period: int
    projected_spend_paise: int
    pace: Literal["ON_PACE", "AHEAD", "OVER", "PROJECTED_OVER"]
    txn_ids: list[uuid.UUID] = Field(default_factory=list)


class GoalIn(BaseModel):
    name: str
    target_paise: int
    current_paise: int = 0
    target_date: date
    priority: int = 0
    monthly_contribution_paise: int = 0


class GoalProjectionOut(BaseModel):
    goal_id: uuid.UUID | str
    name: str
    target_paise: int
    current_paise: int
    shortfall_paise: int
    target_date: date
    months_remaining: int
    required_monthly_paise: int
    allocated_monthly_paise: int
    projected_eta: date | None = None
    months_delta: int
    verdict: Literal["ON_TRACK", "BEHIND", "AHEAD", "UNREACHABLE"]


# --- Simulation -------------------------------------------------------------


class OneOffIn(BaseModel):
    amount_paise: int
    on_date: date
    category_slug: str = "uncategorised"


class ScenarioIn(BaseModel):
    cancel_series: list[str] = Field(default_factory=list)
    category_pct_change: dict[str, float] = Field(default_factory=dict)
    one_off: list[OneOffIn] = Field(default_factory=list)


class GoalDiffOut(BaseModel):
    goal_id: uuid.UUID | str
    name: str
    eta_before: date | None = None
    eta_after: date | None = None
    months_delta: int


class SimulationOut(BaseModel):
    goals: list[GoalDiffOut] = Field(default_factory=list)
    monthly_surplus_before_paise: int
    monthly_surplus_after_paise: int
    monthly_surplus_delta_paise: int
    safe_daily_before_paise: int
    safe_daily_after_paise: int
    safe_daily_delta_paise: int
    cancelled_monthly_paise: int
    #: One paragraph written by the agent around figures the engine produced.
    narration: str | None = None


# --- Agent ------------------------------------------------------------------


class AskIn(BaseModel):
    question: str
    thread_id: uuid.UUID | None = None


class AskOut(BaseModel):
    thread_id: uuid.UUID
    answer: str
    citations: list[CitationOut] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    #: True when the advice-boundary guardrail replaced the answer.
    declined: bool = False


# --- Privacy ----------------------------------------------------------------


class ConsentArtefactOut(BaseModel):
    purpose: str
    data_types: list[str]
    processing: list[str]
    third_parties: list[str]
    retention_days: int
    frequency: str
    revocation: str
    version: int


class ConsentOut(ORMModel):
    id: uuid.UUID
    purpose: str
    data_types: list[str]
    retention_days: int
    granted_at: datetime
    revoked_at: datetime | None = None
    artefact: dict[str, Any] = Field(default_factory=dict)
    version: int


class AiDisclosureOut(ORMModel):
    id: uuid.UUID
    at: datetime
    purpose: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    #: Field NAMES only. A value here would be the bug DESIGN.md 12.1 forbids.
    field_names: list[str]
    redaction_count: int
    redaction_types: list[str]


class LeakScoreOut(BaseModel):
    """DESIGN.md 10.1. Colour and label, never colour alone (section 11.3)."""

    score: int = Field(ge=0, le=100)
    label: Literal["Healthy", "Watch", "Leaking", "Critical"]
    deductions: list[dict[str, Any]] = Field(default_factory=list)


class HealthOut(BaseModel):
    status: Literal["ok"]
