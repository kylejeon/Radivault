"use client";

/**
 * <QualityMetricsCard> — study-detail v3 (buyer-ux-v2/v3 mockup §quality-metrics).
 *
 * 2x2 dense grid of derived data-quality signals on the right rail of the
 * Study Detail page. Always renders all 4 cells; missing fields fall back to
 * "—" with a `--missing` modifier so buyers can tell the slot is intentional
 * but the value is not yet available from the gateway pipeline.
 *
 * Backed-by-data today (FR-V3-API-2):
 *   - imageCount  : `n_instances` (int) + `n_series` for sub-text
 *   - resolution  : NOT YET in central index — TODO surface from
 *                    raw_dicom_tags(0028,0010)x(0028,0011)
 *
 * Pending backend extension (separate dev-spec):
 *   - sliceThickness  (0018,0050) min/max range
 *   - completenessScore (12-field fill rate)
 *
 * Locale: copy split EN/KO via `locale` prop. Mockup ships `[data-locale]`
 * CSS toggling; we keep parity by branching at render time so the React
 * tree is single-string per render.
 */

import type { Locale } from "@/lib/i18n";

export type QualityMetricsCardProps = {
  imageCount: number | null;
  seriesCount: number | null;
  sliceThicknessMm: number | null;
  sliceThicknessRange?: { min: number; max: number } | null;
  resolutionWidth?: number | null;
  resolutionHeight?: number | null;
  pixelSpacingMm?: number | null;
  completenessPct?: number | null;
  completenessFilled?: number | null;
  completenessTotal?: number | null;
  locale?: Locale;
};

const MISSING = "—";

export function QualityMetricsCard({
  imageCount,
  seriesCount,
  sliceThicknessMm,
  sliceThicknessRange,
  resolutionWidth,
  resolutionHeight,
  pixelSpacingMm,
  completenessPct,
  completenessFilled,
  completenessTotal,
  locale = "en",
}: QualityMetricsCardProps) {
  const t =
    locale === "ko"
      ? {
          title: "데이터 품질",
          imageCount: "이미지 수",
          imageCountSub: (n: number) => `${n}개 시리즈`,
          sliceThickness: "슬라이스 두께",
          sliceThicknessSub: (min: number, max: number) =>
            `범위 ${min.toFixed(1)}–${max.toFixed(1)}`,
          resolution: "해상도",
          resolutionSub: (mm: number) => `${mm.toFixed(2)} mm/px`,
          completeness: "완전성",
          completenessSub: (a: number, b: number) => `${a}/${b} 필드`,
        }
      : {
          title: "Data quality",
          imageCount: "Image count",
          imageCountSub: (n: number) => `${n} series`,
          sliceThickness: "Slice thickness",
          sliceThicknessSub: (min: number, max: number) =>
            `range ${min.toFixed(1)}–${max.toFixed(1)}`,
          resolution: "Resolution",
          resolutionSub: (mm: number) => `${mm.toFixed(2)} mm/px`,
          completeness: "Completeness",
          completenessSub: (a: number, b: number) => `${a}/${b} fields`,
        };

  const imageCountDisplay = imageCount != null ? imageCount.toLocaleString() : MISSING;
  const sliceThicknessDisplay =
    sliceThicknessMm != null ? `${sliceThicknessMm.toFixed(1)} mm` : MISSING;
  const resolutionDisplay =
    resolutionWidth != null && resolutionHeight != null
      ? `${resolutionWidth}×${resolutionHeight}`
      : MISSING;
  const completenessDisplay =
    completenessPct != null ? `${completenessPct}%` : MISSING;

  return (
    <section
      data-testid="quality-metrics-card"
      className="rv-detail-section"
    >
      <div className="rv-detail-section__title">
        <span>{t.title}</span>
      </div>
      <div className="rv-quality-metrics">
        <Cell
          label={t.imageCount}
          value={imageCountDisplay}
          sub={
            seriesCount != null && imageCount != null
              ? t.imageCountSub(seriesCount)
              : null
          }
          missing={imageCount == null}
          testid="quality-metrics-image-count"
        />
        <Cell
          label={t.sliceThickness}
          value={sliceThicknessDisplay}
          sub={
            sliceThicknessRange
              ? t.sliceThicknessSub(
                  sliceThicknessRange.min,
                  sliceThicknessRange.max,
                )
              : null
          }
          missing={sliceThicknessMm == null}
          testid="quality-metrics-slice-thickness"
        />
        <Cell
          label={t.resolution}
          value={resolutionDisplay}
          sub={pixelSpacingMm != null ? t.resolutionSub(pixelSpacingMm) : null}
          missing={resolutionWidth == null || resolutionHeight == null}
          testid="quality-metrics-resolution"
        />
        <Cell
          label={t.completeness}
          value={completenessDisplay}
          sub={
            completenessFilled != null && completenessTotal != null
              ? t.completenessSub(completenessFilled, completenessTotal)
              : null
          }
          missing={completenessPct == null}
          score
          testid="quality-metrics-completeness"
        />
      </div>
    </section>
  );
}

function Cell({
  label,
  value,
  sub,
  missing,
  score,
  testid,
}: {
  label: string;
  value: string;
  sub: string | null;
  missing: boolean;
  score?: boolean;
  testid: string;
}) {
  const cls =
    "rv-quality-metric" +
    (score ? " rv-quality-metric--score" : "") +
    (missing ? " rv-quality-metric--missing" : "");
  return (
    <div className={cls} data-testid={testid}>
      <div className="rv-quality-metric__label">{label}</div>
      <div className="rv-quality-metric__value">{value}</div>
      {sub ? <div className="rv-quality-metric__sub">{sub}</div> : null}
    </div>
  );
}
