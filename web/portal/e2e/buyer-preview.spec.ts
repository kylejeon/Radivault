/**
 * Buyer browse → preview → sample download e2e
 * (dev-spec-buyer-browse-preview FR-PREVIEW-1, FR-PREVIEW-2, FR-DOWNLOAD-1).
 *
 * Hermetic: every BFF call is mocked at page.route boundaries so the
 * test is deterministic against the demo CEO machine.
 */

import { expect, test } from "@playwright/test";
import { blockRealUpstream } from "./fixtures/mocks";
import { injectBuyerSession } from "./fixtures/session";

const STUDY_UID = "2.25.preview.e2e.001";

const VERIFIED_DETAIL = {
  pseudo_study_uid: STUDY_UID,
  modality: "CT",
  body_part: "CHEST",
  age_bucket: "50-60",
  sex: "M",
  study_date_shifted: "2024-08-14",
  manufacturer: "SIEMENS",
  model_name: "SOMATOM Force",
  n_instances: 18,
  n_series: 1,
  total_bytes: 32 * 1024 * 1024,
  hospital_opaque_id: "a1b2c3d4e5f6a7b8",
  ingested_at: "2024-08-15T03:20:51Z",
  series: [
    { pseudo_series_uid: "2.25.aaa", modality: "CT", n_instances: 18 },
  ],
  preview_status: "verified" as const,
  preview_slice_count: 18,
};

// Pre-fab tiny JPEG body — JFIF SOI..EOI w/ filler. Browsers tolerate it
// for the <img> render path; Playwright treats it as opaque bytes.
const FAKE_JPEG = Buffer.from([
  0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01,
  0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xff, 0xd9,
]);

test.describe("Buyer preview workflow", () => {
  test.beforeEach(async ({ page, context }) => {
    await blockRealUpstream(page);
    await injectBuyerSession(context);

    // Study detail — verified.
    await page.route(`**/api/search/studies/${STUDY_UID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(VERIFIED_DETAIL),
      });
    });
    // Quota — start at 0/1.
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
    // Thumbnail + frame routes serve our fake JPEG.
    await page.route(
      `**/api/studies/${STUDY_UID}/thumbnail*`,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "image/jpeg",
          headers: {
            "Cache-Control": "public, max-age=86400, immutable",
          },
          body: FAKE_JPEG,
        });
      },
    );
    await page.route(
      `**/api/studies/${STUDY_UID}/series/*/frames/*`,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "image/jpeg",
          body: FAKE_JPEG,
        });
      },
    );
    // Sample download → returns presigned URL + quota_after.
    await page.route(
      `**/api/studies/${STUDY_UID}/sample-download`,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            presigned_url: "https://example.com/sample.dcm?sig=mock",
            expires_at: "2026-04-26T00:00:00Z",
            instance_uid: "1.2.840.preview.sop.001",
            study_uid: STUDY_UID,
            size_bytes: 524288,
            quota_after: {
              used: 1,
              limit: 1,
              resets_at: "2026-04-26T00:00:00+09:00",
            },
          }),
        });
      },
    );
  });

  test("renders SliceViewer + sidebar + SaMD footer for verified study", async ({
    page,
  }) => {
    await page.goto(`/studies/${STUDY_UID}`);
    await expect(page.getByTestId("study-detail-panel")).toBeVisible();
    await expect(page.getByTestId("slice-viewer")).toBeVisible();
    await expect(page.getByTestId("samd-disclaimer")).toBeVisible();
    await expect(page.getByTestId("sample-download-card")).toBeVisible();
    await expect(page.getByTestId("cohort-card")).toBeVisible();
    // Slider is rendered for multi-frame studies.
    await expect(page.getByTestId("slice-slider")).toBeVisible();
    // Counter shows median frame (Math.floor(18/2)+1 = 10).
    await expect(page.getByTestId("slice-counter")).toContainText(
      "Slice 10 of 18",
    );
    // Quota indicator in OK state.
    await expect(page.getByTestId("quota-indicator-inline")).toContainText(
      "Today: 0/1",
    );
    // Sample download enabled.
    const btn = page.getByTestId("sample-download-button");
    await expect(btn).toBeVisible();
    await expect(btn).toBeEnabled();
    await expect(btn).toHaveAttribute("data-state", "default");
  });

  test("clicking Sample download triggers POST + quota updates to 1/1", async ({
    page,
  }) => {
    await page.goto(`/studies/${STUDY_UID}`);
    await expect(page.getByTestId("sample-download-button")).toBeEnabled();

    // We listen for the popup so the test passes whether the browser
    // honours window.open or fires a navigation.
    const [popup] = await Promise.all([
      page.waitForEvent("popup", { timeout: 5_000 }).catch(() => null),
      page.getByTestId("sample-download-button").click(),
    ]);

    // After the round-trip the indicator goes red w/ 1/1 + reset hint.
    await expect(page.getByTestId("quota-indicator-inline")).toContainText(
      "1/1",
    );
    await expect(page.getByTestId("quota-indicator-inline")).toContainText(
      "Resets at 00:00 KST",
    );
    // Button transitions to disabled-quota.
    await expect(page.getByTestId("sample-download-button")).toHaveAttribute(
      "data-state",
      "disabled-quota",
    );

    // Clean up the popup if one opened.
    if (popup) await popup.close();
  });

  test("SaMD lint — viewer DOM has no measure/segment/diagnose surfaces", async ({
    page,
  }) => {
    await page.goto(`/studies/${STUDY_UID}`);
    await expect(page.getByTestId("slice-viewer")).toBeVisible();
    const html = await page
      .getByTestId("slice-viewer")
      .evaluate((el) => el.outerHTML.toLowerCase());
    expect(html).not.toContain("measure");
    expect(html).not.toContain("segment");
    expect(html).not.toContain("annotate");
    expect(html).not.toContain("diagnose");
  });
});

test.describe("Buyer preview — non-verified study", () => {
  const PENDING_DETAIL = {
    ...VERIFIED_DETAIL,
    pseudo_study_uid: "2.25.preview.pending.001",
    preview_status: "pending" as const,
    preview_slice_count: null,
  };

  test.beforeEach(async ({ page, context }) => {
    await blockRealUpstream(page);
    await injectBuyerSession(context);
    await page.route(
      `**/api/search/studies/${PENDING_DETAIL.pseudo_study_uid}`,
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(PENDING_DETAIL),
        });
      },
    );
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
  });

  test("shows ModalityFallback + disabled sample-download for pending study", async ({
    page,
  }) => {
    await page.goto(`/studies/${PENDING_DETAIL.pseudo_study_uid}`);
    await expect(page.getByTestId("modality-fallback")).toBeVisible();
    // Sample download is disabled (data-state).
    await expect(page.getByTestId("sample-download-button")).toHaveAttribute(
      "data-state",
      "disabled-not-verified",
    );
    // Cohort still works (5-phase order flow is independent of preview).
    await expect(page.getByTestId("cohort-card")).toBeVisible();
  });
});
