/**
 * <LocaleToggle> + LocaleProvider — vitest unit (QA HIGH-3 / BL-2).
 *
 * Verifies:
 *   1. Renders both EN + 한국어 buttons with role=tab.
 *   2. Click switches the active button (aria-selected) without reload.
 *   3. setLocale persists to localStorage.
 *   4. Provider hydrates from localStorage on mount.
 */

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  LocaleProvider,
  LocaleToggle,
  useLocale,
} from "@/components/shared/LocaleToggle";

function StubChild() {
  const { locale } = useLocale();
  return <div data-testid="stub-locale">{locale}</div>;
}

describe("v3 — LocaleToggle", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.body.removeAttribute("data-locale");
  });
  afterEach(() => {
    window.localStorage.clear();
  });

  it("renders both EN + KR tabs with role=tab", () => {
    render(
      <LocaleProvider initial="en">
        <LocaleToggle />
      </LocaleProvider>,
    );
    const wrap = screen.getByTestId("v3-locale-toggle");
    expect(wrap).toHaveAttribute("role", "tablist");
    const en = screen.getByTestId("v3-locale-toggle-en");
    const ko = screen.getByTestId("v3-locale-toggle-ko");
    expect(en).toHaveAttribute("role", "tab");
    expect(ko).toHaveAttribute("role", "tab");
    expect(en).toHaveAttribute("aria-selected", "true");
    expect(ko).toHaveAttribute("aria-selected", "false");
  });

  it("switches active tab on click without reload + updates context children", () => {
    render(
      <LocaleProvider initial="en">
        <LocaleToggle />
        <StubChild />
      </LocaleProvider>,
    );
    expect(screen.getByTestId("stub-locale")).toHaveTextContent("en");
    fireEvent.click(screen.getByTestId("v3-locale-toggle-ko"));
    expect(screen.getByTestId("stub-locale")).toHaveTextContent("ko");
    expect(screen.getByTestId("v3-locale-toggle-ko")).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("v3-locale-toggle-en")).toHaveAttribute(
      "aria-selected",
      "false",
    );
  });

  it("persists choice to localStorage + body[data-locale]", () => {
    render(
      <LocaleProvider initial="en">
        <LocaleToggle />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByTestId("v3-locale-toggle-ko"));
    expect(window.localStorage.getItem("radivault.locale")).toBe("ko");
    expect(document.body.getAttribute("data-locale")).toBe("ko");
  });

  it("hydrates from localStorage on mount overriding initial prop", async () => {
    window.localStorage.setItem("radivault.locale", "ko");
    render(
      <LocaleProvider initial="en">
        <StubChild />
      </LocaleProvider>,
    );
    // useEffect runs sync in jsdom + RTL; child should reflect KR.
    expect(await screen.findByText("ko")).toBeInTheDocument();
  });
});
