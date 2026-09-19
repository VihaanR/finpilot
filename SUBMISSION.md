# SUBMISSION.md — Video, Form, and Judge Readiness

---

## 1. The 3-minute video

Mandatory deliverable. Three minutes is **short** — that's roughly 450 spoken words. Every second of dead air is a second not spent on a feature.

### Principles

- **Show working software.** No mockups, no slides beyond a title card, no sped-up fake typing. Judges can tell.
- **Lead with the fact, not the pitch.** "Your auto-debits now fire without asking you" beats "FinPilot is an AI-powered platform."
- **The citation click is the most important two seconds in the video.** It is the visible proof that the numbers are real.
- **Record against localhost** if Render is sluggish. Keep production live separately for the judges.

### Timed script

| Time | On screen | Say |
|---|---|---|
| **0:00–0:20** | Title card → dashboard | "Under RBI's e-mandate framework, any recurring debit up to fifteen thousand rupees goes through with no OTP. No confirmation. Most people's subscriptions and auto-debits now leave their account silently. FinPilot is a finance agent built around that problem." |
| **0:20–0:50** | Drag a statement in, progress runs, dashboard fills | "Upload a bank statement — password-protected PDFs included. It parses, categorises, and detects recurring payments automatically. That's real parsing, not a fixture." |
| **0:50–1:20** | Chat: ask three questions, then **click a number** | "Ask it anything. Where did I spend the most? Which subscriptions am I paying for? What went up since last month? And here's the part that matters — *click*. Every number is clickable, down to the exact transactions behind it. The language model never does arithmetic. A Python engine computes; the model only explains. That's why it can't hallucinate a figure." |
| **1:20–1:50** | Mandate Radar, badges visible | "Mandate Radar. Nine recurring payments found. This one's tagged Silent — under fifteen thousand, so it'll debit without asking. This one went up eighteen percent and nobody told you. These two are duplicate music subscriptions. RBI requires a twenty-four hour warning. We give you seven days — and the exact steps to cancel." |
| **1:50–2:20** | Simulator: toggle subscriptions, ETA moves | "Goals connect to spending. Cancel these three, cut food delivery thirty percent — and the emergency fund lands in March instead of July. That's computed from the actual ledger, not estimated." |
| **2:20–2:40** | Switch to Amazon, cart, interstitial fires | "It follows you to checkout. Budget Guard is a browser extension — this twelve-thousand-rupee purchase would push the emergency fund out by three months. Continue, or wait twenty-four hours." |
| **2:40–3:00** | Data Vault → accessibility page | "Every AI call is logged with exactly what left your device — account numbers never do. Erase and export actually work, built against DPDP Rules 2025. And the whole thing is WCAG 2.1 AA, because in April 2025 the Supreme Court held that digital accessibility is part of Article 21 — in a case about banking. FinPilot." |

**Word count ≈ 430.** Speak at a normal pace; do not rush to fit more in.

### If you're over time

Cut in this order: the extension beat (0:20) → the third chat question (0:08) → tighten the upload narration (0:10). Never cut the citation click or Mandate Radar.

### Recording checklist

- [ ] Reset demo data first — clean known state
- [ ] 1920×1080, browser zoom 100%, no bookmarks bar
- [ ] Notifications off (Windows Focus Assist)
- [ ] Amazon cart pre-loaded in tab 2
- [ ] One silent dry run to find the dead air
- [ ] Mic levels tested
- [ ] Upload → Drive → **Share → Anyone with the link → Viewer**
- [ ] **Open the link in incognito to verify** ← most common submission failure

---

## 2. Submission form — field by field

### Team Name *(required)*
`________________` — fill in.

### Video Demo Link *(required)*
Google Drive link. **Sharing verified in an incognito window.**

### Agent Access Link
Your Vercel URL, e.g. `https://finpilot.vercel.app`

Before pasting it: open it in a fresh incognito window and confirm the login page loads in under three seconds. If Render is cold, your keep-alive ping isn't running (USER.md §8b).

### Agent Credentials
```
Username: demo@finpilot.in
Password: FinPilot@2026

Pre-loaded with 14 months of sample data. A "Reset demo data" button
on the dashboard restores a clean state between test runs.
```

The reset note matters — the form says the team will test 2–3 times, and it tells them their runs won't interfere with each other.

### Additional Materials

```
GitHub (full source, MIT): https://github.com/<you>/FinPilot

DESIGN.md — complete architecture: deterministic analytics engine,
tool-calling agent with mandatory citations, PII redaction before every
LLM call, and the regulatory basis for each India-specific feature.

n8n/finpilot-workflows.json — 4 workflows: Telegram ingestion and Q&A,
daily brief, mandate alerts, monthly summary.

apps/extension — "Budget Guard", an MV3 Chrome extension that intercepts
over-budget checkouts on Amazon and Flipkart. Load unpacked (install
instructions in USER.md); not Web Store published within the hackathon window.

/accessibility — WCAG 2.1 AA conformance statement. Built to RPwD Act 2016
and the Supreme Court's ruling in Pragya Prasun v. Union of India
(30 Apr 2025) that digital accessibility is intrinsic to Article 21.

Note: FinPilot provides no investment, tax or financial advice. It surfaces
the user's own data and arithmetic only — a constraint enforced in code.
```

---

## 3. Judge test-script

The evaluation team will test 2–3 times. These five queries are guaranteed to work against the seeded demo data. Put them as **suggested-question chips in the chat UI** so the judges' first interaction lands well without them having to guess.

| # | Question | What it proves |
|---|---|---|
| 1 | *"Where did I spend the most this month?"* | Categorisation + citations. Clicking the figure opens the transactions |
| 2 | *"Which subscriptions am I paying for?"* | Recurrence detection. Returns 9, flags the duplicate pair |
| 3 | *"What expenses increased compared with last month?"* | Period comparison with per-category deltas |
| 4 | *"How much of my budget is already committed?"* | Safe-to-Spend — the literal PS question |
| 5 | *"If I cancel Spotify and Gaana, when do I hit my emergency fund goal?"* | Scenario simulation with a computed ETA shift |

**Also worth them finding** (surface as dashboard cards, don't rely on them asking):
- The Leak Score gauge
- The price-hike badge on Mandate Radar
- The Data Vault's AI disclosure log
- Category override → "Learned — 14 past transactions updated"

**A question that should fail well:** *"Should I invest in mutual funds?"* → scripted decline that pivots to data. If a judge tries to break the advice boundary, the refusal is the feature.

---

## 4. Optional PPT — 8 slides

Only if you have spare time after the video. The video carries more weight.

| # | Slide | Content |
|---|---|---|
| 1 | Title | FinPilot · team · one line: "A finance agent that can't hallucinate a number" |
| 2 | The problem | Three consequences from DESIGN.md §1, plus the ₹15,000 silent-debit fact |
| 3 | Architecture | The diagram from DESIGN.md §4 |
| 4 | AI integration | Deterministic engine + tool-calling agent + mandatory citations + redaction + eval harness. The "LLM never does arithmetic" claim |
| 5 | Mandate Radar | Screenshot with badges; RBI thresholds; "7 days where the rule gives you 1" |
| 6 | Privacy & accessibility | DPDP timeline (Phase 2 Nov 2026, Phase 3 May 2027) · Article 21 · WCAG 2.1 AA |
| 7 | PS coverage | The §13 matrix — all 12 requirements, each with a named function |
| 8 | Sustainability | SISFS · RBI On-Tap Sandbox · NCFE/FEPA · Bhashini · AA roadmap |

---

## 5. Pre-submission final check

**Product**
- [ ] Vercel URL loads in fresh incognito in < 3 seconds
- [ ] Demo credentials log in successfully
- [ ] Dashboard is populated, not empty
- [ ] All five judge-script questions answer correctly **in production**
- [ ] A citation click opens the transaction drawer
- [ ] Reset demo data works
- [ ] Keep-alive ping running

**Code**
- [ ] Repo public, README present
- [ ] No secrets in the repo (`git log -p | Select-String "sk-ant|eyJ|service_role"`)
- [ ] n8n export secret-scanned
- [ ] `pytest services/api/tests/` green
- [ ] axe-core zero violations

**Submission**
- [ ] Video under 3:00
- [ ] Drive sharing verified **in incognito**
- [ ] Every form field filled
- [ ] Additional Materials text pasted in full

---

## 6. What to say if asked a hard question

**"How do you know the AI isn't making up numbers?"**
It structurally can't state an uncited figure. Every tool returns data plus the transaction IDs behind it, the model is required to attach a citation to every number, and the UI renders each one clickable. The arithmetic is Python with unit tests — the model only narrates. There's also a golden-answer eval suite that asserts the cited figure equals the engine's figure.

**"What happens with a bank you don't support?"**
Generic CSV path plus an LLM structured-extraction fallback, and the UI tells you which adapter parsed your file and with what confidence. We ship two real PDF adapters rather than claiming universal coverage, because claiming it would be false and you'd find out in one upload.

**"Isn't this financial advice?"**
No, and that's enforced in code, not disclaimed in a footer. It surfaces your own data and arithmetic. Recommendation requests hit a scripted decline that pivots to showing you the numbers. Scheme eligibility is phrased as "you appear to meet the stated criteria — verify with your bank," never "you should enrol."

**"Why does accessibility matter for a hackathon prototype?"**
Because in April 2025 the Supreme Court held digital accessibility is intrinsic to Article 21 — in a case about digital KYC excluding blind users from banking — and SEBI mandated it across regulated entities that July. Indian financial software now operates under a constitutional accessibility standard. Building it in from hour one costs almost nothing; retrofitting costs about five times as much.

**"What's the business model?"**
Every expansion path runs through public digital infrastructure that's already funded and operating: DPIIT's SISFS for capital, RBI's On-Tap Regulatory Sandbox for testing, NCFE's 5,000-programme-a-year financial literacy network for distribution, Bhashini for free multilingual support, and the Account Aggregator rails to replace manual uploads. Our consent artefact is already AA-shaped, so becoming an FIU is an integration, not a redesign.
