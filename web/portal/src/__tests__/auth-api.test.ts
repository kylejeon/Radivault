/**
 * Integration tests for the /api/auth/* + /api/account/api-key route
 * handlers. Calls the route function directly with a synthesized Request
 * (matches the contact-api.test.ts pattern).
 *
 * Covers AC-AUTH-1.* / 2.* / 3.* / 4.* / 5.* / 6.* / 8.*.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";

// SESSION_PASSWORD must be defined before iron-session imports load.
process.env.SESSION_PASSWORD = "test_session_password_at_least_32_chars_long_xx";
process.env.BUYER_AUTH_SKIP_EMAIL_VERIFY = "true";
process.env.BUYER_AUTH_PWD_RESET_DISABLED = "false";

// next/headers cookies() requires a request scope under app router. In
// vitest we provide a minimal in-memory CookieStore so iron-session can
// read+write without crashing. The store persists across test cases until
// resetCookieStore() is called in beforeEach.
type CookieEntry = { name: string; value: string };
let cookieJar: CookieEntry[] = [];
function resetCookieStore() {
  cookieJar = [];
}
const cookieStoreMock = {
  get(name: string) {
    const found = cookieJar.find((c) => c.name === name);
    return found ? { name, value: found.value } : undefined;
  },
  getAll() {
    return cookieJar.map((c) => ({ name: c.name, value: c.value }));
  },
  has(name: string) {
    return cookieJar.some((c) => c.name === name);
  },
  set(name: string, value: string) {
    const existing = cookieJar.find((c) => c.name === name);
    if (existing) existing.value = value;
    else cookieJar.push({ name, value });
  },
  delete(name: string) {
    cookieJar = cookieJar.filter((c) => c.name !== name);
  },
  // iron-session calls .set({ name, value, ...options })
};
// allow object-form set used by iron-session
(cookieStoreMock as unknown as { set: (a: unknown, b?: unknown) => void }).set =
  function setCookie(arg1: unknown, arg2?: unknown) {
    if (typeof arg1 === "string" && typeof arg2 === "string") {
      const existing = cookieJar.find((c) => c.name === arg1);
      if (existing) existing.value = arg2;
      else cookieJar.push({ name: arg1, value: arg2 });
      return;
    }
    if (arg1 && typeof arg1 === "object") {
      const o = arg1 as { name: string; value: string };
      const existing = cookieJar.find((c) => c.name === o.name);
      if (existing) existing.value = o.value;
      else cookieJar.push({ name: o.name, value: o.value });
    }
  };

vi.mock("next/headers", () => ({
  cookies: () => cookieStoreMock,
}));

import { POST as signupPOST } from "@/app/api/auth/signup/route";
import { POST as signinPOST } from "@/app/api/auth/signin/route";
import { POST as signoutPOST } from "@/app/api/auth/signout/route";
import { POST as resetReqPOST } from "@/app/api/auth/password-reset/request/route";
import { POST as resetConfirmPOST } from "@/app/api/auth/password-reset/confirm/route";
import { GET as apikeyGET, POST as apikeyPOST } from "@/app/api/account/api-key/route";
import { getAuthStore } from "@/lib/auth/store";
import {
  signupRateLimiter,
  signinIpRateLimiter,
  signinAccountRateLimiter,
  apiKeyRotateRateLimiter,
  passwordResetIpRateLimiter,
} from "@/lib/rate-limit";

function jsonReq(body: unknown, ip = "203.0.113.10"): Request {
  return new Request("http://localhost/api/auth/test", {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-forwarded-for": ip },
    body: JSON.stringify(body),
  });
}

const validSignup = {
  email: "alice@acme.ai",
  password: "correct-horse-battery-staple",
  organization: "Acme",
  intent: "commercial-ai" as const,
  tosPrivacyConsent: true,
  marketingEmailOptIn: false,
  pipaConsents: null,
  locale: "en" as const,
};

beforeEach(() => {
  getAuthStore().reset();
  signupRateLimiter.reset();
  signinIpRateLimiter.reset();
  signinAccountRateLimiter.reset();
  apiKeyRotateRateLimiter.reset();
  passwordResetIpRateLimiter.reset();
  resetCookieStore();
});

describe("/api/auth/signup (FR-AUTH-1)", () => {
  it("AC-AUTH-1.3 returns apiKeyRevealOnce and never echoes the password", async () => {
    const res = await signupPOST(jsonReq(validSignup));
    expect(res.status).toBe(201);
    const body = await res.json();
    expect(body.apiKeyRevealOnce).toMatch(/^rv_live_/);
    expect(body.apiKeyKid).toMatch(/^rv_live_/);
    expect(JSON.stringify(body)).not.toContain("correct-horse-battery-staple");
  });

  it("AC-AUTH-1.2 duplicate email → 409 ERR_EMAIL_TAKEN", async () => {
    await signupPOST(jsonReq(validSignup, "203.0.113.20"));
    const res = await signupPOST(jsonReq(validSignup, "203.0.113.21"));
    expect(res.status).toBe(409);
    const body = await res.json();
    expect(body.error.code).toBe("ERR_EMAIL_TAKEN");
  });

  it("AC-AUTH-3.2 password too short → 400 ERR_VALIDATION (field=password)", async () => {
    const res = await signupPOST(
      jsonReq({ ...validSignup, password: "short" }, "203.0.113.30"),
    );
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("ERR_VALIDATION");
    expect(body.error.field).toBe("password");
  });

  it("AC-AUTH-3.3 password too long → 400 ERR_VALIDATION", async () => {
    const res = await signupPOST(
      jsonReq({ ...validSignup, password: "x".repeat(65) }, "203.0.113.31"),
    );
    expect(res.status).toBe(400);
  });

  it("AC-AUTH-9.3 KR locale missing required PIPA consent → 400", async () => {
    const res = await signupPOST(
      jsonReq(
        {
          ...validSignup,
          email: "ko-bob@acme.ai",
          locale: "ko",
          pipaConsents: {
            collectUse: false, // required, but unchecked
            thirdParty: true,
            crossBorder: true,
            marketing: false,
          },
        },
        "203.0.113.40",
      ),
    );
    expect(res.status).toBe(400);
  });

  it("rate-limits the 2nd signup from the same IP within 1 min → 429", async () => {
    const r1 = await signupPOST(jsonReq(validSignup, "203.0.113.99"));
    expect(r1.status).toBe(201);
    const r2 = await signupPOST(
      jsonReq({ ...validSignup, email: "second@acme.ai" }, "203.0.113.99"),
    );
    expect(r2.status).toBe(429);
  });
});

describe("/api/auth/signin (FR-AUTH-4)", () => {
  it("happy path returns 200", async () => {
    await signupPOST(jsonReq(validSignup, "203.0.113.110"));
    const res = await signinPOST(
      jsonReq(
        { email: validSignup.email, password: validSignup.password, rememberMe: true },
        "203.0.113.111",
      ),
    );
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.email).toBe("alice@acme.ai");
  });

  it("wrong password → 401 ERR_AUTH_INVALID", async () => {
    await signupPOST(jsonReq(validSignup, "203.0.113.120"));
    const res = await signinPOST(
      jsonReq(
        { email: validSignup.email, password: "wrong-password", rememberMe: true },
        "203.0.113.121",
      ),
    );
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("ERR_AUTH_INVALID");
  });

  it("nonexistent email → 401 ERR_AUTH_INVALID (timing-safe)", async () => {
    const res = await signinPOST(
      jsonReq(
        { email: "nobody@nowhere.ai", password: "anything-goes", rememberMe: true },
        "203.0.113.122",
      ),
    );
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("ERR_AUTH_INVALID");
  });

  it("AC-AUTH-4.1 6th attempt from the same IP in 1 min → 429", async () => {
    for (let i = 0; i < 5; i++) {
      await signinPOST(
        jsonReq(
          { email: `nobody${i}@nowhere.ai`, password: "anything", rememberMe: true },
          "203.0.113.130",
        ),
      );
    }
    const r = await signinPOST(
      jsonReq(
        { email: "another@nowhere.ai", password: "anything", rememberMe: true },
        "203.0.113.130",
      ),
    );
    expect(r.status).toBe(429);
  });
});

describe("/api/auth/signout (FR-AUTH-5)", () => {
  it("returns 200 even with no active session", async () => {
    const res = await signoutPOST(jsonReq({}, "203.0.113.150"));
    expect(res.status).toBe(200);
  });
});

describe("/api/auth/password-reset (FR-AUTH-6)", () => {
  it("AC-AUTH-6.1 always 200 — even on missing email", async () => {
    const r1 = await resetReqPOST(
      jsonReq({ email: "ghost@ghost.ai" }, "203.0.113.160"),
    );
    expect(r1.status).toBe(200);
  });

  it("AC-AUTH-6.2 invalid token on confirm → 400 ERR_TOKEN_INVALID", async () => {
    const res = await resetConfirmPOST(
      jsonReq(
        { token: "definitely-not-a-real-token", newPassword: "long-enough-12" },
        "203.0.113.161",
      ),
    );
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("ERR_TOKEN_INVALID");
  });
});

describe("/api/account/api-key (FR-AUTH-8)", () => {
  it("GET without session → 401 ERR_UNAUTHORIZED", async () => {
    const res = await apikeyGET();
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("ERR_UNAUTHORIZED");
  });

  it("POST without session → 401 ERR_UNAUTHORIZED", async () => {
    const res = await apikeyPOST(jsonReq({ action: "regenerate" }, "203.0.113.170"));
    expect(res.status).toBe(401);
  });
});
