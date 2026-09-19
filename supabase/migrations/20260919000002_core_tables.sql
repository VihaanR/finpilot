-- FinPilot schema, part 2: tables.
-- Implements DESIGN.md section 5.2.
--
-- Invariant 1 (DESIGN.md 5.1): money is BIGINT paise. Every currency column
-- below is BIGINT. The only REAL columns in this file are confidences and
-- day-gap statistics, which are not money.
--
-- Invariant 2: ingestion is idempotent, enforced by the UNIQUE constraint on
-- transactions.dedupe_key.

-- --- Identity ---------------------------------------------------------------

create table if not exists accounts (
  id                    uuid primary key default gen_random_uuid(),
  user_id               uuid not null references auth.users(id) on delete cascade,
  bank_code             text not null,
  account_type          account_type not null default 'SAVINGS',
  display_name          text not null,
  last4                 text,
  opening_balance_paise bigint not null default 0,
  current_balance_paise bigint not null default 0,
  balance_as_of         date,
  created_at            timestamptz not null default now()
);

-- --- Ingestion --------------------------------------------------------------

create table if not exists documents (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users(id) on delete cascade,
  kind           document_kind not null default 'STATEMENT',
  filename       text not null,
  storage_path   text,
  sha256         text,
  mime           text,
  status         document_status not null default 'PENDING',
  parser_name    text,
  parser_version text,
  -- Surfaced in the UI so the product never claims universal bank coverage
  -- (DESIGN.md 6.1, "honest scoping note").
  parser_confidence real,
  rows_extracted int not null default 0,
  error          text,
  created_at     timestamptz not null default now(),
  parsed_at      timestamptz
);

-- --- Enrichment -------------------------------------------------------------

create table if not exists categories (
  id         uuid primary key default gen_random_uuid(),
  parent_id  uuid references categories(id) on delete cascade,
  name       text not null,
  slug       text not null unique,
  icon       text,
  is_income  boolean not null default false,
  sort_order int not null default 0
);

create table if not exists merchant_rules (
  id          uuid primary key default gen_random_uuid(),
  -- NULL user_id means a GLOBAL rule shared across the deployment; the tier-2
  -- classification cache writes here (DESIGN.md section 7, tier 2).
  user_id     uuid references auth.users(id) on delete cascade,
  pattern     text not null,
  match_type  match_type not null default 'CONTAINS',
  merchant    text not null,
  category_id uuid references categories(id) on delete set null,
  -- User overrides write priority 1000 so they beat every built-in rule.
  priority    int not null default 100,
  scope       rule_scope not null default 'GLOBAL',
  created_at  timestamptz not null default now()
);

-- --- Ledger -----------------------------------------------------------------

create table if not exists transactions (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references auth.users(id) on delete cascade,
  account_id          uuid references accounts(id) on delete cascade,
  document_id         uuid references documents(id) on delete set null,
  txn_date            date not null,
  value_date          date,
  amount_paise        bigint not null check (amount_paise >= 0),
  direction           txn_direction not null,
  raw_narration       text not null,
  normalized_merchant text,
  counterparty_vpa    text,
  channel             txn_channel not null default 'OTHER',
  balance_paise       bigint,
  category_id         uuid references categories(id) on delete set null,
  category_source     category_source,
  category_confidence real,
  recurring_series_id uuid,
  -- sha256(account_id || txn_date || amount_paise || normalize(raw_narration))
  dedupe_key          text not null unique,
  created_at          timestamptz not null default now()
);

-- --- Engine outputs ---------------------------------------------------------

create table if not exists recurring_series (
  id                    uuid primary key default gen_random_uuid(),
  user_id               uuid not null references auth.users(id) on delete cascade,
  normalized_merchant   text not null,
  category_id           uuid references categories(id) on delete set null,
  direction             txn_direction not null default 'DEBIT',
  cadence               cadence not null,
  median_amount_paise   bigint not null,
  amount_tolerance_paise bigint not null default 0,
  median_gap_days       real,
  gap_mad               real,
  occurrence_count      int not null default 0,
  first_seen            date,
  last_seen             date,
  next_expected_date    date,
  confidence            real,
  mandate_channel       mandate_channel not null default 'UNKNOWN',
  afa_band              afa_band not null default 'REQUIRES_AFA',
  status                series_status not null default 'ACTIVE',
  -- Set when the user presses "I know about this", which clears the
  -- silent_mandate anomaly (DESIGN.md section 10.1).
  acknowledged_at       timestamptz,
  price_history         jsonb not null default '[]'::jsonb,
  series_key            text,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

alter table transactions
  drop constraint if exists transactions_recurring_series_id_fkey;
alter table transactions
  add constraint transactions_recurring_series_id_fkey
  foreign key (recurring_series_id)
  references recurring_series(id) on delete set null;

create table if not exists anomalies (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid not null references auth.users(id) on delete cascade,
  type         text not null,
  severity     anomaly_severity not null default 'MEDIUM',
  period_start date,
  period_end   date,
  txn_ids      uuid[] not null default '{}',
  series_id    uuid references recurring_series(id) on delete cascade,
  metric       jsonb not null default '{}'::jsonb,
  explanation  text not null,
  detected_at  timestamptz not null default now(),
  dismissed_at timestamptz
);

create table if not exists budgets (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  category_id uuid not null references categories(id) on delete cascade,
  period      budget_period not null default 'MONTHLY',
  limit_paise bigint not null,
  starts_on   date not null default current_date,
  created_at  timestamptz not null default now(),
  unique (user_id, category_id, period, starts_on)
);

create table if not exists goals (
  id                         uuid primary key default gen_random_uuid(),
  user_id                    uuid not null references auth.users(id) on delete cascade,
  name                       text not null,
  target_paise               bigint not null,
  current_paise              bigint not null default 0,
  target_date                date not null,
  priority                   int not null default 0,
  monthly_contribution_paise bigint not null default 0,
  created_at                 timestamptz not null default now()
);

-- --- Privacy (DPDP) ---------------------------------------------------------

create table if not exists consents (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references auth.users(id) on delete cascade,
  purpose        text not null,
  data_types     text[] not null default '{}',
  retention_days int not null default 90,
  frequency      text,
  granted_at     timestamptz not null default now(),
  revoked_at     timestamptz,
  -- Modelled on the Account Aggregator consent artefact (DESIGN.md R3).
  artefact       jsonb not null default '{}'::jsonb,
  version        int not null default 1
);

-- One row per LLM call. Records which FIELDS were sent, never their values
-- (DESIGN.md section 12.1).
create table if not exists ai_disclosures (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null references auth.users(id) on delete cascade,
  at                timestamptz not null default now(),
  purpose           text not null,
  model             text not null,
  prompt_tokens     int not null default 0,
  completion_tokens int not null default 0,
  field_names       text[] not null default '{}',
  redaction_count   int not null default 0,
  redaction_types   text[] not null default '{}',
  request_hash      text,
  response_hash     text
);

-- --- Conversation -----------------------------------------------------------

create table if not exists chat_threads (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users(id) on delete cascade,
  title      text,
  created_at timestamptz not null default now()
);

create table if not exists chat_messages (
  id         uuid primary key default gen_random_uuid(),
  thread_id  uuid not null references chat_threads(id) on delete cascade,
  user_id    uuid not null references auth.users(id) on delete cascade,
  role       text not null,
  content    text not null default '',
  tool_calls jsonb not null default '[]'::jsonb,
  -- [{label, value_paise, txn_ids[]}] - DESIGN.md section 9.3
  citations  jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

-- --- RAG over bills and receipts --------------------------------------------

create table if not exists document_chunks (
  id          uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  chunk_text  text not null,
  -- gemini-embedding-2 truncated to 768 dims via MRL (DESIGN.md 5.2, 9.1).
  embedding   vector(768)
);
