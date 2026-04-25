/**
 * POST /api/contact — HIGH-1 fix from qa-report-portal-redesign
 * (AC-HP-7 / FR-HP-12 / FR-INF-4 / FR-INF-5).
 *
 * v0.1 inbox stub: validate the body, optionally relay to a Slack webhook
 * if SLACK_WEBHOOK_URL is set, and always log to stdout so the operator
 * has a paper trail. Replies are always 202 (Accepted) — the actual
 * fan-out to email is intentionally async / out-of-band.
 *
 * Status codes:
 *   - 422 ERR_REQUEST_SCHEMA — validation failure (zod)
 *   - 429 ERR_RATE_LIMITED   — > 5 submissions / minute / IP
 *   - 202                    — accepted (no body content)
 *   - 500                    — only on unexpected runtime exception
 *
 * Rate limit: in-memory token bucket keyed on IP. Persists for the
 * lifetime of the Node.js process; survives request boundaries because
 * the route handler module is hot in Next.js. Multi-instance deploys will
 * trivially defeat this — fine for v0.1; v0.1.1 lifts the bucket into
 * Redis.
 */

import { NextResponse } from "next/server";
import { z } from "zod";
import { contactRateLimiter } from "@/lib/rate-limit";

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

const ContactSchema = z.object({
  name: z.string().trim().min(1).max(120),
  email: z.string().trim().email().max(254),
  organization: z.string().trim().min(0).max(200).optional().default(""),
  intent: z.enum(["buyer", "hospital", "press", "investor", "other"]),
  message: z.string().trim().min(10).max(4000),
  // PIPA L-7 — explicit consent token. The form sends `consent: true`
  // when the checkbox is checked. Server enforces it independently of
  // the client-side disabled state.
  consent: z.literal(true),
});

type ContactBody = z.infer<typeof ContactSchema>;

// ---------------------------------------------------------------------------
// Route
// ---------------------------------------------------------------------------

function clientIp(req: Request): string {
  // Trust the immediate proxy. Production deployments terminate TLS at
  // the edge so the leftmost X-Forwarded-For entry is the real client.
  const fwd = req.headers.get("x-forwarded-for");
  if (fwd && fwd.length > 0) return fwd.split(",")[0].trim();
  const real = req.headers.get("x-real-ip");
  if (real) return real.trim();
  return "unknown";
}

async function relayToSlack(body: ContactBody): Promise<void> {
  const url = process.env.SLACK_WEBHOOK_URL;
  if (!url) return;
  // Slack outgoing webhook accepts a JSON payload with `text`. Fire and
  // forget — we never block the 202 response on this.
  const summary =
    `*New contact* — ${body.intent}\n` +
    `*From:* ${body.name} <${body.email}>` +
    (body.organization ? ` (${body.organization})\n` : "\n") +
    `*Message:*\n${body.message.slice(0, 3000)}`;
  try {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: summary }),
    });
  } catch (err) {
    console.warn("[contact] slack relay failed", err);
  }
}

export async function POST(req: Request) {
  const ip = clientIp(req);
  const rate = contactRateLimiter.check(ip);
  if (!rate.ok) {
    return NextResponse.json(
      {
        error: "ERR_RATE_LIMITED",
        message: `Too many submissions. Retry in ${rate.retryAfterSeconds}s.`,
      },
      {
        status: 429,
        headers: {
          "Retry-After": String(rate.retryAfterSeconds),
        },
      },
    );
  }

  let raw: unknown;
  try {
    raw = await req.json();
  } catch {
    return NextResponse.json(
      {
        error: "ERR_REQUEST_SCHEMA",
        message: "Body must be valid JSON.",
      },
      { status: 422 },
    );
  }

  const parsed = ContactSchema.safeParse(raw);
  if (!parsed.success) {
    return NextResponse.json(
      {
        error: "ERR_REQUEST_SCHEMA",
        message: "Validation failed",
        issues: parsed.error.issues.map((i) => ({
          path: i.path.join("."),
          message: i.message,
        })),
      },
      { status: 422 },
    );
  }

  const body = parsed.data;

  // Operator paper trail — never includes the message body to keep the
  // log line bounded. The Slack relay carries the full text.
  console.info(
    `[contact] ip=${ip} intent=${body.intent} email=${body.email} ` +
      `org="${body.organization ?? ""}" len=${body.message.length}`,
  );

  // Fire-and-forget Slack relay so we never block the 202.
  void relayToSlack(body);

  return new NextResponse(null, { status: 202 });
}
