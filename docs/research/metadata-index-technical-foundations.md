# Metadata Index — 기술적 기반 리서치

## 0. 메타

- **Status**: Draft v0.1
- **작성일**: 2026-04-22
- **작성자**: @researcher (Claude Opus 4.7)
- **근거 요청**: 메인 세션 — Phase 2 "Planning" 진입, Metadata Index v0.1 dev-spec 작성 전 **구매자(Buyer)-facing** 기술 선택 근거 정리
- **feature-slug**: `metadata-index`
- **선행 문서 (중복 회피 위해 상호 참조)**
  - [`docs/prd.md` §4.2 Metadata Index, §4.3 Buyer Portal](../prd.md)
  - [`docs/ARCHITECTURE.md` §4 Zone 2, §5 Zone 3](../ARCHITECTURE.md)
  - [`docs/research/k-meddata-research-summary.md` §3 경쟁사, §6 3-Zone 구조](./k-meddata-research-summary.md)
  - [`docs/research/central-ingest-technical-foundations.md`](./central-ingest-technical-foundations.md) — **Ingest 측 기술 근거. 본 문서는 Buyer-side 전용, Ingest 재기술 금지**
  - [`docs/specs/dev-spec-central-ingest.md` §6 데이터 모델](../specs/dev-spec-central-ingest.md) — **이미 존재하는 SQL 스키마를 그대로 상속**
  - [`docs/specs/design-spec-central-ingest.md` §2 API envelope, §5 error taxonomy](../specs/design-spec-central-ingest.md) — **envelope·에러 코드 네임스페이스 계승**
  - `src/radivault_central/db/models.py` — 실제 SQLAlchemy ORM 소스
- **PRD/ARCHITECTURE 영향**:
  - PRD §4.2 "코호트 검색 API"의 HTTP 계약·인증·쿼터가 본 문서에서 구체화됨. dev-spec 확정 후 PRD 반영 권장.
  - ARCHITECTURE §5.2 "Developer API & SDK"의 Python SDK 제공 시점 결정이 본 문서 §7에 의존.
- **스코프**: Metadata Index v0.1 = **버이어-facing 검색 API 1개 서비스**. Zone 2 내부의 NLP 라벨링 엔진(§4.2), Thumbnail Cache(§4.3), Hot Storage(§4.4), Order Orchestrator(§4.5), Billing(§4.6)은 **본 문서 범위 아님**. 본 문서는 "이미 ingest 된 study/series/instance 테이블 위에 **읽기 전용** API를 노출"하는 범위만 다룬다.

---

## 1. TL;DR

- **인증**: v0.1 은 **opaque API key(argon2id 서버측 해시) + `kid` prefix 룩업** 조합을 권고. OAuth2 client-credentials·mTLS 는 엔터프라이즈 계약(연 $50K+) 성립 시 v0.2 옵션. Segmed·Gradient 모두 API key 로 시작했다는 공개 자료 부합. **buyer_id → quota tier** 매핑을 토큰과 함께 저장해 free/preview/paid 3-tier 시행.
- **페이지네이션**: OFFSET/LIMIT **금지**. `(study_date_shifted DESC, study_pk DESC)` 튜플 키셋 커서 + base64 JSON 인코딩. 1M 스터디에서 깊은 페이지도 O(log N), 측정사례 10–17× 속도 개선 보고.
- **패싯 카운트**: v0.1 은 매 요청 `GROUP BY` 로 정직하게 계산하되, **facet 선택 가능 필드 화이트리스트 6개**(modality, body_part, sex, age_bucket, manufacturer, year bucket)로 카디널리티 상한. 100만 행에서 월 파티션 프루닝 + 커버링 인덱스면 p95 < 800ms 달성 가능. 느려지면 v0.2 에 `cohort_summary` materialized view + `postgres_hll` approximate-distinct 로 분리.
- **DoS 방어**: 4겹 스택 — (1) nginx `client_max_body_size`·`limit_req_zone`, (2) FastAPI 요청 타임아웃 미들웨어, (3) PostgreSQL `statement_timeout` per-role(buyer 15s), (4) Redis-backed slowapi per-buyer. 추가로 **pre-execution cost estimator** (필터 조합의 카디널리티를 `cohort_summary` 로부터 추정해 임계 초과 시 422).
- **멀티 테넌시**: 데이터가 **완전 익명정보**라는 전제에서 v0.1은 "모든 buyer → 모든 hospital 데이터 노출" 기본값. 병원별 buyer opt-out 은 **계약 수준 우선, 기술 레이어는 v0.1.1 backlog** 로 지연 권고(이슈: 경쟁사 병원 민감도). RLS 도입 시 `(hospital_pk, ingested_at)` 복합 인덱스 선행 필수.
- **관측성**: p50/p95/p99 검색 레이턴시, facet 계산 시간, empty-result rate(버이어 UX 지표), buyer-specific error rate 을 `radivault_index_*` Prometheus 네이밍으로 노출. 구조화 로그에는 **raw filter JSON 대신 sha256 해시 + 필드 이름만** 기록(필터 자체가 상품 IP).
- **경쟁 UX**: Gradient Atlas 는 Python SDK + REST 공개, Segmed 는 포털·API 혼합. NIH TCIA 는 NBIA REST v4, OpenNeuro 는 GraphQL. **강한 권고**: v0.1 은 **REST API-only**, SDK 는 v0.2 개방. 대신 OpenAPI 3.1 스펙·2개 이상 `curl` 샘플 쿼리·Postman 컬렉션을 onboarding 산출물로 동봉.

---

## 2. 조사 질문

1. 인터넷에 노출되는 B2B 검색 API 에서 엔터프라이즈 buyer 가 기대하는 인증 방식과 v0.1 에 적합한 최소 조합은?
2. 100만+ 스터디 규모에서 구매자 검색 응답을 2 초 내(p95)로 유지하기 위한 페이지네이션·패싯 카운트 전략은?
3. 인터넷 노출 + 다수의 untrusted buyer 테넌트 환경에서 DoS·쿼리 폭주를 어떻게 다층 방어하는가?
4. "완전 익명정보" 전제 하에서 병원-buyer 가시성 격리는 기술 레이어와 계약 레이어 중 어디에 두는 것이 합리적인가?
5. 검색 워크로드 특유의 관측 지표(empty-result, cardinality explosion, cache hit)는 Central Ingest 메트릭과 어떻게 분리·네이밍하는가?
6. Gradient Atlas·Segmed·NIH TCIA·OpenNeuro 의 공개 API UX 중 RadiVault v0.1 이 직접 모방할 요소와 지연시킬 요소는?

---

## 3. 방법론

- **1차**: FastAPI docs, PostgreSQL 16 docs (`statement_timeout`, RLS, 파티셔닝, 인덱스), Citus `postgresql-hll` 저장소 README, AWS SaaS RLS prescriptive guidance, NBIA REST API Guide, OpenNeuro docs, Gradient Health 공개 웹사이트·PyPI, IETF draft idempotency-key, RFC 6750·8705.
- **2차**: Citus 블로그(5 ways to paginate), Stacksync 블로그 keyset vs offset 벤치, Sequin Stream keyset 가이드, pganalyze 파티셔닝, WorkOS "Top 5 authentication solutions for FastAPI 2026", pganalyze RLS 성능 측정 포스트.
- **3차**: Medium 개발자 블로그(FastAPI + slowapi + Redis 티어드 리미터, Pranav Prakash 2026-01 포스트).
- **경쟁사 1차 부족 영역 플래그**: Gradient Atlas 의 실제 SDK 쿼리 메서드 시그니처·커서 토큰 포맷은 공개 페이지에 없어 2차 자료로만 추정. Segmed Openda 는 "데이터 마켓플레이스 + cohort 빌더" 이상의 API 공개 없음. 이 두 업체의 세부 계약은 "로그인 후 내부 문서"로 보이며 본 문서에서는 **공개 마케팅 자료 수준만 인용**.
- **한계**: RadiVault 가 1M+ 실데이터에 도달하지 않았으므로 facet GROUP BY 측정치는 업계 벤치 인용. dev-spec 구현 후 실측 재검증 필요 플래그.

---

## 4. 결과

### 4.1 Buyer-facing 인증 패턴

#### 4.1.1 옵션 비교

| 옵션 | 보안 강도 | onboarding 마찰 | 엔터프라이즈 기대치 | v0.1 권고 |
|------|----------|----------------|-------------------|-----------|
| **Opaque API key (argon2id 서버 해시)** | 중-상 | **최저** (붙여넣기 1줄) | Gradient·Segmed 초창기 패턴과 부합 | **채택** |
| OAuth2 client-credentials (machine-to-machine) | 상 | 중 (client_id/secret + token endpoint) | 대기업 통합팀 익숙 | v0.2 옵션 |
| mTLS client cert | 최상 | **최고** (CA·CSR·갱신 절차) | FSI·일부 제약사에서 요구 | v0.3+ |

- **argon2id**: RFC 9106·PHC 위너. 2026 현재 FastAPI 공식 문서·pwdlib·OWASP 모두 기본 권고. `argon2-cffi` 가 이미 central-ingest 에서 사용 중이므로 의존성 추가 없음.
- **opaque key 레이아웃 권고**: `rv_live_<kid8>_<random32>` (총 48자). `kid` prefix(8자, index 가능)로 **DB 조회 1회 + argon2 검증 1회** 패턴. argon2 검증은 요청당 ~40–80ms 수준(m=64MiB, t=3, p=4)이므로 **Redis 1분 긍정 캐시**를 추가해 핫패스를 1ms 이하로.
- **쉬운 함정**: 전체 키를 해시한 뒤 "해시로 조회"하면 O(n) 스캔. 반드시 `kid` 기반 index lookup 후 해시 검증. (pganalyze·WorkOS 가이드 공통 경고.)

#### 4.1.2 Key scoping — buyer_id → 가시성·쿼터

본 프로젝트 전제("완전 익명이므로 병원 데이터는 모든 buyer 에게 공개")에서 v0.1 스코프는 단순.

- **visibility**: 기본 `ALL_HOSPITALS`. 계약 예외 시 `exclude_hospitals=[hospital_id,...]` 배열로 처리(hospital 별 opt-out 은 §4.5 참고).
- **quota tier**: enum `free | preview | paid`. 티어별 권고 초기값 (TBD, dev-spec 에서 확정):
  - free: 30 req/min, 100 req/day, 결과 최대 100 study/page, thumbnail 비허용.
  - preview: 120 req/min, 5K req/day, thumbnail 허용, 실 다운로드 불가.
  - paid: 600 req/min, 무제한 일 한도, SLA 99.9%.
- **토큰 DB 컬럼 확장**(central-ingest `auth_token` 참고): `buyer_api_key(buyer_pk, key_kid, key_hash, tier, scope_json, created_at, expires_at, revoked_at, last_used_at)`. `hospital.auth_token` 과 **물리 테이블 분리**(병원 gateway 토큰 ≠ 외부 buyer 키).

#### 4.1.3 경쟁 벤치

- **Gradient Atlas**: 공개 안내에 "robust Python SDK and REST API" 명시. 2025 Atlas 2 런칭 블로그에서 "hundreds of DICOM tags, series-level, longitudinal patient-level search" 언급(출처 §7). 구체 인증 방식은 로그인 후 내부 문서.
- **Segmed Insight/Openda**: "data cloud platform curated for AI development" — 주로 **웹 포털 + 프로젝트별 큐레이션** 중심. 공개 API 는 확인되지 않음(2026-04 기준). RadiVault 는 Segmed 보다 "self-service API" 비중을 더 높게 잡아 Gradient 쪽에 가까운 포지션 권고.
- **NIH TCIA (NBIA REST v4)**: API key 없이 공개 엔드포인트. 내부 TCIA 계정이 있어야 하는 "NBIA Search with Authentication" 는 별도. format 파라미터(CSV/XML/JSON) 반환 — RadiVault v0.1 은 JSON 단일.
- **OpenNeuro**: GraphQL. 유연한 쿼리 vs 예측 가능한 쿼리 비용의 tradeoff 때문에 **RadiVault v0.1 은 REST 권고**(DoS 방어 §4.4 와 궁합).

### 4.2 키셋 커서 페이지네이션

#### 4.2.1 왜 OFFSET/LIMIT 를 거부하는가

- OFFSET N 은 PostgreSQL 이 앞 N 행을 스캔·버려야 해 **깊은 페이지에서 O(N)** 으로 퇴화. 1M 스터디에서 500,000th page 는 분 단위로 느려짐(Stacksync 벤치 17× 느려짐 보고).
- 페이징 중 ingest 가 새 row 추가 시 중복·누락 가능. Central Ingest 는 실시간 ingest 스트림이므로 치명적.

#### 4.2.2 커서 설계 권고

- **정렬 키**: `(study_date_shifted DESC, study_pk DESC)` 1차. 대안 `(ingested_at DESC, study_pk DESC)` — buyer 가 "최신 데이터" 요청 시.
- **인덱스**: `CREATE INDEX idx_study_date_keyset ON study (study_date_shifted DESC, study_pk DESC);` + 파티션별 자동 인덱스. 기존 `idx_study_date` 는 ASC 기본 — **DESC 키셋용 별도 인덱스 추가** dev-spec FR 반영 필요.
- **WHERE 절**: `WHERE (study_date_shifted, study_pk) < ($last_date, $last_pk)` 튜플 비교. PostgreSQL 은 row-value 비교로 인덱스 seek 가능.
- **커서 토큰**: `base64url(json({"v":1,"d":"2026-04-18","p":12345,"s":"YbM3z…"}))` 여기서 `s` = `sha256(filter_json || sort_key)[:12]` 로 필터·정렬 불변 검증. 변경 감지 시 400 `ERR_CURSOR_FILTER_CHANGED`.
- **역방향 페이징**: v0.1 미지원(명시 제외). buyer 가 "뒤로" 를 누르려면 클라이언트가 이전 커서 보관.
- **stable sort 보장**: `study_pk` tiebreaker 필수. 없으면 동일 날짜 다수 스터디에서 중복·누락.

#### 4.2.3 FastAPI + SQLAlchemy 2.0 구현 패턴

- `request` → pydantic `SearchRequest(cursor: str | None, sort: Literal["date_desc","ingested_desc"], limit: int = 50)`.
- repository 계층에서 커서 디코드 → `stmt = select(Study).where(tuple_(Study.study_date_shifted, Study.study_pk) < (d, p)).order_by(Study.study_date_shifted.desc(), Study.study_pk.desc()).limit(limit + 1)`.
- `limit + 1` 로 `has_next` 판별 후 drop.
- 응답 스키마:
  ```jsonc
  {
    "items":     [ { "pseudo_study_uid": "...", "modality": "CT", ... }, ... ],
    "next_cursor": "eyJ2IjoxLCJkIjoi...",
    "has_next":   true,
    "page_size":  50
  }
  ```
  central-ingest envelope(OpenAPI 스타일 옵션 B) 과 호환.

### 4.3 패싯 카운트 구현

#### 4.3.1 v0.1 — 정직한 GROUP BY

- 요청당 필터 적용 후 **N 개 facet 필드 각각 GROUP BY + COUNT(*)** 실행. N = 6 (modality, body_part, sex, age_bucket, manufacturer, year bucket) 화이트리스트.
- 100만 행 · 월 파티션 12개 (최근 1년) · 커버링 인덱스 기준 facet 하나당 30–80ms × 6 = 180–500ms 예상(pganalyze 벤치 추정). p95 < 800ms 가능.
- facet 응답 shape(Segmed·Gradient UI 공통 패턴 맞춰 설계):
  ```jsonc
  {
    "items":  [ ... 50 studies ... ],
    "facets": {
       "modality":     [ { "value": "CT", "count": 42318 }, { "value": "MR", "count": 18244 } ],
       "body_part":    [ ... ],
       "sex":          [ { "value": "M", "count": 33210 }, { "value": "F", "count": 27108 } ],
       "age_bucket":   [ ... ],
       "manufacturer": [ ... ],
       "year":         [ { "value": "2024", "count": 21033 }, ... ]
    },
    "total_matching": 60562,
    "next_cursor":    "..."
  }
  ```
- **buyer 옵션**: 요청에 `include_facets=false` 허용 — 페이지만 넘길 때 facet 쿼리 스킵 (500ms 절감). default true.

#### 4.3.2 v0.2 — Materialized view + HLL (백로그)

- `cohort_summary` materialized view: `(hospital_pk, modality, body_part, sex, age_bucket, manufacturer, year, study_count, patient_count_hll)` 일 1회 `REFRESH MATERIALIZED VIEW CONCURRENTLY`.
- **정확한 distinct patient count** 는 비싸므로 `postgres_hll` (Citus data) 로 approximate count(오차 ~2%). "대략 45,000 환자" 같은 UX 표현은 buyer 에게 수용됨.
- trade-off: MV 가 1분~1일 stale → "정확한 카운트 vs 응답 속도" 결정 필요. 본 문서는 **v0.1 = 실시간 GROUP BY, v0.2 = MV + HLL** 단계 권고.
- on-write trigger 로 MV 증분 갱신하는 패턴도 있으나 central-ingest write throughput 과 결합도 증가 → 거부.

#### 4.3.3 approximate 수용 기준

- buyer 가 **"살 것인지 말 것인지 판단용 카운트"** 라면 ±2% 허용. **"계약서·인보이스 발행용 카운트"** 는 허용 불가 → 주문 확정 경로는 항상 exact count 재계산(Order Orchestrator 범위, 본 문서 밖).

### 4.4 쿼리 복잡도 / DoS 방어

#### 4.4.1 4-layer timeout stack

| 레이어 | 설정 | 목적 |
|--------|-----|------|
| nginx/ALB | `client_max_body_size 1m` (검색은 작음), `proxy_read_timeout 20s`, `limit_req_zone per-IP 60r/m` | L7 coarse rate, slow-read 방어 |
| FastAPI 미들웨어 | `asyncio.wait_for(handler, timeout=15s)` | 요청 수명 상한 |
| PostgreSQL | `ALTER ROLE buyer_app SET statement_timeout = '10s';` | 진짜 느린 쿼리 강제 종료 |
| slowapi (Redis) | per-buyer tier 별 rate | 특정 buyer 폭주 격리 |

- Nginx `limit_req_zone` 와 slowapi 의 차이: 전자는 IP coarse, 후자는 **buyer_id fine-grained**. 둘 다 필요.
- PG `statement_timeout` 은 **role 별** 설정이 권장(앱 전역 postgresql.conf 금지). buyer 쿼리 전용 role `radivault_buyer_ro` 를 분리.

#### 4.4.2 Pre-execution cost estimation

- 요청 필터를 `cohort_summary`(v0.1은 근사로 `SELECT COUNT(*) FROM study WHERE ...`) 에서 **최대 500ms 안에** 미리 조회.
- 결과 rows > 10M → 422 `ERR_QUERY_TOO_BROAD` + hint ("modality 나 year 필터를 추가하세요").
- 필터 화이트리스트 위반(예: `modality IN ('MR','CT','CR','XA','US','DX','NM','PT','MG','XYZ')` — IN 개수 > 10) → 400 `ERR_FILTER_TOO_MANY`.

#### 4.4.3 per-buyer 동시성 캡

- Redis `SETNX buyer:{id}:inflight N; INCR` 패턴으로 buyer 당 동시 검색 요청 **6개** 상한(tier 별 조정). 초과 시 429.
- slowapi 단독으로는 동시성 제어 약함 → 별도 세마포어 키 운영.

### 4.5 멀티 테넌시 (buyer ↔ hospital)

#### 4.5.1 v0.1 기본값

- **전제**: Gateway 에서 annex E Basic Profile 로 완전 익명화 완료 → 중앙 DB 는 익명정보. 병원 식별 컬럼 `hospital_pk` 는 존재하나 buyer 응답에서는 **기본 숨김**(통계 투명성·경쟁 병원 민감도).
- v0.1 = **flat access**. 모든 buyer 가 모든 hospital 데이터 검색 가능. hospital 이름 반환은 `include_hospital=true` + 계약 플래그 시에만.

#### 4.5.2 hospital opt-out 모델 (v0.1.1 검토)

- 시나리오: 병원 A 가 "경쟁사인 AI 회사 X 에게는 우리 데이터 빼 달라" 요청.
- 기술 옵션:
  - (a) **계약 + 애플리케이션 filter**: `buyer_api_key.scope_json.exclude_hospitals=[...]` → 모든 쿼리에 `WHERE hospital_pk NOT IN (...)` 자동 삽입. 구현 단순, 실수 리스크(필터 누락 시 유출).
  - (b) **PostgreSQL RLS**: `CREATE POLICY buyer_hospital_access ON study USING (hospital_pk <> ALL(current_setting('rv.exclude_hospitals')::bigint[]));` + 세션 시작 시 `SET rv.exclude_hospitals = ...`. 실수 방지 강함. 단, `(hospital_pk, ingested_at)` 복합 인덱스 선행 필수 — pganalyze·AWS RLS 가이드 공통: "tenant_id 가 leading column 이 아니면 2 orders of magnitude 느려짐".
- **권고**: v0.1 은 **(a)**, v0.1.1 에 RLS 추가. Kyle 결정 필요(§6).

#### 4.5.3 계약적 vs 기술적 집행

- 계약: MSA·DPA 의 "buyer shall not attempt re-identification" 조항 + 위반 시 해지.
- 기술: (1) 쿼리 레이트·동시성, (2) 결과 row 수 상한, (3) 이상 패턴 감지(무한 small-page scan, 반복 동일 필터) → 알람.
- 두 레이어 **모두** 필요. 법률 자문 필요 플래그.

### 4.6 검색 워크로드 관측성

#### 4.6.1 핵심 메트릭 (Prometheus `radivault_index_*` 네이밍)

| 메트릭 | 타입 | 라벨 | 목적 |
|--------|-----|------|------|
| `radivault_index_search_duration_seconds` | histogram | `tier, has_facets, status` | p50/p95/p99 |
| `radivault_index_facet_duration_seconds` | histogram | `facet_field` | facet 별 병목 식별 |
| `radivault_index_result_size` | histogram | `tier` | 결과 분포 (너무 넓은 필터 식별) |
| `radivault_index_empty_result_total` | counter | `buyer_id_hash` | UX 문제 감지 (zero-result rate > 20% → 필터 UI 재설계) |
| `radivault_index_cache_hit_total` | counter | `cache_layer` | Redis auth cache, MV cache |
| `radivault_index_rate_limited_total` | counter | `tier, reason` | 429 분석 |
| `radivault_index_query_too_broad_total` | counter | - | 422 cost rejections |

central-ingest 네이밍(`radivault_central_*`)과 접두사 분리해 대시보드 구분.

#### 4.6.2 구조화 로그

- 필드: `ts, request_id, buyer_id_hash, tier, endpoint, status, duration_ms, result_size, filter_sha256, filter_fields, cursor_hit, cache_hit`.
- **핵심 금지**: `filter_raw` 를 절대 로그하지 않는다. 필터 자체가 buyer 의 IP(어떤 코호트를 찾는지 = 어떤 AI 제품을 만드는지). `filter_sha256` 과 `filter_fields`(키 이름만) 로만 추적.
- `pg_stat_statements` 활성화 → DBA 가 쿼리 플랜 최적화. 다만 stat 도 buyer-identifiable 이므로 SRE 권한 접근만.

#### 4.6.3 매출 추적 (revenue analytics)

- 매일 배치: "어떤 필터 조합 → 어떤 cohort 미리보기 → X 일 후 주문 확정" 매핑. **purchase funnel**(search → facet → preview → cart → order)의 conversion 측정.
- 본 v0.1 은 search 단계만 구현 → `filter_sha256` 을 나중에 Order Orchestrator 가 교차 조인할 수 있게 **request log 를 DB 에도 미러**(7일 TTL) 권고. purchase 단계 합류는 v0.2+.

### 4.7 경쟁 API UX 설문

#### 4.7.1 Gradient Health Atlas (Durham, NC)

- **공개 페이지**: "robust Python SDK and REST API" — 구체 메서드 미공개.
- **2025 Atlas 2 런칭**: 20M 스터디 즉시, +30M 계약중. "hundreds of DICOM tags 필터, series-level, longitudinal patient-level".
- **배포 채널**: Google Cloud Marketplace 입점(2025).
- **UX 추정**: SDK `atlas.search(modality="CT", body_part="CHEST", age_range=(40,70))` → paginated iterator. 공식 문서 없으므로 **추정**.

#### 4.7.2 Segmed Insight → Openda

- 2024 리브랜딩 Openda. 포털 + 컨설팅(큐레이션 팀) 비중 큼.
- 공개 API 문서 미확인. **"self-service 와 human-curated 의 하이브리드"** 포지션으로 해석됨.
- 배울 점: **"복잡하거나 매우 특수한 코호트는 API 로 못 잡고 사람이 큐레이트"** 를 v0.2 공식 플로우로 인정(= contact-sales 버튼).

#### 4.7.3 NIH TCIA (NBIA REST v4)

- 무료 공개. format 파라미터(CSV/HTML/XML/JSON).
- **PRISM semantic cohort builder** — 비이미지 메타데이터(임상 변수) 900 data elements 기반 코호트 빌더. RadiVault 가 NLP 라벨 엔진 보강 후 **"판독문 진단명 기반 검색"** 으로 유사한 가치 제공 가능(v0.2).
- 학문 커뮤니티 레퍼런스 — RadiVault 버이어 중 학계 티어에게 "TCIA-like API" 를 내세우는 마케팅 훅 가능.

#### 4.7.4 OpenNeuro

- GraphQL. 학술 커뮤니티 친숙.
- **배울 점**: GraphQL 의 유연성은 매력적이지만 **쿼리 복잡도 예측 불가 → DoS 방어 비싸짐**. RadiVault B2B 문맥에는 부적합 판단. v0.1 REST 고수.

#### 4.7.5 엔터프라이즈 연 계약 체결 요건 (종합)

| 요인 | 영향 | RadiVault v0.1 실행 |
|------|-----|-------------------|
| **OpenAPI 3.1 스펙 공개** | 자동 코드 생성 가능 → 엔터프라이즈 통합팀 선호 | FastAPI 자동 생성, `/openapi.json` 공개, `docs.radivault.io` 호스팅 |
| **curl + Python 샘플 5개+** | 30 분 안에 첫 성공 → PoC 의사결정 가속 | dev-spec 에 "sample queries" 부록 필수 |
| **Postman/Insomnia 컬렉션** | 비개발자 세일즈팀도 데모 가능 | 배포 산출물 |
| **Python SDK** | **Gradient 와의 gap 축소** 핵심 | **v0.1 미제공, v0.2 제공** — 단, **"SDK 는 thin wrapper 로 v0.2 제공 예정" 로드맵 공개** 로 락인 불안 완화 |
| **SLA 문서** | 99.9% 가용성·p95 응답 시간 명시 | dev-spec 에 목표치만, 계약 SLA 는 paid tier 만 |
| **SOC 2 진행 상황** | 엔터프라이즈 83% 요구 (k-meddata research §5) | 마케팅 페이지에 "SOC 2 Type I in progress" 표기(과장 금지) |
| **샘플 데이터셋** | "직접 써보기" 의 zero-friction 시작 | free tier 로 100 study 샘플 |

- **강한 의견**: v0.1 은 REST + OpenAPI + 샘플 쿼리 5종 + Postman 컬렉션으로 충분. Python SDK 는 **v0.2 로 지연하되 로드맵에 명시**. 이유: (1) v0.1 API 계약이 첫 3개월간 반드시 breaking 변경 발생할 것, SDK 유지보수 비용이 조기 출시 이점을 상쇄. (2) Gradient 가 SDK 를 이미 확보했으므로 **RadiVault 의 차별화는 SDK 존재 여부가 아니라 한국 데이터 접근성**.

---

## 5. 시사점 (RadiVault에의 함의)

1. **dev-spec 에 "읽기 전용 role 분리" FR 필수**. 현재 central-ingest 는 쓰기/읽기 공용 연결로 구성. Metadata Index v0.1 은 `radivault_buyer_ro` PG role + 별도 connection pool, `statement_timeout=10s`, GRANT SELECT only.
2. **auth_token 테이블 분리**(병원 Gateway 용과 buyer API 용). central-ingest `auth_token` 에 buyer row 혼합 금지. 신규 `buyer`·`buyer_api_key` 테이블.
3. **신규 인덱스 2건** 선제 추가 권고: `(study_date_shifted DESC, study_pk DESC)`, `(ingested_at DESC, study_pk DESC)`. 월 파티션에서 로컬 인덱스로 자동 복제됨.
4. **디자인 명세 envelope 계승**: central-ingest `{error, detail, message_ko, message_en, request_id, doc_url, hint, retry_after}` 그대로 재사용. 신규 에러 코드 `ERR_CURSOR_FILTER_CHANGED`, `ERR_QUERY_TOO_BROAD`, `ERR_FILTER_TOO_MANY`, `ERR_BUYER_QUOTA` 4개 추가 제안.
5. **ARCHITECTURE §5 업데이트 제안**: "Developer API & SDK" 를 "Phase 2.0 REST API / Phase 2.1+ Python SDK" 로 분리 기술. v0.1 은 SDK 없음을 명시.
6. **법률 자문 플래그**: hospital opt-out 을 **계약 문구**로 먼저 셋팅하려면 표준 MSA 에 조항 신설 필요. v0.1 에서는 "기술 레이어 미구현"이지만 **계약서에는 "RadiVault may at hospital's request exclude hospital's data from specific buyers"** 조항 선제 삽입 권고.

---

## 6. 한계·오픈 퀘스천

1. **Kyle 결정 필요 — hospital opt-out**: v0.1 에 계약 문구만 넣고 기술 구현은 v0.1.1? 아니면 v0.1 application-layer filter 까지? (본 문서 §4.5 권고: 계약만, 기술은 v0.1.1)
2. **Kyle 결정 필요 — Python SDK 타이밍**: v0.1 REST-only / v0.2 SDK, 아니면 v0.1.1 에 "thin SDK(requests wrapper)" 조기 릴리즈? (§4.7.5 권고: v0.2)
3. **pricing tier 구체 값 — TBD**: free/preview/paid 각 req/min, 결과 상한, thumbnail 접근, SLA 는 본 문서에 **플레이스홀더만**. 가격은 경영 결정 사항.
4. **"total_matching" 의 정확 vs 근사 — 실측 필요**: v0.1 에서 `COUNT(*)` over 100만 행 필터가 p95 < 1s 유지 가능한지 실제 측정. 불가 시 approximate 전환.
5. **filter_sha256 의 salt 전략**: 매출 분석을 위해서는 buyer 간 비교 가능해야 함(salt 없이 raw filter hash). 보안을 위해서는 per-buyer salt. tradeoff dev-spec 결정.
6. **NLP 라벨 필드의 검색 노출 시점**: 본 문서는 현 스키마(modality·body_part 등) 전제. 판독문 기반 진단명·RadLex 태그 필드는 라벨링 엔진 dev-spec 후 search API 에 추가. v0.1 에서 **스키마는 준비**하고 API 는 v0.2 노출?
7. **buyer 인증과 billing 의 결합**: Stripe metered billing 연동 시 토큰 → customer_id → usage record 매핑. 본 문서 범위 밖 (Billing dev-spec).
8. **data residency**: buyer 가 "한국 외 리전에서는 질의 불가" 요청 시? — 본 프로젝트는 완전 익명정보 전제에서 buyer 측 리전 제약은 없음으로 가정. 일부 정부 buyer 에서는 재확인 필요.

---

## 7. 출처

### 기술 1차
- FastAPI Security & Deployment: https://fastapi.tiangolo.com/tutorial/security/, https://fastapi.tiangolo.com/deployment/
- pwdlib (argon2id 기본): https://github.com/frankie567/pwdlib
- argon2-cffi docs: https://argon2-cffi.readthedocs.io/
- PostgreSQL 16 `statement_timeout`: https://www.postgresql.org/docs/16/runtime-config-client.html
- PostgreSQL 16 Materialized Views: https://www.postgresql.org/docs/16/rules-materializedviews.html
- PostgreSQL 16 Row Security Policies: https://www.postgresql.org/docs/16/ddl-rowsecurity.html
- Citus `postgresql-hll`: https://github.com/citusdata/postgresql-hll, https://docs.citusdata.com/en/stable/articles/hll_count_distinct.html
- slowapi: https://github.com/laurentS/slowapi, https://slowapi.readthedocs.io/
- pg_stat_statements: https://www.postgresql.org/docs/16/pgstatstatements.html

### 페이지네이션·패싯 2차
- Citus Data — "Five ways to paginate in Postgres": https://www.citusdata.com/blog/2016/03/30/five-ways-to-paginate/
- Sequin Stream — "Keyset Cursors, Not Offsets, for Postgres Pagination": https://blog.sequinstream.com/keyset-cursors-not-offsets-for-postgres-pagination/
- Stacksync — "PostgreSQL Keyset Pagination vs Offset": https://www.stacksync.com/blog/keyset-cursors-postgres-pagination-fast-accurate-scalable
- pganalyze — Query Performance: https://pganalyze.com/docs/query-performance

### 멀티 테넌시·RLS
- AWS Prescriptive Guidance — Row-Level Security recommendations: https://docs.aws.amazon.com/prescriptive-guidance/latest/saas-multitenant-managed-postgresql/rls.html
- AWS Blog — Multi-tenant data isolation with PostgreSQL RLS: https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/

### 경쟁사·공개 API
- Gradient Health Atlas (2026-04 조회): https://gradienthealth.io/atlas/
- Gradient Health Atlas 2 런칭 (2025): https://gradienthealth.io/gradient-health-launches-atlas-2-setting-a-new-standard-for-medical-imaging-data-access/
- Segmed/Openda 런칭 (2024): https://www.prnewswire.com/news-releases/segmed-unveils-new-brand-identity-and-introduces-openda-the-next-evolution-for-its-insight-platform-302185953.html
- Segmed 제품 페이지: https://www.segmed.ai/insight
- TCIA NBIA Search REST API Guide: https://wiki.cancerimagingarchive.net/display/Public/NBIA+Search+REST+API+Guide
- TCIA API Guides 허브: https://wiki.cancerimagingarchive.net/display/Public/TCIA+Application+Programming+Interface+(API)+Guides
- OpenNeuro API Examples: https://docs.openneuro.org/api.html
- OpenNeuro Architecture: https://docs.openneuro.org/architecture.html
- PRISM semantic cohort builder (TCIA) 논문: https://pmc.ncbi.nlm.nih.gov/articles/PMC9855624/

### 표준·RFC
- RFC 6750 — OAuth 2.0 Bearer Token Usage
- RFC 8705 — OAuth 2.0 Mutual-TLS Client Authentication
- RFC 9106 — Argon2 Memory-Hard Function for Password Hashing

### 한국 규제
- 개인정보보호법 제28조의8 (법제처, 2023-09-15 개정): https://www.law.go.kr/법령/개인정보보호법
- 개인정보위 "가명정보 처리 가이드라인" (2024)
- (본 문서 §4.5 hospital opt-out 결정 시 법률 자문 필요 플래그)

(모든 경쟁사 공개 수치·제품 상태는 2026-04-22 기준 추정. dev-spec 확정 시 재확인 필요. 본 문서는 법률 자문이 아니다.)

---

## 8. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-22 | @researcher (Claude Opus 4.7) | 최초 작성. Metadata Index v0.1 buyer-facing 검색 API 기술 기반 7개 영역 조사. |

---

### NEXT_STEP
- 완료 산출물: `docs/research/metadata-index-technical-foundations.md`
- 제안 다음 단계: **@planner** — `docs/specs/dev-spec-metadata-index.md` 작성. 본 리서치 §4.1–§4.7 을 근거로 다음을 요구사항화:
  1. **인증 FR**: opaque key(`rv_live_<kid8>_<random32>`) + argon2id + Redis 캐시, 신규 테이블 `buyer`·`buyer_api_key`, central-ingest `auth_token` 과 **물리 분리**.
  2. **페이지네이션 FR**: `(study_date_shifted DESC, study_pk DESC)` 키셋 커서 + base64 JSON + filter_sha256 변경 감지 400 `ERR_CURSOR_FILTER_CHANGED`. 신규 인덱스 2건 Alembic migration.
  3. **패싯 FR**: GROUP BY 화이트리스트 6개 필드, `include_facets=false` 옵션, 응답 shape 고정.
  4. **DoS 방어 FR**: nginx + FastAPI 타임아웃 + PG `statement_timeout=10s`(신규 `radivault_buyer_ro` role) + slowapi tiered rate + pre-execution cost estimator(결과 > 10M → 422 `ERR_QUERY_TOO_BROAD`).
  5. **멀티 테넌시 FR**: v0.1 flat-access + `buyer_api_key.scope_json.exclude_hospitals` application-layer filter. RLS 는 v0.1.1 백로그.
  6. **관측성 FR**: `radivault_index_*` Prometheus prefix, empty-result-rate 알람, raw filter 로그 금지.
  7. **에러 taxonomy 확장**: `ERR_CURSOR_FILTER_CHANGED`·`ERR_QUERY_TOO_BROAD`·`ERR_FILTER_TOO_MANY`·`ERR_BUYER_QUOTA` 4개 신규. central-ingest design-spec §5 포맷 준수.
  8. **SDK 로드맵 명시**: v0.1 REST-only, Python SDK 는 v0.2 로 문서화.
- Kyle 결정 필요 사항:
  1. **Hospital opt-out 정책** — v0.1 은 계약 문구만 / v0.1.1 application filter / v0.2 RLS 중 어디까지?
  2. **Python SDK 타이밍** — v0.1 REST-only (권고) / v0.1.1 thin wrapper / v0.2 정식 SDK?
  3. **Pricing tier** — free/preview/paid 의 req/min·일 한도·결과 상한 실값. 본 문서는 플레이스홀더만.
  4. **Filter hash salt 전략** — per-buyer salt (보안 우선) vs 전역 salt (매출 funnel 분석 우선)?
  5. **NLP 라벨 필드 노출 시점** — 본 v0.1 search API 에 진단명 필드를 placeholder 로 둘지 v0.2 까지 완전 제외할지?
  6. **법률 자문 트리거** — hospital opt-out 계약 조항 신설·"완전 익명" 주장 재확인이 필요한 시점.
