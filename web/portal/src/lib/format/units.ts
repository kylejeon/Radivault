/**
 * Unit-formatting helpers for the buyer study-detail viewer.
 *
 * dev-spec-pixel-spatial-fields FR-PSF-8.3.
 *
 * All helpers accept ``null | undefined`` and return ``null`` so callers can
 * pipe them straight into the existing ``MISSING = "—"`` placeholder
 * convention (FR-PSF-8.4) without an extra null-check at every call site:
 *
 * ```tsx
 * <MetaCard rows={[
 *   { key: "ps", label: "PixelSpacing", value: formatMmPair(s.pixel_spacing_x, s.pixel_spacing_y) },
 * ]} />
 * ```
 *
 * SI units only — no conversion or locale-specific punctuation.
 */

const MISSING_VALUE = null;

function isFiniteNumber(v: number | null | undefined): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

/** ``0.7031 -> "0.703 mm"`` (3-decimal rounding). */
export function formatMm(v: number | null | undefined): string | null {
  if (!isFiniteNumber(v)) return MISSING_VALUE;
  return `${v.toFixed(3)} mm`;
}

/** ``(0.7031, 0.7031) -> "0.703 × 0.703 mm"`` — both axes required. */
export function formatMmPair(
  x: number | null | undefined,
  y: number | null | undefined,
): string | null {
  if (!isFiniteNumber(x) || !isFiniteNumber(y)) return MISSING_VALUE;
  return `${x.toFixed(3)} × ${y.toFixed(3)} mm`;
}

/** ``120 -> "120 kV"``. */
export function formatKv(v: number | null | undefined): string | null {
  if (!isFiniteNumber(v)) return MISSING_VALUE;
  // KVP is reported as DS in DICOM; convention is integer kilovolts but
  // some scanners emit 119.9 — round to 1 decimal and trim trailing zero.
  const rounded = Number(v.toFixed(1));
  const text =
    Number.isInteger(rounded) ? rounded.toString() : rounded.toString();
  return `${text} kV`;
}

/** ``500 -> "500 ms"``. */
export function formatMs(v: number | null | undefined): string | null {
  if (!isFiniteNumber(v)) return MISSING_VALUE;
  return `${v} ms`;
}

/** ``250 -> "250 mA"``. */
export function formatMa(v: number | null | undefined): string | null {
  if (!isFiniteNumber(v)) return MISSING_VALUE;
  return `${v} mA`;
}

/** ``1.5 -> "1.5 T"``. */
export function formatTesla(v: number | null | undefined): string | null {
  if (!isFiniteNumber(v)) return MISSING_VALUE;
  return `${v} T`;
}

/** ``(512, 512) -> "512 × 512"``. */
export function formatPx(
  rows: number | null | undefined,
  columns: number | null | undefined,
): string | null {
  if (!isFiniteNumber(rows) || !isFiniteNumber(columns)) return MISSING_VALUE;
  return `${rows} × ${columns}`;
}

/** ``(16, 12) -> "16 / 12 (alloc / stored)"``. */
export function formatBits(
  allocated: number | null | undefined,
  stored: number | null | undefined,
): string | null {
  if (!isFiniteNumber(allocated) || !isFiniteNumber(stored))
    return MISSING_VALUE;
  return `${allocated} / ${stored} (alloc / stored)`;
}
