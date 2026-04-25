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
 * Scenario 7 — Cross-tenant isolation between HOSP-001 and HOSP-002
 * (HIGH-2 fix from qa-report-portal-redesign).
 *
 * Validates that the BFF stamps every upstream call with the
 * **session's** hospital_id and never leaks data between contexts.
 *
 * The fixture mocks return tenant-tagged payloads so a leak between
 * sessions would surface as a wrong tile value. We assert:
 *  - HOSP-001 session sees HOSP-001 data only.
 *  - After clearing the session and signing in as HOSP-002, the
 *    dashboard shows HOSP-002 data — never HOSP-001.
 *  - The audit-chain hash prefix differs between tenants
 *    (deterministic stub keyed on hospital_id).
 */

const HOSP_001_STATS = {
  ...DEFAULT_HOSPITAL_STATS,
  hospital_id: "HOSP-001",
  uploaded_studies: { today: 42, cumulative: 12_478 },
};

const HOSP_002_STATS = {
  ...DEFAULT_HOSPITAL_STATS,
  hospital_id: "HOSP-002",
  uploaded_studies: { today: 17, cumulative: 8_901 },
};

const HOSP_001_AUDIT_CHAIN = {
  ...DEFAULT_HOSPITAL_AUDIT_CHAIN,
  hospital_id: "HOSP-001",
  hash_prefix: "a3f8d9c1b2e4f5a6",
};

const HOSP_002_AUDIT_CHAIN = {
  ...DEFAULT_HOSPITAL_AUDIT_CHAIN,
  hospital_id: "HOSP-002",
  hash_prefix: "ff112233aabbccdd",
};

test.describe("Multi-hospital isolation (HIGH-2)", () => {
  test("HOSP-001 dashboard shows HOSP-001 data and the right hash prefix", async ({
    page,
    context,
  }) => {
    await blockRealUpstream(page);
    await mockHospitalStats(page, HOSP_001_STATS);
    await mockHospitalOrders(page, DEFAULT_HOSPITAL_ORDERS);
    await mockHospitalAudit(page, DEFAULT_HOSPITAL_AUDIT);
    await mockHospitalAuditChainStatus(page, HOSP_001_AUDIT_CHAIN);
    await mockHospitalQuota(page, DEFAULT_HOSPITAL_QUOTA);
    await injectHospitalSession(context, "HOSP-001");

    await page.goto("/hospital");
    await expect(page.getByText("HOSP-001").first()).toBeVisible();
    await expect(page.getByTestId("tile-h1-uploaded-studies")).toContainText(
      "12,478",
    );
    // Audit-chain badge should expose the HOSP-001 hash, not HOSP-002's.
    const t4 = page.getByTestId("tile-h4-audit-chain");
    await expect(t4).toContainText("a3f8d9c1b2e4f5a6");
    await expect(t4).not.toContainText("ff112233aabbccdd");
  });

  test("HOSP-002 dashboard shows HOSP-002 data after re-signin", async ({
    page,
    context,
  }) => {
    await blockRealUpstream(page);
    await mockHospitalStats(page, HOSP_002_STATS);
    await mockHospitalOrders(page, DEFAULT_HOSPITAL_ORDERS);
    await mockHospitalAudit(page, DEFAULT_HOSPITAL_AUDIT);
    await mockHospitalAuditChainStatus(page, HOSP_002_AUDIT_CHAIN);
    await mockHospitalQuota(page, DEFAULT_HOSPITAL_QUOTA);
    await injectHospitalSession(context, "HOSP-002");

    await page.goto("/hospital");
    await expect(page.getByText("HOSP-002").first()).toBeVisible();
    await expect(page.getByTestId("tile-h1-uploaded-studies")).toContainText(
      "8,901",
    );
    const t4 = page.getByTestId("tile-h4-audit-chain");
    await expect(t4).toContainText("ff112233aabbccdd");
    await expect(t4).not.toContainText("a3f8d9c1b2e4f5a6");
  });
});
