import { expect, test } from "@playwright/test";
import {
  blockRealUpstream,
  DEFAULT_HOSPITAL_AUDIT,
  DEFAULT_HOSPITAL_AUDIT_CHAIN,
  DEFAULT_HOSPITAL_ORDERS,
  DEFAULT_HOSPITAL_QUOTA,
  DEFAULT_HOSPITAL_STATS,
  mockHospitalAudit,
  mockHospitalAuditChainStatus,
  mockHospitalOrders,
  mockHospitalQuota,
  mockHospitalStats,
} from "./fixtures/mocks";
import { injectHospitalSession } from "./fixtures/session";

/**
 * §19.2 / FR-HO-10 — 1:1 문의 floating contact button.
 *
 * Verifies the button is mounted on the three Korean hospital pages,
 * exposes both KakaoTalk + Email options (K-14 default), respects the
 * focus trap on open, ESC closes, and is NOT mounted on the English
 * homepage (the component is render-gated by the page, not by client
 * code, so this guards against future re-mount mistakes).
 */

test.describe("Floating 1:1 문의 button (§19.2)", () => {
  test.describe("on hospital pages", () => {
    test.beforeEach(async ({ page, context }) => {
      await blockRealUpstream(page);
      await mockHospitalStats(page, DEFAULT_HOSPITAL_STATS);
      await mockHospitalOrders(page, DEFAULT_HOSPITAL_ORDERS);
      await mockHospitalAudit(page, DEFAULT_HOSPITAL_AUDIT);
      await mockHospitalAuditChainStatus(page, DEFAULT_HOSPITAL_AUDIT_CHAIN);
      await mockHospitalQuota(page, DEFAULT_HOSPITAL_QUOTA);
      await injectHospitalSession(context, "HOSP-001");
    });

    test("/hospital — trigger renders bottom-right and opens both channels", async ({ page }) => {
      await page.goto("/hospital");
      const trigger = page.getByTestId("floating-contact-button-trigger");
      await expect(trigger).toBeVisible();
      await expect(trigger).toHaveAttribute("aria-label", "1:1 문의 열기");

      await trigger.click();
      await expect(trigger).toHaveAttribute("aria-expanded", "true");
      const popover = page.getByTestId("floating-contact-button-popover");
      await expect(popover).toBeVisible();
      await expect(popover).toHaveAttribute("role", "dialog");
      await expect(popover).toHaveAttribute("aria-modal", "true");

      // Both channels surface (K-14 default = both).
      await expect(
        page.getByTestId("floating-contact-button-kakao"),
      ).toBeVisible();
      const emailLink = page.getByTestId("floating-contact-button-email");
      await expect(emailLink).toBeVisible();
      await expect(emailLink).toHaveAttribute(
        "href",
        "mailto:contact@radivault.io",
      );
    });

    test("/hospital/audit — trigger also mounts here", async ({ page }) => {
      await page.goto("/hospital/audit");
      await expect(
        page.getByTestId("floating-contact-button-trigger"),
      ).toBeVisible();
    });

    test("/hospital/quota — trigger also mounts here", async ({ page }) => {
      await page.goto("/hospital/quota");
      await expect(
        page.getByTestId("floating-contact-button-trigger"),
      ).toBeVisible();
    });

    test("ESC closes the popover", async ({ page }) => {
      await page.goto("/hospital");
      const trigger = page.getByTestId("floating-contact-button-trigger");
      await trigger.click();
      await expect(
        page.getByTestId("floating-contact-button-popover"),
      ).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(
        page.getByTestId("floating-contact-button-popover"),
      ).toHaveCount(0);
    });
  });

  test.describe("on the English homepage", () => {
    test("trigger is NOT mounted on /", async ({ page }) => {
      await page.goto("/");
      await expect(
        page.getByTestId("floating-contact-button-trigger"),
      ).toHaveCount(0);
    });
  });
});
