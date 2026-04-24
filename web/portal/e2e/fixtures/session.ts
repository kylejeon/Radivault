import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { sealData } from "iron-session";
import type { BrowserContext } from "@playwright/test";

/**
 * Session cookie helpers for e2e tests.
 *
 * The portal uses iron-session for both the buyer (``rv_session``) and the
 * hospital admin (``rv_hospital_session``) cookies. Those cookies are
 * encrypted with ``SESSION_PASSWORD`` — so we can't just hand-roll a value.
 * Instead we import iron-session's ``sealData`` here and bake a valid cookie
 * that the Next.js server will happily decrypt.
 *
 * The session password is read from ``web/portal/.env.local`` at runtime.
 * If the file is missing or the key isn't set, we throw — the alternative
 * (falling through to a mock key) would produce silently-broken sessions.
 */

const ENV_LOCAL = resolve(__dirname, "../../.env.local");

let cachedPassword: string | null = null;

function readSessionPassword(): string {
  if (cachedPassword) return cachedPassword;
  if (process.env.SESSION_PASSWORD && process.env.SESSION_PASSWORD.length >= 32) {
    cachedPassword = process.env.SESSION_PASSWORD;
    return cachedPassword;
  }
  let content: string;
  try {
    content = readFileSync(ENV_LOCAL, "utf8");
  } catch (err) {
    throw new Error(
      `Cannot read ${ENV_LOCAL} for SESSION_PASSWORD. ` +
        `Copy .env.example to .env.local and fill SESSION_PASSWORD. (${String(err)})`,
    );
  }
  const match = content.match(/^SESSION_PASSWORD=(.+)$/m);
  if (!match) {
    throw new Error(
      `SESSION_PASSWORD is missing from ${ENV_LOCAL}. Generate one via ` +
        `scripts/demo_setup/generate_demo_secrets.sh or paste any 32+ char string.`,
    );
  }
  const value = match[1].trim();
  if (value.length < 32) {
    throw new Error(`SESSION_PASSWORD must be at least 32 characters; got ${value.length}.`);
  }
  cachedPassword = value;
  return value;
}

/**
 * Seal a BuyerSession payload and return a cookie string value. iron-session
 * sets maxAge on the cookie, not on the seal, so the returned seal is valid
 * for the default TTL (14 days) — plenty for a 30-second test run.
 */
async function sealBuyerSession(): Promise<string> {
  return sealData(
    {
      apiKey: "rv_live_e2edemo_00000000000000000000000000000000",
      signedInAt: Date.now(),
    },
    { password: readSessionPassword() },
  );
}

async function sealHospitalSession(hospitalId: string): Promise<string> {
  return sealData(
    {
      hospitalId,
      signedInAt: Date.now(),
      expiresAt: Date.now() + 12 * 60 * 60 * 1000,
    },
    { password: readSessionPassword() },
  );
}

/**
 * Inject a forged ``rv_session`` cookie into the given browser context so
 * every subsequent request is treated as signed-in. Prefer this over driving
 * the sign-in form because the real ``/api/session`` handler performs a live
 * upstream probe that our tests are trying to avoid.
 */
export async function injectBuyerSession(context: BrowserContext): Promise<void> {
  const value = await sealBuyerSession();
  await context.addCookies([
    {
      name: "rv_session",
      value,
      domain: "localhost",
      path: "/",
      httpOnly: true,
      secure: false,
      sameSite: "Lax",
    },
  ]);
}

/** Inject a forged hospital-admin session cookie for a given hospital_id. */
export async function injectHospitalSession(
  context: BrowserContext,
  hospitalId = "HOSP-001",
): Promise<void> {
  const value = await sealHospitalSession(hospitalId);
  await context.addCookies([
    {
      name: "rv_hospital_session",
      value,
      domain: "localhost",
      path: "/",
      httpOnly: true,
      secure: false,
      sameSite: "Lax",
    },
  ]);
}
