/**
 * Buyer-browse-preview UI component smokes — design-spec §6, §7, §8, §9, §10.
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { StudyThumbnail } from "@/components/preview/StudyThumbnail";
import { SaMDFooter } from "@/components/preview/SaMDFooter";
import { SliceViewer } from "@/components/SliceViewer";

// react-hot-toast emits to the page-level <Toaster /> which isn't mounted
// in unit tests; mock it so click handlers run cleanly.
vi.mock("react-hot-toast", () => {
  const t = {
    success: vi.fn(),
    error: vi.fn(),
  };
  return { default: t, ...t };
});

describe("StudyThumbnail (design-spec §6)", () => {
  it("renders placeholder for non-verified status", () => {
    render(
      <StudyThumbnail studyUid="2.25.placeholder.001" status="pending" />,
    );
    expect(
      screen.getByTestId("study-thumbnail-placeholder-2.25.placeholder.001"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Preview unavailable/)).toBeInTheDocument();
  });

  it("renders the verified slot with data-testid attached", () => {
    render(
      <StudyThumbnail studyUid="2.25.verified.001" status="verified" />,
    );
    // jsdom doesn't have a real IntersectionObserver, so the component
    // immediately falls through to fetch — what we assert is that the
    // slot is rendered with its testid (the e2e suite covers IO timing).
    expect(
      screen.getByTestId("study-thumbnail-2.25.verified.001"),
    ).toBeInTheDocument();
  });
});

describe("SaMDFooter (design-spec §8)", () => {
  it("renders the EN disclaimer + TCIA attribution", () => {
    render(<SaMDFooter />);
    expect(screen.getByTestId("samd-disclaimer")).toBeInTheDocument();
    expect(
      screen.getByText(/Display only — not for diagnostic use/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Demo data based on TCIA/),
    ).toBeInTheDocument();
  });

  it("renders the KR disclaimer when locale='ko'", () => {
    render(<SaMDFooter locale="ko" />);
    expect(
      screen.getByText(/표시 전용 — 진단 용도 사용 금지/),
    ).toBeInTheDocument();
  });
});

describe("SliceViewer (design-spec §7) — SaMD scope", () => {
  it("hides slider when sliceCount=1 (single-frame variant)", () => {
    render(<SliceViewer studyUid="2.25.single.001" sliceCount={1} />);
    expect(screen.getByTestId("slice-viewer")).toBeInTheDocument();
    // Single-frame: slider not rendered.
    expect(screen.queryByTestId("slice-slider")).not.toBeInTheDocument();
  });

  it("renders slider + counter when sliceCount > 1", () => {
    render(<SliceViewer studyUid="2.25.multi.001" sliceCount={10} />);
    expect(screen.getByTestId("slice-slider")).toBeInTheDocument();
    expect(screen.getByTestId("slice-counter")).toBeInTheDocument();
    // Counter starts at the median frame (Math.floor(10/2)+1 = 6).
    expect(screen.getByTestId("slice-counter").textContent).toMatch(
      /Slice 6 of 10/,
    );
  });

  it("exposes zoom + window-level overlays", () => {
    render(<SliceViewer studyUid="2.25.zoom.001" sliceCount={5} />);
    expect(screen.getByTestId("zoom-controls")).toBeInTheDocument();
    expect(screen.getByTestId("window-level-controls")).toBeInTheDocument();
  });

  it("does NOT contain measurement / segmentation / annotate / diagnose tools", () => {
    const { container } = render(
      <SliceViewer studyUid="2.25.lint.001" sliceCount={5} />,
    );
    const html = container.innerHTML.toLowerCase();
    expect(html).not.toContain("measure");
    expect(html).not.toContain("segment");
    expect(html).not.toContain("annotate");
    expect(html).not.toContain("diagnose");
  });
});
