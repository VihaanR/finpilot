# FinPilot progress ledger

Repo: `V:\Projects\FinPilot` — https://github.com/VihaanR/finpilot (public)
Design: `DESIGN.md` · Tasks: `BUILD_TASKS.md` · Human steps: `USER.md`
Session: 19–20 Sep 2026 — built T01, T02 (authored, not applied), T03 and T06
from a bare repo of planning docs; found and fixed three real defects in the
recurrence/anomaly engine by running it against the generated seed data;
switched the runtime LLM provider from Anthropic to Google Gemini (free tier);
then built **T04 ingestion**, **T05 tier-1 categorisation**, an **offline
SQLite store** standing in for the unprovisioned Supabase, and the **full API
route layer** on top of it. Frontend (T08–T11) is next and not yet started.

## Verified state

Every line was run and observed in this session, from the repo root.

**Repository**

- `git rev-list --count HEAD` → **5 commits**, HEAD `1833ade`.
- Working tree is **dirty**: T04/T05/store/routes are written but **not yet
  committed**. `git status --short` shows 2 modified and 23 untracked paths.

**Tests and services**

- `pytest services/api/tests/` → **245 passed** in 1.94s (200 engine/seed +
  45 new ingestion tests). Zero failures, zero skips.
- `GET /health` on a live uvicorn → `{"status":"ok"}`, HTTP 200.
- `cd apps/web && npm run build` → "Compiled successfully", **8/8 static
  pages**, no type errors, from a cleaned `.next`.
- `import app.models` → **14** SQLAlchemy tables, **31** Pydantic schemas.

**Frontend, checked in a real browser**

Run against `next start` (the production build) with the API live, driven by
Playwright + Chromium.

- **axe-core: 0 violations.** Seven routes (`/`, `/radar`, `/goals`,
  `/transactions`, `/upload`, `/vault`, `/accessibility`) × both themes = 14
  scans, tags `wcag2a wcag2aa wcag21a wcag21aa`.
- **0 console errors and 0 page errors** across all seven routes, both themes.
- First Tab stop on every page is **"Skip to main content"**.
- At a 640px viewport (a 1280px screen at 200% zoom) **no route scrolls
  horizontally**.
- Citation drawer: opens with the right rows, Escape closes it, and focus
  returns to the element that opened it — all three verified by assertion, not
  by eye.
- Acknowledging a series returns "no longer counts as a silent mandate";
  overriding a category returns "Learned — 10 past transactions updated";
  the simulator moves both goal ETAs; revoking a consent scope updates the
  vault. Each driven through the real UI against the real API.

**Ingestion and store (new)**

- `demo.load(reset=True)` pushes all three seed CSVs through the real
  `ingest()` pipeline → **936 inserted / 0 duplicates**.
- Immediately re-running it → **0 inserted / 936 duplicates**. This is the
  critical T04 acceptance criterion and it is met by the `dedupe_key` UNIQUE
  constraint, not by an application-level check.
- Tier-1 categorisation over those 936 rows → **97.2% confident**, **2.8%
  uncategorised**. T05 requires ≥70% and <5% respectively.
- Merchant dictionary → **330 distinct merchants**, **694 patterns**
  (exact + VPA), every entry carrying a `service_type` for duplicate detection.
- `app.models.taxonomy` parses the migration file → **42 categories**,
  5 groups. The taxonomy is read from the SQL, never re-typed.
- Engine over the ingested (not seed-ground-truth) ledger → **34 series**,
  **28 anomalies** (19 `silent_mandate`, 4 `category_spike`, 3
  `duplicate_charge`, 1 `price_hike`, 1 `new_large_merchant`), Leak Score
  **22 / poor**. The anomaly count is 28 rather than the seed's 27 because
  categories are now re-derived by the tier-1 rules rather than read from the
  generator's ground truth, which yields one extra category spike.

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

- **T08 — frontend shell, design system, a11y foundation** (uncommitted).
  Green-and-beige glass in an "old money" register: warm paper ground, deep
  forest and brass, Fraunces for display and Inter for text. Contrast ratios
  are written next to each token in `globals.css`, light and dark both
  declared explicitly so the theme toggle wins in either direction, and
  `prefers-contrast: more` swaps the translucent surfaces for solid ones.
  `Money` renders the glyph for sighted readers and the magnitude in words for
  screen readers (Indian numbering: crore, lakh). `ChartWithTable` is the
  mandatory wrapper — every chart ships a real `<table>` alternative with
  `scope` on its headers. `CitationChip` + one app-level `TransactionDrawer`
  give every figure a route to its rows.
- **T09 — dashboard and upload** (uncommitted). Safe-to-Spend hero with the
  committed figure as a citation, Leak Score half-dial (score printed and band
  named, never colour alone), income-vs-spending and category charts, anomaly
  cards with dismiss, a filterable transactions table with inline category
  override, and an SSE upload flow with per-bank password hints.
- **T11 — radar, goals, vault** (uncommitted). The 30-day timeline grouped by
  week with the 7-day banner; all six badges as keyboard-operable buttons that
  reveal the rule as real text rather than a hover-only tooltip; per-series
  Revoke Kit with copyable steps and email template. Goals with a What-If
  simulator (series toggles + category sliders carrying `aria-valuetext`).
  Vault with the consent artefact, a before/after redaction example, the
  storage inventory, and working export and typed-confirmation erase.
- **Three defects the browser pass caught that the build did not:** a month
  label rendering "Invalid Date" because the API returns `2026-09-01` and the
  formatter appended `-01` again; `titleCase` producing "Ai Processing" and
  "Emi Loan Repayment" for slugs carrying acronyms; and `titleCase` used in
  `transactions/page.tsx` without an import, which threw at runtime on a path
  `next build` type-checks but never executes. The last one is the argument
  for running the thing, not just compiling it.
- **A fourth, in the API:** `anomaly_key` was `type:series_key:period_start`,
  and a `category_spike` has no series key — so two spikes in the same month
  collided, and dismissing one would have dismissed both. The key now carries
  a digest of the transaction ids. Found by React complaining about duplicate
  keys in the console.
- **T04 — ingestion** (uncommitted). `normalize` (paise-exact money, channel
  classification, VPA extraction, structural merchant extraction), `dedupe`
  (sha256 over account + date + amount + narration, deduping within a batch as
  well as against the store), an adapter registry tried in descending
  confidence (`generic_csv`, `hdfc_pdf`, `icici_pdf`, `llm_fallback`), PDF
  decryption with per-bank password hints, and a generator-based `pipeline.run`
  that streams stage events for SSE. Merchant extraction was checked against
  the seed's own ground truth: **931 of 936** exact matches.
- **T05 tier-1 — categorisation** (uncommitted). A 330-merchant dictionary plus
  structural rules (salary, EMIs, rent, ATM, interest, self-transfer, bank
  charges, SIPs, insurance, refunds) and a channel fallback, in that
  precedence. Tier-2 (`llm_classify`) is written and declines cleanly with no
  API key, so the product stays on tier 1 rather than failing.
- **Offline store + API routes** (uncommitted). Raw-SQL SQLite mirroring the
  Postgres migration, deliberately *not* SQLAlchemy so the production
  Postgres-typed models stay untouched. On top of it: `/api/dashboard`,
  `/api/transactions` (+ tier-3 category override that rewrites past rows),
  `/api/ingest` (SSE) and `/api/ingest/sync`, `/api/radar` (+ acknowledge),
  `/api/goals`, `/api/simulate`, `/api/vault` (+ consent, export, erase), and
  `/api/demo/reset`. Startup seeds the demo ledger if the store is empty.
- **Three real view-layer defects found by running it, not by reading it:**
  1. Liquid balance was netting the credit card's outstanding against savings.
     A card balance is a liability, not cash; excluded, and surfaced separately
     as `card_outstanding_paise`.
  2. The `DORMANT` badge fired on 17 of 34 series, because rent, EMIs and SIPs
     are *by definition* auto-debits with no side activity. Now restricted to
     subscriptions, where "you forgot about this" is a meaningful claim.
  3. Leak Score deductions were uncapped, so ~20 unacknowledged silent mandates
     alone drove every realistic score to 0. Per-reason caps added; the seed
     now scores 22, which leaves headroom to improve as the user acts.
- **Two adapter bugs found by the new tests** (both genuine, both in source):
  `_find`'s substring fallback let the two-letter candidate `cr` match inside
  `description`, mapping the narration column as the credit column; and the
  money regex's `\d{1,3}(?:,\d{2,3})*` branch chopped an ungrouped `110000.00`
  into `110` and `000.00`, handing the balance column a zero. Fixed by matching
  header candidates on word boundaries and requiring the grouped branch to
  actually contain a comma.
- **Not bugs, checked and left alone.** Safe-to-Spend's low committed figure
  (₹3,149) is correct: DESIGN.md §8.3 defines committed as obligations due
  *strictly before* the next income date, and the as-of date is 13 days out
  with most monthly mandates already fired. Both goals reading UNREACHABLE is
  also correct — the seed's recent months genuinely run a deficit, and feeding
  `goals.project()` an explicit positive surplus reproduces
  `seed/expected.json`'s verdicts exactly.
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

**Code blockers:** none. T04 and T05 tier-1 are done and were built entirely
offline; the SQLite store substitutes for Supabase so the frontend has real
data to render. T08–T11 are fully startable against the live API.

**The SQLite substitution, stated plainly.** `app/store/db.py` is a stand-in,
not the production path. It mirrors the migration's shape in raw SQL and
carries no RLS, no `user_id` scoping and no pgvector. When a Supabase project
exists, the routes swap their store dependency; the engine and the views layer
are unaffected because neither knows how rows are fetched.

**Tooling note:** the `agy` delegation path produced zero files on its one
dispatch (5-minute print timeout). Dropped after one attempt per the
orchestrator fail-fast rule; everything since has been implemented directly.

## Still not done

- **T05 tier-2** — the LLM batch classifier is written but has never run; it
  needs the Gemini key. Tier 1 covers 97.2%, so this is a refinement, not a
  dependency.
- **T07** agent layer — 11 tools, tool-use loop, prompts, guardrails. The
  redaction module (`app/privacy/redact.py`, Luhn + Verhoeff checksums) is
  built and unit-tested; the rest of T07 needs the key.
- **T10** chat with citations — the only frontend route still missing, and the
  only one that needs the Gemini key. The citation plumbing it depends on
  (`CitationChip`, `TransactionDrawer`) is already built and working.
- **T08 leftovers** — Supabase auth pages (no project exists) and an automated
  axe run wired into CI rather than a one-off script.
- **T12** deploy checkpoint — **now the most valuable remaining task.** Every
  P0 route it would deploy exists and works.
- **T13** Budget Guard extension, **T14** n8n workflows (both P1).
- **T15** evals + axe-core, **T16** video + submission.
- **Nothing since `1833ade` is committed.** The whole ingestion, store and
  route layer is working-tree only.

## Unverified figures

- **All Postgres SQL is unexecuted.** Syntax, enum creation, the RLS policy
  loop and the category seed are reviewed but never run *against Postgres*.
  Treat "42 rows" as a count of literals in the migration file. The SQLite
  store exercises an equivalent shape, which is evidence the model is coherent
  but not that the migration applies.
- **The PDF adapters have never seen a real bank PDF.** They are exercised
  against constructed line layouts only. DESIGN.md §6.1 already scopes them as
  best-effort with a fallback, and `detect()` is deliberately conservative, but
  "HDFC statements parse" is not a claim this repo can currently make.
- **No screen reader has been run.** `Money`'s spoken label was verified by
  reading the rendered DOM, not by listening to NVDA or TalkBack. axe-core
  finding nothing is a floor, not a ceiling — it cannot judge whether a label
  is *comprehensible*.
- **The frontend has only been seen at two viewports** (1440×1100 and
  640×400). No real phone, no real tablet.
- **The API ran with `ALLOWED_ORIGINS` widened** for the browser pass, since
  the default only admits `localhost:3000`. That is a test-harness
  accommodation, not a product change.
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
