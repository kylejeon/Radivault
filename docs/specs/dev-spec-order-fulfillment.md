# 개발지시서 — Order Fulfillment v0.1 MVP (Buyer Orders · Gateway Transfer · Staged Download)

> **Status**: Draft v0.1 · **Feature slug**: `order-fulfillment` · **Last updated**: 2026-04-22
> **작성자**: @planner (Claude Opus 4.7) · **근거**:
> - [리서치 — Order Fulfillment 기술 기반](../research/order-fulfillment-technical-foundations.md) — **primary upstream**
> - [리서치 — K-MedData 요약](../research/k-meddata-research-summary.md)
> - [리서치 — Central Ingest 기술 기반 §4.3, §4.4](../research/central-ingest-technical-foundations.md)
> - [리서치 — Metadata Index 기술 기반 §4.1, §4.5](../research/metadata-index-technical-foundations.md)
> - [PRD §4.3, §4.4, §4.7](../prd.md)
> - [ARCHITECTURE §4.4 Hot Storage, §4.5 Order Orchestrator, §5.3 Download Manager, Flow B](../ARCHITECTURE.md)
> - [dev-spec-central-ingest §6 (데이터 모델 · 상속), §7 (envelope)](./dev-spec-central-ingest.md) — **확장 대상**
> - [design-spec-central-ingest §2 (envelope), §5 (error taxonomy)](./design-spec-central-ingest.md) — **envelope·에러 포맷 계승**
> - [dev-spec-metadata-index §6.2 (buyer_api_key 재사용)](./dev-spec-metadata-index.md)
> - [dev-spec-gateway-agent §6, §8 (Gateway 상태·파이프라인 확장 대상)](./dev-spec-gateway-agent.md)
> - `src/radivault_central/`, `src/radivault_search/`, `src/radivault_gateway/` — 실 코드 기준선

---

## 0. 요약 (TL;DR)

RadiVault Zone 2 의 **수익 엔진** — 기존 기획안의 E (Order Orchestrator) 와 H (Order Download) 를 단일 feature 로 병합한 **주문·이행·다운로드** 파이프라인. 버이어가 `POST /v1/orders` 로 `pseudo_study_uid[]` 코호트를 주문 → Central 이 검증·큐잉 → Gateway 가 아웃바운드 long-poll 로 transfer-job 을 pull → PACS fetch + de-ID + 기존 `/v1/ingest/studies` 경로 업로드 → Central 이 staging 복사 + presigned URL 발급 → 버이어 다운로드 → 감사·정리까지 end-to-end 담당한다.

**서비스 shape**: 새 FastAPI 서비스 `radivault_fulfillment` — buyer-facing + Gateway-facing 이중 역할, 쓰기 가능. central-ingest 와 **동일 PostgreSQL** 을 공유 (Alembic revision 0004 로 신규 5 테이블 추가). metadata-index 의 `buyer_api_key` 테이블을 **그대로 재사용**(신규 인증 층 생성 금지). Gateway bearer 인증은 central-ingest 의 `auth_token` 재사용.

**범위 병합 결과**
- **E (Order Orchestrator)**: 주문 FSM 12 상태, transfer-job pull 프로토콜(long-poll + lease), Hot Storage hit/miss 분기, 취소·만료, DLQ.
- **H (Order Download)**: per-object S3 presigned URL 발급, 24h 기본 TTL + refresh, SHA-256 체크섬 manifest, `download_event` 감사, `staging/*` Lifecycle 정리.
- **G (Billing) 제외**: `pending_billing` 스텁만. 실제 카드/PG/Stripe 통합은 v0.1.1+ 별 dev-spec.

**Gateway 영향**: `src/radivault_gateway/transfer/` 신규 subsystem (transfer-job consumer daemon) + config `transfer.*` subtree + CLI `gateway-agent transfer start|status` + 신규 study_job 상태 `ondemand_fetching`, `ondemand_uploaded`. Flow A(상시 수집) 는 건드리지 않고 **병렬 루프**로 운영.

**법적 전제**: 본 서비스는 central-ingest 가 이미 `anonymization_flag="fully_anonymized"` 게이트를 통과시킨 객체만 참조한다. 응답 본문 · 로그 · presigned URL 경로 어디에도 원본 UID 또는 PHI 가 노출되지 않는다. 모든 cross-border download 는 `download_event` 에 5년 보존된다(§6.7).

**v0.1 SLA 목표**
- 주문 제출 → 202 응답 **p95 < 2s**.
- 주문 제출 → `ready_for_download` 도달 (Hot Storage hit 전량) **p95 < 30s**.
- 주문 제출 → `ready_for_download` 도달 (100 study cold path) **p95 < 1 h**.
- Presigned URL TTL 기본 **24h**, 최대 7d (AWS S3 SigV4 상한 정합).
- 주문 TTL `ready_for_download → expired` **7 days** (ARCHITECTURE §3.4 정합).

---

## 1. 기능 개요

Order Fulfillment 는 RadiVault 매출 파이프라인의 **실행부**다. v0.1 범위에서 본 서비스는 다음 3개 인터페이스를 노출한다.

1. **Buyer-facing REST** (`/v1/orders/*`) — 주문 CRUD, 취소, 다운로드 URL 발급. 인증은 metadata-index 의 `buyer_api_key` 재사용.
2. **Gateway-facing REST** (`/v1/gateway/transfer-jobs/*`) — long-poll claim, progress, complete, fail. 인증은 central-ingest 의 `auth_token` 재사용.
3. **Background workers** — 주문 FSM 전이, Hot Storage hit 결정, staging copy, presigned URL 발급, TTL 만료 처리, DLQ 감시, metric emitter.

구매자는 metadata-index (`POST /v1/search/studies`) 로 코호트 크기를 확인한 뒤 해당 `pseudo_study_uid[]` 를 본 서비스에 제출한다. 본 서비스는 (a) 버이어 스코프·쿼터 검증, (b) Hot Storage 상주 여부 확인 후 fetch 필요분을 hospital 별 `transfer_job` 로 fan-out, (c) Gateway 가 long-poll 로 claim 하여 기존 ingest 경로로 업로드, (d) 업로드 완료 시 `staging/<order_id>/` 로 S3 COPY, (e) buyer 요청 시 SigV4 presigned URL batch 발급, (f) 다운로드 이벤트 감사, (g) 7 일 후 TTL 만료·cleanup.

현재 `src/radivault_central/`(central-ingest) 와 `src/radivault_search/`(metadata-index) 는 각각 **읽기-쓰기** 와 **읽기 전용** 서비스로 분리돼 있다. 본 dev-spec 은 세 번째 서비스 `radivault_fulfillment` 를 **쓰기 가능** 으로 추가하며, Postgres · Redis · S3 인프라는 공유한다.

---

## 2. 사용자 스토리

- **As an** AI 기업 통합 개발자, **I want** `POST /v1/orders` 한 번으로 1,000 study 코호트 주문을 제출하고, `GET /v1/orders/{id}` 폴링만으로 상태·진행률·`ready_for_download` 도달 시점을 파악할 수 있다, **so that** 별도 대시보드·세일즈 담당자 경유 없이 자동화 파이프라인으로 편입 가능하다.
- **As a** 제약사 임상 담당자, **I want** 주문 `ready_for_download` 상태에서 `POST /v1/orders/{id}/download-urls` 호출로 per-object presigned URL 배열과 SHA-256 체크섬을 받아 내 로컬 DICOM 파이프라인에 직접 공급한다, **so that** S3 parallel GET 으로 대용량 코호트를 수 분 내 다운로드할 수 있다.
- **As a** RadiVault 운영자, **I want** `fulfillment-admin order inspect` / `transfer-job requeue` / `dlq-dump` 커맨드로 in-flight 주문의 상태·lease 소유자·재시도 횟수를 즉시 확인할 수 있다, **so that** 병원 PACS 장애 발생 시 15분 이내 1st response 가능하다.
- **As a** 병원 Gateway Agent (machine user), **I want** `GET /v1/gateway/transfer-jobs?wait=30s` 를 outbound-only HTTP 로 long-poll 하여 주문 job 을 claim 하고 기존 de-ID + ingest 경로로 재사용해서 업로드한다, **so that** 병원 방화벽에 inbound 포트를 개방하지 않고 RadiVault 주문에 대응할 수 있다.
- **As a** 버이어 세일즈 담당자, **I want** 주문 수·tier 별 수익 지표·p95 fulfillment latency 가 Prometheus `radivault_fulfillment_*` 메트릭으로 실시간 노출된다, **so that** tier 전환·영업 우선순위 판단에 활용한다.
- **As a** 플랫폼 법무 담당자, **I want** 모든 presigned URL 발급·사용이 `download_event` append-only 테이블에 `buyer_pk + order_pk + object_key + src_ip + signature_hash` 로 기록되며 raw URL 은 저장되지 않는다, **so that** 감사 시 "누가 언제 어떤 익명 영상을 다운받았는가" 를 5년간 제시할 수 있다.
- **As a** 병원 DPO (데이터 보호 책임자), **I want** 주문 이행 중 `cancel` 된 경우 이미 fetch 된 스터디는 `unlinked_study` 플래그로 남아 다른 주문에 재할당되기 전까지는 어떤 buyer URL 에도 연결되지 않는다, **so that** 취소 후 잔존 리스크를 관리할 수 있다.

---

## 3. 범위

### 3.1 포함 (In-scope — v0.1 MVP)

1. **FastAPI 서비스 `radivault_fulfillment`** — 신규 패키지 `src/radivault_fulfillment/`. ASGI entrypoint `radivault_fulfillment.asgi:app`. Port 기본 **8002** (central-ingest 8000 / search 8001 충돌 방지).
2. **Buyer-facing 엔드포인트 6종** — `POST /v1/orders`, `GET /v1/orders`, `GET /v1/orders/{id}`, `POST /v1/orders/{id}/cancel`, `POST /v1/orders/{id}/download-urls`. Health/version/ready 는 운영 프로브로 분리.
3. **Gateway-facing 엔드포인트 4종** — `GET /v1/gateway/transfer-jobs?wait=30s` (long-poll claim), `POST /v1/gateway/transfer-jobs/{id}/progress`, `POST /v1/gateway/transfer-jobs/{id}/complete`, `POST /v1/gateway/transfer-jobs/{id}/fail`.
4. **운영 프로브 3종** — `GET /healthz`, `GET /readyz`, `GET /v1/version`.
5. **인증 2-plane** — Buyer: metadata-index `buyer_api_key` 재사용 (argon2id, `rv_live_<kid8>_<rand32>`, `scope_json.tier`). Gateway: central-ingest `auth_token` 재사용 (hospital bearer).
6. **Order FSM 12-state** — `draft → submitted → validating → validated → queued → fetching → staging_partial → staging_complete → ready_for_download → delivering → delivered → expired | cancelled | failed` (리서치 §4.1.1). PG row-level lock 기반 멱등 전이.
7. **Validation 6종** — buyer scope (`scope_json.exclude_hospitals`), tier cohort size cap (preview=50, paid=10,000), daily order quota (preview=5/day, paid=50/day), pseudo_study_uid 존재 + 중복 금지, size cap (tier.max_order_bytes), hospital access.
8. **Pricing stub** — tier unit_price × n_studies → `total_estimated_usd`. `status_billing = "pending_billing"`. 실제 결제 로직 없음.
9. **Transfer-job orchestration** — 주문당 hospital 별 fan-out. PG `SELECT … FOR UPDATE SKIP LOCKED` claim + 15 분 lease TTL + `max_retries=5` + DLQ.
10. **Hot Storage hit 판정** — `study.central_object_present BOOLEAN`(central-ingest 추가 필요, §14 C-1 참조) 조회 후 all-hit → `staging_copy` 만 수행, all-miss → `transfer_job` 발행, mixed → 병렬.
11. **Staging copy** — S3 COPY API (`ingest/*` prefix → `staging/<order_id>/` prefix). 같은 리전·같은 버킷 전제.
12. **Presigned URL batch 발급** — boto3 `generate_presigned_url` (GET). 기본 TTL 24h (환경변수 오버라이드). per-object 배열 응답 + SHA-256 체크섬 포함 + `content-disposition` attachment.
13. **Download URL refresh** — `POST /v1/orders/{id}/download-urls` 를 **호출할 때마다 fresh batch 반환** (refresh 기본 기능, 별도 `/refresh` subpath 없음). 리서치 §4.4.4 revocation 대체 메커니즘.
14. **Download audit** — `download_event` append-only, `url_minted` + `get_started` + `get_completed` + `get_failed` 4 이벤트 타입 (v0.1 은 `url_minted` 만 필수 기록. S3 access log ETL 은 v0.1.1 best-effort).
15. **Order TTL 7 일** — `ready_for_download → expired` (7 days), `expired` 주문은 presigned URL 발급 거부.
16. **Cleanup** — v0.1 은 S3 Lifecycle rule (`staging/*` 8 days 삭제) + `fulfillment-admin order expire-stale` 수동 CLI. 자동 worker (pg_cron 대체 background task) 는 v0.1.1.
17. **Cancellation** — `draft|submitted|validating|validated|queued` 까지 buyer self-cancel 허용. `fetching` 이후는 admin-only + `cancel_requested=true` 플래그만 즉시 설정 (Gateway 협조적 처리). `unlinked_study` 테이블로 orphan 관리.
18. **State tables 5종** — `order`, `order_item`, `transfer_job`, `transfer_job_dead_letter`, `download_event`, `order_state_history`, `unlinked_study` (실제 6+1). ER 다이어그램은 §6.1.
19. **Outbox pattern** — 주문 FSM 전이 + 후속 이펙트 (transfer-job enqueue, audit emit, metric) 를 `order_outbox` 테이블 단일 TX 에 insert → 별도 poller 가 소비. at-least-once 보장.
20. **Idempotency-Key 강제** — `POST /v1/orders` 와 Gateway 쓰기 엔드포인트 3종 (`progress/complete/fail`) 에 헤더 필수. 중앙 central-ingest idempotency 미러 테이블 패턴 재사용 (`order_idempotency_mirror`).
21. **Prometheus metrics** — `radivault_fulfillment_*` prefix. 주요: order lifecycle, transfer-job queue depth, p95 fulfillment, URL mint rate, download bytes, cancellation rate, DLQ depth.
22. **JSON 구조화 로그** — central-ingest FR-60 패턴 재사용. PHI 금지 필드(§6.7) 재천명.
23. **Admin CLI `fulfillment-admin`** — `order` · `transfer-job` · `dlq` · `download` · `migrate` · `version` 6 서브커맨드 트리(§4.13). central-ingest `ingest-admin` 과 동일 스타일 (BSD sysexits, `--json`, `--dry-run`, `--no-color`).
24. **Gateway transfer consumer** — `src/radivault_gateway/transfer/` 신규 모듈. asyncio daemon loop, 동시 claim 캡 2 (기본), de-ID + upload pipeline 재사용, `ondemand_fetching`·`ondemand_uploaded` 신규 study_job state (§14 G-1).
25. **Gateway CLI** — `radivault-gateway transfer start` (daemon), `radivault-gateway transfer status` (inflight job 수, 최근 에러 5건). `start` 서브커맨드와 병렬 기동 가능.
26. **Alembic revision 0004** — central-ingest migrations tree 에 추가. 5+1 신규 테이블 + 인덱스 + `central_fulfillment_app` 역할 부여. `study.central_object_present` 컬럼 추가 (§14 C-1 contract delta).
27. **Tests** — pytest unit (FSM, validation, Hot Storage decision, lease semantics, presigned URL mock, cancellation) + integration (buyer → order → mock Gateway claim → mock ingest → ready → URL mint + audit) + docker-compose e2e variant (`docker-compose-fulfillment.yml`).
28. **Gateway-side tests** — transfer consumer claim/progress/complete flow with mock central fulfillment API.
29. **Docker packaging** — multi-stage, non-root, `Dockerfile.fulfillment` 또는 `Dockerfile.central` build-arg 분기 (metadata-index 와 동일 선택).
30. **docker-compose-fulfillment.yml** — fulfillment 서비스 + 기존 postgres/redis/minio 재사용 (external network `radivault_net`).

### 3.2 제외 (Out-of-scope — v0.1.1 / v0.2 이상)

1. **실제 결제 / Stripe / PG 통합** — `pending_billing` 스텁만. 별 dev-spec (billing · revenue-share).
2. **zip/tar 서버측 번들 다운로드** — per-object URL 배열만 지원. zip 생성 CPU·임시 디스크 비용 회피 (리서치 §4.4.2).
3. **이메일/webhook buyer notification** — v0.1 은 buyer 측 폴링만. v0.1.1 webhook, v0.2 이메일.
4. **Buyer 포털 웹 UI** — API-only. `@designer` 별도 dev-spec.
5. **Hot Storage 자동 promotion (Flow C)** — v0.1 은 수동 pinning (`fulfillment-admin order hotstorage pin` 미구현, central-ingest admin 이 담당할지 결정 보류). 자동화는 v0.2.
6. **CloudFront signed URL / CDN** — v0.1 은 S3 SigV4 presigned URL 만. CDN 도입은 SOC 2 Type I 시점.
7. **Partial delivery (per-item purchase)** — v0.1 은 주문 단위 all-or-nothing. 부분 재시도는 client-side (per-object retry) 로 해결.
8. **Order merge / split** — 운영자 수동 개입만. 자동화 없음.
9. **Subscription tier (지속 코호트 access)** — v0.1 은 개별 주문만.
10. **GPU-가속 download 서비스** — v0.2+.
11. **IP allowlist per buyer** — v0.1 은 TLS + Bearer + audit log 로 갈음. CloudFront signed URL 도입 시점과 연계.
12. **MFA for high-value orders** — v0.1 은 단일 factor. v0.2 OAuth2 + MFA.
13. **NLP 라벨 기반 주문 (판독문 진단명)** — metadata-index 가 해당 필드 추가 후 본 서비스는 자동 상속.
14. **Tier 2/3 (전문의·세그) 라벨링 포함 주문** — v0.1 은 Tier 1 (자동 라벨) 만. Tier 2+ 는 labeling pipeline 선행.
15. **Email/PDF 견적서 발행** — 클릭랩 `agreement_hash` 만. PDF 는 billing dev-spec.
16. **Cross-region replication of staging** — 서울 리전 단일.
17. **Order 재주문 (re-order) 편의 API** — buyer 가 동일 `pseudo_study_uid[]` 로 새 주문 생성만.

---

## 4. 기능 요구사항

번호는 feature-slug 내 고유. `@qa` 는 각 FR 을 §10 AC 로 매핑 검증. 총 **FR 85 개**.

### 4.1 인증 (Buyer + Gateway 이중 plane)

- **FR-1**: `/v1/orders/*` 엔드포인트는 `Authorization: Bearer <buyer_api_key>` 필수. 형식은 metadata-index §4.1 `rv_live_<kid8>_<random32>` 재사용. 누락 → `401 ERR_AUTH_MISSING` (design-spec-central-ingest §5.1 재사용).
- **FR-2**: Buyer 키 조회는 metadata-index 의 `buyer_api_key` 테이블을 **read-only** 로 참조한다. argon2id verify + Redis 60 초 positive cache (`buyer_auth:{kid8}`). 본 서비스에서는 키 발급 · 철회 API 를 제공하지 않으며, `search-admin` (metadata-index CLI) 이 단일 책임.
- **FR-3**: 검증 통과 시 request context 에 `(buyer_pk, buyer_id, tier, scope_json)` 주입. 이후 FR-8, FR-11 등에서 참조.
- **FR-4**: `/v1/gateway/transfer-jobs/*` 엔드포인트는 `Authorization: Bearer <auth_token>` 필수. central-ingest 의 `auth_token` 테이블을 **read-only** 로 참조. argon2id verify. 누락 → `401 ERR_AUTH_MISSING`.
- **FR-5**: Gateway 키 검증 통과 시 request context 에 `(hospital_pk, hospital_id, gateway_id)` 주입. transfer-job 의 hospital 소유권 검증에 사용.
- **FR-6**: 인증 캐시는 Redis 장애 시 fail-closed — `503 ERR_AUTH_UNAVAILABLE` 반환. cache miss 로 인한 argon2 직접 verify 는 평시 허용, negative 결과는 캐시 금지 (타이밍 공격 방지, metadata-index FR-5 재사용).
- **FR-7**: Buyer 와 Gateway plane 은 **엔드포인트 경로로 분리**되며 토큰 타입이 섞이면 `401 ERR_AUTH_WRONG_PLANE` (신규 코드) 반환. 예: buyer 토큰으로 `/v1/gateway/*` 호출 → 401.

### 4.2 Buyer Order 생성 (`POST /v1/orders`)

- **FR-8**: 요청 body 는 pydantic v2 `OrderRequest`(§6.4). 필수 필드: `pseudo_study_uids: list[str]`, `agreement_hash: str`. 선택 필드: `notes: str|None`, `preferred_download_ttl_hours: int|None` (tier 별 상한 적용).
- **FR-9**: 요청은 `Idempotency-Key` 헤더 **서버측 강제**. 형식은 central-ingest FR-28 재사용 (16–128 자, `[A-Za-z0-9_.-]`). 미제공 → `400 ERR_IDEMP_MISSING`.
- **FR-10**: 동일 `(buyer_pk, Idempotency-Key)` 재수신 → 저장된 응답 복제 + `Idempotency-Replayed: true` 응답 헤더. Redis `SETNX` TTL 24h + `order_idempotency_mirror` 테이블 7d 보조.
- **FR-11**: 서버 측 검증 6종 (순서):
  1. **Scope**: `scope_json.exclude_hospitals` 와 요청 cohort 의 hospital 집합 교집합 공집합 확인. 위반 → `403 ERR_ORDER_SCOPE_FORBIDDEN`.
  2. **Tier cohort cap**: `len(pseudo_study_uids)` 이 tier 상한 초과 → `422 ERR_ORDER_TIER_EXCEEDED`. 기본값: preview=50, paid=10,000.
  3. **Daily order quota**: 버이어별 당일 주문 수 (UTC 자정 롤오버) 초과 → `429 ERR_ORDER_QUOTA_EXCEEDED`. 기본값: preview=5/day, paid=50/day.
  4. **UID 유효성**: 모든 `pseudo_study_uid` 가 `study` 테이블에 존재 + 중복 없음. 둘 중 하나라도 위반 → `404 ERR_ORDER_STUDY_NOT_FOUND` 또는 `400 ERR_ORDER_DUPLICATE_STUDY`.
  5. **Size cap**: `SUM(study.total_bytes)` 이 tier 상한 초과 → `413 ERR_ORDER_TOO_LARGE`. 기본값: preview=10GB, paid=2TB.
  6. **Hospital access**: 모든 study 의 hospital 이 buyer 의 scope 허용 목록에 존재. 위반 → `403 ERR_ORDER_SCOPE_FORBIDDEN`.
- **FR-12**: 검증은 동기 실행 (`submitted → validating → validated` FSM 전이 중). p95 < 2 s 목표 (§5).
- **FR-13**: 성공 시 `order` row insert (`status=queued`), `order_item[]` insert, `order_outbox` 이벤트 insert (`event='order.validated'`) 를 **단일 PG TX**. TX 실패 → `503 ERR_DB_UNAVAILABLE`.
- **FR-14**: 응답 `202 Accepted` + `{"order_id", "state", "n_studies", "total_estimated_usd", "estimated_ready_at", "submitted_at"}`. `estimated_ready_at` 은 hot_hit 비율 × 상수로 추정 (§8.1 주석).
- **FR-15**: Pricing stub — `total_estimated_usd = sum(tier_unit_price_usd × 1)` for each order_item. v0.1 기본 `tier_unit_price_usd = 5.0` (Tier 1 자동 라벨, 리서치 §4.5.2). `status_billing = "pending_billing"` 상수. 실제 결제 게이트웨이 호출 없음.
- **FR-16**: `agreement_hash` 는 클릭랩 동의의 sha256 해시 (MSA v0.1 본문 sha256 와 일치). 위반 (누락·오타) → `400 ERR_ORDER_AGREEMENT_REQUIRED`. 현행 MSA 해시는 `fulfillment-admin` 설정에서 읽음.

### 4.3 Buyer Order 조회 (`GET /v1/orders`, `GET /v1/orders/{id}`)

- **FR-17**: `GET /v1/orders` 는 `buyer_pk` 범위 내 주문 목록. 쿼리 파라미터: `status: list[str]|None`, `cursor: str|None`, `limit: int=50` (max 200). 응답은 metadata-index §7.1 keyset cursor 패턴 재사용 (`next_cursor`, `has_next`).
- **FR-18**: `GET /v1/orders/{id}` 는 단일 주문 상세 — `order` row + `order_item[]` summary (per-item state) + `transfer_job[]` summary (state, lease_expires_at, attempt_count, last_error) + `download_event` 집계 (url_minted 횟수, 최근 mint 시각). 다른 buyer 의 주문 조회 → `404 ERR_ORDER_NOT_FOUND` (스코프 누출 방지; `403` 미사용).
- **FR-19**: `progress` 필드는 유도값 — `uploaded_studies / total_studies`. 0–1 float. `eta_seconds` 필드는 진행률 기반 추정, fallback=null.
- **FR-20**: 요청 `Idempotency-Key` 불요 (GET). 페이지네이션 cursor 는 `(created_at DESC, order_pk DESC)` 튜플.

### 4.4 Buyer Order 취소 (`POST /v1/orders/{id}/cancel`)

- **FR-21**: Buyer 취소 허용 전이 — `draft|submitted|validating|validated|queued → cancelled`. 그 외 상태에서 buyer 호출 → `409 ERR_ORDER_STATE_TRANSITION`.
- **FR-22**: `fetching|staging_partial|staging_complete` 상태에서는 buyer 호출 시 `409` 와 함께 `hint="contact admin for cancellation during fetch"` 메시지 반환. admin 취소는 별도 CLI.
- **FR-23**: 취소 성공 시 (a) `order.status='cancelled'`, (b) `order_outbox` 에 `order.cancelled` 이벤트 insert, (c) 연관 `transfer_job` 이 존재하면 `cancel_requested=true` 플래그 즉시 설정 (Gateway 는 다음 progress ping 시 자체 판단 — 리서치 §4.7.3), (d) `order_state_history` 에 `actor='buyer'` row insert. 모두 **단일 PG TX**.
- **FR-24**: 응답 `200 OK` + `{"order_id", "state", "cancelled_at", "refund_eligible": false}` (v0.1 은 pending_billing 이므로 refund 개념 없음; 필드만 false 고정).

### 4.5 Order FSM 전이

- **FR-25**: 12 상태 + 4 terminal (`delivered`, `expired`, `cancelled`, `failed`). 전이 매트릭스는 §8.5 (설계 명세 상세) 및 리서치 §4.1.1 참조.
- **FR-26**: 모든 전이는 PG `SELECT ... FOR UPDATE` 위 `UPDATE order SET status=:to WHERE order_pk=:pk AND status=:from`. rowcount=0 이면 `409 ERR_ORDER_STATE_TRANSITION` — **다른 TX 가 먼저 전이**했거나 illegal.
- **FR-27**: 모든 전이는 `order_state_history` 에 `(from_state, to_state, event, actor, reason, at)` row append. `actor ∈ {'buyer', 'gateway', 'admin', 'system', 'timer'}`.
- **FR-28**: Terminal 상태(`delivered|expired|cancelled|failed`) 에서 어떤 이벤트도 수용 불가 — 멱등 409 반환.
- **FR-29**: Outbox 패턴 — FSM 전이 + 후속 side-effect (transfer_job enqueue, metric emit, audit event) 은 동일 TX 에 `order_outbox(event_pk, event_type, payload_jsonb, dispatched_at=null)` insert. 별도 poller (`fulfillment-outbox-poller` background task) 가 `WHERE dispatched_at IS NULL LIMIT 100` 로 소비.
- **FR-30**: `order_outbox` 소비는 at-least-once. 각 이벤트 핸들러는 멱등 — 재실행 시 동일 결과. `dispatched_at IS NOT NULL` 행은 30일 후 수동 archive.

### 4.6 Transfer Job 생성 (fan-out)

- **FR-31**: `order.validated → queued` 전이 시 outbox 이벤트 `order.queue_transfer_jobs` 발행. Poller 가 소비하여 hospital 별 `transfer_job` row 생성.
- **FR-32**: Fan-out 규칙 — 같은 주문 내 여러 hospital 이 걸쳐 있으면 **hospital_pk 기준 group by** 하여 각 group 당 `transfer_job` 1 row. 주문 내 1 hospital 의 100 study 는 1 transfer_job 이 담는다 (study 단위 fan-out 은 v0.2).
- **FR-33**: `transfer_job.state = 'queued'`, `lease_owner=NULL`, `lease_expires_at=NULL`, `attempt_count=0`. `studies` 컬럼 (JSONB) 에 `[{"pseudo_study_uid","expected_instances","priority"}]` 배열 저장.
- **FR-34**: Hot Storage hit 판정 — 모든 pseudo_study_uid 의 `study.central_object_present=true` 면 **transfer_job 생성 건너뛰기**. 대신 직접 `order_item[].state='hot_hit_pending_copy'` 설정 후 `staging_copy` outbox 이벤트 발행.
- **FR-35**: Mixed path — 같은 주문 내 hot-hit 과 cold 가 섞이면 cold 분은 transfer_job 으로 fan-out, hot-hit 분은 즉시 staging_copy. 두 경로가 **모두** 완료되어야 `order.staging_complete` 전이.
- **FR-36**: 같은 `(order_pk, hospital_pk)` 에 대해 최대 1 transfer_job. 동일 조합 중복 insert 시도 → PG unique constraint 위반 → 내부 에러 (프로그래머 오류).

### 4.7 Gateway Long-poll Claim (`GET /v1/gateway/transfer-jobs?wait=30s`)

- **FR-37**: Long-poll 엔드포인트. 쿼리 파라미터: `wait: int = 30` (초, min=0, max=60 — ALB idle timeout 배려), `max_jobs: int = 1` (v0.1 고정 1).
- **FR-38**: 구현 — `SELECT * FROM transfer_job WHERE state='queued' AND hospital_pk=:mine ORDER BY created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED`. 행이 있으면 `UPDATE state='claimed', lease_owner=:gateway_id, lease_expires_at=now()+15m, attempt_count=attempt_count+1, claimed_at=now()` 후 `200 OK` 로 반환.
- **FR-39**: 행이 없으면 Redis pub/sub 채널 `transfer_job_hospital:{hospital_pk}` 를 `wait` 초간 구독. 새 job 이 insert 되면 publish 트리거 → 즉시 반환. 타임아웃 시 `204 No Content` + `Retry-After: 0`.
- **FR-40**: 응답 body shape (`TransferJobClaim`, §6.4):
  ```jsonc
  {
    "transfer_job_id": "tj_01H...",
    "order_id":        "ord_01H...",
    "hospital_id":     "hosp_abc",
    "studies":         [{"pseudo_study_uid":"2.25.xxx","expected_instances":184,"priority":1}],
    "lease_expires_at":"2026-04-22T10:35:00Z",
    "ruleset_version_required": "v0.1.0",
    "salt_version_required":    1,
    "cancel_requested":         false
  }
  ```
- **FR-41**: Gateway 가 자신의 hospital 이 아닌 job 을 claim 하려 하면 SQL 쿼리에서 이미 필터링되어 발생 불가. (방어적) 만약 DB 레벨 inconsistency 로 diff 가 발생하면 `403 ERR_JOB_HOSPITAL_MISMATCH` 반환.
- **FR-42**: 동시성 — 여러 Gateway instance 가 동시 long-poll 해도 `SKIP LOCKED` 로 한 행은 한 claim 만. v0.1 은 hospital 당 Gateway 1:1 가정이지만 double-deploy 내성.

### 4.8 Transfer Job Progress (`POST /v1/gateway/transfer-jobs/{id}/progress`)

- **FR-43**: 요청 body `ProgressReport`(§6.4): `{"n_fetched", "n_deided", "n_uploaded", "lease_extend": bool}`.
- **FR-44**: 서버는 (a) `transfer_job.lease_owner == :gateway_id` 검증. 위반 → `403 ERR_JOB_LEASE_OWNERSHIP`. (b) `lease_expires_at > now()` 검증. 위반 → `409 ERR_JOB_LEASE_EXPIRED` (job 이 재큐됐을 수 있음).
- **FR-45**: `lease_extend=true` 면 `lease_expires_at = now() + 15m` 갱신. counters (`n_fetched`, `n_deided`, `n_uploaded`) 는 monotonic 증가만 허용 — 감소 시 `400 ERR_JOB_COUNTER_REGRESS`.
- **FR-46**: 응답 `200 OK` + `{"lease_expires_at", "cancel_requested": bool}`. `cancel_requested` 는 FR-23 에서 설정된 플래그를 진단 — Gateway 가 자체 판단으로 abort 선택.
- **FR-47**: Idempotency-Key 필수 (FR-9 패턴). 같은 키 재수신 → 같은 응답 리플레이. counters 재적용 금지 (mirror 에서 확인).

### 4.9 Transfer Job Complete (`POST /v1/gateway/transfer-jobs/{id}/complete`)

- **FR-48**: 요청 body `CompletionReport`(§6.4):
  ```jsonc
  {
    "manifest": [
      {"pseudo_study_uid":"2.25.xxx","n_instances":184,"total_bytes":94321012,"status":"uploaded","central_job_ids":["ingest_01H..."]}
    ],
    "audit_ref": {"seq":22345,"hash":"sha256:..."}
  }
  ```
- **FR-49**: 서버는 (a) lease ownership/expiry 검증 (FR-44), (b) `manifest[].pseudo_study_uid` 이 `transfer_job.studies` 에 존재 검증. 불일치 → `400 ERR_JOB_MANIFEST_MISMATCH`.
- **FR-50**: 성공 시 (**단일 PG TX**):
  1. `transfer_job.state='completed'`, `completed_at=now()`.
  2. 각 `order_item` 에 대해 `state='staged'` (매치되는 pseudo_study_uid).
  3. 모든 `order_item.state ∈ {'staged','hot_hit_staged'}` 면 `order.status='staging_complete'` 전이. 아니면 `staging_partial`.
  4. outbox 이벤트 `order.staging_complete` 또는 `staging_copy_for_order_items` 발행.
- **FR-51**: `staging_complete → ready_for_download` 전이는 별도 outbox consumer 가 수행 — (a) `staging/<order_id>/` prefix 생성, (b) 각 instance 의 S3 object 를 `ingest/*` → `staging/*` 로 COPY (server-side, same-region), (c) COPY 완료 후 `expires_at = now() + 7d` 설정, (d) `ready_for_download` 전이 + `ready_at` 기록.
- **FR-52**: 응답 `200 OK` + `{"transfer_job_id", "state", "order_state"}`. 멱등.

### 4.10 Transfer Job Fail (`POST /v1/gateway/transfer-jobs/{id}/fail`)

- **FR-53**: 요청 body `FailureReport`(§6.4): `{"reason_code", "details", "retryable": bool}`. `reason_code ∈ {PACS_UNAVAILABLE, DEID_FAILED, UPLOAD_FAILED, BURNED_IN_BLOCKED, OTHER}`.
- **FR-54**: `retryable=true` 이고 `attempt_count < max_retries(=5)` — `transfer_job.state='queued'`, `lease_owner=NULL`, `lease_expires_at=NULL`, `last_error=details`. 다음 poll 에서 재claim.
- **FR-55**: `retryable=false` 이거나 한도 도달 → `transfer_job.state='dead'`, `transfer_job_dead_letter` 로 복제 row insert. `order.status='failed'` 로 전이 (부분 성공해도 v0.1 은 주문 전체 실패 정책 — partial delivery 없음).
- **FR-56**: 응답 `200 OK` + `{"transfer_job_id", "state", "attempt_count", "will_retry": bool}`.

### 4.11 Lease Reaper

- **FR-57**: Background task `transfer-job-lease-reaper` — 60 초 주기로 `SELECT * FROM transfer_job WHERE state='claimed' AND lease_expires_at < now()` → 각 row 에 대해 `UPDATE state='queued', lease_owner=NULL, lease_expires_at=NULL, attempt_count=attempt_count+1` + outbox 이벤트 `transfer_job.lease_reaped`.
- **FR-58**: Reaper 가 `attempt_count >= max_retries` 조건 발견 → `state='dead'` + DLQ 삽입 + 주문 `failed` 전이 (FR-55 경로와 동일).
- **FR-59**: Reaper 는 PG advisory lock (`pg_advisory_lock(hashtext('fulfillment_lease_reaper'))`) 으로 단일 인스턴스화. 다중 replica 배포 안전.

### 4.12 Buyer Download URL 발급 (`POST /v1/orders/{id}/download-urls`)

- **FR-60**: 요청 body 선택적: `{"ttl_seconds": int|null}`. 미지정 시 기본 24h (`86400`). 허용 범위 `3600..604800` (1h..7d AWS S3 SigV4 상한, 리서치 §4.4.1).
- **FR-61**: 서버 검증 — `order.status == 'ready_for_download'` AND `now() < order.expires_at`. 위반 시:
  - `order.status ∈ {queued, fetching, ...}` → `409 ERR_ORDER_NOT_READY`.
  - `order.status = expired` 또는 `now() > expires_at` → `410 ERR_ORDER_EXPIRED`.
  - `order.status = cancelled/failed` → `410 ERR_ORDER_TERMINAL`.
- **FR-62**: Tier 별 TTL 상한 — preview: 24h, paid: 7d. 요청 `ttl_seconds` 가 tier 상한 초과 → `422 ERR_URL_TTL_EXCEEDED`.
- **FR-63**: 각 `order_item` 에 연결된 `instance` row 의 object_key 를 boto3 `generate_presigned_url('get_object', ExpiresIn=ttl_seconds)` 로 서명. `ResponseContentDisposition=attachment; filename="<pseudo_sop_uid>.dcm"` 고정. 서명 실패 시 `502 ERR_URL_MINT_FAILED`.
- **FR-64**: 응답 `200 OK` + `DownloadUrlBatch`(§6.4):
  ```jsonc
  {
    "order_id":     "ord_01H...",
    "ttl_seconds":  86400,
    "expires_at":   "2026-04-23T10:00:00Z",
    "items": [
      {
        "pseudo_study_uid": "2.25.xxx",
        "files": [
          { "object_key":"staging/ord_01H.../hosp_abc/.../0001.dcm",
            "bytes": 513222, "sha256":"abcd...", "url":"https://s3.ap-northeast-2.amazonaws.com/..." }
        ]
      }
    ],
    "total_bytes": 94321012,
    "minted_at":   "2026-04-22T10:00:00Z"
  }
  ```
- **FR-65**: 각 URL 에 대해 `download_event` row insert — `event_type='url_minted'`, `signature_hash=sha256(signature)[:16]` (리서치 §4.6.1), `kid8=buyer_api_key.kid`, `src_ip=X-Forwarded-For chain head`, `user_agent=User-Agent` 헤더.
- **FR-66**: **Refresh 패턴** — 같은 주문에 대해 본 엔드포인트를 여러 번 호출하면 매번 새 서명·새 `minted_at` 로 fresh batch 반환. 이전 URL 은 TTL 까지 유효 (AWS S3 SigV4 revocation 불가).
- **FR-67**: Rate-limit — buyer 별 URL mint 1 req/5s (burst 10). 초과 → `429 ERR_URL_MINT_RATE`.
- **FR-68**: 응답 body `files[]` 은 원본 UID · 병원명 · 환자명 어떤 PHI 도 포함하지 않는다. `object_key` 는 가명 UID 기반이며 버킷 prefix 외엔 `pseudo_*` 만 포함 (central-ingest §6 FR-6 정합).

### 4.13 Download Audit + Optional S3 Access Log ETL

- **FR-69**: `download_event` append-only 테이블 (§6.3). `radivault_fulfillment_app` 역할에 INSERT 만 GRANT.
- **FR-70**: 4 이벤트 타입 — `url_minted`(FR-65 필수), `get_started`(S3 access log ETL, v0.1.1 best-effort), `get_completed`(동), `get_failed`(동). v0.1 은 `url_minted` 만 필수.
- **FR-71**: `download_event.signature_hash` 중복이 다른 `src_ip` · `user_agent` 에서 감지되면 background job `fulfillment-audit-sharing-detector` 가 warn 로그. v0.1.1 이상에서 operator alert.
- **FR-72**: S3 Access Log ETL (v0.1.1 backlog) — nightly batch 가 S3 Server Access Log 를 parse → `url_minted` 와 `signature_hash` 로 join → 불일치 (URL 없이 다운로드됨, 이론상 불가) 감지 시 SEV-1. v0.1 은 스텁 (ETL job 없음, Lifecycle/로그 설정만 문서화).

### 4.14 Order TTL + Cleanup

- **FR-73**: 주문 `ready_for_download` 전이 시 `expires_at = now() + config.order_ttl_seconds` (기본 604800 = 7 days, tier 별 override 가능).
- **FR-74**: Background task `fulfillment-expiry-ticker` (60 초 주기) — `SELECT * FROM order WHERE status='ready_for_download' AND expires_at < now() LIMIT 100` → `UPDATE status='expired', expired_at=now()` + outbox `order.expired`.
- **FR-75**: `expired` 주문에 대한 `POST /v1/orders/{id}/download-urls` 호출 → `410 ERR_ORDER_EXPIRED`.
- **FR-76**: S3 Lifecycle rule 문서화 — `staging/<order_id>/` prefix 는 `order.expires_at + 1d` 이후 자동 삭제 (AWS S3 Lifecycle `tag-based expiry` 또는 prefix 별 고정 TTL rule). v0.1 은 **고정 8일 prefix TTL** (7 days order TTL + 1 day buffer) — order TTL 변경 옵션은 v0.1.1.
- **FR-77**: 수동 cleanup CLI — `fulfillment-admin order expire-stale [--dry-run]` 는 expiry-ticker 수동 실행 동등물. 운영자가 TTL 계산 버그 의심 시 사용.

### 4.15 Cancellation 중 Unlinked Study 처리

- **FR-78**: `fetching|staging_*` 상태에서 admin 이 `fulfillment-admin order cancel --force --id ord_...` 실행 → `order.status='cancelled'` 전이 + `cancel_requested=true` 플래그 설정. 이미 업로드된 study 는 `unlinked_study` 테이블에 `(pseudo_study_uid, original_order_pk, detached_at, disposition='available_for_reassignment')` row insert.
- **FR-79**: `unlinked_study` 는 v0.1 에서 **수동 관리** — admin 이 CLI `fulfillment-admin unlinked list` / `reassign --study-uid ... --new-order-id ...` 로 조회·할당. 자동 할당 (spot claim) 은 v0.1.1 백로그.
- **FR-80**: Buyer `fetching` 상태에서 cancel 시도 → `409 ERR_ORDER_STATE_TRANSITION`, `hint="admin cancellation required; contact support"`. buyer 는 자기가 취소 요청했다는 사실을 별도 채널로 RadiVault 에 전달.

### 4.16 Observability

- **FR-81**: Prometheus 메트릭 (prefix `radivault_fulfillment_`):
  - `radivault_fulfillment_order_submissions_total` (counter, labels `tier, status`).
  - `radivault_fulfillment_order_state_duration_seconds` (histogram, label `state` — 각 상태 residence time).
  - `radivault_fulfillment_order_end_to_end_seconds` (histogram, labels `tier, path ∈ {hot,cold,mixed}`).
  - `radivault_fulfillment_transfer_job_queue_depth` (gauge, label `hospital_id`).
  - `radivault_fulfillment_transfer_job_claim_total` (counter, label `hospital_id`).
  - `radivault_fulfillment_transfer_job_completion_seconds` (histogram, label `hospital_id`).
  - `radivault_fulfillment_transfer_job_failures_total` (counter, labels `hospital_id, reason_code`).
  - `radivault_fulfillment_dlq_depth` (gauge).
  - `radivault_fulfillment_url_mint_total` (counter, label `tier`).
  - `radivault_fulfillment_url_mint_rate_limited_total` (counter).
  - `radivault_fulfillment_download_bytes_total` (counter, label `tier`) — S3 Access Log ETL 기반 (v0.1.1).
  - `radivault_fulfillment_cancellation_total` (counter, labels `tier, from_state, actor`).
  - `radivault_fulfillment_expired_orders_total` (counter).
  - `radivault_fulfillment_auth_failures_total` (counter, labels `plane, reason`).
  - `radivault_fulfillment_outbox_backlog` (gauge).
- **FR-82**: JSON 로그 필수 필드 — `ts, level, logger, msg, trace_id, request_id, buyer_id_hash|hospital_id, tier|null, endpoint, status, duration_ms, order_id|null, transfer_job_id|null`. 금지 필드 (§6.7) 재천명.
- **FR-83**: OpenTelemetry span 이름 — `order.create`, `order.validate`, `order.queue_transfer_jobs`, `transfer_job.claim`, `transfer_job.progress`, `transfer_job.complete`, `order.staging_copy`, `order.ready`, `download.mint`, `order.expire`.
- **FR-84**: 알람 기본 임계 (Prometheus + Alertmanager):
  - p95 `radivault_fulfillment_order_end_to_end_seconds{path="hot"}` > 60 s (5 분 평균) → warn.
  - p95 `radivault_fulfillment_order_end_to_end_seconds{path="cold"}` > 3600 s → warn.
  - `radivault_fulfillment_dlq_depth` > 10 → crit.
  - `radivault_fulfillment_outbox_backlog` > 1000 → warn.
  - `radivault_fulfillment_transfer_job_queue_depth{hospital_id=X}` > 50 sustained 10 min → warn (Gateway 장애 의심).

### 4.17 Admin CLI — `fulfillment-admin`

- **FR-85**: CLI 바이너리 `fulfillment-admin`. central-ingest `ingest-admin` 과 동일 스타일 (BSD sysexits, `--json`, `--dry-run`, `--no-color`, `-c/--config`). 명령 트리:
  ```
  fulfillment-admin
  ├── order
  │   ├── inspect       --order-id OID [--json]
  │   ├── list          [--buyer-id BID] [--status STATE] [--since TS] [--limit N] [--json]
  │   ├── force-advance --order-id OID --to STATE --reason STR [--dry-run]
  │   ├── cancel        --order-id OID [--force] --reason STR [--dry-run]
  │   └── expire-stale  [--dry-run]
  ├── transfer-job
  │   ├── inspect       --job-id TJID [--json]
  │   ├── requeue       --job-id TJID [--reset-attempts] [--dry-run]
  │   └── release-lease --job-id TJID [--dry-run]
  ├── dlq
  │   ├── dump          [--limit N] [--json]
  │   ├── requeue       --job-id TJID [--reset-attempts] [--dry-run]
  │   └── fail          --job-id TJID --reason STR [--dry-run]
  ├── download
  │   ├── audit         --order-id OID [--json]
  │   └── mint-stats    --since TS --until TS [--json]
  ├── unlinked
  │   ├── list          [--json]
  │   └── reassign      --study-uid UID --new-order-id OID [--dry-run]
  ├── migrate
  │   ├── current
  │   └── up            [--revision REV] [--dry-run]
  └── version           [--json]
  ```

---

## 5. 비기능 요구사항

| 항목 | 요구 |
|------|------|
| **성능** | `POST /v1/orders` 검증 + `202` 응답 p95 < 2 s (500 study 코호트). `GET /v1/orders/{id}` p95 < 300 ms. `POST /v1/orders/{id}/download-urls` p95 < 1 s (50 object). `GET /v1/gateway/transfer-jobs?wait=30s` return latency: job 있을 시 p95 < 150 ms, no-content 시 wait 에 의존. `POST /v1/gateway/transfer-jobs/{id}/progress` p95 < 100 ms. `/healthz` p95 < 30 ms. `/readyz` p95 < 200 ms. |
| **End-to-end SLA** | Order submit → `ready_for_download` — **Hot Storage hit 전량 p95 < 30 s**, **cold path 100 study 코호트 p95 < 1 h** (Gateway PACS 100 Mbps 가정, 리서치 §6 item 6). 단, PACS 대역폭 실측 필요, 파일럿 후 재평가. |
| **처리량** | 동시 주문 50 buyer × 5 in-flight = 250 active orders. transfer-job pool ≤ hospital 수 × 2 concurrency. URL mint 200 req/s sustained (50 buyer × 4 req/s). |
| **Lease** | transfer_job lease TTL 15 분 고정 (config override 가능 5–60 min). Reaper 60 초 주기. |
| **Long-poll** | `wait` 기본 30 s, max 60 s (ALB idle timeout 배려). HTTP/2 keep-alive 활용. |
| **Download TTL** | 기본 24 h, tier 별 최대: preview=24h, paid=7d. AWS S3 SigV4 `X-Amz-Expires` 7d 상한 준수. |
| **주문 TTL** | `ready_for_download → expired` 7 days 기본, config 오버라이드 허용 (1–14 d). |
| **가용성** | v0.1 best-effort, v0.2 paid tier SLA 99.9%. 배포 중 롤링 업데이트 무중단. |
| **확장성** | Stateless 서비스, gunicorn workers × replicas 수평 확장. 주문 수 100K/월 까지 단일 PG 노드 + 월 파티션. 10M+ 는 read replica + partition pruning. |
| **보안** | TLS 1.3 only (전방 nginx/ALB 종단). PG 역할 분리: `radivault_fulfillment_app` (SELECT + INSERT 주요, UPDATE 제한). 키 해시 argon2id (버이어 · Gateway plane 양쪽 재사용). 응답 · 로그 어디에도 PHI 없음. 컨테이너 non-root UID 10001. |
| **로깅·감사** | 모든 주문 생성 · 전이 · URL mint · cancellation · DLQ 이벤트는 `order_state_history` 또는 `download_event` 에 append-only 기록. 5년 보존. raw Idempotency-Key · API key plaintext · presigned URL raw 저장 금지. |
| **관측성** | JSON 로그 + Prometheus + OTel. 대시보드 지표: 주문 lifecycle 시계열, transfer-job 대기열, URL mint rate, DLQ depth, 실패율. |
| **규제 적합성** | 개보법 제28조의8 — central-ingest 익명 게이트 이후 데이터만. 국외이전 audit trail 은 `download_event` + 5년 보존으로 충족. HIPAA safe harbor 는 ingest 경로 책임 (본 서비스 신규 리스크 없음). |
| **계약 호환** | central-ingest write 경로 영향 없음 (본 서비스는 `instance.object_key` 를 read-only 로 조회, 업로드는 Gateway 가 기존 `/v1/ingest/studies` 재사용). Alembic revision 0004 는 기존 테이블 구조를 변경하지 않으며 `study.central_object_present` 컬럼 **추가만** 한다 (§14 C-1). |
| **호환성** | Python 3.11, PostgreSQL 15/16, Redis 7+, Docker Engine 24+, Compose v2.20+. Ubuntu 22.04 LTS x86_64 (프로덕션). |

---

## 6. 데이터 모델

### 6.1 ER 다이어그램

```mermaid
erDiagram
    buyer ||--o{ "order" : "places"
    buyer_api_key ||--o{ "order" : "authenticates"
    "order" ||--o{ order_item : "contains"
    "order" ||--o{ transfer_job : "fans_out_to"
    "order" ||--o{ order_state_history : "logs"
    "order" ||--o{ order_outbox : "emits"
    "order" ||--o{ download_event : "mints"
    "order" ||--o{ order_idempotency_mirror : "dedups"
    hospital ||--o{ transfer_job : "services"
    order_item }o--|| study : "references"
    transfer_job ||--o{ transfer_job_dead_letter : "on_fail"
    order_item ||--o{ unlinked_study : "on_cancel"
    download_event }o--|| order_item : "targets"
```

- `buyer`, `buyer_api_key` 는 **metadata-index §6.2 상속** (read-only 재사용).
- `hospital`, `study`, `series`, `instance` 는 **central-ingest §6 상속** (read-only 재사용, `study.central_object_present` 컬럼 추가, §14 C-1).
- 신규 테이블 (본 dev-spec) 7종: `order`, `order_item`, `transfer_job`, `transfer_job_dead_letter`, `download_event`, `order_state_history`, `order_outbox`, `order_idempotency_mirror`, `unlinked_study` — 실제 9 테이블 (일부 "핵심 5" + 보조 4).

### 6.2 PostgreSQL 스키마 — Order & Items

```sql
CREATE TABLE "order" (
    order_pk              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id              TEXT NOT NULL UNIQUE,            -- 'ord_<ulid>'
    buyer_pk              BIGINT NOT NULL REFERENCES buyer(buyer_pk),
    kid                   TEXT NOT NULL,                    -- buyer_api_key.kid (감사 추적)
    status                TEXT NOT NULL,                    -- FSM state
    status_billing        TEXT NOT NULL DEFAULT 'pending_billing',
    n_studies             INTEGER NOT NULL,
    total_bytes           BIGINT NOT NULL,
    total_estimated_usd   NUMERIC(12,2) NOT NULL,
    tier                  TEXT NOT NULL,                    -- 'preview' | 'paid' (denormalized)
    agreement_hash        CHAR(64) NOT NULL,
    path_type             TEXT,                             -- 'hot' | 'cold' | 'mixed' | NULL(pre-queue)
    notes                 TEXT,
    submitted_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    validated_at          TIMESTAMPTZ,
    queued_at             TIMESTAMPTZ,
    staging_complete_at   TIMESTAMPTZ,
    ready_at              TIMESTAMPTZ,
    expires_at            TIMESTAMPTZ,
    cancelled_at          TIMESTAMPTZ,
    expired_at            TIMESTAMPTZ,
    delivered_at          TIMESTAMPTZ,
    failed_at             TIMESTAMPTZ,
    last_error_code       TEXT,
    last_error_detail     TEXT,
    cancel_requested      BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX idx_order_buyer_status     ON "order"(buyer_pk, status);
CREATE INDEX idx_order_status_expires   ON "order"(status, expires_at)
  WHERE status IN ('ready_for_download','delivering');
CREATE INDEX idx_order_submitted_desc   ON "order"(buyer_pk, submitted_at DESC);

CREATE TABLE order_item (
    order_item_pk         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_pk              BIGINT NOT NULL REFERENCES "order"(order_pk),
    pseudo_study_uid      TEXT NOT NULL,
    hospital_pk           BIGINT NOT NULL REFERENCES hospital(hospital_pk),
    source                TEXT NOT NULL,               -- 'hot_storage' | 'on_demand' | 'mixed'
    state                 TEXT NOT NULL,               -- 'pending'|'hot_hit_pending_copy'|'fetching'|'staged'|'hot_hit_staged'|'copied'|'failed'
    n_instances           INTEGER,
    total_bytes           BIGINT,
    staged_at             TIMESTAMPTZ,
    last_error            TEXT,
    UNIQUE (order_pk, pseudo_study_uid)
);
CREATE INDEX idx_order_item_order         ON order_item(order_pk);
CREATE INDEX idx_order_item_hospital_state ON order_item(hospital_pk, state);
```

### 6.3 PostgreSQL 스키마 — Transfer Job · DLQ · Download Event

```sql
CREATE TABLE transfer_job (
    transfer_job_pk       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transfer_job_id       TEXT NOT NULL UNIQUE,         -- 'tj_<ulid>'
    order_pk              BIGINT NOT NULL REFERENCES "order"(order_pk),
    hospital_pk           BIGINT NOT NULL REFERENCES hospital(hospital_pk),
    state                 TEXT NOT NULL,                 -- 'queued'|'claimed'|'completed'|'failed'|'dead'
    lease_owner           TEXT,                          -- gateway_id
    lease_expires_at      TIMESTAMPTZ,
    claimed_at            TIMESTAMPTZ,
    completed_at          TIMESTAMPTZ,
    attempt_count         INTEGER NOT NULL DEFAULT 0,
    last_error_code       TEXT,
    last_error_detail     TEXT,
    studies               JSONB NOT NULL,                -- [{pseudo_study_uid,expected_instances,priority}]
    n_fetched             INTEGER NOT NULL DEFAULT 0,
    n_deided              INTEGER NOT NULL DEFAULT 0,
    n_uploaded            INTEGER NOT NULL DEFAULT 0,
    ruleset_version_required TEXT NOT NULL,
    salt_version_required INTEGER NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (order_pk, hospital_pk)
);
CREATE INDEX idx_transfer_job_hospital_state
  ON transfer_job(hospital_pk, state, created_at);
CREATE INDEX idx_transfer_job_lease_expiry
  ON transfer_job(lease_expires_at)
  WHERE state = 'claimed';
CREATE INDEX idx_transfer_job_order ON transfer_job(order_pk);

CREATE TABLE transfer_job_dead_letter (
    dlq_pk                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transfer_job_pk       BIGINT NOT NULL REFERENCES transfer_job(transfer_job_pk),
    dead_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason_code           TEXT NOT NULL,
    reason_detail         TEXT,
    attempts              INTEGER NOT NULL,
    resolved_at           TIMESTAMPTZ,
    resolved_by           TEXT,
    resolution            TEXT                            -- 'requeued'|'failed_final'
);
CREATE INDEX idx_dlq_unresolved
  ON transfer_job_dead_letter(dead_at DESC)
  WHERE resolved_at IS NULL;

CREATE TABLE download_event (
    event_pk              BIGINT GENERATED ALWAYS AS IDENTITY,
    order_pk              BIGINT NOT NULL REFERENCES "order"(order_pk),
    order_item_pk         BIGINT REFERENCES order_item(order_item_pk),
    buyer_pk              BIGINT NOT NULL REFERENCES buyer(buyer_pk),
    kid                   TEXT NOT NULL,
    event_type            TEXT NOT NULL,                 -- 'url_minted'|'get_started'|'get_completed'|'get_failed'
    ts                    TIMESTAMPTZ NOT NULL DEFAULT now(),
    src_ip                INET,
    user_agent            TEXT,
    bytes_transferred     BIGINT,
    http_status           INTEGER,
    request_id            TEXT NOT NULL,
    object_key            TEXT,
    signature_hash        CHAR(16),
    ttl_seconds           INTEGER,
    PRIMARY KEY (event_pk, ts)
) PARTITION BY RANGE (ts);

CREATE INDEX idx_download_event_buyer_time
  ON download_event(buyer_pk, ts DESC);
CREATE INDEX idx_download_event_order
  ON download_event(order_pk);
CREATE INDEX idx_download_event_signature
  ON download_event(signature_hash)
  WHERE signature_hash IS NOT NULL;
```

### 6.4 PostgreSQL 스키마 — Audit · Outbox · Unlinked · Idempotency

```sql
CREATE TABLE order_state_history (
    history_pk            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_pk              BIGINT NOT NULL REFERENCES "order"(order_pk),
    from_state            TEXT,
    to_state              TEXT NOT NULL,
    event                 TEXT NOT NULL,
    actor                 TEXT NOT NULL,                 -- 'buyer'|'gateway'|'admin'|'system'|'timer'
    actor_ref             TEXT,                           -- buyer_pk|gateway_id|admin_user
    reason                TEXT,
    at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_order_history_order_time
  ON order_state_history(order_pk, at DESC);

CREATE TABLE order_outbox (
    outbox_pk             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_pk              BIGINT REFERENCES "order"(order_pk),
    transfer_job_pk       BIGINT REFERENCES transfer_job(transfer_job_pk),
    event_type            TEXT NOT NULL,
    payload               JSONB NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    dispatched_at         TIMESTAMPTZ,
    last_attempt_at       TIMESTAMPTZ,
    attempts              INTEGER NOT NULL DEFAULT 0,
    last_error            TEXT
);
CREATE INDEX idx_outbox_undispatched
  ON order_outbox(created_at)
  WHERE dispatched_at IS NULL;

CREATE TABLE unlinked_study (
    unlinked_pk           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pseudo_study_uid      TEXT NOT NULL,
    hospital_pk           BIGINT NOT NULL REFERENCES hospital(hospital_pk),
    original_order_pk     BIGINT REFERENCES "order"(order_pk),
    detached_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    disposition           TEXT NOT NULL DEFAULT 'available_for_reassignment',
    reassigned_to_order_pk BIGINT REFERENCES "order"(order_pk),
    reassigned_at         TIMESTAMPTZ,
    note                  TEXT
);
CREATE INDEX idx_unlinked_available
  ON unlinked_study(hospital_pk, detached_at)
  WHERE disposition = 'available_for_reassignment';

CREATE TABLE order_idempotency_mirror (
    key                   TEXT NOT NULL,
    buyer_pk              BIGINT NOT NULL REFERENCES buyer(buyer_pk),
    first_seen_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    response_sha256       BYTEA NOT NULL,
    response_status_code  INTEGER NOT NULL,
    order_pk              BIGINT REFERENCES "order"(order_pk),
    PRIMARY KEY (key, buyer_pk)
);
CREATE INDEX idx_order_idemp_mirror_time
  ON order_idempotency_mirror(first_seen_at);
```

**GRANT 정책** (Alembic 0004 에서 적용):

```sql
CREATE ROLE radivault_fulfillment_app NOINHERIT;
ALTER ROLE radivault_fulfillment_app SET statement_timeout = '15s';
ALTER ROLE radivault_fulfillment_app SET lock_timeout = '2s';
ALTER ROLE radivault_fulfillment_app SET idle_in_transaction_session_timeout = '10s';

GRANT CONNECT ON DATABASE radivault_central TO radivault_fulfillment_app;
GRANT USAGE ON SCHEMA public TO radivault_fulfillment_app;

-- central-ingest 테이블 (read-only)
GRANT SELECT ON study, series, instance, patient_pseudo, hospital, auth_token
  TO radivault_fulfillment_app;

-- metadata-index 테이블 (read-only)
GRANT SELECT ON buyer, buyer_api_key TO radivault_fulfillment_app;

-- fulfillment 테이블 (RW)
GRANT SELECT, INSERT, UPDATE ON
  "order", order_item, transfer_job, order_outbox, unlinked_study,
  order_idempotency_mirror
  TO radivault_fulfillment_app;

-- Append-only
GRANT SELECT, INSERT ON
  transfer_job_dead_letter, download_event, order_state_history
  TO radivault_fulfillment_app;
-- UPDATE/DELETE 미부여 on append-only
```

### 6.5 JSON/Pydantic 스키마 — 요청·응답

```python
# src/radivault_fulfillment/api/schemas.py

class OrderRequest(BaseModel):
    pseudo_study_uids: list[str] = Field(..., min_length=1, max_length=10000)
    agreement_hash:    str = Field(..., pattern=r"^[0-9a-f]{64}$")
    notes:             str | None = Field(None, max_length=512)
    preferred_download_ttl_hours: int | None = Field(None, ge=1, le=168)

class OrderItemSummary(BaseModel):
    pseudo_study_uid: str
    hospital_opaque_id: str
    source:           Literal["hot_storage","on_demand","mixed"]
    state:            str
    n_instances:      int | None
    total_bytes:      int | None

class OrderResponse(BaseModel):
    order_id:            str
    state:               str
    state_billing:       str          # "pending_billing"
    n_studies:           int
    total_bytes:         int
    total_estimated_usd: float
    tier:                str
    path_type:           str | None
    submitted_at:        datetime
    estimated_ready_at:  datetime | None
    ready_at:            datetime | None
    expires_at:          datetime | None
    cancelled_at:        datetime | None
    progress:            float         # 0..1
    eta_seconds:         int | None
    items:               list[OrderItemSummary]    # GET /{id} 만, POST 는 빈 배열
    transfer_jobs:       list[TransferJobSummary]  # GET /{id} 만
    last_error:          dict | None

class TransferJobSummary(BaseModel):
    transfer_job_id:   str
    hospital_id:       str
    state:             str
    attempt_count:     int
    lease_expires_at:  datetime | None
    last_error:        str | None

class TransferJobClaim(BaseModel):
    transfer_job_id:            str
    order_id:                   str
    hospital_id:                str
    studies:                    list[dict]         # [{pseudo_study_uid,expected_instances,priority}]
    lease_expires_at:           datetime
    ruleset_version_required:   str
    salt_version_required:      int
    cancel_requested:           bool

class ProgressReport(BaseModel):
    n_fetched:    int = Field(..., ge=0)
    n_deided:     int = Field(..., ge=0)
    n_uploaded:   int = Field(..., ge=0)
    lease_extend: bool = True

class CompletionReportItem(BaseModel):
    pseudo_study_uid: str
    n_instances:      int
    total_bytes:      int
    status:           Literal["uploaded","skipped","quarantined"]
    central_job_ids:  list[str] = []

class CompletionReport(BaseModel):
    manifest: list[CompletionReportItem]
    audit_ref: dict | None = None

class FailureReport(BaseModel):
    reason_code: Literal["PACS_UNAVAILABLE","DEID_FAILED","UPLOAD_FAILED",
                         "BURNED_IN_BLOCKED","OTHER"]
    details:     str = Field(..., max_length=2048)
    retryable:   bool

class DownloadUrlBatchRequest(BaseModel):
    ttl_seconds: int | None = Field(None, ge=3600, le=604800)

class DownloadFile(BaseModel):
    object_key: str
    bytes:      int
    sha256:     str
    url:        str

class DownloadItem(BaseModel):
    pseudo_study_uid: str
    files:            list[DownloadFile]

class DownloadUrlBatch(BaseModel):
    order_id:    str
    ttl_seconds: int
    expires_at:  datetime
    minted_at:   datetime
    items:       list[DownloadItem]
    total_bytes: int
```

### 6.6 Config YAML 스키마 (fulfillment 서비스 + Gateway transfer 추가)

```yaml
# /etc/radivault-fulfillment/fulfillment.yml
version: 1

app:
  env: "prod"
  api_contract_version: "1"
  workers: 5
  port: 8002

db:
  dsn: "${env:FULFILLMENT_APP_DSN}"
  admin_dsn: "${env:FULFILLMENT_ADMIN_DSN}"
  pool_size: 30
  max_overflow: 20

redis:
  url: "${env:REDIS_URL}"
  auth_cache_ttl_seconds: 60
  idempotency_ttl_seconds: 86400
  long_poll_channel_prefix: "transfer_job_hospital:"

storage:
  provider: "s3"
  endpoint_url: "${env:S3_ENDPOINT_URL}"
  region: "ap-northeast-2"
  bucket: "radivault-ingest-prod"
  staging_prefix: "staging/"
  ingest_prefix: "ingest/"
  kms_key_arn: "${env:S3_KMS_KEY_ARN}"
  presign:
    default_ttl_seconds: 86400
    min_ttl_seconds:     3600
    max_ttl_seconds:     604800

order:
  ttl_seconds: 604800                # 7 days
  estimated_ready_seconds_per_study_hot: 0.5
  estimated_ready_seconds_per_study_cold: 36
  tier_defaults:
    preview:
      max_cohort_size: 50
      max_order_bytes: 10737418240    # 10 GB
      daily_order_quota: 5
      download_ttl_max_seconds: 86400
      unit_price_usd: 5.0
    paid:
      max_cohort_size: 10000
      max_order_bytes: 2199023255552  # 2 TB
      daily_order_quota: 50
      download_ttl_max_seconds: 604800
      unit_price_usd: 5.0

transfer_job:
  lease_ttl_seconds: 900              # 15 min
  max_retries: 5
  retry_backoff_initial_seconds: 60
  retry_backoff_factor: 2
  retry_backoff_cap_seconds: 3600
  long_poll_wait_max_seconds: 60
  hospital_concurrency_cap: 2

download:
  rate_limit_mint_per_5s: 1
  rate_limit_mint_burst: 10
  access_log_etl_enabled: false       # v0.1 default off

audit:
  agreement_hash_current: "${env:AGREEMENT_HASH_CURRENT}"

observability:
  log_level: "INFO"
  json_logs: true
  otlp_endpoint: "${env:OTEL_EXPORTER_OTLP_ENDPOINT}"
  metrics_path: "/metrics"
  sentry_dsn: "${env:SENTRY_DSN}"

lease_reaper:
  interval_seconds: 60
  batch_size: 200

outbox_poller:
  interval_seconds: 2
  batch_size: 100

expiry_ticker:
  interval_seconds: 60
  batch_size: 100
```

**Gateway 측 추가 subtree** (`/etc/radivault/gateway.yml` 에 병합, dev-spec-gateway-agent §6.2 확장):

```yaml
transfer:
  enabled: true
  central_url: "https://fulfillment.radivault.io"
  auth_token: "${file:/run/credentials/upload_token}"     # 기존 central.upload_token 와 동일 토큰 재사용 가능
  poll_wait_seconds: 30
  max_concurrent_jobs: 2
  lease_extend_interval_seconds: 300                      # 5 min 마다 progress ping (lease 15 min 중 3회)
  progress_report_interval_seconds: 60                    # n_fetched/n_deided/n_uploaded 갱신 주기
  retry_backoff_initial_seconds: 30
  retry_backoff_factor: 2
  retry_backoff_cap_seconds: 600
```

### 6.7 법적·보안 고려 (6.x Mandatory)

- **§6.7.1 PHI 무포함 보증**: 본 서비스는 central-ingest 의 `anonymization_flag='fully_anonymized'` 게이트를 통과한 객체만 참조. 응답 body · 로그 · presigned URL path · audit 레코드 어디에도 원본 UID · 환자 식별자 · 병원 내부 호스트명이 노출되지 않는다.
- **§6.7.2 Presigned URL TTL 규율**: 기본 24 h, 최대 7 d. AWS S3 SigV4 `X-Amz-Expires` 7 d 상한 (리서치 §4.4.1) 준수. **URL revocation 은 기술적으로 불가**(§6.7.5) 하므로 기본 TTL 을 짧게 유지하고 refresh 로 연장.
- **§6.7.3 Buyer scope 강제**: `scope_json.exclude_hospitals` 는 application-layer 에서 쿼리 시 자동 적용 (`AND study.hospital_pk <> ALL(:exclude)`). buyer 가 request body 로 scope override 를 시도할 수 없다 — pydantic 모델에 해당 필드 미노출. PG RLS 기반 집행은 v0.1.1 백로그.
- **§6.7.4 Cross-border delivery audit**: 모든 `download_event.url_minted` row 는 `src_ip, user_agent, buyer_pk, order_pk, signature_hash, ttl_seconds, ts` 를 기록하며 5 년 보존 (central-ingest §4.10 Audit Log 정책 상속). 법무팀이 "언제 누가 어떤 익명 영상을 해외로 다운받았는가" 를 재구성할 수 있다.
- **§6.7.5 Revocation 한계 명시**: AWS S3 presigned URL 은 mid-stream revoke 불가 (공식 입장, 리서치 §4.4.4). 운영 runbook 에 (a) 짧은 기본 TTL, (b) refresh API 로 회수 대체, (c) 최후 수단으로 KMS key rotation (전체 URL 무력화), (d) S3 bucket policy 임시 deny 명시.
- **§6.7.6 MSA/DPA 플레이스홀더**: `agreement_hash` (FR-16) 는 버이어가 클릭랩 동의한 MSA v0.1 본문의 sha256 해시. 주문 row 에 저장하여 어떤 약관으로 계약이 성사되었는지 재구성 가능. 표준 MSA 필수 조항 — (a) **Cancellation & Refund**: queued 이전 자유 취소, fetching 이후 no refund; (b) **Cross-border delivery audit**: `download_event` 5년 보존 + 국외 buyer 통지 의무 여부 법률 자문 필요 (§11 Q9); (c) `pending_billing` 조항 — 본 주문은 결제 시스템 도입 전이므로 무상 제공임을 e-signed 확인. 법률 자문 착수 타이밍은 §11 Q10.
- **§6.7.7 Cancellation-during-fetch 데이터 처리**: `fetching|staging_*` 상태에서 admin 이 force cancel 시 이미 업로드된 study 는 `unlinked_study` 테이블로 이관 (FR-78). `order_item` 에서는 연결 끊김 (`order_pk` 는 원본 주문 참조로 남으나 `disposition` 이 buyer 접근을 차단). buyer 의 어떤 API 에서도 해당 study 는 보이지 않는다.
- **§6.7.8 Idempotency-Key 감사**: raw key 는 Redis · PG mirror 에 최대 7d+24h 보관 후 삭제. SRE 에게도 mirror 의 key 컬럼은 접근 제한 (search_admin 역할에 GRANT 없음).
- **§6.7.9 에러 메시지 스키마 비노출**: 에러 응답의 `detail` 필드는 필드 이름 수준만 (예: `"order state 'fetching' does not allow buyer cancel"`) — SQL 조각·테이블 이름·내부 FSM 내부 표현은 노출하지 않는다 (design-spec-central-ingest §2 재사용 원칙).
- **§6.7.10 NLP 라벨 부재 선언**: v0.1 은 진단명 · ICD-10 · RadLex 필드를 주문 응답이나 download manifest 에 포함하지 않는다. NLP 라벨 도입 시 별도 dev-spec + contract delta.

### 6.8 금지 필드 (PHI · IP 오염 방지)

로그 · 감사 테이블 · Prometheus 라벨 · 응답 바디 · presigned URL path 어디에서도 금지:

- 원본 `StudyInstanceUID`, `SeriesInstanceUID`, `SOPInstanceUID`, `FrameOfReferenceUID`.
- 환자 이름 · 생년월일 · 주소 · 주민등록번호 · 전화 · email · 그리고 해당 변환 없는 해시.
- 병원 내부 호스트명 (`pacs.hospital.local` 등), 내부 IP.
- API key 평문 · Bearer 토큰 raw · presigned URL raw query string.
- Raw Idempotency-Key (hash 만 mirror 에 저장 허용).
- buyer_contact 개인명 · 연락처 (buyer 는 B2B 법인; 담당자 정보는 metadata-index 의 `buyer_contact` 테이블로 분리 저장 — v0.1.1 backlog).

허용: 가명 UID, `order_id`, `transfer_job_id`, `hospital_opaque_id` (per-buyer salt sha256), `buyer_id_hash`, `kid8`, `signature_hash` (16 bytes), `request_id`, HTTP 상태.

---

## 7. API 계약

모든 4xx/5xx 응답은 design-spec-central-ingest §2.2 envelope 를 따른다 — 필수 5 필드 `{error, detail, message_ko, message_en, request_id}` + 선택 `{doc_url, hint, retry_after}`. 성공 바디는 엔드포인트별 정의.

### 7.1 `POST /v1/orders`

```
Request:
  POST /v1/orders HTTP/1.1
  Host: fulfillment.radivault.io
  Authorization: Bearer rv_live_abcd1234_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  Idempotency-Key: 01HXXXABC...
  Content-Type: application/json
  X-Request-Id: <optional>

  {
    "pseudo_study_uids": ["2.25.aaa","2.25.bbb"],
    "agreement_hash":    "abcd1234...64hex",
    "notes":             "pilot cohort batch 3",
    "preferred_download_ttl_hours": 48
  }

Response 202 Accepted:
  {
    "order_id":             "ord_01HX...",
    "state":                "queued",
    "state_billing":        "pending_billing",
    "n_studies":            2,
    "total_bytes":          188642024,
    "total_estimated_usd":  10.0,
    "tier":                 "preview",
    "path_type":            null,
    "submitted_at":         "2026-04-22T10:00:00Z",
    "estimated_ready_at":   "2026-04-22T10:00:30Z",
    "ready_at":             null,
    "expires_at":           null,
    "cancelled_at":         null,
    "progress":             0.0,
    "eta_seconds":          30,
    "items":                [],
    "transfer_jobs":        [],
    "last_error":           null
  }

Errors:
  400 ERR_REQUEST_SCHEMA          pydantic validation failed
  400 ERR_ORDER_DUPLICATE_STUDY   pseudo_study_uid 중복
  400 ERR_ORDER_AGREEMENT_REQUIRED   agreement_hash 누락/불일치
  400 ERR_IDEMP_MISSING           Idempotency-Key header required
  400 ERR_IDEMP_FORMAT            key length/charset invalid
  401 ERR_AUTH_MISSING            Authorization 누락/형식오류
  401 ERR_AUTH_EXPIRED            key revoked/expired
  401 ERR_AUTH_WRONG_PLANE        Gateway 토큰으로 buyer 엔드포인트 호출
  403 ERR_ORDER_SCOPE_FORBIDDEN   buyer scope 또는 hospital access 위반
  404 ERR_ORDER_STUDY_NOT_FOUND   pseudo_study_uid 가 study 에 없음
  413 ERR_ORDER_TOO_LARGE         total_bytes 가 tier 상한 초과
  422 ERR_ORDER_TIER_EXCEEDED     cohort size 가 tier 상한 초과
  429 ERR_ORDER_QUOTA_EXCEEDED    daily quota 초과
  429 ERR_RATE_LIMITED            per-buyer 전역 rate 초과
  503 ERR_IDEMP_UNAVAILABLE       Redis 장애
  503 ERR_DB_UNAVAILABLE          Postgres 장애
  500 ERR_INTERNAL                unexpected
```

### 7.2 `GET /v1/orders`

```
Request:
  GET /v1/orders?status=ready_for_download,delivering&limit=50&cursor=... HTTP/1.1
  Authorization: Bearer rv_live_...

Response 200:
  {
    "items":       [ { "order_id":"ord_...","state":"...", ... } ],
    "next_cursor": "eyJ...",
    "has_next":    true,
    "page_size":   50
  }

Errors:
  400 ERR_REQUEST_SCHEMA
  400 ERR_CURSOR_VERSION
  401 ERR_AUTH_*
  429 / 503 (공통)
```

### 7.3 `GET /v1/orders/{id}`

```
Request:
  GET /v1/orders/ord_01HX... HTTP/1.1
  Authorization: Bearer rv_live_...

Response 200:
  <OrderResponse 전체 필드 (§6.5 OrderResponse)>

Errors:
  401 ERR_AUTH_*
  404 ERR_ORDER_NOT_FOUND         본인 주문 아니거나 존재하지 않음
  503 ERR_DB_UNAVAILABLE
```

### 7.4 `POST /v1/orders/{id}/cancel`

```
Request:
  POST /v1/orders/ord_01HX.../cancel HTTP/1.1
  Authorization: Bearer rv_live_...
  Idempotency-Key: ...

  {"reason": "changed mind"}          # optional

Response 200:
  {
    "order_id":         "ord_01HX...",
    "state":            "cancelled",
    "cancelled_at":     "2026-04-22T10:03:00Z",
    "refund_eligible":  false
  }

Errors:
  401 ERR_AUTH_*
  404 ERR_ORDER_NOT_FOUND
  409 ERR_ORDER_STATE_TRANSITION    현재 상태에서 cancel 불가 (hint 포함)
  429 / 503 (공통)
```

### 7.5 `POST /v1/orders/{id}/download-urls`

```
Request:
  POST /v1/orders/ord_01HX.../download-urls HTTP/1.1
  Authorization: Bearer rv_live_...

  {"ttl_seconds": 86400}              # optional; default tier default

Response 200:
  <DownloadUrlBatch — §6.5>

Errors:
  401 ERR_AUTH_*
  404 ERR_ORDER_NOT_FOUND
  409 ERR_ORDER_NOT_READY            status != ready_for_download
  410 ERR_ORDER_EXPIRED              expires_at 경과
  410 ERR_ORDER_TERMINAL             cancelled/failed
  422 ERR_URL_TTL_EXCEEDED           ttl_seconds > tier 상한
  429 ERR_URL_MINT_RATE              mint rate 초과
  502 ERR_URL_MINT_FAILED            boto3 서명 실패
  503 ERR_DB_UNAVAILABLE
```

### 7.6 `GET /v1/gateway/transfer-jobs?wait=30s`

```
Request:
  GET /v1/gateway/transfer-jobs?wait=30&max_jobs=1 HTTP/1.1
  Host: fulfillment.radivault.io
  Authorization: Bearer <gateway auth_token>
  Accept: application/json

Response 200 (job claimed):
  <TransferJobClaim §6.5>

Response 204 (empty queue, wait timeout):
  (empty body)
  Retry-After: 0

Errors:
  401 ERR_AUTH_*
  401 ERR_AUTH_WRONG_PLANE          buyer 토큰으로 호출
  403 ERR_JOB_HOSPITAL_MISMATCH     (내부 오류 방어적)
  429 ERR_RATE_LIMITED              long-poll 남발 방어
  503 ERR_DB_UNAVAILABLE
```

### 7.7 `POST /v1/gateway/transfer-jobs/{id}/progress`

```
Request:
  POST /v1/gateway/transfer-jobs/tj_01HX.../progress HTTP/1.1
  Authorization: Bearer <gateway auth_token>
  Idempotency-Key: ...

  {"n_fetched":120,"n_deided":118,"n_uploaded":110,"lease_extend":true}

Response 200:
  {"lease_expires_at":"2026-04-22T10:45:00Z","cancel_requested":false}

Errors:
  400 ERR_JOB_COUNTER_REGRESS
  401 ERR_AUTH_*
  403 ERR_JOB_LEASE_OWNERSHIP       내가 claim한 job 아님
  404 ERR_JOB_NOT_FOUND
  409 ERR_JOB_LEASE_EXPIRED         lease 만료 → 재claim 필요
  409 ERR_JOB_STATE_CONFLICT        state != 'claimed'
  503 ERR_DB_UNAVAILABLE
```

### 7.8 `POST /v1/gateway/transfer-jobs/{id}/complete`

```
Request:
  POST /v1/gateway/transfer-jobs/tj_01HX.../complete HTTP/1.1
  Authorization: Bearer <gateway auth_token>
  Idempotency-Key: ...

  {
    "manifest":[
      {"pseudo_study_uid":"2.25.xxx","n_instances":184,
       "total_bytes":94321012,"status":"uploaded",
       "central_job_ids":["ingest_01HX..."]}
    ],
    "audit_ref":{"seq":22345,"hash":"sha256:..."}
  }

Response 200:
  {"transfer_job_id":"tj_01HX...","state":"completed","order_state":"staging_complete"}

Errors:
  400 ERR_JOB_MANIFEST_MISMATCH
  401 ERR_AUTH_*
  403 ERR_JOB_LEASE_OWNERSHIP
  404 ERR_JOB_NOT_FOUND
  409 ERR_JOB_LEASE_EXPIRED
  409 ERR_JOB_STATE_CONFLICT
  503 ERR_DB_UNAVAILABLE
```

### 7.9 `POST /v1/gateway/transfer-jobs/{id}/fail`

```
Request:
  POST /v1/gateway/transfer-jobs/tj_01HX.../fail HTTP/1.1
  Authorization: Bearer <gateway auth_token>
  Idempotency-Key: ...

  {"reason_code":"PACS_UNAVAILABLE","details":"connection timeout after 3 retries","retryable":true}

Response 200:
  {"transfer_job_id":"tj_01HX...","state":"queued","attempt_count":2,"will_retry":true}

Errors:
  401 ERR_AUTH_*
  403 ERR_JOB_LEASE_OWNERSHIP
  404 ERR_JOB_NOT_FOUND
  409 ERR_JOB_STATE_CONFLICT
  503 ERR_DB_UNAVAILABLE
```

### 7.10 `GET /healthz`, `GET /readyz`, `GET /v1/version`

central-ingest §7.3–7.5 와 동일 스펙. `readyz` 3요소: PG ping + Redis ping + `alembic current == head`. S3 HEAD 는 optional (S3 장애가 주문 접수를 차단해야 할지 §11 Q6).

### 7.11 오류 코드 표 (전역 요약 — 신규 + 재사용)

| Code | HTTP | Category | 재사용/신규 |
|------|------|----------|-------------|
| `ERR_AUTH_MISSING` | 401 | Auth | 재사용 (central-ingest) |
| `ERR_AUTH_EXPIRED` | 401 | Auth | 재사용 |
| `ERR_AUTH_WRONG_PLANE` | 401 | Auth | **신규** — buyer↔gateway plane 혼용 |
| `ERR_AUTH_UNAVAILABLE` | 503 | Auth | **신규** — Redis cache + PG 양측 장애 |
| `ERR_IDEMP_MISSING` | 400 | Idemp | 재사용 |
| `ERR_IDEMP_FORMAT` | 400 | Idemp | 재사용 |
| `ERR_IDEMP_UNAVAILABLE` | 503 | Idemp | 재사용 |
| `ERR_REQUEST_SCHEMA` | 400 | Request | 재사용 (metadata-index) |
| `ERR_ORDER_DUPLICATE_STUDY` | 400 | Order | **신규** |
| `ERR_ORDER_AGREEMENT_REQUIRED` | 400 | Order | **신규** |
| `ERR_ORDER_SCOPE_FORBIDDEN` | 403 | Order | **신규** |
| `ERR_ORDER_STUDY_NOT_FOUND` | 404 | Order | **신규** |
| `ERR_ORDER_NOT_FOUND` | 404 | Order | **신규** |
| `ERR_ORDER_NOT_READY` | 409 | Order | **신규** |
| `ERR_ORDER_STATE_TRANSITION` | 409 | Order | **신규** |
| `ERR_ORDER_EXPIRED` | 410 | Order | **신규** |
| `ERR_ORDER_TERMINAL` | 410 | Order | **신규** |
| `ERR_ORDER_TOO_LARGE` | 413 | Order | **신규** |
| `ERR_ORDER_TIER_EXCEEDED` | 422 | Order | **신규** |
| `ERR_ORDER_QUOTA_EXCEEDED` | 429 | Order | **신규** |
| `ERR_URL_TTL_EXCEEDED` | 422 | URL | **신규** |
| `ERR_URL_MINT_RATE` | 429 | URL | **신규** |
| `ERR_URL_MINT_FAILED` | 502 | URL | **신규** |
| `ERR_JOB_NOT_FOUND` | 404 | Job | **신규** |
| `ERR_JOB_LEASE_OWNERSHIP` | 403 | Job | **신규** |
| `ERR_JOB_LEASE_EXPIRED` | 409 | Job | **신규** |
| `ERR_JOB_STATE_CONFLICT` | 409 | Job | **신규** |
| `ERR_JOB_HOSPITAL_MISMATCH` | 403 | Job | **신규** |
| `ERR_JOB_MANIFEST_MISMATCH` | 400 | Job | **신규** |
| `ERR_JOB_COUNTER_REGRESS` | 400 | Job | **신규** |
| `ERR_RATE_LIMITED` | 429 | Rate | 재사용 |
| `ERR_DB_UNAVAILABLE` | 503 | Infra | 재사용 |
| `ERR_INTERNAL` | 500 | Generic | 재사용 |

**신규 24 개** (target 12–18 대비 상향 — order + job 조합이 세분화됨). design-spec-order-fulfillment 가 각 코드에 5-field 포맷 (§13 Annex) 으로 풀어 쓴다.

---

## 8. 시퀀스·플로우

### 8.1 주문 생성 시퀀스

```
[Buyer] POST /v1/orders {pseudo_study_uids[], agreement_hash, ...}
   |
   v
[Auth middleware (buyer plane)]
   - Authorization: Bearer rv_live_...
   - kid lookup buyer_api_key, argon2 verify
   - attach (buyer_pk, tier, scope_json) to request context
   |
   v (fail → 401 ERR_AUTH_*)
[Rate-limit middleware (slowapi/Redis)]
   - per-buyer rpm + daily
   |
   v (fail → 429 ERR_RATE_LIMITED / ERR_ORDER_QUOTA_EXCEEDED)
[Idempotency middleware]
   - Idempotency-Key required
   - Redis SETNX idem:order:{buyer_pk}:{key} TTL 24h
   - on hit → replay stored response (Idempotency-Replayed: true)
   |
   v
[Request validation (pydantic)]
   - parse OrderRequest (§6.5)
   - agreement_hash matches config.audit.agreement_hash_current
   |
   v (fail → 400 ERR_REQUEST_SCHEMA / ERR_ORDER_AGREEMENT_REQUIRED)
[Server-side validation (FR-11)]
   1. scope_json.exclude_hospitals ∩ cohort hospital set
      → 403 ERR_ORDER_SCOPE_FORBIDDEN
   2. len(pseudo_study_uids) > tier.max_cohort_size
      → 422 ERR_ORDER_TIER_EXCEEDED
   3. daily quota (Redis counter)
      → 429 ERR_ORDER_QUOTA_EXCEEDED
   4. SELECT pseudo_study_uid, hospital_pk, total_bytes
        FROM study WHERE pseudo_study_uid = ANY(:list)
      validate all present + no dup
      → 404 ERR_ORDER_STUDY_NOT_FOUND / 400 ERR_ORDER_DUPLICATE_STUDY
   5. sum(total_bytes) > tier.max_order_bytes
      → 413 ERR_ORDER_TOO_LARGE
   6. hospitals subset-of scope.allowed_hospitals
      → 403 ERR_ORDER_SCOPE_FORBIDDEN
   |
   v
[Hot-Storage hit check (within same SQL)]
   - SELECT pseudo_study_uid, central_object_present
       FROM study WHERE pseudo_study_uid = ANY(:list)
   - partition cohort into {hot_hit, cold}
   - path_type = 'hot' if all hot, 'cold' if all cold, 'mixed' otherwise
   - estimated_ready_at = submitted_at + hot × 0.5s + cold × 36s
   |
   v
[BEGIN PG TX]
   - INSERT "order" (status='queued', path_type, total_estimated_usd, tier, ...)
   - INSERT order_item[] (one per pseudo_study_uid,
       state = 'hot_hit_pending_copy' or 'pending')
   - INSERT order_state_history (from_state=null,to_state='queued',event='order.created',actor='buyer')
   - INSERT order_outbox
       (event_type='order.queue_transfer_jobs', payload={order_pk, hospital_groups})
   - INSERT order_idempotency_mirror
COMMIT
   |
   v (tx fail → 503 ERR_DB_UNAVAILABLE)
[Idempotency finalize Redis]
   |
   v
[Return 202 + OrderResponse]
```

```mermaid
sequenceDiagram
    participant B as Buyer
    participant LB as Nginx/ALB
    participant API as fulfillment API
    participant R as Redis
    participant PG as PostgreSQL
    participant OUT as Outbox Poller

    B->>LB: POST /v1/orders (TLS 1.3, Bearer, Idem-Key)
    LB->>API: HTTP (proxy)
    API->>R: auth cache / rate-limit / idempotency
    R-->>API: ok | replay
    API->>PG: SELECT study x N (scope, size, hot check)
    PG-->>API: rows + central_object_present
    API->>PG: BEGIN; INSERT order/order_item/history/outbox; COMMIT
    PG-->>API: ok
    API->>R: finalize idempotency
    API-->>LB: 202 + OrderResponse
    LB-->>B: 202

    Note over OUT,PG: async (≤2s later)
    OUT->>PG: SELECT * FROM order_outbox WHERE dispatched_at IS NULL
    PG-->>OUT: order.queue_transfer_jobs
    OUT->>PG: INSERT transfer_job(s) per hospital_pk
    OUT->>R: PUBLISH transfer_job_hospital:{hospital_pk}
    OUT->>PG: UPDATE order_outbox SET dispatched_at=now()
```

### 8.2 Gateway Transfer Consumer 시퀀스

```
[Gateway transfer daemon loop]
   |
   v
[GET /v1/gateway/transfer-jobs?wait=30s] (central-ingest outbound TLS)
   |
   v
[Central: auth validate (hospital token)]
   |
   v
[Central: BEGIN TX]
   - SELECT * FROM transfer_job
       WHERE state='queued' AND hospital_pk=:mine
       ORDER BY created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED
   - if row: UPDATE state='claimed', lease_owner=:gateway_id,
              lease_expires_at=now()+15m, claimed_at=now(),
              attempt_count=attempt_count+1
     INSERT order_state_history (if first claim)
   COMMIT
   |
   v
[if no row: SUBSCRIBE redis transfer_job_hospital:{hospital_pk}, wait ≤ 30s]
   - on PUBLISH: loop to top of TX block
   - on timeout: return 204 No Content
   |
   v (row returned)
[Return 200 + TransferJobClaim]
   |
   v
[Gateway: for each study in claim.studies]
   - PACS query → WADO fetch → De-ID → local staging
     (existing Flow A pipeline, reused)
   |  every progress_report_interval:
   v
[Gateway POST /progress {n_fetched,n_deided,n_uploaded,lease_extend}]
   |
   v
[Central: validate lease ownership, update counters, extend lease]
   |
   v ← periodically (every 5m)
[Gateway: for each staged study POST /v1/ingest/studies (central-ingest!)]
   - standard Ingest path, returns central_job_id
   |  accumulates manifest[] with central_job_ids
   v
[Gateway POST /complete {manifest[], audit_ref}]
   |
   v
[Central: BEGIN TX]
   - validate manifest vs transfer_job.studies
   - UPDATE transfer_job state='completed', completed_at
   - UPDATE order_item[] state='staged' for matched pseudo_study_uids
   - IF all order_items.state IN ('staged','hot_hit_staged')
       UPDATE "order" status='staging_complete'
       INSERT order_state_history, order_outbox('order.staging_complete')
     ELSE
       UPDATE "order" status='staging_partial'
   COMMIT
   |
   v
[Return 200]
   |
   v  (async ≤5s)
[Outbox poller picks order.staging_complete]
   - for each order_item: S3 COPY
       ingest/{hash2}/{hosp}/{pseudo_study}/** → staging/{order_id}/{hash2}/{hosp}/{pseudo_study}/**
   - UPDATE order_item.state='copied', staged_at=now()
   - UPDATE "order" status='ready_for_download', ready_at=now(),
              expires_at=now() + config.order.ttl_seconds
   - INSERT order_state_history
```

```mermaid
sequenceDiagram
    participant GW as Gateway
    participant FF as fulfillment API
    participant PG as PostgreSQL
    participant R as Redis
    participant CI as central-ingest API
    participant S3 as S3/MinIO

    GW->>FF: GET /v1/gateway/transfer-jobs?wait=30
    FF->>PG: SELECT ... FOR UPDATE SKIP LOCKED
    PG-->>FF: job row
    FF->>PG: UPDATE state='claimed', lease=+15m
    FF-->>GW: 200 TransferJobClaim
    loop each study
        GW->>GW: PACS fetch + De-ID (existing pipeline)
        GW->>CI: POST /v1/ingest/studies (manifest + dcm)
        CI-->>GW: 201 central_job_id
        GW->>FF: POST /progress (counters, lease_extend)
        FF-->>GW: 200 lease_expires_at
    end
    GW->>FF: POST /complete (manifest[], audit_ref)
    FF->>PG: BEGIN; update transfer_job + order_item + order; COMMIT
    PG-->>FF: ok
    FF-->>GW: 200 state='staging_complete'
    Note over FF,S3: async
    FF->>PG: SELECT order_outbox 'order.staging_complete'
    FF->>S3: COPY ingest/* → staging/<order_id>/*
    S3-->>FF: ok
    FF->>PG: UPDATE order status='ready_for_download', ready_at, expires_at
```

### 8.3 Buyer Download URL mint 시퀀스

```
[Buyer] POST /v1/orders/{id}/download-urls {ttl_seconds}
   |
   v
[Auth + rate-limit (URL mint rate limit FR-67)]
   |
   v
[Validate state]
   - SELECT status, expires_at FROM "order" WHERE order_id=:id AND buyer_pk=:buyer
   - not found or other buyer → 404 ERR_ORDER_NOT_FOUND
   - status != ready_for_download → 409 ERR_ORDER_NOT_READY
   - now() > expires_at         → 410 ERR_ORDER_EXPIRED
   - status ∈ {cancelled,failed} → 410 ERR_ORDER_TERMINAL
   |
   v
[Validate ttl_seconds]
   - apply config tier.download_ttl_max_seconds
   - > tier cap → 422 ERR_URL_TTL_EXCEEDED
   |
   v
[For each order_item → SELECT instance rows (object_key, sha256, bytes)]
   - JOIN from order_item.pseudo_study_uid → study → series → instance
   - object_key is staging/<order_id>/... (post-COPY)
   |
   v
[For each instance]
   - boto3.generate_presigned_url('get_object',
         Bucket, Key, ExpiresIn=ttl_seconds,
         ResponseContentDisposition='attachment; filename=<pseudo_sop_uid>.dcm')
   - compute signature_hash = sha256(url signature)[:16]
   - INSERT download_event (event_type='url_minted', signature_hash,
         src_ip=X-Forwarded-For, user_agent, kid, ttl_seconds)
   |  (bulk insert, async task)
   v
[Construct DownloadUrlBatch response]
   - ttl_seconds, expires_at = now()+ttl, minted_at = now()
   - items[] grouped by pseudo_study_uid
   |
   v
[Return 200 + DownloadUrlBatch]
```

```mermaid
sequenceDiagram
    participant B as Buyer
    participant FF as fulfillment API
    participant PG as PostgreSQL
    participant S3 as S3 SigV4

    B->>FF: POST /v1/orders/{id}/download-urls
    FF->>PG: SELECT order + verify buyer + state + expires_at
    PG-->>FF: row
    FF->>PG: SELECT order_item → study → series → instance
    PG-->>FF: object_keys[]
    loop each object
        FF->>S3: generate_presigned_url (offline, no round-trip)
    end
    FF->>PG: BULK INSERT download_event (url_minted)
    PG-->>FF: ok
    FF-->>B: 200 DownloadUrlBatch (urls + sha256 + ttl)
```

### 8.4 Cancellation 시퀀스 (buyer, queued state)

```
[Buyer] POST /v1/orders/{id}/cancel
   |
   v
[Auth + rate-limit]
   |
   v
[Load order]
   - SELECT order WHERE order_id=:id AND buyer_pk=:buyer FOR UPDATE
   - not found → 404
   |
   v
[Check allowed states]
   - status ∈ {draft,submitted,validating,validated,queued} → proceed
   - else → 409 ERR_ORDER_STATE_TRANSITION
         (if fetching+ : hint="admin cancellation required; contact support")
   |
   v
[BEGIN PG TX]
   - UPDATE "order" SET status='cancelled', cancelled_at=now(), cancel_requested=true
   - UPDATE transfer_job SET state='cancelled'
       WHERE order_pk=:order_pk AND state='queued'     (unclaimed only)
   - UPDATE transfer_job SET cancel_requested=true
       WHERE order_pk=:order_pk AND state='claimed'    (in-flight — cooperative)
   - INSERT order_state_history (from_state=old, to_state='cancelled',
       actor='buyer', reason=:reason)
   - INSERT order_outbox (event_type='order.cancelled')
COMMIT
   |
   v
[Return 200 + {order_id, state, cancelled_at, refund_eligible:false}]
```

admin force-cancel 시 `fetching|staging_*` 허용. 이미 업로드된 `order_item` 은 `unlinked_study` 테이블로 detach (§4.15 FR-78). mermaid 는 이 절차의 분기를 다음과 같이 표현:

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> submitted: submit
    submitted --> validating: auto
    validating --> validated: success
    validating --> failed: validation_failed
    validated --> queued: auto
    queued --> fetching: first_claim
    queued --> cancelled: buyer_cancel
    fetching --> staging_partial: some_items_staged
    fetching --> staging_complete: all_items_staged
    staging_partial --> staging_complete: remainder_staged
    staging_complete --> ready_for_download: staging_copy_complete
    ready_for_download --> delivering: first_url_minted (optional)
    ready_for_download --> expired: timer (now > expires_at)
    delivering --> delivered: all_downloaded (optional; v0.1 은 fallthrough)
    delivering --> expired: timer
    fetching --> cancelled: admin_force_cancel
    staging_partial --> cancelled: admin_force_cancel
    staging_complete --> cancelled: admin_force_cancel
    ready_for_download --> cancelled: admin_force_cancel
    fetching --> failed: max_retries_exceeded
    cancelled --> [*]
    expired --> [*]
    delivered --> [*]
    failed --> [*]
```

### 8.5 Order FSM — 전이 매트릭스 요약

| from → to | 트리거 | Actor | 비고 |
|-----------|-------|-------|------|
| `draft → submitted` | `POST /v1/orders` (FR-8) | buyer | v0.1 은 draft 미구현, submitted 로 직행 |
| `submitted → validating` | FR-12 (동기 내부) | system | |
| `validating → validated` | 검증 통과 | system | |
| `validating → failed` | 검증 실패 | system | — (실제로는 API 400/403/404/413/422 로 반환하므로 DB row 는 존재하지 않는다) |
| `validated → queued` | FR-13 TX commit | system | |
| `queued → fetching` | Gateway first claim | gateway | |
| `queued → cancelled` | buyer cancel FR-21 | buyer | |
| `fetching → staging_partial` | some complete | gateway | |
| `fetching → staging_complete` | all complete | gateway | |
| `staging_partial → staging_complete` | remainder | gateway | |
| `staging_complete → ready_for_download` | S3 COPY done | system | |
| `ready_for_download → delivering` | first URL mint (optional) | system | v0.1 은 delivering 상태를 현재 사용 안 함 (delivered 직접 fallthrough 불가능 → expired 로만 귀결) |
| `ready_for_download → expired` | timer (FR-74) | timer | |
| `ready_for_download → cancelled` | admin only | admin | |
| `fetching/staging_* → cancelled` | admin force | admin | unlinked_study 처리 |
| `fetching/* → failed` | DLQ 진입 | system | |

---

## 9. 의존성

### 9.1 상위 모듈 / 선행 기능

- **central-ingest v0.1** — `study`, `series`, `instance`, `hospital`, `auth_token` 테이블 존재 + `/v1/ingest/studies` 엔드포인트 운영. Gateway 의 transfer 완료 시 upload 타깃. **`study.central_object_present` 컬럼 추가는 본 dev-spec 이 요구하는 contract delta** (§14 C-1).
- **metadata-index v0.1** — `buyer`, `buyer_api_key`, `search_audit` 테이블 존재 + `buyer_api_key.scope_json` 필드에 `exclude_hospitals`, `allowed_hospitals`(신규, §14 C-2) 가 운영 가능. **`search-admin key issue` 가 본 서비스에서 재사용된다** (신규 CLI 없음).
- **Gateway Agent v0.1** — De-ID + `/v1/ingest/studies` 업로드 파이프라인 완비. 본 dev-spec 은 그 위에 **transfer-job consumer 서브시스템**만 추가 (§14 G-1).
- **Hospital 온보딩** — central-ingest FR-75 의 `init-hospital` / `issue-token` 은 변경 불필요. 본 서비스는 기존 `auth_token` 재사용.
- **Buyer 온보딩** — metadata-index `search-admin buyer create` + `key issue` 로 발급된 키로 본 서비스 호출. 신규 온보딩 프로시저 없음.

### 9.2 하위 모듈 / 후속 기능

- **billing-revenue-share (v0.2)** — `"order".total_estimated_usd` · `download_event.bytes_transferred` → 매출 집계 · 병원별 revenue share. 본 dev-spec 의 테이블을 read-only 로 참조.
- **buyer-portal-web (v0.2)** — `POST /v1/orders` · `POST /v1/orders/{id}/download-urls` 를 호출하는 React/Next.js UI. 본 dev-spec API-only v0.1 이 스펙 확정.
- **hot-storage-auto-promotion (v0.2)** — 판매 빈도 분석 → `study.central_object_present=true` 전환 → Gateway batch transfer-job 사전 발행. 본 dev-spec 의 `study.central_object_present` 컬럼 + `transfer_job` 테이블 재사용.
- **notifications-worker (v0.1.1)** — `order.ready_for_download` / `order.expired` 이벤트 → buyer webhook/email. `order_outbox` 소비.
- **s3-access-log-etl (v0.1.1)** — S3 Server Access Log → `download_event.get_started/completed/failed` row 채우기.

### 9.3 외부 시스템·벤더

- **PostgreSQL 15+** — central-ingest 와 동일 DB 인스턴스. Alembic revision 0004 로 신규 테이블 추가.
- **Redis 7+** — auth cache, idempotency, long-poll pub/sub, rate-limit 카운터.
- **S3 호환 객체 스토리지** — 프로덕션: AWS S3 Seoul. Dev: MinIO. boto3 SigV4 presigned URL 지원.
- **역프록시/TLS 종단** — nginx / AWS ALB / NCP LB.

### 9.4 기술 스택 — 제안 (Kyle 승인 필요 · ARCHITECTURE §9 TBD 해소)

| 영역 | 선정 | 근거 |
|------|------|------|
| 언어·버전 | **Python 3.11** | central-ingest 및 search 와 동일 |
| 웹 프레임워크 | **FastAPI ≥ 0.110** | 기존 서비스 일관 |
| ASGI 서버 | **gunicorn + uvicorn.workers.UvicornWorker** | 일관 |
| DB 드라이버 | **SQLAlchemy 2.0 sync + psycopg v3** | **central-ingest 실제 구현 상태와 동기화** (현재 코드 `src/radivault_central/db` 가 sync 경로). async 필요 시 v0.2 마이그레이션 — psycopg 3 async 지원. 리서치 §4.1.1 참조 |
| 마이그레이션 | **Alembic** | central-ingest 동일 repo/tree. revision 0004 (central-ingest 0001-0003 후속) |
| Cache / Long-poll / RateLimit | **Redis 7** + **slowapi** + **redis-py pub/sub** | long-poll wakeup 용 pub/sub 채널 신규 |
| 객체 스토리지 SDK | **boto3** | presigned URL + COPY 지원 |
| 로깅 | **stdlib logging + python-json-logger** | 일관 |
| 메트릭 | **prometheus_client + prometheus-fastapi-instrumentator** | 일관 |
| Tracing | **OpenTelemetry Python SDK** | 일관 |
| 테스트 | **pytest, pytest-asyncio, httpx TestClient, testcontainers-python (optional), moto (S3 mock), freezegun (timer)** | |
| 해시 / 서명 | **argon2-cffi** (공유), **hashlib** (sha256) | 인증 재사용 |
| Container base | **python:3.11-slim-bookworm** | 일관, non-root UID 10001 |
| 배포 타깃 | Ubuntu 22.04 LTS + Docker Compose 프로덕션 | K8s v0.2 |

**ARCHITECTURE.md §4.5 / §5.3 갱신 제안** (Kyle 승인 후 별도 PR):
- §4.5 Order Orchestrator: "pull-based long-poll via outbound Gateway. 15-min lease. PG outbox pattern. DLQ after 5 retries." 추가.
- §5.3 Download Manager: 기본 TTL 24h + refresh 메커니즘. per-object URL 배열 shape 언급. revocation 한계 명시.
- §9 Zone 2 라인에 `radivault_fulfillment` 서비스 추가.
- §3.4 Staging Storage: 병원 on-prem staging 과 Central `staging/<order_id>/` prefix 두 층 구분 명시.

### 9.5 배포 구성 제안

```
                       ┌──────────────────────────────────┐
                       │        Zone 2 — 서울 리전         │
                       │                                  │
 ┌──────────────┐      │   ┌───────────────────────────┐ │
 │ AWS ALB /    │──────┼──▶│ radivault-central :8000   │ │
 │ Nginx TLS    │      │   │ (ingest, anchor, probes)  │ │
 └──────────────┘      │   └────────────┬──────────────┘ │
       ▲               │                │                 │
       │               │   ┌────────────▼──────────────┐ │
       │               │   │ radivault-search  :8001   │ │
       │               │   │ (buyer read-only)         │ │
       │               │   └────────────┬──────────────┘ │
       │               │                │                 │
       │               │   ┌────────────▼──────────────┐ │
       │ buyers + ──── │──▶│ radivault-fulfillment:8002│ │
       │ gateways      │   │ (orders + transfer-jobs + │ │
       │               │   │  download urls)           │ │
       │               │   └────────────┬──────────────┘ │
       │               │                │                 │
       │               │      ┌─────────▼─────────┐       │
       │               │      │ PostgreSQL 15     │       │
       │               │      │ + pg_partman      │       │
       │               │      └─────────┬─────────┘       │
       │               │                │                 │
       │               │      ┌─────────▼─────────┐       │
       │               │      │ Redis 7           │       │
       │               │      └─────────┬─────────┘       │
       │               │                │                 │
       │               │      ┌─────────▼─────────┐       │
       │               │      │ S3 bucket         │       │
       │               │      │ ingest/ + staging/│       │
       │               │      └───────────────────┘       │
       │               └──────────────────────────────────┘
       │
   ┌───▼────────────────────────────┐
   │ Zone 1 — 병원 on-prem           │
   │                                │
   │ radivault-gateway (Docker)     │
   │  - Flow A: PACS poll → ingest  │
   │  - Flow B: transfer consumer   │
   │    (long-poll → fetch → ingest)│
   └────────────────────────────────┘
```

3 개 API 서비스 (ingest 8000 / search 8001 / fulfillment 8002) + 공통 Postgres + 공통 Redis + 단일 S3 버킷. Gateway 는 한 병원당 1 인스턴스, Flow A(상시 수집) 와 Flow B(주문 이행) 두 루프를 병렬 운영.

---

## 10. 수용 기준 (Acceptance Criteria)

`@qa` 가 라인별 바이너리 검증. 총 **40 개**.

### 10.1 인증 · 인가

- [ ] **AC-1** (FR-1/2/3): 유효한 buyer key 로 `POST /v1/orders` 호출 → `202` + `OrderResponse`. 없는 kid → `401 ERR_AUTH_MISSING`. revoked key → `401 ERR_AUTH_EXPIRED`.
- [ ] **AC-2** (FR-4/5): 유효한 gateway token 으로 `GET /v1/gateway/transfer-jobs?wait=30s` 호출 → `200` or `204`. 없는 kid → `401 ERR_AUTH_MISSING`.
- [ ] **AC-3** (FR-7): Buyer key 로 `/v1/gateway/transfer-jobs` 호출 → `401 ERR_AUTH_WRONG_PLANE`. Gateway token 으로 `/v1/orders` 호출 → 동일 `401 ERR_AUTH_WRONG_PLANE`.
- [ ] **AC-4** (FR-6): Redis 중단 후 `POST /v1/orders` → `503 ERR_IDEMP_UNAVAILABLE` (또는 `ERR_AUTH_UNAVAILABLE` — fail-closed).

### 10.2 주문 생성 · 검증

- [ ] **AC-5** (FR-8/9/10): Idempotency-Key 누락 → `400 ERR_IDEMP_MISSING`. 동일 key 재전송 → 저장된 응답 리플레이 + `Idempotency-Replayed: true` 헤더. DB "order" row 는 1개.
- [ ] **AC-6** (FR-11.1/6): `scope_json.exclude_hospitals = [3]` 인 키로 hospital_pk=3 에 속한 study 주문 → `403 ERR_ORDER_SCOPE_FORBIDDEN`. DB 변경 없음.
- [ ] **AC-7** (FR-11.2): preview tier 로 51 study 코호트 주문 → `422 ERR_ORDER_TIER_EXCEEDED`.
- [ ] **AC-8** (FR-11.3): preview tier 6 번째 주문/일 → `429 ERR_ORDER_QUOTA_EXCEEDED`.
- [ ] **AC-9** (FR-11.4): 존재하지 않는 pseudo_study_uid 포함 → `404 ERR_ORDER_STUDY_NOT_FOUND`. 같은 uid 중복 → `400 ERR_ORDER_DUPLICATE_STUDY`.
- [ ] **AC-10** (FR-11.5): preview tier 로 `sum(total_bytes) = 11 GB` 주문 → `413 ERR_ORDER_TOO_LARGE`.
- [ ] **AC-11** (FR-15/16): 성공 주문의 `total_estimated_usd = n_studies × 5.0`. `agreement_hash` 가 config 값과 불일치 시 `400 ERR_ORDER_AGREEMENT_REQUIRED`.
- [ ] **AC-12** (FR-13): 성공 주문 후 DB 에 `order`, `order_item[]`, `order_state_history(to_state=queued)`, `order_outbox(event='order.queue_transfer_jobs', dispatched_at=null)` 각각 정확한 row 수로 존재.

### 10.3 주문 조회 · 취소

- [ ] **AC-13** (FR-17/18): `GET /v1/orders` → 본인 주문만 반환. `GET /v1/orders/{id}` 에 다른 buyer 의 주문 id 입력 → `404 ERR_ORDER_NOT_FOUND` (403 아님 — 스코프 누출 방지).
- [ ] **AC-14** (FR-21/22): `queued` 상태 주문 cancel → `200` + state='cancelled'. `fetching` 상태 주문 buyer cancel → `409 ERR_ORDER_STATE_TRANSITION` + hint 메시지.
- [ ] **AC-15** (FR-23): 취소 성공 시 `cancel_requested=true`, `transfer_job(state='queued') → cancelled`, history + outbox insert 완료.

### 10.4 Hot Storage 분기

- [ ] **AC-16** (FR-34): 코호트 전량 `central_object_present=true` → `path_type='hot'`, transfer_job 0개 생성, 직접 `staging_copy` outbox 발행.
- [ ] **AC-17** (FR-35): mixed 코호트 (hot 50 + cold 50) → hospital 수 만큼 transfer_job 생성 + hot-hit 50 개는 즉시 staging_copy. 두 경로 모두 완료되어야 `staging_complete` 전이.

### 10.5 Transfer Job Long-poll

- [ ] **AC-18** (FR-37/38): queued job 있을 때 `GET /v1/gateway/transfer-jobs?wait=30s` → `200` + TransferJobClaim. DB 에서 해당 row `state='claimed'`, `lease_owner=:gateway_id`, `lease_expires_at=now()+15m`.
- [ ] **AC-19** (FR-39): queue 비어있을 때 `wait=5s` 호출 → 5s 후 `204 No Content`. 그 사이 새 job insert 시 즉시 `200` 반환.
- [ ] **AC-20** (FR-42): 두 프로세스가 동시에 long-poll 하고 queue 에 1 row 있을 때 정확히 한 쪽만 claim (SKIP LOCKED 검증).

### 10.6 Transfer Job Progress · Complete · Fail

- [ ] **AC-21** (FR-43/45): 정상 progress 호출 → lease 15 m 연장. counters 역회 (n_fetched 120 → 100) → `400 ERR_JOB_COUNTER_REGRESS`.
- [ ] **AC-22** (FR-44): 다른 gateway_id 가 남의 lease 로 progress 시도 → `403 ERR_JOB_LEASE_OWNERSHIP`.
- [ ] **AC-23** (FR-48/50): complete 호출 후 transfer_job.state='completed', 모든 order_item.state='staged', order.status='staging_complete' (single hospital case).
- [ ] **AC-24** (FR-51): `staging_complete → ready_for_download` 전이 시 S3 에 `staging/<order_id>/...` 객체 존재 (이전 `ingest/...` 객체도 그대로 유지). `order.ready_at`, `order.expires_at` 설정됨.
- [ ] **AC-25** (FR-53/54/55): `retryable=true` + attempts<5 → state='queued' 로 되돌림. `retryable=false` → DLQ row 생성 + order.status='failed'.

### 10.7 Lease Reaper

- [ ] **AC-26** (FR-57/58): 15 분 lease 만료된 claimed job → reaper 가 `state='queued'`, `attempt_count+=1`. `attempt_count >= 5` 면 DLQ 이관.

### 10.8 Download URL

- [ ] **AC-27** (FR-60/64): `ready_for_download` 주문에 `POST /download-urls {ttl_seconds: 86400}` → `200` + DownloadUrlBatch. 각 URL 이 S3 SigV4 서명 포함 (`X-Amz-Signature` 쿼리 존재), sha256 필드 비어있지 않음.
- [ ] **AC-28** (FR-61): `queued` 주문에 URL mint → `409 ERR_ORDER_NOT_READY`. `expired` 주문 → `410 ERR_ORDER_EXPIRED`. `cancelled` 주문 → `410 ERR_ORDER_TERMINAL`.
- [ ] **AC-29** (FR-62): preview tier 로 `ttl_seconds=172800`(48h) 요청 → `422 ERR_URL_TTL_EXCEEDED` (cap 24h).
- [ ] **AC-30** (FR-63/65): 성공 mint 후 `download_event(event_type='url_minted', signature_hash, src_ip, user_agent)` row 각 URL 당 1개 존재. response_content_disposition 이 `attachment; filename=<pseudo_sop_uid>.dcm` 을 포함.
- [ ] **AC-31** (FR-66): 같은 주문에 본 엔드포인트 3 번 호출 → 매번 다른 signature. 이전 URL 들도 TTL 동안 유효 (revocation 없음 검증).
- [ ] **AC-32** (FR-67): 10 초 내 URL mint 3 회 → 3 번째는 `429 ERR_URL_MINT_RATE`.

### 10.9 TTL · Cleanup

- [ ] **AC-33** (FR-73/74): `ready_for_download` 주문 `expires_at` 을 과거로 설정(fixture) → expiry-ticker 가 다음 주기에 `state='expired'` + `expired_at` 설정. `download-urls` 호출 → `410 ERR_ORDER_EXPIRED`.

### 10.10 Unlinked Study

- [ ] **AC-34** (FR-78/79): `fetching` 상태 + 1 study 이미 업로드된 주문에 admin force cancel → `order.status='cancelled'`, 해당 `order_item` detach, `unlinked_study` row `(pseudo_study_uid, original_order_pk, disposition='available_for_reassignment')` 생성. buyer 의 `GET /v1/orders/{id}` 응답 `items[].state` 는 해당 study 미노출.

### 10.11 Observability

- [ ] **AC-35** (FR-81): `/metrics` 에 `radivault_fulfillment_order_submissions_total{tier,status}`, `radivault_fulfillment_transfer_job_queue_depth{hospital_id}`, `radivault_fulfillment_dlq_depth`, `radivault_fulfillment_url_mint_total{tier}` 모두 노출.
- [ ] **AC-36** (FR-82): JSON 로그를 grep/jq 로 파싱 시 `patient_name`, `original_study_uid`, `pacs_host`, `api_key`, `idempotency_key_raw` 가 **어떤 레코드에도 존재하지 않음**.

### 10.12 Admin CLI

- [ ] **AC-37** (FR-85): `fulfillment-admin order inspect --order-id ord_01HX... --json` → 기대 JSON schema 매칭. `fulfillment-admin dlq dump --limit 10 --json` → DLQ 현황 정확 출력. `fulfillment-admin transfer-job requeue --job-id tj_... --dry-run` → DB 변경 없이 "would-requeue" 출력.

### 10.13 Migrations & Packaging

- [ ] **AC-38** (FR-morphological): `docker compose -f docker-compose-fulfillment.yml up -d` → 60 초 내 `/readyz` 200. 컨테이너 UID 10001. `alembic current` 이 0004 revision.
- [ ] **AC-39** (Contract C-1): central-ingest DB 에 `study.central_object_present BOOLEAN DEFAULT FALSE` 컬럼이 Alembic 0004 로 추가되었고, 기존 ingest 엔드포인트 `/v1/ingest/studies` 는 성공 응답 구조 변화 없이 동작한다 (hosp 1개 study 1개 업로드 회귀 테스트 green).
- [ ] **AC-40** (Gateway G-1): Gateway 에서 `transfer.enabled=true` 설정 + `radivault-gateway transfer start` 기동 → fulfillment mock 과의 통합 테스트 (claim → progress → complete) 전 구간 green. Flow A (상시 수집) 병렬 루프에 회귀 없음.

---

## 11. 오픈 질문

> Kyle 결정 또는 외부 확인 필요. 본 dev-spec 은 답을 단정하지 않는다.

1. **Pull-only 고정 여부** — v0.1 long-poll 만 지원 (본 dev-spec 권고). SSE/WebSocket 도입은 v0.2. 파일럿 중 레이턴시 요구가 30 s 이하가 되면 재고. (리서치 §6 item 1)
2. **Presigned URL 기본 TTL** — 24h (권고) vs 48h vs 7d. 파일럿 buyer 실측 요구를 1 개월 수집 후 확정. (리서치 §6 item 2)
3. **Tier cohort 상한** — preview=50 / paid=10,000 (본 dev-spec 권고). FDA 급 고객이 50K+ 요구 시 재협상. (리서치 §6 item 4)
4. **Billing 도입 시점 & PG 공급자** — v0.1 `pending_billing` 스텁, v0.2 Stripe vs 국내 PG. 회계사 자문 필요. (리서치 §6 item 5)
5. **`fetching` 중 취소 시 unlinked study 자동 재할당 여부** — v0.1 은 수동 관리만 (FR-79). v0.1.1 에서 자동 spot claim 도입 여부. (리서치 §6 item 3)
6. **S3 장애 시 readyz 정책** — S3 HEAD bucket 을 `readyz` 3요소에 포함할지, 아니면 주문 접수만 허용하고 URL mint 만 제한할지. §7.10 참고.
7. **`central_object_present` 컬럼 어느 Alembic revision 에서?** — 본 0004 에서 추가 (권고) vs central-ingest 별도 revision 으로 선행. Contract delta C-1 확정 타이밍.
8. **`buyer_api_key.scope_json` 에 `allowed_hospitals` 필드 추가 시점** — metadata-index 의 `search-admin key issue` CLI 와의 연계. Contract delta C-2.
9. **MSA / DPA 법률 자문 착수 시점** — cancellation/no-refund 조항, cross-border download audit 의무, `pending_billing` 무상 제공 문구. 법무 법인 선정 타이밍.
10. **Web portal (buyer UI) 시점** — 본 v0.1 API-only, UI 는 언제 붙일지 (designer 투입 타이밍).
11. **Hot Storage 자동 promotion** — Flow C 자동화 시점 (v0.1.1 vs v0.2). 수동 pinning CLI 는 본 dev-spec 범위 밖 (central-ingest admin 확장 필요).
12. **Staging prefix TTL 변동성** — order TTL 이 preview=24h/paid=7d 로 다양할 때 S3 Lifecycle rule 을 prefix 기반 고정 vs tag 기반 동적. v0.1 은 고정 8d 권고 (FR-76).

---

## 12. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-22 | @planner (Claude Opus 4.7) | 최초 작성. v0.1 MVP 범위 확정. 85 FR, 40 AC. E (Order Orchestrator) + H (Order Download) 병합. buyer_api_key 재사용 + `auth_token` 재사용. 주문 FSM 12-state, transfer-job long-poll + 15 min lease + 5-retry DLQ, per-object presigned URL 24h/7d, unlinked_study 테이블, `order_outbox` 패턴. Gateway transfer consumer 신규 subsystem 명세. Contract delta C-1 (`study.central_object_present`), C-2 (`buyer_api_key.scope_json.allowed_hospitals`), G-1 (Gateway) 제안. |

---

## 13. Annex — 에러 taxonomy · Contract deltas · State-machine

### 13.1 에러 taxonomy 5-필드 (design-spec 환류용)

design-spec-order-fulfillment 가 확장 정의할 5-field 포맷 예시:

| Code | HTTP | Category | Retriable | Description |
|------|------|----------|-----------|-------------|
| `ERR_ORDER_SCOPE_FORBIDDEN` | 403 | Order/Auth | no | Buyer scope prohibits one or more hospitals in cohort |
| `ERR_ORDER_TIER_EXCEEDED` | 422 | Order/Tier | no | Cohort size exceeds tier cap |
| `ERR_ORDER_QUOTA_EXCEEDED` | 429 | Order/Rate | yes(tomorrow) | Daily order quota for buyer exceeded |
| `ERR_ORDER_STUDY_NOT_FOUND` | 404 | Order/Data | no | One or more pseudo_study_uid not indexed |
| `ERR_ORDER_DUPLICATE_STUDY` | 400 | Order/Data | no | pseudo_study_uid duplicated within cohort |
| `ERR_ORDER_TOO_LARGE` | 413 | Order/Tier | no | sum(total_bytes) exceeds tier.max_order_bytes |
| `ERR_ORDER_AGREEMENT_REQUIRED` | 400 | Order/Legal | no | agreement_hash missing or mismatch |
| `ERR_ORDER_STATE_TRANSITION` | 409 | Order/FSM | no | Illegal state transition for actor |
| `ERR_ORDER_NOT_READY` | 409 | Order/FSM | yes(later) | Order not in ready_for_download state |
| `ERR_ORDER_EXPIRED` | 410 | Order/TTL | no | expires_at has passed |
| `ERR_ORDER_TERMINAL` | 410 | Order/FSM | no | Order is cancelled or failed |
| `ERR_ORDER_NOT_FOUND` | 404 | Order/Auth | no | Order not found or not owned by buyer |
| `ERR_URL_TTL_EXCEEDED` | 422 | URL/Tier | no | Requested ttl_seconds exceeds tier cap |
| `ERR_URL_MINT_RATE` | 429 | URL/Rate | yes | URL mint rate limit exceeded |
| `ERR_URL_MINT_FAILED` | 502 | URL/S3 | yes | boto3 signing failed (S3/KMS problem) |
| `ERR_JOB_NOT_FOUND` | 404 | Job | no | transfer_job_id unknown |
| `ERR_JOB_LEASE_OWNERSHIP` | 403 | Job | no | lease_owner mismatch |
| `ERR_JOB_LEASE_EXPIRED` | 409 | Job | yes(reclaim) | lease past lease_expires_at |
| `ERR_JOB_STATE_CONFLICT` | 409 | Job/FSM | no | job state does not allow operation |
| `ERR_JOB_HOSPITAL_MISMATCH` | 403 | Job | no | Gateway hospital does not own this job |
| `ERR_JOB_MANIFEST_MISMATCH` | 400 | Job | no | Complete manifest diverges from claim studies |
| `ERR_JOB_COUNTER_REGRESS` | 400 | Job | no | Progress counter decreased (non-monotonic) |
| `ERR_AUTH_WRONG_PLANE` | 401 | Auth | no | Wrong token type for endpoint plane |
| `ERR_AUTH_UNAVAILABLE` | 503 | Auth | yes | Auth infra (Redis+PG) unreachable |

### 13.2 Contract Deltas

#### C-1 — central-ingest: `study.central_object_present` 컬럼 신규

- **현재**: `dev-spec-central-ingest §6.3` 의 `study` 테이블에 해당 컬럼 없음.
- **본 dev-spec 요구**: `ALTER TABLE study ADD COLUMN central_object_present BOOLEAN NOT NULL DEFAULT FALSE;` + `UPDATE study SET central_object_present = TRUE WHERE ... (초기 backfill, 전부 TRUE — 이미 ingest 된 record 는 상주)`.
- **central-ingest `/v1/ingest/studies` 변화**: **성공 시 컬럼 `true` 로 기본 설정** — 기존 FR-8 TX 안에 한 줄 추가. **Gateway 는 이 컬럼을 알 필요 없음**. 응답 body 변화 없음. Breaking 없음.
- **Nightly sampling (v0.1.1)**: 야간 배치가 S3 HEAD object 로 drift 검증하여 column 을 `false` 로 되돌리기.
- **조치**: Alembic 0004 본 dev-spec revision 에서 **동시** 처리. central-ingest dev-spec v0.1.1 보강 PR 필요 (§11 Q7).

#### C-2 — metadata-index: `buyer_api_key.scope_json.allowed_hospitals` 필드 신규

- **현재**: metadata-index `scope_json` 은 `{tier, rate_limit_*, max_limit_per_page, max_include_facets, exclude_hospitals}` 필드 정의. v0.1 은 flat access 기본 (`FR-75`).
- **본 dev-spec 요구**: `allowed_hospitals: list[int]|None` 추가. 주문 검증에서 `study.hospital_pk ∈ allowed_hospitals` 강제 (FR-11.6). `None` 이면 v0.1 flat access 동일.
- **조치**: metadata-index dev-spec §4.15 (Hospital opt-out) 에 `allowed_hospitals` 필드 명시. `search-admin key issue --allowed-hospitals 1,3,7` 플래그 추가 필요.
- **Breaking 여부**: no — optional 필드 추가만. 기존 키는 `null` 로 해석.

#### G-1 — gateway-agent: Transfer Job Consumer 신규 subsystem

- **현재**: Gateway dev-spec §4 는 Flow A 상시 수집만 정의. `src/radivault_gateway/orchestrator/` 는 PACS poll 루프.
- **본 dev-spec 요구**:
  - 신규 패키지 `src/radivault_gateway/transfer/` — `consumer.py` (long-poll daemon), `job_runner.py` (De-ID + upload 파이프라인 재사용), `progress_reporter.py`.
  - 신규 CLI 서브커맨드 — `radivault-gateway transfer start` (daemon), `radivault-gateway transfer status` (inflight summary).
  - 신규 config subtree — `transfer.*` (§6.6).
  - 신규 study_job state — `ondemand_fetching`, `ondemand_uploaded` (주문 이행 중인 study 는 Flow A queue 와 구분되도록). gateway dev-spec §6.1 state enum 확장.
  - Flow A 와 병렬 루프 — asyncio Task 두 개, 서로 PACS `max_concurrency` 를 양분 (기본 2+2=4 중 2 Flow A · 2 Flow B).
- **조치**: Gateway dev-spec v0.1.1 보강 PR — §4.10 Transfer Job Consumer 신규 섹션 + §6.2 config `transfer.*` + §6.1 SQLite `study_job.state` enum 확장.
- **Breaking 여부**: no — optional subsystem (`transfer.enabled=false` 기본) + additive state enum.

#### C-3 — central-ingest `/v1/ingest/studies` 응답에 `central_job_id` 활용

- **현재**: central-ingest FR-2 이미 `central_job_id` 반환.
- **본 dev-spec 요구**: Gateway 가 complete manifest 의 `central_job_ids: list[str]` 를 채워 fulfillment 로 보내야 함. audit trail 용. Gateway 구현 시 ingest 응답에서 `central_job_id` 캡처 필수.
- **Breaking 여부**: no — 이미 있는 필드 재사용.

### 13.3 Alembic Coupling 노트

- revision 0001 central-ingest (hospital, auth_token, study, series, instance, audit_*, idempotency_mirror)
- revision 0002 metadata-index (buyer, buyer_api_key, search_audit + roles)
- revision 0003 (예약 — central-ingest 후속 보강 예: `anonymization_flag` 관련)
- **revision 0004 order-fulfillment** (본 dev-spec): `"order"`, `order_item`, `transfer_job`, `transfer_job_dead_letter`, `download_event`, `order_state_history`, `order_outbox`, `order_idempotency_mirror`, `unlinked_study` + role `radivault_fulfillment_app` + **ALTER TABLE study ADD COLUMN central_object_present** (C-1).
- revision 0004 실행 전에 0001, 0002 이 적용되어 있어야 함 (dependency chain).
- revision 0004 롤백 시 역순 DDL — `DROP TABLE` 9 건 + `ALTER TABLE study DROP COLUMN central_object_present`. **주의**: `central_object_present` 롤백은 central-ingest 가 해당 컬럼을 write 하도록 수정된 후라면 ingest 가 깨진다 → 실전에선 revision 역순 전체 롤백만 안전.

### 13.4 Gateway Config 마이그레이션 노트

- 기존 `/etc/radivault/gateway.yml` 에 `transfer:` 섹션만 추가하면 됨 (additive, backward compatible).
- `transfer.enabled=false` (기본) 면 기존 Flow A 만 구동 — 현행 프로덕션 Gateway 는 영향 없음.
- v0.1 파일럿 병원에 활성화하려면 Kyle 승인 + RadiVault SRE 가 구성 변경 및 systemd 재기동.

### 13.5 State Machine 전이 다이어그램 요약

§8.4 mermaid 참조. 11 transition 정의, terminal 4 (`delivered` · `expired` · `cancelled` · `failed`). design-spec 이 **각 transition 을 설명 행 1줄 + 예상 duration + actor 로 풀어 표 작성** 예정.

---

## 14. Contract Deltas (Summary for quick reference)

| # | 대상 | 변경 | Breaking? | 조치 |
|---|------|------|-----------|------|
| C-1 | central-ingest `study` | `central_object_present BOOLEAN NOT NULL DEFAULT FALSE` 컬럼 추가 | **No (additive)** | Alembic 0004. ingest TX 한 줄 추가 (성공 시 `TRUE`). |
| C-2 | metadata-index `buyer_api_key.scope_json` | `allowed_hospitals: list[int]` 필드 (optional) | **No (additive)** | search-admin CLI 옵션 추가. 본 dev-spec 검증 로직 참조. |
| C-3 | central-ingest `/v1/ingest/studies` 응답 | 필드 변경 없음. Gateway 가 `central_job_id` 를 capture 하여 fulfillment 로 forward 해야 함. | No | Gateway 구현 변경만. |
| G-1 | gateway-agent | `transfer/*` subsystem + `transfer.*` config + CLI `transfer start|status` + `ondemand_*` state | **No (feature flag off by default)** | gateway dev-spec v0.1.1 보강 PR. |

**`order_id` 상관 필드 요구 여부** — 본 dev-spec 은 **central-ingest `/v1/ingest/studies` manifest 에 `order_id` 필드 추가를 요구하지 않는다**. Gateway 가 transfer-job claim 에서 `order_id` 를 받아 알고는 있지만, ingest manifest 는 변경하지 않고 Gateway 가 complete manifest 에 `central_job_ids` 를 채워 forward 하는 것으로 매핑을 재구성한다. 이 선택의 이유 — central-ingest 계약 변경 minimized → Gateway · Central 양쪽 계약 동결 유지. **만약 v0.1.1 에서 매핑 정확도 개선이 필요하면 central-ingest manifest 에 `correlation.order_id: str|null` optional 필드 추가 (v0.1.1 gate)**.

---

### NEXT_STEP

- 완료 산출물: `docs/specs/dev-spec-order-fulfillment.md` (v0.1 Draft)
- 제안 다음 단계: **@designer** — `design-spec-order-fulfillment.md` 작성.
  - UI 없는 백엔드 서비스지만 central-ingest / metadata-index 와 마찬가지로 "개발자·운영자-facing UX"(buyer HTTP API envelope + Korean/English error messages, `fulfillment-admin` CLI output, JSON 로그 스키마, Prometheus 메트릭 네이밍, 장애 runbook 8–12 편, buyer API onboarding walkthrough + `curl` 샘플 5종)를 명세할 가치가 있음.
  - buyer 관점 error 메시지는 **영어 우선** (구매자는 글로벌), 운영자 관점 한국어도 병기 (design-spec-central-ingest §5 에러 taxonomy 5-field 스타일 상속).
  - 만약 Kyle 이 "백엔드 전용 → designer 생략" 결정 시 → **@developer** 바로 착수.
- 아키텍처 영향: **ARCHITECTURE.md §4.5 · §5.3 · §3.4 갱신 필요**. §9 표에 `radivault_fulfillment` 서비스 추가. Flow B 를 "pull-based long-poll + outbox orchestration" 으로 리라이트 권고.
- PRD 영향: **PRD §4.3 · §4.4 미세 보정 필요**. "구매 확정 → Gateway 로 전송 명령" 을 "pull 기반 transfer-job 큐잉" 으로 수정. "48시간 내" 표현은 paid 기준 1시간 목표로 상향 가능 (실측 후 Kyle 결정). `pending_billing` 정책을 §4.6 Billing 섹션에 주석으로 반영.
- Kyle 결정 필요 사항 (§11 참고 · 요약):
  1. Pull-only 고정 여부 (v0.1).
  2. Presigned URL 기본 TTL (24h 권고).
  3. Tier cohort 상한 (preview=50, paid=10K 권고).
  4. Billing 도입 시점 & PG 공급자.
  5. unlinked_study 자동 재할당 도입 시점.
  6. `/readyz` S3 포함 정책.
  7. `central_object_present` 컬럼 추가 revision (본 0004 또는 central-ingest 별도).
  8. `allowed_hospitals` 필드 추가 시점 (C-2).
  9. MSA/DPA 법률 자문 착수 시점.
  10. Buyer web portal 착수 시점 (designer 투입).
  11. Hot Storage 자동 promotion (Flow C).
  12. S3 Lifecycle staging prefix TTL 정책 (고정 vs 동적 tag).
