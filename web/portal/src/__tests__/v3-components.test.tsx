/**
 * buyer-search-v3 — vitest smoke for the 7 new v3 components.
 *
 * Focuses on the data-testid contracts the e2e + qa specs rely on:
 *   - hospital-badge / hospital-badge-dot
 *   - modality-dot
 *   - kcd-autocomplete-input
 *   - age-min-input / age-max-input / age-min-slider / age-max-slider
 *   - v3-result-table / v3-row / v3-row-view
 *   - v3-trust-bar / v3-pipa-note
 */

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AgeRangeInput } from "@/components/buyer/v3/AgeRangeInput";
import { HospitalBadge } from "@/components/buyer/v3/HospitalBadge";
import { KCDAutocomplete } from "@/components/buyer/v3/KCDAutocomplete";
import { ModalityDot } from "@/components/buyer/v3/ModalityDot";
import {
  ResultTable,
  type ResultTableItem,
} from "@/components/buyer/v3/ResultTable";
import { PIPATrustNote, TrustBar } from "@/components/buyer/v3/TrustBar";

describe("v3 — HospitalBadge", () => {
  it("renders region in badge variant", () => {
    render(<HospitalBadge regionPseudo="SEOUL-A" />);
    const el = screen.getByTestId("hospital-badge");
    expect(el).toHaveTextContent("SEOUL-A");
    expect(el.className).toMatch(/seoul/);
  });

  it("renders dot variant for table stripe", () => {
    render(<HospitalBadge regionPseudo="BUSAN-B" variant="dot" />);
    const dot = screen.getByTestId("hospital-badge-dot");
    expect(dot.className).toMatch(/busan/);
  });

  it("falls back to unknown when region is null", () => {
    render(<HospitalBadge regionPseudo={null} />);
    const el = screen.getByTestId("hospital-badge");
    expect(el.className).toMatch(/unknown/);
  });
});

describe("v3 — ModalityDot", () => {
  it("renders 6 known modality colours via class", () => {
    for (const m of ["CT", "MR", "MG", "CR", "US", "PT"] as const) {
      const { unmount } = render(<ModalityDot modality={m} />);
      const dot = screen
        .getAllByTestId("modality-dot")[0]
        .querySelector("span[aria-hidden]");
      expect(dot?.className).toContain(`rv-mod-dot--${m.toLowerCase()}`);
      unmount();
    }
  });

  it("falls back to unknown for novel modality", () => {
    render(<ModalityDot modality="OT" />);
    const dot = screen.getByTestId("modality-dot").querySelector("span[aria-hidden]");
    expect(dot?.className).toContain("rv-mod-dot--unknown");
  });
});

describe("v3 — AgeRangeInput", () => {
  it("calls onChange after blur with clamped values", () => {
    const onChange = vi.fn();
    render(
      <AgeRangeInput valueMin={20} valueMax={60} onChange={onChange} />,
    );
    const minInput = screen.getByTestId("age-min-input") as HTMLInputElement;
    fireEvent.change(minInput, { target: { value: "35" } });
    fireEvent.blur(minInput);
    expect(onChange).toHaveBeenCalledWith(35, 60);
  });

  it("swaps when min > max on blur", () => {
    const onChange = vi.fn();
    render(
      <AgeRangeInput valueMin={20} valueMax={60} onChange={onChange} />,
    );
    const minInput = screen.getByTestId("age-min-input") as HTMLInputElement;
    fireEvent.change(minInput, { target: { value: "70" } });
    fireEvent.blur(minInput);
    // 70 > 60 → swap to (60, 70).
    expect(onChange).toHaveBeenCalledWith(60, 70);
  });

  it("clamps below 0", () => {
    const onChange = vi.fn();
    render(
      <AgeRangeInput valueMin={20} valueMax={60} onChange={onChange} />,
    );
    const minInput = screen.getByTestId("age-min-input") as HTMLInputElement;
    fireEvent.change(minInput, { target: { value: "-5" } });
    fireEvent.blur(minInput);
    expect(onChange).toHaveBeenCalledWith(0, 60);
  });
});

describe("v3 — KCDAutocomplete", () => {
  it("renders the input + ARIA combobox", () => {
    render(
      <KCDAutocomplete value="" onChange={() => {}} onSelect={() => {}} />,
    );
    const input = screen.getByTestId("kcd-autocomplete-input");
    expect(input).toHaveAttribute("role", "combobox");
  });
});

describe("v3 — ResultTable", () => {
  const ROW: ResultTableItem = {
    pseudo_study_uid: "1.2.840.HOSP1.7392",
    modality: "CT",
    body_part: "CHEST",
    sex: "F",
    patient_age: 52,
    age_bucket: "50-60",
    study_date_shifted: "2024-08-15",
    manufacturer: "SIEMENS",
    model_name: "SOMATOM Drive",
    n_instances: 312,
    n_series: 3,
    total_bytes: 502267904,
    hospital_region_pseudo: "SEOUL-A",
    hospital_opaque_id: "opaque",
    kcd_code: "I20.9",
    kcd_label_ko: "협심증, 상세불명",
    kcd_label_en: "Angina pectoris, unspecified",
  };

  it("renders the row with all 13 data cells via testids", () => {
    render(
      <ResultTable
        items={[ROW]}
        sortKey="examdate"
        sortDir="desc"
        onSort={() => {}}
      />,
    );
    expect(screen.getByTestId("v3-result-table")).toBeInTheDocument();
    const row = screen.getByTestId("v3-row");
    expect(row).toHaveAttribute("data-uid", ROW.pseudo_study_uid);
    expect(row).toHaveTextContent("SEOUL-A");
    expect(row).toHaveTextContent("2024-08-15");
    expect(row).toHaveTextContent("CT");
    expect(row).toHaveTextContent("CHEST");
    expect(row).toHaveTextContent("I20.9");
    expect(row).toHaveTextContent("Angina pectoris, unspecified");
    expect(row).toHaveTextContent("F");
    expect(row).toHaveTextContent("52");
    expect(row).toHaveTextContent("SIEMENS");
    expect(row).toHaveTextContent("SOMATOM Drive");
    // n_series·n_instances 3·312
    expect(row).toHaveTextContent("3·312");
    // size in MB
    expect(row).toHaveTextContent(/MB/);
    // UID tail …7392
    expect(row).toHaveTextContent("…7392");
    // View CTA
    expect(screen.getByTestId("v3-row-view")).toHaveAttribute(
      "href",
      expect.stringContaining(ROW.pseudo_study_uid),
    );
  });

  it("calls onSort with toggled direction", () => {
    const onSort = vi.fn();
    render(
      <ResultTable
        items={[ROW]}
        sortKey="examdate"
        sortDir="desc"
        onSort={onSort}
      />,
    );
    const dateHeader = document.querySelector('[data-sort="examdate"]') as HTMLElement;
    fireEvent.click(dateHeader);
    expect(onSort).toHaveBeenCalledWith("examdate", "asc");
  });
});

describe("v3 — Trust", () => {
  it("renders TrustBar copy in EN", () => {
    render(<TrustBar locale="en" />);
    expect(screen.getByTestId("v3-trust-bar")).toHaveTextContent(
      "PIPA §28-8",
    );
  });

  it("renders TrustBar copy in KO", () => {
    render(<TrustBar locale="ko" />);
    expect(screen.getByTestId("v3-trust-bar")).toHaveTextContent(
      "개인정보보호법",
    );
  });

  it("renders the PIPA note with production policy header", () => {
    render(<PIPATrustNote locale="en" />);
    expect(screen.getByTestId("v3-pipa-note")).toHaveTextContent(
      /Production policy/i,
    );
  });
});
