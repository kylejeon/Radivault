/**
 * FrameSliderViewer + DefacePill smoke tests
 * (design-spec-jpg-preview-defacing §16 AC-D-1..AC-D-12).
 *
 * Coverage:
 *   - AC-D-1: chip row renders one chip per series.
 *   - AC-D-2: chip click swaps active series + slider min/max.
 *   - AC-D-6: DefacePill text reflects active series's deface_method.
 *   - AC-D-9: legacy fallback (manifest 404) — exercised in
 *     StudyDetailPanel-level test, not here.
 *   - AC-D-11: all-quarantined manifest -> ModalityFallback variant
 *     "unavailable-quarantined".
 *
 * The slider drag debounce (AC-D-3) and screen-reader announce
 * (AC-D-5) are timing-sensitive and are covered by Playwright e2e
 * (post-D-13 — Phase 1.5 deferred).
 */

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import {
  FrameSliderViewer,
  DefacePill,
  type PreviewManifest,
} from "@/components/preview/FrameSliderViewer";

function makeManifest(
  overrides: Partial<PreviewManifest> = {},
): PreviewManifest {
  return {
    pseudo_study_uid: "RV-STD-abc123",
    pipeline_version: "0.1.0",
    series: [
      {
        pseudo_series_uid: "RV-SER-1",
        series_num: 1,
        modality: "CT",
        body_part: "HEAD",
        frame_count: 52,
        preview_status: "generated",
        deface_decision: "required",
        deface_method: "afni_refacer_v0_7",
      },
      {
        pseudo_series_uid: "RV-SER-2",
        series_num: 2,
        modality: "CT",
        body_part: "HEAD",
        frame_count: 48,
        preview_status: "generated",
        deface_decision: "required",
        deface_method: "afni_refacer_v0_7",
      },
    ],
    ...overrides,
  };
}

describe("FrameSliderViewer (AC-D-1..AC-D-12)", () => {
  it("renders one chip per series with first generated active", () => {
    render(
      <FrameSliderViewer
        studyUid="RV-STD-abc123"
        manifest={makeManifest()}
        locale="en"
      />,
    );
    const chips = screen.getAllByTestId("series-chip");
    expect(chips.length).toBe(2);
    expect(chips[0]).toHaveAttribute("data-state", "active");
    expect(chips[1]).toHaveAttribute("data-state", "inactive");
    expect(chips[0]).toHaveAttribute("aria-selected", "true");
  });

  it("switches active series on chip click", () => {
    render(
      <FrameSliderViewer
        studyUid="RV-STD-abc123"
        manifest={makeManifest()}
        locale="en"
      />,
    );
    const chips = screen.getAllByTestId("series-chip");
    fireEvent.click(chips[1]);
    const updated = screen.getAllByTestId("series-chip");
    expect(updated[0]).toHaveAttribute("data-state", "inactive");
    expect(updated[1]).toHaveAttribute("data-state", "active");
  });

  it("renders DefacePill with AFNI text when deface_method=afni_refacer_v0_7", () => {
    render(
      <FrameSliderViewer
        studyUid="RV-STD-abc123"
        manifest={makeManifest()}
        locale="en"
      />,
    );
    const pill = screen.getByTestId("deface-pill");
    expect(pill).toHaveAttribute("data-variant", "amber");
    expect(pill.textContent).toMatch(/AFNI defaced/);
  });

  it("renders DefacePill with no defacing required for chest CT", () => {
    const manifest = makeManifest({
      series: [
        {
          pseudo_series_uid: "RV-SER-c",
          series_num: 1,
          modality: "CT",
          body_part: "CHEST",
          frame_count: 10,
          preview_status: "generated",
          deface_decision: "not_required",
          deface_method: "none_required",
        },
      ],
    });
    render(
      <FrameSliderViewer
        studyUid="RV-STD-c"
        manifest={manifest}
        locale="en"
      />,
    );
    const pill = screen.getByTestId("deface-pill");
    expect(pill).toHaveAttribute("data-variant", "stone");
  });

  it("falls back to ModalityFallback when every series is quarantined", () => {
    const manifest = makeManifest({
      series: [
        {
          ...makeManifest().series[0],
          preview_status: "quarantined",
          deface_method: "deface_failed_runtime",
          frame_count: 0,
        },
        {
          ...makeManifest().series[1],
          preview_status: "quarantined",
          deface_method: "deface_failed_runtime",
          frame_count: 0,
        },
      ],
    });
    render(
      <FrameSliderViewer
        studyUid="RV-STD-q"
        manifest={manifest}
        locale="en"
      />,
    );
    const fallback = screen.getByTestId("modality-fallback");
    expect(fallback).toHaveAttribute("data-variant", "unavailable-quarantined");
  });

  it("disables chip clicks for quarantined series in mixed state", () => {
    const manifest = makeManifest({
      series: [
        makeManifest().series[0],
        {
          ...makeManifest().series[1],
          preview_status: "quarantined",
          deface_method: "deface_failed_runtime",
          frame_count: 0,
        },
      ],
    });
    render(
      <FrameSliderViewer
        studyUid="RV-STD-mix"
        manifest={manifest}
        locale="en"
      />,
    );
    const chips = screen.getAllByTestId("series-chip");
    expect(chips[1]).toBeDisabled();
    expect(chips[1]).toHaveAttribute("data-state", "disabled");
    fireEvent.click(chips[1]);
    // Click is a no-op — first chip is still active.
    const after = screen.getAllByTestId("series-chip");
    expect(after[0]).toHaveAttribute("data-state", "active");
  });

  it("renders dropdown when 6+ series", () => {
    const series = Array.from({ length: 6 }).map((_, i) => ({
      pseudo_series_uid: `RV-SER-${i + 1}`,
      series_num: i + 1,
      modality: "CT",
      body_part: "HEAD" as string | null,
      frame_count: 30,
      preview_status: "generated" as const,
      deface_decision: "required" as const,
      deface_method: "afni_refacer_v0_7" as string,
    }));
    render(
      <FrameSliderViewer
        studyUid="RV-STD-many"
        manifest={makeManifest({ series })}
        locale="en"
      />,
    );
    expect(screen.getByTestId("series-selector")).toBeInTheDocument();
  });
});

describe("DefacePill (design-spec §7.2 variants)", () => {
  it("returns null when method is null", () => {
    const { container } = render(
      <DefacePill method={null} modality="CT" locale="en" />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders rose for deface_failed_runtime", () => {
    render(
      <DefacePill
        method="deface_failed_runtime"
        modality="CT"
        locale="en"
      />,
    );
    expect(screen.getByTestId("deface-pill")).toHaveAttribute(
      "data-variant",
      "rose",
    );
  });

  it("renders Korean text under locale=ko", () => {
    render(<DefacePill method="afni_refacer_v0_7" modality="CT" locale="ko" />);
    expect(screen.getByTestId("deface-pill").textContent).toMatch(
      /AFNI 얼굴 제거됨/,
    );
  });
});
