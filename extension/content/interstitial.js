// FinPilot Budget Guard — the accessible interstitial (DESIGN.md 10.5).
//
// role="alertdialog", focus-trapped, Escape closes and returns focus to
// whatever had it before, colour is never the only signal (every action is
// also a labelled button, the warning also states the figures in words).

function finpilotFormatRupees(paise) {
  const rupees = Math.round(paise / 100);
  return "₹" + rupees.toLocaleString("en-IN");
}

const FINPILOT_COOLDOWN_MS = 24 * 60 * 60 * 1000;

/**
 * Resolves true when this site is inside the 24-hour window the user asked
 * for by clicking "Wait 24 hours".
 *
 * Without this the button is a lie: it wrote a cooldown record that nothing
 * ever read, so the very next page load showed the same dialog again.
 */
function finpilotInCooldown(site) {
  return new Promise((resolve) => {
    chrome.storage.local.get("cooldowns", ({ cooldowns }) => {
      const list = Array.isArray(cooldowns) ? cooldowns : [];
      const cutoff = Date.now() - FINPILOT_COOLDOWN_MS;
      resolve(list.some((c) => c && c.site === site && c.created_at > cutoff));
    });
  });
}

/**
 * Shows the interstitial. `onAction` receives "continue" | "wait" | "dismiss".
 * Returns nothing; the dialog removes itself on any action or Escape.
 */
function finpilotShowInterstitial({ cartPaise, discretionaryPaise, onAction }) {
  if (document.getElementById("finpilot-guard-overlay")) return; // already open

  const previouslyFocused = document.activeElement;

  const overlay = document.createElement("div");
  overlay.id = "finpilot-guard-overlay";

  const dialog = document.createElement("div");
  dialog.id = "finpilot-guard-dialog";
  dialog.setAttribute("role", "alertdialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-labelledby", "finpilot-guard-title");
  dialog.setAttribute("aria-describedby", "finpilot-guard-desc");

  const title = document.createElement("h2");
  title.id = "finpilot-guard-title";
  title.textContent = "This purchase is over your FinPilot budget";

  const desc = document.createElement("p");
  desc.id = "finpilot-guard-desc";
  desc.textContent =
    `This ${finpilotFormatRupees(cartPaise)} purchase is more than the ` +
    `${finpilotFormatRupees(discretionaryPaise)} you have left to spend this month.`;

  const actions = document.createElement("div");
  actions.className = "finpilot-guard-actions";

  function close(action) {
    overlay.remove();
    document.removeEventListener("keydown", onKeydown, true);
    if (previouslyFocused instanceof HTMLElement) previouslyFocused.focus();
    if (onAction) onAction(action);
  }

  function makeButton(label, className, action) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = label;
    btn.className = className;
    btn.addEventListener("click", () => close(action));
    return btn;
  }

  const waitBtn = makeButton("Wait 24 hours", "finpilot-guard-primary", "wait");
  const wishlistBtn = makeButton("Save to wishlist instead", "finpilot-guard-secondary", "dismiss");
  const continueBtn = makeButton("Continue anyway", "finpilot-guard-secondary", "continue");

  actions.append(waitBtn, wishlistBtn, continueBtn);
  dialog.append(title, desc, actions);
  overlay.append(dialog);
  document.body.append(overlay);

  const focusable = [waitBtn, wishlistBtn, continueBtn];

  function onKeydown(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      close("dismiss");
      return;
    }
    if (e.key !== "Tab") return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  document.addEventListener("keydown", onKeydown, true);
  waitBtn.focus();
}
