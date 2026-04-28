"use client";

/**
 * <LongitudinalTimeline> — horizontal stepper of related (prior + follow-up)
 * studies for the same patient pseudo ID. Mockup `.timeline`.
 *
 * Backend status: NOT YET WIRED (separate dev-spec). When the upstream omits
 * related studies we render a placeholder line so buyers see the slot exists
 * but understand the data is pending — *not* fake studies.
 *
 * Each `step` has a modality dot label, a YYYY-MM date, an optional hospital
 * region pseudo, and a state of `prior | current | future`. The visual lane
 * changes accordingly (filled / teal-current / hollow).
 */

import type { Locale } from "@/lib/i18n";

export type TimelineStepState = "prior" | "current" | "future";

export type TimelineStep = {
  /** Modality short label, e.g. "CT", "MR", "CR". */
  modality: string;
  /** "YYYY-MM" preferred; component does not validate. */
  date: string;
  /** Hospital region pseudo, e.g. "SEOUL-A". Optional. */
  hospital?: string | null;
  state: TimelineStepState;
};

export type LongitudinalTimelineProps = {
  /** Patient pseudo ID, surfaced in the title for cohort cross-reference. */
  patientPseudoId?: string | null;
  steps?: TimelineStep[] | null;
  locale?: Locale;
};

export function LongitudinalTimeline({
  patientPseudoId,
  steps,
  locale = "en",
}: LongitudinalTimelineProps) {
  const t =
    locale === "ko"
      ? {
          title: "관련 검사 (시계열)",
          empty: "동일 환자의 다른 검사 정보가 아직 연결되지 않았습니다.",
          summary: (priors: number, follows: number) =>
            `이전 검사 ${priors}건 · 후속 ${follows}건`,
        }
      : {
          title: "Related studies (longitudinal)",
          empty:
            "No prior or follow-up studies linked yet for this patient.",
          summary: (priors: number, follows: number) =>
            `${priors} prior · ${follows} follow-up`,
        };

  const list = steps ?? [];
  const priors = list.filter((s) => s.state === "prior").length;
  const follows = list.filter((s) => s.state === "future").length;

  return (
    <section
      className="rv-detail-section"
      data-testid="longitudinal-timeline"
    >
      <div className="rv-detail-section__title">
        <span>{t.title}</span>
        {patientPseudoId ? (
          <span
            style={{
              fontFamily: "JetBrains Mono, ui-monospace, monospace",
              fontSize: 10,
              color: "var(--rv-stone-500)",
              textTransform: "none",
              letterSpacing: 0,
            }}
          >
            {patientPseudoId}
          </span>
        ) : null}
      </div>
      {list.length === 0 ? (
        <div
          className="rv-timeline__placeholder"
          data-testid="longitudinal-timeline-placeholder"
        >
          {t.empty}
        </div>
      ) : (
        <>
          <div className="rv-timeline">
            {list.map((step, i) => (
              <div
                key={`${step.date}-${i}`}
                className="rv-timeline__step"
                data-testid={`longitudinal-timeline-step-${i}`}
                data-state={step.state}
              >
                <div
                  className={
                    "rv-timeline__dot" +
                    (step.state === "prior"
                      ? " rv-timeline__dot--filled"
                      : step.state === "current"
                        ? " rv-timeline__dot--current"
                        : "")
                  }
                >
                  {step.modality}
                </div>
                <div className="rv-timeline__date">{step.date}</div>
                {step.hospital ? (
                  <div className="rv-timeline__hospital">{step.hospital}</div>
                ) : null}
              </div>
            ))}
          </div>
          <div
            style={{
              marginTop: 8,
              fontSize: 11,
              color: "var(--rv-stone-500)",
            }}
          >
            {t.summary(priors, follows)}
          </div>
        </>
      )}
    </section>
  );
}
