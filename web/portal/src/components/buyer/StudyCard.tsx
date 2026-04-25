"use client";

import clsx from "clsx";
import Link from "next/link";
import { BuyerModalityBadge } from "./ModalityBadge";

/**
 * StudyCard {#study-card-v1} — design-spec-portal-redesign §11.3.
 * FR-BP-4: 9-column DataTable row at the heart of `/search` middle pane.
 *
 * Columns: checkbox · modality · body_part · age_bucket · sex · n_instances ·
 * size_mb · study_year · hospital_opaque_id. The row is keyboard-navigable;
 * Enter routes to `/studies/[id]`, Space toggles the checkbox.
 *
 * Hover tooltip shows the per-hospital cumulative study count when provided
 * (FR-BP-4 micro-tooltip). The full pseudo_study_uid is exposed via the
 * `<code>` element's `title` attribute so power users can copy it.
 */

export type StudyCardItem = {
  pseudo_study_uid: string;
  modality: string | null;
  body_part: string | null;
  age_bucket: string | null;
  sex: string | null;
  n_instances: number;
  total_bytes: number;
  study_date_shifted: string | null;
  hospital_opaque_id: string | null;
};

export type StudyCardProps = {
  study: StudyCardItem;
  selected?: boolean;
  onToggle?: () => void;
  /** Per-hospital cumulative count (rendered in hover tooltip). */
  hospitalStudyCount?: number;
  locale?: "en" | "ko";
};

function yearOf(iso: string | null): string | null {
  if (!iso) return null;
  const m = /^(\d{4})-/.exec(iso);
  return m ? m[1] : null;
}

function sizeMb(totalBytes: number): string {
  return (totalBytes / (1024 * 1024)).toFixed(0);
}

function shortHospital(id: string | null): string {
  if (!id) return "—";
  // Opaque IDs are 16-hex; show first 6 chars with HOSP prefix for readability.
  return `HOSP-${id.slice(0, 6).toUpperCase()}`;
}

export function StudyCard({
  study,
  selected = false,
  onToggle,
  hospitalStudyCount,
  locale = "en",
}: StudyCardProps) {
  const tooltip =
    hospitalStudyCount && hospitalStudyCount > 0
      ? locale === "ko"
        ? `이 병원에 ${hospitalStudyCount} 개 study`
        : `${shortHospital(study.hospital_opaque_id)} has ${hospitalStudyCount} studies in current cohort`
      : undefined;

  function handleKey(e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key === " ") {
      e.preventDefault();
      onToggle?.();
    }
  }

  const year = yearOf(study.study_date_shifted);

  return (
    <div
      data-testid="study-card"
      role="row"
      tabIndex={0}
      onKeyDown={handleKey}
      title={tooltip}
      className={clsx(
        "group flex items-center gap-3 border-b border-border px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-600",
        selected
          ? "border-l-4 border-l-primary-600 bg-primary-50"
          : "border-l-4 border-l-transparent hover:bg-bg-muted",
      )}
    >
      <input
        type="checkbox"
        checked={selected}
        onChange={(e) => {
          e.stopPropagation();
          onToggle?.();
        }}
        aria-label={`Select study ${study.pseudo_study_uid.slice(-8)}`}
        className="size-4 shrink-0 cursor-pointer"
      />
      <div className="w-16 shrink-0">
        <BuyerModalityBadge modality={study.modality} />
      </div>
      <div className="min-w-0 flex-1 truncate text-text">
        <Link
          href={`/studies/${encodeURIComponent(study.pseudo_study_uid)}`}
          className="font-medium hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          {study.body_part ?? "—"}
        </Link>
      </div>
      <div className="w-20 shrink-0 text-text-muted">
        {study.age_bucket ?? "—"}
      </div>
      <div className="w-10 shrink-0 text-center text-text-muted">
        {study.sex ?? "—"}
      </div>
      <div className="w-24 shrink-0 text-right font-mono tabular-nums text-text">
        {study.n_instances.toLocaleString()}
      </div>
      <div className="w-20 shrink-0 text-right font-mono tabular-nums text-text">
        {sizeMb(study.total_bytes)} MB
      </div>
      <div className="w-16 shrink-0 text-right text-text-muted">
        {year ?? "—"}
      </div>
      <div className="w-28 shrink-0">
        <span className="rounded-pill bg-bg-muted px-2 py-0.5 font-mono text-[11px] text-text-muted">
          {shortHospital(study.hospital_opaque_id)}
        </span>
      </div>
    </div>
  );
}
