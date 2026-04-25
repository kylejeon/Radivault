/**
 * StudyThumbnail — design-spec §6.
 *
 * Renders one of four states for a study row's preview slot:
 *
 *   - "verified"    : actual JPEG via /api/studies/[uid]/thumbnail
 *   - "pending" / "phi_detected" / "not_applicable" : placeholder
 *   - loading       : skeleton pulse (until IntersectionObserver fires)
 *   - error (5xx)   : auto-retry once, then small "Retry" link
 *
 * lazy-loaded with IntersectionObserver (NFR-PERF-1 — first-fold latency
 * stays low when /search returns 50 cards).
 */

"use client";

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";
import { getDict, type Locale } from "@/lib/i18n";

export type PreviewStatus =
  | "verified"
  | "pending"
  | "phi_detected"
  | "not_applicable";

export type StudyThumbnailProps = {
  studyUid: string;
  status?: PreviewStatus;
  modality?: string | null;
  studyDescription?: string | null;
  size?: number; // pixel size of the square; design default 96 (row variant)
  locale?: Locale;
  className?: string;
};

type LoadState = "idle" | "loading" | "loaded" | "error";

const PLACEHOLDER_GLYPHS: Record<string, string> = {
  CT: "▦",
  MR: "◉",
  CR: "▤",
  DR: "▤",
  DX: "▤",
  MG: "◬",
  PT: "✦",
  PET: "✦",
  NM: "✦",
  US: "≋",
};

function glyphFor(modality: string | null | undefined): string {
  if (!modality) return "▢";
  return PLACEHOLDER_GLYPHS[modality.toUpperCase()] ?? "▢";
}

export function StudyThumbnail({
  studyUid,
  status = "pending",
  modality,
  studyDescription,
  size = 96,
  locale = "en",
  className,
}: StudyThumbnailProps) {
  const dict = getDict(locale);
  const [state, setState] = useState<LoadState>("idle");
  const [retryCount, setRetryCount] = useState(0);
  const [src, setSrc] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement | null>(null);
  const verified = status === "verified";

  // IntersectionObserver — only request when in viewport. Browsers that
  // don't ship IO (Safari < 12.1) just fall through to immediate fetch.
  useEffect(() => {
    if (!verified) return;
    if (typeof IntersectionObserver === "undefined") {
      setState("loading");
      setSrc(`/api/studies/${encodeURIComponent(studyUid)}/thumbnail`);
      return;
    }
    const node = ref.current;
    if (!node) return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            setState("loading");
            setSrc(`/api/studies/${encodeURIComponent(studyUid)}/thumbnail`);
            io.disconnect();
            break;
          }
        }
      },
      { rootMargin: "200px 0px" },
    );
    io.observe(node);
    return () => io.disconnect();
  }, [studyUid, verified]);

  function onErr() {
    if (retryCount < 1) {
      // One automatic retry — append a cache-bust query param so the
      // browser doesn't replay the failed response from disk.
      setRetryCount((n) => n + 1);
      setSrc(
        `/api/studies/${encodeURIComponent(studyUid)}/thumbnail?retry=${Date.now()}`,
      );
      return;
    }
    setState("error");
  }

  function manualRetry() {
    setRetryCount(0);
    setState("loading");
    setSrc(
      `/api/studies/${encodeURIComponent(studyUid)}/thumbnail?manual=${Date.now()}`,
    );
  }

  // Common box dims — flex-shrink:0 in the parent row keeps the slot from
  // collapsing under truncation pressure.
  const dim = { width: size, height: size };

  // ---- verified: image ----
  if (verified && src) {
    return (
      <div
        ref={ref}
        data-testid={`study-thumbnail-${studyUid}`}
        data-state={state}
        className={clsx(
          "relative shrink-0 overflow-hidden rounded-md border border-border bg-bg-muted",
          className,
        )}
        style={dim}
      >
        {state === "loading" ? (
          <div className="absolute inset-0 motion-safe:animate-pulse bg-bg-muted" />
        ) : null}
        {state !== "error" ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={src}
            alt={
              studyDescription ?? `${modality ?? ""} preview thumbnail`.trim()
            }
            width={size}
            height={size}
            loading="lazy"
            className="size-full object-cover"
            onLoad={() => setState("loaded")}
            onError={onErr}
          />
        ) : null}
        {state === "error" ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 p-2 text-center text-text-muted">
            <span aria-hidden className="text-lg">⚠</span>
            <span className="text-[10px] leading-tight">
              {dict.preview.thumbnailFailed}
            </span>
            <button
              type="button"
              onClick={manualRetry}
              className="text-[10px] font-medium text-primary-700 underline"
            >
              {dict.preview.thumbnailRetry}
            </button>
          </div>
        ) : null}
      </div>
    );
  }

  // ---- verified but pre-IntersectionObserver ----
  if (verified) {
    return (
      <div
        ref={ref}
        data-testid={`study-thumbnail-${studyUid}`}
        data-state="idle"
        className={clsx(
          "relative shrink-0 overflow-hidden rounded-md border border-border bg-bg-muted",
          "motion-safe:animate-pulse",
          className,
        )}
        style={dim}
        aria-hidden
      />
    );
  }

  // ---- placeholder ----
  return (
    <div
      data-testid={`study-thumbnail-placeholder-${studyUid}`}
      data-state={status}
      role="img"
      aria-label={dict.preview.unavailableShort}
      className={clsx(
        "shrink-0 rounded-md border border-border bg-bg-muted",
        "flex flex-col items-center justify-center gap-1 p-1 text-center",
        "text-text-muted",
        className,
      )}
      style={dim}
    >
      <span aria-hidden className="text-2xl leading-none">
        {glyphFor(modality)}
      </span>
      <span className="text-[10px] leading-tight">
        {dict.preview.unavailableShort}
      </span>
    </div>
  );
}
