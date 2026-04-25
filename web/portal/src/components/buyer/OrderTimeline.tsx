"use client";

import { useState } from "react";
import clsx from "clsx";

/**
 * OrderTimeline {#order-timeline-v1} — design-spec-portal-redesign §11.7.
 * FR-BP-10.
 *
 * Two surfaces in one component:
 *   1. 5-phase horizontal stepper (always visible).
 *   2. "View timeline →" drawer with the 12-state FSM event log
 *      (state changes + download events colour-coded teal).
 *
 * The 5 phases mirror the existing `<components/PhaseStepper>` happy path
 * (paid → fetching → de-id → packaging → ready). We deliberately do NOT
 * fold the legacy stepper away — the buyer-portal-demo surfaces still
 * import it. This component is the v0.2 stricter spec for the redesign.
 */

export type TimelinePhase =
  | "paid"
  | "fetching"
  | "de_id"
  | "packaging"
  | "ready";

export type TimelineEvent = {
  ts: string; // ISO timestamp
  kind: "state" | "download";
  message: string;
  detail?: string | null;
};

const PHASES: { key: TimelinePhase; en: string; ko: string }[] = [
  { key: "paid", en: "Submitted", ko: "제출됨" },
  { key: "fetching", en: "Fetching", ko: "수집 중" },
  { key: "de_id", en: "De-identifying", ko: "비식별화" },
  { key: "packaging", en: "Packaging", ko: "패키지" },
  { key: "ready", en: "Ready", ko: "다운로드 가능" },
];

/** Legacy `BuyerPhase` -> §11.7 5-phase mapping. */
export function mapBuyerPhase(
  phase:
    | "accepted"
    | "fetching_from_hospital"
    | "preparing_download"
    | "ready_to_download"
    | "completed"
    | "cancelled"
    | "expired"
    | "failed",
): TimelinePhase {
  switch (phase) {
    case "accepted":
      return "paid";
    case "fetching_from_hospital":
      return "fetching";
    case "preparing_download":
      return "packaging";
    case "ready_to_download":
      return "ready";
    case "completed":
      return "ready";
    default:
      return "paid";
  }
}

export type OrderTimelineProps = {
  phase: TimelinePhase;
  events?: TimelineEvent[];
  locale?: "en" | "ko";
};

export function OrderTimeline({
  phase,
  events = [],
  locale = "en",
}: OrderTimelineProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const idx = PHASES.findIndex((p) => p.key === phase);

  return (
    <div data-testid="order-timeline" className="flex flex-col gap-3">
      <ol
        className="flex items-center gap-2"
        aria-label={locale === "ko" ? "주문 단계" : "Order phase"}
      >
        {PHASES.map((p, i) => {
          const reached = i <= idx;
          const active = i === idx;
          const label = locale === "ko" ? p.ko : p.en;
          return (
            <li key={p.key} className="flex flex-1 items-center gap-2">
              <span
                className={clsx(
                  "inline-block size-2.5 shrink-0 rounded-full",
                  reached ? "bg-primary-600" : "bg-border-strong",
                  active && "animate-pulse",
                )}
                aria-hidden
              />
              <span
                className={clsx(
                  "text-xs",
                  active ? "font-semibold text-text" : "text-text-muted",
                )}
              >
                {label}
              </span>
              {i < PHASES.length - 1 ? (
                <span
                  aria-hidden
                  className={clsx(
                    "h-px flex-1",
                    reached ? "bg-primary-600" : "bg-border",
                  )}
                />
              ) : null}
            </li>
          );
        })}
      </ol>
      <div>
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          className="text-xs text-primary-700 hover:underline"
        >
          {locale === "ko" ? "타임라인 보기 →" : "View timeline →"}
        </button>
      </div>

      {drawerOpen ? (
        <TimelineDrawer
          events={events}
          onClose={() => setDrawerOpen(false)}
          locale={locale}
        />
      ) : null}
    </div>
  );
}

function TimelineDrawer({
  events,
  onClose,
  locale,
}: {
  events: TimelineEvent[];
  onClose: () => void;
  locale: "en" | "ko";
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={locale === "ko" ? "타임라인" : "Timeline"}
      data-testid="timeline-drawer"
      className="fixed inset-0 z-50 flex justify-end bg-text/30"
      onClick={onClose}
    >
      <aside
        onClick={(e) => e.stopPropagation()}
        className="flex h-full w-full max-w-[480px] flex-col gap-3 overflow-y-auto bg-bg p-5 shadow-overlay"
      >
        <header className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-text">
            {locale === "ko" ? "타임라인" : "Timeline"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={locale === "ko" ? "닫기" : "Close"}
            className="text-text-muted hover:text-text"
          >
            ✕
          </button>
        </header>
        {events.length === 0 ? (
          <p className="text-sm text-text-muted">
            {locale === "ko" ? "이벤트 없음" : "No events yet."}
          </p>
        ) : (
          <ul className="flex flex-col gap-3">
            {events.map((e, i) => (
              <li
                key={`${e.ts}-${i}`}
                className="flex gap-3 border-b border-border pb-3 last:border-b-0"
              >
                <span
                  aria-hidden
                  className={clsx(
                    "mt-1 inline-block size-2 shrink-0 rounded-full",
                    e.kind === "download"
                      ? "bg-teal-600"
                      : "bg-primary-600",
                  )}
                />
                <div className="flex-1 text-sm">
                  <div className="font-mono text-xs text-text-muted">
                    {new Date(e.ts).toLocaleString(
                      locale === "ko" ? "ko-KR" : "en-US",
                    )}
                  </div>
                  <div className="text-text">{e.message}</div>
                  {e.detail ? (
                    <div className="mt-0.5 font-mono text-xs text-text-muted">
                      {e.detail}
                    </div>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </aside>
    </div>
  );
}
