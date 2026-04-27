/**
 * <ColumnToggle> — vitest unit (QA HIGH-2 / BL-1).
 *
 * Verifies:
 *   1. Trigger button renders both EN + KR labels.
 *   2. Clicking the button opens the menu (data-testid resolves).
 *   3. Always-on rows (Hospital) are checked + disabled.
 *   4. Deferred rows (v0.1.5) are unchecked + disabled + show hint.
 *   5. Toggling a normal row (e.g. Sex) calls onChange and removes the key.
 *   6. Outside-click closes the menu.
 */

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  ColumnToggle,
  V3_COLUMN_DEFS,
  V3_DEFAULT_VISIBLE,
} from "@/components/buyer/v3/ColumnToggle";

describe("v3 — ColumnToggle", () => {
  it("renders EN trigger label + closed menu by default", () => {
    render(
      <ColumnToggle
        columns={V3_COLUMN_DEFS}
        visibleKeys={V3_DEFAULT_VISIBLE}
        onChange={() => {}}
        locale="en"
      />,
    );
    expect(screen.getByTestId("v3-column-toggle-btn")).toHaveTextContent(
      "Show columns",
    );
    expect(screen.queryByTestId("v3-column-toggle-menu")).toBeNull();
  });

  it("renders KO trigger label", () => {
    render(
      <ColumnToggle
        columns={V3_COLUMN_DEFS}
        visibleKeys={V3_DEFAULT_VISIBLE}
        onChange={() => {}}
        locale="ko"
      />,
    );
    expect(screen.getByTestId("v3-column-toggle-btn")).toHaveTextContent(
      "컬럼 표시",
    );
  });

  it("opens menu on click and shows always-on Hospital + deferred rows", () => {
    render(
      <ColumnToggle
        columns={V3_COLUMN_DEFS}
        visibleKeys={V3_DEFAULT_VISIBLE}
        onChange={() => {}}
        locale="en"
      />,
    );
    fireEvent.click(screen.getByTestId("v3-column-toggle-btn"));
    expect(screen.getByTestId("v3-column-toggle-menu")).toBeInTheDocument();

    // Hospital row — always-on, disabled, checked.
    const hospitalRow = screen.getByTestId("v3-column-toggle-row-hospital");
    const hospitalCb = hospitalRow.querySelector(
      'input[type="checkbox"]',
    ) as HTMLInputElement;
    expect(hospitalCb).toBeDisabled();
    expect(hospitalCb).toBeChecked();
    expect(hospitalRow).toHaveTextContent(/always/i);

    // Slice-thickness — deferred v0.1.5, disabled, unchecked.
    const sliceRow = screen.getByTestId("v3-column-toggle-row-slice_thickness");
    const sliceCb = sliceRow.querySelector(
      'input[type="checkbox"]',
    ) as HTMLInputElement;
    expect(sliceCb).toBeDisabled();
    expect(sliceCb).not.toBeChecked();
    expect(sliceRow).toHaveTextContent("v0.1.5");
  });

  it("toggling Sex calls onChange with key removed", () => {
    const onChange = vi.fn();
    render(
      <ColumnToggle
        columns={V3_COLUMN_DEFS}
        visibleKeys={V3_DEFAULT_VISIBLE}
        onChange={onChange}
        locale="en"
      />,
    );
    fireEvent.click(screen.getByTestId("v3-column-toggle-btn"));
    const sexRow = screen.getByTestId("v3-column-toggle-row-sex");
    const sexCb = sexRow.querySelector(
      'input[type="checkbox"]',
    ) as HTMLInputElement;
    expect(sexCb).toBeChecked();
    fireEvent.click(sexCb);
    expect(onChange).toHaveBeenCalledTimes(1);
    const next = onChange.mock.calls[0][0] as string[];
    expect(next).not.toContain("sex");
    expect(next).toContain("hospital"); // always-on preserved
    expect(next).toContain("examdate");
  });

  it("counts visible toggleable columns in menu title", () => {
    render(
      <ColumnToggle
        columns={V3_COLUMN_DEFS}
        // Drop sex + uid → 10 / 12 toggleable (text-search-description
        // Phase 1.5 added the Description column).
        visibleKeys={V3_DEFAULT_VISIBLE.filter(
          (k) => k !== "sex" && k !== "uid",
        )}
        onChange={() => {}}
        locale="en"
      />,
    );
    fireEvent.click(screen.getByTestId("v3-column-toggle-btn"));
    const menu = screen.getByTestId("v3-column-toggle-menu");
    // 12 toggleable (13 total - hospital always-on).
    expect(menu).toHaveTextContent("Visible columns (10/12)");
  });

  it("outside click closes the menu", () => {
    render(
      <div>
        <button data-testid="outside">outside</button>
        <ColumnToggle
          columns={V3_COLUMN_DEFS}
          visibleKeys={V3_DEFAULT_VISIBLE}
          onChange={() => {}}
          locale="en"
        />
      </div>,
    );
    fireEvent.click(screen.getByTestId("v3-column-toggle-btn"));
    expect(screen.getByTestId("v3-column-toggle-menu")).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByTestId("outside"));
    expect(screen.queryByTestId("v3-column-toggle-menu")).toBeNull();
  });
});
