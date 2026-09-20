"""Generates finpilot-workflows.json (BUILD_TASKS.md T14).

Hand-authored against n8n's node schema rather than built in n8n's own editor
and exported — Docker wasn't available to run n8n locally (see PROGRESS.md).
Kept, rather than deleted after one run, because it's the only record of how
this file was actually produced and the easiest way to regenerate it after
an edit; see n8n/README.md for the verification gap this leaves.

    python generate_workflows.py
"""
import json
import uuid


def nid():
    return str(uuid.uuid4())


FINPILOT_API_BASE = "https://finpilot-w4ki.onrender.com"

FINPILOT_API_CRED = {"httpHeaderAuth": {"id": "finpilot-api-cred", "name": "FinPilot API"}}
TELEGRAM_CRED = {"telegramApi": {"id": "telegram-bot-cred", "name": "Telegram Bot"}}


def http_node(name, pos, method, path, body_params=None, send_body=True, is_form=False):
    params = {
        "method": method,
        "url": FINPILOT_API_BASE + path,
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "options": {},
    }
    if send_body:
        params["sendBody"] = True
        params["specifyBody"] = "keypair"
        if is_form:
            params["contentType"] = "multipart-form-data"
            params["bodyParameters"] = {"parameters": body_params or []}
        else:
            params["contentType"] = "json"
            pairs = [{"name": k, "value": v} for k, v in (body_params or {}).items()]
            params["bodyParameters"] = {"parameters": pairs}
    return {
        "parameters": params,
        "id": nid(),
        "name": name,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": pos,
        "credentials": FINPILOT_API_CRED,
    }


def telegram_send(name, pos, text_expr, chat_id_expr="={{ $json.message.chat.id }}"):
    return {
        "parameters": {
            "resource": "message",
            "operation": "sendMessage",
            "chatId": chat_id_expr,
            "text": text_expr,
            "additionalFields": {"parse_mode": "Markdown"},
        },
        "id": nid(),
        "name": name,
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "position": pos,
        "credentials": TELEGRAM_CRED,
    }


def schedule_trigger(name, pos, cron_expr):
    return {
        "parameters": {
            "rule": {"interval": [{"field": "cronExpression", "expression": cron_expr}]}
        },
        "id": nid(),
        "name": name,
        "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2,
        "position": pos,
    }


def if_node(name, pos, condition_left, operator, condition_right=None):
    condition = {
        "leftValue": condition_left,
        "rightValue": condition_right if condition_right is not None else "",
        "operator": {"type": "string" if operator != "exists" else "object", "operation": operator},
    }
    return {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose"},
                "conditions": [condition],
                "combinator": "and",
            },
            "options": {},
        },
        "id": nid(),
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": pos,
    }


def connect(*pairs):
    """pairs: (from_name, to_name) or (from_name, to_name, output_index)."""
    conns = {}
    for pair in pairs:
        frm, to = pair[0], pair[1]
        out_idx = pair[2] if len(pair) > 2 else 0
        conns.setdefault(frm, {"main": []})
        while len(conns[frm]["main"]) <= out_idx:
            conns[frm]["main"].append([])
        conns[frm]["main"][out_idx].append({"node": to, "type": "main", "index": 0})
    return conns


def workflow(name, nodes, connections, active=False):
    return {
        "name": name,
        "nodes": nodes,
        "connections": connections,
        "active": active,
        "settings": {"executionOrder": "v1"},
        "meta": {"templateCredsSetupCompleted": False},
    }


# --- Workflow 1: Ingest (Telegram Trigger) ----------------------------------

trigger1 = {
    "parameters": {
        "updates": ["message"],
        "additionalFields": {},
    },
    "id": nid(),
    "name": "Telegram Trigger",
    "type": "n8n-nodes-base.telegramTrigger",
    "typeVersion": 1.1,
    "position": [0, 0],
    "credentials": TELEGRAM_CRED,
    "webhookId": "finpilot-ingest-webhook",
}

has_doc = if_node(
    "Has document?", [220, 0], "={{ $json.message.document }}", "exists"
)

download_doc = {
    "parameters": {
        "resource": "file",
        "fileId": "={{ $json.message.document.file_id }}",
    },
    "id": nid(),
    "name": "Download document",
    "type": "n8n-nodes-base.telegram",
    "typeVersion": 1.2,
    "position": [440, -120],
    "credentials": TELEGRAM_CRED,
}

ingest_call = http_node(
    "POST /api/ingest/sync",
    [660, -120],
    "POST",
    "/api/ingest/sync",
    body_params=[{"parameterType": "formBinaryData", "name": "file", "inputDataFieldName": "data"}],
    is_form=True,
)

reply_ingest = telegram_send(
    "Reply with parse summary",
    [880, -120],
    "={{ $json.adapter }} read the statement at {{ Math.round($json.confidence * 100) }}% "
    "confidence — {{ $json.inserted }} new transaction(s), {{ $json.duplicates }} duplicate(s) skipped.",
    chat_id_expr="={{ $('Telegram Trigger').item.json.message.chat.id }}",
)

ask_call = http_node(
    "POST /api/agent/ask/sync",
    [440, 120],
    "POST",
    "/api/agent/ask/sync",
    body_params={"question": "={{ $json.message.text }}"},
)

reply_ask = telegram_send(
    "Reply with answer",
    [660, 120],
    "={{ $json.answer || $json.error || \"I could not answer that.\" }}",
    chat_id_expr="={{ $('Telegram Trigger').item.json.message.chat.id }}",
)

wf1 = workflow(
    "FinPilot - Ingest",
    [trigger1, has_doc, download_doc, ingest_call, reply_ingest, ask_call, reply_ask],
    {
        **connect(("Telegram Trigger", "Has document?")),
        "Has document?": {
            "main": [
                [{"node": "Download document", "type": "main", "index": 0}],
                [{"node": "POST /api/agent/ask/sync", "type": "main", "index": 0}],
            ]
        },
        **connect(
            ("Download document", "POST /api/ingest/sync"),
            ("POST /api/ingest/sync", "Reply with parse summary"),
            ("POST /api/agent/ask/sync", "Reply with answer"),
        ),
    },
)

# --- Workflow 2: Daily brief (08:00 IST) ------------------------------------

trigger2 = schedule_trigger("Daily 08:00 IST", [0, 0], "0 30 2 * * *")  # 02:30 UTC = 08:00 IST
dashboard_call = http_node("GET /api/dashboard", [220, 0], "GET", "/api/dashboard", send_body=False)
radar_call = http_node("GET /api/radar", [440, 0], "GET", "/api/radar", send_body=False)
brief_code = {
    "parameters": {
        "jsCode": (
            "const dash = $('GET /api/dashboard').first().json;\n"
            "const radar = $json;\n"
            "const sts = dash.safe_to_spend || {};\n"
            "const dueToday = (radar.banner?.items || []).filter(i => i.days_away <= 1);\n"
            "let text = 'Good morning. Safe to spend: ₹' + Math.round((sts.safe_daily_paise||0)/100)\n"
            "  + '/day. Discretionary left this month: ₹' + Math.round((sts.discretionary_paise||0)/100) + '.';\n"
            "if (dueToday.length) {\n"
            "  text += '\\nDue today: ' + dueToday.map(i => i.merchant + ' ₹' + Math.round(i.amount_paise/100)).join(', ') + '.';\n"
            "}\n"
            "return [{ json: { text } }];"
        )
    },
    "id": nid(),
    "name": "Compose brief",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [660, 0],
}
send_brief = telegram_send("Send daily brief", [880, 0], "={{ $json.text }}")
send_brief["parameters"]["chatId"] = "REPLACE_WITH_YOUR_TELEGRAM_CHAT_ID"

wf2 = workflow(
    "FinPilot - Daily brief",
    [trigger2, dashboard_call, radar_call, brief_code, send_brief],
    {
        **connect(
            ("Daily 08:00 IST", "GET /api/dashboard"),
            ("GET /api/dashboard", "GET /api/radar"),
            ("GET /api/radar", "Compose brief"),
            ("Compose brief", "Send daily brief"),
        ),
    },
)

# --- Workflow 3: Mandate alert (09:00 IST) ----------------------------------

trigger3 = schedule_trigger("Daily 09:00 IST", [0, 0], "0 30 3 * * *")  # 03:30 UTC = 09:00 IST
radar_call3 = http_node("GET /api/radar", [220, 0], "GET", "/api/radar", send_body=False)
filter_silent = {
    "parameters": {
        "jsCode": (
            "const items = $input.first().json.banner.items || [];\n"
            "const silent = items.filter(i => i.afa_band === 'SILENT' && !i.acknowledged);\n"
            "return silent.map(i => ({ json: i }));"
        )
    },
    "id": nid(),
    "name": "Filter silent mandates",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [440, 0],
}
alert_send = telegram_send(
    "Send mandate alert",
    [660, 0],
    "={{ $json.merchant }} debits ₹" + "{{ Math.round($json.amount_paise/100) }}" +
    " on {{ $json.due_date }} with no OTP — reply to revoke, or see the Revoke Kit in FinPilot.",
    chat_id_expr="REPLACE_WITH_YOUR_TELEGRAM_CHAT_ID",
)
alert_send["parameters"]["chatId"] = "REPLACE_WITH_YOUR_TELEGRAM_CHAT_ID"

wf3 = workflow(
    "FinPilot - Mandate alert",
    [trigger3, radar_call3, filter_silent, alert_send],
    {
        **connect(
            ("Daily 09:00 IST", "GET /api/radar"),
            ("GET /api/radar", "Filter silent mandates"),
            ("Filter silent mandates", "Send mandate alert"),
        ),
    },
)

# --- Workflow 4: Monthly summary (1st at 09:00) -----------------------------

trigger4 = schedule_trigger("Monthly 1st 09:00 IST", [0, 0], "0 30 3 1 * *")
summary_call = http_node("POST /api/summary/generate", [220, 0], "POST", "/api/summary/generate", body_params={})
summary_send = telegram_send(
    "Send monthly summary", [440, 0], "={{ $json.text || 'Summary unavailable: ' + $json.error }}"
)
summary_send["parameters"]["chatId"] = "REPLACE_WITH_YOUR_TELEGRAM_CHAT_ID"

wf4 = workflow(
    "FinPilot - Monthly summary",
    [trigger4, summary_call, summary_send],
    {
        **connect(
            ("Monthly 1st 09:00 IST", "POST /api/summary/generate"),
            ("POST /api/summary/generate", "Send monthly summary"),
        ),
    },
)

out = [wf1, wf2, wf3, wf4]
path = "finpilot-workflows.json"
with open(path, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print("wrote", path)
