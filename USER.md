# USER.md — What You Personally Have To Do

Everything in this file requires a human. The coding agents cannot create accounts, click OAuth consent screens, scan QR codes, or record a video.

**Read the "Do this before" column and front-load the blocking items.** Several take minutes of waiting, and a key you don't have at hour 4 stalls the whole build.

---

## 0. The critical path — do these first, in this order

| # | Action | Blocks | Time | Do before |
|---|---|---|---|---|
| 1 | Groq API key (free) | T07 — chat and monthly summary | 2 min | **Hour 0** |
| 1b | Gemini API key (free) | T05 — bulk categorisation, embeddings, PDF fallback | 3 min | **Hour 0** |
| 2 | Supabase project | T02 — everything | 10 min | **Hour 0** |
| 3 | GitHub repo | commits | 2 min | **Hour 0** |
| 4 | Telegram bot token | T14 | 3 min | Hour 13 |
| 5 | Vercel account | T12 | 5 min | Hour 11 |
| 6 | Render account | T12 | 5 min | Hour 11 |
| 7 | n8n via Docker | T14 | 10 min | Hour 13 |
| 8 | Bhashini registration *(optional)* | vernacular summary | 15 min | Hour 13 |

Items 1–3 are hard blockers. Do them before you start anything else. Items 4–8 can wait but must not be discovered late.

---

## 1. Groq API key — Hour 0

Chat and the monthly summary run on Groq, switched 20 Sep 2026 after the
Gemini free tier's 20-requests/day cap ran out mid-demo-prep. Gemini's daily
cap is per Cloud project and a consumer Google AI plan does not raise it (see
§1b below) — Groq's free tier is rate-limited per minute instead, which is
what actually fixes the problem you'll hit if you only have a Gemini key.

1. Go to `console.groq.com/keys` → sign in → **Create API Key** → copy it
2. No card required. The free tier covers this build.

→ `GROQ_API_KEY=gsk_...`

Set both `GROQ_API_KEY` locally in `services/api/.env` **and** on Render
(Environment tab) if the API is already deployed — chat will keep returning
"Chat needs a Groq API key" until both are set.

## 1b. Gemini API key — Hour 0

Still needed: bulk categorisation (T05 tier-2), the PDF LLM-fallback adapter,
and embeddings all stay on Gemini — none of them share Groq's rate limits or
this switch's motivation.

1. Go to `aistudio.google.com/apikey` → sign in with your Google account
2. **Create API key** → pick or create a Cloud project → copy it
3. No card and no billing setup required. The free tier covers this build.

→ `GEMINI_API_KEY=AIza...`

### The one thing to be clear about

**A consumer Google AI Plus / Pro / Ultra subscription does not raise your API
rate limits.** Those plans cover the Gemini *app* at `gemini.google.com`. The
API has its own quota, applied **per Cloud project**, and the only documented
way to lift it is enabling billing on that project to reach Tier 1. If you hold
a Plus plan, you are still on the API free tier here.

That is fine — the build is designed for it:

- Tier-1 deterministic rules classify ~75% of transactions with **zero** API calls
- Tier-2 results are cached by `sha256(normalized_narration)`, so each unique
  narration shape costs exactly **one** call for the life of the deployment
- Classifying the entire 14-month seed dataset is roughly **19 calls**

**Measured 20 Sep 2026, against your actual key.** The limit that bites is
**per day, per model**, not per minute:

| Model | Free-tier limit | Usable? |
|---|---|---|
| `gemini-3.5-flash-lite` | 5/min and 20/day | yes — bulk classification, PDF fallback |
| `gemini-3.5-flash` | 5/min and 20/day | yes, but nothing here calls it any more |
| any Gemini **Pro** model | **0 per day** | no, needs billing |

`gemini-2.5-pro` additionally returns 404, "no longer available to new users".

**This no longer bounds the demo.** Chat and the monthly summary moved to
Groq (§1) specifically because this table used to gate them — Gemini's role
now is tier-2 categorisation (cached by narration hash, ~19 calls for the
whole seed dataset — see above) and the PDF fallback, neither of which a
judge triggers by asking questions. If tier-2 ever does hit the wall, the
contingency below still applies to it.

Check your own at `aistudio.google.com/rate-limit`.

**If you do hit the limit**, the contingency is already in BUILD_TASKS.md: drop
tier-2 categorisation to on-demand instead of bulk-on-ingest. Tier 1 alone
still covers the large majority, so the product degrades rather than breaks.

---

## 2. Supabase project — Hour 0

1. `supabase.com` → **New project**
2. Name `finpilot`, generate and **save the database password** — you cannot recover it later
3. Region: **Mumbai (ap-south-1)** if available. Relevant to the DPDP data-residency story, not just latency
4. Wait ~2 minutes for provisioning
5. **Settings → API**, copy:
   - Project URL → `SUPABASE_URL`
   - `anon` `public` key → `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `service_role` `secret` key → `SUPABASE_SERVICE_KEY`
6. **Database → Extensions**, enable **`vector`**
7. **Storage → New bucket** named `documents`, **Private** (not public — these are people's bank statements)

> ⚠️ The `service_role` key bypasses row-level security. It goes in the FastAPI environment **only**. It must never appear in `apps/web`, never in a `NEXT_PUBLIC_*` variable, and never in the extension.

---

## 3. GitHub repo — Hour 0

```powershell
cd V:\Projects\FinPilot
git init
git add .
git commit -m "FinPilot: design documents"
gh repo create FinPilot --public --source=. --push
```

Public matters here: the repo is a submission artefact, and the browser extension is distributed from it.

Before pushing, confirm `.gitignore` covers `.env`, `.env.local`, `node_modules/`, `__pycache__/`, `.venv/`, `*.pdf`, `seed/output/`.

---

## 4. Environment files

### `apps/web/.env.local`

```bash
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=http://localhost:8000        # → Render URL at T12
```

### `services/api/.env`

```bash
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...                      # service_role — server only
SUPABASE_ANON_KEY=eyJ...
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres
ALLOWED_ORIGINS=http://localhost:3000            # + Vercel URL at T12
BHASHINI_USER_ID=                                # optional
BHASHINI_API_KEY=                                # optional
TELEGRAM_BOT_TOKEN=                              # filled at hour 13
INTERNAL_API_TOKEN=                              # generate: see below
```

Generate the internal token (used by n8n and the extension to call the API):

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Never commit either file.** `.env.example` (committed) mirrors them with empty values.

---

## 5. Telegram bot — Hour 13 (before T14)

1. Open Telegram, search **@BotFather**
2. `/newbot` → name `FinPilot` → username `finpilot_<something>_bot` (must be globally unique and end in `bot`)
3. Copy the token → `TELEGRAM_BOT_TOKEN` (set in `services/api/.env`, never here — this file is a tracked, public-repo document)
4. `/setdescription` → *"AI-powered personal finance assistant that gives money-smart guidance. Send a bank statement or ask a question."*
5. Message your own bot once so it can message you back — Telegram bots cannot initiate conversations. This also gives you your own chat id: check `https://api.telegram.org/bot<token>/getUpdates` after messaging it, and look for `message.chat.id` — you need this for step 6 below.

The daily brief, mandate alert and monthly summary run **on their own
schedule** (08:00 / 09:00 / 1st-of-month IST), not on a typed command —
`/setcommands` was dropped from this list because nothing in the built
workflows listens for a `/brief`-style command; sending the bot a document
or a plain-English question is what it actually responds to on demand.

Takes about three minutes. This is why we chose Telegram over WhatsApp: the WhatsApp Business API needs Meta app review measured in days, which does not fit a 48-hour window.

---

## 6. n8n — Hour 13 (before T14)

**Requires Docker Desktop running.**

```powershell
docker run -d --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
```

Open `http://localhost:5678`, create the local owner account (local only, no cloud signup needed).

### Import the workflows

**Read `n8n/README.md` first.** The committed `finpilot-workflows.json` was
hand-authored against n8n's node schema (`n8n/generate_workflows.py`), not
built in n8n's own editor and exported — Docker wasn't available in the
session that built T14, so none of this has actually been imported or run
against a live bot yet. Everything below is what closes that gap.

1. **Workflows → Import from File** → `n8n/finpilot-workflows.json` — imports all three at once
2. **Credentials → Add credential → Telegram API** → paste the bot token → name it exactly **`Telegram Bot`**
3. **Credentials → Add credential → Header Auth** → Name: `Authorization`, Value: `Bearer <INTERNAL_API_TOKEN>` (any value works today — this API has no auth enforced yet, §8e) → name it exactly **`FinPilot API`**
4. The API base URL is already baked into each HTTP node as your Render URL — no separate variable to set, but double-check it if you're testing against localhost instead
5. Open the **Daily brief**, **Mandate alert** and **Monthly summary** workflows and replace `REPLACE_WITH_YOUR_TELEGRAM_CHAT_ID` in each one's Telegram node with your own chat id (message your bot once, then check `https://api.telegram.org/bot<token>/getUpdates` for `message.chat.id`) — every workflow here is schedule-triggered, so none of them has an inbound message to infer it from
6. **Activate** all three workflows

> The credential names must match exactly. The exported JSON references credentials by name; a mismatch causes silent no-ops rather than visible errors.
>
> This bot is intentionally one-way: it pushes the daily brief, mandate
> alerts and the monthly summary to your Telegram chat, and does not accept
> or act on anything sent to it. The design originally had a fourth,
> two-way workflow for that; it was dropped on request (BUILD_TASKS.md T14,
> DESIGN.md §10.6).

Test each acceptance criterion from BUILD_TASKS.md T14 by hand: use "Execute
Workflow" on each of the three workflows to trigger it without waiting for
its schedule, and confirm the message arrives in Telegram.

### Re-export for submission

After everything works: **Workflows → Select all → Download**. Save over `n8n/finpilot-workflows.json`.

**Then open the file and confirm no credential values are inside it.** n8n usually strips them, but verify — you are about to make this public:

```powershell
Select-String -Path n8n\finpilot-workflows.json -Pattern "sk-ant|eyJ|bot[0-9]{8,}|service_role"
```

No output means you're clean.

### If n8n eats time

It is a P1 deliverable. If it fights you for more than 45 minutes, ship without it — the n8n JSON is optional on the submission form. Do not let it threaten T12.

---

## 7. Browser extension — Hour 14.5 (after T13)

No build step — it's plain JS/CSS/JSON, loads directly. Full detail in
`extension/README.md`; the short version:

1. `chrome://extensions`
2. Toggle **Developer mode** on (top right)
3. **Load unpacked** → select `V:\Projects\FinPilot\extension`
4. Pin it to the toolbar (puzzle icon → pin) so it's visible when you record
5. Open the popup — it should show a discretionary-budget figure within a
   few seconds, fetched live from production. Nothing to log into: this
   build's API has no auth (§8e), so the extension fetches
   `/api/dashboard` directly rather than needing the web app to hand it a
   snapshot on login (a deliberate simplification over the original
   DESIGN.md §10.5 mechanism — see `extension/README.md`).

**Test before recording — this is the one thing not yet verified.** Open
`amazon.in`, add something above your remaining discretionary budget, go to
the cart. The interstitial should appear. Everything else about the
extension (manifest loads cleanly, the cart-total parser, the ₹-numeric
fallback heuristic, the interstitial's accessibility contract) was verified
against fixture pages in `extension/test-fixtures/` during the build — a
real Amazon or Flipkart cart is the one thing that needed a human account
and couldn't be checked automatically.

> Not published to the Chrome Web Store — review takes days and we have 48 hours. This is a deliberate, stated choice, not an oversight. It does **not** go in the Agent Access Link field; it goes in Additional Materials as a GitHub link with these install instructions.

---

## 8. Deployment — Hour 12.5 (T12)

### 8a. Supabase migrations — **already done, 20 Sep 2026**

Applied over `DATABASE_URL` with psycopg: 14 tables, `categories` = 42 rows,
RLS on and enforced, `pgvector` enabled. Nothing to do here.

Note the app does **not** read Supabase yet — the API still uses its offline
SQLite store (§8e). The schema is ready for when it does.

### 8b. Render — FastAPI

1. `render.com` → **New → Web Service** → connect the GitHub repo
2. Root directory: `services/api`
3. Build: `pip install -r requirements.txt`
4. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Instance: **Free**
6. **Environment** → add every variable from `services/api/.env`
7. Deploy, wait ~3 minutes, then confirm `https://<your-service>.onrender.com/health` returns `{"status":"ok"}`

> **The Python version is the one thing that will break this build.**
>
> `render.yaml` sets `PYTHON_VERSION`, but **that file only applies to
> Blueprint deploys**. A service created by hand through the dashboard — which
> is what the steps above do — never reads it, so Render falls back to its
> current default. On 20 Sep 2026 that default was **Python 3.14**, and the
> build died on `psycopg-binary==3.2.3`: there are no 3.14 wheels for it, and
> it is binary-only so there is no source fallback. `numpy==2.2.1` would have
> failed next for the same reason. The error names psycopg and looks like a
> bad pin; the actual cause is the interpreter, visible only as `cp314` in the
> wheel filenames scrolling past.
>
> `services/api/.python-version` now pins **3.11.13**, which Render reads from
> the service's root directory regardless of how the service was created. If
> Render rejects that exact patch release, set the **`PYTHON_VERSION`**
> environment variable in the dashboard to `3.11` and redeploy.
>
> Do not "fix" this by unpinning psycopg. The pins are consistent with 3.11;
> chasing them one at a time onto a newer interpreter is a much longer
> afternoon than pinning the interpreter once.

**Free tier sleeps after 15 minutes of inactivity and takes ~40 seconds to wake.** A judge hitting a cold start will assume the product is broken. Fix it:

- `cron-job.org` (free) → new job → your `/health` URL → every 10 minutes
- Do this **at T12**, not later. It needs to already be warm when judging starts.

### 8c. Vercel — Next.js

1. `vercel.com` → **Add New → Project** → import the repo
2. Root directory: `apps/web` — this matters twice: Vercel also reads
   `vercel.json` from here, which is why that file lives in `apps/web/` and
   not at the repo root. At the root it would be silently ignored and the
   security headers would never apply.
3. Framework preset: Next.js (auto-detected)
4. **Environment Variables** → the three from `.env.local`, with
   `NEXT_PUBLIC_API_URL` set to the Render URL
5. Deploy

> **`NEXT_PUBLIC_*` is baked in at build time, not read at runtime.** If you
> change `NEXT_PUBLIC_API_URL` later you must **redeploy**, not just restart —
> a restart keeps the old URL compiled into the bundle.

> **Two-pass ordering.** Render needs `ALLOWED_ORIGINS` to contain the Vercel
> URL, and Vercel needs `NEXT_PUBLIC_API_URL` to contain the Render URL, so
> neither can be fully configured first. Deploy Render, copy its URL into
> Vercel, deploy Vercel, then come back and set `ALLOWED_ORIGINS` on Render to
> the Vercel URL. Skipping the last step gives you a site that loads and shows
> nothing, with only a CORS error in the browser console to explain why.

### 8d. Close the loop

- Add the Vercel URL to `ALLOWED_ORIGINS` on Render and redeploy (see the
  two-pass note in §8c — this is the step everyone forgets)
- Confirm `https://<render>.onrender.com/health` → `{"status":"ok"}`
- Open the Vercel URL in a fresh incognito window: the dashboard should be
  populated with no login and no manual step
- ~~Supabase → Authentication → URL Configuration~~ — not applicable, this
  build has no auth (§8e)

### 8e. The demo data — and the login that does not exist

**There is no authentication in this build.** No login page, no Supabase auth
wiring, no session. The public URL opens straight onto a populated dashboard.

That is a deliberate deviation from BUILD_TASKS.md T12, which asks for a
`demo@finpilot.in` account. Building auth on the last day would risk a working
product for a login screen that stands between a judge and the thing being
judged. **Do not create the demo account** — there is nothing to log into.

Two consequences to know about:

- **The API is open.** Anyone with the Render URL can read the demo ledger,
  spend your Groq/Gemini quota, and call `POST /api/vault/erase` with
  `{"confirm":"DELETE"}` to wipe it. The app self-heals: the free tier sleeps
  after 15 minutes, and startup re-seeds an empty store. The **Reset demo
  data** button fixes it immediately.
- **The store is SQLite on Render's ephemeral disk.** It is re-seeded on every
  cold start, so the demo is always clean and never accumulates. Uploads a
  judge makes do not survive a restart. For a demo this is a feature; it is
  not production persistence, and the Supabase schema (already applied) is
  where that would go.

## 9. Bhashini *(optional, hour 13+)*

Only if you're ahead of schedule. The vernacular summary works without it via the Web Speech API.

1. `bhashini.gov.in` → **Sign Up** (ULCA / Bhashini developer portal)
2. Create an app → get `userID` and `ulcaApiKey`
3. Call the pipeline-config endpoint to discover the `serviceId` for the translation task and your target language pair
4. Add both to `services/api/.env`

**Step 3 is the time sink** — service-ID discovery is under-documented and fiddly. Timebox it to 20 minutes. If it resists, skip it: it's a roadmap item in DESIGN.md §14 and the demo works without it.

---

## 10. Recording the video — Hour 16

Full timed script in `SUBMISSION.md`. Setup checklist:

**Before recording**
- [ ] Close Slack, email, notifications — Windows Focus Assist on
- [ ] Browser: new window, one tab, no bookmarks bar, no extensions visible except Budget Guard
- [ ] Reset demo data so the dashboard is in a known clean state
- [ ] Screen resolution 1920×1080; browser zoom at 100%
- [ ] Have the Amazon cart pre-loaded in a second tab so the extension beat doesn't stall
- [ ] Do one full silent dry run — find the dead air before you're recording

**Recording**
- OBS Studio (free) or Loom. 1080p, 30fps
- Record system audio + mic; test mic levels first
- **Keep it under 3:00.** Over-length is a scoring risk on a rubric that specifies three minutes

**After**
- Upload to Google Drive
- **Right-click → Share → "Anyone with the link" → Viewer**
- **Open the link in an incognito window to verify.** The single most common submission failure is a video nobody but the author can open

---

## 11. Submission form

Field-by-field answers in `SUBMISSION.md`. Summary:

| Field | Value |
|---|---|
| Team Name | *(yours)* |
| Video Demo Link | Google Drive link, sharing verified in incognito |
| Agent Access Link | Vercel URL |
| Agent Credentials | `Username: demo@finpilot.in Password: FinPilot@2026` |
| Additional Materials | GitHub repo · n8n JSON · DESIGN.md · accessibility statement |

---

## 12. After evaluation

The form says: *"Remember to disable them after evaluation."*

Once results are announced:
1. Supabase → **Authentication → Users** → delete or disable `demo@finpilot.in`
2. Rotate `GROQ_API_KEY` at `console.groq.com/keys` and `GEMINI_API_KEY` at `aistudio.google.com/apikey` if the repo is public and anything leaked
3. Delete the cron-job.org keep-alive so Render stops burning free hours

---

## 13. Your parallel track while the agents build

You are not idle during the 18 hours. In rough order:

| Hour | You |
|---|---|
| 0 | Keys and accounts (§1–3). Then **LinkedIn post 1** |
| 1–4 | Watch T03/T04 output. Sanity-check that seeded narrations look like real Indian bank narrations — you know what yours look like; the agent is guessing |
| 5–7 | **This is the highest-risk window (T06).** Read the engine tests as they land. If recurrence detection is wrong, everything downstream is confidently wrong |
| 8 | **LinkedIn post 2** |
| 9–12 | Click through the UI as it appears. You will catch UX problems the agent cannot see |
| 12.5 | **Be present for T12.** Deployment always has a human step |
| 13–15 | **LinkedIn post 3.** Test the extension on real Amazon/Flipkart pages |
| 16–18 | Video, form, **LinkedIn post 4** |

The two moments where your attention is worth most: **hour 5–7** (engine correctness) and **hour 12.5** (deployment). Everything else can be reviewed after the fact.

---

## 14. Things that will go wrong

| Symptom | Cause | Fix |
|---|---|---|
| Judge sees a 40-second load | Render cold start | Keep-alive ping (§8b). Set it up at T12 |
| Video link won't open | Drive sharing left on "Restricted" | Verify in incognito |
| Dashboard empty for judges | Demo seed didn't reach production | Re-run §8e, verify in incognito |
| Second judge sees first judge's mess | No reset | Reset demo data button (T12 criteria) |
| CORS errors after deploy | Vercel URL missing from `ALLOWED_ORIGINS` | §8d |
| Auth redirect loop | Vercel URL missing from Supabase URL config | §8d |
| Extension does nothing | Not logged into the web app in that browser | Log in; the app writes the snapshot |
| Chat says "used up the Groq free-tier quota" | Groq's rate limit, not Gemini's | Wait for the window to clear, or switch `GROQ_MODEL_CHAT` |
| Gemini 429s during ingest/upload | Tier-2 categorisation's **daily** cap for that model, not a per-minute one | Switch `GEMINI_MODEL_CLASSIFY` in `services/api/.env` (each model has its own daily bucket), or enable billing (§1b) |
| Expected Plus plan to lift API limits | Consumer subscriptions do not apply to the API | §1b — enable project billing for Tier 1, or stay on free |
| n8n workflows silently no-op | Credential names don't match exactly | §6, step 2–3 |
| Money figures slightly off | A float crept into a currency path | `grep` for float in engine; paise are integers (DESIGN.md §5.1) |

---

## 15. One-page checklist

**Hour 0** — [ ] Groq API key (free, no card) · [ ] Gemini API key (free, no card) · [ ] Supabase project + vector + bucket · [ ] GitHub repo · [ ] LinkedIn post 1

**Hour 12.5** — [ ] Migrations pushed · [ ] Render live, `/health` green · [ ] Vercel live · [ ] CORS + auth URLs · [ ] Demo seeded · [ ] Reset button works · [ ] Keep-alive running · [ ] **Verified in incognito**

**Hour 13–15** — [ ] Telegram bot · [ ] n8n imported, activated, re-exported, secret-scanned · [ ] Extension loaded unpacked · [ ] Extension tested on real Amazon

**Hour 16–18** — [ ] Dry run · [ ] Video < 3:00 · [ ] Drive sharing verified in incognito · [ ] Form submitted · [ ] LinkedIn post 4

**After results** — [ ] Demo account disabled · [ ] Keys rotated · [ ] Keep-alive deleted
