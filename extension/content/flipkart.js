// FinPilot Budget Guard — Flipkart cart/checkout detection.
//
// Flipkart's class names are obfuscated and rotate frequently (a well-known
// scraping pain point), so the primary selectors below are expected to go
// stale faster than Amazon's — which is exactly the case heuristic.js's
// ₹-numeric fallback exists for (DESIGN.md 10.5).

const FINPILOT_FLIPKART_SELECTORS = [
  "[class*='TotalPrice'] [class*='amount']",
  "[data-testid='cart-total-amount']",
  "._30jeq3", // legacy price class, kept as a best-effort extra try
];

function finpilotFlipkartPrimaryTotal() {
  for (const selector of FINPILOT_FLIPKART_SELECTORS) {
    const el = document.querySelector(selector);
    if (!el) continue;
    const paise = finpilotParseRupees(el.textContent || "");
    if (paise) return paise;
  }
  return null;
}

function finpilotFlipkartLooksLikeCheckout() {
  const path = window.location.pathname;
  return path.includes("/viewcart") || path.includes("/checkout");
}

function finpilotFlipkartRun() {
  if (!finpilotFlipkartLooksLikeCheckout()) return;
  if (window.__finpilotGuardShown) return;

  const primary = finpilotFlipkartPrimaryTotal();
  const cartPaise = primary ?? finpilotHeuristicTotal();
  if (!cartPaise) return;

  chrome.storage.local.get("budget", ({ budget }) => {
    const discretionary = budget?.discretionary_paise;
    if (discretionary == null || budget?.error) return;
    if (cartPaise <= discretionary) return;

    window.__finpilotGuardShown = true;
    finpilotShowInterstitial({
      cartPaise,
      discretionaryPaise: discretionary,
      onAction: (action) => {
        if (action === "wait") {
          chrome.runtime.sendMessage({
            type: "record-cooldown",
            entry: { site: "flipkart.com", cart_paise: cartPaise, url: window.location.href },
          });
        }
      },
    });
  });
}

let finpilotFlipkartDebounce = null;
function finpilotFlipkartScheduleRun() {
  clearTimeout(finpilotFlipkartDebounce);
  finpilotFlipkartDebounce = setTimeout(finpilotFlipkartRun, 600);
}

setTimeout(finpilotFlipkartRun, 1200);
const finpilotFlipkartObserver = new MutationObserver(finpilotFlipkartScheduleRun);
finpilotFlipkartObserver.observe(document.body, { childList: true, subtree: true });
