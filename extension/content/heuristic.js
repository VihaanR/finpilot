// FinPilot Budget Guard — fallback cart-total detector.
//
// Site-specific selectors in amazon.js / flipkart.js break whenever the
// retailer reships their markup (DESIGN.md 10.5 calls this out explicitly).
// This heuristic has no knowledge of either site's DOM structure: it scans
// for rupee-prefixed numbers near a checkout-shaped button and takes the
// largest one, which is almost always the order total rather than a line
// item or a shipping fee.

const FINPILOT_RUPEE_RE = /₹\s?([\d,]+(?:\.\d{1,2})?)/;
const FINPILOT_CHECKOUT_WORDS = [
  "place order",
  "proceed to buy",
  "proceed to checkout",
  "buy now",
  "continue",
  "pay now",
];

function finpilotParseRupees(text) {
  const match = FINPILOT_RUPEE_RE.exec(text);
  if (!match) return null;
  const digits = match[1].replace(/,/g, "");
  const rupees = parseFloat(digits);
  if (!Number.isFinite(rupees)) return null;
  return Math.round(rupees * 100); // paise
}

function finpilotIsVisible(el) {
  if (!(el instanceof HTMLElement)) return false;
  const rect = el.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0 && el.offsetParent !== null;
}

function finpilotNearCheckoutControl(el) {
  const rect = el.getBoundingClientRect();
  const buttons = document.querySelectorAll("button, a, input[type=submit]");
  for (const btn of buttons) {
    const label = (btn.textContent || btn.value || "").trim().toLowerCase();
    if (!FINPILOT_CHECKOUT_WORDS.some((w) => label.includes(w))) continue;
    const btnRect = btn.getBoundingClientRect();
    if (Math.abs(btnRect.top - rect.top) < 400) return true;
  }
  return false;
}

/**
 * Scans the page for rupee amounts and returns the most likely cart/order
 * total in paise, or null if nothing plausible is found.
 */
function finpilotHeuristicTotal() {
  const candidates = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const text = node.textContent;
    if (!text || !text.includes("₹")) continue;
    const el = node.parentElement;
    if (!el || !finpilotIsVisible(el)) continue;
    const paise = finpilotParseRupees(text);
    if (paise === null || paise <= 0) continue;
    candidates.push({ paise, el });
  }
  if (candidates.length === 0) return null;

  const nearCheckout = candidates.filter((c) => finpilotNearCheckoutControl(c.el));
  const pool = nearCheckout.length > 0 ? nearCheckout : candidates;
  const best = pool.reduce((max, c) => (c.paise > max.paise ? c : max), pool[0]);
  return best.paise;
}
