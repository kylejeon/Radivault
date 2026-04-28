/**
 * Unit smoke tests for the study-detail v3 components.
 *
 * Covers the testid contracts the e2e suite + parent panel rely on, plus a
 * couple of behaviours that are easy to lose silently:
 *   - Missing-field cells render "—" with the `--missing` modifier (so we can
 *     never silently render fake data).
 *   - ComplianceCollapse defaults to closed and toggles open via aria-expanded.
 *   - DeIDStepper renders all 5 hard-coded stages even when no per-stage hash
 *     is supplied (the chain visual must show the full pipeline shape).
 *   - LongitudinalTimeline shows the placeholder when no steps are wired.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  ComplianceCollapse,
  DeIDStepper,
  LongitudinalTimeline,
  MetaCard,
  QualityMetricsCard,
  SeriesMiniCardList,
  StudyDetailSubBar,
  ViewerPaneV3,
} from "@/components/buyer/v3/study-detail";

describe("QualityMetricsCard", () => {
  it("renders all 4 cells and shows --missing modifier for unwired fields", () => {
    render(
      <QualityMetricsCard
        imageCount={312}
        seriesCount={3}
        sliceThicknessMm={null}
        resolutionWidth={null}
        resolutionHeight={null}
        completenessPct={null}
      />,
    );
    expect(screen.getByTestId("quality-metrics-card")).toBeInTheDocument();
    const imageCell = screen.getByTestId("quality-metrics-image-count");
    expect(imageCell).toHaveTextContent("312");
    expect(imageCell.className).not.toMatch(/--missing/);
    const sliceCell = screen.getByTestId("quality-metrics-slice-thickness");
    expect(sliceCell).toHaveTextContent("—");
    expect(sliceCell.className).toMatch(/--missing/);
    const resCell = screen.getByTestId("quality-metrics-resolution");
    expect(resCell.className).toMatch(/--missing/);
    const compCell = screen.getByTestId("quality-metrics-completeness");
    expect(compCell.className).toMatch(/--missing/);
    expect(compCell.className).toMatch(/--score/);
  });

  it("renders KO copy when locale='ko'", () => {
    render(
      <QualityMetricsCard
        imageCount={10}
        seriesCount={1}
        sliceThicknessMm={null}
        completenessPct={null}
        locale="ko"
      />,
    );
    expect(screen.getByText("이미지 수")).toBeInTheDocument();
    expect(screen.getByText("슬라이스 두께")).toBeInTheDocument();
  });
});

describe("MetaCard", () => {
  it("renders all rows with --missing modifier on null values", () => {
    render(
      <MetaCard
        title="Patient"
        slug="patient"
        rows={[
          { key: "id", label: "Pseudo ID", value: "PT-7392-A" },
          { key: "sex", label: "Sex", value: null },
          { key: "age", label: "Age", value: undefined },
          { key: "consent", label: "Consent", value: "" },
        ]}
      />,
    );
    expect(screen.getByTestId("meta-card-patient")).toBeInTheDocument();
    const sexRow = screen.getByTestId("meta-card-patient-row-sex");
    expect(sexRow.querySelector(".rv-detail-meta-row__v")?.className).toMatch(
      /--missing/,
    );
    const idRow = screen.getByTestId("meta-card-patient-row-id");
    expect(idRow.querySelector(".rv-detail-meta-row__v")?.className).not.toMatch(
      /--missing/,
    );
  });
});

describe("SeriesMiniCardList", () => {
  it("renders one mini-row per series with fallback title", () => {
    render(
      <SeriesMiniCardList
        series={[
          { pseudo_series_uid: "2.25.aaa", modality: "CT", n_instances: 287 },
          { pseudo_series_uid: "2.25.bbb", modality: "CT", n_instances: 64 },
        ]}
      />,
    );
    expect(screen.getByTestId("meta-card-series")).toBeInTheDocument();
    expect(screen.getByTestId("series-mini-card-0")).toBeInTheDocument();
    expect(screen.getByTestId("series-mini-card-1")).toBeInTheDocument();
    expect(screen.getByText(/Series 1/)).toBeInTheDocument();
  });

  it("shows empty placeholder when series list is empty", () => {
    render(<SeriesMiniCardList series={[]} />);
    expect(screen.getByTestId("meta-card-series-empty")).toBeInTheDocument();
  });
});

describe("LongitudinalTimeline", () => {
  it("renders placeholder when no steps wired (default state today)", () => {
    render(<LongitudinalTimeline patientPseudoId="PT-XYZ" />);
    expect(screen.getByTestId("longitudinal-timeline")).toBeInTheDocument();
    expect(
      screen.getByTestId("longitudinal-timeline-placeholder"),
    ).toBeInTheDocument();
  });

  it("renders step dots when steps are supplied", () => {
    render(
      <LongitudinalTimeline
        patientPseudoId="PT-XYZ"
        steps={[
          { modality: "CT", date: "2023-06", state: "prior" },
          { modality: "CT", date: "2024-08", state: "current" },
          { modality: "MR", date: "2025-01", state: "future" },
        ]}
      />,
    );
    expect(
      screen.getByTestId("longitudinal-timeline-step-0"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("longitudinal-timeline-step-2"),
    ).toBeInTheDocument();
  });
});

describe("DeIDStepper", () => {
  it("renders all 5 stages even without per-stage data", () => {
    render(<DeIDStepper />);
    expect(screen.getByTestId("deid-stepper")).toBeInTheDocument();
    for (let i = 1; i <= 5; i++) {
      expect(screen.getByTestId(`deid-stepper-step-${i}`)).toBeInTheDocument();
    }
  });

  it("KO labels render under locale='ko'", () => {
    render(<DeIDStepper locale="ko" />);
    expect(screen.getByText(/익명화 체인/)).toBeInTheDocument();
    expect(screen.getByText(/PHI 태그 제거/)).toBeInTheDocument();
  });
});

describe("ComplianceCollapse", () => {
  it("starts closed by default and exposes aria-expanded", () => {
    render(<ComplianceCollapse />);
    const head = screen.getByTestId("compliance-collapse-head");
    expect(head).toHaveAttribute("aria-expanded", "false");
    const wrap = screen.getByTestId("compliance-collapse");
    expect(wrap.getAttribute("data-state")).toBe("closed");
  });

  it("toggles open on head click", () => {
    render(<ComplianceCollapse />);
    const head = screen.getByTestId("compliance-collapse-head");
    fireEvent.click(head);
    expect(head).toHaveAttribute("aria-expanded", "true");
    const wrap = screen.getByTestId("compliance-collapse");
    expect(wrap.getAttribute("data-state")).toBe("open");
  });

  it("renders DeIDStepper + audit-info inside the body", () => {
    render(<ComplianceCollapse defaultOpen />);
    expect(screen.getByTestId("deid-stepper")).toBeInTheDocument();
    expect(screen.getByTestId("compliance-audit-info")).toBeInTheDocument();
    // Audit fields not yet wired — anchor hash row should show "—".
    const anchorDd = screen.getByTestId("audit-anchor-hash");
    expect(anchorDd).toHaveTextContent("—");
  });
});

describe("StudyDetailSubBar", () => {
  it("renders back link, UID, modality dot when minimal props supplied", () => {
    render(
      <StudyDetailSubBar
        pseudoStudyUid="2.25.100000000000000000000000000001"
        modality="CT"
        hospitalRegionPseudo="SEOUL-A"
        kcdCode="I20.9"
      />,
    );
    expect(screen.getByTestId("study-detail-subbar")).toBeInTheDocument();
    expect(screen.getByTestId("study-detail-back-link")).toBeInTheDocument();
    expect(screen.getByTestId("study-detail-uid")).toHaveTextContent(
      "2.25.100000000000000000000000000001",
    );
    expect(screen.getByTestId("study-detail-kcd-chip")).toHaveTextContent(
      "I20.9",
    );
    // Prev/Next nav not supplied → omitted.
    expect(screen.queryByTestId("study-detail-prev")).toBeNull();
    expect(screen.queryByTestId("study-detail-next")).toBeNull();
  });
});

describe("ViewerPaneV3", () => {
  it("renders children + 4 corner overlays when supplied", () => {
    render(
      <ViewerPaneV3
        topLeft="TL"
        topRight="TR"
        bottomLeft="BL"
        bottomRight="BR"
      >
        <div data-testid="viewer-child">canvas</div>
      </ViewerPaneV3>,
    );
    expect(screen.getByTestId("study-detail-viewer-pane")).toBeInTheDocument();
    expect(screen.getByTestId("viewer-child")).toBeInTheDocument();
    expect(screen.getByTestId("viewer-overlay-tl")).toHaveTextContent("TL");
    expect(screen.getByTestId("viewer-overlay-tr")).toHaveTextContent("TR");
    expect(screen.getByTestId("viewer-overlay-bl")).toHaveTextContent("BL");
    expect(screen.getByTestId("viewer-overlay-br")).toHaveTextContent("BR");
  });

  it("renders SaMD disclaimer at the bottom in EN by default", () => {
    render(
      <ViewerPaneV3>
        <div />
      </ViewerPaneV3>,
    );
    expect(screen.getByText(/Display only/i)).toBeInTheDocument();
  });
});
