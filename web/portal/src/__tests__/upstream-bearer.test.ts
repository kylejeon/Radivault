/**
 * upstream-bearer — HIGH-2 fix from qa-report-portal-redesign.
 *
 * Covers the per-hospital env lookup, fallback to the legacy single
 * bearer, and the once-per-process warning gate.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  bearerForHospital,
  __resetBearerWarning,
} from "@/lib/upstream-bearer";

const ORIGINAL_ENV = { ...process.env };

function clearBearerEnv() {
  for (const k of Object.keys(process.env)) {
    if (k.startsWith("HOSP_") && k.endsWith("_BEARER")) delete process.env[k];
  }
  delete process.env.HOSPITAL_UPSTREAM_BEARER;
}

describe("bearerForHospital", () => {
  beforeEach(() => {
    clearBearerEnv();
    __resetBearerWarning();
  });

  afterEach(() => {
    process.env = { ...ORIGINAL_ENV };
  });

  it("returns the per-hospital bearer for HOSP-001", () => {
    process.env.HOSP_001_BEARER = "rvct_001";
    expect(bearerForHospital("HOSP-001")).toBe("rvct_001");
  });

  it("returns the per-hospital bearer for HOSP-002", () => {
    process.env.HOSP_002_BEARER = "rvct_002";
    expect(bearerForHospital("HOSP-002")).toBe("rvct_002");
  });

  it("does not leak HOSP-001 bearer when HOSP-002 is requested", () => {
    process.env.HOSP_001_BEARER = "rvct_001";
    expect(bearerForHospital("HOSP-002")).toBeNull();
  });

  it("falls back to HOSPITAL_UPSTREAM_BEARER when no per-hospital var", () => {
    process.env.HOSPITAL_UPSTREAM_BEARER = "rvct_legacy";
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    try {
      expect(bearerForHospital("HOSP-001")).toBe("rvct_legacy");
      expect(warn).toHaveBeenCalledOnce();
    } finally {
      warn.mockRestore();
    }
  });

  it("warns at most once per process for the fallback", () => {
    process.env.HOSPITAL_UPSTREAM_BEARER = "rvct_legacy";
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    try {
      bearerForHospital("HOSP-001");
      bearerForHospital("HOSP-002");
      bearerForHospital("HOSP-003");
      expect(warn).toHaveBeenCalledOnce();
    } finally {
      warn.mockRestore();
    }
  });

  it("returns null when neither env is set", () => {
    expect(bearerForHospital("HOSP-001")).toBeNull();
  });

  it("returns null for an empty hospitalId", () => {
    process.env.HOSPITAL_UPSTREAM_BEARER = "rvct_legacy";
    expect(bearerForHospital("")).toBeNull();
  });

  it("normalises legacy ids without the HOSP- prefix", () => {
    process.env.HOSP_legacy_BEARER = "rvct_legacy_id";
    expect(bearerForHospital("legacy")).toBe("rvct_legacy_id");
  });
});
