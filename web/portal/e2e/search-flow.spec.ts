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
 * Scenario 1 — Buyer search flow.
 *
 * Sign-in -> /search -> facet filter (modality=CT, body_part=CHEST) ->
 * result rows reflect the mocked payload. Every BFF call is intercepted
 * so the test runs without a live central-ingest or search service.
 */

test.describe("Buyer search flow", () => {
  test.beforeEach(async ({ page, context }) => {
    await blockRealUpstream(page);
    await mockBuyerSignIn(page);
    await mockSearchFacets(page, DEFAULT_FACETS);
    await mockSearchStudies(page, (body) => filterStudies(body, DEFAULT_STUDIES));
    await injectBuyerSession(context);
  });

  test("signed-in user reaches /search and sees the unfiltered results", async ({ page }) => {
    await page.goto("/search");

    // Wait for the top-nav to render — proves the server-side session gate passed.
    await expect(page.getByRole("link", { name: "Search" })).toBeVisible();

    // The result-count header is the canonical "data has loaded" signal.
    const summary = page.getByText(/of \d+ studies/i);
    await expect(summary).toBeVisible();

    // DEFAULT_STUDIES has 5 rows; each StudyCard renders a "Select study …" checkbox.
    const checkboxes = page.getByRole("checkbox", { name: /Select study/i });
    await expect(checkboxes).toHaveCount(DEFAULT_STUDIES.length);

    // At least one CT badge (DEFAULT_STUDIES has 3 CTs).
    await expect(page.getByLabel("Modality CT").first()).toBeVisible();
  });

  test("selecting modality=CT + body_part=CHEST narrows the table", async ({ page }) => {
    await page.goto("/search");
    await expect(page.getByText(/of \d+ studies/i)).toBeVisible();

    // Facet checkboxes live inside the Modality / Body part <fieldset>s.
    // Scoping by legend keeps us clear of the "Select study …" row checkboxes.
    // The accessible name is "{value} {count}" (label text + count badge), so
    // we anchor on the "CT 156" shape with a regex.
    const modalityGroup = page.getByRole("group", { name: "Modality" });
    const bodyPartGroup = page.getByRole("group", { name: "Body part" });
    await modalityGroup.getByRole("checkbox", { name: /^CT\s/ }).check();
    await bodyPartGroup.getByRole("checkbox", { name: /^CHEST\s/ }).check();

    // The mocked factory returns only rows matching both filters (3 items).
    const filteredCheckboxes = page.getByRole("checkbox", { name: /Select study/i });
    await expect(filteredCheckboxes).toHaveCount(3);

    // The result-count header should reflect the filtered total (3).
    await expect(page.getByText(/3 of 3 studies/)).toBeVisible();

    // Spot check: the MR/BRAIN rows must be gone.
    await expect(page.getByLabel("Modality MR")).toHaveCount(0);
  });

  test("zero-result filters show the EmptyState copy", async ({ page }) => {
    // Override the studies mock to always return zero results on any filter.
    await page.route("**/api/search/studies", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0, next_cursor: null }),
      });
    });
    await page.goto("/search");
    await page
      .getByRole("group", { name: "Modality" })
      .getByRole("checkbox", { name: /^CT\s/ })
      .check();
    await expect(page.getByText(/No studies match these filters/i)).toBeVisible();
  });
});
