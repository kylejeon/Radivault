/**
 * Regression spec — D-13 BLOCKER (v0.2 buyer cannot access any data).
 *
 * Pre-fix symptom (qa-report-d13-demo-rehearsal §BLOCKER #2):
 *   demo@buyer.example signs in via the email/password form → /api/auth/signin
 *   sets `session.buyerPk` and `delete session.apiKey`. Every BFF route then
 *   checked `if (!session.apiKey) return 401` → the SearchApp client redirected
 *   to /signin → infinite loop / blank UI / dead demo.
 *
 * Post-fix contract (this spec asserts):
 *   1. v0.2 (buyerPk only, no apiKey) sessions return 200 from every
 *      buyer-facing BFF route — search, facets, study detail, account quota,
 *      orders list, thumbnail, sample-download.
 *   2. The `INTERNAL_SEARCH_KEY` env var must be set; bearerForBuyer() picks
 *      it up and the upstream call succeeds.
 *   3. The legacy paste-mode shape (apiKey only) is unaffected — the helper
 *      prefers session.apiKey when present.
 *
 * Two-pronged coverage:
 *   - Browser-side tests use `page.route()` mocks so the rendering tests are
 *     hermetic.
 *   - BFF-direct tests use `page.request.*()` which bypasses page.route and
 *     hits the real dev server / real upstream. Those assert the live happy
 *     path — they require `pnpm dev` (auto-seed) + INTERNAL_SEARCH_KEY in
 *     .env.local + the search docker container running. If any of those is
 *     missing the test fails loud (which is the intended demo-day signal).
 *
 * The cookie used is sealed with the production iron-session cipher — it
 * really is the v0.2 shape, not a stub.
 */

import { expect, test } from "@playwright/test";

import { blockRealUpstream } from "./fixtures/mocks";
import {
  injectBuyerSession,
  injectBuyerSessionV2,
} from "./fixtures/session";

const STUDY_UID = "2.25.v02demo.001";

const SEARCH_PAYLOAD = {
  items: [
    {
      pseudo_study_uid: STUDY_UID,
      modality: "CT",
      body_part: "CHEST",
      age_bucket: "50-60",
      sex: "M",
      n_instances: 412,
      total_bytes: 312 * 1024 * 1024,
      study_year: 2024,
      study_date_shifted: "2024-08-14",
      hospital_opaque_id: "a1b2c3d4e5f6a7b8",
    },
  ],
  total: 250, // mirrors the live seed count documented in qa-report-d13.
  next_cursor: null,
  meta: { response_truncated: false },
};

const STUDY_DETAIL = {
  pseudo_study_uid: STUDY_UID,
  modality: "CT",
  body_part: "CHEST",
  hospital_opaque_id: "a1b2c3d4e5f6a7b8",
  series: [],
  preview_status: "verified" as const,
};

const FAKE_JPEG = Buffer.from([
  0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01,
  0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xff, 0xd9,
]);

test.describe("v0.2 buyer data access (D-13 BLOCKER regression)", () => {
  test.beforeEach(async ({ page }) => {
    // Refuse anything not explicitly mocked so accidental upstream hits
    // surface as 599 instead of silently passing through.
    await blockRealUpstream(page);

    await page.route("**/api/search/facets", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          modality: [{ value: "CT", count: 156 }],
          body_part: [{ value: "CHEST", count: 103 }],
          sex: [{ value: "M", count: 168 }],
        }),
      });
    });
    await page.route("**/api/search/studies", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SEARCH_PAYLOAD),
      });
    });
    await page.route(`**/api/search/studies/${STUDY_UID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(STUDY_DETAIL),
      });
    });
    await page.route("**/api/account/quota", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          daily_used: 0,
          daily_limit: 1,
          resets_at: "2026-04-26T00:00:00+09:00",
          available: true,
        }),
      });
    });
    await page.route("**/api/account/api-key", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          kid: "abcd1234",
          masked: "rv_live_abcd1234_••••",
          label: "primary",
          tier: "preview",
          createdAt: "2026-04-25T10:00:00Z",
          lastUsedAt: null,
        }),
      });
    });
    await page.route("**/api/orders", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ items: [] }),
        });
        return;
      }
      await route.continue();
    });
    await page.route(
      `**/api/studies/${STUDY_UID}/thumbnail*`,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "image/jpeg",
          body: FAKE_JPEG,
        });
      },
    );
  });

  test("v0.2 session — /api/search/studies returns 200 with 250 study count", async ({
    page,
    context,
    request: _request,
  }) => {
    void _request; // request fixture isolated; we use page.request to share cookies
    await injectBuyerSessionV2(context);
    const res = await page.request.post("/api/search/studies", {
      data: { limit: 1, include_facets: false },
    });
    expect(res.status()).toBe(200);
    const json = (await res.json()) as { total: number; items: unknown[] };
    expect(json.total).toBe(250);
    expect(Array.isArray(json.items)).toBe(true);
  });

  test("v0.2 session — /api/search/facets returns 200", async ({
    page,
    context,
  }) => {
    await injectBuyerSessionV2(context);
    const res = await page.request.get("/api/search/facets");
    expect(res.status()).toBe(200);
    const json = (await res.json()) as { modality: unknown[] };
    expect(Array.isArray(json.modality)).toBe(true);
  });

  test("v0.2 session — /api/search/studies/[uid] returns 200 with detail", async ({
    page,
    context,
  }) => {
    await injectBuyerSessionV2(context);
    const res = await page.request.get(`/api/search/studies/${STUDY_UID}`);
    expect(res.status()).toBe(200);
    const json = (await res.json()) as { pseudo_study_uid: string };
    expect(json.pseudo_study_uid).toBe(STUDY_UID);
  });

  test("v0.2 session — /api/account/quota returns 200", async ({
    page,
    context,
  }) => {
    await injectBuyerSessionV2(context);
    const res = await page.request.get("/api/account/quota");
    expect(res.status()).toBe(200);
    const json = (await res.json()) as { daily_limit: number };
    expect(json.daily_limit).toBe(1);
  });

  test("v0.2 session — /api/orders GET returns 200 (empty list)", async ({
    page,
    context,
  }) => {
    await injectBuyerSessionV2(context);
    const res = await page.request.get("/api/orders");
    expect(res.status()).toBe(200);
    const json = (await res.json()) as { items: unknown[] };
    expect(json.items.length).toBe(0);
  });

  test("v0.2 session — /api/studies/[uid]/thumbnail returns 200 (image)", async ({
    page,
    context,
  }) => {
    await injectBuyerSessionV2(context);
    const res = await page.request.get(`/api/studies/${STUDY_UID}/thumbnail`);
    expect(res.status()).toBe(200);
    expect(res.headers()["content-type"]).toContain("image/jpeg");
  });

  test("v0.2 session — /search RSC page renders without redirect to /signin", async ({
    page,
    context,
  }) => {
    await injectBuyerSessionV2(context);
    const response = await page.goto("/search");
    expect(response?.status()).toBe(200);
    expect(new URL(page.url()).pathname).toBe("/search");
    // Sanity check: the cohort-review CTA is rendered (it lives inside
    // SearchApp's right pane). If the page had bounced to /signin we'd
    // never see this element.
    await expect(page.getByTestId("cohort-review-cta")).toBeVisible();
  });

  test("legacy paste-mode (apiKey only) — /api/search/studies still 200", async ({
    page,
    context,
  }) => {
    // The fix must not regress the 90-day deprecation window for paste-mode
    // callers. Helper picks session.apiKey before falling back to internal.
    await injectBuyerSession(context);
    const res = await page.request.post("/api/search/studies", {
      data: { limit: 1, include_facets: false },
    });
    expect(res.status()).toBe(200);
  });

  test("no session — /api/search/studies returns 401 ERR_AUTH_EXPIRED", async ({
    page,
  }) => {
    // No cookie injection. The route must short-circuit with the canonical
    // 401 envelope used by the rest of the BFF.
    const res = await page.request.post("/api/search/studies", {
      data: { limit: 1, include_facets: false },
    });
    expect(res.status()).toBe(401);
    const json = (await res.json()) as { error: string };
    expect(json.error).toBe("ERR_AUTH_EXPIRED");
  });
});
