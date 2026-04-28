/**
 * iron-session wrapper (dev-spec §6.2 L-2).
 *
 * Two separate cookies:
 *  - ``rv_session`` — buyer portal (stores encrypted API key + tier).
 *  - ``rv_hospital_session`` — hospital dashboard (stores hospital_id + expiry).
 *
 * Neither cookie is accessible to client JavaScript. Route handlers decrypt
 * at the edge of every request.
 */

import { cookies } from "next/headers";
import { getIronSession, IronSession, SessionOptions } from "iron-session";
import { env } from "@/lib/env";

/**
 * Buyer session payload.
 *
 * v0.1 (legacy, dev-spec-buyer-portal-demo) carried only ``apiKey`` —
 * the raw 56-char rv_live_ string the buyer pasted on /signin. v0.2
 * (dev-spec-buyer-auth FR-AUTH-7) introduces email/password signup and the
 * cookie payload extends to:
 *
 *   - buyerId (public id, audit-safe)
 *   - email (audit display)
 *   - emailVerified (gating /orders/new)
 *   - sessionVersion (bumped on password-reset / account-delete; mismatched
 *     versions ⇒ destroy session on next request)
 *   - locale (en | ko)
 *
 * The legacy ``apiKey`` field is preserved during the 90-day deprecation
 * window for /signin/legacy paste-mode callers (dev-spec §12.2). New
 * email/password signups DO NOT set apiKey on the cookie — the plaintext
 * is returned exactly once via ``apiKeyRevealOnce`` in the signup response
 * body and never re-stored client-side.
 */
export type BuyerSession = {
  // legacy paste-mode (90-day deprecation window)
  apiKey?: string;
  // v0.2 email/password
  buyerPk?: number;
  buyerId?: string;
  email?: string;
  emailVerified?: boolean;
  sessionVersion?: number;
  locale?: "en" | "ko";
  tier?: string;
  signedInAt?: number;
  // Display org for MarketplaceNav avatar (Kyle 2026-04-28). Optional —
  // legacy / pre-v0.3.3 cookies fall back to the email local-part.
  org?: string;
};

export type HospitalSession = {
  hospitalId?: string;
  signedInAt?: number;
  expiresAt?: number;
};

// dev-spec-buyer-auth FR-AUTH-7 / Q13: 24h sliding + 30d absolute. The
// cookie maxAge here is the sliding bound; absolute-30d enforcement happens
// in route handlers when they read ``signedInAt``. Legacy /signin paste-mode
// keeps the old 12h bound only because that flow is being removed in v0.1.5.
const twelveHoursSeconds = 60 * 60 * 12;
const slidingTwentyFourHoursSeconds = 60 * 60 * 24;
export const ABSOLUTE_SESSION_MS = 30 * 24 * 60 * 60 * 1000;

function buyerOptions(): SessionOptions {
  return {
    password: env.sessionPassword,
    cookieName: "rv_session",
    cookieOptions: {
      httpOnly: true,
      secure: env.nodeEnv === "production",
      sameSite: "lax",
      // 24h sliding (FR-AUTH-7 / Q13). The 30d absolute cap is enforced
      // in the consumers of getBuyerSession() against ``signedInAt``.
      maxAge: slidingTwentyFourHoursSeconds,
      path: "/",
    },
  };
}

function hospitalOptions(): SessionOptions {
  return {
    password: env.sessionPassword,
    cookieName: "rv_hospital_session",
    cookieOptions: {
      httpOnly: true,
      secure: env.nodeEnv === "production",
      sameSite: "lax",
      maxAge: twelveHoursSeconds,
      path: "/",
    },
  };
}

export async function getBuyerSession(): Promise<IronSession<BuyerSession>> {
  const jar = await cookies();
  return getIronSession<BuyerSession>(jar, buyerOptions());
}

export async function getHospitalSession(): Promise<IronSession<HospitalSession>> {
  const jar = await cookies();
  return getIronSession<HospitalSession>(jar, hospitalOptions());
}
