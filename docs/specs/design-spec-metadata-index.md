# 디자인 명세 — Metadata Index v0.1 MVP (Buyer-facing Search API · Operator CLI · Observability · Runbook UX)

> **Status**: Draft v0.1 · **Feature slug**: `metadata-index` · **Last updated**: 2026-04-22
> **작성자**: @designer (Claude Opus 4.7) · **근거**:
> - [dev-spec-metadata-index](./dev-spec-metadata-index.md) — 본 디자인의 유일한 source of truth (77 FR · 34 AC · 신규 에러 11종)
> - [design-spec-central-ingest](./design-spec-central-ingest.md) — envelope 포맷, 에러 taxonomy 구조, CLI 출력 컨벤션, runbook 포맷을 **그대로 상속**
> - [design-spec-gateway-agent](./design-spec-gateway-agent.md) — CLI i18n 규약·exit code taxonomy 참고
> - [리서치 — Metadata Index 기술 기반](../research/metadata-index-technical-foundations.md)
> - [UI Guide](../UI_GUIDE.md) — 톤 원칙만 참조

---

## 0. 범위 선언 (Scope Statement)

본 문서는 통상의 GUI/웹 디자인 명세가 **아니다**. Metadata Index v0.1 은 RadiVault 가 최초로 공개하는 **buyer-facing HTTP Search API 서비스**로, v0.1 범위에 웹 UI·대시보드·포털 화면이 없다. 그러나 "API 를 쓰는 외부 개발자 + 운영자 + 영업 엔지니어"가 실제로 마주하는 표면이 분명히 존재하며, 본 문서는 그 **개발자 경험(DX) · 운영자 경험(OpEx)** 를 정의한다.

**디자인 대상 표면 7종**

1. **HTTP API UX (buyer-facing DX)** — 요청·응답 JSON shape, 에러 envelope, cursor 계약, facet 응답 shape, rate-limit 헤더, CORS/Content-Type/버전 정책. **RadiVault 최초의 외부 공개 API**이므로 영업 시연·PoC·구매자 문서에 그대로 노출된다.
2. **Operator CLI (`search-admin`)** — 구매자 생성·키 발급/회수·쿼리 통계·마이그레이션.
3. **Log & Observability 출력** — JSON 로그 schema(`radivault_search.*`), Prometheus 메트릭 네이밍(`radivault_index_*`), 알람 정의.
4. **Error Taxonomy UX** — dev-spec §7.6 / §13.1 의 모든 코드를 5-field(ko+en+context+buyer action+SRE action+doc) 운영자 표로 렌더.
5. **Runbook 산출물** — 검색 특유 장애(empty-result spike, cost estimator storm, cursor churn, key compromise 등) 플레이북 7편.
6. **Buyer Onboarding Walkthrough** — 영업 최초 컨택 → NDA → preview key → 첫 curl → 첫 코호트 → paid 전환 → 첫 구매 문의까지 10 단계.
7. **API 문서 산출물 계획** — OpenAPI 3.1 YAML, curl 샘플 5종, Postman 컬렉션, Swagger UI 호스팅, SDK 로드맵 선언.

**디자인 대상 아닌 것**: 구매자 포털 웹 UI (v0.2+ 별도 slug), 병원 관리 콘솔 (central-ingest 범위), DICOM 뷰어, 모바일 앱, 결제 UI, 썸네일 CDN.

표준 design-spec 템플릿의 시각 디자인 항목(반응형·색 대비·디자인 토큰·스크린리더·포커스 관리 등)은 **HTTP API 서비스 성격상 적용되지 않아** "N/A — HTTP API service" 로 명시한다(central-ingest design-spec 과 동일 패턴). 삭제하지 않고 boilerplate 로 유지하는 이유는 (a) 템플릿 완전성 보장, (b) v0.2 에서 Buyer Portal UI 가 추가되면 본 문서의 어디에 시각 섹션을 붙일지 명확히 하기 위함.

---

## 1. 사용자 (Users)

### 1.1 Primary A — 엔터프라이즈 구매자 통합 개발자 (Enterprise buyer developer)

- **유형**: 의료영상 AI 기업·의료기기 회사의 백엔드/데이터 엔지니어. 미국·EU·싱가포르·일본 본사가 대다수, 한국 지사는 소수.
- **언어**: **영어 우선**. 내부 커뮤니케이션이 영어이며 API 명세·에러 메시지·Postman 예시를 영어 기준으로 읽는다. 한국어 번역은 덤.
- **기술 수준**: HTTP REST·curl·Postman·OpenAPI 3.x 읽기 숙련. Python / TypeScript / Go 중 하나로 SDK 자체 빌드 가능.
- **목표**:
  1. 첫 접촉 후 15분 내 첫 성공 응답(200 OK) 을 받는다 (= "time-to-first-hello" 목표).
  2. 한 주 안에 자사 ETL 파이프라인에서 야간 배치 코호트 새로고침을 붙인다.
  3. 필터·페이지네이션·quota 동작을 스스로 문서만 보고 이해한다 — 영업에 대화 1번으로 끝낸다.
- **기대 계약 (필수)**:
  - `POST /v1/search/studies` 200/400/401/422/429/504 의 응답 shape 이 **OpenAPI 3.1 스펙과 1:1 동일**.
  - `X-RateLimit-*` 헤더로 남은 쿼터를 실시간 파악 가능.
  - `next_cursor` 가 opaque 하지만 **filter 를 바꾸지 않는 한 영구 안정** — 스크립트가 하루 밤새 돌아도 OK.
  - 에러는 `ERR_*` enum 으로 기계 분기 가능, `message_en` 은 한 줄 사람 가독.
- **실패 시 행동**: 4xx → 자기 코드 재수정. 5xx → 지수 백오프. 429 → `Retry-After`. `ERR_CURSOR_FILTER_CHANGED` → 페이지 1 부터 재시작 (자사 SDK 의 페이지 iter 함수에 이 분기를 내장).
- **금지 가정**: "API 가 GET 이면 OK 일 것", "payload size 무제한", "filter 를 변경해도 cursor 유지". 문서로 명시적으로 부정한다.

### 1.2 Primary B — 구매자 측 데이터 사이언티스트 (Buyer data scientist, pre-purchase evaluator)

- **유형**: PhD/MD 레벨 연구자. "사기 전에 샘플 규모와 분포를 눈으로 확인" 을 원한다.
- **언어**: **영어 우선**. 한국어 독해 불가 가정.
- **기술 수준**: curl/jq/Postman 수준. 파이썬 notebook 에서 `requests` 로 한 줄 호출. 본격 SDK 는 아직 안 씀.
- **목표**:
  1. Postman collection 을 한 번 import 해서 "모달리티 CT / 흉부 / 2024 이후" 코호트의 `total_count` 를 본다.
  2. `GET /v1/search/facets` 로 제조사·연도별 분포를 차트로 그려본다(자사 내부 노트북).
  3. 결론: "사면 몇 건 받는지" 를 매니저에게 보여준다 → 구매 의사결정 가속.
- **기대 계약**:
  - **첫 요청 성공까지 curl 1줄**. `Authorization: Bearer rv_live_...` 외 별도 서명 알고리즘·헤더 요구 금지.
  - `facets` 응답이 JSON array 로 **그래프 라이브러리가 바로 받을 수 있는 shape**(`[{value, count}, ...]`).
  - 에러 메시지에 *무엇이* 잘못되었는지 구체 필드명이 포함(`detail: "study_date_shifted.to: field required"`).
- **그래듀에이션 경로**: 연구자 단계 → 통합 엔지니어(Primary A) 에게 인수인계 → Python SDK v0.2 출시 후 SDK 전환.

### 1.3 Secondary — RadiVault SRE (human operator)

- **언어**: 한국어/영어 혼용. 내부 runbook·에스컬레이션은 한국어, Prometheus 쿼리·CLI 는 영어.
- **기술 수준**: Linux/Docker/PostgreSQL/Redis 숙련. central-ingest design-spec §1.2 와 동일 인물.
- **목표**: (a) `/readyz`·`/metrics` 자동 모니터, (b) 검색 특유 알람(empty-result rate, cost-estimator storm, cursor churn, key compromise) 발생 시 5분 내 1st response, (c) `search-admin` 으로 구매자 키 발급·회수·일별 쿼터 사용량 조회.
- **안 해도 되는 일**: Python 코드 읽기, pydantic 내부 구조 이해, OpenAPI 스펙 직접 수정.
- **반드시 해야 하는 일**: `search-admin` CLI, Alembic 마이그레이션(search revision), 장애 대응 runbook, Prometheus 알람 응답, 구매자 키 긴급 회수.

### 1.4 Secondary — RadiVault 영업·세일즈 엔지니어 (Sales Engineer)

- **언어**: 한국어·영어. 프로스펙트와는 영어, 내부 슬랙은 한국어.
- **기술 수준**: curl/Postman 레벨. 구매자 통합 엔지니어(Primary A) 와 대화할 수 있는 수준의 HTTP 지식.
- **목표**:
  1. 데모 미팅에서 Postman collection 을 화면 공유로 실행 → "보세요, 10만 건 나옵니다" 시연.
  2. 프로스펙트의 통합 이슈(401/400/429) 를 **내부 지원 티켓으로 에스컬레이션 없이 1차 해결**.
  3. preview → paid 전환 타이밍 포착 — `search-admin stats buyer-usage` 로 daily quota 소진율을 본다.
- **기대 계약**:
  - Onboarding walkthrough (§7) 가 **그대로 영업 세일즈 플레이북**. 따로 번역할 필요 없이 한 페이지씩 프로스펙트에 보낼 수 있어야 한다.
  - 에러 메시지가 "무엇을 고쳐야 하는가" 를 한 줄로 알려준다 — 영업이 엔지니어 없이도 1차 응대 가능.
  - `search-admin stats` 출력이 월간 영업 보고서에 복붙 가능.

### 1.5 Non-user (v0.1 접근 금지)

- **환자·의료진**: 본 API 에 직접 접근 수단 없음. 병원 IT 경유만.
- **병원 IT 관리자**: central-ingest 범위. 본 API 는 읽기 전용이며 병원 데이터 쓰기 없음.
- **한국 국내 구매자**: 이론상 가능하지만 v0.1 파일럿 타겟은 글로벌 AI 기업. 한국어 onboarding 문서는 v0.2 백로그.

---

## 2. Buyer API UX — 핵심 DX

본 섹션은 RadiVault 의 **첫 외부 공개 HTTP API** 이므로 이하 규약은 향후 모든 Zone 3 API(v0.2 download, v0.3 payments 등) 에 **상속 기본값**이 된다.

### 2.1 응답 Envelope 원칙 (OpenAPI 옵션 B 채택, central-ingest 와 동일)

central-ingest design-spec §2.1 에서 채택한 **옵션 B (OpenAPI-스타일 + 최소 래핑)** 를 그대로 승계한다. 이유: (a) 동일 조직에서 두 envelope 스타일을 유지하는 비용 > 이점, (b) v0.2 Order Orchestrator 가 본 envelope 을 또 상속할 예정.

| 옵션 | 성공 바디 | 실패 바디 | 비고 |
|------|-----------|-----------|------|
| A. `{ok, data?, error?}` | `{"ok":true,"data":{...}}` | `{"ok":false,"error":{...}}` | 기각 — central-ingest 와 충돌 |
| **B. OpenAPI 스타일 (채택)** | `{...}` 직접 | `{"error":"<code>","detail":"<en>","message_ko":"<ko>","message_en":"<en>","request_id":"...","doc_url":"...","hint":"...","retry_after":null}` | dev-spec §7, central-ingest §2.1 과 100% 일치 |

**재확인**: 본 API 는 central-ingest design-spec §2.2 의 **7-field (5 필수 + 2 optional)** envelope 을 비변경 승계한다. 필드 이름·순서·의미 모두 동일. 본 spec 에서는 이를 재정의하지 않고 **참조**한다.

### 2.2 Search 엔드포인트 요청 shape (필터 7차원 all-filled 예시)

다음은 `POST /v1/search/studies` 의 **모든 필터 차원을 채운** 표본 요청이다. 각 필드에 "왜 존재하는가" 한 줄을 붙인다.

```jsonc
POST /v1/search/studies HTTP/1.1
Host: search.radivault.io
Authorization: Bearer rv_live_abcd1234_Zj8f2vX9qK2sLpN4mQbW7yR1eT5aU6c
Content-Type: application/json
X-Request-Id: 01HXQ8WQ9Z3K7V5B2A1N6P4R9T   // optional, client-provided; server echoes back
Idempotency-Key: (not used — search is idempotent by nature)

{
  "modality":      ["CT", "MR"],             // why: 구매자가 제일 먼저 좁히는 필터 — 모델 학습 도메인
  "body_part":     ["CHEST", "ABDOMEN"],     // why: 해부학적 범위 — FDA 허가 타깃 부위 매칭
  "age_bucket":    ["50-60", "60-70"],       // why: 익명화를 위해 정확 나이가 아닌 10살 bucket만 허용
  "sex":           ["M", "F"],               // why: 코호트 균형 검증 — unknown 포함 시 ["M","F","O"]
  "study_date_shifted": {                     // why: 날짜는 병원별 랜덤 시프트 — 재식별 방지
    "from": "2024-01-01",
    "to":   "2026-04-20"
  },
  "manufacturer":  ["SIEMENS", "GE", "PHILIPS"],   // why: 장비 편향 감사 — 허가 대응
  "min_hospitals": 3,                         // why: 단일 병원 편향 방지 — 최소 3곳 이상 합산만 노출
  "sort":          "date_desc",               // why: 기본값; "ingested_desc" 선택 시 최신 수집 순
  "limit":         50,                        // why: 페이지 크기 (tier 별 상한 — preview 100 / paid 200)
  "cursor":        null,                      // why: 다음 페이지 계속 호출 시 직전 응답의 next_cursor
  "include_facets": true                      // why: 분포 차트용 aggregation — false 시 latency 절감
}
```

**설계 원칙**:

- **모든 필드 optional 원칙, 단 cursor 와 filter 는 짝**. filter 없이 조회 가능 여부는 `ERR_QUERY_TOO_BROAD` (추정 rows > 10M) 에 의해 자동 제한됨.
- **대소문자**: enum 값(`modality`, `body_part`, `sex`) 은 **대문자 고정**. 소문자·혼용 → `400 ERR_REQUEST_SCHEMA`. OpenAPI 에 `enum` 로 명시.
- **날짜**: ISO 8601 date (`YYYY-MM-DD`). 타임스탬프(`YYYY-MM-DDTHH:MM:SSZ`) 수락 → `400 ERR_REQUEST_SCHEMA` 에 `detail="study_date_shifted.from must be YYYY-MM-DD"`. 재식별 리스크 방지.
- **POST-for-search 이유**: GET 쿼리스트링은 (a) 복잡한 nested filter 표현 불가, (b) URL 길이 8KB 한계, (c) 일부 로깅 레이어에서 쿼리스트링이 노출. → POST body 선택. SDK 는 `search()` 단일 메서드로 래핑.

### 2.3 Search 응답 shape (items + facets + pagination + meta)

```jsonc
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-Id: 01HXQ8WQ9Z3K7V5B2A1N6P4R9T
X-RateLimit-Limit: 600
X-RateLimit-Remaining: 584
X-RateLimit-Reset: 1713825600        // Unix epoch seconds — next minute window boundary
X-Quota-Limit-Daily: 10000
X-Quota-Remaining-Daily: 9341
X-Quota-Reset-Daily: 1713830400      // Unix epoch seconds — next UTC midnight

{
  "items": [
    {
      "pseudo_study_uid":    "2.25.140737488355328.1.2.3",
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
      "hospital_opaque_id":  "c3d4e5f6a7b8c9d0",   // per-buyer salted sha; different buyer sees different value
      "ingested_at":         "2026-04-21T03:20:51Z"
    }
    /* ...up to 50 items... */
  ],

  "facets": {
    "modality":     [
      {"value": "CT", "count": 42318, "is_truncated": false},
      {"value": "MR", "count": 18244, "is_truncated": false}
    ],
    "body_part":    [
      {"value": "CHEST",   "count": 31055, "is_truncated": false},
      {"value": "ABDOMEN", "count": 29507, "is_truncated": false}
    ],
    "sex":          [
      {"value": "M", "count": 33210, "is_truncated": false},
      {"value": "F", "count": 27108, "is_truncated": false},
      {"value": null, "count": 244, "is_truncated": false}
    ],
    "age_bucket":   [
      {"value": "60-70", "count": 21099, "is_truncated": false},
      {"value": "50-60", "count": 19463, "is_truncated": false}
    ],
    "manufacturer": [
      {"value": "SIEMENS",   "count": 14222, "is_truncated": false},
      {"value": "GE",        "count": 11805, "is_truncated": false},
      {"value": "PHILIPS",   "count":  7011, "is_truncated": false},
      {"value": "__other__", "count":   312, "is_truncated": true}
    ],
    "year":         [
      {"value": "2026", "count":  4012, "is_truncated": false},
      {"value": "2025", "count": 18998, "is_truncated": false},
      {"value": "2024", "count": 21033, "is_truncated": false}
    ]
  },

  "pagination": {
    "next_cursor": "eyJ2IjoxLCJkIjoiMjAyNi0wNC0xOCIsInAiOjEyMzQ1LCJzIjoiWWJNM3o3SzlRYVAxIiwiayI6ImRhdGVfZGVzYyJ9",
    "has_more":    true,
    "page_size":   50
  },

  "meta": {
    "total_hint":             60562,
    "total_count_exact":      true,
    "result_is_approximate":  false,
    "query_duration_ms":      842,
    "buyer_quota_remaining":  9341,
    "buyer_tier":             "paid",
    "facets_suppressed":      false,
    "response_truncated":     false
  }
}
```

**주요 설계 결정**

1. **`items[]` + `facets{}` + `pagination{}` + `meta{}` 4 top-level 블록**. dev-spec §7.1 의 플랫 스타일(`next_cursor`, `has_next`, `page_size` 가 루트에 존재) 에서 **의미 그룹화 개선**. dev-spec 원 응답 필드는 그대로 유지하되, 본 디자인은 `pagination`/`meta` 네임스페이스로 **추가 그룹핑**을 권고(§12 Open Q 로 Kyle 결정 보류).
2. **`total_hint` 의 "exact vs approximate" 신호**:
   - `total_count_exact: true` + `result_is_approximate: false` → `total_hint` 는 정확한 `COUNT(*)` 결과. 구매자는 이 값으로 매출 추정 가능.
   - `total_count_exact: false` → PG planner 기반 estimate. 구매자는 UI 에 "≈" 기호 표시 권고.
   - `result_is_approximate: true` → `items[]` 은 정확하지만 total 은 추정 (대규모 facet 자동 suppression 과 짝).
3. **`buyer_quota_remaining` 은 응답 바디에 + `X-Quota-Remaining-Daily` 헤더에 중복 노출**. 헤더가 표준(브라우저 DevTools 에서 바로 보임), 바디는 SDK 파싱 용이성. 두 값은 항상 일치.
4. **`query_duration_ms`** — buyer 가 p95 latency 를 직접 관찰할 수 있어 자사 SLA/대시보드에 반영. 내부 정확 측정치 그대로 노출 (sensitive 정보 아님).

### 2.4 Cursor 포맷 — opaque 계약

**구매자가 보는 것**: `eyJ2IjoxLCJkIjoiMjAyNi0wNC0xOCIsInAiOjEyMzQ1LCJzIjoiWWJNM3o3SzlRYVAxIiwiayI6ImRhdGVfZGVzYyJ9` — **base64url(no padding) 인코딩된 불투명 문자열**. 내부 필드(`v`, `d`, `p`, `s`, `k`) 는 **공식 문서에 노출하지 않는다**.

**공개 문서 문구 (OpenAPI description)**:

```
cursor (string, optional): An opaque pagination token returned by the server as
`pagination.next_cursor` in a previous response. Pass it back as-is to fetch
the next page. Treat this value as opaque — its structure may change between
versions. Cursors are tied to the filter used when the cursor was issued;
changing any filter field invalidates the cursor and produces
ERR_CURSOR_FILTER_CHANGED. Cursors do not expire on a wall clock but may be
invalidated by server version upgrades (ERR_CURSOR_VERSION).
```

**Cursor 무효화 (invalidation) 시나리오 + 구매자 복구**

```
Scenario 1: buyer changes filter between pages
─────────────────────────────────────────────────
Page 1 request:
  { "modality": ["CT"], "limit": 50 }
  → 200, next_cursor = "eyJ2..."
Page 2 request (BUG: filter changed):
  { "modality": ["CT", "MR"], "limit": 50, "cursor": "eyJ2..." }
  → 400 ERR_CURSOR_FILTER_CHANGED
  {
    "error":      "ERR_CURSOR_FILTER_CHANGED",
    "detail":     "cursor was issued for a different filter; filter_sha256 mismatch",
    "message_en": "The cursor was issued with a different filter. Restart from page 1 with the new filter.",
    "message_ko": "이전 페이지와 필터가 달라졌습니다. 새 필터로 1페이지부터 다시 요청하세요.",
    "hint":       "Drop the `cursor` field and re-send with the new filter to get page 1."
  }

Recovery: client drops cursor, re-sends page 1 of the new filter.
```

**내부 cursor JSON** (구매자 비공개, dev-spec §4.4 FR-25):

```jsonc
{
  "v": 1,                          // version — bump breaks forward-compat
  "d": "2026-04-18",               // sort key value (date) of last-row-of-previous-page
  "p": 12345,                      // tiebreaker study_pk
  "s": "YbM3z7K9QaP1",             // sha256(canonical_filter || sort_key)[:12] base64url — 필터 변조 감지
  "k": "date_desc"                 // sort key (date_desc | ingested_desc)
}
```

본 cursor 는 **base64url(no padding)** 으로 인코딩되어 문자열로 직렬화된다. 공개 문서에는 "opaque" 이라고만 명시하고 위 필드 shape 은 **공개하지 않는다**. 내부 구현자·SRE 는 `search-admin debug cursor <TOKEN>` 으로 디코드 가능(v0.2 예정).

### 2.5 Facet 응답 shape

각 패싯 필드는 `[{value, count, is_truncated}, ...]` 배열. 최대 50 bucket 노출, 51번째 이상은 `{"value": "__other__", "count": N, "is_truncated": true}` 로 요약.

**`is_truncated` 시맨틱**:

- `false` — 이 bucket 의 count 는 정확하고 이 값 이하 다른 버킷이 없다.
- `true` — 이 bucket 은 "나머지 전체" 를 요약한다(`__other__`). 구체 값 목록을 얻고 싶으면 **해당 필드를 filter 로 좁혀 재검색** 해야 한다.

**buyer 질문 "전체 제조사 목록을 얻고 싶다"** 에 대한 공식 답변:

1. `GET /v1/search/facets` 호출 (필터 없는 전역 facet) → 전체 상위 50개 manufacturer + 그 외 `__other__`.
2. `__other__` 이 여전히 존재하면 `POST /v1/search/studies` 에 `manufacturer != SIEMENS,GE,...` (제외) 로 재검색 — 이 패턴은 v0.2 에서 `not_in` 필터로 승격 예정 (§12 Q-5).
3. 그 외: 운영팀에 문의. v0.1 은 의도적으로 `__other__` 를 공개한다(제조사 롱테일이 탐색·경쟁 가치).

**NULL 버킷**: `value: null` 은 **허용** — "해당 필드 미지정" 스터디가 존재함을 알린다. 구매자 클라이언트는 null 버킷을 "Unknown" UI 라벨로 렌더 권고.

### 2.6 에러 응답 예시 3종 (구매자 DX 의 핵심)

아래 3 개는 **구매자가 실제로 가장 자주 만나는 에러** 이며, OpenAPI `examples:` 에 모두 수록하여 Swagger UI 우측 "Try it out" 에서 그대로 보이게 한다.

**(a) 422 — `ERR_QUERY_TOO_BROAD` (가장 흔한 PoC 초기 실수)**

```
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json
X-Request-Id: 01HXQQTB8...

{
  "error":       "ERR_QUERY_TOO_BROAD",
  "detail":      "estimated rows 12,833,091 exceeds limit 10,000,000",
  "message_ko":  "쿼리가 너무 광범위합니다 (예상 약 1,280만 건). 모달리티 또는 날짜 범위를 좁혀주세요.",
  "message_en":  "Query is too broad (estimated ~12.8M rows, limit 10M). Narrow modality or date range.",
  "request_id":  "01HXQQTB8...",
  "doc_url":     "https://docs.radivault.io/search/errors/ERR_QUERY_TOO_BROAD",
  "hint":        "Try adding modality=['CT'] or study_date_shifted.from='2024-01-01'. Planner-estimated rows: 12,833,091.",
  "retry_after": null,
  "extra": {
    "estimated_rows":       12833091,
    "estimated_rows_limit": 10000000,
    "suggested_filters":    ["modality", "study_date_shifted"]
  }
}
```

> **설계 포인트**: `extra.estimated_rows` 를 바디에 명시해 **구매자가 UI 에 "약 1280만 건 너무 많음" 을 그대로 표시**할 수 있게 한다. `hint` 는 사람 가독, `extra` 는 기계 가독.

**(b) 400 — `ERR_CURSOR_FILTER_CHANGED` (buyer 스크립트 버그의 top 원인)**

```
HTTP/1.1 400 Bad Request
Content-Type: application/json
X-Request-Id: 01HXQCFC2...

{
  "error":       "ERR_CURSOR_FILTER_CHANGED",
  "detail":      "cursor filter_sha256 mismatch; cursor was issued for a different filter",
  "message_ko":  "커서 이후 필터가 변경되었습니다. 1페이지부터 다시 시작하세요.",
  "message_en":  "The cursor was issued for a different filter. Please restart from page 1 without the cursor, using your current filter.",
  "request_id":  "01HXQCFC2...",
  "doc_url":     "https://docs.radivault.io/search/errors/ERR_CURSOR_FILTER_CHANGED",
  "hint":        "Drop the `cursor` field from your request body and re-send. Your filter change will take effect from page 1.",
  "retry_after": null
}
```

> **설계 포인트**: `hint` 가 **"어떤 한 줄 코드 변경이 필요한가"** 를 지시. buyer SDK 는 이 코드를 내부 catch 하여 자동 재시작하거나, 호출자에게 "Your filter changed, restarting iteration" 경고를 띄우도록 가이드.

**(c) 429 — `ERR_BUYER_QUOTA` (영업 업셀 시그널)**

```
HTTP/1.1 429 Too Many Requests
Retry-After: 14382
X-Quota-Limit-Daily: 100
X-Quota-Remaining-Daily: 0
X-Quota-Reset-Daily: 1713830400
Content-Type: application/json
X-Request-Id: 01HXQQUO5...

{
  "error":       "ERR_BUYER_QUOTA",
  "detail":      "daily quota exhausted: 100/100 requests used; resets at 2026-04-23T00:00:00Z",
  "message_ko":  "일일 쿼터(100회)를 모두 사용했습니다. 3시간 59분 후 재설정됩니다. 유료 전환 시 일일 10,000회로 상향됩니다.",
  "message_en":  "Daily quota exhausted (100/100). Quota resets at 2026-04-23T00:00:00Z (in ~4h). Upgrade to the paid tier for 10,000 requests/day.",
  "request_id":  "01HXQQUO5...",
  "doc_url":     "https://docs.radivault.io/search/errors/ERR_BUYER_QUOTA",
  "hint":        "Contact sales@radivault.io to discuss an upgrade. Preview tier → Paid tier provides 100× capacity and removes facet auto-suppression.",
  "retry_after": 14382,
  "extra": {
    "tier":                   "preview",
    "quota_used":             100,
    "quota_limit":            100,
    "quota_reset_at":         "2026-04-23T00:00:00Z",
    "upgrade_contact":        "sales@radivault.io",
    "paid_tier_daily_limit":  10000
  }
}
```

> **설계 포인트**: 본 응답은 **영업 기회**다. `hint` 에 업그레이드 연락처 명시, `extra.upgrade_contact` 에 sales 이메일, `paid_tier_daily_limit` 로 숫자 비교 제공. 동시에 `radivault_index_quota_exhausted_total{buyer_tier="preview"}` 메트릭이 증가해 영업이 실시간 알림을 받는다 (§4.4 alert A-7).

### 2.7 Rate-limit · Quota 응답 헤더 계약

**모든 성공 응답(200/201/...) 과 429 에** 아래 헤더를 포함한다.

| 헤더 | 값 타입 | 의미 | 예시 |
|------|---------|------|------|
| `X-RateLimit-Limit` | integer | 현재 windowing scope 의 per-minute 한도 | `600` |
| `X-RateLimit-Remaining` | integer | 남은 per-minute 요청 수 | `584` |
| `X-RateLimit-Reset` | integer (Unix epoch seconds) | 다음 per-minute window 가 열리는 시각 | `1713825600` |
| `X-Quota-Limit-Daily` | integer | 일일 쿼터 (00:00 UTC 기준) | `10000` |
| `X-Quota-Remaining-Daily` | integer | 남은 일일 쿼터 | `9341` |
| `X-Quota-Reset-Daily` | integer (Unix epoch seconds) | 다음 UTC 자정 | `1713830400` |
| `Retry-After` | integer (seconds) | 429 응답에만. `retry_after` body 필드와 일치 | `27` |
| `X-Request-Id` | string (ULID) | 서버 생성, 모든 응답에 | `01HXQ8WQ9Z3K7V5B2A1N6P4R9T` |

**원칙**:

- `X-RateLimit-*` 는 IETF draft `draft-ietf-httpapi-ratelimit-headers` 를 참고한 사실상 표준 이름. GitHub·Stripe 등 주요 API 와 일관.
- `X-Quota-*` 는 RadiVault 고유 — 일일 쿼터 차원을 per-minute 과 분리해 buyer 에게 명확히 전달.
- Rate-limit 초과(429 + `ERR_RATE_LIMITED`) 와 일일 쿼터 초과(429 + `ERR_BUYER_QUOTA`) 는 **동일 상태코드, 다른 에러 코드** 로 구분. 헤더는 둘 다 세팅.

### 2.8 Content-Type 규칙

| 엔드포인트 | Request Content-Type | Response Content-Type | 비고 |
|-----------|----------------------|------------------------|------|
| `POST /v1/search/studies` | `application/json` 필수 | `application/json` | 그 외 → `415 ERR_UNSUPPORTED_MEDIA` |
| `GET /v1/search/studies/{uid}` | — | `application/json` | |
| `GET /v1/search/facets` | — | `application/json` | |
| `GET /v1/search/hospitals` | — | `application/json` | |
| `GET /healthz`·`/readyz`·`/v1/version` | — | `application/json` | 인증 불필요 |
| `GET /metrics` | — | `text/plain; version=0.0.4` | Prometheus scrape |
| `GET /openapi.json`·`/docs` | — | `application/json` · `text/html` | 인증 불필요, 공개 문서화 |

**`Accept` 헤더**: 없거나 `*/*`·`application/json` 이면 JSON. 그 외(`text/xml` 등) → `406 Not Acceptable` + `ERR_NOT_ACCEPTABLE` (central-ingest §2.7 재사용).

### 2.9 CORS 정책 (기본 deny, 명시적 allowlist)

**v0.1 기본값**: `Access-Control-Allow-Origin` 을 설정하지 **않는다** — browser-based 직접 호출 비허용. 구매자의 모든 호출은 **서버사이드 (curl/Python/Node 백엔드)** 에서 일어나야 한다.

**예외 (화이트리스트)**: 구매자 측 내부 개발 대시보드(예: buyer 의 자사 내부 Grafana) 가 필요 시 Origin 별 allowlist 로 enable:

```yaml
# search.yml
cors:
  enabled: false                         # v0.1 default
  allowed_origins: []                    # 예: ["https://dashboard.acme-ai.com"]
  allowed_methods: ["GET", "POST"]
  allowed_headers: ["Authorization", "Content-Type", "X-Request-Id"]
  exposed_headers:
    - "X-Request-Id"
    - "X-RateLimit-Limit"
    - "X-RateLimit-Remaining"
    - "X-RateLimit-Reset"
    - "X-Quota-Limit-Daily"
    - "X-Quota-Remaining-Daily"
    - "X-Quota-Reset-Daily"
    - "Retry-After"
  allow_credentials: false
  max_age_seconds: 600
```

**근거**:

- Browser 직접 호출은 API key 를 JS 에 노출 → 유출 리스크. 기본 deny 가 방어적.
- `allow_credentials: false` 고정 — API key 는 Authorization 헤더로만 전달, cookie 인증 사용 안 함.
- `exposed_headers` 에 rate-limit·quota 헤더 모두 포함(browser JS 에서 읽을 수 있어야 buyer 대시보드 기능이 성립).

### 2.10 API 버전 정책 (`/v1/` prefix + deprecation 헤더)

| 원칙 | 정책 |
|------|------|
| **URL 버전** | 모든 엔드포인트는 `/v1/` prefix. `/search/...`, `/v2/...` 병존 가능. 마이너 breaking 은 disable. |
| **Breaking change 정의** | (a) 필드 삭제, (b) 필드 타입 변경, (c) 에러 코드 의미 변경, (d) 기본값 변경 중 하나 이상. → `/v2/` 로만 노출. |
| **Non-breaking 추가** | (a) 새 필드 추가(옵셔널), (b) 새 엔드포인트, (c) 새 에러 코드 추가 → `/v1/` 내에서 가능. |
| **Deprecation 고지** | 삭제 예정 엔드포인트는 응답에 `Deprecation: Sun, 31 Dec 2027 23:59:59 GMT` + `Link: <...>; rel="deprecation"` 헤더 6개월 이상 선행. |
| **Sunset 헤더** | RFC 8594 `Sunset: <date>` 으로 종료 시각 명시. |
| **API contract version** | `/v1/version` 응답의 `api_contract_version` 필드. breaking 시 bump. |

---

## 3. Operator CLI — `search-admin`

### 3.1 설계 원칙 (central-ingest §3.1 과 동일 + 검색 도메인 특화)

- **영어 우선 UI**, `--lang ko` 옵션은 v0.1 optional.
- **종료 코드** BSD sysexits (`0` OK, `1` 일반 실패, `2` DB error, `64` usage error, `69` not found, `70` internal).
- **`--json`** — 모든 read 명령. 자동화 스크립트·대시보드 연동용.
- **`--dry-run`** — 모든 write 명령(`buyer create`, `key issue`, `key revoke`, `migrate up`).
- **`--no-color`** / `NO_COLOR=1` 환경변수 준수.
- **바이너리 분리**: `ingest-admin` 과 별도 바이너리 `search-admin`. 운영자가 "ingest 문제" 와 "search 문제" 를 혼동 없이 구분. §12 Q-6 에 Kyle 결정 보류(통합 vs 분리).

### 3.2 명령 트리 (전체)

```
search-admin
├── buyer
│   ├── create        --company NAME --contact-email EMAIL --tier {preview|paid} [--note STR] [--json] [--dry-run]
│   ├── show          --buyer-id BID [--json]
│   ├── list          [--tier TIER] [--active-only] [--json]
│   └── update        --buyer-id BID [--tier TIER] [--note STR] [--active {true|false}] [--dry-run]
├── key
│   ├── issue         --buyer-id BID [--tier TIER] [--expires-days N] [--scope-json JSON] [--dry-run] [--json]
│   ├── revoke        --kid KID [--reason STR]
│   └── list          [--buyer-id BID] [--include-revoked] [--json]
├── stats
│   ├── top-queries   [--since 7d] [--limit N] [--json]        # filter_sha256 + count only, no raw filter
│   ├── buyer-usage   --buyer-id BID [--period {day|week|month}] [--json]
│   └── empty-rate    [--since 7d] [--json]                    # per-buyer empty-result rate
├── facet
│   └── warm                                                     # prewarm /v1/search/facets cache
├── migrate
│   ├── up            [--revision REV] [--dry-run]
│   ├── down          --revision REV [--dry-run]
│   └── current
└── version           [--json]
```

**전역 플래그**

| 플래그 | 설명 |
|--------|------|
| `-c, --config PATH` | 기본 `/etc/radivault-search/search.yml` 또는 `$RADIVAULT_SEARCH_CONFIG` |
| `--database-url URL` | Config override (CLI 는 `search_admin` role DSN 사용) |
| `--log-level LEVEL` | DEBUG \| INFO \| WARN \| ERROR |
| `--no-color` | ANSI 색 비활성 |
| `--quiet` | WARN 이하 억제 |
| `-h, --help` | 도움말 |
| `-V, --version` | `version` 서브커맨드 동일 |

### 3.3 `search-admin buyer create`

```
$ search-admin buyer create --help
Usage: search-admin buyer create [OPTIONS]

  Enroll a new buyer organization. Creates a `buyer` row; no API key is issued yet.
  Run `search-admin key issue --buyer-id <BID>` separately to issue the first key.

Options:
  --company TEXT           Legal name of the buyer company (e.g., "Acme AI, Inc.")  [required]
  --contact-email TEXT     Primary technical contact email                            [required]
  --tier [preview|paid]    Default tier for keys issued under this buyer             [default: preview]
  --note TEXT              Freeform note (salesforce-id, MSA reference, etc.)
  --dry-run                Validate inputs but do not insert
  --json                   Emit JSON instead of the framed text block
  -h, --help

Exit codes:
  0   Buyer created
  1   Validation error (e.g., email already enrolled)
  2   DB error
  64  Usage error
  70  Internal
```

**Happy-path (텍스트 출력)**

```
$ search-admin buyer create --company "Acme AI, Inc." --contact-email integrations@acme-ai.com --tier preview --note "MSA: 2026-04-22"
═══════════════════════════════════════════════════════════════════════════════
 RadiVault Search — new buyer enrolled
═══════════════════════════════════════════════════════════════════════════════
 buyer_id      : buy_acme_001
 company       : Acme AI, Inc.
 contact_email : integrations@acme-ai.com
 tier          : preview
 note          : MSA: 2026-04-22
 enrolled_at   : 2026-04-22T10:00:00Z
───────────────────────────────────────────────────────────────────────────────
 Next steps:
  1. Share the Buyer Onboarding doc:
     https://docs.radivault.io/search/onboarding
  2. Issue the first API key:
     search-admin key issue --buyer-id buy_acme_001
═══════════════════════════════════════════════════════════════════════════════
```

**실패 시나리오**

| 상황 | exit | 메시지 |
|------|------|--------|
| 동일 `contact_email` 이미 enrolled | 1 | `[ERR_ADMIN_BUYER_DUPLICATE] contact_email already enrolled: integrations@acme-ai.com → buy_acme_001` |
| 이메일 형식 위반 | 64 | `[ERR_ADMIN_USAGE] --contact-email must be a valid RFC 5322 email` |
| DB 접속 실패 | 2 | `[ERR_ADMIN_DB_UNAVAILABLE] PostgreSQL unreachable — DATABASE_URL 확인` |

### 3.4 `search-admin buyer list`

```
$ search-admin buyer list --tier paid --active-only
BUYER_ID        COMPANY                 TIER    CONTACT_EMAIL                   ENROLLED_AT          ACTIVE  KEYS_ACTIVE
buy_acme_001    Acme AI, Inc.           paid    integrations@acme-ai.com        2026-04-22 10:00Z    yes     2
buy_mediq_007   MediQ Research          paid    api@mediq-research.jp           2026-04-18 03:00Z    yes     1
buy_fdarad_002  FDA-Rad Startup         paid    hello@fdarad.com                2026-03-30 15:22Z    yes     3

3 buyers (3 active, 0 suspended)
```

`--json`:

```json
{
  "filter": {"tier": "paid", "active_only": true},
  "buyers": [
    {"buyer_id":"buy_acme_001","company":"Acme AI, Inc.","tier":"paid","contact_email":"integrations@acme-ai.com","enrolled_at":"2026-04-22T10:00:00Z","active":true,"keys_active":2}
  ],
  "summary": {"total": 3, "active": 3, "suspended": 0}
}
```

### 3.5 `search-admin key issue`

```
$ search-admin key issue --buyer-id buy_acme_001 --tier paid --expires-days 180 --note "initial-production-key"
═══════════════════════════════════════════════════════════════════════════════
 RadiVault Search — new API key issued
═══════════════════════════════════════════════════════════════════════════════
 buyer_id      : buy_acme_001
 tier          : paid
 kid           : abcd1234
 expires_at    : 2026-10-19T10:00:00Z  (180 days)
 issued_at     : 2026-04-22T10:00:00Z
 note          : initial-production-key
───────────────────────────────────────────────────────────────────────────────
 Plaintext API key (shown ONCE, store now):

   rv_live_abcd1234_Zj8f2vX9qK2sLpN4mQbW7yR1eT5aU6cD8gH0iK3

───────────────────────────────────────────────────────────────────────────────
 Next steps:
  1. Hand this key to the buyer technical contact via an encrypted channel
     (1Password share link / age-encrypted file). NEVER paste into email,
     Slack DM, or a support ticket body.
  2. Buyer must store it in an environment variable or a secrets manager.
  3. Send the Onboarding walkthrough link:
     https://docs.radivault.io/search/onboarding
═══════════════════════════════════════════════════════════════════════════════
```

**중요**: 평문 키는 stdout 에 **단 1회** 출력. DB 에는 argon2id 해시만 저장(dev-spec FR-3). 운영자가 terminal scrollback 을 캡처하는 것 외에는 재표시 수단 없음. `--dry-run` 시에는 "would issue, but not inserting" 표시만.

**실패 시나리오**

| 상황 | exit | 메시지 |
|------|------|--------|
| `--buyer-id` 존재하지 않음 | 69 | `[ERR_ADMIN_BUYER_NOT_FOUND] buyer_id not found: buy_unknown` |
| buyer 가 `active=false` | 1 | `[ERR_ADMIN_BUYER_INACTIVE] buyer buy_acme_001 is inactive; run 'buyer update --active true' first` |
| argon2 해시 실패 | 70 | `[ERR_ADMIN_HASH_FAIL] argon2id hashing failed — config.auth.argon2 튜닝 확인` |

### 3.6 `search-admin key revoke`

```
$ search-admin key revoke --kid abcd1234 --reason "buyer reported compromise 2026-04-22"
[OK] revoked key kid=abcd1234 at 2026-04-22T10:05:12Z
     buyer_id         : buy_acme_001
     reason           : buyer reported compromise 2026-04-22
     active keys remaining for this buyer: 1

Next steps:
  1. Notify the buyer via the contact-email registered on the buyer row
     (integrations@acme-ai.com) — see RB-7 template.
  2. If 1 active key remains, suggest immediate rotation.
  3. If 0 active keys remain, the buyer has NO working key — escalate to sales.
```

**에러**: `--kid` 미존재 → `ERR_ADMIN_KEY_NOT_FOUND` (exit 69). 이미 revoked → `ERR_ADMIN_KEY_ALREADY_REVOKED` (exit 1, idempotent 정보만). `--reason` 은 `search_audit` 가 아닌 `buyer_api_key.note` 에 append.

### 3.7 `search-admin key list`

```
$ search-admin key list --buyer-id buy_acme_001
BUYER_ID      KID         TIER    ISSUED_AT            EXPIRES_AT           LAST_USED            STATUS     NOTE
buy_acme_001  abcd1234    paid    2026-04-22 10:00Z    2026-10-19 10:00Z    2026-04-22 14:30Z    active     initial-production-key
buy_acme_001  ef567890    paid    2026-04-20 09:00Z    2026-10-17 09:00Z    2026-04-21 23:45Z    active     pilot-legacy

2 keys (2 active, 0 revoked, 0 expired)
```

### 3.8 `search-admin stats top-queries`

```
$ search-admin stats top-queries --since 7d --limit 10
Top 10 filter_sha256 over the last 7 days (2026-04-15 → 2026-04-22):

FILTER_SHA256                                                       COUNT    EMPTY_RATE  AVG_LATENCY
8f4c2a1d5b6e7f8a9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b     4,123    2.1%        412ms
7a3b9c2d1e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b     2,881    38.4%       2,104ms  ← high empty-rate
5d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e     1,007    0.5%        89ms
...

Summary: 4,123 top filter was used 4,123 times across 14 buyers (39% of total traffic).

Note: raw filter bodies are NEVER stored. Only sha256(canonical_filter || GLOBAL_SALT) is logged.
```

**PHI 차단**: `top-queries` 는 **filter_sha256 + 빈도 + latency** 만 출력. raw 필터 본문·값 목록은 DB 에 없고 CLI 도 절대 출력하지 않는다. SRE 가 "이 sha 가 어떤 필터를 의미하는지" 를 알려면 **buyer 에게 직접 문의** 해야 한다(의도된 정보 차단).

### 3.9 `search-admin stats buyer-usage`

```
$ search-admin stats buyer-usage --buyer-id buy_acme_001 --period week
Buyer: buy_acme_001 (Acme AI, Inc.)  tier=paid
Period: 2026-04-15 → 2026-04-22

DAILY BREAKDOWN
DATE         REQUESTS  200   4xx   5xx   AVG_LATENCY  QUOTA_USED
2026-04-15   0         0     0     0     —            0%
2026-04-16   34        34    0     0     402ms        0.3%
2026-04-17   1,284     1,201 82    1     811ms        12.8%
2026-04-18   4,921     4,800 120   1     1,204ms      49.2%
2026-04-19   6,102     6,001 100   1     1,302ms      61.0%   ← trending up
2026-04-20   8,441     8,402 39    0     1,211ms      84.4%   ← approaching paid limit
2026-04-21   9,102     9,055 45    2     1,322ms      91.0%   ← P2 candidate
2026-04-22   2,110     2,098 12    0     1,189ms      21.1%   (partial day)

TOP 3 ERRORS
ERR_QUERY_TOO_BROAD       128
ERR_RATE_LIMITED           76
ERR_CURSOR_FILTER_CHANGED  48

SALES SIGNAL: 91% quota use on 2026-04-21 → follow-up upsell opportunity.
```

### 3.10 `search-admin stats empty-rate`

```
$ search-admin stats empty-rate --since 7d
Buyer empty-result rate (last 7 days):

BUYER_ID        TIER    REQUESTS  EMPTY   RATE
buy_mediq_007   paid    2,831     1,084   38.3%   ← A-1 alarm threshold exceeded
buy_acme_001    paid    31,994    421     1.3%
buy_fdarad_002  paid    8,112     91      1.1%

Suggested action: for buy_mediq_007, contact the buyer's integration lead
to understand the filter UX issue. RB-1 guidance available.
```

### 3.11 `search-admin facet warm`

```
$ search-admin facet warm
Warming /v1/search/facets cache (global, no filter)...
  modality:     computed 12 values in 242ms
  body_part:    computed  34 values in 291ms
  sex:          computed   3 values in  18ms
  age_bucket:   computed   8 values in  24ms
  manufacturer: computed  18 values in 312ms
  year:         computed   9 values in  11ms
[OK] cache warmed. next expiry: 2026-04-22T10:15:00Z (TTL 15m)
```

### 3.12 `search-admin migrate`

`central-ingest migrate` 와 동일 UX — central-ingest design-spec §3.9 를 그대로 승계. **단, `search-admin migrate up` 은 `MIGRATION_DATABASE_URL` (superuser) 전용**. 일반 `search_admin` role DSN 으로 호출 시 `ERR_ADMIN_WRONG_ROLE` 반환 (central-ingest §5.5 재사용).

### 3.13 `search-admin version`

```
$ search-admin version
radivault-search   0.1.0
build              ab12cd34 (2026-04-22T09:00:00Z)
api_contract       1
python             3.11.9
postgres_client    psycopg 3.1.18
redis_client       redis-py 5.0.7

$ search-admin version --json
{"service":"radivault-search","version":"0.1.0","git_sha":"ab12cd34",
 "built_at":"2026-04-22T09:00:00Z","api_contract_version":"1",
 "python":"3.11.9","psycopg":"3.1.18","redis":"5.0.7"}
```

### 3.14 종료 코드 요약

| Command | 0 | 1 | 2 | 64 | 69 | 70 |
|---------|---|---|---|----|----|----|
| `buyer create` | OK | Duplicate email | DB error | Usage | — | Internal |
| `buyer list/show` | OK | — | DB error | Usage | Not found | — |
| `buyer update` | OK | Validation | DB error | Usage | Not found | Internal |
| `key issue` | OK | Buyer inactive | DB error | Usage | Buyer not found | Hash fail |
| `key revoke` | OK | Already revoked | DB error | Usage | KID not found | — |
| `key list` | OK | — | DB error | Usage | — | — |
| `stats *` | OK | — | DB error | Usage | — | — |
| `facet warm` | OK | Partial fail | DB error | — | — | — |
| `migrate up/down` | OK | Revision conflict | DB error | Usage | — | Internal |
| `migrate current` | OK | — | DB error | — | — | — |
| `version` | 항상 0 | — | — | — | — | — |

---

## 4. Log & Observability 출력

### 4.1 JSON 로그 schema (central-ingest §4.1 확장)

모든 로그는 stdout 에 JSON-lines 방출. central-ingest 의 공통 shape 을 상속하고 **검색 도메인 고유 필드 8종을 추가**:

```jsonc
{
  "ts":          "2026-04-22T10:20:01.234Z",
  "level":       "INFO",
  "service":     "radivault-search",                   // ← central 과 구분
  "logger":      "radivault_search.api.search",
  "trace_id":    "6a8c9e0f1b2d3c4e5f6a7b8c9d0e1f2a",
  "span_id":     "0123456789abcdef",
  "request_id":  "01HXQ8WQ9Z3K7V5B2A1N6P4R9T",
  "event":       "search.request.completed",           // namespace.action
  "message_ko":  "검색 완료 — buy_acme tier=paid, 128 rows, 412ms",
  "message_en":  "Search completed for buy_acme tier=paid, 128 rows, 412ms",
  "path":        "/v1/search/studies",
  "method":      "POST",
  "status":      200,
  "duration_ms": 412,

  // ── 검색 전용 필드 (8개) ──
  "buyer_id_hash":    "sha256:a7b9c2...",              // buyer_id 의 sha256 prefix (raw id 금지)
  "kid":              "abcd1234",                      // key id prefix only (secret 금지)
  "buyer_tier":       "paid",
  "filter_sha256":    "8f4c2a1d5b6e7f8a9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b",
  "filter_fields":    ["modality","body_part","study_date_shifted","min_hospitals"],  // 키 이름만, 값 없음
  "result_count":     128,
  "cursor_present":   false,                           // 본 요청에 cursor 가 있었는가 (boolean)
  "facets_requested": true,
  "cost_estimate_rows": 128342,                        // planner estimate at decision time
  "cache_hit":        {"auth": true, "cost": false, "facet": false}
}
```

**금지 필드** (dev-spec §6.6 · §4.10 FR-52 · 본 문서 §6.7): 원본 StudyInstanceUID, 환자 식별자, 병원 내부 호스트, **raw filter body**, **raw cursor JSON**, **API key plaintext**, **buyer_id plain text**. Logger sanitiser 가 감지 시 레코드 drop + `ERR_LOG_PHI_DETECTED` 카운터 증가 (central-ingest §4.1 와 동일 메커니즘).

### 4.2 5-line 현실적 예시 (이벤트 5종)

```json
{"ts":"2026-04-22T10:20:01.234Z","level":"INFO","service":"radivault-search","logger":"radivault_search.api.search","trace_id":"6a8c...","span_id":"0123...","request_id":"01HXQREQ1","event":"search.request.completed","message_en":"Search completed for buy_acme tier=paid, 128 rows, 412ms","path":"/v1/search/studies","method":"POST","status":200,"duration_ms":412,"buyer_id_hash":"sha256:a7b9c2","kid":"abcd1234","buyer_tier":"paid","filter_sha256":"8f4c2a1d","filter_fields":["modality","body_part","study_date_shifted"],"result_count":128,"cursor_present":false,"facets_requested":true,"cost_estimate_rows":128342,"cache_hit":{"auth":true,"cost":false,"facet":false}}
{"ts":"2026-04-22T10:20:05.112Z","level":"WARN","service":"radivault-search","logger":"radivault_search.cost","trace_id":"7b9d...","span_id":"0abc...","request_id":"01HXQREQ2","event":"search.cost.rejected","message_en":"Cost estimator rejected overly broad query","path":"/v1/search/studies","method":"POST","status":422,"duration_ms":68,"buyer_id_hash":"sha256:a7b9c2","kid":"abcd1234","buyer_tier":"paid","filter_sha256":"5e2f1a","filter_fields":["modality"],"cost_estimate_rows":12833091,"error_code":"ERR_QUERY_TOO_BROAD"}
{"ts":"2026-04-22T10:20:12.800Z","level":"WARN","service":"radivault-search","logger":"radivault_search.ratelimit","trace_id":"8c0e...","span_id":"1bcd...","request_id":"01HXQREQ3","event":"search.quota.exhausted","message_en":"Daily quota exhausted for preview tier buyer","path":"/v1/search/studies","method":"POST","status":429,"duration_ms":4,"buyer_id_hash":"sha256:f1d2e3","kid":"preview88","buyer_tier":"preview","error_code":"ERR_BUYER_QUOTA","extra":{"quota_used":100,"quota_limit":100}}
{"ts":"2026-04-22T10:21:55.012Z","level":"WARN","service":"radivault-search","logger":"radivault_search.auth","trace_id":"9d1f...","span_id":"2cde...","request_id":"01HXQREQ4","event":"search.auth.failure","message_en":"Authentication failed for unknown kid","path":"/v1/search/studies","method":"POST","status":401,"duration_ms":38,"buyer_id_hash":null,"kid":null,"buyer_tier":null,"error_code":"ERR_AUTH_FORMAT","extra":{"reason":"kid_length_invalid","prefix_observed":"rv_live_x"}}
{"ts":"2026-04-22T10:23:00.101Z","level":"ERROR","service":"radivault-search","logger":"radivault_search.db","trace_id":"ae2a...","span_id":"3def...","request_id":"01HXQREQ5","event":"search.query.timeout","message_en":"PG statement_timeout triggered","path":"/v1/search/studies","method":"POST","status":504,"duration_ms":10002,"buyer_id_hash":"sha256:a7b9c2","kid":"abcd1234","buyer_tier":"paid","filter_sha256":"9a0b1c","filter_fields":["modality","body_part","manufacturer"],"error_code":"ERR_QUERY_TIMEOUT","runbook":"RB-4"}
```

### 4.3 Prometheus 메트릭 네이밍 (`radivault_index_*` prefix)

**네임스페이스**: central-ingest 가 `radivault_central_*` 를 사용하므로, search 서비스는 `radivault_index_*` 로 구분 (dev-spec FR-46 명시). 조직 prefix 가 `radivault_` 로 공통.

**17개 핵심 메트릭**

| # | 이름 | 타입 | 라벨 | 단위 | 설명 |
|---|------|------|------|------|------|
| 1 | `radivault_index_requests_total` | Counter | `endpoint`, `buyer_tier`, `status` | — | 엔드포인트별 요청 총계 |
| 2 | `radivault_index_request_duration_seconds` | Histogram | `endpoint`, `buyer_tier` | seconds | end-to-end latency (버킷: 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10) |
| 3 | `radivault_index_result_rows` | Histogram | `endpoint`, `buyer_tier` | — | 응답 `items[]` 길이 분포 (버킷: 0, 1, 10, 50, 200, 1000) |
| 4 | `radivault_index_empty_result_total` | Counter | `buyer_tier`, `buyer_id_hash` | — | result_count==0 요청 (UX 회귀 시그널) |
| 5 | `radivault_index_cost_estimate_rejected_total` | Counter | `buyer_tier` | — | `ERR_QUERY_TOO_BROAD` 횟수 |
| 6 | `radivault_index_cost_estimate_rows` | Histogram | `endpoint` | — | planner estimate 분포 (버킷: 1e3, 1e4, 1e5, 1e6, 1e7) |
| 7 | `radivault_index_cursor_invalidated_total` | Counter | `reason` (`filter_changed`\|`version_mismatch`) | — | cursor 무효화 (client bug 시그널) |
| 8 | `radivault_index_quota_exhausted_total` | Counter | `buyer_tier`, `scope` (`daily`\|`rpm`\|`concurrency`) | — | rate/quota 초과 (영업 시그널) |
| 9 | `radivault_index_facet_compute_duration_seconds` | Histogram | `facet_field` | seconds | 각 facet GROUP BY 소요 |
| 10 | `radivault_index_cache_hit_total` | Counter | `cache_layer` (`auth`\|`facets`\|`hospitals`\|`cost_estimate`) | — | 캐시 적중 |
| 11 | `radivault_index_auth_failures_total` | Counter | `reason` (`missing`\|`format`\|`expired`\|`kid_not_found`\|`hash_mismatch`) | — | 인증 실패 |
| 12 | `radivault_index_concurrency_inflight` | Gauge | `buyer_tier` | — | 현재 동시 실행 중 요청 |
| 13 | `radivault_index_db_pool_in_use` | Gauge | — | — | 현재 사용 중 DB 커넥션 |
| 14 | `radivault_index_db_pool_size` | Gauge | — | — | 풀 전체 크기 |
| 15 | `radivault_index_search_audit_lag_seconds` | Gauge | — | seconds | search_audit 비동기 큐 지연 (억대 데이터 손실 리스크 시그널) |
| 16 | `radivault_index_readyz_checks` | Gauge | `check` (`db`\|`redis`\|`migrations`) | 0\|1 | readiness 체크 결과 |
| 17 | `radivault_index_build_info` | Gauge | `version`, `git_sha`, `python_version` | — | 1로 고정, 빌드 정보 라벨 |

**원칙** (central-ingest §4.3 과 동일):

- enum 라벨 카디널리티 ≤ 10. `buyer_id_hash` 는 제한적 라벨로만 사용(empty-rate 메트릭) — 장기적으로 prometheus relabel 로 bucket 화 필요.
- 단위는 이름에 포함 (`_seconds`, `_total`, `_rows`).
- Histogram 버킷 명시.

### 4.4 알람 설계 (최소 10편, v0.1 은 11편)

**Severity 규약**: `P1` = 즉시 호출(24/7), `P2` = 업무시간 1시간 내, `P3` = 익영업일.

| # | 이름 | 조건 | 임계 | 지속 | Severity | Runbook | 비고 |
|---|------|------|------|------|----------|---------|------|
| A-1 | `SearchEmptyResultRateHigh` | `sum(rate(radivault_index_empty_result_total[15m])) / sum(rate(radivault_index_requests_total{endpoint="/v1/search/studies",status="200"}[15m])) > 0.40` | 전체의 40% 초과 | 15m | P2 | RB-1 | UX 회귀 시그널 (schema 변경 or facet mismatch) |
| A-2 | `SearchP95LatencyHigh` | `histogram_quantile(0.95, sum(rate(radivault_index_request_duration_seconds_bucket{endpoint="/v1/search/studies"}[5m])) by (le)) > 3` | p95 > 3s | 10m | P2 | RB-3 | 용량 시그널 |
| A-3 | `SearchQuotaExhaustionSpike` | `sum(rate(radivault_index_quota_exhausted_total{scope="daily"}[1h])) by (buyer_tier) > 10` | 시간당 10건 초과 | 1h | P3 | RB-2 | 영업 업셀 or 악의적 polling |
| A-4 | `SearchCostEstimatorRejectionSpike` | `sum(rate(radivault_index_cost_estimate_rejected_total[10m])) > 0.5` | 초당 0.5건 초과 | 10m | P2 | RB-3 | 악용(DoS) or 정상 수요 급증 |
| A-5 | `SearchAuditLagHigh` | `radivault_index_search_audit_lag_seconds > 60` | lag > 60s | 5m | P1 | RB-5 | 매출 데이터 유실 리스크 |
| A-6 | `SearchDbPoolSaturation` | `radivault_index_db_pool_in_use / radivault_index_db_pool_size > 0.8` | > 80% | 5m | P1 | RB-4 | PG read pool |
| A-7 | `SearchPgReplicaLag` (v0.2) | `pg_replication_lag_seconds > 30` | > 30s | 5m | P1 | RB-4 | v0.2 replica 도입 후 |
| A-8 | `SearchCursorChurnHigh` | `sum(rate(radivault_index_cursor_invalidated_total[10m])) by (buyer_id_hash) > 0.1` | buyer당 분당 6회 초과 | 10m | P3 | RB-6 | Client bug 시그널 |
| A-9 | `SearchAuthFailureStorm` | `sum(rate(radivault_index_auth_failures_total[1m])) > 50` | 분당 50건 초과 | 3m | P1 | RB-7 | Key 유출 or brute force |
| A-10 | `SearchRedisDown` | `radivault_index_readyz_checks{check="redis"} == 0` | 즉시 | 2m | P1 | central RB-6 | Search 전체 중단 |
| A-11 | `SearchReadyzFailing` | `radivault_index_readyz_checks == 0` (any check) | 즉시 | 3m | P1 | RB-4 | |

---

## 5. Error Taxonomy UX (5-field 운영자 표)

dev-spec §7.6 + §13.1 의 모든 에러 코드를 5-field 템플릿으로 렌더. central-ingest design-spec §5 와 **동일 포맷**:

```
[<CODE>] <한국어 한 줄> / <English one line>
  상황 / Context
  Buyer action / 구매자 조치
  SRE action / 운영자 조치
  Docs: https://docs.radivault.io/search/errors/<CODE>
```

**HTTP status 정책**: RFC 9110 엄격 준수. 4xx = 클라이언트 책임, 5xx = 서버 책임. 422 는 "request 문법 valid 하나 semantic 거부" 에만 (OpenAPI pydantic 검증 실패는 의도적으로 400 — Gateway re-try 로직과 일관).

### 5.1 Auth 영역

| Code | HTTP | 발생 조건 | message_ko | message_en | Buyer 조치 | SRE 조치 | Doc |
|------|------|-----------|------------|------------|-------------|-----------|-----|
| `ERR_AUTH_MISSING` | 401 | Authorization 헤더 누락 | 인증 헤더가 필요합니다. | Authorization header is required. | `Authorization: Bearer rv_live_...` 추가. | — | .../ERR_AUTH_MISSING |
| `ERR_AUTH_FORMAT` | 401 | key prefix/length 위반 (`rv_live_` 또는 `rv_test_` 불일치, 길이 != 48) | 키 형식이 올바르지 않습니다. | API key format invalid. | 키 전체를 붙여넣었는지 확인 (공백·줄바꿈 제거). | — | .../ERR_AUTH_FORMAT (신규) |
| `ERR_AUTH_EXPIRED` | 401 | revoked_at 설정되거나 expires_at 경과 | 인증 키가 만료되거나 철회되었습니다. | API key has expired or been revoked. | 영업에 재발급 요청 — sales@radivault.io. | `search-admin key issue --buyer-id <BID>` 재발급. RB-7 참조. | .../ERR_AUTH_EXPIRED |
| `ERR_SCOPE_FORBIDDEN` | 403 | scope_json 부족 (예: hospital `name_public` 요청인데 tier=preview) | 해당 리소스 접근 권한이 없습니다. | Your API key lacks the required scope for this resource. | 영업 협의. | `search-admin buyer show` 로 scope_json 확인 후 수정. | .../ERR_SCOPE_FORBIDDEN (신규) |

### 5.2 Request Validation 영역

| Code | HTTP | 발생 조건 | message_ko | message_en | Buyer 조치 | SRE 조치 | Doc |
|------|------|-----------|------------|------------|-------------|-----------|-----|
| `ERR_REQUEST_SCHEMA` | 400 | pydantic 검증 실패 | 요청 스키마가 올바르지 않습니다. | Request body failed schema validation. | `detail` 필드의 필드 경로 확인, OpenAPI `/docs` 참조. | — | .../ERR_REQUEST_SCHEMA (신규) |
| `ERR_FILTER_TOO_MANY` | 400 | IN 필터 > 10 원소 | 필터 값이 10개를 초과합니다. | An IN-filter has more than 10 values. | 필터 값을 분할하여 여러 번 요청, 결과 merge. | — | .../ERR_FILTER_TOO_MANY (신규) |
| `ERR_PAGE_LIMIT` | 400 | limit > tier max_limit_per_page | 페이지 크기가 티어 상한을 초과합니다. | `limit` exceeds your tier's max_limit_per_page. | preview=100, paid=200 이하 사용. | tier 상향은 계약 협의 후 `buyer update`. | .../ERR_PAGE_LIMIT |

### 5.3 Cursor 영역

| Code | HTTP | 발생 조건 | message_ko | message_en | Buyer 조치 | SRE 조치 | Doc |
|------|------|-----------|------------|------------|-------------|-----------|-----|
| `ERR_CURSOR_FILTER_CHANGED` | 400 | cursor 의 `s` hash 가 현재 filter sha 와 불일치 | 커서 이후 필터가 변경되었습니다. 1페이지부터 다시 시작하세요. | The cursor was issued for a different filter; restart from page 1. | `cursor` 필드 제거 + 현재 필터로 1페이지 요청. | — | .../ERR_CURSOR_FILTER_CHANGED (신규) |
| `ERR_CURSOR_VERSION` | 400 | cursor `v` != 1 | 지원하지 않는 커서 버전입니다. | Unsupported cursor version. | 처음부터 재시작 (이전 cursor 버림). | 서버 업그레이드 공지 여부 확인 — 구 cursor 는 지원 종료. | .../ERR_CURSOR_VERSION (신규) |

### 5.4 Cost & Perf 영역

| Code | HTTP | 발생 조건 | message_ko | message_en | Buyer 조치 | SRE 조치 | Doc |
|------|------|-----------|------------|------------|-------------|-----------|-----|
| `ERR_QUERY_TOO_BROAD` | 422 | planner estimate > 10M rows | 쿼리가 너무 광범위합니다. 필터를 좁혀주세요. | Query is too broad; narrow your filters. | `modality` · `study_date_shifted` 필터 추가. `extra.estimated_rows` 참조. | RB-3 — 반복 발생 시 estimator threshold 재조정 검토. | .../ERR_QUERY_TOO_BROAD (신규) |
| `ERR_QUERY_TIMEOUT` | 504 | PG statement_timeout=10s 초과 | 쿼리 시간이 초과되었습니다. | Query exceeded the 10s timeout. | 필터 축소 + `include_facets=false` 로 재시도. | RB-4 — 느린 쿼리 plan 조사. `search_audit` 에서 filter_sha256 로 재현. | .../ERR_QUERY_TIMEOUT (신규) |

### 5.5 Rate & Quota 영역

| Code | HTTP | 발생 조건 | message_ko | message_en | Buyer 조치 | SRE 조치 | Doc |
|------|------|-----------|------------|------------|-------------|-----------|-----|
| `ERR_RATE_LIMITED` | 429 | per-minute rate 초과 | 분당 요청 한도를 초과했습니다. | Per-minute rate limit exceeded. | `Retry-After` 준수 재시도. | 한도 튜닝 필요 여부 `search-admin stats buyer-usage` 로 판단. | .../ERR_RATE_LIMITED |
| `ERR_BUYER_QUOTA` | 429 | 일일 쿼터 초과 | 일일 쿼터를 모두 사용했습니다. | Daily quota exhausted. | 내일 재시도 or 유료 전환(sales@). | 영업 알림 — A-3 alert 연계. | .../ERR_BUYER_QUOTA (신규) |
| `ERR_BUYER_CONCURRENCY` | 429 | 동시 inflight > tier cap | 동시 요청 수 한도를 초과했습니다. | Concurrent request cap exceeded for your tier. | 클라이언트 concurrent pool 축소. | tier 상향 제안. | .../ERR_BUYER_CONCURRENCY (신규) |

### 5.6 Data & Infra 영역

| Code | HTTP | 발생 조건 | message_ko | message_en | Buyer 조치 | SRE 조치 | Doc |
|------|------|-----------|------------|------------|-------------|-----------|-----|
| `ERR_STUDY_NOT_FOUND` | 404 | pseudo_study_uid 존재하지 않음 | 스터디를 찾을 수 없습니다. | Study not found. | UID 오타 확인, 리스트 재검색. | — | .../ERR_STUDY_NOT_FOUND (신규) |
| `ERR_UNSUPPORTED_MEDIA` | 415 | Content-Type 위반 | 지원하지 않는 Content-Type 입니다. | Unsupported Content-Type. | `Content-Type: application/json` 사용. | — | .../ERR_UNSUPPORTED_MEDIA |
| `ERR_NOT_ACCEPTABLE` | 406 | Accept 헤더 JSON 외 요구 | 지원하지 않는 Accept 헤더입니다. | Only application/json is supported. | `Accept: application/json` 또는 생략. | — | .../ERR_NOT_ACCEPTABLE |
| `ERR_IDEMP_UNAVAILABLE` | 503 | Redis 불가 (rate-limit 경로) | 서버 상태 확인 중입니다. | Redis unavailable; service degraded. | `Retry-After` 대기. | central RB-6 실행. | .../ERR_IDEMP_UNAVAILABLE |
| `ERR_DB_UNAVAILABLE` | 503 | PG 불가 | DB 연결 불가. | Database unavailable. | 지수 백오프 재시도. | RB-4 실행. | .../ERR_DB_UNAVAILABLE |
| `ERR_INTERNAL` | 500 | 미분류 예외 | 내부 오류입니다. request_id 를 지원팀에 전달하세요. | Internal error. Share request_id with support@radivault.io. | 지원 티켓 (support@radivault.io, request_id 포함). | Sentry/로그에서 stack trace. | .../ERR_INTERNAL |

### 5.7 CLI 전용 에러 (API 에 노출되지 않음)

| Code | 발생 CLI | 상황 | 조치 |
|------|----------|------|------|
| `ERR_ADMIN_BUYER_NOT_FOUND` | `key issue`, `buyer show`, `buyer update` | `--buyer-id` 존재하지 않음 | `search-admin buyer list` 로 확인 |
| `ERR_ADMIN_BUYER_DUPLICATE` | `buyer create` | 동일 `contact_email` 기등록 | 기존 buyer 재활용 or 이메일 변경 |
| `ERR_ADMIN_BUYER_INACTIVE` | `key issue` | `buyer.active=false` | `buyer update --active true` 선행 |
| `ERR_ADMIN_KEY_NOT_FOUND` | `key revoke`, `key list --kid` | kid 존재하지 않음 | `key list` 로 확인 |
| `ERR_ADMIN_KEY_ALREADY_REVOKED` | `key revoke` | 이미 revoked | 정보성 (idempotent) |
| `ERR_ADMIN_HASH_FAIL` | `key issue` | argon2id 실패 | config.auth.argon2 튜닝 |
| `ERR_ADMIN_WRONG_ROLE` | `migrate up/down` | 일반 DSN 으로 DDL 시도 | `MIGRATION_DATABASE_URL` 사용 |
| `ERR_ADMIN_USAGE` | 모든 | `--help` 참조 | — |
| `ERR_ADMIN_DB_UNAVAILABLE` | 모든 | DB 접속 실패 | DATABASE_URL / 네트워크 확인 |

### 5.8 커버리지 확인

**dev-spec §7.6 의 18 codes** 중:

- **재사용(central-ingest 에서 상속)**: `ERR_AUTH_MISSING`, `ERR_AUTH_EXPIRED`, `ERR_PAGE_LIMIT`, `ERR_RATE_LIMITED`, `ERR_IDEMP_UNAVAILABLE`, `ERR_DB_UNAVAILABLE`, `ERR_INTERNAL`, `ERR_UNSUPPORTED_MEDIA`, `ERR_NOT_ACCEPTABLE` — 9종.
- **신규 (이 디자인이 확정)**: `ERR_AUTH_FORMAT`, `ERR_SCOPE_FORBIDDEN`, `ERR_REQUEST_SCHEMA`, `ERR_FILTER_TOO_MANY`, `ERR_CURSOR_FILTER_CHANGED`, `ERR_CURSOR_VERSION`, `ERR_QUERY_TOO_BROAD`, `ERR_QUERY_TIMEOUT`, `ERR_BUYER_QUOTA`, `ERR_BUYER_CONCURRENCY`, `ERR_STUDY_NOT_FOUND` — **11종 (dev-spec 선언과 일치)**.
- **CLI 전용 (design-surface 에서만 추가)**: 9종 (§5.7) — §12 Q-2 에 dev-spec 환류 필요 플래그.

HTTP status 매핑은 RFC 9110 준수 (pydantic 실패 = 400, cost rejection = 422, rate = 429, timeout = 504).

---

## 6. Runbook (Incident Response)

각 runbook 은 5-part 구조: **증상 / 최초 5분 / 격리 / 복구 / 사후**. 한국어. `docs/runbooks/search-RB-N.md` 경로로 별도 저장 권고(본 문서에는 요약).

### RB-1 — Empty-Result Rate Spike (`SearchEmptyResultRateHigh` / A-1)

```
증상:
  A-1 알람 — 15분 창에서 버이어 한 명 또는 전체의 empty-result rate > 40%.
  `radivault_index_empty_result_total` 가 `requests_total{status="200"}` 대비 급증.

최초 5분:
  1) `search-admin stats empty-rate --since 24h` — 어느 buyer 가 원인인지.
  2) buyer 가 특정되면 `search-admin stats buyer-usage --buyer-id <BID> --period day`
     로 당일 top filter_sha256 + 에러 분포 확인.
  3) 최근 48h 내 Central Ingest 쪽 schema 변경/enum 추가가 있었는지 확인.
     (예: modality 새 값 추가, age_bucket 이름 변경)

격리:
  4) Schema mismatch 의심이면 `/v1/search/facets` 응답을 수동 조회 — buyer 가 
     옛 enum 값을 필터로 보내고 있을 수 있음(예: "C_T" vs "CT").
  5) 악의적 탐색 의심이면 해당 kid 의 쿼터 낮추기 or revoke 검토.

복구:
  6) Schema mismatch → 버이어에게 contact-email 공지. enum 값 리스트를 
     `/v1/search/facets` 에서 얻도록 안내 (해당 API 의 존재를 다시 강조).
  7) Facet suppression 임계가 너무 낮아 잘 맞는 쿼리도 무응답처럼 보이는 
     경우(FR-22 의 2M 임계) — cost.facet_auto_suppress_rows 를 상향 검토.

사후:
  8) empty-result 메트릭에 buyer_id_hash 라벨이 너무 많으면 bucket 상위 N 만 
     노출하는 recording rule 추가.
  9) Buyer 와 정기 피드백 루프 구축 — 영업이 월 1회 "empty-rate 가 높은 buyer" 
     리스트 받아 케어.
```

### RB-2 — Buyer Abuse / Quota Burn (`SearchQuotaExhaustionSpike` / A-3)

```
증상:
  A-3 알람 — 1시간 창에서 `ERR_BUYER_QUOTA` 10건 초과, 특정 buyer_tier 에 집중.
  또는 영업 팀이 "buy_XXX 가 preview 인데 매일 100% 소진" 제보.

최초 5분:
  1) `search-admin stats buyer-usage --buyer-id <BID> --period week` 
     — 일별 쿼터 사용률 추이 + top 에러.
  2) `search-admin stats top-queries --since 24h --limit 20` — filter_sha256 
     빈도. 동일 sha 가 수천 회 반복이면 loop 버그 or 스크레이핑 의심.
  3) `search_audit` 에서 해당 buyer 의 시간대별 RPS 패턴 확인 
     (SELECT date_trunc('minute',created_at), count(*) ... WHERE buyer_pk=:X).

격리:
  4) 악의적 의심 시 `search-admin key revoke --kid <KID> --reason "abuse 
     investigation"` 으로 즉시 차단. buyer 에게 전화 공지 (이메일 전).
  5) 영업 수요 급증 의심 시(정당한 구매자) rate_limit_qps override 임시 
     상향 (`search-admin buyer update --scope-json ...`).

복구:
  6) buyer 와 대화 후 paid 전환 제안 (영업 리드).
  7) 악의적 확정 시 MSA/DPA 위반 조항 발동 — 법무 라인 통보.

사후:
  8) 패턴 recording rule 추가 — "동일 filter_sha256 이 1시간에 > 500회" 
     detector (P3 알람 후보).
  9) abuse 판정 기준 문서화 → 영업 플레이북에 반영.
```

### RB-3 — Cost Estimator Storm (`SearchCostEstimatorRejectionSpike` / A-4 · P95 Latency High / A-2)

```
증상:
  A-2 or A-4 알람 — p95 latency > 3s 또는 `ERR_QUERY_TOO_BROAD` 초당 0.5건.
  Buyer 가 "검색이 느려짐" 티켓을 제출.

최초 5분:
  1) Grafana 대시보드에서 `radivault_index_cost_estimate_rows` 분포 확인. 
     상위 10% 가 1M 이상이면 cost estimator 자체는 정상 동작 중.
  2) `search-admin stats top-queries --since 1h` 로 문제 filter_sha256 식별.
  3) PG 쪽: `SELECT query, state, now()-query_start FROM pg_stat_activity 
     WHERE usename='radivault_buyer_ro' ORDER BY now()-query_start DESC LIMIT 10`.

격리:
  4) DoS 의심 시 해당 buyer 의 kid revoke (RB-2 프로토콜).
  5) 정상 수요 급증 시 읽기 복제본 지연 확인 (v0.2 이후), pool size 상향 
     긴급 배포 검토.

복구:
  6) 반복적으로 큰 쿼리를 만드는 buyer 는 영업이 "Paid + 전용 index 옵션" 제안.
  7) Estimator 오차 의심 시 `EXPLAIN (FORMAT JSON)` 결과 vs 실제 COUNT(*) 샘플 
     비교 → `cost.max_estimated_rows` 튜닝.

사후:
  8) cost_estimate_rows 대비 실제 duration 상관관계 분석 (1주일 단위).
  9) 악용 패턴이면 IP allowlist 강화 검토.
```

### RB-4 — PG Read Pool Exhausted (`SearchDbPoolSaturation` / A-6, A-11)

```
증상:
  A-6 알람 — db_pool_in_use / pool_size > 0.8.
  동시에 `/readyz` 가 503 가능. 버이어 요청이 504/503 으로 전환.

최초 5분:
  1) `/readyz` 상태 확인. 503 이면 ALB drain 진행.
  2) `SELECT count(*) FROM pg_stat_activity WHERE state != 'idle' 
      AND usename='radivault_buyer_ro'` — 활성 쿼리 수.
  3) 장기 실행 쿼리(`now()-query_start > 5s`) pid 목록 추출.

격리:
  4) 의심 pid 를 `pg_cancel_backend(pid)` 또는 `pg_terminate_backend(pid)`.
  5) `config.db.pool_size` 임시 증설 (1.5x) 배포 — 워커 수 조정 유의.
  6) v0.2 이후: read replica 로 트래픽 redirect.

복구:
  7) 원인 엔드포인트(예: include_facets=true 대형 쿼리) 차단 feature flag.
  8) `/readyz` green 확인 후 ALB 트래픽 재개.

사후:
  9) PG slow query log 분석, `pg_stat_statements` top 쿼리 식별.
  10) `statement_timeout` 단위 튜닝 (10s → 8s 검토), pool 관리 SLO 추가.
```

### RB-5 — `search_audit` Queue Lag (`SearchAuditLagHigh` / A-5)

```
증상:
  A-5 알람 — search_audit 비동기 insert 큐 lag > 60s. 매출/funnel 분석 
  데이터가 실시간 들어오지 않음.

최초 5분:
  1) `search_audit` 테이블에 최근 5분 row 있는지 직접 조회 
     (`SELECT max(created_at) FROM search_audit`).
  2) `radivault_index_search_audit_lag_seconds` 추이 — 상승/유지/하강.
  3) PG `pg_stat_activity` 에서 insert 대기 커넥션 확인.

격리:
  4) 파티션 갱신 누락 여부 — 월 초 pg_partman 이 신규 파티션 생성 실패 시 insert 
     실패 가능. `search-admin migrate current` + `SELECT partman.run_maintenance()`.
  5) Insert worker 가 PG 연결 고갈로 실패 중이면 RB-4 와 중첩.

복구:
  6) 신규 파티션 수동 생성(`search_audit_2026_05` 등) → insert 재개.
  7) 백로그가 큰 경우 in-memory queue 를 disk 에 flush 하여 복구 후 bulk insert.

사후:
  8) pg_partman 월간 점검을 cron 으로 자동 재시도 2회.
  9) audit lag 가 특정 임계 초과 시 **search 전체를 차단** 옵션(dev-spec 
     ops flag 추가 검토) — Kyle 결정.
```

### RB-6 — Stale Cursor Flood (`SearchCursorChurnHigh` / A-8)

```
증상:
  A-8 알람 — buyer 한 명에 `radivault_index_cursor_invalidated_total` 
  분당 6회 초과. 보통 client-side 버그 (필터를 바꾸면서 cursor 유지).

최초 5분:
  1) `search-admin stats buyer-usage --buyer-id <BID>` — 에러 top 에 
     `ERR_CURSOR_FILTER_CHANGED` 가 과다한지.
  2) 로그에서 해당 buyer 의 filter_sha256 흐름 관찰 — sha 가 요청마다 바뀌는데 
     cursor 를 계속 사용한다면 client bug 확정.

격리:
  4) 필요 없음 — 이건 서비스 측 문제 아님. 버이어에게 연락.

복구:
  5) Buyer contact-email 로 "cursor must be dropped when filter changes" 
     안내 + 에러 메시지 `hint` 인용.
  6) 영업 엔지니어가 주기적으로 "버이어 통합 리뷰" 세션에서 가이드.

사후:
  7) SDK v0.2 에 `search().iter_items()` 헬퍼 포함 — cursor 관리 자동화.
  8) 공식 문서 §2.4 의 "Cursor invalidation" 예제 보강.
```

### RB-7 — API Key Compromise (rotate + notify)

```
증상:
  (a) Buyer 가 "키 유출" 이메일 제보, 또는
  (b) A-9 알람 — 동일 kid 에서 비정상 auth 실패 패턴, 또는
  (c) 영업이 악의적 트래픽 패턴 탐지.

최초 5분:
  1) `search-admin key revoke --kid <KID> --reason "compromise 2026-04-22"` 
     즉시 실행. revocation 은 Redis TTL 60초 내 전파 (auth cache 만료).
  2) `search-admin key list --buyer-id <BID> --include-revoked` 로 해당 
     buyer 의 다른 활성 키 상태 확인.

격리:
  3) Compromise 된 키의 최근 1시간 트래픽을 `search_audit` 에서 분석 — 
     어떤 filter_sha256 이 조회되었는가 (raw filter 는 없지만 sha 로 패턴 식별).
  4) 다른 활성 키가 없으면 buyer 는 현재 no-access. 영업에 즉시 공지.

복구:
  5) Buyer contact-email 로 전화 우선 연락 (이메일 전). 대체 키 발급 
     프로토콜 (암호화 채널 — 1Password share link 또는 age-encrypted file).
  6) `search-admin key issue --buyer-id <BID> --tier <TIER> --expires-days 
     180 --note "rotation after compromise YYYY-MM-DD"`.
  7) Buyer 가 새 키 적용 + 로그에서 첫 200 OK 관측 확인.

사후:
  8) compromise 경로 공동 포렌식 (buyer 측 유출 vs 우리 측). 재발 방지책.
  9) 해당 buyer 는 3개월 간 집중 모니터 — A-9 임계 낮춤.
  10) 필요시 `audit_search_event` 별도 이벤트 코드(`key.compromised_rotation`) 
      기록 — 법적 대응 기록.
```

---

## 7. Buyer Onboarding Walkthrough

대상: **RadiVault 영업·세일즈 엔지니어 ↔ 버이어 통합 엔지니어 공동 수행**. 소요 1–5 영업일 (법적 문서 제외하면 첫 curl 까지 30분). 언어: 영어 우선 (버이어 대상).

### 7.1 전체 플로우 ASCII

```
[Pre]    (1) 영업 최초 컨택 & 리드 자격 검증       ─ Sales
           │
           ▼
[Legal]  (2) NDA / MSA / DPA 체결                ─ RadiVault PM·법무 + Buyer 법무
           │
           ▼
[SRE]    (3) buyer 레코드 생성                   ─ search-admin buyer create
           │
           ▼
[SRE]    (4) Preview API key 발급 & 암호화 전달   ─ search-admin key issue → 1Password share
           │
           ▼
[Buyer]  (5) Onboarding doc · OpenAPI · Postman 수령
           │
           ▼
[Buyer]  (6) 첫 curl 호출 — /v1/version (auth 없이)
           │
           ▼
[Buyer]  (7) 첫 인증 호출 — /v1/search/facets
           │
           ▼
[Buyer]  (8) 첫 코호트 검색 — /v1/search/studies (단순 필터)
           │
           ▼
[Buyer]  (9) Facet 탐색 — 분포 그래프, 필터 반복
           │
           ▼
[Joint]  (10) 영업 팔로업 미팅 — 유스케이스 확정
           │
           ▼
[Buyer]  (11) Paid tier 계약 + scope 조정       ─ search-admin buyer update + key issue (paid)
           │
           ▼
[Buyer]  (12) 첫 구매 문의 (실 데이터 획득) — v0.2 Order Orchestrator 연동
```

### 7.2 단계별 상세 (각 단계 ≥1 curl 예시 포함)

**Step 1 — 영업 최초 컨택 (Sales)**

- 리드 자격: 의료영상 AI 기업, PoC 예산 확보, 기술 integration 역량 보유.
- 영업 → PM: "Prospect ACME AI, CT/chest 모델 학습 데이터 수요" 티켓.
- 산출물: Salesforce opportunity, 본 Onboarding doc 링크 (영어).

**Step 2 — 법적 문서 (Legal)**

- NDA (초기 탐색용) 서명 → MSA (파일럿 구매 전제) → DPA (익명 데이터 이전). 평균 3–10 영업일.
- RadiVault PM 이 sales-engineering Slack 채널에 "NDA 체결" 공지.

**Step 3 — Buyer row 생성 (SRE)**

```
$ search-admin buyer create \
    --company "ACME AI, Inc." \
    --contact-email integrations@acme-ai.com \
    --tier preview \
    --note "MSA signed 2026-04-22 / SF opp #OPP-8812"
[OK] buyer buy_acme_001 created
```

**Step 4 — Preview key 발급 & 전달 (SRE)**

```
$ search-admin key issue \
    --buyer-id buy_acme_001 \
    --tier preview \
    --expires-days 90 \
    --note "preview-initial"
# 평문 키가 stdout 에 한 번만 표시 → 즉시 1Password share link 발급
$ echo 'rv_live_abcd1234_Zj8...' | age -r age1acme_integrations... > preview-key.age
# 1Password → share vault → 24h 만료 링크 → 버이어 contact-email 에 발송
```

**Step 5 — Onboarding doc · OpenAPI · Postman 전달 (영업)**

- 이메일 템플릿(영어):
  ```
  Hi <name>,

  Welcome to RadiVault Search Preview.

  Please find attached:
    - Your Preview API key (1Password share link, expires in 24h)
    - OpenAPI 3.1 spec:   https://docs.radivault.io/search/openapi.json
    - Swagger UI:         https://docs.radivault.io/search/docs
    - Postman collection: https://docs.radivault.io/search/postman.json
    - Quickstart guide:   https://docs.radivault.io/search/quickstart

  Your preview tier grants 100 requests/day and up to 100 results per page.
  ...
  ```

**Step 6 — 첫 curl 호출, 인증 없이 `/v1/version`**

```
$ curl -s https://search.radivault.io/v1/version | jq .
{
  "service":              "radivault-search",
  "version":              "0.1.0",
  "api_contract_version": "1",
  "built_at":             "2026-04-22T09:00:00Z"
}
```

**기대**: 15 초 내 응답. 버이어가 네트워크·DNS·TLS 이상 없음을 확인.

**Step 7 — 첫 인증 호출, `/v1/search/facets`**

```
$ export RV_KEY="rv_live_abcd1234_Zj8..."   # 버이어가 setup
$ curl -s -H "Authorization: Bearer $RV_KEY" \
    https://search.radivault.io/v1/search/facets | jq '.modality'
[
  {"value":"CT","count":421338,"is_truncated":false},
  {"value":"MR","count":188445,"is_truncated":false},
  {"value":"CR","count":102881,"is_truncated":false},
  ...
]
```

**기대**: 200 OK, facet 값 목록 확인. 버이어가 "실데이터가 있다" 를 눈으로 본다.
실패 시 `401 ERR_AUTH_*` → Step 4 로 복귀.

**Step 8 — 첫 코호트 검색 `/v1/search/studies`**

```
$ curl -s -X POST https://search.radivault.io/v1/search/studies \
    -H "Authorization: Bearer $RV_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "modality": ["CT"],
      "body_part": ["CHEST"],
      "study_date_shifted": {"from":"2024-01-01","to":"2026-04-20"},
      "limit": 10,
      "include_facets": true
    }' | jq '{total_hint: .meta.total_hint, n: (.items|length), manufacturers: .facets.manufacturer}'
{
  "total_hint": 31055,
  "n": 10,
  "manufacturers": [
    {"value":"SIEMENS","count":14222,"is_truncated":false},
    {"value":"GE","count":11805,"is_truncated":false},
    {"value":"PHILIPS","count":7011,"is_truncated":false}
  ]
}
```

**기대**: 버이어가 "흉부 CT, 2024+, 3만건, 제조사별 분포" 를 10초 내에 얻는다.

**Step 9 — Facet 탐색 (반복, 버이어 자체 노트북)**

버이어가 자사 Jupyter notebook 에서 `requests` 로 여러 필터 조합 실험. facet 분포를 matplotlib 으로 그려 매니저에게 시연.
이 단계의 지원은 영업 엔지니어가 Slack shared channel 에서 담당.

**Step 10 — 영업 팔로업 미팅**

- 버이어 데이터 사이언티스트·통합 엔지니어·매니저 합동. 1시간.
- 내용: 코호트 규모·품질·제조사 분포 검토. 파일럿 구매 의사 확정.
- 산출물: 파일럿 구매 계약 초안 (Order Orchestrator v0.2 에 연결).

**Step 11 — Paid tier 전환**

```
$ search-admin buyer update \
    --buyer-id buy_acme_001 \
    --tier paid
$ search-admin key issue \
    --buyer-id buy_acme_001 \
    --tier paid \
    --expires-days 365 \
    --note "initial-production-key"
# 평문 키 1회 출력 → 암호화 전달 (preview 키는 별도 revoke — 또는 두 키 병존 허용)
$ search-admin key revoke --kid <PREVIEW_KID> --reason "migrated to paid"
```

**Step 12 — 첫 구매 문의**

- 버이어가 `pseudo_study_uid` 목록을 정하고 "구매 확정" 을 요청 → v0.2 Order Orchestrator 로 배팅.
- v0.1 범위 외. 영업이 `support@radivault.io` 로 수동 처리 (당분간).

### 7.3 롤백

```
1. search-admin key revoke --kid <KID> --reason "rollback-onboarding"
2. (optional) search-admin buyer update --buyer-id <BID> --active false
3. audit 로그 보존, 법무 협의 후 delete 여부 결정 (v0.1 은 기본 retain)
```

### 7.4 시간 예산 요약

| 단계 | 담당 | 예상 소요 |
|------|------|-----------|
| 1–2 법적 | 영업·법무 | 3–10 영업일 |
| 3–4 키 발급 | SRE | 10분 |
| 5 전달 | 영업 | 30분 |
| 6–9 첫 호출·탐색 | Buyer | 당일 1–2시간 |
| 10–11 계약 | 영업·버이어 | 1–2주 |
| 12 첫 구매 | v0.2 | v0.2 범위 |

**KPI — "time-to-first-hello"**: Step 4 (키 발급) 부터 Step 6 (첫 `/v1/version` 200) 까지 **15분 이내**가 목표. Step 8 (첫 코호트 성공) 까지 **60분 이내** 가 목표.

---

## 8. 국제화 (i18n)

| 표면 | 언어 | 근거 |
|------|------|------|
| HTTP API 에러 envelope | `message_ko` + `message_en` 동시 | central-ingest 와 일관. 버이어는 `message_en` 을 주로 읽으나 한국 본사가 있는 경우 `message_ko` 도 유용. |
| API 응답 바디 (success) | 영어 전용 (JSON 키·enum 값) | 버이어 영어 우선, 영어 스펙이 OpenAPI 표준. |
| CLI `--help` | **영어 우선** | 운영자·SRE 타깃. 버이어는 CLI 사용 안 함. |
| CLI 실행 출력 | 영어 기본, `--lang ko` 옵션(v0.1 optional) | central-ingest 와 동일 |
| Console JSON 로그 | 영어 전용 (+ 동반 `message_ko`·`message_en` 필드) | 중앙 집계·규제 보존 |
| Runbook 내부 문서 | **한국어** | 한국 SRE 팀 타깃 |
| Buyer onboarding doc (§7) | **영어 우선**, 한국어 번역 v0.2 | 버이어 글로벌 |
| Error doc (`docs.radivault.io/search/errors/...`) | v0.1 영어 우선, 한국어 병기 v0.2 | 장기적 공개 |
| OpenAPI spec / Swagger UI | 영어 전용 | 국제 표준 |
| Postman collection | 영어 전용 | 동일 |

**한국어 길이 규칙**: `message_ko` 는 120 bytes 이내 (central-ingest §8 상속).

**시간대 표기**: API 응답 JSON 은 UTC ISO8601. Runbook 본문·CLI 콘솔은 KST. CLI `--json` 모드는 UTC.

---

## 9. 접근성 (Accessibility)

| 항목 | 적용 |
|------|------|
| 색 의존 금지 | CLI 색은 보조만, `--no-color` / `NO_COLOR=1` 준수. JSON 로그·Prometheus·API 응답은 색 없음. |
| 고대비 | **N/A — HTTP API service** (시각 UI 없음) |
| 스크린리더 | CLI 출력은 라인 기반 — 리더 친화. `search-admin key issue` 박스 장식(`═`)은 `--plain` 으로 ASCII(`=`) 폴백. |
| 키보드 | CLI — 원천적으로 키보드 전용. |
| UTF-8 | 기본 UTF-8, `LANG=C` 환경에서 ASCII 폴백. |
| 머신 파싱 | 모든 read CLI 에 `--json`. API 는 원천 JSON — 자동화 친화. |
| WCAG 색 대비 4.5:1 | **N/A — HTTP API service**: 시각 UI 없음. 향후 Buyer Portal UI(v0.2+) 에서 재정의. |
| 반응형 | **N/A — HTTP API service**: 뷰포트 개념 없음. CLI 80열 터미널 가로 스크롤 금지 가이드만. |
| 디자인 토큰 (색·간격) | **N/A — HTTP API service**: 시각 토큰 없음. 대신 "에러 코드 네임스페이스"·"메트릭 네이밍 규약"·"JSON 응답 필드 순서" 가 equivalent 역할. |
| 포커스 관리 | **N/A — HTTP API service** |

---

## 10. API 문서 산출물 계획

### 10.1 OpenAPI 3.1 YAML

- **위치**: `docs/api/search-openapi.yaml` (소스), 빌드 시 `docs/api/search-openapi.json` 자동 생성 (CI).
- **공개 URL**: `https://docs.radivault.io/search/openapi.json` (CDN), 및 `https://search.radivault.io/openapi.json` (live from service).
- **권위 우선순위**: 소스(`docs/api/search-openapi.yaml`) → 서비스 `/openapi.json` → 공개 CDN. 세 개가 불일치하면 소스 우선.
- **유지 정책**: dev-spec §7 (엔드포인트 계약) 이 변경되면 OpenAPI PR 이 동일 커밋에 포함되어야 머지 가능 (CI rule).
- **검증**: `spectral lint docs/api/search-openapi.yaml` CI 필수. 룰셋은 OpenAPI 기본 + RadiVault 커스텀 (에러 응답 examples 필수 등).
- **examples**: 모든 에러 응답에 §5 의 실 메시지를 `examples:` 블록으로 등록. Swagger UI "Try it out" 에 그대로 나타남.

### 10.2 curl 예시 5종 (`docs/samples/search/`)

1. **`01-single-modality-date.sh`** — CT + 2024+ 단순 검색 (§7 Step 8 재사용).
2. **`02-multi-modality-facets.sh`** — CT+MR + facet 전체 탐색.
3. **`03-pagination.sh`** — page 1 → next_cursor → page 2 (cursor 반환 확인).
4. **`04-study-detail.sh`** — `/v1/search/studies/{uid}` 단일 상세.
5. **`05-hospitals.sh`** — `/v1/search/hospitals` 전체 병원 리스트.

각 스크립트는 `RV_KEY` 환경변수 의존, `jq` 로 예쁘게 파싱. 주석에 기대 응답 요약 포함. 영어.

### 10.3 Postman collection 구조

- **파일**: `docs/samples/search/postman-collection.json`.
- **폴더 구조**:
  ```
  RadiVault Search v0.1
  ├── 01 Health & Version
  │   ├── GET /healthz
  │   ├── GET /readyz
  │   └── GET /v1/version
  ├── 02 Search
  │   ├── POST /v1/search/studies — minimal
  │   ├── POST /v1/search/studies — all filters
  │   ├── POST /v1/search/studies — pagination (2-page)
  │   └── GET /v1/search/studies/{pseudo_study_uid}
  ├── 03 Facets
  │   └── GET /v1/search/facets
  ├── 04 Hospitals
  │   └── GET /v1/search/hospitals
  └── 05 Error Scenarios (examples)
      ├── 401 ERR_AUTH_MISSING
      ├── 400 ERR_FILTER_TOO_MANY
      ├── 400 ERR_CURSOR_FILTER_CHANGED
      ├── 422 ERR_QUERY_TOO_BROAD
      └── 429 ERR_BUYER_QUOTA
  ```
- **Environment**: `{baseUrl, apiKey}` 두 변수. baseUrl 기본 `https://search.radivault.io`, `apiKey` 는 버이어가 발급받은 값 삽입.
- **Tests**: 각 요청에 기본 assertion — 상태 코드 + `X-Request-Id` 존재.

### 10.4 Interactive docs 호스팅

- **v0.1**: Swagger UI 번들을 `/docs` 경로에 FastAPI 자동 제공. 인증 없이 접근 가능.
- **v0.2**: ReDoc 으로 교체 검토 — 더 깔끔한 레이아웃. Stoplight 는 비용 검토 후 결정.
- **커스텀**: `/docs` 상단에 RadiVault 로고 + 영업 연락처(`sales@radivault.io`) + 온보딩 링크 주입.

### 10.5 Authentication how-to

공식 문서 `docs.radivault.io/search/authentication`:

```md
## Authentication

RadiVault Search uses API key authentication via HTTP Bearer tokens.

### 1. Get your API key
Contact sales@radivault.io to enroll. You will receive:
  - Your preview API key (format: rv_live_<8-char-kid>_<32-char-secret>, total 48 chars).
  - A one-time-use encrypted share link (24h expiry).

### 2. Store it securely
Store in an environment variable or secrets manager. NEVER commit to git:

    export RADIVAULT_KEY="rv_live_abcd1234_..."

### 3. Send with every request
    curl -H "Authorization: Bearer $RADIVAULT_KEY" https://search.radivault.io/...

### 4. Key lifecycle
  - Preview keys expire after 90 days.
  - Paid keys expire after 180 days by default.
  - Contact support@radivault.io to rotate keys.
  - If you suspect compromise, email immediately — we'll revoke within minutes.
```

### 10.6 Sample dataset for tutorial

v0.1 은 별도 합성 데이터셋을 제공하지 않는다. 버이어는 **실제 production index** 에 preview key 로 접근 (cost estimator·quota 로 보호). v0.2 에서 `docs/samples/search/sandbox/` 형태로 1,000 건 합성 데이터 + docker-compose 로 로컬 실행 샘플 검토.

### 10.7 SDK 로드맵 선언

공식 문서 (영어):

```
SDK Roadmap
===========
v0.1 (now):     REST API + OpenAPI 3.1 + curl + Postman collection.
v0.2 (planned): Python SDK (pip install radivault-search) — typed client
                with automatic pagination (iter_items()), exception mapping
                (ERR_* → class), retry-with-jitter.
v0.3 (planned): JavaScript/TypeScript SDK (npm install @radivault/search).
v0.4+ (TBD):    Go, Java, Ruby — based on buyer demand.
```

---

## 11. 수용 기준 (Acceptance Criteria — 디자인 측)

총 18개. `@qa` 가 라인별 바이너리 검증.

- [ ] **AC-D-1** (Request 필드 코멘트) §2.2 의 `POST /v1/search/studies` 요청 예시에 모든 필터 필드(`modality`, `body_part`, `age_bucket`, `sex`, `study_date_shifted`, `manufacturer`, `min_hospitals`, `sort`, `limit`, `cursor`, `include_facets`)가 "why this field exists" 한 줄 코멘트를 가진다.
- [ ] **AC-D-2** (Cursor opaque) §2.4 공개 문서화 문구에 cursor 내부 필드(`v`·`d`·`p`·`s`·`k`) 가 **노출되지 않는다**. 내부 shape 은 본 문서 §2.4 "내부 cursor JSON" 블록에만 존재하며 공개 OpenAPI description 에는 포함되지 않음.
- [ ] **AC-D-3** (11개 신규 에러) dev-spec §7.6 에서 "신규" 로 선언된 **11개 에러 코드** (`ERR_AUTH_FORMAT`, `ERR_SCOPE_FORBIDDEN`, `ERR_REQUEST_SCHEMA`, `ERR_FILTER_TOO_MANY`, `ERR_CURSOR_FILTER_CHANGED`, `ERR_CURSOR_VERSION`, `ERR_QUERY_TOO_BROAD`, `ERR_QUERY_TIMEOUT`, `ERR_BUYER_QUOTA`, `ERR_BUYER_CONCURRENCY`, `ERR_STUDY_NOT_FOUND`) 가 §5 테이블에 **각각 message_ko + message_en + Buyer action + SRE action** 4필드를 모두 가진다.
- [ ] **AC-D-4** (에러 코드 총 커버리지) dev-spec §7.6 의 모든 18개 코드가 §5 에 등장한다. 누락 0건.
- [ ] **AC-D-5** (Runbook 5-part) RB-1..RB-7 가 각각 증상·최초 5분·격리·복구·사후 5섹션을 포함한다.
- [ ] **AC-D-6** (Onboarding curl per step) §7 의 Step 6/7/8/11 에 **각각 최소 1개 curl 예시** 가 존재한다. 영어.
- [ ] **AC-D-7** (CLI JSON) 모든 read CLI (`buyer list`, `buyer show`, `key list`, `stats *`, `version`, `migrate current`) 가 `--json` 플래그에서 top-level `{filter, items|buyers|keys, summary}` 일관 구조를 출력한다.
- [ ] **AC-D-8** (이중 언어 API 에러) 모든 4xx/5xx API 응답이 `message_ko` 와 `message_en` 을 동시에 포함. 누락 시 lint 실패.
- [ ] **AC-D-9** (Prometheus 네이밍) `/metrics` 에 노출되는 RadiVault 고유 메트릭이 모두 `radivault_index_*` 접두사. `grep -E '^[a-z_]+' metrics_dump | grep -v '^(python_|process_|go_|radivault_index_)'` 결과 empty.
- [ ] **AC-D-10** (Alert 구체성) §4.4 11건의 알람이 모두 **구체 숫자** 임계로 Alertmanager rule 정의 가능 (추상 "high" 금지).
- [ ] **AC-D-11** (PHI·raw filter 차단) 로그 sanitiser 가 §4.1 금지 필드(원본 UID·환자명·raw filter body·API key 평문·raw cursor) 감지 시 레코드 drop + `ERR_LOG_PHI_DETECTED` 카운터 증가. 감지 테스트 CI green.
- [ ] **AC-D-12** (CLI 색 독립) `search-admin --no-color` 또는 `NO_COLOR=1` 에서 모든 출력이 ANSI 이스케이프 없음. `grep -P '\x1b\[' output` 결과 empty.
- [ ] **AC-D-13** (에러 doc 링크) 모든 에러 응답이 `doc_url` 필드를 포함. v0.1 에서 해당 URL 이 404 여도 AC 통과 (§12 Q-1 예외 허용).
- [ ] **AC-D-14** (Content-Type·CORS) `POST /v1/search/studies` 에 `text/xml` Content-Type → `415 ERR_UNSUPPORTED_MEDIA`. `Accept: text/html` → `406 ERR_NOT_ACCEPTABLE`. 허용되지 않은 Origin 의 browser preflight → CORS 거부 (응답 헤더에 `Access-Control-Allow-Origin` 부재).
- [ ] **AC-D-15** (Onboarding 12 단계) §7 의 12 단계를 따라가면 버이어가 외부 문서 참조 없이 첫 `/v1/search/studies` 200 에 도달한다. Time-to-first-200 < 60분.
- [ ] **AC-D-16** (Rate-limit 헤더) 모든 200 응답 + 429 응답에 `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `X-Quota-Limit-Daily`, `X-Quota-Remaining-Daily`, `X-Quota-Reset-Daily` 6개 헤더 존재.
- [ ] **AC-D-17** (OpenAPI 완전성) `/openapi.json` 이 dev-spec §7 의 7개 엔드포인트 전부 포함. 각 에러 응답에 §5 실 메시지의 `examples:` 블록 포함. `spectral lint` 통과.
- [ ] **AC-D-18** (Postman 5 error) Postman collection 의 "05 Error Scenarios" 폴더에 5가지 에러 예시(`ERR_AUTH_MISSING`, `ERR_FILTER_TOO_MANY`, `ERR_CURSOR_FILTER_CHANGED`, `ERR_QUERY_TOO_BROAD`, `ERR_BUYER_QUOTA`) 요청이 모두 포함 및 정상 실행 가능.

---

## 12. 오픈 질문

Kyle 결정 또는 외부 확인 필요.

1. **Error doc 호스팅 시점** — `docs.radivault.io/search/errors/<CODE>` 라우트 생성 책임. central-ingest design-spec §11-1 과 동일 이슈 통합. v0.1 에 404 허용 여부.
2. **신규 design-surface 에러 9종 dev-spec 환류** — §5.7 의 CLI 전용 코드(`ERR_ADMIN_*` 9종)를 dev-spec §13.1 enum 에 포함시킬 것인가? 권장: 포함 + `ERR_ADMIN_*` sub-namespace 명시.
3. **응답 envelope 그룹화** — dev-spec §7.1 은 플랫 구조(`next_cursor`·`has_next`·`page_size` 루트 위치), 본 디자인은 `pagination{...}` + `meta{...}` 그룹핑 권고. Breaking change 아님 (필드 이름 보존 불가 이슈) 이므로 **둘 중 하나 선택 필요**. 권고: 그룹화 (가독성·SDK 설계 용이성).
4. **`X-Request-Id` 케이스 정규화** — HTTP 헤더는 대소무관이나 테스트·문서는 `X-Request-Id` 고정 권고. central-ingest 와 동일.
5. **Facet `__other__` 대안** — v0.1 은 상위 50 + `__other__` 요약. 버이어 요청으로 `not_in` 필터를 v0.1.1 에 조기 추가할 가치가 있는가?
6. **`search-admin` vs `ingest-admin` 통합** — dev-spec FR-56 은 분리. 운영자 1명 관점에서 서브커맨드 통합이 더 실용적일 수 있음. `radivault-admin {search|ingest} ...` 단일 바이너리 옵션.
7. **Preview key expiry 기본값** — §3.5 는 180일. Preview 는 90일로 짧게 (실사용 약속 전 회전 강제) 권고 — §7.4 에 90일 명시. 확정 필요.
8. **CORS allowlist 의 운영 UX** — `search.yml` 편집 → 재배포 파이프라인. 버이어가 자주 Origin 추가 요청할 경우 `search-admin cors add-origin <url>` 서브커맨드 검토 (v0.2 백로그).
9. **`meta.buyer_tier` 응답 바디 노출 여부** — 버이어가 자신의 tier 를 응답에서 보면 좋지만 "하드코딩 유혹" 가능. 헤더로만 노출(`X-Buyer-Tier`) 하고 바디에서 제거할지 결정.
10. **Onboarding 이메일 자동화** — Step 5 의 이메일은 v0.1 수동. 영업 운영 부담. v0.1.1 `search-admin buyer notify-welcome` 자동화 제안.
11. **Swagger UI 공개 접근** — `/docs` 는 인증 불필요. 버이어 enum·필드 shape 이 노출되지만 의도된 개방. 경쟁사 리버스엔지니어링 방어책 필요한가? 권고: v0.1 공개 유지.
12. **Empty-result alert buyer 통보 정책** — A-1 알람 시 SRE 가 내부 대응(RB-1). 버이어 자체에게도 "empty-rate 가 높다" 를 이메일로 자동 공지할 것인가? 사생활·영업 관점 결정 필요.
13. **Cursor debug CLI** — §2.4 에 언급한 `search-admin debug cursor <TOKEN>` v0.2 백로그. v0.1 에 추가할 가치?
14. **`ERR_QUERY_TOO_BROAD` 의 `extra` 필드** — `estimated_rows`, `suggested_filters` 를 envelope standard 에 승격할지 아니면 엔드포인트 고유 `extra` 오브젝트로 유지할지. 권고: `extra` 유지 (envelope 범용성 보호).
15. **Hospital opaque ID per-buyer salt 관리 UX** — salt rotation 시 `search-admin hospital rotate-salt` 신설. 버이어에게 "귀사의 hospital_opaque_id 가 일제히 바뀐다" 선행 공지 필요. v0.1.1 검토.

---

## 13. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-22 | @designer (Claude Opus 4.7) | 최초 작성. Buyer-facing HTTP API DX (응답 envelope 그룹화·opaque cursor 계약·facet shape·`total_hint` 시맨틱·CORS/Content-Type/버전 정책) + Operator CLI `search-admin` 9 서브커맨드(buyer/key/stats/facet/migrate/version) + JSON 로그 schema(8 신규 필드) + Prometheus 메트릭 17종(`radivault_index_*`) + 알람 11건 + Error taxonomy UX (dev-spec §7.6 전수 18종 + CLI 전용 9종) + Runbook 7편 (empty-rate / abuse / cost storm / pool exhausted / audit lag / cursor churn / key compromise) + Buyer Onboarding 12 단계 + API 문서 산출물 계획 (OpenAPI 3.1 · curl 5종 · Postman · Swagger UI · SDK 로드맵). central-ingest design-spec §2 envelope / §5 error format / §3 CLI style 완전 상속. 시각 디자인 항목(반응형·색 대비·디자인 토큰)은 "N/A — HTTP API service" 로 명시. |

---

### NEXT_STEP

- 완료 산출물: `docs/specs/design-spec-metadata-index.md` (v0.1 Draft, 본 문서)
- 제안 다음 단계: **@developer** — `claude` 브랜치에서 `metadata-index` 구현 착수.
  - 구현 기준:
    - §2 Buyer API UX (envelope · cursor · facet · rate-limit 헤더 · CORS) 그대로.
    - §3 `search-admin` CLI 구조 (명령 트리 · `--json` · `--dry-run` · 종료 코드).
    - §4 `radivault_index_*` Prometheus 메트릭 17종 + JSON 로그 8 신규 필드.
    - §5 에러 taxonomy (dev-spec 신규 11종 + central 재사용 9종 + CLI 전용 9종).
    - §6 Runbook 7편을 `docs/runbooks/search-RB-1..7.md` 분리 파일로 생성.
    - §7 Onboarding 12 단계를 `docs/onboarding/search-buyer-walkthrough.md` 분리 파일로.
    - §10 산출물: `docs/api/search-openapi.yaml` + `docs/samples/search/{01..05}.sh` + `postman-collection.json`.
  - dev-spec §13 Annex 의 SDK 로드맵은 본 디자인 §10.7 으로 승격 — 공식 문서 1급 섹션으로.
- UI_GUIDE.md 갱신 제안: "부록: Public HTTP API 공통 가이드" 에 **4개 규약** 추가 — (1) envelope 5필수 필드 (2) `Retry-After` + `X-RateLimit-*` + `X-Quota-*` 헤더 (3) cursor opaque 계약 (4) `radivault_index_*` Prometheus prefix. central-ingest design-spec §NEXT_STEP 제안과 병합 권고. 정식 편입은 Kyle 승인 후.
- 추가 디자인 필요:
  - (a) **Buyer Portal v0.2 UI** — 웹 대시보드 (코호트 시각화, facet 차트, usage chart). 별도 slug `buyer-portal`.
  - (b) **Python SDK v0.2** — `pip install radivault-search`. 별도 slug `search-python-sdk`.
  - (c) **Order Orchestrator v0.2** — `pseudo_study_uid` → 구매 확정 → presigned URL. 별도 dev-spec.
  - (d) **Grafana 대시보드 spec** — Prometheus `radivault_index_*` 기반 운영자 보드.
- ARCHITECTURE.md 영향: §5.2 "v0.1 REST-only, SDK v0.2+" 명시 권고. §9 Zone 3 라인에 search 서비스 스택 (FastAPI + PG buyer_ro + Redis) 추가. Kyle 승인 후 별도 PR.
- PRD.md 영향: §4.2 "코호트 검색 API" 의 HTTP DX·인증·쿼터가 본 디자인으로 구체화.
- Kyle 결정 필요 사항 (§12 요약):
  1. §12-1 `docs.radivault.io/search/errors/*` 호스팅 일정.
  2. §12-2 CLI 전용 에러 9종 dev-spec §13.1 환류 승인.
  3. §12-3 응답 envelope 그룹화 (pagination/meta 네임스페이스) 채택 여부.
  4. §12-6 `search-admin` 분리 바이너리 vs `radivault-admin` 통합.
  5. §12-7 Preview key expiry 기본값 90일 확정.
  6. §12-9 `meta.buyer_tier` 바디 노출 여부.
  7. §12-10 Onboarding 이메일 자동화 `search-admin buyer notify-welcome`.
  8. §12-11 Swagger UI 공개 유지 여부.
  9. §12-12 Empty-result alert 의 버이어 자동 공지 정책.
