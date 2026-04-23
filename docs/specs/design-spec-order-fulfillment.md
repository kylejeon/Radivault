# 디자인 명세 — Order Fulfillment v0.1 MVP (Buyer Orders · Gateway Transfer · Staged Download · Admin CLI · Observability · Runbook UX)

> **Status**: Draft v0.1 · **Feature slug**: `order-fulfillment` · **Last updated**: 2026-04-22
> **작성자**: @designer (Claude Opus 4.7) · **근거**:
> - [dev-spec-order-fulfillment](./dev-spec-order-fulfillment.md) — 본 디자인의 **유일한 source of truth** (85 FR · 40 AC · §7 API · §13 에러 · §6 데이터 모델)
> - [design-spec-central-ingest](./design-spec-central-ingest.md) — envelope · 에러 envelope · 5-field 에러 taxonomy · CLI 출력 컨벤션 · runbook 포맷을 **그대로 상속**
> - [design-spec-metadata-index](./design-spec-metadata-index.md) — buyer-facing DX (`X-RateLimit-*`·`X-Quota-*` 헤더, cursor opaque 계약, buyer onboarding) **상속**
> - [design-spec-gateway-agent](./design-spec-gateway-agent.md) — Gateway CLI 패턴, 이중 언어 메시지 정책 상속, `transfer` 서브커맨드 신규 확장 대상
> - [리서치 — Order Fulfillment 기술 기반](../research/order-fulfillment-technical-foundations.md)
> - [UI Guide](../UI_GUIDE.md) — 톤 원칙만 참조

---

## 0. 범위 선언 (Scope Statement)

본 문서는 통상의 GUI/웹 디자인 명세가 **아니다**. Order Fulfillment v0.1 은 RadiVault 의 **수익 엔진** — `radivault_fulfillment` FastAPI 서비스 (port 8002) 가 buyer-facing 주문·다운로드 API 와 Gateway-facing transfer-job long-poll API 를 동시에 호스팅한다. v0.1 범위에는 웹 UI·대시보드·포털 화면이 없다. 그러나 "API 를 쓰는 외부 개발자·운영자·세일즈 엔지니어·병원 Gateway 프로세스"가 실제로 마주하는 표면이 분명히 존재하며, 본 문서는 그 **개발자 경험(DX) · 기계 계약(M2M) · 운영자 경험(OpEx)** 을 정의한다.

**디자인 대상 표면 8종**

1. **Buyer-facing HTTP API UX (DX)** — 주문 생성·조회·취소·다운로드 URL 발급 envelope, 12-state FSM 의 플레인 영어 의미, polling 패턴, 다운로드 manifest shape(sha256 + urls[]), URL refresh 계약(24h TTL/7d 상한), rate-limit·quota 헤더, Idempotency-Key, CORS, 버전 정책. **metadata-index 의 검색 DX 를 잇는 두 번째 외부 공개 API** 이므로 영업 시연·PoC·구매자 문서에 그대로 노출된다.
2. **Gateway-facing HTTP API UX (M2M)** — long-poll 의미론(`wait=30s` / 204 timeout), claim shape, progress 주기·lease 연장, completion 의미(uploaded pseudo_sop_uids[] + central_job_ids echo), fail 의미(reason codes + DLQ), Bearer 토큰 스코프.
3. **Operator CLI (`fulfillment-admin`)** — 주문 조회/상태 추진/강제 취소, transfer-job list/requeue/DLQ dump, URL 감사, buyer 사용량 집계, 마이그레이션, 버전.
4. **Gateway CLI 확장 (`gateway-agent transfer *`)** — 기존 `gateway-agent` 바이너리에 `transfer start|status|test` 서브커맨드 3종 신규 추가 (dev-spec §14 G-1).
5. **Log & Observability 출력** — JSON 로그 schema(`radivault_fulfillment.*`), Prometheus 메트릭 네이밍(`radivault_fulfillment_*`), 알람 정의 10+.
6. **Error Taxonomy UX** — dev-spec §7.11 / §13.1 의 신규 24 개 에러 코드를 5-field 운영자 표로 렌더(code · HTTP · ko · en · when · action · doc).
7. **Runbook 산출물** — 주문 이행 특유 장애(DLQ 증가, fetching stuck, presigned URL mint 실패, sha256 mismatch 민원, 쿼터 소진 storm, Hot Storage hit 급락, mass expiration 이벤트, S3 장애) 플레이북 8편. 한국어.
8. **Onboarding Walkthroughs** — (a) buyer 측: metadata-index 의 검색 완료 → 첫 주문 → 다운로드 → URL refresh → 취소까지 10 단계, 영어 curl 샘플 포함. (b) 병원/Gateway 측: 기존 gateway-agent §7 온보딩에 `transfer` 서브시스템 활성화 단계 추가, 한국어.

**디자인 대상 아닌 것**: 구매자 포털 웹 UI (v0.2+ 별도 slug), 병원 관리 콘솔, DICOM 뷰어, 모바일 앱, 결제 UI, 썸네일 CDN, 실제 Stripe/PG 연동.

표준 design-spec 템플릿의 시각 디자인 항목은 backend 서비스 성격상 **N/A — backend service** 로 표기한다 (central-ingest · metadata-index design-spec 과 동일 패턴).

---

## 1. 사용자 (Users)

### 1.1 Primary A — 엔터프라이즈 구매자 통합 개발자

- **유형**: 의료영상 AI 기업·의료기기 회사 백엔드/데이터 엔지니어. metadata-index §1.1 과 **동일 인물** (검색하던 사람이 주문한다).
- **언어**: **영어 우선**. `message_en` 이 1차 독해 대상.
- **기술**: HTTP REST·curl·Postman·OpenAPI 3.x·httpx/boto3 숙련. S3 presigned URL parallel GET 가능.
- **목표**:
  1. metadata-index 코호트를 **단일 `POST /v1/orders`** 로 제출. 15 분 내 자동화 파이프라인 편입.
  2. `GET /v1/orders/{id}` 폴링만으로 상태 전이 관찰.
  3. per-object URL 배열 → parallel GET + sha256 검증.
  4. URL 실패 시 재mint (refresh = re-mint).
- **기대 계약**: OpenAPI 1:1 응답 shape / 상태 plain-English / `Idempotency-Key` 재전송 시 same order_id / sha256 64자 lowercase hex / ttl 이 `X-Amz-Expires` 와 일치.
- **실패 시**: 4xx → 자기 코드 수정. 5xx → 백오프. 429 → `Retry-After`. `ERR_ORDER_EXPIRED` → 같은 코호트 새 주문. URL 403/404 → 재mint.
- **금지 가정**: "presigned URL revoke 가능" · "주문 7d TTL 연장" · "URL 영구". 명시적 부정.

### 1.2 Primary B — 구매자 측 데이터 사이언티스트

- **유형**: PhD/MD. metadata-index §1.2 에서 facet 탐색하던 사람. "사기 전에 실 영상을 받아 본다".
- **언어**: **영어 우선**. 한국어 독해 불가 가정.
- **기술**: curl/jq/Postman. Python notebook `requests`+`httpx`.
- **목표**: 10 study 주문 → 다운로드 → local DICOM 뷰어. sha256 자체 검증. 파일럿 의사결정.
- **기대**: curl 3줄 이내 첫 다운로드. manifest 가 Python dict 로 바로 먹히는 shape. 에러 `detail` 에 구체 필드명.
- **그래듀에이션**: 연구자 → 통합 엔지니어(Primary A) → Python SDK v0.2.

### 1.3 Primary C — Gateway Agent 프로세스 (기계)

- **유형**: 무인 클라이언트. 병원 on-premise Docker Compose. Flow A (central-ingest) + Flow B (transfer consumer) 병렬.
- **언어**: N/A. `message_en` 로그, `message_ko` audit.log 보조.
- **기대**: `GET /v1/gateway/transfer-jobs?wait=30s` — 204 정상, 200 OK 시 15 분 lease / `POST /progress` lease 절반 주기 / `POST /complete` manifest+central_job_ids[] echo / `POST /fail` retryable 로 재큐 vs DLQ.
- **실패 시**: 4xx 자체 로그 (에스컬레이션 금지). 5xx 백오프. 403 lease ownership → job 포기.
- **제약**: Flow A 에 영향 없이 병렬. 기존 De-ID + ingest 파이프라인 재사용. `transfer.enabled=false` 기본값 존중.

### 1.4 Primary D — RadiVault SRE (한국어)

- **언어**: 한국어/영어 혼용 (runbook·에스컬레이션 한국어, CLI 영어).
- **기술**: Linux/Docker/PG/Redis/S3 숙련. central-ingest · metadata-index §1.2 **동일 인물** — 이제 세 서비스 운영.
- **목표**: `/readyz`·`/metrics` 자동 모니터 / DLQ·stuck·mint 실패·mass expiration 알람에 15 분 1st response / `fulfillment-admin` 으로 강제 추진·force-cancel·DLQ 재큐.
- **반드시**: `fulfillment-admin` CLI, Alembic 0004, runbook 8편, 알람 응답, unlinked_study 수동 재할당.

### 1.5 Primary E — RadiVault 세일즈 엔지니어 (영어 우선)

- **언어**: 한국어·영어. 프로스펙트 영어, 내부 한국어.
- **기술**: curl/Postman/httpx.
- **목표**: 데모 "10건 주문 → 2분 후 다운로드" 시연 / 404·409·422 에러를 엔지니어 없이 1차 응대 / preview → paid 전환 타이밍 포착 (`stats buyer-usage`).
- **기대**: §9 Onboarding 이 그대로 영업 플레이북. 에러 메시지 한 줄이 fix 지침.

### 1.6 Secondary — finance / 운영 (future billing readiness)

- v0.1 은 `pending_billing` 스텁만. `order.total_estimated_usd` · `download_event.bytes_transferred` (v0.1.1 ETL) 가 "나중에 집계 가능하게 축적" 되는지 보장. **본 디자인은 billing UI 를 정의하지 않는다**.

### 1.7 Non-user

- 환자·의료진·방사선사 접근 불가. 한국 국내 buyer 는 v0.1 파일럿 타겟 아님 — 한국어 buyer onboarding 은 v0.2.

---

## 2. Buyer-facing HTTP API UX — 핵심 DX

본 섹션은 RadiVault 의 **두 번째 외부 공개 HTTP API** (metadata-index 다음) 이므로 envelope·rate-limit·CORS·버전 정책은 metadata-index design-spec 을 **그대로 상속**하고, 주문/다운로드 도메인 고유의 DX 만 이 섹션에서 정의한다.

### 2.1 응답 Envelope 원칙 (OpenAPI 옵션 B — central-ingest · metadata-index 와 동일)

| 옵션 | 성공 바디 | 실패 바디 | 비고 |
|------|-----------|-----------|------|
| A. `{ok, data?, error?}` | `{"ok":true,"data":{...}}` | `{"ok":false,"error":{...}}` | **기각** — central-ingest · metadata-index 충돌 |
| **B. OpenAPI 스타일 (채택)** | `{...}` 직접 | `{"error":"<code>","detail":"<en>","message_ko":"<ko>","message_en":"<en>","request_id":"...","doc_url":"...","hint":"...","retry_after":null}` | dev-spec §7, central-ingest §2.1, metadata-index §2.1 과 100% 일치 |

**재확인**: 본 API 는 central-ingest design-spec §2.2 의 **7-field (5 필수 + 2 optional)** envelope 을 **비변경 승계**한다. 본 문서에서는 재정의하지 않고 **참조**한다. `order-fulfillment` 도메인 고유 실패 예시 5종은 §2.8 에서 풀어낸다.

### 2.2 주문 생성 UX — `POST /v1/orders` 요청/응답 annotated

RadiVault 의 **매출 파이프라인 진입점**. Buyer 가 metadata-index 에서 얻은 `pseudo_study_uid[]` 를 한 번에 주문 제출한다.

**요청 예시 (두 경로 — 명시적 uid vs 저장된 필터; 후자는 v0.1.1 deferred)**

```jsonc
// (A) v0.1 canonical — 명시적 pseudo_study_uid[]
POST /v1/orders HTTP/1.1
Host: fulfillment.radivault.io
Authorization: Bearer rv_live_abcd1234_Zj8f2vX9qK2sLpN4mQbW7yR1eT5aU6c
Idempotency-Key: 01HXXORDER1ABCDEF234567890       // ULID, same key → same order_id
Content-Type: application/json

{
  "pseudo_study_uids": [                            // required, 1..10000 (tier cap)
    "2.25.140737488355328.1.2.3",
    "2.25.140737488355328.1.2.4",
    "2.25.140737488355328.1.2.5"
  ],
  "agreement_hash": "abcd1234...abcdef",            // required, sha256 of signed MSA body
  "notes": "pilot cohort batch 3",                  // optional, ≤512 chars
  "preferred_download_ttl_hours": 48                // optional, tier cap (preview=24, paid=168)
}

// (B) v0.1.1 deferred — saved cohort filter
// "saved_filter_id": "fil_01HX..." — v0.1 returns 501 ERR_ORDER_NOT_IMPLEMENTED (see §14 Q1).
```

**성공 응답 — `202 Accepted`**

```jsonc
HTTP/1.1 202 Accepted
Content-Type: application/json
X-Request-Id: 01HXXORDER1SERVER
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-Quota-Limit-Daily: 50
X-Quota-Remaining-Daily: 49
X-Quota-Reset-Daily: 1713830400
Idempotency-Replayed: false                    // true on replay (same key+body)

{
  "order_id":             "ord_01HXXORDER1ABCDEF",  // ULID, stable
  "state":                "queued",                  // §2.3 FSM
  "state_billing":        "pending_billing",         // v0.1 constant
  "n_studies":            3,
  "total_bytes":          282963036,
  "total_estimated_usd":  15.0,                      // n_studies × tier.unit_price_usd
  "tier":                 "paid",
  "path_type":            null,                      // hot|cold|mixed, set by orchestrator
  "submitted_at":         "2026-04-22T10:00:00Z",
  "estimated_ready_at":   "2026-04-22T10:00:30Z",    // hot×0.5s + cold×36s
  "ready_at":             null,                      // set at ready_for_download
  "expires_at":           null,                      // set at ready (ready + 7d)
  "cancelled_at":         null,
  "progress":             0.0,                       // 0..1
  "eta_seconds":          30,
  "items":                [],                        // populated in GET /{id}
  "transfer_jobs":        [],
  "last_error":           null
}
```

**설계 포인트**: **`202` (not 201)** — 비동기 이행. `estimated_ready_at` = `hot×0.5s + cold×36s` (단순 기대값, 상한/하한 아님). `progress: 0.0` POST 에서는 항상 0. `Idempotency-Replayed` false 기본; 재전송 시 true + 원 응답 바이트 복제 (central-ingest §2.4 계승).

### 2.3 주문 상태 의미론 — 12-state plain-English

Buyer 가 `GET /v1/orders/{id}.state` 에서 보는 값. **숫자 아닌 문자열 enum**. 각 상태의 "의미" · "얼마나 걸리나" · "다음에 뭐가 있나" 를 buyer 가 한 눈에 이해할 수 있어야 한다.

| State | plain-English meaning | Typical duration | Next state |
|-------|----------------------|------------------|------------|
| `draft` | Not used in v0.1 (submitted via `POST /v1/orders` directly). Reserved. | — | `submitted` |
| `submitted` | We received your request and are about to validate it. | < 1s | `validating` |
| `validating` | Checking scope, tier caps, quota, UID existence, size cap. | < 2s | `validated` / HTTP 4xx |
| `validated` | Passed validation. Queuing transfer jobs. | < 1s | `queued` |
| `queued` | **You're in line.** Hot-path copies immediately; cold-path awaits hospital pull. | < 10s | `fetching` |
| `fetching` | **Hospital gateway is pulling** images, de-identifying, uploading. | hot: seconds. cold: ~1h for 100 studies. | `staging_partial` / `staging_complete` |
| `staging_partial` | Some studies arrived; others in transit. | Minutes | `staging_complete` |
| `staging_complete` | All studies arrived. Copying into your private download area. | < 30s S3 copy | `ready_for_download` |
| `ready_for_download` | **You can download.** Call `POST /download-urls`. | 7 days window | `delivering` / `expired` |
| `delivering` | First URL minted (v0.1 unused; reserved for analytics). | N/A | `delivered` / `expired` |
| `delivered` | All files downloaded (v0.1 not auto-triggered; ETL is v0.1.1). | terminal | — |
| `expired` | 7-day window ended. Place a new order to re-download. | terminal | — |
| `cancelled` | You or admin cancelled. | terminal | — |
| `failed` | Server-side failure. Check `last_error`. Contact support. | terminal | — |

**ASCII state diagram (embedded in OpenAPI description)**

```
                 ┌─────────────┐
                 │   submitted │
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │ validating  │──────────► HTTP 4xx (no DB row)
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │  validated  │
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐ ───► cancelled (buyer)
                 │   queued    │
                 └──────┬──────┘
                        ▼
                 ┌─────────────┐
                 │  fetching   │ ───► cancelled (admin), failed (5 retries)
                 └──────┬──────┘
                        ▼
           ┌─────────────┴─────────────┐
           ▼                           ▼
   ┌───────────────┐           ┌───────────────┐
   │staging_partial│──────────►│staging_complete│
   └───────────────┘           └───────┬───────┘
                                       ▼
                              ┌──────────────────┐
                              │ready_for_download│ ───► expired (timer), cancelled (admin)
                              └────────┬─────────┘
                                       ▼
                              ┌──────────────────┐
                              │   delivering     │ (v0.1 unused)
                              └────────┬─────────┘
                                       ▼
                              ┌──────────────────┐
                              │    delivered     │ (terminal)
                              └──────────────────┘
```

### 2.4 Polling 패턴 — 구매자가 실제로 쓰는 curl 루프

```bash
# buyer script — poll until ready or cancel
ORDER_ID="ord_01HXXORDER1ABCDEF"
while true; do
  RESP=$(curl -sS -H "Authorization: Bearer $RV_KEY" \
         https://fulfillment.radivault.io/v1/orders/$ORDER_ID)
  STATE=$(echo "$RESP" | jq -r .state)
  PROGRESS=$(echo "$RESP" | jq -r .progress)
  echo "$(date -u +%H:%M:%S)  state=$STATE  progress=$PROGRESS"
  case "$STATE" in
    ready_for_download) echo "ready — minting URLs"; break ;;
    expired|cancelled|failed) echo "terminal state: $STATE"; exit 1 ;;
    *) sleep 5 ;;     # recommended polling interval: 5s (server supports up to 1 req/s on GET)
  esac
done
```

**권장 폴링 주기 (공식 문서 플랭크)**:

- `queued|validating|validated` 상태에서 **≥ 2s** 간격.
- `fetching|staging_*` 상태에서 **≥ 5s** 간격.
- `ready_for_download|expired|cancelled|failed` 도달 시 **즉시 중단**.
- 1 req/s 초과 폴링은 `429 ERR_RATE_LIMITED` 가능 — Retry-After 준수.

### 2.5 다운로드 URL UX — `POST /v1/orders/{id}/download-urls` response + parallel GET 샘플

Buyer 가 가장 자주 쓰는 엔드포인트. per-object manifest + sha256 + presigned URL 을 **한 번에** 반환. buyer 는 이 응답을 바로 parallel downloader 에 투입한다.

**응답 shape**

```jsonc
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-Id: 01HXXMINT1SERVER
X-RateLimit-Remaining: 58
Cache-Control: private, no-store                // MUST NOT be cached by proxies

{
  "order_id":    "ord_01HXXORDER1ABCDEF",
  "ttl_seconds": 86400,                          // echoed or tier default
  "expires_at":  "2026-04-23T10:00:00Z",         // when these URLs stop
  "minted_at":   "2026-04-22T10:00:00Z",
  "items": [
    {
      "pseudo_study_uid": "2.25.140737488355328.1.2.3",
      "files": [
        { "object_key": "staging/ord_01HXX.../2.25.zzzz1.dcm",
          "bytes":      513222,
          "sha256":     "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
          "url":        "https://s3.ap-northeast-2.amazonaws.com/.../2.25.zzzz1.dcm?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Expires=86400&X-Amz-Signature=...&response-content-disposition=attachment%3B%20filename%3D%222.25.zzzz1.dcm%22" }
        /* ...one entry per DICOM instance... */
      ]
    }
    /* ...more items per order... */
  ],
  "total_bytes": 188642024,
  "n_files":     512
}
```

**Buyer code sample — curl + httpx parallel download with integrity check**

```bash
# (1) curl — serial, one file at a time (simple but slow)
jq -r '.items[].files[] | "\(.url) \(.sha256) \(.object_key|split("/")|last)"' manifest.json | \
while read url expected_sha filename; do
  curl -sS -o "dicoms/$filename" "$url"
  actual_sha=$(sha256sum "dicoms/$filename" | awk '{print $1}')
  [ "$actual_sha" != "$expected_sha" ] && { echo "mismatch $filename"; rm "dicoms/$filename"; }
done
```

```python
# (2) httpx parallel download + sha256 verification (recommended)
import asyncio, hashlib, httpx, json, pathlib

async def fetch(client, url, path, expected_sha):
    r = await client.get(url); r.raise_for_status()
    if hashlib.sha256(r.content).hexdigest() != expected_sha:
        raise ValueError(f"sha256 mismatch: {path.name}")
    path.write_bytes(r.content)

async def download_all(manifest, out_dir, concurrency=16):
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(timeout=300.0) as c:
        async def bound(u, s, p):
            async with sem: await fetch(c, u, p, s)
        await asyncio.gather(*[
            bound(f["url"], f["sha256"], out_dir / pathlib.Path(f["object_key"]).name)
            for item in manifest["items"] for f in item["files"]
        ])

asyncio.run(download_all(json.load(open("manifest.json")),
                         pathlib.Path("./dicoms")))
```

**설계 포인트**: `url` 은 완전 HTTPS (쿼리 포함, buyer 조작 금지). `sha256` 64자 lowercase hex (prefix 없음). `object_key` 는 파일명 추출용 — **원본 UID/병원명/PHI 없음** (dev-spec §6.7). `Cache-Control: private, no-store` — 중간 proxy 캐싱 방지.

### 2.6 URL Refresh 계약 — 24h TTL + re-mint (revocation 불가)

**핵심 사실 (문서화 plank)**: AWS S3 presigned URL 은 **서명 후 revoke 불가**. 따라서 RadiVault 는 "revocation" 을 "짧은 TTL + on-demand re-mint" 로 대체한다.

| 항목 | 값 / 정책 |
|------|-----------|
| **기본 TTL** | 24 hours (`86400` seconds) |
| **최소 TTL** | 1 hour (`3600`) — 더 짧게 달라는 요청은 `422 ERR_URL_TTL_EXCEEDED` 아닌 `clamped to 3600`? → v0.1 은 **400 ERR_REQUEST_SCHEMA** (`ttl_seconds < 3600`) |
| **최대 TTL** | tier별: preview=24h, paid=7d (604800). AWS S3 SigV4 `X-Amz-Expires` 7d 상한. |
| **초과 요청** | `422 ERR_URL_TTL_EXCEEDED` — 응답 `hint` 에 tier cap 명시 |
| **Refresh 방법** | 같은 엔드포인트 `POST /v1/orders/{id}/download-urls` 를 **재호출** (별도 `/refresh` 경로 없음). 매번 새 서명, 새 `minted_at`, 새 sha256 은 동일 (파일 내용 불변). |
| **이전 URL 의 운명** | 이전 서명은 **서명 TTL 까지 계속 유효**. 회수 불가. 7d 파기가 필요하면 S3 KMS 키 로테이션 (RB-OF-3) 또는 버킷 정책 임시 deny. |
| **주문 만료 (7d) 도달 후** | `POST /download-urls` → `410 ERR_ORDER_EXPIRED`. 이미 발급된 URL 은 **자체 TTL 까지 여전히 유효** (buyer 가 download 중이라면 끝까지). 단 8d 후 S3 Lifecycle rule 이 staging/ 객체를 삭제하므로 실질 최대 기한은 `order.expires_at + 1d` |
| **URL Rate-limit** | per-buyer 1 req / 5s, burst 10 (dev-spec FR-67). 초과 → `429 ERR_URL_MINT_RATE`. |

**문서화 문구 (buyer mental model)**:

> "Download URLs are like **short-lived concert tickets** — they scan at the gate until they expire. We cannot un-print a ticket once you hold it. So we print them with short expiry and you come back for new ones. If you lose a ticket (or your download fails), just ask for another batch. Your order itself remains valid for 7 days — plenty of time to re-mint as many URL batches as you need."

### 2.7 취소 UX — state-gated cancellation

```
POST /v1/orders/ord_01HXX.../cancel HTTP/1.1
Authorization: Bearer rv_live_...
Content-Type: application/json

{"reason": "changed cohort; will resubmit"}        // optional
```

| Current state | Buyer cancel allowed? | Response |
|---------------|----------------------|----------|
| `submitted`·`validating`·`validated`·`queued` | **Yes** | `200 OK` + `state=cancelled`. Any `queued` transfer_job is also cancelled (no DB garbage). |
| `fetching`·`staging_partial`·`staging_complete` | **No — admin only** | `409 ERR_ORDER_STATE_TRANSITION`, `hint: "Cancellation during fetch requires admin intervention. Contact support@radivault.io with your order_id. Studies already uploaded may be retained as unlinked and offered in future orders."` |
| `ready_for_download`·`delivering` | **No — admin only** | `409 ERR_ORDER_STATE_TRANSITION`, `hint: "Ready orders cannot be cancelled by buyer; contact support for refund review."` (v0.1 no refund; field `refund_eligible: false` constant) |
| `expired`·`cancelled`·`delivered`·`failed` | **No — terminal** | `409 ERR_ORDER_STATE_TRANSITION` (idempotent 멱등 정보 반환 without mutating) |

**성공 응답 shape**

```jsonc
HTTP/1.1 200 OK
{
  "order_id":        "ord_01HXX...",
  "state":           "cancelled",
  "cancelled_at":    "2026-04-22T10:03:00Z",
  "refund_eligible": false                   // v0.1 constant
}
```

### 2.8 에러 shape 실제 예시 5종 (buyer 가 실제로 만나는 상위 5)

각 예시는 OpenAPI `examples:` 에 등재 → Swagger UI "Try it out" 우측 표시.

**(a) 403 `ERR_ORDER_SCOPE_FORBIDDEN` — buyer scope 위반 (hospital 제외목록 교차)**

```
HTTP/1.1 403 Forbidden
X-Request-Id: 01HXXSCOPE1...
Content-Type: application/json

{
  "error":       "ERR_ORDER_SCOPE_FORBIDDEN",
  "detail":      "cohort includes 2 hospitals excluded by your key scope",
  "message_ko":  "요청하신 코호트에 스코프상 제외된 병원(2곳)이 포함되어 있습니다.",
  "message_en":  "Your cohort includes 2 hospitals excluded from your API key scope. Narrow your pseudo_study_uids or contact sales to expand your scope.",
  "request_id":  "01HXXSCOPE1...",
  "doc_url":     "https://docs.radivault.io/fulfillment/errors/ERR_ORDER_SCOPE_FORBIDDEN",
  "hint":        "Use metadata-index /v1/search/facets with your key to see allowed hospitals.",
  "retry_after": null,
  "extra": {
    "excluded_hospital_count": 2,
    "sales_contact":           "sales@radivault.io"
  }
}
```

**(b) 422 `ERR_ORDER_TIER_EXCEEDED` — 코호트 크기 tier 상한 초과**

```
HTTP/1.1 422 Unprocessable Entity
{
  "error":       "ERR_ORDER_TIER_EXCEEDED",
  "detail":      "cohort size 120 exceeds preview tier cap 50",
  "message_ko":  "프리뷰 티어는 한 주문당 최대 50건까지만 지원합니다 (요청 120건).",
  "message_en":  "The preview tier allows up to 50 studies per order; your request has 120. Split into multiple orders or upgrade to paid (10,000 per order).",
  "request_id":  "01HXXTIER1...",
  "doc_url":     "https://docs.radivault.io/fulfillment/errors/ERR_ORDER_TIER_EXCEEDED",
  "hint":        "Upgrade: contact sales@radivault.io. Paid tier = 10,000 studies/order.",
  "retry_after": null,
  "extra": {
    "tier":             "preview",
    "cohort_size":      120,
    "tier_cap":         50,
    "paid_tier_cap":    10000,
    "upgrade_contact":  "sales@radivault.io"
  }
}
```

**(c) 409 `ERR_ORDER_STATE_TRANSITION` — 주문 FSM 이 현재 상태에서 요청을 받지 못함**

```
HTTP/1.1 409 Conflict
{
  "error":       "ERR_ORDER_STATE_TRANSITION",
  "detail":      "cannot cancel order in state=fetching",
  "message_ko":  "fetching 상태의 주문은 구매자가 직접 취소할 수 없습니다. 지원팀에 문의하세요.",
  "message_en":  "Orders in 'fetching' state cannot be cancelled by the buyer. Contact support@radivault.io with your order_id. Studies already uploaded may be retained as unlinked and offered in future orders.",
  "request_id":  "01HXXSTATE1...",
  "doc_url":     "https://docs.radivault.io/fulfillment/errors/ERR_ORDER_STATE_TRANSITION",
  "hint":        "Only admin force-cancel is allowed after fetching begins. We respond to support tickets within 1 business day.",
  "retry_after": null,
  "extra": {
    "current_state":              "fetching",
    "allowed_buyer_cancel_states": ["submitted","validating","validated","queued"],
    "support_contact":             "support@radivault.io"
  }
}
```

**(d) 410 `ERR_ORDER_EXPIRED` — 주문 만료 후 URL mint 시도**

```
HTTP/1.1 410 Gone
{
  "error":       "ERR_ORDER_EXPIRED",
  "detail":      "order expired at 2026-04-29T10:00:00Z (now 2026-04-30T05:12:45Z)",
  "message_ko":  "주문이 만료되었습니다 (2026-04-29T10:00:00Z). 동일 코호트로 새 주문을 생성하세요.",
  "message_en":  "This order expired at 2026-04-29T10:00:00Z. To download the same cohort again, submit a new order with the same pseudo_study_uids.",
  "request_id":  "01HXXEXPD1...",
  "doc_url":     "https://docs.radivault.io/fulfillment/errors/ERR_ORDER_EXPIRED",
  "hint":        "Orders remain downloadable for 7 days after ready_for_download. Store downloads to your own storage promptly.",
  "retry_after": null,
  "extra": {
    "expired_at":    "2026-04-29T10:00:00Z",
    "window_days":   7
  }
}
```

**(e) 502 `ERR_URL_MINT_FAILED` — boto3/S3/KMS 일시 장애**

```
HTTP/1.1 502 Bad Gateway
{
  "error":       "ERR_URL_MINT_FAILED",
  "detail":      "boto3 presign failed: KmsKeyDisabledException",
  "message_ko":  "다운로드 URL 서명에 실패했습니다. 잠시 후 다시 시도해주세요.",
  "message_en":  "Failed to sign download URLs due to a temporary S3/KMS issue. Please retry in 30 seconds.",
  "request_id":  "01HXXMINT1...",
  "doc_url":     "https://docs.radivault.io/fulfillment/errors/ERR_URL_MINT_FAILED",
  "hint":        "This is a transient server-side issue; no buyer action required beyond retry.",
  "retry_after": 30,
  "extra": {
    "downstream": "s3-kms",
    "op":         "generate_presigned_url"
  }
}
```

### 2.9 Rate-limit + Quota 헤더 계약 (metadata-index §2.7 재사용)

**모든 성공 응답 + 429 에** 다음 헤더 세트 포함 (metadata-index §2.7 과 동일, scope 만 fulfillment-specific):

| 헤더 | 값 타입 | 의미 |
|------|---------|------|
| `X-RateLimit-Limit` | integer | 현재 per-minute 한도 (기본 60 rpm) |
| `X-RateLimit-Remaining` | integer | 남은 per-minute 요청 수 |
| `X-RateLimit-Reset` | integer (Unix epoch) | 다음 per-minute window boundary |
| `X-Quota-Limit-Daily` | integer | **일일 주문 쿼터** (preview=5, paid=50) — **주문 생성 전용**. GET 류는 rate-limit 만 적용. |
| `X-Quota-Remaining-Daily` | integer | 남은 일일 주문 수 |
| `X-Quota-Reset-Daily` | integer (Unix epoch) | 다음 UTC 자정 |
| `Retry-After` | integer (seconds) | 429 전용. `retry_after` body 필드와 반드시 일치 |
| `X-Request-Id` | ULID | 서버 생성, 모든 응답 |
| `Idempotency-Replayed` | `true`\|`false` | POST /v1/orders 전용 — replay 시 `true` |

**쿼터 vs rate-limit 분리 설계**: metadata-index 에서는 "검색 요청 수" 가 단일 차원이었으나 본 서비스는 **주문 생성 (무거움, 쿼터)** vs **주문 조회 (가벼움, rate-limit only)** 를 구분.

- `POST /v1/orders` → rate-limit + daily order quota 양쪽 적용.
- `GET /v1/orders[/{id}]`, `POST /download-urls`, `POST /cancel` → rate-limit 만 적용 (주문 수량에 영향 없음).
- `POST /download-urls` 는 추가로 URL mint 전용 rate-limit (1 req/5s, burst 10; FR-67).

### 2.10 Idempotency — `POST /v1/orders` 전용 계약

metadata-index 는 "검색은 본질적으로 멱등" 이라 idempotency-key 미사용. 본 서비스의 **`POST /v1/orders` 는 state-mutating** 이므로 central-ingest §2.4 idempotency 계약을 **그대로 상속**한다.

| 규칙 | 값 |
|------|-----|
| **필수 여부** | `POST /v1/orders`, `POST /cancel`, `POST /progress`, `POST /complete`, `POST /fail` 모두 **필수** — 미제공 시 `400 ERR_IDEMP_MISSING` |
| **형식** | 16–128자, `[A-Za-z0-9_.-]`. 위반 시 `400 ERR_IDEMP_FORMAT` |
| **권장 생성** | client ULID (26자) |
| **네임스페이스** | `(key, buyer_pk)` 또는 `(key, hospital_pk)` — buyer/gateway plane 별 분리 |
| **TTL** | Redis 24h; `order_idempotency_mirror` DB 7d (dev-spec FR-10) |
| **Replay 헤더** | 동일 key+payload → `Idempotency-Replayed: true` + 원 응답 바이트 복제 + `X-Original-Request-Id` 추가 |
| **Mismatch** | 동일 key + 다른 payload sha256 → **409 `ERR_IDEMP_MISMATCH`** (central-ingest design-spec §2.4 신규 코드 재사용) |
| **Redis 장애** | `503 ERR_IDEMP_UNAVAILABLE` — fail-closed, 무결성 우선 |

**`POST /v1/orders` 전용 추가 계약**: 같은 `(buyer_pk, Idempotency-Key)` 재수신 시 **절대 동일 `order_id` 반환**, 절대 두 번째 `order` row 를 만들지 않는다. 이는 FR-10 의 강제 계약으로, buyer 가 네트워크 타임아웃 상황에서 안전하게 재시도할 수 있게 한다.

**문서화 문구 (buyer mental model)**:

> "Think of `Idempotency-Key` as a **check number** you write on a money order. Submit the same check twice and the bank gives you back the original receipt — no double withdrawal. If we receive the same key with a different body, that's a bug on your side and we reject with 409. Generate a fresh ULID for every new order you actually intend."

### 2.11 Content-Type 규칙

| 엔드포인트 | Request | Response | 비고 |
|-----------|---------|----------|------|
| `POST /v1/orders` · `/cancel` · `/download-urls` | `application/json` 필수 | `application/json` | 그 외 → `415 ERR_UNSUPPORTED_MEDIA` |
| `GET /v1/orders` · `/v1/orders/{id}` | — | `application/json` | |
| `GET /v1/gateway/transfer-jobs?wait=30s` | — | `application/json` (200) or empty (204) | |
| `POST /v1/gateway/transfer-jobs/{id}/progress` · `/complete` · `/fail` | `application/json` | `application/json` | |
| `GET /healthz`·`/readyz`·`/v1/version` | — | `application/json` | 인증 불필요 |
| `GET /metrics` | — | `text/plain; version=0.0.4` | Prometheus scrape |

**`Accept`**: 없음 또는 `*/*`·`application/json` → JSON. 그 외 → `406 ERR_NOT_ACCEPTABLE` (central-ingest §2.7 재사용).

### 2.12 CORS 정책 (metadata-index §2.9 와 동일 — 기본 deny + 명시적 allowlist)

**v0.1 기본값**: CORS 미활성. Buyer 의 모든 호출은 서버사이드(curl/Python/Node 백엔드) 에서. Browser 직접 호출 불허 (API key JS 노출 리스크).

```yaml
# fulfillment.yml
cors:
  enabled: false
  allowed_origins: []
  allowed_methods: ["GET","POST"]
  allowed_headers: ["Authorization","Content-Type","X-Request-Id","Idempotency-Key"]
  exposed_headers:
    - "X-Request-Id"
    - "X-RateLimit-Limit"
    - "X-RateLimit-Remaining"
    - "X-RateLimit-Reset"
    - "X-Quota-Limit-Daily"
    - "X-Quota-Remaining-Daily"
    - "X-Quota-Reset-Daily"
    - "Retry-After"
    - "Idempotency-Replayed"
  allow_credentials: false
  max_age_seconds: 600
```

### 2.13 API 버전 정책 (metadata-index §2.10 계승)

| 원칙 | 정책 |
|------|------|
| **URL 버전** | 모든 엔드포인트 `/v1/` prefix |
| **Breaking 정의** | 필드 삭제 / 타입 변경 / 에러 코드 의미 변경 / 기본값 변경 → `/v2/` 만 노출 |
| **Non-breaking 추가** | 필드 추가(옵셔널) / 새 엔드포인트 / 새 에러 코드 → `/v1/` 내 가능 |
| **Deprecation 헤더** | `Deprecation: <GMT-date>` + `Link: <...>; rel="deprecation"` 6개월 이상 선행 |
| **Sunset** | RFC 8594 `Sunset: <date>` |
| **`/v1/version.api_contract_version`** | breaking 시 bump |

---

## 3. Gateway-facing HTTP API UX — M2M 계약

본 섹션은 **기계 대 기계 계약** 이므로 `message_ko` 보다 `detail`·`error` 코드의 결정론적 분기가 우선. 그러나 Gateway 로그에는 bilingual 메시지가 나가도록 envelope 는 §2.1 그대로.

### 3.1 Long-poll 의미론 — `GET /v1/gateway/transfer-jobs?wait=30s`

Gateway 가 병원 내부에서 outbound-only 로 호출. 방화벽 inbound 포트 개방 불필요 — RadiVault 의 **핵심 채택 결정** (리서치 §6 item 1).

| 시나리오 | Gateway 가 받는 것 |
|----------|-------------------|
| **Queue 에 claimable job 있음** | `200 OK` + `TransferJobClaim` body + 15 분 lease 확보됨 |
| **Queue 비어있고 wait 초 내 새 job 없음** | `204 No Content` + `Retry-After: 0` — Gateway 는 즉시 다시 long-poll |
| **Queue 비어있다가 wait 중 새 job 발생** | Redis pub/sub 으로 즉시 200 OK (< 100ms 지연) |
| **인증 실패** | `401 ERR_AUTH_MISSING` / `401 ERR_AUTH_EXPIRED` / `401 ERR_AUTH_WRONG_PLANE` (buyer token 오용) |
| **SQL 레이스 — 다른 replica 가 먼저 claim** | `SKIP LOCKED` 로 내부 처리, 해당 gateway 는 다음 row 로 자동 이동 |
| **DB 장애** | `503 ERR_DB_UNAVAILABLE` + `Retry-After: 5` |

**Claim 상세 body shape** (dev-spec §7.6 재확인):

```jsonc
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-Id: 01HXXCLAIM1...

{
  "transfer_job_id":          "tj_01HXXTJ1ABCDEF",
  "order_id":                 "ord_01HXXORDER1ABCDEF",
  "hospital_id":              "hosp_abc",
  "studies": [
    {"pseudo_study_uid":"2.25.140737488355328.1.2.3","expected_instances":184,"priority":1},
    {"pseudo_study_uid":"2.25.140737488355328.1.2.4","expected_instances":82,"priority":1}
  ],
  "lease_expires_at":          "2026-04-22T10:15:00Z",   // 15 min from claim
  "ruleset_version_required":  "v0.1.0",                   // Gateway must match
  "salt_version_required":     1,
  "cancel_requested":          false                        // becomes true if buyer cancelled during fetch
}
```

**Long-poll 클라이언트 구현 요령 (공식 plank, Gateway dev-spec §4.7 재확인)**:

- `wait` 기본 30s, max 60s (ALB idle timeout 배려).
- HTTP/2 keep-alive 필수.
- `wait=0` 은 즉시 return (non-blocking poll) — 기동 초기 warmup 용.
- 네트워크 중단 시 Gateway 는 **자체 지수 백오프** — 5s→10s→30s→60s→60s.

### 3.2 Progress UX — 얼마나 자주, 어떤 카운터

**권장 주기**: `progress_report_interval_seconds=60` (gateway.yml §6.6). lease 15 분 중 최소 3회 갱신 — reaper 에 잡히지 않기 위한 안전 margin.

**요청 body (ProgressReport)**:

```jsonc
POST /v1/gateway/transfer-jobs/tj_01HXXTJ1ABCDEF/progress HTTP/1.1
Authorization: Bearer <hospital auth_token>
Idempotency-Key: 01HXXPROG1GATEWAY...
Content-Type: application/json

{
  "n_fetched":   120,            // cumulative, monotonic — MUST NOT decrease
  "n_deided":    118,
  "n_uploaded":  110,
  "lease_extend": true           // extend lease by +15 min
}
```

**응답**:

```jsonc
HTTP/1.1 200 OK
{
  "lease_expires_at":  "2026-04-22T10:30:00Z",
  "cancel_requested":  false                    // Gateway가 이 값이 true 면 abort 선택
}
```

**카운터 규칙**:

- `n_fetched` ≤ 병원 PACS 에서 받은 instance 수 누계.
- `n_deided` ≤ `n_fetched` (de-ID 완료).
- `n_uploaded` ≤ `n_deided` (central-ingest 업로드 완료).
- **monotonic 증가만 허용** — 감소 시 `400 ERR_JOB_COUNTER_REGRESS` (버그 시그널).

**Lease 연장 의미론**: `lease_extend: true` → 서버가 `lease_expires_at = now() + 15m`. **Gateway 가 lease_extend 없이 침묵하면 reaper 가 15 분 후 re-queue** (FR-57).

### 3.3 Completion UX — 무엇을 echo 해야 하나

```jsonc
POST /v1/gateway/transfer-jobs/tj_01HXXTJ1ABCDEF/complete HTTP/1.1
Authorization: Bearer <hospital auth_token>
Idempotency-Key: 01HXXCOMP1GATEWAY...
Content-Type: application/json

{
  "manifest": [
    {
      "pseudo_study_uid": "2.25.140737488355328.1.2.3",
      "n_instances":      184,
      "total_bytes":      94321012,
      "status":           "uploaded",                       // "uploaded"|"skipped"|"quarantined"
      "central_job_ids":  ["ingest_01HXXCEN1","ingest_01HXXCEN2"]    // echoed from /v1/ingest/studies responses
    },
    {
      "pseudo_study_uid": "2.25.140737488355328.1.2.4",
      "n_instances":      82,
      "total_bytes":      41002912,
      "status":           "quarantined",
      "central_job_ids":  []
    }
  ],
  "audit_ref": {
    "seq":  22345,
    "hash": "sha256:c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4"
  }
}
```

**필수 포함**:

- `manifest[].pseudo_study_uid` — claim 의 `studies[].pseudo_study_uid` 와 1:1 매칭 (불일치 → `400 ERR_JOB_MANIFEST_MISMATCH`).
- `manifest[].status` — 3-state enum. `quarantined` 는 BurnedIn 등 de-ID 필터로 막힌 경우 (전체 주문은 `failed` 로 이행).
- `manifest[].central_job_ids[]` — Gateway 가 `/v1/ingest/studies` 업로드 응답에서 받은 `central_job_id` 를 그대로 echo. audit 추적용 (dev-spec §14 C-3).

**응답**:

```jsonc
HTTP/1.1 200 OK
{
  "transfer_job_id": "tj_01HXXTJ1ABCDEF",
  "state":           "completed",
  "order_state":     "staging_complete"   // or "staging_partial" if multi-hospital order
}
```

### 3.4 Failure 의미론 — reason codes + DLQ

```jsonc
POST /v1/gateway/transfer-jobs/tj_01HXXTJ1ABCDEF/fail HTTP/1.1
Authorization: Bearer <hospital auth_token>
Idempotency-Key: 01HXXFAIL1GATEWAY...

{
  "reason_code": "PACS_UNAVAILABLE",
  "details":     "connection timeout to pacs.hospital.local after 3 retries (5xx sustained 90s)",
  "retryable":   true                           // true → requeue, false → DLQ immediately
}
```

**Reason codes** (dev-spec §7.9):

| Code | 의미 | 기본 `retryable` |
|------|------|-----------------|
| `PACS_UNAVAILABLE` | 병원 PACS 응답 없음/5xx | `true` (재시도 후 회복 가능) |
| `DEID_FAILED` | De-ID 엔진 예외 | `false` (ruleset 버그 의심) |
| `UPLOAD_FAILED` | central-ingest `/v1/ingest/studies` 5xx | `true` |
| `BURNED_IN_BLOCKED` | pixel burn-in 검출 → 격리 (safe behavior) | `false` (영구 차단) |
| `OTHER` | 위 5 미분류 | Gateway 판단 |

**Retry policy**: `retryable=true` + `attempt_count < max_retries(5)` → `state='queued'`, 서버가 다음 poll 에서 재claim. `retryable=false` 또는 한도 도달 → `state='dead'` + `transfer_job_dead_letter` row + 주문 `failed` (v0.1 은 partial delivery 없음, 주문 all-or-nothing).

**DLQ visibility**:

- `fulfillment-admin dlq-dump --since 7d --json` (§4.7) 로 dump.
- Prometheus `radivault_fulfillment_transfer_job_dlq_total{hospital_id, reason}` 카운터.
- Alert `A-OF-2` (DLQ 성장률 > 5/hr) → P2 호출.

### 3.5 Bearer 토큰 스코프 — central-ingest `auth_token` 재사용

**핵심**: Gateway 는 **별도 토큰을 받지 않는다**. central-ingest 에서 발급된 `auth_token` 을 그대로 `Authorization: Bearer <token>` 로 보낸다. 서버는 `auth_token` 테이블을 **read-only** 로 참조 (dev-spec FR-4).

| 속성 | 값 |
|------|-----|
| **Key format** | `rvct_<kid8>.<random32>` — central-ingest §4.1 와 동일 |
| **Verification** | argon2id verify + Redis 60s cache |
| **Revocation** | `ingest-admin token revoke --kid <KID>` → Redis TTL 60s 내 전파 → fulfillment 도 즉시 차단 |
| **Rotation** | central-ingest `token rotate` 프로토콜 그대로 (RB-8) |
| **Plane 혼용** | buyer token 으로 `/v1/gateway/*` 호출 → `401 ERR_AUTH_WRONG_PLANE` (dev-spec FR-7). 역방향도 동일. |

**운영 의미**: 한 병원당 토큰 하나가 central-ingest (Flow A) + fulfillment transfer (Flow B) 양쪽에 작동. **Gateway 운영자는 새 credential 를 추가로 받지 않는다** — 온보딩 간소화의 핵심 결정.

---

## 4. Operator CLI — `fulfillment-admin`

### 4.1 설계 원칙 (central-ingest §3.1 · metadata-index §3.1 과 동일)

- **명령 1개 = 작업 1개**. 복합 플래그 남용 금지.
- **영어 우선 UI**, `--lang ko` v0.1 optional.
- **종료 코드** BSD sysexits (central-ingest §3.11 와 동일): `0` OK, `1` 일반 실패, `2` DB error, `64` usage error (`EX_USAGE`), `69` not found (`EX_UNAVAILABLE`), `70` internal error (`EX_SOFTWARE`).
- **`--json`**: 모든 read 명령 지원.
- **`--dry-run`**: 모든 write 명령 지원.
- **`--no-color`** / `NO_COLOR=1` 준수.
- **바이너리 분리**: `fulfillment-admin` 별도 바이너리 (central-ingest 의 `ingest-admin`, metadata-index 의 `search-admin` 과 병존).

### 4.2 전체 명령 트리

```
fulfillment-admin
├── order
│   ├── inspect       --order-id OID [--json]
│   ├── advance       --order-id OID --to-state STATE --reason STR [--dry-run]
│   ├── cancel        --order-id OID --admin-reason STR [--force] [--dry-run]
│   └── expire-stale  [--dry-run]
├── job
│   ├── list          [--hospital-id HID] [--state STATE] [--limit N] [--json]
│   ├── inspect       --job-id JID [--json]
│   ├── requeue       --job-id JID [--reset-attempts] [--dry-run]
│   ├── release-lease --job-id JID [--dry-run]
│   └── dlq-dump      [--since 7d] [--limit N] [--json]
├── url
│   └── audit         --order-id OID [--json]
├── stats
│   ├── buyer-usage   --buyer-id BID --period {day|week|month} [--json]
│   └── dlq-summary   [--since 7d] [--json]
├── unlinked
│   ├── list          [--hospital-id HID] [--json]
│   └── reassign      --study-uid UID --new-order-id OID [--dry-run]
├── migrate
│   ├── up            [--revision REV] [--dry-run]
│   ├── down          --revision REV [--dry-run]
│   └── current
└── version           [--json]
```

**전역 플래그** (central-ingest §3.2 와 동일): `-c/--config`, `--database-url`, `--log-level`, `--no-color`, `--quiet`, `-h/--help`, `-V/--version`.

### 4.3 `fulfillment-admin order inspect`

```
Usage: fulfillment-admin order inspect --order-id OID [--json]
  Inspect order row + items + transfer_jobs + download aggregate + history.
  한 주문 상세 조회.
Exit: 0 found, 1 not found, 2 DB error, 64 usage
```

**Happy-path 출력**

```
$ fulfillment-admin order inspect --order-id ord_01HXXORDER1ABCDEF
═══════════════════════════════════════════════════════════════════════════════
 ORDER ord_01HXXORDER1ABCDEF
═══════════════════════════════════════════════════════════════════════════════
 buyer_id         : buy_acme_001           tier   : paid
 state            : ready_for_download     billing: pending_billing
 n_studies        : 3      n_instances: 512     total_bytes : 282,963,036
 total_usd        : $15.00 (3 × $5.00 preview-rate stub)
 path_type        : mixed  (hot=1, cold=2)
 agreement_hash   : abcd1234...abcdef (MSA v0.1)
 submitted_at     : 2026-04-22T10:00:00Z
 validated_at     : 2026-04-22T10:00:01Z
 queued_at        : 2026-04-22T10:00:01Z
 staging_complete : 2026-04-22T10:04:42Z
 ready_at         : 2026-04-22T10:05:09Z
 expires_at       : 2026-04-29T10:05:09Z   ← in 7d 0h
 cancelled_at     : —
 last_error       : —

 ITEMS (3)
 STATE           PSEUDO_STUDY_UID                   HOSP       INSTANCES  BYTES
 hot_hit_staged  2.25.140737488355328.1.2.3         hosp_abc   184        94,321,012
 staged          2.25.140737488355328.1.2.4         hosp_abc   82         41,002,912
 staged          2.25.140737488355328.1.2.5         hosp_xyz   246        147,639,112

 TRANSFER_JOBS (2)
 STATE      TJ_ID                  HOSP       ATTEMPTS  LEASE_EXPIRES            LAST_ERROR
 completed  tj_01HXXTJ1ABCDEF      hosp_abc   1         —                        —
 completed  tj_01HXXTJ2ABCDEF      hosp_xyz   2         —                        (1st: PACS_UNAVAILABLE)

 DOWNLOAD AUDIT AGGREGATE
 url_minted: 4 events (last 2026-04-22T10:15:22Z)
 get_started / completed / failed : 0/0/0 (S3 access log ETL is v0.1.1)

 STATE HISTORY (last 6)
 2026-04-22T10:00:00Z  null → submitted       actor=buyer
 2026-04-22T10:00:01Z  submitted → queued     actor=system
 2026-04-22T10:00:12Z  queued → fetching      actor=gateway(gw_7f3a9c)
 2026-04-22T10:04:42Z  fetching → staging_complete  actor=gateway(gw_7f3a9c)
 2026-04-22T10:05:09Z  staging_complete → ready_for_download  actor=system
 (earlier entries elided — see `--json` for full history)

 Runbook tip: for mint failures see RB-OF-3. For stuck fetching see RB-OF-2.
═══════════════════════════════════════════════════════════════════════════════
```

**에러 시나리오**

| 상황 | exit | 메시지 |
|------|------|--------|
| `--order-id` 미존재 | 1 | `[ERR_ADMIN_ORDER_NOT_FOUND] order not found: ord_xxx / 해당 주문이 없습니다.` |
| DB 접근 실패 | 2 | `[ERR_DB_UNAVAILABLE] PostgreSQL unreachable — DATABASE_URL 확인` |

### 4.4 `fulfillment-admin order advance` (SRE override)

운영자가 FSM 전이를 **강제** 추진. 사용: (a) `fetching` stuck 복구, (b) S3 COPY 실패 후 수동 재시도.

```
Usage: fulfillment-admin order advance --order-id OID --to-state STATE --reason STR [--dry-run]
  Force-advance FSM. Logs to order_state_history(actor='admin', reason=...).
  주문 FSM 강제 전이. SRE override.
Valid --to-state: queued, fetching, staging_complete, ready_for_download, cancelled, failed
Exit: 0 OK, 1 illegal transition, 2 DB, 64 usage, 69 not found, 70 internal
```

**Happy-path**

```
$ fulfillment-admin order advance --order-id ord_01HXX... \
    --to-state ready_for_download \
    --reason "manual S3 COPY completed after transient failure 2026-04-22"
[OK] ord_01HXX... : staging_complete → ready_for_download
     history logged (actor=admin, reason='manual S3 COPY completed ...')
     ready_at set to 2026-04-22T11:47:23Z
     expires_at set to 2026-04-29T11:47:23Z (+7d)
```

**실패**

```
$ fulfillment-admin order advance --order-id ord_01HXX... --to-state ready_for_download --reason ...
[FAIL] illegal transition: current=fetching → requested=ready_for_download
       legal next states from 'fetching': staging_partial, staging_complete, cancelled, failed
       Runbook: RB-OF-2 (fetching stuck) for recovery.
Exit 1.
```

### 4.5 `fulfillment-admin order cancel` (admin force-cancel)

```
Usage: fulfillment-admin order cancel --order-id OID --admin-reason STR [--force] [--dry-run]
  Admin force-cancel. Sets cancel_requested=true; Gateway observes on next progress.
  Already-uploaded studies detach to `unlinked_study`.
  --force required to cancel during fetching/staging_* states.
  관리자 강제 취소. unlinked_study 이관.
Exit: 0 OK, 1 already terminal, 2 DB, 64 usage (missing --force), 69 not found
```

**Happy-path (fetching state, 1 study 업로드됨)**

```
$ fulfillment-admin order cancel --order-id ord_01HXX... --admin-reason "buyer support request SR-2026-0422-001" --force
Pre-state inspection:
  ord_01HXX... : state=fetching
  transfer_jobs: 1 claimed (tj_01HXX..., lease exp 2026-04-22T10:15:00Z)
  order_items: 1 staged, 1 pending

[OK] ord_01HXX... : fetching → cancelled
     cancel_requested=true set (Gateway will observe on next progress ping)
     transfer_job(tj_01HXX...) left as-is (cooperative cancel; will terminate at next progress)
     1 study detached to unlinked_study:
       (2.25.140737488355328.1.2.3, hosp_abc) disposition='available_for_reassignment'
     history logged (actor=admin, reason='buyer support request SR-2026-0422-001')

 Next step:
  1. Notify buyer via contact-email registered on buyer row.
  2. Watch `fulfillment-admin unlinked list` — detached study may be reassigned
     to a future matching order.
```

### 4.6 `fulfillment-admin job list` / `job requeue` / `job dlq-dump`

```
$ fulfillment-admin job list --hospital-id hosp_abc --state claimed --limit 20
TJ_ID              ORDER_ID             STATE    HOSP      ATTEMPTS  LEASE_EXPIRES          STUDIES
tj_01HXXTJ1A       ord_01HXX..1         claimed  hosp_abc  1         2026-04-22T10:15:00Z   2
tj_01HXXTJ2B       ord_01HXX..2         claimed  hosp_abc  2         2026-04-22T10:18:00Z   5
tj_01HXXTJ3C       ord_01HXX..3         queued   hosp_abc  0         —                       1
...

3 jobs matched (state=claimed by filter, but last shown is state=queued — 'list' intentionally ignores --state when --json absent to keep context; with --json output honors filter strictly)
```

```
$ fulfillment-admin job requeue --job-id tj_01HXXTJ1A --reset-attempts --dry-run
(dry-run) would transition tj_01HXXTJ1A: claimed → queued
          reset lease_owner=NULL, lease_expires_at=NULL
          attempt_count 3 → 0 (--reset-attempts)
          outbox event 'transfer_job.manually_requeued' scheduled
          no change applied.

$ fulfillment-admin job requeue --job-id tj_01HXXTJ1A --reset-attempts
[OK] tj_01HXXTJ1A : claimed → queued (attempts reset 3 → 0)
     next gateway long-poll will claim this job.
     history logged.
```

```
$ fulfillment-admin job dlq-dump --since 7d --json | jq '.[]|{tj:.transfer_job_id,reason:.reason_code,hosp:.hospital_id,dead:.dead_at}'
{"tj":"tj_01HXXDEAD1","reason":"PACS_UNAVAILABLE","hosp":"hosp_xyz","dead":"2026-04-18T03:21:00Z"}
{"tj":"tj_01HXXDEAD2","reason":"DEID_FAILED","hosp":"hosp_abc","dead":"2026-04-19T12:05:00Z"}
{"tj":"tj_01HXXDEAD3","reason":"UPLOAD_FAILED","hosp":"hosp_xyz","dead":"2026-04-20T08:11:00Z"}

3 dead-letter entries in last 7 days.
  by_reason : PACS_UNAVAILABLE=1  DEID_FAILED=1  UPLOAD_FAILED=1
  by_hospital: hosp_xyz=2  hosp_abc=1
  oldest unresolved: 4 days ago.

Recommended next steps:
  - PACS_UNAVAILABLE persisted: check hosp_xyz PACS connectivity, RB-OF-1.
  - DEID_FAILED: inspect Gateway ruleset version on hosp_abc, RB-OF-1.
```

### 4.7 `fulfillment-admin url audit`

```
$ fulfillment-admin url audit --order-id ord_01HXXORDER1ABCDEF
Order: ord_01HXXORDER1ABCDEF  buyer=buy_acme_001  tier=paid
Period: 2026-04-22T10:00:00Z → 2026-04-30T10:00:00Z  (ready → expired window)

URL MINTING EVENTS (download_event.url_minted)
TS                   REQUEST_ID       SRC_IP          USER_AGENT             TTL   N_FILES  SIG_HASH
2026-04-22 10:05:31Z 01HXXMINT1...   203.0.113.42    httpx/0.27 (acme-sdk)  86400 512      a1b2c3d4e5f6a7b8
2026-04-22 22:14:08Z 01HXXMINT2...   203.0.113.42    httpx/0.27 (acme-sdk)  86400 512      b2c3d4e5f6a7b8c9
2026-04-23 18:02:19Z 01HXXMINT3...   198.51.100.77   curl/8.4.0              172800 512     c3d4e5f6a7b8c9d0   ← new IP!
2026-04-24 06:11:45Z 01HXXMINT4...   203.0.113.42    httpx/0.27 (acme-sdk)  86400 512      d4e5f6a7b8c9d0e1

Summary:
  total mint events  : 4
  distinct src_ips   : 2    (203.0.113.42 × 3, 198.51.100.77 × 1)
  distinct user agents: 2    (httpx × 3, curl × 1)
  total url-mints bytes-equiv (= n_files × total_bytes): 754,040,144 × 4 = 3.0 GB (per-mint, not per-download)

NOTE: v0.1 does not record get_started/get_completed/get_failed (S3 access log ETL is v0.1.1).
      sharing-detector WARN: same order minted from 2 distinct src_ips — log for follow-up (buyer to confirm).
```

### 4.8 `fulfillment-admin stats buyer-usage`

```
$ fulfillment-admin stats buyer-usage --buyer-id buy_acme_001 --period week
Buyer: buy_acme_001 (Acme AI, Inc.)  tier=paid
Period: 2026-04-15 → 2026-04-22  (UTC)

DAILY BREAKDOWN
DATE         ORDERS  READY   FAILED  CANCELLED  EXPIRED  TOTAL_USD  AVG_READY_TIME
2026-04-15   0       0       0       0          0        $0.00      —
2026-04-16   2       2       0       0          0        $100.00    42s
2026-04-17   5       5       0       0          0        $250.00    38s
2026-04-18   8       7       1       0          0        $400.00    51s
2026-04-19   12      11      0       1          0        $600.00    34s
2026-04-20   15      14      0       0          0        $750.00    29s
2026-04-21   22      20      0       1          1        $1,100.00  37s
2026-04-22   4       3       0       0          0        $200.00    31s  (partial day)

TOTALS
  orders placed       : 68
  reached ready_for_download: 62
  failed              : 1
  cancelled           : 2
  expired             : 1
  total_estimated_usd : $3,400.00  (pending_billing — no charges posted)

TOP ERRORS
ERR_ORDER_TIER_EXCEEDED     4
ERR_ORDER_STATE_TRANSITION  2
ERR_URL_MINT_RATE           1

SALES SIGNAL: avg ready-time 35s = good; monitor total_estimated_usd for billing rollout.
```

### 4.9 `fulfillment-admin migrate` · `version`

`central-ingest migrate` 와 동일 UX (§3.9). **단, `migrate up` 은 `MIGRATION_DATABASE_URL` superuser 전용**. 일반 `radivault_fulfillment_app` role DSN 으로 호출 시 `ERR_ADMIN_WRONG_ROLE` (central-ingest §5.5 재사용).

```
$ fulfillment-admin version
radivault-fulfillment  0.1.0
build                  ab12cd34 (2026-04-22T09:00:00Z)
api_contract           1
alembic_head           0004 (order-fulfillment initial)
python                 3.11.9
psycopg                3.1.18
boto3                  1.34.77

$ fulfillment-admin version --json
{"service":"radivault-fulfillment","version":"0.1.0","git_sha":"ab12cd34",
 "built_at":"2026-04-22T09:00:00Z","api_contract_version":"1",
 "alembic_head":"0004","python":"3.11.9","psycopg":"3.1.18","boto3":"1.34.77"}
```

### 4.10 종료 코드 요약

| Command | 0 | 1 | 2 | 64 | 69 | 70 |
|---------|---|---|---|----|----|----|
| `order inspect` | OK | Not found | DB error | Usage | — | — |
| `order advance` | OK | Illegal transition | DB error | Usage | Not found | Internal |
| `order cancel` | OK | Already terminal | DB error | Usage (missing --force) | Not found | — |
| `order expire-stale` | OK | Partial fail | DB error | Usage | — | — |
| `job list/inspect` | OK | — | DB error | Usage | Not found | — |
| `job requeue/release-lease` | OK | Illegal | DB error | Usage | Not found | — |
| `job dlq-dump` | OK | — | DB error | Usage | — | — |
| `url audit` | OK | Not found | DB error | Usage | — | — |
| `stats buyer-usage/dlq-summary` | OK | — | DB error | Usage | Not found | — |
| `unlinked list/reassign` | OK | Study not available | DB error | Usage | Not found | — |
| `migrate up/down` | OK | Revision conflict | DB error | Usage | — | Internal |
| `migrate current` | OK | — | DB error | — | — | — |
| `version` | 항상 0 | — | — | — | — | — |

---

## 5. Gateway CLI 확장 — `gateway-agent transfer *`

기존 `gateway-agent` 바이너리 (design-spec-gateway-agent §3) 에 `transfer` 서브커맨드 신규 추가. dev-spec §14 G-1 의 contract delta.

### 5.1 `gateway-agent transfer start`

daemon mode. Flow A (`gateway-agent start`) 와 **병렬** 실행 가능.

```
Usage: gateway-agent transfer start [--oneshot] [--fulfillment-url URL]
                                    [--poll-wait N] [--max-concurrent N]
  Long-poll RadiVault Fulfillment. claim → fetch → de-ID → upload → complete cycles.
  Requires transfer.enabled=true in gateway.yml.
  SIGTERM/SIGINT: graceful shutdown (finish in-flight + release lease).
  주문 이행 컨슈머 데몬. Flow A 와 병렬 운영.
Exit: 0 clean shutdown, 64 config invalid, 69 central unreachable at start, 70 internal
```

**Happy-path 콘솔 출력 (TTY)**

```
2026-04-22T01:15:00Z  INFO  radivault.transfer         starting transfer consumer (v0.1.0)
2026-04-22T01:15:00Z  INFO  radivault.transfer         hospital_id=hosp_abc gateway_id=gw_7f3a9c
2026-04-22T01:15:00Z  INFO  radivault.transfer         central_url=https://fulfillment.radivault.io
2026-04-22T01:15:00Z  INFO  radivault.transfer         max_concurrent=2 poll_wait=30s lease_interval=300s
2026-04-22T01:15:00Z  INFO  radivault.transfer         long-poll tick #1 start
2026-04-22T01:15:31Z  INFO  radivault.transfer         204 no content (31s wait) — loop
2026-04-22T01:16:01Z  INFO  radivault.transfer         200 OK tj=tj_01HXXTJ1A studies=2 lease_exp=+15m
2026-04-22T01:16:03Z  INFO  radivault.pipeline         tj=tj_01HXXTJ1A study=2.25.aaaa fetch ok (2.1s)
2026-04-22T01:16:07Z  INFO  radivault.pipeline         tj=tj_01HXXTJ1A study=2.25.aaaa deid ok (4.0s)
2026-04-22T01:16:11Z  INFO  radivault.pipeline         tj=tj_01HXXTJ1A study=2.25.aaaa upload ok central_job_id=ingest_01HX...
2026-04-22T01:16:11Z  INFO  radivault.transfer         progress: fetched=1 deided=1 uploaded=1 lease_exp=+15m
2026-04-22T01:16:13Z  INFO  radivault.pipeline         tj=tj_01HXXTJ1A study=2.25.bbbb fetch ok (1.8s)
...
2026-04-22T01:16:28Z  INFO  radivault.transfer         complete tj=tj_01HXXTJ1A state=completed order_state=staging_complete
2026-04-22T01:16:28Z  INFO  radivault.transfer         long-poll tick #2 start
```

**에러 시나리오**

| 상황 | exit | 메시지 |
|------|------|--------|
| `transfer.enabled=false` | 64 | `ERR_CFG_030 transfer.enabled is false — refusing to start. Set transfer.enabled=true in gateway.yml.` |
| `transfer.central_url` 미설정 | 64 | `ERR_CFG_031 transfer.central_url missing in config.` |
| Fulfillment service unreachable (3 connect failures) | 69 | `ERR_TRANSFER_010 fulfillment service unreachable at startup (https://fulfillment.radivault.io). Check network / DNS / credentials.` |
| Bearer auth 401 | 계속 재시도 | `WARN_TRANSFER_001 auth failed — verify that the same central auth_token has fulfillment plane authorization.` |
| Lease 만료 후 progress 403 | job 포기 | `WARN_TRANSFER_002 lease expired; job tj_01HXXTJ1A abandoned — server will requeue.` |

### 5.2 `gateway-agent transfer status`

현재 claim 된 job 수, lease 남은 시간, 최근 완료 5건.

```
$ gateway-agent transfer status
Transfer Consumer Status — gw_7f3a9c (hosp_abc)
=========================================================================================

  daemon pid        : 12345        uptime: 2h14m
  poll_wait         : 30s          max_concurrent: 2
  central_url       : https://fulfillment.radivault.io      last_poll: 2026-04-22T03:29:12Z

IN-FLIGHT JOBS (1 / 2)
┌──────────────────┬──────────────────────┬──────────┬─────────────────┬──────────────┐
│ TJ_ID            │ ORDER_ID             │ STUDIES  │ PROGRESS        │ LEASE LEFT   │
├──────────────────┼──────────────────────┼──────────┼─────────────────┼──────────────┤
│ tj_01HXXTJ1A     │ ord_01HXXORDER1      │ 2        │ [███████  ] 70% │ 8m12s        │
└──────────────────┴──────────────────────┴──────────┴─────────────────┴──────────────┘

RECENT COMPLETIONS (last 5)
TS                    TJ_ID             STUDIES  DURATION   STATE
2026-04-22T03:26:41Z  tj_01HXXTJ0Z      1        6.2s       completed
2026-04-22T03:22:18Z  tj_01HXXTJ0Y      3        42.1s      completed
2026-04-22T03:15:09Z  tj_01HXXTJ0X      1        8.8s       completed
2026-04-22T03:02:33Z  tj_01HXXTJ0W      2        21.4s      completed
2026-04-22T02:47:11Z  tj_01HXXTJ0V      1        7.9s       completed

RECENT FAILURES (last 5)
TS                    TJ_ID             REASON_CODE         RETRYABLE  DETAILS
2026-04-22T01:45:22Z  tj_01HXXTJ0U      PACS_UNAVAILABLE    true       connection timeout (3x)
(no other recent failures)
```

`--json`:

```json
{
  "gateway_id": "gw_7f3a9c",
  "hospital_id": "hosp_abc",
  "daemon_pid": 12345,
  "uptime_seconds": 8040,
  "poll_wait_seconds": 30,
  "max_concurrent_jobs": 2,
  "central_url": "https://fulfillment.radivault.io",
  "last_poll_at": "2026-04-22T03:29:12Z",
  "inflight": [
    {"transfer_job_id":"tj_01HXXTJ1A","order_id":"ord_01HXXORDER1",
     "n_studies":2,"progress":0.70,"lease_seconds_remaining":492}
  ],
  "recent_completions": [/*...*/],
  "recent_failures":    [/*...*/]
}
```

### 5.3 `gateway-agent transfer test` — one-shot validation

온보딩·CI 용 — mock 또는 staging 서버에 1회 claim→progress→complete 사이클.

```
Usage: gateway-agent transfer test --fulfillment-url URL [--hospital-id HID] [--timeout 60]
  Single cycle against mock / staging fulfillment endpoint.
  1회 사이클. 온보딩 검증용.
Exit: 0 cycle OK, 1 cycle failed, 2 queue empty, 64 usage
```

**Happy-path**

```
$ gateway-agent transfer test --fulfillment-url http://localhost:8002
[STEP 1/4] long-poll GET /v1/gateway/transfer-jobs?wait=30s
           ... 200 OK tj=tj_01HXXTEST1 studies=1 lease_exp=+15m
[STEP 2/4] simulate fetch + de-id (skipping actual PACS — --test mode)
           ... synthesized manifest for 1 study, 10 instances
[STEP 3/4] POST /progress {n_fetched:10,n_deided:10,n_uploaded:10,lease_extend:true}
           ... 200 OK lease_exp=+15m cancel_requested=false
[STEP 4/4] POST /complete {manifest:[1 study], audit_ref:...}
           ... 200 OK state=completed order_state=staging_complete

CYCLE OK  (6.1s end-to-end)
```

**Queue empty**

```
$ gateway-agent transfer test --fulfillment-url http://localhost:8002 --timeout 10
[STEP 1/4] long-poll GET /v1/gateway/transfer-jobs?wait=10s
           ... 204 No Content (queue empty)
Exit 2 — no job to claim. Populate a test order and retry.
```

### 5.4 Gateway CLI 종료 코드 요약 (추가분만)

| Command | 0 | 1 | 2 | 64 | 69 | 70 |
|---------|---|---|---|----|----|----|
| `transfer start` | Clean shutdown | — | — | Config invalid | Central unreachable | Internal |
| `transfer status` | OK | State DB error | — | — | — | — |
| `transfer test` | Cycle OK | Cycle fail | Queue empty | Usage | — | — |

---

## 6. Log & Observability 출력

### 6.1 JSON 로그 schema (central-ingest §4.1 · metadata-index §4.1 확장)

stdout JSON-lines. 공통 shape 상속 + **fulfillment 전용 필드 8종**:

```jsonc
{
  "ts":"2026-04-22T10:20:01.234Z","level":"INFO",
  "service":"radivault-fulfillment","logger":"radivault_fulfillment.api.orders",
  "trace_id":"6a8c...","span_id":"0123...","request_id":"01HXXORDER1SERVER",
  "event":"order.created",                         // namespace.action
  "message_ko":"주문 생성 — buy_acme tier=paid 3 studies",
  "message_en":"Order created for buy_acme tier=paid n_studies=3",
  "path":"/v1/orders","method":"POST","status":202,"duration_ms":842,

  // ── Fulfillment-specific fields (8) ──
  "order_id":"ord_01HXXORDER1ABCDEF",               // null if pre-ack events
  "transfer_job_id":null,                            // set for job.* events
  "buyer_id_hash":"sha256:a7b9c2...",                // never raw buyer_id
  "hospital_id":null,                                // Gateway plane events only
  "state_from":null,                                 // FSM transition only
  "state_to":"queued",
  "event_type":"order.created",                      // enum, stable for filtering
  "extra":{"tier":"paid","n_studies":3,"total_bytes":282963036,"idempotency_replayed":false}
}
```

**금지 필드** (dev-spec §6.8 · metadata-index §6.6 상속):

- 원본 `StudyInstanceUID`, `SOPInstanceUID` / 환자 이름·생년월일·ID / 병원 내부 호스트명
- API key plaintext · Bearer raw · presigned URL raw query string
- Raw Idempotency-Key (hash 만 mirror 에 저장) · buyer 담당자 개인정보

감지 시 sanitiser 가 레코드 drop + `ERR_LOG_PHI_DETECTED` 카운터 증가 (central-ingest §4.1 동일 메커니즘).

**Event type enum**: `order.{created,validated,queued,cancelled,expired,failed,state_changed}` · `job.{queued,claimed,progress,completed,failed,dead_letter,lease_expired,lease_released}` · `download.{url_minted,expired}` · `auth.{failure,success,revoked}` · `idempotency.{replayed,mismatch}` · `staging.copy_{started,completed,failed}`.

### 6.2 6-line 현실적 예시 (이벤트 6종 커버)

아래는 공통 필드(`service`, `logger`, `trace_id`, `span_id`) 를 생략한 축약본. 실제 line 은 §6.1 full shape.

```jsonc
{"ts":"2026-04-22T10:00:00.120Z","level":"INFO","event":"order.created","request_id":"01HXXREQ1","path":"/v1/orders","method":"POST","status":202,"duration_ms":842,"order_id":"ord_01HXXORDER1","buyer_id_hash":"sha256:a7b9c2","state_from":null,"state_to":"queued","extra":{"tier":"paid","n_studies":3,"total_bytes":282963036,"idempotency_replayed":false}}
{"ts":"2026-04-22T10:00:12.501Z","level":"INFO","event":"job.claimed","request_id":"01HXXREQ2","path":"/v1/gateway/transfer-jobs","method":"GET","status":200,"duration_ms":54,"order_id":"ord_01HXXORDER1","transfer_job_id":"tj_01HXXTJ1","hospital_id":"hosp_abc","state_from":"queued","state_to":"claimed","extra":{"lease_expires_at":"2026-04-22T10:15:00Z","attempt_count":1}}
{"ts":"2026-04-22T10:03:00.882Z","level":"INFO","event":"job.progress","request_id":"01HXXREQ3","path":"/v1/gateway/transfer-jobs/tj_01HXXTJ1/progress","method":"POST","status":200,"duration_ms":18,"transfer_job_id":"tj_01HXXTJ1","hospital_id":"hosp_abc","extra":{"n_fetched":3,"n_deided":3,"n_uploaded":3,"lease_extended":true}}
{"ts":"2026-04-22T10:04:42.009Z","level":"INFO","event":"job.completed","request_id":"01HXXREQ4","path":"/v1/gateway/transfer-jobs/tj_01HXXTJ1/complete","method":"POST","status":200,"duration_ms":142,"order_id":"ord_01HXXORDER1","transfer_job_id":"tj_01HXXTJ1","hospital_id":"hosp_abc","state_from":"fetching","state_to":"staging_complete","extra":{"n_studies":3,"central_job_ids":["ingest_01HX1","ingest_01HX2","ingest_01HX3"]}}
{"ts":"2026-04-22T10:05:31.412Z","level":"INFO","event":"download.url_minted","request_id":"01HXXMINT1","path":"/v1/orders/ord_01HXXORDER1/download-urls","method":"POST","status":200,"duration_ms":317,"order_id":"ord_01HXXORDER1","buyer_id_hash":"sha256:a7b9c2","extra":{"n_files":512,"ttl_seconds":86400,"total_bytes":282963036,"tier":"paid"}}
{"ts":"2026-04-29T10:05:09.221Z","level":"INFO","event":"order.expired","request_id":null,"order_id":"ord_01HXXORDER1","buyer_id_hash":"sha256:a7b9c2","state_from":"ready_for_download","state_to":"expired","extra":{"window_days":7,"n_url_mint_events":4}}
```

### 6.3 Prometheus 메트릭 네이밍 (`radivault_fulfillment_*` — 최소 16)

**네임스페이스**: `radivault_fulfillment_*`. central-ingest=`radivault_central_*`, metadata-index=`radivault_index_*` 와 직교.

**17개 핵심 메트릭**

| # | 이름 | 타입 | 라벨 | 단위 | 설명 |
|---|------|------|------|------|------|
| 1 | `radivault_fulfillment_orders_total` | Counter | `tier`, `final_state` | — | 주문 총계, `final_state ∈ {ready_for_download, expired, cancelled, failed}` |
| 2 | `radivault_fulfillment_order_submit_to_ready_seconds` | Histogram | `tier`, `path_type` | seconds | 주문 제출 → ready 전이 end-to-end latency (버킷: 1, 10, 30, 60, 300, 900, 1800, 3600, 7200) |
| 3 | `radivault_fulfillment_active_orders` | Gauge | `tier`, `state` | — | 현재 in-flight 주문 수 (state 별 gauge) |
| 4 | `radivault_fulfillment_transfer_jobs_total` | Counter | `hospital_id`, `final_state` | — | transfer_job 총계, `final_state ∈ {completed, failed, dead}` |
| 5 | `radivault_fulfillment_transfer_job_duration_seconds` | Histogram | `hospital_id` | seconds | claim → complete 구간 (버킷: 10, 60, 300, 900, 1800, 3600) |
| 6 | `radivault_fulfillment_transfer_job_queue_depth` | Gauge | `hospital_id` | — | `state=queued` 대기열 깊이 |
| 7 | `radivault_fulfillment_transfer_job_dlq_total` | Counter | `hospital_id`, `reason` | — | DLQ 신규 진입 |
| 8 | `radivault_fulfillment_transfer_job_lease_expired_total` | Counter | `hospital_id` | — | Reaper 가 재큐한 lease 만료 건 수 |
| 9 | `radivault_fulfillment_presigned_urls_minted_total` | Counter | `tier` | — | URL mint 성공 |
| 10 | `radivault_fulfillment_presigned_url_ttl_seconds` | Histogram | `tier` | seconds | 요청된 ttl 분포 (버킷: 3600, 14400, 43200, 86400, 259200, 604800) |
| 11 | `radivault_fulfillment_download_events_total` | Counter | `buyer_id_hash`, `result_code` | — | `url_minted`·`get_*` 이벤트 (v0.1 은 `url_minted` 만) |
| 12 | `radivault_fulfillment_download_bytes_total` | Counter | `tier` | bytes | 누적 서빙 바이트 (mint 시점 기준 추정; S3 ETL v0.1.1 에서 실측으로 대체) |
| 13 | `radivault_fulfillment_cancellations_total` | Counter | `from_state`, `actor` | — | 취소 이벤트. actor ∈ `{buyer, admin}` |
| 14 | `radivault_fulfillment_hot_storage_hit_ratio` | Gauge | — | — | 주문당 `central_object_present=true` 비율 (0..1) |
| 15 | `radivault_fulfillment_unlinked_study_orphans` | Gauge | `hospital_id` | — | 미할당 `unlinked_study` 레코드 수 |
| 16 | `radivault_fulfillment_order_idempotency_replays_total` | Counter | — | — | POST /v1/orders idempotency replay 건 |
| 17 | `radivault_fulfillment_build_info` | Gauge | `version`, `git_sha`, `alembic_head`, `python_version` | — | 1로 고정, 빌드 정보 라벨 |

**원칙** (central-ingest §4.3 상속):

- enum 라벨 카디널리티 ≤ 10. `hospital_id` 는 병원 수 만큼 (≤ 수십) 허용. `buyer_id_hash` 는 **`download_events_total` 한 곳에만** — 장기적으로 recording rule 로 bucket 화.
- 단위 이름 포함 (`_seconds`, `_bytes`, `_total`).
- Histogram 버킷 명시.

### 6.4 알람 설계 (최소 10편, v0.1 은 12편)

**Severity 규약** (central-ingest §4.4 상속): `P1` = 즉시 호출(24/7), `P2` = 업무시간 1시간 내, `P3` = 익영업일.

| # | 이름 | 조건 | 임계 | 지속 | Severity | Runbook |
|---|------|------|------|------|----------|---------|
| A-OF-1 | `FulfillmentReadyLatencyHigh` | `histogram_quantile(0.95, sum by (le) (rate(radivault_fulfillment_order_submit_to_ready_seconds_bucket[15m]))) > 7200` | p95 submit→ready > 2h | 15m | P2 | RB-OF-2 |
| A-OF-2 | `FulfillmentDlqGrowthHigh` | `sum(rate(radivault_fulfillment_transfer_job_dlq_total[1h])) > 5/3600` | > 5 신규 DLQ / hour | 1h | P2 | RB-OF-1 |
| A-OF-3 | `FulfillmentLongPollStuckConnections` | `sum(http_long_poll_inflight{service="radivault-fulfillment"}) > 2 * count(up{job="gateway-agent"})` | 연결 수 > 2× Gateway 수 | 10m | P2 | RB-OF-1 |
| A-OF-4 | `FulfillmentLeaseExpiredRateHigh` | `sum(rate(radivault_fulfillment_transfer_job_lease_expired_total[1h])) / sum(rate(radivault_fulfillment_transfer_jobs_total[1h])) > 0.03` | lease 만료 비율 > 3%/hr | 30m | P2 | RB-OF-1 |
| A-OF-5 | `FulfillmentHotStorageHitRatioLow` | `radivault_fulfillment_hot_storage_hit_ratio < 0.05` | hit ratio < 5% | 1h | P3 | RB-OF-6 |
| A-OF-6 | `FulfillmentDownload5xxHigh` | `sum(rate(radivault_fulfillment_download_events_total{result_code=~"5.."}[5m])) / sum(rate(radivault_fulfillment_download_events_total[5m])) > 0.01` | 다운로드 5xx > 1% | 10m | P1 | RB-OF-4 / RB-OF-8 |
| A-OF-7 | `FulfillmentUnlinkedOrphansHigh` | `radivault_fulfillment_unlinked_study_orphans > 100` | 미할당 orphan > 100 | 6h | P3 | RB-OF-1 |
| A-OF-8 | `FulfillmentIdempotencyReplaySpike` | `increase(radivault_fulfillment_order_idempotency_replays_total[5m]) > 10` | 5분 내 replay > 10 | 5m | P3 | RB-OF-2 |
| A-OF-9 | `FulfillmentUrlMintFailureHigh` | `sum(rate(radivault_fulfillment_presigned_urls_minted_total{result="failed"}[5m])) / sum(rate(radivault_fulfillment_presigned_urls_minted_total[5m])) > 0.005` | mint 실패 > 0.5% | 10m | P1 | RB-OF-3 |
| A-OF-10 | `FulfillmentS3ExpirationLag` | (배치) objects with `ingested_at < now()-8d` in `staging/*` prefix | lag > 24h past TTL | 배치 | P3 | RB-OF-7 |
| A-OF-11 | `FulfillmentMassExpirationStorm` | `increase(radivault_fulfillment_orders_total{final_state="expired"}[1h]) > 20` | 1시간 내 20+ expired | 1h | P2 | RB-OF-7 |
| A-OF-12 | `FulfillmentReadyzFailing` | `radivault_fulfillment_readyz_checks{check=~"db\|redis\|migrations"} == 0` | 즉시 | 3m | P1 | central RB-4/6 |

---

## 7. Error Taxonomy UX (5-field 운영자 표)

dev-spec §7.11 + §13.1 의 **신규 24 에러 코드** 를 namespace 별로 5-field 템플릿으로 렌더. 포맷은 central-ingest design-spec §5 와 동일:

```
[<CODE>] <한국어 한 줄> / <English one line>
  Context / 상황
  Buyer action / 구매자 조치   (구매자 전용 코드)
  Operator action / 운영자 조치 (병원 Gateway 또는 RadiVault SRE)
  Docs: https://docs.radivault.io/fulfillment/errors/<CODE>
```

### 7.1 `ERR_ORDER_*` 네임스페이스 (주문 도메인, 주로 buyer)

| Code | HTTP | 발생 조건 | message_ko | message_en | Buyer 조치 | SRE 조치 | Doc |
|------|------|-----------|------------|------------|-------------|----------|-----|
| `ERR_ORDER_DUPLICATE_STUDY` | 400 | `pseudo_study_uids` 배열에 중복값 | 주문 안에 동일 UID 가 중복 포함되었습니다. | The same pseudo_study_uid appears multiple times in this order. | 클라이언트에서 `set()` 로 dedup. | — | .../ERR_ORDER_DUPLICATE_STUDY |
| `ERR_ORDER_AGREEMENT_REQUIRED` | 400 | `agreement_hash` 누락/불일치 | MSA 동의 해시가 누락되었거나 일치하지 않습니다. | MSA agreement_hash missing or mismatched. | 최신 MSA 본문의 sha256 을 재계산. sales@ 에 문의. | `fulfillment-admin` config `audit.agreement_hash_current` 확인. | .../ERR_ORDER_AGREEMENT_REQUIRED |
| `ERR_ORDER_SCOPE_FORBIDDEN` | 403 | `scope_json.exclude_hospitals` 위반 또는 `allowed_hospitals` 밖 hospital 포함 | 스코프 상 접근 불가 병원이 코호트에 포함됩니다. | Cohort includes hospitals outside your key scope. | `metadata-index /v1/search/facets` 로 본인 key 의 접근가능 병원 확인. sales@ 에 scope 확장 문의. | `search-admin buyer show` + `key issue --allowed-hospitals` 검토. | .../ERR_ORDER_SCOPE_FORBIDDEN |
| `ERR_ORDER_STUDY_NOT_FOUND` | 404 | 하나 이상의 `pseudo_study_uid` 가 `study` 테이블에 없음 | 하나 이상의 스터디 UID 를 찾을 수 없습니다. | One or more pseudo_study_uid not indexed. | 오타 확인, metadata-index 로 재검색. | ingest 경로 delay 또는 누락 — central-ingest 쪽 점검. | .../ERR_ORDER_STUDY_NOT_FOUND |
| `ERR_ORDER_NOT_FOUND` | 404 | 본인 주문이 아니거나 존재하지 않음 | 주문을 찾을 수 없습니다. | Order not found or not owned by your buyer key. | order_id 오타 확인, GET /v1/orders 로 본인 주문 목록 조회. | — (정상 — scope leak 방지 의도). | .../ERR_ORDER_NOT_FOUND |
| `ERR_ORDER_NOT_READY` | 409 | 주문이 `ready_for_download` 가 아님 | 주문이 아직 다운로드 준비 상태가 아닙니다. | Order is not in ready_for_download state. | GET /v1/orders/{id} 폴링하여 상태 확인. | — | .../ERR_ORDER_NOT_READY |
| `ERR_ORDER_STATE_TRANSITION` | 409 | 현재 상태에서 요청한 전이 불가 (buyer cancel in fetching, 등) | 현재 상태에서는 해당 전이가 허용되지 않습니다. | State transition not allowed from current state. | `hint` 필드 준수 — 예: fetching → support@ 문의. | `fulfillment-admin order advance` 로 강제 추진 가능 (SRE override). | .../ERR_ORDER_STATE_TRANSITION |
| `ERR_ORDER_EXPIRED` | 410 | `expires_at` 경과 | 주문 다운로드 기간이 만료되었습니다. | Order expired (7d window elapsed). | 새 주문 생성 (동일 UID 재사용 가능). | — | .../ERR_ORDER_EXPIRED |
| `ERR_ORDER_TERMINAL` | 410 | 주문이 cancelled/failed | 주문이 이미 종결되었습니다. | Order is terminal (cancelled or failed). | 새 주문 생성. | `fulfillment-admin order inspect` 로 last_error 조회. | .../ERR_ORDER_TERMINAL |
| `ERR_ORDER_TOO_LARGE` | 413 | `sum(total_bytes)` tier 상한 초과 | 주문 전체 크기가 티어 상한을 초과합니다. | Total bytes exceed tier cap. | 주문 분할 또는 paid 전환 (sales@). | — | .../ERR_ORDER_TOO_LARGE |
| `ERR_ORDER_TIER_EXCEEDED` | 422 | `len(pseudo_study_uids)` tier 상한 초과 | 코호트 크기가 티어 상한을 초과합니다. | Cohort size exceeds tier cap. | preview=50 / paid=10000 이하. sales@ 에 상향 문의. | — | .../ERR_ORDER_TIER_EXCEEDED |
| `ERR_ORDER_QUOTA_EXCEEDED` | 429 | 일일 주문 쿼터 초과 | 일일 주문 쿼터를 초과했습니다. | Daily order quota exhausted. | 다음 UTC 자정 이후 재시도 또는 paid 전환. | `fulfillment-admin stats buyer-usage` 관찰 — 영업 업셀 시그널. | .../ERR_ORDER_QUOTA_EXCEEDED |

### 7.2 `ERR_JOB_*` 네임스페이스 (Gateway plane, M2M)

| Code | HTTP | 발생 조건 | message_ko | message_en | Gateway 조치 | SRE 조치 | Doc |
|------|------|-----------|------------|------------|--------------|----------|-----|
| `ERR_JOB_NOT_FOUND` | 404 | 해당 `transfer_job_id` 없음 | transfer_job 을 찾을 수 없습니다. | transfer_job_id unknown. | 본인이 claim 한 job 만 update — 로컬 상태 재점검. | `fulfillment-admin job inspect` 로 DB 확인. | .../ERR_JOB_NOT_FOUND |
| `ERR_JOB_LEASE_OWNERSHIP` | 403 | `lease_owner` 불일치 | 해당 job 의 lease 소유자가 아닙니다. | You are not the current lease owner. | 해당 job 포기 (다른 Gateway 가 인수). 로컬 상태 정리. | — | .../ERR_JOB_LEASE_OWNERSHIP |
| `ERR_JOB_LEASE_EXPIRED` | 409 | `lease_expires_at < now()` | lease 가 만료되어 해당 작업이 취소되었습니다. | Lease expired; job has been returned to the queue. | 해당 job 포기. 다음 long-poll 에서 재claim 시도. | — | .../ERR_JOB_LEASE_EXPIRED |
| `ERR_JOB_STATE_CONFLICT` | 409 | `state != claimed` 에서 progress/complete 호출 | job 상태가 요청을 수용할 수 없습니다. | Job state does not allow this operation. | 로컬 상태 재점검. | `fulfillment-admin job inspect` 로 실제 state 확인. | .../ERR_JOB_STATE_CONFLICT |
| `ERR_JOB_HOSPITAL_MISMATCH` | 403 | Gateway hospital 이 해당 job 의 hospital 과 불일치 (방어적) | 해당 job 이 본인 병원 소속이 아닙니다. | Job belongs to a different hospital. | Gateway 설정 `agent.hospital_id` 재확인 — 잘못 배포된 credentials 의심. | central `ingest-admin token list` 로 토큰·병원 매핑 검증. | .../ERR_JOB_HOSPITAL_MISMATCH |
| `ERR_JOB_MANIFEST_MISMATCH` | 400 | complete manifest 의 uid 가 claim studies 와 불일치 | complete manifest 가 claim 내용과 일치하지 않습니다. | Complete manifest diverges from claim studies. | claim 응답을 그대로 참조하여 manifest 작성. 누락/추가 금지. | Gateway 버그 제보. | .../ERR_JOB_MANIFEST_MISMATCH |
| `ERR_JOB_COUNTER_REGRESS` | 400 | `n_fetched/n_deided/n_uploaded` 감소 | 진행 카운터가 단조 증가하지 않습니다. | Progress counters must be monotonically non-decreasing. | 로컬 progress state 를 장비 재시작에 안전하게 저장. | Gateway 버그 제보. | .../ERR_JOB_COUNTER_REGRESS |

### 7.3 `ERR_URL_*` + `ERR_DOWNLOAD_*` 네임스페이스

| Code | HTTP | 발생 조건 | message_ko | message_en | Buyer 조치 | SRE 조치 | Doc |
|------|------|-----------|------------|------------|-------------|----------|-----|
| `ERR_URL_TTL_EXCEEDED` | 422 | `ttl_seconds > tier.download_ttl_max_seconds` | 요청 TTL 이 티어 상한을 초과합니다. | Requested ttl_seconds exceeds tier cap. | preview=24h, paid=7d 이하. | — | .../ERR_URL_TTL_EXCEEDED |
| `ERR_URL_MINT_RATE` | 429 | URL mint rate (1 req/5s, burst 10) 초과 | URL 발급 속도가 제한을 초과했습니다. | URL mint rate limit exceeded. | Retry-After 준수. 이전에 받은 URL 배치 재사용. | — | .../ERR_URL_MINT_RATE |
| `ERR_URL_MINT_FAILED` | 502 | boto3 `generate_presigned_url` 실패 | 다운로드 URL 서명 실패. 잠시 후 재시도. | Presigning failed (S3/KMS transient). | `retry_after` 후 재시도. | RB-OF-3 — KMS/S3 연결 확인. | .../ERR_URL_MINT_FAILED |
| `ERR_DOWNLOAD_HASH_MISMATCH` (신규, design-side) | N/A (client-side) | buyer 가 sha256 비교 실패를 지원에 제보 | 다운로드 파일 해시가 manifest 와 일치하지 않습니다. | Downloaded file sha256 does not match manifest. | 재다운로드 (새 URL batch). 반복 실패 시 support@. | RB-OF-4 실행. | .../ERR_DOWNLOAD_HASH_MISMATCH |

### 7.4 재사용 (central-ingest · metadata-index 상속)

| Code | HTTP | 상속 출처 | 본 서비스 적용 |
|------|------|----------|----------------|
| `ERR_AUTH_MISSING` | 401 | central-ingest §5.1 | 모든 엔드포인트 |
| `ERR_AUTH_EXPIRED` | 401 | central-ingest §5.1 | 모든 엔드포인트 |
| `ERR_AUTH_WRONG_PLANE` | 401 | dev-spec FR-7 (신규) | buyer↔gateway token 혼용 시 |
| `ERR_AUTH_UNAVAILABLE` | 503 | dev-spec FR-6 (신규) | Redis + PG 양측 장애 |
| `ERR_IDEMP_MISSING` | 400 | central-ingest §5.2 | POST endpoints |
| `ERR_IDEMP_FORMAT` | 400 | central-ingest §5.2 | POST endpoints |
| `ERR_IDEMP_MISMATCH` | 409 | central-ingest design §2.4 (신규) | POST /v1/orders 등 |
| `ERR_IDEMP_UNAVAILABLE` | 503 | central-ingest §5.2 | POST endpoints |
| `ERR_REQUEST_SCHEMA` | 400 | metadata-index §5.2 | 모든 POST |
| `ERR_RATE_LIMITED` | 429 | central-ingest §5.5 | 전역 rate |
| `ERR_DB_UNAVAILABLE` | 503 | central-ingest §5.5 | 모든 |
| `ERR_INTERNAL` | 500 | central-ingest §5.5 | 모든 |
| `ERR_UNSUPPORTED_MEDIA` | 415 | central-ingest §5.5 | Content-Type 위반 |
| `ERR_NOT_ACCEPTABLE` | 406 | central-ingest §5.5 | Accept 위반 |

### 7.5 CLI 전용 에러 (API 노출 없음)

| Code | 발생 CLI | 상황 | 조치 |
|------|----------|------|------|
| `ERR_ADMIN_ORDER_NOT_FOUND` | `order inspect/advance/cancel` | order_id 없음 | `order list` 로 조회 |
| `ERR_ADMIN_JOB_NOT_FOUND` | `job inspect/requeue/release-lease` | job_id 없음 | `job list` 로 조회 |
| `ERR_ADMIN_STATE_TRANSITION_ILLEGAL` | `order advance` | 요청 state 전이 불법 | 허용 state 참조 |
| `ERR_ADMIN_ORDER_TERMINAL` | `order cancel` | 이미 종결 주문 | 정보성 |
| `ERR_ADMIN_UNLINKED_UNAVAILABLE` | `unlinked reassign` | disposition != `available_for_reassignment` | `unlinked list` 로 disposition 확인 |
| `ERR_ADMIN_WRONG_ROLE` | `migrate up/down` | 일반 DSN 으로 DDL 시도 | `MIGRATION_DATABASE_URL` 사용 (central-ingest §5.5 재사용) |
| `ERR_ADMIN_USAGE` | 모든 | `--help` 참조 | — |
| `ERR_ADMIN_DB_UNAVAILABLE` | 모든 | DB 접속 실패 | DATABASE_URL 확인 |

### 7.6 Coverage

- **dev-spec §7.11 신규 24 코드**: 모두 §7.1/7.2/7.3 에 포함.
- **재사용 (상속) 14 코드**: §7.4.
- **design-side 신규 2 코드** (dev-spec 환류 필요, §14 Open Q): `ERR_DOWNLOAD_HASH_MISMATCH` (client-side 민원 트리거), `ERR_ORDER_NOT_IMPLEMENTED` (saved_filter_id 경로 501 응답용).
- **CLI 전용 8 코드**: §7.5.

---

## 8. Runbook (Incident Response)

각 runbook 은 5-part 구조: **증상 / 최초 5분 / 격리 / 복구 / 사후**. 한국어 본문. `docs/runbooks/of-RB-N.md` 로 별도 저장 권장.

### RB-OF-1 — Transfer Job DLQ Filling Up (`A-OF-2`)

```
증상: A-OF-2 — 특정 병원 DLQ 신규 진입 1h 5건 초과.
       radivault_fulfillment_transfer_job_dlq_total{hospital_id,reason} 급증.
최초 5분:
  1) fulfillment-admin job dlq-dump --since 24h --json 로 reason 분포.
  2) 병원·reason 조합 지배적이면 병원 IT 전화 (Slack/메일 금지).
  3) job list --hospital-id --state claimed 로 현재 lease 보유 수 확인.
  4) 병원의 gateway-agent transfer status 결과 공유 요청.
격리:
  5) PACS_UNAVAILABLE → 병원 PACS 점검 요청.
  6) DEID_FAILED → 병원 Gateway ruleset/salt_version 확인 (central 허용목록 대조).
  7) UPLOAD_FAILED → central-ingest 장애 의심, central RB-4/5 중첩 실행.
복구:
  8) 원인 해소 후 job requeue --reset-attempts. 병원 IT 확인 후 수행.
  9) 주문이 failed 전이되었다면 order advance --to-state queued 로 복구.
사후:
  10) 주간 3회 이상 동일 병원 DLQ → alert 격상 P1.
  11) PACS reliability 를 병원 SLA 계약에 반영.
```

### RB-OF-2 — Order Stuck in `fetching` for Hours (`A-OF-1`)

```
증상: A-OF-1 — submit→ready p95 > 2h, 또는 buyer 티켓 "몇 시간째 fetching".
최초 5분:
  1) order inspect --order-id <OID> 로 transfer_jobs 상태 확인.
  2) lease_expires_at 이 과거 15분 이상이면 Reaper 자체 이상 — job list --state claimed
     로 전체 stale lease 수 집계.
  3) Gateway transfer status 공유 요청 — TJ_ID 가 실제 처리 중인지.
격리:
  4) Gateway silent 이면 병원 IT 에 Gateway 재기동 요청.
  5) PG advisory lock 의심 시 SELECT pg_advisory_unlock(hashtext('fulfillment_lease_reaper')).
  6) long-poll 연결 수 과다 (A-OF-3) 이면 재배포.
복구:
  7) job release-lease 로 강제 lease 반환 → 다음 long-poll 재claim.
  8) buyer contact-email 로 delay 안내. 필요 시 force cancel + 재주문 크레딧 (v0.2).
사후:
  9) lease_expired_total rate 주간 리포트 추가.
  10) Gateway progress ping 주기 설정 일치 여부 monitoring 강화.
```

### RB-OF-3 — Presigned URL Mint Failures Spiking (`A-OF-9`)

```
증상: A-OF-9 — URL mint 실패율 0.5% 초과. buyer 가 502 ERR_URL_MINT_FAILED 수신.
       주문 자체는 ready_for_download 유지.
최초 5분:
  1) 로그 grep event:download.url_minted status:502 → extra.downstream 확인.
  2) AWS Health Dashboard (ap-northeast-2) S3 / KMS 공지 확인.
  3) IAM / KMS key access 최근 변경 CloudTrail 5분 점검.
격리:
  4) KMS key disabled 의심 시 KMS console 에서 즉시 enable.
  5) boto3 SigV4 실패면 node AWS_* credential refresh.
  6) DNS (s3.ap-northeast-2) 해석 실패면 VPC endpoint 재설정.
복구:
  7) 1차 복구 후 5분 A-OF-9 모니터.
  8) buyer contact-email 로 mint 지연 안내.
사후:
  9) KMS key rotation 일정 자동화.
  10) boto3 retry 내부 분해 — 재시도 로그 강화.
```

### RB-OF-4 — Buyer Reports Corrupted Downloads (sha256 Mismatch)

```
증상: Buyer 티켓 — "sha256 manifest 와 불일치". 규모 크면 저장소 이상.
최초 5분:
  1) 문제 order_id + object_key 수집.
  2) url audit --order-id 로 최근 mint 내역.
  3) S3 직접 GET + 로컬 sha256 → manifest 와 비교.
격리:
  4) S3 object corrupted 면 ingest 경로까지 역추적 (central manifest.files[].sha256 vs actual).
  5) 서명 버그 의심 시 (ResponseContentDisposition 관련) 최근 배포 롤백.
복구:
  6) 원본 유효 → 재mint 안내.
  7) 원본 corrupted → unlinked_study 이관 + 동일 코호트 재주문 크레딧.
사후:
  8) mismatch 메트릭 radivault_fulfillment_download_hash_mismatch_total 추가 (v0.1.1).
  9) buyer SDK 에 sha256 자동 검증 예제 강조 (§9 온보딩).
```

### RB-OF-5 — Buyer Quota Exhaustion Storm

```
증상: ERR_ORDER_QUOTA_EXCEEDED 429 가 단일 buyer 에서 분당 수십 건. 영업 "abuse 의심" 제보.
최초 5분:
  1) stats buyer-usage --buyer-id --period day 로 오늘 주문·에러 분포.
  2) search-admin stats top-queries 교차 점검 (metadata-index 쪽 이상 패턴).
  3) search_audit 에서 buyer RPS 패턴 확인 (metadata-index RB-2 상속).
격리:
  4) 악의적 의심 → search-admin key revoke --kid <KID>.
  5) 정당한 수요 급증 → tier 임시 상향 또는 paid 전환.
복구:
  6) 영업·법무 판정 — 악의적이면 MSA/DPA 위반 조항 발동.
  7) 정상 수요면 tier 영구 상향 + integration pattern 리뷰.
사후:
  8) "동일 filter_sha256 반복" 감지 recording rule 추가.
  9) abuse 판정 기준 문서화.
```

### RB-OF-6 — Hot Storage Hit Rate Suddenly Drops (`A-OF-5`)

```
증상: A-OF-5 — hot_storage_hit_ratio 30%+ → <5%. cold path 증가, A-OF-1 동반 가능.
최초 5분:
  1) study.central_object_present=true 100건 random 샘플 확인.
  2) 최근 배치 job 이 column 을 잘못 flip 했는지 git log.
  3) central-ingest /v1/ingest/studies 성공 시 central_object_present=TRUE 세팅 확인 (C-1).
격리:
  4) 버그 확정 → central-ingest revision 롤백.
  5) buyer 영향: cold path 지속 (기능 영향 없음, latency 증가).
복구:
  6) 수동 backfill UPDATE study SET central_object_present = TRUE WHERE object_key IS NOT NULL.
  7) hit ratio 복귀 30m 모니터.
사후:
  8) Grafana + 주간 리포트에 hit ratio 추세.
  9) hot storage auto promotion (Flow C) 일정 재검토.
```

### RB-OF-7 — Mass Expiration Event (`A-OF-11`)

```
증상: A-OF-11 — 1h 20+ 주문 expired. PR/고객 응대 비화 가능.
최초 5분:
  1) stats dlq-summary 에 동반 이상 있는지.
  2) SELECT buyer_pk, count(*) FROM order WHERE status='expired' AND expired_at > now()-1h GROUP BY 1.
  3) 원인 분류 — (a) buyer download 놓침, (b) buyer ETL 실패, (c) S3 Lifecycle rule 버그.
격리:
  4) (a) buyer 통지. (b) buyer ETL 의 동기화 문제. (c) staging/ prefix TTL 검증.
복구:
  5) staging/ Lifecycle 삭제 전이라면 order advance 로 re-ready 복구. +1d 이후 불가.
  6) buyer contact-email 건별 사과 + 재주문 안내.
사후:
  7) 만료 T-3d/T-1d 이메일 알림 (v0.1.1 notifications-worker).
  8) 영업 교육 자료 업데이트.
```

### RB-OF-8 — S3 Outage During Active Orders

```
증상: AWS S3 ap-northeast-2 장애 + A-OF-6 다운로드 5xx 급증. in-flight 다운로드 실패.
최초 5분:
  1) AWS Health Dashboard 확인, ETA.
  2) /readyz 가 S3 포함 여부에 따라 서비스 전체 503 vs 부분 가용.
  3) buyer 공지 (status page) 업데이트.
격리:
  4) 신규 URL mint 실패. 발급된 URL 은 S3 상태 의존.
  5) 주문 접수는 계속 (PG/Redis 만 의존). cold path upload 는 지연.
복구:
  6) S3 회복 후 buyer 에게 재mint 공지.
  7) ready 주문의 expires_at 을 장애 시간만큼 연장 (v0.1.1 extend-ttl 백로그).
사후:
  8) multi-region replication 검토 (v0.2).
  9) buyer SDK 의 retry/backoff 전략 가이드 업데이트.
```

---

## 9. Buyer Onboarding Walkthrough

**대상**: **RadiVault 영업·세일즈 엔지니어 ↔ 버이어 통합 엔지니어 / 데이터 사이언티스트 공동 수행**. metadata-index 온보딩 §7 의 **연장선** — 검색을 끝낸 buyer 가 **실제로 영상을 주문하고 다운로드** 하는 최초 경로. 소요: 첫 다운로드까지 **60 분 이내** (metadata-index 가 완료된 가정). 언어: **영어 우선** (buyer 대상). curl 샘플 포함.

### 9.1 전체 플로우 ASCII

```
[Pre]    (0) metadata-index onboarding 완료 — preview/paid key 확보, 첫 코호트 탐색
           │
           ▼
[Buyer]  (1) Evaluate cohort — pick 3 studies via search → record pseudo_study_uids
           │
           ▼
[Buyer]  (2) Create first order — POST /v1/orders (curl)
           │
           ▼
[Buyer]  (3) Poll state — loop GET /v1/orders/{id} until ready_for_download
           │
           ▼
[Buyer]  (4) Get download URLs — POST /v1/orders/{id}/download-urls
           │
           ▼
[Buyer]  (5) Download + verify sha256 (parallel, httpx)
           │
           ▼
[Buyer]  (6) Wait 24h+ to see URL expiry — attempt GET → 403 (signature expired)
           │
           ▼
[Buyer]  (7) Refresh URLs — re-mint same endpoint, verify fresh signature
           │
           ▼
[Buyer]  (8) Cancel a test order — POST /v1/orders/{id}/cancel (queued state)
           │
           ▼
[Buyer]  (9) Inspect total_estimated_usd — read billing preview stub
           │
           ▼
[Joint]  (10) Sales follow-up — upgrade to paid tier, discuss production integration
```

### 9.2 단계별 상세 (각 단계 ≥ 1 curl 예시)

**Step 1 — Evaluate cohort via metadata-index search**

```bash
export RV_KEY="rv_live_abcd1234_Zj8..."
curl -sS -X POST https://search.radivault.io/v1/search/studies \
  -H "Authorization: Bearer $RV_KEY" \
  -H "Content-Type: application/json" \
  -d '{"modality":["CT"],"body_part":["CHEST"],"limit":3}' \
  | jq '.items[].pseudo_study_uid'
# "2.25.140737488355328.1.2.3"
# "2.25.140737488355328.1.2.4"
# "2.25.140737488355328.1.2.5"
```

**Step 2 — Create first order**

```bash
# MSA sha256 is provided by RadiVault at contract signing
MSA_HASH="abcd1234ef5678901234567890abcdef1234567890abcdef1234567890abcdef"
IDEM_KEY="$(uuidgen)"

curl -sS -X POST https://fulfillment.radivault.io/v1/orders \
  -H "Authorization: Bearer $RV_KEY" \
  -H "Idempotency-Key: $IDEM_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"pseudo_study_uids\": [
      \"2.25.140737488355328.1.2.3\",
      \"2.25.140737488355328.1.2.4\",
      \"2.25.140737488355328.1.2.5\"
    ],
    \"agreement_hash\": \"$MSA_HASH\",
    \"notes\": \"first-order onboarding test\",
    \"preferred_download_ttl_hours\": 48
  }"
# → 202 Accepted, {"order_id":"ord_01HXX...","state":"queued","estimated_ready_at":"...","n_studies":3,"total_estimated_usd":15.0, ...}
export ORDER_ID="ord_01HXX..."
```

**Step 3 — Poll state until ready**

```bash
while true; do
  R=$(curl -sS -H "Authorization: Bearer $RV_KEY" \
        https://fulfillment.radivault.io/v1/orders/$ORDER_ID)
  STATE=$(echo "$R" | jq -r .state)
  echo "$(date -u +%H:%M:%S) state=$STATE progress=$(echo $R | jq -r .progress)"
  case "$STATE" in
    ready_for_download) break ;;
    expired|cancelled|failed) echo "Terminal: $STATE — check last_error"; exit 1 ;;
    *) sleep 5 ;;
  esac
done
```

**Step 4 — Get download URLs**

```bash
curl -sS -X POST https://fulfillment.radivault.io/v1/orders/$ORDER_ID/download-urls \
  -H "Authorization: Bearer $RV_KEY" \
  -H "Content-Type: application/json" \
  -d '{"ttl_seconds": 86400}' \
  > manifest.json
jq '{n_files: .n_files, total_bytes: .total_bytes, expires_at: .expires_at}' manifest.json
# {"n_files":512,"total_bytes":282963036,"expires_at":"2026-04-23T10:05:31Z"}
```

**Step 5 — Download + verify sha256 (parallel)**

Python snippet from §2.5 — `asyncio.run(download_all(json.load(open("manifest.json")), pathlib.Path("./dicoms"), concurrency=16))`.

**Step 6 — Wait 24h+ to see URL expiry**

```bash
# after 24h
curl -sSI "$(jq -r '.items[0].files[0].url' manifest.json)" | head -1
# HTTP/1.1 403 Forbidden — X-Amz-Expires exceeded
```

**Step 7 — Refresh URLs (re-mint)**

```bash
# order is still ready_for_download (within 7d window)
curl -sS -X POST https://fulfillment.radivault.io/v1/orders/$ORDER_ID/download-urls \
  -H "Authorization: Bearer $RV_KEY" \
  -H "Content-Type: application/json" \
  -d '{"ttl_seconds": 86400}' \
  > manifest_v2.json
# fresh signatures — different X-Amz-Signature from manifest.json
```

**Step 8 — Cancel a test order (queued state)**

```bash
# submit a new order then cancel before fetching begins
TEST_ORDER=$(curl -sS -X POST https://fulfillment.radivault.io/v1/orders \
  -H "Authorization: Bearer $RV_KEY" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d "{\"pseudo_study_uids\":[\"2.25.xxx\"],\"agreement_hash\":\"$MSA_HASH\"}" \
  | jq -r .order_id)

sleep 1   # immediately cancel while queued

curl -sS -X POST https://fulfillment.radivault.io/v1/orders/$TEST_ORDER/cancel \
  -H "Authorization: Bearer $RV_KEY" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"reason":"onboarding test cancel"}'
# → 200 {"order_id":"...","state":"cancelled","cancelled_at":"...","refund_eligible":false}
```

**Step 9 — Inspect billing preview stub**

```bash
curl -sS -H "Authorization: Bearer $RV_KEY" \
  https://fulfillment.radivault.io/v1/orders/$ORDER_ID \
  | jq '{total_usd: .total_estimated_usd, billing: .state_billing}'
# {"total_usd":15.0,"billing":"pending_billing"}
```

> v0.1 note: `pending_billing` means **no charge is posted yet**. Preview tier is free; paid tier issues a `pending_billing` entry for future settlement when billing ships in v0.2.

**Step 10 — Sales follow-up → paid upgrade**

RadiVault 영업이 사용량 리포트 (`fulfillment-admin stats buyer-usage`) 를 공유하며 paid 전환 제안. Paid tier:
- cohort cap: 50 → 10,000
- daily orders: 5 → 50
- max URL TTL: 24h → 7d
- max_order_bytes: 10 GB → 2 TB

### 9.3 KPI — "time-to-first-download"

| Milestone | Target |
|-----------|--------|
| Step 2 (order create) 응답 | < 2s |
| Step 3 (ready_for_download) 도달 — hot-path 3 studies | < 30s p95 |
| Step 4 (URL mint) 응답 | < 1s |
| Step 5 (parallel download 1GB) 완료 | < 120s (buyer 네트워크 100 Mbps+) |
| 전체 (Step 2 → Step 5 완료) | < 5 min |

### 9.4 Rollback

```
1. fulfillment-admin order cancel --order-id <OID> --admin-reason "onboarding rollback"
2. (optional) search-admin key revoke --kid <KID> --reason "rollback-onboarding"
3. audit 로그 보존. cleanup 은 자동 Lifecycle rule 에 의해 +8d 삭제.
```

---

## 10. Hospital / Gateway Onboarding Delta

기존 `design-spec-gateway-agent §7` 온보딩에 **`transfer` 서브시스템 활성화** 단계를 추가. 한국어 (병원 IT 담당자 대상). Flow A (central-ingest) 온보딩이 이미 완료된 병원에 대해 실행.

### 10.1 전체 델타 플로우

```
[Pre]    (A) Flow A (central-ingest) 온보딩 완료 — 토큰·ruleset·첫 anchor 수신 GA
           │
           ▼
[SRE]    (B) Fulfillment 서비스 URL 공유                ─ 내부 공지·이메일
           │
           ▼
[Hosp]   (C) gateway.yml 에 transfer: 섹션 추가
           │
           ▼
[Joint]  (D) transfer test 드라이런 — 1회 claim → complete 사이클
           │
           ▼
[Hosp]   (E) transfer start 데몬 병렬 기동 (Flow A 와 분리 프로세스)
           │
           ▼
[SRE]    (F) Central 측 검증 — 첫 주문 이행 관찰
           │
           ▼
[Post]   (G) 24h Soak → 알람 없으면 transfer GA 목록 추가
```

### 10.2 단계별 상세

**Step B — Fulfillment URL 공유 (RadiVault SRE → 병원 IT)**

- URL: `https://fulfillment.radivault.io`
- 요구: outbound 443 only, inbound 없음. (방화벽 규칙은 기존 central-ingest 와 동일)
- 공지 문구: "주문 이행 pull 엔드포인트. 기존 upload 토큰 재사용. Flow A 와 병렬 데몬."

**Step C — gateway.yml 에 `transfer:` 섹션 추가 (병원 IT)**

```yaml
# /etc/radivault/gateway.yml  — 추가분만
transfer:
  enabled: true
  central_url: "https://fulfillment.radivault.io"
  # 기존 central.upload_token 재사용 가능 (dev-spec §6.6)
  auth_token: "${file:/run/credentials/upload_token}"
  poll_wait_seconds: 30
  max_concurrent_jobs: 2
  lease_extend_interval_seconds: 300      # 5 min
  progress_report_interval_seconds: 60    # 1 min
  retry_backoff_initial_seconds: 30
  retry_backoff_factor: 2
  retry_backoff_cap_seconds: 600
```

검증 (병원 IT):

```
$ gateway-agent version
gateway-agent 0.1.0 build ab12cd34 ruleset v0.1.0 ...
  # v0.1.1 이상 — transfer 서브커맨드 지원 확인

$ gateway-agent transfer --help
# transfer start / status / test 서브커맨드가 나타나야 함
```

**Step D — transfer test 드라이런 (병원 IT + RadiVault SRE 동시 관찰)**

병원 IT:

```
$ gateway-agent transfer test --fulfillment-url https://fulfillment.radivault.io
[STEP 1/4] long-poll ...
```

RadiVault SRE 병행 (별도 터미널):

```
$ fulfillment-admin job list --hospital-id hosp_abc --state claimed
# 테스트 주문이 전달되며 claim 확인
```

**기대**: STEP 4/4 `CYCLE OK` 출력.
**실패 시**:
- STEP 1/4 에서 204 → 테스트용 주문을 SRE 가 먼저 생성 (파일럿 internal buyer key 로).
- STEP 1/4 에서 401 → `transfer.auth_token` 이 `central.upload_token` 과 다르면 다시 맞춤.

**Step E — transfer start 데몬 병렬 기동 (병원 IT)**

```
$ docker compose logs -f gateway-agent
# Flow A 는 continue

# 별도 단위 (systemd unit 또는 compose service 추가):
$ docker compose run -d --name gateway-agent-transfer \
    gateway-agent transfer start
# 또는 systemd:
$ sudo systemctl enable --now radivault-gateway-transfer.service
```

**주의**: Flow A 와 Flow B 는 **PACS 최대 동시 페치 한도** (`pacs.max_concurrency=4`) 를 공유. 기본 2+2=4 분배 — Flow A 가 2, Flow B 가 2. 변경 시 양측 config 협의.

**Step F — Central 측 검증 (RadiVault SRE)**

```
$ fulfillment-admin job list --hospital-id hosp_abc --state claimed --limit 5
# 병원이 job 을 claim 하고 있는지 실시간 확인

$ fulfillment-admin order inspect --order-id <test OID>
# staging_complete 까지 전이 관찰
```

**Step G — 24h Soak**

- P2 이상 알람 (A-OF-1..A-OF-12) 없으면 transfer GA 병원 리스트에 포함.
- `radivault_fulfillment_transfer_jobs_total{hospital_id=X,final_state="completed"}` 추세 확인.

### 10.3 롤백

```
1. gateway.yml 에서 transfer.enabled = false
2. docker compose stop gateway-agent-transfer (또는 systemctl stop)
3. Flow A 는 계속 운영 — 영향 없음
```

Central 측은 해당 hospital_id 의 transfer_job 을 자동으로 queue 에 유지 → 병원이 재활성화하면 자동으로 재claim.

---

## 11. 국제화 (i18n)

| 표면 | 언어 | 근거 |
|------|------|------|
| Buyer API (envelope body) | `message_en` 우선 + `message_ko` 병기 (central-ingest §2.2 그대로) | buyer 는 글로벌 기업 (영어 first) |
| Buyer OpenAPI / docs / curl 예제 | **영어** (metadata-index §8 상속) | 외부 공개 |
| Buyer onboarding walkthrough (§9) | **영어** | 동일 이유 |
| Gateway API (envelope body) | `message_en` 우선 + `message_ko` 병기 | 기계 계약 (ko 는 병원 IT 로그 복사용) |
| Hospital / Gateway onboarding (§10) | **한국어** (gateway-agent design-spec §7 상속) | 병원 IT 담당자 모국어 |
| Admin CLI (`fulfillment-admin`) `--help` | **영어** | SRE·자동화 친화 |
| Admin CLI 실행 출력 (박스) | 영어 기본, `--lang ko` optional (v0.1 optional) | 일관성 |
| JSON 로그 | **영어 전용** (+ `message_ko` + `message_en` 필드 동반) | 중앙 집계·규제 보존 |
| Runbook 본문 (§8) | **한국어** | SRE 모국어 |
| Error doc (`docs.radivault.io/fulfillment/errors/*`) | v0.1 영어 우선, 한국어 병기 | 장기적 공개 |

**한국어 길이 규칙** (central-ingest §8 상속): `message_ko` ≤ 120 bytes. 초과 시 마침표 앞 `…` + `doc_url` 참조 유도.

**시간대**: API 응답 JSON 은 UTC ISO8601. Runbook·CLI 콘솔은 KST. CLI `--json` 모드는 UTC.

---

## 12. 접근성 (Accessibility)

| 항목 | 적용 |
|------|------|
| 색 의존 금지 | CLI 색은 보조만, `--no-color` / `NO_COLOR=1` 준수. 로그 JSON·Prometheus 는 색 없음. |
| 스크린리더 | CLI 출력은 라인 기반 — 리더 친화. `fulfillment-admin order inspect` 의 박스 장식 (`═`) 은 `--plain` 으로 ASCII (`=`) 폴백. |
| 키보드 | CLI 전용 — 원천 키보드. |
| UTF-8 | 기본 UTF-8, `LANG=C` 에서 ASCII 폴백. |
| WCAG 색 대비 4.5:1 | **N/A — backend service**: 시각 UI 없음. Grafana 대시보드는 별도 dashboard-spec. |
| 반응형 | **N/A — backend service**: 뷰포트 없음. CLI 는 80열 가로 스크롤 금지. |
| 디자인 토큰 (색·간격) | **N/A — backend service**: "메트릭 네이밍 규약"·"에러 코드 네임스페이스" 가 equivalent. |
| 포커스 관리 | N/A. |

---

## 13. 수용 기준 (Acceptance Criteria — 디자인 측)

총 **22 개**. `@qa` 가 라인별 바이너리 검증.

- [ ] **AC-D-OF-1** (envelope) dev-spec §7 모든 엔드포인트 (POST /v1/orders, GET /v1/orders, GET /v1/orders/{id}, POST /cancel, POST /download-urls, GET /v1/gateway/transfer-jobs, POST /progress, POST /complete, POST /fail, /healthz, /readyz, /v1/version) 가 §2.1 표준 에러 envelope 의 5 필수 + 2 optional 필드를 포함한 에러 응답을 문서화.
- [ ] **AC-D-OF-2** (에러 coverage) dev-spec §7.11 의 신규 24 에러 코드 전부 + 재사용 14 코드 전부 가 §7 Error Taxonomy 표에 등장. 누락 0 건.
- [ ] **AC-D-OF-3** (bilingual) 모든 4xx/5xx 응답이 `message_ko` + `message_en` 동시 포함. lint 실패 없음.
- [ ] **AC-D-OF-4** (CLI) `fulfillment-admin` 서브커맨드 전체 (order/job/url/stats/unlinked/migrate/version 트리 — 최소 16개 명령) 가 `--help` 구현. 출력이 §4 Usage/Options/Exit codes 구조와 일치.
- [ ] **AC-D-OF-5** (Gateway CLI delta) `gateway-agent transfer {start|status|test}` 3종이 `--help` + exit codes 구현. 기존 Gateway CLI 계약 변화 없음 (additive).
- [ ] **AC-D-OF-6** (state semantics) OpenAPI description 에 §2.3 의 12-state plain-English 표 및 ASCII state diagram 이 포함.
- [ ] **AC-D-OF-7** (polling sample) §2.4 curl polling 샘플이 공식 Postman 컬렉션 / Quickstart 에 포함.
- [ ] **AC-D-OF-8** (download manifest) `POST /download-urls` 응답에 `items[].files[]` 마다 `object_key`, `bytes`, `sha256` (64 hex lowercase), `url` (SigV4 full URL) 4 필드 모두 포함.
- [ ] **AC-D-OF-9** (refresh contract) 같은 주문에 `POST /download-urls` 3 회 호출 → 매번 다른 signature. 이전 URL 들은 자체 TTL 까지 유효 (문서에 revocation 불가 명시).
- [ ] **AC-D-OF-10** (idempotency) 동일 `(buyer_pk, Idempotency-Key, payload sha256)` 재전송 → 저장된 응답 + `Idempotency-Replayed: true`. 다른 payload 동일 key → `409 ERR_IDEMP_MISMATCH`.
- [ ] **AC-D-OF-11** (long-poll) `GET /v1/gateway/transfer-jobs?wait=30s` 가 queue empty 시 30s 이내 `204 No Content` + `Retry-After: 0`. queue 새 job 시 Redis pub/sub 로 < 200ms 내 200 반환.
- [ ] **AC-D-OF-12** (lease) progress 호출 시 lease_extend=true 면 `lease_expires_at = now() + 15m`. counters 감소 시 `400 ERR_JOB_COUNTER_REGRESS`.
- [ ] **AC-D-OF-13** (JSON logs) §6.2 6-line 예시 이벤트 6종 (`order.created`, `job.claimed`, `job.progress`, `job.completed`, `download.url_minted`, `order.expired`) 모두 실제 구현에서 동일 shape 방출.
- [ ] **AC-D-OF-14** (Prometheus 네이밍) `/metrics` 에 노출되는 모든 RadiVault 고유 메트릭이 `radivault_fulfillment_*` 접두사 사용. 최소 16개 메트릭 노출 (§6.3).
- [ ] **AC-D-OF-15** (Alert) §6.4 알람 12건 모두 Alertmanager rule 파일로 정의. 임계가 구체 숫자 (추상 "high" 금지).
- [ ] **AC-D-OF-16** (runbooks) RB-OF-1..RB-OF-8 각 runbook 이 증상·최초5분·격리·복구·사후 5 섹션 포함. 본 문서 요약 + `docs/runbooks/of-RB-N.md` 파일 존재.
- [ ] **AC-D-OF-17** (PHI 차단) 로그 sanitiser 가 §6.1 금지 필드 감지 시 레코드 drop + `ERR_LOG_PHI_DETECTED` 카운터 증가. CI 테스트 green.
- [ ] **AC-D-OF-18** (buyer onboarding) §9 의 10 단계를 따라가면 파일럿 buyer 1곳이 외부 문서 참조 없이 첫 주문 → 첫 다운로드 → sha256 검증 완료.
- [ ] **AC-D-OF-19** (hospital onboarding) §10 의 7 단계를 따라가면 파일럿 병원 1 곳이 외부 문서 참조 없이 transfer 서브시스템 활성화 → 첫 주문 이행 완료.
- [ ] **AC-D-OF-20** (rate-limit headers) 모든 성공 응답 및 429 에 `X-RateLimit-*`·`X-Quota-*`·`Idempotency-Replayed`·`X-Request-Id` 헤더 포함 (§2.9).
- [ ] **AC-D-OF-21** (doc_url) 모든 에러 응답이 `doc_url` 필드 포함. v0.1 에서 해당 URL 404 허용 (central-ingest §11-1 예외 승계).
- [ ] **AC-D-OF-22** (Gateway breaking none) 본 디자인 구현 후 기존 Gateway Flow A (central-ingest 상시 수집) 회귀 테스트 green — `transfer.enabled=false` 상태에서 기존 Gateway 계약 변화 없음.

---

## 14. 오픈 질문 (Open Questions)

Kyle 결정 또는 외부 확인 필요. dev-spec §11 의 12 개 와 중복되지 않는 **design 측 고유 이슈** 중심으로 기재 (dev-spec 측 open question 은 별도 채널).

1. **saved_filter_id 경로 API-stable vs removed** — §2.2 (B) 에서 언급한 미래 경로를 v0.1 에서 "501 ERR_NOT_IMPLEMENTED" 로 예약할지, 아니면 schema 에서 아예 제거할지. **권고**: 예약 (미래 쿼리 안정성).
2. **`ERR_DOWNLOAD_HASH_MISMATCH` dev-spec 환류** — 본 디자인에서 추가한 client-side 민원 코드. v0.1 은 문서화만, v0.1.1 에서 서버 측 감지 + 401/502 응답 코드로 승격 여부.
3. **CLI 바이너리 명칭** — `fulfillment-admin` vs `radivault-fulfillment`. central-ingest 는 `ingest-admin` 으로 짧음을 택함. 본 디자인은 전자 채택. Kyle 확정.
4. **`X-Quota-*` 헤더 이름 표준화** — metadata-index 와 동일 이름 사용 vs fulfillment 도메인 접두사 추가. 공유 SDK 에서 **동일 이름** 권고 (현재 선택).
5. **`Idempotency-Replayed` 헤더 케이스** — 소문자 vs 대소 혼합 (HTTP 헤더는 case-insensitive 이지만 테스트·docs 일관성 필요). central-ingest 결정 (`Idempotency-Replayed`) 그대로 채택.
6. **`X-Original-Request-Id` 헤더 채택** — replay 시 원본 추적. central-ingest §11-6 결정 승계 — 채택.
7. **CORS 기본값** — v0.1 `enabled: false` 권고. 세일즈가 프로스펙트 대시보드 enable 요청 시 proceed.
8. **Download URL refresh 무제한 정책** — 현재 주문 수명 7d 내 mint 무제한. 영업 악용 가능성 — 24h 내 mint 100회 등 secondary rate-limit 필요 여부.
9. **sha256 알파벳 대소문자** — API 응답·CLI·문서 모두 lowercase 로 강제. 테스트 케이스 포함.
10. **URL `ResponseContentDisposition` 파일명 형식** — `<pseudo_sop_uid>.dcm` 고정 (dev-spec FR-63). buyer 가 원본 filename 요구하면 거부 (재식별 방지).
11. **Alert severity (P1/P2/P3) PagerDuty 매핑** — central-ingest §11-11 와 동일 이슈 — SRE 팀 내부 표준 확정.
12. **Runbook 저장 위치** — `docs/runbooks/of-RB-N.md` 파일 분리 vs 본 문서 inline. central-ingest §11-8 와 동일 — 분리 권고.
13. **`fulfillment-admin unlinked reassign` 자동화** — v0.1 은 수동 CLI. v0.1.1 에서 orphan detector + auto-match 여부.
14. **Gateway v0.1.1 `transfer` 서브시스템 트랙 착수 시점** — Central fulfillment v0.1 GA 에 필수 선행. dev-spec §14 G-1 타임라인 확정 필요.
15. **Mass expiration 통지** — v0.1 은 통지 없음 (buyer 책임). v0.1.1 notifications-worker 가 T-3d/T-1d webhook 발송 여부.
16. **`pending_billing` 표시 문구** — OpenAPI 에서 "No charge is posted in v0.1" 명시 여부. 법무 검토.
17. **Status page 운영** — `status.radivault.io` — S3 장애 시 실시간 공지 채널. v0.1 MVP 여부.
18. **Postman collection / SDK 배포 일정** — metadata-index 온보딩과 번들 vs 별도.

---

## 15. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-22 | @designer (Claude Opus 4.7) | 최초 작성. buyer-facing HTTP API DX (주문 생성/조회/취소/다운로드 envelope · 12-state plain-English · polling 패턴 · manifest shape · URL refresh 계약 · 취소 UX · 5 에러 예시 · rate-limit+quota 헤더 · Idempotency · Content-Type · CORS · 버전) + Gateway-facing M2M UX (long-poll 의미·progress·completion·failure·Bearer 스코프) + `fulfillment-admin` CLI 16+ 명령 · `gateway-agent transfer *` 3 명령 · JSON 로그 schema + Prometheus 17 메트릭 · 12 알람 + Error taxonomy 24 신규 + 14 재사용 + 8 CLI 전용 + Runbook 8편 (RB-OF-1..8) + Buyer onboarding 10단계 (영어 curl) + Hospital/Gateway onboarding delta 7단계 (한국어). design-spec-central-ingest envelope · 에러 taxonomy · runbook 포맷 상속. design-spec-metadata-index buyer DX · cursor opaque · `X-RateLimit-*`/`X-Quota-*` 헤더 상속. dev-spec §7.11 24 신규 코드 전수 커버 + design-side 2 신규 (ERR_DOWNLOAD_HASH_MISMATCH, ERR_ORDER_NOT_IMPLEMENTED). 시각 섹션 N/A — backend service. |

---

### NEXT_STEP

- 완료 산출물: `docs/specs/design-spec-order-fulfillment.md` (v0.1 Draft)
- 제안 다음 단계: **@developer** — `claude` 브랜치에서 `radivault_fulfillment` 서비스 구현 착수 (dev-spec + 본 design-spec 동시 참조).
  - 본 디자인 §2 HTTP API UX (envelope + bilingual), §3 Gateway M2M 계약, §4 `fulfillment-admin` CLI, §5 `gateway-agent transfer *` 확장, §6 로그·메트릭 네이밍, §7 에러 taxonomy, §8 runbook (`docs/runbooks/of-RB-N.md` 파일 분리 권고), §9-10 온보딩을 구현 기준으로 반영.
  - **Gateway 기존 계약 breaking 없음 확인** — `transfer.enabled=false` 기본값에서 Flow A 회귀 테스트 전 구간 green 필수.
- UI_GUIDE.md 갱신 제안: "부록: CLI 도구 공통 가이드"·"HTTP API 공통 가이드" 에 **주문·다운로드 도메인 고유** 4개 항목 추가 — ① 12-state plain-English 네이밍 · ② URL refresh (revocation 불가) 문구 · ③ Idempotency-Key 강제 범위 (POST /v1/orders) · ④ download manifest sha256 lowercase 강제. 정식 편입은 Kyle 승인 후.
- 추가 디자인 필요:
  - (a) **buyer-portal-web v0.2** — API-only v0.1 에 React UI 붙이는 별도 slug. 본 §2 의 envelope/state/refresh 를 그대로 visualization.
  - (b) **billing-revenue-share v0.2** — `total_estimated_usd`·`download_event` ETL 기반 매출 리포트 대시보드.
  - (c) **운영자 Grafana 대시보드** — 본 §6.3 메트릭 17종을 3 보드 (Order Lifecycle / Transfer Jobs / Downloads) 로 레이아웃 — 별도 dashboard-spec.
- Kyle 결정 필요 사항 (§14 요약):
  1. saved_filter_id 501 예약 여부.
  2. `ERR_DOWNLOAD_HASH_MISMATCH` dev-spec 환류.
  3. CLI 바이너리 명칭 확정 (`fulfillment-admin`).
  4. CORS 기본값 deny 승인.
  5. URL refresh 무제한 vs secondary rate-limit.
  6. Unlinked 자동 재할당 도입 시점.
  7. Gateway v0.1.1 `transfer` 서브시스템 트랙 착수 시점.
  8. Mass expiration 통지 도입 시점.
  9. `pending_billing` 법무 검토.
  10. Status page 도입 시점.
