# FinPilot

A personal finance decision-support agent for India: ingests bank statements,
categorises them, detects recurring mandates and anomalies, and answers
questions with a clickable citation behind every figure.

## Build, test, run

Windows paths. The venv interpreter is `Scripts/python.exe`, not `bin/python`.

```bash
# Engine + seed tests (200 currently). Run from the repo root.
services/api/.venv/Scripts/python.exe -m pytest services/api/tests/

# API — GET /health must return {"status":"ok"}
# NOTE: :8000 is inside this machine's Windows reserved port exclusion range
# (netsh int ipv4 show excludedportrange protocol=tcp) and CANNOT bind — the
# error is a misleading "socket access forbidden", not "in use". Use 8001 and
# rebuild the web app with a matching NEXT_PUBLIC_API_URL, since Next bakes it
# in at build time.
cd services/api && .venv/Scripts/python.exe -m uvicorn app.main:app --port 8001

# Web on :3000
cd apps/web && npm run dev
cd apps/web && npm run build     # must exit 0 with no type errors

# Accessibility sweep: every route x both themes, zero axe violations.
# Needs the API live; Playwright starts the web server itself.
cd apps/web && NEXT_PUBLIC_API_URL=http://localhost:8001 npx playwright test
cd apps/web && npx playwright test --grep-invert @quota   # skip the one
                                   # spec that spends Groq quota

# Regenerate the demo dataset (pin --as-of, see gotchas)
services/api/.venv/Scripts/python.exe seed/generate.py --seed 42 --as-of 2026-09-19

# Apply migrations. The four files were applied 20 Sep 2026 over DATABASE_URL
# with psycopg (one transaction per file) — that path is verified. The npx
# path below is still UNVERIFIED; it needs the Supabase CLI and a login.
npx supabase link --project-ref <ref> && npx supabase db push
```

## Architecture

The load-bearing claim is that **the language model never computes a number**.
A pure Python engine does the arithmetic; the agent only selects tools and
writes prose around figures the engine produced.

- `services/api/app/engine/` — recurrence, anomaly, cashflow, budget, goals,
  simulate. Pure functions over frozen dataclasses. No DB, no LLM, no network.
- `services/api/app/models/` — SQLAlchemy tables + Pydantic wire schemas.
  Deliberately *not* imported by the engine.
- `services/api/app/{ingest,enrich,agent,privacy}/` — built.
- `apps/web/` — Next.js 15 App Router, Tailwind v4, Recharts.
- Runtime inference is split across two free tiers, never Anthropic:
  **Groq** (`openai/gpt-oss-20b`) for chat and the monthly summary —
  switched 20 Sep 2026 off Gemini after its 20-requests/day cap ran out
  mid-demo-prep; **Google Gemini** (`gemini-3.5-flash-lite`) still does bulk
  classification, vision, and `gemini-embedding-2` at 768 dims. Model IDs
  live in `app/config.py`.
- `supabase/migrations/` — 4 migrations: enums, 14 tables, indexes + RLS,
  42-row category taxonomy.
- `seed/generate.py` — deterministic 14-month synthetic Indian ledger, plus
  `seed/expected.json` ground truth for the eval harness.

Design authority is `DESIGN.md` — §5 data model, §6 ingestion, §7
categorisation, §8 engine, §9 agent, §11 accessibility, §12 privacy.
Task list and acceptance criteria are in `BUILD_TASKS.md`. Everything needing
a human (API keys, deploys, video) is in `USER.md`.

## Current status

Read `PROGRESS.md` before assuming anything about what currently works — this
file describes structure, not the day's state.

## The agentic layer, in one paragraph

The agent has two modes. `POST /api/agent/ask` is read-only (12 tools) and is
what `/chat` and the eval goldens use — **keep it behaviourally identical**.
`POST /api/agent/act` additionally exposes `propose_*` tools that *stage*
changes into an `ActionRegistry`; the UI renders them as cards and
`POST /api/agent/actions/apply` is the only thing that writes. Staging tools
are reachable only when `ToolContext.actions` is set, which is what keeps
`/ask` incapable of mutating anything.

## Gotchas Claude keeps re-discovering

- **The model must never convert a unit.** `"50L"` → paise is arithmetic, and
  arithmetic is the engine's job. `propose_create_goal` takes
  `amount_value=50, amount_unit="lakh"` and `app/agent/money.py` converts.
  Same rule as every other figure, just less obvious.
- **Never restate a staged action's amount in the prose.** It came from the
  user, not a tool, so it has no citation — and `guardrails.audit_citations`
  flags any uncited rupee figure. The action card carries the number as
  structured data instead.
- **Deleting a transaction is a side table, not a column.**
  `deleted_transactions` mirrors the `dismissals`/`acknowledgements` pattern.
  If you add a new read path over `transactions`, it must filter deleted ids —
  both `transactions()` and `engine_txns()` do, and missing one makes the
  dashboard and the transactions table disagree about the same ledger.
- **`detect_anomalies` does not give the model transaction ids**, by design —
  they live on the citation, server-side. `get_anomaly_transactions` is the
  deliberate bridge for acting on a duplicate; don't "fix" this by widening
  the anomaly payload.
- **Two Groq model ids 404 on this account** despite Groq's docs listing them
  as live: `llama-3.3-70b-versatile` and `llama-3.1-8b-instant`. Only
  `openai/gpt-oss-20b` works. It is the default in `config.py`, so if chat
  breaks, suspect a stale `GROQ_MODEL_CHAT` in `.env` or the Render dashboard
  overriding it.

- **Money is `int` paise everywhere.** Fields are named `*_paise`; `Txn`
  rejects a float amount at construction. Format to rupees only at the render
  boundary. `tests/test_purity.py` asserts every returned `*_paise` is an int.
- **The engine must not import `google.genai`, `supabase`, `sqlalchemy` or
  `psycopg`.** That isolation is what makes it testable without infrastructure,
  and `tests/test_purity.py` fails the build if it is broken.
- **`recurrence.detect` has three guards that DESIGN.md §8.1 does not
  mention** — gap consistency, cluster dominance, and a tight probable-pair
  test. They are not optional polish: without them the seed yields ~200 phantom
  "subscriptions" (Swiggy, Uber, DMart), because `gap_mad` is itself a median
  and so ignores outliers entirely, and any 3 of 200 transactions can look
  regular by chance. `test_seed.py::test_no_phantom_series_from_busy_merchants`
  is the regression guard.
- **Category-spike detection refuses a month still in progress.** It runs on
  the last *complete* month. Pro-rating was tried and is wrong for lumpy fixed
  charges — one broadband debit that already happened reads as a 1.6× spike.
- **Seed determinism is per `(seed, as-of date)`.** The 14-month window is
  anchored to today, so an unpinned run produces different output tomorrow.
  Tests pin `as_of = 2026-09-19`.
- **`pytest.ini` lives at the repo root** and sets `pythonpath = services/api`,
  resolved against rootdir. That is what makes `import app.engine` work; there
  is no editable install.
- **Next.js is pinned to 15.** `create-next-app@latest` now installs 16.x;
  DESIGN.md §4.1 and BUILD_TASKS.md T01 both specify 15. Also pass
  `--no-turbopack`, or the v15 scaffolder prompts and hangs non-interactively.
- **A consumer Google AI Plus/Pro/Ultra plan does not raise Gemini *API* rate
  limits.** API quota is per Cloud project and needs billing for Tier 1.
- **The Gemini free tier allows ~20 requests per day, per model.** Measured
  20 Sep 2026 against a real key. Every flash model enforces **two** quotas at
  once — `GenerateRequestsPerMinutePerProjectPerModel` = **5/min** and
  `GenerateRequestsPerDayPerProjectPerModel` = **20/day** — and the daily one
  is the wall that ends the session. Gemini **Pro** models are **0/day**,
  unreachable without billing; `gemini-2.5-pro` also 404s as "no longer
  available to new users". This bit chat specifically, which is why chat and
  the summary moved to Groq (`GROQ_MODEL_CHAT`/`GROQ_MODEL_SUMMARY` in
  `services/api/.env`) — Gemini's remaining job is tier-2 categorisation and
  the PDF fallback, both far below 20 calls/day on the seed dataset (~19
  total, cached by narration hash).

  Sustained volume — the T15 eval harness at 25 live questions — is now
  bounded by Groq's per-minute limit rather than Gemini's daily one; still
  opt-in (`--live-all`), still worth pacing. `agent/loop.py` deliberately does
  **not** retry 429: retrying a quota error spends another request to be told
  the same thing.
- **Hand-written types in `apps/web/lib/types.ts` are not checked against the
  API.** They are mirrors, maintained by hand, and TypeScript will happily
  verify a page against a shape the server has never sent. The vault page
  declared `fields`/`txn_count` where `/api/vault` returns
  `field_types`/`redacted_count`; it type-checked, built, and threw a
  client-side exception that blanked the whole page the moment the AI
  disclosure log had one row in it. When you change a route's payload, grep
  `lib/types.ts` for the shape and run the Playwright suite — `npm run build`
  cannot catch this class of bug.
- **`render.yaml` only applies to Blueprint deploys.** A Render service
  created by hand in the dashboard ignores it entirely, including
  `PYTHON_VERSION` — the build then runs on Render's current default (3.14 as
  of 20 Sep 2026) and dies on `psycopg-binary`, which ships no 3.14 wheels and
  has no sdist. `services/api/.python-version` pins 3.11.13 and is read
  whichever way the service was made. The failure names psycopg; the cause is
  the interpreter, and the only clue is `cp314` in the wheel filenames.
- **`seed/output/` is gitignored; `seed/expected.json` is committed.** The eval
  harness reads the latter, so regenerating the seed can dirty the tree.
