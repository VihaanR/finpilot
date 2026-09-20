# FinPilot Budget Guard

MV3 Chrome extension (BUILD_TASKS.md T13, DESIGN.md §10.5). Warns before a
purchase on Amazon.in or Flipkart pushes you past FinPilot's discretionary
budget for the month, with a "Wait 24 hours" cooling-off option.

## Load it (ships unpacked — see DESIGN.md §10.5 for why)

1. `chrome://extensions` → enable **Developer mode** (top right)
2. **Load unpacked** → select this `extension/` folder
3. Open the extension's popup (puzzle-piece icon in the toolbar) to confirm
   it shows a discretionary-budget figure — it fetches live from
   `https://finpilot-w4ki.onrender.com/api/dashboard` on install and every
   15 minutes after. Switch the **API** dropdown to "Local (localhost:8001)"
   when developing against a local API.
4. Visit an Amazon.in or Flipkart cart page with a total above your
   discretionary budget — the interstitial should appear.

## How cart-total detection works

Each site has primary DOM selectors (`content/amazon.js`, `content/flipkart.js`)
plus a shared fallback heuristic (`content/heuristic.js`) that scans for
₹-prefixed numbers near a checkout-shaped button and takes the largest one.
Retail sites reship markup often — the heuristic is what keeps this working
when a selector goes stale, not a nice-to-have. Verified against fixture
pages in `test-fixtures/`, including one with every known selector
deliberately absent, to confirm the fallback alone still finds the total.
**Not yet verified against a live Amazon.in or Flipkart cart** — that needs
a real account and cart, which is a manual, owner-side check.

## A deliberate deviation from DESIGN.md §10.5

The spec called for the web app to push a signed budget snapshot into
`chrome.storage.local` via `externally_connectable` on login. This build's
API has no auth (USER.md §8e — deliberate, documented), so that handshake
would add a login dependency without adding any actual protection: the
extension just fetches `/api/dashboard` directly instead, same data, on the
same cadence, with one fewer moving part.

## What "Wait 24 hours" actually does right now

It records a cooldown entry in `chrome.storage.local` (visible in the popup
under "Paused purchases") and, if `n8n/finpilot-workflows.json` is imported
and running with the FinPilot API and Telegram credentials configured, could
be extended to enqueue the next-day Telegram nudge DESIGN.md §10.5 describes.
That wiring is not built — the extension does not have the owner's Telegram
bot token, and building it against nothing to actually notify would be
unverifiable. This is the honest current state, not the target state.

## What the extension stores

Only `budget` (the fetched discretionary figures), `cooldowns` (site, cart
total, timestamp — no product details, no transaction data), and the chosen
`apiBase`. No account numbers, merchant names, or transaction ids ever reach
it — verify with `chrome://extensions` → Details → "Inspect views" →
Application → Storage.
