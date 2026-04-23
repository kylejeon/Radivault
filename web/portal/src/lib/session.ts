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

export type BuyerSession = {
  apiKey?: string;
  buyerId?: string;
  tier?: string;
  signedInAt?: number;
};

export type HospitalSession = {
  hospitalId?: string;
  signedInAt?: number;
  expiresAt?: number;
};

const twelveHoursSeconds = 60 * 60 * 12;

function buyerOptions(): SessionOptions {
  return {
    password: env.sessionPassword,
    cookieName: "rv_session",
    cookieOptions: {
      httpOnly: true,
      secure: env.nodeEnv === "production",
      sameSite: "lax",
      maxAge: twelveHoursSeconds,
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
