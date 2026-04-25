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
 * Scenario 3 — Hospital console dashboard load (9-tile, design-spec §18.1).
 *
 * Forges a hospital session with HOSP-001 and asserts:
 *  - all 9 tiles render from their mocked endpoints (FR-HO-3.1..3.9)
 *  - the audit-log preview surfaces the top-N events (FR-HO-7)
 *  - degraded gateway flips the heartbeat tile to amber (FR-HO-3.5)
 *  - every /api/hospital/* call resolves through the mock (no 599)
 */

test.describe("Hospital console — 9-tile dashboard", () => {
  test.beforeEach(async ({ page, context }) => {
    await blockRealUpstream(page);
    await mockHospitalStats(page, DEFAULT_HOSPITAL_STATS);
    await mockHospitalOrders(page, DEFAULT_HOSPITAL_ORDERS);
    await mockHospitalAudit(page, DEFAULT_HOSPITAL_AUDIT);
    await mockHospitalAuditChainStatus(page, DEFAULT_HOSPITAL_AUDIT_CHAIN);
    await mockHospitalQuota(page, DEFAULT_HOSPITAL_QUOTA);
    await injectHospitalSession(context, "HOSP-001");
  });

  test("all 9 tiles render", async ({ page }) => {
    await page.goto("/hospital");

    // Wordmark + hospital_id pill in header. Wordmark also appears in
    // the strengthened KR footer (§19.1) so we anchor on the header.
    await expect(
      page.getByRole("banner").getByText("RadiVault 병원 콘솔"),
    ).toBeVisible();
    await expect(page.getByText("HOSP-001").first()).toBeVisible();

    // Tile 1 — uploaded studies + sparkline.
    const t1 = page.getByTestId("tile-h1-uploaded-studies");
    await expect(t1).toContainText("42");      // today
    await expect(t1).toContainText("12,478");  // cumulative

    // Tile 2 — total bytes.
    await expect(page.getByTestId("tile-h2-total-bytes")).toContainText(/B|KB|MB|GB|TB/);

    // Tile 3 — modality donut. SVG present + total study count rendered.
    const t3 = page.getByTestId("tile-h3-modality");
    await expect(t3.locator("svg")).toBeVisible();
    // CT (5,102) + MR (3,014) + CR (2,511) = 10,627
    await expect(t3).toContainText("10,627");

    // Tile 4 — audit chain status (ok variant + 16-char hash).
    const t4 = page.getByTestId("tile-h4-audit-chain");
    await expect(t4.getByTestId("audit-chain-status-badge")).toHaveAttribute(
      "data-variant",
      "ok",
    );
    await expect(t4).toContainText("a3f8d9c1b2e4f5a6");

    // Tile 5 — gateway heartbeat with online tone.
    const t5 = page.getByTestId("tile-h5-gateway-hb");
    await expect(t5.getByTestId("gateway-heartbeat-chart")).toHaveAttribute(
      "data-variant",
      "online",
    );

    // Tile 6 — quota 3-up. Both progressbars + max_concurrent_uploads number.
    const t6 = page.getByTestId("tile-h6-quota");
    await expect(t6.locator('[role="progressbar"]')).toHaveCount(2);
    await expect(t6).toContainText("4"); // max_concurrent_uploads

    // Tile 7 — revenue. K-13 form + K-15 disclaimer.
    const t7 = page.getByTestId("tile-h7-revenue");
    await expect(t7).toContainText("₩ 18,400,000");
    await expect(t7).toContainText("시뮬레이션 — v0.2 정산 대기");

    // Tile 8 — order inflow. 3 orders, all buyer **** masked.
    const t8 = page.getByTestId("tile-h8-order-inflow");
    await expect(t8).toContainText("3 건"); // 3 orders this month
    await expect(t8.getByText("buyer ****")).toHaveCount(3);

    // Tile 9 — ruleset / salt / pixel.
    const t9 = page.getByTestId("tile-h9-ruleset");
    await expect(t9).toContainText("v0.1.0"); // de-id ruleset
    await expect(t9).toContainText("2026-01"); // salt version
    await expect(t9).toContainText("v0.2.0"); // pixel engine
  });

  test("gateway heartbeat flips to warning when stats marks degraded", async ({ page }) => {
    await mockHospitalStats(page, {
      ...DEFAULT_HOSPITAL_STATS,
      gateway_health: {
        status: "warning",
        last_sync_at: new Date(Date.now() - 20 * 60_000).toISOString(),
        last_sync_delta_seconds: 1200,
      },
    });
    await page.goto("/hospital");
    await expect(
      page.getByTestId("gateway-heartbeat-chart"),
    ).toHaveAttribute("data-variant", "warning");
  });

  test("audit log preview shows the top events with the 'full log' link", async ({ page }) => {
    await page.goto("/hospital");
    const preview = page.getByTestId("hospital-audit-preview");
    await expect(preview).toContainText("ingest.accepted");
    await expect(preview.getByRole("link", { name: /전체 로그/ })).toHaveAttribute(
      "href",
      "/hospital/audit",
    );
  });

  test("every BFF call is intercepted (no 599 tripwire)", async ({ page }) => {
    const hits: string[] = [];
    page.on("response", (res) => {
      if (res.url().includes("/api/hospital/")) {
        hits.push(`${res.status()} ${res.url()}`);
      }
    });
    await page.goto("/hospital");
    await expect(page.getByTestId("tile-h1-uploaded-studies")).toContainText("42");
    // Audit-log preview is the lazy second fetch — wait for it before
    // snapshotting hits, otherwise the assertion can race the request.
    await expect(
      page.getByTestId("hospital-audit-preview"),
    ).toContainText("ingest.accepted");
    const joined = hits.join("\n");
    expect(joined).toMatch(/200 .*\/api\/hospital\/stats/);
    expect(joined).toMatch(/200 .*\/api\/hospital\/orders/);
    expect(joined).toMatch(/200 .*\/api\/hospital\/me\/audit-chain-status/);
    expect(joined).toMatch(/200 .*\/api\/hospital\/me\/quota/);
    expect(joined).toMatch(/200 .*\/api\/hospital\/audit/);
    expect(joined).not.toMatch(/599/);
  });
});

test.describe("Hospital console — /audit page (§18.2)", () => {
  test.beforeEach(async ({ page, context }) => {
    await blockRealUpstream(page);
    await mockHospitalAudit(page, DEFAULT_HOSPITAL_AUDIT);
    await injectHospitalSession(context, "HOSP-001");
  });

  test("renders the time-ordered list with KST timestamps", async ({ page }) => {
    await page.goto("/hospital/audit");
    await expect(page.getByText("감사 로그").first()).toBeVisible();
    const list = page.getByTestId("audit-log-list");
    await expect(list).toBeVisible();
    await expect(list).toContainText("ingest.accepted");
    await expect(list).toContainText("3f4a9b12");
  });
});

test.describe("Hospital console — /quota page (§18.3)", () => {
  test.beforeEach(async ({ page, context }) => {
    await blockRealUpstream(page);
    await mockHospitalQuota(page, DEFAULT_HOSPITAL_QUOTA);
    await injectHospitalSession(context, "HOSP-001");
  });

  test("renders 4 sections + the v0.1 enforce disclaimer", async ({ page }) => {
    await page.goto("/hospital/quota");
    await expect(page.getByTestId("quota-daily")).toBeVisible();
    await expect(page.getByTestId("quota-monthly")).toBeVisible();
    await expect(page.getByTestId("quota-concurrent")).toContainText("4");
    await expect(page.getByTestId("quota-ruleset")).toContainText("v0.1.0");
    await expect(
      page.getByText(/v0.1 한도 집행 없음 — 표시만/),
    ).toBeVisible();
  });
});
