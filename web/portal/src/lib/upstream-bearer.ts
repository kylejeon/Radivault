/**
 * Per-hospital upstream bearer lookup (HIGH-2 fix from
 * docs/qa/qa-report-portal-redesign.md).
 *
 * The portal hospital BFFs proxy to central-ingest. v0.1.5 will replace
 * this with a per-session issued token; until then the BFF derives the
 * bearer from `process.env` keyed by the iron-session ``hospitalId``.
 *
 * Convention: ``HOSP-001`` -> env var ``HOSP_001_BEARER``. The hyphen is
 * stripped so the env var stays POSIX-clean.
 *
 * Backwards compatibility: if no per-hospital var is set we fall back to
 * the legacy single ``HOSPITAL_UPSTREAM_BEARER`` and log a warning so the
 * deprecation is visible. Removing the fallback is a v0.1.1 follow-up
 * once every deploy has migrated.
 *
 * The function is intentionally synchronous so route handlers can call it
 * inline without an extra await. It throws when nothing is configured —
 * the BFF must catch and translate to a 503 response (see usage in
 * /api/hospital/*).
 */

const ENV_PREFIX = "HOSP_";
const ENV_SUFFIX = "_BEARER";

/** Convert "HOSP-001" -> "HOSP_001_BEARER". */
function envKeyFor(hospitalId: string): string {
  // Strip the leading "HOSP-" so we can re-attach our underscore form.
  // Anything else (legacy ids, future namespaces) is normalised by
  // replacing every non-alphanumeric character with `_`.
  const stem = hospitalId.replace(/^HOSP-/i, "").replace(/[^a-zA-Z0-9]/g, "_");
  return `${ENV_PREFIX}${stem}${ENV_SUFFIX}`;
}

let warnedFallback = false;

export function bearerForHospital(hospitalId: string): string | null {
  if (!hospitalId) return null;
  const key = envKeyFor(hospitalId);
  const token = process.env[key];
  if (token && token.length > 0) return token;

  // Backwards-compat — single shared bearer (deprecated).
  const fallback = process.env.HOSPITAL_UPSTREAM_BEARER;
  if (fallback && fallback.length > 0) {
    if (!warnedFallback) {
      // Emit once per process so the log isn't spammed on every request.
      // Using console.warn (Next.js server captures it).
      console.warn(
        `[upstream-bearer] No ${key} configured for ${hospitalId}; ` +
          "falling back to HOSPITAL_UPSTREAM_BEARER. " +
          "This fallback is deprecated — set per-hospital env vars before D-day.",
      );
      warnedFallback = true;
    }
    return fallback;
  }
  return null;
}

/** Test seam — clears the once-per-process warning gate. */
export function __resetBearerWarning(): void {
  warnedFallback = false;
}
