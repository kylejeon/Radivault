"use client";

import clsx from "clsx";

export type FacetItem = { value: string; count: number };

/**
 * Left-pane facet group (design-spec §3.4).
 *
 * Renders as a grouped list of checkboxes with their counts. The search page
 * sends a ``POST /api/search/studies`` each time selections change; we do not
 * maintain URL query state for cursor/filter_sha256 (§FR-A-15).
 */
export function FacetGroup({
  label,
  facet,
  items,
  selected,
  onToggle,
}: {
  label: string;
  facet: string;
  items: FacetItem[];
  selected: Set<string>;
  onToggle: (value: string) => void;
}) {
  return (
    <fieldset className="card p-4">
      <legend className="mb-2 text-sm font-medium text-ink">{label}</legend>
      <ul className="flex flex-col gap-1.5">
        {items.length === 0 ? (
          <li className="text-xs text-ink-subtle">No values in current results.</li>
        ) : null}
        {items.map((it) => (
          <li key={`${facet}:${it.value}`}>
            <label className="flex cursor-pointer items-center justify-between gap-2 text-sm">
              <span className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={selected.has(it.value)}
                  onChange={() => onToggle(it.value)}
                  className="size-4"
                />
                <span className={clsx(selected.has(it.value) && "font-semibold")}>
                  {it.value || "(unknown)"}
                </span>
              </span>
              <span className="rounded-full bg-surface-muted px-2 py-0.5 text-[11px] text-ink-subtle">
                {it.count.toLocaleString()}
              </span>
            </label>
          </li>
        ))}
      </ul>
    </fieldset>
  );
}
