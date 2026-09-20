# FinPilot n8n workflows

Three workflows (BUILD_TASKS.md T14), one file each in `workflows/` (import
these — see "Importing" below for why), plus a combined
`finpilot-workflows.json` for the CLI path. All three are one-way: FinPilot
pushes information to your Telegram chat on a schedule. There is no inbound
side — the bot never receives or acts on a message from you.

| Workflow | Trigger | Behaviour |
|---|---|---|
| **Daily brief** | Schedule, 08:00 IST | `GET /api/dashboard` + `GET /api/radar` → safe-to-spend and anything due today, sent to Telegram. |
| **Mandate alert** | Schedule, 09:00 IST | `GET /api/radar` → any unacknowledged `SILENT` item due within the banner window → Telegram alert. |
| **Monthly summary** | Schedule, 1st at 09:00 IST | `POST /api/summary/generate` → the month's prose summary, sent to Telegram. |

## Scope, deliberately narrowed

The original design also had a fourth workflow, **Ingest** — a Telegram
Trigger that accepted an uploaded statement or an arbitrary typed question
and had the bot reply, i.e. a second conversational front end for the chat
agent alongside the web app. That was dropped on the owner's explicit
instruction: *"I don't want the telegram bot to do anything, I just want it
to ship out important info."* `generate_workflows.py` no longer emits that
workflow at all — there is no Telegram Trigger node, no inbound webhook, and
the bot only ever calls `sendMessage`. If a two-way bot is wanted later,
`git log` has the removed workflow to restore, but nothing here builds
toward it.

## The honest state of this file

**This was hand-authored against n8n's node schema, not built in n8n's own
editor and exported.** BUILD_TASKS.md's own process for T14 is "build the
workflows in a local Docker n8n, then export" — that needs Docker running
locally, which wasn't available in this session (PROGRESS.md's blockers
list). `generate_workflows.py` produces this JSON programmatically instead,
using the same node types and parameter shapes n8n's editor would export,
but it has never actually been imported into a running n8n or exercised
against a live Telegram bot.

Treat this as a well-structured starting point, not a verified deliverable.
The daily brief firing correctly, the mandate alert only firing on a real
unacknowledged silent mandate, and a clean import into a fresh n8n all still
need to actually be run once Docker and a bot token exist.

## To actually use this

1. **Docker + n8n**: `docker run -it --rm -p 5678:5678 n8nio/n8n` (or add to
   `docker-compose` if you already run other services). Open
   `http://localhost:5678`.
2. **Telegram bot token** (USER.md §5): message [@BotFather](https://t.me/BotFather),
   `/newbot`, copy the token.
3. In n8n, add two credentials, **named exactly this** — the workflows
   reference credentials by name, not by inlined secret, so the names must
   match or n8n will ask you to reassign them on import:
   - **`Telegram Bot`** — type "Telegram API", paste the bot token.
   - **`FinPilot API`** — type "Header Auth". This API has no auth enforced
     yet (`internal_api_token` in `services/api/app/config.py` is defined
     but never checked — see USER.md), so any header name/value works today;
     this credential exists so nothing needs to change here if that gets
     enforced later. Header name `Authorization`, value `Bearer <anything>`.
4. **Import**: n8n → Workflows → **Import from File**, once per file, for
   each of `workflows/01-daily-brief.json`, `workflows/02-mandate-alert.json`,
   `workflows/03-monthly-summary.json`. Do **not** import
   `finpilot-workflows.json` this way — that file is a JSON *array* of all
   three workflows, and n8n's own file-import dialog reads exactly one
   workflow object per file. Pointing it at the array produces exactly the
   error a real run hit: *"The imported data does not contain valid workflow
   data ('nodes' and 'connections' are missing)"* — it looked for those keys
   on the array itself, one level too high. The array file is only valid for
   n8n's CLI (`n8n import:workflow --input=finpilot-workflows.json`), which
   this setup doesn't otherwise use.
5. **Fix the three placeholders**: every workflow here is schedule-triggered,
   so none of them has an inbound message to reply to — each sends to a
   fixed chat instead. Open each, find the Telegram node's **Chat ID** field
   (`REPLACE_WITH_YOUR_TELEGRAM_CHAT_ID`), and set it to your own chat id
   (message your bot once, then check
   `https://api.telegram.org/bot<token>/getUpdates` for `message.chat.id`).
6. **Activate** each workflow (the toggle in the top-right of its editor).
7. Test each workflow with "Execute Workflow" in its editor (doesn't wait for
   the schedule) and confirm the message arrives in Telegram, then re-export
   (Workflows → select all three → Download saves one array file — see
   USER.md §2c) and confirm the re-exported file still passes the secret scan
   below.

## Secret scan (T14 acceptance criterion)

```bash
grep -inE "sk-ant|eyJ|bot[0-9]{8,}|service_role" n8n/finpilot-workflows.json n8n/workflows/*.json
```

Returns nothing as committed — credentials are referenced by name
(`FinPilot API`, `Telegram Bot`), never inlined. Re-run this after any manual
edit in n8n's editor before re-exporting; n8n does not inline credential
*values* into workflow JSON by default, but it's the check that catches it
if that ever changes.
