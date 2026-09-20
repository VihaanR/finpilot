# USER.md — What You Personally Have To Do

Everything in this file needs a human. Coding agents cannot create accounts,
click OAuth consent screens, load a Chrome extension, or record a video.

**Last updated 20 Sep 2026.** Rewritten around what is *left*. The build is
done and deployed; §1–§4 are the remaining work, and everything after §5 is
reference for when something breaks.

---

## Status at a glance

| | |
|---|---|
| **Live frontend** | https://finpilot-swart.vercel.app |
| **Live API** | https://finpilot-w4ki.onrender.com/health |
| **Repo** | https://github.com/VihaanR/finpilot (public) |
| **Keys** | Groq + Gemini in `services/api/.env` and on Render — done |
| **Supabase** | Project created, 4 migrations applied, RLS verified — done |
| **Keep-alive** | cron-job.org pinging `/health` every 10 min — done |
| **Tests** | 326 pytest · 36 Playwright · CI green on every push |

**Done and needs nothing from you:** T01–T13, T15, deployment, migrations,
accessibility sweep, evals, CI, the browser extension's code.

**Left, in priority order:** §1 extension on a real cart · §2 n8n + Telegram ·
§3 record the video · §4 submit.

> If time runs short, **§3 and §4 beat §1 and §2.** A working, deployed,
> un-recorded product scores worse than a recorded one. n8n is optional on the
> submission form.

---

## 1. Test the extension on a real cart — 10 min

The only part of the extension never verified against a live retailer. Two
bugs you reported were fixed on 20 Sep (an EMI panel being read as the cart
total, and the interstitial not actually blocking navigation), so this is a
re-test of both.

1. `chrome://extensions` → toggle **Developer mode** (top right)
2. **Load unpacked** → select `V:\Projects\FinPilot\extension`
3. Pin it to the toolbar (puzzle icon → pin) so it's visible when you record
4. Open the popup — it should show a discretionary-budget figure within a few
   seconds, fetched live from production. There is nothing to log into.

Then, on `amazon.in`:

- [ ] Add something **above** your remaining discretionary budget, go to cart
- [ ] The amount in the interstitial matches the **actual cart total** — not an
      EMI/"no cost EMI" figure, not a crossed-out MRP, not a delivery fee
- [ ] Clicking **Place your order** is *blocked* — the page does not navigate
- [ ] **Continue anyway** lets it through
- [ ] **Wait 24 hours** blocks it, and reloading the cart does not re-prompt
- [ ] A cart **below** budget shows nothing at all

If the amount is still wrong, the cause is almost always a page element the
label-matching didn't catch — send me the cart URL and the figure it showed.

---

## 2. n8n + Telegram — 30–45 min (optional)

**Requires Docker Desktop running.** This is the one item to drop if it fights
you: it is optional on the submission form.

### 2a. Telegram bot

1. Telegram → **@BotFather** → `/newbot` → name `FinPilot` → username ending in `bot`
2. Copy the token into `services/api/.env` as `TELEGRAM_BOT_TOKEN`
   — **never into this file**; it is tracked and the repo is public
3. `/setdescription` → *"AI-powered personal finance assistant. Sends you a
   daily brief, mandate alerts and a monthly summary."*
4. Message your own bot once (bots cannot start a conversation), then open
   `https://api.telegram.org/bot<token>/getUpdates` and copy `message.chat.id`

> **This bot is one-way by design.** It pushes the daily brief, mandate alerts
> and the monthly summary. It does **not** answer questions or accept
> statements — that scope was deliberately removed (BUILD_TASKS.md T14).

### 2b. n8n

```powershell
docker run -d --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
```

Open `http://localhost:5678`, create the local owner account (local only).

1. **Workflows → Import from File** → `n8n/finpilot-workflows.json` (all three)
2. **Credentials → Telegram API** → paste the bot token → name it exactly **`Telegram Bot`**
3. **Credentials → Header Auth** → Name `Authorization`, Value `Bearer anything`
   → name it exactly **`FinPilot API`** (this API has no auth enforced, §7c)
4. In **each** of the three workflows, replace
   `REPLACE_WITH_YOUR_TELEGRAM_CHAT_ID` in its Telegram node with your chat id
   — all three are schedule-triggered, so none can infer it
5. **Activate** all three
6. Test each with **Execute Workflow** (don't wait for the schedule) and
   confirm the message lands in Telegram

> Credential names must match **exactly**. A mismatch causes a silent no-op,
> not a visible error.

### 2c. Re-export before submitting

**Workflows → Select all → Download**, save over `n8n/finpilot-workflows.json`,
then confirm no credential values leaked in:

```powershell
Select-String -Path n8n\finpilot-workflows.json -Pattern "sk-ant|eyJ|bot[0-9]{8,}|service_role"
```

No output means you're clean.

---

## 3. Record the video — under 3:00

Full timed script in `SUBMISSION.md`.

**Before recording**
- [ ] Close Slack, email, notifications — Windows Focus Assist on
- [ ] New browser window, one tab, no bookmarks bar, only Budget Guard visible
- [ ] **Reset demo data** so the dashboard is in a known clean state
- [ ] 1920×1080, browser zoom 100%
- [ ] Amazon cart pre-loaded in a second tab so the extension beat doesn't stall
- [ ] One full silent dry run — find the dead air before you're recording

**Must-show beats**
- [ ] The **agentic panel** on the dashboard doing a multi-step request in one
      sentence — set up a goal *and* remove a duplicated transaction, staged as
      action cards you approve. This is the hackathon's headline.
- [ ] A citation chip opening to the real transactions underneath a figure
- [ ] Budget Guard blocking a real over-budget checkout
- [ ] The privacy vault (consent, redaction, export/erase)

**Recording**: OBS Studio or Loom, 1080p/30fps, system audio + mic (test levels).
**Keep it under 3:00** — over-length is a scoring risk on a 3-minute rubric.

**After**
- [ ] Upload to Google Drive
- [ ] Right-click → Share → **"Anyone with the link" → Viewer**
- [ ] **Open the link in an incognito window to verify.** The single most
      common submission failure is a video nobody but the author can open.

---

## 4. Submit

Field-by-field answers in `SUBMISSION.md`.

| Field | Value |
|---|---|
| Team Name | *(yours)* |
| Video Demo Link | Google Drive link, **verified in incognito** |
| Agent Access Link | `https://finpilot-swart.vercel.app` |
| Agent Credentials | **None — there is no login.** Say so explicitly. |
| Additional Materials | GitHub repo · n8n JSON · DESIGN.md · accessibility statement |

> ⚠️ **Do not paste a Vercel *preview* URL.** Preview deployments sit behind
> Vercel's SSO wall and show a login screen to anyone without a Vercel session.
> Only the production URL above is public.

---

## 5. After evaluation

1. Rotate `GROQ_API_KEY` (`console.groq.com/keys`) and `GEMINI_API_KEY`
   (`aistudio.google.com/apikey`) — the repo is public
2. Delete the cron-job.org keep-alive so Render stops burning free hours
3. Revoke the Telegram bot token via @BotFather if you set one up

*(There is no demo account to disable — see §7c.)*

---

# Reference

Everything below is already done. It's here for when something breaks.

## 6. Environment files

**Never commit either.** `.env.example` (committed) mirrors them with empty values.

`apps/web/.env.local`
```bash
NEXT_PUBLIC_API_URL=http://localhost:8001        # Render URL in production
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

`services/api/.env`
```bash
GROQ_API_KEY=gsk_...            # chat, monthly summary, the agentic panel
GEMINI_API_KEY=AIza...          # tier-2 categorisation, PDF fallback, embeddings
SUPABASE_URL=...                # schema applied; app still reads SQLite (§7c)
SUPABASE_SERVICE_KEY=...        # service_role — server only, never NEXT_PUBLIC_*
DATABASE_URL=postgresql://...
ALLOWED_ORIGINS=http://localhost:3000
TELEGRAM_BOT_TOKEN=             # §2a
INTERNAL_API_TOKEN=             # python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 7. How this thing is deployed

### 7a. Render — the Python version will break a rebuild

`render.yaml` sets `PYTHON_VERSION`, but **that file only applies to Blueprint
deploys**. This service was created by hand in the dashboard, so it never reads
it and Render falls back to its default — 3.14 as of 20 Sep 2026, which has no
`psycopg-binary` wheels and no sdist. The error names psycopg; the real cause is
the interpreter, visible only as `cp314` in the wheel filenames.

`services/api/.python-version` pins **3.11.13** and is read either way. If Render
rejects that patch release, set `PYTHON_VERSION=3.11` in the dashboard.
Do **not** "fix" this by unpinning psycopg.

### 7b. The CORS trap

`ALLOWED_ORIGINS` must contain the Vercel URL **with no trailing slash** — a
browser's `Origin` header never has one, and the match is exact. A mismatch
gives 200s from curl with no CORS header, which a browser treats as a hard
failure with nothing to grep for server-side. The code now strips trailing
slashes defensively (`test_config.py` pins it).

Also: `NEXT_PUBLIC_*` is baked in at **build** time. Changing
`NEXT_PUBLIC_API_URL` needs a **redeploy**, not a restart.

### 7c. No authentication — deliberate

No login page, no session. The public URL opens straight onto a populated
dashboard. Building auth on the last day would risk a working product for a
login screen standing between a judge and the thing being judged.

Consequences:

- **The API is open.** Anyone with the Render URL can read the demo ledger and
  spend your Groq/Gemini quota. The **Reset demo data** button fixes any mess.
- **The store is SQLite on Render's ephemeral disk.** A cold start re-seeds it,
  so the demo is always clean. Agent-made changes (a created goal, a removed
  duplicate) survive a *restart with the disk intact*, but not a true cold
  start — that needs the Supabase swap, which is deliberately deferred. The
  keep-alive ping (§ status table) is what prevents cold starts during judging.

## 8. Model quotas

**Groq** runs chat, the monthly summary and the agentic panel. Rate-limited
per minute, no hard daily wall — this is why chat moved off Gemini.

**Gemini** does tier-2 categorisation, the PDF fallback and embeddings. Its
free tier is **5/min and 20/day, per model, per Cloud project**. Gemini *Pro*
models are **0/day** without billing. Classifying the whole seed dataset is
~19 calls, cached by narration hash, so this no longer bounds the demo.

> A consumer Google AI Plus/Pro/Ultra subscription does **not** raise API rate
> limits — those cover the Gemini app, not the API. Only project billing does.

Check yours at `aistudio.google.com/rate-limit`.

## 9. Things that will go wrong

| Symptom | Cause | Fix |
|---|---|---|
| Judge sees a 40-second load | Render cold start | Keep-alive ping — confirm it's still running |
| Video link won't open | Drive sharing left on "Restricted" | Verify in incognito |
| Judge sees a login screen | You pasted a Vercel **preview** URL | Use the production URL, §4 |
| Dashboard loads but is empty | CORS — Vercel URL missing/trailing-slashed in `ALLOWED_ORIGINS` | §7b |
| Chat says "Groq free-tier quota" | Groq's per-minute limit | Wait for the window, or switch `GROQ_MODEL_CHAT` |
| Gemini 429 during upload | Tier-2's **daily** cap for that model | Switch `GEMINI_MODEL_CLASSIFY` (each model has its own bucket) |
| Extension shows the wrong amount | A page element read as the cart total | Send me the cart URL + the figure |
| Extension does nothing | Budget not fetched yet, or cart is under budget | Open the popup and hit Refresh |
| n8n workflows silently no-op | Credential names don't match exactly | §2b steps 2–3 |
| Render rebuild dies on psycopg | Python 3.14 | §7a |

## 10. Final checklist

- [ ] Extension tested on a real Amazon cart (§1)
- [ ] n8n imported, activated, re-exported, secret-scanned (§2) *(optional)*
- [ ] Dry run done
- [ ] Video under 3:00, Drive sharing **verified in incognito**
- [ ] Submission form complete, production URL, "no credentials" stated
- [ ] *After results:* keys rotated, keep-alive deleted
