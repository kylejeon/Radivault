"use client";

/**
 * <ViewerWatermark> — C-DV-Watermark (design-spec-dicom-viewer §4.10).
 *
 * `◆ RADIVAULT` SVG wordmark placed bottom-right of the canvas inner
 * (Kyle 2026-04-28 — was top-center). Used for anti-screenshot
 * identification: visible in captures + slideshow demos so the source
 * is identifiable.
 *
 * Visual:
 *   - tilt: -12°
 *   - opacity 0.32, mix-blend-mode: screen — visible on dark lung-window
 *     and bright bone-window without invading diagnostic area.
 *   - width 22% of canvas inner (clamp 140-260 px); 32% on mobile.
 *   - aria-hidden, pointer-events:none, user-select:none.
 *
 * Z-index: 3 — below the 4-corner overlays (z=4) and DefacePill (z=5),
 * above the image (z=0~1). When BR overlay (De-ID hash) is wired, it
 * renders on top of this watermark.
 */

export function ViewerWatermark() {
  return (
    <svg
      className="rv-viewer-watermark"
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 240 60"
      xmlns="http://www.w3.org/2000/svg"
      data-testid="dv-watermark"
    >
      <g transform="rotate(-12 120 30)">
        <text
          x="120"
          y="38"
          textAnchor="middle"
          fontFamily="'Inter','Pretendard',sans-serif"
          fontWeight="700"
          fontSize="22"
          letterSpacing="3"
          fill="rgba(255,255,255,0.85)"
        >
          ◆ RADIVAULT
        </text>
      </g>
    </svg>
  );
}
