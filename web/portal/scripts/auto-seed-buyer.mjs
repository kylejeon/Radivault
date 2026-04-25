#!/usr/bin/env node
/**
 * auto-seed-buyer.mjs — RadiVault demo buyer auto-seed wrapper.
 *
 * Goal (CEO decision K-4, D-13 demo-day SOP):
 *   Whenever an operator runs `pnpm dev` from web/portal/, the demo buyer
 *   credential `demo@buyer.example` / `radivault-demo-2026` MUST already
 *   exist in the in-memory auth store by the time they hit /signin. Manual
 *   `python scripts/demo_seed/seed_buyer_auth.py` is too easy to forget at
 *   T-minus-5 minutes before the CEO walks in.
 *
 * Why this is an orchestrator instead of a `predev` hook:
 *   The auth store lives inside the Next.js process. A `predev` step would
 *   POST to an endpoint that does not exist yet. So this script:
 *     1. Spawns `next dev -p 3000` as a child (stdio inherited).
 *     2. Polls `http://localhost:3000/api/health-lite` (a HEAD on the home
 *        page actually — see probe()) until ready or timeout.
 *     3. Calls POST /api/auth/signup once. 201 → log plaintext key (or
 *        write to .demo_buyer_auth.local.txt). 409 ERR_EMAIL_TAKEN →
 *        idempotent skip.
 *     4. Forwards SIGINT / SIGTERM to the child so Ctrl+C still works.
 *
 * Skip conditions (no signup attempted, child still launched):
 *   - process.env.NODE_ENV === "production"
 *   - process.env.BUYER_AUTH_DEMO_SEED === "false"
 *
 * Re-entry / idempotency:
 *   - 409 ERR_EMAIL_TAKEN → log skip, exit 0 from probe.
 *   - DEMO_BUYER_API_KEY set → reuse, do not re-issue.
 *
 * NEVER use this in prod builds. The package.json wires it ONLY into `dev`.
 */

import { spawn } from "node:child_process";
import { setTimeout as sleep } from "node:timers/promises";
import { writeFile, chmod, mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

const PORT = Number(process.env.PORT ?? 3000);
const HOST = `http://localhost:${PORT}`;
const READINESS_TIMEOUT_MS = 60_000;
const READINESS_POLL_MS = 500;
const SEED_EMAIL = process.env.DEMO_BUYER_EMAIL ?? "demo@buyer.example";
const SEED_PASSWORD = process.env.DEMO_BUYER_PASSWORD ?? "radivault-demo-2026";
const SEED_ORG = process.env.DEMO_BUYER_ORG ?? "Demo Buyer Global AI";
const SEED_INTENT = process.env.DEMO_BUYER_INTENT ?? "commercial-ai";
const KEY_OUT_PATH = join(
  __dirname,
  "..",
  "..",
  "..",
  "scripts",
  "demo_seed",
  ".demo_buyer_auth.local.txt",
);

function log(msg) {
  // eslint-disable-next-line no-console
  console.log(`[auto-seed] ${msg}`);
}

function warn(msg) {
  // eslint-disable-next-line no-console
  console.warn(`[auto-seed] ${msg}`);
}

/** Probe the dev server. We GET the homepage rather than poking
 * /api/auth/signup directly — the signup endpoint has a 1/min/IP rate
 * limit, and the probe would burn the budget the seed itself needs.
 * Any HTTP response (200 / 3xx / 404 / 5xx) means Next is up. ECONN /
 * fetch failure → not ready yet. */
async function probe() {
  try {
    const res = await fetch(`${HOST}/`, {
      method: "GET",
      // Some Next 14 dev startups stream the response — we just need
      // the head, so abort after a short read.
      headers: { Accept: "text/html" },
    });
    // Drain the body so the socket is reusable.
    try {
      await res.text();
    } catch {
      // ignore
    }
    return res.status > 0;
  } catch {
    return false;
  }
}

async function waitForReady() {
  const start = Date.now();
  while (Date.now() - start < READINESS_TIMEOUT_MS) {
    if (await probe()) return true;
    await sleep(READINESS_POLL_MS);
  }
  return false;
}

async function seedBuyer() {
  const body = {
    email: SEED_EMAIL,
    password: SEED_PASSWORD,
    organization: SEED_ORG,
    intent: SEED_INTENT,
    tosPrivacyConsent: true,
    marketingEmailOptIn: false,
    pipaConsents: null,
    locale: "en",
  };

  let res;
  try {
    res = await fetch(`${HOST}/api/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (err) {
    warn(`signup network error: ${err.message ?? err}`);
    return;
  }

  if (res.status === 201) {
    let payload = {};
    try {
      payload = await res.json();
    } catch {
      // ignore JSON parse failure — non-fatal
    }
    log(`demo buyer ready: ${SEED_EMAIL} (buyerId=${payload.buyerId ?? "?"})`);
    const plaintext = payload.apiKeyRevealOnce;
    if (plaintext) {
      // Reuse via env override pattern: if DEMO_BUYER_API_KEY is set, the
      // operator has already pinned a key — do not overwrite the local file.
      if (process.env.DEMO_BUYER_API_KEY) {
        log("DEMO_BUYER_API_KEY env set — skipping local key file write.");
      } else {
        try {
          await mkdir(dirname(KEY_OUT_PATH), { recursive: true });
          await writeFile(KEY_OUT_PATH, plaintext + "\n", { encoding: "utf-8" });
          await chmod(KEY_OUT_PATH, 0o600);
          log(`plaintext API key written to ${KEY_OUT_PATH}`);
        } catch (err) {
          warn(`could not write key file: ${err.message ?? err}`);
        }
      }
    }
    return;
  }

  if (res.status === 409) {
    let code = "";
    try {
      const j = await res.json();
      code = j?.error?.code ?? "";
    } catch {
      // ignore
    }
    if (code === "ERR_EMAIL_TAKEN" || code === "ERR_EMAIL_RECENTLY_DELETED") {
      log(`demo buyer already present (${code}) — idempotent skip.`);
      return;
    }
    warn(`signup 409 with unexpected code=${code}`);
    return;
  }

  warn(`signup HTTP ${res.status} — manual fallback: \`python scripts/demo_seed/seed_buyer_auth.py\``);
}

async function runOrchestrator(extraArgs) {
  // Decide whether to skip BEFORE spawning, so the log is the first thing
  // an operator sees if the skip condition is set.
  const isProd = process.env.NODE_ENV === "production";
  const seedDisabled = process.env.BUYER_AUTH_DEMO_SEED === "false";
  const skipSeed = isProd || seedDisabled;

  if (isProd) {
    log("skipped (NODE_ENV=production) — auto-seed disabled in prod builds.");
  } else if (seedDisabled) {
    log("skipped (BUYER_AUTH_DEMO_SEED=false).");
  }

  // D-13 BLOCKER fix — INTERNAL_SEARCH_KEY check. v0.2 (email/password)
  // sessions have no apiKey on the cookie, so every BFF call to search /
  // fulfillment falls through to the system key. If the operator forgot
  // to seed it, /search renders 401 and the demo dies silently.
  if (!process.env.INTERNAL_SEARCH_KEY) {
    warn(
      "INTERNAL_SEARCH_KEY is not set in .env.local — v0.2 (email/password) " +
        "BFF calls will fail with 401 ERR_AUTH_EXPIRED detail=no_internal_key.",
    );
    warn("To enable v0.2 session BFF, run:");
    warn(
      "  docker exec radivault-search-1 search-admin buyer create " +
        "--buyer-id buy_portal_internal --company 'RadiVault Portal Internal' " +
        "--contact-email portal-internal@radivault.local --tier paid --json",
    );
    warn(
      "  docker exec radivault-search-1 search-admin key issue " +
        "--buyer-id buy_portal_internal --tier paid --expires-days 365 --json",
    );
    warn(
      "Then append the rv_live_* plaintext to web/portal/.env.local as INTERNAL_SEARCH_KEY=… and restart `pnpm dev`.",
    );
  }

  const nextBin = join(__dirname, "..", "node_modules", ".bin", "next");
  const child = spawn(nextBin, ["dev", "-p", String(PORT), ...extraArgs], {
    stdio: "inherit",
    env: process.env,
  });

  // Forward Ctrl+C / kill to the child. Without this, the orchestrator dies
  // first and Next becomes an orphan tied to PID 1.
  const forward = (sig) => {
    if (!child.killed) child.kill(sig);
  };
  process.on("SIGINT", () => forward("SIGINT"));
  process.on("SIGTERM", () => forward("SIGTERM"));

  child.on("exit", (code, signal) => {
    process.exit(code ?? (signal ? 1 : 0));
  });

  if (!skipSeed) {
    // Detach the seed task so it does not block the dev server's stdout flow.
    (async () => {
      const ready = await waitForReady();
      if (!ready) {
        warn(
          `dev server not ready after ${READINESS_TIMEOUT_MS / 1000}s — ` +
            "skipping auto-seed. Run `python scripts/demo_seed/seed_buyer_auth.py` manually.",
        );
        return;
      }
      await seedBuyer();
    })().catch((err) => {
      warn(`unexpected: ${err.stack ?? err.message ?? err}`);
    });
  }
}

// CLI entry. Pass through any extra args (e.g. `pnpm dev --turbo`).
const extraArgs = process.argv.slice(2);
runOrchestrator(extraArgs);
