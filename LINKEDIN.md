# LINKEDIN.md — Raw Material

You're running LinkedIn yourself at 2 posts/day. This file is **material, not a campaign** — facts you can use, four drafts you can cut apart, and a shot list.

Use as much or as little as you want.

---

## The facts worth leading with

These carry on their own merit. Someone who has never heard of FinPilot will still stop for them — which is the whole point, since engagement is what's scored.

| Fact | Hook |
|---|---|
| Recurring debits up to **₹15,000** need no OTP under RBI's e-mandate framework (₹1 lakh for insurance, SIPs, credit-card bills) | "Your subscriptions now leave your account without asking you. That's not a bug — it's the rule." |
| Banks must send a pre-debit alert **24 hours** ahead | "24 hours' notice on money you forgot you'd committed. One SMS among forty." |
| **DPDP Rules 2025** notified 13 Nov 2025 — Phase 2 on **13 Nov 2026**, Phase 3 on **13 May 2027** | "Most Indian apps have 19 months to comply. Building it in now costs a weekend; retrofitting it costs a rewrite." |
| **Pragya Prasun v. Union of India** (30 Apr 2025): Supreme Court held digital accessibility is intrinsic to the **right to life under Article 21** — in a case about digital KYC excluding blind users from banking | "In April 2025 the Supreme Court made digital accessibility a fundamental right. The case was about banking. Almost no fintech has noticed." |
| **SEBI**, 31 Jul 2025: digital accessibility mandatory for all regulated entities | "It's not aspirational any more. It's a circular." |
| Account Aggregator: **2.61 billion** accounts enabled, 1,020 live FIUs, Sahamati made SRO 5 Jun 2026 | "India built consent-based financial data sharing at a scale nobody else has. Most people have never heard of it." |
| **PMSBY**: ₹20/year → ₹2 lakh accident cover. **PMJJBY**: ₹436/year → ₹2 lakh life cover | "₹456 a year buys ₹4 lakh of government insurance cover. Most people paying ₹499/month for streaming don't have it." |
| **Bhashini** (MeitY): free ASR/TTS/translation across 22 scheduled languages | "The government built free language AI infrastructure and most developers don't know it exists." |

Every one of these is verified with a date in `DESIGN.md` §3. Don't post a number you can't point at.

---

## Four drafts

Cut them up, rewrite in your voice, ignore them entirely. They're a starting point.

### Day 1 morning — the hook

> Under RBI's e-mandate framework, any recurring debit up to ₹15,000 goes through without an OTP.
>
> No confirmation. No tap. The money just leaves.
>
> For insurance premiums, SIPs and credit card bills, that ceiling is ₹1 lakh.
>
> Banks are required to send a pre-debit alert 24 hours ahead — one SMS, competing with forty others, about money you agreed to six months ago and forgot.
>
> That's not a scandal. It's the rails working as designed, and it's why auto-debit is convenient.
>
> But it means most of us have no idea what's committed until it's gone.
>
> I'm building something about that this weekend. 48 hours.
>
> #fintech #RBI #buildinpublic

### Day 1 evening — the technical opinion

> The problem with LLMs and money isn't that they're bad at arithmetic.
>
> It's that they're *confidently* bad at it, and financial software has no tolerance for a number that's 4% wrong.
>
> So in what I'm building, the model doesn't do arithmetic at all.
>
> A Python engine computes — recurrence detection, anomaly detection, cash-flow projection, goal ETAs — all of it unit-tested. The model gets tool access to that engine and its only job is to explain the result.
>
> Every tool returns data *plus the transaction IDs behind it*. Every number in the UI is clickable, down to the exact rows that sum to it.
>
> If the model states a figure it can't cite, that's structurally visible.
>
> There's also a golden-answer eval suite that asserts the number the agent cited equals the number the engine computed.
>
> "AI-powered" should mean the AI is doing the part it's good at.
>
> #AI #LLM #fintech

### Day 2 morning — the one most people won't know

> On 30 April 2025, the Supreme Court held that digital accessibility is an intrinsic part of the right to life under Article 21.
>
> Pragya Prasun v. Union of India. The case was about digital KYC — blind users and acid-attack survivors being locked out of opening bank accounts because the process required them to blink at a camera or read a code they couldn't see.
>
> SEBI followed on 31 July 2025, mandating digital accessibility across every regulated entity.
>
> Indian financial software now operates under a constitutional accessibility standard.
>
> I'd guess most people building in this space don't know that yet. I didn't, two days ago.
>
> So the thing I'm building is WCAG 2.1 AA: full keyboard operation, a table view behind every chart, currency announced as words instead of glyphs, no meaning carried by colour alone.
>
> Built in from the first commit, it costs almost nothing. Retrofitted, it's roughly a 5x job.
>
> That asymmetry is the whole argument.
>
> #accessibility #a11y #fintech #RPwD

### Day 2 evening — the demo

> FinPilot. Built in 18 hours.
>
> Upload a bank statement — password-protected PDFs included. It parses, categorises, and finds every recurring payment.
>
> Then it tells you the things nobody tells you:
>
> → Which auto-debits will fire silently (under ₹15,000 = no OTP, per RBI)
> → Which subscription quietly went up 18%
> → That you're paying for two music services
> → What's actually committed before your next salary
> → And if you cancel these three, your emergency fund arrives in March instead of July
>
> Every number is clickable down to the transactions behind it. The model never does arithmetic — a tested Python engine does, and the model explains.
>
> There's a browser extension that catches you at the Amazon checkout and tells you what the purchase costs you in months of delay on your goals.
>
> Every AI call is logged with exactly which fields left your device. Account numbers never do. Erase and export actually work — built against DPDP Rules 2025, whose main deadline is May 2027.
>
> And it's WCAG 2.1 AA throughout.
>
> [video]
>
> #buildinpublic #fintech #AI

---

## Shot list

What to capture while building — you won't want to go back for these at hour 17.

| Shot | When | Why it works |
|---|---|---|
| **Leak Score gauge** | after T09 | One number, instantly legible, screenshot-native |
| **Mandate Radar with badges** | after T11 | `SILENT` / `PRICE UP 18%` / `DUPLICATE` in one frame tells the whole story |
| **Citation drawer open** | after T10 | The proof shot for the anti-hallucination claim |
| **Simulator before/after** | after T11 | March → July. Causal and concrete |
| **Extension interstitial on real Amazon** | after T13 | The most arresting single image in the whole build |
| **Data Vault disclosure log** | after T11 | Shows redaction tokens where account numbers would be |
| **Terminal: `pytest` green** | after T06 | Credibility with technical readers |
| **axe-core: 0 violations** | after T15 | Pairs with the Article 21 post |

---

## Don't

- Don't post a number you can't source. Every fact above has a date in `DESIGN.md` §3.
- Don't call it financial advice, or imply it gives any. The product doesn't, and saying otherwise is both wrong and a regulatory own-goal.
- Don't claim universal bank support. Two PDF adapters plus generic CSV plus an LLM fallback. Say that.
- Don't say the extension is on the Chrome Web Store. It isn't — review takes days.
- Don't imply DPDP compliance is certified. It's *designed against* the Rules. Different claim.
