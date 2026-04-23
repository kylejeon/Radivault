# RadiVault Order API — Buyer Quickstart (Order to Download)

> **Status**: Draft — Kyle review required before any external distribution
> **Document version**: v0.1 (2026-04-22)
> **Author**: @marketer (RadiVault)
> **Audience**: ML / data engineers at AI and medical-device companies who have already completed the [Search API Quickstart](./api-quickstart-buyer-en.md) and want to purchase a cohort and download the DICOMs
> **Language**: English
> **Purpose**: get from "I picked a cohort" to "the DICOMs are on my laptop" in under 30 minutes
> **API version**: `v1` (order-fulfillment v0.1 — QA PASS with minor, 2026-04-22)
> **Authoritative references**:
> - [dev-spec-order-fulfillment §3, §6, §7](../specs/dev-spec-order-fulfillment.md) — scope, schemas, API contracts
> - [design-spec-order-fulfillment §2, §7](../specs/design-spec-order-fulfillment.md) — buyer UX, error taxonomy
> - [qa-report-order-fulfillment](../qa/qa-report-order-fulfillment.md) — QA PASS with minor, 2026-04-22
> **Distribution**: not for external distribution until Kyle approves.
> **Billing disclosure**: **v0.1 billing is a stub — no charge occurs**. Payment integration (Stripe / local PG) ships in v0.2. `total_estimated_usd` and `state_billing: "pending_billing"` are shown for future settlement planning only.

---

## 0. TL;DR

```bash
# 1. Create your first order (you'll get a state machine back, not DICOMs)
export RADIVAULT_KEY="rv_live_abcd1234_Zj8f2vX9qK2sLpN4mQbW7yR1eT5aU6c"
export IDEM_KEY="$(uuidgen)"
export MSA_HASH="<sha256 of the MSA body RadiVault sent you at signing>"

curl -sS -X POST https://fulfillment.radivault.io/v1/orders \
  -H "Authorization: Bearer $RADIVAULT_KEY" \
  -H "Idempotency-Key: $IDEM_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"pseudo_study_uids\": [\"2.25.140737488355328.1.2.3\"],
    \"agreement_hash\":    \"$MSA_HASH\"
  }" | jq '{order_id, state, total_estimated_usd, state_billing}'

# 2. Poll for readiness, then mint download URLs, then parallel-download with sha256 check.
# 3. Total expected wall clock, hot-path 3 studies: ~30 seconds. Cold-path 100 studies: ~1 hour.
```

If that returned `202 Accepted` with a `state: "queued"` and a `state_billing: "pending_billing"`, you are live. Read on.

---

## 1. Prerequisites

This quickstart assumes you have already done the [Search API Quickstart](./api-quickstart-buyer-en.md). Specifically, you need:

- **A paid-tier API key** — preview keys can place orders for test purposes, but cohort caps are 50 studies and the download TTL is capped at 24h. For anything that looks like production, request a paid-tier upgrade from [sales@radivault.io](mailto:sales@radivault.io).
- **A cohort of `pseudo_study_uid`s** from your last Search API response. These opaque IDs are stable — the ID you saw yesterday still points to the same study today.
- **A signed MSA (Master Service Agreement)** and the **`agreement_hash`** — a SHA-256 of the exact MSA body you signed. RadiVault Sales provides this 64-character hex value at contract signing. You send it on every `POST /v1/orders`; the server rejects mismatches with `400 ERR_ORDER_AGREEMENT_REQUIRED`.
- **A billing agreement placeholder** — **v0.1 billing is a stub**. Your MSA explicitly acknowledges that no payment gateway is integrated yet; preview tier is free, paid tier accumulates `pending_billing` entries that will reconcile when v0.2 ships. Nothing is charged to a card in v0.1. Confirm with Sales which clause covers this.
- **Storage for the download** — v0.1 cohorts top out at 2 TB per order (paid tier). Provision disk accordingly before you start, or you will run out of space mid-stream.
- **Terminal with `curl`, `jq`, `sha256sum`** — macOS/Linux native; Windows via WSL.
- **(Recommended) Python 3.10+ with `httpx`** — for the parallel downloader in §7.

### 1.1 Base URL

- **Production**: `https://fulfillment.radivault.io`
- **Test (sandbox)**: `https://fulfillment.sandbox.radivault.io` *(v0.2+)*

All endpoints are prefixed with `/v1/`. Search still lives on `search.radivault.io`; ordering lives on `fulfillment.radivault.io`. They share the same API key.

### 1.2 Store your secrets

```bash
# ~/.zshrc or equivalent
export RADIVAULT_KEY="rv_live_abcd1234_Zj8f2vX9qK2sLpN4mQbW7yR1eT5aU6c"
export RADIVAULT_MSA_HASH="<64-hex sha256 — ask sales@radivault.io>"
```

Never commit either value to version control. If you suspect a leak, email [support@radivault.io](mailto:support@radivault.io) — we can revoke within minutes.

### 1.3 A note on scope

Your API key has an associated **scope** — the set of hospitals you are allowed to buy from. It is set at contract signing and surfaced through the Search API's facet results. If a study's originating hospital is not in your scope, the Order API rejects the whole order with `403 ERR_ORDER_SCOPE_FORBIDDEN`. See §11 for recovery.

---

## 2. Order lifecycle — the 12-state FSM in plain English

Every order moves through a well-defined finite state machine. You do not normally see `draft`, `submitted`, `validating`, `delivering`; the three you care about are `queued`, `fetching`, and `ready_for_download`. Here is the whole picture, from [design-spec §2.3](../specs/design-spec-order-fulfillment.md).

| State | Meaning | Typical duration | What you do |
|-------|---------|------------------|-------------|
| `draft` | Reserved; not returned in v0.1. | — | — |
| `submitted` | Request received; validating next. | < 1 s | — |
| `validating` | Six synchronous checks (scope, tier caps, quota, UID existence, size, hospital access). | < 2 s | — |
| `validated` | Passed; queuing transfer jobs. | < 1 s | — |
| `queued` | **You're in line.** Hot-path copies instantly; cold-path wakes a hospital Gateway. | < 10 s | begin polling |
| `fetching` | **Hospital Gateway is pulling** DICOMs from PACS, de-identifying, uploading. | Hot: seconds. Cold: ~1 h / 100 studies. | poll every 5 s |
| `staging_partial` | Some arrived; others in transit. | minutes | poll every 5 s |
| `staging_complete` | All arrived; copying into your private download area. | < 30 s | poll every 5 s |
| `ready_for_download` | **Downloadable.** Call `POST /download-urls` any time in the 7-day window. | 7 days | mint URLs, download |
| `delivering` | First URL minted; reserved for analytics. | v0.1 unused | treat as ready |
| `delivered` | All files downloaded (auto-mark lands in v0.1.1). | terminal | — |
| `expired` | 7-day window ended. Re-order with the same UIDs. | terminal | new order |
| `cancelled` | You or an admin cancelled. | terminal | — |
| `failed` | Server-side failure exceeded retry limits; see `last_error`. | terminal | contact support |

**Typical wall-clock, paid tier**

- **Hot-path, 3 studies**: `submitted → ready_for_download` in ~30 s.
- **Cold-path, 100 studies** (all fetched fresh from the hospital Gateway): ~1 hour, governed by PACS I/O and de-identification CPU, not RadiVault latency.
- **Mixed-path**: the slower leg dominates; the hot leg waits silently.

**ASCII state diagram** (condensed; full diagram in [design-spec §2.3](../specs/design-spec-order-fulfillment.md))

```
submitted → validating → validated → queued → fetching → staging_partial
                                                       \
                                                        → staging_complete → ready_for_download → delivering → delivered
                                                                                 \              \
                                                                                  → expired      → cancelled
                                                                                                 → failed
```

---

## 3. Creating your first order — `POST /v1/orders`

### 3.1 Realistic example — 3-study hot-path order

```bash
export RADIVAULT_KEY="rv_live_abcd1234_..."
export RADIVAULT_MSA_HASH="abcd1234ef5678901234567890abcdef1234567890abcdef1234567890abcdef"
export IDEM_KEY="$(uuidgen)"

curl -sS -X POST https://fulfillment.radivault.io/v1/orders \
  -H "Authorization: Bearer $RADIVAULT_KEY" \
  -H "Idempotency-Key: $IDEM_KEY" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: $(uuidgen)" \
  -d "{
    \"pseudo_study_uids\": [
      \"2.25.140737488355328.1.2.3\",
      \"2.25.140737488355328.1.2.4\",
      \"2.25.140737488355328.1.2.5\"
    ],
    \"agreement_hash\":    \"$RADIVAULT_MSA_HASH\",
    \"notes\":             \"pilot cohort batch 3\",
    \"preferred_download_ttl_hours\": 48
  }"
```

### 3.2 Annotated response

```jsonc
HTTP/1.1 202 Accepted
Content-Type: application/json
X-Request-Id: 01HXXORDER1SERVER
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-Quota-Limit-Daily: 50
X-Quota-Remaining-Daily: 49
X-Quota-Reset-Daily: 1713830400
Idempotency-Replayed: false

{
  "order_id":             "ord_01HXXORDER1ABCDEF",   // ULID — save this
  "state":                "queued",                   // see §2 for the FSM
  "state_billing":        "pending_billing",          // v0.1 stub; no charge
  "n_studies":            3,
  "total_bytes":          282963036,
  "total_estimated_usd":  15.0,                       // for v0.2 settlement; not charged
  "tier":                 "paid",
  "path_type":            null,                       // hot | cold | mixed — set by orchestrator
  "submitted_at":         "2026-04-22T10:00:00Z",
  "estimated_ready_at":   "2026-04-22T10:00:30Z",     // hot×0.5s + cold×36s heuristic
  "ready_at":             null,                       // set on ready_for_download
  "expires_at":           null,                       // set to ready_at + 7 days
  "cancelled_at":         null,
  "progress":             0.0,                        // 0..1
  "eta_seconds":          30,
  "items":                [],                         // populated via GET /{id}
  "transfer_jobs":        [],                         // populated via GET /{id}
  "last_error":           null
}
```

### 3.3 Field guidance

- `pseudo_study_uids` — 1..10,000 paid, 1..50 preview. Dedup client-side; duplicates → `400 ERR_ORDER_DUPLICATE_STUDY`.
- `agreement_hash` — must match the MSA hash Sales provided. Mismatch → `400 ERR_ORDER_AGREEMENT_REQUIRED`.
- `notes` — ≤ 512 chars, free text in your audit trail. Never embed PHI.
- `preferred_download_ttl_hours` — 1..168; tier-capped (preview ≤ 24, paid ≤ 168). Sets the default TTL for later URL mint calls.
- **Not accepted in v0.1**: `saved_filter_id`, `billing_method`, `delivery_email`, any PHI, raw DICOM UIDs, patient name, DOB — either deferred ([dev-spec §3.2](../specs/dev-spec-order-fulfillment.md)) or forbidden ([dev-spec §6.8](../specs/dev-spec-order-fulfillment.md)).

### 3.4 Response quota headers

`X-RateLimit-Remaining` (per-minute cap — back off near 0), `X-Quota-Remaining-Daily` (order-creation only; preview=5, paid=50; GETs not counted), `Idempotency-Replayed` (`true` on re-submission of the same key).

---

## 4. Idempotency — why and how

`POST /v1/orders` mutates state and charges your quota. Network glitches are normal. You do not want the same cohort purchased twice because of a TCP reset.

### 4.1 The contract ([design-spec §2.10](../specs/design-spec-order-fulfillment.md))

- **Required** on all buyer-mutating POSTs (`/v1/orders`, `/cancel`, gateway `/progress|/complete|/fail`). Omitted → `400 ERR_IDEMP_MISSING`.
- **Format**: 16–128 chars, `[A-Za-z0-9_.-]`. Fresh ULID recommended.
- **Namespace**: `(key, buyer_pk)` — buyers can't collide with each other.
- **TTL**: Redis 24 h + PostgreSQL mirror 7 d.
- **Replay**: same key + same body → same `order_id`, byte-identical response, `Idempotency-Replayed: true` header. Never creates a second row.
- **Mismatch**: same key + different body → `409 ERR_IDEMP_MISMATCH`.

### 4.2 Mental model

> Think of `Idempotency-Key` as the check number you write on a money order. Submit the same check twice and the bank hands back the original receipt — no double withdrawal.

### 4.3 Client pattern

```bash
# Generate once, store, retry with the SAME key until you get a definitive response.
IDEM_KEY="$(uuidgen)"
for i in 1 2 3; do
  RESP=$(curl -sS -X POST https://fulfillment.radivault.io/v1/orders \
    -H "Authorization: Bearer $RADIVAULT_KEY" \
    -H "Idempotency-Key: $IDEM_KEY" \
    -H "Content-Type: application/json" \
    -d "$BODY" || true)
  echo "$RESP" | jq -e .order_id >/dev/null && break
  sleep $((2 ** i))
done
```

A replayed response is indistinguishable from a fresh one except for the `Idempotency-Replayed: true` header. If you want "genuinely new order", you must generate a new key.

---

## 5. Polling for readiness

v0.1 has no server-push (webhooks ship in v0.1.1, email in v0.2). You poll `GET /v1/orders/{id}` and back off appropriately.

### 5.1 Recommended cadence ([design-spec §2.4](../specs/design-spec-order-fulfillment.md))

| State | Poll interval |
|-------|---------------|
| `queued` / `validating` / `validated` | ≥ 2 s |
| `fetching` / `staging_partial` / `staging_complete` | ≥ 5 s |
| `ready_for_download` / `expired` / `cancelled` / `failed` | **stop polling immediately** |

Polling faster than ~1 req/s trips `429 ERR_RATE_LIMITED` — respect the `Retry-After` header.

### 5.2 Bash loop with exponential backoff

```bash
#!/usr/bin/env bash
# poll an order until terminal or ready
ORDER_ID="ord_01HXXORDER1ABCDEF"
BACKOFF=2; MAX=30

while : ; do
  RESP=$(curl -sS -H "Authorization: Bearer $RADIVAULT_KEY" \
         https://fulfillment.radivault.io/v1/orders/$ORDER_ID)
  STATE=$(echo "$RESP" | jq -r .state)
  PROG=$(echo "$RESP" | jq -r .progress)
  ETA=$(echo "$RESP" | jq -r .eta_seconds)
  echo "$(date -u +%H:%M:%S) state=$STATE progress=$PROG eta=${ETA}s"

  case "$STATE" in
    ready_for_download) echo "READY — mint URLs"; break ;;
    expired|cancelled|failed)
      echo "TERMINAL: $STATE"
      echo "$RESP" | jq '.last_error'
      exit 1
      ;;
    queued|validating|validated) sleep 2 ;;
    fetching|staging_partial|staging_complete)
      sleep $BACKOFF
      BACKOFF=$(( BACKOFF * 2 < MAX ? BACKOFF * 2 : MAX ))
      ;;
    *) sleep 5 ;;
  esac
done
```

### 5.3 Sample `GET /v1/orders/{id}` responses at each interesting state

```jsonc
// queued — just after POST /v1/orders
{ "state":"queued", "progress":0.0, "eta_seconds":30, "path_type":null,
  "transfer_jobs":[], "last_error":null }

// fetching — hospital Gateway is pulling
{ "state":"fetching", "progress":0.42, "eta_seconds":720, "path_type":"cold",
  "transfer_jobs":[
    { "transfer_job_id":"tj_01HXX...", "hospital_id":"hosp_opaque_a1b2c3d4",
      "state":"claimed", "attempt_count":1,
      "lease_expires_at":"2026-04-22T10:25:00Z", "last_error":null }
  ] }

// staging_complete — S3 COPY in progress
{ "state":"staging_complete", "progress":0.95, "eta_seconds":20, "path_type":"mixed" }

// ready_for_download — stop polling, mint URLs
{ "state":"ready_for_download", "progress":1.0,
  "ready_at":"2026-04-22T10:00:28Z", "expires_at":"2026-04-29T10:00:28Z" }

// failed — terminal; inspect last_error
{ "state":"failed", "progress":0.33,
  "last_error":{ "reason_code":"PACS_UNAVAILABLE",
                 "details":"connection timeout after 5 retries",
                 "at":"2026-04-22T10:22:00Z" } }
```

---

## 6. Getting download URLs — `POST /v1/orders/{id}/download-urls`

Once the order is `ready_for_download`, mint a batch of **per-file presigned HTTPS URLs** plus SHA-256 checksums and byte counts. You then download in parallel with integrity verification.

### 6.1 Request

```bash
curl -sS -X POST https://fulfillment.radivault.io/v1/orders/$ORDER_ID/download-urls \
  -H "Authorization: Bearer $RADIVAULT_KEY" \
  -H "Content-Type: application/json" \
  -d '{"ttl_seconds": 86400}' \
  > manifest.json

jq '{n_files, total_bytes, expires_at, ttl_seconds}' manifest.json
```

`ttl_seconds` is optional. Default: 24 h. Range: 3600 (1 h) to 604800 (7 d). Tier caps: preview = 24 h, paid = 7 d. Over tier → `422 ERR_URL_TTL_EXCEEDED`.

### 6.2 Response shape ([dev-spec §6.5 / §7.5](../specs/dev-spec-order-fulfillment.md))

```jsonc
HTTP/1.1 200 OK
Content-Type: application/json
Cache-Control: private, no-store

{
  "order_id":    "ord_01HXXORDER1ABCDEF",
  "ttl_seconds": 86400,
  "expires_at":  "2026-04-23T10:00:00Z",
  "minted_at":   "2026-04-22T10:00:00Z",
  "items": [
    {
      "pseudo_study_uid": "2.25.140737488355328.1.2.3",
      "files": [
        {
          "object_key": "staging/ord_01HXX.../hosp_opaque_a1b2c3d4/2.25.zzzz1.dcm",
          "bytes":      513222,
          "sha256":     "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
          "url":        "https://s3.ap-northeast-2.amazonaws.com/.../2.25.zzzz1.dcm?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Expires=86400&X-Amz-Signature=..."
        }
        /* ...one entry per DICOM instance... */
      ]
    }
    /* ...more study items... */
  ],
  "total_bytes": 282963036,
  "n_files":     512
}
```

### 6.3 Field guarantees

- `url` — HTTPS with SigV4 query auth. Opaque; any mutation breaks the signature.
- `sha256` — 64-char lowercase hex, no prefix. Content hash of exactly what the URL serves.
- `bytes` — expected length; sanity-check before SHA-256.
- `object_key` — opaque S3 path, safe as a filename. Pseudonymized only — no PHI, no hospital name, no original UIDs ([dev-spec §6.8](../specs/dev-spec-order-fulfillment.md)).
- `pseudo_study_uid` — stable group key; useful for per-study folders on disk. We recommend `./dicoms/<pseudo_study_uid>/<basename-of-object_key>`.

---

## 7. Parallel download with integrity check — `httpx` in 50 lines

An official Python SDK ships in v0.2. For now, plain `httpx` is enough.

```python
# download_order.py — parallel DICOM fetch + sha256 verify
# usage: python download_order.py manifest.json ./dicoms
import asyncio, hashlib, httpx, json, pathlib, sys

CONCURRENCY, TIMEOUT_S, MAX_RETRIES = 16, 300.0, 3
RETRY_CODES = {500, 502, 503, 504}

async def fetch(c, url, path, sha, nb):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = await c.get(url)
            if r.status_code in RETRY_CODES: r.raise_for_status()
            r.raise_for_status()
            body = r.content
            if len(body) != nb: raise ValueError(f"bytes mismatch: {path.name}")
            if hashlib.sha256(body).hexdigest() != sha:
                raise ValueError(f"sha256 mismatch: {path.name}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body); return
        except (httpx.HTTPStatusError, httpx.TransportError):
            if attempt == MAX_RETRIES: raise
            await asyncio.sleep(2 ** attempt)

async def main(manifest_path, out_dir):
    m = json.loads(pathlib.Path(manifest_path).read_text())
    out, sem = pathlib.Path(out_dir), asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as c:
        async def bounded(u, p, s, n):
            async with sem: await fetch(c, u, p, s, n)
        await asyncio.gather(*[
            bounded(f["url"],
                    out / item["pseudo_study_uid"] / pathlib.Path(f["object_key"]).name,
                    f["sha256"], f["bytes"])
            for item in m["items"] for f in item["files"]
        ])
    print(f"done: {m['n_files']} files, {m['total_bytes']} bytes")

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
```

### 7.1 Expected throughput

Single-threaded curl ~10–30 MB/s (SigV4 overhead). `httpx` + 16 concurrent typically saturates a 1 Gbps corporate link at ~100 MB/s. S3 `ap-northeast-2` (Seoul) is primary — best throughput from Asia-Pacific regions; transpacific is stable but higher latency.

### 7.2 Integrity failure handling

On sha256 mismatch: (1) log `request_id` + `object_key`; (2) retry the same URL once — AWS rarely returns corrupt bytes; (3) if still failing, mint a fresh batch (§8) — content and sha256 are unchanged, URL is new; (4) after three failures, email [support@radivault.io](mailto:support@radivault.io) with both `request_id`s. This is `ERR_DOWNLOAD_HASH_MISMATCH` territory and we investigate.

---

## 8. Handling refresh — 24 h URL TTL, re-mint flow

### 8.1 The rule

- Each URL batch has a `ttl_seconds` (default 24 h, max = your tier cap). After that, every URL returns `403 SignatureDoesNotMatch` (AWS).
- The **order itself** is valid for 7 days (paid) or tier cap. Within that window you can call `POST /v1/orders/{id}/download-urls` **as often as you want** (subject to 1 req / 5 s rate limit) and get a fresh batch.
- You cannot revoke an already-minted URL mid-stream. AWS S3 has no revocation for presigned URLs. We compensate with short TTLs and rotate on demand.

### 8.2 Mental model

> Download URLs are like short-lived concert tickets — they scan at the gate until they expire. We cannot un-print a ticket once you hold it. So we print them with short expiry and you come back for new ones. If you lose a ticket (or your download fails), just ask for another batch. Your order itself remains valid for 7 days — plenty of time to re-mint as many URL batches as you need.

### 8.3 Re-mint example

```bash
# manifest.json from 2 days ago — URLs are dead
curl -sSI "$(jq -r '.items[0].files[0].url' manifest.json)" | head -1
# HTTP/1.1 403 Forbidden

# order is still ready_for_download (within 7-day window)
curl -sS -X POST https://fulfillment.radivault.io/v1/orders/$ORDER_ID/download-urls \
  -H "Authorization: Bearer $RADIVAULT_KEY" \
  -H "Content-Type: application/json" \
  -d '{"ttl_seconds": 86400}' \
  > manifest_v2.json

# sha256 for each file is identical; url and minted_at are fresh
diff <(jq '.items[].files[].sha256' manifest.json    | sort) \
     <(jq '.items[].files[].sha256' manifest_v2.json | sort)
# (empty — same content)
```

### 8.4 Re-mint rate limit

- `POST /v1/orders/{id}/download-urls`: 1 request per 5 seconds, burst 10, per buyer. Excess → `429 ERR_URL_MINT_RATE`.
- This is distinct from the per-minute API rate limit.
- In practice: mint once per download session; retry individual files against the latest batch.

---

## 9. Handling expiration — 7-day order TTL

### 9.1 What expiration means

- The order is in `ready_for_download` for exactly 7 days (paid tier) from `ready_at`. At that point an internal timer transitions it to `expired`.
- Once `expired`:
  - `POST /v1/orders/{id}/download-urls` → `410 ERR_ORDER_EXPIRED`.
  - Any URL previously minted remains valid until its own TTL expires — but the S3 Lifecycle rule deletes the `staging/<order_id>/` prefix 8 days after `ready_at` ([dev-spec FR-76](../specs/dev-spec-order-fulfillment.md)), so even unexpired URLs stop serving ~1 day after order expiry.
  - You cannot un-expire an order.

### 9.2 Recovery — submit a new order with the same UIDs

```bash
curl -sS -X POST https://fulfillment.radivault.io/v1/orders \
  -H "Authorization: Bearer $RADIVAULT_KEY" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d "{\"pseudo_study_uids\": [\"2.25.140737488355328.1.2.3\"], \"agreement_hash\": \"$RADIVAULT_MSA_HASH\"}"
```

- The same `pseudo_study_uid`s will resolve to the same studies — content is stable.
- In v0.1 this re-runs the full fulfillment pipeline. Hot-path optimization (studies already in central hot storage → instant re-delivery) is deferred per [dev-spec §3.2 #5](../specs/dev-spec-order-fulfillment.md); treat re-orders as cold-path.
- **Billing note**: in v0.1, `pending_billing` accumulates; no actual charge. In v0.2, re-orders are priced identically to first orders — there is no free re-download discount in the v0.2 spec we have today. See §13.

### 9.3 Best practice — archive as you download

Treat RadiVault as a delivery service, not a storage service. The moment a file lands, copy it to your own S3 / GCS / data lake. Do not rely on the 7-day window for ad-hoc re-download; one bad on-call page and you'll miss it.

---

## 10. Cancellation — allowed states

### 10.1 State matrix ([design-spec §2.7](../specs/design-spec-order-fulfillment.md))

| Current state | Buyer cancel? | Response |
|---------------|---------------|----------|
| `submitted`, `validating`, `validated`, `queued` | Yes | `200 OK`, `state: "cancelled"`. Any queued transfer jobs are cancelled server-side. |
| `fetching`, `staging_partial`, `staging_complete` | **No — admin only** | `409 ERR_ORDER_STATE_TRANSITION`, with `hint` asking you to contact support. Studies already uploaded may be retained internally as *unlinked* and offered in future orders ([dev-spec §6.7.7](../specs/dev-spec-order-fulfillment.md)). |
| `ready_for_download`, `delivering` | No — admin only | `409 ERR_ORDER_STATE_TRANSITION`. v0.1 has no refund flow; `refund_eligible: false`. |
| `expired`, `cancelled`, `delivered`, `failed` | No — terminal | `409 ERR_ORDER_STATE_TRANSITION` (idempotent; no state change). |

### 10.2 Sample call

```bash
curl -sS -X POST https://fulfillment.radivault.io/v1/orders/$ORDER_ID/cancel \
  -H "Authorization: Bearer $RADIVAULT_KEY" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{"reason": "wrong cohort; will resubmit"}'
```

```jsonc
HTTP/1.1 200 OK
{
  "order_id":        "ord_01HXX...",
  "state":           "cancelled",
  "cancelled_at":    "2026-04-22T10:03:00Z",
  "refund_eligible": false
}
```

### 10.3 Admin cancellation during fetch

If you absolutely must stop a fetching order (e.g. the cohort turned out to be wrong after commit), email [support@radivault.io](mailto:support@radivault.io) with the `order_id` and a brief reason. We respond within **1 business day**. Admin-force-cancel marks the order `cancelled` and detaches any already-uploaded studies into an internal `unlinked_study` table; those studies may be offered back to you (or another buyer in scope) in a subsequent order. **Legal-review flag**: contractual treatment of cancellation-during-fetch — whether the partial fetch counts toward a later paid download — is under legal review; confirm with Sales before assuming free re-delivery.

---

## 11. Error handling — the six you will actually see

Every error uses the standard envelope ([dev-spec §7](../specs/dev-spec-order-fulfillment.md)):

```json
{
  "error":       "<ERR_CODE>",
  "detail":      "<short technical reason, English>",
  "message_ko":  "<Korean user-facing message>",
  "message_en":  "<English user-facing message>",
  "request_id":  "01HXX...",
  "doc_url":     "https://docs.radivault.io/fulfillment/errors/<ERR_CODE>",
  "hint":        "<actionable remediation>",
  "retry_after": null,
  "extra":       { "...": "..." }
}
```

Always log `request_id` before retrying. Support tickets start from that ID.

### 11.1 `ERR_ORDER_SCOPE_FORBIDDEN` — 403

Cohort includes hospitals your key is not scoped to.

```json
{ "error":"ERR_ORDER_SCOPE_FORBIDDEN",
  "detail":"cohort includes 2 hospitals excluded by your key scope",
  "hint":"Use /v1/search/facets to see allowed hospitals, or contact sales@radivault.io to expand scope.",
  "extra":{"excluded_hospital_count":2, "sales_contact":"sales@radivault.io"} }
```

**Recovery**: drop the excluded hospitals, or expand scope via Sales.

### 11.2 `ERR_ORDER_TIER_EXCEEDED` — 422

Cohort size exceeds your tier cap.

```json
{ "error":"ERR_ORDER_TIER_EXCEEDED",
  "detail":"cohort size 120 exceeds preview tier cap 50",
  "hint":"Split into multiple orders, or contact sales@radivault.io for paid tier (10,000/order).",
  "extra":{"tier":"preview","cohort_size":120,"tier_cap":50,"paid_tier_cap":10000} }
```

**Recovery**: split client-side, or upgrade. No contractual penalty for splitting.

### 11.3 `ERR_ORDER_STATE_TRANSITION` — 409

Current state does not allow the requested action (most common: buyer cancel during `fetching`).

```json
{ "error":"ERR_ORDER_STATE_TRANSITION",
  "detail":"cannot cancel order in state=fetching",
  "hint":"Cancellation during fetch requires admin intervention. Contact support@radivault.io with your order_id.",
  "extra":{"current_state":"fetching","allowed_buyer_cancel_states":["submitted","validating","validated","queued"]} }
```

**Recovery**: wait for completion (usually faster than admin cancel) or email support.

### 11.4 `ERR_ORDER_EXPIRED` — 410

Tried to mint URLs for an expired order.

```json
{ "error":"ERR_ORDER_EXPIRED",
  "detail":"order expired at 2026-04-29T10:00:00Z (now 2026-04-30T05:12:45Z)",
  "hint":"Submit a new order with the same pseudo_study_uids to re-download.",
  "extra":{"expired_at":"2026-04-29T10:00:00Z","window_days":7} }
```

**Recovery**: see §9.2 — re-order with the same UIDs.

### 11.5 `ERR_URL_MINT_FAILED` — 502

Transient AWS S3 / KMS failure on our side.

```json
{ "error":"ERR_URL_MINT_FAILED",
  "detail":"boto3 presign failed: KmsKeyDisabledException",
  "hint":"Transient server-side issue. Retry in 30 seconds.",
  "retry_after":30,
  "extra":{"downstream":"s3-kms","op":"generate_presigned_url"} }
```

**Recovery**: respect `Retry-After`. If it persists beyond ~5 minutes, page [support@radivault.io](mailto:support@radivault.io).

### 11.6 `ERR_DOWNLOAD_HASH_MISMATCH` — client-side

Raised by **your** downloader when a file's sha256 does not match the manifest. Rarely an S3 issue — usually a partial write / truncation on your side. Re-download once; if it fails again re-mint the batch; after three failures contact support with both `request_id`s and the `object_key`.

---

## 12. Rate limits and quotas

### 12.1 Response headers (200 / 429)

`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` — per-minute cap (base 60). `X-Quota-Limit-Daily`, `X-Quota-Remaining-Daily`, `X-Quota-Reset-Daily` — daily **order-creation** quota (preview = 5, paid = 50); resets 00:00 UTC. `Retry-After` — present on 429, must be respected. `X-Request-Id` — ULID for support tickets. `Idempotency-Replayed` — `true` if the response is a cached replay.

### 12.2 Tier behavior ([dev-spec FR-11 / config §6.6](../specs/dev-spec-order-fulfillment.md))

| Dimension | Preview | Paid |
|-----------|---------|------|
| Studies per order (cap) | 50 | 10,000 |
| Order bytes (cap) | 10 GB | 2 TB |
| Orders per day | 5 | 50 |
| Download URL TTL (max) | 24 h | 7 d |
| URL mint rate | 1 req / 5 s (burst 10) | 1 req / 5 s (burst 10) |

*Exact tier parameters are contractual — see your MSA. Numbers above match the v0.1 defaults.*

### 12.3 Upgrade path

Email [sales@radivault.io](mailto:sales@radivault.io) with your `buyer_id`, current tier, workload description (daily orders, cohort size, peak concurrency), and intended use (training, validation, regulatory submission). Preview-to-paid turnaround: 1–2 business days pending MSA/DPA.

---

## 13. v0.1 billing — what the stub means for you

### 13.1 What v0.1 does and does not do

- Every paid-tier order returns `total_estimated_usd` = `n_studies × unit_price_usd` (default **$5.00/study**, Tier 1 auto-label; subject to MSA) and is stamped `state_billing: "pending_billing"`.
- **No charge is posted.** No Stripe, no PG, no invoice. Preview tier is free in v0.1 and in v0.2.
- Paid-tier `pending_billing` entries accumulate for reconciliation when v0.2 payment ships. Your MSA should spell out whether those entries retroactively bill on v0.2 launch, or are waived, or are converted to a committed volume. **Legal-review flag**: confirm with Sales / Legal before committing to paid-tier volume you are not ready to settle in v0.2.

### 13.2 What ships in v0.2

Stripe + Korean local PG (Toss / KG Inicis) for card/wire, per-country VAT, receipt PDFs, dynamic `refund_eligible`, saved cohorts, and webhook notifications for `ready_for_download` (no more polling).

### 13.3 Forward compatibility

Code written against v0.1 keeps working in v0.2 — the only addition is an optional `payment_method_id` on `POST /v1/orders` (spec TBD). FSM, URL schema, and auth model do not change.

---

## 14. FAQ

### Q1. Can I re-download the same cohort after 7 days without re-paying?

**Not in v0.1.** In v0.1 the billing stub means nothing is ever charged, so "re-download free" vs "re-download priced" is a v0.2 policy decision. Our current v0.2 spec prices re-orders identically to first orders — there is no auto-discount for re-fetching the same UIDs. Best practice: archive to your own storage during the 7-day window. **Legal-review flag**: MSA language for repeated delivery of the same studies (including cancellation-during-fetch retention) is under review.

### Q2. What if some studies fail during fetch?

v0.1 is **all-or-nothing per order**. If any transfer job in the order exhausts its retry budget, the whole order moves to `failed` ([dev-spec FR-55](../specs/dev-spec-order-fulfillment.md)). Partial delivery is deferred to v0.2. Practical recovery: split large cohorts across several smaller orders — a single hospital outage then costs you one order, not the whole cohort.

### Q3. How do I purchase the same cohort again?

Submit a fresh `POST /v1/orders` with the same `pseudo_study_uid`s and a new `Idempotency-Key`. Content is stable (DICOMs are re-pulled from the source; output bytes are reproducible). There is no "re-order" convenience endpoint in v0.1.

### Q4. Can I use a CDN in front of the download URLs?

**Not in v0.1.** RadiVault uses S3 SigV4 presigned URLs directly. CloudFront signed URLs ship alongside SOC 2 Type I. Fronting the URLs with your own CDN exposes plaintext DICOMs to that CDN and pulls it into your compliance scope — usually better to download once and redistribute internally.

### Q5. Does the URL work from IP-allowlisted corporate networks?

Yes — standard HTTPS GET to `s3.ap-northeast-2.amazonaws.com`. Allowlist AWS Seoul S3 ranges. TLS 1.2+ required; corporate MITM inspection and legacy TLS 1.0/1.1 stacks will break signing.

### Q6. Where are the buckets regionally hosted?

`ap-northeast-2` (Seoul) is the v0.1 primary. Cross-region replication is deferred ([dev-spec §3.2 #16](../specs/dev-spec-order-fulfillment.md)). Transpacific single-connection throughput ~50–80 MB/s; the §7 parallel pattern ~300–500 MB/s.

### Q7. What is the SLA for the fetch pipeline?

v0.1 has no contractual SLA; service is in pilot. Observed targets ([design-spec §9.3](../specs/design-spec-order-fulfillment.md)): hot-path 3 studies → `ready_for_download` in < 30 s p95; URL mint < 1 s p95; 1 GB on 100 Mbps → < 2 minutes. Cold-path throughput is PACS-I/O-bound (~100 studies/hour/hospital). Formal SLA (99.9% availability) lands with SOC 2 Type I — [sales@radivault.io](mailto:sales@radivault.io).

---

## 15. Next steps

1. **End-to-end test on preview tier** — run §3–§7 against a 3-study cohort (< 2 minutes total). Record every `X-Request-Id`.
2. **Upgrade to paid tier** — email [sales@radivault.io](mailto:sales@radivault.io) with your `buyer_id` and workload estimate. Preview keys stay active during cutover.
3. **Production checklist**: API key in secrets manager (not CI env files); `Idempotency-Key` regenerated per real order and retained for retries; polling ≥ 5 s with terminal-state early exit; sha256 verified before ingest; downloads archived to your own storage within 24 h; `request_id` logged on every 4xx/5xx; scope and tier limits from MSA captured in your runbook.
4. **Procurement**: SOC 2 Type II status, PIPA §28-8 legal opinion, MSA/DPA templates — under NDA via Sales.
5. **Subscribe to the changelog** — v0.2 adds Stripe billing, webhooks, saved cohorts, Python SDK. Email [buyer@radivault.io](mailto:buyer@radivault.io).

**Support**: [support@radivault.io](mailto:support@radivault.io) — include your `order_id`, `X-Request-Id`, and timestamp.
**Sales (tier / purchase / MSA)**: [sales@radivault.io](mailto:sales@radivault.io).
**Compliance questions (PIPA, HIPAA alignment, audit logs)**: [compliance@radivault.io](mailto:compliance@radivault.io).

---

## 16. Change history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| v0.1 | 2026-04-22 | @marketer | Initial draft. Based on order-fulfillment v0.1 (QA PASS with minor, 2026-04-22). Anchored to [dev-spec §3, §6, §7](../specs/dev-spec-order-fulfillment.md) and [design-spec §2, §7, §9](../specs/design-spec-order-fulfillment.md). Legal-review items flagged: cancellation-during-fetch contract language, download URL revocation limits, re-order billing policy, cross-border delivery audit retention. Awaiting Kyle approval. |
