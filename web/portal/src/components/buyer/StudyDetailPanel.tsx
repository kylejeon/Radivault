"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BuyerModalityBadge } from "./ModalityBadge";
import { SliceViewerOrFallback } from "@/components/SliceViewer";
import { SampleDownloadButton } from "@/components/preview/SampleDownloadButton";
import {
  FrameSliderViewer,
  type PreviewManifest,
} from "@/components/preview/FrameSliderViewer";
import {
  QuotaIndicator,
  type QuotaState,
} from "@/components/preview/QuotaIndicator";
import { getDict, type Locale } from "@/lib/i18n";

/**
 * StudyDetailPanel {#study-detail-v1} — design-spec-portal-redesign §11.4
 * extended by design-spec-buyer-browse-preview §7.
 *
 * Layout (top→bottom):
 *
 *   1. Header bar (back link · UID · "Add to cohort").
 *   2. Hospital origin row.
 *   3. Main grid 1fr · 320px:
 *      - Left  : SliceViewer (verified) | ModalityFallback
 *      - Right : Sample download CTA · Quota · Cohort CTA · Series list
 *   4. Metadata 2-col grid (StudyItem fields).
 *
 * SaMD footer is owned by the page wrapper (StudyDetailClient), not this
 * component, because it needs to be page-sticky.
 */

export type SeriesSummary = {
  pseudo_series_uid: string;
  modality: string | null;
  n_instances: number;
};

export type StudyDetail = {
  pseudo_study_uid: string;
  modality: string | null;
  body_part: string | null;
  age_bucket: string | null;
  patient_age: number | null;
  sex: string | null;
  study_date_shifted: string | null;
  manufacturer: string | null;
  model_name: string | null;
  n_instances: number;
  n_series: number;
  total_bytes: number;
  hospital_opaque_id: string | null;
  ingested_at: string | null;
  series: SeriesSummary[];
  // dev-spec-buyer-browse-preview FR-DATA-1 — when absent, we treat the
  // study as 'pending' (safe default) so the viewer falls back.
  preview_status?:
    | "verified"
    | "pending"
    | "phi_detected"
    | "not_applicable"
    | null;
  preview_slice_count?: number | null;
};

export type StudyDetailPanelProps = {
  study: StudyDetail;
  onAddToCohort?: () => void;
  alreadyInCohort?: boolean;
  locale?: Locale;
};

function shortHospital(id: string | null): string {
  if (!id) return "—";
  return `HOSP-${id.slice(0, 6).toUpperCase()}`;
}

export function StudyDetailPanel({
  study,
  onAddToCohort,
  alreadyInCohort,
  locale = "en",
}: StudyDetailPanelProps) {
  const dict = getDict(locale);
  const t =
    locale === "ko"
      ? {
          back: "← 결과로 돌아가기",
          add: "코호트에 추가",
          inCohort: "✓ 이미 코호트에 있음",
          metaTitle: "STUDY 메타데이터",
          seriesTitle: "SERIES",
          modality: "모달리티",
          bodyPart: "신체 부위",
          age: "연령",
          sex: "성별",
          manufacturer: "제조사",
          model: "모델",
          studyDate: "촬영 일자",
          totalBytes: "총 용량",
          instances: "인스턴스 수",
          seriesCount: "시리즈 수",
          ingested: "수집 시각",
          hospital: "이 병원의 보유 study 수",
          viewAll: "이 병원 전체 보기 →",
        }
      : {
          back: "← Back to results",
          add: "+ Add to cohort",
          inCohort: "✓ Already in cohort",
          metaTitle: "STUDY METADATA",
          seriesTitle: "SERIES",
          modality: "Modality",
          bodyPart: "Body Part",
          age: "Age",
          sex: "Sex",
          manufacturer: "Manufacturer",
          model: "Model",
          studyDate: "Study Date",
          totalBytes: "Total Bytes",
          instances: "Instance Count",
          seriesCount: "Series Count",
          ingested: "Ingested",
          hospital: "From this hospital",
          viewAll: "view all from this hospital →",
        };

  const totalMb = (study.total_bytes / (1024 * 1024)).toFixed(1);
  const previewStatus = study.preview_status ?? "pending";
  const sliceCount = study.preview_slice_count ?? 1;

  // Quota state — fetched on mount + bumped optimistically by the
  // SampleDownloadButton via onQuotaUpdate.
  const [quota, setQuota] = useState<QuotaState | null>(null);
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const res = await fetch("/api/account/quota");
        if (!active) return;
        if (!res.ok) return;
        const body = (await res.json()) as {
          daily_used: number;
          daily_limit: number;
          resets_at: string | null;
        };
        setQuota({
          used: body.daily_used,
          limit: body.daily_limit,
          resetsAtIso: body.resets_at,
        });
      } catch {
        /* tolerate — UI will show skeleton */
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  // jpg-preview-defacing FR-API-2 — fetch preview manifest in parallel
  // with the study fetch (already done by parent client). 404 means the
  // study predates the new pipeline (FR-NEWONLY-2 silent coexistence)
  // so we fall back to the existing SliceViewerOrFallback.
  // ``previewManifest === null`` => still loading.
  // ``previewManifest === undefined`` => 404 / unavailable, fall back.
  const [previewManifest, setPreviewManifest] = useState<
    PreviewManifest | null | undefined
  >(null);
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const res = await fetch(
          `/api/studies/${encodeURIComponent(
            study.pseudo_study_uid,
          )}/preview-manifest`,
        );
        if (!active) return;
        if (res.status === 404) {
          setPreviewManifest(undefined);
          return;
        }
        if (!res.ok) {
          // Other failures: treat as legacy / fall back. Keeps the
          // page resilient when search service has the new endpoint
          // disabled.
          setPreviewManifest(undefined);
          return;
        }
        const body = (await res.json()) as PreviewManifest;
        setPreviewManifest(body);
      } catch {
        if (active) setPreviewManifest(undefined);
      }
    })();
    return () => {
      active = false;
    };
  }, [study.pseudo_study_uid]);

  return (
    <div data-testid="study-detail-panel" className="flex flex-col gap-5">
      {/* 1. Header bar */}
      <header className="sticky top-16 z-10 -mx-6 flex items-center justify-between gap-4 border-b border-border bg-bg px-6 py-3">
        <div className="flex items-center gap-4">
          <Link
            href="/search"
            className="text-sm text-primary-700 hover:underline"
          >
            {t.back}
          </Link>
          <code
            className="font-mono text-xs text-text-muted"
            title={study.pseudo_study_uid}
          >
            UID: {study.pseudo_study_uid}
          </code>
        </div>
        <button
          type="button"
          onClick={onAddToCohort}
          disabled={alreadyInCohort}
          data-testid="add-to-cohort"
          className="rounded-md bg-primary-600 px-3 py-1.5 text-sm font-semibold text-white disabled:bg-bg-muted disabled:text-text-muted"
        >
          {alreadyInCohort ? t.inCohort : t.add}
        </button>
      </header>

      {/* 2. Hospital origin */}
      <div className="flex items-center gap-2 rounded-md bg-bg-muted px-4 py-2 text-sm">
        <span aria-hidden className="text-primary-600">◆</span>
        <span className="font-mono text-text">
          {shortHospital(study.hospital_opaque_id)}
        </span>
        <span className="text-text-muted">· {t.hospital}</span>
      </div>

      {/* 3. Viewer + Sidebar grid (design-spec §7.6) */}
      <div className="grid grid-cols-1 gap-5 desktop:grid-cols-[minmax(0,1fr)_320px]">
        {previewManifest === null ? (
          // Loading manifest — show a small skeleton in the viewer slot.
          <div
            data-testid="study-detail-viewer-skeleton"
            className="h-96 animate-pulse rounded-md bg-bg-muted"
          />
        ) : previewManifest === undefined ? (
          // Manifest 404 / unavailable — legacy study, fall back to
          // the existing SliceViewerOrFallback (FR-NEWONLY-3 silent
          // coexistence).
          <SliceViewerOrFallback
            studyUid={study.pseudo_study_uid}
            sliceCount={sliceCount}
            previewStatus={previewStatus}
            modality={study.modality}
            locale={locale}
          />
        ) : (
          // jpg-preview-defacing — buyer sees the per-frame slider with
          // the AFNI-defaced (or anatomy-clear) frames. Manifest itself
          // tells the component how to branch on per-series state.
          <FrameSliderViewer
            studyUid={study.pseudo_study_uid}
            manifest={previewManifest}
            locale={locale}
          />
        )}
        <aside className="flex flex-col gap-4">
          {/* Sample download card */}
          <section
            data-testid="sample-download-card"
            className="rounded-md border border-border bg-bg p-4"
          >
            <h3 className="mb-3 text-sm font-semibold text-text">
              {dict.sampleDownload.sectionTitle}
            </h3>
            <SampleDownloadButton
              studyUid={study.pseudo_study_uid}
              previewStatus={previewStatus}
              quota={quota}
              onQuotaUpdate={setQuota}
              locale={locale}
            />
            <p className="mt-2 text-xs text-text-muted">
              {dict.sampleDownload.description}
            </p>
            <div className="mt-3">
              <QuotaIndicator state={quota} variant="inline" locale={locale} />
            </div>
          </section>

          {/* Cohort card — visually separated (design-spec §9.2) */}
          <section
            data-testid="cohort-card"
            className="rounded-md border border-border bg-bg p-4"
          >
            <h3 className="mb-3 text-sm font-semibold text-text">
              {dict.cohortCta.sectionTitle}
            </h3>
            <button
              type="button"
              onClick={onAddToCohort}
              disabled={alreadyInCohort}
              data-testid="add-to-cohort-sidebar"
              className="inline-flex w-full items-center justify-center gap-2 rounded-md border border-border-strong px-4 py-3 text-sm font-medium text-text hover:bg-bg-muted disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span aria-hidden>+</span>
              <span>{alreadyInCohort ? t.inCohort : t.add}</span>
            </button>
            <p className="mt-2 text-xs text-text-muted">
              {dict.cohortCta.description}
            </p>
          </section>

          {/* Series list */}
          <section className="rounded-md border border-border bg-bg p-4">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-muted">
              {t.seriesTitle} ({study.series.length})
            </h3>
            {study.series.length === 0 ? (
              <p className="text-sm text-text-muted">—</p>
            ) : (
              <ul className="flex flex-col divide-y divide-border text-sm">
                {study.series.map((s, i) => (
                  <li
                    key={s.pseudo_series_uid}
                    className="flex items-center justify-between gap-2 py-2"
                  >
                    <span className="text-text-muted">{i + 1}</span>
                    <code
                      className="flex-1 truncate font-mono text-xs text-text"
                      title={s.pseudo_series_uid}
                    >
                      …{s.pseudo_series_uid.slice(-10)}
                    </code>
                    <BuyerModalityBadge modality={s.modality} size="sm" />
                    <span className="font-mono text-xs text-text-muted">
                      {s.n_instances}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>

      {/* 4. Metadata grid */}
      <div className="grid grid-cols-1 gap-5 desktop:grid-cols-1">
        <section className="rounded-md border border-border bg-bg p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-muted">
            {t.metaTitle}
          </h2>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm desktop:grid-cols-4">
            <MetaRow label={t.modality}>
              <BuyerModalityBadge modality={study.modality} />
            </MetaRow>
            <MetaRow label={t.bodyPart}>{study.body_part ?? "—"}</MetaRow>
            <MetaRow label={t.age}>
              {study.patient_age != null ? String(study.patient_age) : "—"}
            </MetaRow>
            <MetaRow label={t.sex}>{study.sex ?? "—"}</MetaRow>
            <MetaRow label={t.manufacturer}>
              {study.manufacturer ?? "—"}
            </MetaRow>
            <MetaRow label={t.model}>{study.model_name ?? "—"}</MetaRow>
            <MetaRow label={t.studyDate}>
              {study.study_date_shifted ?? "—"}
            </MetaRow>
            <MetaRow label={t.totalBytes}>
              <span className="font-mono">{totalMb} MB</span>
            </MetaRow>
            <MetaRow label={t.instances}>
              <span className="font-mono">{study.n_instances.toLocaleString()}</span>
            </MetaRow>
            <MetaRow label={t.seriesCount}>
              <span className="font-mono">{study.n_series}</span>
            </MetaRow>
          </dl>
        </section>
      </div>
    </div>
  );
}

function MetaRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <>
      <dt className="text-xs text-text-muted">{label}</dt>
      <dd className="text-sm text-text">{children}</dd>
    </>
  );
}

/**
 * ViewerStub — design-spec §11.4. Placeholder for the future DICOM viewer.
 */
export function ViewerStub({ locale = "en" }: { locale?: "en" | "ko" }) {
  const t =
    locale === "ko"
      ? {
          title: "DICOM 뷰어 — v0.1 미포함",
          body: "픽셀 데이터는 주문 처리 후 제공됩니다.",
          cta: "뷰어 통합 데모 요청 →",
        }
      : {
          title: "DICOM viewer not included in v0.1.",
          body: "Pixel data available after order fulfillment.",
          cta: "Request viewer integration demo →",
        };
  return (
    <div
      data-testid="viewer-stub"
      className="flex flex-col items-center gap-3 rounded-lg bg-bg-muted px-6 py-12 text-center"
    >
      <div
        aria-hidden
        className="text-4xl text-text-muted"
        style={{ lineHeight: 1 }}
      >
        ▣
      </div>
      <h3 className="text-base font-medium text-text">{t.title}</h3>
      <p className="text-sm text-text-muted">{t.body}</p>
      <a
        href="mailto:sales@radivault.io?subject=Viewer%20integration%20demo"
        className="mt-2 text-sm font-medium text-primary-700 hover:underline"
      >
        {t.cta}
      </a>
    </div>
  );
}
