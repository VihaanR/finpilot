# USER.md — What's Left For You

Only the work that still needs a human. Everything already done — deployment,
keys, migrations, gotchas, environment reference — lives in `PROGRESS.md`.

**Nothing here is blocked. Four items, in priority order.**

> If the clock runs out, **§3 and §4 beat §1 and §2.** A working, deployed,
> un-recorded product scores worse than a recorded one, and the n8n JSON is
> optional on the submission form.

| | Item | Time | Optional? |
|---|---|---|---|
| §1 | Test the extension on a real cart | 10 min | no |
| §2 | n8n + Telegram | 30–45 min | **yes — cut first** |
| §3 | Record the video | 60 min | no |
| §4 | Submit | 15 min | no |
| §5 | After results are announced | 5 min | no |
| §6 | Connect Gmail (Data Vault) | 10 min | **yes — not part of the submission scope** |

---

## 1. Test the extension on a real cart — 10 min

The only part of Budget Guard never verified against a live retailer. Two bugs
you reported were fixed on 20 Sep — an EMI panel being read as the cart total,
and the interstitial not actually blocking navigation — so this re-tests both.

**Load it**

1. `chrome://extensions` → toggle **Developer mode** (top right)
2. **Load unpacked** → select `V:\Projects\FinPilot\extension`
3. Pin it to the toolbar (puzzle icon → pin) so it's visible when you record
4. Open the popup — a discretionary-budget figure should appear within a few
   seconds, fetched live from production. There is nothing to log into.

**Then on `amazon.in`, with something in the cart above your remaining budget**

- [ ] The amount shown matches the **actual cart total** — not an EMI or "no
      cost EMI" figure, not a crossed-out MRP, not a delivery fee
- [ ] Clicking **Place your order** is *blocked* — the page does not navigate
- [ ] **Continue anyway** lets it through
- [ ] **Wait 24 hours** blocks it, and reloading the cart does not re-prompt
- [ ] A cart **below** budget shows nothing at all
- [ ] Afterwards, reload the dashboard — a **Budget Guard** card should appear
      in the right column showing what it stopped

If the amount is still wrong, send me the cart URL and the figure it showed —
it'll be a page element the label-matching didn't catch.

---

## 2. n8n + Telegram — 30–45 min (optional)

**Needs Docker Desktop running.** Drop this one if it fights you.

### 2a. Telegram bot

1. Telegram → **@BotFather** → `/newbot` → name `FinPilot` → username ending in `bot`
2. Put the token in `services/api/.env` as `TELEGRAM_BOT_TOKEN`
   — **never in a tracked file**; this repo is public
3. `/setdescription` → *"AI-powered personal finance assistant. Sends you a
   daily brief, mandate alerts and a monthly summary."*
4. Message your own bot once (bots can't start a conversation), then open
   `https://api.telegram.org/bot<token>/getUpdates` and copy `message.chat.id`

> **One-way by design.** It pushes the daily brief, mandate alerts and the
> monthly summary. It does not answer questions or accept statements — that
> scope was deliberately removed (BUILD_TASKS.md T14).

### 2b. n8n

```powershell
docker run -d --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
```

Open `http://localhost:5678` and create the local owner account (local only).

1. **Workflows → Import from File**, once per file — `n8n/workflows/01-daily-brief.json`,
   `02-mandate-alert.json`, `03-monthly-summary.json`. Don't point this at
   `n8n/finpilot-workflows.json`: that one file holds all three as a JSON
   array, and n8n's file-import dialog only reads a single workflow object,
   so it fails with *"the imported data does not contain valid workflow data
   ('nodes' and 'connections' are missing)"* — that array file is generated
   only for reference/the CLI import path, not this dialog.
2. **Credentials → Telegram API** → paste the bot token → name it exactly **`Telegram Bot`**
3. **Credentials → Header Auth** → Name `Authorization`, Value `Bearer anything`
   → name it exactly **`FinPilot API`** (this API has no auth enforced)
4. In **each** workflow, replace `REPLACE_WITH_YOUR_TELEGRAM_CHAT_ID` in its
   Telegram node with your chat id — all three are schedule-triggered, so none
   can infer it
5. **Activate** all three
6. Test each with **Execute Workflow** (don't wait for the schedule) and
   confirm the message lands in Telegram

> Credential names must match **exactly**. A mismatch is a silent no-op, not a
> visible error.

### 2c. Re-export before submitting

**Workflows → Select all → Download**, save over `n8n/finpilot-workflows.json`
(this is the one file worth attaching to the submission — the individual
`n8n/workflows/*.json` files are only for re-importing), then confirm nothing
leaked:

```powershell
Select-String -Path n8n\finpilot-workflows.json,n8n\workflows\*.json -Pattern "sk-ant|eyJ|bot[0-9]{8,}|service_role"
```

No output means you're clean.

---

## 3. Record the video — under 3:00

Full timed script in `SUBMISSION.md`.

**Before**
- [ ] Close Slack, email, notifications — Windows Focus Assist on
- [ ] New browser window, one tab, no bookmarks bar, only Budget Guard visible
- [ ] **Reset demo data** for a known clean state
- [ ] 1920×1080, browser zoom 100%
- [ ] Amazon cart pre-loaded in a second tab so the extension beat doesn't stall
- [ ] One full silent dry run — find the dead air before you're recording

**Must-show beats**
- [ ] **The agentic panel** on the dashboard, handling a multi-step request in
      one sentence — set up a goal *and* remove a duplicated transaction,
      staged as action cards you approve. This is the headline; lead with it.
- [ ] A citation chip opening to the real transactions under a figure
- [ ] Budget Guard blocking a real over-budget checkout
- [ ] The privacy vault — consent, redaction, export/erase

> **Type the agentic sentence once before you record.** Every deterministic
> layer under it is tested, but the model actually choosing the right tools
> for your exact phrasing is the one thing no test covers.

**Recording**: OBS Studio or Loom, 1080p/30fps, system audio + mic (test levels).
**Under 3:00** — over-length is a scoring risk on a 3-minute rubric.

**After**
- [ ] Upload to Google Drive
- [ ] Right-click → Share → **"Anyone with the link" → Viewer**
- [ ] **Open the link in an incognito window to verify.** The most common
      submission failure is a video nobody but the author can open.

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

> ⚠️ **Never paste a Vercel *preview* URL.** Previews sit behind Vercel's SSO
> wall and show a login screen to anyone without a Vercel session. Only the
> production URL above is public.

---

## 5. After results are announced

1. Rotate `GROQ_API_KEY` (`console.groq.com/keys`) and `GEMINI_API_KEY`
   (`aistudio.google.com/apikey`) — the repo is public
2. Delete the cron-job.org keep-alive so Render stops burning free hours
3. Revoke the Telegram bot token via @BotFather, if you created one

*(There's no demo account to disable — this build has no login. See
PROGRESS.md.)*

---

## 6. Connect Gmail (Data Vault) — 10 min, optional

A new panel at the top of the Data Vault: connect a Gmail account and pull
HDFC transaction-alert emails in as transactions, no manual upload needed.
Built after the original submission scope — nice to have in the recording,
not required for it.

1. **Google Cloud Console** (same project as `GEMINI_API_KEY` works fine) →
   APIs & Services → **enable the Gmail API**
2. APIs & Services → Credentials → **Create credentials → OAuth client ID**
   → Application type **Web application**
3. Add an **Authorized redirect URI**: `http://localhost:8001/api/email/callback`
   (and your Render URL + `/api/email/callback` if you want this live too)
4. OAuth consent screen → **Audience** → while it's in Testing mode, add your
   own Google account under **Test users** — otherwise Google refuses the
   login with "app not verified" and no way past it
5. Copy the **Client ID** and **Client secret** into `services/api/.env`:
   `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`
6. Restart the API, open the Data Vault, click **Connect Gmail**, approve the
   Google consent screen, then **Sync now**

Only HDFC's own transaction-alert emails (`alerts@hdfcbank.bank.in`) are
read, and only the one verified debit-alert wording is parsed — anything
else is skipped and counted, never guessed at. If you don't bank with HDFC
or don't want to set up an OAuth client, skip this entirely; nothing else in
the product depends on it.

---

## If something breaks

Symptom → cause → fix is in **PROGRESS.md § "Things that will go wrong"**,
along with the environment reference, deployment facts and model quotas.
