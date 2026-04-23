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
  get nodeEnv() {
    return optional("NODE_ENV", "development");
  },
};

export const isDemoOperatorAllowed = () => env.demoopToken.length > 0;
