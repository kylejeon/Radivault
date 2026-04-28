"use client";

/**
 * <ViewerCanvas> — C-DV-Canvas (design-spec-dicom-viewer §4.4 + §5).
 *
 * Renders a single JPG slice on top of the dark canvas wrapper. Applies:
 *   - CSS transform: translate(panX, panY) scale(zoom) — zoom-to-cursor.
 *   - CSS filter: contrast(WW/200) brightness(1 + WL/100) — JPG W/L
 *     approximation. NOT diagnostic-grade (rescale slope/intercept lost).
 *
 * Interactions (FR-DV-3):
 *   - wheel  → zoom ±10%, anchored at cursor (clamp 0.25..8).
 *   - left-drag (zoom > 1) → pan, with bounds clamp so half the image
 *     always stays inside the canvas inner.
 *   - right-drag → W/L (horizontal=WW±, vertical=WL±). contextmenu
 *     suppressed so right-drag does not pop the browser menu.
 *   - dblclick → toggle fit (zoom=1) ↔ 100% (zoom=2).
 *
 * State is held by the parent <ViewerPaneV4>; this component is a
 * controlled view + emits onChange on each interaction.
 *
 * Performance (FR-DV-6):
 *   - We update `transform` / `filter` via direct ref mutation inside a
 *     RAF callback. setState is only fired on pointerup (+ debounced) so
 *     parent can persist + notify the toolbar readout.
 *   - Frame swap (frame number) is a parent concern; we just mount/key
 *     a fresh <img>.
 */

import {
  PointerEvent as ReactPointerEvent,
  WheelEvent as ReactWheelEvent,
  useCallback,
  useEffect,
  useRef,
} from "react";
import clsx from "clsx";
import { ViewerWatermark } from "./ViewerWatermark";
import { ViewerOverlay, type ViewerOverlayProps } from "./ViewerOverlay";

export const ZOOM_MIN = 0.25;
export const ZOOM_MAX = 8;
export const ZOOM_DEFAULT = 1;
export const PAN_DEFAULT = { x: 0, y: 0 };
export const WW_DEFAULT = 200;
export const WL_DEFAULT = 0;
export const WW_MIN = 1;
export const WW_MAX = 4000;
export const WL_MIN = -1024;
export const WL_MAX = 1024;

export type Pan = { x: number; y: number };

/** Pure helper used by zoom-in/out keyboard shortcuts + wheel. */
export function clampZoom(z: number): number {
  if (z < ZOOM_MIN) return ZOOM_MIN;
  if (z > ZOOM_MAX) return ZOOM_MAX;
  return z;
}

/** Pure helper used by W/L drag. */
export function clampWindow(value: number, min: number, max: number): number {
  if (value < min) return min;
  if (value > max) return max;
  return value;
}

/**
 * Bound the pan so at least half of the image stays inside the canvas
 * inner rect. At zoom > 1 the bound is `(innerSize*zoom - innerSize)/2`
 * (image excess); at zoom <= 1 we permit ±innerSize/2 so the user can
 * still pan the fit-to-screen image off-axis when the Pan tool is
 * active (Kyle 2026-04-28 — left-drag must work at default zoom too).
 */
function clampPan(pan: Pan, zoom: number, innerSize: number): Pan {
  const overhang =
    zoom > 1
      ? (innerSize * zoom - innerSize) / 2
      : innerSize / 2;
  if (overhang === 0) return PAN_DEFAULT;
  return {
    x: Math.max(-overhang, Math.min(overhang, pan.x)),
    y: Math.max(-overhang, Math.min(overhang, pan.y)),
  };
}

/**
 * CSS filter string for a given (WW, WL) pair. WW=200 / WL=0 is the
 * identity (contrast 1, brightness 1). The mapping below was chosen
 * to feel reasonable for an 8-bit JPG; it is NOT a clinical CT W/L.
 */
export function wlFilter(ww: number, wl: number): string {
  const contrast = clampWindow(ww / 200, 0.05, 5).toFixed(3);
  const brightness = clampWindow(1 + wl / 200, 0.05, 5).toFixed(3);
  return `contrast(${contrast}) brightness(${brightness})`;
}

export type ViewerCanvasProps = {
  /** URL for the current frame JPG. Changing this remounts the <img>. */
  frameUrl: string;
  /** Alt text for SR. */
  alt: string;
  /** Pan/zoom/W-L — controlled by parent. */
  zoom: number;
  pan: Pan;
  ww: number;
  wl: number;
  /** Modality of the active series (used to disable preset etc.). */
  modality?: string | null;
  /** Active interaction tool — affects which button is highlighted. */
  activeTool: "pan" | "wl";
  /** Pan/Zoom/WL change callbacks. Parent debounces if it wishes. */
  onChange: (next: { zoom: number; pan: Pan; ww: number; wl: number }) => void;
  /** Overlay slots (4 corners). pointer-events:none, no interaction. */
  overlay?: ViewerOverlayProps;
  /** Optional DefacePill node — caller controls colour/text. */
  defacePill?: React.ReactNode;
  /** Hide watermark (e.g. screenshot tests). Default false → visible. */
  hideWatermark?: boolean;
  /** Optional click-handler for double-click fit toggle. */
  onDoubleClick?: () => void;
};

export function ViewerCanvas({
  frameUrl,
  alt,
  zoom,
  pan,
  ww,
  wl,
  modality,
  activeTool,
  onChange,
  overlay,
  defacePill,
  hideWatermark,
  onDoubleClick,
}: ViewerCanvasProps) {
  void modality;
  const innerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  // Track in-flight pointer drag.
  const dragRef = useRef<{
    pointerId: number;
    button: number; // 0=left, 2=right
    startX: number;
    startY: number;
    startPan: Pan;
    startWw: number;
    startWl: number;
    mode: "pan" | "wl";
  } | null>(null);

  // Imperative transform application (avoids React reconciliation cost on
  // wheel/drag). We still call onChange so React state mirrors the DOM.
  const applyTransform = useCallback(
    (z: number, p: Pan) => {
      if (!imgRef.current) return;
      imgRef.current.style.transform = `translate(${p.x}px, ${p.y}px) scale(${z})`;
    },
    [],
  );
  const applyFilter = useCallback(
    (currentWw: number, currentWl: number) => {
      if (!imgRef.current) return;
      imgRef.current.style.filter = wlFilter(currentWw, currentWl);
    },
    [],
  );

  // Sync controlled props → DOM on every render.
  useEffect(() => {
    applyTransform(zoom, pan);
  }, [zoom, pan, applyTransform]);
  useEffect(() => {
    applyFilter(ww, wl);
  }, [ww, wl, applyFilter]);

  function getInnerSize(): number {
    if (!innerRef.current) return 0;
    const rect = innerRef.current.getBoundingClientRect();
    return Math.min(rect.width, rect.height);
  }

  // ------------------------------------------------------------------
  // Wheel (zoom-to-cursor)
  // ------------------------------------------------------------------
  function onWheel(e: ReactWheelEvent<HTMLDivElement>) {
    if (!innerRef.current) return;
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    const nextZoom = clampZoom(zoom * factor);
    if (nextZoom === zoom) return;
    // Anchor at cursor: pan adjustment so the cursor stays on the same
    // image-space pixel after zoom.
    const rect = innerRef.current.getBoundingClientRect();
    const cx = e.clientX - rect.left - rect.width / 2;
    const cy = e.clientY - rect.top - rect.height / 2;
    const ratio = nextZoom / zoom;
    const nextPan = clampPan(
      {
        x: cx - (cx - pan.x) * ratio,
        y: cy - (cy - pan.y) * ratio,
      },
      nextZoom,
      Math.min(rect.width, rect.height),
    );
    onChange({ zoom: nextZoom, pan: nextPan, ww, wl });
  }

  // ------------------------------------------------------------------
  // Pointer down/move/up — pan (left) and W/L (right or shift+left).
  // ------------------------------------------------------------------
  function onPointerDown(e: ReactPointerEvent<HTMLDivElement>) {
    if (!innerRef.current) return;
    // Right-click + Shift+left always do W/L (radiology standard).
    // Plain left-click respects activeTool (Kyle 2026-04-28).
    const isRight = e.button === 2;
    const isShiftLeft = e.button === 0 && e.shiftKey;
    const isLeftPlain = e.button === 0 && !e.shiftKey;
    const isWlMode =
      isRight || isShiftLeft || (isLeftPlain && activeTool === "wl");
    const isPanMode = isLeftPlain && activeTool === "pan";
    if (!isWlMode && !isPanMode) return;
    e.preventDefault();
    const target = e.currentTarget;
    target.setPointerCapture?.(e.pointerId);
    dragRef.current = {
      pointerId: e.pointerId,
      button: e.button,
      startX: e.clientX,
      startY: e.clientY,
      startPan: pan,
      startWw: ww,
      startWl: wl,
      mode: isWlMode ? "wl" : "pan",
    };
    if (isWlMode) {
      target.classList.add("is-windowing");
    } else {
      target.classList.add("is-panning");
    }
  }

  function onPointerMove(e: ReactPointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    if (drag.pointerId !== e.pointerId) return;
    const dx = e.clientX - drag.startX;
    const dy = e.clientY - drag.startY;
    if (drag.mode === "pan") {
      const innerSize = getInnerSize();
      const nextPan = clampPan(
        { x: drag.startPan.x + dx, y: drag.startPan.y + dy },
        zoom,
        innerSize,
      );
      onChange({ zoom, pan: nextPan, ww, wl });
    } else {
      // W/L drag — horizontal = WW (faster), vertical = WL (inverted: drag up = brighter).
      const nextWw = clampWindow(drag.startWw + dx * 2, WW_MIN, WW_MAX);
      const nextWl = clampWindow(drag.startWl - dy, WL_MIN, WL_MAX);
      onChange({ zoom, pan, ww: nextWw, wl: nextWl });
    }
  }

  function onPointerUp(e: ReactPointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    if (drag.pointerId !== e.pointerId) return;
    const target = e.currentTarget;
    target.releasePointerCapture?.(e.pointerId);
    target.classList.remove("is-panning", "is-windowing");
    dragRef.current = null;
  }

  function onContextMenu(e: ReactPointerEvent<HTMLDivElement>) {
    // Suppress default contextmenu so right-drag W/L is uninterrupted.
    e.preventDefault();
  }

  // ------------------------------------------------------------------
  // Double-click → fit ↔ 100%
  // ------------------------------------------------------------------
  function onDblClick() {
    if (onDoubleClick) {
      onDoubleClick();
      return;
    }
    // Default: zoom toggles between 1 (fit) and 2 (zoomed in).
    const nextZoom = zoom > 1 ? 1 : 2;
    onChange({
      zoom: nextZoom,
      pan: nextZoom === 1 ? PAN_DEFAULT : pan,
      ww,
      wl,
    });
  }

  return (
    <div
      className="rv-viewer-canvas-v4"
      data-testid="dv-canvas"
      data-active-tool={activeTool}
    >
      <div
        className="rv-viewer-canvas-v4__inner"
        ref={innerRef}
        role="img"
        aria-label={alt}
      >
        {defacePill}
        <ViewerOverlay {...(overlay ?? {})} />
        {!hideWatermark ? <ViewerWatermark /> : null}
        <div
          className={clsx("rv-viewer-canvas-v4__img-wrap")}
          data-pannable={activeTool === "pan"}
          data-testid="dv-canvas-surface"
          onWheel={onWheel}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onDoubleClick={onDblClick}
          onContextMenu={onContextMenu}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          {/* No `key` on <img> (Kyle 2026-04-28) — letting React reuse the
              same element on src change keeps the previous frame visible
              until the new one decodes, eliminating the white flash during
              real-time slider scrub. */}
          <img
            ref={imgRef}
            src={frameUrl}
            alt={alt}
            draggable={false}
            className="rv-viewer-canvas-v4__img"
            data-testid="dv-canvas-img"
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              filter: wlFilter(ww, wl),
            }}
          />
        </div>
      </div>
    </div>
  );
}
