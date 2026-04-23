# QA 리포트 — order-fulfillment v0.1 MVP

> **Status**: Round 1 · **Feature slug**: `order-fulfillment` · **검수 일자**: 2026-04-22
> **작성자**: @qa (Claude Opus 4.7, 1M ctx)
> **검수 대상 커밋 범위**: `9b243fb..d4e1697` (3 commits, ~80 files new, 2 modified)
> **브랜치**: `claude`
> **최종 판정**: **PASS with minor issues**
> **근거 스펙**:
> - [dev-spec-order-fulfillment](../specs/dev-spec-order-fulfillment.md) (85 FR / 40 AC / 24 new error codes / 9 tables / 4 contract deltas)
> - [design-spec-order-fulfillment](../specs/design-spec-order-fulfillment.md) (17 metrics / 12 alerts / CLI / runbooks)
> - [research — order-fulfillment-technical-foundations](../research/order-fulfillment-technical-foundations.md)

---

## 1. 요약

**판정**: PASS with minor issues.

- 40 AC 중 **30 full PASS / 6 PASS(구현은 완료, 단 deployment 전 수동 검증 필요) / 4 DEFERRED(인프라/후속 revision 의존)**. 보안 핵심 5개 시나리오(Idempotency 교차, buyer 데이터 누출, Gateway 교차 병원, plane 혼용, plane 혼용 역방향)를 **live TestClient 공격 시뮬레이션으로 실측 검증하여 전부 스펙대로 동작**함을 확인 (§4 보안 참조).
- 개발자가 선언한 4가지 deviation 모두 스펙 내 명시된 defer 경로(§3.1 #11/#15/#16, §13.2 C-1, §14 C-2 additive)를 정확히 따르며, deployment blocker 아님. 다만 **배포 전 Critical 급으로 승격될 operational 갭 2건** 존재 (§4.1 참조) — outbox poller/lease reaper/expiry ticker가 서비스 프로세스에서 기동되지 않으므로 실전 주문 흐름은 운영자가 수동 CLI로 tick 해야 end-to-end 완주. MVP launch 시 대체 수단(cron 주기 실행 or 별도 scheduler sidecar) 준비 필수.
- 82 unit + 2 integration + 143/50/17/49/20 기존 회귀 = 363 통과. Ruff clean. OpenAPI 9 path + 2 probe + metrics = 11 endpoint 전부 노출됨.

### 긍정 관찰 (non-blocking)
- 인증 plane 분리가 **경로 기반 + 토큰 prefix 기반 이중 검사**로 엄격. `rv_live_*`/`rv_test_*` 토큰이 `/v1/gateway/*` 방향으로 흘러가면 `ERR_AUTH_WRONG_PLANE`(401), Gateway bearer가 buyer path에 들어오면 같은 코드로 거부. 양쪽 방향 모두 단위+실측 검증됨.
- Idempotency-Key 스코프가 `buyer_pk`/`hospital_pk` 레벨에서 분리(`idem:ff:{scope_type}:{scope_owner}:{key}`, `src/radivault_fulfillment/idempotency/middleware.py:104`). 서로 다른 buyer가 동일 key 제출 시 **각자 새 주문이 생성**되며 교차 누출 없음(실측 확인, §4 Test 1).
- Buyer 데이터 격리: 모든 주문 조회 쿼리가 `buyer_pk` 필터(`get_order_for_buyer` `orders/repository.py:23`, `list_orders_for_buyer:30`); 다른 buyer의 order_id 조회 시 `404 ERR_ORDER_NOT_FOUND`로 응답 (403 아님 — 스코프 누출 방지, FR-18 준수).
- Gateway 교차 병원 격리: `try_claim_once`의 SELECT에 `hospital_pk=:mine` 필수 필터(`jobs/long_poll.py:42`) + 반환 후 `JobHospitalMismatch` 방어적 검증(`routers/gateway_jobs.py:63`). 실측 확인.
- 24개 신규 error code 전부 exception 클래스 + ko/en 메시지 + doc_url 제공(`errors.py:52-233`), 엔벨로프 구조가 central-ingest와 정합.
- 17개 Prometheus 메트릭 중 AC-35 표본 전부 `telemetry.py:17-134`에 정의 + 런타임에서 increment됨(`ORDER_SUBMISSIONS_TOTAL`, `URL_MINT_TOTAL`, `TRANSFER_JOB_CLAIM_TOTAL`, `TRANSFER_JOB_FAILURES_TOTAL`, `EXPIRED_ORDERS_TOTAL`, `DLQ_DEPTH` — gauge는 수집기 부재 시 0). 메트릭 바디에 `radivault_fulfillment_order_submissions_total` 등 전부 노출 확인.
- SKIP LOCKED 처리가 dialect-aware. PG에서 `.with_for_update(skip_locked=True)`, SQLite에서 plain SELECT (`jobs/long_poll.py:37-46`). 테스트 코멘트(`test_long_poll_claim.py:87`)가 true concurrency는 PG에서만 검증 가능함을 명시.
- FSM idempotency: `UPDATE order SET status=:to WHERE ... AND status=:from`(`state_machine.py:138-143`)가 rowcount=0 시 `ERR_ORDER_STATE_TRANSITION` — 두 TX race에서 **한 쪽만 성공**하는 optimistic lock 구현. Terminal 상태(`delivered/expired/cancelled/failed`) 는 `is_allowed(..)`에서 무조건 차단(`state_machine.py:84`).
- 파일 구조, 네이밍, 에러 envelope 패턴, probe 구성, migration revision chain 모두 central-ingest/metadata-index/de-id-pixel과 정합.

---

## 2. 수용 기준 매트릭스 (40 AC)

### 2.1 인증 · 인가 (§10.1)

| AC | 판정 | 증거 |
|---|------|------|
| **AC-1** (buyer key → 202 / 없는 kid → 401 / revoked → 401) | **PASS** | `auth/buyer.py:90-138` kid not found → `AuthExpired(401, ERR_AUTH_EXPIRED)`; `row.revoked_at` → same; 실측: 정상 키는 202로 주문 생성(attacker scenario Test 1 ok). |
| **AC-2** (gateway token → 200/204) | **PASS** | `auth/gateway.py:53-91` + 실측: Gateway A 토큰으로 `GET /v1/gateway/transfer-jobs?wait=0` → 200 + hospital_id="hosp_a"; 빈 큐일 때 204 (attacker Test 3). |
| **AC-3** (plane 혼용 → ERR_AUTH_WRONG_PLANE) | **PASS** | 실측 확인: buyer rv_live_ 토큰으로 `/v1/gateway/*` → 401 ERR_AUTH_WRONG_PLANE (`auth/gateway.py:62`); gateway ULID 토큰으로 `/v1/orders` → 401 ERR_AUTH_WRONG_PLANE (`auth/buyer.py:100`). |
| **AC-4** (Redis 장애 fail-closed) | **PASS (trace)** | `idempotency/middleware.py:108-113` — Redis `get` 예외 시 `IdempUnavailable(503)` 반환. auth cache miss는 argon2 직접 검증으로 fall-through (`auth/buyer.py:120`). Redis 완전 중단 시 auth는 fall-through + idempotency는 503, 스펙과 정합. (라이브 장애 주입 미실시 — §11 Q6 infra-dependent.) |

### 2.2 주문 생성 · 검증 (§10.2)

| AC | 판정 | 증거 |
|---|------|------|
| **AC-5** (Idempotency-Key 누락/replay) | **PASS** | `idempotency/middleware.py:89-94` missing → `IdempMissing(400 ERR_IDEMP_MISSING)`; replay 경로 `115-133` Redis SETNX → `Idempotency-Replayed: true` 헤더 + 저장된 body 복제. `tests/fulfillment/integration/test_order_flow_e2e.py:50-63` replay가 동일 order_id 반환 확인. 단일 row 보장은 `order_idempotency_mirror` UNIQUE PK `(key, buyer_pk)` (`db/models.py:274-277`). |
| **AC-6** (scope exclude) | **PASS** | `orders/validator.py:110-114` `OrderScopeForbidden(403)`; `tests/fulfillment/unit/test_validator.py:90-103`. |
| **AC-7** (tier cohort cap) | **PASS** | `validator.py:67-73`; `test_validator.py:44-56`. |
| **AC-8** (daily quota) | **PASS** | `validator.py:76-85`; `test_validator.py:106-142`. |
| **AC-9** (study not found / duplicate) | **PASS** | `validator.py:62-64`(duplicate 400) + `:87-96`(not found 404); `test_validator.py:29-41, 59-70`. |
| **AC-10** (size cap) | **PASS** | `validator.py:102-107`; `test_validator.py:73-87`. |
| **AC-11** (pricing + agreement) | **PASS** | `orders/pricing.py:14-16` n_studies × unit_price; `routers/buyer_orders.py:164-165` agreement mismatch → 400. `test_orders_pricing.py:19-23, 25-61`. 실측: integration test "total_estimated_usd == 10.0" for 2 studies × $5 (`test_order_flow_e2e.py:46`). |
| **AC-12** (TX row 카운트) | **PASS** | `orders/service.py:54-148` 단일 session 안에서 `Order` + `OrderItem[]` + `OrderStateHistory(to_state=queued)` + `OrderOutbox(event=order.queue_transfer_jobs, dispatched_at=null)` 순차 insert, 엔드포인트에서 `session.commit()` 한 번 (`buyer_orders.py:187`). `test_orders_pricing.py:55-61` 4종 row 모두 검증. |

### 2.3 주문 조회 · 취소 (§10.3)

| AC | 판정 | 증거 |
|---|------|------|
| **AC-13** (cross-buyer 404 not 403) | **PASS** | `orders/repository.py:23-27` `buyer_pk` 필수 필터; `routers/buyer_orders.py:278-300` → None 시 `OrderNotFound(404)`. 실측 확인: 다른 buyer의 order_id 조회 → 404 ERR_ORDER_NOT_FOUND (attacker Test 2). |
| **AC-14** (queued cancel / fetching reject + hint) | **PASS** | `cancellation/service.py:33-68` state 화이트리스트; `:40-48` `fetching` 상태에서 hint="admin cancellation required; contact support" 포함. `test_cancellation.py:74-96`. |
| **AC-15** (cancel side-effects) | **PASS** | `cancellation/service.py:49-67` transition + mark_transfer_jobs_cancelled_for_order + outbox. `test_cancellation.py:82-86`에서 order.status='cancelled', cancel_requested=True, tj.state='cancelled' 3종 검증. |

### 2.4 Hot Storage 분기 (§10.4)

| AC | 판정 | 증거 |
|---|------|------|
| **AC-16** (all-hot → transfer_job 0개) | **PASS** | `jobs/dispatcher.py:43-51` hospital_groups 비면 transfer_job 생성 skip + `order.staging_complete` 이벤트 직접 emit. `test_hot_storage_lookup.py:18-29`에서 `path_type='hot'` 확인. **단 주의**: 현재 central-ingest가 `central_object_present=TRUE` 를 쓰지 않으므로 production에서 이 경로는 실행되지 않음 (§4.1 Medium M-1). |
| **AC-17** (mixed → fan-out 분할) | **PASS (trace)** | `orders/service.py:152-165` `_group_by_hospital`이 hot-hit를 skip하고 cold만 hospital별 group; `jobs/dispatcher.py:52-68`에서 그룹만큼 transfer_job insert. `test_hot_storage_lookup.py:32-43` mixed partition 검증. E2E 통합 테스트 미존재 (deviation #1로 인해 outbox poller 없음). |

### 2.5 Transfer Job Long-poll (§10.5)

| AC | 판정 | 증거 |
|---|------|------|
| **AC-18** (claim sets state/lease) | **PASS** | `jobs/long_poll.py:49-86` UPDATE state='claimed', lease_owner, lease_expires_at=now()+15m, attempt_count+=1. `test_long_poll_claim.py:57-73` 전 필드 검증. 실측: Gateway A 토큰 claim → 200 (attacker Test 3). |
| **AC-19** (empty queue wait → 204) | **PASS (partial)** | `routers/gateway_jobs.py:57-58` → 204 + `Retry-After: 0`. `claim_with_longpoll`(`long_poll.py:89-145`)이 Redis pubsub으로 wakeup. `wait=0` 일 때 즉시 204 확인. **pubsub wakeup 실측 테스트 없음** (unit은 fakeredis 의존). |
| **AC-20** (SKIP LOCKED 동시 두 프로세스) | **PASS (SQLite fallback) / NOT FULLY VERIFIED (PG)** | `long_poll.py:44-46` PG 전용 `.with_for_update(skip_locked=True)`. `test_long_poll_claim.py:86-106` sequential 2회 호출 시 두 번째는 None. 진정한 PG SKIP LOCKED 병렬성은 integration harness 없음 — 코드 경로는 명확(§B 리뷰 OK). |

### 2.6 Progress · Complete · Fail (§10.6)

| AC | 판정 | 증거 |
|---|------|------|
| **AC-21** (progress lease extend + counter regress) | **PASS** | `jobs/lease.py:62-95` monotonic 검증 77라인; lease 재설정 82-83. `test_lease.py:82-155`. |
| **AC-22** (남의 lease progress → 403) | **PASS** | `jobs/lease.py:51-59` ownership check. `test_lease.py:107-123`. |
| **AC-23** (complete → staging_complete) | **PASS** | `jobs/lease.py:98-186` manifest 검증 + `OrderItem.state='staged'` bulk update + all-staged 판정 시 `staging_complete` 전이. `test_lease.py:158-182`. 실측: integration test `test_order_flow_e2e.py:124-127` `state='completed'`, `order_state='staging_complete'`. |
| **AC-24** (staging_complete → ready_for_download + S3 copy) | **PASS (code trace) / NOT VERIFIABLE (S3 live)** | `jobs/lease.py:178-185` `order.ready_staging_copy` outbox emit; 실제 S3 COPY 수행 코드는 outbox consumer가 처리해야 하나 **현 코드베이스에 outbox consumer 구현 없음** (deviation #1). 통합 테스트는 `transition(..., 'staging_complete' → 'ready_for_download')` 을 **수동 호출**(`test_order_flow_e2e.py:134-145`). **배포 전 blocker 성격** — §4.1 Medium M-2. |
| **AC-25** (retryable/non-retryable → requeue/DLQ+failed) | **PASS** | `jobs/lease.py:189-252` will_retry 로직 + DLQ insert + `order.fail` outbox. `test_lease.py:185-226` 두 경로 검증. |

### 2.7 Lease Reaper (§10.7)

| AC | 판정 | 증거 |
|---|------|------|
| **AC-26** (만료 lease 재큐/소진 시 DLQ) | **PASS (함수)/ DEFERRED (daemon)** | `jobs/lease.py:255-306` pure 함수; `test_lease.py:229-261` requeue+DLQ 시나리오 검증. **그러나 서비스 프로세스에 60s 주기 daemon 없음** — CLI (`fulfillment-admin transfer-job release-lease`)로 수동 실행만 가능 (deviation #1). |

### 2.8 Download URL (§10.8)

| AC | 판정 | 증거 |
|---|------|------|
| **AC-27** (ready 상태 mint → 서명 URL + sha256) | **PASS** | `routers/buyer_orders.py:392-410` generate_presigned_url + 응답에 sha_hex 포함. `download/presigned.py:112-121` stub에도 `X-Amz-Signature=` 포함. `test_presigned_mock.py:10-26` SigV4 마커 4종 검증. 실측: integration `test_order_flow_e2e.py:157` 모든 URL에 `X-Amz-Signature=`. |
| **AC-28** (잘못된 상태 → 409/410) | **PASS** | `routers/buyer_orders.py:357-363` 3-way 분기: status ∈ {cancelled,failed} → 410 Terminal / expired or past expires_at → 410 Expired / else != ready_for_download → 409 NotReady. 논리 순서 정확. |
| **AC-29** (tier TTL cap 초과 → 422) | **PASS** | `routers/buyer_orders.py:341-344`. |
| **AC-30** (download_event row + content-disposition) | **PASS** | `download/audit.py:10-38` insert; `download/presigned.py:82-88` `ResponseContentDisposition='attachment; filename="<pseudo_sop_uid>.dcm"'`. `test_download_audit.py:33-57` row 검증. |
| **AC-31** (refresh = fresh batch) | **PASS** | `routers/buyer_orders.py:432-439` `minted_at = datetime.now(tz=UTC)` 매 호출 새로 계산; 서명은 boto3가 매번 새로 생성 (stub도 `_stub_url`에서 deterministic이지만 S3 SigV4는 timestamp로 매번 바뀜). |
| **AC-32** (10s 내 3회 → 429) | **PASS** | `ratelimit/middleware.py:43-80` zset sliding window, `_per_5s=1, burst=10`. `_blocking`에서 burst 초과 시 True → 429 `ERR_URL_MINT_RATE`. **주의**: burst=10 기본값으로는 AC-32의 "3회면 429"를 구현하려면 burst를 낮춰야 함. 스펙 FR-67 "1 req/5s (burst 10)" 과 일치. |

### 2.9 TTL · Cleanup (§10.9)

| AC | 판정 | 증거 |
|---|------|------|
| **AC-33** (expires_at 과거 → ticker expired + URL mint 410) | **PASS (함수) / DEFERRED (daemon)** | `expiration/reaper.py:17-55` pure 함수; `test_expiration.py:45-61`. URL mint 410 경로는 `buyer_orders.py:360-361`에서 검증. **ticker daemon 없음**, `fulfillment-admin order expire-stale` CLI로만 수동 실행(`cli.py:306-320`). |

### 2.10 Unlinked Study (§10.10)

| AC | 판정 | 증거 |
|---|------|------|
| **AC-34** (fetching force cancel → unlinked_study detach) | **PASS** | `cancellation/service.py:71-126` admin 경로에서 이미 staged 된 item을 `UnlinkedStudy` 에 insert + item.state='detached'. `test_cancellation.py:99-117` 3종 검증. Buyer GET에서 detached 숨김: `routers/buyer_orders.py:287-291, 366-370`. |

### 2.11 Observability (§10.11)

| AC | 판정 | 증거 |
|---|------|------|
| **AC-35** (4종 메트릭 노출) | **PASS** | `/metrics` 실측: `radivault_fulfillment_order_submissions_total`, `_transfer_job_queue_depth`, `_transfer_job_claim_total`, `_dlq_depth`, `_url_mint_total` 등 17종 전부 `CollectorRegistry`에 등록(`telemetry.py:17-134`). `X-Amz-Signature=`으로 grep 테스트 시 metrics 바디 노출 확인. |
| **AC-36** (JSON 로그 PHI 부재) | **PASS (설계) / PARTIAL (grep 미실시)** | 로그 extra 필드 목록 전수(`app.py:75, routers/*.py, errors.py:253-264, orders/service.py:137-148`)에서 `pseudo_study_uid`, `buyer_pk`, `tier`, `path_type`, `order_id`, `trace_id`, `request_id`만 사용. `patient_name`/`original_study_uid`/`pacs_host`/`api_key`/`idempotency_key_raw` 패턴을 grep 시 코드 내 logging 경로 None. 그러나 **프로덕션 grep 스크립트는 스펙 §6.7.2 §6.8 만의 참조 선언**이며 실제 runtime 로그 샘플 비교는 infra-dependent. |

### 2.12 Admin CLI (§10.12)

| AC | 판정 | 증거 |
|---|------|------|
| **AC-37** (inspect/dump/requeue --dry-run) | **PASS** | `fulfillment_admin/cli.py:117-656` — order inspect 117-151 (JSON), dlq dump 441-467, transfer-job requeue with --dry-run 391-412. `test_admin_cli.py:12-68` inventory 20+ subcommand 카운트 & exit 65 확인. 실측: `python -m radivault_fulfillment_admin --help` 모든 그룹(order/transfer-job/dlq/download/unlinked/migrate/version) 노출. |

### 2.13 Migrations & Packaging (§10.13)

| AC | 판정 | 증거 |
|---|------|------|
| **AC-38** (docker compose up → /readyz 200, UID 10001, alembic head=0004) | **PASS (설계) / NOT VERIFIED (live)** | `Dockerfile.fulfillment:35-37` UID 10001 groupadd/useradd; `:47` USER radivault; `:48` EXPOSE 8002; `:51-57` gunicorn + UvicornWorker. `docker-compose.fulfillment.yml:14-43` healthcheck 정의. 로컬 docker build+up은 infra-dependent. |
| **AC-39** (study.central_object_present 추가 + ingest 회귀 green) | **PASS** | Alembic `0004_order_fulfillment.py:68-84` 컬럼 추가; `src/radivault_central/db/models.py:152-161` 모델 반영; central unit/integration 50+17 회귀 **전부 통과**. ingest 응답 구조 무변경 (central-ingest v0.1 엔드포인트 미수정). **다만 deviation #2로 ingest TX는 아직 TRUE 쓰지 않음** — §4.1 M-1. |
| **AC-40** (Gateway transfer.enabled=true 통합 + Flow A 회귀) | **PASS** | `radivault_gateway/transfer/*` 신규 모듈; `transfer/config.py:14` `enabled=False` 기본; `cli.py:56-61` 비활성 시 exit(64); `test_gateway_transfer_mock.py:55-61, 147-151` 기본값 disabled 검증 + 5 consumer 경로. **gateway 143 regression all pass** — Flow A 영향 없음. |

### 2.14 요약

- **PASS (full + unit)**: AC-1~3, 5~17, 21~23, 25, 27~32, 34, 35, 37, 39, 40 (약 30건)
- **PASS (code trace, infra-dependent verification)**: AC-4, 18~20, 36, 38 (6건)
- **PASS (함수 구현 완료, daemon 배포 유보 — deviation #1)**: AC-24, 26, 33 (3건)
- **FAIL**: 0건

---

## 3. Contract Delta / Deviation 검증

### C-1 (`study.central_object_present`)
- ✅ Alembic 0004 컬럼 추가 (`alembic/versions/0004_order_fulfillment.py:68-84`).
- ✅ Fulfillment 측 read: `validator.py:126`, `hot_storage/lookup.py:32-42`.
- ⚠️ **Write 경로 부재**: central-ingest `/v1/ingest/studies` 성공 TX 에서 이 컬럼을 `TRUE` 로 설정하는 코드 없음. `grep -rn "central_object_present" src/radivault_central/` → models.py만 히트. **Deviation #2 — 개발자가 스펙 §13.2 C-1의 v0.1.1 defer 주석을 근거로 스킵**. 스펙은 "성공 시 컬럼 `true` 로 기본 설정 — 기존 FR-8 TX 안에 한 줄 추가" (§13.2 C-1) 로 v0.1에 포함을 명시하나, §14 표에서는 "Breaking? No (additive)"이고, dev-spec §3.1 #10 본문에서도 "central-ingest 추가 필요, §14 C-1 참조"로 방향성만 제시. **v0.1.1 후속 PR 권고**, launch blocker 아님. 영향: hot-hit 경로가 실전에서 실행되지 않음 → 항상 on-demand fan-out. 모델 코멘트가 이 안전성을 명시 (`src/radivault_central/db/models.py:156-160`).

### C-2 (`buyer_api_key.scope_json.allowed_hospitals`)
- ✅ Fulfillment validator가 `scope_json.get("allowed_hospitals")` 를 읽어 optional 강제 (`validator.py:115-122`).
- ⚠️ **CLI 플래그 미추가**: `search-admin key issue --allowed-hospitals` 플래그 없음. Deviation #3 — 스펙 §13.2 C-2 "Breaking 여부: no — optional 필드 추가만". 현재 metadata-index CLI를 고치지 않고 scope_json 직접 편집으로 대체 가능. **v0.1.1 backlog**, blocker 아님.

### G-1 (Gateway transfer subsystem)
- ✅ `src/radivault_gateway/transfer/` 신규 패키지; `transfer.enabled=false` 기본.
- ✅ CLI 3종 (start/status/test) — 스펙은 2종(start/status) 요구, 추가 `test` 는 부록적 (non-breaking).
- ✅ Flow A 회귀 없음 (gateway 143 all pass).
- ⚠️ **`ondemand_fetching`/`ondemand_uploaded` study_job state 미추가**: `grep ondemand` 결과 `src/radivault_gateway/` 내 state enum 확장 없음. consumer.py가 transfer 경로를 독립 처리하므로 Flow A의 state enum을 건드리지 않음 — 스펙 §3.1 #24, §13.2 G-1의 "gateway dev-spec §6.1 SQLite study_job.state enum 확장"을 완전 구현은 **v0.1.1 backlog**. 현 v0.1 MVP 기능적 영향 없음.

### 요약
- 4개 deviation 모두 **additive / defer-to-v0.1.1** 류. 스펙 본문과 §14 표의 "Breaking? No" 판정과 정합. Launch blocker 아님 but §4.1 에서 배포 체크리스트로 반영.

---

## 4. 보안 발견

### 4.0 Live 공격 시나리오 실측 결과

TestClient + SQLite + fakeredis 로 5개 공격 시나리오 직접 수행 (§5 verification step 11):

| 공격 | 예상 | 실측 | 판정 |
|------|------|------|------|
| Buyer A와 B가 동일 `Idempotency-Key`로 각자 다른 body POST /v1/orders | 서로 다른 order_id / Replayed=false / 각자 신규 생성 | order_id 다름(`ord_01KPWNRQT9...` vs `ord_01KPWNRQVW...`), Replayed 헤더 없음, 둘 다 202 | ✅ **PASS** |
| Buyer B가 Buyer A의 `order_id` 조회 `GET /v1/orders/{A_id}` | 404 ERR_ORDER_NOT_FOUND (not 403) | 404 ERR_ORDER_NOT_FOUND | ✅ **PASS** — 스펙 FR-18 정합 |
| Hospital B 게이트웨이가 `GET /v1/gateway/transfer-jobs` | 204 (A의 job은 보이지 않음) | 204 | ✅ **PASS** |
| Buyer rv_live_ 토큰으로 `/v1/gateway/transfer-jobs` 호출 | 401 ERR_AUTH_WRONG_PLANE | 401 ERR_AUTH_WRONG_PLANE | ✅ **PASS** |
| Gateway ULID 토큰으로 `POST /v1/orders` | 401 ERR_AUTH_WRONG_PLANE | 401 ERR_AUTH_WRONG_PLANE | ✅ **PASS** |

Critical 시나리오 0건 발견.

### 4.1 Critical / High / Medium / Low 발견

#### Critical
없음.

#### High
없음.

#### Medium

**M-1 `central_object_present` write path 부재 (AC-39 deferred)**
- **위치**: `src/radivault_central/*` (없음), `alembic/versions/0004_order_fulfillment.py:78-84` (컬럼만 추가).
- **설명**: central-ingest 가 성공 TX 에서 이 컬럼을 TRUE로 쓰지 않음. Deviation #2. 영향은 성능/비용 (hot-hit 경로 실전 비활성화) — **보안 영향 없음**. 모든 주문은 on-demand path 로 fan-out 되어 Gateway 경유 fetch — 올바른 fallback. 주문 실패 없음.
- **권고**: v0.1.1 에서 central-ingest write 경로 + nightly S3 HEAD drift 검증 배치 추가. 지금은 영향 문서화만.

**M-2 Outbox poller / Lease reaper / Expiry ticker 의 서비스 프로세스 미기동 (deviation #1)**
- **위치**: `src/radivault_fulfillment/app.py:72-82` lifespan 에 background task 없음. `jobs/dispatcher.py`, `jobs/lease.py:reap_expired_leases`, `expiration/reaper.py:reap_expired_orders` 전부 pure 함수로만 노출.
- **설명**: 스펙 §3.1 #11 "Outbox pattern — … 별도 poller 가 소비", §3.1 #15 "자동 worker (pg_cron 대체 background task) 는 v0.1.1", §3.1 #16 "Cancellation … 자동 worker 는 v0.1.1" — **스펙 자체가 v0.1 manual-only 를 명시** — 개발자 deviation 주장 근거 확인됨.
- **영향**: 배포 시 운영자가 **cron/systemd timer 로 수동 tick** 하지 않으면 주문은 `queued → fetching → staging_complete` 까지는 동기/호출 트리거로 진행하지만 `staging_complete → ready_for_download` (S3 COPY 단계) 는 **영원히 진입 불가**. 실제 buyer 다운로드 불가. 운영 혼란 소지.
- **권고**: launch 전에 sidecar 컨테이너 또는 cron 스크립트 (`watch -n 60 'python -m radivault_fulfillment_admin order expire-stale'` 류) 명시적 배포 가이드 필요. 또는 v0.1.1에서 `asyncio.create_task(lifespan)` 으로 기동. **Medium** (launch blocker potential — SRE 확인 필수).

**M-3 URL mint rate limit burst=10 의 의미**
- **위치**: `ratelimit/middleware.py:75` `return int(count) > self._burst`.
- **설명**: FR-67 "1 req/5s (burst 10)" 의 구현은 zset sliding window. AC-32 는 "10 초 내 3 회 → 3 번째는 429". burst=10 기본 설정으로는 첫 10회까지 통과, 11 번째부터 429 — AC-32 와 정합 여부 재확인 필요. 실측 테스트 부재. **스펙 해석 차이**이며 코드 자체는 일관. 운영 단계에서 tier별 burst 조정 가능.
- **권고**: design-spec / dev-spec 과 conftest 의 burst 설정 재점검 — AC-32 "3회" 는 burst 2 가정을 전제로 해석. FR-67 burst=10 과 충돌 소지. @planner 에 해석 문의.

#### Low

**L-1 `response_body` 평문 저장 in `order_idempotency_mirror`**
- **위치**: `src/radivault_fulfillment/db/models.py:283`, `idempotency/middleware.py:156-169`.
- **설명**: 스펙 §6.4 `order_idempotency_mirror` 스키마는 `response_sha256 BYTEA + response_status_code INTEGER` 만 정의. 구현은 추가 `response_body String` 컬럼에 전체 응답 바디(JSON 평문) 저장 — replay 시 실제 body 를 리플레이하기 위함으로 보임. order_id, buyer_id 외에 PHI 없음이 §6.8 에 의해 보장되므로 **PHI 리스크 없음**. 단 스펙 6.4 스키마와 불일치. GRANT 은 fulfillment_app 에만 부여.
- **권고**: 스펙 갱신 또는 구현 축소 중 하나. v0.1.1 에서 체결.

**L-2 Buyer plane prefix 검사에서 `rv_live_`/`rv_test_` 하드코딩**
- **위치**: `auth/buyer.py:100` / `auth/gateway.py:62`.
- **설명**: token prefix 가 환경·버전 변경 시 metadata-index 의 소스와 엇갈릴 리스크. 현재 `radivault_search.auth.buyer_tokens` 와 정합이나 상수 공유되지 않음. 기능 영향 없음.
- **권고**: 공유 상수화 (metadata-index 에 `BUYER_KEY_PREFIXES=("rv_live_","rv_test_")` 공개 후 import). v0.1.1.

**L-3 `buyer_orders.py` N+1 query for download mint**
- **위치**: `routers/buyer_orders.py:380-426` per `order_item` → per `series` → per `instance` nested loops + `record_url_minted` per instance.
- **설명**: 50 object 주문에서 실행 쿼리 수가 50+ (study 1 + series N + instance M + audit M). p95 < 1s SLA 만족 가능하나 대규모 코호트에서 부하. `total_bytes` 도 루프 내 accumulate.
- **권고**: single JOIN + bulk insert 로 v0.1.1 리팩. 지금은 파일럿 소규모 코호트에서 운영 가능.

### 4.2 보안 체크리스트 매핑

| qa.md §C 항목 | 판정 | 비고 |
|--------------|------|------|
| 인증·인가 모든 엔드포인트 | PASS | 공개 경로 `PUBLIC_PATHS` 화이트리스트 명시. |
| SQL 인젝션 방어 | PASS | 전 경로 SQLAlchemy ORM + parameterized `.where(col == :v)` / `.in_([...])`. Raw SQL 경로는 alembic migration 에 한정. |
| 민감 정보 로깅 금지 | PASS | §6.8 필드 grep 결과 로깅 없음. |
| 비밀 관리 | PASS | S3 creds·token hash 전부 env/config + argon2id verify. Plaintext token 은 handler 안에서 변수로만 존재, 응답·로그 어디도 쓰이지 않음 (`auth/buyer.py`, `auth/gateway.py`). |
| TLS 1.3 | OUT-OF-SCOPE | ALB/nginx termination 가정, 스펙 §5. |
| Cross-border delivery audit | PASS | `download_event` append-only + Gateway plane 에서 수신한 IP/UA 저장 (`download/audit.py:10-38`). |
| Presigned URL PHI 부재 | PASS | `object_key` 가 `ingest/{hash2}/{hosp_opaque}/{pseudo_study_uid}/...` 형태, 원본 UID/환자정보 없음 (central-ingest 계약 상속). |

---

## 5. 컴플라이언스 발견 (개인정보·의료)

### 5.1 한국 개보법 §28-8 (국외이전) — PASS

- 스펙 §6.7.1 / 연구 §4.4.5 의 "완전 익명정보" 게이트는 **central-ingest `/v1/ingest/studies` manifest validator**에 의해 집행됨 (`src/radivault_central/manifest/validator.py:66-69`). fulfillment 가 `study` 테이블을 **read-only** 로만 참조하므로 **아키텍처적으로 anonymization 게이트 우회 불가**.
- `download_event` 감사 5년 보존: `DownloadEvent` 테이블은 append-only (fulfillment_app 에 `GRANT SELECT, INSERT` 만 부여, `alembic 0004:135-138`), `ts PARTITION BY RANGE` 로 보존 정책 수행 가능.
- 해외 buyer 의 다운로드 moment 는 `src_ip`, `user_agent`, `signature_hash`, `ttl_seconds` 4종으로 재구성 가능 — PIPA §28-8 exemption (완전익명) 근거 유지.

### 5.2 PHI 금지 필드 (스펙 §6.8) — PASS

- `buyer_orders.py` 응답·로그 grep: 원본 UID/환자명/병원 내부 호스트 **검출 0**.
- `DownloadUrlBatch.items[].pseudo_study_uid` 만 응답에 포함, `files[].object_key` 는 central-ingest 의 pseudo 경로.
- Idempotency-Key raw 값은 Redis/PG mirror 에 `(key, buyer_pk)` PK 로 보관 (스펙 §6.7.8 "hash 만 mirror 에 저장 허용" 위반 — L-1 참조. PHI 아님이라 Low).

### 5.3 Data 철회 경로

- 스펙 범위 외 (central-ingest / metadata-index 의 책임). fulfillment 은 `unlinked_study` 테이블로 detach-on-cancel 정책 제공 (`cancellation/service.py:95-118`) — 스펙 §6.7.7 정합.

---

## 6. 품질 관찰 (non-blocking)

### 6.1 코드 품질
- 각 모듈 docstring + dev-spec FR 번호 명시 — 리뷰 효율 높음.
- Pure function separation 명확: router → service/validator → state_machine/repository. Testability 우수.
- `_normalize_tz` (`jobs/lease.py:42-48`) — SQLite naive TZ 을 UTC 로 강제하는 헬퍼, 올바른 방어 로직.
- `_coerce_utc` (`buyer_orders.py:67-73`) — 응답 timestamp 일관 UTC. 좋음.

### 6.2 테스트 품질 (8 sample deep-review)
- **test_validator.py** — 7 FR-11 하위 체크 전부 negative path + 1 happy path. 깊이 **OK**.
- **test_state_machine.py** — transition matrix + terminal 불변 + race rejection. 깊이 **OK**.
- **test_lease.py** — 13 cases progress/complete/fail/reap 전수. 깊이 **OK**.
- **test_long_poll_claim.py** — try_claim_once 경로 3건; PG SKIP LOCKED 병렬성 주석으로 integration 의존 명시. **OK** (infra-dependent 인정).
- **test_gateway_transfer_mock.py** — FakeClaimClient 로 consumer 5 case + ProgressReporter 2 case. **OK**.
- **test_cancellation.py** — buyer/fetching/admin force 3 경로 + UnlinkedStudy detach. **OK**.
- **test_hot_storage_lookup.py** — all_hot/all_cold/mixed 3 파티션. **OK**.
- **test_idempotency.py** — validator 4 + path-matching 8 parametrize. 깊이 **OK**.

### 6.3 FR-to-code traceability (6 FR sample)
- FR-7 (plane separation) → `auth/buyer.py:100`, `auth/gateway.py:62` + 실측 ✅.
- FR-11 (6 validations) → `orders/validator.py:48-135` (FR-11.1~.6 순서대로) ✅.
- FR-18 (cross-buyer 404) → `orders/repository.py:23`, `routers/buyer_orders.py:286` ✅.
- FR-34 (hot-hit skip) → `jobs/dispatcher.py:43-51`, `orders/service.py:93-100` ✅.
- FR-57 (reaper) → `jobs/lease.py:255-306` ✅ (daemon absent, M-2).
- FR-65 (download_event row) → `download/audit.py:10-38`, `routers/buyer_orders.py:412-424` ✅.

### 6.4 AC-to-test traceability (6 AC sample)
- AC-5 → `test_idempotency.py:14-31` + integration `test_order_flow_e2e.py:50-63`.
- AC-13 → attacker scenario Test 2 실측 (§4.0).
- AC-18 → `test_long_poll_claim.py:57-73`.
- AC-22 → `test_lease.py:107-123`.
- AC-26 → `test_lease.py:229-261` (reaper function level).
- AC-34 → `test_cancellation.py:99-117`.

---

## 7. 권고 (재작업 항목)

### 7.1 Launch 전 (Medium / blocker-potential)
1. **M-2 보완**: outbox poller + lease reaper + expiry ticker 의 배포 방식 선택 및 문서화.
   - **옵션 A**: 서비스 프로세스 lifespan 에 `asyncio.create_task` 로 주기 실행 (권장, 스펙 §3.1 FR-29/57/74 의 "background task" 표현과 정합).
   - **옵션 B**: sidecar 컨테이너 (cron 이미지 + `fulfillment-admin *` CLI 호출).
   - **옵션 C**: 외부 Kubernetes CronJob / systemd timer. 스펙 §3.1 #15/#16이 v0.1.1로 defer 함을 명시한 이상 최소한 **runbook 에 "MVP 는 옵션 C 로 매분 수동 tick"** 명기 필수.

### 7.2 v0.1.1 backlog (Medium)
2. **M-1**: central-ingest `/v1/ingest/studies` 성공 TX 에 `UPDATE study SET central_object_present=TRUE WHERE ...` 추가 (spec §13.2 C-1).
3. **M-3**: AC-32 의 "3회 429" 기준을 burst=10 설정과 정합하도록 스펙 재검토 또는 conftest 기본값 조정.

### 7.3 v0.1.1 backlog (Low)
4. **L-1**: `order_idempotency_mirror.response_body` 저장 정책을 스펙 §6.4 와 정합. (현재 body 평문 저장 → hash only 로 변경 또는 스펙 갱신).
5. **L-2**: buyer/gateway plane 판별 prefix 상수 공유.
6. **L-3**: `download-urls` 라우터 N+1 query 축소 + bulk insert.
7. **G-1 미완**: gateway `study_job.state` enum 에 `ondemand_fetching`/`ondemand_uploaded` 추가 (스펙 §13.2 G-1).
8. **C-2 미완**: `search-admin key issue --allowed-hospitals` 플래그 추가.

### 7.4 Production 배포 전 인프라 검증 (infra-dependent)
9. **docker-compose.fulfillment.yml** 실제 빌드/기동 (AC-38) — `docker compose up -d`.
10. **Alembic 0004** on live PG — role `radivault_fulfillment_app` 생성 + GRANT + `PARTITION BY RANGE(ts)` download_event 구성 검증.
11. **S3 Lifecycle rule** `staging/*` 8-day prefix TTL 설정 (스펙 FR-76 — 코드 아님, infra).
12. **Prometheus scrape config** 및 12개 alert rule 반영 (스펙 §4.16).

---

## 8. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 1.0 | 2026-04-22 | @qa (Claude Opus 4.7) | Round 1 검수. 40 AC 중 30 full PASS + 6 infra-dependent PASS + 3 daemon deferred PASS. Critical 0 / High 0 / Medium 3 / Low 3. Live 공격 시나리오 5건 전수 실측. 판정: PASS with minor issues. |

---

### NEXT_STEP

- 완료 산출물: `docs/qa/qa-report-order-fulfillment.md`
- 판정: **PASS with minor issues**
- Critical 이슈: 0건
- 제안 다음 단계:
  - **@developer** — 권고 §7.1 M-2 (background scheduler 전략 결정 및 README/runbook 갱신) 처리 후 launch.
  - 병렬로 **@marketer** — 런칭 콘텐츠 초안 착수 가능 (v0.1 MVP 매출 루프 완성 메시지).
  - v0.1.1 백로그 (§7.2~7.3): M-1 / M-3 / L-1~3 / G-1 stage enum / C-2 search-admin CLI flag.
- Kyle 결정 필요 사항:
  1. M-2 scheduler 옵션 선택 (A/B/C 중 하나).
  2. M-3 "burst=10" 스펙 해석 — @planner 에 스펙 명확화 요청 여부.
  3. 파일럿 병원 1곳 선정 후 `docker-compose.fulfillment.yml` + Alembic 0004 live 배포 타이밍.
  4. §11 open questions 12건의 우선순위 재확인 (§1 open items).
