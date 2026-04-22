# 디자인 명세 — Central Ingest v0.1 MVP (HTTP API · Admin CLI · Observability · Runbook UX)

> **Status**: Draft v0.1 · **Feature slug**: `central-ingest` · **Last updated**: 2026-04-22
> **작성자**: @designer (Claude Opus 4.7) · **근거**:
> - [dev-spec](./dev-spec-central-ingest.md) — 본 디자인의 유일한 source of truth
> - [design-spec-gateway-agent](./design-spec-gateway-agent.md) — 에러 메시지 템플릿·에러 코드 네임스페이스·runbook 패턴 상속
> - [UI Guide](../UI_GUIDE.md) — 원칙(톤)만 참고
> - [리서치 — Central Ingest 기술 기반](../research/central-ingest-technical-foundations.md)

---

## 0. 범위 선언 (Scope Statement)

본 문서는 통상의 GUI 디자인 명세가 **아니다**. Central Ingest는 RadiVault Zone 2의 **백엔드 HTTP 서비스**로 웹/데스크톱 UI가 존재하지 않는다 (Gateway Agent와 동일한 구조). 대신 "개발자·운영자가 실제로 마주하는 표면"이 존재하며, 본 문서는 그 UX를 정의한다.

**디자인 대상 표면 6종**

1. **HTTP API UX** — 응답 바디 envelope, 에러 페이로드 스키마, `Idempotency-Key`·`Idempotency-Replayed` 헤더 계약, `Retry-After` 의미, multipart 규칙, 페이지네이션 플레이스홀더
2. **Operator CLI (`ingest-admin`)** — 토큰 발급·회수, 앵커 체인 검증, 스터디 조회, 마이그레이션, 버전 확인 — RadiVault SRE 전용
3. **Log & Observability 출력** — JSON 로그 스키마, Prometheus 메트릭 네이밍 규약(`radivault_central_*`), 알람 정의
4. **Error Taxonomy UX** — dev-spec §13에 나열된 에러 코드를 이중 언어 운영자 메시지로 매핑
5. **Runbook 산출물** — 장애별 5–12줄 액션 기반 플레이북 8편
6. **Hospital Onboarding Walkthrough** — RadiVault SRE ↔ 병원 IT가 공동으로 수행하는 프로비저닝 단계

**디자인 대상 아닌 것**: 구매자 포털, 병원 관리 콘솔 웹, 운영자 대시보드, DICOM 뷰어, 모바일 앱.

표준 design-spec 템플릿의 일부 항목(반응형·색 대비·디자인 토큰·스크린리더)은 백엔드 서비스 성격상 적용되지 않아 "N/A — backend service" 로 표기한다.

---

## 1. 사용자 (Users)

### 1.1 Primary A — Gateway Agent (machine user)

- **유형**: 무인 클라이언트. 병원 on-premise에서 Docker Compose로 기동되어 HTTPS로만 통신.
- **언어**: N/A (기계). 다만 에러 페이로드의 `message_en`만 로그로 노출되고, `message_ko`는 Gateway `audit.log` 보조 힌트로 기록될 수 있음.
- **기대 계약**: `POST /v1/ingest/studies`, `POST /v1/audit/anchor`, `GET /healthz`, `GET /v1/version` 4개 엔드포인트만 사용.
- **실패 시 행동**: 4xx → Gateway FR-20 로직에 따라 재시도 금지/영구 격리. 5xx → 지수 백오프 재시도. 429 → `Retry-After` 준수.
- **제약**: Gateway v0.1은 `job_id` 필드만 읽음 → 응답 JSON은 **superset 확장만 허용, 기존 필드 삭제 금지**.

### 1.2 Primary B — RadiVault SRE (human operator)

- **언어**: 한국어/영어 혼용. 영어 기술 문서·콘솔에는 영어, 내부 runbook·에스컬레이션에는 한국어.
- **기술 수준**: Linux/Docker/PostgreSQL 숙련. SQL로 데이터 조회·운영 가능. K8s는 v0.2 범위(본 문서는 Docker Compose 기준).
- **목표**: (a) `/readyz`·`/metrics`·Prometheus 알람이 정상 상태임을 자동화 대시보드에서 확인, (b) 장애 발생 시 runbook 1건을 5분 안에 찾아 1st response, (c) 신규 병원 온보딩을 30분 이내 완료.
- **안 해도 되는 일**: Python 코드 읽기, FastAPI 내부 구조 이해, manifest 바이너리 파싱.
- **반드시 해야 하는 일**: `ingest-admin` CLI 사용, Alembic 마이그레이션 실행, 장애 대응 runbook 실행, Prometheus 알람 응답, 병원 토큰 발급·회수.

### 1.3 Primary C — 병원 IT 관리자 (human, Korean)

- **언어**: 한국어 모국어. Gateway design-spec §2.1의 "병원 IT 운영자"와 동일 인물.
- **접촉 표면**: (a) Gateway Agent의 로그·상태에 Central 응답의 `error.code` 또는 `error.message_ko` 가 전파됨, (b) 온보딩 시 RadiVault SRE와 화상·전화로 공동 작업, (c) 문제 발생 시 에러 코드를 RadiVault 지원에 전달.
- **목표**: Central이 만든 에러 메시지를 **그대로 복사해 지원 티켓에 첨부**할 수 있도록 `message_ko + code` 1줄이 Gateway 콘솔에 명시적으로 나와야 한다.

### 1.4 Secondary — 구매자 측 통합 개발자 (future, v0.2+)

- **언어**: 영어 우선.
- **접촉 표면**: v0.1에서는 `/v1/version` 외 접근 불가. v0.2에서 `/v1/search`·`/v1/download`가 열리면 본 문서의 envelope·에러 포맷이 그대로 적용되도록 **설계 시부터 공개 API 관점으로 엄격한 계약**을 요구.

### 1.5 Non-user

- 환자·의료진·연구자·구매자(엔드 유저)는 Central Ingest에 직접 접근하지 않는다. 모든 접근은 Gateway 또는 추후 Order Orchestrator를 경유.

---

## 2. HTTP API UX

### 2.1 응답 Envelope 원칙

두 가지 envelope 스타일 중 **하나**를 선택해야 한다. 본 디자인은 **옵션 B**(OpenAPI 스타일: 상태 코드 + 최소 래핑 바디)를 채택한다.

| 옵션 | 성공 바디 | 실패 바디 | 장점 | 단점 |
|------|-----------|-----------|------|------|
| A. `{ok, data?, error?}` | `{"ok":true,"data":{...}}` | `{"ok":false,"error":{...}}` | SDK 측 분기 단순 | HTTP 상태와 `ok` 중복, 스트리밍 힘듦 |
| **B. OpenAPI 스타일 (채택)** | `{...}` 직접 | `{"error":"<code>","detail":"<en>","message_ko":"<ko>","request_id":"..."}` | dev-spec §7의 기존 예시와 정확히 일치, HTTP 상태가 곧 의미 | SDK가 상태 코드 분기 필요 |

**채택 근거**: dev-spec §7.1–§7.6 본문이 이미 옵션 B 스타일 예시를 사용 중이며, Gateway mock과 100% 호환. 옵션 A로 전환 시 Gateway FR-20 재시도 로직까지 영향.

### 2.2 에러 페이로드 스키마 (표준)

모든 4xx/5xx 응답은 아래 바디 구조를 **반드시** 따른다. 성공 바디(2xx)는 엔드포인트별 정의.

```jsonc
{
  "error":       "ERR_MANIFEST_ANON",                   // 코드 (dev-spec §7.7 enum)
  "detail":      "anonymization_flag must be fully_anonymized",  // en, 기계 가독
  "message_ko":  "manifest의 anonymization_flag가 fully_anonymized 여야 합니다.",
  "message_en":  "Manifest anonymization_flag must be 'fully_anonymized'.",
  "request_id":  "01HXX8WQ9Z3K7V5B2A1N6P4R9T",          // ULID
  "doc_url":     "https://docs.radivault.io/central-ingest/errors/ERR_MANIFEST_ANON",
  "hint":        "Gateway 측에서 manifest.anonymization_flag 필드를 추가해 재업로드하세요.",  // optional
  "retry_after": null                                    // 429/503만 정수 초, 그 외 null
}
```

**필드 5 (+ 2 optional) 고정**:

| 필드 | 필수 | 타입 | 설명 |
|------|------|------|------|
| `error` | 필수 | string | dev-spec §7.7 enum. `ERR_*` prefix. 유일 식별자. |
| `detail` | 필수 | string (en) | 한 줄 기계 가독 영문. `message_en`의 축약 버전 허용. |
| `message_ko` | 필수 | string (ko) | 병원 IT 담당자가 Gateway 로그에서 보고 이해할 한국어. |
| `message_en` | 필수 | string (en) | `detail`과 동일하거나 풀 문장. 장기적으로 공개 문서화. |
| `request_id` | 필수 | string (ULID) | 서버가 생성한 요청 식별자. `X-Request-Id` 응답 헤더와 동일 값. |
| `doc_url` | 권장 | URL | `docs.radivault.io/central-ingest/errors/<CODE>` — v0.1은 404 허용(§11 Open Q-1). |
| `hint` | optional | string | 운영자·Gateway 개발자 구체 조치. 한국어 또는 영어. |
| `retry_after` | optional | integer\|null | 429/503에만 값. 응답 헤더 `Retry-After`와 **반드시 일치**. |

**dev-spec §7 원본 envelope**(`{error, detail, request_id}`)와의 호환성: 위 스키마는 dev-spec envelope을 **superset 확장**한다 (3개 필수 → 5개 필수). 발행될 응답에서 원본 필드 3개는 그대로 유지되므로 Gateway 계약 breaking 없음. 추가된 `message_ko`·`message_en`·`doc_url`은 Gateway가 무시 가능.

### 2.3 대표 에러 응답 예시 3종

**(a) 401 — 잘못된 Bearer 토큰 (`ERR_AUTH_EXPIRED`)**

```
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer realm="central-ingest", error="invalid_token"
Content-Type: application/json
X-Request-Id: 01HXX8WQ9Z3K7V5B2A1N6P4R9T

{
  "error":      "ERR_AUTH_EXPIRED",
  "detail":     "token revoked or expired",
  "message_ko": "인증 토큰이 만료되었거나 철회되었습니다. RadiVault 지원에 재발급을 요청하세요.",
  "message_en": "Authentication token has expired or been revoked. Please request re-issuance from RadiVault support.",
  "request_id": "01HXX8WQ9Z3K7V5B2A1N6P4R9T",
  "doc_url":    "https://docs.radivault.io/central-ingest/errors/ERR_AUTH_EXPIRED",
  "retry_after": null
}
```

**(b) 409 — Idempotency replay 성공 경로 (상태는 원 응답 그대로, 추가 헤더)**

```
HTTP/1.1 201 Created
Content-Type: application/json
Idempotency-Replayed: true
X-Request-Id: 01HXX9AB2C4D6E8F0G1H3J5K7L
X-Original-Request-Id: 01HXX8WQ9Z3K7V5B2A1N6P4R9T

{
  "central_job_id": "ingest_01HXX8WQ9Z3K7V5B2A1N6P4R9T",
  "job_id":         "ingest_01HXX8WQ9Z3K7V5B2A1N6P4R9T",
  "received_at":    "2026-04-22T10:20:01Z",
  "object_keys":    ["prod/a1/hosp_abc/2.25.xxxx/2.25.yyyy/2.25.zzzz.dcm"]
}
```

> 리플레이는 **원 응답을 바이트 단위 복제**하며, 새 `X-Request-Id`와 원본을 가리키는 `X-Original-Request-Id` 두 헤더를 추가한다. `Idempotency-Replayed: true`는 Gateway가 audit log에 "replay hit" 이벤트를 기록할 수 있도록 해 준다.

**(c) 422 대신 400 — manifest 검증 실패 (`ERR_MANIFEST_SCHEMA`)**

> dev-spec은 pydantic 검증 실패를 `400`으로 통일한다(OpenAPI 기본 `422`가 아님). 이는 Gateway FR-20 재시도 로직의 "4xx=재시도 금지" 단순 분류와 일치시키기 위함.

```
HTTP/1.1 400 Bad Request
Content-Type: application/json
X-Request-Id: 01HXXABCDE12345678901234567

{
  "error":      "ERR_MANIFEST_SCHEMA",
  "detail":     "manifest JSON failed pydantic validation: files[3].sha256: field required",
  "message_ko": "manifest의 files[3].sha256 필드가 누락되었습니다. Gateway 로그의 해당 스터디를 확인하세요.",
  "message_en": "Manifest field 'files[3].sha256' is missing. Check gateway logs for this study.",
  "request_id": "01HXXABCDE12345678901234567",
  "doc_url":    "https://docs.radivault.io/central-ingest/errors/ERR_MANIFEST_SCHEMA",
  "hint":       "Gateway ruleset_version v0.1.0 이상에서 해결됨. 업그레이드 권고.",
  "retry_after": null
}
```

### 2.4 Idempotency-Key 사용자 계약

| 규칙 | 값 | 근거 |
|------|-----|------|
| 필수 여부 | **필수** — 미제공 시 `400 ERR_IDEMP_MISSING` | dev-spec FR-28 |
| 형식 | 16–128자, `[A-Za-z0-9_.-]`만 허용. 위반 시 `400 ERR_IDEMP_FORMAT` | dev-spec FR-28 |
| 권장 생성 | Gateway가 ULID 문자열(26자) 사용 | Gateway dev-spec §7.3.1 |
| 네임스페이스 | `(key, hospital_id)` 복합. 다른 병원 간 충돌 불가 | dev-spec FR-31 |
| TTL | Redis 24시간 (환경변수 `IDEMPOTENCY_TTL_SECONDS` override) | dev-spec FR-29 |
| Mirror | DB `ingest_idempotency_mirror` 에 7일 더 유지 | dev-spec FR-33 |
| 리플레이 | 동일 key 재수신 시 저장된 원 응답 + 헤더 `Idempotency-Replayed: true` | dev-spec FR-30 |
| mismatch | 동일 key + 다른 payload sha256 → **409 `ERR_IDEMP_MISMATCH`** (신규 코드, §5 테이블에 추가) | 설계 결정 |
| Redis 장애 | `503 ERR_IDEMP_UNAVAILABLE` — 무결성 우선, 수락 금지 | dev-spec FR-32 |

**Gateway 운영자 관점 mental model (문서화 문구)**:

> "Idempotency-Key 는 **스터디 1건에 한 평생 1번 쓰는 영수증 번호**다. 같은 key를 다시 보내면 서버는 처음 받은 결과를 그대로 돌려준다. 다른 payload에 같은 key를 재활용하면 409가 떨어진다. 네트워크 중단으로 응답을 못 받았을 때 안전하게 재시도하려고 존재한다."

### 2.5 Rate-limit 응답

```
HTTP/1.1 429 Too Many Requests
Retry-After: 27
Content-Type: application/json
X-Request-Id: 01HXXRATE...

{
  "error":       "ERR_RATE_LIMITED",
  "detail":      "hospital per-minute ingest limit exceeded (60/min)",
  "message_ko":  "병원별 분당 요청 한도(60회)를 초과했습니다. 27초 후 다시 시도하세요.",
  "message_en":  "Hospital per-minute ingest limit (60/min) exceeded. Retry after 27 seconds.",
  "request_id":  "01HXXRATE...",
  "doc_url":     "https://docs.radivault.io/central-ingest/errors/ERR_RATE_LIMITED",
  "retry_after": 27
}
```

**원칙**:

- `Retry-After` 응답 헤더와 바디 `retry_after` 값이 **반드시 일치**.
- 값은 **정수 초**, RFC 7231 유효 포맷 중 delta-seconds 사용(HTTP-date 금지 — 파서 모호성 제거).
- 분당/시간당/일일/월간 한도 4종 모두 `429` 상태로 통일하되 `error.code` 로 구분: `ERR_RATE_LIMITED`, `ERR_RATE_QUOTA_DAILY`, `ERR_RATE_QUOTA_MONTHLY`.

### 2.6 Anonymization Gate 응답

manifest에 `anonymization_flag` 필드가 없거나 `"fully_anonymized"` 외의 값일 때:

```
HTTP/1.1 403 Forbidden
Content-Type: application/json
X-Request-Id: 01HXXANON...

{
  "error":       "ERR_MANIFEST_ANON",
  "detail":      "manifest.anonymization_flag must be 'fully_anonymized'",
  "message_ko":  "manifest의 anonymization_flag가 fully_anonymized 가 아니면 업로드가 차단됩니다. 국외이전 방지 게이트입니다.",
  "message_en":  "Uploads are blocked unless manifest.anonymization_flag == 'fully_anonymized'. This is the cross-border transfer gate.",
  "request_id":  "01HXXANON...",
  "doc_url":     "https://docs.radivault.io/central-ingest/errors/ERR_MANIFEST_ANON",
  "hint":        "Gateway v0.1 사용 시 manifest 필드가 아직 없을 수 있습니다. Gateway v0.1.1 업그레이드가 필요합니다 (dev-spec §13 D-3).",
  "retry_after": null
}
```

이 에러는 **법적 게이트**(개보법 제28조의8)이므로 `hint` 필드에 Gateway 업그레이드 안내를 포함해 병원 IT 담당자가 지원 티켓에 바로 쓸 수 있게 한다.

### 2.7 Content-Type 규칙

| 엔드포인트 | Request | Response | 비고 |
|-----------|---------|----------|------|
| `POST /v1/ingest/studies` | `multipart/form-data; boundary=...` 필수 | `application/json` | manifest part는 반드시 `application/json`, 파일 파트는 `application/dicom` — 미지정 시 `400 ERR_INGEST_CTYPE` (신규 코드) |
| `POST /v1/audit/anchor` | `application/json` 필수 | `application/json` | 그 외는 `415 Unsupported Media Type` + `ERR_UNSUPPORTED_MEDIA` |
| `GET /healthz`·`/readyz`·`/metrics`·`/v1/version` | — | `application/json` (metrics는 `text/plain; version=0.0.4`) | |
| `POST /v1/studies/{uid}/withdraw-stub` | `application/json` | `application/json` | 501 반환(dev-spec FR-73) |

`Accept` 헤더가 없거나 `*/*` 이면 `application/json` 기본. JSON 외 요청 시 `406 Not Acceptable` + `ERR_NOT_ACCEPTABLE`.

### 2.8 페이지네이션 (향후 엔드포인트 대비 플레이스홀더)

v0.1은 목록 조회 API가 없다. 그러나 v0.2 이후 추가될 `/v1/studies`, `/v1/anchors`, `/v1/audit/events` 등에서는 **cursor 기반 페이지네이션**을 권장 사용한다 (오프셋 기반 금지 — 감사 테이블 월 파티션과 호환 안 됨).

**권장 계약 (문서화 plank)**:

```
GET /v1/studies?hospital_id=hosp_abc&limit=50&cursor=eyJ0cyI6IjIwMjYt...

Response 200:
{
  "items":       [ ... ],
  "next_cursor": "eyJ0cyI6IjIwMjYt..." ,   // null if end
  "limit":       50
}
```

- `limit`: 기본 50, 최대 500. 초과 → `400 ERR_PAGE_LIMIT`.
- `cursor`: 불투명 base64url 문자열(`{ts, pk}` 인코딩). 클라이언트는 **해석 금지**, 서버만.
- 정렬: 기본 내림차순 `ingested_at DESC`. 변경은 `order=asc` 쿼리.
- 필터 누락 시 **hospital_id 필수**(scoping 보호). 예외 `/v1/version` 등.

v0.1에서는 위 계약을 문서화만 하고 엔드포인트는 구현하지 않는다.

---

## 3. Operator CLI — `ingest-admin`

### 3.1 설계 원칙

- **명령 1개 = 작업 1개**. 복합 플래그 남용 금지.
- **영어 우선 UI**, 한국어는 `--lang ko` 옵션으로 전환(v0.1 optional).
- **종료 코드**(`EX_*`)는 BSD sysexits 기반으로 Gateway CLI와 동일 (0/1/2/64/69/70).
- **`--json` 플래그**: 모든 read 계열 명령은 `--json` 출력 지원. 자동화 스크립트·관측 연동용.
- **`--dry-run` 플래그**: 모든 write 계열 명령(`token issue`, `token revoke`, `migrate up`)은 `--dry-run`으로 DB 변경 없이 검증.
- **`--no-color`**, `NO_COLOR=1` 환경변수 준수 (Gateway design-spec §9와 일관).

### 3.2 명령 트리

```
ingest-admin
├── token
│   ├── issue     --hospital-id HID [--expires-days N] [--note STR] [--dry-run]
│   ├── revoke    --kid KID [--reason STR]
│   └── list      [--hospital-id HID] [--include-revoked] [--json]
├── anchor
│   └── verify    --hospital-id HID [--from SEQ] [--to SEQ] [--json]
├── study
│   └── show      --pseudo-study-uid UID [--json]
├── withdraw
│   └── request   --pseudo-study-uid UID --reason STR            # v0.1 스텁 → 501 응답 기록만
├── migrate
│   ├── up        [--revision REV] [--dry-run]
│   ├── down      --revision REV [--dry-run]
│   └── current
└── version       [--json]
```

**전역 플래그**

| 플래그 | 설명 |
|--------|------|
| `-c, --config PATH` | 기본 `/etc/radivault-central/ingest.yml` 또는 `$RADIVAULT_CENTRAL_CONFIG` |
| `--database-url URL` | Config override. 일회성 작업용. |
| `--log-level LEVEL` | DEBUG \| INFO \| WARN \| ERROR |
| `--no-color` | ANSI 색 비활성 |
| `--quiet` | WARN 이하 억제 |
| `-h, --help` | 도움말 |
| `-V, --version` | `version` 서브커맨드 동일 |

### 3.3 `ingest-admin token issue`

```
$ ingest-admin token issue --help
Usage: ingest-admin token issue [OPTIONS]

  Issue a new Bearer token for a hospital. Prints the token ONCE to stdout.
  Stores only the argon2id hash in the database; plaintext is never persisted.

Options:
  --hospital-id TEXT      External hospital identifier (e.g., hosp_abc)  [required]
  --expires-days INTEGER  Expiry in days from now. Omit for no expiry.
  --note TEXT             Human-readable note (stored alongside token row)
  --dry-run               Validate inputs but do not insert
  --json                  Emit JSON instead of the framed text block
  -h, --help              Show this message and exit

Exit codes:
  0   Token issued
  1   Hospital not found (ERR_ADMIN_HOSPITAL_NOT_FOUND)
  2   Database error
  64  Argument validation error (EX_USAGE)
```

**Happy-path 출력 (텍스트)**

```
$ ingest-admin token issue --hospital-id hosp_abc --expires-days 365 --note "pilot-2026-apr"
═══════════════════════════════════════════════════════════════════════════════
 RadiVault Central — new Bearer token issued
═══════════════════════════════════════════════════════════════════════════════
 hospital_id : hosp_abc
 token_kid   : rvct_0a1b2c3d
 expires_at  : 2027-04-22T10:00:00Z
 issued_at   : 2026-04-22T10:00:00Z
 note        : pilot-2026-apr
───────────────────────────────────────────────────────────────────────────────
 Plaintext token (shown ONCE, store now):

   rvct_0a1b2c3d.ZJ3f8vX9qK2sLpN4mQbW7yR1eT5aU6cD8gH0iK3lM6nP8qR

───────────────────────────────────────────────────────────────────────────────
 Next steps:
  1. Hand this token to the hospital IT contact via an encrypted channel
     (1Password share link / age-encrypted file / onsite USB).
  2. Hospital IT writes it to /etc/radivault/credentials/upload_token (0600).
  3. Do NOT email, Slack DM, or paste into a ticket.
═══════════════════════════════════════════════════════════════════════════════
```

**에러 시나리오**

| 상황 | 종료 | 메시지 |
|------|------|--------|
| `--hospital-id` 등록 안 됨 | 1 | `[ERR_ADMIN_HOSPITAL_NOT_FOUND] 병원이 등록되어 있지 않습니다: hosp_xyz / Hospital not enrolled: hosp_xyz. 먼저 init-hospital을 실행하세요.` |
| argon2 해시 실패 | 2 | `[ERR_ADMIN_HASH_FAIL] argon2id 해싱 실패 / argon2id hashing failed — config.auth.argon2 튜닝 확인.` |
| DB 접속 실패 | 2 | `[ERR_DB_UNAVAILABLE] PostgreSQL 연결 실패 / PostgreSQL unreachable — DATABASE_URL 및 네트워크 확인.` |

### 3.4 `ingest-admin token revoke`

```
$ ingest-admin token revoke --kid rvct_0a1b2c3d --reason "compromised 2026-04-22"
[OK] revoked rvct_0a1b2c3d at 2026-04-22T10:05:12Z
     hospital_id  : hosp_abc
     reason       : compromised 2026-04-22
     active tokens remaining for this hospital: 1
```

**에러**: `--kid` 미존재 → `ERR_ADMIN_TOKEN_NOT_FOUND` (exit 1). 이미 철회 → `ERR_ADMIN_TOKEN_ALREADY_REVOKED` (exit 1, idempotent 정보만).

### 3.5 `ingest-admin token list`

```
$ ingest-admin token list --hospital-id hosp_abc
HOSPITAL_ID   KID             ISSUED_AT            EXPIRES_AT           LAST_USED            STATUS    NOTE
hosp_abc      rvct_0a1b2c3d   2026-04-22 10:00Z    2027-04-22 10:00Z    2026-04-22 14:30Z    active    pilot-2026-apr
hosp_abc      rvct_ffeedd00   2025-10-01 09:00Z    2026-10-01 09:00Z    2026-04-22 02:15Z    active    legacy
hosp_abc      rvct_11223344   2025-01-15 11:00Z    2026-01-15 11:00Z    2025-12-30 23:45Z    expired   bootstrap

3 tokens (2 active, 0 revoked, 1 expired)
```

`--include-revoked` 시 철회 항목도 포함. `--json` 시:

```json
{
  "hospital_id": "hosp_abc",
  "tokens": [
    {"kid":"rvct_0a1b2c3d","issued_at":"...","expires_at":"...","last_used_at":"...","status":"active","note":"pilot-2026-apr"}
  ],
  "summary": {"total":3, "active":2, "revoked":0, "expired":1}
}
```

### 3.6 `ingest-admin anchor verify`

```
$ ingest-admin anchor verify --hospital-id hosp_abc
Verifying anchor chain for hosp_abc...
Range: seq [1..12345]  anchors=284
Continuity : PASS
Monotonic  : PASS
Head hash  : sha256:c3d4e5f6...
Last anchor: 2026-04-22 10:00:12 KST  lag=15m
[OK] chain intact

$ ingest-admin anchor verify --hospital-id hosp_abc --from 1 --to 9999 --json
{
  "hospital_id":"hosp_abc","seq_lo":1,"seq_hi":9999,
  "anchors":201,"continuity":"pass","monotonic":"pass",
  "head_hash":"sha256:abcd...","last_anchored_at":"...",
  "lag_seconds":901
}
```

**실패 예시**

```
$ ingest-admin anchor verify --hospital-id hosp_xyz
[FAIL] chain break at seq=4821
       prev.seq_hi = 4820, expected next seq_lo = 4821
       actual  seq_lo  = 4823  (gap of 2)
       anchored_at    = 2026-04-20 11:00:00Z
       last valid seq = 4820 @ 2026-04-20 10:00:00Z
  Runbook: RB-3 (anchor chain break) — https://docs.radivault.io/central-ingest/runbooks/RB-3
Exit 1.
```

### 3.7 `ingest-admin study show`

```
$ ingest-admin study show --pseudo-study-uid 2.25.140737...
STUDY
  pseudo_study_uid   : 2.25.140737488355328.1.2.3
  hospital_id        : hosp_abc
  gateway_id         : gw_7f3a9c
  central_job_id     : ingest_01HXX8WQ9Z
  ingested_at        : 2026-04-22 10:20:01 KST
  modality           : MR  (body_part=BRAIN)
  n_series           : 5
  n_instances        : 184
  total_bytes        : 94,321,012
  study_date_shifted : 2026-05-13      (+42d offset)

OBJECT KEYS (first 3 of 184)
  prod/a1/hosp_abc/2.25.xxxx/2.25.yyyy/2.25.zzzz1.dcm
  prod/a1/hosp_abc/2.25.xxxx/2.25.yyyy/2.25.zzzz2.dcm
  prod/a1/hosp_abc/2.25.xxxx/2.25.yyyy/2.25.zzzz3.dcm

AUDIT EVENTS (last 5 for this study)
  2026-04-22 10:20:01Z  ingest.accepted   http=201  request_id=01HXX...
  2026-04-22 10:18:44Z  ingest.rejected   http=409  error=ERR_MANIFEST_DUP   request_id=...
  (earlier events elided)
```

### 3.8 `ingest-admin withdraw request` (v0.1 스텁)

```
$ ingest-admin withdraw request --pseudo-study-uid 2.25.xxx --reason "data subject request 2026-04-22"
[STUB] withdraw flow not implemented in v0.1 (dev-spec FR-73).
       Request logged to audit_ingest_event (event=withdraw.stub.invoked).
       See Runbook RB-8 for manual containment procedure.
Exit 0.
```

### 3.9 `ingest-admin migrate`

```
$ ingest-admin migrate current
current revision: ab12cd34ef56 (head)   applied at 2026-04-22T08:00:00Z

$ ingest-admin migrate up --dry-run
planned migrations:
  ab12cd34ef56 → cd34ef5678ab   add_hospital_quota_monthly_column
  cd34ef5678ab → ef5678abcd12   add_idx_anchor_hash_dup
(dry-run — no changes applied)

$ ingest-admin migrate up
applying ab12cd34ef56 → cd34ef5678ab ... ok (0.42s)
applying cd34ef5678ab → ef5678abcd12 ... ok (0.18s)
[OK] head reached: ef5678abcd12
```

**주의**: `migrate` 는 반드시 `MIGRATION_DATABASE_URL` (DDL 권한 슈퍼유저) 사용. 애플리케이션 런타임 DSN(`central_app`, SELECT+INSERT 한정)으로는 거부하고 `ERR_ADMIN_WRONG_ROLE` 반환.

### 3.10 `ingest-admin version`

```
$ ingest-admin version
radivault-central  0.1.0
build              ab12cd34 (2026-04-22T09:00:00Z)
api_contract       1
python             3.11.9
postgres_client    asyncpg 0.29.0
boto3              1.34.77

$ ingest-admin version --json
{"service":"radivault-central","version":"0.1.0","git_sha":"ab12cd34",
 "built_at":"2026-04-22T09:00:00Z","api_contract_version":"1",
 "python":"3.11.9","asyncpg":"0.29.0","boto3":"1.34.77"}
```

### 3.11 종료 코드 요약

| Command | 0 | 1 | 2 | 64 | 69 | 70 |
|---------|---|---|---|----|----|----|
| `token issue` | OK | Hospital not found | DB error | Arg error | — | Internal |
| `token revoke` | OK | KID not found / already | DB error | Arg error | — | Internal |
| `token list` | OK | — | DB error | Arg error | — | — |
| `anchor verify` | chain OK | chain break | DB error | Arg error | — | — |
| `study show` | OK | Not found | DB error | Arg error | — | — |
| `withdraw request` | Stub logged | — | DB error | Arg error | — | — |
| `migrate up/down` | OK | Revision conflict | DB error | Arg error | — | Internal |
| `migrate current` | OK | — | DB error | — | — | — |
| `version` | 항상 0 | — | — | — | — | — |

---

## 4. Log & Observability 출력

### 4.1 JSON 로그 스키마 (단일 레코드 shape)

모든 애플리케이션 로그는 stdout에 **JSON-lines** 로 방출한다 (dev-spec FR-60 기반 확장).

```jsonc
{
  "ts":          "2026-04-22T10:20:01.234Z",    // UTC ISO8601, ms 정밀
  "level":       "INFO",                         // DEBUG|INFO|WARN|ERROR|CRITICAL
  "service":     "radivault-central",            // 고정
  "logger":      "radivault_central.api.ingest", // python logger 이름
  "trace_id":    "6a8c9e0f1b2d3c4e5f6a7b8c9d0e1f2a",
  "span_id":     "0123456789abcdef",
  "request_id":  "01HXX8WQ9Z3K7V5B2A1N6P4R9T",
  "hospital_id": "hosp_abc",                     // 토큰 매핑 시 주입, 미인증 요청에는 null
  "gateway_id":  "gw_7f3a9c",                    // manifest 읽은 뒤에만
  "event":       "ingest.accepted",              // namespace.action
  "message_ko":  "업로드 수락 — hosp_abc 2.25.xxxx (184 instances, 94.3MB)",
  "message_en":  "Ingest accepted for hosp_abc study=2.25.xxxx (184 instances, 94.3MB)",
  "path":        "/v1/ingest/studies",
  "method":      "POST",
  "status":      201,
  "duration_ms": 8742,
  "extra": {                                     // 구조화 추가 필드 (PHI 금지)
    "central_job_id": "ingest_01HXX8WQ9Z3K7V5B2A1N6P4R9T",
    "pseudo_study_uid": "2.25.140737488355328.1.2.3",
    "n_instances": 184,
    "bytes_received": 94321012,
    "idempotency_replayed": false
  }
}
```

**금지 필드** (dev-spec §6.7): 원본 StudyInstanceUID / PatientName / PatientID / 병원 내부 호스트명 / 토큰 평문 / PACS IP. Logger는 sanitiser 필터를 거쳐 이들을 감지하면 **레코드 전체 삭제 + `ERR_LOG_PHI_DETECTED` 카운터 증가**.

**필드 순서 규약**: 위 순서대로 직렬화. SRE 가 `jq` 로 빠르게 grep 할 때 컬럼 위치가 안정화된다.

### 4.2 5-line 현실적 예시 (이벤트 5종 커버)

```json
{"ts":"2026-04-22T10:20:01.234Z","level":"INFO","service":"radivault-central","logger":"radivault_central.api.ingest","trace_id":"6a8c...","span_id":"0123...","request_id":"01HXX8WQ9Z","hospital_id":"hosp_abc","gateway_id":"gw_7f3a9c","event":"ingest.accepted","message_ko":"업로드 수락 — hosp_abc 2.25.xxxx (184 instances, 94.3MB)","message_en":"Ingest accepted","path":"/v1/ingest/studies","method":"POST","status":201,"duration_ms":8742,"extra":{"central_job_id":"ingest_01HXX","pseudo_study_uid":"2.25.xxx","n_instances":184,"bytes_received":94321012,"idempotency_replayed":false}}
{"ts":"2026-04-22T10:20:03.007Z","level":"INFO","service":"radivault-central","logger":"radivault_central.middleware.idempotency","trace_id":"7b9d...","span_id":"0abc...","request_id":"01HXX9AB2C","hospital_id":"hosp_abc","gateway_id":"gw_7f3a9c","event":"idempotency.replayed","message_ko":"Idempotency replay — 기존 응답 반환","message_en":"Idempotency-Key replay","path":"/v1/ingest/studies","method":"POST","status":201,"duration_ms":14,"extra":{"original_request_id":"01HXX8WQ9Z","idempotency_key_prefix":"01HXX8","idempotency_replayed":true}}
{"ts":"2026-04-22T10:21:55.012Z","level":"WARN","service":"radivault-central","logger":"radivault_central.auth","trace_id":"8c0e...","span_id":"1bcd...","request_id":"01HXXAUTH2","hospital_id":null,"gateway_id":null,"event":"auth.failure","message_ko":"인증 실패 — 잘못된 kid","message_en":"Authentication failed","path":"/v1/ingest/studies","method":"POST","status":401,"duration_ms":4,"extra":{"error_code":"ERR_AUTH_MISSING","reason":"kid_not_found","token_kid_prefix":"rvct_deadbee"}}
{"ts":"2026-04-22T10:22:10.556Z","level":"ERROR","service":"radivault-central","logger":"radivault_central.storage.s3","trace_id":"9d1f...","span_id":"2cde...","request_id":"01HXXSTOR3","hospital_id":"hosp_abc","gateway_id":"gw_7f3a9c","event":"storage.write_failed","message_ko":"S3 쓰기 실패 — 3회 재시도 소진","message_en":"S3 PUT failed after retries","path":"/v1/ingest/studies","method":"POST","status":502,"duration_ms":45001,"extra":{"error_code":"ERR_STORE_WRITE","bucket":"radivault-ingest-prod","retries":3,"last_aws_error":"RequestTimeout"}}
{"ts":"2026-04-22T10:23:00.101Z","level":"CRITICAL","service":"radivault-central","logger":"radivault_central.anchor","trace_id":"ae2a...","span_id":"3def...","request_id":"01HXXANCH4","hospital_id":"hosp_abc","gateway_id":"gw_7f3a9c","event":"anchor.chain_break","message_ko":"앵커 체인 불연속 — hosp_abc seq 4820→4823 (gap 2)","message_en":"Anchor chain discontinuity","path":"/v1/audit/anchor","method":"POST","status":400,"duration_ms":12,"extra":{"error_code":"ERR_ANCHOR_RANGE","prev_seq_hi":4820,"cur_seq_lo":4823,"gap":2,"runbook":"RB-3"}}
```

### 4.3 Prometheus 메트릭 네이밍 규약

**네임스페이스**: 모든 메트릭은 `radivault_central_*` 접두사로 시작 (RadiVault 조직 + 서비스 식별). 예외 없음. 표준 process/python runtime 메트릭(`process_*`, `python_gc_*`)은 그대로 유지.

**16개 핵심 메트릭**

| # | 이름 | 타입 | 라벨 | 단위 | 설명 |
|---|------|------|------|------|------|
| 1 | `radivault_central_ingest_requests_total` | Counter | `hospital_id`, `status` (`accepted`\|`rejected`\|`replayed`) | — | Ingest 요청 총계 |
| 2 | `radivault_central_ingest_bytes_total` | Counter | `hospital_id` | bytes | 누적 수신 바이트 |
| 3 | `radivault_central_ingest_duration_seconds` | Histogram | `hospital_id`, `outcome` | seconds | 전체 요청 시간 (버킷: 0.5, 1, 2, 5, 10, 30, 60, 300, 600, 900) |
| 4 | `radivault_central_ingest_instances_total` | Counter | `hospital_id` | — | 누적 DICOM instance 수 |
| 5 | `radivault_central_idempotency_dedup_total` | Counter | `hospital_id`, `result` (`hit`\|`miss`\|`mismatch`) | — | Idempotency 처리 |
| 6 | `radivault_central_auth_failures_total` | Counter | `reason` (`missing`\|`expired`\|`mismatch`\|`kid_not_found`) | — | 인증 실패 |
| 7 | `radivault_central_anchor_requests_total` | Counter | `hospital_id`, `status` (`accepted`\|`rejected`) | — | Anchor 요청 |
| 8 | `radivault_central_anchor_lag_seconds` | Gauge | `hospital_id` | seconds | 마지막 앵커로부터 경과 |
| 9 | `radivault_central_anchor_chain_breaks_total` | Counter | `hospital_id` | — | 체인 불연속 누적(CRITICAL 알람용) |
| 10 | `radivault_central_rate_limit_hits_total` | Counter | `hospital_id`, `scope` (`per_min`\|`per_hour`\|`daily`\|`monthly`\|`ip`) | — | 레이트 리밋 |
| 11 | `radivault_central_storage_operations_total` | Counter | `operation` (`put`\|`delete`\|`head`), `outcome` (`ok`\|`retry`\|`fail`) | — | S3 호출 |
| 12 | `radivault_central_storage_duration_seconds` | Histogram | `operation` | seconds | S3 호출 지연 |
| 13 | `radivault_central_db_pool_in_use` | Gauge | — | — | 현재 사용 중 DB 커넥션 |
| 14 | `radivault_central_db_pool_size` | Gauge | — | — | 풀 전체 크기 (포화율 계산) |
| 15 | `radivault_central_redis_operations_total` | Counter | `operation`, `outcome` | — | Redis 호출 |
| 16 | `radivault_central_manifest_rejections_total` | Counter | `hospital_id`, `error_code` | — | manifest preflight 실패 (taxonomy 분포) |
| 17 | `radivault_central_build_info` | Gauge | `version`, `git_sha`, `python_version` | — | 1로 고정, 라벨로 빌드 정보 노출 |
| 18 | `radivault_central_readyz_checks` | Gauge | `check` (`db`\|`redis`\|`s3`\|`migrations`) | 0\|1 | 각 readiness check 결과 |

**원칙**:

- `status`·`outcome`·`scope`·`operation` 등 enum-label은 **카디널리티 ≤ 10**. `pseudo_study_uid`, `request_id`, `trace_id` 같은 고카디널리티 값은 라벨로 **절대 금지**.
- 단위는 이름에 포함(`_bytes`, `_seconds`, `_total`). Prometheus 기본 규약 준수.
- Histogram 버킷은 명시적 정의. `_seconds` 는 SI 초 단위(밀리초 금지).

### 4.4 알람 설계 (최소 10편)

**Severity 규약**: `P1` = 즉시 호출(24/7), `P2` = 업무시간 1시간 내 대응, `P3` = 익영업일 대응.

| # | 이름 | 조건 | 임계 | 지속 | Severity | Runbook |
|---|------|------|------|------|----------|---------|
| A-1 | `IngestAnchorLagHigh` | `radivault_central_anchor_lag_seconds{hospital_id=~".+"} > 10800` | lag > 3h | 15m | P2 | RB-3 |
| A-2 | `IngestAnchorLagCritical` | `...{hospital_id=~".+"} > 21600` | lag > 6h | 5m | P1 | RB-3 |
| A-3 | `IngestErrorRateHigh` | `sum(rate(radivault_central_ingest_requests_total{status="rejected"}[5m])) / sum(rate(radivault_central_ingest_requests_total[5m])) > 0.01` | 전체 요청의 1% 초과 실패 | 10m | P2 | RB-2 |
| A-4 | `IngestStorageFailuresHigh` | `sum(rate(radivault_central_storage_operations_total{outcome="fail"}[5m])) / sum(rate(radivault_central_storage_operations_total[5m])) > 0.005` | 0.5% 초과 | 10m | P1 | RB-5 |
| A-5 | `IngestDbPoolSaturation` | `radivault_central_db_pool_in_use / radivault_central_db_pool_size > 0.8` | 80% 초과 | 5m | P1 | RB-4 |
| A-6 | `IngestRedisDown` | `radivault_central_readyz_checks{check="redis"} == 0` | 즉시 | 2m | P1 | RB-6 |
| A-7 | `IngestAuthFailureStorm` | `sum by (hospital_id) (rate(radivault_central_auth_failures_total[1m])) > 50` | 병원당 50회/분 초과 | 3m | P1 | RB-1 |
| A-8 | `IngestIdempotencyMismatch` | `increase(radivault_central_idempotency_dedup_total{result="mismatch"}[5m]) > 0` | 1건이라도 | 1m | P2 | RB-2 |
| A-9 | `IngestAnchorChainBreak` | `increase(radivault_central_anchor_chain_breaks_total[1m]) > 0` | 1건이라도 | 1m | P1 | RB-3 |
| A-10 | `IngestManifestRejectionSpike` | `sum by (hospital_id,error_code) (rate(radivault_central_manifest_rejections_total[10m])) > 5` | 특정 병원·code 10분 내 5회/분 초과 | 10m | P2 | RB-2 |
| A-11 | `IngestReadyzFailing` | `radivault_central_readyz_checks < 1` 중 하나라도 | 즉시 | 3m | P1 | RB-4/5/6 중 원인별 |
| A-12 | `IngestIdempotencyMirrorDivergence` | (배치 잡) mirror DB row count - Redis key count 차이 > 100 | >100 | 배치 | P3 | RB-6 |

### 4.5 로그·메트릭 수집 다이어그램 (ASCII)

```
                        ┌──────────────────────────────┐
                        │  gunicorn + uvicorn (FastAPI)│
                        │   radivault_central.asgi:app │
                        └──────┬──────────┬────────────┘
                               │stdout    │/metrics
                               ▼          ▼
                   ┌────────────────┐   ┌────────────────┐
                   │ JSON log lines │   │ Prometheus     │
                   │ (docker logs /  │   │ scrape target  │
                   │  journald)     │   │                │
                   └───────┬────────┘   └───────┬────────┘
                           │                     │
                           ▼                     ▼
                   ┌────────────────┐   ┌────────────────┐
                   │ Log aggregator │   │ Prometheus     │
                   │ (OpenSearch /  │   │ server +       │
                   │  Loki v0.2)    │   │ Alertmanager   │
                   └────────────────┘   └───────┬────────┘
                                                │
                                                ▼
                                       ┌────────────────┐
                                       │ On-call 알림 /   │
                                       │ Slack #oncall   │
                                       └────────────────┘
```

v0.1 은 Prometheus + Alertmanager + Slack webhook 기본. OpenSearch/Loki 로그 집계는 v0.2.

---

## 5. Error Taxonomy UX

dev-spec §13 / §7.7 의 모든 에러 코드를 운영자 친화 표로 펼친다. 5-field 템플릿을 사용(Gateway design-spec §5.5와 정확히 동일 포맷):

**템플릿**

```
[<CODE>] <한국어 한 줄> / <English one line>
  <상황 필드들 key: value 들여쓰기 2칸>
  수정 / Fix: <가능하면 1줄 제안>
  문서 / Docs: https://docs.radivault.io/central-ingest/errors/<CODE>
```

### 5.1 Auth 영역

| Code | HTTP | 발생 조건 | message_ko | message_en | Gateway 운영자 조치 | RadiVault SRE 조치 | Doc |
|------|------|-----------|------------|------------|----------------------|-----------------------|-----|
| `ERR_AUTH_MISSING` | 401 | `Authorization` 헤더 누락/형식 오류 | 인증 헤더가 없거나 형식이 잘못되었습니다. | Authorization header missing or malformed. | `/etc/radivault/credentials/upload_token` 존재·권한 0600 확인. | 최근 deploy로 헤더 strip 여부 확인(nginx config). | .../ERR_AUTH_MISSING |
| `ERR_AUTH_EXPIRED` | 401 | 토큰 만료 또는 철회 | 인증 토큰이 만료되었거나 철회되었습니다. | Token has expired or been revoked. | RadiVault 지원에 재발급 요청 + `ticket`에 `token_kid` 포함. | `ingest-admin token list --hospital-id HID` 확인 → 필요 시 `token issue` 재발급. | .../ERR_AUTH_EXPIRED |
| `ERR_AUTH_MISMATCH` | 403 | manifest.hospital_id 또는 gateway_id가 토큰의 hospital과 불일치 | 토큰과 manifest의 hospital_id가 일치하지 않습니다. | Token hospital_id does not match manifest. | Gateway config `agent.hospital_id` 확인. | audit_token 발급 정보 vs 병원 설정 대조. | .../ERR_AUTH_MISMATCH |

### 5.2 Idempotency 영역

| Code | HTTP | 발생 | message_ko | message_en | Gateway 조치 | SRE 조치 | Doc |
|------|------|------|------------|------------|--------------|----------|-----|
| `ERR_IDEMP_MISSING` | 400 | `Idempotency-Key` 헤더 누락 | Idempotency-Key 헤더가 필요합니다. | Idempotency-Key header required. | Gateway v0.1.1 이상으로 업그레이드 (dev-spec §13 D-2). | Gateway 운영자에게 업그레이드 공지. | .../ERR_IDEMP_MISSING |
| `ERR_IDEMP_FORMAT` | 400 | 키 길이 16–128, charset `[A-Za-z0-9_.-]` 위반 | Idempotency-Key 형식이 잘못되었습니다. | Idempotency-Key format invalid. | ULID 등 권장 포맷 사용. | — | .../ERR_IDEMP_FORMAT |
| `ERR_IDEMP_MISMATCH` | 409 | 동일 key + 다른 payload sha256 (신규) | 동일 Idempotency-Key에 다른 요청 바디가 제출되었습니다. | Same Idempotency-Key with different payload. | key 재사용 금지. 새 UUID 생성 후 재전송. | mirror DB에서 기존 sha256 확인, Gateway 로그 교차검증. | .../ERR_IDEMP_MISMATCH |
| `ERR_IDEMP_UNAVAILABLE` | 503 | Redis 다운 | 서버 상태 확인 중입니다. 잠시 후 재시도하세요. | Redis unavailable; service degraded. | 지수 백오프 재시도 (Retry-After 준수). | RB-6 실행. | .../ERR_IDEMP_UNAVAILABLE |

### 5.3 Manifest 영역

| Code | HTTP | 발생 | message_ko 요약 | Gateway 조치 | SRE 조치 |
|------|------|------|-----------------|--------------|----------|
| `ERR_MANIFEST_SCHEMA` | 400 | pydantic 검증 실패 | manifest 스키마 위반 (필드명 명시) | Gateway ruleset/빌드 확인. | error_code 분포 메트릭 확인. |
| `ERR_MANIFEST_VERSION` | 400 | `manifest_version != 1` | 지원하지 않는 manifest 버전. | Gateway 구버전 점검. | — |
| `ERR_MANIFEST_SHA256` | 400 | 파일 sha256 불일치 | 파일 체크섬 불일치 — 업로드 중 손상 의심. | Gateway 재시도. | 디스크·네트워크 이슈 확인. |
| `ERR_MANIFEST_RULESET` | 400 | 허용목록 외 ruleset_version | ruleset_version이 허용 목록 밖. | RadiVault에 신규 ruleset 등록 요청. | `hospital.allowed_ruleset_versions` 업데이트. |
| `ERR_MANIFEST_SALT` | 400 | salt_version 불일치 | salt_version이 현재 병원 설정과 다름. | 중앙 salt 회전 후 Gateway 갱신 누락 확인. | `hospital.salt_version_current` 비교. |
| `ERR_MANIFEST_DEID` | 400 | method_code_sequence에 113100 없음 | de-id 방법 코드가 누락되었습니다. | Gateway ruleset 버그 제보. | 해당 ruleset 퇴출. |
| `ERR_MANIFEST_ANON` | 403 | anonymization_flag 누락/부정 | 완전 익명화 플래그가 없습니다 — 업로드 차단. | Gateway v0.1.1 업그레이드 (D-3). | 병원 Gateway 롤아웃 일정 확인. |
| `ERR_MANIFEST_DUP` | 409 | pseudo_study_uid 중복 | 이미 수신된 스터디입니다. | 정상 — Idempotency-Key 사용. | `study` 테이블 원본 row 점검. |
| `ERR_MANIFEST_TOOMANY` | 413 | n_instances > 상한 | instance 수가 병원 한도를 초과. | 스터디 분할 또는 한도 상향 요청. | `hospital.max_instances_per_study` 조정 검토. |
| `ERR_MANIFEST_TOOBIG` | 413 | total_bytes > 상한 | 전체 크기가 병원 한도를 초과. | 한도 상향 요청. | `hospital.max_study_bytes` 조정 검토. |

### 5.4 Anchor 영역

| Code | HTTP | 발생 | Gateway 조치 | SRE 조치 |
|------|------|------|--------------|----------|
| `ERR_ANCHOR_SCHEMA` | 400 | 페이로드 스키마 위반 | Gateway 빌드 확인. | — |
| `ERR_ANCHOR_RANGE` | 400 | seq 불연속 | **즉시 Gateway audit 체인 검증**(`gateway-agent audit verify`). RB-3. | RB-3 실행. |
| `ERR_ANCHOR_INITIAL` | 400 | 첫 앵커 seq_lo≠1 | Gateway state.sqlite3 seq 재초기화(지원 개입). | 수동 재설정 승인. |
| `ERR_ANCHOR_MONO` | 400 | anchored_at 비단조 | 시간 동기(NTP) 확인. | — |
| `ERR_ANCHOR_ORDER` | 400 | seq_lo > seq_hi | Gateway 버그 — 지원 보고. | — |
| `ERR_ANCHOR_DUP` | 409 | (hospital, range) 중복 | 정상 — 중복 재시도 무시. | — |
| `ERR_ANCHOR_HASH_DUP` | 409 | head_hash 재출현 | 체인 꼬임 의심 — 지원 보고. | RB-3 실행. |

### 5.5 Rate & Storage & DB & 기타

| Code | HTTP | 발생 | Gateway 조치 | SRE 조치 |
|------|------|------|--------------|----------|
| `ERR_RATE_LIMITED` | 429 | 분·시 한도 초과 | Retry-After 준수 재시도. | 한도 튜닝 검토. |
| `ERR_RATE_QUOTA_DAILY` | 429 | 일 쿼터 초과 | 업로드 일정 분산. | 쿼터 계약 확인. |
| `ERR_RATE_QUOTA_MONTHLY` | 429 | 월 쿼터 초과 | 월 쿼터 상향 계약 협의. | 월 집계 테이블 점검. |
| `ERR_STORE_WRITE` | 502 | S3 쓰기 3회 재시도 실패 | 지수 백오프 재시도. | RB-5 실행. |
| `ERR_DB_UNAVAILABLE` | 503 | PG 불가 | 지수 백오프 재시도. | RB-4 실행. |
| `ERR_NOT_IMPLEMENTED` | 501 | withdraw-stub | — | 호출자에게 v0.2 일정 안내. |
| `ERR_INTERNAL` | 500 | 미분류 예외 | `request_id` 수집 후 지원 전달. | Sentry/로그에서 stack trace 조회. |
| `ERR_UNSUPPORTED_MEDIA` | 415 | Content-Type 위반 | 헤더 수정 재시도. | — |
| `ERR_NOT_ACCEPTABLE` | 406 | Accept 헤더 위반 | `Accept: application/json` 사용. | — |
| `ERR_INGEST_CTYPE` (신규) | 400 | multipart 필수 엔드포인트에 JSON | 헤더 확인. | — |
| `ERR_PAGE_LIMIT` (v0.2) | 400 | limit>500 | — | — |
| `ERR_LOG_PHI_DETECTED` (internal) | — | 로그 sanitiser 차단 | — | 즉시 콜드 리뷰·재현. |
| `ERR_ADMIN_HOSPITAL_NOT_FOUND` | — (CLI) | token issue 시 hospital 없음 | — | `init-hospital` 선행. |
| `ERR_ADMIN_TOKEN_NOT_FOUND` | — (CLI) | revoke 시 kid 없음 | — | `token list` 조회. |
| `ERR_ADMIN_TOKEN_ALREADY_REVOKED` | — (CLI) | 중복 revoke | — | 정보성. |
| `ERR_ADMIN_HASH_FAIL` | — (CLI) | argon2 실패 | — | config 튜닝. |
| `ERR_ADMIN_WRONG_ROLE` | — (CLI) | DDL 권한 없는 DSN으로 migrate 시도 | — | `MIGRATION_DATABASE_URL` 사용. |

> **Coverage 확인**: dev-spec §7.7 표의 모든 코드(ERR_AUTH_*, ERR_IDEMP_*, ERR_MANIFEST_*, ERR_ANCHOR_*, ERR_STORE_*, ERR_DB_*, ERR_RATE_*, ERR_NOT_IMPLEMENTED, ERR_INTERNAL) 를 본 §5에 모두 포함. 본 §5는 추가로 본 디자인에서 신설한 6개(`ERR_IDEMP_MISMATCH`, `ERR_UNSUPPORTED_MEDIA`, `ERR_NOT_ACCEPTABLE`, `ERR_INGEST_CTYPE`, `ERR_PAGE_LIMIT`, `ERR_LOG_PHI_DETECTED`)와 CLI 전용 5개(`ERR_ADMIN_*`)를 덧붙였다. §11 Open Q-1에 이들 신규 코드의 dev-spec 환류 필요 기재.

---

## 6. Runbook (Incident Response)

각 runbook은 5–12줄 액션 기반 플레이북. 한국어. `docs/runbooks/RB-N.md` 경로로 별도 저장 권장(본 문서에는 요약).

### RB-1 — Auth Failure Storm (`IngestAuthFailureStorm`)

```
증상:
  Prometheus A-7 알람 — 한 병원에서 분당 50회 초과 401. Gateway 모든 토큰 실패 의심.

최초 5분:
  1) `ingest-admin token list --hospital-id <HID>` — 활성 토큰 수·만료 확인.
  2) `ingest-admin anchor verify --hospital-id <HID>` — Gateway 살아있는지 교차 체크.
  3) Slack #oncall 에 하우 알림: "인증 실패 폭주 hosp_XYZ, 조사 착수".

격리:
  4) 악의 의심 시 해당 hospital_id 의 모든 토큰 즉시 `token revoke`.
  5) rate-limit 추가(IP allow-list, 임시 `ip_global_per_min` 축소) — nginx 레벨 권장.

복구:
  6) 병원 IT 담당자에 채널 공지(전화 우선) — 토큰 회전 제안.
  7) 새 토큰 발급 후 암호화 채널 전달 (RB-8 절차 따름).

사후:
  8) 로그 보관, 24h 내 Postmortem 초안 작성. 원인이 버그이면 이슈 등록.
```

### RB-2 — Manifest Validation Spike (`IngestManifestRejectionSpike`)

```
증상:
  A-10 알람 — 특정 hospital_id·error_code 조합이 10분에 5회/분 초과.

최초 5분:
  1) `radivault_central_manifest_rejections_total` 레이블로 어떤 error_code 인지 파악.
  2) Gateway 운영자에게 최근 ruleset / 버전 배포가 있었는지 확인.
  3) 샘플 request_id로 로그에서 manifest 필드 누락 상세 확인.

격리:
  4) 원인이 Gateway 빌드 버그면 해당 병원의 Gateway 롤백을 권고.
  5) 원인이 Central의 새 검증 규칙이면 feature flag(`ops.strict_validation`)로 일시 완화 가능한지 검토.

복구:
  6) 수정 배포 후 1h 동안 메트릭 정상화 확인.

사후:
  7) ruleset 변경 프로세스에 Central 사전 리뷰 단계 추가.
```

### RB-3 — Anchor Chain Break (`IngestAnchorChainBreak` / A-9)

```
증상:
  A-9 알람 또는 A-1/A-2 lag 알람. `ingest-admin anchor verify` 가 FAIL.

최초 5분:
  1) `ingest-admin anchor verify --hospital-id <HID>` 로 break seq 확인.
  2) Gateway 측 `gateway-agent audit verify /var/log/radivault/audit.log` 요청(병원 IT에 전화).
  3) `audit_anchor` 테이블에서 최근 24h row 직접 조회(`SELECT seq_lo,seq_hi,anchored_at FROM audit_anchor WHERE hospital_pk=... ORDER BY anchored_at DESC LIMIT 50;`).

격리:
  4) **Ingest 차단 기본 OFF(dev-spec FR-17)** — 정책 결정에 따라 `ops.anchor_lag_block_enabled = true` 플립 가능. Kyle 승인 필요.

복구:
  5) 원인이 Gateway 재시작 중 누락이면 수동 anchor 주입(개발자 스크립트, SRE+개발자 동시 승인).
  6) 원인이 악의적 변조 의심이면 해당 병원 수사 절차 — 즉시 KISA·법무 라인에 보고.

사후:
  7) 3개월 간 해당 병원 anchor 분 단위 모니터. 재발 시 자동 차단 활성화.
```

### RB-4 — PostgreSQL Connection Pool Exhausted (`IngestDbPoolSaturation`)

```
증상:
  A-5 알람 — `db_pool_in_use / db_pool_size > 0.8` 5분 지속. 동시에 /readyz 실패 가능.

최초 5분:
  1) `/readyz` 상태 확인. 503이면 ALB에서 트래픽 드레인 진행 중.
  2) `SELECT count(*) FROM pg_stat_activity WHERE state != 'idle';` — long-running 쿼리 찾기.
  3) `SELECT pid, query, now()-query_start AS dur FROM pg_stat_activity ORDER BY dur DESC LIMIT 10;`.

격리:
  4) 5분 이상 진행 중인 analytics 쿼리를 `pg_cancel_backend(pid)` 또는 `pg_terminate_backend(pid)`.
  5) `config.db.pool_size` 임시 증설 배포(1.5x) — 워커 추가 생성 유의.

복구:
  6) 의심 엔드포인트(예: 신규 search API) 차단, 원인 수정 배포.
  7) `/readyz` green 확인 후 ALB 트래픽 재개.

사후:
  8) PG slow query log · APM 샘플링 강화. pool 관리 SLO 대시보드 추가.
```

### RB-5 — S3 Write Failures (`IngestStorageFailuresHigh`)

```
증상:
  A-4 알람 — S3 5xx/타임아웃 0.5% 초과.

최초 5분:
  1) AWS Health Dashboard (또는 NCP) ap-northeast-2 S3 공지 확인.
  2) `radivault_central_storage_duration_seconds` p95 급증 여부.
  3) 샘플 실패 request_id의 `last_aws_error` 필드로 원인 코드 추출.

격리:
  4) 일시 장애이면 Gateway 측 Retry 만으로 흡수 — 추가 조치 없음.
  5) 지속 장애이면 `anchor_lag_block_enabled` 와 별개로 Ingest 405/503 반환 feature flag 검토(v0.2).

복구:
  6) S3 회복 후 `audit_ingest_event` 중 event='storage.orphan' row 스캔 → 수동 정리 스크립트.
  7) 반복 실패 건 수동 재업로드 협조 요청(병원 Gateway에 `sync-once --since` 지침).

사후:
  8) multi-region fail-over 검토 (v0.2).
```

### RB-6 — Redis Down (Idempotency Degraded) (`IngestRedisDown`)

```
증상:
  A-6 알람 — readyz check=redis 가 0. 신규 Ingest 전량 503 ERR_IDEMP_UNAVAILABLE.

최초 5분:
  1) `docker compose ps redis` 또는 ElastiCache 콘솔 확인.
  2) Redis 컨테이너 kill/restart 또는 클러스터 failover 트리거.
  3) Slack 공지 — "Central 현재 Ingest 일시 중단, 복구 진행 중. Gateway 재시도 대기".

격리:
  4) 무결성 우선 (dev-spec FR-32) — 절대 "Redis 없이 수락" 우회 금지.

복구:
  5) Redis 복구 후 5분 soak — `/readyz` green 확인.
  6) `ingest_idempotency_mirror` DB 테이블 vs Redis 키 수 비교 배치 돌림(A-12 사전 점검).

사후:
  7) Redis Sentinel/Cluster 도입 검토(v0.1은 단일 노드).
```

### RB-7 — Disk Full on Worker

```
증상:
  컨테이너 로그 `OSError: [Errno 28] No space left on device`. /readyz 503 혹은 502 폭증.

최초 5분:
  1) `df -h` 호스트 디스크 사용률 확인.
  2) `docker system df` — 이미지·볼륨·로그 드라이버 크기 점검.
  3) docker logs 로테이트 실패 추정 시 journald 드라이버로 전환.

격리:
  4) 트래픽 드레인 (nginx upstream 제거) → 해당 노드 격리.

복구:
  5) `docker system prune -a --filter "until=72h"`.
  6) log rotation 설정 재확인(`max-size: 100m`, `max-file: 5`).

사후:
  7) 디스크 70% 알람 추가, `/var/lib/docker` 별도 볼륨 분리 검토.
```

### RB-8 — Hospital Urgent Token Rotation

```
증상:
  병원 측 토큰 유출 의심, 또는 IT 인력 교체로 선제적 회전.

최초 5분:
  1) `ingest-admin token list --hospital-id <HID>` 현재 유효 토큰 전수 목록.
  2) 병원 IT 담당자와 전화 연결 (채팅 금지 — 보안).
  3) 새 토큰 발급 `ingest-admin token issue --hospital-id <HID> --expires-days 365 --note "rotate-YYYY-MM-DD"`.

전달:
  4) age-encrypted 파일 또는 1Password 일회성 링크로 전달. 이메일·Slack·티켓 본문 절대 금지.
  5) 병원 IT가 `/etc/radivault/credentials/upload_token` 업데이트, `docker compose restart gateway-agent`.
  6) Central 로그에서 5분 내 새 kid로 201 관측 확인.

격리:
  7) 구 토큰 `ingest-admin token revoke --kid <OLD_KID> --reason "rotation"`.

사후:
  8) `audit_ingest_event` 에 token rotation 이벤트 기록(별도 이벤트 코드 `token.rotated`).
```

### (선택) RB-9 — Idempotency Mirror Divergence (`IngestIdempotencyMirrorDivergence`)

```
증상:
  A-12 배치 잡 — mirror DB row와 Redis 키 수 차이 > 100.

조사:
  1) Redis 최근 flush·eviction 정책 확인(`maxmemory-policy`).
  2) mirror DB 최근 7일 row 수 추이(`SELECT date_trunc('hour',first_seen_at), count(*) ...`).

복구:
  3) Redis evict 이슈라면 memory 증설·정책 `noeviction` 로 전환.
  4) 데이터 손실 없음 확인 후 경보 해제.

사후:
  5) Redis용량 모니터링 알람 추가.
```

---

## 7. Hospital Onboarding Walkthrough

대상: **RadiVault SRE ↔ 병원 IT 관리자 공동 수행**. 소요 30–60분. 언어: 화면·채널 한국어 우선.

### 7.1 전체 플로우 ASCII

```
[Pre]    (1) 계약·법적 검토 완료          ─ RadiVault PM·법무
           │
           ▼
[SRE]    (2) hospital row 생성            ─ ingest-admin init-hospital (별도 dev-spec FR-75)
           │
           ▼
[SRE]    (3) 토큰 발급 & 암호화 전달      ─ ingest-admin token issue → age/1Password
           │
           ▼
[Hosp]   (4) 네트워크·PACS 사전 체크      ─ Gateway design-spec §7.1 체크리스트
           │
           ▼
[Hosp]   (5) Gateway bundle 배포          ─ docker-compose bundle.tgz
           │
           ▼
[Hosp]   (6) credentials 배치 + gateway.yml 편집
           │
           ▼
[Hosp]   (7) de-id-test → sync-once --dry-run
           │
           ▼
[Joint]  (8) 첫 실 업로드 (1건 — 지정)    ─ 실시간 SRE·Hosp 동시 관찰
           │
           ▼
[SRE]    (9) Central 측 검증              ─ ingest-admin study show
           │
           ▼
[SRE]    (10) anchor 첫 수신 확인         ─ ingest-admin anchor verify
           │
           ▼
[Joint]  (11) 운영 인계 & systemd 전환    ─ docker compose up -d → systemctl enable
           │
           ▼
[Post]   (12) 24h soak → P2 알람 없으면 GA ─ 대시보드 등록, PagerDuty rotation 추가
```

### 7.2 단계별 "화면" (운영자 관점)

**Step 1 — 사전 계약** (RadiVault PM)

```
[ ] 병원과 데이터 제공 계약 체결 (DPO 서명)
[ ] 호스팅 리전 합의 (한국 기본)
[ ] 허용 ruleset 버전 합의 (기본 v0.1.0)
```

**Step 2 — Hospital row 생성 (SRE)**

```
$ ingest-admin init-hospital \
    --hospital-id hosp_abc \
    --name "서울메디컬센터" \
    --region KR-SE \
    --allowed-ruleset-versions '["v0.1.0"]' \
    --daily-byte-quota 214748364800     # 200GB
[OK] hospital hosp_abc created (pk=3)
```

**Step 3 — Token 발급 & 전달 (SRE → Hospital)**

```
$ ingest-admin token issue --hospital-id hosp_abc --expires-days 365 --note "pilot-onboarding-2026-04"
# 출력 블록 한 번만 표시 — 즉시 age로 암호화해 1Password share link 생성
$ echo '<TOKEN>' | age -r age1hospital_admin_pubkey... > upload_token.age
# 1Password → "Shared with hospital IT" vault → 24h 만료 링크 발급
```

산출물 (SRE 측): `audit_ingest_event(event='token.issued', token_kid='rvct_...', hospital_id='hosp_abc')` 자동 기록.

**Step 4 — 병원 네트워크 사전 체크 (Hospital IT)**

Gateway design-spec §7.1의 체크리스트 그대로. 추가 Central 전용 체크:

```
[ ] *.radivault.io:443 아웃바운드 통신 테스트
    curl -v https://ingest.radivault.io/healthz
    → {"status":"ok"}  ← 이 응답 확인
[ ] GET /v1/version 응답 확인
    curl -s https://ingest.radivault.io/v1/version | jq .
```

**Step 5 — Gateway 배포**

Gateway design-spec §7.2–§7.6 그대로.

**Step 6 — credentials 배치**

```
$ sudo install -d -m 0700 /etc/radivault/credentials
$ age -d -i ~/.ssh/age.key upload_token.age > /etc/radivault/credentials/upload_token
$ sudo chmod 0600 /etc/radivault/credentials/*
```

**Step 7 — de-id-test → dry-run**

Gateway design-spec §7.5–§7.6 그대로. **Central 관여 없음** — 이 단계에서 네트워크 전송 금지.

**Step 8 — Joint 첫 실 업로드 (공동 작업)**

- 병원 IT: `docker compose run --rm gateway-agent sync-once --since 2026-04-22 --until 2026-04-22 --limit 1`
- SRE: 동시에 `docker compose logs -f central-ingest | jq 'select(.hospital_id=="hosp_abc")'` 관찰
- 기대 로그 시퀀스: `ingest.accepted` (status=201) 1개 + `anchor.accepted` 시간당 1개 (처음 1h는 없을 수 있음).

**Step 9 — Central 검증 (SRE)**

```
$ ingest-admin study show --pseudo-study-uid 2.25.xxxxx
# 확인: hospital_id, ingested_at, total_bytes, n_instances 가 manifest와 일치
```

**Step 10 — 첫 anchor 수신 확인 (SRE, 1시간 후)**

```
$ ingest-admin anchor verify --hospital-id hosp_abc
Verifying anchor chain for hosp_abc...
Range: seq [1..1]  anchors=1
Continuity : PASS
Monotonic  : PASS
[OK] chain intact
```

**Step 11 — 운영 인계 (Joint)**

- 병원 IT: `docker compose up -d` + `systemctl enable --now radivault-gateway`
- SRE: Prometheus 대시보드에 `hospital_id="hosp_abc"` 필터 탭 추가. PagerDuty schedule에 해당 병원 lag 알람 포함.

**Step 12 — 24h Soak**

- P2 이상 알람 없으면 병원을 GA 목록에 추가.
- 1주일 뒤 anchor chain 재검증 정례 업무 일정화.

### 7.3 롤백

온보딩 중단이 필요한 경우:

```
1. ingest-admin token revoke --kid <KID> --reason "rollback-onboarding"
2. Hospital IT: docker compose down, 자격 파일 삭제
3. (선택) hospital.active=false UPDATE — GA 제외
```

이미 업로드된 데이터 삭제는 v0.2 withdraw worker 의무화 대기(FR-73 stub).

---

## 8. 국제화 (i18n)

| 표면 | 언어 | 근거 |
|------|------|------|
| HTTP API 에러 envelope | `message_ko` + `message_en` 동시 | dev-spec §7, Gateway design-spec §5.5와 일관 |
| CLI `--help` | 영어 우선 | 운영자 타깃(SRE)·자동화 친화 |
| CLI 실행 출력 | 영어 기본, `--lang ko` 옵션(v0.1 optional) | — |
| Console JSON 로그 | 영어 전용 (+ 동반 `message_ko`·`message_en` 필드) | 중앙 집계·규제 보존 |
| Runbook 내부 문서 | **한국어** | 운영 엔지니어·지원팀 타깃 |
| Hospital onboarding 문서 | 한국어 | 병원 IT 담당자 |
| Error doc (`docs.radivault.io/...`) | v0.1 영어 우선, 한국어 병기 | 장기적 공개 |

**한국어 길이 규칙 (Gateway design-spec §8 상속)**: `message_ko` 는 120 bytes 이내(한글 3bytes 가정). 초과 시 마침표 앞 생략 `…` 후 `doc_url` 참조 유도.

**시간대 표기**: API 응답 JSON 은 UTC ISO8601. Runbook 본문·CLI 콘솔은 KST. CLI `--json` 모드는 UTC.

---

## 9. 접근성 (Accessibility)

| 항목 | 적용 |
|------|------|
| 색 의존 금지 | CLI 색은 보조만, `--no-color` / `NO_COLOR=1` 준수. 로그 JSON·Prometheus는 색 없음. |
| 고대비 | N/A — backend service (텍스트 출력만). |
| 스크린리더 | CLI 출력은 라인 기반 — 리더 친화. `ingest-admin token issue` 의 박스 장식(`═`)은 `--plain` 으로 ASCII(`=`) 폴백. |
| 키보드 | CLI — 원천적으로 키보드 전용. |
| UTF-8 | 기본 UTF-8, `LANG=C` 환경에서 ASCII 폴백. |
| WCAG 색 대비 4.5:1 | **N/A — backend service**: 시각 UI가 없다. Prometheus/Grafana 대시보드 디자인은 별도 대시보드-spec 범위. |
| 반응형 | **N/A — backend service**: 뷰포트 개념 없음. CLI는 80열 터미널 가로 스크롤 금지 가이드만(Gateway §9와 동일). |
| 디자인 토큰 (색·간격) | **N/A — backend service**: 시각 토큰 없음. 대신 "메트릭 네이밍 규약"·"에러 코드 네임스페이스"가 equivalent 역할. |
| 포커스 관리 | N/A. |

---

## 10. 수용 기준 (Acceptance Criteria — 디자인 측)

총 15개. `@qa` 가 라인별 바이너리 검증.

- [ ] **AC-D-1** (HTTP API) dev-spec §7의 **모든 엔드포인트**(`/v1/ingest/studies`, `/v1/audit/anchor`, `/healthz`, `/readyz`, `/v1/version`, `/v1/studies/{uid}/withdraw-stub`)가 §2.2 표준 에러 envelope의 5 필수 필드 + 2 optional 필드를 포함한 에러 응답을 문서화한다.
- [ ] **AC-D-2** (에러 코드) dev-spec §7.7 / §13 의 **모든 에러 코드**가 본 §5 Error Taxonomy 표에 나타난다. 누락 0건.
- [ ] **AC-D-3** (CLI) `ingest-admin` 서브커맨드 9개(`token issue`·`token revoke`·`token list`·`anchor verify`·`study show`·`withdraw request`·`migrate up/down/current`·`version`)가 `--help`를 구현한다. `--help` 출력이 §3의 Usage/Options/Exit codes 섹션 구조와 일치.
- [ ] **AC-D-4** (이중 언어) 모든 4xx/5xx API 응답이 `message_ko` 와 `message_en` 을 동시에 포함. 누락 시 lint 실패.
- [ ] **AC-D-5** (Runbook) RB-1..RB-8 이 각각 증상·최초5분·격리·복구·사후 5섹션을 포함한다. 본 문서에 요약 + `docs/runbooks/RB-N.md` 파일 존재.
- [ ] **AC-D-6** (JSON 로그) §4.2 5-line 예시의 이벤트 타입 5종(`ingest.accepted`, `idempotency.replayed`, `auth.failure`, `storage.write_failed`, `anchor.chain_break`)이 모두 실제 구현에서 동일 shape으로 방출된다.
- [ ] **AC-D-7** (Prometheus 네이밍) `/metrics` 에 노출되는 모든 RadiVault 고유 메트릭이 `radivault_central_*` 접두사를 사용한다. 예외 0건. `grep -E '^[a-z_]+' metrics_dump | grep -v '^(python_|process_|go_|radivault_central_)'` 결과 empty.
- [ ] **AC-D-8** (Alert) §4.4 표의 알람 12건이 모두 Alertmanager rule 파일로 정의되며 임계가 구체 숫자(추상 "high" 금지).
- [ ] **AC-D-9** (Idempotency) 동일 `Idempotency-Key` + 다른 payload sha256 → 409 `ERR_IDEMP_MISMATCH` 로 응답하며, 응답 바디 `hint` 에 원본 `request_id` 를 포함한다.
- [ ] **AC-D-10** (PHI 차단) 로그 sanitiser 필터가 §4.1 금지 필드(원본 UID·환자명·내부 호스트명)를 감지하면 레코드를 드롭하고 `ERR_LOG_PHI_DETECTED` 카운터를 증가시킨다. 감지 테스트가 CI green.
- [ ] **AC-D-11** (Onboarding) §7의 12 단계를 따라가면 파일럿 병원 1곳이 외부 문서 참조 없이 초기 업로드·첫 anchor 수신에 성공한다.
- [ ] **AC-D-12** (CLI JSON) 모든 read 명령(`token list`, `anchor verify`, `study show`, `version`)이 `--json` 플래그에서 일관된 top-level 키 구조(`hospital_id`·`summary`·`items` 등)를 출력한다.
- [ ] **AC-D-13** (에러 doc 링크) 모든 에러 응답이 `doc_url` 필드를 포함한다. v0.1에서 해당 URL이 404여도 AC 통과(§11 Q-1 예외 허용).
- [ ] **AC-D-14** (Content-Type) multipart 필수 엔드포인트에 JSON 바디 전송 시 `415` 또는 `400 ERR_INGEST_CTYPE` 반환. `Accept: text/xml` 요청은 `406 ERR_NOT_ACCEPTABLE`.
- [ ] **AC-D-15** (Gateway delta 문서화) 본 디자인 산출물이 dev-spec §13 델타(D-1..D-7)를 §11·§12 에서 재확인하고, Gateway v0.1.1 트랙 분리를 명시한다.

---

## 11. 오픈 질문

Kyle 결정 또는 외부 확인 필요.

1. **Error doc 호스팅** — `docs.radivault.io/central-ingest/errors/<CODE>` 라우트 생성 책임 (Gateway design-spec §11-1과 동일 이슈). v0.1 404 허용 여부.
2. **신규 에러 코드 6종 dev-spec 환류** — 본 디자인이 추가한 `ERR_IDEMP_MISMATCH`, `ERR_UNSUPPORTED_MEDIA`, `ERR_NOT_ACCEPTABLE`, `ERR_INGEST_CTYPE`, `ERR_PAGE_LIMIT`, `ERR_LOG_PHI_DETECTED` 를 dev-spec §7.7 enum에 포함시킬 것인가? 권장: 포함(단 `ERR_PAGE_LIMIT`는 v0.2 가드).
3. **CLI 바이너리 명칭** — `ingest-admin` vs `radivault-central` 혼재. dev-spec FR-75는 후자, 본 디자인은 전자 사용(짧음). Kyle 결정.
4. **이중 언어 API 에러** — dev-spec §7 원본 envelope은 단일 `detail` 필드. 본 디자인은 `message_ko`/`message_en` 추가. Gateway breaking 없음이나 dev-spec 환류 필요.
5. **`Idempotency-Replayed` 응답 헤더 케이스** — 소문자 `idempotency-replayed` vs 대소 혼합. HTTP 헤더는 대소무관하나 문서·테스트 일관성 필요. 권고: `Idempotency-Replayed`.
6. **`X-Original-Request-Id` 헤더 채택 여부** — 리플레이 시 원본 추적. 권고: 채택.
7. **Prometheus 라벨 cardinality 제한** — `error_code` 라벨이 50+ 로 성장하면 fan-out 영향. 권장: `error_code` 는 `radivault_central_manifest_rejections_total` 한 곳에만 허용, 다른 메트릭은 `status` 수준 enum 유지.
8. **Runbook 저장 위치** — `docs/runbooks/RB-N.md` 파일 분리 vs 본 문서 inline. 권장: 분리(grep·링크 용이).
9. **Hospital onboarding 체크리스트 PDF화** — 병원에 전달할 별도 인쇄용 산출물. v0.1은 마크다운만.
10. **CLI `--lang ko` 지원 범위** — 전체 번역 vs 에러 메시지만. 권고: 에러 메시지만 ko, 도움말·테이블 헤더는 영어 고정.
11. **Alert severity 매핑** — P1/P2/P3 을 PagerDuty 기본 severity와 어떻게 매핑할지. SRE 팀 내부 표준 확정 필요.
12. **Gateway v0.1.1 델타 타임라인** — dev-spec §13의 D-1..D-7 중 D-2/D-3 은 실운영 필수. Gateway v0.1.1 착수 시점 확정해야 Central v0.1 GA 가능.

---

## 12. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-22 | @designer (Claude Opus 4.7) | 최초 작성. HTTP API UX(envelope·에러 스키마·Idempotency 계약·Content-Type·페이지네이션 플레이스홀더) + Operator CLI `ingest-admin` 9 서브커맨드 + JSON 로그 schema + Prometheus 메트릭 18종·알람 12건 + Error taxonomy UX(dev-spec §7.7 전수 포함 + 신규 6종 + CLI 전용 5종) + Runbook 8편 + Hospital onboarding 12 단계. Gateway design-spec의 에러 메시지 템플릿·에러 코드 네임스페이스 패턴 상속. 반응형·색 대비·디자인 토큰 항목은 "N/A — backend service" 로 표기. dev-spec §13 Gateway 델타(D-1..D-7)는 **별도 Gateway v0.1.1 트랙**으로 분리, 본 디자인은 그 가정 하에 설계. |

---

### NEXT_STEP

- 완료 산출물: `docs/specs/design-spec-central-ingest.md` (v0.1 Draft)
- 제안 다음 단계: **@developer** — `claude` 브랜치에서 `central-ingest` 구현 착수.
  - 본 디자인 명세 §2 HTTP API UX(envelope + `message_ko`/`message_en`), §3 CLI 구조, §4 로그·메트릭 네이밍, §5 에러 코드 표, §6 runbook (하나당 `docs/runbooks/RB-N.md` 파일 분리 권고), §7 온보딩 절차를 구현 기준으로 반영.
  - Gateway 기존 계약 breaking 없음 확인 — dev-spec FR-70/71 호환성 시험 케이스 필수 유지.
- UI_GUIDE.md 갱신 제안: "부록: CLI 도구 공통 가이드"(Gateway §NEXT_STEP 제안과 병합)에 **HTTP API 공통 가이드** 4개 항목 추가 — 에러 envelope 5필수 필드 / `Idempotency-Key` 계약 / `Retry-After` 사용 / Prometheus 네이밍 규약. 정식 편입은 Kyle 승인 후.
- 추가 디자인 필요:
  - (a) **Gateway v0.1.1** 분기 디자인(dev-spec §13 D-1..D-7) — 별도 slug `gateway-agent-v0.1.1` 권고.
  - (b) v0.2 에서 열릴 버이어 검색 API(`/v1/studies`)·다운로드 API 의 공식 페이지네이션 디자인 — 본 문서 §2.8은 플레이스홀더.
  - (c) 운영자 대시보드(Grafana 보드 레이아웃)는 별도 dashboard-spec.
- Kyle 결정 필요 사항:
  1. §11-1 docs.radivault.io 호스팅 일정.
  2. §11-2 신규 에러 코드 6종의 dev-spec §7.7 환류 승인.
  3. §11-3 CLI 바이너리 명칭(`ingest-admin` vs `radivault-central`) 확정.
  4. §11-4 이중 언어 에러 envelope (dev-spec §7 envelope 확장) 승인.
  5. §11-7 Prometheus `error_code` 라벨 카디널리티 정책.
  6. §11-11 Alert severity (P1/P2/P3) PagerDuty 매핑 기준.
  7. §11-12 Gateway v0.1.1 트랙 착수 시점.
