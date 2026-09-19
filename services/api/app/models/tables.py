"""SQLAlchemy models mirroring supabase/migrations/.

These are the persistence shapes. The analytics engine does not import them:
it takes the frozen dataclasses in `app.engine.types` instead, which is what
keeps it unit-testable without a database (DESIGN.md section 4.2).

Money columns are BigInteger paise without exception (DESIGN.md 5.1).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    BigInteger,
    Float,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    bank_code: Mapped[str] = mapped_column(Text, nullable=False)
    account_type: Mapped[str] = mapped_column(Text, nullable=False, default="SAVINGS")
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    last4: Mapped[str | None] = mapped_column(Text)
    opening_balance_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    current_balance_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    balance_as_of: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False, default="STATEMENT")
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(Text)
    mime: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="PENDING")
    parser_name: Mapped[str | None] = mapped_column(Text)
    parser_version: Mapped[str | None] = mapped_column(Text)
    parser_confidence: Mapped[float | None] = mapped_column(Float)
    rows_extracted: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = _pk()
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    icon: Mapped[str | None] = mapped_column(Text)
    is_income: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class MerchantRule(Base):
    __tablename__ = "merchant_rules"

    id: Mapped[uuid.UUID] = _pk()
    #: NULL for GLOBAL rules, including the tier-2 classification cache.
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    match_type: Mapped[str] = mapped_column(Text, nullable=False, default="CONTAINS")
    merchant: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL")
    )
    priority: Mapped[int] = mapped_column(Integer, default=100)
    scope: Mapped[str] = mapped_column(Text, nullable=False, default="GLOBAL")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        # DESIGN.md 5.1 invariant 2: re-uploading an overlapping statement
        # must insert nothing new.
        UniqueConstraint("dedupe_key", name="transactions_dedupe_key_key"),
        CheckConstraint("amount_paise >= 0", name="transactions_amount_nonneg"),
        Index("idx_transactions_user_date", "user_id", "txn_date"),
        Index("idx_transactions_user_merchant", "user_id", "normalized_merchant"),
        Index("idx_transactions_user_category", "user_id", "category_id"),
    )

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE")
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL")
    )
    txn_date: Mapped[date] = mapped_column(Date, nullable=False)
    value_date: Mapped[date | None] = mapped_column(Date)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    raw_narration: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_merchant: Mapped[str | None] = mapped_column(Text)
    counterparty_vpa: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(Text, nullable=False, default="OTHER")
    balance_paise: Mapped[int | None] = mapped_column(BigInteger)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL")
    )
    category_source: Mapped[str | None] = mapped_column(Text)
    category_confidence: Mapped[float | None] = mapped_column(Float)
    recurring_series_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    dedupe_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    account: Mapped["Account | None"] = relationship(back_populates="transactions")


class RecurringSeries(Base):
    __tablename__ = "recurring_series"
    __table_args__ = (
        Index("idx_recurring_series_user_next_expected", "user_id", "next_expected_date"),
    )

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    normalized_merchant: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL")
    )
    direction: Mapped[str] = mapped_column(Text, nullable=False, default="DEBIT")
    cadence: Mapped[str] = mapped_column(Text, nullable=False)
    median_amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_tolerance_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    median_gap_days: Mapped[float | None] = mapped_column(Float)
    gap_mad: Mapped[float | None] = mapped_column(Float)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[date | None] = mapped_column(Date)
    last_seen: Mapped[date | None] = mapped_column(Date)
    next_expected_date: Mapped[date | None] = mapped_column(Date)
    confidence: Mapped[float | None] = mapped_column(Float)
    mandate_channel: Mapped[str] = mapped_column(Text, default="UNKNOWN")
    afa_band: Mapped[str] = mapped_column(Text, default="REQUIRES_AFA")
    status: Mapped[str] = mapped_column(Text, default="ACTIVE")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price_history: Mapped[list] = mapped_column(JSONB, default=list)
    series_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False, default="MEDIUM")
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    txn_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recurring_series.id", ondelete="CASCADE")
    )
    metric: Mapped[dict] = mapped_column(JSONB, default=dict)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE")
    )
    period: Mapped[str] = mapped_column(Text, nullable=False, default="MONTHLY")
    limit_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    target_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    monthly_contribution_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    data_types: Mapped[list] = mapped_column(ARRAY(String), default=list)
    retention_days: Mapped[int] = mapped_column(Integer, default=90)
    frequency: Mapped[str | None] = mapped_column(Text)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    artefact: Mapped[dict] = mapped_column(JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)


class AiDisclosure(Base):
    """One row per LLM call. Field NAMES only, never values (DESIGN.md 12.1)."""

    __tablename__ = "ai_disclosures"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    field_names: Mapped[list] = mapped_column(ARRAY(String), default=list)
    redaction_count: Mapped[int] = mapped_column(Integer, default=0)
    redaction_types: Mapped[list] = mapped_column(ARRAY(String), default=list)
    request_hash: Mapped[str | None] = mapped_column(Text)
    response_hash: Mapped[str | None] = mapped_column(Text)


class ChatThread(Base):
    __tablename__ = "chat_threads"

    id: Mapped[uuid.UUID] = _pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = _pk()
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_threads.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    tool_calls: Mapped[list] = mapped_column(JSONB, default=list)
    citations: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = _pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    # pgvector column; declared as Text here so importing the models never
    # requires the pgvector Python bindings. Vector search runs through
    # Supabase RPC rather than the ORM.
    embedding: Mapped[str | None] = mapped_column(Text)
