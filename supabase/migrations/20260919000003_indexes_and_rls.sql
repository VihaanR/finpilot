-- FinPilot schema, part 3: indexes and row-level security.
-- Implements DESIGN.md sections 5.2 and 12.2.

-- --- Indexes named in BUILD_TASKS.md T02 ------------------------------------

create index if not exists idx_transactions_user_date
  on transactions (user_id, txn_date);

create index if not exists idx_transactions_user_merchant
  on transactions (user_id, normalized_merchant);

create index if not exists idx_transactions_user_category
  on transactions (user_id, category_id);

create index if not exists idx_recurring_series_user_next_expected
  on recurring_series (user_id, next_expected_date);

-- --- Supporting indexes -----------------------------------------------------

create index if not exists idx_transactions_account on transactions (account_id);
create index if not exists idx_transactions_document on transactions (document_id);
create index if not exists idx_documents_user on documents (user_id, created_at desc);
create index if not exists idx_anomalies_user on anomalies (user_id, detected_at desc);
create index if not exists idx_budgets_user on budgets (user_id);
create index if not exists idx_goals_user on goals (user_id, priority);
create index if not exists idx_ai_disclosures_user on ai_disclosures (user_id, at desc);
create index if not exists idx_chat_messages_thread on chat_messages (thread_id, created_at);
create index if not exists idx_document_chunks_user on document_chunks (user_id);

-- The tier-2 classification cache is keyed by sha256(normalized_narration)
-- stored in `pattern`, so global lookups must be fast (DESIGN.md section 7).
create index if not exists idx_merchant_rules_lookup
  on merchant_rules (scope, priority desc, pattern);
create index if not exists idx_merchant_rules_user on merchant_rules (user_id);

-- --- Row-level security -----------------------------------------------------
-- DESIGN.md section 12.2: RLS on every user-scoped table, keyed to auth.uid().
-- The FastAPI service uses the service_role key, which bypasses RLS; these
-- policies protect the browser's anon-key access path.

alter table accounts         enable row level security;
alter table documents        enable row level security;
alter table transactions     enable row level security;
alter table merchant_rules   enable row level security;
alter table recurring_series enable row level security;
alter table anomalies        enable row level security;
alter table budgets          enable row level security;
alter table goals            enable row level security;
alter table consents         enable row level security;
alter table ai_disclosures   enable row level security;
alter table chat_threads     enable row level security;
alter table chat_messages    enable row level security;
alter table document_chunks  enable row level security;

do $$
declare
  t text;
begin
  foreach t in array array[
    'accounts', 'documents', 'transactions', 'recurring_series', 'anomalies',
    'budgets', 'goals', 'consents', 'ai_disclosures', 'chat_threads',
    'chat_messages', 'document_chunks'
  ]
  loop
    execute format('drop policy if exists %I on %I', t || '_owner', t);
    execute format(
      'create policy %I on %I for all
         using (auth.uid() = user_id)
         with check (auth.uid() = user_id)',
      t || '_owner', t
    );
  end loop;
end $$;

-- merchant_rules is the exception: GLOBAL rules have a NULL user_id and are
-- readable by everyone, while only the owner may touch a USER rule.
drop policy if exists merchant_rules_read on merchant_rules;
create policy merchant_rules_read on merchant_rules
  for select using (user_id is null or auth.uid() = user_id);

drop policy if exists merchant_rules_write on merchant_rules;
create policy merchant_rules_write on merchant_rules
  for insert with check (auth.uid() = user_id);

drop policy if exists merchant_rules_update on merchant_rules;
create policy merchant_rules_update on merchant_rules
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists merchant_rules_delete on merchant_rules;
create policy merchant_rules_delete on merchant_rules
  for delete using (auth.uid() = user_id);

-- The category taxonomy is reference data: readable by all, writable by none
-- through the anon key.
alter table categories enable row level security;
drop policy if exists categories_read on categories;
create policy categories_read on categories for select using (true);
