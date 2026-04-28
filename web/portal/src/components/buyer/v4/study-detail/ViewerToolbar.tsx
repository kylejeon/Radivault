"use client";

/**
 * <ViewerToolbar> — C-DV-Toolbar (design-spec-dicom-viewer §4.3).
 *
 * Horizontal strip placed between SeriesPicker and Canvas. 5 left-group
 * buttons: Zoom + / Zoom − / Pan / W-L / Preset ▾. Live W/L+zoom readout
 * (mono) in the center. 2 right-group buttons: Reset / Fullscreen.
 *
 * Keyboard hints in `data-tip` attributes — the global tooltip pattern
 * `[data-tip]:hover::after` (globals.css) renders the hint above the
 * button on hover. Buttons remain pure `<button>` with proper aria-label
 * + aria-pressed; the tooltip is decorative.
 *
 * The active "tool" state (`pan` vs `wl`) is managed by the parent
 * <ViewerPaneV4> — pan is the default when zoom > 1, and W/L is the
 * active interpretation of right-button drag (FR-DV-3.3, default
 * modifier). The `activeTool` prop just decides which button shows the
 * teal-500 active background.
 *
 * The `i` icon next to W/L (FR-DV-3.3 / Q-DV-3) carries the
 * "Approximate W/L based on JPG luminance" tooltip — surfaced via
 * `data-tip` on the parent button.
 */

import clsx from "clsx";
import { PresetMenu, type PresetId, type PresetSpec } from "./PresetMenu";

export type ToolbarTool = "pan" | "wl";

export type ViewerToolbarProps = {
  /** Active tool (pan or wl). Visible-only; the canvas reads the same state. */
  activeTool: ToolbarTool;
  /** Callback when the user clicks Pan/W-L button. */
  onSelectTool: (tool: ToolbarTool) => void;
  /** Active preset (for the dropdown ✓ mark). */
  activePreset: PresetId;
  /** Preset selection handler — `"custom"` resets activePreset to `"custom"`. */
  onSelectPreset: (preset: PresetSpec | "custom") => void;
  /** Disable the preset dropdown when modality is not CT. */
  presetDisabled?: boolean;
  /** Live readouts. */
  ww: number;
  wl: number;
  zoom: number;
  /** Zoom in/out — clamps applied in <ViewerPaneV4>. */
  onZoomIn: () => void;
  onZoomOut: () => void;
  /** Reset everything (zoom=1, pan=0, ww/wl=preset default). */
  onReset: () => void;
  /** Fullscreen toggle. */
  onToggleFullscreen: () => void;
  /** Whether currently in fullscreen mode. */
  isFullscreen?: boolean;
};

export function ViewerToolbar({
  activeTool,
  onSelectTool,
  activePreset,
  onSelectPreset,
  presetDisabled,
  ww,
  wl,
  zoom,
  onZoomIn,
  onZoomOut,
  onReset,
  onToggleFullscreen,
  isFullscreen,
}: ViewerToolbarProps) {
  return (
    <div
      className="rv-viewer-toolbar"
      aria-label="Viewer tools"
      data-testid="dv-toolbar"
    >
      <div className="rv-viewer-toolbar__group">
        <button
          type="button"
          className="rv-viewer-toolbar__btn"
          aria-label="Zoom in (plus key)"
          data-tip="Zoom in (+ or =)"
          onClick={onZoomIn}
          data-testid="dv-tool-zoom-in"
        >
          <span className="rv-viewer-toolbar__icon" aria-hidden>
            ⊕
          </span>
          Zoom +
        </button>
        <button
          type="button"
          className="rv-viewer-toolbar__btn"
          aria-label="Zoom out (minus key)"
          data-tip="Zoom out (− key)"
          onClick={onZoomOut}
          data-testid="dv-tool-zoom-out"
        >
          <span className="rv-viewer-toolbar__icon" aria-hidden>
            ⊖
          </span>
          Zoom −
        </button>
        <button
          type="button"
          className={clsx(
            "rv-viewer-toolbar__btn",
            activeTool === "pan" && "rv-viewer-toolbar__btn--active",
          )}
          aria-label="Pan tool"
          aria-pressed={activeTool === "pan"}
          data-tip="Pan (left-drag · zoom > 1)"
          onClick={() => onSelectTool("pan")}
          data-testid="dv-tool-pan"
        >
          <span className="rv-viewer-toolbar__icon" aria-hidden>
            ✥
          </span>
          Pan
        </button>
        <button
          type="button"
          className={clsx(
            "rv-viewer-toolbar__btn",
            activeTool === "wl" && "rv-viewer-toolbar__btn--active",
          )}
          aria-label="Window/Level tool — approximate W/L based on JPG luminance"
          aria-pressed={activeTool === "wl"}
          data-tip="W/L (right-drag · approx — request DICOM raw for diagnostic-grade)"
          onClick={() => onSelectTool("wl")}
          data-testid="dv-tool-wl"
        >
          <span className="rv-viewer-toolbar__icon" aria-hidden>
            ◐
          </span>
          W/L
          <span
            className="rv-info-i"
            aria-hidden
            title="Approximate W/L based on JPG luminance — for diagnostic-grade W/L, request DICOM raw via order."
          >
            i
          </span>
        </button>
        <PresetMenu
          active={activePreset}
          onSelect={onSelectPreset}
          disabled={presetDisabled}
        />
      </div>

      <div
        className="rv-viewer-toolbar__readout"
        aria-live="polite"
        data-testid="dv-toolbar-readout"
      >
        <strong>WW {Math.round(ww)}</strong> /{" "}
        <strong>WL {Math.round(wl)}</strong>
        &nbsp;·&nbsp; zoom <strong>{zoom.toFixed(1)}×</strong>
      </div>

      <div className="rv-viewer-toolbar__sep" aria-hidden />
      <div className="rv-viewer-toolbar__group">
        <button
          type="button"
          className="rv-viewer-toolbar__btn"
          aria-label="Reset view"
          data-tip="Reset (R)"
          onClick={onReset}
          data-testid="dv-tool-reset"
        >
          <span className="rv-viewer-toolbar__icon" aria-hidden>
            ↺
          </span>
          Reset
        </button>
        <button
          type="button"
          className="rv-viewer-toolbar__btn"
          aria-label={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
          aria-pressed={isFullscreen}
          data-tip="Fullscreen (F · Esc to exit)"
          onClick={onToggleFullscreen}
          data-testid="dv-tool-fullscreen"
        >
          <span className="rv-viewer-toolbar__icon" aria-hidden>
            ⛶
          </span>
        </button>
      </div>
    </div>
  );
}
