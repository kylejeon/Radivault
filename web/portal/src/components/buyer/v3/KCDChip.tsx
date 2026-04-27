"use client";

/**
 * <KCDChip> — text-search-description Phase 1.5 / design-spec §6.
 *
 * Locale-aware diagnostic-code chip. Same `kcd_code` (e.g. "G45.9") rendered
 * with a different *prominent prefix* depending on buyer locale:
 *
 *   en → "ICD-10 G45.9"   tooltip: "Korean coded as KCD-8 (95% identical to WHO ICD-10)"
 *   ko → "KCD-8 G45.9"    tooltip: "WHO ICD-10 호환 (95% 동일)"
 *
 * Visual style is identical across locales (teal-100 bg + teal-700 fg pill,
 * matching the Phase 1.0 inline `.rv-kcd-chip` rendering). Only the prefix
 * literal + tooltip text + aria-label differ.
 *
 * Props:
 *   code        — canonical KCD-8 / ICD-10 code string ("G45.9").
 *   labelKo     — Korean diagnostic label (e.g. "일과성 뇌허혈 발작").
 *   labelEn     — English diagnostic label (e.g. "Transient ischaemic attack").
 *   locale      — 'en' | 'ko' (LocaleProvider injection).
 *   variant     — 'inline' (ResultTable cell, default) | 'detail' (Study
 *                 Detail panel; renders provenance footer note).
 *   size        — 'sm' (autocomplete dropdown) | 'md' (table/detail).
 *   onClick     — optional click handler. When provided, chip becomes a
 *                 button with role=button + cursor:pointer (Kyle: facet
 *                 filter add). When omitted, chip is non-interactive.
 *
 * a11y:
 *   - Tab focus reachable via tabIndex=0 when onClick is set.
 *   - aria-describedby connects chip to the tooltip element so screen
 *     readers announce the provenance text on focus.
 *   - Tooltip is a sibling element with role="tooltip"; visibility is
 *     toggled via the [data-tooltip-open] attribute (CSS-driven, no React
 *     state churn for hover).
 */

import { useId, useState } from "react";

export type KCDChipProps = {
  code: string;
  labelKo: string | null;
  labelEn: string | null;
  locale: "en" | "ko";
  variant?: "inline" | "detail";
  size?: "sm" | "md";
  onClick?: (code: string) => void;
  className?: string;
};

const TEAL_BG_100 = "#ccfbf1";
const TEAL_FG_700 = "#0f766e";
const TEXT_STRONG = "#020617";
const TEXT_MUTED = "#64748b";
const BORDER_LIGHT = "#e2e8f0";

const TOOLTIP_BY_LOCALE: Record<"en" | "ko", string> = {
  en: "Korean coded as KCD-8 (95% identical to WHO ICD-10)",
  ko: "WHO ICD-10 호환 (95% 동일)",
};

const PREFIX_BY_LOCALE: Record<"en" | "ko", string> = {
  en: "ICD-10",
  ko: "KCD-8",
};

const FOOTER_NOTE_BY_LOCALE: Record<"en" | "ko", string> = {
  en: "Provenance: Korean Standard Classification of Diseases v8 (KCD-8)",
  ko: "출처: 한국표준질병사인분류 8차 (KCD-8)",
};

const ARIA_LABEL_BY_LOCALE: Record<"en" | "ko", (code: string) => string> = {
  en: (code) => `Diagnosis code ${code}, ICD-10 standard`,
  ko: (code) => `진단 코드 ${code}, KCD-8 기준`,
};

export function KCDChip({
  code,
  labelKo,
  labelEn,
  locale,
  variant = "inline",
  size = "md",
  onClick,
  className,
}: KCDChipProps): JSX.Element {
  const tooltipId = useId();
  const [tooltipOpen, setTooltipOpen] = useState(false);
  const prefix = PREFIX_BY_LOCALE[locale];
  const tooltip = TOOLTIP_BY_LOCALE[locale];
  const footerNote = FOOTER_NOTE_BY_LOCALE[locale];
  const ariaLabel = ARIA_LABEL_BY_LOCALE[locale](code);
  const labelText = locale === "ko" ? labelKo ?? "" : labelEn ?? "";

  const chipFontSize = size === "sm" ? 11 : 12;
  const chipPaddingY = 2;
  const chipPaddingX = size === "sm" ? 6 : 8;
  const labelFontSize = size === "sm" ? 12 : 14;
  const interactive = !!onClick;

  function handleKey(e: React.KeyboardEvent<HTMLSpanElement>) {
    if (!interactive) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick?.(code);
    }
  }

  return (
    <span
      className={className ?? "rv-kcd-chip-wrap"}
      data-testid="kcd-chip-wrap"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        position: "relative",
      }}
    >
      <span
        role={interactive ? "button" : undefined}
        tabIndex={interactive ? 0 : -1}
        aria-label={ariaLabel}
        aria-describedby={tooltipId}
        data-testid="kcd-chip"
        data-locale={locale}
        data-code={code}
        onClick={interactive ? () => onClick?.(code) : undefined}
        onKeyDown={handleKey}
        onMouseEnter={() => setTooltipOpen(true)}
        onMouseLeave={() => setTooltipOpen(false)}
        onFocus={() => setTooltipOpen(true)}
        onBlur={() => setTooltipOpen(false)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          padding: `${chipPaddingY}px ${chipPaddingX}px`,
          background: TEAL_BG_100,
          color: TEAL_FG_700,
          borderRadius: 999,
          fontSize: chipFontSize,
          fontWeight: 600,
          whiteSpace: "nowrap",
          cursor: interactive ? "pointer" : "default",
          fontFamily:
            "Inter, Pretendard, system-ui, -apple-system, sans-serif",
        }}
      >
        {prefix} {code}
      </span>
      {labelText ? (
        <span
          data-testid="kcd-chip-label"
          style={{
            fontSize: labelFontSize,
            color: "#0f172a",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            minWidth: 0,
          }}
        >
          {labelText}
        </span>
      ) : null}
      <span
        id={tooltipId}
        role="tooltip"
        data-testid="kcd-chip-tooltip"
        hidden={!tooltipOpen}
        style={{
          position: "absolute",
          bottom: "calc(100% + 8px)",
          left: 0,
          maxWidth: 320,
          padding: "8px 12px",
          background: TEXT_STRONG,
          color: "#ffffff",
          borderRadius: 8,
          fontSize: 12,
          fontWeight: 400,
          lineHeight: 1.4,
          boxShadow: "0 8px 16px rgba(15, 23, 42, 0.18)",
          zIndex: 60,
          display: tooltipOpen ? "block" : "none",
          pointerEvents: "none",
        }}
      >
        {tooltip}
      </span>
      {variant === "detail" ? (
        <span
          data-testid="kcd-chip-footer"
          style={{
            display: "block",
            width: "100%",
            marginTop: 4,
            fontSize: 11,
            color: TEXT_MUTED,
            borderTop: `1px solid ${BORDER_LIGHT}`,
            paddingTop: 4,
          }}
        >
          {footerNote}
        </span>
      ) : null}
    </span>
  );
}
