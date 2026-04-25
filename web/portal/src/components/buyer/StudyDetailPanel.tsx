"use client";

import Link from "next/link";
import { BuyerModalityBadge } from "./ModalityBadge";

/**
 * StudyDetailPanel {#study-detail-v1} — design-spec-portal-redesign §11.4.
 * FR-BP-8: full-page study detail at `/studies/[id]`. Sections (top→bottom):
 *
 *   1. Header bar (back link · UID · "Add to cohort").
 *   2. Hospital origin row.
 *   3. Metadata 2-col grid (StudyItem fields).
 *   4. Series list table (SearchStudyDetail.series).
 *   5. ViewerStub placeholder ("DICOM viewer not included in v0.1").
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
};

export type StudyDetailPanelProps = {
  study: StudyDetail;
  onAddToCohort?: () => void;
  alreadyInCohort?: boolean;
  locale?: "en" | "ko";
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
  const t =
    locale === "ko"
      ? {
          back: "← 결과로 돌아가기",
          add: "코호트에 추가",
          inCohort: "✓ 이미 코호트에 있음",
          metaTitle: "STUDY 메타데이터",
          seriesTitle: "SERIES",
          viewerTitle: "DICOM 뷰어 — v0.1 미포함",
          viewerBody: "픽셀 데이터는 주문 처리 후 제공됩니다.",
          viewerCta: "뷰어 통합 데모 요청 →",
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
          viewerTitle: "DICOM viewer not included in v0.1.",
          viewerBody: "Pixel data available after order fulfillment.",
          viewerCta: "Request viewer integration demo →",
          modality: "Modality",
          bodyPart: "Body Part",
          age: "Age Bucket",
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

      {/* 3. Metadata + Series */}
      <div className="grid grid-cols-1 gap-5 desktop:grid-cols-2">
        <section className="rounded-md border border-border bg-bg p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-muted">
            {t.metaTitle}
          </h2>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <MetaRow label={t.modality}>
              <BuyerModalityBadge modality={study.modality} />
            </MetaRow>
            <MetaRow label={t.bodyPart}>{study.body_part ?? "—"}</MetaRow>
            <MetaRow label={t.age}>{study.age_bucket ?? "—"}</MetaRow>
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

        <section className="rounded-md border border-border bg-bg p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-muted">
            {t.seriesTitle} ({study.series.length})
          </h2>
          {study.series.length === 0 ? (
            <p className="text-sm text-text-muted">—</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-xs uppercase text-text-muted">
                <tr>
                  <th className="pb-2 text-left">#</th>
                  <th className="pb-2 text-left">UID</th>
                  <th className="pb-2 text-left">Mod</th>
                  <th className="pb-2 text-right">Inst</th>
                </tr>
              </thead>
              <tbody>
                {study.series.map((s, i) => (
                  <tr key={s.pseudo_series_uid} className="border-t border-border">
                    <td className="py-1.5 text-text-muted">{i + 1}</td>
                    <td className="py-1.5 font-mono text-xs text-text">
                      …{s.pseudo_series_uid.slice(-12)}
                    </td>
                    <td className="py-1.5">
                      <BuyerModalityBadge modality={s.modality} size="sm" />
                    </td>
                    <td className="py-1.5 text-right font-mono">
                      {s.n_instances}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>

      {/* 5. ViewerStub */}
      <ViewerStub locale={locale} />
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
