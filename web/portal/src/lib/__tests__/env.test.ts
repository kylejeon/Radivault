/**
 * Tests for `env.ts` — buyer-auth specific getters.
 *
 * Focus: BLOCKER #2 fix from qa-report-d13-demo-rehearsal — ensure
 * `buyerAuthSkipEmailVerify` no longer throws at module-import / build
 * prerender time and that NODE_ENV-aware defaulting preserves the HIGH-1
 * intent (production fail-closed when ENV is omitted).
 *
 * The getter is invoked fresh on every access, so we mutate
 * `process.env` between cases without needing to reset module state.
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { env } from "@/lib/env";

const FLAG = "BUYER_AUTH_SKIP_EMAIL_VERIFY";

describe("env.buyerAuthSkipEmailVerify (BLOCKER #2 / AC-DEMO-4)", () => {
  const originalNodeEnv = process.env.NODE_ENV;
  const originalFlag = process.env[FLAG];

  beforeEach(() => {
    delete process.env[FLAG];
  });

  afterEach(() => {
    // Restore the test environment exactly as we found it so subsequent
    // suites (which assume NODE_ENV=test) don't get clobbered.
    if (originalNodeEnv === undefined) {
      delete (process.env as Record<string, string | undefined>).NODE_ENV;
    } else {
      (process.env as Record<string, string | undefined>).NODE_ENV =
        originalNodeEnv;
    }
    if (originalFlag === undefined) {
      delete process.env[FLAG];
    } else {
      process.env[FLAG] = originalFlag;
    }
  });

  it("dev default — flag omitted in development → skip = true", () => {
    (process.env as Record<string, string | undefined>).NODE_ENV =
      "development";
    expect(env.buyerAuthSkipEmailVerify).toBe(true);
  });

  it("prod default — flag omitted in production → skip = false (HIGH-1 fail-closed)", () => {
    (process.env as Record<string, string | undefined>).NODE_ENV = "production";
    // Crucially: must NOT throw (BLOCKER #2 — previous guard threw on
    // every `pnpm build` prerender).
    expect(() => env.buyerAuthSkipEmailVerify).not.toThrow();
    expect(env.buyerAuthSkipEmailVerify).toBe(false);
  });

  it("prod explicit true — operator override allowed → skip = true (no throw)", () => {
    (process.env as Record<string, string | undefined>).NODE_ENV = "production";
    process.env[FLAG] = "true";
    // Operator explicitly opted in (e.g. demo build artifact). The
    // previous over-strict guard threw here; the new fix must pass.
    expect(() => env.buyerAuthSkipEmailVerify).not.toThrow();
    expect(env.buyerAuthSkipEmailVerify).toBe(true);
  });

  it("prod explicit false — operator opt-out → skip = false", () => {
    (process.env as Record<string, string | undefined>).NODE_ENV = "production";
    process.env[FLAG] = "false";
    expect(env.buyerAuthSkipEmailVerify).toBe(false);
  });
});
