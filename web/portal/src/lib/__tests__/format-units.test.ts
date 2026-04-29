/**
 * Tests for ``web/portal/src/lib/format/units.ts``.
 *
 * dev-spec-pixel-spatial-fields AC-PSF-6.5 — unit-helper output must
 * match the SI reference strings the Pixel & Spatial / Acquisition
 * cards render.
 */

import { describe, expect, it } from "vitest";

import {
  formatBits,
  formatKv,
  formatMa,
  formatMm,
  formatMmPair,
  formatMs,
  formatPx,
  formatTesla,
} from "@/lib/format/units";

describe("formatMm", () => {
  it("rounds to 3 decimals", () => {
    expect(formatMm(0.7031)).toBe("0.703 mm");
    expect(formatMm(1.25)).toBe("1.250 mm");
  });

  it("returns null for null/undefined/NaN", () => {
    expect(formatMm(null)).toBeNull();
    expect(formatMm(undefined)).toBeNull();
    expect(formatMm(Number.NaN)).toBeNull();
  });
});

describe("formatMmPair", () => {
  it("formats both axes", () => {
    expect(formatMmPair(0.7031, 0.7031)).toBe("0.703 × 0.703 mm");
  });

  it("returns null when either axis is missing", () => {
    expect(formatMmPair(0.7, null)).toBeNull();
    expect(formatMmPair(null, 0.7)).toBeNull();
    expect(formatMmPair(null, null)).toBeNull();
  });
});

describe("formatKv", () => {
  it("strips trailing decimals when integer", () => {
    expect(formatKv(120)).toBe("120 kV");
    expect(formatKv(120.0)).toBe("120 kV");
  });

  it("keeps 1 decimal when non-integer", () => {
    expect(formatKv(119.9)).toBe("119.9 kV");
  });

  it("null short-circuits", () => {
    expect(formatKv(null)).toBeNull();
  });
});

describe("formatMs / formatMa / formatTesla", () => {
  it("ms passes through integer", () => {
    expect(formatMs(500)).toBe("500 ms");
    expect(formatMs(null)).toBeNull();
  });
  it("mA passes through integer", () => {
    expect(formatMa(250)).toBe("250 mA");
    expect(formatMa(null)).toBeNull();
  });
  it("Tesla passes through float", () => {
    expect(formatTesla(1.5)).toBe("1.5 T");
    expect(formatTesla(null)).toBeNull();
  });
});

describe("formatPx", () => {
  it("formats rows × columns", () => {
    expect(formatPx(512, 512)).toBe("512 × 512");
    expect(formatPx(640, 480)).toBe("640 × 480");
  });
  it("returns null when either dim is missing", () => {
    expect(formatPx(512, null)).toBeNull();
    expect(formatPx(null, 512)).toBeNull();
  });
});

describe("formatBits", () => {
  it("formats alloc / stored", () => {
    expect(formatBits(16, 12)).toBe("16 / 12 (alloc / stored)");
  });
  it("returns null when either is missing", () => {
    expect(formatBits(16, null)).toBeNull();
    expect(formatBits(null, 12)).toBeNull();
  });
});
