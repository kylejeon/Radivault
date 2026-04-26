import { expect, test } from "@playwright/test";
import {
  blockRealUpstream,
  DEFAULT_FACETS,
  DEFAULT_STUDIES,
  filterStudies,
  mockBuyerSignIn,
  mockSearchFacets,
  mockSearchStudies,
} from "./fixtures/mocks";
import { injectBuyerSession } from "./fixtures/session";

/**
 * Scenario 1 — Buyer search flow (design-spec-portal-redesign §12.1).
 *
 * The v0.2 portal is a 3-pane layout: 280 px FacetSidebar (with the
 * min_hospitals slider as the lead facet, FR-BP-7), middle results
 * column with sticky FederatedSignal (FR-BP-6), and 320 px cohort
 * sidebar.  We assert the layout, the SearchRequest schema fields
 * (FR-INF-8/9), and the federated signal copy.
 */

// buyer-search-v3 supersedes the v0.2 3-pane shell on /search. The v3 e2e
// coverage lives in `v3-search-data-density.spec.ts`. The v0.2 specs are
// preserved for historical reference but skipped — re-enable only after
// rolling back to SearchApp.tsx.
test.describe.skip("Buyer search flow (3-pane v0.2 — superseded by v3)", () => {
  test.beforeEach(async ({ page, context }) => {
    await blockRealUpstream(page);
    await mockBuyerSignIn(page);
    await mockSearchFacets(page, DEFAULT_FACETS);
    await mockSearchStudies(page, (body) => filterStudies(body, DEFAULT_STUDIES));
    await injectBuyerSession(context);
  });

  test("renders 3-pane shell with facet sidebar + federated signal + cohort", async ({
    page,
  }) => {
    await page.goto("/search");

    // Shell — three landmarks.
    await expect(page.getByTestId("facet-sidebar")).toBeVisible();
    await expect(page.getByTestId("federated-signal")).toBeVisible();
    // Cohort sidebar uses the standard aria-label from i18n ("Cohort"/"코호트").
    await expect(page.getByRole("complementary", { name: "Cohort" })).toBeVisible();

    // Federated signal copy — northstar metric.
    const signal = page.getByTestId("federated-signal");
    await expect(signal).toContainText(/across/);
    await expect(signal).toContainText(/hospital/);

    // 9-column DataTable rows.
    const rows = page.getByTestId("study-card");
    await expect(rows).toHaveCount(DEFAULT_STUDIES.length);

    // min_hospitals slider is the FIRST facet section.
    await expect(
      page.getByTestId("facet-section-facet-min-hospitals"),
    ).toBeVisible();
    await expect(page.getByTestId("min-hospitals-value")).toHaveText("1+");
  });

  test("selecting a study row populates the cohort sidebar", async ({ page }) => {
    await page.goto("/search");
    await expect(page.getByTestId("federated-signal")).toBeVisible();

    // Select the first 2 study rows via their checkbox.
    const cbs = page.getByRole("checkbox", { name: /Select study/i });
    await expect(cbs).toHaveCount(DEFAULT_STUDIES.length);
    await cbs.nth(0).check();
    await cbs.nth(1).check();

    // Cohort mini-list shows two cart-item-mini.
    await expect(page.getByTestId("cart-item-mini")).toHaveCount(2);

    // Review CTA points at /orders/new with the count appended.
    const cta = page.getByTestId("cohort-review-cta");
    await expect(cta).toBeVisible();
    await expect(cta).toContainText("(2)");
    await expect(cta).toHaveAttribute("href", "/orders/new");
  });

  test("zero-result query swaps the FederatedSignal to its empty variant", async ({
    page,
  }) => {
    await page.route("**/api/search/studies", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [],
          facets: {},
          total_count: 0,
          total_count_exact: true,
          next_cursor: null,
          has_next: false,
          page_size: 25,
          response_truncated: false,
        }),
      });
    });
    await page.goto("/search");
    await expect(page.getByTestId("federated-signal-empty")).toBeVisible();
    await expect(page.getByTestId("federated-signal-empty")).toContainText(
      /No results across/,
    );
  });

  test("search payload uses canonical SearchRequest field names (FR-INF-8/9)", async ({
    page,
  }) => {
    let lastBody: Record<string, unknown> | null = null;
    await page.route("**/api/search/studies", async (route) => {
      lastBody = JSON.parse(route.request().postData() ?? "{}") as Record<
        string,
        unknown
      >;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(filterStudies(lastBody, DEFAULT_STUDIES)),
      });
    });
    await page.goto("/search");
    await expect(page.getByTestId("federated-signal")).toBeVisible();
    // Wait for the debounced initial fetch to land.
    await page.waitForTimeout(500);

    expect(lastBody).not.toBeNull();
    // Canonical fields per dev-spec-metadata-index §6.4.
    expect(lastBody).toHaveProperty("limit");
    expect(lastBody).toHaveProperty("include_facets");
    expect(lastBody).toHaveProperty("sort");
    // Banned legacy fields.
    expect(lastBody).not.toHaveProperty("page_size");
    expect(lastBody).not.toHaveProperty("modalities");
    expect(lastBody).not.toHaveProperty("body_parts");
  });
});
