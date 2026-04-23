import { NextResponse } from "next/server";
import { createHash, timingSafeEqual } from "node:crypto";
import { env } from "@/lib/env";
import { getHospitalSession } from "@/lib/session";

/**
 * POST /api/hospital/session — hospital admin sign-in (D-5).
 *
 * v0.1 stub: ``RV_HOSPITAL_ADMIN_TOKENS`` is a JSON map
 * ``{"hospital_id": "argon2id_hash"}`` shipped as env. For the demo the hash
 * check is SHA-256 (argon2 dep bloats the portal bundle) — v0.1.5 migrates
 * to argon2id via a separate worker. The hash choice is documented in
 * dev-spec §11 Q-Sec-1 (Kyle decision pending).
 *
 * Format of stored hash: ``sha256:<hex>``. Callers generate via:
 *   node -e "console.log('sha256:' + require('crypto').createHash('sha256').update(process.argv[1]).digest('hex'))" <plaintext>
 */
export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as {
    hospital_id?: string;
    admin_token?: string;
  };
  const hospitalId = (body.hospital_id ?? "").trim();
  const token = (body.admin_token ?? "").trim();
  if (!hospitalId || !token) {
    return NextResponse.json(
      { error: "ERR_AUTH_FORMAT", detail: "hospital_id and admin_token are required" },
      { status: 400 },
    );
  }
  const tokens = env.hospitalAdminTokens;
  const stored = tokens[hospitalId];
  if (!stored) {
    return NextResponse.json(
      { error: "ERR_AUTH_INVALID", detail: "hospital not registered" },
      { status: 401 },
    );
  }
  const expected = stored.startsWith("sha256:")
    ? stored.slice("sha256:".length)
    : stored;
  const candidate = createHash("sha256").update(token).digest("hex");
  const expectedBuf = Buffer.from(expected, "hex");
  const candidateBuf = Buffer.from(candidate, "hex");
  if (expectedBuf.length !== candidateBuf.length || !timingSafeEqual(expectedBuf, candidateBuf)) {
    return NextResponse.json(
      { error: "ERR_AUTH_INVALID", detail: "token mismatch" },
      { status: 401 },
    );
  }
  const session = await getHospitalSession();
  session.hospitalId = hospitalId;
  session.signedInAt = Date.now();
  session.expiresAt = Date.now() + 12 * 60 * 60 * 1000;
  await session.save();
  return NextResponse.json({ ok: true });
}
