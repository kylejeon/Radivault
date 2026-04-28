"use client";

/**
 * <PresetMenu> — C-DV-PresetMenu (design-spec-dicom-viewer §4.7).
 *
 * W/L preset dropdown attached to the toolbar `Preset ▾` button. Five
 * built-in CT presets (Lung / Bone / Soft tissue / Mediastinum / Brain)
 * + Custom… that simply hands control back to manual right-drag W/L.
 *
 * MR / SEG / PT — the parent <ViewerToolbar> renders this with
 * `disabled=true`, which collapses the trigger to a non-interactive
 * disabled button + tooltip "CT presets only — adjust W/L manually".
 *
 * JPG-domain limit (FR-DV-3.5): the WW/WL pairs below are clinical
 * Hounsfield-unit conventions, but the underlying preview is JPG (8-bit,
 * rescale slope/intercept lost). The CSS filter applied in <ViewerCanvas>
 * is brightness/contrast approximation, NOT diagnostic-grade. UI surfaces
 * this via the `i` icon next to the W/L tool button.
 */

import { useEffect, useRef, useState } from "react";
import clsx from "clsx";

export type PresetId =
  | "lung"
  | "bone"
  | "soft"
  | "mediastinum"
  | "brain"
  | "custom"
  | "none";

export type PresetSpec = {
  id: PresetId;
  label: string;
  ww: number | null; // null for `custom` / `none`
  wl: number | null;
  swatch: "lung" | "bone" | "soft" | "mediastinum" | "brain" | "custom";
};

export const PRESETS: PresetSpec[] = [
  { id: "lung", label: "Lung", ww: 1500, wl: -600, swatch: "lung" },
  { id: "bone", label: "Bone", ww: 2000, wl: 300, swatch: "bone" },
  { id: "soft", label: "Soft tissue", ww: 400, wl: 40, swatch: "soft" },
  {
    id: "mediastinum",
    label: "Mediastinum",
    ww: 350,
    wl: 50,
    swatch: "mediastinum",
  },
  { id: "brain", label: "Brain", ww: 80, wl: 40, swatch: "brain" },
];

export type PresetMenuProps = {
  /** Currently active preset (or `"none"` / `"custom"`). */
  active: PresetId;
  onSelect: (preset: PresetSpec | "custom") => void;
  /** Disabled when active series is non-CT. */
  disabled?: boolean;
};

export function PresetMenu({ active, onSelect, disabled }: PresetMenuProps) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (!wrapRef.current) return;
      if (wrapRef.current.contains(e.target as Node)) return;
      setOpen(false);
    }
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, [open]);

  // Close on Esc.
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  function pick(p: PresetSpec | "custom") {
    onSelect(p);
    setOpen(false);
  }

  return (
    <div
      className={clsx("rv-preset-menu", open && "is-open")}
      ref={wrapRef}
      data-testid="dv-preset-menu"
    >
      <button
        type="button"
        className="rv-viewer-toolbar__btn"
        aria-label="Window/Level presets"
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={disabled}
        data-tip={
          disabled
            ? "CT presets only — adjust W/L manually"
            : "Preset (P) — CT only"
        }
        onClick={(e) => {
          e.stopPropagation();
          if (!disabled) setOpen((v) => !v);
        }}
        data-testid="dv-preset-trigger"
      >
        Preset
        <span
          className="rv-viewer-toolbar__icon"
          style={{ fontSize: 9 }}
          aria-hidden
        >
          ▾
        </span>
      </button>
      <div
        className="rv-preset-menu__panel"
        role="menu"
        aria-label="W/L presets"
      >
        {PRESETS.map((preset) => {
          const isActive = active === preset.id;
          return (
            <button
              key={preset.id}
              type="button"
              role="menuitemradio"
              aria-checked={isActive}
              className={clsx(
                "rv-preset-menu__item",
                isActive && "rv-preset-menu__item--active",
              )}
              onClick={(e) => {
                e.stopPropagation();
                pick(preset);
              }}
              data-testid={`dv-preset-${preset.id}`}
            >
              <span
                className={`rv-preset-menu__swatch rv-preset-menu__swatch--${preset.swatch}`}
                aria-hidden
              />
              <span className="rv-preset-menu__label">
                {preset.label}
                <small>
                  WW {preset.ww} · WL {preset.wl}
                </small>
              </span>
              <span className="rv-preset-menu__check" aria-hidden>
                ✓
              </span>
            </button>
          );
        })}
        <div className="rv-preset-menu__sep" aria-hidden />
        <button
          type="button"
          role="menuitemradio"
          aria-checked={active === "custom"}
          className={clsx(
            "rv-preset-menu__item",
            active === "custom" && "rv-preset-menu__item--active",
          )}
          onClick={(e) => {
            e.stopPropagation();
            pick("custom");
          }}
          data-testid="dv-preset-custom"
        >
          <span
            className="rv-preset-menu__swatch rv-preset-menu__swatch--custom"
            aria-hidden
          />
          <span className="rv-preset-menu__label">
            Custom…
            <small>drag right-button to adjust</small>
          </span>
        </button>
      </div>
    </div>
  );
}
