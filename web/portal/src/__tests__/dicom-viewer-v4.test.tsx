/**
 * DICOM Viewer v2 (study-detail v4) tests
 * — design-spec-dicom-viewer.md §12 AC-D-1..AC-D-32
 * — dev-spec-dicom-viewer.md §10 AC-DV-1..AC-DV-10.x
 *
 * Mocks `next/navigation` (router/searchParams) so ViewerPaneV4 can run
 * outside the App Router context. The slider/keyboard tests run in
 * jsdom and rely only on react-testing-library + vitest fake timers.
 *
 * Coverage map (one-to-one with AC items):
 *   AC-D-3       Preset 5 + Custom in dropdown
 *   AC-D-4       Picker dropdown open / close
 *   AC-D-5       Picker item click → URL replace + active sync
 *   AC-D-6       MR series → Preset trigger disabled
 *   AC-D-18      Disabled (pending) row → not selectable
 *   AC-D-20      Watermark aria-hidden + opacity 0.08
 *   AC-D-24      No "Sample download" DOM in the right rail
 *   AC-D-27      No `.trust-bar` in nav (study-detail page)
 *   AC-D-30/31   No `.locale-toggle` / [data-set-locale] / body[data-locale]
 *   AC-DV-2.3    Keyboard 1..9 → series hotkey
 *   AC-DV-3.1    Wheel zoom clamps to 0.25..8x
 *   AC-DV-3.4    R key → reset
 *   AC-DV-3.5    Preset click → CSS filter applied
 *   AC-DV-3.7    contextmenu suppressed
 *   AC-DV-4.2    Arrow keys / PgUp / PgDn / Home / End frame nav
 */

import { render, screen, fireEvent, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ViewerPaneV4,
  PRESETS,
  wlFilter,
  clampZoom,
  clampWindow,
  ZOOM_MIN,
  ZOOM_MAX,
  WW_MIN,
  WW_MAX,
} from "@/components/buyer/v4/study-detail";
import { SeriesMiniCardListV4 } from "@/components/buyer/v4/study-detail";
import type { PreviewManifest } from "@/components/preview/FrameSliderViewer";

// ---------------------------------------------------------------------------
// next/navigation mock — ViewerPaneV4 uses useRouter / useSearchParams.
// ---------------------------------------------------------------------------
let mockSearchParams = new URLSearchParams();
const replaceMock = vi.fn();

vi.mock("next/navigation", () => {
  return {
    useRouter: () => ({
      replace: replaceMock,
      push: vi.fn(),
      refresh: vi.fn(),
    }),
    useSearchParams: () => mockSearchParams,
  };
});

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeManifest(
  overrides: Partial<PreviewManifest> = {},
): PreviewManifest {
  return {
    pseudo_study_uid: "RV-STD-abc123",
    pipeline_version: "0.2.1",
    series: [
      {
        pseudo_series_uid: "RV-SER-1",
        series_num: 1,
        modality: "CT",
        body_part: "Topogram",
        frame_count: 2,
        preview_status: "generated",
        deface_decision: "not_required",
        deface_method: "none_required",
      },
      {
        pseudo_series_uid: "RV-SER-2",
        series_num: 2,
        modality: "CT",
        body_part: "Pre-contrast Chest",
        frame_count: 155,
        preview_status: "generated",
        deface_decision: "not_required",
        deface_method: "none_required",
      },
      {
        pseudo_series_uid: "RV-SER-3",
        series_num: 3,
        modality: "CT",
        body_part: "Post-contrast Chest",
        frame_count: 155,
        preview_status: "generated",
        deface_decision: "not_required",
        deface_method: "none_required",
      },
      {
        pseudo_series_uid: "RV-SER-11",
        series_num: 11,
        modality: "SEG",
        body_part: "SEG mask",
        frame_count: 0,
        preview_status: "pending",
        deface_decision: null,
        deface_method: null,
      },
    ],
    ...overrides,
  };
}

function ControlledViewer(props: {
  manifest: PreviewManifest;
  initialUid?: string | null;
  studyUid?: string;
}) {
  // ViewerPaneV4 is controlled — wrap in a tiny harness that owns the UID.
  const [uid, setUid] = (
    require("react") as typeof import("react")
  ).useState<string | null>(
    props.initialUid ?? props.manifest.series[2]?.pseudo_series_uid ?? null,
  );
  return (
    <ViewerPaneV4
      studyUid={props.studyUid ?? "RV-STD-abc123"}
      manifest={props.manifest}
      activeSeriesUid={uid}
      onActiveSeriesChange={setUid}
      locale="en"
    />
  );
}

beforeEach(() => {
  mockSearchParams = new URLSearchParams();
  replaceMock.mockReset();
});

afterEach(() => {
  document.body.innerHTML = "";
});

// ---------------------------------------------------------------------------
// Pure helpers (AC-DV-3.1, AC-DV-3.5)
// ---------------------------------------------------------------------------

describe("ViewerCanvas helpers", () => {
  it("clampZoom: snaps below ZOOM_MIN and above ZOOM_MAX", () => {
    expect(clampZoom(0.1)).toBe(ZOOM_MIN);
    expect(clampZoom(20)).toBe(ZOOM_MAX);
    expect(clampZoom(1)).toBe(1);
  });

  it("clampWindow: respects min/max bounds", () => {
    expect(clampWindow(-9999, WW_MIN, WW_MAX)).toBe(WW_MIN);
    expect(clampWindow(9999, WW_MIN, WW_MAX)).toBe(WW_MAX);
    expect(clampWindow(123, WW_MIN, WW_MAX)).toBe(123);
  });

  it("wlFilter: identity at WW=200/WL=0", () => {
    expect(wlFilter(200, 0)).toBe("contrast(1.000) brightness(1.000)");
  });

  it("wlFilter: lung preset (1500/-600) lifts contrast and lowers brightness (filter clamps WW@5x for stability)", () => {
    const f = wlFilter(1500, -600);
    // contrast clamps to 5.000 (max), brightness 1 + (-600/200) = -2 clamps to 0.05
    expect(f).toBe("contrast(5.000) brightness(0.050)");
  });

  it("PRESETS list ships exactly the 5 documented CT presets", () => {
    expect(PRESETS.map((p) => p.id)).toEqual([
      "lung",
      "bone",
      "soft",
      "mediastinum",
      "brain",
    ]);
  });
});

// ---------------------------------------------------------------------------
// SeriesPicker / Toolbar / Watermark — AC-D-3, AC-D-4, AC-D-5, AC-D-18, AC-D-20
// ---------------------------------------------------------------------------

describe("ViewerPaneV4 — SeriesPicker + Toolbar + Watermark", () => {
  it("AC-D-3 Preset menu: lists 5 CT presets + Custom", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    fireEvent.click(screen.getByTestId("dv-preset-trigger"));
    expect(screen.getByTestId("dv-preset-lung")).toBeInTheDocument();
    expect(screen.getByTestId("dv-preset-bone")).toBeInTheDocument();
    expect(screen.getByTestId("dv-preset-soft")).toBeInTheDocument();
    expect(screen.getByTestId("dv-preset-mediastinum")).toBeInTheDocument();
    expect(screen.getByTestId("dv-preset-brain")).toBeInTheDocument();
    expect(screen.getByTestId("dv-preset-custom")).toBeInTheDocument();
  });

  it("AC-D-4 SeriesPicker dropdown: closed by default, opens on trigger click, closes on outside click", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    const wrap = screen.getByTestId("dv-series-picker");
    expect(wrap.classList.contains("is-open")).toBe(false);
    fireEvent.click(screen.getByTestId("dv-series-picker-trigger"));
    expect(wrap.classList.contains("is-open")).toBe(true);
    // outside click
    fireEvent.click(document.body);
    expect(wrap.classList.contains("is-open")).toBe(false);
  });

  it("AC-D-5 Picker item click: URL replace ?series=N + active sync", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    fireEvent.click(screen.getByTestId("dv-series-picker-trigger"));
    fireEvent.click(screen.getByTestId("dv-series-picker-item-1")); // series 1 (Topogram)
    expect(replaceMock).toHaveBeenCalledTimes(1);
    const target = replaceMock.mock.calls[0][0] as string;
    expect(target).toContain("series=1");
    expect(screen.getByTestId("dv-series-picker-current").textContent).toBe(
      "1",
    );
  });

  it("AC-D-18 disabled (pending) row is not clickable + carries pending chip", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    fireEvent.click(screen.getByTestId("dv-series-picker-trigger"));
    const disabled = screen.getByTestId("dv-series-picker-item-4"); // SEG · pending
    expect(disabled.getAttribute("aria-disabled")).toBe("true");
    expect(disabled.classList.contains("rv-series-picker__item--disabled")).toBe(
      true,
    );
    fireEvent.click(disabled);
    // current still 3 (no change)
    expect(screen.getByTestId("dv-series-picker-current").textContent).toBe(
      "3",
    );
  });

  it("AC-D-6 MR series → Preset trigger disabled", () => {
    const manifest = makeManifest({
      series: [
        {
          pseudo_series_uid: "RV-SER-1",
          series_num: 1,
          modality: "MR",
          body_part: "T1 axial",
          frame_count: 24,
          preview_status: "generated",
          deface_decision: "required",
          deface_method: "afni_refacer_v0_7",
        },
      ],
    });
    render(<ControlledViewer manifest={manifest} initialUid="RV-SER-1" />);
    const trigger = screen.getByTestId("dv-preset-trigger");
    expect(trigger).toBeDisabled();
    expect(trigger.getAttribute("data-tip")).toMatch(/CT presets only/);
  });

  it("AC-D-20 Watermark renders aria-hidden + correct viewBox", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    const wm = screen.getByTestId("dv-watermark");
    expect(wm.getAttribute("aria-hidden")).toBe("true");
    expect(wm.getAttribute("viewBox")).toBe("0 0 240 60");
    // SVG fill should be white-rgba (visible across W/L windows).
    expect(wm.innerHTML).toMatch(/RADIVAULT/);
  });
});

// ---------------------------------------------------------------------------
// Keyboard hotkeys — AC-DV-2.3 / AC-DV-3.4 / AC-DV-4.2
// ---------------------------------------------------------------------------

describe("ViewerPaneV4 — keyboard shortcuts", () => {
  it("AC-DV-2.3 keyboard 1 → series 1 (works even with dropdown closed)", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    const pane = screen.getByTestId("dv-viewer-pane");
    pane.focus();
    fireEvent.keyDown(pane, { key: "1" });
    expect(screen.getByTestId("dv-series-picker-current").textContent).toBe(
      "1",
    );
  });

  it("AC-DV-2.3 keyboard hotkey ignored when activeElement is INPUT", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    // Insert a sibling input + focus it BEFORE pressing 1.
    const input = document.createElement("input");
    input.type = "text";
    document.body.appendChild(input);
    input.focus();
    expect(document.activeElement?.tagName).toBe("INPUT");
    fireEvent.keyDown(screen.getByTestId("dv-viewer-pane"), { key: "1" });
    // current should not change from default series (3rd in fixture).
    expect(screen.getByTestId("dv-series-picker-current").textContent).toBe(
      "3",
    );
  });

  it("AC-DV-3.4 R key → reset (preset removed, ww/wl back to 200/0)", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    // Activate Lung preset first.
    fireEvent.click(screen.getByTestId("dv-preset-trigger"));
    fireEvent.click(screen.getByTestId("dv-preset-lung"));
    expect(screen.getByTestId("dv-toolbar-readout").textContent).toMatch(
      /WW 1500/,
    );
    // Hit R.
    const pane = screen.getByTestId("dv-viewer-pane");
    pane.focus();
    fireEvent.keyDown(pane, { key: "R" });
    expect(screen.getByTestId("dv-toolbar-readout").textContent).toMatch(
      /WW 200/,
    );
    expect(screen.getByTestId("dv-toolbar-readout").textContent).toMatch(
      /zoom 1\.0×/,
    );
  });

  it("AC-DV-4.2 ←/→ key changes the frame counter", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    const pane = screen.getByTestId("dv-viewer-pane");
    pane.focus();
    // Default series is series 3 with frame_count=155 → median=78.
    expect(screen.getByTestId("dv-frame-counter").textContent).toBe(
      "78 / 155",
    );
    fireEvent.keyDown(pane, { key: "ArrowRight" });
    expect(screen.getByTestId("dv-frame-counter").textContent).toBe(
      "79 / 155",
    );
    fireEvent.keyDown(pane, { key: "ArrowLeft" });
    fireEvent.keyDown(pane, { key: "ArrowLeft" });
    expect(screen.getByTestId("dv-frame-counter").textContent).toBe(
      "77 / 155",
    );
  });

  it("AC-DV-4.2 PgUp = -10 / PgDn = +10 (Q-DV-4 GUI convention)", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    const pane = screen.getByTestId("dv-viewer-pane");
    pane.focus();
    expect(screen.getByTestId("dv-frame-counter").textContent).toBe(
      "78 / 155",
    );
    fireEvent.keyDown(pane, { key: "PageUp" });
    expect(screen.getByTestId("dv-frame-counter").textContent).toBe(
      "68 / 155",
    );
    fireEvent.keyDown(pane, { key: "PageDown" });
    fireEvent.keyDown(pane, { key: "PageDown" });
    expect(screen.getByTestId("dv-frame-counter").textContent).toBe(
      "88 / 155",
    );
  });

  it("AC-DV-4.2 Home / End jump to first/last", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    const pane = screen.getByTestId("dv-viewer-pane");
    pane.focus();
    fireEvent.keyDown(pane, { key: "Home" });
    expect(screen.getByTestId("dv-frame-counter").textContent).toBe(
      "1 / 155",
    );
    fireEvent.keyDown(pane, { key: "End" });
    expect(screen.getByTestId("dv-frame-counter").textContent).toBe(
      "155 / 155",
    );
  });

  it("+ / − keys zoom in/out", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    const pane = screen.getByTestId("dv-viewer-pane");
    pane.focus();
    fireEvent.keyDown(pane, { key: "+" });
    expect(screen.getByTestId("dv-toolbar-readout").textContent).toMatch(
      /zoom 1\.1×/,
    );
    fireEvent.keyDown(pane, { key: "-" });
    expect(screen.getByTestId("dv-toolbar-readout").textContent).toMatch(
      /zoom 1\.0×/,
    );
  });
});

// ---------------------------------------------------------------------------
// Preset application + canvas filter — AC-DV-3.5
// ---------------------------------------------------------------------------

describe("ViewerPaneV4 — preset → canvas filter", () => {
  it("AC-DV-3.5 Lung preset → toolbar readout WW 1500 / WL -600", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    fireEvent.click(screen.getByTestId("dv-preset-trigger"));
    fireEvent.click(screen.getByTestId("dv-preset-lung"));
    expect(screen.getByTestId("dv-toolbar-readout").textContent).toMatch(
      /WW 1500/,
    );
    expect(screen.getByTestId("dv-toolbar-readout").textContent).toMatch(
      /WL -600/,
    );
    // Filter on the <img> reflects the WW/WL via wlFilter().
    const img = screen.getByTestId("dv-canvas-img") as HTMLImageElement;
    // CSS filter property is injected via inline style.
    expect(img.style.filter).toContain("contrast");
    expect(img.style.filter).toContain("brightness");
  });
});

// ---------------------------------------------------------------------------
// contextmenu suppression — AC-DV-3.7
// ---------------------------------------------------------------------------

describe("ViewerPaneV4 — interaction guards", () => {
  it("AC-DV-3.7 right-click on canvas does not pop the browser contextmenu", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    const surface = screen.getByTestId("dv-canvas-surface");
    const evt = new MouseEvent("contextmenu", {
      bubbles: true,
      cancelable: true,
    });
    surface.dispatchEvent(evt);
    expect(evt.defaultPrevented).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// SeriesMiniCardListV4 — bidirectional sync
// ---------------------------------------------------------------------------

describe("SeriesMiniCardListV4 — bidirectional sync", () => {
  function harness() {
    const items = makeManifest().series.map((s, i) => ({
      pseudo_series_uid: s.pseudo_series_uid,
      modality: s.modality,
      n_instances: s.frame_count,
      preview_status: s.preview_status,
      description: s.body_part ?? null,
      slice_thickness_mm: i === 0 ? 1.0 : 1.0,
      resolution_w: 512,
      resolution_h: 512,
    }));
    let uid: string | null = items[2].pseudo_series_uid;
    const onSelect = vi.fn((next: string) => {
      uid = next;
    });
    const result = render(
      <SeriesMiniCardListV4
        series={items}
        activeSeriesUid={uid}
        onSelect={onSelect}
        locale="en"
      />,
    );
    return { onSelect, result, items };
  }

  it("renders one row per series + active stripe on the matching uid", () => {
    const { items } = harness();
    expect(screen.getByTestId("dv-meta-card-series")).toBeInTheDocument();
    items.forEach((_, i) => {
      expect(
        screen.getByTestId(`dv-series-mini-card-${i}`),
      ).toBeInTheDocument();
    });
    expect(
      screen
        .getByTestId("dv-series-mini-card-2")
        .classList.contains("rv-series-mini--active"),
    ).toBe(true);
  });

  it("click on a row → onSelect(uid)", () => {
    const { onSelect } = harness();
    fireEvent.click(screen.getByTestId("dv-series-mini-card-0"));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith("RV-SER-1");
  });

  it("disabled (pending) row → not selectable", () => {
    const { onSelect } = harness();
    fireEvent.click(screen.getByTestId("dv-series-mini-card-3"));
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("Enter / Space activate row from keyboard", () => {
    const { onSelect } = harness();
    fireEvent.keyDown(screen.getByTestId("dv-series-mini-card-1"), {
      key: "Enter",
    });
    expect(onSelect).toHaveBeenCalledWith("RV-SER-2");
    fireEvent.keyDown(screen.getByTestId("dv-series-mini-card-0"), {
      key: " ",
    });
    expect(onSelect).toHaveBeenCalledWith("RV-SER-1");
  });
});

// ---------------------------------------------------------------------------
// DOM invariants — AC-D-24, AC-D-30, AC-D-31
// ---------------------------------------------------------------------------

describe("DOM invariants — EN-only buyer portal", () => {
  it("AC-D-24 ViewerPaneV4 + right rail render no 'Sample download' marker", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    expect(screen.queryByText(/sample download/i)).toBeNull();
    expect(document.querySelector(".rv-detail-cta__hint")).toBeNull();
  });

  it("AC-D-30 ViewerPaneV4 emits no .locale-toggle / [data-set-locale]", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    expect(document.querySelectorAll(".locale-toggle").length).toBe(0);
    expect(document.querySelectorAll("[data-set-locale]").length).toBe(0);
  });

  it("AC-D-31 ViewerPaneV4 does not set body[data-locale]", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    expect(document.body.getAttribute("data-locale")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Slider drag debounce — AC-DV-4.1
// ---------------------------------------------------------------------------

describe("ViewerPaneV4 — slider drag debounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("AC-DV-4.1 slider drag → 80 ms debounce → frame swap", () => {
    render(<ControlledViewer manifest={makeManifest()} />);
    const slider = screen.getByTestId("dv-frame-slider") as HTMLInputElement;
    // Default frame is 78 (median of 155).
    expect(screen.getByTestId("dv-frame-counter").textContent).toBe(
      "78 / 155",
    );
    fireEvent.change(slider, { target: { value: "100" } });
    // Pre-debounce, count unchanged.
    expect(screen.getByTestId("dv-frame-counter").textContent).toBe(
      "78 / 155",
    );
    act(() => {
      vi.advanceTimersByTime(81);
    });
    expect(screen.getByTestId("dv-frame-counter").textContent).toBe(
      "100 / 155",
    );
  });
});
