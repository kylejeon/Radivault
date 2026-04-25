# RadiVault Demo-Day Runbook (D-13 / K-4)

> **Status**: v0.1 · **Last updated**: 2026-04-25
> **Owner**: Kyle (CEO) · **Operator role**: anyone with repo access
> **Scope**: D-day demo only (CEO meeting + buyer pitch). Pilot deployments
> use a different procedure (TBD; see `docs/ops/install-guide.md`).
>
> See also:
> - `docs/ops/demo-deploy-runbook.md` — full backend stack bring-up.
> - `docs/ops/hospital-admin-credentials.md` — Hospital Dashboard tokens.

---

## 0. Why this file exists

Demo-day failure modes that have actually happened in rehearsal:

1. Operator forgot to run `python scripts/demo_seed/seed_buyer_auth.py`
   after restarting the portal → `/signin` 401 in front of the CEO.
2. Operator typed the wrong password → MemoryAuthStore silently no-op'd.
3. The reveal-once API key was scrolled off-screen, no recovery without
   regen.

This runbook is the 60-minute ritual that prevents all three. **The
auto-seed hook (CEO decision K-4) automates step 3 of §2 below**, but the
operator still walks through this checklist.

---

## 1. Demo credentials (single source of truth)

### Buyer (auto-seeded on `pnpm dev` — see §3)

| field        | value                         |
|--------------|-------------------------------|
| email        | `demo@buyer.example`          |
| password     | `radivault-demo-2026`         |
| organization | `Demo Buyer Global AI`        |
| intent       | `commercial-ai`               |
| API key      | written to `scripts/demo_seed/.demo_buyer_auth.local.txt` (chmod 0600, gitignored) |

### Hospital admins (per `docs/ops/hospital-admin-credentials.md`)

| hospital_id | admin password         |
|-------------|-----------------------|
| HOSP-001    | `radivault-demo-2026` |
| HOSP-002    | `tunteun-demo-2026`   |

> **Internal use only**: this repo is private. If it becomes public, rotate
> all four passwords above before the push.

---

## 2. T-minus-60-min checklist

Run from `/Users/yonghyuk/Radivault` (or your clone).

### 2.1 Backend stack up

```bash
# central-ingest
docker compose -f src/radivault_central/docker-compose.yml up -d

# search + fulfillment (separate terminals or your usual flow)
uvicorn radivault_search.app:app --port 8003 --reload
uvicorn radivault_fulfillment.app:app --port 8002 --reload

# Healthchecks (3x 200 = green)
curl -sf http://localhost:8001/healthz
curl -sf http://localhost:8003/healthz
curl -sf http://localhost:8002/healthz
```

### 2.2 Sample data seeded

If empty, run (per `demo-deploy-runbook.md` §4):

```bash
bash scripts/demo_seed/inject_all.sh
python scripts/demo_seed/verify.py        # expects 10..50 studies
```

### 2.3 Portal up — auto-seed runs by itself

```bash
cd web/portal
pnpm dev
```

Within 5–10 seconds you should see in the same terminal:

```
[auto-seed] demo buyer ready: demo@buyer.example (buyerId=buy_…)
[auto-seed] plaintext API key written to .../scripts/demo_seed/.demo_buyer_auth.local.txt
```

If you see instead:

| log line | meaning | action |
|---|---|---|
| `[auto-seed] skipped (BUYER_AUTH_DEMO_SEED=false).` | env opt-out is set | unset the flag in `.env.local` and restart |
| `[auto-seed] skipped (NODE_ENV=production)` | wrong build profile for demo | use `pnpm dev` not `pnpm start` |
| `[auto-seed] demo buyer already present (ERR_EMAIL_TAKEN) — idempotent skip.` | safe — buyer carried over from a prior request inside the same dev process | proceed |
| `[auto-seed] dev server not ready after 60s` | Next failed to compile | scroll up for the real error; fix and restart |
| `[auto-seed] signup HTTP 5xx` | upstream / store error | run §4 fallback |

### 2.4 Live signin smoke test

```bash
curl -s -o /tmp/rv-signin.json -w 'HTTP=%{http_code}\n' \
  -X POST http://localhost:3000/api/auth/signin \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@buyer.example","password":"radivault-demo-2026"}'
cat /tmp/rv-signin.json
# Expect HTTP=200 and a body with "buyerId":"buy_…"
```

### 2.5 Reveal-once key copy (only if doing demo #5)

```bash
cat scripts/demo_seed/.demo_buyer_auth.local.txt
# Copy into your scratchpad. The /account page will mask it as 'rv_live_…'.
```

If you need to reset the reveal-once flow mid-demo:

```bash
# Either restart the dev server (fresh in-memory store, fresh key issued)
#   Ctrl+C then pnpm dev again
# Or call the rotate endpoint — requires being signed in:
curl -s -X POST http://localhost:3000/api/account/api-key \
  -H 'Cookie: <copy from devtools>' \
  -H 'Content-Type: application/json' \
  -d '{"action":"regenerate"}'
```

### 2.6 Hospital admin sign-in smoke

Browse `http://localhost:3000/hospital`, type `HOSP-001` +
`radivault-demo-2026` → expect 6-tile dashboard with the simulated badge.

---

## 3. How the auto-seed hook works

**File**: `web/portal/scripts/auto-seed-buyer.mjs`
**Wired in**: `web/portal/package.json` → `"dev": "node scripts/auto-seed-buyer.mjs"`
**Original Next dev command**: still available as `pnpm dev:next` (raw, no seed).

Flow:

```
pnpm dev
  └─ node scripts/auto-seed-buyer.mjs
       ├─ spawn  next dev -p 3000   (stdio inherited, signals forwarded)
       └─ async readiness probe  (GET / every 500ms, max 60s)
            └─ on first 2xx/4xx:  POST /api/auth/signup
                  ├─ 201 Created  → write plaintext key to .demo_buyer_auth.local.txt
                  ├─ 409 ERR_EMAIL_TAKEN  → idempotent skip
                  └─ 5xx / network error  → log and exit (next dev keeps running)
```

Skip conditions (the seed phase is suppressed but `next dev` still
launches):

- `NODE_ENV=production` — defensive guard, prod builds must never auto-seed.
- `BUYER_AUTH_DEMO_SEED=false` — explicit operator opt-out.

The probe pings `GET /` (cheap, no rate limit) rather than the signup
endpoint itself (which has a 1/min/IP rate limit and would self-poison
the seed call).

---

## 4. Fallback — manual seed if auto-seed failed

```bash
# 1. Verify the dev server is up (independent of auto-seed status)
curl -sf http://localhost:3000/

# 2. Run the legacy seed script (idempotent — handles 409 silently)
python scripts/demo_seed/seed_buyer_auth.py

# 3. The plaintext key prints to stdout AND lands in
#    scripts/demo_seed/.demo_buyer_auth.local.txt
```

If signup keeps returning 5xx, restart the portal:

```bash
# Ctrl+C in the portal terminal
cd web/portal && pnpm dev
# Auto-seed runs again on fresh boot.
```

---

## 5. Five-minute "demo broke mid-flow" recovery

| symptom | cause | fix |
|---------|-------|-----|
| `/signin` returns 401 with correct password | dev server restarted; in-memory store wiped; auto-seed didn't run | Ctrl+C the portal, `pnpm dev` again, watch for `[auto-seed] demo buyer ready` |
| `/search` shows 0 results after a working pre-check | search service restarted, lost in-memory index | re-run `bash scripts/demo_seed/inject_all.sh` |
| Hospital tile B-2 (revenue) blank | NEXT_PUBLIC_DEMO_* env unset | check `.env.local` — those three keys must be present |
| API key field shows `rv_live_…` only (operator never saw plaintext) | reveal-once already happened | `cat scripts/demo_seed/.demo_buyer_auth.local.txt` for the cached copy |
| Browser shows hydration error | dev HMR race | hard refresh (`Cmd+Shift+R`) once, do NOT restart the server |

---

## 6. After the demo

```bash
# Stop the portal (Ctrl+C)

# Optional: wipe local plaintext key files
rm -f scripts/demo_seed/.demo_buyer_auth.local.txt
rm -f scripts/demo_seed/.buyer_key.local.txt

# Stop backend (if no more demos this week)
docker compose -f src/radivault_central/docker-compose.yml down
```

---

## 7. Change log

| version | date       | change                                                    |
|---------|------------|-----------------------------------------------------------|
| 0.1     | 2026-04-25 | Initial draft. Wraps `pnpm dev` auto-seed hook (K-4).     |
