import { test, expect } from "@playwright/test";
import path from "node:path";
import { pathToFileURL } from "node:url";

/**
 * Budget Guard regression suite.
 *
 * The extension's own verification was a one-off script that was never
 * committed, so nothing guarded the cart-total parser against a regression.
 * These specs drive the real `extension/content/*.js` sources against the
 * committed fixtures — no extension install, no API, no web server needed,
 * because the parser and the interstitial are both pure DOM code.
 */

const EXT = path.resolve(__dirname, "../../../extension");
const fixture = (name: string) =>
  pathToFileURL(path.join(EXT, "test-fixtures", name)).href;

async function loadGuardScripts(page: import("@playwright/test").Page) {
  await page.addScriptTag({ path: path.join(EXT, "content/heuristic.js") });
  await page.addScriptTag({ path: path.join(EXT, "content/interstitial.js") });
}

test.describe("cart-total heuristic", () => {
  test("finds the order total when every known selector is absent", async ({ page }) => {
    await page.goto(fixture("amazon-cart-heuristic-only.html"));
    await loadGuardScripts(page);
    // ₹9,999.00 order total, not the ₹40.00 delivery fee.
    expect(await page.evaluate(() => finpilotHeuristicTotal())).toBe(999900);
  });

  test("finds the total in Amazon's split symbol/whole/fraction markup", async ({ page }) => {
    await page.goto(fixture("amazon-cart-split-price.html"));
    await loadGuardScripts(page);
    // No single text node holds "₹" beside its digits here — this is the
    // markup a real amazon.in cart actually ships.
    expect(await page.evaluate(() => finpilotHeuristicTotal())).toBe(999900);
  });

  test("reads a split price with no decimal element as rupees, not 100x", async ({ page }) => {
    await page.goto(fixture("amazon-cart-split-price.html"));
    await loadGuardScripts(page);
    // The ₹40.00 delivery fee ships as "₹" + "40" + "00" with no decimal
    // element. Read naively that concatenates to ₹4,000 and would fire the
    // interstitial on a delivery fee.
    const fee = await page.evaluate(() => {
      const blocks = Array.from(document.querySelectorAll(".a-price"));
      const el = blocks[blocks.length - 1] as HTMLElement;
      return finpilotAmountFromElement(el);
    });
    expect(fee).toBe(4000);
  });

  test("parses a whole-text rupee figure exactly, in paise", async ({ page }) => {
    await page.goto(fixture("amazon-cart.html"));
    await loadGuardScripts(page);
    expect(await page.evaluate(() => finpilotParseRupees("Subtotal: ₹18,499.00"))).toBe(1849900);
    expect(await page.evaluate(() => finpilotParseRupees("₹40"))).toBe(4000);
    expect(await page.evaluate(() => finpilotParseRupees("no price here"))).toBeNull();
  });

  test("prefers the labelled order total over a nearby EMI financing figure", async ({ page }) => {
    await page.goto(fixture("amazon-cart-emi-panel.html"));
    await loadGuardScripts(page);
    // The old "biggest ₹ figure near the checkout button" rule picked the
    // ₹5,93,990 EMI repayment total over the real ₹32,310 order total —
    // exactly the inaccurate-amount bug reported against a live cart.
    expect(await page.evaluate(() => finpilotHeuristicTotal())).toBe(3231000);
  });
});

test.describe("24-hour cooldown", () => {
  async function withCooldowns(page: import("@playwright/test").Page, cooldowns: unknown[]) {
    await page.goto(fixture("amazon-cart.html"));
    await page.evaluate((c) => {
      (window as any).chrome = {
        storage: { local: { get: (_k: string, cb: (v: unknown) => void) => cb({ cooldowns: c }) } },
      };
    }, cooldowns);
    await loadGuardScripts(page);
  }

  test("suppresses the dialog for the site the user chose to wait on", async ({ page }) => {
    await withCooldowns(page, [{ site: "amazon.in", created_at: Date.now() - 60_000 }]);
    expect(await page.evaluate(() => finpilotInCooldown("amazon.in"))).toBe(true);
  });

  test("does not leak the cooldown to the other retailer", async ({ page }) => {
    await withCooldowns(page, [{ site: "amazon.in", created_at: Date.now() - 60_000 }]);
    expect(await page.evaluate(() => finpilotInCooldown("flipkart.com"))).toBe(false);
  });

  test("expires after 24 hours", async ({ page }) => {
    const old = Date.now() - 25 * 60 * 60 * 1000;
    await withCooldowns(page, [{ site: "amazon.in", created_at: old }]);
    expect(await page.evaluate(() => finpilotInCooldown("amazon.in"))).toBe(false);
  });
});

test.describe("interstitial accessibility contract", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(fixture("amazon-cart.html"));
    await loadGuardScripts(page);
    await page.evaluate(() => {
      (window as any).__action = null;
      finpilotShowInterstitial({
        cartPaise: 1849900,
        discretionaryPaise: 500000,
        onAction: (a: string) => ((window as any).__action = a),
      });
    });
  });

  test("is an alertdialog naming both figures, focused on the first action", async ({ page }) => {
    const dialog = page.locator("#finpilot-guard-dialog");
    await expect(dialog).toHaveAttribute("role", "alertdialog");
    await expect(dialog).toHaveAttribute("aria-modal", "true");
    await expect(page.locator("#finpilot-guard-desc")).toContainText("₹18,499");
    await expect(page.locator("#finpilot-guard-desc")).toContainText("₹5,000");
    await expect(page.locator("button.finpilot-guard-primary")).toBeFocused();
  });

  test("traps Tab between the three actions", async ({ page }) => {
    const labels = async () => page.evaluate(() => document.activeElement?.textContent);
    expect(await labels()).toBe("Wait 24 hours");
    await page.keyboard.press("Tab");
    expect(await labels()).toBe("Save to wishlist instead");
    await page.keyboard.press("Tab");
    expect(await labels()).toBe("Continue anyway");
    await page.keyboard.press("Tab"); // wraps, never escapes to the page
    expect(await labels()).toBe("Wait 24 hours");
    await page.keyboard.press("Shift+Tab");
    expect(await labels()).toBe("Continue anyway");
  });

  test("Escape closes it and reports the action", async ({ page }) => {
    await page.keyboard.press("Escape");
    await expect(page.locator("#finpilot-guard-overlay")).toHaveCount(0);
    expect(await page.evaluate(() => (window as any).__action)).toBe("dismiss");
  });

  test("each button closes it with its own action", async ({ page }) => {
    await page.locator("button.finpilot-guard-primary").click();
    await expect(page.locator("#finpilot-guard-overlay")).toHaveCount(0);
    expect(await page.evaluate(() => (window as any).__action)).toBe("wait");
  });
});

test.describe("checkout click interception", () => {
  // amazon.js's old passive MutationObserver approach only ever *displayed*
  // the interstitial after the fact — it never stopped a click that had
  // already submitted the form or fired the site's own navigation. This
  // fixture has a real `<a href="#navigated">` checkout link, so these specs
  // prove the click itself is what gets blocked, not just that a dialog
  // shows up somewhere.
  async function loadAmazonGuard(
    page: import("@playwright/test").Page,
    opts: { budget?: Record<string, unknown>; cooldowns?: unknown[] } = {}
  ) {
    await page.goto(fixture("amazon-cart-navigable.html"));
    await page.evaluate(
      ({ budget, cooldowns }) => {
        const sent: unknown[] = [];
        (window as any).__sentMessages = sent;
        (window as any).chrome = {
          storage: {
            local: {
              get: (_keys: unknown, cb: (v: unknown) => void) => cb({ budget, cooldowns }),
            },
          },
          runtime: {
            sendMessage: (msg: unknown) => sent.push(msg),
          },
        };
      },
      { budget: opts.budget ?? null, cooldowns: opts.cooldowns ?? [] }
    );
    await page.addScriptTag({ path: path.join(EXT, "content/interstitial.js") });
    await page.addScriptTag({ path: path.join(EXT, "content/heuristic.js") });
    await page.addScriptTag({ path: path.join(EXT, "content/click-guard.js") });
    await page.addScriptTag({ path: path.join(EXT, "content/amazon.js") });
  }

  test("blocks navigation and shows the interstitial when the cart is over budget", async ({ page }) => {
    await loadAmazonGuard(page, { budget: { discretionary_paise: 500000 } }); // ₹5,000 left; cart is ₹18,499
    await page.click("#placeYourOrder");
    await expect(page.locator("#finpilot-guard-overlay")).toBeVisible();
    expect(await page.evaluate(() => window.location.hash)).toBe(""); // never navigated
  });

  test("Continue anyway lets the original click through", async ({ page }) => {
    await loadAmazonGuard(page, { budget: { discretionary_paise: 500000 } });
    await page.click("#placeYourOrder");
    await page.locator(".finpilot-guard-secondary", { hasText: "Continue anyway" }).click();
    await expect(page.locator("#finpilot-guard-overlay")).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => window.location.hash)).toBe("#navigated");
  });

  test("Wait 24 hours keeps the click blocked and records a cooldown", async ({ page }) => {
    await loadAmazonGuard(page, { budget: { discretionary_paise: 500000 } });
    await page.click("#placeYourOrder");
    await page.locator(".finpilot-guard-primary", { hasText: "Wait 24 hours" }).click();
    expect(await page.evaluate(() => window.location.hash)).toBe("");
    const sent = await page.evaluate(() => (window as any).__sentMessages);
    expect(sent).toEqual([
      expect.objectContaining({ type: "record-cooldown", entry: expect.objectContaining({ site: "amazon.in" }) }),
    ]);
  });

  test("does not intercept a cart within budget", async ({ page }) => {
    await loadAmazonGuard(page, { budget: { discretionary_paise: 5000000 } }); // ₹50,000 left
    await page.click("#placeYourOrder");
    await expect(page.locator("#finpilot-guard-overlay")).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => window.location.hash)).toBe("#navigated");
  });

  test("fails open when no budget data is available yet", async ({ page }) => {
    await loadAmazonGuard(page, { budget: null });
    await page.click("#placeYourOrder");
    await expect(page.locator("#finpilot-guard-overlay")).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => window.location.hash)).toBe("#navigated");
  });
});

declare function finpilotHeuristicTotal(): number | null;
declare function finpilotInCooldown(site: string): Promise<boolean>;
declare function finpilotAmountFromElement(el: HTMLElement): number | null;
declare function finpilotParseRupees(text: string): number | null;
declare function finpilotShowInterstitial(opts: {
  cartPaise: number;
  discretionaryPaise: number;
  onAction?: (a: string) => void;
}): void;
