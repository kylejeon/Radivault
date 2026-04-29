"use client";

import { useEffect, useState } from "react";
import { SliceViewerOrFallback } from "@/components/SliceViewer";
import { type PreviewManifest } from "@/components/preview/FrameSliderViewer";
import {
  ComplianceCollapse,
  LongitudinalTimeline,
  MetaCard,
  QualityMetricsCard,
  StudyDetailSubBar,
  ViewerPaneV3,
} from "@/components/buyer/v3/study-detail";
import {
  SeriesMiniCardListV4,
  ViewerPaneV4,
  type SeriesMiniItemV4,
} from "@/components/buyer/v4/study-detail";
import type { Locale } from "@/lib/i18n";
import {
  formatBits,
  formatKv,
  formatMm,
  formatMmPair,
  formatPx,
} from "@/lib/format/units";

/**
 * StudyDetailPanel — study-detail v3 (mockup buyer-ux-v2/v3/study-detail.html).
 *
 * Layout (top → bottom):
 *
 *   1. <StudyDetailSubBar>        — back · hospital · KCD · modality · UID
 *   2. <ViewerPaneV3>             — dark canvas + 4 corner overlays
 *      · child = <FrameSliderViewer> | <SliceViewerOrFallback>
 *        | <LegacyThumbnailFallback>
 *   3. Right rail (sticky):
 *      · <QualityMetricsCard>     — 2x2 derived signals
 *      · <MetaCard kind="patient">
 *      · <MetaCard kind="study">
 *      · <SeriesMiniCardList>
 *      · <MetaCard kind="acquisition">
 *      · <MetaCard kind="pixel">
 *      · <LongitudinalTimeline>
 *      · sticky CTA — Add to cohort
 *   4. <ComplianceCollapse>       — collapsible footer (DeID stepper + audit)
 *
 * SaMD disclaimer is rendered inside <ViewerPaneV3>; the page-level sticky
 * <SaMDFooter> from `StudyDetailClient` remains for cross-route consistency.
 *
 * Backend coverage:
 *   - All 14 fields the mockup shows are slotted. Fields not yet wired to the
 *     central index (KVP, Tube current, Contrast, PixelSpacing, Slice
 *     thickness, PhotomtrInterp, FrameOfRef, Accession, IRB, anchor hash)
 *     render as "—" with a `--missing` modifier. Backend extension is a
 *     separate dev-spec; here we ship the UI skeleton.
 */

export type SeriesSummary = {
  pseudo_series_uid: string;
  modality: string | null;
  n_instances: number;
  // v3 mockup-only fields — optional, populated when backend extends:
  description?: string | null;
  slice_thickness_mm?: number | null;
  resolution_w?: number | null;
  resolution_h?: number | null;
  // dev-spec-pixel-spatial-fields FR-PSF-7.1 — Tier-1 series-level
  // fields. Optional so legacy series rows ingested before alembic 0011
  // (and the demo's pre-wipe data) keep rendering "—".
  photometric_interpretation?: string | null;
  pixel_spacing_x?: number | null;
  pixel_spacing_y?: number | null;
  rows?: number | null;
  columns?: number | null;
  bits_allocated?: number | null;
  bits_stored?: number | null;
  frame_of_reference_uid_pseudo?: string | null;
  kvp?: number | null;
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
  /**
   * Buyer-facing hospital identity (e.g., "SEOUL-A", "BUSAN-B"). Same value
   * the search results table renders via <HospitalBadge>. Falls back to a
   * `HOSP-XXXXXX` opaque short code if the upstream omits it.
   */
  hospital_region_pseudo?: string | null;
  ingested_at: string | null;
  series: SeriesSummary[];
  // FR-V3-API-2 — KCD ontology fields surfaced in the sub-bar chip + Study
  // card description. All optional (legacy studies don't have KCD).
  kcd_code?: string | null;
  kcd_label_ko?: string | null;
  kcd_label_en?: string | null;
  // Phase 1.5 free-text — optional study description / protocol name.
  study_description?: string | null;
  protocol_name?: string | null;
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

const MISSING = "—";

function shortHospital(id: string | null): string {
  if (!id) return MISSING;
  return `HOSP-${id.slice(0, 6).toUpperCase()}`;
}

function patientPseudoFromUid(uid: string): string {
  // Stable, opaque, deterministic pseudo derived from the study UID tail. The
  // central pipeline issues a real per-patient pseudo at ingest; until that
  // surfaces in the search detail response we synthesise a display-only token
  // so the cohort timeline title is never empty. Kept short on purpose so
  // nobody mistakes it for a real medical record number.
  const tail = uid.replace(/[^A-Za-z0-9]/g, "").slice(-6).toUpperCase();
  return tail ? `PT-${tail}` : "PT-—";
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
          add: "+ 코호트에 추가",
          inCohort: "✓ 이미 코호트에 있음",
          ctaHint:
            "코호트에 담아 /orders/new 에서 전체 study 배송 계약을 검토하세요. 본 페이지의 미리보기는 SaMD 면책 대상입니다.",
          patient: "환자",
          patientPseudoId: "가명 ID",
          patientSex: "성별",
          patientAge: "나이 (세)",
          patientConsent: "동의",
          study: "검사",
          examDate: "촬영일 (시프트)",
          accession: "접수",
          description: "설명",
          modality: "모달리티",
          bodyPart: "부위",
          acquisition: "획득 정보",
          manufacturer: "제조사",
          model: "모델",
          kvp: "KVP",
          tubeCurrent: "관전류",
          contrast: "조영제",
          pixelTitle: "픽셀 · 공간",
          photomtr: "PhotomtrInterp",
          pixelSpacing: "PixelSpacing",
          frameOfRef: "FrameOfRef",
          sliceThickness: "슬라이스 두께",
          resolution: "해상도",
          bits: "Bits (할당 / 저장)",
        }
      : {
          add: "+ Add to cohort",
          inCohort: "✓ Already in cohort",
          ctaHint:
            "Add this study to your cohort and review full delivery in /orders/new. Previews on this page are subject to the SaMD disclaimer.",
          patient: "Patient",
          patientPseudoId: "Pseudo ID",
          patientSex: "Sex",
          patientAge: "Age (years)",
          patientConsent: "Consent",
          study: "Study",
          examDate: "Exam Date (shifted)",
          accession: "Accession",
          description: "Description",
          modality: "Modality",
          bodyPart: "Body part",
          acquisition: "Acquisition",
          manufacturer: "Manufacturer",
          model: "Model",
          kvp: "KVP (CT)",
          tubeCurrent: "Tube current",
          contrast: "Contrast",
          pixelTitle: "Pixel & spatial",
          photomtr: "PhotomtrInterp",
          pixelSpacing: "PixelSpacing",
          frameOfRef: "FrameOfRef",
          sliceThickness: "Slice thickness",
          resolution: "Resolution",
          bits: "Bits (alloc / stored)",
        };

  const previewStatus = study.preview_status ?? "pending";
  const sliceCount = study.preview_slice_count ?? 1;

  // jpg-preview-defacing FR-API-2 — fetch preview manifest in parallel.
  // ``previewManifest === null``      => still loading.
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

  // FR-DV-2.5 — active series UID lifted to panel level so the v4 viewer
  // and the right-rail SERIES card mirror each other.
  const [activeSeriesUid, setActiveSeriesUid] = useState<string | null>(null);
  useEffect(() => {
    if (!previewManifest) return;
    if (activeSeriesUid) return;
    const firstGenerated = previewManifest.series.find(
      (s) => s.preview_status === "generated",
    );
    if (firstGenerated) setActiveSeriesUid(firstGenerated.pseudo_series_uid);
    else if (previewManifest.series.length > 0) {
      setActiveSeriesUid(previewManifest.series[0].pseudo_series_uid);
    }
  }, [previewManifest, activeSeriesUid]);

  // FR-DV-1.4 / page-scoped CSS — opt the body into the v4 layout overrides
  // (compliance footer compactness, viewport clamp). Cleared on unmount so
  // any other route keeps the v3 surface intact.
  useEffect(() => {
    if (typeof document === "undefined") return;
    const prev = document.body.dataset.page;
    document.body.dataset.page = "study-detail-v4";
    return () => {
      if (prev != null) document.body.dataset.page = prev;
      else delete document.body.dataset.page;
    };
  }, []);

  // ---------------------------------------------------------------
  // Derived display values for the right-rail cards.
  // ---------------------------------------------------------------
  const hospitalRegion =
    study.hospital_region_pseudo ?? shortHospital(study.hospital_opaque_id);
  const patientPseudo = patientPseudoFromUid(study.pseudo_study_uid);
  const totalMb = (study.total_bytes / (1024 * 1024)).toFixed(1);

  // KCD chip in sub-bar: prefer locale-matched label tooltip.
  const kcdLabel =
    locale === "ko"
      ? study.kcd_label_ko ?? study.kcd_label_en
      : study.kcd_label_en ?? study.kcd_label_ko;
  const studyDescription =
    study.study_description ?? study.protocol_name ?? null;

  // Series mini items — when the preview manifest is available, drive the
  // right-rail list off of IT (same order + indexing as the left
  // <SeriesPicker> dropdown so row "13" in the rail is row "13" in the
  // dropdown). Study-endpoint metadata (slice_thickness, resolution,
  // description) is merged in by pseudo_series_uid. Pre-manifest fallback
  // keeps using study.series so the rail still renders during the brief
  // initial load. Kyle 2026-04-28 — left/right out of sync because the
  // two endpoints returned series in different orders.
  const studyByUid: Record<string, (typeof study.series)[number]> = {};
  for (const s of study.series) {
    studyByUid[s.pseudo_series_uid] = s;
  }
  // dev-spec-pixel-spatial-fields FR-PSF-8.5 — active series lookup so
  // the Pixel & Spatial / Acquisition cards re-bind on series picker
  // change. Falls back to the first series when activeSeriesUid is
  // null (initial render / no preview manifest yet).
  const activeSeries: SeriesSummary | undefined =
    (activeSeriesUid && studyByUid[activeSeriesUid]) ||
    study.series[0] ||
    undefined;

  const seriesItems: SeriesMiniItemV4[] = previewManifest
    ? previewManifest.series.map((m) => {
        const s = studyByUid[m.pseudo_series_uid];
        return {
          pseudo_series_uid: m.pseudo_series_uid,
          modality: s?.modality ?? m.modality,
          n_instances: s?.n_instances ?? m.frame_count ?? 0,
          description: s?.description ?? null,
          slice_thickness_mm: s?.slice_thickness_mm ?? null,
          resolution_w: s?.resolution_w ?? null,
          resolution_h: s?.resolution_h ?? null,
          preview_status: m.preview_status ?? null,
        };
      })
    : study.series.map((s) => ({
        pseudo_series_uid: s.pseudo_series_uid,
        modality: s.modality,
        n_instances: s.n_instances,
        description: s.description ?? null,
        slice_thickness_mm: s.slice_thickness_mm ?? null,
        resolution_w: s.resolution_w ?? null,
        resolution_h: s.resolution_h ?? null,
        preview_status: null,
      }));

  // Viewer overlays — use real values where available; corners not populated
  // simply omit lines rather than printing "—" inside dark overlays (those
  // would look like data, not absence).
  const overlayTopLeft = (
    <>
      {[hospitalRegion, study.modality].filter(Boolean).join(" · ") || null}
      {study.preview_slice_count != null ? (
        <>
          <br />
          slice {Math.max(1, Math.floor(sliceCount / 2))} / {sliceCount}
        </>
      ) : null}
    </>
  );
  const overlayTopRight = (
    <>
      {[study.manufacturer, study.model_name].filter(Boolean).join(" · ") ||
        null}
      {study.study_date_shifted ? (
        <>
          <br />
          {study.study_date_shifted} (shifted)
        </>
      ) : null}
    </>
  );
  const overlayBottomLeft = (
    <>
      {[study.sex, study.patient_age].filter((v) => v != null).join(" · ") ||
        null}
      <br />
      pseudo {patientPseudo}
    </>
  );

  return (
    <div data-testid="study-detail-panel" style={{ width: "100%" }}>
      {/* 1. Sub-bar (back · hospital · KCD · modality · UID) */}
      <StudyDetailSubBar
        pseudoStudyUid={study.pseudo_study_uid}
        modality={study.modality}
        hospitalRegionPseudo={study.hospital_region_pseudo ?? null}
        kcdCode={study.kcd_code ?? null}
        locale={locale}
      />

      {/* 2. Main 2-col layout — viewer + right rail */}
      <main className="rv-layout-detail">
        {/* Left: viewer pane */}
        {previewManifest === null ? (
          <ViewerPaneV3
            topLeft={overlayTopLeft}
            topRight={overlayTopRight}
            bottomLeft={overlayBottomLeft}
            bottomRight={null}
            locale={locale}
          >
            <div
              data-testid="study-detail-viewer-skeleton"
              style={{
                width: "100%",
                height: "100%",
                minHeight: 480,
                background: "#0f172a",
              }}
            />
          </ViewerPaneV3>
        ) : previewManifest === undefined ? (
          <ViewerPaneV3
            topLeft={overlayTopLeft}
            topRight={overlayTopRight}
            bottomLeft={overlayBottomLeft}
            bottomRight={null}
            locale={locale}
          >
            {previewStatus === "verified" ? (
              <SliceViewerOrFallback
                studyUid={study.pseudo_study_uid}
                sliceCount={sliceCount}
                previewStatus={previewStatus}
                modality={study.modality}
                locale={locale}
              />
            ) : (
              <LegacyThumbnailFallback
                studyUid={study.pseudo_study_uid}
                previewStatus={previewStatus}
                modality={study.modality}
                locale={locale}
              />
            )}
          </ViewerPaneV3>
        ) : (
          <ViewerPaneV4
            studyUid={study.pseudo_study_uid}
            manifest={previewManifest}
            activeSeriesUid={activeSeriesUid}
            onActiveSeriesChange={setActiveSeriesUid}
            overlayTopLeft={overlayTopLeft}
            overlayTopRight={overlayTopRight}
            overlayBottomLeft={overlayBottomLeft}
            overlayBottomRight={null}
            locale={locale}
          />
        )}

        {/* Right rail */}
        <aside className="rv-right-rail" aria-label="Study metadata">
          <QualityMetricsCard
            imageCount={study.n_instances}
            seriesCount={study.n_series}
            sliceThicknessMm={null /* TODO surface from raw_dicom_tags(0018,0050) */}
            resolutionWidth={null /* TODO surface from raw_dicom_tags(0028,0010) */}
            resolutionHeight={null /* TODO surface from raw_dicom_tags(0028,0011) */}
            pixelSpacingMm={null /* TODO surface from raw_dicom_tags(0028,0030) */}
            completenessPct={null /* TODO compute from 12-field fill rate */}
            locale={locale}
          />

          {/* Metadata cards — Patient / Study / Series / Acquisition / Pixel */}
          <section
            className="rv-detail-section"
            data-testid="study-detail-meta-section"
          >
            <div className="rv-detail-section__title">
              <span>{locale === "ko" ? "메타데이터" : "Metadata"}</span>
              <span
                style={{
                  fontFamily: "JetBrains Mono, ui-monospace, monospace",
                  fontSize: 10,
                  color: "var(--rv-stone-500)",
                  textTransform: "none",
                  letterSpacing: 0,
                }}
              >
                {totalMb} MB · {study.n_instances.toLocaleString()}{" "}
                {locale === "ko" ? "인스턴스" : "inst"}
              </span>
            </div>

            <MetaCard
              title={t.patient}
              slug="patient"
              rows={[
                {
                  key: "pseudo-id",
                  label: t.patientPseudoId,
                  value: patientPseudo,
                },
                { key: "sex", label: t.patientSex, value: study.sex },
                {
                  key: "age",
                  label: t.patientAge,
                  value:
                    study.patient_age != null
                      ? String(study.patient_age)
                      : null,
                },
                {
                  key: "consent",
                  label: t.patientConsent,
                  value: "PIPA §28-8",
                },
              ]}
            />

            <MetaCard
              title={t.study}
              slug="study"
              rows={[
                {
                  key: "exam-date",
                  label: t.examDate,
                  value: study.study_date_shifted,
                },
                {
                  key: "accession",
                  label: t.accession,
                  value: locale === "ko" ? "마스킹됨" : "masked",
                },
                {
                  key: "description",
                  label: t.description,
                  value: studyDescription ?? kcdLabel ?? null,
                },
                {
                  key: "modality",
                  label: t.modality,
                  value: study.modality,
                },
                {
                  key: "body-part",
                  label: t.bodyPart,
                  value: study.body_part,
                },
              ]}
            />

            <SeriesMiniCardListV4
              series={seriesItems}
              activeSeriesUid={activeSeriesUid}
              onSelect={setActiveSeriesUid}
              locale={locale}
            />

            <MetaCard
              title={t.acquisition}
              slug="acquisition"
              rows={[
                {
                  key: "manufacturer",
                  label: t.manufacturer,
                  value: study.manufacturer,
                },
                { key: "model", label: t.model, value: study.model_name },
                {
                  // dev-spec-pixel-spatial-fields FR-PSF-8.2 — Tier-1
                  // KVP is series-level. Falls back to "—" via formatKv
                  // when null.
                  key: "kvp",
                  label: t.kvp,
                  value: formatKv(activeSeries?.kvp ?? null),
                },
                {
                  // Tier-2 (out of scope for this task) — keep TODO
                  // anchor so the follow-up ticket has a one-touch
                  // landing spot.
                  key: "tube-current",
                  label: t.tubeCurrent,
                  value: null /* TODO Tier-2 (0018,1151) */,
                },
                {
                  key: "contrast",
                  label: t.contrast,
                  value: null /* TODO Tier-2 (0018,0010) */,
                },
              ]}
            />

            <MetaCard
              title={t.pixelTitle}
              slug="pixel"
              rows={[
                {
                  // dev-spec-pixel-spatial-fields FR-PSF-8.1 / FR-PSF-8.7
                  // — Tier-1 Pixel & Spatial card binding. Order follows
                  // mockup (PhotomtrInterp -> PixelSpacing ->
                  // SliceThickness -> Resolution -> Bits -> FrameOfRef).
                  key: "photomtr",
                  label: t.photomtr,
                  value: activeSeries?.photometric_interpretation ?? null,
                },
                {
                  key: "pixel-spacing",
                  label: t.pixelSpacing,
                  value: formatMmPair(
                    activeSeries?.pixel_spacing_x ?? null,
                    activeSeries?.pixel_spacing_y ?? null,
                  ),
                },
                {
                  key: "slice-thickness",
                  label: t.sliceThickness,
                  value: formatMm(activeSeries?.slice_thickness_mm ?? null),
                },
                {
                  key: "resolution",
                  label: t.resolution,
                  value: formatPx(
                    activeSeries?.rows ?? null,
                    activeSeries?.columns ?? null,
                  ),
                },
                {
                  key: "bits",
                  label: t.bits,
                  value: formatBits(
                    activeSeries?.bits_allocated ?? null,
                    activeSeries?.bits_stored ?? null,
                  ),
                },
                {
                  key: "frame-of-ref",
                  label: t.frameOfRef,
                  value: activeSeries?.frame_of_reference_uid_pseudo ?? null,
                },
              ]}
            />
          </section>

          <div className="rv-detail-section--longitudinal-v42">
            <LongitudinalTimeline
              patientPseudoId={patientPseudo}
              steps={null /* TODO backend: fetch related studies for patient */}
              locale={locale}
            />
          </div>

          {/* Sticky CTA — single primary (Sample download + hint removed
              v0.3 of design-spec, Kyle 2026-04-28). z-index 4 + isolation
              fix vs longitudinal timeline dots stack-bleed. */}
          <div className="rv-detail-cta rv-detail-cta--v42">
            <button
              type="button"
              onClick={onAddToCohort}
              disabled={alreadyInCohort}
              data-testid="add-to-cohort"
              style={{
                width: "100%",
                padding: "10px 14px",
                background: alreadyInCohort
                  ? "var(--rv-stone-200)"
                  : "var(--rv-navy-900)",
                color: alreadyInCohort ? "var(--rv-stone-500)" : "#fff",
                border: "1px solid transparent",
                borderRadius: "var(--rv-radius-md)",
                fontSize: 13,
                fontWeight: 600,
                cursor: alreadyInCohort ? "default" : "pointer",
              }}
            >
              {alreadyInCohort ? t.inCohort : t.add}
            </button>
          </div>
        </aside>
      </main>

      {/* 4. Compliance & audit footer (default-collapsed) */}
      <ComplianceCollapse
        ingestedAt={study.ingested_at}
        hospitalIrb={null /* TODO backend audit chain */}
        consentType={"broad · PIPA §28-8"}
        anchorHash={null /* TODO audit chain */}
        chainStatus={null /* TODO audit chain */}
        chainEventCount={null}
        wormRetentionYears={5}
        rulesetVersion={null /* TODO surface from gateway pipeline */}
        runAt={null}
        locale={locale}
      />
    </div>
  );
}

/**
 * <LegacyThumbnailFallback> — used when the new jpg-preview-defacing
 * manifest is unavailable (legacy study) AND `preview_status` is not yet
 * `verified`. Renders the existing per-study mid-slice thumbnail so the
 * viewer slot isn't an empty placeholder. A small caption surfaces the
 * `PHI verification pending` state.
 */
function LegacyThumbnailFallback({
  studyUid,
  previewStatus,
  modality,
  locale = "en",
}: {
  studyUid: string;
  previewStatus: "pending" | "phi_detected" | "not_applicable";
  modality?: string | null;
  locale?: Locale;
}) {
  const [errored, setErrored] = useState(false);
  const t =
    locale === "ko"
      ? {
          captionPending:
            "PHI 검증 대기 중 — 대표 슬라이스 한 장만 표시됩니다.",
          captionPhi: "PHI 가 감지되어 미리보기가 차단되었습니다.",
          captionNa: modality
            ? `${modality} 모달리티는 슬라이스 미리보기를 제공하지 않습니다.`
            : "이 모달리티는 슬라이스 미리보기를 제공하지 않습니다.",
          alt: "대표 슬라이스 미리보기",
        }
      : {
          captionPending:
            "PHI verification pending — single representative slice shown.",
          captionPhi: "Preview blocked: PHI detected on burned-in pixels.",
          captionNa: modality
            ? `${modality} modality does not produce slice previews.`
            : "This modality does not produce slice previews.",
          alt: "Representative slice preview",
        };
  const caption =
    previewStatus === "phi_detected"
      ? t.captionPhi
      : previewStatus === "not_applicable"
        ? t.captionNa
        : t.captionPending;

  if (errored || previewStatus === "phi_detected") {
    // Phi-detected studies must NOT show the thumbnail.
    return (
      <SliceViewerOrFallback
        studyUid={studyUid}
        sliceCount={1}
        previewStatus={previewStatus}
        modality={modality}
        locale={locale}
      />
    );
  }

  return (
    <div
      data-testid="legacy-thumbnail-fallback"
      style={{
        height: "100%",
        width: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 12,
        padding: 16,
        background: "#000",
      }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={`/api/studies/${encodeURIComponent(studyUid)}/thumbnail`}
        alt={t.alt}
        onError={() => setErrored(true)}
        style={{
          maxHeight: 460,
          maxWidth: "100%",
          borderRadius: 4,
          border: "1px solid rgba(255,255,255,0.08)",
          objectFit: "contain",
          background: "#000",
        }}
      />
      <p
        style={{
          fontSize: 11,
          color: "rgba(255,255,255,0.6)",
          textAlign: "center",
        }}
      >
        {caption}
      </p>
    </div>
  );
}

/**
 * ViewerStub — design-spec §11.4. Placeholder for the future DICOM viewer.
 * Kept exported for back-compat with any caller still importing it from this
 * module.
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
