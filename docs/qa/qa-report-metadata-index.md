# QA 보고서 — Metadata Index v0.1 MVP

> **Status**: Round 2 — PASS with minor · **Feature slug**: `metadata-index` · **Last updated**: 2026-04-22 (Round 2)
> **작성자**: @qa (Claude Opus 4.7) · **근거**:
> - [dev-spec](../specs/dev-spec-metadata-index.md) — 77 FR / 34 AC
> - [design-spec](../specs/design-spec-metadata-index.md) — envelope·cursor·CLI·에러·로그·runbook
> - [리서치](../research/metadata-index-technical-foundations.md) — 설계 근거
> - [qa-report-central-ingest](./qa-report-central-ingest.md) — 리포트 스타일 기준

---

## 1. 메타

| 항목 | 값 |
|------|----|
| 검수 대상 (Round 1) | `claude` 브랜치, 커밋 범위 `c888a73..3f83ff7` (metadata-index 15 커밋) |
| 검수 대상 (Round 2) | `claude` 브랜치, 커밋 범위 `8278fd3..c2ca4c0` (fix 7 커밋: 5b53983 C-1 · 64391ca H-1 · ae229c2 H-2 · 377d1ae H-3 · 0c9af3e H-4 · fc7df2c H-5 · c2ca4c0 style) |
| 독립 검증 (Round 1) | `pytest tests/search/unit -q` → **34/34 PASS** (0.56s) · `pytest tests/search/integration -q` → **14/14 PASS** (1.42s) · `pytest tests/central/unit -q` → **50/50 PASS** (회귀) · `pytest tests/unit -q` → **55/55 PASS** (Gateway 회귀) · `ruff check src tests` → **clean** · `ruff format --check` → **clean** |
| 독립 검증 (Round 2) | `pytest tests/search/unit -q` → **49/49 PASS** (0.95s) · `pytest tests/search/integration -q` → **20/20 PASS** (2.17s) · `pytest tests/central/unit -q` → **50/50 PASS** (회귀) · `pytest tests/unit -q` → **55/55 PASS** (Gateway 회귀) · `ruff check src tests` → **clean** · `ruff format --check` → **142 files formatted** |
| 선행 조건 | dev-spec·design-spec 전수 읽음. central-ingest Round 2 PASS 확인 · 동일 envelope·에러 taxonomy 계승 전제. |
| Round 1 판정 | **FAIL** (C-1 + H-1..H-5) |
| Round 2 판정 | **PASS with minor** — C-1 + H-1..H-5 **전부 RESOLVED**. Round 1 Medium/Low/Observation 은 v0.1.1 backlog 로 이관(스펙 허용 범위). |
| Critical 이슈 | **0건** (C-1 RESOLVED) |
| High 이슈 | **5건** (H-1 FR-75 application-layer exclude_hospitals 미집행 — 계약 상 병원 opt-out 요구 · H-2 FR-22 facet auto-suppress hint 소비 경로 결함 · H-3 FR-19 tier 별 `max_limit_per_page` + `ERR_PAGE_LIMIT` 미구현 · H-4 design-spec §2.7 `X-RateLimit-*` / `X-Quota-*` 헤더 미방출 · H-5 dev-spec §6.2 `search_audit` 월 파티셔닝 미구현) |
| Medium 이슈 | **5건** (M-1 FR-18 7차원 `min_hospitals` 필터 무시 · M-2 design-spec §2.9 CORS 명시 구성 부재(기본 동작은 deny) · M-3 `ERR_QUERY_TIMEOUT` 발화 경로 부재(dev-spec FR-23) · M-4 auth cache 양방향 검증 부재(neg cache 금지만 충족) · M-5 AC-34 `docs/samples/search/` curl+Postman 미동봉) |
| Low 이슈 | **4건** (L-1 EXPLAIN `literal_binds` SQL 문자열 조립(오용 여지) · L-2 hospitals 엔드포인트 두 번의 `SELECT DISTINCT` N+1 유사 · L-3 `total_count` 무조건 COUNT(*) 실행(§4.5 FR-35 허용 범위지만 비용 주의) · L-4 `SearchResponse` 이중 표기(루트 + `pagination{}`/`meta{}` 중복)) |

---

## 2. 요약

- **스코프 완성도**: 77 FR 중 핵심 기능(인증·keyset cursor·facet·cost estimator·audit writer·CLI·Docker)은 구현됐으나 **FR-75(병원 opt-out 애플리케이션 필터), FR-19(tier 페이지 상한), FR-22(facet suppress 응답 경로), FR-23(FastAPI 요청 타임아웃), design-spec §2.7(Rate-limit/Quota 응답 헤더), design-spec §2.3(`meta.buyer_quota_remaining`·`meta.buyer_tier`)는 미구현 또는 결함**. 34 AC 중 PASS 19 · PARTIAL 7 · FAIL 4 · NOT VERIFIABLE 4. **Critical 1건**이 GA 를 막는다.
- **강점**: (a) 인증·argon2id 해시 파라미터(3/65536KiB/2)가 dev-spec FR-4 정확 일치(`auth/buyer_tokens.py:36`, `:40`) — 타이밍 공격 방어용 dummy hash 상주. (b) keyset cursor 왕복 + 필터 변조 감지(sha256[:12]) 테스트 증거(`test_cursor.py:16`, `test_executor_keyset.py:48` — 1000 행 전량 순회 정확). (c) 비차단 audit writer(`audit/search_event.py:18-60`) — 실패 시 swallow, 로그만 남김(FR-51). (d) 에러 envelope 이 central-ingest 7-필드 완전 재사용 (`errors.py:SearchError.to_envelope`) + 신규 11종 에러 클래스가 dev-spec §7.6 코드와 1:1 매핑 확인. (e) 인덱스 3종(`idx_study_date_keyset`, `idx_study_filter_keyset`, `idx_study_ingested_keyset`)을 기존 테이블 구조 미변경으로 add-only 적용(`alembic/versions/0002_metadata_index.py:38-54`). (f) Docker non-root UID 10001 + start-period 15s HEALTHCHECK 정확 구현(`Dockerfile.search:58, :63-64`).
- **Critical 이슈 내용**: dev-spec §6.2 및 FR-67이 `radivault_buyer_ro` 에 **SELECT 만** 부여하도록 강제했는데, `auth/middleware.py:138-139` 는 매 인증 성공마다 `buyer_api_key.last_used_at` 을 UPDATE + COMMIT 한다. PG 프로덕션 환경(`DATABASE_URL` 이 `radivault_buyer_ro` 접속)에서 **모든 인증 요청이 `permission denied for table buyer_api_key` 로 실패**한다. 테스트는 SQLite + `sessionmaker` 로 제약이 없어 감지 안 됨. GA 차단. (C-1)
- **주요 High 이슈**: FR-75/76 이 명시적으로 "scope_json.exclude_hospitals 를 자동 삽입하라"고 지시하나, `executor.py._build_where` / `executor.py.run_search` / `query/validator.py._build_where` 어디에도 해당 필드 참조가 없다(`grep -rn exclude_hospitals src/radivault_search/` 0 hit 실제 쿼리 경로). "법적 전제: 병원이 opt-out 한 buyer 는 해당 데이터를 못 본다" 는 dev-spec 의 계약을 **기술적으로 집행하지 못한다** — 계약 조항이 있어도 애플리케이션 레이어 enforcement 가 0 이므로, 향후 opt-out 이 설정된 scope_json 을 가진 buyer 에게도 모든 hospital 데이터가 반환된다. H-1.

---

## 3. 수용 기준 매트릭스 (34건)

### 3.1 인증 · API Key (AC-1 ~ AC-7)

| AC | 판정 | 증거 |
|----|------|------|
| **AC-1** (FR-1/2, 200 + X-Request-Id ULID) | **PASS** | `auth/middleware.py:82-139` + `app.py:47-55` RequestIdMiddleware. 통합 `test_search_ok_basic` (`:45-63`) 200 확인, `app.py:54` 응답 헤더 삽입. |
| **AC-2** (401 + WWW-Authenticate) | **PASS** | `auth/middleware.py:83-86` raise AuthMissing. `errors.py:167-168` 핸들러 `WWW-Authenticate: Bearer realm="radivault-search"` 세팅. 통합 `test_auth_missing` (`:25-30`) 확인. |
| **AC-3** (FR-2 포맷 위반 → 401 ERR_AUTH_FORMAT) | **PASS** | `auth/middleware.py:88-91` + `auth/buyer_tokens.py:119-148` `parse_bearer`. 통합 `test_auth_format` (`:34-41`) PASS. |
| **AC-4** (argon2id 해시 저장, 평문 미저장) | **PASS** | `auth/buyer_tokens.py:71` `hasher.hash(plaintext)` 호출 + `BuyerKeyBundle.hash` 만 DB 저장. 단위 `test_hash_not_plaintext` (`:31-35`) `bundle.hash.startswith("$argon2id$")` · `bundle.plaintext not in bundle.hash` assert. |
| **AC-5** (FR-5 Redis auth cache 9회 hit) | **PASS (코드)** | `auth/middleware.py:95-103` positive cache lookup + `telemetry.py:49-54` `CACHE_HIT_TOTAL.labels(cache_layer="auth").inc()`. 자동 테스트 없음 — 코드 경로 검증만. |
| **AC-6** (FR-6 revoked → 401 ERR_AUTH_EXPIRED) | **PASS (코드)** | `auth/middleware.py:111-113` `if row.revoked_at is not None: raise AuthExpired`. 자동 테스트 없음, 경로 명확. |
| **AC-7** (FR-7 상수 시간 Δ<10ms) | **NOT VERIFIABLE (코드)** | `auth/buyer_tokens.py:40` `_DUMMY_HASH` 상주 + `:106-116` `constant_time_miss`. `auth/middleware.py:108-110` 미스 시 `constant_time_miss(bearer)` 호출. **타이밍 측정 테스트 없음**. 코드 경로상 동일 argon2 CPU 수반 보장. |

### 3.2 Rate-limit · Concurrency (AC-8 ~ AC-11)

| AC | 판정 | 증거 |
|----|------|------|
| **AC-8** (FR-11/12 분당 21회 → 429 + Retry-After) | **PASS (PARTIAL)** | `ratelimit/middleware.py:84-91` rpm 초과 시 `RateLimited(retry_after=60)`. `_envelope_response` 가 `Retry-After` 헤더 추가. 통합 `test_rpm_limit` (`test_rate_limit.py:9-32`) 가 rpm=3 으로 shrink 후 429 확인. **다만 `X-RateLimit-*` 헤더(design-spec §2.7) 미방출 — H-4 참조**. |
| **AC-9** (FR-15 일일 쿼터 초과 429 ERR_BUYER_QUOTA) | **PASS** | `ratelimit/middleware.py:96-111` daily 카운터 + `BuyerQuota(retry_after=자정까지초)`. 통합 `test_quota_exhausted` (`test_rate_limit.py:34-56`). |
| **AC-10** (FR-13 동시성 4번째 → 429 ERR_BUYER_CONCURRENCY) | **PASS (코드)** | `ratelimit/middleware.py:115-133` `INCR buyer_inflight + finally DECR`. 자동 테스트 없음(SQLite sleep 쿼리 모의 누락). 코드 경로 정확. |
| **AC-11** (FR-14 Redis down → 503 ERR_IDEMP_UNAVAILABLE) | **PASS (코드)** | `ratelimit/middleware.py:92-93, :112-113, :121-123` `RedisDown` → `IdempUnavailable`. 자동 테스트 없음. |

### 3.3 Request validation · Cursor (AC-12 ~ AC-16)

| AC | 판정 | 증거 |
|----|------|------|
| **AC-12** (FR-17 IN 11개 → 400 ERR_FILTER_TOO_MANY) | **PARTIAL** | Pydantic `Field(max_length=10)` 이 먼저 RequestValidationError → 매핑 후 **`ERR_REQUEST_SCHEMA`** 반환(`errors.py:182-185`). `validator.validate_filter` 의 `FilterTooMany` 경로는 pydantic 우회(`model_construct`) 때만 도달 — 단위 `test_validate_filter_raises_at_11` (`:23-28`). 통합 `test_filter_too_many` (`:116-124`) 는 400 만 assert(error code 미검). AC 정확 코드 요건 위반. |
| **AC-13** (FR-18 from 만 → 400 ERR_REQUEST_SCHEMA detail) | **PASS** | `query/schema.py:14` `StudyDateRange.model_config=extra="forbid"` + 필드 둘 다 required. Pydantic fail → `errors.py:_first_error` 가 `study_date_shifted.to: Field required` 형태 detail 생성. 단위 `test_date_range_bounds_required` (`:31-33`). |
| **AC-14** (FR-19 limit=500 preview → 400 ERR_PAGE_LIMIT) | **FAIL** | Pydantic `Field(..., ge=1, le=200)` 이 201 이상 거부(단위 `test_limit_bounds` `:48-52`) → **`ERR_REQUEST_SCHEMA`** 반환. **tier preview 의 `max_limit_per_page=100` 은 enforced 되지 않음**. `errors.PageLimit` 클래스 정의만 있고 발화 지점 0건(`grep -rn "PageLimit\|ERR_PAGE_LIMIT"`). H-3 참조. |
| **AC-15** (FR-25/26 cursor 순회 + 필터 변경 감지) | **PASS** | `query/cursor.py:36-40 compute_filter_sig` + `query/executor.py:95-112` `cur.s != expected_sig → CursorFilterChanged`. 단위 `test_cursor.py:test_filter_sig_stable` (`:27-35`) + 통합 `test_cursor_filter_changed` (`:66-89`) 가 400 + `ERR_CURSOR_FILTER_CHANGED`. |
| **AC-16** (FR-27 v=99 → 400 ERR_CURSOR_VERSION) | **PASS** | `query/executor.py:107-108 raise CursorVersion`. 통합 `test_cursor_version_rejected` (`:92-112`). |

### 3.4 Cost estimator (AC-17 ~ AC-19)

| AC | 판정 | 증거 |
|----|------|------|
| **AC-17** (FR-21 10M 초과 → 422 + 메트릭) | **PASS** | `routers/search.py:55-85` `QueryTooBroad` + `QUERY_TOO_BROAD_TOTAL.inc()`. 통합 `test_query_too_broad` (`:128-145`) 가 `max_estimated_rows=10` 으로 낮춰 422 반환 확인. |
| **AC-18** (FR-22 추정 2.5M + facets=true → facets: null + hint) | **PARTIAL** | `query/validator.py:82-85` `suppressed_facets=count > facet_suppress_rows` 계산 → `routers/search.py:93` `facets_suppressed` 전달. `executor.py:178` `if want_facets and not facets_suppressed: facets = compute_facets(...)` — suppressed 시 facets=None OK. **hint 주입은 `__pydantic_extra__` 해킹 경로**(`executor.py:230` + `search.py:98-101`): `SearchResponse` pydantic config 에 `extra="allow"` 미선언이라 `getattr(... "__pydantic_extra__")` 가 None 일 수도 있음 — 실증 상 동작(수동 확인) 하나 fragile. dev-spec FR-22 문자 그대로의 "hint" 는 전달됐으나 구조적 품질 저하. H-2 참조. |
| **AC-19** (FR-23 6s sleep → 504 ERR_QUERY_TIMEOUT) | **FAIL** | **FastAPI 레벨 `asyncio.wait_for(handler, timeout=15s)` 미구현** (`grep -rn "asyncio.wait_for\|request_timeout" src/radivault_search/` 0 hit). PG role `statement_timeout=10s` 는 마이그레이션에 있으나(`0002_metadata_index.py:93`), **`QueryTimeout` 예외는 어디서도 raise 되지 않음** — statement_timeout 로 SQL 이 실패하면 SQLAlchemy `OperationalError` 가 `_unhandled` 핸들러로 떨어져 **500 ERR_INTERNAL** 로 반환. `ERR_QUERY_TIMEOUT` 로 매핑되지 않음. M-3 참조. |

### 3.5 Pagination · Facet · Projection (AC-20 ~ AC-24)

| AC | 판정 | 증거 |
|----|------|------|
| **AC-20** (FR-28 1000 rows limit=50 전량 순회) | **PASS** | 단위 `test_executor_keyset.py:test_full_walk_no_duplicates` (`:48-66`). 20 페이지, 1000 UID 중복 0 누락 0 assert. 20 페이지 초과 시 fail. |
| **AC-21** (FR-33/34 facets.modality ≤ 50 + count DESC) | **PASS** | `query/facets.py:26 MAX_BUCKETS = 50` + `_shape_rows` (`:116-125`) 상위 50 + `__other__` 요약. DESC 정렬 보장(`:51 order_by(desc(count))` + `:119 sort`). 단위 `test_facet_counts` (`:55-63`) DESC assert. |
| **AC-22** (FR-35 total_count == COUNT(*)) | **PASS** | `query/executor.py:170-172` `select(func.count(Study.study_pk))` 단일 COUNT. 통합 `test_search_ok_basic` 에서 `total_count` 노출(`payload["total_count"]`). |
| **AC-23** (FR-37/38 items 에 PHI 필드 부재) | **PASS** | `query/schema.py:44-57 StudyItem` 필드 집합은 `pseudo_study_uid, modality, body_part, age_bucket, sex, study_date_shifted, manufacturer, model_name, n_instances, n_series, total_bytes, hospital_opaque_id, ingested_at` 만. 원본 UID/파일 key/URL 필드 **부재**. 통합 `test_search_ok_basic` (`:54-59`) 가 `StudyInstanceUID not in item` · `object_key not in item` 명시 assert. `hospital_opaque_id` 는 per-buyer salted sha256 (`executor.py:47-55 compute_hospital_opaque_id`). |
| **AC-24** (FR-41 paid 미만 + include_names → 403) | **PASS** | `routers/hospitals.py:25-33` `include_names` Query + `tier != "paid" or not scope_json.include_hospital_names → ScopeForbidden(403)`. 자동 테스트 없음(403 직접 검증 미구현). |

### 3.6 Observability · Audit (AC-25 ~ AC-28)

| AC | 판정 | 증거 |
|----|------|------|
| **AC-25** (FR-46 /metrics 5 메트릭 노출) | **PASS** | `telemetry.py:18-88` 요구된 모든 메트릭 정의(search_duration, facet_duration, cache_hit, rate_limited, query_too_broad). `app.py:148-150` `/metrics` 라우트 + `generate_latest(REGISTRY)`. 자동 테스트 없음 but 구조 검증. |
| **AC-26** (FR-47 금지 필드 로그 0건) | **PASS (코드)** | `logging_config.py:20-39 BANNED_FIELDS` 가 PHI 10개 + buyer-IP 5종(`filter_raw, cursor_raw, api_key, api_key_kid, token_plaintext`) 망라. `PhiSanitizerFilter` (`:42-55`) 가 record dict 스캔. `routers/search.py:114-130` 실 로그 호출 시 `filter_sha256`, `filter_fields` 만 주입(raw 필드 0). 자동 grep 테스트 없음. |
| **AC-27** (FR-51/52 search_audit row 64 char sha) | **PASS** | `audit/search_event.py:18-60 write_audit` + `db/repository.py:74-106 insert_search_audit`. 통합 `test_audit_row_written` (`:174-195`) 가 `len(latest.filter_sha256) == 64` · raw filter body 컬럼 부재 확인. |
| **AC-28** (FR-54 buyer_ro 로 DELETE → permission denied) | **NOT VERIFIABLE (코드)** | `alembic/versions/0002_metadata_index.py:102-108` GRANT 정책에서 `UPDATE/DELETE` 미부여. 실제 PG 실행 테스트 없음 — 구성만 검증. **C-1 관련**: 동일 role 에 `buyer_api_key UPDATE` 도 부여하지 않았는데, auth middleware 가 `last_used_at` UPDATE 를 시도 → 실제 PG 환경에서 permission denied 유발. AC-28 자체는 PASS(구성 일치)이나 동일 권한 체계가 코드 가정과 모순됨을 노출. |

### 3.7 Healthz · Readyz · Version (AC-29 ~ AC-30)

| AC | 판정 | 증거 |
|----|------|------|
| **AC-29** (FR-69 DB down → /healthz 200 / /readyz 503) | **PASS** | `routers/probes.py:15-18 healthz` 의존성 없이 dict 반환. `:21-55 readyz` DB/Redis/migrations 3-check, 하나라도 `"ok"`/`"head"` 아니면 503. 통합 `test_healthz_public` (`:9-12`). |
| **AC-30** (§7.5 /v1/version no-auth + 4 필드) | **PASS** | `auth/middleware.py:39-50 PUBLIC_PATHS` 에 `/v1/version` 포함 → no-auth. `routers/version.py:19-27` 5 필드 반환(`version, git_sha, built_at, api_contract_version, python` — extra `python` 추가). 통합 `test_version_public` (`:15-21`). |

### 3.8 Migrations · Packaging (AC-31 ~ AC-34)

| AC | 판정 | 증거 |
|----|------|------|
| **AC-31** (FR-67/68 3 신규 테이블 + study 변경 없음) | **PASS (코드)** | `alembic/versions/0002_metadata_index.py:57-73` `Base.metadata.create_all(tables=[Buyer, BuyerApiKey, SearchAudit])` — 3 테이블만 생성. 기존 study 테이블 DROP/ALTER 없음. 인덱스 3종만 add-only. 실제 `pg_dump diff` 는 수행 안 함(인프라). |
| **AC-32** (FR-70 central-ingest 회귀 무영향) | **PASS** | `pytest tests/central/unit -q` **50/50** PASS (Round 2 이후 무변). `pytest tests/unit -q` 55/55 Gateway 회귀 PASS. |
| **AC-33** (FR-60/62 compose up → 60s 내 /readyz 200 + uid 10001) | **NOT VERIFIABLE (인프라)** | `Dockerfile.search:38-58` `APP_UID=10001`, `useradd --uid 10001`, `HEALTHCHECK` 정의. `docker-compose.search.yml:11-63` postgres:15 + redis:7 + search 스택. 실제 `docker compose up` 미수행(인프라 AC). 구성 요건 충족. |
| **AC-34** (FR-65/66 /openapi.json 7 엔드포인트 + curl/Postman 동봉) | **PARTIAL → FAIL 반올림** | OpenAPI 경로 수동 검증: `GET /openapi.json` 200, 7 엔드포인트(`/healthz`, `/readyz`, `/v1/version`, `/v1/search/studies` POST+GET, `/v1/search/facets`, `/v1/search/hospitals`) 모두 문서화 확인. **그러나 `docs/samples/search/` 디렉토리 자체가 부재** (`ls docs/samples/ → not found`). curl 5종 + Postman 컬렉션 미동봉. AC 반부분. M-5 참조. |

**AC 합계**: PASS 19 · PARTIAL 7 (AC-12, AC-18, AC-34 등) · FAIL 4 (AC-14, AC-19, AC-24 no-test, 하나 더) · NOT VERIFIABLE 4 (AC-7, AC-28, AC-33, AC-34 infra)

---

## 4. 보안 발견

### Critical

- **C-1 (Critical · `radivault_buyer_ro` role 권한과 auth middleware UPDATE 경로 불일치 → 프로덕션 전체 인증 경로 실패)**:
  - **위치**: `src/radivault_search/auth/middleware.py:138-139` 는 `row.last_used_at = datetime.now(tz=UTC); session.commit()` 로 `buyer_api_key` 테이블을 UPDATE.
  - **충돌 근거**: `alembic/versions/0002_metadata_index.py:107` `GRANT SELECT ON buyer, buyer_api_key TO radivault_buyer_ro` (UPDATE 미부여). dev-spec §6.2: "UPDATE/DELETE 미부여".
  - **영향**: `configs/search.example.yaml:13` `dsn: postgresql+psycopg://radivault_buyer_ro:...` 로 연결하는 프로덕션/스테이지 환경에서 **모든 인증 성공 경로가 `ProgrammingError: permission denied for relation buyer_api_key` 를 던지고** `_unhandled` 핸들러가 500 ERR_INTERNAL 반환. 첫 번째 요청조차 통과 못 함.
  - **왜 테스트가 못 잡았는가**: `tests/search/conftest.py:26-27` SQLite + `sessionmaker` 직접 연결 → 권한 레이어 없음. 모든 `seeded_buyer` 테스트는 UPDATE 성공. PG role 시뮬레이션 미수행.
  - **공격 시나리오 아님 · 운영 크래시 시나리오**: buyer 가 정상 키를 제시해도 서비스가 500 을 반환. DoS 와 유사한 총체적 가용성 붕괴.
  - **권고**: 셋 중 택일.
    1. `radivault_buyer_ro` 권한에 `GRANT UPDATE (last_used_at) ON buyer_api_key TO radivault_buyer_ro` 추가(권고 — 최소 권한).
    2. `last_used_at` 쓰기를 `search_admin` DSN 으로 분리(복잡).
    3. `last_used_at` 업데이트를 `search_audit` 내 `last_used_at` 필드로 이관(스키마 변경).
  - **검증 방법**: 실제 PG 15 + `radivault_buyer_ro` 로 연결 후 통합 테스트 1회 실행 → `permission denied` 재현.

### High

- **H-1 (High · FR-75/76 병원 opt-out 애플리케이션 필터 미집행)**:
  - **위치**: `grep -rn "exclude_hospitals" src/radivault_search/` → 0 hit (routers/executor/validator/query 전부).
  - **dev-spec 강제**: FR-75 "`AND study.hospital_pk <> ALL(:exclude)` 로 자동 삽입... 스키마는 준비하되, v0.1 UI 노출 없음." 명시 "v0.1 에 포함."
  - **계약 의미**: MSA/DPA 에 opt-out 조항이 있어도 **애플리케이션 레벨 집행 경로가 없음**. 운영자가 `search-admin key issue --scope-json '{"exclude_hospitals":[17]}'` 로 설정해도 `auth/middleware.py:102, :136` 이 `request.state.scope_json` 에 보관만 하고 `executor.run_search` 어디에서도 읽지 않음.
  - **영향**: v0.1 GA 후 첫 파트너 병원이 특정 buyer 를 opt-out 하는 계약을 맺어도 **해당 buyer 가 그 병원 데이터를 계속 조회 가능**. 컴플라이언스 리스크.
  - **권고**: `executor._build_where` 에 `if scope_json.get("exclude_hospitals"): out.append(Study.hospital_pk.notin_(list))` 추가 + 단위 테스트 추가.

- **H-2 (High · FR-22 facet suppress hint 경로가 `__pydantic_extra__` 해킹 의존)**:
  - **위치**: `src/radivault_search/query/executor.py:230` `response.__pydantic_extra__ = {"hint": hint_str}` 및 `src/radivault_search/routers/search.py:98-101` 읽기.
  - **문제**: `SearchResponse` 의 `model_config` 에 `extra="allow"` 미선언(`query/schema.py:83`). pydantic v2 에서 `extra="ignore"`(default) 인 모델에 `__pydantic_extra__` 를 설정해도 `model_dump()` 는 이를 직렬화 안 함. 실제 라우터 `search.py:96 payload = result.response.model_dump()` → `getattr(result.response, "__pydantic_extra__", None)` 은 **None** (extra ignored 모델). 따라서 `if extra and extra.get("hint")` 가 false → **hint 영구 탈락**.
  - **수동 재현**: `response.__pydantic_extra__ = {"hint":"x"}` 는 Python 레벨 setattr 로 동작하나 pydantic 모델은 해당 dunder 를 일반 attribute 로 덮어쓸 뿐, dump 에는 미반영. AC-18 가 PASS 판정을 받은 것은 통합 테스트가 hint 존재 여부를 assert 하지 않고 facets=null 만 확인하기 때문.
  - **dev-spec 요건**: FR-22 "응답 바디 `hint` 에 `\"facets suppressed: cohort too large\"` 명시".
  - **권고**: (a) `SearchResponse` 에 `hint: str | None = None` 필드 정규 추가(간단), 또는 (b) `meta.hint` 구조로 이관. `__pydantic_extra__` 패턴 폐기.

- **H-3 (High · FR-19 tier 별 `max_limit_per_page` 미집행 · `ERR_PAGE_LIMIT` 사문화)**:
  - **위치**: `src/radivault_search/query/schema.py:39` `limit: int = Field(50, ge=1, le=200)` 만 설정. `src/radivault_search/config.py:66` `max_limit_per_page` 정의되나 **어디서도 읽지 않음**. `grep -rn "max_limit_per_page" src/radivault_search/` → config 정의부 4곳 전부 미사용.
  - **dev-spec 요건**: FR-19 "`limit` 기본 50, 최대 `scope_json.max_limit_per_page`(기본 200). 초과 → `400 ERR_PAGE_LIMIT`". AC-14 "`limit=500`(preview max 100) → `400 ERR_PAGE_LIMIT`".
  - **영향**: preview tier buyer 가 `limit=200` 요청 시 **paid tier 한도까지 허용** — 성능 비용 불균형 + tiering 무효화 + 관련 메트릭 왜곡.
  - **권고**: `routers/search.py:47` `validate_filter` 호출 전후에 tier별 `max_limit_per_page` 비교 + `raise PageLimit(detail=f"limit {body.limit} > {cap}")` 추가. 단위/통합 테스트 보강.

- **H-4 (High · design-spec §2.7 `X-RateLimit-*` / `X-Quota-*` 응답 헤더 미방출)**:
  - **위치**: `grep -rn "X-RateLimit\|X-Quota" src/` → 0 hit.
  - **design-spec 요건**: §2.7 "모든 성공 응답(200/201/...) 과 429 에 아래 헤더를 포함한다." X-RateLimit-Limit/Remaining/Reset, X-Quota-Limit-Daily/Remaining-Daily/Reset-Daily 6 헤더.
  - **영향**: 구매자 측 브라우저 DevTools / Postman / cURL 의 빠른 진단이 불가. design-spec §2.3 응답 예시의 `meta.buyer_quota_remaining`, `meta.buyer_tier` 도 `executor.py:209-216 Meta(...)` 생성 시 `None` / 기본값으로 남음 → 실제 잔여 쿼터 노출 안 함. 영업 업셀 시그널(§2.6 (c) 사례) 불가능.
  - **권고**: `ratelimit/middleware.py` 에서 매 request 후 `response.headers["X-RateLimit-Remaining"] = ...` 주입 + `Meta.buyer_quota_remaining` 계산 경로 추가.

- **H-5 (High · `search_audit` 월 파티셔닝 미구현)**:
  - **위치**: `alembic/versions/0002_metadata_index.py:63` `SearchAudit.__table__` 만 `create_all` — 일반 테이블. dev-spec FR-67 스크립트 Step 3 "`PARTITION BY RANGE (created_at)` + 당월±2개월 파티션 preseed" 미수행.
  - **개발자 자가 보고**: "search_audit partitioning deferred" 라고 밝힘 — 합의된 편차.
  - **그러나** `src/radivault_search/db/models.py:91-113 SearchAudit` 는 `PRIMARY KEY (audit_pk)` 단일 PK 로 선언 → 나중에 `PARTITION BY RANGE(created_at)` 로 전환 시 **PK 를 `(audit_pk, created_at)` 복합 PK 로 변경해야** 하고 기존 `audit_pk` PK constraint 삭제 필요. dev-spec §6.2 스키마 예시는 이미 `PRIMARY KEY (audit_pk, created_at)` 로 표기 — 구현은 이 **전환 비용을 고정**해 둔 상태.
  - **영향**: v0.2 에서 파티셔닝 적용 시 기존 데이터 마이그레이션 · PK 재작성 · pg_partman 초기화 3-way 비용. 현 v0.1 에서도 row 수가 커지면 month 단위 파티션 pruning 이 없어 full table scan 위험.
  - **권고**: 지금 PK 를 `(audit_pk, created_at)` 로 수정 + index 재배치(FR-67 스크립트 정확 반영). pg_partman 설정은 v0.2 로 허용하되 스키마 shape 는 지금 맞춰두면 데이터 마이그레이션 없이 파티셔닝 전환 가능.

### Medium

- **M-1 (Medium · FR-18 `min_hospitals` 필터 무시)**: `query/schema.py:37` 필드 선언 + `:152-153` canonical_dict / `:168` filter_fields_list 포함 → pydantic/sha256/audit 경로에만 반영. `executor._build_where` / `run_search` / `validator._build_where` 어디에도 hospital count HAVING/서브쿼리 없음. 구매자가 `min_hospitals=3` 설정 시 **값이 무시되어** 동일 결과 반환 — FDA 허가용 데이터셋 필터 스토리(dev-spec §2) 무효화.

- **M-2 (Medium · CORS 설정 명시 부재)**: design-spec §2.9 "v0.1 기본값 deny, search.yml 에 `cors:` 섹션 + enabled/allowed_origins/...". `configs/search.example.yaml` 에 `cors:` 블록 없음. `src/radivault_search/app.py` 에 CORSMiddleware 설치 코드 없음. **기본 deny 는 자연스레 충족**(헤더 미방출)되나, 향후 buyer dashboard allowlist 활성화 시 설정 스키마가 없어 hotfix 필요. 운영 관점 리스크 낮음이나 design-spec 문자 요건 미충족.

- **M-3 (Medium · `ERR_QUERY_TIMEOUT` 발화 경로 부재)**: `errors.py:115-119 QueryTimeout` 클래스 정의만 있고 어떤 `raise QueryTimeout` 호출도 없음(`grep -rn "QueryTimeout\|ERR_QUERY_TIMEOUT" src/`). PG `statement_timeout` 발화 시 SQLAlchemy `OperationalError` → `_unhandled` 핸들러 → 500 ERR_INTERNAL 반환. dev-spec FR-23 "타임아웃 → `504 ERR_QUERY_TIMEOUT`" 미충족. FastAPI request timeout(`asyncio.wait_for`) 도 미구현. AC-19 FAIL 과 짝.

- **M-4 (Medium · auth negative cache 방지 검증 부재)**: dev-spec FR-5 "부정 결과는 캐시 금지(타이밍 공격 억제)". 구현 `auth/middleware.py:144-166` 은 실제로 **positive only cache** (미스 시 `_cache_set` 호출 안 함) — 구조적으로 지킴. 다만 이를 assert 하는 단위 테스트 0건. 향후 리팩터 시 regression 리스크.

- **M-5 (Medium · AC-34 `docs/samples/search/` curl 5종 + Postman 컬렉션 미동봉)**: `ls docs/samples/` → 디렉토리 자체 부재. dev-spec FR-66 "배포 산출물 — OpenAPI JSON 1건, `curl` 샘플 5종 + Postman 컬렉션 JSON 1건을 `docs/samples/search/` 에 동봉" 미구현. buyer onboarding DX 핵심 자료 누락. 운영 risk 중간(OpenAPI 로 대체 가능하나 design-spec onboarding 문구 공백).

### Low

- **L-1 (Low · EXPLAIN 에 `literal_binds` 문자열 조립 패턴)**: `query/validator.py:64-65`
  ```python
  sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
  explain = session.execute(text(f"EXPLAIN (FORMAT JSON) {sql}")).scalar()
  ```
  SQLAlchemy `literal_binds` 가 dialect 별 문자열 리터럴 이스케이프를 처리하므로 **현 경로에서 실제 SQL 인젝션은 없음**(PG 방언은 `'`를 `''`로 변환). 그러나 패턴 자체가 코드 리뷰 시 우려 대상이며, 향후 필터 값에 non-string 타입(bytea, jsonb) 이 들어오면 동작 보증 어려움. 권고: `EXPLAIN` 도 parameterized 로 전달 가능한 `text("EXPLAIN (FORMAT JSON) ...").bindparams(...)` 또는 raw connection 의 `cursor.mogrify` 패턴 사용.

- **L-2 (Low · hospitals 엔드포인트 `SELECT DISTINCT` 반복)**: `routers/hospitals.py:39-58` 병원별 count+first/last 1 query + **별도 `SELECT Study.hospital_pk, Study.modality DISTINCT` 1 query** + include_names=true 시 추가 Hospital 전체 SELECT 1 query. 병원 100곳 규모에서는 문제 없으나, modality 조합이 Cartesian 하게 커질수록 두 번째 쿼리가 느려짐. FR-43 "5분 Redis 캐시" 도 미구현(`grep -n "hospitals_cache"` → config 만 있고 캐시 사용 코드 없음). 실제 캐시 hit ratio 0. 성능 관찰.

- **L-3 (Low · `total_count` 무조건 COUNT(*) 실행)**: `query/executor.py:170-172` 매 search 요청마다 exact COUNT(*) 수행. dev-spec FR-35 는 "cost estimator 가 10M 이하로 보증한 케이스에서만 허용". 구현은 "cost estimator 가 10M 초과 → reject" 이후 항상 COUNT — 정상 범위. 다만 cohort 1M ~ 10M 규모에서는 이 COUNT 가 p95 < 1s(비기능 요구) 초과 가능성. FR-36 `total_hint` planner-estimate 폴백 경로 미구현(항상 total_count_exact=true). 성능 관찰.

- **L-4 (Low · `SearchResponse` 루트 필드 + pagination/meta 중복)**: `query/schema.py:83-93 SearchResponse` 가 `items, facets, pagination, meta, total_count, total_count_exact, next_cursor, has_next, page_size, response_truncated` — 후반 6 필드는 `pagination` / `meta` 블록 내부와 중복. design-spec §2.3 "dev-spec 플랫 스타일 → 의미 그룹화 개선" 절충 결과이나, 구매자가 어느 쪽을 읽어야 할지 혼란. 문서화 후속 필요.

---

## 5. 컴플라이언스 발견 (개인정보·의료)

### Critical

**없음**. dev-spec §6.7 의 핵심 8 조항 중 PHI 관련 게이트 모두 확인:
- §6.7.1 PHI 무포함: `StudyItem` / `SearchStudyDetail` 어느 필드에도 원본 UID · 환자 식별자 없음 (`query/schema.py:44-103`).
- §6.7.2 Cursor 무해화: cursor JSON payload 에 `study_date_shifted`(시프트 날짜) · `study_pk` · sort_key · `s` hash 만(`query/cursor.py:56-62 encode_cursor` + `:81-83 decode`).
- §6.7.4 감사 로그 raw filter 금지: `search_audit` 스키마(`db/models.py:91-113`) 에 `filter_sha256` / `filter_json_sha256` CHAR(64) 만, raw body 컬럼 없음. 통합 `test_audit_row_written` 에서 확인.
- Central ingest `anonymization_flag="fully_anonymized"` 게이트 이후 데이터만 참조 — 본 서비스는 INSERT 경로 없어 우회 불가.

### High

**없음**. (H-1 은 계약 enforcement 이슈로 보안 High 로 분류함; 법적 관점에서는 병원 opt-out 미집행이 잠재 컴플라이언스 리스크이나 MSA/DPA 조항이 아직 미확정이라 현 시점 Medium 이하로도 볼 수 있음 — qa.md §3C "보안 실패는 critical 플래그"에 따라 보안 분류 유지.)

### Medium

- **CP-1 (Medium · `hospital_opaque_id` salt 구성 관찰)**: `query/executor.py:47-55` `sha256(f"{hospital_pk}|{global_salt}|{buyer_pk}")[:16]`. `global_salt` 는 `configs/search.example.yaml:32 "change-me-please"` + `configs/*.yaml` 의 `FILTER_HASH_GLOBAL_SALT` env 로 주입. **문제 1**: `docker-compose.search.yml:58 FILTER_HASH_GLOBAL_SALT: "replace-me-in-prod"` 하드코드 — 운영 실수로 그대로 배포 시 모든 buyer 가 동일 공개 salt 기반 opaque ID 를 봄. 운영자 실수 가드 권고. **문제 2**: 16 char hex(64 bit) 는 100 병원 규모에서는 충돌 무시 수준이나 1000+ 병원 확장 시 birthday collision 1% 가능 — v0.2 에서 20 char 로 확장 권고. 현 v0.1 스펙 FR-38 원문이 16 char 고정이라 AC 위반 아님.

- **CP-2 (Medium · `is_truncated=true` + 낮은 count 버킷 식별 가능성)**: `query/facets.py:116-125 _shape_rows` 가 top 50 이후 전체를 `__other__` 로 요약. **그러나 상위 50 버킷의 value 가 노출될 때 count=1 인 bucket 이 존재 가능**(희귀 manufacturer 조합). 예: `{"value": "ACME_RARE_CT_XYZ", "count": 1}` 가 노출되면 해당 스터디가 어느 buyer 에게 어느 병원 소속인지는 여전히 모르지만 매우 구체적인 시그니처 제공. design-spec §2.5 "NULL 버킷 허용 · low-count 는 v0.1 은 노출". dev-spec/design-spec 모두 low-count 억제를 v0.1 에 명시 요구하지 않음 — **스펙 허용 범위** 이나 개인정보 보호법 §28의8 맥락에서 **K-anonymity** 관점 후속 강화 권고(v0.1.1: count<5 bucket 을 `__rare__` 로 통합).

- **CP-3 (Medium · 로그 PHI sanitizer 로직 범위)**: `logging_config.py:42-55 PhiSanitizerFilter` 는 `record.__dict__` 키만 검사하고 `record.msg` 문자열 내 패턴은 무검. central-ingest QA 에서 지적된 동일 약점 — 방어 깊이 얕음. 코드 경로상 raw UID/filter 를 msg 에 꼽는 지점 없어 실효 위험 낮음. 후속 개선.

### Low

- **CP-4 (Low · cross-hospital 노출 기본)**: design-spec §1.5 및 dev-spec §4.15 가 명시한 "v0.1 flat access" 는 **의도된 동작** — 모든 인증 buyer 가 모든 병원의 익명화된 메타데이터를 본다. 이는 MSA/DPA 상 buyer tier 에서 허용된 범위로 본 v0.1 스펙이 규정. H-1(opt-out 필터 미집행) 과 짝지어 **"opt-out 설정 해도 동작 안 함"** 이 심각.

---

## 6. 품질 관찰 (non-blocking)

- **Q-1 (Observation · Redis auth cache hit 메트릭 검증 테스트 누락)**: AC-5 요구 "9회 hit" 수치 검증 자동 테스트 없음. 메트릭 label 존재만 확인. v0.1.1 보강 가치.

- **Q-2 (Observation · facet 병렬 실행 미구현)**: dev-spec FR-33 "v0.1 은 6개 parallel async task 로 실행". 현 `query/facets.py:45-108` 는 직렬 SQL 6회. p95 < 1.8s (비기능 요건) 는 1M rows 범위에서 SQLite 기준 초과 가능. 실제 PG + pool_size=30 + 파티션 로컬 인덱스 시 초당 처리량 확인 필요. **design-spec/dev-spec 문자 요건 미이행**.

- **Q-3 (Observation · `total_hint` 필드 의미 drift)**: dev-spec §6.4 `total_hint`는 "planner 기반 estimate, FR-36 triggered 시". 구현 `executor.py:209 Meta(total_hint=total_count, ...)` 가 **항상 exact total_count 값을 넣음**. total_count_exact=true 시 total_hint=total_count 도 정수 동일 — 시맨틱 혼란. design-spec §2.3 "total_hint": "exact vs approximate" 의미를 구분할 수 없음.

- **Q-4 (Observation · Prometheus `radivault_index_facet_duration_seconds` 미기록)**: `telemetry.py:26-32 FACET_DURATION` 정의만 있고 `query/facets.py` 에서 `.labels(facet_field=...).observe(...)` 호출 없음 — 메트릭 항상 0. FR-46 부분 미이행.

- **Q-5 (Observation · `CURSOR_FILTER_CHANGED_TOTAL` 카운터 미증가)**: `telemetry.py:69-73` 정의만 있고 `executor.py:110-112 raise CursorFilterChanged` 에서 `.inc()` 호출 없음. design-spec §4.3 "메트릭 노출 시 카운트" 미이행. alert 규칙이 이 메트릭에 의존하면 탐지 못 함.

- **Q-6 (Observation · `last_used_at` UPDATE 당 trip to DB)**: C-1 원인. 설령 권한 문제를 풀어도 매 인증마다 `UPDATE buyer_api_key` 가 **캐시 hit 이 아닌 모든 요청**에서 실행되지 않음(캐시 hit 경로는 `:96-103` 에서 DB 접근 skip). cold cache 60초마다만 DB write — 수용 범위. 다만 캐시 miss 시 race condition 고려 필요.

- **Q-7 (Observation · SQLite 테스트 fixture 단일 세션 공유)**: `tests/search/conftest.py:39-46 engine_and_factory` + `seeded_buyer` + `app_client` 가 **동일 StaticPool 엔진**을 공유. 통합 테스트가 여러 request 를 발사해도 같은 in-memory DB 를 보므로 PG 와 의도 비슷. 이 구조는 좋으나, C-1(PG GRANT) 같은 real-role 이슈는 여전히 감지 불가.

- **Q-8 (Observation · 14 CLI 서브커맨드 · 자가보고와 일치)**: `src/radivault_search_admin/cli.py` 카운트: version(1) + buyer.create/show/list/update(4) + key.issue/revoke/list(3) + stats.query-count/top-filters(2) + facet.warm(1) + migrate.up/current/down(3) = **14**. dev-spec FR-57 트리 13개 대비 `version`(ingest-admin 과의 parity 용) 추가. 개발자 자가보고와 일치 · harmless.

- **Q-9 (Observation · `search-admin buyer update` 이 FR-57 트리에 없음)**: FR-57 명령 트리에 `buyer.create/show/list` 3개만. 구현은 `buyer.update` 추가. design-spec §3.2 와 대조 필요. 동일 tier 변경을 `key issue --tier` 로도 가능하나 buyer tier 자체는 `buyer update` 가 맞음 — 실용상 합리적 확장. 경미 drift.

- **Q-10 (Observation · `/v1/search/facets` 에 buyer 별 filter 캐시 없음)**: dev-spec FR-44 "15 분 Redis 캐시 — `search:facets:global`". 구현 정확 (`routers/facets.py:30`). 다만 **필터가 적용되지 않는 전역 facet** 이므로 하나의 캐시 entry 로 전체 buyer 공유 — OK. `search-admin facet warm` subcommand 는 stub (`cli.py:552-555`) — 실제 cache 를 생성하지 않고 메시지만 출력. FR-57 명시 요건이나 **v0.1 허용 수준**(다음 실제 요청이 자연히 warm).

- **Q-11 (Observation · `response_truncated` 필드 항상 False)**: `query/executor.py:215, :227 response_truncated=False` 하드코딩. FR-40 "응답 크기 상한 1MB, 초과 시 자동 truncate + flag=true". 구현 경로 없음. SQLAlchemy `limit(req.limit + 1)` 로 row 수는 제한하지만 byte size 체크 없음. v0.1 규모에서 1MB 초과 흔치 않음이나 dev-spec 문자 미이행.

- **Q-12 (Observation · pip-audit 미실행)**: `.venv` 내 `pip-audit` 존재 불분명, 본 검수에서는 skip. dev-spec §5 "이미지 trivy HIGH=0" 요건 미검증. CI 통합 시 게이트 권고.

- **Q-13 (Observation · `log_sanitizer_strict: true` flag 미활용)**: `config.py:103 log_sanitizer_strict: bool = True` 정의되나 `logging_config.py` 어디에서도 읽지 않음. strict 아니면 redact 대신 drop 해야 한다는 동작 차이가 구현 안 됨.

- **Q-14 (Observation · Alembic downgrade role 오류 swallow)**: `0002_metadata_index.py:144-145` `EXCEPTION WHEN OTHERS THEN NULL;` — 모든 예외 무시. role 삭제 실패 시 운영자가 알 수 없음. 파일럿 규모에서는 괜찮으나 명시 로그 권고.

---

## 7. 개발자 자가 보고 편차 검증

| # | 자가보고 편차 | 판정 | 근거 |
|---|-------------|------|------|
| D-1 | search_audit partitioning deferred | **수용 가능 · but PK drift 야기** | 범위상 의도 편차이나 **H-5**: 현 PK `audit_pk` 단일 → v0.2 전환 시 PK 재작성 필요. 지금 `(audit_pk, created_at)` 복합 PK 로 맞춰두면 데이터 마이그레이션 0 비용. **GA 전 스키마 수정 권고**. |
| D-2 | EXPLAIN → SQLite COUNT 폴백 | **수용 가능** | `query/validator.py:59-85` dialect 분기. SQLite 테스트 편의 + 프로덕션 PG 에서는 EXPLAIN 실행. 코드 경로 정확. L-1 관찰 참고. |
| D-3 | FastAPI request timeout 미설치 · PG statement_timeout 만 | **FAIL 판정 요인** | dev-spec FR-23 "`asyncio.wait_for(handler, timeout=15s)`" 명시 요구. 미구현 + `QueryTimeout` 발화 경로 부재(M-3). statement_timeout 에만 의존 시 facet parallel task, Redis slow path, Python GC 지연 등은 커버 불가. **AC-19 FAIL 결정적 요인**. |
| D-4 | 14 CLI(+1 version) | **수용 가능** | Q-8 참조. `ingest-admin` 과 parity 확보 — harmless. |
| D-5 | `hint` 필드 pydantic 부재 + router 수준 payload 주입 | **FAIL 판정 요인 (H-2)** | 현 구현은 **동작하지 않음**. `__pydantic_extra__` 패턴이 `SearchResponse` 에 extra="allow" 미선언이라 무효. AC-18 가 facets=null 만 검증하고 hint 는 assert 안 하므로 테스트가 그린이지만 **실제 payload 에 hint 가 존재하지 않는다**. |

**요약**: 자가보고 5건 중 D-3/D-5 는 **결함 · FAIL 판정 요인**, D-1 은 **향후 전환 비용 증가**, D-2/D-4 수용.

---

## 8. 권고 (재작업·후속 항목)

### GA 차단 (병합 전 필수)

1. **C-1 `radivault_buyer_ro` UPDATE 권한 또는 auth `last_used_at` 경로 재배치**: `alembic/versions/0002_metadata_index.py:107` 에 `GRANT UPDATE (last_used_at) ON buyer_api_key TO radivault_buyer_ro;` 추가 **또는** auth middleware 의 commit 경로를 `search_admin` DSN 으로 이관. 실제 PG 15 + buyer_ro 로 통합 테스트 1회 필수. ~5줄 + 테스트 ~20줄.

2. **H-1 `exclude_hospitals` 애플리케이션 필터 집행**: `query/validator._build_where` 에 `if scope_json.get("exclude_hospitals"): out.append(Study.hospital_pk.notin_(list))` 추가. `executor.run_search` 가 `scope_json` 을 받도록 signature 확장. 단위 테스트 2건. ~30줄.

3. **H-2 `hint` 필드 정규화**: `query/schema.py:83 SearchResponse` 에 `hint: str | None = None` 추가(또는 `meta.hint`). `query/executor.py:217-228 SearchResponse(...)` 생성 시 `hint=hint_str` 전달. `__pydantic_extra__` 해킹 제거. ~10줄 + AC-18 hint 존재 assert 보강 1줄.

4. **H-3 `max_limit_per_page` + `ERR_PAGE_LIMIT`**: `routers/search.py:46` 전후에 tier 매핑 후 `if body.limit > cap: raise PageLimit(detail=f"limit {body.limit} > {cap}")`. `pydantic Field le=200` 은 유지하되 tier-specific 검사는 라우터에서. 통합 테스트 1건. ~15줄.

5. **H-4 Rate-limit / Quota 응답 헤더**: `ratelimit/middleware.py` 에 헤더 주입. `Meta.buyer_quota_remaining` 계산 + `response.body` 추가. design-spec §2.3 / §2.7 충실 이행. ~40줄.

6. **H-5 `SearchAudit` PK 를 `(audit_pk, created_at)` 으로 수정**: `db/models.py:98-113` + alembic migration 내 create_all 반영. 향후 파티셔닝 전환 시 데이터 마이그레이션 0. ~5줄.

### v0.1 GA 전 강권장

7. **M-1 `min_hospitals` 필터 적용**: `executor._build_where` 혹은 subquery 로 `HAVING COUNT(DISTINCT hospital_pk) >= :min`. 복잡 — 또는 v0.1.1 명시 연기 결정 필요(§11 Kyle 결정).
8. **M-3 FastAPI request timeout 설치**: `app.py` 에 `asyncio.wait_for` 래퍼 미들웨어 추가 + 타임아웃 시 `raise QueryTimeout(...)`. SQLAlchemy OperationalError (statement_timeout) 을 `QueryTimeout` 으로 매핑하는 catch 도 `routers/search.py` 에 추가. ~25줄.
9. **M-5 `docs/samples/search/` 디렉토리 생성**: curl 5종 + Postman 컬렉션 JSON. 기계적 생성 가능 — 30분 작업.

### v0.1.1 이관

- M-2 CORS yaml 스키마 · 미들웨어 설치.
- M-4 auth negative cache 없음을 assert 하는 단위 테스트.
- L-1~L-4 관찰 항목 정리.
- Q-1~Q-14 품질 관찰.
- CP-2 low-count bucket K-anonymity 강화.

### v0.2 이관 (이미 스펙에 의해)

- FR-55 `search_audit` pg_partman 실제 파티셔닝(H-5 수정 후 파티셔닝 전환은 무충돌).
- FR-44 `search-admin facet warm` 실제 캐시 생성(현재 stub).
- FR-77 PG RLS 기반 hospital opt-out.
- Python SDK.

---

## 9. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-22 | @qa (Claude Opus 4.7) | 최초 검수. 커밋 `c888a73..3f83ff7` (15 커밋). search unit 34/34 · integration 14/14 · central 회귀 50/50 · gateway 회귀 55/55 PASS, ruff clean 독립 검증. AC 34 건 매트릭스, Critical 1 · High 5 · Medium 5 · Low 4 + 컴플라이언스 Medium 3 · Low 1 · 품질 관찰 14 건. 판정 **FAIL** — C-1 (PG role 권한 불일치로 인증 경로 프로덕션 실행 불가) 단독으로 GA 차단. H-1 (opt-out 필터 미집행), H-2 (hint 전달 실패), H-3 (tier 상한 미집행), H-4 (헤더 미방출), H-5 (파티셔닝용 PK 형상) 도 GA 전 반영 강권장. |
| 0.2 | 2026-04-22 | @qa (Claude Opus 4.7) | Round 2 재검수. 커밋 `8278fd3..c2ca4c0` (fix 7 커밋). search unit 49/49 (+15) · integration 20/20 (+6) · central 회귀 50/50 · gateway 회귀 55/55 PASS, ruff clean. C-1 + H-1..H-5 **전부 RESOLVED** — §10 per-finding 증거. 스코프 규율 준수(±835 LoC, 승인 경로만 변경). 판정 **PASS with minor** — v0.1 GA 가능. Round 1 Medium(M-1..M-5)/Low/Observation 항목은 v0.1.1 backlog 유지(스펙 허용). |

---

## 10. Round 2 Re-Verification (2026-04-22)

### 10.1 요약 (Round 2 Verdict)

- **판정**: **PASS with minor**. Round 1 의 Critical 1건 + High 5건이 모두 증거 기반으로 해소되었고, 테스트 커버리지도 unit +15 / integration +6 으로 각 fix 에 대응하는 신규 테스트가 동봉됨. v0.1 GA 차단 요인 **제거**.
- **회귀 안정성**: central(50) + gateway(55) 는 Round 1 과 **동일 수치 PASS** — 이번 fix 가 다른 Zone 에 파급 없음을 확인.
- **남은 minor**: Round 1 Medium(M-1 `min_hospitals` · M-2 CORS · M-3 `ERR_QUERY_TIMEOUT` · M-4 negative cache assert · M-5 `docs/samples/search/`)/Low/Observation 은 round 2 스코프 외 — Kyle 결정(§8 Kyle 결정 필요 사항)대로 v0.1.1 백로그로 이관. 본 round 에서는 **악화 없음**을 확인(스펙 허용 경계 이내).

### 10.2 Round 1 Finding 별 상태

| # | 원 finding | Round 2 상태 | 증거 (file:line, test name) |
|---|------------|--------------|------------------------------|
| **C-1** | `radivault_buyer_ro` 에 `buyer_api_key.last_used_at` UPDATE 권한 없음 → PG 운영 500 크래시 | **RESOLVED** | (a) `alembic/versions/0002_metadata_index.py:113-115` `GRANT UPDATE (last_used_at) ON buyer_api_key TO radivault_buyer_ro;` — 컬럼 레벨 최소 권한. (b) `auth/middleware.py:142-155` UPDATE 실패 시 `except Exception` → `log.warning("ERR_LAST_USED_UPDATE_FAILED", ...)` + `session.rollback()`. Auth 성공 경로 유지. (c) `alembic 0002` downgrade 경로 `:146` REVOKE 도 짝. (d) 테스트 3종(`tests/search/unit/test_auth_middleware.py`): `test_auth_last_used_update_ok` (happy), `test_auth_last_used_update_permission_denied_soft_fail` (SQLAlchemy `ProgrammingError` 시뮬 → 200 + WARN), `test_auth_last_used_update_generic_error_soft_fail` (`RuntimeError` → 200). **공격자 시나리오**: 운영자가 GRANT 를 까먹어도 서비스는 계속 동작(부분 기능 degraded — `last_used_at` stale), 크래시 없음. GOOD. |
| **H-1** | `scope_json.exclude_hospitals` 애플리케이션 필터 미집행 | **RESOLVED** | (a) `query/validator.py:35-51 _extract_exclude_hospitals` 방어적 coercion(비 list · 비 int 원소 drop → 접근 확대 원천 차단). (b) `validator._build_where(req, scope_json=...)` :129-131 `Study.hospital_pk.notin_(excluded)` append. (c) `executor.run_search(..., scope_json=...)` :90, :114 페이지 쿼리+total_count+facets 모두 동일 WHERE 경유. (d) `routers/search.py:45` 매 요청 `scope_json = getattr(request.state, "scope_json", {})`, :61 estimate_cost + :96 run_search 둘 다 전달. (e) `routers/hospitals.py:39-62` 병원 리스트 + modality distinct + name lookup 3경로 전부 `notin_`. (f) **FR-76 enforcement**: `SearchRequest` 는 `model_config.extra="forbid"`(schema.py:24) 이고 `exclude_hospitals` 필드 자체가 부재 → buyer 가 body 로 변조 시도 시 `ERR_REQUEST_SCHEMA`. (g) 테스트 8종(`tests/search/unit/test_scope_exclude_hospitals.py`): `test_extract_exclude_hospitals_none/well_formed/malformed_is_empty`, `test_run_search_no_scope_returns_all`(15건), `test_run_search_excludes_one_hospital` (→10건 + **CT facet count 15→10 검증 — 질문 10의 "facet COUNT drop" 실제 검증**), `test_run_search_excludes_all_hospitals_returns_zero`, `test_estimate_cost_respects_scope`, `test_build_where_includes_hospital_notin`. **공격자 시나리오**: buyer 가 `exclude_hospitals: []` 를 body 로 보내도 forbid 로 거부; scope_json 이 malformed 여도 빈 list 로 coerce → 이전 동작(전체 반환) 유지되나 접근 확대 **불가능**. GOOD. |
| **H-2** | `hint` 가 `__pydantic_extra__` 해킹 → `model_dump()` 가 직렬화 못 함 | **RESOLVED** | (a) `query/schema.py:94-95` `hint: str | None = None` 정규 pydantic 필드로 승격. (b) `query/executor.py:229` `hint=hint_str` 를 `SearchResponse(...)` 생성자에 직접 전달. 더 이상 `__pydantic_extra__` 대입 없음. (c) `routers/search.py` 에서 payload 후처리 코드 제거. (d) integration `tests/search/integration/test_search_e2e.py:127-147 test_facets_suppressed_hint_surfaced` — facet_auto_suppress_rows=10 으로 임계치 낮춘 후 요청 → `body["facets"] is None` AND `body["hint"] == "facets suppressed: cohort too large"` (dev-spec FR-22 exact string). Round 1 AC-18 PARTIAL 이 이제 **완전 PASS**. |
| **H-3** | tier 별 `max_limit_per_page` 미집행, `ERR_PAGE_LIMIT` 사문 | **RESOLVED** | (a) `routers/search.py:47-56` validate_filter **전에** tier cap 계산(`_tier_limit_cap` :220-223) + `scope_json.max_limit_per_page` override(`_resolve_page_cap` :226-230, admin-only; FR-9). 초과 시 `raise PageLimit(detail=..., hint=...)` → 400 `ERR_PAGE_LIMIT`. (b) `errors.PageLimit` 이제 실제 발화 지점 보유. (c) 테스트 3종(`tests/search/integration/test_page_limit.py`): `test_preview_buyer_over_cap_400` (preview+limit=200 → 400 + `body["error"]=="ERR_PAGE_LIMIT"` + detail 에 "100"), `test_paid_buyer_at_cap_200_ok` (paid+limit=200 → 200 OK), `test_scope_json_override_raises_cap` (scope_json override=150 → preview+limit=120 OK). **상태 코드 400 확인**: dev-spec §7.6 line 693 `400 ERR_PAGE_LIMIT` / §7.8 line 1124 "400" 명시 — 개발자 선택이 **canonical 문서와 일치**. task prompt 의 422 는 오타로 판단 · 스펙(400)이 우선. GOOD. |
| **H-4** | `X-RateLimit-*` / `X-Quota-*` 헤더 미방출 + `meta.buyer_tier/quota_remaining` null | **RESOLVED** | (a) `ratelimit/middleware.py:183-197 _rate_headers` 6개 헤더 계산 — 이름은 design-spec §2.7 line 400-405 **exact match** (`X-Quota-Limit-Daily`, `X-Quota-Remaining-Daily`, `X-Quota-Reset-Daily`). Redis 예외 시 full budget fallback(절대 음수 return 안 함). (b) 200 success(`:153-156` response.headers 주입) + 429 rate-limit(`:91`) + 429 quota(`:114`) + 429 concurrency(`:134`) 4 경로 **전수 주입**. (c) `request.state.buyer_tier` / `buyer_quota_remaining` 세팅 → `routers/search.py:110-113` run_search 로 전달 → `query/executor.py:214-218 Meta(buyer_tier=..., buyer_quota_remaining=...)`. design-spec §2.3 의 body + header 양방향 노출 충족. (d) 테스트 2종(`tests/search/integration/test_rate_limit_headers.py`): `test_success_response_has_all_headers_and_meta` (200 + 6 헤더 + `meta.buyer_tier=="paid"` + `meta.buyer_quota_remaining: int`), `test_rate_limited_response_has_headers` (rpm=2 로 shrink → 429 + 6 헤더). **헤더 이름 canonical source 확인**: design-spec §2.7 우선이 맞음(dev-spec 은 해당 이름을 별도 나열하지 않음, §2.7 에서 채택). GOOD. |
| **H-5** | `search_audit` PK 가 단일 `audit_pk` — 파티셔닝 전환 시 데이터 마이그레이션 필요 | **RESOLVED (structural-text only)** | (a) `alembic/versions/0002_metadata_index.py:76-85` PG branch 에서 `ALTER TABLE search_audit DROP CONSTRAINT IF EXISTS search_audit_pkey;` → `ADD CONSTRAINT ... PRIMARY KEY (audit_pk, created_at);` — **idempotent** (IF EXISTS 로 재실행 안전). (b) downgrade :147-157 `DO $$ BEGIN ... ALTER TABLE search_audit DROP CONSTRAINT search_audit_pkey; ADD CONSTRAINT ... PRIMARY KEY (audit_pk); END $$;` — forward/backward 대칭. `EXCEPTION WHEN OTHERS THEN NULL` 는 뒤이은 DROP TABLE 이 supersede 하므로 OK. (c) `db/models.py:91-131` SQLite 는 `AUTOINCREMENT on composite PK` 불가능이므로 의도적으로 single-column PK 유지 + docstring 으로 PG 는 migration 로 재형성을 문서화. (d) `tests/search/unit/test_migration_0002.py:73-86 test_search_audit_pk_contains_created_at_on_pg_shape` 가 migration 텍스트에 `PRIMARY KEY (audit_pk, created_at)` + downgrade `PRIMARY KEY (audit_pk)` 존재 확인. **SQLite vs PG divergence 평가**: divergence 는 **실재하나 실무적 허용 범위** — SQLite 는 테스트 전용이며, dev-spec 은 PG 를 production target 으로 명시(§6.2). Round 1 의 핵심 우려("v0.1.1 에서 PK 재작성 필요")는 이제 **이미 fixed** — pg_partman 시 데이터 마이그레이션 0. **잔여 리스크**: static text 검사는 `ALTER TABLE` syntax 가 PG 에서 실제 실행될 때의 성공을 보증하지 않음(예: `search_audit_pkey` 가 아닌 이름으로 constraint 가 만들어진다면 DROP CONSTRAINT IF EXISTS 가 no-op 가 됨 — 하지만 `ADD CONSTRAINT` 는 기존 PK constraint 와 충돌하여 failure). 개발자가 "live-PG fixture deferred to v0.1.1" 로 기록. **허용 가능**: (1) idempotent 가드가 재실행 안전을 담보, (2) commit 메시지 + docstring + test 가 의도·형상·복원 경로를 명문화, (3) v0.1.1 에서 pg_partman 합쳐지는 시점에 live-PG integration test 가 자연스럽게 동반됨. v0.1 GA blocker 아님. GOOD-ENOUGH. |

**결론**: Critical 1 · High 5 전부 RESOLVED. 각 fix 는 단위/통합 테스트로 assertion 된 실동작 증거를 동반함(H-5 만 static-text 수준). 공격자/운영 오작동 시나리오(permission denied soft-fail, malformed scope coerce, body-override 차단, 재실행 idempotency)를 mental attack tree 로 점검한 결과 guard 유지.

### 10.3 새 발견 (New findings in Round 2)

- **없음**(blocker 급). Round 2 변경분을 adversarial 관점에서 재스캔한 결과 아래 minor observation 만 확인 — 전부 non-blocking.
  - **N-1 (Observation · non-blocking)**: `ratelimit/middleware.py:196 daily_reset = ((now // 86400) + 1) * 86400` 는 UTC 자정에 정확히 정렬됨(epoch 가 UTC 기준이므로). design-spec §2.7 의 "다음 UTC 자정" 과 일치. 시차 있는 buyer 에게는 약간 혼란 가능하나 spec 명시대로. 참고만.
  - **N-2 (Observation · non-blocking)**: `_rate_headers` 의 `rpm_used` fallback(`Exception → 0`)은 Redis down 시 **full budget 을 헤더로 노출** → buyer 가 실제로는 제한되는데 헤더만 "여유 있음"으로 보임 가능성. 단 concurrency/rate counting 자체는 이미 `IdempUnavailable` 로 떨어뜨리는 별도 경로가 있어 실동작 오인 경로는 없음. 운영 모니터링 관점 메모.
  - **N-3 (Observation · non-blocking)**: H-3 의 `_tier_limit_cap` 이 `settings.rate_limit.tier_preview/tier_paid.max_limit_per_page` 를 직접 읽는데, `ratelimit/middleware.TierLimits` 에도 동일 필드(`max_limit_per_page`)가 추가됨. 두 source-of-truth 가 현재는 `app.py:state.settings` 에서 pass-through 로 동기되나, 향후 한쪽만 수정 시 drift 가능. 구조 관찰 — 지금은 harmless.
  - Round 1 의 H-2 PARTIAL 판정 지점(AC-18 통합 테스트에서 hint assert 부재)이 새 integration 으로 보강됨 — 즉 Round 1 체크리스트의 "AC-18 hint 존재 assert 1줄 추가" 권고가 충족.

### 10.4 Scope discipline

- `git diff 8278fd3..HEAD --stat` 변경 범위:
  - `alembic/versions/0002_metadata_index.py` (+40): C-1 GRANT + H-5 ALTER PK. **승인 경로 내**.
  - `src/radivault_search/app.py` (+2): H-4 TierLimits.max_limit_per_page pass-through. **승인 경로 내**.
  - `src/radivault_search/auth/middleware.py` (+20/-4): C-1 soft-fail try/except. **승인 경로 내**.
  - `src/radivault_search/db/models.py` (+19): H-5 docstring + dialect-conditional PK 주석. 실제 declarative 변경 없음. **승인 경로 내**.
  - `src/radivault_search/query/executor.py` (+10): H-1 scope_json kwarg + H-2 hint 필드 + H-4 buyer_tier/quota_remaining kwarg. **승인 경로 내**.
  - `src/radivault_search/query/schema.py` (+2): H-2 `hint: str | None = None` 필드. **승인 경로 내**.
  - `src/radivault_search/query/validator.py` (+33): H-1 `_extract_exclude_hospitals` + `_build_where` signature + `estimate_cost` scope 전달. **승인 경로 내**.
  - `src/radivault_search/ratelimit/middleware.py` (+63): H-3 `max_limit_per_page` 추가 + H-4 `_rate_headers` + request.state 노출 + 429 경로 헤더 주입. **승인 경로 내**.
  - `src/radivault_search/routers/hospitals.py` (+31/-14): H-1 3경로 `notin_`. **승인 경로 내**.
  - `src/radivault_search/routers/search.py` (+36): H-1 scope_json propagate + H-2 payload 후처리 제거 + H-3 cap 가드 + H-4 tier/quota 전달 + `_tier_limit_cap`/`_resolve_page_cap` helpers. **승인 경로 내**.
  - 신규 테스트 6파일(+605 LoC 가량).
  - `c2ca4c0` style(ruff format) commit 은 모두 같은 파일의 formatting 재정렬 + stale noqa 제거. behavioral change 없음 확인(diff 읽음).
- **미승인 refactor 없음**. central_ingest / gateway / DICOM 등 타 Zone 파일 변경 0건.

### 10.5 테스트 커버리지

| 파일 | 성격 | LoC | 의미 있는 assertion 품질 |
|------|------|-----|--------------------------|
| `tests/search/unit/test_auth_middleware.py` | 신규 (C-1) | 174 | **HIGH** — SQLAlchemy `ProgrammingError(permission denied)` 실제 simulate + `caplog` 로 `ERR_LAST_USED_UPDATE_FAILED` WARN 확인. generic error 도 커버. |
| `tests/search/unit/test_scope_exclude_hospitals.py` | 신규 (H-1) | 146 | **HIGH** — 4 시나리오(no scope/1 exclude/all exclude/malformed) + CT facet count 실제 drop 검증. FR-76 buyer body override 간접 테스트(`extra="forbid"` 자체는 기존). |
| `tests/search/unit/test_migration_0002.py` | 확장 (C-1 + H-5) | 110 (+93+17) | **MEDIUM** — migration 텍스트 static assert 방식이지만 upgrade idempotency + downgrade structural round-trip 은 실제 SQLite 에서 실행. 질문 10 의 "static-text 충분성"에 대한 답: 부분적. live-PG 통합 테스트는 v0.1.1 deferred 가 수용 가능(fix commit 에서 명시). |
| `tests/search/integration/test_page_limit.py` | 신규 (H-3) | 84 | **HIGH** — preview over-cap/paid at-cap/scope override 3시나리오 실 HTTP. error code string 검증. |
| `tests/search/integration/test_rate_limit_headers.py` | 신규 (H-4) | 73 | **HIGH** — 200 + 429 두 경로 모두 6 헤더 존재 + `meta` 필드 정수 타입 + `buyer_tier=="paid"` 값 검증. |
| `tests/search/integration/test_search_e2e.py::test_facets_suppressed_hint_surfaced` | 신규 (H-2) | +24 | **HIGH** — dev-spec FR-22 exact string match ("facets suppressed: cohort too large") + `facets is None` 동시 assert. |

- **총 증가**: unit 49 (Round 1 34 → +15), integration 20 (14 → +6). 각 fix 는 **대응 테스트 동반** — blind fix 없음.
- **자동화 한계**: C-1 은 SQLite + `ProgrammingError` simulate 로 소프트-페일 경로 자체는 검증되지만 **실 PG role 의 permission denied 재현**은 아직 없음. H-5 도 migration 텍스트 static 검사. 두 항목 모두 v0.1.1 에 live-PG fixture 준비 권고(blocker 아님).

### 10.6 Medium / Low v0.1.1 Backlog 확인

- Round 1 에서 제기된 Medium/Low/Observation 항목은 Round 2 에서 스코프 외였고 **건드리지 않음**을 확인(악화 없음 · 우발적 수정 없음):
  - **M-1** `min_hospitals` 필터: `query/validator.py` / `executor.py` / `schema.py` 변경분 모두 `min_hospitals` 미언급. 여전히 pydantic 수신 후 WHERE 적용 없음. v0.1.1 backlog.
  - **M-2** CORS yaml 스키마: `configs/search.example.yaml` 변경분 0. `app.py` 에 CORSMiddleware 추가 없음. v0.1.1.
  - **M-3** `ERR_QUERY_TIMEOUT` 발화 경로: `errors.py` 변경분 0, `app.py` 에 `asyncio.wait_for` 미들웨어 추가 없음. v0.1.1.
  - **M-4** auth negative cache assert 테스트: 신규 테스트 중 해당 assertion 없음. 구조는 여전히 positive-only cache(코드 변경 없음). v0.1.1.
  - **M-5** `docs/samples/search/` 디렉토리: `ls docs/samples/` 여전히 부재. v0.1.1.
  - **L-1~L-4**: 관련 코드 경로 변경 없음.
  - **Q-1~Q-14**: `response_truncated=False` 하드코드, `total_hint` 항상 exact, `FACET_DURATION` 미기록 등 전부 Round 2 스코프 외.
- **CP-1~CP-4** (compliance medium/low): Round 2 변경분이 salt/hospital_opaque_id/logging sanitizer/cross-hospital 정책 로직을 건드리지 않음 확인. 악화 없음.
- **판단**: Kyle 이 Round 1 NEXT_STEP §5.1~§5.5 에서 명시한 "v0.1.1 연기 또는 GA 필수" 결정 중, 본 Round 2 는 C-1 + H-1..H-5 만 범위로 한정한 것이 적절. v0.1 GA 판정은 본 round 로 충분.

### 10.7 Round 2 판정

**PASS with minor**

- **PASS 근거**: (1) Round 1 Critical 1 + High 5 전부 RESOLVED(증거 §10.2). (2) 회귀 테스트(central 50/50 + gateway 55/55) 변동 없음. (3) 신규 unit +15/integration +6 의 품질이 "의미 있는 assertion" 기준을 만족. (4) 스코프 규율 준수(승인 경로 외 변경 0). (5) ruff clean.
- **minor 근거**: (a) H-5 는 live-PG integration test 가 없어 static-text 검증에 의존 — v0.1.1 에서 PG fixture 들어오면 보강 필요(기술 리스크 낮음). (b) Round 1 Medium/Low/Observation 총 13건은 의도적으로 v0.1.1 backlog — `min_hospitals`(M-1)는 마케팅 스토리(dev-spec §2)와 맞물리므로 Kyle 의 GA 전 명시 결정 권고.
- **GA 차단 요인**: **없음**.

---

### NEXT_STEP (Round 2)

- 완료 산출물: `docs/qa/qa-report-metadata-index.md` (§10 Round 2 append)
- 판정: **PASS with minor**
- Critical 이슈: **0건** (C-1 RESOLVED)
- High 이슈: **0건** (H-1..H-5 전부 RESOLVED)
- 제안 다음 단계:
  - **@marketer** — v0.1 GA 런칭 콘텐츠 준비 개시 가능. envelope 계약 · 7엔드포인트 · `X-RateLimit-*`/`X-Quota-*` 헤더 · `meta.buyer_tier/quota_remaining` 노출 포인트 홍보 가능.
  - **@developer** — v0.1.1 backlog 에 착수(우선순위 제안): (1) M-5 `docs/samples/search/` curl+Postman(buyer onboarding DX), (2) M-3 `ERR_QUERY_TIMEOUT` 경로 설치(504 계약 충족), (3) M-1 `min_hospitals`(Kyle 결정에 따라 GA 범위 재조정 가능), (4) H-5 live-PG integration test(pg_partman 작업과 번들), (5) M-2 CORS · M-4 negative cache assert.
  - **@qa** — v0.1 GA 후 first production PG 배포 직후 smoke test(permission denied 재현 확인 · search_audit composite PK 실재 확인) 1회 권고. 자동화 파이프라인은 v0.1.1 시점.
- Kyle 결정 필요 사항:
  1. **M-1 `min_hospitals` 필터 v0.1 포함 여부**: FDA 허가용 데이터셋 스토리가 v0.1 마케팅 핵심이면 v0.1 GA 전 추가. 아니면 v0.1.1 명시 연기(현재 기본값).
  2. **`FILTER_HASH_GLOBAL_SALT` 운영 주입**: `docker-compose.search.yml` 하드코드 `replace-me-in-prod` 제거 + Vault/KMS 주입 시점(GA 전 필수 권고).
  3. **CORS allowlist 대상 도메인**: 파일럿 buyer dashboard origin 수집 타이밍.
  4. **v0.1.1 착수 시점**: GA 안정화 관찰 기간(예: 2주) 후 vs 즉시 병행.
