import { expect, test } from "@playwright/test";

/**
 * /signup + /signin happy paths (dev-spec-buyer-auth FR-AUTH-1, 4, 8).
 *
 * The portal runs with BUYER_AUTH_SKIP_EMAIL_VERIFY=true (default in
 * env.ts) so the OTP modal is skipped after signup → ApiKeyRevealModal
 * opens directly with the one-time plaintext.
 *
 * The auth store is a process-local in-memory singleton; tests run
 * sequentially (workers=1, fullyParallel=false in playwright.config) so
 * each spec sees a fresh-ish slate, but we use unique emails per case
 * regardless to avoid collisions.
 *
 * We deliberately do NOT call blockRealUpstream() — the auth endpoints
 * are first-party portal routes that need to reach the in-memory store.
 * Instead we block only the post-signin upstream calls (search facets
 * etc.) that would otherwise hit a non-existent service.
 */

test.describe("buyer-auth (FR-AUTH-1, FR-AUTH-4, FR-AUTH-8)", () => {
  test.beforeEach(async ({ page }) => {
    // Stub /api/search/* and /api/orders/* with empty 200s so /search
    // doesn't hang waiting for upstream responses. Auth routes are
    // intentionally untouched.
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

  test("signup → reveal-once modal → /search", async ({ page }) => {
    const email = `e2e-signup-${Date.now()}@example.com`;
    await page.goto("/signup");
    await expect(
      page.getByRole("heading", { name: /Create your RadiVault account/i }),
    ).toBeVisible();

    await page.getByLabel(/Work email/).fill(email);
    await page.getByLabel(/^Password/).fill("correct-horse-staple-9");
    // Confirm-password field added in 03196cd; without it the submit
    // stays disabled. Sync e2e with the current SignupForm UX.
    await page.getByLabel(/Confirm password/).fill("correct-horse-staple-9");
    await page.getByLabel(/Organization/).fill("E2E Test Co");
    // Accept ToS+Privacy
    await page
      .getByRole("checkbox", { name: /Terms of Service/i })
      .check();

    await page.getByTestId("signup-submit").click();

    // ApiKeyRevealModal opens (skip-flag default true).
    await expect(page.getByTestId("apikey-plaintext")).toBeVisible();
    const plaintext = await page.getByTestId("apikey-plaintext").textContent();
    expect(plaintext ?? "").toMatch(/^rv_live_/);

    // Confirm checkbox + Done → /search.
    await page
      .getByRole("checkbox", { name: /I have saved my key/i })
      .check();
    await page.getByTestId("apikey-reveal-done").click();
    await expect(page).toHaveURL(/\/search/);
  });

  test("signin happy path lands on /search", async ({ page }) => {
    const email = `e2e-signin-${Date.now()}@example.com`;
    const password = "correct-horse-staple-9";

    // Create account via API (more deterministic than driving the form
    // for this signin-focused test). The API call hits the same in-memory
    // store the signin handler reads from, so the credential pair is
    // guaranteed to exist on the next request.
    const signupRes = await page.request.post("/api/auth/signup", {
      data: {
        email,
        password,
        organization: "E2E Test Co",
        intent: "commercial-ai",
        tosPrivacyConsent: true,
        marketingEmailOptIn: false,
        pipaConsents: null,
        locale: "en",
      },
    });
    expect(signupRes.status()).toBe(201);

    // Sign out via direct API call so the next /signin GET doesn't bounce
    // us straight to /search via the already-signed-in redirect guard.
    await page.request.post("/api/auth/signout");

    // Drive the signin form.
    await page.goto("/signin");
    await expect(
      page.getByRole("heading", { name: /Welcome back/i }),
    ).toBeVisible();
    await page.getByLabel(/^Email/).fill(email);
    await page.getByLabel(/^Password/).fill(password);
    await page.getByTestId("signin-submit").click();
    await expect(page).toHaveURL(/\/search/);
  });

  test("legacy API-key paste mode is hidden behind advanced toggle", async ({
    page,
  }) => {
    await page.goto("/signin");
    // Default = email form.
    await expect(page.getByTestId("signin-form-email")).toBeVisible();
    await expect(page.getByTestId("signin-form-legacy")).toHaveCount(0);
    // Toggle to legacy.
    await page.getByTestId("signin-toggle-mode").click();
    await expect(page.getByTestId("signin-form-legacy")).toBeVisible();
    await expect(page.getByTestId("signin-form-email")).toHaveCount(0);
  });
});
