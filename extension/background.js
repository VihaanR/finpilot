// FinPilot Budget Guard — background service worker.
//
// Owns the only network calls this extension makes: fetching the user's
// discretionary budget from FinPilot's own API and caching it in
// chrome.storage.local, where content scripts (which run inside the
// checkout page's origin, not the extension's) can read it without needing
// their own network permissions.
//
// DESIGN.md 10.5 originally specified the web app pushing a signed budget
// snapshot into storage via `externally_connectable` on login. This build's
// API has no auth (USER.md 8e — deliberate, documented), so that handshake
// buys nothing a direct fetch doesn't already give: the extension just asks
// the API itself, on the same cadence, with no extra moving parts.

const DEFAULT_API_BASE = "https://finpilot-w4ki.onrender.com";
const REFRESH_ALARM = "finpilot-budget-refresh";

async function apiBase() {
  const { apiBase } = await chrome.storage.local.get("apiBase");
  return apiBase || DEFAULT_API_BASE;
}

async function refreshBudget() {
  const base = await apiBase();
  try {
    const res = await fetch(`${base}/api/dashboard`);
    if (!res.ok) throw new Error(`dashboard ${res.status}`);
    const dashboard = await res.json();
    const sts = dashboard.safe_to_spend || {};
    await chrome.storage.local.set({
      budget: {
        discretionary_paise: sts.discretionary_paise ?? null,
        safe_daily_paise: sts.safe_daily_paise ?? null,
        as_of: dashboard.as_of ?? null,
        fetched_at: Date.now(),
        error: null,
      },
    });
  } catch (err) {
    const { budget } = await chrome.storage.local.get("budget");
    await chrome.storage.local.set({
      budget: { ...(budget || {}), error: String(err), fetched_at: Date.now() },
    });
  }
}

async function recordCooldown(entry) {
  const { cooldowns } = await chrome.storage.local.get("cooldowns");
  const list = Array.isArray(cooldowns) ? cooldowns : [];
  list.push({ ...entry, created_at: Date.now() });
  await chrome.storage.local.set({ cooldowns: list.slice(-20) });
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(REFRESH_ALARM, { periodInMinutes: 15 });
  refreshBudget();
});

chrome.runtime.onStartup.addListener(() => {
  refreshBudget();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === REFRESH_ALARM) refreshBudget();
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "refresh-budget") {
    refreshBudget().then(() => sendResponse({ ok: true }));
    return true; // async response
  }
  if (message?.type === "record-cooldown") {
    recordCooldown(message.entry).then(() => sendResponse({ ok: true }));
    return true;
  }
  return false;
});
