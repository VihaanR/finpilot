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
  if (rect.width <= 0 || rect.height <= 0) return false;
  // `offsetParent === null` is NOT a visibility test: it is also null for
  // every `position: fixed` element, which is exactly what a sticky order
  // summary or a bottom checkout bar usually is.
  const style = getComputedStyle(el);
  return style.visibility !== "hidden" && style.display !== "none";
}

/**
 * Reads a rupee amount from `el`'s combined text.
 *
 * Retailers routinely split one price across several elements — Amazon ships
 * the symbol, the whole part, the decimal point and the fraction as four
 * separate spans — so no single text node holds "₹" beside its digits and a
 * per-text-node parse finds nothing at all.
 *
 * The trap in reading the combined text instead is that the decimal point is
 * itself an element, and when a retailer omits it "40" and "00" concatenate
 * into ₹4,000 — a 100x overestimate that fires the interstitial on a delivery
 * fee. So when the combined text carries no decimal point and the final
 * fragment is exactly two digits, those two digits are read as the fraction.
 */
function finpilotAmountFromElement(el) {
  const text = (el.textContent || "").replace(/\s+/g, " ");
  const paise = finpilotParseRupees(text);
  if (paise === null) return null;
  if (text.includes(".")) return paise;

  const fragments = [];
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const t = (node.textContent || "").trim();
    if (t) fragments.push(t);
  }
  const last = fragments[fragments.length - 1];
  if (fragments.length > 1 && /^\d{2}$/.test(last) && paise >= 100 * 100) {
    return Math.round(paise / 100);
  }
  return paise;
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

// A real checkout page is full of rupee figures that are not the order
// total: EMI financing panels ("Total payable over 12 months"), crossed-out
// MRPs, "you save" banners, delivery fees, recommendation carousels. All of
// those can legitimately sit close to the checkout button, so "biggest
// number near the button" (the old rule) can and does latch onto one of
// them instead of the real total. A labelled total is worth more than
// proximity; these two lists say which label wins and which disqualifies.
const FINPILOT_TOTAL_LABEL_RE =
  /\b(order total|grand total|cart total|subtotal|sub-total|amount payable|payable amount|total amount|to pay|amount to pay)\b/i;
const FINPILOT_EXCLUDE_RE =
  /\b(emi|m\.?r\.?p\.?|list price|strike|original price|you save|savings|delivery|shipping|installment|instalment)\b/i;

function finpilotNearbyText(el, hops) {
  const parts = [el.textContent || ""];
  let node = el.previousElementSibling;
  if (node) parts.push(node.textContent || "");
  // Stop at <body>: climbing past it picks up <head> (title, injected
  // scripts, meta tags) — content with no relation to what's on screen.
  let ancestor = el;
  for (let i = 0; i < hops && ancestor.parentElement && ancestor !== document.body; i++) {
    ancestor = ancestor.parentElement;
    if (ancestor === document.body) break;
    if (ancestor.previousElementSibling) parts.push(ancestor.previousElementSibling.textContent || "");
  }
  return parts.join(" ");
}

function finpilotIsStrikethrough(el) {
  let node = el;
  for (let i = 0; i < 3 && node instanceof HTMLElement; i++) {
    if (getComputedStyle(node).textDecorationLine.includes("line-through")) return true;
    node = node.parentElement;
  }
  return false;
}

/**
 * Scans the page for rupee amounts and returns the most likely cart/order
 * total in paise, or null if nothing plausible is found.
 */
function finpilotHeuristicTotal() {
  const candidates = [];
  const seen = new Set();

  function consider(el) {
    if (!el || seen.has(el)) return;
    seen.add(el);
    if (!finpilotIsVisible(el)) return;
    if (finpilotIsStrikethrough(el)) return;
    const paise = finpilotAmountFromElement(el);
    if (paise === null || paise <= 0) return;
    const context = finpilotNearbyText(el, 3);
    if (FINPILOT_EXCLUDE_RE.test(context)) return;
    const labeled = FINPILOT_TOTAL_LABEL_RE.test(context);
    candidates.push({ paise, el, labeled });
  }

  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const text = node.textContent;
    if (!text || !text.includes("₹")) continue;
    const el = node.parentElement;
    if (!el) continue;
    if (finpilotParseRupees(text) !== null) {
      consider(el);
      continue;
    }
    // The symbol sits alone in its own element: climb to the nearest
    // ancestor that also carries digits, which is the price wrapper.
    let ancestor = el;
    while (ancestor && ancestor !== document.body) {
      if (/\d/.test(ancestor.textContent || "")) {
        consider(ancestor);
        break;
      }
      ancestor = ancestor.parentElement;
    }
  }
  if (candidates.length === 0) return null;

  // A figure explicitly labelled as a total/subtotal beats mere proximity to
  // the checkout button — that proximity rule is what let an EMI or MRP
  // panel outrank the real total. Only fall back to "biggest number near the
  // button" when nothing on the page carries a total-shaped label at all.
  const labeled = candidates.filter((c) => c.labeled);
  const pool = labeled.length > 0 ? labeled : candidates;
  const nearCheckout = pool.filter((c) => finpilotNearCheckoutControl(c.el));
  const finalPool = nearCheckout.length > 0 ? nearCheckout : pool;
  const best = finalPool.reduce((max, c) => (c.paise > max.paise ? c : max), finalPool[0]);
  return best.paise;
}
