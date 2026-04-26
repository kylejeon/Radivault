import { expect, test } from "@playwright/test";
import { injectBuyerSession } from "./fixtures/session";

/**
 * buyer-search-v3 LocaleToggle e2e (QA HIGH-3 / BL-2).
 *
 * 1. Both EN + 한국어 buttons render with role=tab.
 * 2. Click 한국어 → trust bar text + PIPA note + KCD note all swap to KR
 *    in-place (no full page navigation).
 * 3. Click EN → swaps back; localStorage persisted.
 */

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
];

test.describe("buyer-search-v3 — LocaleToggle", () => {
  test.beforeEach(async ({ page, context }) => {
    await injectBuyerSession(context);
    await page.route("**/api/**", async (route) => {
      const u = route.request().url();
      if (u.includes("/api/search/facets")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({}),
        });
        return;
      }
      if (u.includes("/api/search/studies")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            items: V3_ROWS,
            facets: {},
            total_count: 1,
            total_hint: 1,
            page_size: 25,
            has_next: false,
            meta: { query_duration_ms: 12, buyer_tier: "preview" },
          }),
        });
        return;
      }
      await route.fulfill({
        status: 599,
        contentType: "application/json",
        body: JSON.stringify({ error: "ERR_E2E_UNMOCKED" }),
      });
    });
  });

  test("renders both EN + KR tabs and switches in-place", async ({ page }) => {
    await page.goto("/search");
    await page.waitForResponse(
      (r) => r.url().includes("/api/search/studies") && r.status() === 200,
      { timeout: 8000 },
    );

    const tablist = page.getByTestId("v3-locale-toggle");
    await expect(tablist).toBeVisible();
    await expect(tablist).toHaveAttribute("role", "tablist");

    const enBtn = page.getByTestId("v3-locale-toggle-en");
    const koBtn = page.getByTestId("v3-locale-toggle-ko");
    await expect(enBtn).toHaveAttribute("aria-selected", "true");
    await expect(koBtn).toHaveAttribute("aria-selected", "false");

    // EN trust bar copy.
    await expect(page.getByTestId("v3-trust-bar")).toContainText("PIPA §28-8");
    await expect(page.getByTestId("v3-pipa-note")).toContainText(
      /Production policy/i,
    );
    await expect(page.getByTestId("v3-kcd-heuristic-note")).toContainText(
      /Demo note/i,
    );

    // Switch to KR — same URL, same DOM root, different copy.
    const urlBefore = page.url();
    await koBtn.click();
    await expect(koBtn).toHaveAttribute("aria-selected", "true");
    await expect(enBtn).toHaveAttribute("aria-selected", "false");
    expect(page.url()).toBe(urlBefore); // no navigation

    await expect(page.getByTestId("v3-trust-bar")).toContainText(
      "개인정보보호법",
    );
    await expect(page.getByTestId("v3-pipa-note")).toContainText("운영 정책");
    await expect(page.getByTestId("v3-kcd-heuristic-note")).toContainText(
      "데모 안내",
    );

    // ColumnToggle button copy follows the locale.
    await expect(page.getByTestId("v3-column-toggle-btn")).toContainText(
      "컬럼 표시",
    );
  });

  test("persists choice via localStorage", async ({ page }) => {
    await page.goto("/search");
    await page.waitForResponse(
      (r) => r.url().includes("/api/search/studies") && r.status() === 200,
      { timeout: 8000 },
    );
    await page.getByTestId("v3-locale-toggle-ko").click();
    const stored = await page.evaluate(() =>
      window.localStorage.getItem("radivault.locale"),
    );
    expect(stored).toBe("ko");

    // body[data-locale] attribute also updated for non-React surfaces.
    const attr = await page.evaluate(() =>
      document.body.getAttribute("data-locale"),
    );
    expect(attr).toBe("ko");
  });
});
