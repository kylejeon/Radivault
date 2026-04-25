import { NextResponse, type NextRequest } from "next/server";

/**
 * Edge middleware — MEDIUM-3 fix from qa-report-portal-redesign.
 *
 * Bounces signed-in buyers from the marketing homepage (`/`) to the
 * post-sign-in dashboard (`/dashboard`, FR-BP-20). We detect the
 * presence of the iron-session cookie only; the dashboard route still
 * runs the real auth check and redirects to `/signin` when the cookie
 * is missing or expired.
 *
 * Why cookie-presence and not full decrypt?
 *   - Decrypting iron-session requires the Node.js runtime, but Next
 *     middleware runs on the Edge by default. Promoting it to Node
 *     adds startup overhead and reduces request fan-out.
 *   - A stale-but-still-present cookie sends the user to /dashboard,
 *     which then redirects to /signin via getBuyerSession() — net
 *     effect: one extra hop in the unlikely stale case, zero overhead
 *     in the steady state.
 *
 * Scope: only `/` is rewritten. Korean homepage (`/ko`) is intentionally
 * left as marketing — buyer flows are EN-only in v0.1.
 */

const BUYER_COOKIE = "rv_session";

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (pathname !== "/") return NextResponse.next();

  const cookie = req.cookies.get(BUYER_COOKIE);
  if (!cookie?.value) return NextResponse.next();

  const url = req.nextUrl.clone();
  url.pathname = "/dashboard";
  return NextResponse.redirect(url);
}

export const config = {
  // Only the EN homepage; everything else falls through.
  matcher: ["/"],
};
