"use client";

/**
 * <SeriesMiniCardList> — compact series list rendered inside a Series card on
 * the study-detail right rail (mockup `.detail-meta-card` containing
 * `.series-mini` rows).
 *
 * Each mini-row has 3 columns: numbered chip · title + sub · instance count.
 * Title falls back to "Series N" when no description tag is available; sub
 * carries modality + slice thickness + resolution if known, else "—".
 */

import type { Locale } from "@/lib/i18n";

export type SeriesMiniItem = {
  pseudo_series_uid: string;
  modality: string | null;
  n_instances: number;
  /** Optional human-readable description (DICOM 0008,103E). */
  description?: string | null;
  /** Optional slice thickness in mm (DICOM 0018,0050). */
  slice_thickness_mm?: number | null;
  /** Optional pixel resolution width × height. */
  resolution_w?: number | null;
  resolution_h?: number | null;
};

export type SeriesMiniCardListProps = {
  series: SeriesMiniItem[];
  locale?: Locale;
};

export function SeriesMiniCardList({
  series,
  locale = "en",
}: SeriesMiniCardListProps) {
  const t =
    locale === "ko"
      ? {
          title: "시리즈",
          countLabel: (n: number, inst: number) => `${n}개 시리즈 · ${inst} inst`,
          fallback: (i: number) => `시리즈 ${i}`,
          inst: "inst",
          empty: "시리즈 없음",
        }
      : {
          title: "Series",
          countLabel: (n: number, inst: number) => `${n} series · ${inst} inst`,
          fallback: (i: number) => `Series ${i}`,
          inst: "inst",
          empty: "No series",
        };

  const totalInst = series.reduce((s, x) => s + (x.n_instances ?? 0), 0);

  return (
    <div className="rv-detail-meta-card" data-testid="meta-card-series">
      <div className="rv-detail-meta-card__head">
        <span>{t.title}</span>
        {series.length > 0 ? (
          <span className="rv-detail-meta-card__head__count">
            {t.countLabel(series.length, totalInst)}
          </span>
        ) : null}
      </div>
      {series.length === 0 ? (
        <div
          className="rv-detail-meta-row"
          data-testid="meta-card-series-empty"
        >
          <span className="rv-detail-meta-row__k">{t.empty}</span>
          <span className="rv-detail-meta-row__v rv-detail-meta-row__v--missing">
            —
          </span>
        </div>
      ) : (
        series.map((s, i) => (
          <SeriesMiniRow
            key={s.pseudo_series_uid}
            index={i}
            series={s}
            fallbackTitle={t.fallback(i + 1)}
            instLabel={t.inst}
          />
        ))
      )}
    </div>
  );
}

function SeriesMiniRow({
  index,
  series,
  fallbackTitle,
  instLabel,
}: {
  index: number;
  series: SeriesMiniItem;
  fallbackTitle: string;
  instLabel: string;
}) {
  const title =
    series.description && series.description.trim().length > 0
      ? series.description.trim()
      : fallbackTitle;

  // Compose the sub-line "modality · slice mm · resolution²".
  const subParts: string[] = [];
  if (series.modality) subParts.push(series.modality);
  if (series.slice_thickness_mm != null)
    subParts.push(`${series.slice_thickness_mm.toFixed(1)} mm`);
  if (series.resolution_w != null && series.resolution_h != null) {
    subParts.push(
      series.resolution_w === series.resolution_h
        ? `${series.resolution_w}²`
        : `${series.resolution_w}×${series.resolution_h}`,
    );
  }
  const sub = subParts.length > 0 ? subParts.join(" · ") : "—";

  return (
    <div
      className="rv-series-mini"
      data-testid={`series-mini-card-${index}`}
    >
      <div className="rv-series-mini__num">{index + 1}</div>
      <div style={{ minWidth: 0 }}>
        <span className="rv-series-mini__title" title={title}>
          {title}
        </span>
        <span className="rv-series-mini__sub">{sub}</span>
      </div>
      <div className="rv-series-mini__count">
        {series.n_instances.toLocaleString()} {instLabel}
      </div>
    </div>
  );
}
