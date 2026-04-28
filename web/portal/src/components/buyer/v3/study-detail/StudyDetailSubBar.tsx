"use client";

/**
 * <StudyDetailSubBar> — top horizontal strip on the study-detail page
 * (mockup `.detail-subbar`).
 *
 * Shows: Back-to-search · HospitalBadge · KCD chip · Modality dot+label ·
 * UID mono · (optional Prev/Next nav).
 *
 * Prev/Next navigation requires the search context (which UIDs the buyer was
 * scrolling) so it is OPTIONAL — if not wired, the right side simply omits
 * the nav cluster (mockup ships static "3 / 250" placeholder; we don't
 * fabricate).
 */

import Link from "next/link";
import { HospitalBadge } from "@/components/buyer/v3/HospitalBadge";
import { ModalityDot } from "@/components/buyer/v3/ModalityDot";
import type { Locale } from "@/lib/i18n";

export type StudyDetailSubBarProps = {
  pseudoStudyUid: string;
  modality: string | null;
  hospitalRegionPseudo: string | null;
  kcdCode?: string | null;
  /** Optional caller-controlled prev/next handlers + position label. */
  prev?: { onClick: () => void; disabled?: boolean } | null;
  next?: { onClick: () => void; disabled?: boolean } | null;
  /** "3 / 250" position label when prev/next is wired. */
  positionLabel?: string | null;
  locale?: Locale;
};

export function StudyDetailSubBar({
  pseudoStudyUid,
  modality,
  hospitalRegionPseudo,
  kcdCode,
  prev,
  next,
  positionLabel,
  locale = "en",
}: StudyDetailSubBarProps) {
  const t =
    locale === "ko"
      ? { back: "검색으로", prev: "이전", next: "다음" }
      : { back: "Back to search", prev: "Prev", next: "Next" };

  return (
    <div
      className="rv-detail-subbar"
      data-testid="study-detail-subbar"
    >
      <div className="rv-detail-subbar__breadcrumb">
        <Link href="/search" data-testid="study-detail-back-link">
          ← {t.back}
        </Link>
      </div>
      <div className="rv-detail-subbar__title">
        {hospitalRegionPseudo ? (
          <HospitalBadge regionPseudo={hospitalRegionPseudo} />
        ) : null}
        {kcdCode ? (
          <span
            className="rv-detail-kcd-chip"
            data-testid="study-detail-kcd-chip"
          >
            {kcdCode}
          </span>
        ) : null}
        <ModalityDot modality={modality} showLabel />
        <span style={{ color: "var(--rv-stone-500)" }}>·</span>
        <span
          className="rv-col-mono"
          style={{
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            maxWidth: 360,
            display: "inline-block",
          }}
          title={pseudoStudyUid}
          data-testid="study-detail-uid"
        >
          {pseudoStudyUid}
        </span>
      </div>
      {prev || next ? (
        <div className="rv-detail-subbar__nav">
          <button
            type="button"
            disabled={!prev || prev.disabled}
            onClick={prev?.onClick}
            data-testid="study-detail-prev"
            style={navBtnStyle(!prev || Boolean(prev.disabled))}
          >
            ← {t.prev}
          </button>
          {positionLabel ? (
            <span
              style={{
                fontFamily: "JetBrains Mono, ui-monospace, monospace",
                fontSize: 11,
              }}
            >
              {positionLabel}
            </span>
          ) : null}
          <button
            type="button"
            disabled={!next || next.disabled}
            onClick={next?.onClick}
            data-testid="study-detail-next"
            style={navBtnStyle(!next || Boolean(next.disabled))}
          >
            {t.next} →
          </button>
        </div>
      ) : null}
    </div>
  );
}

function navBtnStyle(disabled: boolean): React.CSSProperties {
  return {
    padding: "3px 8px",
    fontSize: 11,
    fontWeight: 600,
    border: "1px solid var(--rv-stone-300)",
    borderRadius: 3,
    background: "#fff",
    color: disabled ? "var(--rv-stone-400)" : "var(--rv-stone-700)",
    cursor: disabled ? "default" : "pointer",
  };
}
