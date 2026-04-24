import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for the RadiVault Buyer Portal + Hospital Dashboard
 * (feature-slug: portal-e2e).
 *
 * Purpose: CEO-meeting demo safety net. Every spec mocks the BFF boundary
 * with `page.route` so the tests are hermetic — no real central-ingest,
 * metadata-index, fulfillment, or Orthanc calls.
 *
 * The webServer block is configured with reuseExistingServer=true: if a
 * Next.js dev server is already bound to :3000 (Kyle's common workflow),
 * Playwright attaches to it instead of spinning up a second copy. When the
 * port is idle, Playwright boots `npm run dev` on its own.
 */
export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*\.spec\.ts/,
  fullyParallel: false, // Single browser, single-session demo — no need to race.
  forbidOnly: !!process.env.CI,
  retries: 0, // Demo safety net; a failed test must be eyeballed, not retried.
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
    // Next.js dev mode uses eval() for HMR runtime, but our CSP in
    // next.config.mjs is production-grade ("script-src 'self' 'unsafe-inline'"
    // — no 'unsafe-eval'). That's dev-spec FR-X-5 compliant for production
    // but blocks React hydration under dev. bypassCSP is a Playwright-only
    // override; real browsers hitting the dev server are unaffected.
    bypassCSP: true,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 120_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
