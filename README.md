# FinPilot

**A personal finance decision-support agent for India.**
Deterministic ledger first, agent second — the language model never computes a number.

FinPilot ingests bank statements, bills and expense records; categorises them; detects
recurring payments, upcoming obligations and unusual spending; and answers questions
about all of it with a citation on every figure you can click through to the exact
transactions behind it.

---

## Why it looks like this

Three design decisions carry the product:

**1. The engine is pure, and the agent only calls it.**
Every number comes from unit-tested Python in `services/api/app/engine/` — recurrence
detection, anomaly statistics, cash-flow, budgets, goals, simulation. The agent selects
tools and writes prose; it never does arithmetic. A hallucinated figure has no citation,
and the UI renders it as unverified.

**2. Money is `BIGINT` paise everywhere.**
No floats touch a currency value at any point. Formatting to `₹1,234.56` happens exactly
once, at the render boundary. Floating-point rupees is the most common source of silent
wrongness in finance code.

**3. Ingestion is idempotent.**
`dedupe_key = sha256(account_id ‖ txn_date ‖ amount_paise ‖ normalize(raw_narration))`
with a `UNIQUE` constraint. Re-uploading an overlapping statement inserts nothing new.
Users upload overlapping date ranges constantly; without this the product silently
double-counts.

### Mandate Radar

The India-specific edge. Under the RBI e-mandate framework, recurring debits up to
₹15,000 require no OTP after setup — most people's auto-debits now fire silently.
FinPilot lists them, badges each one with the rule that makes it silent, and gives you
seven days' notice where the regulation gives you one.

### Accessibility

In *Pragya Prasun v. Union of India* and *Amar Jain v. Union of India* (30 April 2025)
the Supreme Court held digital accessibility to be an intrinsic component of the
fundamental right to life under Article 21, in a case about digital KYC excluding blind
and low-vision users from banking. SEBI mandated the same across regulated entities on
31 July 2025. FinPilot targets **WCAG 2.1 AA**, and every chart ships a table view.
See [`/accessibility`](apps/web/app/accessibility) and DESIGN.md §11.

---

## Layout

```
apps/web/            Next.js 15 · App Router · TypeScript · Tailwind · Recharts
apps/extension/      MV3 "Budget Guard" browser extension            [P1]
services/api/        FastAPI
  app/ingest/          parsers, adapters, dedupe
  app/enrich/          3-tier categorisation
  app/engine/          recurrence · anomaly · cashflow · budget · goals · simulate
  app/agent/           tools · loop · prompts · guardrails
  app/privacy/         redaction · consent · audit · retention
  tests/               engine unit tests
  evals/               golden-answer regression harness
seed/                synthetic Indian statement generator
supabase/migrations/ schema, RLS, category taxonomy
n8n/                 Telegram workflows                              [P1]
```

## Documentation

| File | What it holds |
|---|---|
| [DESIGN.md](DESIGN.md) | Single source of architectural truth |
| [BUILD_TASKS.md](BUILD_TASKS.md) | Task list with acceptance criteria |
| [USER.md](USER.md) | Every step that needs a human |
| [SUBMISSION.md](SUBMISSION.md) | Video script, form answers, judge test-script |

---

## Running locally

Prerequisites: Node 20+, Python 3.11, a Supabase project, an Anthropic API key.
Full setup instructions, including how to obtain each credential, are in
[USER.md](USER.md).

### API

```bash
cd services/api
python -m venv .venv && .venv/Scripts/activate      # Windows
pip install -r requirements.txt
cp .env.example .env                                 # then fill it in
uvicorn app.main:app --reload                        # http://localhost:8000
```

`GET /health` returns `{"status":"ok"}`.

### Web

```bash
cd apps/web
npm install
cp .env.example .env.local                           # then fill it in
npm run dev                                          # http://localhost:3000
```

### Database

```bash
npx supabase link --project-ref <your-project-ref>
npx supabase db push
```

The migrations create every table, enable row-level security keyed to `auth.uid()`,
and seed the 42-row category taxonomy.

---

## Tests

```bash
pytest services/api/tests/ -v    # engine unit tests
pytest evals/ -v                 # golden-answer regression against the seed data
```

The eval harness asserts that the figure the **agent cited** equals the figure the
**engine computed**, against a deterministic synthetic dataset. It is a real regression
harness, not a demo prop.

---

## What this is not

Stated explicitly so the scope stays honest:

- **No investment, securities, insurance or tax advice.** Eligibility and arithmetic
  only, enforced in code by a post-generation boundary check.
- **No payment initiation.** FinPilot reads and analyses. It never moves money and never
  cancels a mandate for you — the Revoke Kit tells you how; you do it.
- **No credit scoring or lending decisions.**
- **No bank credential collection.** No screen-scraping, no net-banking passwords.
  Upload, or (future) Account Aggregator consent.
- **No claim of universal bank coverage.** Bank PDF layouts change without notice. Two
  real adapters, a robust generic CSV path, an LLM structured-extraction fallback, and a
  manual column mapper. The UI names the adapter that parsed each document and its
  confidence.
- **Not production-hardened.** A prototype with production-shaped architecture.

## Licence

See [LICENSE](LICENSE) if present; otherwise all rights reserved pending selection.
