/**
 * Shared homepage component snapshots — design-spec-portal-redesign §5.
 *
 * Confirms the components render with the right copy in both locales
 * and that the `data-testid` contracts the e2e suite depends on are
 * stable.
 */

import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ComplianceBadge } from "@/components/shared/ComplianceBadge";
import { TrustBar } from "@/components/shared/TrustBar";
import { MetricTile } from "@/components/shared/MetricTile";
import { ValueTile } from "@/components/shared/ValueTile";

describe("ComplianceBadge", () => {
  it("renders all four variants in EN", () => {
    for (const variant of ["pipa", "soc2", "iso27001", "hipaa"] as const) {
      const { container } = render(
        <ComplianceBadge variant={variant} locale="en" />,
      );
      expect(
        container.querySelector(`[data-testid="compliance-badge-${variant}"]`),
      ).not.toBeNull();
    }
  });

  it("renders KR text", () => {
    const { getByTestId } = render(
      <ComplianceBadge variant="pipa" locale="ko" />,
    );
    expect(getByTestId("compliance-badge-pipa").textContent).toContain("준수");
  });
});

describe("TrustBar", () => {
  it("renders four columns in EN with correct status text", () => {
    const { getByTestId, getAllByText } = render(<TrustBar locale="en" />);
    expect(getByTestId("trust-bar")).not.toBeNull();
    // "in preparation" appears once for SOC 2.
    expect(getAllByText(/in preparation/).length).toBeGreaterThanOrEqual(1);
    expect(getAllByText(/aligned/).length).toBeGreaterThanOrEqual(1);
  });

  it("renders four columns in KR with Korean status text", () => {
    const { getAllByText } = render(<TrustBar locale="ko" />);
    expect(getAllByText("준비 중").length).toBeGreaterThanOrEqual(1);
    expect(getAllByText("준수").length).toBeGreaterThanOrEqual(1);
  });
});

describe("MetricTile", () => {
  it("renders the value and label", () => {
    const { getByText } = render(
      <MetricTile value="2" label="hospitals federated" sublabel="in demo" />,
    );
    expect(getByText("2")).not.toBeNull();
    expect(getByText("hospitals federated")).not.toBeNull();
    expect(getByText("in demo")).not.toBeNull();
  });
});

describe("ValueTile", () => {
  it("renders numbered variant with the step number", () => {
    const { getByText } = render(
      <ValueTile
        variant="numbered"
        step={3}
        title="De-ID engine"
        body="PHI tags + OCR + deface"
      />,
    );
    expect(getByText("3")).not.toBeNull();
    expect(getByText("De-ID engine")).not.toBeNull();
  });
});
