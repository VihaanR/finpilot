import { defineConfig, devices } from "@playwright/test";

/**
 * Runs against the **production build**, not `next dev`.
 *
 * The three defects the first browser pass caught were all runtime-only —
 * including a missing import on a path `next build` type-checks but never
 * executes. Dev-mode overlays and hydration differences hide exactly that
 * class of bug, so the suite drives what the user would actually load.
 *
 * The API is expected to be running separately on :8000; it holds the ledger
 * and is not this config's to start.
 */
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  timeout: 45_000,
  use: {
    baseURL: process.env.WEB_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    viewport: { width: 1440, height: 1100 },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: process.env.WEB_BASE_URL
    ? undefined
    : {
        command: "npm start",
        url: "http://localhost:3000",
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
