# RadiVault Search API — Buyer Quickstart

> **Status**: Draft — Kyle review required before any external distribution
> **Document version**: v0.1 (2026-04-22)
> **Author**: @marketer (RadiVault)
> **Audience**: ML engineers, data scientists, and application developers at buyer companies integrating the RadiVault Search API
> **Language**: English
> **Purpose**: get from "I just received an API key" to "I ran my first cohort search" in under 15 minutes
> **API version**: `v1` (metadata-index v0.1 — QA PASS with minor, 2026-04-22)
> **Authoritative references**: [dev-spec-metadata-index §7](../specs/dev-spec-metadata-index.md) (API contracts), [design-spec-metadata-index §2](../specs/design-spec-metadata-index.md) (buyer API UX)
> **Distribution**: not for external distribution until Kyle approves.

---

## 0. TL;DR

```bash
# 1. Set your key
export RADIVAULT_KEY="rv_live_abcd1234_Zj8f2vX9qK2sLpN4mQbW7yR1eT5aU6c"

# 2. Smoke test — no auth needed
curl -s https://search.radivault.io/v1/version | jq .

# 3. First authenticated call
curl -s -X POST https://search.radivault.io/v1/search/studies \
  -H "Authorization: Bearer $RADIVAULT_KEY" \
  -H "Content-Type: application/json" \
  -d '{"modality":["MR"],"body_part":["HEAD"],"age_bucket":["40-50","50-60"],"sex":["M"],"limit":10}' \
  | jq '{total: .total_hint, n: (.items|length), modalities: .facets.modality}'
```

If that returned `200 OK` with an `items` array, you're live. Read on for the rest.

---

## 1. Prerequisites

You need:

- **Your API key** — a 48-character string starting with `rv_live_` (or `rv_test_` for test environments). Delivered via an encrypted one-time-use link with 24h expiry. If you haven't received it, contact [sales@radivault.io](mailto:sales@radivault.io).
- **Terminal with `curl` and `jq`** — macOS/Linux built-in; Windows users can use WSL or Git Bash.
- **(Optional) Python 3.10+ with `httpx`** — for the Python examples in §11.
- **A basic HTTPS outbound path** to `search.radivault.io` (TCP 443). No VPN or IP allowlisting required for v0.1.

### 1.1 Base URL

- **Production**: `https://search.radivault.io`
- **Test (sandbox)**: `https://search.sandbox.radivault.io` *(v0.2+)*

All endpoints are prefixed with `/v1/`. Example: `POST /v1/search/studies`.

### 1.2 Store the key

Never commit the key to version control. Use environment variables or your secrets manager.

```bash
# ~/.zshrc or equivalent
export RADIVAULT_KEY="rv_live_abcd1234_Zj8f2vX9qK2sLpN4mQbW7yR1eT5aU6c"
```

If you suspect a key has been exposed, email [support@radivault.io](mailto:support@radivault.io) immediately — we can revoke within minutes.

---

## 2. Hello World — `/v1/version`

The first call you should ever make is unauthenticated. It verifies DNS, TLS, and that the service is reachable.

```bash
curl -s https://search.radivault.io/v1/version
```

Expected response:

```json
{
  "service":              "radivault-search",
  "version":              "0.1.0",
  "api_contract_version": "1",
  "built_at":             "2026-04-22T09:00:00Z"
}
```

If this call fails, do not attempt authenticated calls — resolve the network issue first. Typical causes: corporate proxy stripping TLS, DNS block, outbound firewall.

---

## 3. Authentication

RadiVault uses **HTTP Bearer token** authentication. Send your key on every authenticated request:

```
Authorization: Bearer rv_live_abcd1234_Zj8f2vX9qK2sLpN4mQbW7yR1eT5aU6c
```

### 3.1 Key format

- Prefix: `rv_live_` (production) or `rv_test_` (sandbox).
- 8-character Key ID (kid) — visible in server logs for support.
- `_` separator.
- 32-character random secret — never logged, never recoverable.
- Total: 48 characters.

### 3.2 Rate-limit and quota headers

Every **200** and **429** response carries these headers:

| Header | Meaning |
|--------|---------|
| `X-RateLimit-Limit` | Per-minute request cap for your tier (preview: 20, paid: 600). |
| `X-RateLimit-Remaining` | Requests remaining in the current minute window. |
| `X-RateLimit-Reset` | Unix epoch seconds — when the next minute window opens. |
| `X-Quota-Limit-Daily` | Daily quota for your tier (preview: 100, paid: 10,000). |
| `X-Quota-Remaining-Daily` | Requests remaining today (resets at 00:00 UTC). |
| `X-Quota-Reset-Daily` | Unix epoch seconds — next UTC midnight. |
| `Retry-After` | **429 only**. Seconds to wait before retrying. |
| `X-Request-Id` | Server-generated ULID — **include in every support ticket**. |

Always read `X-RateLimit-Remaining` and back off when it approaches 0. Your client is responsible for smooth pacing.

### 3.3 Key lifecycle

- **Preview keys**: expire after 90 days. Rotate by requesting a new key from Sales; both keys can stay active during cutover.
- **Paid keys**: expire after 180 days by default.
- **Rotation**: zero-downtime — you can run old and new keys in parallel, then revoke the old one.
- **Revocation**: email [support@radivault.io](mailto:support@radivault.io). Effective within minutes.

---

## 4. Your first cohort search

The main endpoint is `POST /v1/search/studies`. It takes a JSON filter body and returns matching study metadata plus optional facet aggregations.

### 4.1 Realistic example — "MR brain studies, adult men 40–60"

```bash
curl -s -X POST https://search.radivault.io/v1/search/studies \
  -H "Authorization: Bearer $RADIVAULT_KEY" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: $(uuidgen)" \
  -d '{
    "modality":           ["MR"],
    "body_part":          ["HEAD"],
    "age_bucket":         ["40-50", "50-60"],
    "sex":                ["M"],
    "study_date_shifted": {"from": "2024-01-01", "to": "2026-04-20"},
    "min_hospitals":      3,
    "sort":               "date_desc",
    "limit":              50,
    "include_facets":     true
  }'
```

### 4.2 Annotated response

```jsonc
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-Id: 01HXQ8WQ9Z3K7V5B2A1N6P4R9T
X-RateLimit-Limit: 600
X-RateLimit-Remaining: 584
X-RateLimit-Reset: 1713825600
X-Quota-Limit-Daily: 10000
X-Quota-Remaining-Daily: 9341
X-Quota-Reset-Daily: 1713830400

{
  // Up to `limit` matching studies, sorted by the chosen `sort` key.
  "items": [
    {
      "pseudo_study_uid":    "2.25.140737488355328.1.2.3",  // stable opaque ID — use for ordering
      "modality":            "MR",
      "body_part":           "HEAD",
      "age_bucket":          "50-60",                        // 10-year buckets only — never exact age
      "sex":                 "M",
      "study_date_shifted":  "2026-04-18",                   // date is shifted per-patient for de-identification
      "manufacturer":        "SIEMENS",
      "model_name":          "MAGNETOM Skyra",
      "n_instances":         384,                            // DICOM instances (slices)
      "n_series":            6,
      "total_bytes":         512288128,
      "hospital_opaque_id":  "c3d4e5f6a7b8c9d0",             // per-buyer salted sha256 — different buyers see different IDs
      "ingested_at":         "2026-04-21T03:20:51Z"
    }
    // ... up to 50 items
  ],

  // Per-dimension aggregate counts across the ENTIRE filtered corpus, not just this page.
  "facets": {
    "modality":     [{"value": "MR", "count": 18244, "is_truncated": false}],
    "body_part":    [{"value": "HEAD", "count": 18244, "is_truncated": false}],
    "sex":          [{"value": "M", "count": 9182, "is_truncated": false}],
    "age_bucket":   [
      {"value": "40-50", "count": 4217, "is_truncated": false},
      {"value": "50-60", "count": 4965, "is_truncated": false}
    ],
    "manufacturer": [
      {"value": "SIEMENS", "count": 5120, "is_truncated": false},
      {"value": "GE",      "count": 2911, "is_truncated": false},
      {"value": "PHILIPS", "count": 1151, "is_truncated": false}
    ],
    "year":         [
      {"value": "2026", "count":  580},
      {"value": "2025", "count": 4012},
      {"value": "2024", "count": 4590}
    ]
  },

  // Total number of studies matching the filter across all pages.
  "total_count":        9182,
  "total_hint":         null,
  "total_count_exact":  true,

  // Opaque continuation token — pass as `cursor` on your next request.
  "next_cursor":        "eyJ2IjoxLCJkIjoiMjAyNi0wNC0xOCIsInAiOjEyMzQ1LCJzIjoiWWJNM3o3SzlRYVAxIiwiayI6ImRhdGVfZGVzYyJ9",
  "has_next":           true,
  "page_size":          50,
  "response_truncated": false
}
```

**Tip**: the `facets` block is computed against the entire filtered corpus, not just the current page. That is why you can drive a distribution chart from a single first request.

---

## 5. Filter reference

All filters on `POST /v1/search/studies` are optional — but at least one is nearly always required to avoid `ERR_QUERY_TOO_BROAD` (see §8). Field shapes come from [dev-spec §6.4](../specs/dev-spec-metadata-index.md).

| Field | Type | Max items | Example | Notes |
|-------|------|-----------|---------|-------|
| `modality` | `list[str]` | 10 | `["CT", "MR"]` | **Uppercase only**. Enum: CT, MR, CR, DR, MG, US, XA, NM, PT, RF. |
| `body_part` | `list[str]` | 10 | `["CHEST", "ABDOMEN"]` | Uppercase. Normalized from DICOM `BodyPartExamined`. |
| `age_bucket` | `list[str]` | 10 | `["40-50", "50-60"]` | 10-year buckets: `0-10`, `10-20`, ... `80+`. Exact age is never exposed. |
| `sex` | `list["M" \| "F" \| "O"]` | 3 | `["M", "F"]` | `O` = other / unknown. |
| `study_date_shifted` | `{from, to}` object | — | `{"from":"2024-01-01","to":"2026-04-20"}` | **Both bounds required** if present. `YYYY-MM-DD`, ISO 8601. Dates are per-patient-shifted for de-identification — do not rely on exact calendar alignment. |
| `manufacturer` | `list[str]` | 10 | `["SIEMENS", "GE"]` | Normalized uppercase. |
| `min_hospitals` | `int` (1–20) | — | `3` | Drops results that would come from fewer than N hospitals. Prevents single-site bias. |
| `sort` | `"date_desc" \| "ingested_desc"` | — | `"date_desc"` | Default: `date_desc`. |
| `limit` | `int` (1–200) | — | `50` | Preview tier caps at 100; paid tier at 200. |
| `cursor` | `str` | — | `"eyJ2Ijo..."` | Opaque. Pass the server's `next_cursor` unchanged. |
| `include_facets` | `bool` | — | `true` | Set to `false` to skip facet computation and reduce latency on large queries. |

### 5.1 Forbidden inputs

The following are explicitly **not** in the v0.1 API shape and will be ignored by pydantic validation:

- Raw `StudyInstanceUID`, `SeriesInstanceUID`, `SOPInstanceUID` — never accepted as input.
- Patient name, DOB, MRN, or any direct identifier — never accepted.
- Diagnosis names, ICD-10, RadLex, or free-text report search — not in v0.1. NLP labels ship in a later release.

---

## 6. Facets — using the `include_facets` block

Facets are histograms per dimension, computed over the **entire filtered corpus** for your current request. Use them to:

- Drive a distribution chart in your internal data tool.
- Validate a cohort's device mix or sex balance before committing to a larger pull.
- Guide progressive filter refinement.

### 6.1 Example — explore manufacturer mix

```bash
curl -s -X POST https://search.radivault.io/v1/search/studies \
  -H "Authorization: Bearer $RADIVAULT_KEY" \
  -H "Content-Type: application/json" \
  -d '{"modality":["CT"],"body_part":["CHEST"],"limit":1,"include_facets":true}' \
  | jq '.facets.manufacturer'
```

Response excerpt:

```json
[
  {"value": "SIEMENS",   "count": 14222, "is_truncated": false},
  {"value": "GE",        "count": 11805, "is_truncated": false},
  {"value": "PHILIPS",   "count":  7011, "is_truncated": false},
  {"value": "__other__", "count":   312, "is_truncated": true}
]
```

### 6.2 `is_truncated` semantics

- `false` — this is an exact bucket; no equal-or-higher-count bucket is hidden.
- `true` — typically on a `__other__` bucket summarizing the long tail beyond the top 50. To enumerate the long tail, narrow the filter and re-search.

### 6.3 Auto-suppression on broad queries

If your filter would match more than ~2 million rows, facets are auto-suppressed and `meta.facets_suppressed: true` is set. Narrow the filter or set `include_facets: false` explicitly to avoid wasted work.

---

## 7. Pagination

Pagination is **cursor-based** (keyset). Offset-based pagination is not supported.

### 7.1 Iterate all pages

```bash
#!/usr/bin/env bash
set -euo pipefail
CURSOR="null"; TOTAL=0
while : ; do
  if [[ "$CURSOR" == "null" ]]; then
    BODY='{"modality":["MR"],"body_part":["HEAD"],"limit":100,"include_facets":false}'
  else
    BODY=$(jq -nc --arg c "$CURSOR" '{modality:["MR"],body_part:["HEAD"],limit:100,include_facets:false,cursor:$c}')
  fi
  RESP=$(curl -s -X POST https://search.radivault.io/v1/search/studies \
    -H "Authorization: Bearer $RADIVAULT_KEY" -H "Content-Type: application/json" -d "$BODY")
  N=$(echo "$RESP" | jq '.items | length'); TOTAL=$((TOTAL + N))
  echo "page: $N items (running total: $TOTAL)"
  [[ "$(echo "$RESP" | jq -r '.has_next')" != "true" ]] && break
  CURSOR=$(echo "$RESP" | jq -r '.next_cursor')
done
```

### 7.2 Rules

- **Cursors are opaque** — do not parse, decode, or cache the internal contents. Treat them as a black box. Server version bumps may invalidate cursors without warning (`ERR_CURSOR_VERSION`).
- **Filter must stay identical between pages** — change any filter field and you will receive `ERR_CURSOR_FILTER_CHANGED`. Drop the cursor and restart from page 1 with the new filter.
- **No time-based cursor expiry** in v0.1; cursors stay valid until the next server deploy.

---

## 8. Error handling

Every error uses the same envelope:

```json
{
  "error":       "<ERROR_CODE>",
  "detail":      "<short technical reason in English>",
  "message_ko":  "<Korean user-facing message>",
  "message_en":  "<English user-facing message>",
  "request_id":  "01HXX...",
  "doc_url":     "https://docs.radivault.io/search/errors/<ERROR_CODE>",
  "hint":        "<actionable remediation>",
  "retry_after": null
}
```

Some errors add an `extra` object with machine-readable context. Always log `request_id` before retrying — support tickets start from that ID.

### 8.1 The five errors you will actually see

#### `ERR_QUERY_TOO_BROAD` — HTTP 422

Your filter would match more than 10 million rows. The server refuses to execute for everyone's sake.

```json
{
  "error":   "ERR_QUERY_TOO_BROAD",
  "detail":  "estimated rows 12,833,091 exceeds limit 10,000,000",
  "hint":    "Try adding modality=['CT'] or study_date_shifted.from='2024-01-01'.",
  "extra":   {
    "estimated_rows":       12833091,
    "estimated_rows_limit": 10000000,
    "suggested_filters":    ["modality", "study_date_shifted"]
  }
}
```

**Recovery**: add `modality` and/or a narrow `study_date_shifted`. Re-run.

#### `ERR_BUYER_QUOTA` — HTTP 429

You have used today's request quota. `Retry-After` tells you when it resets.

```json
{
  "error":       "ERR_BUYER_QUOTA",
  "detail":      "daily quota exhausted: 100/100 requests used",
  "hint":        "Contact sales@radivault.io to discuss an upgrade.",
  "retry_after": 14382,
  "extra":       {"tier": "preview", "paid_tier_daily_limit": 10000}
}
```

**Recovery**: wait until `quota_reset_at`, or email [sales@radivault.io](mailto:sales@radivault.io) to upgrade tier. Do not hammer the 429 — every retry still counts against your rate-limit.

#### `ERR_CURSOR_FILTER_CHANGED` — HTTP 400

You paginated with a cursor issued for a different filter.

```json
{
  "error": "ERR_CURSOR_FILTER_CHANGED",
  "hint":  "Drop the `cursor` field from your request body and re-send."
}
```

**Recovery**: drop the `cursor`, keep the current filter, request page 1 of the new filter. Your SDK/client should detect this error and restart the iteration automatically.

#### `ERR_AUTH_REVOKED` *(maps to `ERR_AUTH_EXPIRED`)* — HTTP 401

Your key was revoked or has expired.

```json
{
  "error": "ERR_AUTH_EXPIRED",
  "hint":  "Contact sales@radivault.io for a new key."
}
```

**Recovery**: request a new key. Do not retry with the revoked key — the audit log flags repeated 401s.

#### `ERR_PAGE_LIMIT` — HTTP 400

You requested more items per page than your tier allows.

```json
{
  "error":  "ERR_PAGE_LIMIT",
  "detail": "limit 200 exceeds preview-tier max 100",
  "hint":   "Reduce `limit` to 100 or less, or request a paid tier."
}
```

**Recovery**: reduce `limit`; paid tier caps at 200.

### 8.2 All error codes at a glance

Full taxonomy: [dev-spec §7.6](../specs/dev-spec-metadata-index.md).

| Code | HTTP | Category |
|------|------|----------|
| `ERR_AUTH_MISSING` / `ERR_AUTH_FORMAT` / `ERR_AUTH_EXPIRED` | 401 | auth |
| `ERR_SCOPE_FORBIDDEN` | 403 | auth |
| `ERR_REQUEST_SCHEMA` / `ERR_FILTER_TOO_MANY` / `ERR_PAGE_LIMIT` | 400 | validation |
| `ERR_CURSOR_FILTER_CHANGED` / `ERR_CURSOR_VERSION` | 400 | cursor |
| `ERR_QUERY_TOO_BROAD` | 422 | cost |
| `ERR_RATE_LIMITED` / `ERR_BUYER_QUOTA` / `ERR_BUYER_CONCURRENCY` | 429 | rate |
| `ERR_STUDY_NOT_FOUND` | 404 | data |
| `ERR_IDEMP_UNAVAILABLE` / `ERR_DB_UNAVAILABLE` | 503 | infra |
| `ERR_QUERY_TIMEOUT` | 504 | perf |
| `ERR_INTERNAL` | 500 | generic |

---

## 9. Rate limits and tiers

| Tier | RPM | Daily quota | Max `limit` per page | Concurrency | Facet suppression |
|------|-----|-------------|----------------------|-------------|-------------------|
| **Preview** | 20 | 100 | 100 | 3 | Aggressive |
| **Paid** | 600 | 10,000 | 200 | 20 | Only above ~2M rows |

Exact tier parameters are contractual — see your MSA.

### 9.1 Requesting a tier upgrade

Email [sales@radivault.io](mailto:sales@radivault.io) with:

- Your `buyer_id` (we gave it when we issued the key).
- Your current tier.
- A brief description of the workload (QPS, daily volume, concurrency).
- Intended use (training data research, cohort exploration for paid purchase, etc.).

Typical turnaround for preview→paid upgrade: 1–2 business days (MSA/DPA pending).

---

## 10. Best practices

### 10.1 Cache by filter hash (client-side)

Hash the canonical form of your filter (sorted keys, lowercase values inside lists, etc.) as SHA-256 and use it as a cache key. Identical filters returning identical page-1 results can be cached for minutes on your side without surprising users. Our server exposes an internal `filter_sha256` in audit logs that is computed the same way.

### 10.2 Batch when you can, not when you can't

Pull page size `100` (preview) or `200` (paid) to amortize round-trip cost. Do not, however, issue 10 parallel filter variations hoping to "parallelize" — concurrency is capped per buyer; excess requests get `ERR_BUYER_CONCURRENCY`.

### 10.3 Retry with exponential jitter

- Retry only on `429`, `503`, `504`, or transient network failure.
- Never retry `4xx` validation errors — they are deterministic.
- Use exponential backoff with jitter: `sleep = min(base * 2**attempt, 60) + uniform(0, base)`.
- Respect `Retry-After` when present; it supersedes your backoff.

### 10.4 All reads are idempotent

`GET` and `POST /v1/search/studies` are read-only. Re-issuing the same request has no side effects beyond rate-limit/quota consumption. You do not need `Idempotency-Key`.

### 10.5 Monitor your empty-result rate

If your `items` array is empty on more than ~30% of calls, your filters are likely over-constrained or mis-normalized (wrong case, unsupported enum). RadiVault tracks this metric on its side (`radivault_index_search_empty_results_total`) and will reach out if we see anomalies, but the primary defense is your own dashboard.

---

## 11. Python example — plain `httpx` (no SDK required)

An official Python SDK ships in v0.2. Until then, plain `httpx` is enough. This is an illustrative skeleton, not a complete library.

```python
import os, time, httpx
from typing import Any, Iterator

BASE_URL = "https://search.radivault.io"

class RadiVaultError(Exception):
    def __init__(self, code: str, status: int, detail: str, request_id: str | None, retry_after: int | None):
        super().__init__(f"[{status} {code}] {detail} (req {request_id})")
        self.code, self.retry_after = code, retry_after

class RadiVaultClient:
    def __init__(self, api_key: str | None = None, timeout_s: float = 15.0) -> None:
        key = api_key or os.environ["RADIVAULT_KEY"]
        self._c = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            timeout=timeout_s,
        )

    def version(self) -> dict[str, Any]:
        r = self._c.get("/v1/version"); r.raise_for_status(); return r.json()

    def search(self, filt: dict[str, Any]) -> dict[str, Any]:
        r = self._c.post("/v1/search/studies", json=filt)
        if r.status_code >= 400:
            b = r.json() if r.headers.get("Content-Type", "").startswith("application/json") else {}
            raise RadiVaultError(
                code=b.get("error", "UNKNOWN"), status=r.status_code,
                detail=b.get("detail", ""), request_id=r.headers.get("X-Request-Id"),
                retry_after=int(r.headers["Retry-After"]) if "Retry-After" in r.headers else None,
            )
        return r.json()

    def iter_all(self, filt: dict[str, Any]) -> Iterator[dict[str, Any]]:
        cursor: str | None = None
        while True:
            page = self.search({**filt, "cursor": cursor} if cursor else filt)
            yield from page["items"]
            if not page.get("has_next"): return
            cursor = page["next_cursor"]

if __name__ == "__main__":
    c = RadiVaultClient()
    print(c.version())
    filt = {"modality":["MR"],"body_part":["HEAD"],"sex":["M"],"limit":100,"include_facets":False}
    n = 0
    try:
        for _ in c.iter_all(filt):
            n += 1
    except RadiVaultError as e:
        if e.code == "ERR_BUYER_QUOTA" and e.retry_after:
            time.sleep(e.retry_after)
        else:
            raise
    print(f"total: {n}")
```

---

## 12. FAQ

### Q1. Can I get raw DICOM pixel data through this API?

**No.** This API is metadata search only. Pixel data is delivered through a separate **purchase flow** (Order Orchestrator, v0.2). That flow is order-by-order, contract-governed, and follows your MSA/DPA. You identify a cohort here, then place a purchase request — pixel delivery takes up to 48 hours per [PRD §5](../prd.md).

### Q2. Why Korean data specifically?

Korea has one of the world's most PACS-saturated healthcare systems and one of the highest per-capita imaging volumes. Multiple Korean medical-imaging AI vendors have cleared FDA authorizations using data from this ecosystem — an external validation of data quality. For AI teams that need demographic and device diversity beyond US-centric corpora, Korean data is a structural advantage. See [research §4](../research/k-meddata-research-summary.md#4-왜-한국인가).

### Q3. Is this HIPAA-compliant?

RadiVault is **aligned with HIPAA Safe Harbor de-identification**. De-identification happens at the hospital Gateway before any data leaves the premises; the 18 identifier categories are removed or transformed. We do not claim HIPAA "certification" because HIPAA is a compliance framework, not a certification regime. For enterprise buyers: SOC 2 Type II is in preparation; details available in a procurement call.

### Q4. How fresh is the metadata?

Partner Gateway Agents push anonymized metadata on a daily cadence; the central index typically surfaces new studies within 24 hours of hospital ingest. `ingested_at` on each study tells you when it arrived in the central index. We do not currently offer a "changed since" feed; this is a v0.2 candidate.

### Q5. Is there a hard cap on cohort size?

**No hard cap**, but the query is cost-gated — filters that would touch more than 10M rows return `ERR_QUERY_TOO_BROAD`. Within that, your tier's daily quota caps throughput. Cohort pulls for paid purchases are negotiated separately from API quotas — talk to Sales for a 500k+ study cohort plan.

### Q6. Can I save queries?

**Not in v0.1.** Saved queries, alerts, and scheduled cohort refreshes are planned for v0.2. Today, store your canonical filter JSON in your own repo and re-run it.

---

## 13. Next steps

1. **Run through §0–§4** end-to-end. If any call fails, capture the `X-Request-Id` and email [support@radivault.io](mailto:support@radivault.io).
2. **Explore facets** (§6) against your intended cohort. Validate device mix and demographic distribution before committing engineering time.
3. **Plan a purchase flow preview** — once your cohort looks right, request a call with Sales. They walk you through the MSA/DPA, pricing, and Order Orchestrator preview (v0.2).
4. **Subscribe to changelog** — v0.2 adds saved queries, NLP-label filters, and the Python SDK. Email [buyer@radivault.io](mailto:buyer@radivault.io) to be notified.

**Support**: [support@radivault.io](mailto:support@radivault.io) — include your `X-Request-Id`, the time, and the exact request body.
**Sales (tier / purchase)**: [sales@radivault.io](mailto:sales@radivault.io).
**General**: [buyer@radivault.io](mailto:buyer@radivault.io).

---

## 14. Change history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| v0.1 | 2026-04-22 | @marketer | Initial draft. Based on metadata-index v0.1 (QA PASS with minor, 2026-04-22). API contracts anchored to [dev-spec §7](../specs/dev-spec-metadata-index.md) and [design-spec §2](../specs/design-spec-metadata-index.md). Awaiting Kyle approval. |
