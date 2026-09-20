/**
 * The accessibility sweep (DESIGN.md §11, BUILD_TASKS.md T08 and T15).
 *
 * Every route, both themes, zero axe violations. This exists as a committed
 * spec rather than a one-off script because an accessibility claim that is
 * only ever checked by hand is a claim that quietly stops being true.
 *
 * Run against the production build with the API live:
 *
 *   cd services/api && .venv/Scripts/python.exe -m uvicorn app.main:app
 *   cd apps/web && npm run build && npm start
 *   cd apps/web && npx playwright test
 *
 * `/chat` is included. Its answer region only renders once a question has
 * been asked, so one spec asks a real question — the single place this suite
 * spends Gemini quota, and the reason it is marked `@quota`. Skip it with
 * `--grep-invert @quota` when quota matters more than coverage.
 */

import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const ROUTES = [
  "/",
  "/chat",
  "/radar",
  "/goals",
  "/transactions",
  "/upload",
  "/vault",
  "/accessibility",
] as const;

const THEMES = ["light", "dark"] as const;

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function setTheme(page: Page, theme: (typeof THEMES)[number]) {
  await page.emulateMedia({ colorScheme: theme });
  await page.evaluate((t) => document.documentElement.setAttribute("data-theme", t), theme);
}

async function scan(page: Page) {
  return new AxeBuilder({ page }).withTags(WCAG).analyze();
}

for (const route of ROUTES) {
  for (const theme of THEMES) {
    test(`axe: ${route} (${theme})`, async ({ page }) => {
      const errors: string[] = [];
      page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
      page.on("pageerror", (e) => errors.push(e.message));

      await page.goto(route);
      await setTheme(page, theme);
      await page.waitForLoadState("networkidle");

      const results = await scan(page);
      expect(
        results.violations.map((v) => `${v.id}: ${v.help}`),
        `axe violations on ${route} (${theme})`,
      ).toEqual([]);

      // A page that throws is not accessible either, whatever axe says.
      expect(errors, `console errors on ${route} (${theme})`).toEqual([]);
    });
  }
}

test("skip link is the first focusable element on every route", async ({ page }) => {
  for (const route of ROUTES) {
    await page.goto(route);
    // Without waiting, Tab can fire before the document has focus and lands
    // nowhere — which passes on an idle machine and fails in a full run.
    await page.waitForLoadState("domcontentloaded");
    await page.locator("body").waitFor({ state: "attached" });
    await page.keyboard.press("Tab");
    const focused = await page.evaluate(() => document.activeElement?.textContent?.trim());
    expect(focused, `first Tab stop on ${route}`).toContain("Skip to main content");
  }
});

test("no route scrolls horizontally at 200% zoom", async ({ page }) => {
  // 1280px at 200% zoom is a 640px viewport (DESIGN.md §11: zoom to 200%
  // must lose no content or function).
  await page.setViewportSize({ width: 640, height: 400 });
  for (const route of ROUTES) {
    await page.goto(route);
    await page.waitForLoadState("networkidle");
    const overflows = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    );
    expect(overflows, `${route} scrolls horizontally at 640px`).toBe(false);
  }
});

test("chat is keyboard-operable and suggestions are real buttons", async ({ page }) => {
  await page.goto("/chat");
  const suggestion = page.getByRole("button", { name: /Where did I spend the most/i });
  await expect(suggestion).toBeVisible();
  await suggestion.focus();
  await expect(suggestion).toBeFocused();

  const input = page.getByLabel(/Ask a question about your money/i);
  await input.fill("test");
  await expect(page.getByRole("button", { name: "Ask" })).toBeEnabled();
});

test("@quota chat renders a cited answer with an openable citation", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/chat");
  await page.getByRole("button", { name: /Where did I spend the most/i }).click();

  // The answer region is aria-live, so it must exist before the answer lands.
  const live = page.locator('[aria-live="polite"]');
  await expect(live).toHaveAttribute("aria-busy", "true");

  const answer = page.locator("article p").first();
  await expect(answer).toContainText(/₹/, { timeout: 75_000 });
  await expect(live).toHaveAttribute("aria-busy", "false");

  // A cited figure is a button that opens the drawer.
  const chip = page.getByRole("button", { name: /Show the \d+ transactions? behind this figure/i }).first();
  await expect(chip).toBeVisible();
  await chip.click();
  await expect(page.getByRole("dialog")).toBeVisible();

  // Escape closes it and focus returns to the chip that opened it.
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(chip).toBeFocused();

  const results = await scan(page);
  expect(results.violations.map((v) => v.id), "axe on the answered chat page").toEqual([]);
});
