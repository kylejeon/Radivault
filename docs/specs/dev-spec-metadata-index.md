# 개발지시서 — Metadata Index v0.1 MVP (Buyer-facing Search API)

> **Status**: Draft v0.1 · **Feature slug**: `metadata-index` · **Last updated**: 2026-04-22
> **작성자**: @planner (Claude Opus 4.7) · **근거**:
> - [리서치 — Metadata Index 기술 기반](../research/metadata-index-technical-foundations.md) (primary upstream)
> - [리서치 — K-MedData 요약](../research/k-meddata-research-summary.md) (market context)
> - [PRD §4.2 중앙 메타데이터 인덱스, §4.3 구매자 포털](../prd.md)
> - [ARCHITECTURE §4 Zone 2, §5 Zone 3](../ARCHITECTURE.md)
> - [dev-spec-central-ingest §6 데이터 모델](./dev-spec-central-ingest.md) — **상속하는 스키마**
> - [design-spec-central-ingest §2 envelope, §5 error taxonomy](./design-spec-central-ingest.md) — **envelope·에러 포맷 계승**
> - `src/radivault_central/db/models.py` — 실 ORM 참조

---

## 0. 요약 (TL;DR)

RadiVault Zone 3 의 첫 공개 인터넷 엔드포인트. Central Ingest 가 이미 수집·정규화한 `study`, `series`, `instance`, `patient_pseudo` 테이블 위에 **읽기 전용 검색 API**를 노출한다. v0.1 범위는 "엔터프라이즈 AI 구매자가 API 키 한 줄로 모달리티·부위·연령·성별·날짜 범위 등을 결합해 코호트 규모를 파악하고 샘플 메타데이터를 받는 것"까지이며, 썸네일·다운로드·결제·포털 UI·NLP 라벨 검색은 모두 **후속 dev-spec**이다.

서비스는 `radivault_search` 라는 **별도 FastAPI 서비스**로 제공되며, 동일 PostgreSQL 인스턴스에 대해 **READ-only 전용 역할**(`radivault_buyer_ro`)로 연결한다. 중앙 ingest 와 **물리적으로 분리 가능한 컨테이너**이나, v0.1 은 같은 저장소·같은 Alembic 트리의 확장 migration 으로 배포한다. envelope·에러 포맷은 design-spec-central-ingest §2 / §5 를 승계하며, 신규 에러 코드 5종(`ERR_CURSOR_FILTER_CHANGED`, `ERR_QUERY_TOO_BROAD`, `ERR_FILTER_TOO_MANY`, `ERR_BUYER_QUOTA`, `ERR_BUYER_CONCURRENCY`)을 추가한다.

**법적 전제**: 본 서비스는 Central Ingest 가 이미 `anonymization_flag="fully_anonymized"` 게이트를 통과한 데이터만 참조한다. 응답 어디에도 원본 UID·환자 식별자는 포함되지 않으며, 로그·감사 테이블에는 **필터 sha256**과 필드 이름 목록만 기록해 필터 자체(구매자 IP)가 새어 나가지 않도록 한다.

---

## 1. 기능 개요

Metadata Index v0.1 은 다음을 제공하는 **단일 HTTP API 서비스**다.

- 구매자가 필터(modality, body part, age bucket, sex, date range, manufacturer, hospital coverage)를 조합하여 **해당 조건의 코호트 규모·분포·샘플**을 즉시 확인할 수 있는 검색 엔드포인트.
- API 키 기반 인증(argon2id 서버 해시, `rv_live_<kid8>_<random32>` 포맷) + 병원별 이용약관과 물리 분리된 `buyer_api_key` 테이블.
- 깊은 페이지까지 안정적인 **keyset cursor 페이지네이션**.
- 화이트리스트 필드에 대한 **faceted aggregation**(opt-out 가능).
- 위험한 광범위 쿼리에 대한 **pre-execution cost estimator**, PG `statement_timeout`, per-buyer rate limit, 동시성 캡 등 다층 DoS 방어.
- `radivault_index_*` Prometheus prefix 메트릭, PHI-안전 JSON 로그, `search_audit` 테이블.
- `search-admin` CLI: 구매자 키 발급·회수·조회, 쿼리 통계 덤프.
- Docker 이미지 · docker-compose-search · Alembic migration(신규 테이블 + 신규 인덱스).
- `/healthz`, `/readyz`, `/v1/version` 운영 프로브.

**구매자는 이 API 로 "쓸 만한 데이터가 얼마나 있는지"를 초단위로 답을 얻는다.** 실제 파일 다운로드·썸네일·결제는 Order Orchestrator · Download Manager · Billing dev-spec 에서 연결된다.

---

## 2. 사용자 스토리

- **As an** AI-기업 통합 개발자, **I want** 한 줄 `curl` 명령으로 `modality=CT, body_part=CHEST, age=50-70, date>=2024` 코호트의 **총 스터디 수·병원 분포·제조사 분포**를 2초 이내 받는다, **so that** PoC 의사결정 회의에 들어가기 전에 구매 가치를 수치로 제시할 수 있다.
- **As an** FDA 허가용 데이터셋을 찾는 엔지니어, **I want** `min_hospitals` 필터로 "최소 3곳 이상 병원 합산" 코호트만 노출되도록 제한한다, **so that** 단일 병원 편향을 피할 수 있다.
- **As a** 제약사 임상 통계 엔지니어, **I want** keyset cursor 로 페이지를 넘기더라도 필터가 변경되지 않은 이상 중복·누락 없이 전체 코호트를 스트림으로 받을 수 있다, **so that** 별도의 offset 계산 없이 자동화 스크립트를 안정 운용한다.
- **As a** RadiVault 플랫폼 SRE, **I want** 구매자별 "empty-result rate > 40%" 알람이 울린다, **so that** 필터 UX 에 문제가 생겼거나 특정 구매자가 비정상 탐색 중인 상황을 즉시 알아챈다.
- **As an** 영업 담당자, **I want** 구매자가 발급받은 키가 "preview tier 100 queries/day" 한도에 접근하면 메트릭을 통해 실시간으로 본다, **so that** 유료 전환 타이밍을 놓치지 않는다.
- **As a** 플랫폼 법무 담당자, **I want** 모든 검색 요청이 `search_audit` 에 `filter_sha256 + result_count + buyer_id` 로 저장되고 raw filter body 는 **절대 저장되지 않는다**, **so that** 구매자의 탐색 패턴 자체가 내부에서도 IP 유출되지 않는다.

---

## 3. 범위

### 3.1 포함 (In-scope — v0.1 MVP)

1. **API 엔드포인트 7종** (아래 외에는 v0.1 비공개):
   - `POST /v1/search/studies` — 코호트 요약 검색(필터 + 패싯 + 페이지네이션).
   - `GET /v1/search/studies/{pseudo_study_uid}` — 단일 스터디 메타데이터 상세(다운로드 없음).
   - `GET /v1/search/facets` — 가능한 필터 값·카디널리티(UI 자동 완성용).
   - `GET /v1/search/hospitals` — 참여 병원 불투명 ID + 집계 카운트.
   - `GET /healthz`, `GET /readyz`, `GET /v1/version` — 운영 프로브.
2. **Buyer 인증** — argon2id + `rv_live_<kid8>_<random32>` 포맷, 신규 `buyer_api_key` 테이블(§6.2). central-ingest `auth_token` 과 물리 테이블 분리.
3. **필터 7차원** — modality, body_part, age_bucket, sex, study_date_shifted(range), manufacturer, hospital_coverage(min_hospitals).
4. **Keyset cursor pagination** — `(study_date_shifted DESC, study_pk DESC)` 튜플 + base64 JSON + `filter_sha256` 변조 감지.
5. **Faceted aggregation** — 화이트리스트 6 필드(modality, body_part, sex, age_bucket, manufacturer, year), `include_facets=true|false` 스위치.
6. **Pre-execution cost estimator** — 결과 추정치 > 10M rows → `ERR_QUERY_TOO_BROAD`.
7. **Multi-layer DoS 방어** — PG `statement_timeout=10s`(buyer role), FastAPI request timeout 15s, slowapi + Redis tiered rate-limit, per-buyer concurrency semaphore, per-IN 필터 ≤ 10 element 상한.
8. **Observability** — `radivault_index_*` Prometheus prefix, JSON 구조화 로그(필터 sha256 only), OpenTelemetry spans.
9. **`search_audit` 테이블** — 모든 검색 요청을 `filter_sha256 + result_count + latency_ms + buyer_pk + request_id` 로 기록(PHI 금지, raw filter 금지). 매출 funnel v0.2 를 위한 전제 데이터.
10. **Admin CLI `search-admin`** — `buyer` · `key` · `stats` 3 서브커맨드 트리(§4.10).
11. **Packaging** — 별도 Docker 이미지(`Dockerfile.search` 또는 `Dockerfile.central` 의 build-arg 분기; §4.12). `docker-compose-search.yml` — search 서비스 + 기존 postgres/redis 재사용.
12. **Alembic migration** — central-ingest 의 기존 `alembic/versions/` 에 **새 revision 1개**(buyer_api_key, search_audit 테이블 + 3개 composite index + `radivault_buyer_ro` role 부여). 별도 alembic repo 가 필요한지는 §9.2 코멘트 참조.
13. **Envelope / 에러 포맷** — design-spec-central-ingest §2 의 7-field envelope(`error`, `detail`, `message_ko`, `message_en`, `request_id`, `doc_url`, `hint`, `retry_after`) 그대로 재사용. 신규 에러 코드 5종만 추가.
14. **Tests** — pytest unit + integration. central-ingest fixture 재사용 + 합성 study row factory(패싯 검증용) 추가.

### 3.2 제외 (Out-of-scope — v0.2 이상)

1. **Purchase / cart / billing 흐름** — Order Orchestrator dev-spec.
2. **실제 파일 다운로드 / S3 presigned URL 발급** — Download Manager dev-spec.
3. **Buyer portal 웹 UI** — 본 dev-spec 은 API 전용.
4. **NLP 라벨 기반 검색**(판독문 진단명, RadLex, ICD-10) — NLP label pipeline dev-spec 의 스키마 확장이 선행되어야 함.
5. **Python / JS SDK 제공** — REST + OpenAPI 3.1 + curl 샘플 5종 + Postman 컬렉션으로 대체(§4.12).
6. **Materialized `cohort_summary` view + HyperLogLog** — v0.2 성능 백로그. v0.1 은 정직한 GROUP BY.
7. **Hospital opt-out 기술 집행** — v0.1 은 MSA/DPA 계약 조항만. application-layer `exclude_hospitals` 필터는 v0.1.1, PG RLS 는 v0.2 백로그(§11 Q1).
8. **OAuth2 client-credentials / mTLS** — v0.2 옵션.
9. **Thumbnail image serving**.
10. **Saved cohorts / cohort diff** — v0.2+.
11. **Cross-language SDK (Go/Java/Ruby)** — 우선순위 없음.
12. **Materialized view 갱신 워커, pg_cron** — 범위 외.
13. **GraphQL 대안**.
14. **Full-text 서치**(Elasticsearch/OpenSearch 통합) — Phase 3 검토.

---

## 4. 기능 요구사항

번호는 feature-slug 내 고유. `@qa` 는 각 FR 을 §10 AC 로 매핑 검증.

### 4.1 인증 · API Key 관리

- **FR-1**: 모든 `/v1/search/*` 엔드포인트는 `Authorization: Bearer <api_key>` 헤더 필수. 미제공/형식 오류 → `401 ERR_AUTH_MISSING`(design-spec-central-ingest §5.1 재사용).
- **FR-2**: API 키 포맷은 `rv_live_<kid8>_<random32>` 고정. 총 길이 48자. `rv_test_*` prefix 는 dev/stage 환경 전용(§4.12 환경변수 `RV_SEARCH_ENV` 로 분기). 포맷 위반 → `401 ERR_AUTH_FORMAT`(design-spec 신규 코드, §13 Annex 환류 필요).
- **FR-3**: 키 조회 순서 — (1) 키 prefix `kid8` 추출, (2) `buyer_api_key` 인덱스 lookup 1회, (3) argon2id verify. `token_hash = argon2id(salt || secret)` 저장. 평문 키 DB 저장 금지.
- **FR-4**: argon2id 파라미터 기본값 `time_cost=3, memory_cost=65536 KiB, parallelism=2` — 리서치 §4.1.1. 파라미터는 `search.yml` 의 `auth.argon2.*` 에서 override 가능.
- **FR-5**: 검증 결과는 Redis 에 **60초 positive cache** (`buyer_auth:{kid8}` → `{buyer_pk, tier, rate_qps, rate_daily, scope_json}`). Cache hit 시 argon2 계산 skip. 부정 결과는 캐시 금지(타이밍 공격 억제).
- **FR-6**: 활성 조건 — `revoked_at IS NULL` AND (`expires_at IS NULL OR expires_at > now()`). 아니면 `401 ERR_AUTH_EXPIRED`.
- **FR-7**: 키 검증은 상수 시간 비교(`argon2.verify`). 부정 결과 분기 시 항상 argon2 최소 1회 실행하여 key 존재/부재 타이밍 차 제거.
- **FR-8**: 한 buyer 당 **여러 활성 키 동시 허용**(회전용). `revoked_at IS NOT NULL` 인 키는 즉시 거부.
- **FR-9**: `buyer_api_key.scope_json` 는 v0.1 에서 다음 필드만 해석한다: `{"tier": "preview|paid", "rate_limit_qps": int, "rate_limit_daily": int, "max_limit_per_page": int, "max_include_facets": bool}`. 미설정 필드는 `tier` 디폴트 매트릭스(§5) 값을 적용.
- **FR-10**: 인증 통과 시 요청 컨텍스트에 `(buyer_pk, tier, kid8)` 주입. 이후 모든 레이어는 이를 참조.

### 4.2 Rate-limit · Concurrency cap

- **FR-11**: slowapi + Redis 백엔드. 기본 한도(티어별):
  - **preview**: 20 req/min, **100 req/day**.
  - **paid**: 600 req/min, **10,000 req/day** (계약 시 override).
  - global per-IP: 300 req/min (coarse DoS 방어).
- **FR-12**: 한도 초과 → `429 ERR_RATE_LIMITED` + `Retry-After: <seconds>` 헤더, design-spec §2.5 포맷. 일일 쿼터 초과 → `429 ERR_BUYER_QUOTA`(신규 코드). per-buyer 동시성 초과 → `429 ERR_BUYER_CONCURRENCY`(신규).
- **FR-13**: Per-buyer 동시성 캡 — Redis 키 `buyer_inflight:{buyer_pk}` 에 `INCR` + `DECR`. 기본 상한 **6**(paid 는 20, §5 테이블). 초과 시 429 `ERR_BUYER_CONCURRENCY`. 요청 종료 시 `DECR` 보장(`finally` 블록).
- **FR-14**: Redis 장애 시 서비스는 보수적으로 **503 `ERR_IDEMP_UNAVAILABLE`** 반환(rate-limit 검증 불가 시 수락 금지; design-spec §5.2 재사용). 다만 `/healthz`·`/readyz`·`/v1/version` 은 영향 받지 않음.
- **FR-15**: Daily quota 카운터는 Redis `INCR buyer_daily:{buyer_pk}:{YYYYMMDD}` + TTL 26h. PG `search_audit` 테이블에서 fallback 집계 가능(월 보고서용).

### 4.3 Request validation · Cost estimator

- **FR-16**: 요청 바디는 `POST /v1/search/studies` 에서 pydantic v2 모델 `SearchRequest`(§6.4) 로 검증. 필드 타입 오류 → `400 ERR_REQUEST_SCHEMA`(design-spec §5 재사용 — `ERR_MANIFEST_SCHEMA` 와 구분을 위해 신규 코드 등록).
- **FR-17**: 각 `IN` 필터(`modality`, `body_part`, `manufacturer`, `age_bucket`) 는 **최대 10 원소**. 초과 → `400 ERR_FILTER_TOO_MANY`.
- **FR-18**: `study_date_shifted` 필터는 `from`·`to` **양쪽 필수**. 한쪽만 오면 `400 ERR_REQUEST_SCHEMA`. 허용 범위: `1900-01-01 ≤ from < to ≤ today + 1y`(시프트 날짜 허용 폭). 위반 → 동일 에러.
- **FR-19**: `limit` 기본 50, 최대 `scope_json.max_limit_per_page`(기본 200). 초과 → `400 ERR_PAGE_LIMIT`(design-spec §5.5 재사용).
- **FR-20**: `min_hospitals` 는 양의 정수 1..20. 초과 → `400 ERR_REQUEST_SCHEMA`.
- **FR-21**: Pre-execution cost estimator —
  - (a) Redis 캐시 `cohort_estimate:{filter_sha256}` 확인 (TTL 5분), 있으면 사용.
  - (b) 없으면 **단일 쿼리** `SELECT count_estimate FROM pg_class …` 또는 `EXPLAIN (FORMAT JSON)` 파싱으로 **예상 row 추정**(<=500ms timeout). PG planner rows 만 사용하므로 정확한 COUNT 불필요.
  - (c) 추정치 > 10,000,000 → `422 ERR_QUERY_TOO_BROAD` + `hint="Add a modality/date filter"` 응답.
  - (d) 성공 시 Redis 에 추정치 저장.
- **FR-22**: 요청에 포함된 `include_facets=true` 이고 추정치 > 2,000,000 rows → 패싯 계산 시 추가 비용 고려; 추정치가 임계를 넘으면 자동으로 `facets` 필드를 `null` 로 반환하고 응답 바디 `hint` 에 `"facets suppressed: cohort too large"` 명시(정책 결정 §11 Q4).
- **FR-23**: 전역 PG `statement_timeout = 10s` — `radivault_buyer_ro` 역할에 `ALTER ROLE radivault_buyer_ro SET statement_timeout = '10s';`. FastAPI 레벨 `asyncio.wait_for(handler, timeout=15s)`. 타임아웃 → `504 ERR_QUERY_TIMEOUT`(신규 코드).

### 4.4 Keyset cursor pagination

- **FR-24**: `POST /v1/search/studies` 응답은 키셋 커서 페이지네이션 사용. 정렬 기본 `(study_date_shifted DESC, study_pk DESC)`. 대안 `ingested_desc`(`(ingested_at DESC, study_pk DESC)`) 는 `sort=ingested_desc` 로 선택 가능.
- **FR-25**: Cursor token 구조 —
  ```jsonc
  {
    "v": 1,
    "d": "2026-04-18",           // study_date_shifted ISO yyyy-mm-dd 또는 ingested_at timestamp
    "p": 12345,                  // study_pk
    "s": "YbM3z7K9QaP1",         // sha256(filter_json_canonical || sort_key)[:12] base64url
    "k": "date_desc"             // sort_key
  }
  ```
  전체 JSON 을 `base64url(no padding)` 인코딩하여 문자열로 직렬화.
- **FR-26**: Cursor 디코드 시 `s` 필드가 **현재 요청의 filter_sha256 기반 예측값과 불일치** → `400 ERR_CURSOR_FILTER_CHANGED`. 다시 1페이지부터 시작해야 함. hint: `"filter parameters changed since cursor was issued; restart from page 1"`.
- **FR-27**: Cursor `v` 필드가 현재 서버의 지원 버전(1) 이 아니면 `400 ERR_CURSOR_VERSION`(신규). v0.1 은 v=1 고정.
- **FR-28**: SQL — `WHERE (study_date_shifted, study_pk) < (:d, :p)` row-value 비교. `ORDER BY study_date_shifted DESC, study_pk DESC LIMIT :limit + 1` — `+1` 로 `has_next` 판별.
- **FR-29**: 역방향 페이징(previous page) 미지원. 클라이언트는 이전 cursor 를 자체 보관해야 함.
- **FR-30**: `next_cursor` 는 `has_next == true` 인 경우에만 응답 필드로 포함. 끝이면 `null`.

### 4.5 Faceted aggregation

- **FR-31**: 화이트리스트 facet 필드 6개 — `modality`, `body_part`, `sex`, `age_bucket`, `manufacturer`, `year`(= `EXTRACT(YEAR FROM study_date_shifted)`). 다른 필드 facet 요청 시 400 무시(요청에 포함될 수 없음).
- **FR-32**: `include_facets` 기본 **true**. `false` 시 facet 쿼리 전체 skip(레이턴시 절감).
- **FR-33**: 각 facet 은 **별도 GROUP BY 쿼리**로 계산. v0.1 은 6개 parallel async task 로 실행(PG connection pool size ≥ 10 가정). 모든 facet 이 개별적으로 `statement_timeout=10s` 한도 안에 완료되어야 함.
- **FR-34**: 각 facet 값 당 `{"value": <str>, "count": <int>}` 객체 배열 반환. 값이 NULL 인 경우 `"value": null` 로 그대로. 상한 값 갯수는 **facet 당 50개 상위 항목**(count DESC). 초과 분은 `{"value": "__other__", "count": N}` 로 요약.
- **FR-35**: `total_count` — 현재 필터에 매칭되는 총 `study_pk` 수 (exact). 10M 이하 쿼리만 허용되므로(FR-21) 1회 COUNT(*) 허용. PG `statement_timeout` 로 bounded.
- **FR-36**: `total_hint` — `total_count` 계산을 skip 해야 할 경우(§4.3 FR-22 triggered) planner 기반 estimate 를 정수로 반환. client 는 `total_count_exact: false` 플래그로 분기.

### 4.6 Result projection (Cohort summary)

- **FR-37**: `POST /v1/search/studies` 응답 `items` 배열은 **스터디 메타데이터 요약**만 포함. 다운로드 URL · 파일 키 · 원본 UID · 환자 이름 어떤 것도 포함하지 않는다.
- **FR-38**: 각 `item` 필드(§6.4):
  - `pseudo_study_uid` (stable string, 구매자는 이후 구매 확정 시 이 UID 로 주문을 식별).
  - `modality`, `body_part`, `age_bucket`, `sex`, `study_date_shifted`, `manufacturer`, `model_name`.
  - `n_instances`, `n_series`, `total_bytes` — 구매 의사결정용 크기 지표.
  - `hospital_opaque_id` — `sha256(hospital_pk || buyer_salt)[:16]` (구매자마다 다른 opaque ID; 교차 비교 방지).
  - `ingested_at` — UTC timestamp.
- **FR-39**: `GET /v1/search/studies/{pseudo_study_uid}` 는 FR-38 필드에 더해 `series` 배열(series 별 `modality`, `n_instances`, `pseudo_series_uid`) 을 포함. instance 레벨은 미노출(다운로드 흐름에서만).
- **FR-40**: 검색 결과의 sample 갯수는 `limit` 로 제한되지만, **응답 크기 상한 1 MB**(gzip 전). 초과 시 자동 truncate + `response_truncated: true` 플래그.

### 4.7 Hospitals endpoint

- **FR-41**: `GET /v1/search/hospitals` — 현재 참여 병원 목록을 **불투명 ID 집계**로 반환. 실제 병원명은 기본 비공개. 구매자는 tier = `paid` + `scope_json.include_hospital_names=true` 시에만 `name_public` 필드 접근 가능(`403 ERR_SCOPE_FORBIDDEN`(신규)로 제어).
- **FR-42**: 응답 shape:
  ```jsonc
  {
    "items": [
      {
        "hospital_opaque_id": "abc123...",
        "study_count":         218344,
        "first_study_date":    "2021-03-01",
        "last_study_date":     "2026-04-20",
        "modalities":          ["CT","MR","CR"]
      }
    ],
    "total_hospitals": 7
  }
  ```
- **FR-43**: 병원별 study count 는 5분 Redis 캐시. Cache miss 시 `SELECT hospital_pk, COUNT(*) FROM study GROUP BY 1` — `statement_timeout` 안에 완료.

### 4.8 Facets endpoint (filter 자동완성)

- **FR-44**: `GET /v1/search/facets` — 전체 코퍼스 기준 화이트리스트 6필드 각각의 가능한 값과 카운트. 응답 캐시 **15분**(facet 쿼리는 코호트 필터가 없어 상대적으로 stable). 빌드 시점에 warm-cache 가능(`search-admin facet warm`).
- **FR-45**: 응답 shape:
  ```jsonc
  {
    "modality":     [{"value":"CT","count":421338},{"value":"MR","count":188445}, ...],
    "body_part":    [...],
    "sex":          [{"value":"M","count":333210},{"value":"F","count":271083},{"value":null,"count":412}],
    "age_bucket":   [...],
    "manufacturer": [...],
    "year":         [{"value":"2024","count":210332}, ...],
    "computed_at":  "2026-04-22T10:00:00Z"
  }
  ```

### 4.9 Observability

- **FR-46**: Prometheus 메트릭(prefix `radivault_index_`):
  - `radivault_index_search_duration_seconds`(histogram, labels `tier, endpoint, status, has_facets`).
  - `radivault_index_facet_duration_seconds`(histogram, label `facet_field`).
  - `radivault_index_result_size`(histogram, label `tier`).
  - `radivault_index_empty_result_total`(counter, label `buyer_id_hash`).
  - `radivault_index_cache_hit_total`(counter, label `cache_layer` ∈ {`auth`, `facets`, `hospitals`, `cost_estimate`}).
  - `radivault_index_rate_limited_total`(counter, labels `tier, reason` ∈ {`rpm`, `daily`, `concurrency`, `ip`}).
  - `radivault_index_query_too_broad_total`(counter).
  - `radivault_index_cursor_filter_changed_total`(counter).
  - `radivault_index_auth_failures_total`(counter, label `reason`).
- **FR-47**: 구조화 JSON 로그 필수 필드: `ts, level, logger, msg, trace_id, request_id, buyer_id_hash, tier, endpoint, status, duration_ms, result_count, cache_hit, cursor_presence, filter_sha256, filter_fields`. `filter_fields` 는 **키 이름 list 만**(값 없음). `filter_raw`, `cursor_raw`, `api_key`, `api_key_kid` 등은 어떤 레코드에도 기록 금지. 로그 sanitizer 가 금지 필드 감지 시 즉시 `ERR_LOG_PHI_DETECTED` 내부 경보.
- **FR-48**: OpenTelemetry span 이름 — `search.request`, `search.auth`, `search.cost_estimate`, `search.query`, `search.facet.<field>`, `search.audit.insert`. exporter 구성은 central-ingest 와 동일(`OTEL_EXPORTER_OTLP_ENDPOINT` 환경변수).
- **FR-49**: 요청마다 `request_id` = ULID 서버 생성, 응답 헤더 `X-Request-Id`. 클라이언트가 `X-Request-Id` 헤더로 제공 시 그대로 전파.
- **FR-50**: 알람 기본 임계:
  - p95 `radivault_index_search_duration_seconds{endpoint="/v1/search/studies"}` > 2s (5분 평균) → warn.
  - `radivault_index_empty_result_total / radivault_index_search_duration_seconds_count` per buyer > 40% (15분 창) → warn (필터 UX 또는 이상 패턴 탐지).
  - `radivault_index_query_too_broad_total` rate > 0.5/s → warn.
  - Redis·PG unavailable → crit.

### 4.10 Buyer usage audit

- **FR-51**: 모든 성공 및 실패 요청(4xx·5xx 포함)은 `search_audit`(§6.3) 테이블에 1 row 기록. 비동기(background task) 로 삽입 — 검색 응답 반환 후 별도 커넥션에서 실행하여 latency 영향 없도록.
- **FR-52**: `search_audit` 필드 — `audit_pk, buyer_pk, kid8, endpoint, filter_sha256, filter_json_sha256, result_count, cache_hit, status_code, error_code, latency_ms, request_id, cursor_presence, created_at`. **raw filter body 금지**.
- **FR-53**: `filter_sha256` = `sha256(canonical_json(filter) || GLOBAL_SALT)` — 리서치 §4.6.2. GLOBAL_SALT 는 전역 고정(매출 funnel 분석을 위해 buyer 간 동일 sha 비교 가능). per-buyer salt 로 할 지는 §11 Q3 Kyle 결정.
- **FR-54**: `search_audit` 테이블도 append-only. `radivault_buyer_ro` 역할은 `INSERT` 만 허용, `UPDATE/DELETE` 금지(§6.2). Admin CLI 는 `search_admin` 별도 역할로 SELECT.
- **FR-55**: 월 파티셔닝(`PARTITION BY RANGE (created_at)`), pg_partman 자동 생성 스크립트는 central-ingest 설정을 재사용.

### 4.11 Admin CLI — `search-admin`

- **FR-56**: CLI 바이너리 `search-admin` — central-ingest 의 `ingest-admin` 과 같은 코드베이스에서 `console_scripts` 진입점으로 제공(분리 바이너리). `--json`, `--dry-run`, `--no-color`, `NO_COLOR=1` 옵션 지원(central-ingest 와 일관).
- **FR-57**: 명령 트리:
  ```
  search-admin
  ├── buyer
  │   ├── create        --name NAME --contact-email EMAIL --tier {preview|paid} [--note STR]
  │   ├── show          --buyer-id BID [--json]
  │   └── list          [--active-only] [--json]
  ├── key
  │   ├── issue         --buyer-id BID [--tier TIER] [--expires-days N] [--scope-json JSON] [--dry-run]
  │   ├── revoke        --kid KID8 [--reason STR]
  │   └── list          --buyer-id BID [--include-revoked] [--json]
  ├── stats
  │   ├── query-count   --buyer-id BID --since DATETIME --until DATETIME [--json]
  │   └── top-filters   --limit N --since DATETIME [--json]    # filter_sha256 빈도 상위
  ├── facet
  │   └── warm          # /v1/search/facets 캐시 사전 워밍
  └── migrate
      ├── current       # alembic current
      └── up            # alembic upgrade head (search 관련 revision만 필터링)
  ```
- **FR-58**: `key issue` 는 plaintext key 를 **stdout 1회만** 출력(argon2 해시만 DB 저장). 운영자는 안전 채널로 구매자에게 전달. `--dry-run` 시 DB 변경 없이 "would-issue" 표시.
- **FR-59**: 종료 코드(BSD sysexits) — `0` 성공, `64` usage 오류, `69` 미존재(예: buyer_id not found → `ERR_ADMIN_BUYER_NOT_FOUND`), `70` 내부 오류.

### 4.12 Packaging · Ops

- **FR-60**: Docker 이미지 — multi-stage(`python:3.11-bookworm` builder → `python:3.11-slim-bookworm` runtime), non-root `USER 10001:10001`. `Dockerfile.search` 을 신규 생성하거나 `Dockerfile.central` 에 `--build-arg SERVICE=search` 분기. v0.1 권고: **단일 Dockerfile + build-arg** — 이미지 두 개를 유지하지 말고 동일 파이썬 패키지(`radivault`)에서 `radivault_search.asgi:app` 모듈만 다르게 엔트리포인트로 실행(§9.2).
- **FR-61**: Gunicorn + uvicorn workers. `radivault_search` 는 검색 워크로드 특성상 IO-bound → workers = `2 * vCPU + 1`, threads 1. `timeout 30` (검색 쿼리 15s + facet parallel 여유).
- **FR-62**: `HEALTHCHECK --interval=30s --timeout=5s --start-period=15s CMD curl -fsS http://localhost:8001/healthz`. Search 서비스 기본 port 는 8001(central-ingest 8000 과 충돌 방지).
- **FR-63**: `docker-compose-search.yml` — `search` 서비스 + **기존 postgres · redis 컨테이너 재사용**(외부 network `radivault_net`). MinIO 는 검색 서비스가 S3 접근하지 않으므로 불필요. `docker-compose.dev.yml` 과 함께 up 하는 패턴 문서화.
- **FR-64**: SIGTERM 시 진행 중 검색 쿼리는 **15초 graceful drain**(PG cancel 대신 응답 반환 대기). K8s `terminationGracePeriodSeconds ≥ 30s`.
- **FR-65**: OpenAPI 3.1 스펙 자동 생성(`GET /openapi.json`, `GET /docs` Swagger UI) 인증 없이 접근 가능. 인증 필요 엔드포인트는 스펙에만 문서화되고 호출은 401 반환.
- **FR-66**: 배포 산출물 — OpenAPI JSON 1건, `curl` 샘플 5종 + Postman 컬렉션 JSON 1건을 `docs/samples/search/` 에 동봉(Admin 문서; 본 dev-spec 의 §13 Annex 와 동일).

### 4.13 Migrations

- **FR-67**: Alembic revision 1개 신규(`alembic/versions/XXXXXX_metadata_index_v0_1.py`). 변경 내용:
  1. `CREATE TABLE buyer` (§6.2).
  2. `CREATE TABLE buyer_api_key` (§6.2).
  3. `CREATE TABLE search_audit` — `PARTITION BY RANGE (created_at)` + 당월±2개월 파티션 preseed.
  4. `CREATE ROLE radivault_buyer_ro` + `GRANT SELECT ON study, series, instance, patient_pseudo, hospital TO radivault_buyer_ro;` + `GRANT INSERT ON search_audit TO radivault_buyer_ro;` + `ALTER ROLE radivault_buyer_ro SET statement_timeout = '10s';`.
  5. `CREATE ROLE search_admin` + `GRANT SELECT, INSERT, UPDATE ON buyer, buyer_api_key TO search_admin;` + `GRANT SELECT ON search_audit TO search_admin;`.
  6. 3개 복합 인덱스 추가(§6.3) on `study`.
- **FR-68**: Alembic migration 은 **central-ingest 동일 repo**(`src/radivault_central/db/migrations/`) 의 새 revision 으로 관리. separate `alembic-search/` 를 두지 않음 — 테이블 간 FK (`buyer_api_key.buyer_pk → buyer.buyer_pk`) 는 같은 DB 이며, 두 서비스가 동일 스키마 바라봄. **별도 alembic repo 는 runtime 에 schema drift 위험을 도입하므로 거부**. (이 결정이 맞지 않다고 판명되면 §9.2 주석대로 역전 가능하도록 README 를 준비.)
- **FR-69**: `alembic upgrade head` 이후 search service 기동 시 `readyz` 는 `alembic current == head` 확인한다(central-ingest FR-74 와 동일 패턴).
- **FR-70**: 본 revision 은 central-ingest 의 기존 study 인덱스(`idx_study_modality_bodypart`, `idx_study_date` 등)를 **삭제하거나 이름 변경하지 않는다**. 모든 변경은 순수 추가만.

### 4.14 Mock fixtures · Test harness

- **FR-71**: pytest 통합 테스트 — central-ingest 의 `tests/integration` conftest 재사용. 같은 PG 컨테이너에서 ingest 가 넣은 study row 를 search API 가 쿼리하는 end-to-end 검증 가능해야 함.
- **FR-72**: 합성 study factory(`tests/factories/study_factory.py`) — 임의 modality/body_part/age_bucket 조합으로 N rows 삽입 후 facet count 검증. N 기본 1,000, 스트레스 테스트 N ≥ 100,000 옵션(`RADIVAULT_SEARCH_LOAD=1`).
- **FR-73**: Mock buyer key 생성 — `tests/fixtures/buyer_keys.py` 에 testcontainers 레벨에서 임시 key 발급(`search-admin key issue --dry-run=false` 호출 시뮬레이션). 테스트 완료 후 cleanup.
- **FR-74**: `@pytest.mark.integration` 로 gated. `RADIVAULT_SEARCH_INTEGRATION=1` 환경변수 없으면 skip.

### 4.15 Hospital opt-out (v0.1 기본값)

- **FR-75**: v0.1 은 **flat access** — 인증된 모든 buyer 가 모든 hospital 데이터 검색 가능. `exclude_hospitals` 필터는 application-level 로 `buyer_api_key.scope_json.exclude_hospitals=[hospital_pk,...]` 를 쿼리에 `AND study.hospital_pk <> ALL(:exclude)` 로 자동 삽입. 스키마는 준비(`scope_json.exclude_hospitals`) 하되, v0.1 UI 노출 없음.
- **FR-76**: `exclude_hospitals` 파싱은 **신뢰하는 JSON 필드만** — 구매자는 request body 에 해당 필드를 직접 설정할 수 없다. 키 발급 시 admin CLI 가 명시적으로 설정한 값만 반영.
- **FR-77**: PG RLS 기반 집행은 v0.2 백로그(§11 Q1). v0.1 은 application-layer만.

---

## 5. 비기능 요구사항

| 항목 | 요구 |
|------|------|
| **성능** | 1,000,000 study rows 기준: `POST /v1/search/studies` 단순 필터(modality + date range) **p95 < 1s**, `include_facets=true` 시 **p95 < 1.8s**. `GET /v1/search/facets`(15m 캐시 hit) p95 < 80ms. `GET /v1/search/hospitals`(5m 캐시 hit) p95 < 100ms. `GET /healthz` p95 < 30ms. `/readyz` p95 < 200ms. Cost estimator p95 < 400ms. |
| **처리량** | 50 concurrent queries across all buyers supported(pool_size=30, max_overflow=20). Redis 3K cmd/s sustained. PG `radivault_buyer_ro` statement_timeout=10s. |
| **가용성** | v0.1 best-effort. v0.2 SLA 99.9% (paid tier 만). 배포 중 롤링 업데이트 무중단. |
| **보안** | TLS 1.3 only (전방 nginx/ALB 종단). API key argon2id 해시. PG 계정 분리: `radivault_buyer_ro`(SELECT + search_audit INSERT only), `search_admin`(buyer, buyer_api_key DML). PHI 절대 금지. 컨테이너 non-root UID 10001. 이미지 trivy HIGH=0. |
| **로깅·감사** | 모든 요청 `search_audit` append-only 기록 (PHI·raw filter 금지). 로그 5년 보존(central-ingest 와 동일 버킷). empty-result > 40% alert. `filter_raw`/`api_key` 로그 샘플링 시 pipeline 즉시 차단. |
| **확장성** | Search 서비스 horizontal (stateless) — PG read replica v0.2 추가 가능. PG 단일 노드 1M rows 까지 본 인덱스 셋으로 대응, 10M+ 는 month-partition pruning + read replica. |
| **레이트·쿼터 기본값 (tier)** | preview: 20 req/min, 100 req/day, max_limit_per_page=100, include_facets=true. paid: 600 req/min, 10,000 req/day, max_limit_per_page=200, include_facets=true, concurrency=20. 계약 override 는 `buyer_api_key.scope_json` 만. |
| **관측성** | p50/p95/p99 latency, empty-result-rate 알람, cache hit %, cost-estimate 차단율. 대시보드 대시보드 central-ingest 와 분리. |
| **국제화** | 로그·에러 메시지 `message_ko` + `message_en` 이중 언어(design-spec-central-ingest §2 재사용). 기본 응답 본문 영어. |
| **호환성** | Python 3.11, PostgreSQL 15/16 + pg_partman, Redis 7+, Docker Engine 24+, Compose v2.20+. Ubuntu 22.04 LTS x86_64(프로덕션). |
| **계약 호환** | central-ingest write 경로에 영향 없음 — 본 서비스는 READ-only. Alembic 새 revision 은 기존 테이블 구조·인덱스를 **변경하지 않는다**. |
| **규제 적합성** | 개보법 제28조의8 전제. ingest 단계 익명 게이트 이후 데이터만 참조. 응답 바디·로그 어디에도 원본 UID·환자 식별자 없음. HIPAA de-identification 대응은 ingest 책임. 본 서비스 신규 법적 리스크 없음. |

---

## 6. 데이터 모델

### 6.1 ER 다이어그램

```mermaid
erDiagram
    hospital ||--o{ study : "owns"
    study ||--o{ series : "contains"
    series ||--o{ instance : "contains"
    patient_pseudo ||--o{ study : "participates"
    buyer ||--o{ buyer_api_key : "issues"
    buyer ||--o{ search_audit : "triggers"
    buyer_api_key ||--o{ search_audit : "used-for"
```

- `hospital`, `study`, `series`, `instance`, `patient_pseudo` 는 **central-ingest §6 상속**(read-only).
- `buyer`, `buyer_api_key`, `search_audit` 는 본 dev-spec 이 신규 추가하는 테이블.

### 6.2 PostgreSQL 스키마 — Buyer · API Key · Audit

```sql
CREATE TABLE buyer (
    buyer_pk        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    buyer_id        TEXT NOT NULL UNIQUE,             -- 외부 식별자 (e.g., 'buy_acme_001')
    name            TEXT NOT NULL,
    contact_email   TEXT NOT NULL,
    tier            TEXT NOT NULL DEFAULT 'preview',  -- 'preview' | 'paid'
    scope_json      JSONB NOT NULL DEFAULT '{}'::JSONB,
    note            TEXT,
    enrolled_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    active          BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX idx_buyer_active ON buyer(active) WHERE active;

CREATE TABLE buyer_api_key (
    key_pk          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    buyer_pk        BIGINT NOT NULL REFERENCES buyer(buyer_pk),
    kid             TEXT NOT NULL,                    -- 8 char prefix (indexed for O(log N) lookup)
    token_hash      TEXT NOT NULL,                    -- argon2id(secret)
    tier            TEXT NOT NULL,                    -- denormalized from buyer for fast lookup
    rate_limit_qps  INTEGER,                          -- optional override
    rate_limit_daily INTEGER,
    scope_json      JSONB NOT NULL DEFAULT '{}'::JSONB,
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ,
    last_used_at    TIMESTAMPTZ,
    note            TEXT,
    UNIQUE (kid)
);
CREATE INDEX idx_buyer_api_key_buyer_active
  ON buyer_api_key(buyer_pk)
  WHERE revoked_at IS NULL;

CREATE TABLE search_audit (
    audit_pk         BIGINT GENERATED ALWAYS AS IDENTITY,
    buyer_pk         BIGINT NOT NULL REFERENCES buyer(buyer_pk),
    kid              TEXT NOT NULL,
    endpoint         TEXT NOT NULL,                   -- e.g., '/v1/search/studies'
    filter_sha256    CHAR(64),
    filter_json_sha256 CHAR(64),                      -- request body canonical sha256
    result_count     BIGINT,
    cache_hit        BOOLEAN NOT NULL DEFAULT FALSE,
    status_code      INTEGER NOT NULL,
    error_code       TEXT,
    latency_ms       INTEGER NOT NULL,
    request_id       TEXT NOT NULL,
    cursor_presence  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (audit_pk, created_at)
) PARTITION BY RANGE (created_at);

-- 월 파티션은 pg_partman 자동.
CREATE INDEX idx_search_audit_buyer_time
  ON search_audit (buyer_pk, created_at DESC);
CREATE INDEX idx_search_audit_filter_sha
  ON search_audit (filter_sha256);
```

**GRANT 정책** (Alembic 적용):

```sql
-- central-ingest 의 central_migrator 가 마이그레이션 실행
CREATE ROLE radivault_buyer_ro NOINHERIT;
ALTER ROLE radivault_buyer_ro SET statement_timeout = '10s';
ALTER ROLE radivault_buyer_ro SET lock_timeout = '2s';
ALTER ROLE radivault_buyer_ro SET idle_in_transaction_session_timeout = '5s';

GRANT CONNECT ON DATABASE radivault_central TO radivault_buyer_ro;
GRANT USAGE ON SCHEMA public TO radivault_buyer_ro;
GRANT SELECT ON study, series, instance, patient_pseudo, hospital
  TO radivault_buyer_ro;
GRANT SELECT ON buyer, buyer_api_key
  TO radivault_buyer_ro;
GRANT INSERT ON search_audit TO radivault_buyer_ro;
-- UPDATE/DELETE 미부여

CREATE ROLE search_admin NOINHERIT;
GRANT SELECT, INSERT, UPDATE ON buyer, buyer_api_key TO search_admin;
GRANT SELECT ON search_audit TO search_admin;
GRANT USAGE ON SCHEMA public TO search_admin;
```

### 6.3 Study 신규 인덱스 (keyset pagination + facet)

PostgreSQL 파티션 `study` 에 추가 3개 인덱스:

```sql
-- 인덱스 1: 기본 keyset cursor용 — 필수 (FR-24, FR-28)
CREATE INDEX idx_study_date_keyset
  ON study (study_date_shifted DESC, study_pk DESC);
-- 근거: tuple (study_date_shifted, study_pk) < (cursor_d, cursor_p) index seek.
-- 필터 없이 최신순 페이징에 가장 빈번. 파티션 별 로컬로 자동 생성됨.

-- 인덱스 2: modality + bodypart 필터 + 키셋 정렬 커버링
CREATE INDEX idx_study_filter_keyset
  ON study (modality, body_part, study_date_shifted DESC, study_pk DESC);
-- 근거: 가장 빈번한 buyer 필터 조합(modality IN (...) + body_part IN (...)) 과
-- 정렬 키를 하나의 B-tree 에 합쳐 커버링 seek. facet GROUP BY (modality) 에도 leftmost prefix 활용.

-- 인덱스 3: ingested_desc alternative sort 용
CREATE INDEX idx_study_ingested_keyset
  ON study (ingested_at DESC, study_pk DESC);
-- 근거: sort=ingested_desc 요청(최신 ingest 순) 의 keyset.
-- buyer 가 "어제 들어온 데이터만" 탐색할 때 사용. DESC + tiebreaker 조합.
```

**추가 인덱스 정당화**: 리서치 §4.2.2 + §4.3.1 기반. 월 파티션(central-ingest FR-53) 의 로컬 인덱스로 자동 복제. write-amp 영향 — 파일럿 (<1M rows) 규모에서 허용범위. write throughput 이 ingest 성능에 충격을 주면 v0.1.1 에서 인덱스 2를 제거하고 별도 column-store(ClickHouse 등) 검토(§11 Q6).

### 6.4 Pydantic 스키마 — 요청·응답

```python
# src/radivault_search/api/schemas.py

class StudyDateRange(BaseModel):
    from_: date = Field(..., alias="from")
    to: date

class SearchRequest(BaseModel):
    modality:       list[str] | None = Field(None, max_length=10)        # FR-17
    body_part:      list[str] | None = Field(None, max_length=10)
    age_bucket:     list[str] | None = Field(None, max_length=10)         # e.g., ["30-40","40-50"]
    sex:            list[Literal["M","F","O"]] | None = None
    study_date_shifted: StudyDateRange | None = None                       # FR-18 both bounds required
    manufacturer:   list[str] | None = Field(None, max_length=10)
    min_hospitals:  int | None = Field(None, ge=1, le=20)                  # FR-20
    sort:           Literal["date_desc","ingested_desc"] = "date_desc"
    limit:          int = Field(50, ge=1, le=200)                          # FR-19
    cursor:         str | None = None
    include_facets: bool = True                                            # FR-32

class StudyItem(BaseModel):
    pseudo_study_uid:   str
    modality:           str | None
    body_part:          str | None
    age_bucket:         str | None
    sex:                str | None
    study_date_shifted: date | None
    manufacturer:       str | None
    model_name:         str | None
    n_instances:        int
    n_series:           int
    total_bytes:        int
    hospital_opaque_id: str
    ingested_at:        datetime

class FacetValue(BaseModel):
    value: str | None
    count: int

class SearchResponse(BaseModel):
    items:             list[StudyItem]
    facets:            dict[str, list[FacetValue]] | None                 # None if include_facets=false or suppressed
    total_count:       int | None                                          # exact when FR-35 path
    total_hint:        int | None                                          # planner-estimate when FR-36
    total_count_exact: bool
    next_cursor:       str | None
    has_next:          bool
    page_size:         int
    response_truncated: bool                                               # FR-40

class SearchStudyDetail(StudyItem):
    series: list[SeriesSummary]

class SeriesSummary(BaseModel):
    pseudo_series_uid: str
    modality:          str | None
    n_instances:       int
```

### 6.5 Config YAML 스키마 (search 서비스용)

```yaml
# /etc/radivault-search/search.yml
version: 1

app:
  env: "prod"
  api_contract_version: "1"
  workers: 5
  port: 8001

db:
  dsn: "${env:SEARCH_BUYER_RO_DSN}"            # postgres://radivault_buyer_ro:...@pg:5432/radivault_central
  admin_dsn: "${env:SEARCH_ADMIN_DSN}"          # for search-admin CLI
  pool_size: 30
  max_overflow: 20

redis:
  url: "${env:REDIS_URL}"
  auth_cache_ttl_seconds: 60
  cost_estimate_ttl_seconds: 300
  facets_cache_ttl_seconds: 900
  hospitals_cache_ttl_seconds: 300

auth:
  hash_algorithm: "argon2id"
  argon2:
    time_cost: 3
    memory_cost_kib: 65536
    parallelism: 2
  global_filter_salt: "${env:FILTER_HASH_GLOBAL_SALT}"    # FR-53
  api_key_prefix_live: "rv_live_"
  api_key_prefix_test: "rv_test_"

rate_limit:
  tier_preview:
    rpm: 20
    daily: 100
    concurrency: 3
    max_limit_per_page: 100
  tier_paid:
    rpm: 600
    daily: 10000
    concurrency: 20
    max_limit_per_page: 200
  ip_global_per_min: 300

cost:
  max_estimated_rows: 10000000                 # FR-21 10M
  facet_auto_suppress_rows: 2000000            # FR-22
  cost_estimate_timeout_ms: 500

timeouts:
  fastapi_request_timeout_seconds: 15
  pg_statement_timeout: "10s"
  graceful_drain_seconds: 15

observability:
  log_level: "INFO"
  json_logs: true
  otlp_endpoint: "${env:OTEL_EXPORTER_OTLP_ENDPOINT}"
  metrics_path: "/metrics"
  sentry_dsn: "${env:SENTRY_DSN}"
  log_sanitizer_strict: true                   # FR-47 금지 필드 감지 시 차단
```

### 6.6 금지 필드 (PHI · IP 오염 방지)

로그·감사 테이블·Prometheus 라벨·응답 바디 어디에서도 금지:

- 원본 `StudyInstanceUID`, `SeriesInstanceUID`, `SOPInstanceUID`.
- 환자 이름·생년월일·주소·주민등록번호 및 해당 해시.
- 병원 내부 호스트명, 내부 IP.
- **Buyer 원본 filter body**(keys + values) — `filter_fields` list 만 허용.
- **API key 평문 · `kid` 외 나머지 secret**.
- **Raw cursor token** — cursor presence 여부(boolean) 만.

허용: 가명 UID, `hospital_opaque_id`(per-buyer salted sha256), `buyer_id_hash`, `filter_sha256`, `request_id`, HTTP 상태.

### 6.7 법적·보안 고려 (6.x Mandatory)

- **§6.7.1 PHI 무포함 보증**: Central ingest 의 anonymization gate(FR-9 / FR-39) 를 통과한 데이터만 참조. 본 서비스는 어떤 원본 UID·환자 식별자도 DB 에서 접근하지 않는다(스키마상 컬럼이 존재하지 않음).
- **§6.7.2 Cursor token 무해화**: cursor JSON 에는 `study_date_shifted`(시프트 날짜)·`study_pk`(가상 PK)·sort_key·`s` hash 만 포함. 원본 날짜·환자 식별자 어떤 것도 노출되지 않는다. Cursor 는 공개되어도 다른 buyer 에게 의미가 없다(해당 buyer 의 filter_sha256 을 알아야 매칭).
- **§6.7.3 에러 메시지 스키마 비노출**: 에러 응답의 `detail` 필드는 필드 이름 수준(예: `"filter_sha256 mismatch"`)만 노출하고 column 이름·테이블 이름·SQL 조각을 포함하지 않는다. Pydantic 오류는 `{"error":"ERR_REQUEST_SCHEMA","detail":"field 'modality': too many items"}` 형태로 표준화.
- **§6.7.4 감사 로그 raw filter 금지**: `search_audit.filter_sha256` / `filter_json_sha256` 만 저장. raw filter body 는 Redis·PG·stdout 어디에도 저장/기록되지 않는다. 운영 SRE 에게도 raw body 접근 수단 없음.
- **§6.7.5 Key rotation**: 구매자는 `key issue` 로 새 키를 발급받은 뒤 구 키를 `key revoke` 로 회수. 두 키 동시 활성 허용(FR-8) — zero-downtime 회전. API key 만료 기본 180일(`--expires-days 180`), override 허용.
- **§6.7.6 OpenAPI doc 노출 범위**: `/openapi.json` 은 스키마만 공개, 실제 예시 `api_key`·URL 은 sample 문서(`docs/samples/search/`) 에만. 스펙이 구매자 필드 shape 를 유출하지만 이는 의도된 개방(onboarding) 이다.
- **§6.7.7 Hospital opt-out 법적 근거**: MSA/DPA 에 "RadiVault may at hospital's written request exclude its data from specific buyers"(리서치 §5.6) 조항 선제 삽입(법무 결재 필요 §11 Q2). v0.1 application-layer 가 충분한지 v0.1.1 RLS 로 이행할지 결정 보류.
- **§6.7.8 NLP 필드 부재 선언**: 본 v0.1 API 는 진단명·RadLex·ICD-10 필드를 검색·응답 어디에도 노출하지 않는다. 구매자가 요청 본문에 해당 필드를 보내더라도 pydantic 단계에서 무시. NLP 라벨은 별도 dev-spec 에서 합류.

---

## 7. API 계약

모든 4xx/5xx 응답 바디는 design-spec-central-ingest §2.2 envelope 를 따른다:

```jsonc
{
  "error":       "ERR_QUERY_TOO_BROAD",
  "detail":      "estimated rows 12,833,091 exceeds limit 10,000,000",
  "message_ko":  "쿼리가 너무 광범위합니다 (예상 1,280만 건). 모달리티 또는 날짜 범위를 좁혀주세요.",
  "message_en":  "Query too broad (estimated 12.8M rows). Narrow modality or date range.",
  "request_id":  "01HXX...",
  "doc_url":     "https://docs.radivault.io/search/errors/ERR_QUERY_TOO_BROAD",
  "hint":        "try modality=['CT'] AND study_date_shifted.from=2024-01-01",
  "retry_after": null
}
```

### 7.1 `POST /v1/search/studies`

```
Request:
  POST /v1/search/studies HTTP/1.1
  Host: search.radivault.io
  Authorization: Bearer rv_live_abcd1234_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  Content-Type: application/json
  X-Request-Id: <optional>

  {
    "modality":      ["CT","MR"],
    "body_part":     ["CHEST"],
    "age_bucket":    ["50-60","60-70"],
    "sex":           ["M","F"],
    "study_date_shifted": {"from":"2024-01-01","to":"2026-04-20"},
    "manufacturer":  ["SIEMENS","GE"],
    "min_hospitals": 3,
    "sort":          "date_desc",
    "limit":         50,
    "cursor":        null,
    "include_facets": true
  }

Response 200 OK:
  {
    "items": [
      {
        "pseudo_study_uid":    "2.25.abcd...",
        "modality":            "CT",
        "body_part":           "CHEST",
        "age_bucket":          "60-70",
        "sex":                 "M",
        "study_date_shifted":  "2026-04-20",
        "manufacturer":        "SIEMENS",
        "model_name":          "SOMATOM Force",
        "n_instances":         512,
        "n_series":            4,
        "total_bytes":         412553221,
        "hospital_opaque_id":  "c3d4e5f6a7b8c9d0",
        "ingested_at":         "2026-04-21T03:20:51Z"
      },
      "...(up to 50 items)..."
    ],
    "facets": {
      "modality":     [{"value":"CT","count":42318},{"value":"MR","count":18244}],
      "body_part":    [{"value":"CHEST","count":31055}],
      "sex":          [{"value":"M","count":33210},{"value":"F","count":27108}],
      "age_bucket":   [{"value":"60-70","count":21099}],
      "manufacturer": [{"value":"SIEMENS","count":14222}],
      "year":         [{"value":"2024","count":21033},{"value":"2025","count":18998}]
    },
    "total_count":        60562,
    "total_hint":         null,
    "total_count_exact":  true,
    "next_cursor":        "eyJ2IjoxLCJkIjoiMjAyNi0wNC0xOCIsInAiOjEyMzQ1LCJzIjoiWWJNM3o3SzlRYVAxIiwiayI6ImRhdGVfZGVzYyJ9",
    "has_next":           true,
    "page_size":          50,
    "response_truncated": false
  }

Errors:
  400 ERR_REQUEST_SCHEMA          pydantic validation failed
  400 ERR_FILTER_TOO_MANY         >10 items in IN filter
  400 ERR_PAGE_LIMIT              limit > max_limit_per_page
  400 ERR_CURSOR_FILTER_CHANGED   cursor sha mismatch with current filter
  400 ERR_CURSOR_VERSION          cursor version unsupported
  401 ERR_AUTH_MISSING            Authorization missing/invalid
  401 ERR_AUTH_EXPIRED            key revoked/expired
  401 ERR_AUTH_FORMAT             key prefix/length wrong
  422 ERR_QUERY_TOO_BROAD         estimated rows > 10M
  429 ERR_RATE_LIMITED            per-min rate exceeded
  429 ERR_BUYER_QUOTA             daily quota exceeded
  429 ERR_BUYER_CONCURRENCY       per-buyer concurrency cap
  503 ERR_IDEMP_UNAVAILABLE       Redis unavailable (rate-limit path)
  503 ERR_DB_UNAVAILABLE          Postgres unavailable
  504 ERR_QUERY_TIMEOUT           statement_timeout triggered
  500 ERR_INTERNAL                unexpected
```

### 7.2 `GET /v1/search/studies/{pseudo_study_uid}`

```
Request:
  GET /v1/search/studies/2.25.abcd... HTTP/1.1
  Authorization: Bearer rv_live_...

Response 200 OK:
  {
    "pseudo_study_uid":   "2.25.abcd...",
    "modality":           "CT",
    "body_part":          "CHEST",
    "age_bucket":         "60-70",
    "sex":                "M",
    "study_date_shifted": "2026-04-20",
    "manufacturer":       "SIEMENS",
    "model_name":         "SOMATOM Force",
    "n_instances":        512,
    "n_series":           4,
    "total_bytes":        412553221,
    "hospital_opaque_id": "c3d4e5f6a7b8c9d0",
    "ingested_at":        "2026-04-21T03:20:51Z",
    "series": [
      {"pseudo_series_uid":"2.25.xyz","modality":"CT","n_instances":256},
      "..."
    ]
  }

Errors:
  401 ERR_AUTH_*
  404 ERR_STUDY_NOT_FOUND         (신규) — uid 존재하지 않음
  429 / 503 / 504 (공통)
```

### 7.3 `GET /v1/search/facets`

```
Request:
  GET /v1/search/facets HTTP/1.1
  Authorization: Bearer rv_live_...

Response 200 OK:
  (FR-45 shape, caching 15분)

Errors:
  401, 429, 503 (공통)
```

### 7.4 `GET /v1/search/hospitals`

```
Request:
  GET /v1/search/hospitals HTTP/1.1
  Authorization: Bearer rv_live_...

Response 200 OK:
  (FR-42 shape)

Errors:
  401, 403 ERR_SCOPE_FORBIDDEN(name_public 요구 시 tier 불충분), 429, 503 (공통)
```

### 7.5 `GET /healthz` · `/readyz` · `/v1/version`

central-ingest §7.3–7.5 와 동일 스펙 — `readyz` 는 PG ping + Redis ping + `alembic current == head` 3요소. 인증 불필요.

### 7.6 오류 코드 표 (신규 + 재사용)

| Code | HTTP | Category | 재사용/신규 |
|------|------|----------|-------------|
| `ERR_AUTH_MISSING` | 401 | Auth | 재사용(design-spec-central-ingest §5.1) |
| `ERR_AUTH_EXPIRED` | 401 | Auth | 재사용 |
| `ERR_AUTH_FORMAT` | 401 | Auth | **신규** — 키 포맷 위반 |
| `ERR_REQUEST_SCHEMA` | 400 | Request | **신규** — pydantic fail (central-ingest ERR_MANIFEST_SCHEMA 와 구분) |
| `ERR_FILTER_TOO_MANY` | 400 | Request | **신규** — IN 필터 > 10 |
| `ERR_PAGE_LIMIT` | 400 | Request | 재사용(design-spec §5.5 v0.2 가드를 v0.1 정식 사용) |
| `ERR_CURSOR_FILTER_CHANGED` | 400 | Cursor | **신규** — filter sha 불일치 |
| `ERR_CURSOR_VERSION` | 400 | Cursor | **신규** |
| `ERR_QUERY_TOO_BROAD` | 422 | Cost | **신규** — estimated rows > 10M |
| `ERR_QUERY_TIMEOUT` | 504 | Perf | **신규** — statement_timeout triggered |
| `ERR_RATE_LIMITED` | 429 | Rate | 재사용 |
| `ERR_BUYER_QUOTA` | 429 | Rate | **신규** — 일일 쿼터 |
| `ERR_BUYER_CONCURRENCY` | 429 | Rate | **신규** — 동시성 |
| `ERR_SCOPE_FORBIDDEN` | 403 | Auth | **신규** — scope_json 부족(name_public 등) |
| `ERR_STUDY_NOT_FOUND` | 404 | Data | **신규** |
| `ERR_IDEMP_UNAVAILABLE` | 503 | Infra | 재사용 |
| `ERR_DB_UNAVAILABLE` | 503 | Infra | 재사용 |
| `ERR_INTERNAL` | 500 | Generic | 재사용 |

신규 9종. Design-spec-metadata-index 에 5-field 포맷 (§13 Annex) 으로 풀어 쓴다.

---

## 8. 시퀀스·플로우

### 8.1 Search 플로우 (성공 경로, 필터 + 패싯 + 페이지)

```
[Buyer] POST /v1/search/studies (JSON)
   |
   v
[Nginx/ALB TLS 종단] → [gunicorn worker]
   |
   v
[Auth middleware]
   - Authorization: Bearer <key>
   - parse kid8, lookup Redis auth cache
   - on miss: SELECT buyer_api_key WHERE kid=:kid8, argon2 verify
   - attach (buyer_pk, tier, scope_json) to request context
   - negative result: constant-time argon2 dummy then 401
   |
   v (fail → 401 ERR_AUTH_*)
[Rate-limit middleware (slowapi/Redis)]
   - rpm bucket, daily counter, per-ip
   |
   v (fail → 429 ERR_RATE_LIMITED / ERR_BUYER_QUOTA)
[Concurrency semaphore]
   - INCR buyer_inflight:{buyer_pk}; check cap
   |
   v (fail → 429 ERR_BUYER_CONCURRENCY)
[Request validation (pydantic)]
   - parse SearchRequest (§6.4)
   - enforce FR-17, FR-18, FR-19, FR-20
   |
   v (fail → 400 ERR_REQUEST_SCHEMA / ERR_FILTER_TOO_MANY / ERR_PAGE_LIMIT)
[Cursor decode if present]
   - decode base64url, parse JSON
   - validate v, k, s
   - compute expected_s = sha256(canonical_filter || sort)[:12]
   - if s != expected_s → 400 ERR_CURSOR_FILTER_CHANGED
   |
   v
[Compute filter_sha256 for audit/cache key]
   - canonical_json(filter) || GLOBAL_SALT → sha256
   |
   v
[Pre-execution cost estimator]
   - Redis GET cohort_estimate:{filter_sha256}
   - on miss: EXPLAIN (FORMAT JSON) of filtered query, parse 'Plan Rows'
   - if estimate > 10M → 422 ERR_QUERY_TOO_BROAD
   - cache estimate in Redis TTL 5m
   |
   v
[Main query execution]
   - SELECT ... WHERE filter... AND (study_date_shifted, study_pk) < (:d,:p)
     ORDER BY study_date_shifted DESC, study_pk DESC LIMIT :limit+1
   - determine has_next by size
   - form items[] (exclude +1 sentinel)
   |
   v
[If include_facets:]
   - asyncio.gather 6 GROUP BY queries (parallel)
   - each bounded by PG statement_timeout=10s
   - if estimator.total > 2M: auto-suppress facets (FR-22), set hint
   |
   v
[Compute total_count (exact) if cost ok]
   - SELECT COUNT(*) FROM study WHERE filter...
   - else use planner estimate → total_hint
   |
   v
[Compute hospital_opaque_id per row]
   - sha256(hospital_pk || GLOBAL_SALT || buyer_pk)[:16]
   |
   v
[Build next_cursor if has_next]
   - encode {v,d,p,s,k} base64url
   |
   v
[Enqueue search_audit row (background task)]
   - INSERT into search_audit partition
   |
   v
[Return 200 + items + facets + total_count + next_cursor + X-Request-Id]
```

### 8.2 Facets 플로우 (전체 코퍼스 filter 자동완성)

```
[GET /v1/search/facets]
   |
   v
[Auth + rate-limit (공통)]
   |
   v
[Redis GET facets:global]
   - on hit → return cached (TTL 15m)
   - on miss:
       asyncio.gather 6 GROUP BY queries (no filter)
       cache result with TTL 15m
   |
   v
[Return 200 + 6-field facets + computed_at]
```

### 8.3 Hospitals 플로우

```
[GET /v1/search/hospitals]
   |
   v
[Auth + rate-limit]
   |
   v
[Redis GET hospitals:global]
   - on miss: SELECT hospital_pk, COUNT(study), MIN/MAX(study_date) GROUP BY hospital_pk
   - per row compute hospital_opaque_id (per-buyer salted)
   - cache TTL 5m (keyed per buyer_pk to avoid cross-buyer leak via opaque_id)
   |
   v
[Return 200 + items[] + total_hospitals]
```

### 8.4 mermaid 요약

```mermaid
sequenceDiagram
    participant B as Buyer client
    participant LB as Nginx/ALB
    participant APP as FastAPI (radivault_search)
    participant R as Redis
    participant PG as PostgreSQL (buyer_ro)

    B->>LB: POST /v1/search/studies (TLS1.3, Bearer)
    LB->>APP: HTTP
    APP->>R: auth cache GET kid8
    R-->>APP: miss
    APP->>PG: SELECT buyer_api_key WHERE kid=:kid8
    PG-->>APP: row
    APP->>APP: argon2 verify (~40ms)
    APP->>R: cache auth 60s
    APP->>R: rate-limit consume + inflight INCR
    R-->>APP: ok
    APP->>APP: pydantic validate
    APP->>R: cost_estimate cache GET
    R-->>APP: miss
    APP->>PG: EXPLAIN (FORMAT JSON) <query>
    PG-->>APP: planner rows
    APP->>R: cache estimate 5m
    par Main query + Facets
        APP->>PG: SELECT ... LIMIT 51
        PG-->>APP: rows
    and
        APP->>PG: 6× GROUP BY facet queries
        PG-->>APP: counts
    end
    APP->>PG: COUNT(*) total
    PG-->>APP: n
    APP-->>LB: 200 + items + facets + next_cursor
    LB-->>B: 200
    APP->>PG: INSERT search_audit (async)
    APP->>R: inflight DECR
```

### 8.5 장애 복구 시퀀스

- **PG read replica timeout** — `ERR_QUERY_TIMEOUT` 504. 구매자는 필터 좁히거나 `include_facets=false` 로 재시도.
- **Redis 장애** — rate-limit 검증 불가 → `ERR_IDEMP_UNAVAILABLE` 503. 무결성 우선.
- **Cursor version 불일치(서버 업그레이드 직후)** — `ERR_CURSOR_VERSION` 400. 클라이언트는 처음부터 재시작.
- **Cost estimator 오차**(EXPLAIN 이 실제보다 10× 낮게 추정) — 실행 쿼리가 `statement_timeout` 에 걸려 `ERR_QUERY_TIMEOUT`. 추후 분석 후 `cost.max_estimated_rows` 하향 조정.

---

## 9. 의존성

### 9.1 상위 모듈 / 선행 기능

- **central-ingest v0.1** — 본 dev-spec 의 DB 스키마·auth 패턴·envelope·에러 taxonomy 를 상속. study row 가 존재하지 않으면 search API 는 빈 결과만 반환.
- **Hospital 온보딩 + ingest 운영** — `study` 파티션이 실제 데이터로 채워져야 값이 있는 검색이 가능.
- **Buyer 온보딩 (영업)** — `buyer` row 수동 입력은 RadiVault 영업·운영팀 책임. `search-admin buyer create` 후 `key issue` 로 구매자에게 키 전달.

### 9.2 하위 모듈 / 후속 기능

- **order-orchestrator** — search 결과의 `pseudo_study_uid` 를 구매 cart 에 담아 구매 확정 → presigned URL 발급. 본 dev-spec 의 응답 필드 이름·타입에 의존.
- **thumbnail-cdn** — search 응답 `pseudo_study_uid` 로 썸네일 URL 을 구성할 수 있는 계약을 요청. 본 dev-spec 은 썸네일 URL 을 **제공하지 않지만** 향후 `thumbnail_url` 필드 추가 시 비호환 없음(superset).
- **python-sdk** (v0.2) — 본 dev-spec §13 Annex 에 SDK 로드맵 명시.
- **billing** — `search_audit` 의 filter_sha256 × order 매핑으로 funnel 분석 (v0.2).

**Alembic repo 결합 결정 (§4 FR-68 주석)**: v0.1 은 central-ingest 의 단일 alembic 트리에 revision 1개 추가 방식 채택. 독립 `alembic-search/` repo 를 두면 동일 스키마에 두 개의 `alembic_version` 테이블이 생기거나 revision 순서 역전 위험. 다만 두 서비스의 배포 독립성이 커지면(v0.3+) 별도 스키마(`search_schema`) + 별도 alembic tree 로 분리 가능 — 이 경우 신규 테이블 3종 은 `search_schema.*` 로 이동한다. 본 dev-spec 은 **v0.1 동일 repo 단일 트리**를 명시 채택.

### 9.3 외부 시스템·벤더

- **PostgreSQL 15+** — central-ingest 와 동일 인스턴스(최소 v0.1). v0.2 에 read replica 분리.
- **Redis 7+** — central-ingest 와 **동일 인스턴스** 재사용(키 네임스페이스 분리: `search:*` prefix). rate-limit, 캐시 통합.
- **역프록시 / TLS 종단** — central-ingest 와 공통. 서브도메인 `search.radivault.io` 권고(별도 ALB target group).

### 9.4 기술 스택 — 제안 (Kyle 승인 필요 · ARCHITECTURE §9 추가 TBD 해소)

| 영역 | 선정 | 근거 |
|------|------|------|
| 언어·버전 | **Python 3.11** | central-ingest 동일, 공유 ORM 재사용 |
| 웹 프레임워크 | **FastAPI ≥ 0.110** | 동일 envelope/에러 사용, OpenAPI 자동 |
| ASGI | **gunicorn + uvicorn.workers.UvicornWorker** | 동일 |
| DB 드라이버 | **SQLAlchemy 2.0 sync + psycopg v3** | central-ingest 실 구현과 일관. async 전환은 v0.2 검토. |
| 마이그레이션 | **Alembic** (central-ingest repo 공유) | §4.13 |
| Redis client | **redis-py 5.x** | slowapi 호환 |
| Rate limit | **slowapi** | central-ingest 동일 |
| 패스워드 해시 | **argon2-cffi** | central-ingest 동일 |
| 로깅 | **python-json-logger** | 동일 |
| 메트릭 | **prometheus-client + prometheus-fastapi-instrumentator** | 동일 |
| Tracing | **OpenTelemetry SDK + instrumentation-fastapi + instrumentation-sqlalchemy** | 동일 |
| 테스트 | **pytest, pytest-asyncio, httpx AsyncClient, testcontainers** | central-ingest fixture 재사용 |
| Container base | **python:3.11-slim-bookworm** | non-root UID 10001 |
| 배포 타깃 | **Ubuntu 22.04 LTS + Docker Compose**, K8s-ready v0.2 | central-ingest 동일 |

**ARCHITECTURE §9 갱신 제안**(Kyle 승인 후 별도 PR):
- `Zone 3 Developer API` 항목을 "Phase 2.0 REST API(FastAPI·PostgreSQL buyer_ro · Redis) / Phase 2.1+ Python SDK" 로 세분.
- §5.2 Developer API & SDK 에 "v0.1 REST-only, SDK 는 v0.2+" 명시.

---

## 10. 수용 기준 (Acceptance Criteria)

`@qa` 가 라인별 바이너리 검증. 총 **34 개**.

### 10.1 인증 · API Key

- [ ] **AC-1** (FR-1/2): 유효한 Bearer key `rv_live_abcd1234_...` 로 `POST /v1/search/studies` → `200` 응답. `X-Request-Id` 헤더 ULID 포맷.
- [ ] **AC-2** (FR-1): Authorization 누락 → `401 ERR_AUTH_MISSING` + `WWW-Authenticate: Bearer` 헤더.
- [ ] **AC-3** (FR-2): key 포맷 `rv_live_short` (형식 위반) → `401 ERR_AUTH_FORMAT`.
- [ ] **AC-4** (FR-3/4): 새 key 발급 → `buyer_api_key.token_hash` 에 평문이 저장되지 않음, argon2id 포맷(`$argon2id$…$`)으로만 저장.
- [ ] **AC-5** (FR-5): 동일 Bearer 로 연속 10회 호출 — 첫 요청만 argon2 실행(측정), 이후 9회는 Redis auth cache hit, `radivault_index_cache_hit_total{cache_layer="auth"}` 9 증가.
- [ ] **AC-6** (FR-6): `revoked_at=now()` 설정된 key → `401 ERR_AUTH_EXPIRED`.
- [ ] **AC-7** (FR-7): 무효 kid 5회 요청 응답 시간 타이밍 측정 Δ < 10ms (constant time).

### 10.2 Rate-limit · Concurrency

- [ ] **AC-8** (FR-11/12): preview tier key 로 분당 21회 요청 시 21번째 `429 ERR_RATE_LIMITED` + `Retry-After` 정수 초 헤더 + 바디.
- [ ] **AC-9** (FR-15): preview tier key 로 101번째 요청 `429 ERR_BUYER_QUOTA` (daily). UTC 자정 롤오버 후 정상.
- [ ] **AC-10** (FR-13): 동일 buyer 로 4개 동시 장시간 쿼리(sleep 쿼리 모의) — 4번째 요청 `429 ERR_BUYER_CONCURRENCY` (preview 상한 3).
- [ ] **AC-11** (FR-14): Redis 중단 상태에서 `POST /v1/search/studies` → `503 ERR_IDEMP_UNAVAILABLE`.

### 10.3 Request validation · Cursor

- [ ] **AC-12** (FR-17): `modality` 에 11개 값 → `400 ERR_FILTER_TOO_MANY`.
- [ ] **AC-13** (FR-18): `study_date_shifted.from` 만 제공, `to` 누락 → `400 ERR_REQUEST_SCHEMA`, detail 에 `study_date_shifted.to: field required`.
- [ ] **AC-14** (FR-19): `limit=500` (preview max 100) → `400 ERR_PAGE_LIMIT`.
- [ ] **AC-15** (FR-25/26): 페이지 1 응답의 `next_cursor` 로 페이지 2 요청 → `200`, 새 페이지 아이템이 페이지 1 과 중복 없음. `next_cursor` 수신 후 filter `modality` 에 값 추가 후 재요청 → `400 ERR_CURSOR_FILTER_CHANGED`.
- [ ] **AC-16** (FR-27): 수동으로 cursor `v=99` 설정 후 요청 → `400 ERR_CURSOR_VERSION`.

### 10.4 Cost estimator

- [ ] **AC-17** (FR-21): 아무 필터 없이 1억 row 합성 DB 기준 요청 → `422 ERR_QUERY_TOO_BROAD` + hint. Prometheus `radivault_index_query_too_broad_total` 카운터 1 증가.
- [ ] **AC-18** (FR-22): 추정 2.5M rows 조건 + `include_facets=true` 요청 → `200` 응답이되 `facets: null` 및 hint 에 "facets suppressed" 존재.
- [ ] **AC-19** (FR-23): 인위적 느린 쿼리(6s sleep) 모의 → `504 ERR_QUERY_TIMEOUT`.

### 10.5 Pagination · Facet · Projection

- [ ] **AC-20** (FR-28): 합성 데이터 1,000 studies + limit=50 → 20 페이지에 걸쳐 전량 순회 가능, 중복 0, 누락 0.
- [ ] **AC-21** (FR-33/34): `include_facets=true` 응답의 `facets.modality` 배열 길이 ≤ 50, count DESC 정렬.
- [ ] **AC-22** (FR-35): `total_count_exact: true` 응답의 `total_count` 는 직접 SELECT COUNT(*) 결과와 일치.
- [ ] **AC-23** (FR-37/38): 응답 `items[].` 에 `pseudo_study_uid, modality, body_part, ...` 필드만 존재, `StudyInstanceUID`·파일 key·URL 필드 **부재**(grep 0).
- [ ] **AC-24** (FR-41): paid tier 미만으로 `GET /v1/search/hospitals?include_names=true` 요청(v0.1 파라미터 없으나 scope_json override 시나리오) → `403 ERR_SCOPE_FORBIDDEN`.

### 10.6 Observability · Audit

- [ ] **AC-25** (FR-46): `/metrics` 에 `radivault_index_search_duration_seconds`, `radivault_index_facet_duration_seconds`, `radivault_index_cache_hit_total`, `radivault_index_rate_limited_total`, `radivault_index_query_too_broad_total` 전부 노출.
- [ ] **AC-26** (FR-47): 임의 10회 요청 후 JSON 로그를 `jq '[inputs] | .[] | keys[]' | sort -u` 해도 `filter_raw`, `api_key`, `cursor_raw`, `StudyInstanceUID` 키 0건. `filter_sha256`, `filter_fields` 는 존재.
- [ ] **AC-27** (FR-51/52): 성공 검색 후 `search_audit` 에 row 1개. 필드에 `filter_sha256`(64 char), `result_count`, `latency_ms` 존재, raw filter body 컬럼 부재.
- [ ] **AC-28** (FR-54): `radivault_buyer_ro` 계정으로 `DELETE FROM search_audit WHERE 1=1;` → permission denied. `UPDATE` 동일.

### 10.7 Healthz · Readyz · Version

- [ ] **AC-29** (FR-69): PG 중단 상태에서 `/healthz` 는 `200 {"status":"ok"}`. `/readyz` 는 `503 {"ready":false,"checks":{"db":"timeout",...}}`.
- [ ] **AC-30** (§7.5): `/v1/version` 인증 없이 `200` + 4개 필드 `version, git_sha, built_at, api_contract_version`.

### 10.8 Migrations · Packaging

- [ ] **AC-31** (FR-67/68): central-ingest repo 에서 `alembic upgrade head` 실행 → `buyer`, `buyer_api_key`, `search_audit` 테이블 생성됨, 기존 study 테이블 구조 unchanged (`pg_dump --schema-only` diff 0 rows).
- [ ] **AC-32** (FR-70): Alembic revision 적용 후 기존 central-ingest 의 pytest AC-1 ~ AC-36 모두 그대로 녹색.
- [ ] **AC-33** (FR-60/62): `docker compose -f docker-compose-search.yml up -d` → 60초 내 `GET http://localhost:8001/readyz 200`. 컨테이너 user `id -u == 10001`.
- [ ] **AC-34** (FR-65/66): `GET /openapi.json` 200 반환, 스펙 내 7 엔드포인트 전부 문서화. `docs/samples/search/` 에 curl 5종 + Postman 컬렉션 동봉.

---

## 11. 오픈 질문

> Kyle 결정 또는 외부 자문 필요. 본 dev-spec 은 답을 단정하지 않는다.

1. **Hospital opt-out 정책 단계** — v0.1 = 계약만 + scope_json.exclude_hospitals (권고) / v0.1.1 = application filter 전면 / v0.2 = PG RLS. 현재 dev-spec 은 application-layer 까지 준비하되 UI 는 없음. 어느 단계까지 v0.1 에 포함할 것인가?
2. **법률 자문 트리거** — hospital opt-out 계약 조항 신설·"완전 익명" 주장 법적 재확인. 자문 법인 선정 및 스케줄.
3. **Filter hash salt 전략** — 전역 GLOBAL_SALT (매출 funnel 분석용, FR-53 권고) vs per-buyer salt (보안 우선). 매출 교차분석이 얼마나 중요한가가 결정자.
4. **include_facets auto-suppress 임계** — 2M rows (FR-22) 기본값을 유지할지, 더 낮게(500K?) 또는 높게(5M?) 할지. 실측 후 조정.
5. **Python SDK 제공 시점** — v0.2 권고 (리서치 §4.7.5). v0.1.1 에 thin wrapper 를 조기 릴리즈할 이유 (파일럿 구매자 요청) 가 있다면 재고.
6. **Composite index #2 write-amp 관리** — `idx_study_filter_keyset` 가 ingest write-amp 에 미치는 영향을 1M rows 실측 후 유지/삭제 결정. 삭제 시 모달리티+부위 필터 쿼리 plan 재검증.
7. **NLP 라벨 필드 검색 노출 시점** — 본 v0.1 search API 에 placeholder field (`diagnosis_codes: string[]`) 를 미리 두어 SDK 계약 breaking 을 피할지, v0.2 에 깔끔히 추가할지.
8. **Pricing tier 실값** — preview (100/day) vs paid (10K/day) 이 경영상 합리적인가? free-tier 도입 여부.
9. **`search-admin` 분리 바이너리** vs `ingest-admin` 하나에 `search` 서브커맨드 통합 — 현재는 분리(FR-56). 운영 복잡도 대비 호불호.
10. **Host `search.radivault.io` 서브도메인** vs `api.radivault.io/v1/search/` — TLS cert, CORS 정책, onboarding UX 와 연관.
11. **Cost estimator 의 EXPLAIN 허용 여부** — `EXPLAIN (FORMAT JSON)` 은 쿼리 plan 을 노출해 레이트 한도 밖에서 DB 부하를 만들 수 있다. planner_row_estimate 를 위한 더 저비용의 `pg_class.reltuples` 기반 휴리스틱으로 대체할지 검토.
12. **Hospital opaque ID salt** — per-buyer salt 는 cross-buyer join attack 방지용. salt 유출 시 rotation 절차 정의 필요.

---

## 12. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-22 | @planner (Claude Opus 4.7) | 최초 작성. v0.1 MVP 범위 확정 — buyer-facing 검색 API 7 엔드포인트, argon2id 인증, keyset pagination, 패싯 aggregation, cost estimator, 신규 테이블 3종 (`buyer`, `buyer_api_key`, `search_audit`), 신규 study 인덱스 3종. Central-ingest envelope·에러 taxonomy 계승 + 신규 코드 9종. FR 77개, AC 34개. Alembic 은 central-ingest repo 공유 단일 트리. Python SDK 는 v0.2 지연. Hospital opt-out 은 scope_json 스키마만 준비, 기술 집행은 v0.1.1 백로그. |

---

## 13. Annex

### 13.1 에러 taxonomy 표 (5-field 포맷 — design-spec-central-ingest §5 동일 템플릿)

본 dev-spec 은 design-spec-metadata-index 작성 단계에서 아래 형식으로 확장된다. 개발자 참고를 위한 초안:

| Code | HTTP | 발생 조건 | message_ko | message_en | Buyer 조치 | RadiVault SRE 조치 |
|------|------|-----------|------------|------------|-------------|---------------------|
| `ERR_AUTH_MISSING` | 401 | Authorization 헤더 누락 | 인증 헤더가 없습니다. | Authorization header missing. | `rv_live_<kid>_<secret>` 헤더 추가. | — |
| `ERR_AUTH_EXPIRED` | 401 | key revoked/expired | 인증 키가 만료되거나 철회되었습니다. | API key expired or revoked. | 영업에 재발급 요청. | `search-admin key issue` 재발급. |
| `ERR_AUTH_FORMAT` | 401 | key prefix/length 위반 | 키 형식이 올바르지 않습니다. | API key format invalid. | 키 전체를 붙여넣기 확인. | — |
| `ERR_REQUEST_SCHEMA` | 400 | pydantic 검증 실패 | 요청 스키마가 올바르지 않습니다. | Request schema invalid. | 필드명·타입 OpenAPI 참조. | — |
| `ERR_FILTER_TOO_MANY` | 400 | IN 필터 > 10 | 필터에 10개를 초과하는 값이 있습니다. | IN filter exceeds 10 items. | 값 분할하여 페이지별 요청. | — |
| `ERR_PAGE_LIMIT` | 400 | limit > max_limit_per_page | 페이지 크기가 티어 상한을 초과합니다. | Page limit exceeds tier cap. | limit ≤ 100 (preview) 사용. | tier 상향은 계약 협의. |
| `ERR_CURSOR_FILTER_CHANGED` | 400 | cursor sha 불일치 | 커서 이후 필터가 변경되었습니다. 1페이지부터 다시 시작하세요. | Filter changed since cursor issued. Restart from page 1. | cursor + filter 일관성 유지. | — |
| `ERR_CURSOR_VERSION` | 400 | cursor v != 1 | 지원하지 않는 커서 버전입니다. | Unsupported cursor version. | 처음부터 재시작. | 서버 업그레이드 공지. |
| `ERR_QUERY_TOO_BROAD` | 422 | 추정 rows > 10M | 쿼리가 너무 광범위합니다. 필터를 좁혀주세요. | Query too broad. Narrow filters. | modality·date 추가. | 실측 로그로 임계 재조정. |
| `ERR_QUERY_TIMEOUT` | 504 | statement_timeout | 쿼리가 시간을 초과했습니다. | Query timed out. | 재시도 + 필터 축소. | 느린 쿼리 plan 조사. |
| `ERR_RATE_LIMITED` | 429 | 분당 한도 초과 | 분당 요청 한도를 초과했습니다. | Per-minute rate limit exceeded. | Retry-After 준수. | tier 상향 협의 or 한도 튜닝. |
| `ERR_BUYER_QUOTA` | 429 | 일일 쿼터 초과 | 일일 쿼터를 모두 사용했습니다. | Daily quota exhausted. | 내일 재시도 or 유료 전환. | 계약 상향 검토. |
| `ERR_BUYER_CONCURRENCY` | 429 | 동시성 cap | 동시 요청 수 한도를 초과했습니다. | Concurrent request cap exceeded. | 동시 요청 줄이기. | tier 상향. |
| `ERR_SCOPE_FORBIDDEN` | 403 | scope_json 불충분 | 해당 데이터 접근 권한이 없습니다. | Insufficient scope for this resource. | 영업 협의. | scope_json 수정. |
| `ERR_STUDY_NOT_FOUND` | 404 | pseudo_study_uid 없음 | 스터디를 찾을 수 없습니다. | Study not found. | UID 오타 확인. | — |
| `ERR_IDEMP_UNAVAILABLE` | 503 | Redis 다운 | 서버 상태 확인 중입니다. | Service degraded; Redis unavailable. | Retry-After 대기. | RB 실행. |
| `ERR_DB_UNAVAILABLE` | 503 | PG 다운 | DB 연결 불가. | Database unavailable. | 지수 백오프 재시도. | RB 실행. |
| `ERR_INTERNAL` | 500 | 미분류 | 내부 오류입니다. request_id 를 지원팀에 전달하세요. | Internal error. Share request_id with support. | 지원 티켓. | Sentry/stack trace. |

### 13.2 SDK 로드맵 (v0.2+)

v0.1 은 **REST API + OpenAPI 3.1 + curl 샘플 + Postman 컬렉션**만 제공하고 Python SDK 는 v0.2 로 지연(리서치 §4.7.5 권고). 단, API 는 SDK-friendly 하게 설계한다:

- **Resource naming 일관** — 모든 조회는 `/v1/search/<plural_resource>[/{id}]` 형태. v0.2 에 `/v1/search/studies/{id}/thumbnail` 추가 시 확장 자연스러움.
- **Idempotent GETs** — `GET` 은 부작용 없음. `POST /v1/search/studies` 는 조회 성격이지만 큰 JSON body 로 GET 쿼리 한계 회피 목적 (GraphQL 유사 패턴). SDK 측에서는 `search()` 단일 메서드로 래핑.
- **Stable cursor** — cursor JSON 은 서버 업그레이드 시 `v` bump 로 break 하되, 그 전에는 forever-stable. SDK 가 cursor 를 opaque 하게 취급하면 SDK 버전 업데이트 없이 동작.
- **Pagination helper** — SDK v0.2 는 `search().iter_items()` 형태의 자동 페이지네이션 제공. 본 dev-spec 의 `has_next`/`next_cursor` 계약이 그 전제.
- **Error type mapping** — SDK v0.2 는 `ERR_*` 코드별 Python exception class 1:1 매핑 (`QueryTooBroadError`, `RateLimitedError`, …). 본 dev-spec 의 에러 enum 안정성이 SDK forward-compat 을 보장.
- **TypedDict / dataclass** — 응답 shape 는 OpenAPI 3.1 에서 자동 생성 가능. SDK v0.2 는 `datamodel-code-generator` 로 타입 생성.
- **curl 샘플 5종**(v0.1 배포 산출물):
  1. Single modality + date range search.
  2. Multi-modality + facets.
  3. Pagination (cursor 2-page roundtrip).
  4. Single study detail.
  5. Hospitals list.

### 13.3 central-ingest 계약 영향 요약

| 영역 | 영향 |
|------|------|
| `study`, `series`, `instance`, `patient_pseudo`, `hospital` 테이블 | **읽기 전용**. 컬럼/타입/제약 변경 없음. |
| 기존 인덱스 | 변경 없음. 신규 3개 추가(§6.3). |
| Alembic head | +1 revision (metadata_index_v0_1). central-ingest pytest는 revision 적용 후에도 green 유지(AC-32). |
| Envelope · 에러 포맷 | design-spec-central-ingest §2/§5 와 **완전 호환**. 신규 코드 9종 추가 (§13.1). |
| central-ingest ingest 경로 | 영향 없음. 본 서비스는 write 하지 않음(search_audit 만 append INSERT). |

### 13.4 호환 시험 체크리스트 (QA 참고)

- [ ] central-ingest 의 `@pytest.mark.integration` 테스트가 search revision 적용 후 녹색.
- [ ] `radivault_buyer_ro` 계정으로 study/series/instance 에 INSERT/UPDATE/DELETE 시도 → permission denied.
- [ ] `search_audit` 월 파티션이 pg_partman 으로 자동 생성됨 (배포 당월 ± 2).
- [ ] `search-admin key issue` 로 발급한 key 로 실제 `POST /v1/search/studies` 성공 → 바로 `key revoke` 후 동일 key 요청 `401 ERR_AUTH_EXPIRED`.

---

### NEXT_STEP

- 완료 산출물: `docs/specs/dev-spec-metadata-index.md` (v0.1 Draft)
- 제안 다음 단계: **@designer** — `design-spec-metadata-index.md` 작성.
  - **설계 표면 6종**: (1) HTTP API UX(envelope 재사용 + 신규 에러 코드 5-field 확장), (2) `search-admin` CLI UX, (3) JSON 로그 / Prometheus 네이밍(`radivault_index_*`), (4) 에러 taxonomy 이중언어 표(본 §13.1 를 design-spec §5 로 승격), (5) Runbook 세트(empty-result alert, query-too-broad storm, Redis down, PG slow query, key leak incident), (6) Buyer onboarding walkthrough(`search-admin buyer create` → `key issue` → 구매자에게 전달 절차).
  - UI 는 없으므로 색·타이포 토큰 등은 "N/A — backend service"로 표기 (central-ingest design-spec 과 동일 패턴).
- 아키텍처 영향: **ARCHITECTURE.md §5.2 갱신 필요** — "v0.1 REST-only, Python SDK 는 v0.2+" 명시. §9 Zone 3 라인에 search 서비스 스택 추가. Kyle 승인 후 별도 PR.
- PRD 영향: §4.2 "코호트 검색 API" 의 HTTP 계약·인증·쿼터가 본 dev-spec 으로 구체화됨. §4.3 "Developer API" 를 "v0.1 REST, v0.2 Python SDK" 로 정정.
- Kyle 결정 필요 사항(§11 요약):
  1. Hospital opt-out 정책 v0.1 범위 (application filter 포함 vs 계약만).
  2. Filter hash salt 전략(전역 vs per-buyer).
  3. Pricing tier 실값 (preview 100/day, paid 10K/day 확정?).
  4. Python SDK 타이밍 (v0.2 vs v0.1.1 thin).
  5. Cost estimator 구현 — EXPLAIN 허용 여부.
  6. `search-admin` 별도 바이너리 vs `ingest-admin` 통합.
  7. 서브도메인 (`search.radivault.io` vs `api.radivault.io/v1/search/`).
  8. NLP 라벨 필드 placeholder 도입 시점.
  9. 합법 자문 트리거 — hospital opt-out 계약 조항 승인.
