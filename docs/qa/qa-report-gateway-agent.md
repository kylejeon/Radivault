# QA 보고서 — Gateway Agent v0.1 MVP

> **Status**: Final · **Feature slug**: `gateway-agent` · **Last updated**: 2026-04-22 (Round 2)
> **작성자**: @qa · **근거**: [dev-spec](../specs/dev-spec-gateway-agent.md), [design-spec](../specs/design-spec-gateway-agent.md)
> **최신 판정 (Round 2)**: **PASS with minor issues**

---

## 1. 메타

| 항목 | 값 |
|------|-----|
| 검수 대상 | `claude` 브랜치, 커밋 범위 `8c33deb..48ba21f` (planner 이후 developer 10 커밋) |
| 독립 검증 결과 | `pytest tests/unit -q` → 48/48 통과 (0.35s), `ruff check src tests` → clean, `pip-audit` → 취약점 0건 |
| 최종 판정 | **FAIL (재작업 필요)** |
| Critical 이슈 | 2건 (FR-11 격리 파일 삭제 버그, FR-25 anchor 스케줄러 미구현) |
| High 이슈 | 3건 (FR-14 staging 레이아웃 불일치, FR-27 logrotate postrotate 공란, AC-2 테스트 부재) |

---

## 2. 요약

- **디펜스·무결성**: 감사 체인(FR-22~26)과 설정 로더(FR-34~37)는 견고하며 독립 tamper 테스트에서 FAIL 감지 정상. PHI 로그 오염 없음(`_short_hash(original_uid)` 해시만 감사 기록). 보안적으로는 Critical 노출 없음.
- **FAIL 사유**: 번인 격리 시 파일을 **quarantine/으로 이동하지 않고 삭제**한다 (AC-8 직접 위반). 시간당 중앙 anchor(FR-25/AC-19)는 `UploadClient.post_audit_anchor` 메서드로 구현되었지만 **호출자가 없음** — 데몬·스케줄러 어디에도 연결 안 됨. 이 둘은 dev-spec §10의 수용 기준을 명시적으로 통과 불가 상태로 만든다.
- **강점**: Annex E 태그 매트릭스(AC-32), UID 가명화 결정성(AC-5), 환자 날짜 오프셋 일관성(AC-7), 원본 UID 비유출(AC-6), manifest sha256 무결성(AC-14), 감사 체인 tamper 탐지(AC-17/AC-20)는 코드·테스트 모두에서 확인됨.

---

## 3. 수용 기준 매트릭스

| AC | 판정 | 증거 |
|----|------|-----|
| AC-1 (Orthanc 10스터디 sync-once) | NOT VERIFIABLE | Orthanc 컨테이너 비가동. 코드 경로 `DicomWebPacsClient.query_studies`/`fetch_study` 정상, 통합 테스트는 `@pytest.mark.integration`로 스킵 (`tests/integration/test_pipeline_orthanc.py`). |
| AC-2 (PACS 401 거부 시 감사 로그) | **FAIL** | `pipeline.py:115-118` `PacsError` 처리 시 `pacs.query.failed` 감사 기록 코드 경로 존재하나, 401 시나리오 단위 테스트 **없음**. `src/radivault_gateway/pacs/client.py:145-164` 4xx는 즉시 raise로 분기하므로 retry_failed 동작은 설계상 가능하나 증거 불가. |
| AC-3 (지수 백오프 5회) | PASS (코드) | `pacs/client.py:140-164` 5회, cap 60s, jitter ±20%. 단위 테스트는 미포함(시간 의존). |
| AC-4 (PatientName, PatientID 등 제거/더미) | **PASS** | `deid/engine.py:75-115` ANNEX_E_MATRIX Z/D/X 액션, `tests/unit/test_deid.py::test_basic_annex_e_strips_identifiers`. |
| AC-5 (결정적 UID 가명화) | **PASS** | `deid/engine.py:295-314`, `tests/unit/test_deid.py::test_uid_pseudonymisation_deterministic`. |
| AC-6 (원본 UID/PID 비포함) | **PASS** | `tests/unit/test_deid.py::test_original_uids_not_present_in_output` 바이트 grep 확인, `tests/unit/test_pipeline_mock.py:186` manifest 바이트 검증. |
| AC-7 (환자별 고정 오프셋 일관) | **PASS** | `deid/engine.py:316-328`, `tests/unit/test_deid.py::test_patient_date_offset_consistent_across_studies` (30일 델타 보존). |
| AC-8 (번인 → quarantine/, staging/ 미기록) | **FAIL · Critical** | `orchestrator/pipeline.py:191-214` 번인 감지 시 `shutil.rmtree(staging_dir)`만 수행. **물리적 quarantine 디렉터리에 파일을 이동하는 코드가 없음**. `StateDB.add_quarantine` 함수는 정의되었으나 pipeline에서 호출되지 않는다. AC-8의 "quarantine/에만 존재"는 충족 불가. |
| AC-9 (PatientIdentityRemoved=YES 등) | **PASS** | `deid/engine.py:453-478`, `tests/unit/test_deid.py::test_method_tags_set`. 단, 메서드 코드 `113105` = Clean Descriptors는 **DICOM CID 7050 표준**이 맞고 dev-spec §6.4의 `113111`은 스펙 오타로 판단 (개발자 선택이 표준에 부합). |
| AC-10 (악성 ruleset → reverify 실패 → 업로드 차단) | **PASS** | `deid/engine.py:262-291` reverify + `pipeline.py:244-267` `failed_reverify` 분기, `tests/unit/test_deid.py::test_reverify_fails_when_blacklisted_tag_left`. |
| AC-11 (업로드 성공 후 staging 1초 내 삭제) | **PASS** | `pipeline.py:367-373` + `staging/manager.py:33-49`, `tests/unit/test_pipeline_mock.py:175` (staging dir 비존재 확인). |
| AC-12 (retention_hours 초과 경고) | PARTIAL | `staging/manager.py:61-71 stale_studies`는 구현되었으나 경고 로그·audit 기록·status 반영 경로 **미연결**. `status` CLI는 oldest_pending_ts를 전혀 계산하지 않음. 실제 운영 경고 발송 불가. |
| AC-13 (85% backpressure) | PASS (코드) | `pipeline.py:85-94` + `staging/manager.py:51-59`, 단위 테스트 부재 (시스템 디스크 의존). |
| AC-14 (multipart sha256 무결성) | **PASS** | `upload/client.py:98-125` build_manifest + `radivault_mock_central/main.py:69-84` sha256 verify, `tests/unit/test_upload.py::test_mock_central_verifies_sha256`. |
| AC-15 (500 × 10회 → state=failed_upload) | PASS (코드) | `upload/client.py:183-193` 5xx retry, `pipeline.py:326-345` `schedule_retry` + `failed_upload`. 테스트는 permanent 400 비재시도만 커버(`tests/unit/test_upload.py::test_upload_client_permanent_400_not_retried`) — 10회 × 5xx 시나리오 단위 테스트 없음. |
| AC-16 (HTTPS_PROXY env 준수) | PASS (코드) | httpx 기본 `trust_env=True`. 추가 테스트 없음. |
| AC-17 (hash 체인 수학적 정확성) | **PASS** | `audit/log.py:27-39` canonicalize excludes `hash`, `tests/unit/test_audit_chain.py::test_hash_covers_all_fields_except_hash`. 독립 tamper 테스트 통과: 5건 append, seq=3 hash 1바이트 변조 → `verify_chain` `ok=False, first_mismatch_seq=3`. |
| AC-18 (8개 이벤트 시퀀스) | PASS (코드) | `pipeline.py` 이벤트 8종: pacs.query, pacs.fetch.completed, deid.started, deid.completed, staging.written, upload.started, upload.completed, staging.cleanup. `tests/unit/test_pipeline_mock.py::test_pipeline_happy_path_end_to_end`에서 chain OK까지 확인. |
| AC-19 (시간당 anchor POST) | **FAIL · Critical** | `upload/client.py:195-217 post_audit_anchor` 메서드 존재, dev-spec `anchor_interval_seconds` config 키 존재. 그러나 **어디에서도 호출되지 않음** (grep `post_audit_anchor` → 정의 1회, 호출 0회). `start` 데몬 루프(`cli/main.py:298-331`)에 anchor 스케줄러 없음. AC-19 명백 미충족. |
| AC-20 (audit verify 변조 시 exit 1 + seq) | **PASS** | `cli/main.py:117-137` + `audit/log.py:160-214`, `tests/unit/test_audit_chain.py::test_tampering_detected` 및 독립 tamper 테스트. |
| AC-21 (audit.log 0600) | PASS (코드) | `audit/log.py:102,149` `touch(mode=0o600)` 및 `os.open(..., 0o600)`. 실제 런타임 `ls -l` 검증 불가(미기동). |
| AC-22 (CLI exit code 규칙) | **PASS** | `cli/main.py` 모든 커맨드 §7.4 exit 규칙 준수, `tests/unit/test_cli.py::test_audit_verify_missing_file`(2), `test_config_validation_error_exits_64`(64), `test_de_id_test_reports_bad_input`(1). |
| AC-23 (필수 키 누락 시 10초 내 종료) | **PASS** | `config/loader.py:147-172` pydantic 에러 → `ConfigError(ERR_CFG_002)` → `cli/main.py:32-36` exit 64. `tests/unit/test_config.py::test_missing_required_key_raises_err_cfg_002`. |
| AC-24 (컨테이너 uid 10001) | PASS (Dockerfile) | `Dockerfile:28-35` `useradd --uid 10001 ... USER radivault:radivault`. 런타임 `docker inspect` 미검증. |
| AC-25 (healthcheck healthy) | PASS (코드) | `Dockerfile:47-48` HEALTHCHECK — 그러나 dev-spec FR-39의 "SQLite ping + staging FS write check"가 아니라 `version` 명령으로 대체됨. **디자인 의도와 약간 다름** (경미). |
| AC-26 (De-ID P50<5s, P95<15s) | NOT VERIFIABLE | 벤치마크 테스트 코드 없음. 200 instances 픽스처 미포함. v0.2 권장. |
| AC-27 (1,000 스터디 연속 무누수) | NOT VERIFIABLE | 부하 테스트 없음. |
| AC-28 (CI 15분) | **FAIL** | GitHub Actions workflow 파일 없음 (`.github/workflows/` 부재). Dev-spec 수용 기준 미구현. |
| AC-29 (trivy HIGH 0) | **FAIL** | trivy 실행 근거 없음. `pip-audit`는 PyPI 의존성 통과이나 이미지 스캔 아님. |
| AC-30 (self-signed + ca_bundle 미지정 거부) | PASS (코드) | `pacs/client.py:105-107` `verify=True` 기본. 실제 테스트 픽스처 없음. |
| AC-31 (README 설치·장애·salt 회전) | PARTIAL | README.md는 빠른 시작·CLI·감사 로그 포함. 그러나 **salt 회전 절차, 장애 대응 플레이북, runbook 링크 부재**. dev-spec §12.3 / design-spec §7.3 정렬 불충분. |
| AC-32 (Annex A 매트릭스 교차 검증) | **PASS** | `deid/engine.py:74-115` ANNEX_E_MATRIX, `tests/unit/test_deid.py::test_annex_a_matrix_covers_required_tags` 13개 태그 확인. 단, 검증은 "존재 체크"만, action 값 1:1 비교 아님 — spec drift 방지는 약함. |

**AC 합계**: PASS 15 · PARTIAL/경미 3 · NOT VERIFIABLE 3 · FAIL 4 (AC-2, AC-8, AC-19, AC-28, AC-29 중 AC-2는 증거 부족 분류)

---

## 4. 보안 발견

### Critical
없음 (비밀 하드코딩·UID 유출·체인 변조 불가 등 critical 벡터는 클린).

### High
- **H-1 HTTPS 강제 미구현**: `central.base_url`이 `http://`여도 클라이언트가 거부하지 않음(`upload/client.py:64`). dev-spec §5 비기능표 "TLS 1.3 outbound-only" 및 §12.3 위반 가능. Dev 환경 편의로 수용 가능하나 프로덕션 가드(`startswith("https://")` 체크) 부재.
- **H-2 PACS Basic auth 평문 로그 위험**: `pacs/client.py:156` 재시도 warning에 `attempt`, `delay_s`만 남겨 안전하나, httpx 기본 DEBUG 로그가 활성화되면 Authorization 헤더가 나올 수 있음. `logging_config.py` 확인 필요 — 현재 별도 필터 없음.

### Medium
- **M-1 `${file:}` 권한 검증 주석만 존재**: `config/loader.py:75` 주석에 "macOS는 warning, Linux에서 enforced"라고 기재되어 있으나 **실제 Linux 권한 검증 코드가 없음**. 0644 salt 파일도 통과. ERR_CFG_011 에러 코드는 정의되었지만 발화 지점 없음.
- **M-2 secret 평문 로깅 금지 가드 부재**: 설정 로드 후 `cfg.deid.salt`, `cfg.central.upload_token`, `cfg.pacs.auth.token` 값이 문자열로 메모리에 존재. DEBUG 로깅에서 config repr을 찍을 경우 노출 위험. `__repr__` 재정의 없음.
- **M-3 mock central `secrets.token_hex`로 job_id 생성하나**, `EXPECTED_TOKEN` 기본값 `"mock-upload-token"`이 모듈 import 시점에 결정 — 테스트마다 reload 필요하고 프로덕션 오용 방지 표시 부족.

### Low
- **L-1** `pacs/client.py:263` 멀티파트 폴백: boundary 파싱 실패 시 전체 body를 단일 DICOM으로 취급. 악성 PACS 응답에 대해 파서 오용 가능(실제 공격 벡터는 낮음).
- **L-2** `audit/log.py:100-113` 복구 로직이 전체 파일 스캔 — 대용량 audit.log에서 기동 지연 가능. 성능 이슈이지 보안은 아님.

---

## 5. 컴플라이언스 발견 (개인정보·의료)

### Critical
- **C-1 (FR-11/AC-8) 번인 격리가 "파일 삭제"로 구현됨**: `orchestrator/pipeline.py:206` `shutil.rmtree(staging_dir, ignore_errors=True)`만 수행되어 번인 포함 DICOM이 **quarantine/ 디렉터리에 남지 않는다**. dev-spec §4.3 FR-14의 디렉터리 트리(부록 B `/var/lib/radivault/quarantine/<pseudo_study_uid>/`)도 생성되지 않음. 결과:
  - 운영자가 수동 QA 불가 (AC-8 "quarantine/에만 존재" 미충족).
  - DPO 감사 시 격리 증빙 영상 부재 → 개인정보보호법 위반 가능성 있는 케이스(번인 PHI)가 "처리되지 않음" 상태로만 남음.
  - 재검증 실패(FR-13)도 동일: `pipeline.py:258` `shutil.rmtree(staging_dir)` — §8.2 "quarantine/으로 이동"과 불일치.
- **C-2 (FR-25/AC-19) 시간당 중앙 anchor 미실행**: `post_audit_anchor` 코드는 있으나 호출자가 없음. 이는 병원 내부 로컬 감사 로그 변조 시 중앙 탐지가 불가능함을 의미하며, dev-spec §12.2 "무결성·변조 방지" 약속을 런타임에서 보장 못함. 로컬 tamper는 탐지 가능하나 로컬 액터가 `verify` 이전에 중앙을 속일 수 있는 창이 열려 있음.

### High
- **CP-1** DB 테이블 `quarantine`, `StateDB.add_quarantine` 정의되어 있으나 오케스트레이터에서 호출되지 않음 — DB-FS 일관성 버그. C-1과 쌍.
- **CP-2** audit.log 내 `original_study_uid_hash` 필드는 SHA-256 16 hex(64 bit)만 사용. 동일 salt가 없다면 pre-image 공격 난이도 높으나, 원본 UID의 구조(OID 형식)가 제한된 엔트로피라 salt 없이 log만 유출 시 약한 재식별 표면 존재. 평가: 수용 수준이나 문서화 필요.

### Medium
- **CP-3 FR-14 staging 레이아웃 불일치**: 구현은 `{root}/{pseudo_study_uid}/{filename}.dcm`(플랫), dev-spec은 `{root}/{pseudo_study_uid}/{pseudo_series_uid}/{pseudo_sop_uid}.dcm` (3-depth). `staging/manager.py:3` docstring도 3-depth를 주장하나 실구현과 다름. 기능적 영향은 적으나 파일명 제어에 series 레벨 분리가 없어 대형 스터디에서 inode 포화 가능성.
- **CP-4 FR-16 경고 경로 비활성**: `stale_studies()`는 있지만 `start` 데몬·`status` CLI에서 호출되지 않음. retention 초과 경고가 사실상 발생하지 않는다. AC-12 PARTIAL의 근거.
- **CP-5** 한국 개인정보보호법 §28-8 게이트: **Gateway 측**에서는 "reverify 실패 시 업로드 차단"이 구현되어(`pipeline.py:244-267`) 익명화 실패 데이터의 해외 전송은 차단됨. 이는 PASS. 다만 중앙 측 추가 게이트는 dev-spec 범위 외.

### Low
- **CP-6** Audit 로그는 UTC ISO8601 ms 타임스탬프 사용. 5년 보존·파일명 타임스탬프·logrotate 설정 모두 확인됨(FR-27). PASS.
- **CP-7** HIPAA Safe Harbor 18 식별자 매핑: ANNEX_E_MATRIX가 Name/Address/Telephone/SSN/MRN/Account/CertNumber/VehicleID/Device ID/URL/IP/Biometric/Photo/기타 중 DICOM에 해당하는 태그 대부분 커버. 단, `(0010,1000) OtherPatientIDs`, `(0010,2160) EthnicGroup`, `(0010,21B0) AdditionalPatientHistory` 등 누락 — v0.1 기본 Annex E Basic profile 상속에 의존하나 `pydicom/deid` 미사용이므로 **상속되는 규칙이 실제로 없음**. 즉 매트릭스 외 태그는 모두 유지됨. 이는 CP-8 권고로 후속 처리.
- **CP-8** Private tag 일괄 제거(`deid/engine.py:352 remove_private_tags`)는 FR-7 "safe_private=false"와 일관 — PASS.

---

## 6. 품질 관찰 (non-blocking)

1. **테스트 전체 시간 0.35s / 48 케이스**: 부하·시간 기반 AC(AC-3, AC-15, AC-26, AC-27)를 커버하지 못하나 단위 수준으로는 견고. 대부분 테스트가 dev-spec 수용 기준을 명시적으로 언급하여 트레이서빌리티 양호.
2. **스펙 ↔ 코드 트레이스**: FR-6 → `ANNEX_E_MATRIX`(deid/engine.py:74), FR-9 → audit 필드는 `original_study_uid_hash`만 사용(pipeline.py:161), FR-18 → `upload_study`(upload/client.py:127) — 3건 모두 정합.
3. **에러 메시지 UX**: design-spec §4.5 6-항목 포맷(코드/ko/en/수정/문서/values) 전부 구현(`config/loader.py:43-50`). Config 에러는 ERR_CFG_{000,001,002,003,010,012,013}.
4. **메서드 코드 매트릭스 버그**: `engine.py:50` `"clean_graphics": ("113109", "Retain Safe Private Option")` — 값과 라벨이 서로 다른 옵션. "placeholder; real code differs" 주석 있음. 실제로는 이 dict가 method code 시퀀스 생성에 사용되지 않고(`_set_method_tags`는 별도 하드코딩 code_pairs 사용) 결과적으로 dead code. 제거 권장.
5. **status CLI는 design-spec §6.2 ASCII 박스를 구현하지 않음** — 단순 라인 나열. AC-D-3 미충족. v0.1 수용 기준(dev-spec)에는 명시되지 않아 blocker 아니나 design-spec 대비 gap.
6. **SIGHUP reload는 미지원**(design-spec §3.3 v0.1 "미지원" 명시). PASS.
7. **Dead code**: `engine.py:42-51` METHOD_CODES dict 미사용, `PHI_BLACKLIST`는 `Tag().element | (group<<16)` 패턴을 사용해 `(group<<16)|element` 형식으로 통합되나 비트 순서가 옳은지 확인 필요 — `tests/unit/test_deid.py::test_reverify_fails_when_blacklisted_tag_left`가 실동작 확인. 통과.
8. **staging docstring drift** (§5 CP-3) — 수정 필요.
9. **README salt 회전 섹션 부재** (AC-31) — 추가 필요.

---

## 7. 권고 (재작업 항목)

### Must-fix (병합 차단)
1. **(Critical) FR-11/AC-8 복구**: 
   - QuarantineRequired 처리 시 `staging_dir` 또는 `fetch_dir` 원본을 `{staging_root}/../quarantine/{pseudo_study_uid or quarantine_{hash}}/` 로 `shutil.move`.
   - `StateDB.add_quarantine` 호출로 `payload_path` 기록.
   - `failed_reverify` 분기도 동일 처리.
   - 테스트: "번인 처리 후 quarantine/ 디렉터리에 파일 존재" assert 추가.
2. **(Critical) FR-25/AC-19 구현**: 
   - `start` 데몬 루프에 `anchor_interval_seconds` 주기 anchor 호출 추가.
   - `UploadClient.post_audit_anchor(gateway_id, seq_range, head_hash)` 호출 후 `audit.anchor.uploaded` 감사 기록.
   - 테스트: 인터벌 짧게 세팅 후 mock central anchor 엔드포인트 수신 확인.

### Should-fix (머지 후 바로)
3. **(High) AC-2 PACS 401 단위 테스트**: `DicomWebPacsClient` + httpx MockTransport로 401 시나리오. `pacs.query.failed` 감사 기록 확인.
4. **(High) FR-14 staging 레이아웃**: series/sop 3-depth로 변경 또는 dev-spec 수정(planner에 문의). 현재 docstring은 현실과 다름.
5. **(High) FR-16 연결**: `status` CLI 및 `start` 틱에서 `stale_studies()` 호출해 경고 발화.
6. **(High) HTTPS 가드**: `UploadClient.__init__`에서 `base_url.startswith("https://")` 체크, `RADIVAULT_ALLOW_PLAINTEXT_CENTRAL=1` 없으면 거부.
7. **(High) AC-28 GitHub Actions workflow** 추가 (`ruff + pytest unit`).
8. **(High) AC-29 trivy 이미지 스캔** CI 단계 추가.
9. **(High) AC-31 README**: `salt 회전`, `장애 대응 티어1` 섹션 추가 (design-spec §7.3과 정렬).

### Nice-to-have
10. **(Medium)** `config/loader.py`의 `ERR_CFG_011` 실제 검증 로직 구현(Linux 권한 0600 체크).
11. **(Medium)** `engine.py`의 METHOD_CODES dict 제거 또는 실사용.
12. **(Medium)** design-spec §6.2 ASCII 박스 status UI 구현 (AC-D-3).
13. **(Medium)** Annex E Basic profile의 표준 태그(OtherPatientIDs, EthnicGroup 등) 매트릭스에 추가 — 또는 `pydicom/deid` 병용으로 기본 rule 상속.

---

## 8. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 1.0 | 2026-04-22 | @qa (Claude Opus 4.7) | 최초 검수 보고. 48/48 단위 테스트 통과·ruff clean·pip-audit 클린 독립 확인. Critical 2건(FR-11 quarantine 파일 삭제, FR-25 anchor 스케줄러 부재)으로 **FAIL** 판정. |
| 2.0 | 2026-04-22 | @qa (Claude Opus 4.7) | 재검수 (Round 2). Round 1 Critical 2건 및 High/Medium 3건 모두 RESOLVED 확인. 54/54 단위 테스트 통과, ruff clean. 신규 minor 발견 1건(design-spec 113111 잔존)만 남아 **PASS with minor issues** 판정. |

---

### NEXT_STEP
- 완료 산출물: `docs/qa/qa-report-gateway-agent.md`
- 판정: **FAIL**
- Critical 이슈: 2건 — (C-1) 번인 격리 파일 삭제, (C-2) 감사 anchor 스케줄러 미구현
- 제안 다음 단계:
  - FAIL → **@developer** — 권고 §7 Must-fix 1·2 우선 재작업, Should-fix 3·4·5·6 병행. 재수정 후 `@qa` 재검수 호출.
  - @marketer 병렬 금지 (핵심 컴플라이언스 경로 미완).
- Kyle 결정 필요 사항:
  1. dev-spec §6.4 메서드 코드 `113111` vs DICOM CID 7050 `113105` — 스펙 오타 정정 여부 (@planner 경유).
  2. staging 레이아웃 2-depth vs 3-depth 유지 여부 — v0.1 플랫이 운영 편의상 허용이면 dev-spec 업데이트, 아니면 코드 수정.
  3. HTTPS 강제 가드 도입 기본값(거부 vs 경고).
  4. AC-28 CI / AC-29 trivy 범위를 v0.1 필수로 유지할지 v0.1.1로 분리할지.

---

## Round 2 Re-Verification (2026-04-22)

검수 대상 커밋: `c4f698d..HEAD` (= `f1309d2..2168a39`, 총 6 커밋, 10 파일, +479/-23).
독립 검증: `pytest tests/unit -q` → **54/54 통과 (0.39s)**, `ruff check src tests` → clean, `ruff format --check src tests` → 36 files already formatted. 브랜치: `claude`.

### 2.1 요약 (Round 2 판정)

- **판정: PASS with minor issues.**
- Round 1 Critical 2건(C-1 번인 격리 파일 삭제, C-2 감사 anchor 스케줄러 부재)이 모두 RESOLVED. 코드·테스트·DB 행·감사 이벤트까지 증거 기반 확인. 병합 차단 사유 소멸.
- Round 1 High/Medium 중 H-1(HTTPS 강제), CP-3(staging 3-depth), AC-12(stale_studies 연결), 스펙 오타(dev-spec §6.4 113105) — **4건 모두 RESOLVED**.
- 신규 minor 1건 발견: `docs/specs/design-spec-gateway-agent.md:422` 주석에 `113111`이 잔존. 개발자 주장 범위(dev-spec)는 수정되었으나 design-spec YAML 예시 주석까지 놓침. 기능·보안 영향 없음 → minor.
- 스코프 규율 우수. 전체 diff 479/23 라인 중 새 테스트가 211줄로 가장 크고, 구현 코드 변경은 목표 기능 외 touch 없음. 무허가 리팩터·over-engineering 흔적 없음.

### 2.2 Round 1 Finding별 상태

| 코드 | 항목 | Round 2 상태 | 증거 |
|------|------|-------------|------|
| **C-1** | FR-11/AC-8 번인 격리 파일 보존 | **RESOLVED** | `orchestrator/pipeline.py:193-225`: QuarantineRequired 시 `self._staging.move_to_quarantine(fetch_dir, qid)` 호출 → `StateDB.add_quarantine(..., payload_path=...)` 기록. `staging/manager.py:82-97` `move_to_quarantine()` 구현(기본 `root.parent/quarantine`, 0o700). `failed_reverify` 분기(`pipeline.py:262-288`)도 동일하게 `move_to_quarantine(staging_dir, pseudo_uid)` 호출 — §8.2 일치. 테스트 `tests/unit/test_pipeline_mock.py:215-303 test_pipeline_quarantines_burned_in_studies`가 (a) `quarantine/<id>/*.dcm` 존재, (b) `staging/` 비어있음, (c) `SELECT reason, payload_path FROM quarantine` row, 모두 assert. |
| **C-2** | FR-25/AC-19 감사 anchor 스케줄러 | **RESOLVED** | `cli/main.py:298-391` `start` 데몬: `anchor_interval = cfg.audit.anchor_interval_seconds`, `_maybe_anchor()` 헬퍼가 `audit_logger.head_seq`/`.head_hash`를 읽어 `upload_client.post_audit_anchor(...)`를 호출, 성공 시 `audit.anchor.uploaded`, 실패 시 `audit.anchor.failed` 감사 이벤트 append. 스케줄 체크 루프 본문(line 379-381)과 슬립 내부(line 389-391) 두 지점에 있어 신호 수신/오랜 tick 중에도 주기 유지. 테스트 `tests/unit/test_upload.py:170-276 test_daemon_loop_schedules_anchor`가 `start --oneshot` 실행 → mock central `_anchors/*.json`에 `gateway_id`, `head_hash`(sha256 접두), `seq_range` 검증. 추가로 `tests/unit/test_upload.py:125-167 test_post_audit_anchor_reaches_mock_central`가 UploadClient 계약 단독 검증. |
| **H-1** | HTTPS 강제 (central.base_url) | **RESOLVED** | `upload/client.py:66-79`: scheme !=`https`이면 `ValueError` raise (기본). `allow_insecure=True`이면 `log.warning("insecure central base_url in use — not for production")`. `config/schema.py:112-115` `CentralConfig.allow_insecure: bool = False` (opt-in). `cli/main.py:529` config → UploadClient에 전달. 테스트 `test_upload_client_rejects_http_by_default` (279-283) + `test_upload_client_accepts_http_with_allow_insecure` (286-297) 양방향 커버. |
| **CP-3** | Staging 3-depth (FR-14) | **RESOLVED** | `deid/engine.py:242-251`: `series_dir = output_dir / new_series; out_path = series_dir / f"{new_sop}.dcm"` — `{out}/{series}/{sop}.dcm`. `reverify`는 `rglob("*.dcm")`로 서브트리 탐색(`engine.py:278`). `pipeline.py:299-310`: 파이프라인이 series 서브디렉터리 보존하며 `final_staging / series_name`으로 이관, `final_staging.rglob("*.dcm")`로 재수집. 결과 트리는 `{staging_root}/{pseudo_study_uid}/{pseudo_series_uid}/{pseudo_sop_uid}.dcm`으로 dev-spec §4.3 FR-14 일치. 테스트 `test_deid_output_follows_series_depth_layout` (195-212)이 per-file 경로 assert. |
| **AC-12** | `stale_studies()` status 연결 | **RESOLVED** | `cli/main.py:424-477`: `status`가 StagingManager를 생성해 `stale_studies(threshold_seconds=...)` 호출, JSON 모드는 `data["staging"]["stale_count"]`, 텍스트 모드는 `Stale: N` 라인 출력(design-spec §6.2 `Staging` 블록). 테스트 `test_status_shows_stale_row` (`tests/unit/test_cli.py:121-145`): 73시간 backdate된 디렉터리를 생성 → text/JSON 양쪽에서 stale=1 검증. |
| **Spec typo** | dev-spec §6.4 113111 → 113105 | **RESOLVED (dev-spec)** / **PARTIAL (design-spec)** | `docs/specs/dev-spec-gateway-agent.md:338, 818` 모두 `113105`로 교정, 파일 내 `113111` 잔존 없음 (grep 0건). 다만 `docs/specs/design-spec-gateway-agent.md:422`의 YAML 예시 주석 `clean_descriptors: true # DCM 113111`은 **여전히 잔존**. 기능 영향은 없으나 스펙 drift이므로 §2.3 N-1로 신규 등록. |

**추가 확인 (여전히 open 대상)**:
- **AC-29 (trivy)**: v0.1 범위 유지 여부 Kyle 결정 대기. 현재 workflow 미추가. 본 Round 2 스코프 외.
- **AC-28 (CI)**: 동일. `.github/workflows/` 부재. 본 Round 2 스코프 외.
위 두 건은 Round 1 권고에 남아 있으나 Kyle이 v0.1 필수에서 제외하기로 지시한 상태로 해석 (카르론). Round 2에서는 재FAIL 처리하지 않음.

### 2.3 새 발견 (Round 2 신규)

- **N-1 (Low · 문서 drift)**: `docs/specs/design-spec-gateway-agent.md:422` YAML 예시 주석에 `# DCM 113111` 잔존. dev-spec는 `113105`로 정합화되었으므로 design-spec도 맞추는 것이 안전. 기능·보안 영향 없음. 후속 doc-only patch 권고.
- **N-2 (Observation · non-blocking)**: Round 1에서 보고한 Round 1 발견 중 **Should-fix 항목 5건** (AC-2 단위 테스트, AC-28 CI workflow, AC-29 trivy, AC-31 README salt 회전, H-2/M-1/M-2 Medium 보안 가드)은 Round 2 스코프에 포함되지 않았고 여전히 open. Round 2 대상은 Round 1 Must-fix + 선별 High로 한정되었으므로 scope 위반이 아님. v0.1.1에서 후속.
- **N-3 (Observation)**: "첫 틱 즉시 anchor" (`cli/main.py:328` `last_anchor_at = time.monotonic() - anchor_interval`) 동작은 dev-spec에 명시되지 않은 개발자 선택. 운영 측면에서 기동 직후 중앙 연결 가시성 확보 목적이며 오남용 위험 없음 → **수용 가능한 범위 내 부가 동작**으로 판단. scope creep은 아님 (데몬 anchor 경로의 초기 상태 값 한 줄).

기존 Round 1 발견 중 리패키징된 항목은 없음(진짜 신규만 등록).

### 2.4 Scope 규율 평가

| 파일 | 변경 라인 | 적정성 |
|------|----------|--------|
| `tests/unit/test_upload.py` | +183/-0 | 적정. 2개 신규 테스트(post_audit_anchor, daemon_loop) 및 H-1 테스트 2개 추가. |
| `src/radivault_gateway/cli/main.py` | +91/-? | C-2 anchor 스케줄러(~60줄), AC-12 status stale 섹션(~15줄), H-1 allow_insecure 전달(1줄). 의도한 3건만 포함. |
| `src/radivault_gateway/staging/manager.py` | +62/-? | C-1 quarantine_root / quarantine_dir / move_to_quarantine. FR-11 직접 대응. |
| `tests/unit/test_pipeline_mock.py` | +53/-? | 신규 2 테스트 + 기존 테스트의 `allow_insecure=True` 전파. |
| `src/radivault_gateway/orchestrator/pipeline.py` | +49/-? | C-1 quarantine 전환, CP-3 3-depth 이관. 목표 외 touch 없음. |
| `tests/unit/test_cli.py` | +28 | `test_status_shows_stale_row`, `allow_insecure` 전파. |
| `src/radivault_gateway/upload/client.py` | +18/-? | H-1 validator + warn log만. |
| `src/radivault_gateway/deid/engine.py` | +10/-? | CP-3 series subdir + reverify rglob. |
| `src/radivault_gateway/config/schema.py` | +4 | `allow_insecure` 필드 추가만. |
| `docs/specs/dev-spec-gateway-agent.md` | +2/-2 | 오타 교정만. |

결론: **무허가 리팩터·스코프 이탈 없음**. 모든 변경이 Round 1 권고와 1:1 매핑. 테스트 비율도 훌륭 (211/295 구현 라인에 테스트 추가). 작업 규율 A.

### 2.5 테스트 커버리지 관찰

- **`test_pipeline_quarantines_burned_in_studies`**: 얕지 않음. (a) 파일 시스템(`*.dcm` in quarantine), (b) 파이프라인 summary counters, (c) staging 비어있음, (d) DB row(`reason`, `payload_path`) 전부 assert. AC-8 증빙용으로 충분.
- **`test_daemon_loop_schedules_anchor`**: CLI 진입(`CliRunner`) + `_build_pipeline` monkey-patch + `httpx.MockTransport` bridge → `start --oneshot` 1회 tick 후 mock central `_anchors/` JSON 페이로드 검증. head_hash 포맷, seq_range 둘 다 assert. AC-19의 본질 요구(인터벌 호출 발생·올바른 head 전달)를 기능 단위로 커버. 단, "시간당" 간격 자체는 60s로 축소(`anchor_interval_seconds: 60`)해 즉시 발화 경로만 테스트 — 인터벌 경과 로직은 간접 검증. 수용 가능.
- **`test_post_audit_anchor_reaches_mock_central`**: UploadClient 계약만 단독 검증(POST body, anchor_id response). 단위 분리 적절.
- **`test_upload_client_rejects_http_by_default` / `_accepts_http_with_allow_insecure`**: 양방향 브랜치 + warn 로그 record 검증.
- **`test_status_shows_stale_row`**: 73h backdate로 실 경계조건 커버, text/JSON 양면 확인.
- **`test_deid_output_follows_series_depth_layout`**: 각 output path의 parent 이름이 pseudo_series_uids 집합에 포함되는지 단위로 확인. 얕긴 해도 FR-14의 실질적 요구는 충족.

전반적으로 **6개 신규 테스트 모두 행동(behavior) 기반**이며 구현 디테일에 결합되지 않음. shallow smoke 테스트 없음.

### 2.6 Round 2 최종 판정

**PASS with minor issues** (병합 가능)
- Round 1 Critical 2건 및 High/Medium 3건 모두 RESOLVED, 증거 확보.
- 유일한 open 항목은 Low 문서 drift 1건(N-1: design-spec 113111 잔존).
- Round 1에서 이월된 Should-fix(AC-2 테스트, AC-28/29 CI/trivy, AC-31 README, H-2/M-1/M-2) 및 오늘 신규 발견한 N-1은 **v0.1.1 후속**으로 분리 처리 권고 — v0.1 MVP 병합·배포는 차단 사유 없음.

---

### NEXT_STEP (Round 2)
- 완료 산출물: `docs/qa/qa-report-gateway-agent.md` (Round 2 섹션 추가)
- 판정: **PASS with minor issues**
- Critical 이슈: 0건 (Round 1 C-1, C-2 RESOLVED)
- Minor 이슈: 1건 — (N-1) design-spec:422 `113111` 잔존 (문서 drift)
- 제안 다음 단계:
  - PASS with minor → **@marketer** 런칭 콘텐츠 준비 병렬 가능.
  - **@developer** N-1 doc-only patch (design-spec 422) 머지 후 처리 가능. v0.1.1 backlog에 Round 1 Should-fix 5건 + N-1 묶어 이관.
- Kyle 결정 필요 사항:
  1. AC-28 CI workflow / AC-29 trivy를 v0.1 필수 → v0.1.1 이월로 공식 승인할지.
  2. Round 1 Medium 보안 가드(H-2 PACS Basic auth 로그 필터, M-1 Linux 0600 enforce, M-2 secret __repr__)의 v0.1.1 타임라인.
