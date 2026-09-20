// FinPilot Budget Guard — click interception.
//
// amazon.js/flipkart.js originally only *observed* the DOM (a MutationObserver
// on a debounce) and showed the interstitial whenever it noticed a checkout
// page. That never stopped anything: by the time the debounce fired, a real
// click on "Place your order" had already submitted the form or fired the
// site's own navigation. The dialog appeared, if at all, on top of a page
// that was already leaving. This is the actual guard: it intercepts the
// click itself, in the capture phase, before the site's own listeners or a
// form submission ever run.

/**
 * Wires click interception for one site's checkout controls.
 *
 * `isCheckoutTrigger(el)` decides whether a clicked element is a checkout
 * action. `computeTotal()` returns the cart total in paise (or null).
 * `site` is the cooldown key ("amazon.in" / "flipkart.com").
 */
function finpilotGuardCheckoutClicks({ site, isCheckoutTrigger, computeTotal }) {
  const bypass = new WeakSet();

  document.addEventListener(
    "click",
    (event) => {
      // The interstitial's own "Continue anyway" button necessarily contains
      // a checkout word ("continue") — without this guard the click-guard
      // intercepts its own dialog's buttons and they stop working.
      if (event.target instanceof Element && event.target.closest("#finpilot-guard-overlay")) return;

      const target =
        event.target instanceof Element
          ? event.target.closest("button, a, input[type=submit], input[type=button]")
          : null;
      if (!target || !isCheckoutTrigger(target)) return;

      if (bypass.has(target)) {
        // This is our own re-dispatched click after "Continue anyway" — let
        // it proceed exactly once.
        bypass.delete(target);
        return;
      }

      event.preventDefault();
      event.stopImmediatePropagation();

      const proceed = () => {
        bypass.add(target);
        target.click();
      };

      chrome.storage.local.get("budget", async ({ budget }) => {
        const discretionary = budget?.discretionary_paise;
        const cartPaise = computeTotal();

        // Fail open: never block a purchase on our own missing data or error.
        if (discretionary == null || budget?.error || cartPaise == null) return proceed();
        if (cartPaise <= discretionary) return proceed();
        if (await finpilotInCooldown(site)) return proceed();

        finpilotShowInterstitial({
          cartPaise,
          discretionaryPaise: discretionary,
          onAction: (action) => {
            // Every outcome is reported, not just "wait". What the user did
            // when warned is the interesting signal, and the dashboard can
            // only show "Budget Guard stopped 3 purchases" if it hears about
            // the ones that were *not* stopped too.
            chrome.runtime.sendMessage({
              type: "guard-outcome",
              entry: {
                site,
                outcome: action,
                cart_paise: cartPaise,
                discretionary_paise: discretionary,
                url: window.location.href,
              },
            });
            if (action === "continue") proceed();
            // "wait" and "dismiss": do nothing — the click stays swallowed
            // and the page never navigates.
          },
        });
      });
    },
    true // capture: run before the page's own handlers and before a submit fires
  );
}
