# FinPilot progress ledger

Repo: `V:\Projects\FinPilot` — https://github.com/VihaanR/finpilot (public)
Design: `DESIGN.md` · Tasks: `BUILD_TASKS.md` · Human steps: `USER.md`
Session: 19 Sep 2026 — built T01, T02 (authored, not applied), T03 and T06 from
a bare repo of planning docs; found and fixed three real defects in the
recurrence/anomaly engine by running it against the generated seed data; then
switched the runtime LLM provider from Anthropic to Google Gemini (free tier).
Last refreshed after a full re-verification pass — no code changed since
`7772813`, but every claim below was re-run rather than carried forward.

## Verified state

Every line was run and observed in this session, from the repo root, against
commit `5e06750`.

**Repository**

- `git rev-list --count HEAD` → **5 commits**, HEAD `5e06750`.
- `git status --short` → empty; `git status -sb` → `main...origin/main` with no
  divergence. Local and remote both at `5e06750`, working tree clean.

**Tests and services**

- `pytest services/api/tests/` → **200 passed** in 0.36s.
- `GET /health` on a live uvicorn → `{"status":"ok"}`, HTTP 200.
- `cd apps/web && npm run build` → "Compiled successfully", 5/5 static pages,
  no type errors.
- `import app.models` → **14** SQLAlchemy tables, **31** Pydantic schemas.

**Gemini provider swap**

- `import anthropic` → `ModuleNotFoundError`; the package is gone from the venv.
- `import google.genai` → **2.24.0**.
- `app.config` resolves `gemini-3.8-flash` (chat), `gemini-2.5-pro` (summary),
  `gemini-3.5-flash-lite` (classify), `gemini-embedding-2` at **768 dims**.
- `document_chunks.embedding` in the migration → `vector(768)`, matching
  `settings.embedding_dimensions`.

**Schema and engine invariants**

- Category taxonomy migration → **42 rows** (T02 requires > 40).
- Float-in-money scan over `supabase/migrations/*.sql` → 6 matches, all
  non-money: `parser_confidence`, `category_confidence`, `median_gap_days`,
  `gap_mad`, `confidence`, plus one comment line.
- Engine purity → **0** files under `app/engine/` import `google`, `anthropic`,
  `supabase`, `sqlalchemy` or `psycopg`.

**Seed dataset**

- `seed/generate.py --seed 42 --as-of 2026-09-19` run twice → identical md5 for
  all five outputs. **936 transactions**, 3 accounts, 14 months,
  `seed/expected.json` holding 34 ground-truth values.
- Engine over the seed → **34 recurring series** (23 ACTIVE, 4 PROBABLE,
  7 LAPSED), **9 of them subscriptions** (8 ACTIVE plus the annual Amazon Prime
  as PROBABLE); **27 anomalies** spanning all five DESIGN.md §8.2 types
  (19 `silent_mandate`, 3 `category_spike`, 3 `duplicate_charge`,
  1 `price_hike`, 1 `new_large_merchant`).

## Completed recently

- **T00** — `git init`, `.gitignore`, planning docs committed (`c5a8fed`).
- **T06 — analytics engine** (`5ced4f8`). DESIGN.md §8 as pure functions:
  `recurrence`, `anomaly`, `cashflow`, `budget`, `goals`, `simulate`, `stats`,
  plus `types.py` of frozen dataclasses. Two judgement calls DESIGN.md leaves
  open, both documented in code: `median_amount_paise` reports the *current*
  price level so Safe-to-Spend commits what will actually debit; surplus left
  over after planned contributions accelerates the highest-priority goal so
  freeing up money moves an ETA instead of vanishing.
- **T01 — scaffold** (`1899d7f`). Next.js 15.5.25 / React 19 / Tailwind v4 /
  Recharts / Supabase client / Playwright + axe-core. FastAPI with pinned
  `requirements.txt`. `render.yaml` and `vercel.json` per USER.md §8. Both
  `.env.example` files list every variable in DESIGN.md and USER.md §4, empty.
- **T02 — schema** (`1899d7f`). Four migrations: enums, 14 tables, indexes and
  RLS (`auth.uid() = user_id` on every user-scoped table), and the category
  taxonomy. Money is `BIGINT` paise throughout. SQLAlchemy + Pydantic mirrors.
- **T03 — seed generator** (`1899d7f`). 14 months of synthetic Indian
  statements in HDFC/ICICI/SBI narration shapes, containing every feature T03
  plants: salary with an appraisal bump, rent by NACH, two EMIs, seasonal
  electricity, 9 subscriptions (price hike, duplicate music pair, trial→paid,
  dormant), a festival category spike, a duplicate charge, a ₹42,000 new
  merchant, two goals, six budgets.
- **T06 detector hardening** (`1899d7f`) — the substantive find of the session.
  The first version reported ~200 recurring series on the seed, with Swiggy,
  Uber and DMart appearing as subscriptions. Three genuine defects:
  1. `gap_mad` is a *median* of deviations, so it ignores outliers: gaps of
     `[30,30,30,200,30,5]` give MAD 0 and pass. Now requires most gaps near
     the median, not just the median one.
  2. Any 3 of 200 transactions can look regular by chance. Added a dominance
     test — a series must account for ≥30% of that merchant's activity across
     its own span.
  3. Spikes compared an in-progress month against complete months, so on the
     19th every category read as a large fall.
  Also: price hikes no longer fire on credit series (a salary appraisal is not
  a price hike) or report a ₹1→₹199 trial as a 19,800% increase; spike severity
  now requires effect size, not just a significant z.
- **Runtime LLM switched to Google Gemini.** No code called Anthropic yet
  (T05/T07 unbuilt), so this was config, docs and one dependency. DESIGN.md §9.1
  now routes chat → `gemini-3.8-flash`, summary → `gemini-2.5-pro`, bulk
  classification and vision → `gemini-3.5-flash-lite`, embeddings →
  `gemini-embedding-2`; all free-tier eligible. `VECTOR(1024)` → `VECTOR(768)`
  (a Google-recommended MRL size; the migration had never been applied, so the
  change was free). `requirements.txt` swaps `anthropic` for `google-genai`
  and re-pins `pydantic` to 2.13.5, which that SDK requires. The consent
  artefact and `ai_disclosures` third-party now name Google, not Anthropic —
  that is a user-visible privacy claim and had to be accurate. BUILD_TASKS.md's
  `[O]`/`[S]`/`[H]` tags were deliberately left alone: they say which model
  *writes the code*, not what the product calls.
- **Doc hygiene** (`5e06750`). The ledger had carried four references forward
  unchecked after the Gemini switch — a stale HEAD hash, a stale commit count,
  `anthropic` in the engine-purity line, and "the Anthropic key" as T04's
  remaining dependency. Corrected; that is precisely the failure mode this
  file exists to prevent.
- **Docs** — BUILD_TASKS.md T06 and T11 corrected in place. "Exactly 9
  recurring series" was unsatisfiable alongside T03's required seed contents;
  annotated with the measured figures. `CLAUDE.md` and this file added.

## Blockers or ceiling

**External — needs a human, cannot be fixed by writing code:**

- **No Supabase project.** `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` /
  `DATABASE_URL` are unset. The migrations have **never been executed against
  any database**, so three T02 acceptance criteria are unmet: migrations apply
  cleanly, a duplicate `dedupe_key` raises a unique violation, and a query as
  user A returns zero rows of user B. See USER.md §2.
- **Docker Desktop daemon not running**, so a local Postgres+pgvector container
  was not available as a fallback for the above. Starting Docker Desktop would
  unblock migration testing without needing Supabase.
- **No Gemini API key.** Blocks T05 tier-2 categorisation and all of T07
  (agent tools, citations, guardrails, redaction). Free, no card, ~3 minutes at
  `aistudio.google.com/apikey` — see USER.md §1.
  Note: the owner holds a **Google AI Plus** consumer plan. That covers the
  Gemini *app*, not the API; API quota is per Cloud project and only billing
  lifts it to Tier 1. The build assumes free-tier limits (~10 RPM) throughout,
  which the tier-1 rules and the narration-hash cache are designed around.
- Later, in order: Telegram bot token (T14), Vercel + Render accounts (T12),
  n8n via Docker (T14).

**Code blockers:** none. T04 is fully startable — its critical criterion
(uploading the same file twice produces zero new rows) is verifiable offline
against the generated seed CSVs, and only the `llm_fallback` adapter needs the
Gemini key.

**Tooling note:** the `agy` delegation path produced zero files on its one
dispatch (5-minute print timeout). Dropped after one attempt per the
orchestrator fail-fast rule; everything since has been implemented directly.

## Still not done

- **T04** ingestion — PDF decryption, adapters, normalisation, dedupe,
  `POST /api/ingest` with SSE. Next task.
- **T05** categorisation — ~300-entry merchant dictionary, 3-tier rules.
  The dictionary should also populate `service_type`, which the engine already
  reads for duplicate-subscription detection.
- **T07** agent layer — 11 tools, tool-use loop, prompts, guardrails, redaction.
- **T08–T11** frontend — shell and a11y foundation, dashboard, chat, radar,
  simulator, vault. No route beyond the create-next-app placeholder exists yet.
- **T12** deploy checkpoint — the most important task in BUILD_TASKS.md.
- **T13** Budget Guard extension, **T14** n8n workflows (both P1).
- **T15** evals + axe-core, **T16** video + submission.
- No API route beyond `/health` is implemented.

## Unverified figures

- **All SQL is unexecuted.** Syntax, enum creation, the RLS policy loop and the
  category seed are reviewed but never run. Treat "42 rows" as a count of
  literals in the migration file, not of rows in a database.
- `render.yaml` and `vercel.json` have never been used for a deploy.
- **No Gemini API call has ever been made.** The model IDs, free-tier
  availability and embedding dimensionality come from Google's current docs
  (`ai.google.dev`), not from an exercised request. First real call happens at
  T05.
- The 34-series / 27-anomaly counts are specific to `--seed 42 --as-of
  2026-09-19`. They move with the as-of date, since the 14-month window slides.
- `MIN_CLUSTER_DOMINANCE = 0.30`, `MIN_GAP_CONSISTENCY = 0.75`,
  `MIN_SPIKE_RELATIVE_CHANGE = 0.30` and `PRICE_HIKE_MIN_CONFIDENCE = 0.7` were
  chosen to fit this seed dataset. They are reasonable and documented, but they
  are tuned against synthetic data, not validated against real statements.
