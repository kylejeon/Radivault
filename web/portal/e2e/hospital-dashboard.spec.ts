import { expect, test } from "@playwright/test";
import {
  blockRealUpstream,
  DEFAULT_HOSPITAL_AUDIT,
  DEFAULT_HOSPITAL_ORDERS,
  DEFAULT_HOSPITAL_STATS,
  mockHospitalAudit,
  mockHospitalOrders,
  mockHospitalStats,
} from "./fixtures/mocks";
import { injectHospitalSession } from "./fixtures/session";

/**
 * Scenario 3 — Hospital dashboard 6-tile load.
 *
 * Dev-spec §3.B lists the route as ``/hospital/{gateway_id}`` but the v0.1
 * implementation keeps hospital_id in the cookie and renders everything
 * from ``/hospital`` (see web/portal/src/app/hospital/page.tsx). The test
 * forges a hospital session with HOSP-001 and asserts all six tiles load
 * from their mocked endpoints.
 */

test.describe("Hospital dashboard", () => {
  test.beforeEach(async ({ page, context }) => {
    await blockRealUpstream(page);
    await mockHospitalStats(page, DEFAULT_HOSPITAL_STATS);
    await mockHospitalOrders(page, DEFAULT_HOSPITAL_ORDERS);
    await mockHospitalAudit(page, DEFAULT_HOSPITAL_AUDIT);
    await injectHospitalSession(context, "HOSP-001");
  });

  test("all six tiles render from mocked stats/orders/audit", async ({ page }) => {
    await page.goto("/hospital");

    // Header should confirm we're authenticated as HOSP-001.
    await expect(page.getByText("RadiVault 병원 대시보드")).toBeVisible();
    await expect(page.getByText("HOSP-001")).toBeVisible();

    // B-1 Studies — today / cumulative numbers.
    const b1 = page.getByTestId("tile-b1-studies");
    await expect(b1).toContainText("42"); // today
    await expect(b1).toContainText("12,478"); // cumulative (ko-KR locale separator)

    // B-2 Revenue — headline, disclaimer, and a derived KRW amount.
    const b2 = page.getByTestId("tile-b2-revenue");
    await expect(b2).toContainText("예상 수익 (시뮬레이션)");
    await expect(b2).toContainText("시뮬레이션 — v0.2 정산 대기");
    await expect(b2).toContainText(/₩\s*[\d,]+/);

    // B-3 Map — KoreaHeatmap renders as an SVG with aria-label.
    const b3 = page.getByTestId("tile-b3-map");
    await expect(b3.getByRole("img", { name: "기여 지역 지도" })).toBeVisible();

    // B-4 Gateway — "online" status renders the 정상 label.
    const b4 = page.getByTestId("tile-b4-gateway");
    await expect(b4).toContainText("정상");
    await expect(b4).toContainText("마지막 동기화");

    // B-5 Orders — order id and phase for each stream row.
    const b5 = page.getByTestId("tile-b5-orders");
    await expect(b5).toContainText("ord_5a3f");
    await expect(b5).toContainText("12 스터디");

    // B-6 Audit — 4 event rows, each with an 8-char hash short.
    const b6 = page.getByTestId("tile-b6-audit");
    await expect(b6).toContainText("ingest.accepted");
    await expect(b6).toContainText("3f4a9b12");
    await expect(b6.locator("ul li")).toHaveCount(DEFAULT_HOSPITAL_AUDIT.events.length);
  });

  test("B-4 reflects a degraded (warning) gateway status when mocked", async ({ page }) => {
    // Re-register the stats mock with warning status. Our factory returns a
    // localised Korean pill per dev-spec FR-B-13.
    await mockHospitalStats(page, {
      ...DEFAULT_HOSPITAL_STATS,
      gateway_health: {
        status: "warning",
        last_sync_at: new Date(Date.now() - 20 * 60_000).toISOString(),
        last_sync_delta_seconds: 1200,
      },
    });
    await page.goto("/hospital");
    const b4 = page.getByTestId("tile-b4-gateway");
    await expect(b4).toContainText("주의");
  });

  test("each /api/hospital/* call is intercepted (no live upstream)", async ({ page }) => {
    const hits: string[] = [];
    page.on("response", (res) => {
      if (res.url().includes("/api/hospital/")) {
        hits.push(`${res.status()} ${res.url()}`);
      }
    });
    await page.goto("/hospital");
    await expect(page.getByTestId("tile-b1-studies")).toContainText("42");

    // All three hospital BFF endpoints are hit and all resolve 200 from mocks.
    const joined = hits.join("\n");
    expect(joined).toMatch(/200 .*\/api\/hospital\/stats/);
    expect(joined).toMatch(/200 .*\/api\/hospital\/orders/);
    expect(joined).toMatch(/200 .*\/api\/hospital\/audit/);
    // Critically: we never got a 599 (the blockRealUpstream tripwire).
    expect(joined).not.toMatch(/599/);
  });
});
