"use client";

/**
 * <MetaCard> — generic key/value card for the study-detail right rail.
 *
 * Used for the Patient / Study / Acquisition / Pixel & spatial cards (mockup
 * `.detail-meta-card`). Caller passes a head label (+ optional right-aligned
 * count chip) and a list of rows; missing values render as "—" with the
 * `--missing` modifier so the slot is visibly empty rather than hidden.
 *
 * Series cards use a different shape (number + 2-line title + count) so they
 * have their own `<SeriesMiniCardList>` component.
 */

import type { ReactNode } from "react";

export type MetaRow = {
  /** Stable test/identifier key — used for testid + react key. */
  key: string;
  label: string;
  /** ``null`` / ``undefined`` / `""` are rendered as "—" */
  value: ReactNode | null | undefined;
};

export type MetaCardProps = {
  /** EN/KO already resolved by caller. */
  title: string;
  /** Test-id slug — e.g. ``patient`` → ``data-testid="meta-card-patient"``. */
  slug: string;
  /** Optional right-aligned head chip (e.g. ``"3 series · 312 inst"``). */
  count?: string | null;
  rows: MetaRow[];
};

const MISSING = "—";

export function MetaCard({ title, slug, count, rows }: MetaCardProps) {
  return (
    <div
      className="rv-detail-meta-card"
      data-testid={`meta-card-${slug}`}
    >
      <div className="rv-detail-meta-card__head">
        <span>{title}</span>
        {count ? (
          <span className="rv-detail-meta-card__head__count">{count}</span>
        ) : null}
      </div>
      {rows.map((row) => {
        const isMissing =
          row.value == null || row.value === "" || row.value === MISSING;
        return (
          <div
            key={row.key}
            className="rv-detail-meta-row"
            data-testid={`meta-card-${slug}-row-${row.key}`}
          >
            <span className="rv-detail-meta-row__k">{row.label}</span>
            <span
              className={
                "rv-detail-meta-row__v" +
                (isMissing ? " rv-detail-meta-row__v--missing" : "")
              }
              title={typeof row.value === "string" ? row.value : undefined}
            >
              {isMissing ? MISSING : row.value}
            </span>
          </div>
        );
      })}
    </div>
  );
}
