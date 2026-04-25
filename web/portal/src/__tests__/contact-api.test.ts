/**
 * /api/contact — HIGH-1 fix from qa-report-portal-redesign.
 *
 * Covers happy-path 202, schema 422, missing-consent 422,
 * malformed-JSON 422, and the per-IP 429 token bucket.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { POST } from "@/app/api/contact/route";
import { contactRateLimiter } from "@/lib/rate-limit";

function buildRequest(
  body: unknown,
  ip = "203.0.113.10",
  init: { rawBody?: string; contentType?: string } = {},
): Request {
  const headers = new Headers({
    "Content-Type": init.contentType ?? "application/json",
    "X-Forwarded-For": ip,
  });
  return new Request("http://localhost/api/contact", {
    method: "POST",
    headers,
    body: init.rawBody ?? JSON.stringify(body),
  });
}

const VALID_BODY = {
  name: "Alice Demo",
  email: "alice@example.com",
  organization: "Demo AI Lab",
  intent: "buyer",
  message: "We would love to evaluate the dataset for our retina classifier.",
  consent: true,
};

describe("/api/contact POST", () => {
  beforeEach(() => {
    contactRateLimiter.reset();
  });

  it("accepts a well-formed body with consent and returns 202", async () => {
    const res = await POST(buildRequest(VALID_BODY));
    expect(res.status).toBe(202);
  });

  it("rejects missing required fields with 422 ERR_REQUEST_SCHEMA", async () => {
    const res = await POST(
      buildRequest({ ...VALID_BODY, email: "not-an-email" }),
    );
    expect(res.status).toBe(422);
    const body = (await res.json()) as { error: string };
    expect(body.error).toBe("ERR_REQUEST_SCHEMA");
  });

  it("rejects missing PIPA consent with 422", async () => {
    const { consent: _consent, ...withoutConsent } = VALID_BODY;
    const res = await POST(buildRequest(withoutConsent));
    expect(res.status).toBe(422);
  });

  it("rejects consent: false with 422 (literal(true) check)", async () => {
    const res = await POST(buildRequest({ ...VALID_BODY, consent: false }));
    expect(res.status).toBe(422);
  });

  it("rejects malformed JSON with 422", async () => {
    const res = await POST(
      buildRequest(null, "203.0.113.11", {
        rawBody: "not-json",
      }),
    );
    expect(res.status).toBe(422);
  });

  it("rejects too-short message with 422 (10 char minimum)", async () => {
    const res = await POST(buildRequest({ ...VALID_BODY, message: "hi" }));
    expect(res.status).toBe(422);
  });

  it("rate-limits the 6th request from the same IP with 429", async () => {
    const ip = "203.0.113.99";
    for (let i = 0; i < 5; i++) {
      const ok = await POST(buildRequest(VALID_BODY, ip));
      expect(ok.status).toBe(202);
    }
    const blocked = await POST(buildRequest(VALID_BODY, ip));
    expect(blocked.status).toBe(429);
    const body = (await blocked.json()) as { error: string };
    expect(body.error).toBe("ERR_RATE_LIMITED");
    expect(blocked.headers.get("Retry-After")).toBeTruthy();
  });

  it("does not rate-limit different IPs against each other", async () => {
    for (let i = 0; i < 5; i++) {
      await POST(buildRequest(VALID_BODY, "203.0.113.40"));
    }
    const other = await POST(buildRequest(VALID_BODY, "203.0.113.41"));
    expect(other.status).toBe(202);
  });
});
