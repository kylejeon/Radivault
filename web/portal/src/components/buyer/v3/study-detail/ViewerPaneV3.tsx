"use client";

/**
 * <ViewerPaneV3> — dark viewer canvas wrapper for the study-detail page
 * (mockup `.viewer-pane`).
 *
 * Wraps the existing <FrameSliderViewer> / <SliceViewerOrFallback> /
 * <LegacyThumbnailFallback> inside a black-canvas surface that adds:
 *
 *   - 4 monospace overlays at the corners (study info / device / patient /
 *     De-ID hash) — CT-scanner-style burned-in metadata, EXCEPT here it is
 *     deliberately the de-identified replacement metadata, not original
 *     burn-in pixels.
 *   - SaMD "display only" disclaimer line below the canvas.
 *
 * The viewer tools / slice slider / W-L palette in the mockup are stylistic
 * decorations of the underlying viewer interactions; we do NOT add a parallel
 * tools palette because the existing slider/scrubber lives inside
 * <FrameSliderViewer> / <SliceViewer>. The dark wrapper just gives the
 * scrubbed viewer the v3 visual frame.
 *
 * Overlays are pointer-events:none so they never block scrubber gestures.
 */

import type { ReactNode } from "react";
import type { Locale } from "@/lib/i18n";

export type ViewerPaneV3Props = {
  /** The actual viewer component (FrameSliderViewer / fallback). */
  children: ReactNode;
  /** Top-left overlay (e.g. "SEOUL-A · CT"). */
  topLeft?: string | ReactNode | null;
  /** Top-right overlay (e.g. manufacturer + KVP). */
  topRight?: string | ReactNode | null;
  /** Bottom-left overlay (e.g. "F · 52" / patient pseudo). */
  bottomLeft?: string | ReactNode | null;
  /** Bottom-right overlay (e.g. De-ID hash + ruleset). */
  bottomRight?: string | ReactNode | null;
  locale?: Locale;
};

export function ViewerPaneV3({
  children,
  topLeft,
  topRight,
  bottomLeft,
  bottomRight,
  locale = "en",
}: ViewerPaneV3Props) {
  const disclaimer =
    locale === "ko"
      ? "표시 전용 — 진단 용도 아님 (SaMD 면책)"
      : "Display only — not for diagnostic use (SaMD disclaimer)";

  return (
    <section className="rv-viewer-pane" aria-label="DICOM viewer">
      <div className="rv-viewer-canvas-wrap" data-testid="study-detail-viewer-pane">
        {children}
        {topLeft ? (
          <div className="rv-viewer-overlay" data-testid="viewer-overlay-tl">
            {topLeft}
          </div>
        ) : null}
        {topRight ? (
          <div
            className="rv-viewer-overlay rv-viewer-overlay--tr"
            data-testid="viewer-overlay-tr"
          >
            {topRight}
          </div>
        ) : null}
        {bottomLeft ? (
          <div
            className="rv-viewer-overlay rv-viewer-overlay--bl"
            data-testid="viewer-overlay-bl"
          >
            {bottomLeft}
          </div>
        ) : null}
        {bottomRight ? (
          <div
            className="rv-viewer-overlay rv-viewer-overlay--br"
            data-testid="viewer-overlay-br"
          >
            {bottomRight}
          </div>
        ) : null}
      </div>
      <div className="rv-viewer-disclaimer">{disclaimer}</div>
    </section>
  );
}
