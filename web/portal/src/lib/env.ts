/**
 * Typed environment variables (BFF-side only).
 *
 * All upstream URLs and secrets are read here. Importing this module in a
 * client component is a bug — the build step should fail because the
 * referenced keys never start with `NEXT_PUBLIC_`.
 *
 * Missing values are tolerated at module load time but throw on first access
 * so that developer machines without a `.env.local` can still run the portal
 * against the demo-canned fallback (see `src/lib/canned.ts`).
 */

function required(key: string): string {
  const v = process.env[key];
  if (!v) {
    throw new Error(
      `Missing required env var: ${key}. ` +
        `Copy web/portal/.env.example to .env.local and fill it in.`,
    );
  }
  return v;
}

function optional(key: string, fallback = ""): string {
  return process.env[key] ?? fallback;
}

export const env = {
  get centralIngestUrl() {
    return required("CENTRAL_INGEST_URL");
  },
  get searchUrl() {
    return required("SEARCH_URL");
  },
  get fulfillmentUrl() {
    return required("FULFILLMENT_URL");
  },
  get sessionPassword() {
    return required("SESSION_PASSWORD");
  },
  get demoopToken() {
    return optional("DEMOOP_TOKEN");
  },
  get hospitalAdminTokens(): Record<string, string> {
    const raw = optional("RV_HOSPITAL_ADMIN_TOKENS", "{}");
    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        return parsed as Record<string, string>;
      }
    } catch {
      // fall through
    }
    return {};
  },
  get hospitalUpstreamBearer() {
    return optional("HOSPITAL_UPSTREAM_BEARER");
  },
  // ---- INTERNAL_SEARCH_KEY (D-13 BLOCKER fix; dev-spec-buyer-auth Q15) -----
  // Portal SSR holds a long-lived rv_live_* search key issued for the
  // system buyer "buy_portal_internal". It's used by every BFF route that
  // proxies to the search/fulfillment services on behalf of a v0.2
  // (email/password) session — those sessions intentionally have no
  // ``apiKey`` on the cookie (the plaintext is shown ONCE in the signup
  // reveal modal and never re-stored client-side).
  //
  // Failure semantics (intentional):
  //   - returns "" when ENV is missing → bearerForBuyer() flips to
  //     {ok:false, reason:"no_internal_key"} so the BFF returns a clean
  //     401 ERR_AUTH_EXPIRED with a specific detail.
  //   - we deliberately do NOT throw at module-import time: a misconfigured
  //     deploy must still produce a working /signin page so the operator
  //     can read the error in the response body.
  //   - in production, the operator MUST set this — see
  //     web/portal/scripts/auto-seed-buyer.mjs which prints a WARN at
  //     dev-server boot when the var is missing.
  get internalSearchKey() {
    return optional("INTERNAL_SEARCH_KEY", "");
  },
  get nodeEnv() {
    return optional("NODE_ENV", "development");
  },
  // ---- buyer-auth (dev-spec-buyer-auth FR-AUTH-12) -------------------------
  get buyerAuthSkipEmailVerify() {
    // HIGH-1 (qa-report-buyer-auth) intent — production must be fail-closed
    // when the operator forgets to set the flag. We achieve that by making
    // the default depend on NODE_ENV:
    //   - dev/test  → default "true"  (demo/CI ergonomics, OTP skipped)
    //   - production → default "false" (skip disabled unless ENV explicit)
    //
    // BLOCKER #2 (qa-report-d13-demo-rehearsal) re-fix: the previous guard
    // threw on prerender for /signup + /ko/signup whenever NODE_ENV was
    // production AND raw !== "false", which meant `pnpm build` always
    // failed. AC-DEMO-4 only requires that ENV-omission stay fail-closed
    // in prod; explicit "true" is a legitimate operator override (e.g.
    // building a demo artifact for the CEO deck) and must not throw.
    const isProduction = process.env.NODE_ENV === "production";
    const fallback = isProduction ? "false" : "true";
    const raw = optional("BUYER_AUTH_SKIP_EMAIL_VERIFY", fallback);
    return raw === "true";
  },
  get buyerAuthPwdResetDisabled() {
    return optional("BUYER_AUTH_PWD_RESET_DISABLED", "false") === "true";
  },
  get buyerAuthDemoSeed() {
    return optional("BUYER_AUTH_DEMO_SEED", "true") === "true";
  },
};

export const isDemoOperatorAllowed = () => env.demoopToken.length > 0;
