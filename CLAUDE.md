# FinPilot

A personal finance decision-support agent for India: ingests bank statements,
categorises them, detects recurring mandates and anomalies, and answers
questions with a clickable citation behind every figure.

## Build, test, run

Windows paths. The venv interpreter is `Scripts/python.exe`, not `bin/python`.

```bash
# Engine + seed tests (200 currently). Run from the repo root.
services/api/.venv/Scripts/python.exe -m pytest services/api/tests/

# API on :8000 — GET /health must return {"status":"ok"}
cd services/api && .venv/Scripts/python.exe -m uvicorn app.main:app --reload

# Web on :3000
cd apps/web && npm run dev
cd apps/web && npm run build     # must exit 0 with no type errors

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
- `services/api/app/{ingest,enrich,agent,privacy}/` — scaffolded, not yet built.
- `apps/web/` — Next.js 15 App Router, Tailwind v4, Recharts.
- Runtime inference is **Google Gemini** on the free tier, never Anthropic:
  `gemini-3.5-flash` for chat and the monthly summary,
  `gemini-3.5-flash-lite` for bulk classification and vision,
  `gemini-embedding-2` at 768 dims. Model IDs live in `app/config.py`.
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

## Gotchas Claude keeps re-discovering

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
  available to new users".

  One chat question costs 2–3 calls, so a model id affords roughly **8
  questions a day**. Each model id is a separate bucket, so switching
  `GEMINI_MODEL_CHAT` in `services/api/.env` buys another 20. Anything
  needing sustained volume — the T15 eval harness at 25 questions — needs
  billing. `agent/loop.py` deliberately does **not** retry 429: on a daily cap
  each retry spends another request to be told the same thing.
- **`seed/output/` is gitignored; `seed/expected.json` is committed.** The eval
  harness reads the latter, so regenerating the seed can dirty the tree.
