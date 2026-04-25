import { expect, test } from "@playwright/test";
import { blockRealUpstream } from "./fixtures/mocks";
import { injectBuyerSession } from "./fixtures/session";

/**
 * /account + /studies/[uid] smoke (design-spec-portal-redesign §12.2 + §12.4).
 *
 * /account renders the Stripe-style masked api key + tier + reveal-once
 * stub.  /studies/[uid] hits the new BFF passthrough and renders
 * StudyDetailPanel; the 404 surface is asserted via a forced upstream miss.
 */

const STUDY_UID = "2.25.100000000000000000000000000001";

test.describe("/account (FR-BP-13)", () => {
  test.beforeEach(async ({ page, context }) => {
    await blockRealUpstream(page);
    await injectBuyerSession(context);
  });

  test("renders profile + Stripe-masked api key + Regenerate/Revoke", async ({
    page,
  }) => {
    await page.goto("/account");
    // Page-level heading.
    await expect(page.getByRole("heading", { name: "Account" })).toBeVisible();
    // v0.2 (dev-spec-buyer-auth FR-AUTH-8) mask: rv_live_<4>…<4>.
    // Legacy session payload (injectBuyerSession) carries an apiKey only,
    // so the /account server page falls into the legacy mask branch but
    // emits the new v0.2 format (single source of truth in
    // src/lib/auth/api-key.ts maskApiKey).
    const masked = await page
      .getByTestId("account-apikey-masked")
      .textContent();
    expect(masked).toMatch(/^rv_live_/);
    expect(masked).toContain("…");
    // Raw key body (`e2edemo_…`) must NEVER show up un-masked.
    expect(masked).not.toContain("e2edemo_00000000");

    // FR-AUTH-8 actions are wired: Regenerate + Revoke buttons present.
    await expect(page.getByTestId("account-regenerate")).toBeVisible();
    await expect(page.getByTestId("account-revoke")).toBeVisible();
  });
});

test.describe("/studies/[uid] (FR-BP-8)", () => {
  test.beforeEach(async ({ page, context }) => {
    await blockRealUpstream(page);
    await injectBuyerSession(context);
  });

  test("renders the study detail panel for a known UID", async ({ page }) => {
    await page.route(`**/api/search/studies/${STUDY_UID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          pseudo_study_uid: STUDY_UID,
          modality: "CT",
          body_part: "CHEST",
          age_bucket: "50-60",
          sex: "M",
          study_date_shifted: "2024-08-14",
          manufacturer: "SIEMENS",
          model_name: "SOMATOM Force",
          n_instances: 287,
          n_series: 2,
          total_bytes: 142 * 1024 * 1024,
          hospital_opaque_id: "a1b2c3d4e5f6a7b8",
          ingested_at: "2024-08-15T03:20:51Z",
          series: [
            { pseudo_series_uid: "2.25.aaa", modality: "CT", n_instances: 287 },
            { pseudo_series_uid: "2.25.bbb", modality: "CT", n_instances: 64 },
          ],
        }),
      });
    });
    await page.goto(`/studies/${STUDY_UID}`);
    await expect(page.getByTestId("study-detail-panel")).toBeVisible();
    await expect(page.getByText("SIEMENS")).toBeVisible();
    await expect(page.getByText("SOMATOM Force")).toBeVisible();
    // Viewer stub renders.
    await expect(page.getByTestId("viewer-stub")).toBeVisible();
    // Add to cohort button present and enabled.
    await expect(page.getByTestId("add-to-cohort")).toBeVisible();
  });

  test("404 from upstream surfaces the page-level not-found state", async ({
    page,
  }) => {
    await page.route(`**/api/search/studies/${STUDY_UID}`, async (route) => {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({
          error: "ERR_STUDY_NOT_FOUND",
          detail: "Unknown study",
          request_id: "req-e2e-404",
        }),
      });
    });
    await page.goto(`/studies/${STUDY_UID}`);
    await expect(page.getByText(/Study not found/)).toBeVisible();
    await expect(
      page.getByRole("link", { name: /Back to results/i }),
    ).toBeVisible();
  });
});
