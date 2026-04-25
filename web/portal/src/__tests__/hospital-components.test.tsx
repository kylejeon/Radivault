/**
 * Hospital console v0.3 components — design-spec §17 + §19.
 *
 * Smoke tests for the 7 new tiles plus FloatingContactButton +
 * FooterKr `variant="hospital"`. Mirrors the `data-testid` contracts
 * the hospital-dashboard e2e spec relies on.
 */

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

import {
  AuditChainStatusBadge,
  type AuditChainStatusData,
} from "@/components/hospital/AuditChainStatusBadge";
import {
  GatewayHeartbeatChart,
  type GatewayHeartbeatData,
} from "@/components/hospital/GatewayHeartbeatChart";
import { QuotaTile } from "@/components/hospital/QuotaTile";
import { RulesetVersionBadge } from "@/components/hospital/RulesetVersionBadge";
import { ModalityDistributionChart } from "@/components/hospital/ModalityDistributionChart";
import { RevenueTile, REVENUE_DUMMY } from "@/components/hospital/RevenueTile";
import { OrderInflowTile } from "@/components/hospital/OrderInflowTile";
import { FloatingContactButton } from "@/components/shared/FloatingContactButton";
import { FooterKr } from "@/components/shared/FooterKr";
import {
  formatBytes,
  formatKrw,
  formatRelativeKo,
} from "@/components/hospital/format";

describe("format helpers", () => {
  it("formatBytes scales B → MB → GB", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(150 * 1024 * 1024)).toBe("150.0 MB");
    expect(formatBytes(2 * 1024 * 1024 * 1024)).toBe("2.0 GB");
  });
  it("formatKrw uses ₩ 150,000 form (K-13)", () => {
    expect(formatKrw(18_400_000)).toBe("₩ 18,400,000");
    expect(formatKrw(0)).toBe("₩ 0");
  });
  it("formatRelativeKo returns Korean relative copy", () => {
    const now = Date.UTC(2026, 3, 25, 12, 0, 0);
    const t1 = new Date(now - 30 * 1000).toISOString();
    const t2 = new Date(now - 90 * 60_000).toISOString();
    const t3 = new Date(now - 5 * 60_000).toISOString();
    expect(formatRelativeKo(t1, now)).toBe("방금 전");
    expect(formatRelativeKo(t3, now)).toMatch(/5분 전/);
    expect(formatRelativeKo(t2, now)).toMatch(/시간 전/);
  });
});

describe("AuditChainStatusBadge (§17.1)", () => {
  const ok: AuditChainStatusData = {
    last_anchor_at: new Date().toISOString(),
    hash_prefix: "a3f8d9c1b2e4f5a6",
    chain_continuous: true,
    last_anchor_age_seconds: 240,
  };
  it("renders ok variant with hash prefix", () => {
    render(<AuditChainStatusBadge data={ok} />);
    expect(screen.getByTestId("audit-chain-status-badge")).toHaveAttribute(
      "data-variant",
      "ok",
    );
    expect(screen.getByTestId("audit-chain-status-badge-hash")).toHaveTextContent(
      "a3f8d9c1b2e4f5a6",
    );
  });
  it("renders broken variant when chain_continuous=false", () => {
    render(
      <AuditChainStatusBadge
        data={{ ...ok, chain_continuous: false }}
      />,
    );
    expect(screen.getByTestId("audit-chain-status-badge")).toHaveAttribute(
      "data-variant",
      "broken",
    );
  });
  it("renders stale variant when age >= 1h", () => {
    render(
      <AuditChainStatusBadge
        data={{ ...ok, last_anchor_age_seconds: 4000 }}
      />,
    );
    expect(screen.getByTestId("audit-chain-status-badge")).toHaveAttribute(
      "data-variant",
      "stale",
    );
  });
  it("renders loading skeleton", () => {
    render(<AuditChainStatusBadge data={null} loading />);
    expect(screen.getByTestId("audit-chain-status-badge")).toHaveAttribute(
      "data-state",
      "loading",
    );
  });
  it("renders error pill when error=true", () => {
    render(<AuditChainStatusBadge data={null} error />);
    expect(screen.getByTestId("audit-chain-status-badge")).toHaveAttribute(
      "data-state",
      "error",
    );
  });
});

describe("GatewayHeartbeatChart (§17.2)", () => {
  const onlineData: GatewayHeartbeatData = {
    status: "online",
    last_sync_at: new Date(Date.now() - 2 * 60_000).toISOString(),
    last_sync_delta_seconds: 120,
  };
  it("renders the 24h sparkline with online tone", () => {
    render(<GatewayHeartbeatChart data={onlineData} />);
    const el = screen.getByTestId("gateway-heartbeat-chart");
    expect(el).toHaveAttribute("data-variant", "online");
    expect(el.querySelector("svg")).not.toBeNull();
  });
  it("renders the empty state when status=unknown + no last_sync_at", () => {
    render(
      <GatewayHeartbeatChart
        data={{
          status: "unknown",
          last_sync_at: null,
          last_sync_delta_seconds: null,
        }}
      />,
    );
    expect(screen.getByTestId("gateway-heartbeat-chart")).toHaveAttribute(
      "data-state",
      "empty",
    );
  });
});

describe("QuotaTile (§17.3)", () => {
  const QUOTA = {
    daily: {
      bytes_used: 100 * 1024 * 1024,
      bytes_limit: 10 * 1024 * 1024 * 1024,
      resets_at: new Date().toISOString(),
    },
    monthly: {
      bytes_used: 1 * 1024 * 1024 * 1024,
      bytes_limit: 300 * 1024 * 1024 * 1024,
      resets_at: new Date().toISOString(),
    },
    max_concurrent_uploads: 4,
  };
  it("renders 3 segments with progressbars", () => {
    const { container } = render(<QuotaTile data={QUOTA} />);
    expect(screen.getByTestId("quota-tile")).toBeInTheDocument();
    const bars = container.querySelectorAll('[role="progressbar"]');
    expect(bars.length).toBe(2); // daily + monthly
    expect(screen.getByText("4")).toBeInTheDocument();
  });
  it("renders the partial-failed state per segment", () => {
    render(
      <QuotaTile
        data={{ ...QUOTA, monthly: null }}
      />,
    );
    expect(screen.getByText(/조회 실패/)).toBeInTheDocument();
  });
});

describe("RulesetVersionBadge (§17.4)", () => {
  it("renders 3 lines + rotate date", () => {
    render(
      <RulesetVersionBadge
        data={{
          ruleset_version: "v0.1.0",
          salt_version: "2026-01",
          salt_rotate_at: new Date(Date.now() + 30 * 86400_000).toISOString(),
          pixel_engine_version: "v0.2.0",
        }}
      />,
    );
    expect(screen.getByTestId("ruleset-version-badge")).toHaveAttribute(
      "data-variant",
      "current",
    );
    expect(screen.getByText("v0.1.0")).toBeInTheDocument();
    expect(screen.getByText("v0.2.0")).toBeInTheDocument();
  });
  it("flips to outdated when salt rotate has passed", () => {
    render(
      <RulesetVersionBadge
        data={{
          ruleset_version: "v0.1.0",
          salt_version: "2026-01",
          salt_rotate_at: new Date(Date.now() - 86400_000).toISOString(),
          pixel_engine_version: "v0.2.0",
        }}
      />,
    );
    expect(screen.getByTestId("ruleset-version-badge")).toHaveAttribute(
      "data-variant",
      "outdated",
    );
  });
});

describe("ModalityDistributionChart (§17.5)", () => {
  it("renders donut + legend with totals", () => {
    render(
      <ModalityDistributionChart
        slices={[
          { modality: "CT", count: 100 },
          { modality: "MR", count: 50 },
        ]}
      />,
    );
    expect(screen.getByTestId("modality-distribution-chart")).toBeInTheDocument();
    // Total = 150 — rendered in the donut center.
    expect(screen.getByText("150")).toBeInTheDocument();
    // Legend rows
    expect(screen.getByText("CT")).toBeInTheDocument();
    expect(screen.getByText("MR")).toBeInTheDocument();
  });
  it("renders empty state when total=0", () => {
    render(<ModalityDistributionChart slices={[]} />);
    expect(screen.getByTestId("modality-distribution-chart")).toHaveAttribute(
      "data-state",
      "empty",
    );
  });
});

describe("RevenueTile (§17.6 / K-15)", () => {
  it("renders the static dummy for HOSP-001 with KRW + Δ + disclaimer", () => {
    render(<RevenueTile data={REVENUE_DUMMY["HOSP-001"]} />);
    expect(screen.getByTestId("revenue-tile")).toBeInTheDocument();
    expect(screen.getByText("₩ 18,400,000")).toBeInTheDocument();
    expect(screen.getByTestId("revenue-tile-delta")).toHaveTextContent(/12.3/);
    expect(screen.getByText(/시뮬레이션 — v0.2 정산 대기/)).toBeInTheDocument();
  });
  it("renders empty state for HOSP-002 (first month)", () => {
    render(<RevenueTile data={REVENUE_DUMMY["HOSP-002"]} />);
    expect(screen.getByTestId("revenue-tile")).toHaveAttribute(
      "data-state",
      "empty",
    );
    expect(screen.getByText(/이번 달 첫 데이터/)).toBeInTheDocument();
    // Disclaimer must still render in the empty state.
    expect(screen.getByText(/시뮬레이션 — v0.2 정산 대기/)).toBeInTheDocument();
  });
});

describe("OrderInflowTile (§17.7 / FR-SH-5)", () => {
  it("masks every buyer label as 'buyer ****'", () => {
    render(
      <OrderInflowTile
        data={{
          count_this_month: 42,
          recent: [
            {
              order_id_masked: "ord_5a3f",
              n_studies: 12,
              submitted_at: new Date().toISOString(),
            },
            {
              order_id_masked: "ord_7c2e",
              n_studies: 24,
              submitted_at: new Date().toISOString(),
            },
            {
              order_id_masked: "ord_a1b2",
              n_studies: 8,
              submitted_at: new Date().toISOString(),
            },
          ],
        }}
      />,
    );
    expect(screen.getByTestId("order-inflow-tile")).toBeInTheDocument();
    expect(screen.getByText("42 건")).toBeInTheDocument();
    // Three rows, all masked.
    expect(screen.getAllByText("buyer ****").length).toBe(3);
  });
  it("renders empty state when count=0", () => {
    render(
      <OrderInflowTile
        data={{ count_this_month: 0, recent: [] }}
      />,
    );
    expect(screen.getByTestId("order-inflow-tile")).toHaveAttribute(
      "data-state",
      "empty",
    );
  });
});

describe("FloatingContactButton (§19.2 / FR-HO-10)", () => {
  it("renders the trigger with Korean aria-label", () => {
    render(<FloatingContactButton />);
    const trigger = screen.getByTestId("floating-contact-button-trigger");
    expect(trigger).toHaveAttribute("aria-label", "1:1 문의 열기");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });
  it("opens the popover with both kakao + email options (K-14 default)", () => {
    render(<FloatingContactButton />);
    fireEvent.click(screen.getByTestId("floating-contact-button-trigger"));
    expect(screen.getByTestId("floating-contact-button-popover")).toBeInTheDocument();
    expect(screen.getByTestId("floating-contact-button-kakao")).toBeInTheDocument();
    expect(
      screen.getByTestId("floating-contact-button-email"),
    ).toHaveAttribute("href", "mailto:contact@radivault.io");
  });
  it("respects channels prop (kakao only)", () => {
    render(<FloatingContactButton channels={["kakao"]} />);
    fireEvent.click(screen.getByTestId("floating-contact-button-trigger"));
    expect(
      screen.queryByTestId("floating-contact-button-email"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("floating-contact-button-kakao"),
    ).toBeInTheDocument();
  });
  it("ESC closes the popover and returns focus to trigger", async () => {
    render(<FloatingContactButton />);
    const trigger = screen.getByTestId("floating-contact-button-trigger");
    fireEvent.click(trigger);
    expect(
      screen.getByTestId("floating-contact-button-popover"),
    ).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(
      screen.queryByTestId("floating-contact-button-popover"),
    ).not.toBeInTheDocument();
    // Focus restored to the trigger.
    expect(trigger).toHaveFocus();
  });
});

describe("FooterKr variant (§19.1)", () => {
  it("homepage variant renders the original 4-column ladder + legal block", () => {
    const { container } = render(<FooterKr />);
    expect(container.querySelector('[data-testid="footer-kr"]')).not.toBeNull();
    expect(
      container.querySelector('[data-testid="footer-kr-legal"]'),
    ).not.toBeNull();
  });
  it("hospital variant renders the strengthened legal block + 4-col grid", () => {
    const { container } = render(<FooterKr variant="hospital" />);
    expect(
      container.querySelector('[data-testid="footer-kr-hospital"]'),
    ).not.toBeNull();
    expect(
      container.querySelector('[data-testid="footer-kr-hospital-legal"]'),
    ).not.toBeNull();
    // Strengthened fields per §19.1 — at least 대표이사 + 통신판매업 + 개인정보보호책임자.
    expect(container.textContent).toContain("대표이사");
    expect(container.textContent).toContain("통신판매업");
    expect(container.textContent).toContain("개인정보보호책임자");
  });
});

// Make sure vi is not flagged as unused when sub-suites grow.
vi.fn;
