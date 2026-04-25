import { expect, test } from "@playwright/test";
import {
  blockRealUpstream,
  DEFAULT_FACETS,
  DEFAULT_STUDIES,
  filterStudies,
  mockCreateOrder,
  mockOrderDetail,
  mockSearchFacets,
  mockSearchStudies,
} from "./fixtures/mocks";
import { injectBuyerSession } from "./fixtures/session";

/**
 * Scenario 2 — Order placement flow (design-spec-portal-redesign §12.3).
 *
 * v0.2 promotes the legacy `<ReviewOrderModal>` to a full `/orders/new`
 * route (FR-BP-9). The flow is now:
 *
 *   /search → check 3 studies → click "Review order (3)" link →
 *   /orders/new shows cart + summary → tick DUA → "Place order" →
 *   POST /api/orders → redirect to /orders/{id} → 5-phase stepper visible.
 */

const ORDER_ID = "ord_e2edemo01";

test.describe("Order placement flow (v0.2 /orders/new)", () => {
  test.beforeEach(async ({ page, context }) => {
    await blockRealUpstream(page);
    await mockSearchFacets(page, DEFAULT_FACETS);
    await mockSearchStudies(page, (body) => filterStudies(body, DEFAULT_STUDIES));
    await mockCreateOrder(page, ORDER_ID);
    await mockOrderDetail(page, ORDER_ID, "accepted");
    await injectBuyerSession(context);
  });

  test("happy path — 3 studies, DUA accepted, order accepted", async ({ page }) => {
    await page.goto("/search");
    await expect(page.getByTestId("federated-signal")).toBeVisible();

    // Select first 3 study rows from the new DataTable.
    const cbs = page.getByRole("checkbox", { name: /Select study/i });
    await expect(cbs).toHaveCount(DEFAULT_STUDIES.length);
    for (let i = 0; i < 3; i += 1) await cbs.nth(i).check();

    // Cohort review CTA shows the count and routes to /orders/new.
    const cta = page.getByTestId("cohort-review-cta");
    await expect(cta).toContainText("(3)");
    await cta.click();
    await page.waitForURL(/\/orders\/new$/);

    // /orders/new shows the cart with 3 full rows + DUA checkbox + place-order CTA.
    await expect(page.getByTestId("cart-item-full")).toHaveCount(3);
    const dua = page.getByTestId("dua-checkbox");
    const submit = page.getByTestId("place-order");
    await expect(submit).toBeDisabled();

    await dua.check();
    await expect(submit).toBeEnabled();

    await submit.click();
    await page.waitForURL(`**/orders/${ORDER_ID}`, { timeout: 10_000 });

    // Order tracker renders the legacy 5-phase stepper.
    await expect(page.getByRole("list", { name: "Order phase" })).toBeVisible();
    await expect(page.getByText("Accepted")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: ORDER_ID }),
    ).toBeVisible();
  });

  test("422 validation error keeps the buyer on /orders/new with a banner", async ({
    page,
  }) => {
    await page.route("**/api/orders", async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 422,
        contentType: "application/json",
        body: JSON.stringify({
          error: "ERR_ORDER_VALIDATION",
          detail: "At least one study must be selected",
          request_id: "req-e2e-validation",
        }),
      });
    });

    await page.goto("/search");
    await expect(page.getByTestId("federated-signal")).toBeVisible();
    await page.getByRole("checkbox", { name: /Select study/i }).first().check();
    await page.getByTestId("cohort-review-cta").click();
    await page.waitForURL(/\/orders\/new$/);

    await page.getByTestId("dua-checkbox").check();
    await page.getByTestId("place-order").click();

    // We must NOT have navigated away from /orders/new.
    await expect(page).toHaveURL(/\/orders\/new$/);
    // The ErrorBanner shows the upstream `detail` field verbatim. Scope by
    // the alert that lives inside <main> so we don't collide with the Next
    // route announcer (`#__next-route-announcer__`, also role="alert").
    const banner = page.locator("main").getByRole("alert");
    await expect(banner).toContainText(/At least one study/i);
  });

  test("empty cohort renders the back-to-search empty state", async ({ page }) => {
    await page.goto("/orders/new");
    await expect(page.getByText(/No studies selected/)).toBeVisible();
    await expect(
      page.getByRole("link", { name: /Back to search/i }),
    ).toBeVisible();
  });

  test("AC-BP-8 — POST /api/orders body carries the allowed_hospitals scope", async ({
    page,
  }) => {
    // Capture the body the BFF receives so we can assert the federated
    // cohort scope (HIGH-4 fix from qa-report-portal-redesign).
    let captured: { allowed_hospitals?: string[] } | null = null;
    await page.route("**/api/orders", async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      captured = JSON.parse(route.request().postData() ?? "{}") as {
        allowed_hospitals?: string[];
      };
      await route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({
          order_id: ORDER_ID,
          state: "queued",
          buyer_phase: "accepted",
        }),
      });
    });

    await page.goto("/search");
    // Pick the first 3 studies — DEFAULT_STUDIES spans both HOSP-001 and
    // HOSP-002, so the cohort is federated.
    const cbs = page.getByRole("checkbox", { name: /Select study/i });
    for (let i = 0; i < 3; i += 1) await cbs.nth(i).check();
    await page.getByTestId("cohort-review-cta").click();
    await page.waitForURL(/\/orders\/new$/);

    await page.getByTestId("dua-checkbox").check();
    await page.getByTestId("place-order").click();
    await page.waitForURL(`**/orders/${ORDER_ID}`, { timeout: 10_000 });

    expect(captured).not.toBeNull();
    const scope = captured!.allowed_hospitals ?? [];
    // Must be a non-empty deduped sorted array of opaque hospital ids
    // pulled from the cart's hospital_opaque_id field.
    expect(scope.length).toBeGreaterThan(0);
    expect(new Set(scope).size).toBe(scope.length);
    const sorted = [...scope].sort();
    expect(sorted).toEqual(scope);
  });
});
