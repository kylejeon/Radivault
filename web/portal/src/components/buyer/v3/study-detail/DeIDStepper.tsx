"use client";

/**
 * <DeIDStepper> — 5-stage de-identification chain visual (mockup `.deid-stepper`).
 *
 * Used inside <ComplianceCollapse>; demoted from a sticky right-rail in v2 to
 * an opt-in collapsed footer block in v3 because buyers don't need PHI scrub
 * provenance to make a purchase decision (mockup index.html v2→v3 axis A3).
 *
 * Stages are hard-coded (the pipeline implements exactly these 5: PHI tag
 * scrub, UID re-gen, date shift, burn-in OCR, 3D defacing). Per-stage hash +
 * status would normally come from the central audit chain — for now the UI
 * surfaces the labels only; hashes show "—" so we do not fabricate values.
 */

import type { Locale } from "@/lib/i18n";

export type DeIDStage = {
  /** 1-based stage number (1..5). */
  num: number;
  /** Truncated 4-char hash (e.g. ``"a3f0…"``) or null when not yet wired. */
  hash?: string | null;
  /** Whether the stage actually ran for this study (e.g. defacing skipped on chest CT). */
  done?: boolean;
};

export type DeIDStepperProps = {
  /** Override per-stage state. Defaults to all 5 stages with no hashes. */
  stages?: DeIDStage[];
  /** Pipeline ruleset version, e.g. ``"v0.2.1"``. Optional. */
  rulesetVersion?: string | null;
  /** ISO timestamp of last full pipeline run. Optional. */
  runAt?: string | null;
  locale?: Locale;
};

const STAGE_DEFS_EN = [
  {
    num: 1,
    title: "PHI tag scrub",
    sub: "DICOM PS3.15 Annex E Basic Profile",
  },
  { num: 2, title: "UID re-generation", sub: "SHA-256 + per-hospital salt" },
  { num: 3, title: "Date shift", sub: "Per-patient ±1y offset" },
  { num: 4, title: "Burn-in OCR scrub", sub: "Tesseract + KO/EN dictionary" },
  { num: 5, title: "3D defacing", sub: "pydeface (modality-conditional)" },
];

const STAGE_DEFS_KO = [
  { num: 1, title: "PHI 태그 제거", sub: "DICOM PS3.15 Annex E 기본 프로파일" },
  { num: 2, title: "UID 재생성", sub: "SHA-256 + 병원별 salt" },
  { num: 3, title: "날짜 시프트", sub: "환자별 ±1년 오프셋" },
  { num: 4, title: "번인 OCR 제거", sub: "Tesseract + 한·영 사전" },
  { num: 5, title: "3D 디페이싱", sub: "pydeface (모달리티 조건부)" },
];

export function DeIDStepper({
  stages,
  rulesetVersion,
  runAt,
  locale = "en",
}: DeIDStepperProps) {
  const defs = locale === "ko" ? STAGE_DEFS_KO : STAGE_DEFS_EN;
  const t =
    locale === "ko"
      ? {
          headOk: (n: number, total: number) =>
            `익명화 체인 · ${total}단계 · ${n}건 검증`,
          ruleset: (v: string) => `룰셋 ${v}`,
          rulesetMissing: "룰셋 정보 없음",
        }
      : {
          headOk: (n: number, total: number) =>
            `De-ID chain · ${total} stages · ${n} verified`,
          ruleset: (v: string) => `ruleset ${v}`,
          rulesetMissing: "ruleset version pending",
        };

  const stageMap = new Map<number, DeIDStage>();
  for (const s of stages ?? []) stageMap.set(s.num, s);

  const verifiedCount = (stages ?? []).filter((s) => s.done !== false).length;
  // If no stages provided, treat all 5 as in-progress (no hashes yet).
  const totalDone = stages ? verifiedCount : defs.length;

  return (
    <div className="rv-deid-stepper" data-testid="deid-stepper">
      <div className="rv-deid-stepper__head">
        <span className="rv-deid-stepper__head__icon">✓</span>
        <span>{t.headOk(totalDone, defs.length)}</span>
      </div>
      {defs.map((def) => {
        const meta = stageMap.get(def.num);
        const done = meta?.done !== false;
        return (
          <div
            key={def.num}
            className="rv-deid-step"
            data-testid={`deid-stepper-step-${def.num}`}
          >
            <div
              className={
                "rv-deid-step__num" +
                (done ? " rv-deid-step__num--done" : "")
              }
            >
              {def.num}
            </div>
            <div className="rv-deid-step__body">
              <span className="rv-deid-step__title">{def.title}</span>
              <span className="rv-deid-step__title-sub">{def.sub}</span>
              <span className="rv-deid-step__hash">
                {meta?.hash ? meta.hash : "—"}
              </span>
            </div>
          </div>
        );
      })}
      <div className="rv-deid-stepper__footer">
        <span>
          {rulesetVersion ? t.ruleset(rulesetVersion) : t.rulesetMissing}
        </span>
        <span>{runAt ?? "—"}</span>
      </div>
    </div>
  );
}
