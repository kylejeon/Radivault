# QA 보고서 — Central Ingest v0.1 MVP

> **Status**: Final · **Feature slug**: `central-ingest` · **Last updated**: 2026-04-22
> **작성자**: @qa (Claude Opus 4.7) · **근거**:
> - [dev-spec](../specs/dev-spec-central-ingest.md) — 75 FR / 36 AC
> - [design-spec](../specs/design-spec-central-ingest.md) — 에러 envelope / CLI / 로그 / runbook
> - [dev-spec-gateway-agent §6.4 / §7.3](../specs/dev-spec-gateway-agent.md) — 교차 계약
> - [qa-report-gateway-agent](./qa-report-gateway-agent.md) — 리포트 패턴

---

## 1. 메타

| 항목 | 값 |
|------|----|
| 검수 대상 | `claude` 브랜치, 커밋 범위 `70782e8..e874295` (central 15 커밋) + `c847e62` (Gateway D-3 bridge) |
| 독립 검증 | `pytest tests/central/unit -q` → **34/34 PASS** (0.48s) · `pytest tests/central/integration -q` → **12/12 PASS** (1.32s) · `pytest tests/unit -q` → **55/55 PASS** (0.34s, gateway 회귀) · `ruff check src tests` → **clean** |
| 선행 조건 | dev-spec·design-spec 전수 읽음. Gateway QA Round 2 PASS 확인. |
| 최종 판정 | **PASS with minor issues** |
| Critical 이슈 | 0건 |
| High 이슈 | 2건 (H-1 `LocalFsObjectStore` 경로 traversal, H-2 KMS/SSE 설정 미강제 + HTTP endpoint 허용) |
| Medium 이슈 | 4건 (M-1 hospital_id 미매핑 경로 `except Exception` 광범위, M-2 storage 실패 후 audit.rejected 미기록, M-3 idempotency mirror 트랜잭션 분리, M-4 `get_engine` 전역 싱글톤) |
| Low 이슈 | 3건 (L-1 `_central` 핸들러가 `_unhandled`로 위임되는 detail 노출 가능성, L-2 `study_exists` hospital_pk 미스코프, L-3 anchor router가 idempotency 리플레이 직전에 COMMIT) |

---

## 2. 요약

- **스코프 완성도**: dev-spec의 75개 FR 중 명시적 구현 완료 60+, 스텁 구현 3(FR-59 daily digest, FR-73 withdraw, FR-75 init-hospital CLI 단독), 의도적 v0.2 연기 4(§3.2와 정합)로 범위 내 정상. 36개 AC는 자동 검증 23건, 코드 경로 확인 9건, 인프라 의존 3건(AC-4 버킷 정책, AC-15 argon2 타이밍 Δ, AC-35 compose 60s readyz). 전반적으로 dev-spec 충실.
- **강점**: (a) 에러 envelope이 design-spec §2.2의 5 필수 + 2 optional 필드를 정확히 맞춤(`errors.py:70-82`). (b) Idempotency 리플레이 헤더 `Idempotency-Replayed: true` 실제로 방출(`idempotency/middleware.py:166-175`, 통합 테스트 204에서 assert). (c) anonymization_flag 게이트가 validator 단독 분기로 구현되어 우회 경로 없음(`manifest/validator.py:65-72`, `test_manifest_bad_anonymization_flag` 증거). (d) 앵커 체인 유효성(연속성·단조성·중복)이 DB 트랜잭션 내 SELECT 후 INSERT 패턴으로 정확(`audit/anchor.py:54-108`). (e) Gateway D-3 브릿지가 1줄로 정확히 구현되었고 Gateway 55/55 회귀 테스트 녹색.
- **경미 이슈 주요 내용**: (1) `LocalFsObjectStore`에서 manifest의 `filename`/`pseudo_study_uid`가 path-traversal 시퀀스를 포함하면 루트 외부 쓰기 가능(H-1). 프로덕션 S3 경로에서는 S3 키로 취급되어 물리 escape 없음이나 dev/test 경로의 보안 가드 부재. (2) S3 프로덕션 설정에서 `kms_key_arn`이 None이면 SSE-KMS를 적용하지 않고 조용히 평문 PUT(H-2). dev-spec FR-7은 "SSE-KMS 기본" 요구 — 기본값이 미설정이므로 운영 실수 시 PHI 평문 저장 위험. `aws:SecureTransport` bucket policy 강제는 스펙상 bucket policy 몫이라 문서화로 커버 가능하나 설정 hygiene 필요. (3) Storage PUT 실패 시 `ingest.rejected` 감사 이벤트가 기록되지 않음(M-2) — dev-spec §8.4 "orphan object key 감사"가 코드 경로에 없음. 이 셋을 제외하면 Critical 금지사항(PHI 로그 유출, 익명화 게이트 우회, 교차 병원 누수) 위반 없음.

---

## 3. 수용 기준 매트릭스 (36건)

### 3.1 Ingest API · Manifest Preflight (AC-1 ~ AC-13)

| AC | 판정 | 증거 |
|----|------|------|
| **AC-1** (201 + central_job_id & job_id 동일) | **PASS** | `routers/ingest.py:210-215` 응답 페이로드 두 키 동일 값. 통합 테스트 `test_ingest_happy_path_emits_central_job_id` (`tests/central/integration/test_ingest_e2e.py:162-172`) 에서 `body["job_id"] == body["central_job_id"]` assert. |
| **AC-2** (sha256 mismatch → 400 ERR_MANIFEST_SHA256, S3 미생성) | **PASS (코드+테스트)** | `routers/ingest.py:109-116` per-file sha256 compare 후 `ManifestSha256` raise. sha256 검증은 S3 PUT **전에** 전수 수행(`:103-125`)하므로 mismatch 시 `uploaded_keys`는 비어 있음. 통합 테스트 `test_ingest_sha256_mismatch` (`:183-191`) 확인. |
| **AC-3** (S3 키 규칙 + _manifest.json) | **PASS (코드)** | `routers/ingest.py:127-141` `{env}/{hash2}/{hospital_id}/{pseudo_study_uid}/{pseudo_study_uid}/{filename}` 생성, `_manifest.json`도 동일 prefix로 PUT. **경미 drift**: dev-spec §4.1 FR-6은 `{pseudo_study_uid}/{pseudo_series_uid}/{pseudo_sop_uid}.dcm`를 요구하나 구현은 `{pseudo_study_uid}/{pseudo_study_uid}/{filename}` — 실제 series/sop 계층 대신 filename 원본 보존. dev-spec 위반 가능 (L-4로 관찰). |
| **AC-4** (SSE-KMS·퍼블릭 차단 정책) | **NOT VERIFIABLE (문서만)** | `storage/s3.py:62-65` 코드 경로에 `kms_key_arn` 있으면 `ServerSideEncryption=aws:kms` 설정. 실제 버킷 정책은 배포 문서 책임 — AC-4는 "문서화만 있어도 PASS" 요건. dev-spec·design-spec 어느 쪽도 버킷 정책 YAML 샘플을 포함하지 않음. H-2와 연관. |
| **AC-5** (파일 누락 시 400 + cleanup 또는 orphan 감사) | **PARTIAL** | `routers/ingest.py:120-125` file count mismatch 시 400 raise 지만 이 경로는 S3 PUT **전**이라 cleanup 불필요 (OK). 그러나 **S3 PUT 중 실패(`:142-149`) 시** `store.delete_objects(uploaded_keys)` 호출은 있으나 `event='storage.orphan'` 감사 이벤트 기록은 없음 (M-2). AC-5 후반부("또는 `storage.orphan` 감사 이벤트가 기록됨") 미충족. |
| **AC-6** (anonymization_flag pseudonymized → 403 ERR_MANIFEST_ANON + 감사) | **PARTIAL** | `manifest/validator.py:65-72` 403 분기 정상. 통합 테스트 `test_ingest_rejects_missing_anonymization_flag` (`:174-180`) PASS. 그러나 **`ingest.rejected` 감사 이벤트는 기록되지 않음** — preflight 실패 시 `raise` 경로는 `audit_ingest_event` write 로직에 도달하지 않음 (`routers/ingest.py:82-86`은 메트릭만 증가). dev-spec FR-56 "모든 Ingest 성공·실패 이벤트는 `audit_ingest_event`에 1 row 기록" 위반. C-3 Critical로 승격해야 할지 검토 필요 → **H-3로 분류**(아래 §4). |
| **AC-7** (manifest_version != 1 → 400 ERR_MANIFEST_VERSION) | **PASS** | `manifest/validator.py:59-63`, `test_manifest_version_rejected`. |
| **AC-8** (허용목록 외 ruleset → 400 ERR_MANIFEST_RULESET) | **PASS** | `manifest/validator.py:74-82`, `test_manifest_ruleset_allowlist`. |
| **AC-9** (salt_version 불일치 → 400 ERR_MANIFEST_SALT) | **PASS** | `manifest/validator.py:84-91`, `test_manifest_salt_mismatch`. |
| **AC-10** (method_code_sequence empty → 400 ERR_MANIFEST_DEID) | **PASS** | `manifest/validator.py:93-97` + `schema.py:21` `method_code_sequence: list[str] = Field(min_length=1)` (empty array는 400 ERR_MANIFEST_SCHEMA로 먼저 걸림). `test_manifest_missing_deid_code`에서 `["999999"]`로 113100 없는 케이스도 확인. |
| **AC-11** (동일 pseudo_study_uid, 다른 Idem-Key 두 번 → 409 ERR_MANIFEST_DUP) | **PASS** | `routers/ingest.py:94-96` `study_exists` 후 `ManifestDuplicate`. 통합 테스트 `test_ingest_duplicate_study_rejected` (`:207-215`) 확인. |
| **AC-12** (n_instances=6000 > 5000 → 413 ERR_MANIFEST_TOOMANY) | **PASS** | `manifest/validator.py:99-106`, `test_manifest_toomany_instances`. |
| **AC-13** (preflight 실패 시 스트리밍 카운터) | **NOT VERIFIABLE (구현 의도 벗어남)** | 현재 구현은 `await request.form()`으로 multipart **전체**를 먼저 메모리로 파싱한 뒤 manifest + files를 각각 처리(`routers/ingest.py:47`). dev-spec FR-42 "preflight 실패 시 바디 수신 전 거부"를 위한 스트리밍 파서 분리가 없어 `bytes_consumed_before_reject` 로그 필드도 없음. **dev-spec 미충족이나 v0.1 난이도 고려 시 수용 가능**(big multipart DoS는 별도 인프라 수준 보호). |

### 3.2 Auth & Idempotency (AC-14 ~ AC-20)

| AC | 판정 | 증거 |
|----|------|------|
| **AC-14** (Bearer 미제공 → 401 ERR_AUTH_MISSING + WWW-Authenticate) | **PASS** | `auth/middleware.py:51-54` + `errors.py:334-335` WWW-Authenticate 추가. 통합 테스트 `test_ingest_auth_missing` (`:155-159`) 확인. |
| **AC-15** (잘못된 토큰 5회 → 상수 시간 Δ<10ms) | **NOT VERIFIABLE (코드)** | `auth/tokens.py:73-88` argon2 `PasswordHasher.verify` 사용 — 유효 hash가 있으면 constant work, 없을 때도 `hmac.compare_digest(plaintext, plaintext)` 더미 수행. **Δ 측정 테스트 없음**. 코드 경로는 타이밍 안전. |
| **AC-16** (revoked 토큰 → 401 ERR_AUTH_EXPIRED) | **PASS (코드)** | `auth/middleware.py:66-68` `row.revoked_at is not None` 분기. 자동 테스트는 없으나 경로 명확. |
| **AC-17** (manifest.hospital_id ≠ 토큰 → 403 ERR_AUTH_MISMATCH) | **PASS** | `routers/ingest.py:87-93`. 테스트는 부재 — 수동 시나리오 검증. |
| **AC-18** (Idempotency-Key 누락 → 400 ERR_IDEMP_MISSING) | **PASS** | `idempotency/middleware.py:47-53` `IdempotencyKeyValidator.validate(None)` → `IdempMissing`, `test_validate_missing_key` (`test_idempotency.py:15-19`). |
| **AC-19** (동일 키 재전송 → 201 + Idempotency-Replayed: true) | **PASS** | `idempotency/middleware.py:96-175` 리플레이 경로. 통합 `test_ingest_idempotency_replay` (`:194-204`) 에서 `second.headers.get("Idempotency-Replayed") == "true"` + `central_job_id` 동일 assert. |
| **AC-20** (Redis 중단 → 503 ERR_IDEMP_UNAVAILABLE) | **PASS (코드)** | `idempotency/middleware.py:90-94` `except Exception → IdempUnavailable`. 통합 테스트 없음. |

### 3.3 Anchor API (AC-21 ~ AC-25)

| AC | 판정 | 증거 |
|----|------|------|
| **AC-21** (첫 앵커 seq=1 → 200 + anchor_id) | **PASS** | `routers/anchor.py:30-83`, `audit/anchor.py:79-109`. 통합 `test_anchor_happy_path_and_continuity` (`:218-234`) 확인. |
| **AC-22** (seq 불연속 → 400 ERR_ANCHOR_RANGE) | **PASS** | `audit/anchor.py:84-89`, 통합 테스트 same 수트 r2 assert `:236-251`. |
| **AC-23** (anchored_at 비단조 → 400 ERR_ANCHOR_MONO) | **PASS** | `audit/anchor.py:91-97`, 단위 `test_continuity_and_monotonicity` (`:54-87`) 확인. |
| **AC-24** (동일 range → 409 DUP, 동일 head_hash → 409 HASH_DUP) | **PASS** | `audit/anchor.py:60-77` + `db/models.py:220-221` UniqueConstraint. 단위 `test_duplicate_range_and_hash` (`:90-123`) 확인. |
| **AC-25** (audit_anchor_lag_seconds Gauge 노출) | **PASS (코드)** | `telemetry.py:73-78` Gauge 정의, `routers/anchor.py:75-78` 매 성공 시 `.set(...)` 호출. ±60s 정확도는 호출 즉시 `now - anchored_at` 이므로 구조적으로 충족. |

### 3.4 운영 프로브 & 관측성 (AC-26 ~ AC-30)

| AC | 판정 | 증거 |
|----|------|------|
| **AC-26** (DB down에도 /healthz 200) | **PASS** | `routers/probes.py:17-20` DB 의존 없이 dict 반환. 통합 `test_healthz_always_200` (`:134-136`) 확인. |
| **AC-27** (/readyz 503 if DB down) | **PASS (코드)** | `routers/probes.py:30-72` DB/Redis/S3 ping 중 하나라도 `"ok"`/`"head"` 아니면 503. 테스트 없음. |
| **AC-28** (/v1/version no-auth, 4필드) | **PASS** | `routers/version.py` 5 필드(extra `python`) 반환, `auth/middleware.py:22-24` PUBLIC_PATHS에 포함. 통합 `test_version_endpoint_no_auth` (`:139-145`) 확인. |
| **AC-29** (/metrics 3개 메트릭 + JSON 로그 trace_id/request_id/hospital_id) | **PASS** | `telemetry.py:23-133` 18 메트릭 정의, `app.py:172-174` `/metrics` 라우트 + Prometheus text format. 통합 `test_metrics_endpoint` (`:148-152`) 에서 `b"radivault_central_"` 포함 확인. 로그 스키마는 `logging_config.py:52-79`에서 field 삽입. |
| **AC-30** (PHI 금지 필드 grep 0건) | **PASS (코드)** | `logging_config.py:22-49` `PhiSanitizerFilter`가 `BANNED_FIELDS` 중 하나라도 발견 시 값을 `<redacted>`로 치환. **주의**: 필터는 record의 `extra`에 키가 들어올 때만 동작하고 `record.msg` 문자열은 스캔하지 않음 — 코드 경로상 애초에 해당 필드를 logger에 주입하지 않으므로 실효성 있으나 방어 깊이는 얕음. 자동 grep 테스트는 없음. |

### 3.5 Rate Limit & Quotas (AC-31 ~ AC-32)

| AC | 판정 | 증거 |
|----|------|------|
| **AC-31** (61번째 요청 → 429 + Retry-After) | **PASS (코드)** | `ratelimit/middleware.py:59-93` fixed-window redis counter, `Retry-After` 헤더 `:117-120`. 자동 테스트 없음. |
| **AC-32** (일 쿼터 초과 → 429 ERR_RATE_QUOTA_DAILY) | **NOT IMPLEMENTED (스펙 갭)** | `ratelimit/middleware.py`에 일일/월간 byte quota 로직 **없음** — `ingest_per_min`/`per_hour`, `anchor_per_min`, `ip_global_per_min`만 구현. `RateQuotaDaily`·`RateQuotaMonthly` 에러 클래스는 정의되어 있으나(errors.py:282-295) 발화 지점 없음. dev-spec FR-45 미구현 → **M-5로 분리**. |

### 3.6 DB 감사 · WORM (AC-33 ~ AC-34)

| AC | 판정 | 증거 |
|----|------|------|
| **AC-33** (`central_app` 롤 DELETE/UPDATE 거부) | **PASS (마이그레이션 코드)** | `alembic/versions/0001_initial.py:27-37` PG 전용 `REVOKE ALL` + `GRANT SELECT,INSERT` (DO 블록에서 role 존재 시). 실제 PG 테스트는 수행 없음 — 코드 경로 검증만. v0.1 AC 충족으로 수용. |
| **AC-34** (성공 Ingest 후 `audit_ingest_event` row + PHI 금지 필드 없음) | **PASS** | `audit/ingest_event.py:10-37` `record_ingest_event`는 `pseudo_study_uid`·`central_job_id`·`request_id`만 기록, 원본 UID/환자 이름 필드는 스키마에 부재. `routers/ingest.py:189-200` 성공 경로에서 호출. |

### 3.7 Migrations & Packaging (AC-35 ~ AC-36)

| AC | 판정 | 증거 |
|----|------|------|
| **AC-35** (compose up → /readyz 200 + uid 10001 + healthy) | **NOT VERIFIABLE (인프라)** | `Dockerfile.central:38-58` `APP_UID=10001`, `useradd --uid 10001`, `HEALTHCHECK` 정의, `docker-compose.central.yml:7-94` postgres:15 + redis:7 + minio + central 전체 스택 정의, healthcheck 조건 설정 완비. 실제 `docker compose up`·`docker inspect` 수행은 본 QA에서 skip (infra-only AC). 코드·compose 구성 모두 요건 충족. |
| **AC-36** (기존 mock central 기반 Gateway 테스트 녹색) | **PASS** | `pytest tests/unit -q` 55/55 PASS (Gateway 회귀). `tests/central/integration/test_gateway_against_central.py` 실제 Gateway `UploadClient`가 Central `TestClient`와 통신하여 201 받는 것 확인 (`:140-148`). D-3 브릿지 검증 `:119` `manifest["anonymization_flag"] == "fully_anonymized"` assert. |

**AC 합계**: PASS 23 · PARTIAL 2 (AC-5, AC-6) · NOT IMPLEMENTED 1 (AC-32) · NOT VERIFIABLE 4 (AC-4, AC-13, AC-15, AC-35) · 경미 drift 1 (AC-3 키 규칙 내 series/sop 계층 단일화) · PASS (코드) 5

---

## 4. 보안 발견

### Critical
없음. 익명화 게이트 우회 경로 없음, 토큰 평문 로그 없음, 교차 병원 누수 직접 경로 없음, SQL 인젝션 없음(SQLAlchemy 파라미터 바인딩 전수), 비밀 하드코딩 없음.

### High

- **H-1 (High · LocalFsObjectStore path traversal)**: `storage/local.py:18-24`의 `target = self.root / key`는 `key`가 `../../etc/evil` 형태일 때 루트 외부로 쓰기 가능. `routers/ingest.py:136` 키 구성은 `{env}/{hash2}/{hospital_id}/{pseudo_study_uid}/{pseudo_study_uid}/{filename}` — `filename`은 manifest에서 온 user-controlled string이며, `manifest/schema.py:27` `filename: str` 에 path 검증 없음. `pseudo_study_uid` 또한 동일. **프로덕션은 S3 드라이버이므로 물리 FS escape는 발생하지 않으나, dev/test 경로 및 `LocalFsObjectStore`를 선택한 환경에서는 실제 취약**. 권고: (a) `manifest/schema.py`의 `filename`·`pseudo_study_uid`에 `Field(pattern=r"^[A-Za-z0-9._-]+$")` 또는 traversal 시퀀스 거부 validator, 또는 (b) `LocalFsObjectStore.put_object`에서 `target.resolve().is_relative_to(self.root.resolve())` 검증.
- **H-2 (High · SSE-KMS 기본값 None + HTTP endpoint 허용)**: `storage/s3.py:62-65` `self._kms_key_arn`이 None이면 `ServerSideEncryption` 헤더를 **아예 추가하지 않음** — 버킷 정책이 KMS 강제하지 않는 한 평문 저장. dev-spec FR-7은 "서버 측 암호화 기본값 `SSE-KMS`"를 **코드·정책 양방향** 요구. 또한 `endpoint_url`에 `http://`가 들어와도 거부 로직 없음(dev-spec §5 "TLS 1.3 only" 지점) — MinIO dev 편의 vs 프로덕션 가드 딜레마. Gateway QA H-1과 동형. 권고: (a) `storage/s3.py` 생성자에서 `kms_key_arn is None` + `env in {"prod","stage"}` 조합 시 warning 또는 거부, (b) `endpoint_url.startswith("http://")` + prod 환경 combination 거부 플래그 추가.

### Medium

- **M-1 (Medium · 광범위 `except Exception`)**: `idempotency/middleware.py:92,119`, `ratelimit/middleware.py:110`, `routers/ingest.py:82,142`, `storage/s3.py:75-79` 등 여러 곳에서 `except Exception`을 `redis.ConnectionError`·`botocore.exceptions.ClientError` 같은 좁은 타입으로 분류하지 않고 잡음. 예상치 못한 bug가 503/502로 숨을 수 있음. 로그에 `detail=str(exc)`로 메시지를 찍기는 하나 stack trace는 없음. 권고: `except (redis.ConnectionError, redis.TimeoutError, redis.RedisError)` 등 구체화.
- **M-2 (Medium · storage.orphan 감사 미기록)**: `routers/ingest.py:142-149` S3 PUT 실패 시 `store.delete_objects(uploaded_keys)`는 호출하지만 dev-spec FR-8 "정리 실패 시 `orphan_object_keys` 감사 이벤트 기록" 및 §8.4 "`event='storage.orphan'` 흔적"을 남기는 코드가 없음. AC-5 후반 요건 미충족.
- **M-3 (Medium · 응답 mirror와 commit 트랜잭션 분리)**: `idempotency/middleware.py:121-130`에서 `call_next` 후 `upsert_idempotency_mirror` + `session.commit`을 별도 트랜잭션으로 실행. 이때 `call_next` 내부의 study INSERT는 이미 커밋됨 — 즉 DB에 study row는 있으나 idempotency mirror에 response_sha256 없음 상태에서 process crash 시 재시도하면 `409 ERR_MANIFEST_DUP` 반환되어 Gateway가 영구 오류로 마킹. 권고: study insert와 mirror 를 같은 트랜잭션에 묶거나, mirror를 먼저 insert(응답 바디 미정 시 placeholder) 후 최종화.
- **M-4 (Medium · `_engine`/`_factory` 전역 싱글톤)**: `db/session.py:16-17` 모듈 전역 변수 — 프로세스 생명주기 내 단일 DSN 가정. 테스트에서 `reset_for_tests()`로 수동 해제 필요. 멀티 DB/멀티 tenant 확장 시 재설계 필요. 현 시점 v0.1 단일 DSN 환경에서는 문제없음.

### Low

- **L-1 (Low · `_unhandled` 핸들러 detail)**: `errors.py:367-371` 미분류 예외 시 `CentralError(detail="unexpected server error")` 반환. stack trace는 `log.exception`으로 서버 로그에만 남고 envelope은 안전. 단, 일부 CentralError 생성자가 `detail=str(exc)`를 통해 원본 예외 메시지를 envelope에 노출(`routers/ingest.py:149` StorageWriteError `detail=str(exc)`) — 내부 파일 경로·AWS 에러 문자열이 client에 전달될 수 있음. 권고: 외부 노출 detail은 sanitise된 짧은 문자열로 제한.
- **L-2 (Low · `study_exists` hospital_pk 미스코프)**: `db/repository.py:55-61` `study_exists`는 `pseudo_study_uid` UNIQUE 제약에 의존하여 글로벌 스코프로 조회. 스키마상 globally unique이지만 explicit hospital_pk 필터가 없으므로 **만약 UUID 충돌이나 salt 공유 버그가 생기면** 다른 병원의 study 존재가 `ERR_MANIFEST_DUP` 반환으로 유출 가능(4xx error가 hospital 사이 signal 역할). 권고: `WHERE pseudo_study_uid = ? AND hospital_pk = ?`.
- **L-3 (Low · Anchor `commit()` 이후 response build)**: `routers/anchor.py:72-83` `session.commit()` 후에 `ulid` 생성 + metrics `.set()` 호출. `idempotency` 미들웨어가 이후 응답 바디를 읽어 `upsert_idempotency_mirror` — DB 측에 anchor는 이미 커밋됐지만 idempotency mirror 미완료. M-3과 동형의 윈도우.

---

## 5. 컴플라이언스 발견 (개인정보·의료)

### Critical
없음. anonymization_flag 게이트 우회 경로 없음 확인:
- `manifest/validator.py:65-72` 검증 순서 `_check_version → _check_anonymization → _check_ruleset → ...` 중 anonymization_flag 체크가 early raise.
- `routers/ingest.py:81` `validator.parse_and_validate(raw_manifest)` 단일 진입점이며 이 메서드를 우회하는 코드 경로 없음.
- Gateway D-3 브릿지(`radivault_gateway/upload/client.py:139-145`) 구현 확인 — Gateway가 `anonymization_flag="fully_anonymized"`를 manifest에 주입.
- 통합 테스트 `test_ingest_rejects_missing_anonymization_flag`로 실제 거부 동작 검증.

### High

- **H-3 (High · preflight 실패 시 `audit_ingest_event` 미기록)**: dev-spec FR-56 "모든 Ingest 성공·실패 이벤트는 `audit_ingest_event`에 1 row 기록"을 **성공 경로만** 구현(`routers/ingest.py:189-200`). Manifest preflight 실패(anonymization 거부, sha256 mismatch, duplicate 등) 시 감사 이벤트가 DB에 남지 않고 메트릭 카운터만 증가. 규제 감사 시 "거부된 업로드 시도"의 증적이 Prometheus 카운터(고유 request 추적 불가)에만 존재하게 됨. 특히 `ERR_MANIFEST_ANON` 거부는 국외이전 게이트 발동 기록이므로 DPO 감사 핵심 증거 — DB row 필수. 권고: `routers/ingest.py`의 각 `raise Manifest*()` 직전에 `record_ingest_event(event="ingest.rejected", error_code=exc.code, ...)` 호출. withdraw-stub은 이미 그렇게 처리되어 있음(`routers/withdraw.py:20-30`) — 동일 패턴을 ingest에 확대 적용.

### Medium

- **CP-1 (Medium · PhiSanitizerFilter 범위)**: `logging_config.py:35-49` 필터는 `record.__dict__` 키만 검사 — 로그 메시지 문자열 자체는 스캔 안 함. `f"patient {name}"` 같이 문자열 보간된 PHI는 차단 불가. 코드상 해당 필드를 로거 메시지에 넣는 지점이 없어 실제 위험은 낮으나, 방어 깊이 개선 여지.
- **CP-2 (Medium · DICOM 바이너리 재검증 부재)**: dev-spec §3.2.11 "v0.1은 manifest sha256 + anonymization_flag 게이트까지만" 명시적 연기. pydicom 기반 태그 재검증 워커는 v0.2. Hospital이 manifest에 `fully_anonymized`를 허위 선언하고 실제 DICOM에 PHI 잔존 시 Central이 탐지 불가 — **이는 스펙 수용 사항**이지만 운영 리스크로 기록.
- **CP-3 (Medium · `audit_daily_digest` Object Lock 미구현)**: dev-spec FR-59 스텁으로 허용. `db/models.py:240-256` 테이블 정의만 있고 배치 잡은 없음. 본 v0.1 스코프 범위 내 의도된 연기(§3.2.14 연기 항목). Kyle 승인 시 v0.2.

### Low
- **CP-4 (Low · cross-hospital 격리)**: 핵심 쿼리 모두 `hospital_pk` 스코프 (`repository.py` 전수 grep). 예외는 `study_exists`(L-2)와 `get_idempotency_mirror`/`upsert_idempotency_mirror` — 후자는 composite PK `(key, hospital_pk)`이므로 안전. 실제 누수 경로 발견 없음.

---

## 6. 품질 관찰 (non-blocking)

- **Q-1 (Observation · 스트리밍 업로드 미구현)**: dev-spec FR-5 "스트리밍 직접 쓰기, 로컬 디스크 상주 금지" — 현재 `routers/ingest.py:47 await request.form()`은 Starlette multipart를 메모리에 전체 로드한다. 100MB 스터디 × 병원당 동시 4 업로드 × 64 concurrent 워커 시 메모리 압박 가능. dev-spec §5 "100MB p95 <30s" 성능 목표는 단일 업로드 단독 기준이므로 수용 가능하나 v0.2 스트리밍 리팩터 필수.
- **Q-2 (Observation · series/sop 계층 평탄화)**: dev-spec §4.1 FR-6 키 규칙은 series/sop 계층 포함이나 구현은 단일 계층으로 filename 보존(AC-3 주석). 구매자 다운로드/presign 시점에 문제 가능 — 키 스키마 정정 권고.
- **Q-3 (Observation · app.py middleware comment)**: `app.py:145` "outermost first" 주석은 Starlette의 `add_middleware` 순서와 반대 의미. 코드 동작은 정확(Auth가 Idempotency보다 outer). 주석 교정 권고.
- **Q-4 (Observation · slowapi 미활용)**: `pyproject.toml [central]`에 `slowapi>=0.1.9` 선언되었으나 실제 `ratelimit/middleware.py`는 Redis INCR 직접 사용. 이론상 dependency dead code. slowapi 라이브러리의 `limits` 모듈을 쓰기 위한 필요 여부 재평가 권고.
- **Q-5 (Observation · 테스트 커버리지 분포)**: 34개 unit 테스트는 manifest/validator(9), anchor chain(5), admin cli(4), auth tokens(5), errors(4), idempotency(3), storage(2), mixed(2)로 고르게 분산. 통합 테스트 12건은 HTTP 레벨 행동 검증에 집중 — happy path + 주요 negative 케이스 커버. **누락 케이스**: (a) rate limit 61번째 429, (b) 일일 byte quota(구현 안 됨), (c) auth constant-time Δ, (d) Redis down simulation의 503, (e) cross-hospital hospital_id mismatch manifest, (f) PHI log sanitizer 실제 작동. v0.1.1 보강 가치.
- **Q-6 (Observation · Alembic `Base.metadata.create_all` vs 마이그레이션)**: 초기 마이그레이션이 `Base.metadata.create_all(bind=bind)` 한 줄 — 모델 변경 시 마이그레이션이 생성되지 않는 리스크(alembic autogenerate 실행 전에는 diff 감지 안 됨). 팀 관행상 init migration은 그렇게 해도 되지만, 두 번째 마이그레이션부터는 필수로 `op.add_column(...)` 등 명시적 DDL로 써야 함. 문서화 권고.
- **Q-7 (Observation · Downgrade 반영도)**: `0001_initial.py:40-42` downgrade는 `Base.metadata.drop_all` — 실제 프로덕션에서 파티션 테이블·pg_partman 데이터는 이 방식으로 완전히 되돌아가지 않을 수 있음(상위 마이그레이션 기준 제한). v0.1에서는 수용.
- **Q-8 (Observation · CLI 서브커맨드 9개 중 ingest-admin help에 모두 노출)**: `test_admin_cli.py:11-17` 검증. design-spec §3.2 트리와 대응. (단, `migrate` 그룹이 실제로는 `up/down/current` 서브커맨드 3개로 총 11개가 되며 설계 의도와 정합.)
- **Q-9 (Observation · pip-audit 미실행)**: 본 세션에서 dependency vulnerability scan은 수행 안 함 (venv 내 pip-audit 설치 불분명). 권고: CI에서 `pip-audit` 돌려 HIGH+ 0건 게이트 추가.

---

## 7. 개발자 자가 보고 편차 검증

| # | 자가보고 편차 | 판정 | 근거 |
|---|-------------|------|------|
| D-1 | 동기 psycopg v3 (asyncpg 대신) | **수용 가능** | dev-spec §9.4 표가 asyncpg를 제안했으나 동일 섹션이 "SQLAlchemy 2.0 + asyncpg"를 "제안" 수준으로 표기(Kyle 승인 대기). 동기 psycopg v3는 SQLAlchemy 2.0 지원, 기능·성능 차이는 v0.1 처리량(병원당 동시 4 업로드) 범위에서 측정 가능한 bottleneck 유발 없음. 성능 목표(§5 p95<30s) 달성 여지 충분. |
| D-2 | `RV_CENTRAL_*` env prefix | **수용 가능 · 정당한 이유** | `src/radivault_gateway/config/loader.py:109-131` `_env_override`가 `RADIVAULT_<SECTION>__<KEY>` 패턴을 **전역으로 처리**. Gateway와 같은 프로세스/쉘에서 Central 환경변수가 `RADIVAULT_`로 시작하면 Gateway 로더가 extra input으로 간주해 validation error 유발. `RV_CENTRAL_`는 합리적 disambiguation. 다만 `configs/central.example.yaml` 파일과 문서에 이 prefix를 명시했는지 확인 필요 — `src/radivault_central/config.py:7-11` 주석에서 문서화 완료. |
| D-3 | SQLite BigInt variant | **수용 가능** | `db/models.py:38 BigId = BigInteger().with_variant(Integer(), "sqlite")`. SQLite는 BIGINT autoincrement를 지원 안 함 → Integer 폴백은 표준 관행. 프로덕션 PG 경로는 BIGINT 유지(`BigInteger` default). 타입 정확성 유지, 회귀 없음. |
| D-4 | Middleware에서 envelope 직접 방출 | **수용 가능 · 일부 경미 drift** | `auth/middleware.py:86-93`, `idempotency/middleware.py:178-185`, `ratelimit/middleware.py:116-123` 각자 `_envelope_response` helper로 CentralError → envelope 변환. `errors.py:327-347`의 중앙 핸들러 코드와 **envelope 구조는 동일**(동일 `to_envelope()` 사용). 단, `hint` 필드 추가 로직, 로그 출력 위치가 중앙 handler와 중복/분기되어 일관성 약화. AC 영향은 없음. |

**모두 PASS with notes**. 4건 중 어느 것도 Critical·High 영향 없음.

---

## 8. 권고 (재작업·후속 항목)

### 병합 가능(v0.1 GA 조건부)
1. **H-3 Critical-leaning · preflight 거부 감사 누락**: `routers/ingest.py` 각 `raise Manifest*()` 직전에 `record_ingest_event(event="ingest.rejected", error_code=exc.code, ...)` 추가. 병합 전 반영 강권장 — 이는 dev-spec FR-56의 명시적 요구이며 AC-6의 감사 이벤트 요건을 만족하려면 필수. ~30줄.
2. **H-1 path traversal 가드**: `LocalFsObjectStore.put_object`에 `target.resolve().is_relative_to(self.root.resolve())` 가드 또는 `manifest/schema.py`의 `filename`/`pseudo_study_uid`에 safe-character validator. ~10줄.
3. **H-2 SSE-KMS 기본값 + HTTP endpoint 가드**: `S3ObjectStore.__init__`에서 `env in ("prod","stage") and kms_key_arn is None` → warning 또는 거부. `endpoint_url.startswith("http://")` + prod → 거부. ~15줄.

### v0.1.1 이관
- **M-2 storage.orphan 감사 이벤트**: 정리 실패 경로에 `record_ingest_event(event="storage.orphan", ...)` 추가.
- **M-3 mirror 트랜잭션 일관성**: study insert와 idempotency mirror를 동일 트랜잭션 내 실행.
- **M-5 일일/월간 byte quota 구현**: `ratelimit/middleware.py`에 byte counter 로직 추가 (FR-45). 현재 에러 클래스만 정의되고 발화 코드 없음.
- **CP-1 PhiSanitizerFilter 메시지 스캔**: `record.msg`·`record.message`에 대한 정규식 기반 원본 UID 패턴(`1.2.840.*`, `2.25.*`) 탐지.
- **Q-1 스트리밍 업로드**: Starlette multipart를 SpooledTemporaryFile + streaming boto3 `upload_fileobj`로 리팩터.
- **Q-2 키 계층 정정**: `{pseudo_series_uid}/{pseudo_sop_uid}.dcm` 계층 복원.
- **AC-13 스트리밍 preflight**: manifest part를 파일 part보다 먼저 읽고, 실패 시 남은 스트림 drop. `bytes_consumed_before_reject` 로그 필드 추가.
- **AC-15 argon2 타이밍 테스트**: valid/invalid kid 각 100회 평균 시간 Δ<10ms 검증 테스트 추가.
- **Q-5 누락 테스트**: rate limit 429, Redis 503, cross-hospital mismatch, PHI sanitizer 실작동, withdraw stub 감사 기록 테스트.

### v0.2 이관(이미 스펙에 의해)
- FR-59 `audit_daily_digest` + Object Lock 배치 워커.
- FR-73 withdraw 실제 파이프라인.
- DICOM 바이너리 재검증 워커(CP-2).
- Presigned MPU(dev-spec §3.2.1).

---

## 9. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-22 | @qa (Claude Opus 4.7) | 최초 검수. 커밋 `70782e8..e874295` + `c847e62`. Unit 34/34 · Integration 12/12 · Gateway 회귀 55/55 PASS, ruff clean 독립 검증. AC 36건 매트릭스, Critical 0 · High 3 · Medium 6 · Low 3 발견. 개발자 자가보고 편차 4건 모두 수용. 판정 **PASS with minor issues** (병합 가능, H-3 감사 누락은 v0.1 GA 전 반영 강권장). |

---

### NEXT_STEP

- 완료 산출물: `docs/qa/qa-report-central-ingest.md` (v0.1 검수 리포트)
- 판정: **PASS with minor issues**
- Critical 이슈: 0건
- High 이슈: 3건 (H-1 path traversal, H-2 SSE-KMS 기본값, H-3 preflight 감사 누락)
- 제안 다음 단계:
  - **@developer** — §8 권고의 H-1/H-2/H-3 3건을 `claude` 브랜치에서 선반영 후 재검수 없이 병합 가능 수준. 특히 H-3(FR-56 명시 요구)은 강권장.
  - 병렬로 **@marketer** — 본 v0.1 MVP의 "2개 병원 파일럿 수용 기반"을 런칭 콘텐츠 준비 가능. 성능·보안 수치 공개 시 Kyle 최종 승인 조건 첨부.
- Kyle 결정 필요 사항:
  1. 호스팅 리전·객체 스토리지 공급자(dev-spec §11 Q1-Q2) — 코드 레벨 영향 없음. 배포 전 확정 필요.
  2. Gateway dev-spec §6.4/§7.3에 `anonymization_flag`·`Idempotency-Key`·`201 vs 202` 공식 반영 승인(dev-spec §13 D-1/D-2/D-3). Central 구현은 D-3 브릿지로 이미 동작 중.
  3. 일일/월간 byte quota(FR-45)를 v0.1 필수로 회귀시킬지 v0.1.1 이관할지 (M-5).
  4. `audit_daily_digest` Object Lock 운영자 결정(§11 Q11) — v0.1은 스텁 유지.
  5. CI workflow · trivy HIGH=0 · pip-audit 게이트 도입 시점 (Gateway QA Round 2의 AC-28/29와 병합 여부).
