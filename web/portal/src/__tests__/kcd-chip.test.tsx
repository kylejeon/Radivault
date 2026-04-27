/**
 * text-search-description Phase 1.5 — vitest for KCDChip + PhiPendingBadge.
 *
 * Covers DA-1 ~ DA-4 (KCDChip locale prominence + tooltip + accessibility),
 * DA-8 ~ DA-10 (PhiPendingBadge cell + detail variants + color-blind safe
 * marker text), DA-15 (locale-driven re-render).
 */

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { KCDChip } from "@/components/buyer/v3/KCDChip";
import { PhiPendingBadge } from "@/components/buyer/v3/PhiPendingBadge";


describe("KCDChip — locale-aware prefix (FR-TS15-11, DA-1)", () => {
  it("renders ICD-10 prefix when locale=en", () => {
    render(
      <KCDChip
        code="G45.9"
        labelKo="일과성 뇌허혈 발작"
        labelEn="Transient ischaemic attack"
        locale="en"
      />,
    );
    const chip = screen.getByTestId("kcd-chip");
    expect(chip).toHaveTextContent("ICD-10 G45.9");
    expect(chip).toHaveAttribute("data-locale", "en");
  });

  it("renders KCD-8 prefix when locale=ko", () => {
    render(
      <KCDChip
        code="G45.9"
        labelKo="일과성 뇌허혈 발작"
        labelEn="Transient ischaemic attack"
        locale="ko"
      />,
    );
    const chip = screen.getByTestId("kcd-chip");
    expect(chip).toHaveTextContent("KCD-8 G45.9");
    expect(chip).toHaveAttribute("data-locale", "ko");
  });
});


describe("KCDChip — locale-aware label text (FR-TS15-11)", () => {
  it("uses English label when locale=en", () => {
    render(
      <KCDChip
        code="G45.9"
        labelKo="일과성 뇌허혈 발작"
        labelEn="Transient ischaemic attack"
        locale="en"
      />,
    );
    expect(screen.getByTestId("kcd-chip-label")).toHaveTextContent(
      "Transient ischaemic attack",
    );
  });

  it("uses Korean label when locale=ko", () => {
    render(
      <KCDChip
        code="G45.9"
        labelKo="일과성 뇌허혈 발작"
        labelEn="Transient ischaemic attack"
        locale="ko"
      />,
    );
    expect(screen.getByTestId("kcd-chip-label")).toHaveTextContent(
      "일과성 뇌허혈 발작",
    );
  });
});


describe("KCDChip — tooltip (FR-TS15-12, DA-2)", () => {
  it("renders English tooltip text", () => {
    render(
      <KCDChip code="G45.9" labelKo={null} labelEn="TIA" locale="en" />,
    );
    const tooltip = screen.getByTestId("kcd-chip-tooltip");
    expect(tooltip).toHaveTextContent(
      "Korean coded as KCD-8 (95% identical to WHO ICD-10)",
    );
  });

  it("renders Korean tooltip text", () => {
    render(
      <KCDChip code="G45.9" labelKo="TIA" labelEn={null} locale="ko" />,
    );
    const tooltip = screen.getByTestId("kcd-chip-tooltip");
    expect(tooltip).toHaveTextContent("WHO ICD-10 호환 (95% 동일)");
  });

  it("opens tooltip on hover", () => {
    render(
      <KCDChip code="G45.9" labelKo={null} labelEn="TIA" locale="en" />,
    );
    const chip = screen.getByTestId("kcd-chip");
    const tooltip = screen.getByTestId("kcd-chip-tooltip");
    expect(tooltip).toHaveAttribute("hidden");
    fireEvent.mouseEnter(chip);
    expect(tooltip).not.toHaveAttribute("hidden");
    fireEvent.mouseLeave(chip);
    expect(tooltip).toHaveAttribute("hidden");
  });

  it("opens tooltip on focus (keyboard a11y)", () => {
    render(
      <KCDChip
        code="G45.9"
        labelKo={null}
        labelEn="TIA"
        locale="en"
        onClick={() => {}}
      />,
    );
    const chip = screen.getByTestId("kcd-chip");
    fireEvent.focus(chip);
    expect(screen.getByTestId("kcd-chip-tooltip")).not.toHaveAttribute(
      "hidden",
    );
  });
});


describe("KCDChip — accessibility (DA-3, NFR-TS15-A11Y-1)", () => {
  it("aria-label varies by locale", () => {
    const { rerender } = render(
      <KCDChip code="G45.9" labelKo={null} labelEn="TIA" locale="en" />,
    );
    expect(screen.getByTestId("kcd-chip")).toHaveAttribute(
      "aria-label",
      "Diagnosis code G45.9, ICD-10 standard",
    );
    rerender(
      <KCDChip code="G45.9" labelKo="TIA" labelEn={null} locale="ko" />,
    );
    expect(screen.getByTestId("kcd-chip")).toHaveAttribute(
      "aria-label",
      "진단 코드 G45.9, KCD-8 기준",
    );
  });

  it("connects chip to tooltip via aria-describedby", () => {
    render(
      <KCDChip code="G45.9" labelKo={null} labelEn="TIA" locale="en" />,
    );
    const chip = screen.getByTestId("kcd-chip");
    const tooltip = screen.getByTestId("kcd-chip-tooltip");
    expect(chip).toHaveAttribute("aria-describedby", tooltip.id);
  });

  it("becomes a button when onClick is supplied (Kyle: facet add)", () => {
    const onClick = vi.fn();
    render(
      <KCDChip
        code="G45.9"
        labelKo={null}
        labelEn="TIA"
        locale="en"
        onClick={onClick}
      />,
    );
    const chip = screen.getByTestId("kcd-chip");
    expect(chip).toHaveAttribute("role", "button");
    expect(chip).toHaveAttribute("tabindex", "0");
    fireEvent.click(chip);
    expect(onClick).toHaveBeenCalledWith("G45.9");
  });

  it("triggers onClick on Enter / Space keypress", () => {
    const onClick = vi.fn();
    render(
      <KCDChip
        code="G45.9"
        labelKo={null}
        labelEn="TIA"
        locale="en"
        onClick={onClick}
      />,
    );
    const chip = screen.getByTestId("kcd-chip");
    fireEvent.keyDown(chip, { key: "Enter" });
    expect(onClick).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(chip, { key: " " });
    expect(onClick).toHaveBeenCalledTimes(2);
  });

  it("is non-interactive when no onClick", () => {
    render(
      <KCDChip code="G45.9" labelKo={null} labelEn="TIA" locale="en" />,
    );
    const chip = screen.getByTestId("kcd-chip");
    expect(chip).not.toHaveAttribute("role");
    expect(chip).toHaveAttribute("tabindex", "-1");
  });
});


describe("KCDChip — variant (DA-12, design-spec §6.4)", () => {
  it("renders provenance footer when variant=detail", () => {
    render(
      <KCDChip
        code="G45.9"
        labelKo={null}
        labelEn="TIA"
        locale="en"
        variant="detail"
      />,
    );
    expect(screen.getByTestId("kcd-chip-footer")).toHaveTextContent(
      "Provenance: Korean Standard Classification of Diseases v8 (KCD-8)",
    );
  });

  it("hides provenance footer when variant=inline (default)", () => {
    render(
      <KCDChip code="G45.9" labelKo={null} labelEn="TIA" locale="en" />,
    );
    expect(screen.queryByTestId("kcd-chip-footer")).toBeNull();
  });

  it("renders Korean footer text in ko locale", () => {
    render(
      <KCDChip
        code="G45.9"
        labelKo="TIA"
        labelEn={null}
        locale="ko"
        variant="detail"
      />,
    );
    expect(screen.getByTestId("kcd-chip-footer")).toHaveTextContent(
      "출처: 한국표준질병사인분류 8차 (KCD-8)",
    );
  });
});


describe("PhiPendingBadge — cell variant (FR-TS15-10, DA-8)", () => {
  it("renders ⚠ icon + 'pending' text in en", () => {
    render(<PhiPendingBadge variant="cell" locale="en" />);
    const badge = screen.getByTestId("phi-pending-badge");
    expect(badge).toHaveAttribute("data-variant", "cell");
    expect(badge).toHaveTextContent("pending");
    // Icon is rendered as inline svg.
    expect(badge.querySelector("svg")).not.toBeNull();
  });

  it("renders Korean text in ko", () => {
    render(<PhiPendingBadge variant="cell" locale="ko" />);
    expect(screen.getByTestId("phi-pending-badge")).toHaveTextContent(
      "검토 대기",
    );
  });

  it("has role=status for screen readers (NFR-TS15-A11Y-1)", () => {
    render(<PhiPendingBadge variant="cell" locale="en" />);
    expect(screen.getByTestId("phi-pending-badge")).toHaveAttribute(
      "role",
      "status",
    );
  });

  it("has tooltip via title attribute", () => {
    render(<PhiPendingBadge variant="cell" locale="en" />);
    expect(screen.getByTestId("phi-pending-badge")).toHaveAttribute(
      "title",
      "Excluded for de-identification review",
    );
  });
});


describe("PhiPendingBadge — detail variant (DA-9, design-spec §9.2)", () => {
  it("renders 'PHI verification pending' in en", () => {
    render(<PhiPendingBadge variant="detail" locale="en" />);
    const badge = screen.getByTestId("phi-pending-badge");
    expect(badge).toHaveAttribute("data-variant", "detail");
    expect(badge).toHaveTextContent("PHI verification pending");
  });

  it("renders Korean text in ko", () => {
    render(<PhiPendingBadge variant="detail" locale="ko" />);
    expect(screen.getByTestId("phi-pending-badge")).toHaveTextContent(
      "PHI 검증 대기 중",
    );
  });
});


describe("PhiPendingBadge — color-blind safe (DA-10, §7.4)", () => {
  it("never relies on color alone — both icon AND text are present", () => {
    const { container } = render(
      <PhiPendingBadge variant="cell" locale="en" />,
    );
    // Icon (svg).
    expect(container.querySelector("svg")).not.toBeNull();
    // Text.
    expect(container.textContent).toContain("pending");
  });
});


// vitest global; mirrored from text-search.test.tsx.
import { vi } from "vitest";
