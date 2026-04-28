"use client";

/**
 * <ViewerOverlay> — C-DV-Overlay (design-spec-dicom-viewer §4.6).
 *
 * 4-corner monospace metadata overlays on top of the canvas:
 *
 *   TL = hospital_opaque_id · modality / WW WL / slice n / total
 *   TR = manufacturer · model / study_date (shifted) / kVp · mAs (CT) | TE · TR (MR)
 *   BL = sex · age / pseudo PT-id
 *   BR = ▣ De-ID hash16 / ruleset version
 *
 * `pointer-events: none` so they never block zoom/pan/W-L drag. Z-index
 * 4 — above the watermark (z=3) and below DefacePill (z=5). Caller
 * passes pre-formatted ReactNode chunks so the data shape stays
 * StudyDetail-agnostic.
 */

import type { ReactNode } from "react";

export type ViewerOverlayProps = {
  topLeft?: ReactNode | null;
  topRight?: ReactNode | null;
  bottomLeft?: ReactNode | null;
  bottomRight?: ReactNode | null;
};

export function ViewerOverlay({
  topLeft,
  topRight,
  bottomLeft,
  bottomRight,
}: ViewerOverlayProps) {
  return (
    <>
      {topLeft ? (
        <div
          className="rv-viewer-overlay-v4"
          data-testid="dv-overlay-tl"
          aria-hidden
        >
          {topLeft}
        </div>
      ) : null}
      {topRight ? (
        <div
          className="rv-viewer-overlay-v4 rv-viewer-overlay-v4--tr"
          data-testid="dv-overlay-tr"
          aria-hidden
        >
          {topRight}
        </div>
      ) : null}
      {bottomLeft ? (
        <div
          className="rv-viewer-overlay-v4 rv-viewer-overlay-v4--bl"
          data-testid="dv-overlay-bl"
          aria-hidden
        >
          {bottomLeft}
        </div>
      ) : null}
      {bottomRight ? (
        <div
          className="rv-viewer-overlay-v4 rv-viewer-overlay-v4--br"
          data-testid="dv-overlay-br"
          aria-hidden
        >
          {bottomRight}
        </div>
      ) : null}
    </>
  );
}
