import { NextResponse } from "next/server";
import { env, isDemoOperatorAllowed } from "@/lib/env";

/**
 * POST /api/demoop/enable — toggle Demo Operator Mode.
 *
 * Server refuses unless ``DEMOOP_TOKEN`` is set (dev-spec AC-D-2). The BFF
 * sets a short-lived, non-HttpOnly cookie so the client badge can render.
 * All the actual demo features are rendered client-side on the presence of
 * this cookie — no secret data is keyed off it.
 */
export async function POST(req: Request) {
  if (!isDemoOperatorAllowed()) {
    return NextResponse.json(
      { error: "ERR_DEMOOP_DISABLED", detail: "DEMOOP_TOKEN not configured" },
      { status: 403 },
    );
  }
  const header = req.headers.get("X-Demoop-Token");
  if (header && header !== env.demoopToken) {
    return NextResponse.json(
      { error: "ERR_DEMOOP_INVALID", detail: "Demo token mismatch" },
      { status: 403 },
    );
  }
  const res = NextResponse.json({ ok: true });
  res.cookies.set("rv_demoop", "1", {
    path: "/",
    httpOnly: false, // Must be JS-readable for the badge.
    sameSite: "lax",
    maxAge: 2 * 60 * 60, // 2h
  });
  return res;
}
