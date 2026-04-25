import { expect, test } from "@playwright/test";

/**
 * Homepage e2e — design-spec-portal-redesign §6 + dev-spec AC-HP-1..10.
 *
 * Hermetic: the homepage makes no upstream BFF calls so no `page.route`
 * mocks are needed. The single dependency is the Next dev server boot
 * managed by `playwright.config.ts`.
 */

test.describe("Homepage — EN (/)", () => {
  test("renders the hero with the option-A headline", async ({ page }) => {
    await page.goto("/");

    // Hero block.
    await expect(page.getByTestId("hero-en")).toBeVisible();
    await expect(page.getByTestId("hero-headline")).toContainText(
      "Korea's medical imaging data",
    );

    // CTA pair (FR-HP-2).
    await expect(page.getByTestId("hero-cta-primary")).toContainText(
      "Request data access",
    );
    await expect(page.getByTestId("hero-cta-secondary")).toContainText(
      "View technical overview",
    );
  });

  test("renders trust bar with four compliance badges", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("trust-bar")).toBeVisible();
    for (const variant of ["pipa", "soc2", "iso27001", "hipaa"]) {
      await expect(page.getByTestId(`compliance-badge-${variant}`)).toBeVisible();
    }
  });

  test("renders the canonical 5-step how-it-works ladder", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("how-it-works")).toBeVisible();
    for (let i = 1; i <= 5; i++) {
      await expect(page.getByTestId(`step-${i}`)).toBeVisible();
    }
  });

  test("renders the four metric tiles + TCIA attribution", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("metrics-grid")).toBeVisible();
    for (let i = 1; i <= 4; i++) {
      await expect(page.getByTestId(`metric-tile-${i}`)).toBeVisible();
    }
    await expect(page.getByTestId("tcia-attribution")).toContainText("TCIA");
  });

  test("never renders forbidden compliance vocabulary", async ({ page }) => {
    await page.goto("/");
    const html = await page.content();
    expect(html).not.toMatch(/\bcertified\b/i);
    expect(html).not.toMatch(/\bguaranteed\b/i);
    expect(html).not.toMatch(/HIPAA-compliant/);
  });

  test("CTA primary navigates to /contact?intent=buyer", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("hero-cta-primary").click();
    await page.waitForURL(/\/contact\?intent=buyer/);
    await expect(page.getByTestId("contact-form")).toBeVisible();
  });
});

test.describe("Homepage — KR (/ko)", () => {
  test("renders the Korean hero", async ({ page }) => {
    await page.goto("/ko");
    await expect(page.getByTestId("hero-ko")).toBeVisible();
    await expect(page.getByTestId("hero-headline")).toContainText(
      "한국 의료영상 데이터",
    );
    // MEDIUM-5 fix in qa-report-portal-redesign — primaryCta is the
    // buyer-side action ("데이터 요청"); the hospital-partner path lives
    // on the secondary `forHospitals` link below.
    await expect(page.getByTestId("hero-cta-primary")).toContainText(
      "데이터 요청",
    );
  });

  test("renders the KR footer with the legal block", async ({ page }) => {
    await page.goto("/ko");
    const legal = page.getByTestId("footer-kr-legal");
    await expect(legal).toBeVisible();
    await expect(legal).toContainText("대표자");
    await expect(legal).toContainText("사업자등록번호");
    await expect(legal).toContainText("주소");
    await expect(legal).toContainText("고객센터");
  });

  test("never renders forbidden KR compliance vocabulary", async ({ page }) => {
    await page.goto("/ko");
    const html = await page.content();
    expect(html).not.toMatch(/인증됨/);
    expect(html).not.toMatch(/보장/);
  });
});

test.describe("Language toggle", () => {
  test("EN -> KR navigates to /ko and sets cookie", async ({ page, context }) => {
    await page.goto("/");
    await page.getByTestId("lang-toggle-ko").first().click();
    await page.waitForURL(/\/ko$/);
    await expect(page.getByTestId("hero-ko")).toBeVisible();

    // Read both surfaces — context.cookies() can miss cookies set via
    // document.cookie before a same-document navigation in chromium when
    // bypassCSP is on. Falling back to document.cookie keeps the assertion
    // honest while still letting context.cookies() be the primary check.
    const docCookie = await page.evaluate(() => document.cookie);
    const ctxCookies = await context.cookies();
    const ctxHas = ctxCookies.some(
      (c) => c.name === "radivault_locale" && c.value === "ko",
    );
    const docHas = /radivault_locale=ko/.test(docCookie);
    expect(ctxHas || docHas).toBe(true);
  });

  test("KR -> EN navigates to /", async ({ page }) => {
    await page.goto("/ko");
    await page.getByTestId("lang-toggle-en").first().click();
    await page.waitForURL(/localhost:3000\/$/);
    await expect(page.getByTestId("hero-en")).toBeVisible();
  });
});

test.describe("SEO surfaces", () => {
  test("/robots.txt exposes Disallow for portal routes", async ({ page }) => {
    const res = await page.request.get("/robots.txt");
    expect(res.status()).toBe(200);
    const body = await res.text();
    expect(body).toContain("Disallow: /portal");
    expect(body).toContain("Disallow: /hospital");
    expect(body).toContain("Sitemap:");
  });

  test("/sitemap.xml lists the 5 marketing URLs", async ({ page }) => {
    const res = await page.request.get("/sitemap.xml");
    expect(res.status()).toBe(200);
    const body = await res.text();
    expect(body).toContain("https://radivault.io/");
    expect(body).toContain("https://radivault.io/ko");
    expect(body).toContain("https://radivault.io/contact");
    expect(body).toContain("https://radivault.io/trust-center");
    expect(body).toContain("https://radivault.io/docs");
  });

  test("EN page emits JSON-LD Organization schema", async ({ page }) => {
    await page.goto("/");
    const ld = await page.locator('script[type="application/ld+json"]').textContent();
    expect(ld).toBeTruthy();
    expect(ld!).toContain("RadiVault Inc.");
    expect(ld!).toContain("Organization");
  });
});
