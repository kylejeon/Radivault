import { expect, test } from "@playwright/test";
import {
  blockRealUpstream,
  mockBuyerSignIn,
} from "./fixtures/mocks";
import { injectBuyerSession } from "./fixtures/session";

/**
 * buyer-search-v3 E2E (FR-V3-DEMO-1..7).
 *
 * Mocks the v3 /api/search/studies + /api/search/facets responses with the
 * 13-column shape and asserts that the dense table, the facet sidebar, the
 * KCD autocomplete, and the age range input all render the v3 contract.
 *
 * NOTE: when a stale Next.js dev server is bound to :3000 (a previous
 * `pnpm dev` session), the static-chunk requests may 404 — preventing
 * React hydration. The 5-group accordion + age range + KCD input testids
 * still resolve from the SSR'd initial DOM; the result-table + 250-count
 * assertions require hydration, so a fresh dev server (`pnpm dev`) must
 * be running for those two tests to pass.
 */

const V3_FACETS = {
  modality: [
    { value: "CT", count: 98 },
    { value: "MR", count: 62 },
    { value: "CR", count: 48 },
    { value: "MG", count: 28 },
  ],
  body_part: [
    { value: "CHEST", count: 112 },
    { value: "HEAD", count: 58 },
    { value: "ABDOMEN", count: 42 },
  ],
  sex: [
    { value: "F", count: 128 },
    { value: "M", count: 122 },
  ],
  manufacturer: [
    { value: "SIEMENS", count: 80 },
  ],
  model_name: [],
  year: [{ value: "2024", count: 250 }],
  contrast_used: [],
  hospital_region: [
    { value: "SEOUL-A", count: 142 },
    { value: "BUSAN-B", count: 108 },
  ],
  kcd_code: [
    { value: "I20.9", count: 38 },
    { value: "I63.9", count: 17 },
    { value: "C50.9", count: 14 },
  ],
  computed_at: "2026-04-25T12:00:00Z",
};

const V3_ROWS = [
  {
    pseudo_study_uid: "1.2.840.HOSP1.7392.20240815.001",
    modality: "CT",
    body_part: "CHEST",
    age_bucket: "50-60",
    patient_age: 52,
    sex: "F",
    study_date_shifted: "2024-08-15",
    manufacturer: "SIEMENS",
    model_name: "SOMATOM Drive",
    n_instances: 312,
    n_series: 3,
    total_bytes: 502267904,
    hospital_opaque_id: "opaque1",
    hospital_region_pseudo: "SEOUL-A",
    kcd_code: "I20.9",
    kcd_label_ko: "협심증, 상세불명",
    kcd_label_en: "Angina pectoris, unspecified",
    ingested_at: "2024-08-16T03:42:11Z",
    preview_status: "verified",
    preview_slice_count: 312,
  },
  {
    pseudo_study_uid: "1.2.840.HOSP2.8421.20240919.002",
    modality: "MR",
    body_part: "HEAD",
    age_bucket: "60-70",
    patient_age: 68,
    sex: "M",
    study_date_shifted: "2024-09-19",
    manufacturer: "PHILIPS",
    model_name: "Ingenia 3.0T",
    n_instances: 188,
    n_series: 5,
    total_bytes: 312000000,
    hospital_opaque_id: "opaque2",
    hospital_region_pseudo: "BUSAN-B",
    kcd_code: "G45.9",
    kcd_label_ko: "일과성 뇌허혈 발작",
    kcd_label_en: "Transient ischaemic attack",
    ingested_at: "2024-09-20T01:00:00Z",
    preview_status: "verified",
    preview_slice_count: 188,
  },
];

test.describe("buyer-search-v3 — dense table + facets + KCD", () => {
  test.beforeEach(async ({ page, context }) => {
    await injectBuyerSession(context);
    // Use a single broad handler that branches by URL to guarantee precedence.
    await page.route("**/api/**", async (route) => {
      const u = route.request().url();
      if (u.includes("/api/search/facets")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(V3_FACETS),
        });
        return;
      }
      if (u.includes("/api/search/studies")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            items: V3_ROWS,
            facets: V3_FACETS,
            total_count: 250,
            total_hint: 250,
            page_size: 25,
            has_next: false,
            meta: { query_duration_ms: 38, buyer_tier: "preview" },
          }),
        });
        return;
      }
      // Fallthrough — refuse anything we forgot to mock.
      await route.fulfill({
        status: 599,
        contentType: "application/json",
        body: JSON.stringify({
          error: "ERR_E2E_UNMOCKED",
          detail: `Unmocked route ${u}`,
        }),
      });
    });
  });

  test("renders dense 13-col table with v3 fields", async ({ page }) => {
    await page.goto("/search");
    // Wait for the initial debounced (250 ms) /api/search/studies response.
    await page.waitForResponse(
      (r) => r.url().includes("/api/search/studies") && r.status() === 200,
      { timeout: 8000 },
    );
    // Trust bar always present.
    await expect(page.getByTestId("v3-trust-bar").first()).toBeVisible();
    // Result table + at least 2 rows.
    const table = page.getByTestId("v3-result-table");
    await expect(table).toBeVisible();
    const rows = page.getByTestId("v3-row");
    await expect(rows).toHaveCount(2);
    // Row contents — KCD chip + label, hospital badge, exact age.
    const firstRow = rows.first();
    await expect(firstRow).toContainText("SEOUL-A");
    await expect(firstRow).toContainText("2024-08-15");
    await expect(firstRow).toContainText("CT");
    await expect(firstRow).toContainText("I20.9");
    await expect(firstRow).toContainText("Angina pectoris, unspecified");
    await expect(firstRow).toContainText("52");
    // PIPA note in footer.
    await expect(page.getByTestId("v3-pipa-note")).toBeVisible();
  });

  test("facet sidebar exposes 5 groups (Hospital · Clinical · Patient · Imaging · Time)", async ({
    page,
  }) => {
    await page.goto("/search");
    await expect(page.getByTestId("facet-hospital")).toBeVisible();
    await expect(page.getByTestId("facet-clinical")).toBeVisible();
    await expect(page.getByTestId("facet-patient")).toBeVisible();
    await expect(page.getByTestId("facet-imaging")).toBeVisible();
    await expect(page.getByTestId("facet-time")).toBeVisible();
  });

  test("age range input wires min/max", async ({ page }) => {
    await page.goto("/search");
    const minInput = page.getByTestId("age-min-input");
    await expect(minInput).toBeVisible();
    await expect(page.getByTestId("age-max-input")).toBeVisible();
    await expect(page.getByTestId("age-min-slider")).toBeVisible();
    await expect(page.getByTestId("age-max-slider")).toBeVisible();
  });

  test("KCD autocomplete input is wired with role=combobox", async ({ page }) => {
    await page.goto("/search");
    const input = page.getByTestId("kcd-autocomplete-input");
    await expect(input).toBeVisible();
    await expect(input).toHaveAttribute("role", "combobox");
  });

  test("results header shows 250 / hospital count / query ms", async ({ page }) => {
    await page.goto("/search");
    const header = page.getByTestId("v3-results-header");
    await expect(header).toContainText("250");
    await expect(header).toContainText(/hospital/i);
    await expect(header).toContainText(/ms/i);
  });
});
