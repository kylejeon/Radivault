/**
 * API key minting + masking (dev-spec-buyer-auth FR-AUTH-1, FR-AUTH-8).
 *
 * Format mirrors the existing search-admin output:
 *   rv_live_<48 url-safe chars> = 56 chars total.
 *
 * The kid (key id) is the first 16 chars (``rv_live_<8>``) — unique enough
 * to use as a row PK without leaking the full secret. We store only
 * SHA-256(plaintext) on the server.
 */

import { randomBytes, createHash } from "node:crypto";

export type MintedKey = {
  plaintext: string; // 'rv_live_…' — return ONCE then drop
  kid: string; // 'rv_live_<8>' — safe to log
  tokenHash: string; // SHA-256(plaintext) hex
};

export function mintApiKey(): MintedKey {
  const raw = randomBytes(36).toString("base64url"); // ~48 chars
  const plaintext = `rv_live_${raw}`;
  const kid = plaintext.slice(0, 16); // 'rv_live_' + 8 chars
  const tokenHash = createHash("sha256").update(plaintext).digest("hex");
  return { plaintext, kid, tokenHash };
}

/**
 * Stripe-style mask: ``rv_live_<first4>…<last4>``.
 *
 * Total visible characters: 8 (prefix) + 4 + 1 ellipsis + 4 = 17.
 * The full key is 56 chars, so 39 chars are hidden.
 */
export function maskApiKey(plaintext: string): string {
  if (!plaintext) return "rv_live_…";
  // Strip prefix to expose mid characters
  const prefixLen = "rv_live_".length;
  const body = plaintext.slice(prefixLen);
  if (body.length < 8) return "rv_live_…"; // defensive
  const first = body.slice(0, 4);
  const last = body.slice(-4);
  return `rv_live_${first}…${last}`;
}

/**
 * Mask given just a kid (e.g. ``rv_live_K8dF7sX9``) — appends ellipsis +
 * `??` to avoid implying the last 4 are known. Used on /account when we
 * have only the kid (no plaintext) at GET time.
 */
export function maskKid(kid: string): string {
  if (!kid) return "rv_live_…";
  return `${kid}…`;
}
