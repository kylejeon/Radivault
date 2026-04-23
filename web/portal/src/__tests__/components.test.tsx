/**
 * Smoke tests for the critical demo-facing components.
 *
 * These are deliberately minimal: they exist so a silent CSS / props regression
 * doesn't turn up 30 seconds before a demo. Anything UX-rich is exercised by
 * the Playwright e2e suite (scaffolded but not landed in v0.1).
 */
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { PhaseStepper } from "@/components/PhaseStepper";
import { ModalityBadge } from "@/components/ModalityBadge";
import { StudyCard } from "@/components/StudyCard";
import { CohortSummary } from "@/components/CohortSummary";
import { TileCard } from "@/components/TileCard";
import { resolveError } from "@/lib/errors";

describe("PhaseStepper", () => {
  it("renders the 5 happy-path steps", () => {
    render(<PhaseStepper phase="fetching_from_hospital" />);
    expect(screen.getByText("Accepted")).toBeInTheDocument();
    expect(screen.getByText("Fetching from hospital")).toBeInTheDocument();
    expect(screen.getByText("Preparing download")).toBeInTheDocument();
    expect(screen.getByText("Ready to download")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("shows a red banner for terminal errors", () => {
    render(<PhaseStepper phase="cancelled" />);
    expect(screen.getByRole("status")).toHaveTextContent(/cancelled/);
    expect(screen.queryByText("Fetching from hospital")).not.toBeInTheDocument();
  });
});

describe("ModalityBadge", () => {
  it("uses modality class for known modalities", () => {
    const { container } = render(<ModalityBadge modality="CT" />);
    const badge = container.querySelector("span.badge-modality");
    expect(badge?.className).toMatch(/\bct\b/);
    expect(badge).toHaveTextContent("CT");
  });
  it("falls back to unknown for missing modality", () => {
    const { container } = render(<ModalityBadge modality={null} />);
    const badge = container.querySelector("span.badge-modality");
    expect(badge?.className).toMatch(/\bunknown\b/);
  });
});

describe("StudyCard", () => {
  it("renders truncated UID and stats", () => {
    render(
      <StudyCard
        pseudoStudyUid="2.25.1234567890.abcdef"
        modality="MR"
        bodyPart="BRAIN"
        nInstances={42}
        sizeMb={128.5}
        studyYear={2025}
      />,
    );
    expect(screen.getByText(/abcdef/)).toBeInTheDocument();
    expect(screen.getByText("BRAIN")).toBeInTheDocument();
    expect(screen.getByText(/42 instances/)).toBeInTheDocument();
    expect(screen.getByText(/128.5 MB/)).toBeInTheDocument();
    expect(screen.getByText("2025")).toBeInTheDocument();
  });
});

describe("CohortSummary", () => {
  it("disables Review when cohort is empty", () => {
    render(<CohortSummary count={0} totalSizeMb={0} onReview={() => {}} />);
    expect(screen.getByRole("button", { name: /Review order/ })).toBeDisabled();
  });
  it("masks price (v0.1)", () => {
    render(<CohortSummary count={10} totalSizeMb={500} onReview={() => {}} />);
    expect(screen.getByText(/contact for pricing/)).toBeInTheDocument();
  });
});

describe("TileCard", () => {
  it("renders a headline value + footer", () => {
    render(
      <TileCard
        title="예상 수익 (시뮬레이션)"
        value="₩ 1,234,567"
        footer="시뮬레이션 — v0.2 정산 대기"
      />,
    );
    expect(screen.getByText("예상 수익 (시뮬레이션)")).toBeInTheDocument();
    expect(screen.getByText("₩ 1,234,567")).toBeInTheDocument();
    expect(screen.getByText(/v0.2 정산 대기/)).toBeInTheDocument();
  });
});

describe("resolveError", () => {
  it("returns the canonical message for a known code", () => {
    const m = resolveError("ERR_AUTH_EXPIRED");
    expect(m.title).toMatch(/expired/i);
    expect(m.variant).toBe("auth");
  });
  it("falls back for unknown codes", () => {
    const m = resolveError("ERR_TOTALLY_UNKNOWN");
    expect(m.code).toBe("ERR_TOTALLY_UNKNOWN");
    expect(m.title).toMatch(/went wrong/i);
  });
});
