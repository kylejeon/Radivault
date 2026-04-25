/**
 * Common error envelope + request-id helpers for /api/auth/* (dev-spec
 * §7.11). Envelope shape:
 *
 *   { error: { code: 'ERR_*', message: string, field?: string }, request_id }
 *
 * Routes call ``authError(code, message, status, field?)`` and ``ok(body)``
 * to keep the surface consistent.
 */

import { NextResponse } from "next/server";
import { randomBytes } from "node:crypto";

export function newRequestId(): string {
  return "req_" + randomBytes(8).toString("hex");
}

export function authError(
  code: string,
  message: string,
  status: number,
  field?: string,
  requestId?: string,
): NextResponse {
  return NextResponse.json(
    {
      error: { code, message, ...(field ? { field } : {}) },
      request_id: requestId ?? newRequestId(),
    },
    { status },
  );
}

export function authOk<T extends Record<string, unknown>>(
  body: T,
  init?: { status?: number; cookieName?: string },
): NextResponse {
  return NextResponse.json(body, { status: init?.status ?? 200 });
}

/**
 * Resolve a client-IP-ish key for rate limiting. Cloudflare and most edge
 * proxies forward the original via ``cf-connecting-ip`` or
 * ``x-forwarded-for``; in dev/Playwright the headers are absent so we fall
 * back to a literal token (single bucket = global limit, fine for tests).
 */
export function resolveClientIp(headers: Headers): string {
  return (
    headers.get("cf-connecting-ip") ??
    headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
    headers.get("x-real-ip") ??
    "ip:unknown"
  );
}

export function resolveUserAgent(headers: Headers): string {
  return headers.get("user-agent") ?? "ua:unknown";
}
