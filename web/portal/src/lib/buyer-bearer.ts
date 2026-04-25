/**
 * bearerForBuyer — resolve the upstream Bearer for a buyer-side BFF call.
 *
 * D-13 BLOCKER fix (qa-report-d13-demo-rehearsal §BLOCKER #2 + planner
 * directive 2026-04-25). dev-spec-buyer-auth Q15 (L.1010) calls for the
 * portal SSR to call the search service with a long-lived
 * ``INTERNAL_SEARCH_KEY``, while the buyer's own kid is forwarded in
 * audit metadata only. Until this helper landed, every BFF route checked
 * ``session.apiKey`` only — but v0.2 sessions (email/password signin)
 * have no apiKey on the cookie because:
 *
 *   1. The signup endpoint returns the plaintext ONCE in the response
 *      body (apiKeyRevealOnce) and never stores it server-side.
 *   2. Both signin and signup explicitly ``delete session.apiKey;``
 *      (signin route L.135, signup route L.213).
 *
 * As a result, every v0.2 buyer hitting /search → /api/search/studies
 * got 401 ERR_AUTH_EXPIRED → SearchApp redirected to /signin → infinite
 * loop. The fix below makes the BFF prefer the user's own ``apiKey`` when
 * present (legacy paste-mode + the brief signup-reveal window) and fall
 * back to the system ``INTERNAL_SEARCH_KEY`` otherwise.
 *
 * The mode return value lets the caller forward an ``X-Acting-Buyer-Mode``
 * header to the upstream so audit_event rows can distinguish "user key"
 * vs "internal key acting on behalf of buyerPk=N". The search-side
 * audit-attribution change is v0.1.5 backlog — for now the header is
 * informational only and the search service ignores it.
 */

import { env } from "@/lib/env";
import type { BuyerSession } from "@/lib/session";

export type BearerForBuyerResult =
  | { ok: true; bearer: string; mode: "user" | "internal" }
  | { ok: false; reason: "no_session" | "no_internal_key" };

/**
 * Resolve the Bearer used for an upstream call on behalf of a buyer.
 *
 * Decision table:
 *
 *   session.apiKey   session.buyerPk   internalSearchKey   →  result
 *   ──────────────   ───────────────   ─────────────────   ─────────
 *   present          *                 *                   →  ok user
 *   absent           present           present             →  ok internal
 *   absent           present           absent              →  fail no_internal_key
 *   absent           absent            *                   →  fail no_session
 *
 * Why "user" wins when both are present: the legacy paste-mode flow and
 * the signup-reveal-modal window both put the buyer's own plaintext on
 * the cookie. Routing those calls through INTERNAL_SEARCH_KEY would
 * silently rewrite the upstream audit-actor — a regression we explicitly
 * avoid until the search-side X-Acting-Buyer-Pk wiring lands.
 */
export function bearerForBuyer(session: BuyerSession): BearerForBuyerResult {
  if (session.apiKey && session.apiKey.length > 0) {
    return { ok: true, bearer: session.apiKey, mode: "user" };
  }
  if (!session.buyerPk) {
    return { ok: false, reason: "no_session" };
  }
  const internal = env.internalSearchKey;
  if (!internal || internal.length === 0) {
    return { ok: false, reason: "no_internal_key" };
  }
  return { ok: true, bearer: internal, mode: "internal" };
}

/**
 * Build the X-Acting-Buyer-* headers a BFF should forward upstream when
 * acting on behalf of a buyer with INTERNAL_SEARCH_KEY. Today the search
 * service ignores these — they exist so v0.1.5 (which will rewrite the
 * audit_event.buyer_pk attribution) has a clean header contract to read.
 *
 * Always safe to spread into a fetch headers init: keys with undefined
 * values are omitted by the JSON-style filter.
 */
export function actingBuyerHeaders(
  session: BuyerSession,
  mode: "user" | "internal",
): Record<string, string> {
  const out: Record<string, string> = { "X-Acting-Buyer-Mode": mode };
  if (session.buyerPk !== undefined) {
    out["X-Acting-Buyer-Pk"] = String(session.buyerPk);
  }
  return out;
}
