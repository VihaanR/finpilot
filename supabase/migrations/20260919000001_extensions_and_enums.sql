-- FinPilot schema, part 1: extensions and enum types.
-- Implements DESIGN.md section 5.2.

-- pgvector backs semantic search over bill and receipt text (DESIGN.md 9.2,
-- tool `search_documents`). Supabase exposes it in the `extensions` schema.
create extension if not exists vector;
create extension if not exists pgcrypto;

-- --- Identity ---------------------------------------------------------------
do $$ begin
  create type account_type as enum ('SAVINGS', 'CURRENT', 'CREDIT_CARD');
exception when duplicate_object then null; end $$;

-- --- Ingestion --------------------------------------------------------------
do $$ begin
  create type document_kind as enum ('STATEMENT', 'BILL', 'RECEIPT');
exception when duplicate_object then null; end $$;

do $$ begin
  create type document_status as enum
    ('PENDING', 'PARSED', 'FAILED', 'NEEDS_PASSWORD');
exception when duplicate_object then null; end $$;

do $$ begin
  create type txn_direction as enum ('DEBIT', 'CREDIT');
exception when duplicate_object then null; end $$;

do $$ begin
  create type txn_channel as enum
    ('UPI', 'NEFT', 'IMPS', 'CARD', 'NACH', 'ACH', 'ATM', 'CASH', 'CHEQUE', 'OTHER');
exception when duplicate_object then null; end $$;

-- --- Enrichment -------------------------------------------------------------
do $$ begin
  create type category_source as enum ('RULE', 'LLM', 'USER');
exception when duplicate_object then null; end $$;

do $$ begin
  create type match_type as enum ('REGEX', 'CONTAINS', 'VPA');
exception when duplicate_object then null; end $$;

do $$ begin
  create type rule_scope as enum ('GLOBAL', 'USER');
exception when duplicate_object then null; end $$;

-- --- Engine outputs ---------------------------------------------------------
do $$ begin
  create type cadence as enum
    ('WEEKLY', 'FORTNIGHTLY', 'MONTHLY', 'QUARTERLY', 'HALF_YEARLY', 'ANNUAL');
exception when duplicate_object then null; end $$;

do $$ begin
  create type mandate_channel as enum
    ('UPI_AUTOPAY', 'NACH', 'CARD_EMANDATE', 'SI', 'MANUAL', 'UNKNOWN');
exception when duplicate_object then null; end $$;

-- Derived from the RBI e-mandate framework (DESIGN.md R1).
do $$ begin
  create type afa_band as enum ('SILENT', 'HIGH_LIMIT', 'REQUIRES_AFA');
exception when duplicate_object then null; end $$;

-- DESIGN.md section 5.2 lists ACTIVE|LAPSED|CANCELLED, but section 8.1
-- requires two-occurrence clusters to be surfaced with status PROBABLE.
-- PROBABLE is included so the engine can round-trip its own output.
do $$ begin
  create type series_status as enum
    ('ACTIVE', 'PROBABLE', 'LAPSED', 'CANCELLED');
exception when duplicate_object then null; end $$;

do $$ begin
  create type anomaly_severity as enum ('LOW', 'MEDIUM', 'HIGH');
exception when duplicate_object then null; end $$;

do $$ begin
  create type budget_period as enum ('MONTHLY');
exception when duplicate_object then null; end $$;
