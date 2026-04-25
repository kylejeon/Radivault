import clsx from "clsx";

/**
 * FederatedSignal {#federated-signal-v1} — design-spec-portal-redesign §11.2.
 * FR-BP-6: "1 search = N hospitals" northstar badge that sits sticky atop the
 * `/search` results column.
 *
 * The N hospitals value is computed server-side (COUNT DISTINCT
 * `hospital_opaque_id`) — this component never derives it from the client
 * search results to avoid race conditions during pagination.
 *
 * Variants:
 *   - `standard`: default sticky banner (top of `/search` results pane).
 *   - `mini`:     compact pill used inside the cohort sidebar
 *                 ("Selected 12 · From 2 hospitals", §11.6).
 *   - `empty`:    0-result variant ("No results across our 2 partner
 *                 hospitals", §11.2).
 */

export type FederatedSignalProps = {
  studyCount: number;
  hospitalCount: number;
  filterChips?: string[];
  /** Optional partial-failure warning (§14.5). */
  partialWarning?: string | null;
  variant?: "standard" | "mini" | "empty";
  locale?: "en" | "ko";
};

function formatCount(n: number, locale: "en" | "ko"): string {
  return new Intl.NumberFormat(locale === "ko" ? "ko-KR" : "en-US").format(n);
}

export function FederatedSignal({
  studyCount,
  hospitalCount,
  filterChips,
  partialWarning,
  variant = "standard",
  locale = "en",
}: FederatedSignalProps) {
  const studies = formatCount(studyCount, locale);
  const hospitals = formatCount(hospitalCount, locale);

  if (variant === "empty") {
    const text =
      locale === "ko"
        ? `${hospitals} 개 파트너 병원에서 일치 결과 없음`
        : `No results across our ${hospitals} partner hospitals`;
    return (
      <div
        data-testid="federated-signal-empty"
        role="status"
        className="rounded-md border-l-4 border-l-primary-600 bg-primary-50 px-4 py-2.5 text-sm text-text"
      >
        <span className="text-text-muted">{text}</span>
      </div>
    );
  }

  if (variant === "mini") {
    const text =
      locale === "ko"
        ? `선택 ${studies} · ${hospitals} 개 병원`
        : `Selected ${studies} · From ${hospitals} hospitals`;
    return (
      <div
        data-testid="federated-signal-mini"
        className="text-xs font-medium text-text-muted"
      >
        {text}
      </div>
    );
  }

  const studiesLabel = locale === "ko" ? "study" : "studies";
  const acrossLabel = locale === "ko" ? "개 병원에서 집계" : "across";
  const hospitalsLabel = locale === "ko" ? "" : "hospitals";

  return (
    <div
      data-testid="federated-signal"
      role="status"
      aria-live="polite"
      className={clsx(
        "sticky top-16 z-10 flex flex-col gap-2 rounded-md border-l-4 border-l-primary-600 bg-primary-50 px-4 py-2.5 text-sm text-text shadow-card",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 font-semibold">
          <span aria-hidden className="text-primary-600">◆</span>
          {locale === "ko" ? (
            <span>
              <span className="text-primary-700 tabular-nums">{studies}</span>{" "}
              {studiesLabel} · <span className="text-primary-700 tabular-nums">{hospitals}</span>{" "}
              {acrossLabel}
            </span>
          ) : (
            <span>
              <span className="text-primary-700 tabular-nums">{studies}</span>{" "}
              {studiesLabel} {acrossLabel}{" "}
              <span className="text-primary-700 tabular-nums">{hospitals}</span>{" "}
              {hospitalsLabel}
            </span>
          )}
        </div>
        {filterChips && filterChips.length > 0 ? (
          <div className="flex items-center gap-1.5 text-xs text-text-muted">
            <span aria-hidden>•</span>
            <span>
              {filterChips.slice(0, 3).join(" · ")}
              {filterChips.length > 3 ? ` · +${filterChips.length - 3}` : ""}
            </span>
          </div>
        ) : null}
      </div>
      {partialWarning ? (
        <div
          role="alert"
          className="rounded-sm bg-status-warning-bg px-2 py-1 text-xs text-status-warning-fg"
        >
          {partialWarning}
        </div>
      ) : null}
    </div>
  );
}
