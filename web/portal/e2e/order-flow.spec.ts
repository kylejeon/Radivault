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
 * Scenario 2 — Order placement flow.
 *
 * /search → check 3 studies → Review order → accept DUA → Confirm →
 * POST /api/orders is mocked to 202 accepted → redirect to /orders/{id} →
 * PhaseStepper shows "Accepted" highlighted.
 */

const ORDER_ID = "ord_e2edemo01";

test.describe("Order placement flow", () => {
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
    await expect(page.getByText(/of \d+ studies/i)).toBeVisible();

    // Select the first three study rows.
    const selectBoxes = page.getByRole("checkbox", { name: /Select study/i });
    await expect(selectBoxes).toHaveCount(DEFAULT_STUDIES.length);
    for (let i = 0; i < 3; i += 1) {
      await selectBoxes.nth(i).check();
    }

    // Cohort sidebar should show 3.
    await expect(page.getByRole("button", { name: /Review order \(3\)/ })).toBeEnabled();

    // Open the review modal.
    await page.getByRole("button", { name: /Review order \(3\)/ }).click();
    const dialog = page.getByRole("dialog", { name: "Review order" });
    await expect(dialog).toBeVisible();

    // Confirm is disabled until DUA is ticked.
    const confirm = dialog.getByRole("button", { name: "Confirm order" });
    await expect(confirm).toBeDisabled();

    // Tick the DUA checkbox (single unlabelled checkbox inside the dialog).
    await dialog.getByRole("checkbox").check();
    await expect(confirm).toBeEnabled();

    // Submit. The mocked /api/orders returns 202 with buyer_phase=accepted.
    await confirm.click();

    // Receipt view appears with the order id, then the client auto-navigates
    // to /orders/{id} after ~2.5s. We wait for the URL change.
    await expect(dialog.getByText(ORDER_ID)).toBeVisible();
    await page.waitForURL(`**/orders/${ORDER_ID}`, { timeout: 10_000 });

    // Phase stepper shows "Accepted" as the active step.
    await expect(page.getByRole("list", { name: "Order phase" })).toBeVisible();
    await expect(page.getByText("Accepted")).toBeVisible();
    await expect(page.getByText("Fetching from hospital")).toBeVisible();

    // The top card displays the order id (mono-spaced heading).
    await expect(page.getByRole("heading", { name: ORDER_ID })).toBeVisible();
  });

  test("422 validation error keeps the modal open with an error banner", async ({ page }) => {
    // Override the create-order mock to return a 422.
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
    await expect(page.getByText(/of \d+ studies/i)).toBeVisible();

    // Select 1 study to get past the cohort-empty guard.
    await page.getByRole("checkbox", { name: /Select study/i }).first().check();
    await page.getByRole("button", { name: /Review order \(1\)/ }).click();

    const dialog = page.getByRole("dialog", { name: "Review order" });
    await dialog.getByRole("checkbox").check();
    await dialog.getByRole("button", { name: "Confirm order" }).click();

    // Dialog stays open; alert role banner surfaces the error detail.
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("alert")).toContainText(/At least one study/i);
    // We must NOT have navigated away.
    await expect(page).toHaveURL(/\/search/);
  });
});
