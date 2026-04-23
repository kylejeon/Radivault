# Order Fulfillment — 기술적 기반 리서치

## 0. 메타

- **Status**: Draft v0.1
- **작성일**: 2026-04-22
- **작성자**: @researcher (Claude Opus 4.7)
- **근거 요청**: 메인 세션 — Phase 2 "Planning" 진입, 수익 엔진 `order-fulfillment` v0.1 dev-spec 작성 전 **구매 확정 → Gateway 온디맨드 페치 → 중앙 스테이징 → 구매자 다운로드 → 감사** 전 구간의 기술 근거 정리.
- **feature-slug**: `order-fulfillment`
- **스코프 병합**: 기존 기획안의 E(Order Orchestrator) + H(Order Download)를 단일 dev-spec로 합친다. 과금(G)은 제외하며 `status="pending_billing"` 스텁만 남긴다.
- **선행 문서 (중복 회피 위해 상호 참조)**
  - [`docs/prd.md` §4.2, §4.3, §4.4, §4.7](../prd.md)
  - [`docs/ARCHITECTURE.md` §3, §4.4 Hot Storage, §4.5 Order Orchestrator, §5 Zone 3, Flow B](../ARCHITECTURE.md)
  - [`docs/research/k-meddata-research-summary.md` §3 경쟁사, §6 Model 3 Hybrid, §10 로드맵](./k-meddata-research-summary.md)
  - [`docs/research/central-ingest-technical-foundations.md` §4.3 객체 스토리지·presigned, §4.4 PG 스키마, §4.6 한국 호스팅](./central-ingest-technical-foundations.md)
  - [`docs/research/metadata-index-technical-foundations.md` §4.1 buyer auth, §4.2 cursor, §4.5 쿼터 tier](./metadata-index-technical-foundations.md)
  - [`docs/specs/dev-spec-central-ingest.md` §6 데이터 모델](../specs/dev-spec-central-ingest.md) — **확장 대상**
  - [`docs/specs/dev-spec-gateway-agent.md` §4.4, §4.8 Upload Client·Packaging; §7.3 Central API 계약](../specs/dev-spec-gateway-agent.md) — **신규 transfer-job consumer 추가 대상**
  - [`docs/specs/dev-spec-metadata-index.md` §4.1 buyer_api_key, §4.10 search_audit](../specs/dev-spec-metadata-index.md) — **buyer 인증 재사용**
  - `src/radivault_central/routers/` (ingest, anchor, probes, version, withdraw)
  - `src/radivault_search/routers/` (search, facets, hospitals)
  - `src/radivault_gateway/orchestrator/` (기존 Flow A 루프, 신규 Flow B transfer-job 컨슈머가 여기에 추가)

- **PRD/ARCHITECTURE 영향(제안)**
  - **PRD §4.4**: "구매 확정 → Gateway로 전송 명령" 표현은 **push 지시**를 함의. 본 문서 §4.2는 **pull(long-poll)** 권고이므로, PRD 본문을 "Central이 transfer-job을 큐잉하고 Gateway가 pull로 consume" 표현으로 **미세 보정** 필요.
  - **ARCHITECTURE §4.5 Order Orchestrator**: 현재 "메시지 큐 + 워커 함수" 수준 기술. 본 문서 §4.1 FSM과 §4.3 Hot Storage 결정 경로를 반영해 확장 권고.
  - **ARCHITECTURE §5.3 Download Manager**: 7일 TTL presigned URL 기본값은 유지. 본 문서 §4.4에서 **per-object vs per-manifest**, **단축 TTL 회수(refresh) 패턴**을 구체화.

- **스코프 제한**: 본 문서는 `order-fulfillment` v0.1의 **기술 근거**만 다룬다. 실제 요구사항화·DB 스키마·API 계약은 @planner의 `dev-spec-order-fulfillment.md`가 확정한다. 빌링·수익 분배(G), 라벨링 파이프라인(F), Hot Storage 선제 로직(C-auto), 웹훅/이메일 알림은 본 문서 범위 밖.

- **법률 자문 필요 플래그**
  - 구매자 MSA(Master Services Agreement) · DPA(Data Processing Addendum) 표준 문구.
  - "cross-border delivery audit log"의 개보법 제28조의8 해석(완전 익명정보 전제 유지 시 문제 없음, 전제 붕괴 시 주의).

---

## 1. TL;DR

- **FSM**: `draft → submitted → validating → validated → queued → fetching → staging_partial → staging_complete → ready_for_download → delivering → delivered → expired | cancelled | failed` 12-상태. 모든 전이는 Central이 단일 권위(single source of truth)이며, Gateway·Buyer는 이벤트만 보고한다. 취소(cancel) 가능 구간은 `draft/submitted/validating/validated/queued`까지, `fetching` 이후는 **metadata-only tombstone** 허용·실제 리콜 불가. 전이는 PG 트랜잭션 + `(order_pk, from_state, to_state)` row-lock으로 멱등 보장.
- **Transfer-job 프로토콜**: v0.1은 **pull(long-poll)** 을 **유일 공식 경로로 채택**. 이유 — Gateway가 이미 outbound-only로 설계됐고(`dev-spec-gateway-agent §4.4, §12.3`), 신규 inbound 포트를 병원 방화벽에 뚫는 순간 **파일럿 병원 IT 승인이 수 주 이상 지연**될 위험. 엔드포인트 3개: `GET /v1/gateway/transfer-jobs?wait=30s`(long-poll + lease), `POST /…/{id}/progress`(n_fetched/n_deided/n_uploaded), `POST /…/{id}/complete|fail`. 리스(lease) TTL 15분, `max_retries=5`, DLQ `transfer_job_dead_letter`.
- **Hot Storage vs 온디맨드**: v0.1은 **온디맨드를 디폴트**로 구현. `study.central_object_present`(S3 HEAD 또는 PG 컬럼) 결과가 true면 Gateway 호출 없이 즉시 staging 복사 또는 presigned 발급. Hot Storage **선제적 보관**(ARCHITECTURE §4.4, Flow C 자동화)은 v0.1.1 backlog. v0.1은 **수동 pinning**(운영자 CLI)만 지원.
- **Presigned URL**: AWS S3 SigV4 기준 **최대 TTL 7일(`604800s`)** — 아키텍처 §5.3 기본값과 일치. v0.1은 **per-object URL 리스트**(스터디당 N개). zip/tar 사전 패키징은 비용·메모리상 defer. **revocation은 불가능**이므로 기본 TTL을 **24시간**으로 짧게 하고 만료 전 **refresh API**(`POST /v1/orders/{id}/download/refresh`)를 노출해 현실적 회수 경로 확보. SHA-256 체크섬은 manifest 응답에 포함하여 buyer가 로컬 검증.
- **Validation & Pricing stub**: metadata-index의 `buyer_api_key` (tier enum `free|preview|paid`)를 **그대로 재사용**해 별도 인증층 만들지 않는다. 주문 생성 시 (a) 쿼터(일·월 order수·총 study수), (b) 코호트 크기(tier별 상한), (c) `exclude_hospitals` scope 준수, (d) `pseudo_study_uid` 중복·유효성을 검증. 가격은 Tier-기반 **단가 × 수량**의 `total_estimated_usd`만 계산하고 결제 없이 `status=pending_billing`으로 고정.
- **Download audit**: 모든 presigned URL 발급·사용을 append-only `download_event` 테이블에 기록 — `download_event(buyer_pk, order_pk, order_item_pk, ts, src_ip, user_agent, bytes_transferred, http_status, request_id)`. S3 Access Log(또는 CloudFront real-time log)를 **2차 증거**로 nightly ETL. 개인 식별 정보 없음(구매자는 B2B 법인, 단 연락처 담당자는 별도 `buyer_contact` 테이블로 분리).
- **Cleanup**: 주문 TTL 7일(ready→delivered). 만료 시 **staging 영역만 회수**하고 원본은 Hot Storage/기본 S3에 남긴다(다음 주문 재사용). Gateway transfer-job 취소는 **협조적**(Gateway가 다음 progress ping 시 `cancelled=true` 수신 → 자원 정리 + 업로드 포기). 사전-fetching 상태 취소 요청은 **환불 불가 tombstone** 정책.
- **의사결정 근거**: 본 문서는 Gradient Atlas 48시간 딜리버리(공개 마케팅), Segmed "Curated Project" 워크플로(공개 런칭 자료), AWS S3 presigned URL 공식 문서, AWS Step Functions·SQS orchestration 패턴, RFC 7540 long-polling 관용, Stripe Orders API의 **상태 기계 설계 원칙**(영감 차원, 구현 아님)을 교차 참고.

---

## 2. 조사 질문

1. 구매 확정 → 전달 완료까지 수 분~48시간 범위의 비동기 플로우를 **시각화 가능한 FSM**으로 어떻게 설계하는가? 전이 이벤트의 권위는 Central이 가져야 하는가, 분산되어도 되는가?
2. Gateway가 inbound 포트 없이도 Central의 주문을 받을 수 있게 하는 **pull vs push** 트레이드오프는? v0.1에서 무엇을 선택하고 v0.2에 무엇을 열어두는가?
3. 중앙 Hot Storage 상주 여부를 어느 레이어에서 판정하고, 온디맨드 페치와 어떻게 **조건 분기**하는가? 사전 프리스테이징(Flow C)을 v0.1에 넣는 비용 대비 가치는?
4. S3 presigned URL의 **signing·TTL·revocation·IP 제한·체크섬 검증**에 대한 2026년 공식 가이드는 무엇인가? zip 번들 vs per-object URL의 실무 선택 기준은?
5. 주문 검증에서 buyer 티어별 쿼터·코호트 크기 상한·이중 지불 방지를 어떻게 강제하는가? 결제 없는 `pending_billing` 스텁은 어느 경계까지 안전한가?
6. Download event 감사 로그는 HIPAA·개보법·SOC 2 관점에서 어떤 필드를 **반드시** 기록해야 하며, 구매자의 기업 연락처가 "개인정보"에 해당해 PIPA 대응이 필요한 범위는?
7. 주문 취소·만료·staging cleanup의 구체 정책(어느 상태에서 취소 허용, Gateway in-flight 작업의 처리)은? 경쟁사 Gradient/Segmed의 공개된 취소 정책은?

---

## 3. 방법론

- **1차 자료**
  - AWS S3 Developer Guide — Presigned URLs, SigV4, Object Lock, Multipart Upload, Access Logs: `docs.aws.amazon.com/AmazonS3/latest/userguide/`.
  - AWS Step Functions Developer Guide (long-running workflow orchestration): `docs.aws.amazon.com/step-functions/`.
  - AWS SQS Developer Guide (visibility timeout, DLQ, long polling): `docs.aws.amazon.com/AWSSimpleQueueService/`.
  - AWS CloudFront — Signed URLs / Signed Cookies / OAC.
  - RFC 7540 HTTP/2 (long-polling semantics over HTTP/2 streams).
  - RFC 8470 HTTP Early Data (멀리성을 위한 참고).
  - IETF `draft-ietf-httpapi-idempotency-key-header` (중복 주문 방지 재사용).
  - PostgreSQL 16 docs — Advisory Locks, `SKIP LOCKED`, `SELECT ... FOR UPDATE`, partitioning.
- **2차 자료**
  - Gradient Health 공개 블로그: "Atlas 2 launch" (2025), "48-hour delivery" 언급.
  - Segmed/Openda 런칭 자료(PR Newswire 2024), Insight 제품 페이지.
  - Stripe Orders API docs — state machine 참조(`stripe.com/docs/api/orders_v2`). 구현 참조는 아니며 설계 개념만 인용.
  - Shopify Fulfillment API — partial-fulfillment 모델.
  - AWS Well-Architected SaaS Lens — tenant isolation 기반 주문 격리.
  - Medium / Stripe Engineering 블로그 — saga pattern, outbox pattern.
- **한국 규제 1차**
  - 개인정보보호법 제28조의8 (법제처, 2023-09-15 개정) — 이전 리서치와 동일 출처.
  - 개인정보위 "가명정보 처리 가이드라인"(2024).
  - 방사선 영상 해외 이전에 관한 보건복지부 지침(있다면) 확인 필요 플래그.
- **한계**
  - Gradient·Segmed의 **정확한 FSM 내부 구조**는 공개되지 않음. "48시간 ETA", "project-based delivery" 같은 마케팅 문구만 공개 → 본 문서는 "업계 관행은 `pending → processing → ready → delivered`" 수준으로만 인용.
  - "presigned URL revocation 불가"는 AWS 공식 입장. 사설 CDN·프록시로 revocation을 흉내내는 구현은 있지만 v0.1 스코프를 넘는다.
  - 실제 하드웨어 처리량 측정치 없음 — 페치 48시간 내 이행 가능성은 Gateway/PACS 대역폭 실측이 필요(파일럿 1주 수집 후 재평가).

---

## 4. 결과

### 4.1 Order lifecycle state machine

#### 4.1.1 상태 정의 (v0.1 권고 12 states)

| State | 의미 | 진입 트리거 | 이탈 조건 |
|-------|------|-------------|-----------|
| `draft` | Buyer가 장바구니에 담고 아직 제출 전 | `POST /v1/orders (dry_run=true)` 또는 cart add | buyer 제출 |
| `submitted` | Buyer가 제출 완료, 서버 검증 대기 | `POST /v1/orders` | 서버 수락 |
| `validating` | 서버 측 쿼터·스코프·cohort 유효성 검사 중 | server task enqueue | 검증 결과 |
| `validated` | 검증 통과, 큐 대기 | `validating.success` | Orchestrator 집기 |
| `queued` | Orchestrator가 study 단위 sub-job 생성 | `validated.consumed` | Gateway/Hot-hit 분기 |
| `fetching` | 하나 이상의 study에 대해 Gateway가 페치·De-ID·업로드 중 | Gateway claim | 모든 study 업로드 완료 |
| `staging_partial` | 절반 이상 업로드 완료, 부분 전달 가능(옵션) | N/M 업로드 완료 (v0.1은 파생 뷰 only) | 나머지 업로드 완료 |
| `staging_complete` | 모든 study가 staging 버킷에 존재 | 마지막 transfer-job complete | URL 발급 준비 |
| `ready_for_download` | presigned URL 발급 + buyer 통보(상태 폴링) | `staging.complete → ready` | buyer download 시작 |
| `delivering` | buyer가 하나 이상의 URL로 다운로드 중 | 첫 바이트 전송 | 100% 완료 또는 TTL |
| `delivered` | 모든 object 전체 바이트 완료 또는 TTL 만료 후 수동 종결 | completion event / timer | terminal |
| `expired` | TTL 만료 (`ready_for_download`에서 7일) | timer | terminal (재발급 옵션은 별도 SKU) |
| `cancelled` | buyer 또는 admin이 취소 | `POST /cancel` (허용 상태에서만) | terminal |
| `failed` | 복구 불가 오류 | 모든 재시도 실패 | terminal |

- **단일 권위**: 상태는 `order.status` 단일 컬럼 + `order_status_history(order_pk, from, to, reason, actor, at)` 이벤트 원장. Gateway·Buyer는 **상태를 직접 쓰지 못하고** 이벤트를 보고하면 Central이 변환·기록.
- **이벤트 모델**: inbound 이벤트 — `buyer.submit`, `buyer.cancel`, `gateway.progress`, `gateway.complete`, `gateway.fail`, `download.start`, `download.complete`, `timer.expire`. 각 이벤트는 (from,to) 매트릭스 1개에만 매칭되며, 매칭 없으면 `409 ERR_ORDER_ILLEGAL_TRANSITION`.
- **정지(terminal) 3종**: `delivered | expired | cancelled` + `failed`. terminal에서 상태 변경은 어떤 이벤트도 수용하지 않는다(멱등 409 반환).

#### 4.1.2 전이 규칙 & 멱등성

- **PG 트랜잭션 + row-level lock**: 상태 전이는 `SELECT ... FOR UPDATE` 위 `UPDATE order SET status=:to WHERE order_pk=:pk AND status=:from`. rowcount=0이면 다른 트랜잭션이 먼저 전이했거나 illegal. Idempotency-Key (IETF draft, central-ingest에서 이미 사용)를 orchestration 이벤트에도 적용 권고.
- **Outbox 패턴**: 상태 전이 + 후속 이펙트(transfer-job enqueue, audit emit)는 같은 TX에 `outbox` 테이블 row insert. 별도 poller가 `outbox → sideeffects`를 실행(at-least-once). 단일 TX 두 시스템을 쓰지 않아 saga 없이 강한 일관성.
- **중복 제출**: `Idempotency-Key` header를 `order.create`에 강제. 24h TTL. 같은 key 재수신 → 같은 order_id 반환(응답 캐시).

#### 4.1.3 취소 가능성(reversibility)

- v0.1 허용 매트릭스 (Buyer 측):

  | from | cancel 허용? | 근거 |
  |------|:------------:|------|
  | `draft` | YES | 제출 전 |
  | `submitted` | YES | 서버 수락 전 |
  | `validating` | YES | 검증은 내부 작업만 소비 |
  | `validated` | YES | 큐 진입 전 |
  | `queued` | YES | Orchestrator가 Gateway 명령 보내기 직전 |
  | `fetching` / `staging_*` | **NO** | Gateway 자원 이미 소비 — 취소해도 이미 fetch 중인 study는 계속 처리됨(중단 비용이 더 큼). Central이 `cancelled_by_admin` 플래그만 기록하고 후속 업로드는 "폐기 모드"로 전환 — 업로드되되 buyer에게 URL 발급 안 함. |
  | `ready_for_download` | **CONDITIONAL** | buyer가 "필요 없음"을 선언하면 expired로 조기 전환만 가능. 이미 다운로드한 경우 취소 불가. |
  | `delivering` | NO | 최소 1 byte 전송 시 부분 배송으로 간주 |
  | terminal | NO | — |

- Admin 측은 모든 상태에서 취소 가능(`force=true` + reason 필수, audit 기록).

#### 4.1.4 업계 레퍼런스

- **Gradient Health**: 공개 마케팅에 "48-hour turnaround" 언급. 실제 FSM은 비공개. "project-based delivery"라는 표현으로 **batch export** 형태 암시.
- **Segmed/Openda**: 큐레이션 프로젝트 중심 — "human-in-the-loop"가 있어 FSM에 `qa_review` 상태가 있을 가능성. RadiVault v0.1은 NLP-자동 라벨 주문까지만 상정하므로 **qa_review는 v0.2 Tier 2/3용** 확장 여지만 남긴다.
- **Stripe Orders API**(영감): `open → submitted → processing → complete → canceled`. RadiVault는 staging/fetching 중간을 세분화해야 하는 점이 다름 — **물리 데이터 파이프라인**이므로 FSM이 더 길어야 관측·디버깅 가능.
- **Shopify Fulfillment**: `partially_fulfilled` 상태가 있으며 주문 단위가 아닌 라인 아이템 단위 — 본 문서 `staging_partial`의 권고 근거.

---

### 4.2 Gateway pull-based transfer job protocol

#### 4.2.1 Pull vs Push 결정 매트릭스

| 기준 | Pull (Gateway → Central long-poll) | Push (Central → Gateway webhook) |
|------|-----------------------------------|----------------------------------|
| 방화벽 친화성 | **우수** — Gateway는 이미 outbound-only | 나쁨 — 병원 내 inbound 포트 개방 필요 |
| 인증 재사용 | 기존 Bearer(`upload_token`) 그대로 | 신규 webhook HMAC shared secret 필요 |
| 병원 IT 승인 | **기존 승인 범위 내** | 신규 변경 요청 → 수 주 지연 |
| 레이턴시 | poll interval 의존(30s 권고), 최악 poll 주기 | 수 초 이내 |
| 중앙 로직 단순도 | 주문을 큐에 넣고 기다림 — 단순 | 재시도·circuit breaker·Dead webhook 필요 |
| 장애 시 복구 | Gateway가 reconnect 하면 자동 재개 | Central이 재시도 책임 |
| 스케일 | 각 Gateway 1 open connection → 병원 수에 선형 | Central 측 fan-out 비용 |

- **v0.1 결정**: **Pull(long-poll) 채택**. 이유 — 이미 `dev-spec-gateway-agent §4.4, §12.3`에서 outbound-only를 **설계 원칙**으로 선언했고, push를 재도입하는 순간 원칙이 깨진다. 레이턴시 penalty는 30s poll interval + 48h SLA라는 기본 목표 하에 **무시 가능**.
- **v0.2 선택지**: paid tier 일부 병원에서 레이턴시가 치명적이면 **병원 측 주도 push 회피 대안**으로 **Server-Sent Events(SSE)** 장기 연결을 검토(여전히 outbound-only). WebSocket은 프록시 호환 문제로 거부.

#### 4.2.2 Long-poll 엔드포인트 설계

```
GET /v1/gateway/transfer-jobs?wait=30s&max_jobs=1
Host: ingest.radivault.io
Authorization: Bearer <gateway_upload_token>
Accept: application/json

-- 200 OK (job 있음)
{
  "transfer_job_id": "tj_01HX...",
  "order_id":        "ord_01HX...",
  "hospital_id":     "hosp_abc",
  "lease_expires_at":"2026-04-22T10:35:00Z",
  "studies":[
    {"pseudo_study_uid":"2.25.xxxx","expected_instances":184,"priority":1}
  ],
  "ruleset_version_required":"v0.1.0",
  "salt_version_required":1
}

-- 204 No Content (빈 큐 + wait 타임아웃)
(body empty, Retry-After: 0 헤더)
```

- **wait**: 기본 30s, 최대 60s (ALB idle timeout 고려). HTTP/2 연결 재사용으로 open-connection 비용 최소화.
- **Lease**: 서버는 `transfer_job.lease_expires_at = now() + 15m`으로 claim을 기록. 만료되면 `SKIP LOCKED` 폴링으로 다른 Gateway 재클레임(단, 병원별 Gateway가 1:1이므로 사실상 같은 Gateway의 재시도 케이스).
- **max_jobs**: v0.1은 1 고정(동시 2 job의 상호 의존 복잡성 회피). v0.2 batch claim.

#### 4.2.3 Progress / Complete / Fail 보고

```
POST /v1/gateway/transfer-jobs/{tj_id}/progress
{
  "n_fetched":  120,
  "n_deided":   118,
  "n_uploaded": 110,
  "lease_extend": true
}
-- 200 OK { "lease_expires_at":"..." }

POST /v1/gateway/transfer-jobs/{tj_id}/complete
{
  "manifest": [
    { "pseudo_study_uid":"2.25.xxx","n_instances":184,"total_bytes":94321012,"status":"uploaded" }
  ],
  "audit_ref": { "seq":22345, "hash":"sha256:..." }
}
-- 200 OK → Central이 order FSM `fetching → staging_complete`

POST /v1/gateway/transfer-jobs/{tj_id}/fail
{
  "reason_code":"PACS_UNAVAILABLE|DEID_FAILED|UPLOAD_FAILED|BURNED_IN_BLOCKED|OTHER",
  "details":"...",
  "retryable": true
}
-- 200 OK → Central 재시도 카운터 +1; 한도 초과 시 `failed`
```

- `progress`는 lease 연장 용도와 관찰성 메트릭 동시 충족. Central은 progress 없이 15분 지나면 lease 회수·재큐.
- `complete` manifest는 Ingest 경로의 `POST /v1/ingest/studies`로 이미 올라온 study들을 **주문 연결 관점**에서 집계. 즉 study 업로드 본체는 기존 Ingest 엔드포인트 재사용이며, complete는 "주문 X의 페치 부분이 끝났다"는 프레이밍만 제공.

#### 4.2.4 재시도 & Dead Letter

- 재시도 정책: `max_retries = 5`, 지수 백오프 initial 60s factor 2 cap 1h. Gateway가 `retryable=false`를 반환하면 즉시 DLQ.
- DLQ 테이블 `transfer_job_dead_letter` — 운영자 대시보드에서 `admin-cli order requeue --id` 또는 `admin-cli order fail --id` 수동 처리.
- 재시도 한도 도달 시 order FSM → `failed`, buyer에게 상태 폴링으로 통보. v0.1.1에서 이메일/webhook.

#### 4.2.5 동시성·격리

- 같은 병원(hospital_pk)에 대해 **동시 transfer-job 캡** = 기본 2, 설정 가능. 이유 — `dev-spec-gateway-agent §4.1 FR-5`가 PACS 측 `max_concurrency`를 기본 4로 두었고, 그 중 절반을 주문 fetching에, 나머지를 Flow A 상시 수집에 배분.
- 같은 `(order_pk, pseudo_study_uid)`는 최대 1 transfer-job. 중복 claim 시 409.

---

### 4.3 Hot Storage vs 온디맨드 페치 결정

#### 4.3.1 Study별 presence check

- **필드**: `study.central_object_present BOOLEAN DEFAULT FALSE` + `study.first_uploaded_at`, `study.last_verified_at`.
- **Update 규칙**:
  - Ingest 성공 시 true (이미 `central-ingest` 범위).
  - Admin `pin`/`unpin` 명령 시 수동 제어.
  - 야간 배치에서 S3 HEAD object로 sampling 재검증(drift 방지).
- **Order creation 분기**:
  - 요청 cohort의 각 study를 `SELECT central_object_present FROM study WHERE pseudo_study_uid = ANY(:list)` 한 번에 조회.
  - all present → **hot path**: `staging_copy` job만 생성(S3 COPY API, 같은 리전 내 0.001$/GB 수준의 요청 비용만).
  - all missing → **cold path**: `transfer_job` 생성 → Gateway pull.
  - 혼합 → **mixed**: 두 sub-job을 병렬.

#### 4.3.2 비용 모델

- **Storage 비용**(AWS S3 Seoul Standard 기준 공개가 2026-04 추정)
  - 모든 study 상주: 100만 study × 100MB = 100TB → 월 $2,500 (`central-ingest §4.3` 재확인).
  - Hot 10% + Cold 90%: Hot 10TB × $25 + Cold in-hospital(무상 가정) → 월 $250.
- **온디맨드 페치 비용**
  - Gateway→Central egress: AWS S3 inbound 무료(수신 측). 병원 측 WAN은 병원 부담.
  - 주문 1건 평균 50 study × 100MB = 5GB 업로드 → 네트워크는 무료, 처리 지연 ≈ 병원 대역폭 100Mbps 기준 7분 + PACS 페치 + De-ID.

- **권고**: v0.1은 **전량 cold (온디맨드)** 를 디폴트로. 상주 비용은 10% 수준으로도 현금 흐름을 크게 악화시키므로, 판매 빈도 데이터가 쌓이기 전엔 무의미.

#### 4.3.3 Cache eviction 정책 (v0.1.1 대비)

- 후보:
  - **LRU (Last Accessed)**: 단순. "인기 있지만 오래 조회 안 된 데이터"를 놓칠 리스크.
  - **Purchase-frequency weighted**: `score = α × recency + β × buy_count`. **권고**. α=0.4, β=0.6 초기값.
  - **코호트 기반 eviction**: 희귀 코호트는 priority +1 가중치 — 희귀한 study가 지우지 말아야 할 자산.
- v0.1 미구현. 현재는 모든 ingested study가 S3 라이프사이클 룰(`central-ingest §4.3.5`)로 90일 후 IA, 180일 후 Glacier IR 로 이행.

#### 4.3.4 Flow C (선제 staging) v0.1.1 backlog 이유

- **구현 비용**: 판매 통계 분석 → 코호트 식별 → admin 승인 → Gateway 대상 batch transfer-job. 현재 MVP에는 데이터 수집 자체가 빈곤해 자동화가 과적합.
- **수동 pinning**만 v0.1에 포함: admin-cli `order-admin hotstorage pin --pseudo-study-uid ...` + `unpin`.

---

### 4.4 Presigned download URL 설계

#### 4.4.1 AWS S3 SigV4 presigned URL 메커니즘 (2026-04 기준)

- **서명 과정**(공식 문서 요약)
  - 요청 파라미터 canonicalize → `CanonicalRequest` 문자열화.
  - `StringToSign = "AWS4-HMAC-SHA256" \n <timestamp> \n <scope> \n <sha256(CanonicalRequest)>`.
  - `signingKey = HMAC(HMAC(HMAC(HMAC("AWS4"+secret, date), region), service), "aws4_request")`.
  - `signature = HMAC(signingKey, StringToSign)`.
  - URL 쿼리로 `X-Amz-Algorithm`, `X-Amz-Credential`, `X-Amz-Date`, `X-Amz-Expires`, `X-Amz-SignedHeaders`, `X-Amz-Signature` 부착.
- **TTL 상한**: **최대 7일(604800초)**. IAM user long-term 자격증명 기준. IAM role(short-term session) 기반 서명은 세션 토큰 수명이 상한. 아키텍처 §5.3이 이미 7일을 명시 — **정합**.
- **TTL 권고값**
  - v0.1 기본 **24h**. 이유: URL 누출 시 블라스트 반경 축소 + refresh 패턴으로 필요 시 연장.
  - paid tier·대용량 스터디(>10GB)에 한해 **72h** 옵션.
  - 7일은 "내 회사 내부 네트워크 사정상 주말까지 필요"한 실수요에만 opt-in.

#### 4.4.2 Per-object vs Per-manifest(zip/tar)

| 옵션 | 장점 | 단점 |
|------|------|------|
| **Per-object URL 배열** (권고) | 병렬 다운로드(S3 parallel GET), 실패 시 부분 재시도, 서버 측 zip 생성 비용 없음 | Buyer가 N 요청 관리 |
| **서버 측 zip/tar 번들** | 단일 URL 편의 | zip 생성 CPU·메모리·임시 디스크, 부분 재시도 불가, 대형 cohort는 Lambda/EC2 spikes |
| **on-the-fly zip streaming** | 사전 생성 비용 없음 | 생성 시 TTL 타이밍 미묘, 실패 시 재개 불가 |

- **v0.1 결정**: per-object URL 배열. 응답 shape:
  ```jsonc
  {
    "order_id": "ord_01HX...",
    "expires_at":"2026-04-23T10:00:00Z",
    "ttl_seconds": 86400,
    "items":[
      {
        "pseudo_study_uid":"2.25.xxxx",
        "files":[
          { "object_key":"…/0001.dcm", "bytes":513222,
            "sha256":"abcd...", "url":"https://s3.ap-northeast-2.amazonaws.com/..." }
        ]
      }
    ],
    "total_bytes": 94321012,
    "refresh_url":"https://api.radivault.io/v1/orders/ord_.../download/refresh"
  }
  ```
- **Parallel 권고**: buyer SDK 문서에 "16 concurrent GETs + HTTP Range partial retries" 예시 포함. 단일 스터디 평균 100–800MB 기준 수 분 완료.

#### 4.4.3 Access control

- **SignedHeaders 제한**: `X-Amz-SignedHeaders=host` 고정. 추가 헤더 서명은 buyer 다양한 HTTP 클라이언트 호환성 저해.
- **IP 제한 옵션**: SigV4 자체로는 IP 제약 없음. IP 제한이 필요하면 **CloudFront Signed URL + IP policy**로 대체(v0.2). v0.1은 계약 조항 + audit 로그 기반 감지로 갈음.
- **Per-order 키 회전**: buyer가 같은 order를 여러 번 diff download하면 새 URL이 매번 생성됨. S3 객체 키는 동일하되 서명은 매번 fresh. 이는 **revocation 대체**의 가장 중요한 메커니즘 — 이전 URL을 무효화할 수는 없지만 TTL이 짧다면 사실상 회수됨.
- **response-content-disposition**: presigned URL에 `attachment; filename="<pseudo_sop_uid>.dcm"` 강제 삽입해 브라우저 실행 방지.

#### 4.4.4 Revocation 한계 설계

- AWS S3 presigned URL은 **mid-stream revoke 불가**. 대응책:
  - **짧은 기본 TTL(24h)** + `refresh` API.
  - **KMS key rotation**(최후 수단): 버킷 SSE-KMS 키를 회전하면 해당 URL의 암호 복호화가 실패 — 단, 모든 활성 URL을 무력화하므로 **단일 유출 의심 시에만** 사용.
  - **S3 bucket policy 임시 deny**(장애 대응): `aws:CurrentTime > emergency_cutoff` 조건. v0.1 runbook에 명시.
- **Cloudflare/CloudFront 대안**: CDN 뒤에 두면 `cookie-based signed URL` 방식으로 **쿠키 revoke ≈ URL revoke** 에 근접. CDN 도입은 Phase 2+.

#### 4.4.5 SHA-256 체크섬 검증

- **Manifest에 포함**: `files[].sha256` 을 Ingest manifest에서 이미 기록(central-ingest §6.5). 다운로드 응답 JSON이 이를 그대로 전달.
- **Buyer 측 검증**: SDK 예시 `shasum -a 256 file.dcm | compare`. 서버측 추가 API(`GET /v1/orders/{id}/checksums`) 제공해 편의.
- **S3 side**: `x-amz-checksum-sha256` 업로드 시 기록 → `HEAD Object` 응답에 포함 → SDK가 자동 검증 가능(옵션).

---

### 4.5 Order validation & pricing stub

#### 4.5.1 Validation 규칙

| 규칙 | 임계 | 실패 코드 |
|------|------|-----------|
| **Buyer 스코프** | `buyer_api_key.scope_json.exclude_hospitals` 와 order cohort 교집합 공집합 | `403 ERR_ORDER_SCOPE_FORBIDDEN` |
| **코호트 크기** | Tier별 상한: free=0(주문 불가), preview=50 study, paid=10,000 study | `422 ERR_ORDER_COHORT_TOO_LARGE` |
| **일일/월간 주문 수** | preview=5/day, paid=50/day (override 가능) | `429 ERR_ORDER_QUOTA_EXCEEDED` |
| **`pseudo_study_uid` 유효성** | 모든 UID가 `study` 테이블에 존재 | `404 ERR_ORDER_STUDY_NOT_FOUND` |
| **중복 UID** | 한 주문 내 중복 허용 안함 | `400 ERR_ORDER_DUPLICATE_STUDY` |
| **크기 상한** | `sum(total_bytes) ≤ tier.max_order_bytes` (preview=10GB, paid=2TB) | `413 ERR_ORDER_TOO_LARGE` |
| **생성 레이트** | slowapi `orders.create` 10/min | `429 ERR_RATE_LIMITED` |

- Validation은 `submitted → validating → validated` 전이 중 동기 실행(< 2s p95 목표). 긴 검증(대규모 cohort membership verification)은 async task로 분리 가능.

#### 4.5.2 Pricing stub

- **단가 표**: Tier dev-spec `k-meddata-research-summary §8` 기반.
  - Tier 1 (자동 라벨): $3–8/study. v0.1 기본값 $5.
  - Tier 2 (전문의 라벨): $15–40/study — v0.1 out-of-scope.
  - Tier 3 (세그): $50–150 — v0.1 out-of-scope.
- v0.1은 **Tier 1만** 판매 가능. `order.total_estimated_usd = n_studies × tier_unit_price` 저장.
- 실제 과금은 없음: `status=pending_billing` 필드가 `ready_for_download` 이후 모든 주문에 기본 true. Billing feature(G)가 활성화되기 전까지 **환불·이의제기 불가**임을 계약서 `§FEE TBD` 조항에 명시하는 법률 자문 필요 플래그.
- **pending_billing 경계 안전성**:
  - 수익 실현 관점: 기록만 하고 수금은 하지 않으므로 GAAP 기준 **매출 인식 불가**. 회계 기록은 별도 CRM에 "free trial" 또는 "POC 무상 제공".
  - 법적 안전성: buyer에게 "결제 시스템 준비 중이며 본 주문은 무상 제공된다"는 e-signed 확인 필요. 표준 MSA에 해당 조항 선 삽입 권고.

#### 4.5.3 Pre-authorization flow (v0.2 대비)

- Billing feature 도입 시 `validating → preauthorizing → preauthorized → queued` 로 FSM 확장 (카드 hold 또는 invoice commit).
- v0.1 FSM에 `preauthorizing` 자리를 비워두면 v0.2 이관 시 breaking change 최소화.

#### 4.5.4 PDF 계약 / 클릭랩

- v0.1: **클릭랩 동의 화면**(web portal 미구현이므로 API 레벨 `agreement_hash` 필수 필드)만. 각 주문에 `agreement_version` 기록.
- PDF 계약 발행은 v0.2+ billing과 동반.

---

### 4.6 Download event auditing

#### 4.6.1 이벤트 스키마(제안)

```sql
CREATE TABLE download_event (
    event_pk            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_pk            BIGINT NOT NULL REFERENCES orders(order_pk),
    order_item_pk       BIGINT REFERENCES order_item(order_item_pk),
    buyer_pk            BIGINT NOT NULL REFERENCES buyer(buyer_pk),
    kid8                CHAR(8) NOT NULL,
    event_type          TEXT NOT NULL,          -- 'url.issued'|'get.started'|'get.completed'|'get.failed'
    ts                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    src_ip              INET,                   -- S3 Access Log join
    user_agent          TEXT,
    bytes_transferred   BIGINT,
    http_status         INTEGER,
    request_id          TEXT NOT NULL,
    object_key          TEXT,
    signature_hash      CHAR(16)                -- SigV4 signature sha256[:16] (유출 감지)
) PARTITION BY RANGE (ts);
```

- append-only (INSERT only GRANT; central-ingest `audit_ingest_event` 와 동일 패턴).
- `signature_hash`는 **URL 재사용/공유 탐지** 목적 — 같은 hash가 다른 IP·UA에서 반복 조회되면 의심 플래그.

#### 4.6.2 2차 증거 — S3 Access Log ETL

- S3 버킷에 Server Access Logging 활성화 → 별도 버킷 `radivault-s3-access-logs-{env}`로 집계.
- 일 1회 ETL job: access log + presigned URL 발급 레코드 JOIN → `download_event`와 대조. 불일치(발급 없이 다운로드됨 == 이론상 불가능) 시 SEV-1.
- 감사 보존: 중앙 `audit_daily_digest` 패턴 재사용(5년).

#### 4.6.3 매출 Attribution

- `download_event → order → buyer` 조인으로 "어느 buyer가 어느 hospital data를 얼마나 받았는가"를 **Revenue Share(Phase 2 Billing)** 가 참조.
- metadata-index `search_audit`와 `download_event`를 `filter_sha256 / pseudo_study_uid` 로 funnel 매핑 가능.

#### 4.6.4 GDPR / PIPA 고려

- **구매자 데이터**(buyer_contact.name, email, phone) — 기업 소속 개인이므로 **PIPA 대상 개인정보**. 다만 **B2B 업무 목적 + 명시 동의** 하에서는 합법. 단, 국외이전 시 개보법 §28의8의 일반 B2B 예외 해당 여부는 법률 자문 필요.
- **다운로드 이력**은 buyer 기업 단위 집계가 주목적이므로 개인식별성 제한. 단, `src_ip` + `user_agent`는 **개별 사용자 식별 가능** → minimization 원칙 적용: 수집하되 5년 후 익명화(ip → /24 마스크).

---

### 4.7 Cancellation / expiration / cleanup

#### 4.7.1 만료 TTL

- `ready_for_download → expired` 7일 (ARCHITECTURE §3.4, S3 SigV4 max와 정합).
- 운영 개정: paid tier 14일 옵션(URL refresh로 연장).

#### 4.7.2 Staging cleanup

- 만료 시: staging 전용 버킷·prefix(`staging/<order_id>/`)는 **S3 Lifecycle rule `expires_at+1d`** 로 자동 삭제.
- 주의: study 본체는 `ingest/` prefix에 별도 보관 → 주문 만료가 본체를 지우지 않는다(재주문 시 즉시 재발급).

#### 4.7.3 Gateway in-flight 취소 처리

- `queued → cancelled` 전이는 문제 없음(transfer-job 생성 전).
- `fetching` 상태에서 취소 요청:
  - Central은 `orders.cancel_requested=true` 플래그만 즉시 기록.
  - Gateway는 다음 `progress` ping에서 이 플래그를 조회(응답 필드로 포함) → Gateway가 자체 판단으로 **현재 처리 중 스터디 continue + 후속 skip** 또는 **즉시 abort**. v0.1 권고: **continue** — 자원 이미 소비했고 업로드 완료 시 Hot Storage가 revenue share 자산으로 남음.
  - 완료된 study는 Central에 업로드되지만 order에는 연결되지 않고 `unlinked` 플래그로 저장 → admin이 나중에 다른 주문에 수동 할당 가능.

#### 4.7.4 버이어 알림

- v0.1: **상태 폴링만** (`GET /v1/orders/{id}` 반환되는 `status`, `progress`, `eta_seconds` 필드).
- v0.1.1: webhook POST(구매자 등록 endpoint), 이메일 알림(운영자 수동 발신).
- SSE 실시간 스트리밍(`GET /v1/orders/{id}/stream`)은 paid tier 전용 v0.2.

#### 4.7.5 경쟁사 정책

- Gradient Health: 공개 자료는 "48h" ETA만 언급, 취소 정책 비공개.
- Segmed/Openda: "프로젝트별 큐레이션" 방식이어서 취소는 세일즈 협상 영역.
- **RadiVault 권고**: 자동화된 `queued`까지 취소 free, `fetching` 이후는 **no refund**. 표준 MSA에 명시.

---

## 5. 시사점 (RadiVault에의 함의)

1. **dev-spec의 핵심 축 3개**: (a) Order FSM 12-state + transition 매트릭스, (b) Gateway pull long-poll 엔드포인트 3종 + lease, (c) Buyer download API 2종(manifest 발급 + refresh). 이 셋이 상호 의존하므로 dev-spec에서 **시퀀스 다이어그램 필수**.
2. **기존 dev-spec 2곳 연쇄 변경 필요**
   - `dev-spec-gateway-agent`: §4.4 Upload Client 외에 **신규 §4.10 Transfer Job Consumer**. `radivault_gateway/orchestrator/` 아래 새 모듈. Flow A는 건드리지 않고 병렬 루프로 운영.
   - `dev-spec-central-ingest`: §6 데이터 모델에 `orders`, `order_item`, `transfer_job`, `transfer_job_dead_letter`, `download_event`, `outbox` 테이블 추가. §7 API 섹션에 `/v1/orders/*`, `/v1/gateway/transfer-jobs/*` 라우터 추가.
3. **metadata-index 재사용**: buyer 인증·쿼터·스코프 필드 **모두 그대로**. `buyer_api_key.scope_json`에 `exclude_hospitals` 이미 있음 — 주문 검증이 이를 참조.
4. **Web portal 부재 대응**: v0.1은 UI 없음. curl/Postman/Python SDK 예제 5개를 dev-spec 부록으로 발행. Segmed도 초창기 공식 포털 없이 세일즈팀 문의가 프로비저닝 진입점이었음을 참고.
5. **ARCHITECTURE 문서 갱신 제안**
   - §4.5 Order Orchestrator: "pull-based, long-poll via outbound Gateway" 명시.
   - §5.3 Download Manager: 기본 TTL 24h + refresh 메커니즘 추가.
   - §3.4 Staging Storage: Gateway 측 staging과 Central 측 `staging/` prefix 두 개 존재 구분 필요 — 현 아키텍처 문서는 전자만 언급.
6. **법률 자문 항목 신설**
   - 표준 MSA §"Cancellation & Refund" 조항: queued 이전 자유 취소, fetching 이후 no refund.
   - 표준 DPA §"Cross-border delivery audit": download_event 저장 5년 + 국외 buyer에 대한 통지 의무 여부.
   - `pending_billing` 주문의 매출 인식 처리에 대한 회계사 자문.

---

## 6. 한계·오픈 퀘스천 (≤10)

1. **Kyle 결정 — pull 전용 고정 vs SSE 옵션**: v0.1을 pull long-poll로 고정(권고). 향후 레이턴시 요구 시 SSE를 열지 여부?
2. **Kyle 결정 — 기본 presigned TTL**: 24h(권고) vs 48h vs 7d. 파일럿 buyer가 실제 요구하는 값은 실측 필요.
3. **Kyle 결정 — `fetching` 중 취소 시 unlinked study 자원**: 자동 관측(대시보드 notice)만 할지, 자동 "스팟 할당"으로 다른 주문이 소비 가능하게 할지.
4. **Kyle 결정 — Tier별 cohort 크기 상한**: 본 문서 값(preview=50, paid=10K study)은 업계 추정. 파일럿 FDA급 고객은 훨씬 크게 요구 가능.
5. **Kyle 결정 — Billing 도입 시점**: v0.1 `pending_billing` 스텁만, v0.2 Stripe 통합 또는 국내 PG? 결제 게이트웨이 선정은 별도 dev-spec.
6. **실측 필요 — 48h SLA 달성률**: Gateway 처리량(§4.2.5 동시성 2 job) × 평균 cohort 50 study × 100MB / 병원 100Mbps = 약 1.1시간. 병원 PACS 부하 고려하면 실측 필요.
7. **오픈 — S3 Lifecycle `staging/*` 정책 세밀도**: 주문 TTL이 다양(24h/72h/7d)일 때 동일 prefix에 두면 lifecycle rule로 표현 어려움 → `staging/<ttl>/<order_id>/` 2-tier 구조 권고, 추후 확정.
8. **오픈 — CloudFront 도입 시점**: 글로벌 buyer 응답 속도 + IP 제한 revocation 기능 필요. SOC 2 Type I 취득 시점과 연동.
9. **오픈 — outbox poller 성능**: at-least-once에서 같은 사이드이펙트가 재실행되지 않게 idempotency key. 규모 커지면 Kafka/NATS로 대체.
10. **법률 플래그 — buyer 연락처 개인정보 처리**: buyer_contact 테이블의 PIPA 대응 범위는 법률 자문 필요.

---

## 7. 출처

### AWS 1차
- AWS S3 Developer Guide — Sharing objects with presigned URLs: `https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html`
- AWS S3 — Authenticating Requests (SigV4): `https://docs.aws.amazon.com/AmazonS3/latest/API/sig-v4-authenticating-requests.html`
- AWS S3 — Logging requests with server access logging: `https://docs.aws.amazon.com/AmazonS3/latest/userguide/ServerLogs.html`
- AWS S3 — Lifecycle configuration: `https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html`
- AWS CloudFront — Using signed URLs: `https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-signed-urls.html`
- AWS SQS — Visibility timeout & DLQ: `https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html`
- AWS Step Functions — Long-running workflows: `https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html`

### IETF / RFC
- RFC 7540 — HTTP/2 (long-lived connections)
- RFC 8470 — Using Early Data in HTTP
- IETF draft-ietf-httpapi-idempotency-key-header (이전 리서치와 공통)
- RFC 6750 — OAuth 2.0 Bearer Tokens

### PostgreSQL
- PostgreSQL 16 — `SELECT ... FOR UPDATE SKIP LOCKED`: `https://www.postgresql.org/docs/16/sql-select.html`
- PostgreSQL 16 — Advisory Locks: `https://www.postgresql.org/docs/16/explicit-locking.html`
- pg_partman README (재인용)

### 경쟁사 / 업계 레퍼런스
- Gradient Health Atlas (2026-04 조회): `https://gradienthealth.io/atlas/`
- Gradient Health Atlas 2 launch: `https://gradienthealth.io/gradient-health-launches-atlas-2-setting-a-new-standard-for-medical-imaging-data-access/`
- Segmed/Openda 런칭: `https://www.prnewswire.com/news-releases/segmed-unveils-new-brand-identity-and-introduces-openda-the-next-evolution-for-its-insight-platform-302185953.html`
- Stripe Orders API (영감 차원만): `https://stripe.com/docs/api/orders_v2` — RadiVault가 직접 채택하는 API 아님.
- Shopify Fulfillment partial states: `https://shopify.dev/docs/api/admin-rest/2024-07/resources/fulfillment`

### 한국 규제 (이전 리서치와 공통)
- 개인정보보호법 제28조의8 (법제처, 2023-09-15 개정)
- 개인정보위 "가명정보 처리 가이드라인" (2024)
- 본 문서는 법률 자문이 아니다. 구체 사안은 변호사 자문 필요.

(모든 공개 가격·제품 상태는 2026-04-22 기준 추정. dev-spec 확정 시 재확인 필요.)

---

## 8. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-22 | @researcher (Claude Opus 4.7) | 최초 작성. Order Fulfillment v0.1 기술 기반 7개 영역(FSM · pull transfer-job · Hot vs on-demand · presigned URL · validation + pricing stub · download audit · cancel/expire/cleanup) 조사. |

---

### NEXT_STEP
- 완료 산출물: `docs/research/order-fulfillment-technical-foundations.md`
- 제안 다음 단계: **@planner** — `docs/specs/dev-spec-order-fulfillment.md` 작성. 본 리서치 §4.1–§4.7을 근거로 다음을 요구사항화:
  1. **Order FSM 모듈**: 12-state 전이 매트릭스, Idempotency-Key 강제, `orders` + `order_item` + `order_status_history` 테이블, PG row-lock 기반 멱등 전이.
  2. **Gateway transfer-job 프로토콜**: `GET /v1/gateway/transfer-jobs?wait=30s` long-poll + lease 15분 + progress/complete/fail 엔드포인트. `SKIP LOCKED` 폴링. DLQ.
  3. **Hot Storage 분기**: `study.central_object_present` 컬럼 + order creation 시 `hot_hit / cold / mixed` 분기 로직. 수동 pinning CLI.
  4. **Presigned URL API**: `POST /v1/orders/{id}/download` 발급 + `POST /…/download/refresh` refresh. 기본 TTL 24h. 응답 shape 고정.
  5. **Validation + pricing stub**: Tier별 cohort 상한·일 주문 수 한도, `total_estimated_usd` 계산, `status=pending_billing` 표기.
  6. **Download audit**: `download_event` append-only 테이블, S3 Access Log ETL 야간 배치.
  7. **Cleanup**: `staging/*` Lifecycle rule, `ready→expired` 7d 기본 TTL, cancelled 중 unlinked study 처리 정책.
  8. **Gateway dev-spec 연쇄 갱신**: `§4.10 Transfer Job Consumer` 신규 섹션 제안(FR 번호 후속 배정).
  9. **Central-ingest dev-spec 연쇄 갱신**: `§6.8 Order 데이터 모델` 신규 + §7에 `/v1/orders/*`, `/v1/gateway/transfer-jobs/*` 라우터 추가 제안.
  10. **샘플 / Postman**: `docs/samples/orders/` 5개 시나리오(create, poll, download, cancel, refresh).
- Kyle 결정 필요 사항:
  1. **Pull-only 고정 여부** — v0.1 확정, v0.2 SSE 도입 시점.
  2. **Presigned URL 기본 TTL** — 24h(권고) vs 48h vs 7d.
  3. **Tier cohort 상한** — preview=50/paid=10K(권고) 확정?
  4. **Billing 도입 시점 & PG 공급자** — v0.2 vs v0.3, Stripe vs 국내 PG.
  5. **`fetching` 중 취소 시 unlinked study 정책** — 운영자 수동 처리 vs 자동 재할당.
  6. **표준 MSA·DPA 법률 자문 착수 시점** — cancellation/no-refund 조항, cross-border download audit, `pending_billing` 무상 제공 조항 정비.
  7. **Web portal 시점** — 본 v0.1은 API-only, UI는 언제 붙일지(designer 투입 타이밍).
