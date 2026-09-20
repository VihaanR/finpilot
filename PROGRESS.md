# FinPilot progress ledger

> **Time budget, set by the owner 20 Sep 2026: ~6 hours remaining as of the
> start of this session's second half.** Core product (T01–T12, T15) is done
> and live, chat is solid (the Gemini-quota wall is resolved — see the Groq
> switch below), and both optional P1 items (T13 extension, T14 n8n) are now
> built — code-complete and largely verified, with the remaining gaps being
> owner-side manual checks (a real Amazon/Flipkart cart for T13; Docker +
> a Telegram bot for T14 — see Completed recently for exactly what's left).
> Remaining budget is for those two checks and recording T16. If time runs
> short, **T16 (record + submit) wins over any partial P1 work** — a
> working, deployed, un-recorded product scores worse than a recorded one,
> per BUILD_TASKS.md's own scheduling rule. This ledger is updated after
> every change from here on, so re-read this file first if resuming
> mid-session.


Repo: `V:\Projects\FinPilot` — https://github.com/VihaanR/finpilot (public)
Design: `DESIGN.md` · Tasks: `BUILD_TASKS.md` · Human steps: `USER.md`
Session: 19–20 Sep 2026 — built T01–T06 from a bare repo of planning docs,
then **T04 ingestion**, **T05 tier-1**, an **offline SQLite store** standing in
for Supabase, the **full API route layer**, the **frontend** (T08, T09, T11),
and finally **T07 the agent layer**, **T10 chat with citations** and **T15 the
eval harness**, a **committed accessibility suite**, the **Supabase
migrations**, and **T12 deploy**. The owner supplied a Gemini key and a
Supabase project mid-session, which turned several long-standing "unverified"
claims into measured ones — and falsified two of them. **FinPilot is now live
in production** at https://finpilot-swart.vercel.app, backed by
https://finpilot-w4ki.onrender.com. A second half then switched chat and the
summary from Gemini to Groq after the free-tier quota ran out, and built
both P1 items — **T13 Budget Guard** and **T14 n8n workflows**. Everything is
committed and pushed to `origin/main`.

Scope decided with the owner: Gemini is for **recording a demo video**, not
live judging, so the free tier stands and billing was rejected. The Supabase
**store swap was deliberately not attempted** — the schema is applied, but the
API still reads SQLite, which self-seeds and is sufficient for a demo. Doing
that refactor on the last day would risk a working product.

## Verified state

Every line was run and observed in this session, from the repo root.

**Repository**

- `git rev-list --count HEAD` → **23 commits**, HEAD `04a4161`.
- Working tree is **clean**, and **pushed**: `git status -sb` shows no
  divergence from `origin/main`. That matters because Render and Vercel
  deploy *from GitHub* — nothing built in this session is live until pushed.
- Secret scan over every outgoing commit's diff: no keys, no `.env`, no
  `*.db`, and no Supabase project ref.

**Production — live end to end, both sides deployed and checked from outside**

- `https://finpilot-w4ki.onrender.com/health` → `{"status":"ok"}`.
- `/api/dashboard` on the deployed instance → `as_of 2026-09-19`, 3 accounts,
  leak score **22** — identical to local. **The SQLite store self-seeded on
  Render's blank ephemeral disk**, which is the mechanism the whole
  no-database deploy rests on, now proven in production rather than simulated.
- `/api/radar`, `/api/goals`, `/api/vault`, `/api/agent/suggestions` → all
  **200**, checked with the real `Origin: https://finpilot-swart.vercel.app`
  header and the CORS response header confirmed present on each, not just the
  status code (a 200 with no CORS header still fails silently in a browser).
- `https://finpilot-swart.vercel.app` loads **200** for an unauthenticated
  request — no Vercel SSO wall. (A sibling *preview* URl,
  `...-npsx2kd29-....vercel.app`, does 302 to `vercel.com/sso-api` for anyone
  without a Vercel session; that one must never go on the submission form.)
- `/api/agent/suggestions` → Gemini key present, AI consent granted, 4
  questions. (Checked via the endpoint that reports readiness *without*
  calling the model, to preserve quota for the video.)

**The CORS trap, and why it took three passes to actually close**

`ALLOWED_ORIGINS` started at the code default (`localhost:3000`) — reported
here as the T12 blocker. The owner set it in the Render dashboard, but to a
value with a **trailing slash**: `https://finpilot-swart.vercel.app/`. A
browser's `Origin` header never carries one, so `CORSMiddleware`'s exact
string match silently rejected every request — 200 from curl, no
`access-control-allow-origin` header, which a browser treats as a hard
failure with no server-side error to grep for. Fixed in code
(`allowed_origins_list` now `.rstrip("/")`s every entry) and covered by
`test_config.py`, so a future re-paste of the same kind of URL cannot
reintroduce it. Verified live after the redeploy settled: preflight and GET
both carry the header, all data routes return real data through the deployed
frontend's actual origin.

**The Render build failure, and what it actually was**

The first deploy died on `psycopg-binary==3.2.3`, "no matching distribution",
which reads as a bad pin. It was not: the wheel names said `cp314`. Render
built on **Python 3.14**, for which psycopg-binary ships no wheels and has no
sdist; `numpy==2.2.1` would have failed next. `render.yaml` does set
`PYTHON_VERSION`, but **that file applies only to Blueprint deploys** and the
service was created by hand in the dashboard, so it was never read.
`services/api/.python-version` (3.11.13, the interpreter every pin is tested
against) fixed it — the successful build shows `cp311` wheels throughout.

**Tests and services**

- `pytest services/api/tests/ evals/` → **326 passed**, zero failures. 25 live
  eval cases skip by default (they need model quota; see below).
- `cd apps/web && npm run build` → 12/12 static pages, no type errors.
- `npx playwright test --grep-invert @quota` → **30/30 pass** against the
  production build with the API live: 8 routes × 2 themes of axe (0
  violations), skip-link first on every route, no horizontal scroll at a 640px
  viewport, and 11 Budget Guard specs (cart-total parser, 24-hour cooldown,
  interstitial a11y contract). The live chat spec is the `@quota` one excluded
  here; with it, 31/31 —
  streamed answer, `aria-busy` toggling, citation chip opening the drawer,
  Escape returning focus to the chip, 0 axe violations on the answered page.
- `POST /api/demo/reset` → ledger returns to **936** transactions, clearing a
  test upload. That is a T12 acceptance criterion, met early.
- `GET /health` on a live uvicorn → `{"status":"ok"}`, HTTP 200.
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

**Gemini, now exercised against a real key (was entirely unverified)**

- A live `generate_content` call returns text; a live `embed_content` returns
  **768 dims**, matching `document_chunks.embedding vector(768)`.
- The agent answered *"Where did I spend the most last month?"* with
  **"Shopping in September 2026, totaling ₹48,433 [c1]"** — 6/6 figures cited,
  zero uncited, zero invented citation ids, and ₹48,433 is exactly the
  4,843,300 paise independently re-summed from the store.
- **Two configured models were wrong, and only a real key could show it.**
  `gemini-2.5-pro` (the summary model) returns **404, "no longer available to
  new users"**, and every Gemini *Pro* model reports **`limit: 0`/day** on the
  free tier. Chat and summary now run on `gemini-3.5-flash`.
- **Free-tier quota is ~20 requests/day per model**, alongside 5/min. Every doc
  in the repo previously claimed ~10 RPM with no daily cap. A chat question
  costs 2–3 calls, so one model id is worth roughly **8 questions a day**.
  Corrected in DESIGN.md §9.1, USER.md §1, CLAUDE.md and BUILD_TASKS.md.

**Supabase, now migrated (was entirely unverified)**

- `DATABASE_URL` connects: **PostgreSQL 17.6**, `pgvector` **enabled**.
- All four migrations **applied cleanly**, one transaction per file, over
  `DATABASE_URL` with psycopg. **14 public tables**, matching DESIGN.md §5.2.
- `select count(*) from categories` → **42** (T02 requires > 40).
- **RLS is on for all 14 tables**, and enforced, not merely enabled: inserting
  one transaction for each of two auth users and then querying as each of them
  (`set local role authenticated` + a `request.jwt.claims` sub) returns
  `own=1, other=0, visible_total=1`. The unfiltered `count(*)` seeing 1 of 2
  rows is the proof the policy filtered, rather than a `WHERE` clause doing it.
- A duplicate `dedupe_key` raises `UniqueViolation` on
  `transactions_dedupe_key_key`.
- All 13 `user_id` columns carry a real FK to `auth.users` with
  `ON DELETE CASCADE`. Worth recording because `information_schema` reports
  them as *absent* — it hides constraints referencing a table you do not own,
  and `auth.users` belongs to `supabase_auth_admin`. `pg_constraint` is the
  honest source; the first check here was a false negative.

**That closes the three open T02 acceptance criteria.** Test rows were deleted
afterwards; the schema is empty of data.

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

- **T13 Budget Guard extension and T14 n8n workflows, both built.** Neither
  was blocking — Docker still isn't running locally, so T14's own build
  process (build in a running n8n, then export) couldn't happen — but both
  are now in a real, mostly-verified state rather than untouched.

  **T13** (`extension/`) — MV3, no build step, loads unpacked directly.
  Deliberately simplified from DESIGN.md §10.5: the extension fetches
  `/api/dashboard` directly rather than the spec's signed-snapshot handshake
  via `externally_connectable`, because this API has no auth to make that
  handshake meaningful. Verified with a Playwright-driven smoke test against
  the actual loaded extension (zero manifest/console errors, background
  service worker fetches real production data — `discretionary_paise`
  parsed correctly through to the popup) and against fixture pages in
  `extension/test-fixtures/` for the parts that need DOM content a live
  retailer provides: the primary-selector parser, the ₹-numeric fallback
  heuristic (correctly picks a ₹9,999 order total over a ₹40 delivery fee
  when every known selector is deliberately absent), and the interstitial's
  full accessibility contract — `role="alertdialog"`, initial focus lands on
  a button, Tab is trapped between the three actions, Escape closes and
  returns focus to whatever had it. **Never tested against a real
  `amazon.in` or `flipkart.com` cart** — that's the one thing left needing a
  human account, flagged in `extension/README.md` and USER.md §7.

  **T14** (`n8n/finpilot-workflows.json`) — four workflows (Ingest, Daily
  brief, Mandate alert, Monthly summary), hand-authored via
  `n8n/generate_workflows.py` against n8n's node schema rather than built in
  n8n's own editor, since Docker wasn't available to run n8n locally. Points
  at the API routes that actually exist (`/api/ingest/sync`,
  `/api/agent/ask/sync`, `/api/dashboard`, `/api/radar`,
  `/api/summary/generate`) rather than the `/api/brief`/`/api/obligations`
  DESIGN.md §10.6 assumed and this session never built. Structurally
  verified — valid JSON, every node reachable from exactly one trigger with
  no orphans, secret scan clean — but **never imported into a running n8n or
  exercised against a live Telegram bot.** `n8n/README.md` is explicit about
  that gap and has the exact steps to close it once Docker and a bot token
  exist.

  `DESIGN.md` §10.5/§10.6 and `BUILD_TASKS.md`'s T13/T14 sections both carry
  correction notes recording these deviations and the verification state,
  matching how every other divergence from the original design in this repo
  has been handled.

- **Chat and the monthly summary switched from Gemini to Groq, live and
  verified in production.** Gemini's chat quota (20 requests/day) ran out
  during this session's own testing, with no headroom left for recording —
  Groq's free tier is rate-limited per minute rather than gated by a hard
  daily wall, which is what actually fixes that. `agent/loop.py`'s
  hand-driven tool-calling loop now speaks Groq's OpenAI-compatible chat
  completions API instead of the Gemini SDK; citations, the guardrail order,
  and the redaction seam (`llm.py`) are all unchanged — only the transport
  and the model id moved. Gemini stays for bulk categorisation, the PDF
  LLM-fallback adapter, and embeddings, none of which shared the problem.

  Three real defects surfaced getting this live, in order:
  1. **`llama-3.3-70b-versatile` 404'd in production** — "does not exist or
     you do not have access to it" — despite being listed as live on Groq's
     own docs page. Read as an account-tier restriction, not a real
     deprecation.
  2. **The fallback, `llama-3.1-8b-instant`, 404'd identically.** Since two
     different valid model ids failed the same way, the real signal was the
     account, not the model choice. Checking the account's own Playground
     model dropdown (rather than trusting Groq's docs) gave the actual
     available set; `openai/gpt-oss-20b` — documented tool-calling capable —
     was in it and is what's live now.
  3. **"Where did I spend the most last month?"** — one of the four canned
     demo questions — failed roughly half the time with "I don't have data
     for that period", alternating with a correct, fully-cited answer on an
     identical repeat call. Cause: the system prompt never stated the
     ledger's current date, so resolving "last month" into a
     `period=YYYY-MM` tool argument was genuinely ambiguous, and this
     smaller model guessed wrong noticeably more often than the ones this
     ran on before. Fixed by grounding the prompt in `snapshot.as_of`
     (`agent/prompts.py`'s `system_prompt(as_of)`); confirmed 3/3 correct,
     fully cited, on repeat testing against production after the fix.

  `DESIGN.md` §9.1, `USER.md` §1/§1b, `CLAUDE.md`'s quota gotcha, the vault
  consent artefact, and the eval harness's quota-skip message were all
  updated to match — they were written when Gemini served chat too.
  `pytest services/api/tests/ evals/` stayed green (326 passed) through every
  step of this.

- **T12 deploy is done — live in production, verified from outside.**
  `https://finpilot-w4ki.onrender.com` (API) and
  `https://finpilot-swart.vercel.app` (frontend). Fixed a real build failure
  along the way: the first Render deploy died on `psycopg-binary`, which
  looked like a bad pin but was actually Python 3.14 (Render's default,
  since `render.yaml`'s `PYTHON_VERSION` only applies to Blueprint deploys, and
  this service was created by hand). `services/api/.python-version` pins
  3.11.13 and fixed it — confirmed by `cp311` wheels in the successful build
  log. Then closed a CORS trap: `ALLOWED_ORIGINS` was set with a trailing
  slash, which a browser's `Origin` header never has, so every request was
  silently rejected with no error on either side. Fixed in code
  (`.rstrip("/")` on every configured origin) with a regression test, not just
  the dashboard value, so the same paste-in mistake can't recur. Also caught
  and flagged: a sibling Vercel *preview* URL sits behind Vercel's SSO wall
  and would show a login screen to any judge who clicked it — the production
  URL above does not.

- **T12 deploy prep** (`d08460b`). Verified before fixing: the API was booted
  with `.env` hidden and configuration supplied only through environment
  variables, the way Render runs it. It came up, read `ALLOWED_ORIGINS` from
  the environment, resolved the corrected model ids, and **self-seeded the
  demo ledger on a blank disk** — a populated dashboard from an empty
  database, no manual step. That was the main deploy risk.

  Three real defects in the configs:
  1. **`vercel.json` sat at the repo root, where Vercel would never read it.**
     Root Directory is `apps/web`, and Vercel reads `vercel.json` from the
     root directory — the file was inert and its security headers would have
     silently never applied. Moved, and its `cd apps/web` prefixes dropped
     since they would now resolve to `apps/web/apps/web`.
  2. **`pyyaml` was undeclared**, so the eval suite passes locally and fails
     on a fresh clone — where a judge or CI meets it first.
  3. **USER.md promised a login that does not exist.** §8e now states plainly
     that this build has no auth and tells the owner *not* to create the
     `demo@finpilot.in` account T12 asks for.

  Also corrected: §8a still instructed running migrations that are already
  applied, and §8d configured Supabase auth redirects for auth that does not
  exist. Added the two ordering traps that bite real deploys — `NEXT_PUBLIC_*`
  is baked in at build time, and `ALLOWED_ORIGINS`/`NEXT_PUBLIC_API_URL` are
  mutually dependent, making the deploy inherently two-pass.

- **A committed accessibility suite** (`c679e7f`). `apps/web/tests/a11y.spec.ts`
  replaces the one-off script: 8 routes × 2 themes, skip-link, 200% zoom, the
  chat keyboard path, and one live chat spec marked `@quota`. It runs against
  the *production* build, because dev-mode overlays hide the runtime-only bugs
  it exists to catch. It immediately caught two:
  1. **The vault page crashed as soon as any AI call had been made** — it read
     `d.fields`/`d.txn_count` where the API sends `field_types`/`redacted_count`,
     so `undefined.join` blanked the whole page. It type-checked because
     `lib/types.ts` is a hand-written mirror that declared the same wrong
     names. This would have broken the demo: the privacy vault is a USP and it
     died the moment you used the chat you were demoing.
  2. **No SSE frame ever reached the browser.** `sse_starlette` separates
     frames with `

`; both readers split on `

` and matched
     nothing, yielding zero events while the request looked healthy — 200,
     body streaming, no error. Chat hung on "Thinking…". The upload page had
     the identical bug and looked fine only because the upload still
     succeeded with its progress stages silently missing.

- **T07 — agent layer** (`d9d68db`, `e3904e8`). The 11 tools of DESIGN.md §9.2,
  each hitting the engine and returning `{data, citations}`; a hand-driven
  Gemini function-calling loop with automatic function calling *disabled*, so
  citations are captured and the answer is audited before it reaches the user;
  guardrails (advice boundary, untrusted-document fence, citation audit); and
  `llm.py` as the single seam where redaction and `ai_disclosures` happen, so
  no second code path can skip them.
- **T10 — chat with citations** (`8472b3a`). The last missing route. Streaming
  SSE, `aria-live`/`aria-busy`, plain-language tool indicator, the four PS
  questions as chips, and an affordability card deep-linked to the simulator.
  A figure arriving **without** a citation renders in an explicit unverified
  state — the visible half of §9.3 only works if the absence is something the
  user can see.
- **T15 — eval harness** (`42a8649`). 25 goldens sourced from
  `seed/expected.json`, asserted in three layers: the engine against ground
  truth (offline, always), then the agent's tool choice and the figure it
  *cited* (live, opt-in). The live layers are opt-in because 25 questions at
  2–3 calls each does not fit a 20/day free tier.
- **Four defects found by running the new code, not by reading it:**
  1. `config.py` resolved `.env` against the **working directory**, so settings
     loaded only when the process started inside `services/api`. Uvicorn does;
     pytest does not, and silently got an *empty* key — a product behaving
     exactly as though no key existed, with no error. Now anchored to the module.
  2. The advice decline was **not deterministic**: asked about mutual funds the
     model declined in its own words, and the guardrail reported
     `declined=False`, because a refusal contains no advice patterns. The
     boundary is now also checked on the *question*, before any model call —
     spec-exact per §9.4, and it costs no quota.
  3. My own first retry implementation retried **429**, spending three more of
     twenty requests to be told the same thing. Quota errors are no longer
     retried; 5xx still is.
  4. The eval harness compared a **count** (9 subscriptions) against cited
     *paise*. Counts are not money; they now have their own assertion.

- **T08 — frontend shell, design system, a11y foundation** (`f2b90ec`).
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
- **T09 — dashboard and upload** (`f2b90ec`). Safe-to-Spend hero with the
  committed figure as a citation, Leak Score half-dial (score printed and band
  named, never colour alone), income-vs-spending and category charts, anomaly
  cards with dismiss, a filterable transactions table with inline category
  override, and an SSE upload flow with per-bank password hints.
- **T11 — radar, goals, vault** (`f2b90ec`). The 30-day timeline grouped by
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
- **T04 — ingestion** (`e2467cb`). `normalize` (paise-exact money, channel
  classification, VPA extraction, structural merchant extraction), `dedupe`
  (sha256 over account + date + amount + narration, deduping within a batch as
  well as against the store), an adapter registry tried in descending
  confidence (`generic_csv`, `hdfc_pdf`, `icici_pdf`, `llm_fallback`), PDF
  decryption with per-bank password hints, and a generator-based `pipeline.run`
  that streams stage events for SSE. Merchant extraction was checked against
  the seed's own ground truth: **931 of 936** exact matches.
- **T05 tier-1 — categorisation** (`e2467cb`). A 330-merchant dictionary plus
  structural rules (salary, EMIs, rent, ATM, interest, self-transfer, bank
  charges, SIPs, insurance, refunds) and a channel fallback, in that
  precedence. Tier-2 (`llm_classify`) is written and declines cleanly with no
  API key, so the product stays on tier 1 rather than failing.
- **Offline store + API routes** (`e2467cb`). Raw-SQL SQLite mirroring the
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

- **Budget Guard hardened, and its verification committed.** The extension's
  own check had been a one-off script that was never committed, so nothing
  guarded the cart-total parser. Replacing it with
  `apps/web/tests/extension.spec.ts` (11 specs, driving the real
  `extension/content/*.js` sources — no extension install, no API, no web
  server) immediately found three genuine defects, none of which the two
  existing fixtures could surface:
  1. **The heuristic found nothing at all on a real Amazon cart.** Amazon
     ships a price as four elements (symbol, whole, decimal, fraction), so
     no text node holds "₹" beside its digits; both committed fixtures used
     whole-text prices and so never exercised it. It now climbs to the
     nearest ancestor carrying digits.
  2. **The obvious fix overestimates by 100x.** Reading the combined text
     turns "₹" + "40" + "00" into ₹4,000 when a retailer omits the decimal
     element — an interstitial fired by a delivery fee. A trailing two-digit
     fragment with no decimal point in the text is now read as the fraction.
  3. **`finpilotIsVisible` rejected every `position: fixed` element.**
     `offsetParent === null` is not a visibility test; it is also null for
     fixed positioning, which is what a sticky order summary or a bottom
     checkout bar usually is.

  Also: **"Wait 24 hours" was a lie.** It wrote a cooldown record that
  nothing ever read, so the next page load showed the same dialog again. The
  content scripts now consult it, per retailer, with a real 24-hour expiry.

  `pytest services/api/tests/ evals/` stayed green (326 passed, 25 live eval
  cases skipped) and the full Playwright suite is **30/30** with the API live
  — 19 a11y specs plus the 11 new ones.

- **CI wired** (`.github/workflows/ci.yml`). Two jobs: pytest on the
  interpreter `services/api/.python-version` pins, and a browser job that
  boots the API on 8001, builds the web app with a matching
  `NEXT_PUBLIC_API_URL` (baked in at build time, so it has to be set there)
  and runs Playwright with `--grep-invert @quota`. That closes the T08
  leftover and means the axe floor is enforced on every push rather than
  whenever someone remembers to run a script.

## Blockers or ceiling

**External — needs a human, cannot be fixed by writing code:**

- ~~No Supabase project / migrations never applied.~~ **Cleared 20 Sep 2026.**
  The schema is live and all three open T02 criteria pass (see Verified state).
  What remains is that the **app does not use it yet**: the routes still read
  the offline SQLite store, so swapping the store dependency is now a real,
  unblocked task rather than a hypothetical one.
- **Docker Desktop daemon not running**, so a local Postgres+pgvector container
  was not available as a fallback for the above. Starting Docker Desktop would
  unblock migration testing without needing Supabase.
- ~~Gemini key supplied and working, chat quota tight (~20 req/day).~~
  **Superseded 20 Sep 2026.** Chat and the summary now run on Groq
  (`openai/gpt-oss-20b`), rate-limited per minute rather than a hard daily
  cap — see the Groq switch under Completed recently. Gemini's remaining
  job (bulk categorisation, PDF fallback, embeddings) stays well under its
  free-tier cap on the seed dataset (~19 calls total).
- ~~Vercel + Render accounts (T12).~~ **Cleared 20 Sep 2026.** Both deployed,
  live, verified. See Completed recently.
- ~~cron-job.org keep-alive ping.~~ **Set up by the owner, 20 Sep 2026.**
  Render's free tier no longer risks a cold-start on a judge's first click.
- **Docker still not running** — the one remaining blocker for T14
  verification (see Completed recently: the workflow JSON is built, just
  never imported or run). Telegram bot token also still needed for the same.

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

- **Point the API at Supabase.** The schema is live and verified, but
  `app/store/db.py` (SQLite) is still what the routes use. This is the swap
  the store layer was designed for — the engine and views are unaffected
  because neither knows how rows are fetched — and it is a prerequisite for
  T12 deploying anything with real persistence.
- ~~T12 deploy checkpoint.~~ **Done, live, and verified from outside** — see
  Completed recently. What's left of T12 is a single owner-only step: the
  cron-job.org keep-alive ping on `.../health`, so Render's free-tier sleep
  doesn't cold-start a judge's first click. Not code; nothing to commit.
- ~~Enable Gemini billing.~~ **Decided against, 20 Sep 2026.** The owner is
  using Gemini to record a demo video, not for live judging, so ~20 requests
  per day per model is sufficient and billing is unnecessary. The full 25-case
  eval run (`--live-all`) therefore stays out of reach by choice, not by
  accident; the 7-case live subset covers the acceptance criteria.
- **T05 tier-2** — the batch classifier is written and has still never run.
  Tier 1 covers 97.2%, so it remains a refinement, not a dependency.
- ~~T08 leftovers — an axe run wired into CI rather than a one-off script.~~
  **Done 20 Sep 2026** — `.github/workflows/ci.yml` runs `pytest
  services/api/tests/ evals/` and, in a second job, boots the API, builds the
  web app and runs the whole Playwright suite (axe on 8 routes x 2 themes,
  plus the new extension specs) with `--grep-invert @quota` so a push never
  spends model quota. Supabase auth pages remain undone and are deliberate —
  this build has no auth (USER.md §8e).
- **The NVDA pass.** axe-core is a floor, not a ceiling: it cannot judge
  whether a label is *comprehensible*. Still the only accessibility claim in
  DESIGN.md §11 with no evidence behind it.
- ~~T13 Budget Guard extension, T14 n8n workflows (both P1).~~ **Built 20
  Sep 2026** — see Completed recently. What's left of each is verification
  only, both owner-side: T13 needs a real `amazon.in`/`flipkart.com` cart;
  T14 needs Docker running and the import steps in `n8n/README.md` walked
  through once.
- **T16** video + submission.


## Unverified figures

- **The Budget Guard extension has never seen a real Amazon.in or Flipkart
  cart.** Its cart-total parsing (primary selectors and the ₹-numeric
  heuristic), the 24-hour cooldown and the interstitial's accessibility
  contract are now covered by a **committed** suite
  (`apps/web/tests/extension.spec.ts`, 11 specs) against fixture pages in
  `extension/test-fixtures/` — including one reproducing Amazon's real
  split symbol/whole/decimal/fraction price markup, which is what exposed
  the heuristic returning `null` on a live cart. The DOM of an actual
  retailer page, with real ad and tracking scripts running alongside it, is
  still not something this session could exercise.
- **The n8n workflow export has never been imported into a running n8n or
  run against a live Telegram bot.** `n8n/finpilot-workflows.json` is
  structurally valid and points at the right API routes, but every one of
  BUILD_TASKS.md T14's functional acceptance criteria — the bot replying to
  a statement or a question, the scheduled workflows firing correctly —
  is unverified because Docker wasn't available to run n8n locally.
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
- ~~No Gemini API call has ever been made.~~ **Retired 20 Sep 2026** — calls
  are exercised, and doing so falsified two documented model choices (see
  Verified state). What remains unverified: the **summary generator has never
  produced prose**, only its pre-computed facts; and no **vision** or
  **embedding-backed document search** path has run, since no pgvector index
  exists.
- ~~`/chat` has not been through a browser or axe-core pass.~~ **Retired** —
  it is in the committed Playwright suite now, and doing so caught two runtime
  defects `npm run build` could not see (see Completed recently).
- **The live eval layer has only ever run its 7-case subset**, on
  `gemini-3.5-flash-lite`. The other 18 cases have never been executed against
  a model.
- The 34-series / 27-anomaly counts are specific to `--seed 42 --as-of
  2026-09-19`. They move with the as-of date, since the 14-month window slides.
- `MIN_CLUSTER_DOMINANCE = 0.30`, `MIN_GAP_CONSISTENCY = 0.75`,
  `MIN_SPIKE_RELATIVE_CHANGE = 0.30` and `PRICE_HIKE_MIN_CONFIDENCE = 0.7` were
  chosen to fit this seed dataset. They are reasonable and documented, but they
  are tuned against synthetic data, not validated against real statements.
