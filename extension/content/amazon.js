// FinPilot Budget Guard — Amazon.in cart/checkout detection.
//
// Primary selectors target the cart and buy-now flows as of Sep 2026.
// Amazon reships markup often enough that these are expected to go stale;
// heuristic.js's ₹-numeric fallback is what keeps this alive when they do
// (DESIGN.md 10.5, BUILD_TASKS.md T13: "if primary selectors fail, the
// heuristic still finds the total").

const FINPILOT_AMAZON_SELECTORS = [
  "#sc-subtotal-amount-activecart .a-offscreen",
  "#sc-subtotal-amount-buybox .a-offscreen",
  "#subtotals-marketplace-table .grand-total-price",
  "#grand-total-price",
  ".a-price.priceToPay .a-offscreen",
];

function finpilotAmazonPrimaryTotal() {
  for (const selector of FINPILOT_AMAZON_SELECTORS) {
    const el = document.querySelector(selector);
    if (!el) continue;
    const paise = finpilotParseRupees(el.textContent || "");
    if (paise) return paise;
  }
  return null;
}

function finpilotAmazonLooksLikeCheckout() {
  const path = window.location.pathname;
  return (
    path.includes("/cart") ||
    path.includes("/gp/buy") ||
    path.includes("/checkout") ||
    document.querySelector("#buy-now-button, #placeYourOrder, input[name='placeYourOrder1']") !== null
  );
}

function finpilotAmazonRun() {
  if (!finpilotAmazonLooksLikeCheckout()) return;
  if (window.__finpilotGuardShown) return;

  const primary = finpilotAmazonPrimaryTotal();
  const cartPaise = primary ?? finpilotHeuristicTotal();
  if (!cartPaise) return;

  chrome.storage.local.get("budget", async ({ budget }) => {
    const discretionary = budget?.discretionary_paise;
    if (discretionary == null || budget?.error) return; // fail open, never block on our own error
    if (cartPaise <= discretionary) return;
    if (await finpilotInCooldown("amazon.in")) return; // user already chose to wait

    window.__finpilotGuardShown = true;
    finpilotShowInterstitial({
      cartPaise,
      discretionaryPaise: discretionary,
      onAction: (action) => {
        if (action === "wait") {
          chrome.runtime.sendMessage({
            type: "record-cooldown",
            entry: { site: "amazon.in", cart_paise: cartPaise, url: window.location.href },
          });
        }
      },
    });
  });
}

// Amazon's cart/checkout pages are heavily client-rendered; give the DOM a
// moment to settle, then watch for further changes (quantity edits, etc.)
// without re-showing the dialog once shown on this page load. Debounced —
// an unthrottled observer on a busy page would re-scan the whole body on
// every mutation. This is an early, informational warning only — it cannot
// stop a click that has already happened.
let finpilotAmazonDebounce = null;
function finpilotAmazonScheduleRun() {
  clearTimeout(finpilotAmazonDebounce);
  finpilotAmazonDebounce = setTimeout(finpilotAmazonRun, 600);
}

setTimeout(finpilotAmazonRun, 1200);
const finpilotAmazonObserver = new MutationObserver(finpilotAmazonScheduleRun);
finpilotAmazonObserver.observe(document.body, { childList: true, subtree: true });

// The actual guard: intercept the checkout click itself so the page cannot
// navigate away before the budget check runs.
const FINPILOT_AMAZON_CHECKOUT_SELECTOR =
  "#buy-now-button, #placeYourOrder, input[name='placeYourOrder1'], #submitOrderButtonId, #hlb-view-cart-announce";

finpilotGuardCheckoutClicks({
  site: "amazon.in",
  isCheckoutTrigger(el) {
    if (el.closest(FINPILOT_AMAZON_CHECKOUT_SELECTOR)) return true;
    const label = (el.textContent || el.value || "").trim().toLowerCase();
    return FINPILOT_CHECKOUT_WORDS.some((w) => label.includes(w));
  },
  computeTotal() {
    return finpilotAmazonPrimaryTotal() ?? finpilotHeuristicTotal();
  },
});
