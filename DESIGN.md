# FinPilot — Design Document

**Personal Finance Decision Support Agent**
Problem Statement 2 · Build window: 18 hours · Status: design frozen, ready for implementation

---

## 0. How to read this document

This is the **single source of architectural truth**. It is written to be executed by coding agents (Opus for judgement-heavy work, Sonnet for mechanical work) with no further design decisions required.

- **DESIGN.md** (this file) — what to build and why
- **BUILD_TASKS.md** — the hour-by-hour task list with acceptance criteria and model routing
- **USER.md** — everything a human must do (signups, keys, deploys, n8n import)
- **SUBMISSION.md** — video script, form answers, judge test-script
- **LINKEDIN.md** — post drafts and verified facts

If implementation and this document disagree, this document wins. If this document is silent on something, prefer the simplest thing that satisfies the acceptance criteria in BUILD_TASKS.md.

---

## 1. The problem, stated precisely

People can *see* their transactions but have no system that **explains** them or helps them **plan around what is already committed**.

Financial data is fragmented across bank statements, credit-card statements, bills, emails and spreadsheets. The consequences are specific and measurable:

1. **Recurring expenses are invisible.** Subscriptions and auto-debits accumulate silently and are never audited.
2. **Cash-flow pressure arrives unannounced.** People know their balance but not their *committed* balance.
3. **Everyday spending is disconnected from goals.** Nobody can state what a ₹12,000 purchase costs them in months of delay on an emergency fund.

FinPilot addresses all three by building a **deterministic financial ledger** and putting an **agent in front of it** — never the other way around.

### 1.1 The India-specific sharpening

The generic version of this problem has been solved a hundred times. The Indian version has a live, under-exploited edge:

Under the **RBI Digital Payments E-mandate Framework**, recurring debits up to **₹15,000** are processed **without any OTP or additional-factor authentication** after the initial mandate setup (₹1 lakh for insurance premiums, SIPs and credit-card bills). Banks must send a pre-debit alert 24 hours ahead, but that alert arrives as one SMS among dozens.

The practical result: **most Indians' recurring debits now fire silently.** The money leaves without a single interactive confirmation. This is not a hypothetical — it is the default behaviour of the payments rails today, and it is precisely the blind spot the problem statement's "identify recurring payments" and "identify upcoming recurring financial obligations" bullets describe.

That insight produces **Mandate Radar**, our headline feature, and it is a differentiator no generic PFM clone will have.

---

## 2. Design rationale driven by the scoring rubric

| Area | Weight | How this design earns it |
|---|---|---|
| Problem understanding | 15% | §1 above + the PS coverage matrix in §13, which maps every mandatory bullet to a named function and endpoint |
| Prototype quality & UX | 20% | One polished product deployed at hour 13, not a broad brittle one at hour 17. Seeded demo account with a reset button, because judges test 2–3 times |
| AI Integration | 25% | §9 — typed tool-calling agent over a deterministic engine, mandatory citations on every number, PII redaction before every call, and a golden-answer eval harness |
| LinkedIn content + engagement | 25% | Owner-managed. `LINKEDIN.md` supplies verified, independently shareable facts rather than product pitches |
| Innovation & creativity | 15% | Mandate Radar, Budget Guard browser extension, DPDP Consent Ledger, accessibility-by-construction under Article 21 |

**The load-bearing observation:** roughly 55% of the score is narrative, documentation and content rather than code. This document is therefore a *deliverable*, not scaffolding.

---

## 3. Regulatory foundation

Every India-specific feature traces to a verified source. Dates matter — several of these are recent enough that building against them is genuinely forward-looking.

| # | Instrument | Verified fact | Feature |
|---|---|---|---|
| R1 | **RBI Digital Payments E-mandate Framework** | Recurring debits ≤ **₹15,000** require no AFA/OTP after setup. **₹1 lakh** threshold for insurance premiums, mutual-fund SIPs and credit-card bills. 24-hour pre-debit notification mandatory. Zero-liability protection. Applies equally to UPI AutoPay and NACH. Banks may not charge for e-mandate. | Mandate Radar (§10.1) |
| R2 | **DPDP Act 2023 + DPDP Rules 2025** | Rules notified **13 Nov 2025**. Phase 1 (Data Protection Board) Nov 2025. Phase 2 (Consent Manager framework) **13 Nov 2026**. Phase 3 (all remaining substantive obligations) **13 May 2027**. Consent notices must be standalone, clear, purpose-specific. | Consent Ledger (§10.2) |
| R3 | **RBI Account Aggregator framework** | Consent-artefact model: AA forwards a signed artefact to each FIP, which validates it before releasing encrypted data. Sahamati recognised as SRO **5 Jun 2026**. 176 FIPs, 1,020 FIUs, 17 AAs live; 2.61bn accounts enabled, 252.9m users (as of 31 Dec 2025). | Consent artefact UX, roadmap to FIU status |
| R4 | **Pragya Prasun v. Union of India** & **Amar Jain v. Union of India**, decided **30 Apr 2025** | Supreme Court held that **digital accessibility is an intrinsic component of the fundamental right to life under Article 21**. The case concerned digital KYC processes excluding blind, low-vision and acid-attack survivors from banking and telecom. | Accessibility (§11) |
| R5 | **SEBI circular, 31 Jul 2025** | Mandates digital accessibility for **all SEBI-regulated entities**, enforcing RPwD Act 2016 and following R4. | Accessibility statement |
| R6 | **RPwD Act 2016**, §§40–46 | Requires ICT content in accessible formats. Applicable standards: **WCAG 2.1 AA**, **IS 17802**, **GIGW 3.0**. | Accessibility conformance target |
| R7 | **Bhashini** (MeitY, National Language Translation Mission) | Free ASR, TTS, NMT and transliteration across the 22 scheduled languages. Already powers DigiLocker, UMANG and CSC. Model hub contributed by AI4Bharat, C-DAC, IIIT-H. | Vernacular monthly summary (§10.7) |
| R8 | **Income-tax, FY 2026-27** | New regime is default: ₹75,000 standard deduction, ₹60,000 rebate → nil tax up to ₹12L (₹12.75L salaried). 80C/80D/HRA/home-loan interest unavailable in new regime. 80CCD(1B) gives ₹50,000 over and above 80C. | Tax Regime Radar (roadmap, §14) |
| R9 | **Government schemes** | PMJJBY ₹436/yr → ₹2L life cover (18–50). PMSBY ₹20/yr → ₹2L accident cover (18–70). APY extended to FY2030-31, contributions ₹42–₹1,454/mo, 80CCD benefit. SSY 8.2%. PPF 7.1%, tax-free. SCSS 8.2%. JanSamarth: 13 credit-linked subsidy schemes, 54.10 lakh applications / ₹3,00,951 cr processed as of 1 Jun 2026. | Scheme Match (roadmap, §14) |
| R10 | **Funding & sustainability** | DPIIT **SISFS**: up to ₹20L grant for PoC/prototype, up to ₹50L for scale-up; ₹945 cr corpus, ~3,600 startups, 300+ recognised incubators; financial inclusion is a stated preference sector. **RBI Regulatory Sandbox moved to On-Tap in 2025** — no cohort wait. **NCFE** (promoted by RBI, SEBI, IRDAI, PFRDA under FSDC) runs 5,000+ FEPA adult-literacy programmes per year. | §15 |

### 3.1 The advice boundary — a hard constraint

The problem statement is explicit: *"The goal is not to provide investment or financial advice."*

This is treated as a **product constraint enforced in code**, not a disclaimer in a footer:

- Every scheme, tax or goal feature surfaces **eligibility criteria and arithmetic only** — never a recommendation.
- Phrasing is fixed at the template level: *"You appear to meet the stated eligibility for X. Verify with your bank."* Never *"You should enrol in X."*
- The agent has a scripted decline for recommendation requests (§9.4) that pivots to showing data.
- A post-generation boundary check runs before any answer renders.

This constraint is also a *scoring asset*: it demonstrates problem understanding, and it is the correct engineering posture for anything touching Indian financial services.

---

## 4. System architecture

```
                      ┌──────────────────────────────┐
                      │  apps/web  (Next.js, Vercel) │
                      │  Dashboard · Chat · Radar    │
                      │  Simulator · Vault · A11y    │
                      └───────────┬──────────────────┘
                                  │ REST + SSE
┌─────────────────┐               │              ┌──────────────────────┐
│ apps/extension  │───────────────┤              │  n8n (Docker, local) │
│ Budget Guard    │   signed      │              │  Telegram · schedules│
│ MV3 content     │   budget      │              └──────────┬───────────┘
│ script          │   snapshot    │                         │ webhook
└─────────────────┘               │                         │
                      ┌───────────▼─────────────────────────▼────────┐
                      │       services/api  (FastAPI, Render)        │
                      │                                              │
                      │  ingest/  → parse → normalize → dedupe       │
                      │  enrich/  → 3-tier categorisation            │
                      │  engine/  → recurrence · anomaly · cashflow  │
                      │             budget · goals · simulator       │
                      │  agent/   → tools · citations · guardrails   │
                      │  privacy/ → redaction · consent · audit      │
                      └───────────┬─────────────────┬────────────────┘
                                  │                 │
                    ┌─────────────▼──────┐   ┌──────▼─────────────┐
                    │ Supabase Postgres  │   │ Gemini API         │
                    │ + pgvector         │   │ 3.8-flash / 2.5-pro│
                    │ + Storage + Auth   │   └────────────────────┘
                    └────────────────────┘
```

### 4.1 Repository layout

```
FinPilot/
├─ apps/
│  ├─ web/                    Next.js 15 · App Router · TS · Tailwind · shadcn/ui · Recharts
│  │  ├─ app/
│  │  │  ├─ (auth)/login/
│  │  │  ├─ dashboard/        summary, charts, safe-to-spend
│  │  │  ├─ transactions/     table, filters, category override
│  │  │  ├─ radar/            Mandate Radar
│  │  │  ├─ goals/            goals + What-If Simulator
│  │  │  ├─ budgets/
│  │  │  ├─ chat/             agent with citations
│  │  │  ├─ vault/            DPDP Data Vault
│  │  │  ├─ accessibility/    conformance statement
│  │  │  └─ api/              thin BFF proxy to FastAPI
│  │  ├─ components/
│  │  │  ├─ ui/               shadcn primitives
│  │  │  ├─ charts/           every chart wraps ChartWithTable
│  │  │  └─ citations/        CitationChip, TransactionDrawer
│  │  └─ lib/
│  └─ extension/              MV3 "Budget Guard"                              [P1]
│     ├─ manifest.json
│     ├─ src/content/         amazon.ts, flipkart.ts, interstitial.tsx
│     ├─ src/background/      service-worker.ts
│     └─ src/popup/
├─ services/api/
│  ├─ app/
│  │  ├─ ingest/              adapters/ (hdfc, icici, generic_csv, llm_fallback), pdf.py, dedupe.py
│  │  ├─ enrich/              rules.py, merchants.py, llm_classify.py
│  │  ├─ engine/              recurrence.py, anomaly.py, cashflow.py, budget.py, goals.py, simulate.py
│  │  ├─ agent/               tools.py, loop.py, prompts.py, guardrails.py
│  │  ├─ privacy/             redact.py, consent.py, audit.py, retention.py
│  │  ├─ models/              SQLAlchemy / Pydantic
│  │  └─ routes/
│  ├─ tests/                  unit tests for engine/ (mandatory)
│  └─ evals/                  golden.yaml + test_evals.py
├─ seed/                      synthetic Indian statement generator
├─ n8n/                       finpilot-workflows.json                          [P1]
├─ supabase/migrations/
└─ DESIGN.md · BUILD_TASKS.md · USER.md · SUBMISSION.md · LINKEDIN.md
```

### 4.2 Why this split

Python owns parsing and statistics because `pdfplumber`, `pikepdf`, `pandas` and robust-statistics code are materially better there, and because the analytics engine must be **unit-testable in isolation** — it is the component whose correctness the entire product rests on.

TypeScript owns the interface because UX is 20% of the score and shadcn/Radix gives accessible primitives for free, which is what makes the WCAG 2.1 AA target affordable inside 18 hours.

---

## 5. Data model

Supabase Postgres. All tables carry `user_id` with row-level security.

### 5.1 Two non-negotiable invariants

**1. Money is `BIGINT` paise. Never float, never `NUMERIC` with implicit rounding, never a formatted string.**
Formatting to `₹1,234.56` happens exactly once, at the render boundary. Every intermediate value — sums, medians, projections, tolerances — is integer paise. Floating-point rupees is the single most common source of silent wrongness in finance code, and wrong numbers in a demo the judges poke at 2–3 times is fatal.

**2. Ingestion is idempotent.**
`transactions.dedupe_key = sha256(account_id ‖ txn_date ‖ amount_paise ‖ normalize(raw_narration))`, with a `UNIQUE` constraint. Re-uploading an overlapping statement inserts nothing new. Users *will* upload overlapping date ranges; without this the demo silently double-counts.

### 5.2 Tables

```sql
-- Identity ------------------------------------------------------------------
users                 -- Supabase auth
accounts              id, user_id, bank_code, account_type(SAVINGS|CURRENT|CREDIT_CARD),
                      display_name, last4, opening_balance_paise, current_balance_paise,
                      balance_as_of

-- Ingestion -----------------------------------------------------------------
documents             id, user_id, kind(STATEMENT|BILL|RECEIPT), filename, storage_path,
                      sha256, mime, status(PENDING|PARSED|FAILED|NEEDS_PASSWORD),
                      parser_name, parser_version, rows_extracted, error, created_at, parsed_at

transactions          id, user_id, account_id, document_id,
                      txn_date DATE, value_date DATE,
                      amount_paise BIGINT NOT NULL,        -- always positive
                      direction ENUM(DEBIT|CREDIT),
                      raw_narration TEXT,
                      normalized_merchant TEXT,
                      counterparty_vpa TEXT,               -- e.g. swiggy@ybl
                      channel ENUM(UPI|NEFT|IMPS|CARD|NACH|ACH|ATM|CASH|CHEQUE|OTHER),
                      balance_paise BIGINT,
                      category_id, category_source ENUM(RULE|LLM|USER),
                      category_confidence REAL,
                      recurring_series_id NULL,
                      dedupe_key TEXT UNIQUE NOT NULL,
                      created_at

-- Enrichment ----------------------------------------------------------------
categories            id, parent_id, name, slug, icon, is_income, sort_order
merchant_rules        id, user_id NULL, pattern, match_type(REGEX|CONTAINS|VPA),
                      merchant, category_id, priority, scope(GLOBAL|USER), created_at
                      -- user overrides write here with scope=USER, priority=1000

-- Engine outputs ------------------------------------------------------------
recurring_series      id, user_id, normalized_merchant, category_id,
                      cadence ENUM(WEEKLY|FORTNIGHTLY|MONTHLY|QUARTERLY|HALF_YEARLY|ANNUAL),
                      median_amount_paise BIGINT, amount_tolerance_paise BIGINT,
                      median_gap_days REAL, gap_mad REAL,
                      occurrence_count INT, first_seen DATE, last_seen DATE,
                      next_expected_date DATE, confidence REAL,
                      mandate_channel ENUM(UPI_AUTOPAY|NACH|CARD_EMANDATE|SI|MANUAL|UNKNOWN),
                      afa_band ENUM(SILENT|HIGH_LIMIT|REQUIRES_AFA),  -- derived from R1
                      status ENUM(ACTIVE|LAPSED|CANCELLED),
                      acknowledged_at TIMESTAMPTZ NULL,   -- user has seen and accepted it
                      price_history JSONB                 -- [{from, amount_paise}]

anomalies             id, user_id, type, severity(LOW|MEDIUM|HIGH),
                      period_start, period_end, txn_ids UUID[], series_id NULL,
                      metric JSONB,                       -- {z, baseline, observed, ...}
                      explanation TEXT, detected_at, dismissed_at NULL

budgets               id, user_id, category_id, period(MONTHLY), limit_paise, starts_on
goals                 id, user_id, name, target_paise, current_paise, target_date,
                      priority, monthly_contribution_paise, created_at

-- Privacy (DPDP) ------------------------------------------------------------
consents              id, user_id, purpose, data_types TEXT[], retention_days,
                      frequency, granted_at, revoked_at NULL, artefact JSONB, version

ai_disclosures        id, user_id, at, purpose, model, prompt_tokens, completion_tokens,
                      field_names TEXT[],            -- which FIELDS (not values) were sent
                      redaction_count INT, redaction_types TEXT[],
                      request_hash, response_hash

-- Conversation --------------------------------------------------------------
chat_threads          id, user_id, title, created_at
chat_messages         id, thread_id, role, content, tool_calls JSONB,
                      citations JSONB,               -- [{label, value_paise, txn_ids[]}]
                      created_at

-- RAG over bills/receipts ---------------------------------------------------
document_chunks       id, document_id, user_id, chunk_text, embedding VECTOR(768)
                      -- gemini-embedding-2 emits 3072 dims natively and
                      -- truncates cleanly via MRL; 768 is a Google-recommended
                      -- size and the cheapest to index.
```

### 5.3 Category taxonomy

Two levels, seeded at migration time, India-shaped:

**Income** — Salary · Freelance/Business · Interest · Dividend · Refund · Transfer In · Other Income
**Essential** — Rent · Utilities (Electricity, Water, Gas, Broadband, Mobile) · Groceries · Transport/Fuel · Healthcare · Insurance Premium · Education · Domestic Help
**Lifestyle** — Food Delivery · Dining Out · Shopping · Entertainment · Subscriptions · Travel · Fitness · Personal Care
**Financial** — EMI/Loan Repayment · Credit Card Payment · Investment (SIP/MF) · PPF/NPS/Small Savings · Taxes · Fees & Charges
**Other** — Transfer Out · Cash Withdrawal · Uncategorised

`Uncategorised` must always exist and must be visible in the UI. Hiding unclassified spend is how PFM tools quietly lie.

---

## 6. Ingestion pipeline

```
upload → Supabase Storage → documents row
  → type detect (magic bytes, not extension)
  → PDF:  pikepdf.is_encrypted?
             yes → 422 NEEDS_PASSWORD + bank-specific hint → retry with password
             no  → pdfplumber text layer
                     empty → OCR fallback (P2; P0 returns a clear error)
     CSV/XLSX: pandas, header sniffing
     Image:    vision model structured extraction (bills/receipts)
  → adapter registry: first adapter whose detect() returns True
  → RawRow[] → normalize → dedupe_key → INSERT ... ON CONFLICT DO NOTHING
  → enrich (§7)
  → recompute recurrence + anomalies for the affected account
  → SSE progress to the UI at every stage
```

### 6.1 Adapter registry

```python
class StatementAdapter(Protocol):
    name: str
    version: str
    def detect(self, text: str, filename: str) -> float: ...   # 0.0–1.0 confidence
    def parse(self, text: str) -> list[RawRow]: ...
```

Registry tries adapters in descending `detect()` confidence and falls through to `llm_fallback`.

**P0 ships:** `generic_csv` (robust, column-mapping heuristics + a manual column-mapper UI fallback), `hdfc_pdf`, `icici_pdf`, `llm_fallback`.

**Honest scoping note.** Bank PDF layouts change without notice and are genuinely brittle. Two real adapters plus a strong generic CSV path plus an LLM structured-extraction fallback plus the seeded demo dataset is the correct allocation of 18 hours. Claiming universal bank coverage would be a lie the judges could catch in one upload. The UI says exactly which adapter parsed a document, and offers the column-mapper when confidence is low.

### 6.2 Password-protected PDFs

Indian bank statements arrive encrypted by default. The UI must ask for the password with a **bank-specific hint**, because users do not know their own password format:

| Bank | Format |
|---|---|
| HDFC | Customer ID |
| ICICI | First 4 letters of name (lowercase) + DDMM of birth |
| SBI | Three variants depending on source (net banking / email / YONO) — show all three |
| Axis | First 4 letters of name (uppercase) + DDMM |
| Kotak | Customer relationship number |
| PNB / BoB / BoI | Account number, mobile, or PAN |

Passwords are used in-memory for decryption and **never persisted**. This is stated in the UI at the point of entry.

### 6.3 The seed generator

`seed/generate.py` produces **14 months** of realistic synthetic data for the demo account. It must contain, by construction, one instance of everything the demo needs to show:

- Monthly salary credit on a consistent date, with one appraisal bump
- Rent (NACH), two EMIs (auto-debit), utilities with seasonal variance
- Realistic UPI narrations: `UPI/DR/412345678901/SWIGGY/YBL/Payment from ph`, `UPI-ZOMATO-ZOMATO@PAYTM-...`
- **9 subscriptions** including: one with a **price hike** at month 9, one **duplicate** (two music services), one **trial→paid** conversion, and one **dormant** (charged but no matching usage signal)
- A **category spike** (festival-month shopping, ~3.5× baseline)
- A **duplicate charge** (same merchant, same amount, 40 hours apart)
- A **new large merchant** (one-off ₹42,000 electronics purchase)
- Two goals partially funded, one on track and one behind

The generator is deterministic given a seed, so the eval harness (§9.5) can assert exact numeric answers against it.

---

## 7. Categorisation — 3-tier hybrid

This is deliberately *not* "send everything to an LLM". The tiering is the engineering story.

### Tier 1 — Deterministic rules (free, instant, auditable)

- **VPA handle extraction**: `swiggy@ybl`, `zomato@paytm`, `care@okhdfcbank` — the merchant token before `@` is a strong signal
- **Narration regex**: channel markers (`UPI/`, `NEFT-`, `IMPS`, `ACH D-`, `NACH`, `POS`, `ATW`), then merchant token extraction
- **Merchant dictionary**, ~300 entries covering Indian retail reality: Swiggy, Zomato, Blinkit, Zepto, Instamart, BigBasket, DMart, Amazon, Flipkart, Myntra, Ajio, Nykaa, IRCTC, MakeMyTrip, Uber, Ola, Rapido, Jio, Airtel, Vi, ACT, Netflix, Hotstar, Prime, Spotify, Gaana, Cult.fit, Zerodha, Groww, Upstox, LIC, HDFC Life, ICICI Pru, NPS, PPF, Apollo, PharmEasy, 1mg, BESCOM/MSEDCL/TNEB and similar DISCOMs…

Target: **~75% of retail transactions classified at tier 1.**

### Tier 2 — LLM batch classification (for the remainder)

- Unknowns batched **50 narrations per call**, sent **redacted** (§12.1)
- Structured output: `{id, merchant, category_slug, confidence, is_recurring_hint}`
- **Cached by `sha256(normalized_narration)`** in `merchant_rules` with `scope=GLOBAL`, so each *unique narration shape* costs exactly one classification for the lifetime of the deployment
- Results below confidence 0.6 land in `Uncategorised`, not a guess

### Tier 3 — User override (authoritative, permanent)

Changing a category in the UI writes a `merchant_rules` row with `scope=USER, priority=1000` and retroactively re-categorises matching historical transactions. The UI confirms with *"Learned — 14 past transactions updated."* This is the moment the product feels intelligent, and it costs almost nothing to build.

---

## 8. Analytics engine

**Pure Python. No LLM. Deterministic. Unit-tested.** This is the component the agent calls; if it is wrong, everything above it is wrong confidently.

All functions live in `services/api/app/engine/` and take explicit inputs, so they are testable without a database.

### 8.1 Recurrence detection — `recurrence.py`

```
for each normalized_merchant with ≥2 debits:
    cluster transactions by amount:
        tolerance = max(₹10, 5% of cluster median)
    for each cluster with ≥3 occurrences:
        gaps        = successive day differences
        median_gap  = median(gaps)
        gap_mad     = median(|gap − median_gap|)
        if gap_mad / median_gap < 0.25:
            cadence  = nearest of {7, 14, 30, 91, 182, 365} to median_gap
            next_expected_date = last_seen + median_gap
            confidence = f(occurrence_count, gap_mad, amount_variance)
            → recurring_series
    clusters with exactly 2 occurrences and tight amount match
        → status = PROBABLE, surfaced but flagged
```

**Mandate channel inference** from narration markers — `ACH D-` / `NACH` → `NACH`; `AUTOPAY` / `UPI-MANDATE` → `UPI_AUTOPAY`; `SI-` / `STANDING INSTR` → `SI`; `EMANDATE` → `CARD_EMANDATE`; otherwise `UNKNOWN`.

**AFA band** derived from R1:
- `median_amount_paise ≤ ₹15,000` → **`SILENT`** (will debit with no OTP)
- category ∈ {Insurance Premium, Investment SIP, Credit Card Payment} and ≤ ₹1,00,000 → **`HIGH_LIMIT`**
- otherwise → `REQUIRES_AFA`

**Price-hike detection**: when a new occurrence lands more than 10% above `median_amount_paise`, append to `price_history` and raise a `price_hike` anomaly rather than silently widening the tolerance.

### 8.2 Anomaly detection — `anomaly.py`

Five types, each producing a plain-English `explanation` from a fixed template. **Robust statistics throughout** — median and MAD, never mean and standard deviation, because a single festival month destroys a mean-based baseline.

| Type | Rule | Severity |
|---|---|---|
| `category_spike` | robust z = 0.6745·(observed − median)/MAD over trailing 6 months; \|z\| > 3 | HIGH if z > 5 |
| `new_large_merchant` | first-ever transaction for a merchant AND amount > p90 of the user's debits | MEDIUM |
| `duplicate_charge` | same merchant, same amount, within 72 hours | HIGH |
| `price_hike` | recurring series median rose > 10% vs prior | MEDIUM |
| `silent_mandate` | active series with `afa_band = SILENT` and `acknowledged_at IS NULL` | MEDIUM |

Requires ≥3 months of history for `category_spike`; below that the engine returns an explicit `insufficient_history` marker rather than a fabricated baseline.

### 8.3 Cash-flow & Safe-to-Spend — `cashflow.py`

```
next_income_date   = next_expected_date of the recurring CREDIT series (salary)
committed_paise    = Σ recurring_series due strictly before next_income_date
goal_due_paise     = Σ monthly_contribution_paise for goals not yet funded this month
discretionary      = current_balance − committed − goal_due
days_remaining     = (next_income_date − today).days
safe_daily_paise   = max(0, discretionary // days_remaining)
```

Returns the full forward schedule, not just the number, so the UI can render a runway chart and the agent can cite the individual obligations.

This function **is the literal answer** to the PS question *"How much of my budget is already committed?"*

### 8.4 Budget engine — `budget.py`

Per category: `spent`, `limit`, `remaining`, `pct_used`, `days_elapsed / days_in_period`, and a `pace` verdict — `ON_PACE` / `AHEAD` / `OVER` / `PROJECTED_OVER` (linear projection of current burn to period end).

### 8.5 Goal engine — `goals.py`

```
months_remaining   = months_between(today, target_date)
required_monthly   = (target_paise − current_paise) / months_remaining
projected_surplus  = median(monthly income − monthly expense, last 3 complete months)
available          = projected_surplus allocated across goals by priority
projected_eta      = first month where cumulative available ≥ (target − current)
verdict            = ON_TRACK | BEHIND(months_late) | AHEAD(months_early)
```

Note the engine reports arithmetic and a verdict. It never says what to do about it.

### 8.6 Scenario simulator — `simulate.py`

```python
def simulate(user_id, scenario: Scenario) -> SimulationResult
```

`Scenario` accepts:
- `cancel_series: list[series_id]` — remove those recurring obligations
- `category_pct_change: dict[category_slug, float]` — e.g. `{"food-delivery": -0.30}`
- `one_off: list[{amount_paise, date, category}]` — a purchase being considered

Returns a **before/after diff for every goal** (`eta_before`, `eta_after`, `months_delta`), the change in monthly surplus, and the change in Safe-to-Spend. Pure function of the current ledger plus the scenario — no LLM, fully reproducible.

This is what powers both the What-If Simulator UI (§10.4) and the Budget Guard extension (§10.5).

---

## 9. Agent layer

**This section carries the 25% AI Integration score. The central claim is architectural: the language model never computes a number.**

### 9.1 Model routing

Runtime inference splits across two providers, both free tier. The routing
below keeps one model per job rather than one model for everything, because
the jobs have genuinely different shapes.

| Use | Model | Why |
|---|---|---|
| Interactive chat loop | `openai/gpt-oss-20b` (Groq) | Function calling, and a rate limit that isn't a hard daily wall |
| Monthly summary generation | `openai/gpt-oss-20b` (Groq) | Runs async; the figures are pre-computed, so the model only writes prose |
| Batch categorisation | `gemini-3.5-flash-lite` (Gemini) | High volume, narrow structured task |
| Receipt/bill extraction | `gemini-3.5-flash-lite` (vision, Gemini) | Structured extraction from images |
| Document embeddings | `gemini-embedding-2` (Gemini) | 768-dim output for pgvector search |

> **Corrected 20 Sep 2026 (second pass).** Chat and the summary moved from
> Gemini to Groq after the 20-requests/day Gemini free-tier cap (see the
> correction note below) ran out mid-demo-prep, with no headroom left for
> recording. Groq's free tier is rate-limited per minute rather than gated by
> a hard daily wall, and `openai/gpt-oss-20b` supports the same
> function-calling shape `agent/loop.py` already drives by hand — exactly the
> provider-agnostic swap the closing paragraph of this section anticipated.
> Batch categorisation, the PDF LLM-fallback adapter, and embeddings stay on
> Gemini: none of them share Groq's daily-cap problem, so there was nothing to
> fix there.

> **Corrected 20 Sep 2026, measured against a real key.** This table first
> routed chat to `gemini-3.8-flash` and the summary to `gemini-2.5-pro`.
> Neither survives contact with the free tier:
>
> - `gemini-2.5-pro` returns **404 "no longer available to new users"**, and
>   every Gemini *Pro* model reports **`limit: 0`/day** on the free tier. No
>   Pro model is reachable without billing.
> - Flash models enforce **two** quotas at once:
>   `GenerateRequestsPerMinutePerProjectPerModel` = **5/min** and
>   `GenerateRequestsPerDayPerProjectPerModel` = **20/day**. The daily one is
>   the wall. One question costs two or more calls, so any single model id
>   affords roughly **eight questions per day**.
>
> Chat and the summary therefore run on `gemini-3.5-flash`, which supports
> function calling; the choice buys a bucket separate from the classifier's,
> not a larger one. Each model id is its own quota, so swapping ids is the
> cheapest way to find more headroom. Sustained volume — the §9.5 eval harness
> at 25 questions — needs billing. Model ids live in `app/config.py`; nothing
> else in the architecture moves.

Two consequences worth stating plainly:

- **Free-tier quotas are per Cloud project and are not raised by a consumer
  Google AI Plus / Pro / Ultra subscription.** Those cover the Gemini app, not
  the API. Moving to Tier 1 requires enabling billing on the project.
- The quota therefore shapes §7's design rather than being a footnote to it.
  Tier-1 rules classify ~75% of transactions for free, and tier-2 results are
  cached by `sha256(normalized_narration)`, so each *unique narration shape*
  costs exactly one call for the lifetime of the deployment. Bulk-classifying
  the entire 14-month seed is roughly 19 calls.

The architecture is provider-agnostic by construction: the model selects tools
and writes prose, the engine computes every number. Swapping providers changes
`agent/loop.py` and the model IDs, and nothing about what the product asserts.

### 9.2 Tools

Every tool is typed, hits the deterministic engine, and returns `{data, citations}`.

| Tool | Purpose |
|---|---|
| `query_transactions(filters)` | date range, category, merchant, amount range, direction |
| `get_category_breakdown(period)` | totals per category, ranked |
| `compare_periods(period_a, period_b)` | per-category deltas, absolute and % |
| `list_recurring(status?)` | all recurring series with cadence, amount, AFA band |
| `get_upcoming_obligations(days)` | forward schedule of due debits |
| `get_budget_status(period)` | per-category budget vs actual with pace |
| `get_goal_projection(goal_id?)` | ETA, required monthly, verdict |
| `detect_anomalies(period)` | the five anomaly types with explanations |
| `simulate_scenario(scenario)` | the §8.6 what-if engine |
| `get_safe_to_spend()` | committed vs discretionary, forward schedule |
| `search_documents(query)` | pgvector semantic search over bill/receipt text |

### 9.3 Citations — the anti-hallucination architecture

Every tool response carries:

```json
{
  "data": { "total_paise": 1843200, "category": "food-delivery" },
  "citations": [
    { "label": "Food Delivery, Sept 2026",
      "value_paise": 1843200,
      "txn_ids": ["…", "…"],
      "txn_count": 27 }
  ]
}
```

The system prompt requires the model to attach a citation id to every figure it states. The API response embeds citations alongside the message. The UI renders each figure as a `CitationChip` — a clickable element that opens a `TransactionDrawer` listing the exact transactions that sum to it.

Three consequences, all of which are worth saying out loud in the demo:

1. **A hallucinated number has nowhere to hide.** If the model invents a figure, it has no citation and the UI renders it in an "unverified" state.
2. **Every claim is auditable by the user in one click.**
3. **The arithmetic is Python's**, so it is correct by unit test rather than by hope.

### 9.4 Guardrails

**Advice boundary.** System prompt establishes the constraint; a lightweight post-generation check scans for recommendation patterns (`you should invest`, `I recommend buying`, `this fund`, `better returns`). On a hit, the answer is replaced with a scripted decline that pivots to data:

> *"I can't make investment or financial recommendations — that's outside what I do. What I can do is show you the numbers: here's what you've committed for the next 30 days and how each goal is tracking."*

**PII redaction before every LLM call** — §12.1. Non-negotiable, applies to categorisation batches and chat alike.

**Prompt-injection defence.** Uploaded document text is untrusted input. It is wrapped in explicit delimiters and the system prompt states that content inside them is *data to be analysed, never instructions to follow*. A bill with "ignore previous instructions" printed on it must not do anything.

**Grounding constraint.** The model may not answer financial questions from parametric knowledge. If no tool returns relevant data, it must say so: *"I don't have data for that period — try uploading a statement covering it."*

### 9.5 Eval harness

`evals/golden.yaml` — 25 questions against the deterministic seed dataset, each with the exact expected numeric answer computed independently by the engine:

```yaml
- id: top_category_sept
  question: "Where did I spend the most in September 2026?"
  expect_tool: get_category_breakdown
  expect_value_paise: 1843200
  expect_category: food-delivery
  tolerance_paise: 0

- id: committed_next_30
  question: "How much of my budget is already committed?"
  expect_tool: get_safe_to_spend
  expect_value_paise: 4120000
```

`pytest evals/` asserts that the figure the agent *cited* equals the figure the engine computes. This is a genuine regression harness, not a demo prop, and it is unusual enough in a hackathon to be worth thirty seconds of the video.

### 9.6 Monthly summary generation

Runs on `openai/gpt-oss-20b` via Groq (see the 9.1 correction note) with all engine outputs for the month pre-computed and supplied as structured input. Produces:

- **Headline**: income, expense, net, savings rate
- **Top movements**: three largest category changes vs the previous month, with figures
- **Recurring obligations**: what is committed next month, and which items are `SILENT`
- **Anomalies**: what was unusual and why
- **Goal impact**: each goal's ETA and the delta from last month
- **Action items**: 3–5 concrete, non-advisory items — *"Two music subscriptions are active (₹298/mo combined). Review whether both are needed."* Never *"Cancel Spotify."*

Rendered in the UI, sent via Telegram, and available as a Bhashini-translated version (§10.7).

---

## 10. Feature specifications

### 10.1 Mandate Radar — P0 · India USP

**The pitch**: *Your auto-debits now fire without asking you. This is the list of them.*

**View**: a 30-day forward timeline of every active `recurring_series`, grouped by week, each row showing merchant, amount, expected date, cadence and mandate channel.

**Badges**, each with a tooltip citing the rule:

| Badge | Condition | Tooltip |
|---|---|---|
| `SILENT` | `afa_band = SILENT` | "Under RBI rules, recurring debits up to ₹15,000 need no OTP. This will debit without asking you." |
| `HIGH-LIMIT` | `afa_band = HIGH_LIMIT` | "Insurance, SIP and credit-card mandates can debit up to ₹1,00,000 without additional authentication." |
| `PRICE UP 18%` | `price_history` shows a rise | Shows old → new amount with the date it changed |
| `DUPLICATE` | two active series in the same category with similar amounts | Names both |
| `TRIAL→PAID` | first occurrence ≪ median, subsequent at median | Shows the conversion date |
| `DORMANT` | active series, no related activity signal | Flags for review |

**The 7-day banner.** RBI requires a 24-hour pre-debit alert. FinPilot shows the same information **7 days ahead**, because 24 hours is not enough time to act on a mandate you had forgotten. This framing — *we give you seven days where the regulation gives you one* — is the single clearest articulation of the product's value.

**Revoke Kit.** Per-item, channel-specific, copy-to-clipboard:
- *UPI AutoPay* → UPI app → Mandates → find the mandate → Pause or Revoke
- *NACH* → net banking → e-Mandate management → cancel (with the note that cancellation takes effect after the current cycle)
- *Card e-mandate* → card issuer portal → Manage standing instructions
- Plus a pre-written cancellation email template addressed to the merchant

**Acknowledge.** Each item has *"I know about this"* → sets `acknowledged_at`, clears the `silent_mandate` anomaly. The radar is about *unknown* debits, not all debits.

**Leak Score (0–100).** One number, computed as a weighted deduction from 100 across duplicate subscriptions, unacknowledged silent mandates, price hikes in the last 6 months, and dormant series. Displayed as a large, colour-and-label (never colour-alone) gauge on the dashboard. It is the most screenshot-able artefact in the product.

### 10.2 DPDP Consent Ledger — P0 · India USP

**The pitch**: *Built for a law whose main deadline is 13 May 2027.*

**Consent artefact** — shown on first upload, modelled on the Account Aggregator artefact structure (R3):

| Field | Value |
|---|---|
| Purpose | Personal finance analysis and insight generation |
| Data types | Transaction records, account metadata, uploaded bills |
| Processing | Categorisation, recurrence detection, anomaly detection, AI-generated summaries |
| Third parties | Google (Gemini API, AI processing, redacted), Supabase (storage, India region where available) |
| Retention | 90 days from upload, then automatic deletion |
| Frequency | On demand, per your action |
| Revocation | Any time, from Data Vault — takes effect immediately |

Stored in `consents.artefact`. Versioned — a changed artefact requires re-consent.

**Data Vault page** — the feature judges will remember:

- **AI Disclosure Log**: every LLM call ever made for this user — timestamp, purpose, model, and *which fields* were sent. Crucially it shows the redaction: `narration: "UPI/DR/<REDACTED_REF>/SWIGGY/YBL"` with a note that **account numbers, IFSC codes and names never left the device un-tokenised**.
- **Storage inventory**: documents held, size, days until auto-deletion.
- **Erase everything** — DPDP right to erasure. Actually cascades and actually deletes, with a typed confirmation. Not a stub.
- **Export everything** — DPDP right to portability. Streams a JSON bundle of transactions, categories, goals, budgets and consent history.
- **Revoke consent** — immediately disables AI features while leaving the deterministic engine working. This is a meaningful demonstration that the product degrades gracefully rather than breaking.

**Retention job** — a scheduled purge of documents past `retention_days`. Runs via n8n (P1) or an in-process scheduler.

### 10.3 Cited answers + Safe-to-Spend — P0

Covered in §9.3 and §8.3. UI surface:

- **Dashboard hero**: *"₹41,200 committed over the next 11 days. Safe to spend: ₹640/day."* with the committed figure clickable to its constituent obligations.
- **Chat**: every figure a `CitationChip`; clicking opens the transaction drawer.
- **Runway chart**: projected balance to next salary, with obligation markers — and, per §11, a table-view toggle.

### 10.4 What-If Simulator — P0

Reached from any goal card, and deep-linked from chat when the agent recognises an affordability question.

**Controls**: toggle off any recurring series · percentage slider per discretionary category · add a one-off purchase (amount, date).

**Output**: for every goal, `ETA before → ETA after` with the month delta rendered prominently, plus the change in monthly surplus and Safe-to-Spend. The agent writes one paragraph of narration around the numbers the engine produced.

The demo line: *"Cancel these three subscriptions and cut food delivery 30% — your emergency fund lands in March instead of July."* Concrete, causal, and computed rather than asserted.

### 10.5 Budget Guard browser extension — P1

MV3 extension, content scripts on `*://*.amazon.in/*` and `*://*.flipkart.com/*`.

**Mechanism**
1. On login, the web app writes a **signed budget snapshot** into `chrome.storage.local` via `externally_connectable` — remaining discretionary budget, safe-to-spend, active goals with ETAs, and a short-lived token.
2. The content script detects cart / buy-now totals — primary DOM selectors per site, with a fallback heuristic that scans for ₹-prefixed numerics near checkout controls (layouts change; the heuristic keeps it alive).
3. If `cart_total > remaining_discretionary` **or** a simulation shows it pushes a goal ETA out, inject an interstitial.

**The interstitial** — accessible by construction: focus-trapped dialog, `role="alertdialog"`, Escape closes, never colour-alone:

> **This ₹12,499 purchase moves your Emergency Fund from March to June.**
> You have ₹4,200 of discretionary budget left this month.
> `[ Continue anyway ]` `[ Wait 24 hours ]` `[ Save to wishlist ]`

**Wait 24 hours** writes a cooling-off timer and schedules a Telegram nudge for the next day: *"Yesterday you paused a ₹12,499 purchase. Still want it?"* Cooling-off is the behaviourally effective intervention here, and it is far more interesting than a blunt block.

**Distribution constraint, stated honestly**: Chrome Web Store review does not clear in 48 hours. The extension ships **unpacked** via GitHub with load instructions in USER.md, and appears in the demo video. It is deliberately *not* part of the Agent Access Link given to judges.

> **Built 20 Sep 2026, with the mechanism simplified.** This build's API has
> no auth (§10.6 below and USER.md §8e), so step 1's signed-snapshot
> handshake via `externally_connectable` was dropped — the extension fetches
> `/api/dashboard` directly instead, same data, no login dependency to wire
> up. The goal-ETA-simulation trigger in step 3 is not built; only the
> discretionary-budget comparison is. "Wait 24 hours" writes a local
> cooldown record rather than actually enqueuing a Telegram nudge, since
> that needs §10.6's bot token. See `extension/README.md` for what was
> verified and what still needs a real `amazon.in`/`flipkart.com` cart to
> confirm.

### 10.6 n8n Telegram agent — P1 · the optional n8n deliverable

Four workflows, exported to `n8n/finpilot-workflows.json`:

| Workflow | Trigger | Behaviour |
|---|---|---|
| **Ingest** | Telegram Trigger | Document → download → `POST /api/ingest/sync` → reply with parse summary. Text → `POST /api/agent/ask/sync` → reply with the answer |
| **Daily brief** | Schedule, 08:00 IST | `GET /api/dashboard` + `GET /api/radar` → safe-to-spend and anything due today |
| **Mandate alert** | Schedule, 09:00 IST | `GET /api/radar` → any unacknowledged `SILENT` item due within the banner window → alert |
| **Monthly summary** | Schedule, 1st at 09:00 | `POST /api/summary/generate` → Telegram |

Telegram rather than WhatsApp is a deliberate, stated choice: WhatsApp Business API approval is measured in days, Telegram bot creation in minutes. Same demonstrated capability, zero schedule risk.

> **Corrected 20 Sep 2026.** The table originally named `GET /api/brief` and
> `GET /api/obligations?days=3`, neither of which was ever built — §10.6 was
> written before T09–T11 shipped the actual route layer. The corrected table
> above points at the routes that actually exist: `/api/dashboard` carries
> safe-to-spend, `/api/radar` carries obligations with `afa_band` and
> `days_away` already computed, so nothing new needed adding. "(Opus)" on
> the monthly summary was a leftover from before the runtime model was
> decided (§9.1) — it runs on the same model chat does, whichever that is
> today. Email delivery is dropped from the monthly summary; Telegram only.
>
> **Built the same day, but not verified.** BUILD_TASKS.md T14's own process
> — build in a running n8n, then export — needed Docker, which wasn't
> available. `n8n/generate_workflows.py` hand-produces the same JSON shape
> instead; it's structurally sound (validated JSON, every node reachable
> from one trigger, no orphans, secret scan clean) but has never been
> imported into n8n or run against a live bot. `n8n/README.md` has the gap
> and the steps to close it.

### 10.7 Vernacular summary — P0 (translation only)

The monthly summary gets a language selector. Translation goes through **Bhashini** (R7) with a single REST call — a government-funded public API, free for citizens, already serving DigiLocker and UMANG.

Voice input/output uses the browser-native **Web Speech API** (`hi-IN` and other Indian locales) — zero dependency, zero cost, works offline in the demo.

Full Bhashini ASR/TTS pipeline is roadmap (§14): its service-ID discovery is a known time sink and is not worth betting an 18-hour build on.

---

## 11. Accessibility — P0, cross-cutting

**This is not a feature row. It is a constraint on every component.** Built in from hour one it is nearly free; retrofitted it costs roughly five times as much.

### 11.1 Why it belongs in a finance product specifically

In **Pragya Prasun v. Union of India** and **Amar Jain v. Union of India** (30 April 2025), the Supreme Court held that **digital accessibility is an intrinsic component of the fundamental right to life under Article 21** — in a case specifically about digital KYC excluding blind, low-vision and acid-attack survivors from banking. **SEBI followed on 31 July 2025** by mandating digital accessibility across all regulated entities.

Financial software in India is now operating under a constitutional accessibility standard. Almost nothing in the consumer PFM space reflects that yet.

### 11.2 Conformance target

**WCAG 2.1 Level AA**, aligned with **IS 17802** and **GIGW 3.0** as referenced by RPwD Act 2016 §§40–46.

### 11.3 Concrete requirements

- Semantic landmarks (`header`, `nav`, `main`, `aside`), one `h1` per page, correct heading order
- Skip-to-content link as the first focusable element
- **Full keyboard operability** — every interactive element reachable and actuatable; visible focus indicator at ≥3:1 contrast; no keyboard traps; focus management on dialogs and drawers
- **Contrast ≥ 4.5:1** for text and ≥ 3:1 for UI components, verified in **both** light and dark themes
- **No colour-only encoding.** Every chart series carries a pattern or direct label in addition to colour; every status badge pairs colour with text
- **Table-view toggle on every chart** — `ChartWithTable` wrapper renders a properly-headed `<table>` alternative. This is the single highest-value accessibility feature for a data-heavy product and non-negotiable for every chart
- **`aria-live="polite"`** on the streaming agent response region so screen readers announce answers as they arrive; `aria-busy` during tool execution
- **Currency announced as words** — `aria-label="eighteen thousand four hundred rupees"` alongside the visual `₹18,400`, because screen readers mangle currency glyphs and grouped digits
- Form inputs with associated `<label>`, `aria-describedby` for hints, `aria-invalid` + `role="alert"` for errors
- `prefers-reduced-motion` respected on every transition and chart animation
- **200% text scaling** without loss of content or function — rem units throughout, no fixed-height containers around text
- Meaningful `alt` text on informative images; `alt=""` on decorative ones
- Language declared (`lang="en-IN"`, switching with the vernacular selector)

### 11.4 Verification

- **axe-core** automated pass in CI on every route — zero violations required
- Documented **manual NVDA pass** over the primary flow: login → upload → dashboard → ask a question → open a citation → Mandate Radar
- Keyboard-only walkthrough of the same flow

### 11.5 Accessibility Statement page

A real `/accessibility` page stating the conformance target, the standards applied, known limitations, the verification performed, and a contact route for accessibility feedback — citing RPwD Act 2016 §§40–46, *Pragya Prasun/Amar Jain* (30 Apr 2025), the SEBI circular (31 Jul 2025), WCAG 2.1 AA, IS 17802 and GIGW 3.0.

Publishing known limitations honestly is itself part of the standard.

---

## 12. Security & privacy

### 12.1 PII redaction — before every LLM call, without exception

`privacy/redact.py` runs on all text leaving the system:

| Pattern | Token |
|---|---|
| Account numbers (9–18 digits) | `<ACCT_n>` |
| IFSC codes (`^[A-Z]{4}0[A-Z0-9]{6}$`) | `<IFSC_n>` |
| Card PANs (13–19 digits, Luhn-valid) | `<CARD_n>` |
| UPI reference numbers (12 digits) | `<REF_n>` |
| Phone numbers (Indian formats) | `<PHONE_n>` |
| Email addresses | `<EMAIL_n>` |
| PAN (`^[A-Z]{5}[0-9]{4}[A-Z]$`) | `<PAN_n>` |
| Aadhaar (12 digits, Verhoeff-valid) | `<AADHAAR_n>` |
| Account-holder name | `<NAME>` |

Merchant names are deliberately **not** redacted — they are the signal the model needs. The redaction map lives in request scope only, reverse-mapped on render, never persisted. Every call writes an `ai_disclosures` row recording *which field types* were sent and how many tokens were redacted — never the values.

### 12.2 Other controls

- **Row-level security** on every Supabase table, keyed to `auth.uid()`
- Service-role key confined to the FastAPI service; never shipped to the browser or the extension
- Uploads validated by magic bytes, size-capped, stored in a private bucket with signed short-lived URLs
- PDF passwords held in memory only, never logged, never persisted
- API rate limiting on ingest and agent endpoints
- Extension holds a short-lived token and a budget snapshot only — **never transaction data**
- Secrets in environment variables; `.env` git-ignored; `.env.example` committed

---

## 13. Problem-statement coverage matrix

Every mandatory bullet, with the function and endpoint that satisfies it.

| # | PS requirement | Feature | Engine function | Endpoint |
|---|---|---|---|---|
| 1 | Upload statements, bills, expense records | Multi-format ingest with password handling | `ingest/pipeline.run()` | `POST /api/ingest` |
| 2 | Automatically categorise transactions | 3-tier hybrid categorisation | `enrich/categorize()` | auto on ingest · `PATCH /api/transactions/{id}/category` |
| 3 | Identify recurring payments and subscriptions | Mandate Radar | `engine/recurrence.detect()` | `GET /api/recurring` |
| 4 | Detect unusual spending patterns | Five anomaly types, robust statistics | `engine/anomaly.detect()` | `GET /api/anomalies` |
| 5 | Summarise monthly income and expenses | Dashboard + monthly summary | `engine/cashflow.monthly_summary()` | `GET /api/summary/{month}` |
| 6 | Identify upcoming recurring obligations | 30-day radar, 7-day alert | `engine/cashflow.upcoming()` | `GET /api/obligations?days=30` |
| 7 | Compare actual spending against budgets | Budget engine with pace verdict | `engine/budget.status()` | `GET /api/budgets/status` |
| 8 | Define financial goals | Goals CRUD | — | `POST /api/goals` |
| 9 | Analyse how spending affects goals | Goal projection + What-If Simulator | `engine/goals.project()` · `engine/simulate.simulate()` | `GET /api/goals/{id}/projection` · `POST /api/simulate` |
| 10 | Generate personalised spending insights | Insight cards + agent narration | `engine/*` + `agent/loop` | `GET /api/insights` |
| 11a | *"Where did I spend the most this month?"* | Agent tool | `get_category_breakdown` | `POST /api/agent/ask` |
| 11b | *"Which subscriptions am I paying for?"* | Agent tool | `list_recurring` | `POST /api/agent/ask` |
| 11c | *"What expenses increased vs last month?"* | Agent tool | `compare_periods` | `POST /api/agent/ask` |
| 11d | *"How much of my budget is already committed?"* | Agent tool | `get_safe_to_spend` | `POST /api/agent/ask` |
| 12 | Monthly summary with observations and action items | Opus-generated summary | `agent/summary.generate()` | `POST /api/summary/generate` |

All twelve are P0. None is deferred.

---

## 14. Roadmap — specified, not built in the 18-hour window

Included in the product as "Coming next" cards and shown in the video's closing seconds. Each is specified well enough to build immediately after the hackathon.

**Scheme Match** — infer eligibility signals from detected cash-flow (income band, presence or absence of an insurance debit, no pension contribution, dependants inferred from education spend) and match against a JSON rulebook covering PMJJBY (₹436/yr → ₹2L, ages 18–50), PMSBY (₹20/yr → ₹2L, ages 18–70), APY, SSY (8.2%), PPF (7.1%), NPS 80CCD(1B), and JanSamarth's 13 credit-linked schemes. Strictly framed: *"You appear to meet the stated eligibility. Verify with your bank."* Roughly 45 minutes of work — **the first item to pull forward if the build runs ahead of schedule.**

**Tax Regime Radar** — from detected debits (insurance premiums, ELSS SIPs, PPF, NPS, rent, home-loan EMI), compute the old-vs-new regime break-even for FY 2026-27 (new regime default, ₹75,000 standard deduction, ₹60,000 rebate → nil tax to ₹12L / ₹12.75L salaried). Shows the arithmetic and the break-even deduction figure, never a recommendation, with a verify-with-a-CA prompt. Deferred because it carries the highest advice-boundary risk and is the least demonstrable of the candidates.

**Full Bhashini voice** — complete ASR + TTS pipeline across 22 scheduled languages, replacing the Web Speech API. Combined with the §11 accessibility work this serves low-vision and low-literacy users through the same surface.

**Account Aggregator integration** — the natural end state. The consent artefact in §10.2 is already AA-shaped, so becoming an FIU is an integration rather than a redesign. Target: replace manual upload with consented, real-time FIP data.

**OCR for scanned statements** — scanned-image PDFs currently return a clear error rather than a bad parse.

---

## 15. Sustainability

A hackathon prototype should be able to answer "and then what?". FinPilot's path does not depend on speculative funding:

- **DPIIT Startup India Seed Fund Scheme** — up to ₹20 lakh for proof-of-concept and prototype development, up to ₹50 lakh for scale-up, through 300+ recognised incubators from a ₹945 crore corpus. Financial inclusion is a stated preference sector.
- **RBI Regulatory Sandbox** — moved to an **On-Tap** model in 2025, so there is no cohort window to wait for. FinPilot's AA-shaped consent architecture and DPDP-ready audit log make it sandbox-legible today.
- **NCFE / FEPA** — the National Centre for Financial Education, promoted by RBI, SEBI, IRDAI and PFRDA under the FSDC, runs 5,000+ adult financial-education programmes annually for farmers, SHGs, Anganwadi and ASHA workers. An accessible, vernacular, free tool is a distribution fit rather than a pitch.
- **Bhashini** — MeitY-funded language infrastructure, free to citizens, removes the cost of multilingual support entirely.
- **Account Aggregator ecosystem** — 1,020 live FIUs and 2.61 billion enabled accounts mean the data rails already exist. The roadmap is integration, not invention.

The through-line: every expansion path is a **public digital-infrastructure programme that is already funded and already operating**, which is what makes the plan credible rather than aspirational.

---

## 16. Non-goals

Stated explicitly so scope stays honest:

- **No investment, securities, insurance or tax advice.** Eligibility and arithmetic only. Enforced in code (§9.4).
- **No payment initiation.** FinPilot reads and analyses; it never moves money and never cancels a mandate on the user's behalf. The Revoke Kit tells you how; you do it.
- **No credit scoring or lending decisions.**
- **No real bank credential collection.** No screen-scraping, no net-banking passwords. Upload or (future) AA consent only.
- **No claim of universal bank coverage.** The UI names the adapter used and offers manual column mapping when confidence is low.
- **Not a production-hardened system.** It is a prototype with production-shaped architecture, and the README says so.

---

## 17. Demo & evaluation readiness

The submission form states that the evaluation team will test the agent **2–3 times**. That is a design input:

- **Pre-seeded demo account** with 14 months of data so the product is never empty on first load
- **"Reset demo data" button**, prominently placed — test run 1 must not pollute test runs 2 and 3
- **Guaranteed-good question set** documented in SUBMISSION.md so the evaluators' first queries land on well-covered ground
- **Graceful empty states** everywhere, with an obvious path to the demo data
- **No cold-start latency trap** — Render free tier sleeps; USER.md includes a keep-alive ping so the first judge request is not a 40-second spin-up

---

## 18. Open decisions

None. Design is frozen. Proceed to BUILD_TASKS.md.
