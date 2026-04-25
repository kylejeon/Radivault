/**
 * Unit tests for `bearerForBuyer` (D-13 BLOCKER fix).
 *
 * Covers the four decision-table cases documented in
 * `web/portal/src/lib/buyer-bearer.ts`. Each case mutates
 * `process.env.INTERNAL_SEARCH_KEY` before calling the getter so the
 * env reader sees the test-local value (the env getter is invoked fresh
 * per call — see web/portal/src/lib/env.ts).
 */

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { actingBuyerHeaders, bearerForBuyer } from "@/lib/buyer-bearer";
import type { BuyerSession } from "@/lib/session";

const KEY = "INTERNAL_SEARCH_KEY";
const FAKE_INTERNAL = "rv_live_abcd1234_test_internal_search_key_value";
const FAKE_USER = "rv_live_user5678_paste_mode_legacy_value_xxxx";

describe("bearerForBuyer (D-13 BLOCKER fix)", () => {
  const original = process.env[KEY];

  beforeEach(() => {
    delete process.env[KEY];
  });

  afterEach(() => {
    if (original === undefined) {
      delete process.env[KEY];
    } else {
      process.env[KEY] = original;
    }
  });

  it("user-key wins when session.apiKey present (legacy paste-mode)", () => {
    process.env[KEY] = FAKE_INTERNAL;
    const session: BuyerSession = {
      apiKey: FAKE_USER,
      buyerPk: 42,
      signedInAt: Date.now(),
    };
    const result = bearerForBuyer(session);
    expect(result).toEqual({
      ok: true,
      bearer: FAKE_USER,
      mode: "user",
    });
  });

  it("internal-key used when only buyerPk on cookie + INTERNAL_SEARCH_KEY set", () => {
    process.env[KEY] = FAKE_INTERNAL;
    const session: BuyerSession = {
      buyerPk: 90001,
      buyerId: "buy_v02_demo",
      email: "demo@buyer.example",
      sessionVersion: 1,
      signedInAt: Date.now(),
    };
    const result = bearerForBuyer(session);
    expect(result).toEqual({
      ok: true,
      bearer: FAKE_INTERNAL,
      mode: "internal",
    });
  });

  it("no_internal_key when v0.2 session present but ENV unset (operator misconfig)", () => {
    // INTERNAL_SEARCH_KEY intentionally not set in this case.
    const session: BuyerSession = {
      buyerPk: 90001,
      signedInAt: Date.now(),
    };
    const result = bearerForBuyer(session);
    expect(result).toEqual({ ok: false, reason: "no_internal_key" });
  });

  it("no_session when neither apiKey nor buyerPk present", () => {
    process.env[KEY] = FAKE_INTERNAL;
    const session: BuyerSession = {};
    const result = bearerForBuyer(session);
    expect(result).toEqual({ ok: false, reason: "no_session" });
  });
});

describe("actingBuyerHeaders", () => {
  it("forwards X-Acting-Buyer-Mode + Pk for v0.2 internal-mode call", () => {
    const session: BuyerSession = {
      buyerPk: 90001,
      signedInAt: Date.now(),
    };
    expect(actingBuyerHeaders(session, "internal")).toEqual({
      "X-Acting-Buyer-Mode": "internal",
      "X-Acting-Buyer-Pk": "90001",
    });
  });

  it("forwards Mode only when buyerPk is missing (legacy paste-mode)", () => {
    const session: BuyerSession = {
      apiKey: FAKE_USER,
      signedInAt: Date.now(),
    };
    expect(actingBuyerHeaders(session, "user")).toEqual({
      "X-Acting-Buyer-Mode": "user",
    });
  });
});
