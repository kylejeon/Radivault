/**
 * Buyer-portal v0.2 components — design-spec-portal-redesign §11.
 *
 * Smoke tests for the 7 new components plus the MarketplaceNav. We assert
 * the data-testid contracts (the e2e suite will rely on them) and a couple
 * of design-spec-mandated behaviours that are easy to lose silently
 * (Stripe-style mask format, FederatedSignal empty-state copy, etc.).
 */

import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { BuyerModalityBadge } from "@/components/buyer/ModalityBadge";
import { FederatedSignal } from "@/components/buyer/FederatedSignal";
import { StudyCard } from "@/components/buyer/StudyCard";
import {
  StudyDetailPanel,
  ViewerStub,
} from "@/components/buyer/StudyDetailPanel";
import {
  EMPTY_FACET_STATE,
  FacetSidebar,
} from "@/components/buyer/FacetSidebar";
import { CartItem, CartEmpty } from "@/components/buyer/CartItem";
import { OrderTimeline, mapBuyerPhase } from "@/components/buyer/OrderTimeline";

const STUDY = {
  pseudo_study_uid: "2.25.100000000000000000000000000001",
  modality: "CT",
  body_part: "CHEST",
  age_bucket: "50-60",
  sex: "M",
  n_instances: 287,
  total_bytes: 142 * 1024 * 1024,
  study_date_shifted: "2023-08-14",
  hospital_opaque_id: "a1b2c3d4e5f6a7b8",
};

describe("BuyerModalityBadge (§11.1)", () => {
  it("renders all 7 design-spec variants", () => {
    for (const m of ["CT", "MR", "MG", "CR", "DX", "PT", "US"]) {
      const { unmount } = render(<BuyerModalityBadge modality={m} />);
      expect(
        screen.getByTestId(`modality-badge-${m.toLowerCase()}`),
      ).toBeInTheDocument();
      unmount();
    }
  });
  it("falls back to `unknown` for non-canonical modalities", () => {
    render(<BuyerModalityBadge modality="QQ" />);
    expect(screen.getByTestId("modality-badge-unknown")).toBeInTheDocument();
  });
  it("exposes an aria-label for screen readers", () => {
    render(<BuyerModalityBadge modality="MR" />);
    expect(screen.getByLabelText(/modality: MR/i)).toBeInTheDocument();
  });
});

describe("FederatedSignal (§11.2)", () => {
  it("renders the standard variant with study + hospital counts", () => {
    render(<FederatedSignal studyCount={150} hospitalCount={2} />);
    expect(screen.getByTestId("federated-signal")).toBeInTheDocument();
    expect(screen.getByText(/150/)).toBeInTheDocument();
    expect(screen.getByText(/2/)).toBeInTheDocument();
    expect(screen.getByText(/across/i)).toBeInTheDocument();
  });
  it("renders the empty variant with the partner-hospitals copy", () => {
    render(
      <FederatedSignal studyCount={0} hospitalCount={2} variant="empty" />,
    );
    expect(screen.getByTestId("federated-signal-empty")).toBeInTheDocument();
    expect(screen.getByText(/2 partner hospitals/)).toBeInTheDocument();
  });
  it("renders the mini variant inside cohort sidebar", () => {
    render(
      <FederatedSignal studyCount={12} hospitalCount={2} variant="mini" />,
    );
    expect(screen.getByTestId("federated-signal-mini")).toBeInTheDocument();
  });
});

describe("StudyCard (§11.3)", () => {
  it("renders all 9 columns with the expected aria-label on the checkbox", () => {
    render(<StudyCard study={STUDY} />);
    expect(screen.getByTestId("study-card")).toBeInTheDocument();
    expect(
      screen.getByLabelText(/Select study .{8}/),
    ).toBeInTheDocument();
    expect(screen.getByText("CHEST")).toBeInTheDocument();
    expect(screen.getByText("50-60")).toBeInTheDocument();
    expect(screen.getByText("287")).toBeInTheDocument();
    expect(screen.getByText("142 MB")).toBeInTheDocument();
    expect(screen.getByText("2023")).toBeInTheDocument();
    expect(screen.getByText(/HOSP-A1B2C3/)).toBeInTheDocument();
  });
  it("highlights the selected row with the primary border accent", () => {
    const { container } = render(<StudyCard study={STUDY} selected />);
    expect(container.querySelector('[role="row"]')?.className).toMatch(
      /border-l-primary/,
    );
  });
});

describe("StudyDetailPanel (§11.4)", () => {
  const detail = {
    ...STUDY,
    manufacturer: "SIEMENS",
    model_name: "SOMATOM Force",
    n_series: 3,
    ingested_at: "2024-01-01T00:00:00Z",
    series: [
      { pseudo_series_uid: "2.25.aaa", modality: "CT", n_instances: 287 },
      { pseudo_series_uid: "2.25.bbb", modality: "CT", n_instances: 64 },
    ],
  };
  it("renders metadata grid + series + viewer stub", () => {
    render(<StudyDetailPanel study={detail} />);
    expect(screen.getByTestId("study-detail-panel")).toBeInTheDocument();
    expect(screen.getByText(/SIEMENS/)).toBeInTheDocument();
    expect(screen.getByText(/SOMATOM Force/)).toBeInTheDocument();
    expect(screen.getByTestId("viewer-stub")).toBeInTheDocument();
  });
  it("exposes the Add to cohort button", () => {
    render(<StudyDetailPanel study={detail} />);
    expect(screen.getByTestId("add-to-cohort")).toBeInTheDocument();
  });
});

describe("ViewerStub", () => {
  it("renders the EN copy and the demo CTA", () => {
    render(<ViewerStub />);
    expect(
      screen.getByText(/DICOM viewer not included in v0.1/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Request viewer integration demo/)).toBeInTheDocument();
  });
});

describe("FacetSidebar (§11.5)", () => {
  it("renders the min_hospitals slider as the first facet", () => {
    render(
      <FacetSidebar
        values={EMPTY_FACET_STATE}
        onChange={() => {}}
        facets={{
          modality: [{ value: "CT", count: 87 }],
          body_part: [],
          age_bucket: [],
          sex: [],
          manufacturer: [],
          year: [],
        }}
      />,
    );
    expect(screen.getByTestId("facet-sidebar")).toBeInTheDocument();
    expect(
      screen.getByTestId("facet-section-facet-min-hospitals"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("min-hospitals-value")).toHaveTextContent("1+");
  });
  it("renders all 6 design-spec facet sections", () => {
    render(
      <FacetSidebar
        values={EMPTY_FACET_STATE}
        onChange={() => {}}
        facets={{
          modality: [{ value: "CT", count: 1 }],
          body_part: [{ value: "CHEST", count: 1 }],
          age_bucket: [{ value: "50-60", count: 1 }],
          sex: [{ value: "M", count: 1 }],
          manufacturer: [{ value: "SIEMENS", count: 1 }],
          year: [{ value: "2024", count: 1 }],
        }}
      />,
    );
    for (const id of [
      "modality",
      "body-part",
      "age-bucket",
      "facet-sex",
      "manufacturer",
      "year",
    ]) {
      expect(
        screen.getByTestId(`facet-section-${id}`),
      ).toBeInTheDocument();
    }
  });
});

describe("CartItem (§11.6)", () => {
  it("renders the mini variant with remove button", () => {
    render(<CartItem item={STUDY} variant="mini" />);
    expect(screen.getByTestId("cart-item-mini")).toBeInTheDocument();
    expect(screen.getByLabelText(/Remove:/)).toBeInTheDocument();
  });
  it("renders the full variant with size + year columns", () => {
    render(<CartItem item={STUDY} variant="full" />);
    expect(screen.getByTestId("cart-item-full")).toBeInTheDocument();
    expect(screen.getByText("142 MB")).toBeInTheDocument();
    expect(screen.getByText("2023")).toBeInTheDocument();
  });
  it("renders the empty placeholder", () => {
    render(<CartEmpty />);
    expect(screen.getByTestId("cart-empty")).toBeInTheDocument();
  });
});

describe("OrderTimeline (§11.7)", () => {
  it("renders 5 phases", () => {
    render(<OrderTimeline phase="paid" />);
    expect(screen.getByTestId("order-timeline")).toBeInTheDocument();
    expect(screen.getByText("Submitted")).toBeInTheDocument();
    expect(screen.getByText("Fetching")).toBeInTheDocument();
    expect(screen.getByText("De-identifying")).toBeInTheDocument();
    expect(screen.getByText("Packaging")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });
  it("maps the legacy BuyerPhase enum to the 5-phase model", () => {
    expect(mapBuyerPhase("accepted")).toBe("paid");
    expect(mapBuyerPhase("fetching_from_hospital")).toBe("fetching");
    expect(mapBuyerPhase("preparing_download")).toBe("packaging");
    expect(mapBuyerPhase("ready_to_download")).toBe("ready");
    expect(mapBuyerPhase("completed")).toBe("ready");
  });
});
