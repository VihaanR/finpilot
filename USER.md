# USER.md — What You Personally Have To Do

Everything in this file requires a human. The coding agents cannot create accounts, click OAuth consent screens, scan QR codes, or record a video.

**Read the "Do this before" column and front-load the blocking items.** Several take minutes of waiting, and a key you don't have at hour 4 stalls the whole build.

---

## 0. The critical path — do these first, in this order

| # | Action | Blocks | Time | Do before |
|---|---|---|---|---|
| 1 | Anthropic API key | T05, T07 — everything AI | 5 min | **Hour 0** |
| 2 | Supabase project | T02 — everything | 10 min | **Hour 0** |
| 3 | GitHub repo | commits | 2 min | **Hour 0** |
| 4 | Telegram bot token | T14 | 3 min | Hour 13 |
| 5 | Vercel account | T12 | 5 min | Hour 11 |
| 6 | Render account | T12 | 5 min | Hour 11 |
| 7 | n8n via Docker | T14 | 10 min | Hour 13 |
| 8 | Bhashini registration *(optional)* | vernacular summary | 15 min | Hour 13 |

Items 1–3 are hard blockers. Do them before you start anything else. Items 4–8 can wait but must not be discovered late.

---

## 1. Anthropic API key — Hour 0

1. Go to `console.anthropic.com` → sign in
2. **Settings → API Keys → Create Key**, name it `finpilot`
3. Copy it immediately — it is shown once
4. **Billing → add credits.** A $10–20 balance is ample for this build. An empty balance produces confusing 400-level errors mid-build, which is a miserable thing to debug at hour 7.

→ `ANTHROPIC_API_KEY=sk-ant-...`

**Check your rate limits** under Settings → Limits. If you're on the lowest tier, tell the agent at T05 to drop tier-2 categorisation to on-demand instead of bulk-on-ingest (this contingency is already in BUILD_TASKS.md).

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
ANTHROPIC_API_KEY=sk-ant-...
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
3. Copy the token → `TELEGRAM_BOT_TOKEN`
4. `/setdescription` → *"Your personal finance agent. Send a statement or ask a question."*
5. `/setcommands` →
   ```
   start - Link your FinPilot account
   brief - Today's spending brief
   upcoming - Recurring payments due soon
   summary - This month's summary
   ```
6. Message your own bot once so it can message you back — Telegram bots cannot initiate conversations

Takes about three minutes. This is why we chose Telegram over WhatsApp: the WhatsApp Business API needs Meta app review measured in days, which does not fit a 48-hour window.

---

## 6. n8n — Hour 13 (before T14)

**Requires Docker Desktop running.**

```powershell
docker run -d --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
```

Open `http://localhost:5678`, create the local owner account (local only, no cloud signup needed).

### Import the workflows

1. **Workflows → Import from File** → `n8n/finpilot-workflows.json`
2. **Credentials → Add credential → Telegram API** → paste the bot token → name it exactly **`Telegram Bot`**
3. **Credentials → Add credential → Header Auth** → Name: `Authorization`, Value: `Bearer <INTERNAL_API_TOKEN>` → name it exactly **`FinPilot API`**
4. In each workflow, set the API base URL variable to your Render URL
5. **Activate** all four workflows

> The credential names must match exactly. The exported JSON references credentials by name; a mismatch causes silent no-ops rather than visible errors.

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

```powershell
cd apps\extension
npm install
npm run build
```

Then in Chrome:
1. `chrome://extensions`
2. Toggle **Developer mode** on (top right)
3. **Load unpacked** → select `V:\Projects\FinPilot\apps\extension\dist`
4. Pin it to the toolbar (puzzle icon → pin) so it's visible when you record
5. Log into the FinPilot web app in the same browser — this is what writes the budget snapshot the extension reads

**Test before recording:** open `amazon.in`, add something above your remaining discretionary budget, go to the cart. The interstitial should appear.

> Not published to the Chrome Web Store — review takes days and we have 48 hours. This is a deliberate, stated choice, not an oversight. It does **not** go in the Agent Access Link field; it goes in Additional Materials as a GitHub link with these install instructions.

---

## 8. Deployment — Hour 12.5 (T12)

### 8a. Supabase migrations

```powershell
npx supabase link --project-ref <your-project-ref>
npx supabase db push
```

Verify in the Supabase Table Editor that all tables exist and `categories` has rows.

### 8b. Render — FastAPI

1. `render.com` → **New → Web Service** → connect the GitHub repo
2. Root directory: `services/api`
3. Build: `pip install -r requirements.txt`
4. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Instance: **Free**
6. **Environment** → add every variable from `services/api/.env`
7. Deploy, wait ~3 minutes, then confirm `https://<your-service>.onrender.com/health` returns `{"status":"ok"}`

**Free tier sleeps after 15 minutes of inactivity and takes ~40 seconds to wake.** A judge hitting a cold start will assume the product is broken. Fix it:

- `cron-job.org` (free) → new job → your `/health` URL → every 10 minutes
- Do this **at T12**, not later. It needs to already be warm when judging starts.

### 8c. Vercel — Next.js

1. `vercel.com` → **Add New → Project** → import the repo
2. Root directory: `apps/web`
3. Framework preset: Next.js (auto-detected)
4. **Environment Variables** → the three from `.env.local`, with `NEXT_PUBLIC_API_URL` set to the Render URL
5. Deploy

### 8d. Close the loop

- Add the Vercel URL to `ALLOWED_ORIGINS` on Render and redeploy
- Supabase → **Authentication → URL Configuration** → add the Vercel URL to Site URL and Redirect URLs

### 8e. Seed the demo account

```powershell
python seed\generate.py --seed 42 --user demo@finpilot.in --push-production
```

Then **verify in a fresh incognito window**: open the Vercel URL, log in as `demo@finpilot.in` / `FinPilot@2026`, confirm the dashboard is populated.

Incognito matters — your normal browser has a session and will hide a broken login.

---

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
2. Rotate `ANTHROPIC_API_KEY` if the repo is public and anything leaked
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
| Anthropic 400s mid-build | Credit balance empty | §1, step 4 |
| n8n workflows silently no-op | Credential names don't match exactly | §6, step 2–3 |
| Money figures slightly off | A float crept into a currency path | `grep` for float in engine; paise are integers (DESIGN.md §5.1) |

---

## 15. One-page checklist

**Hour 0** — [ ] Anthropic key + credits · [ ] Supabase project + vector + bucket · [ ] GitHub repo · [ ] LinkedIn post 1

**Hour 12.5** — [ ] Migrations pushed · [ ] Render live, `/health` green · [ ] Vercel live · [ ] CORS + auth URLs · [ ] Demo seeded · [ ] Reset button works · [ ] Keep-alive running · [ ] **Verified in incognito**

**Hour 13–15** — [ ] Telegram bot · [ ] n8n imported, activated, re-exported, secret-scanned · [ ] Extension built and loaded · [ ] Extension tested on real Amazon

**Hour 16–18** — [ ] Dry run · [ ] Video < 3:00 · [ ] Drive sharing verified in incognito · [ ] Form submitted · [ ] LinkedIn post 4

**After results** — [ ] Demo account disabled · [ ] Keys rotated · [ ] Keep-alive deleted
