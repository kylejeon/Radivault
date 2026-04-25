import { expect, test } from "@playwright/test";

import {
  blockRealUpstream,
  DEFAULT_FACETS,
  DEFAULT_STUDIES,
  filterStudies,
  mockSearchFacets,
  mockSearchStudies,
} from "./fixtures/mocks";
import {
  injectBuyerSession,
  injectBuyerSessionV2,
} from "./fixtures/session";

/**
 * Regression spec — BLOCKER #1 from qa-report-d13-demo-rehearsal.
 *
 * The v0.2 email/password signin route sets `session.buyerPk` and
 * `delete session.apiKey`. Three RSC route guards (/search, /dashboard,
 * /studies/[uid]) previously checked `!session?.apiKey` only, which
 * meant a freshly-signed-in v0.2 buyer was redirected back to /signin →
 * /search → /signin … infinitely.
 *
 * This spec asserts that:
 *   1. The route guards accept the v0.2 cookie shape (buyerPk only,
 *      no apiKey) — i.e. /search and /dashboard return 200 and stay.
 *   2. The legacy paste-mode cookie shape (apiKey only, no buyerPk)
 *      still satisfies the guards — fix did not regress the 90-day
 *      deprecation window for paste-mode callers.
 *
 * Why injected cookies and not the live signin form:
 *   The signup endpoint enforces 1/min/IP and the signin form path is
 *   exercised by buyer-auth.spec.ts:75 ("signin happy path lands on
 *   /search"). Injecting a sealed cookie that mirrors the exact shape
 *   the signin route writes (BuyerSession with buyerPk + buyerId +
 *   email + sessionVersion + locale + tier + signedInAt; no apiKey)
 *   exercises the same guards without competing for the rate-limit
 *   bucket. The seal uses the production iron-session cipher so the
 *   server treats the cookie as genuine.
 *
 * Fixture mocks (`/api/search/**`, `/api/orders/**`) are stubbed so the
 * RSC pages render without a live upstream.
 */

test.describe("auth redirect-no-loop (BLOCKER #1 regression)", () => {
  test.beforeEach(async ({ page }) => {
    // Stub upstream so /search and /dashboard can render after the
    // guard passes. Auth endpoints are intentionally untouched.
    await page.route("**/api/search/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0, modality: [] }),
      });
    });
    await page.route("**/api/orders/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [] }),
      });
    });
  });

  test("v0.2 (buyerPk only) — /search lands and stays (no redirect loop)", async ({
    page,
    context,
  }) => {
    await injectBuyerSessionV2(context);

    const response = await page.goto("/search");
    // The bug pre-fix returned a 307 → /signin chain. The fix yields a
    // direct 200 with the URL unchanged.
    expect(response?.status()).toBe(200);
    expect(new URL(page.url()).pathname).toBe("/search");
  });

  test("v0.2 (buyerPk only) — /dashboard lands and stays (no redirect loop)", async ({
    page,
    context,
  }) => {
    await injectBuyerSessionV2(context);

    const response = await page.goto("/dashboard");
    expect(response?.status()).toBe(200);
    expect(new URL(page.url()).pathname).toBe("/dashboard");
  });

  test("v0.2 (buyerPk only) — /studies/[uid] gate accepts the session", async ({
    page,
    context,
  }) => {
    await injectBuyerSessionV2(context);

    // Stub the detail endpoint so the page renders past the gate.
    await page.route("**/api/search/studies/*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          uid: "1.2.3.4.demo",
          modality: "MR",
          hospital_opaque_id: "1d3fed8642a2bf73",
          metadata: {},
        }),
      });
    });

    const response = await page.goto("/studies/1.2.3.4.demo");
    expect(response?.status()).toBe(200);
    expect(new URL(page.url()).pathname).toBe("/studies/1.2.3.4.demo");
  });

  test("legacy paste-mode (apiKey only) — /search still reachable", async ({
    page,
    context,
  }) => {
    // No buyerPk on this cookie — pure legacy shape from sealBuyerSession().
    // The fix must accept either branch of the OR-guard.
    await blockRealUpstream(page);
    await mockSearchFacets(page, DEFAULT_FACETS);
    await mockSearchStudies(page, (body) => filterStudies(body, DEFAULT_STUDIES));
    await injectBuyerSession(context);

    const response = await page.goto("/search");
    expect(response?.status()).toBe(200);
    expect(new URL(page.url()).pathname).toBe("/search");
  });

  test("legacy paste-mode (apiKey only) — /dashboard still reachable", async ({
    page,
    context,
  }) => {
    await injectBuyerSession(context);

    const response = await page.goto("/dashboard");
    expect(response?.status()).toBe(200);
    expect(new URL(page.url()).pathname).toBe("/dashboard");
  });
});
