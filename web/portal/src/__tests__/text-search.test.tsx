/**
 * text-search-description Phase 1.0 — vitest smoke for the 5 new components.
 *
 * Focuses on:
 *   - <SearchBar> typing + clear + masked-badge mount
 *   - <AutocompleteDropdown> keyboard nav contract
 *   - <HighlightedText> XSS sanitisation (only <mark> survives)
 *   - <MaskedQueryBadge> mounts only when ``flagged`` is non-empty
 */

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  AutocompleteDropdown,
  type AutocompleteSuggestion,
} from "@/components/buyer/v3/AutocompleteDropdown";
import { HighlightedText } from "@/components/buyer/v3/HighlightedText";
import { MaskedQueryBadge } from "@/components/buyer/v3/MaskedQueryBadge";
import { SearchBar } from "@/components/buyer/v3/SearchBar";

const SAMPLE_SUGGESTIONS: AutocompleteSuggestion[] = [
  { text: "BRAIN MR", field: "body_part", score: 0.9 },
  { text: "BRAIN CT", field: "body_part", score: 0.7 },
  { text: "BREAST MG", field: "body_part", score: 0.5 },
];

describe("HighlightedText — XSS hardening (FR-TS-9)", () => {
  it("renders mark tags from server snippet", () => {
    const { container } = render(
      <HighlightedText html="BRAIN <mark>MR</mark>" fallback="brain mr" />,
    );
    expect(container.querySelectorAll("mark").length).toBe(1);
    expect(container.textContent).toBe("BRAIN MR");
  });

  it("strips script tags even if server emits them", () => {
    const { container } = render(
      <HighlightedText
        html='Brain <script>alert("xss")</script> <mark>MR</mark>'
        fallback="brain mr"
      />,
    );
    // The script tag must not survive — only literal text + <mark>.
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelectorAll("mark").length).toBe(1);
  });

  it("strips arbitrary attributes from rogue tags", () => {
    const { container } = render(
      <HighlightedText
        html='<img src="x" onerror="alert(1)" /> <mark>MR</mark>'
        fallback="x mr"
      />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelectorAll("mark").length).toBe(1);
  });

  it("renders fallback when html is null", () => {
    const { container } = render(
      <HighlightedText html={null} fallback="plain text" />,
    );
    expect(container.textContent).toBe("plain text");
    expect(container.querySelector("mark")).toBeNull();
  });

  it("truncates long snippets with ellipsis", () => {
    const longHtml = "x".repeat(300) + "<mark>END</mark>";
    const { container } = render(
      <HighlightedText html={longHtml} fallback="" maxLength={50} />,
    );
    expect(container.textContent?.length).toBeLessThanOrEqual(50);
    expect(container.textContent).toMatch(/…$/);
  });
});

describe("MaskedQueryBadge — FR-TS-10", () => {
  it("does not render when flagged is empty", () => {
    const { container } = render(
      <MaskedQueryBadge flagged={[]} locale="en" />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("mounts when flagged contains a pattern", () => {
    render(<MaskedQueryBadge flagged={["KOREAN_NAME"]} locale="en" />);
    const badge = screen.getByTestId("ts-masked-query-badge");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveAttribute("role", "status");
  });

  it("renders Korean copy under ko locale", () => {
    render(<MaskedQueryBadge flagged={["KOREAN_NAME"]} locale="ko" />);
    expect(screen.getByText("검색어 마스킹됨")).toBeInTheDocument();
  });
});

describe("AutocompleteDropdown — FR-TS-8 / design-spec §7", () => {
  it("does not render when closed", () => {
    const { container } = render(
      <AutocompleteDropdown
        open={false}
        loading={false}
        query="bra"
        suggestions={SAMPLE_SUGGESTIONS}
        focusedIndex={-1}
        locale="en"
        listboxId="ts-test"
        onPick={vi.fn()}
        onHover={vi.fn()}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders all suggestions with field badges", () => {
    render(
      <AutocompleteDropdown
        open={true}
        loading={false}
        query="bra"
        suggestions={SAMPLE_SUGGESTIONS}
        focusedIndex={-1}
        locale="en"
        listboxId="ts-test"
        onPick={vi.fn()}
        onHover={vi.fn()}
      />,
    );
    const items = screen.getAllByTestId("ts-suggestion");
    expect(items).toHaveLength(SAMPLE_SUGGESTIONS.length);
    expect(items[0]).toHaveAttribute("data-field", "body_part");
  });

  it("marks the focused option via aria-selected", () => {
    render(
      <AutocompleteDropdown
        open={true}
        loading={false}
        query="bra"
        suggestions={SAMPLE_SUGGESTIONS}
        focusedIndex={1}
        locale="en"
        listboxId="ts-test"
        onPick={vi.fn()}
        onHover={vi.fn()}
      />,
    );
    const items = screen.getAllByTestId("ts-suggestion");
    expect(items[0].getAttribute("aria-selected")).toBe("false");
    expect(items[1].getAttribute("aria-selected")).toBe("true");
  });

  it("calls onPick on mousedown (not click) so blur doesn't race", () => {
    const onPick = vi.fn();
    render(
      <AutocompleteDropdown
        open={true}
        loading={false}
        query="bra"
        suggestions={SAMPLE_SUGGESTIONS}
        focusedIndex={-1}
        locale="en"
        listboxId="ts-test"
        onPick={onPick}
        onHover={vi.fn()}
      />,
    );
    const items = screen.getAllByTestId("ts-suggestion");
    fireEvent.mouseDown(items[0]);
    expect(onPick).toHaveBeenCalledWith(SAMPLE_SUGGESTIONS[0]);
  });

  it("renders the empty-suggestion row when no matches", () => {
    render(
      <AutocompleteDropdown
        open={true}
        loading={false}
        query="zzz"
        suggestions={[]}
        focusedIndex={-1}
        locale="en"
        listboxId="ts-test"
        onPick={vi.fn()}
        onHover={vi.fn()}
      />,
    );
    expect(screen.getByText("No suggestions")).toBeInTheDocument();
  });
});

describe("SearchBar — FR-TS-1", () => {
  it("renders placeholder + clear button hidden when empty", () => {
    render(
      <SearchBar
        value=""
        onChange={() => {}}
        onSubmit={() => {}}
        locale="en"
        disableAutocomplete
      />,
    );
    const input = screen.getByTestId("ts-search-input") as HTMLInputElement;
    expect(input).toBeInTheDocument();
    expect(input.placeholder).toMatch(/Search by body part/i);
    expect(screen.queryByTestId("ts-search-clear")).not.toBeInTheDocument();
  });

  it("shows the clear button when q is non-empty", () => {
    render(
      <SearchBar
        value="brain"
        onChange={() => {}}
        onSubmit={() => {}}
        locale="en"
        disableAutocomplete
      />,
    );
    expect(screen.getByTestId("ts-search-clear")).toBeInTheDocument();
  });

  it("clear button resets q to empty string", () => {
    const onChange = vi.fn();
    render(
      <SearchBar
        value="brain"
        onChange={onChange}
        onSubmit={() => {}}
        locale="en"
        disableAutocomplete
      />,
    );
    fireEvent.click(screen.getByTestId("ts-search-clear"));
    expect(onChange).toHaveBeenCalledWith("");
  });

  it("Enter key triggers onSubmit with current value", () => {
    const onSubmit = vi.fn();
    render(
      <SearchBar
        value="MR brain"
        onChange={() => {}}
        onSubmit={onSubmit}
        locale="en"
        disableAutocomplete
      />,
    );
    const input = screen.getByTestId("ts-search-input");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledWith("MR brain");
  });

  it("mounts MaskedQueryBadge when flaggedPatterns has entries", () => {
    render(
      <SearchBar
        value="홍길동 brain"
        onChange={() => {}}
        onSubmit={() => {}}
        locale="en"
        disableAutocomplete
        flaggedPatterns={["KOREAN_NAME"]}
      />,
    );
    expect(screen.getByTestId("ts-masked-query-badge")).toBeInTheDocument();
  });

  it("renders Korean placeholder under ko locale", () => {
    render(
      <SearchBar
        value=""
        onChange={() => {}}
        onSubmit={() => {}}
        locale="ko"
        disableAutocomplete
      />,
    );
    const input = screen.getByTestId("ts-search-input") as HTMLInputElement;
    expect(input.placeholder).toMatch(/부위/);
  });
});
