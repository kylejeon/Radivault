# QA 리포트 — de-id-pixel v0.2 (Gateway Agent v0.2)

> **Status**: Draft v1 · **Feature slug**: `de-id-pixel` · **검수 일자**: 2026-04-22
> **작성자**: @qa (Claude Opus 4.7, 1M ctx)
> **대상 커밋 범위**: `c39e526..26c9d47` (6 commits, claude 브랜치)
> **근거 스펙**: [dev-spec-de-id-pixel](../specs/dev-spec-de-id-pixel.md) (47 FR / 35 AC), [design-spec-de-id-pixel](../specs/design-spec-de-id-pixel.md) (20 AC-D)

---

## 1. 최종 판정

**FAIL (Critical — 병합 불가)**

1. **AC-1 / FR-31 / FR-34 파이프라인 통합 결함 (Critical)**: `PixelDeidEngine`은 "BurnedInAnnotation=YES 스터디를 격리 대신 pixel 경로로 승격"이라는 핵심 기능 요건(dev-spec §1.2, FR-31, §8.1 플로우차트)을 **충족하지 못한다**. `DeidEngine._check_quarantine`(`src/radivault_gateway/deid/engine.py:336-343`)은 `pixel.enabled`과 **무관하게** 무조건 `QuarantineRequired`를 raise하며, `Pipeline._process_study`(`orchestrator/pipeline.py:208-250`)는 이를 잡아 pixel 호출 없이 격리한다. 즉 "격리 큐를 픽셀 처리로 승격"이라는 스펙 전체 목적이 **런타임에 실행되지 않는다**. 단위 테스트는 `PixelDeidEngine.process_study`를 직접 호출해 AC-1을 통과시키지만, 실제 `Pipeline.run_once` 경로를 커버하는 테스트는 없다.
2. **AC-28 Defacing DICOM 태그 누락 (High)**: `_mark_dicom_defaced`(`deid/pixel/engine.py:386-406`)는 정의만 존재하고 **호출 사이트가 전혀 없다** — 정상 defacing 통과 시에도 `(0012,0063)`에 `Defaced` 서브스트링, `(0012,0064)`에 `RV_DEFACE_01` 코드가 추가되지 않는다. AC-28 전체 FAIL.
3. **AC-D-1 bilingual flag 설명 누락 (Medium)**: `de-id-test --help` 출력 내 신규 플래그(`--pixel`, `--ocr-only` 등)가 영어 단독 설명이다. design-spec §2.3.1은 ko+en 병기를 요구(AC-D-1). 실제 출력 확인.
4. 기타: 상기 결함은 회귀 없이 PR 수정 가능하나, (1)은 스펙 전체의 **raison d'être**를 깨므로 critical 차단 사유.

### 긍정 관찰
- 122 gateway unit + 50/17 central + 49/20 search 회귀 모두 통과. Ruff clean.
- PHI 로그 오염 방지(FR-38)는 설계·구현 모두 엄격. OCR `box.text`를 로깅·DB에 기록하는 코드 경로 grep 결과 없음. `box_hash`(sha256[:16]) 유틸로 CLI surface도 안전.
- 재검증 게이트(FR-19 OCR residual, FR-29 face voxel)의 실패→격리 경로는 단위 테스트로 6건 커버됨.
- 의료 제외 매칭(FR-25/26)은 default 7개 영문 패턴을 parametrized test로 전부 검증.
- Bit-equivalence 설계 원칙(FR-41): `build_pixel_deid_engine(cfg)`이 `enabled=False`에서 `None` 반환 → `Pipeline` 생성자에서 `if self._pixel is not None` 분기로 v0.1 경로 완전 보존. 구조적으로 안전.

---

## 2. 수용 기준 매트릭스

### 2.1 dev-spec §10 AC-1..AC-35

| AC | 판정 | 증거 |
|---|-----|-----|
| AC-1 (BurnedInAnnotation=YES → OCR_REQUIRED at triage) | **PASS (unit) / FAIL (pipeline)** | 단위: `tests/unit/test_pixel_triage.py:17-23`, `test_any_instance_with_burn_in_wins:48-56`. 그러나 파이프라인에서는 **절대 실행되지 않음** — `deid/engine.py:340` 무조건 quarantine. §3 Critical #1 참조. |
| AC-2 (Modality=US → OCR_REQUIRED) | PASS | `test_modality_allowlist_triggers_ocr_required:26-32` |
| AC-3 (CT+NO → SKIP) | PASS | `test_ct_no_burn_in_is_skip:35-39` |
| AC-4 (TesseractOcrEngine detect_text 합성 영상) | PASS (live test) | `tests/integration/test_pixel_tesseract.py:36-53` — `PIXEL_TEST_TESSERACT=1` 필요; 기본 skip. 코드상 `_boxes_from_tesseract_dict` 로직은 단위 테스트로 검증됨(`test_pixel_ocr_mock.py:30-43`). |
| AC-5 (solid_black fill → bbox 픽셀 0) | PASS | `test_pixel_redaction.py:27-37` |
| AC-6 (residual recheck) | PASS | `test_pixel_redaction.py:73-124`, `test_pixel_pipeline.py:153-170` (FAIL path → `ERR_PIXEL_RESIDUAL_TEXT`) |
| AC-7 (Tesseract 바이너리 부재 → `ERR_PIXEL_OCR_ENGINE_FAILURE`, state=pixel_failed) | PARTIAL | `test_build_ocr_engine_raises_when_unavailable:71-75` 바이너리 부재 시 코드 경로 증거 있음. 그러나 실제 파이프라인에서 state=`pixel_failed`로 전이되는지 통합 증거 없음 (engine 실패 경로는 `pipeline.py:539-578`에 존재하지만 integration 테스트 없음). |
| AC-8 (`on_missing=disable/fail_start`) | PASS | `engine.py:484-506` 로직 + `test_pydeface_is_available_returns_false_on_host:43-46` |
| AC-9 (CT+HEAD → defacing, CHEST → skip) | PASS | `engine.py:159-181` `_defacing_eligible` + `test_residual_face_voxels_quarantines:219-243` (MR+HEAD) |
| AC-10 (DENTAL → EXCLUSION) | PASS | `test_medical_exclusion_quarantines_before_defacing:192-216` + `test_pixel_exclusion.py:16-38` |
| AC-11 (한국어 "치과" 미매칭 확인) | PASS | `test_korean_keyword_not_matched_by_default:51-53` |
| AC-12 (실 pydeface → removed ratio > 0.05) | NOT VERIFIABLE | `tests/integration/test_pixel_pydeface.py:40-60` — live only, FSL 미설치 환경 skip. 코드상 `_estimate_removed_ratio`는 `pragma: no cover`. |
| AC-13 (stub ratio=0 → `ERR_PIXEL_RESIDUAL_FACE_VOXELS`) | PASS | `test_residual_face_voxels_quarantines:219-243` |
| AC-14 (fallback → `pixel.deface.fallback_used` audit 이벤트) | PARTIAL | `test_defacing_fallback_used_on_primary_failure:246-273`이 fallback 호출을 확인하지만 audit log에 `pixel.deface.fallback_used` 이벤트가 실제 기록되는지는 검증 안 됨. `engine.py:281-290`에 log 호출은 존재하나 AuditLogger로 가는 경로 아님(logger만). |
| AC-15 (pixel.enabled=false → v0.1 바이트 동등) | PASS (design-level) | `build_pixel_deid_engine`가 `None` 반환 + `Pipeline.__init__` `pixel=None` 기본 → `_pixel is None` 분기 완전 skip(`pipeline.py:319`). 단 **바이트-동등 비교 테스트는 부재** — "structurally equivalent"만 보증. 단위 회귀 122건이 통과한다는 점이 간접 증거. |
| AC-16 (정상 경로 state 전이) | PARTIAL | state enum 추가는 확인(`state/db.py:124-127`), `Pipeline._run_pixel_stage`이 `PIXEL_PROCESSING` 설정(line 482). 그러나 성공 시 `PIXEL_DEIDED`로 전이하는 명시 코드 부재 — `_run_pixel_stage`가 성공 반환 후 파이프라인은 `StudyState.DEIDED` / `UPLOADED`로 직행(`pipeline.py:353-360, 436`). `PIXEL_DEIDED` 값이 enum에 있으나 쓰이지 않음. |
| AC-17 (pixel 실패 → state=pixel_failed + quarantine row with `pixel_residual_text` reason) | PASS | `pipeline.py:512-517` `mark_state(pseudo_uid, PIXEL_FAILED)` + `add_quarantine(..., reason=f"pixel:{exc.code}")` |
| AC-18 (crash recovery → pixel_processing 롤백 + 재큐잉) | **FAIL** | 크래시 복구 로직이 구현되지 않음. `grep -n "pixel_processing" src` 결과 state 정의 외에 감지·롤백 코드 없음. FR-36 미구현. |
| AC-19 (audit.log 5개 시퀀셜 이벤트) | PARTIAL | `pipeline.py:497-504, 582-595`에서 `pixel.quarantined`와 `pixel.completed` 2종만 audit에 기록. dev-spec FR-37가 요구하는 `pixel.ocr.started/completed`, `pixel.deface.started/completed`, `pixel.ocr.box_count` 등 세분 이벤트 부재. |
| AC-20 (OCR 원문 텍스트 grep 부재) | PASS | `grep "box\.text\|\.text.*extra" src`에서 logging·audit 경로 결과 0건. `box_hash`만 유틸로 존재. |
| AC-21 (pixel_audit_event 행 + audit_seq 일치) | PARTIAL | `pipeline.py:506-511, 596-622`에서 pixel_audit_event 행 작성. 그러나 `audit_seq` 값은 **설정되지 않음**(항상 `None`) — `add_pixel_audit_event` 호출 시 audit_seq 인자 미전달. 교차 참조 불가. |
| AC-22 (인덱스 3종 — study/op/outcome) | PASS | `state/db.py:98-101` 4개 인덱스(study/op/outcome/created). |
| AC-23 (config 없을 때 기본 false) | PASS | `test_load_config_with_pixel_default_off:91-94` |
| AC-24 (invalid engine → exit 64) | PASS | `test_invalid_engine_exits_64_via_loader:135-146` + `cli/main.py:36` `sys.exit(64)` on ERR_CFG_*. |
| AC-25 (env var override) | PASS (naming 편차) | `test_env_override_sets_enabled:125-132` with `RADIVAULT_DEID__PIXEL__ENABLED`. 그러나 dev-spec FR-43은 `RADIVAULT_DEID_PIXEL_<KEY>` 단일 언더스코어를, design-spec §3.4는 `RADIVAULT_DEID_PIXEL__ENABLED` 복합을 예시로 듬. 실 구현은 `RADIVAULT_DEID__PIXEL__ENABLED`. **명세-구현 명명 혼선** (Medium). |
| AC-26 (slim 이미지에서 enabled=true → ERR_PIXEL_OCR_ENGINE_FAILURE exit) | PASS | `engine.py:476-480` wrap → `ERR_CFG_PIXEL_ENGINE_MISSING` + `cli/main.py:849-854` exit 64. 실증: `python -m radivault_gateway pixel-selftest`가 dev host에서 exit 3 반환 확인. |
| AC-27 (`(0012,0063) PixelRedacted` + `113101` 코드 추가) | PASS (구조적) | `engine.py:363-383` `_mark_dicom_pixel_redacted` 호출 사이트 `line 242`. 단 unit test가 tag 쓰기 결과를 재읽어 검증하지 않음 — 간접 증거. |
| **AC-28** (Defacing `(0012,0063) Defaced` + `RV_DEFACE_01` 코드) | **FAIL** | `_mark_dicom_defaced`(engine.py:386-406)는 **호출 사이트 부재**. `grep "_mark_dicom_defaced" src`는 함수 정의 한 줄만 반환. Defacing 실행 후 DICOM 태그 갱신 없음. |
| AC-29 (성능) | NOT VERIFIABLE | 벤치마크 스위트 부재. |
| AC-30 (메모리 2 GB) | NOT VERIFIABLE | 측정 없음. |
| AC-31 (E2E 지연 +120초) | NOT VERIFIABLE | 측정 없음. |
| AC-32 (Central manifest 신규 필드 없음) | PASS | `upload/client.py:126-147` manifest 구조에 pixel 관련 신규 필드 없음 확인. method_code_sequence만 v0.1과 동일 스키마로 유지. |
| AC-33 (Metadata Index 회귀) | PASS | search 49 unit + 20 integration 전부 통과. |
| AC-34 (-pixel 이미지 pixel-selftest exit 0) | NOT VERIFIABLE | 이미지 빌드·실행 환경 부재. Dockerfile.pixel 구조 검토만 수행(§5 참고). |
| AC-35 (기본 이미지에서 exit 3) | PASS | `python -m radivault_gateway pixel-selftest --json` 실제 실행 → `"exit_code": 3`. |

### 2.2 design-spec §11 AC-D-1..AC-D-20

| AC-D | 판정 | 증거 |
|------|-----|-----|
| AC-D-1 (`de-id-test --help` 신규 플래그 + ko+en 병기) | **FAIL** | 실행 결과 플래그는 모두 존재하나 모든 설명이 영어 단독. 예: `--pixel  Also run pixel stage (OCR + defacing)`. 한국어 병기 없음. design-spec §2.3.1 표 기대치 미충족. |
| AC-D-2 (`pixel-selftest --help` exit code 5종 명시) | PARTIAL | `--help` 출력에 exit code 설명 자체 부재. `pixel_selftest.py:104-107` docstring에는 있으나 Click `--help`에는 렌더되지 않음. |
| AC-D-3 (selftest 출력 [OCR]/[DEFACING]/Summary 구조) | PASS | `_render_human()`(`pixel_selftest.py:140-182`) 구조 확인 + 실제 실행 로그 확인. |
| AC-D-4 (selftest --json ocr/defacing/summary + exit_code) | PASS | 실제 `pixel-selftest --json` 출력에 3 블록 + `summary.exit_code` 포함. |
| AC-D-5 (`status` Pipeline 24h 라인 확장 + [v0.2] 라벨) | PARTIAL | `cli/main.py:757` `"Pixel stage  [v0.2]"` 라벨은 있음. 그러나 design-spec §2.5.1은 `Pipeline (24h)` 섹션 **내부**에 `pixel_deided`/`pixel_failed` 카운트 2줄 추가를 요구. 구현은 상태별 카운트를 `counts_by_state()`에서 그대로 출력하므로 라인 존재는 하되 `[v0.2]` 라벨은 별도 Pixel stage 섹션에만 달림. |
| AC-D-6 (Pixel stage 80열 유지) | PASS | 렌더 폭 계산 `_render_pixel_status()` 각 라인 ≤ 80열 확인. |
| AC-D-7 (status --json 상위 pixel 블록 7 필드) | PASS | `cli/main.py:728-751` `_pixel_status` 반환 dict에 `enabled, engines, triage_24h, ocr_24h, deface_24h, quarantine_24h, engine_errors_24h` 7개. |
| AC-D-8 (disabled 시 Pixel stage 섹션 완전 생략) | PASS | `cli/main.py:625, 648` 조건부 렌더. |
| AC-D-9 (`configs/gateway.pixel.example.yaml`가 validation 통과) | PASS | `test_pixel_example_yaml_parses:118-122` |
| AC-D-10 (config 에러 메시지 7 항목) | PARTIAL | `format_cli_error`는 code/ko+en/fields/Fix/Docs 5요소. 그러나 `ERR_CFG_PIXEL_ENGINE_MISSING`의 "파일/경로/현재값/기대값" 4항 현지화는 `config/loader.py`의 기존 ERR_CFG_ 포맷으로 커버(통합 테스트 없음). |
| AC-D-11 (금지 필드 없음) | PASS | `grep -rn "pixel.*text\|pixel.*raw_ocr\|pixel.*absolute_coord" src` 결과 0. 로그 필드 네임 `pixel.{stage,library,decision,reason,error_code,duration_ms,confidence_p50/p10,redaction_count,defaced_voxel_ratio}` 모두 safe. |
| AC-D-12 (Prometheus 10 metrics radivault_gateway_pixel_*) | **NOT IMPLEMENTED** | `grep -rn "prometheus\|/metrics" src/radivault_gateway` 0건. dev 자백. 스펙 §NFR "관측성" 미준수. 배포 단계에서 알림 A1-A6도 수신처 없음. |
| AC-D-13 (6 알림 A1-A6 + PromQL) | **NOT IMPLEMENTED** | 메트릭 미송출로 알림 룰 정의 자체 무의미. 스펙 문서에만 존재. |
| AC-D-14 (pixel-selftest는 기본 이미지에서도 존재) | PASS | 커맨드 등록 `cli/main.py:22, L?` 항시 노출 확인. 실행 시 exit 3. |
| AC-D-15 (9 error codes master 표) | PASS | `test_pixel_errors.py:14-28` 9개 전수 존재. |
| AC-D-16 (각 에러 code 8 필드) | PARTIAL | `PixelErrorMessage` dataclass에는 code/ko/en/suggested_action/log_level 5 필드. design-spec §5.1은 exit/trigger/operator_action/sre_action 등 8 필드 요구. 구현이 8 필드 카드를 완전히 제공하진 않으나 운영 가이드는 대부분 `suggested_action` 한 줄로 축약됨. |
| AC-D-17 (Runbook RB-PX-1..6 5섹션) | NOT VERIFIABLE (문서 외) | Runbook은 design-spec 본문 텍스트이므로 코드 검증 대상 아님. |
| AC-D-18 (`de-id-test --pixel --show-boxes` 원문 텍스트 없음) | PASS | `cli/main.py:377-381` — `--show-boxes`는 "(stats-only; hashed text never printed — FR-38)" 만 출력. 원문 출력 경로 없음. |
| AC-D-19 (Rollback 4 스텝) | NOT VERIFIABLE (문서 외) | design-spec §7.3 문서에 존재. 운영 대상 외 코드 검증 대상 아님. |
| AC-D-20 (임상 QA 5 sign-off 기준) | NOT VERIFIABLE (문서 외) | design-spec §8.3 문서 대상. |

---

## 3. Critical 발견 (Severity: Critical — 병합 불가)

### Critical #1 — BurnedInAnnotation=YES 스터디가 pixel 경로로 재라우팅되지 않는다 (FR-31, AC-1 파이프라인 레벨 FAIL)

- **파일**: `src/radivault_gateway/deid/engine.py:336-343`, `src/radivault_gateway/orchestrator/pipeline.py:207-250`
- **증상**: `pixel.enabled=true`에서도 `BurnedInAnnotation=YES`인 모든 DICOM은 `DeidEngine._check_quarantine`에서 무조건 `QuarantineRequired`로 빠져 pipeline 208행에서 격리되고 pixel 호출은 일어나지 않는다. 즉 **"번인 스터디를 OCR로 승격한다"라는 이 기능의 핵심 목적이 실제 런타임에 작동하지 않는다**.
- **증거 체인**:
  1. `engine.py:338-340`: `if burned == "YES": raise QuarantineRequired("burned_in_yes", ...)`.
  2. `pipeline.py:208-250`: `except QuarantineRequired` → `state=QUARANTINED`로 전이, `shutil.rmtree(staging_dir)`, 즉시 return. Pixel 호출 무조건 skip.
  3. `pipeline.py:319` `if self._pixel is not None:` 블록은 **reverify 통과 이후에야 도달** — burn-in 스터디는 여기까지 절대 오지 않음.
  4. 유닛 테스트 `tests/unit/test_pixel_pipeline.py`는 `PixelDeidEngine.process_study`를 직접 호출해 AC-1을 "pass"하게 보이지만 `Pipeline.run_once` 경로의 회귀 증거는 없다.
  5. 오히려 기존 v0.1 테스트 `test_pipeline_quarantines_burned_in_studies`(`tests/unit/test_pipeline_mock.py:215+`)가 **여전히 통과한다** — pixel을 주입하지 않은 케이스지만 pixel 활성 케이스에서도 동작은 동일하다(DeidEngine 레벨에서 차단되므로).
- **영향**: dev-spec §0 TL;DR "격리를 픽셀 처리로 승격"이라는 feature 전체의 원래 약속이 깨진다. 파일럿 병원이 `pixel.enabled=true`로 배포해도 번인 US/SC/OT 스터디는 여전히 격리 큐에 쌓인다.
- **우회**: `gateway.pixel.example.yaml` line 28에서 `burnin_quarantine_modalities: ["SC", "OT"]`로 US만 제거 — 그러나 이것은 BurnedInAnnotation 태그 자체가 아니라 모달리티 블랙리스트를 좁히는 것뿐이며, `BurnedInAnnotation=YES`인 CT/MR/US/기타는 모두 여전히 차단된다.
- **요구 수정**: `DeidEngine._check_quarantine`에 `pixel_enabled` 플래그를 주입하여 `pixel.enabled=true + BurnedInAnnotation=YES`인 경우 quarantine raise를 보류하고 pipeline이 pixel 경로로 라우팅하도록. 동시에 `pipeline._process_study`의 `except QuarantineRequired` 블록을 분기해 pixel 경로 재시도 로직 삽입.

### Critical #2 — AC-28 Defacing DICOM 태그 미기록 (FR-18, §6.4 DICOM 태그 효과)

- **파일**: `src/radivault_gateway/deid/pixel/engine.py:386-406`
- **증상**: `_mark_dicom_defaced`는 정의만 존재하며 `grep -n "_mark_dicom_defaced" src/radivault_gateway/deid/pixel/engine.py` 결과 함수 정의 한 줄만 보인다. `_run_defacing` 내부(`line 262-318`) 어디에서도 호출하지 않음. Defacing 성공 시 출력 DICOM의 `(0012,0063)`에 `Defaced` 서브스트링이 없고 `(0012,0064)`에 `RV_DEFACE_01` 코드가 없다.
- **영향**: Central/Metadata Index가 이후 "pixel-defaced 여부 필터"를 제공하려 할 때(향후 별건 feature) 소급 구분 불가. 더 즉시: dev-spec §6.4/AC-28 binary-pass 기준 위반.
- **요구 수정**: `_run_defacing` 성공 path 끝(거의 즉시 return 직전)에 대상 DICOM 파일들을 순회하며 `_mark_dicom_defaced(ds) + ds.save_as` 수행.

---

## 4. High / Medium / Low 발견

### High #1 — AC-18 크래시 복구 미구현 (FR-36)

- **파일**: 없음 (로직 자체 부재)
- **증상**: `pixel_processing` 상태인 study_job을 재기동 시 감지하고 `deided`로 롤백해 재큐잉하는 로직이 구현되지 않음. dev-spec FR-36.
- **리스크**: 프로세스 크래시 시 study가 `pixel_processing` 상태로 영구 멎음. 수동 DB 개입 필요.
- **우선순위**: High — 운영 안정성 직접 영향.

### High #2 — Prometheus 메트릭·알림 미구현 (AC-D-12, AC-D-13, NFR 관측성)

- **파일**: `src/radivault_gateway/` 전체 — `prometheus_client` 의존성 및 `/metrics` endpoint 부재.
- **증상**: design-spec §4.3의 10개 메트릭 + §4.4의 6개 알림이 배포 불가능. dev 자백. Gateway v0.1도 /metrics endpoint 부재였던 것으로 보이므로 본 feature 범위 밖 결정(deferred)이 타당할 수 있으나, **dev-spec NFR "관측성" 요건 미충족**은 명시적.
- **권고**: @planner와 Kyle 결정 — v0.2 MVP 범위에서 관측성 deferral 허용할지, 또는 별건 스펙으로 분리할지.

### High #3 — AC-14 `pixel.deface.fallback_used` audit 이벤트 미기록

- **파일**: `src/radivault_gateway/deid/pixel/engine.py:281-290`
- **증상**: `_run_defacing`의 fallback 경로에서 `log.warning("pixel.deface.fallback_used", ...)`만 호출하고 `AuditLogger.append`로 가지 않음. Audit hash-chain에 이벤트가 남지 않아 법적 증거 부족.
- **요구 수정**: pipeline 레이어로 fallback 발생 이벤트를 surface하고 `self._audit.append("pixel.deface.fallback_used", ...)` 호출.

### Medium #1 — FR-37 세분 audit 이벤트 축소 (AC-19 PARTIAL)

- **파일**: `src/radivault_gateway/orchestrator/pipeline.py:496-595`
- **증상**: dev-spec FR-37는 `pixel.triage.decided`, `pixel.ocr.started`, `pixel.ocr.completed`, `pixel.ocr.box_count`, `pixel.deface.started`, `pixel.deface.completed`, `pixel.medical_exclusion.matched`, `pixel.skipped` 등 세분 이벤트를 요구. 구현은 `pixel.quarantined`와 `pixel.completed` 2종 + DB만 기록. triage·ocr·deface 각각의 started/completed 이벤트 audit 로그에 부재.
- **영향**: design-spec §2.6 `audit verify` 하단 event breakdown에서 `pixel.*` namespace 상세 카운트가 비게 됨.

### Medium #2 — AC-21 audit_seq 상호 참조 미기록

- **파일**: `src/radivault_gateway/orchestrator/pipeline.py:506-622`
- **증상**: `add_pixel_audit_event(..., audit_seq=<?>)` 호출이 audit_seq를 전달하지 않아 항상 NULL. 이에 따라 `pixel_audit_event.audit_seq` ↔ audit.log `seq` 교차 참조 불가 — dev-spec §6.2 column 설계 목적 불실.
- **요구 수정**: `self._audit.append(...)`의 반환값(seq)을 받아 `add_pixel_audit_event`에 주입.

### Medium #3 — AC-16 PIXEL_DEIDED 상태 미사용

- **파일**: `src/radivault_gateway/orchestrator/pipeline.py:596` 이후
- **증상**: `StudyState.PIXEL_DEIDED`는 enum에 정의되나 전이 코드가 부재. 성공 pixel 스터디는 pixel 직후 `mark_state(pseudo_uid, DEIDED)` → `UPLOADING` → `UPLOADED`로 진행. dev-spec §6.1 상태 다이어그램과 불일치.
- **영향**: `summary.pixel_deided` 카운트는 `StudyOutcome.state == PIXEL_DEIDED`에만 증가하는데(`pipeline.py:148`), 실 경로는 `UPLOADED`로 전이하므로 **`pixel_deided` 카운터는 항상 0**. status 화면에 pixel 성공 카운트 영원히 0으로 표시.

### Medium #4 — AC-D-1 bilingual flag 설명 누락

- 실제 `de-id-test --help` 출력에서 `--pixel`, `--ocr-only`, `--deface-only`, `--both`, `--show-boxes`, `--show-voxel-stats` 설명이 영어 단독. design-spec §2.3.1 규정은 ko+en 병기. 다른 플래그 (예: `--log-level`)도 완전 bilingual은 아니나 새 플래그에 대해 스펙이 명시 예시를 제공하므로 미충족.

### Medium #5 — AC-25 환경변수 네이밍 편차

- dev-spec FR-43: `RADIVAULT_DEID_PIXEL_<KEY>` (단일 `_`). design-spec §3.4: `RADIVAULT_DEID_PIXEL__<KEY>`. 구현: `RADIVAULT_DEID__PIXEL__<KEY>`. 3자 모두 서로 다름. 테스트(`test_pixel_config.py:130`)는 구현 본떠 pass. 운영자가 문서만 보고 설정 시 override 실패 가능.

### Low #1 — `_pick_defacing_volume`은 .dcm 경로를 반환하지만 PydefaceEngine은 NIfTI 입력을 기대

- **파일**: `engine.py:409-419`, `deface_engine.py:76-115`
- **증상**: `_pick_defacing_volume`이 `*.dcm` 후보를 반환 → `PydefaceEngine.deface_volume`가 `nibabel.load()` 호출 → 실패. dev-spec FR-27 요구 "DICOM→NIfTI 변환 레이어" 미구현(`pragma: no cover - live only` 주석 상태).
- **영향**: live defacing path가 pilot 환경에서 첫 호출 즉시 `ERR_PIXEL_DEFACE_FAILURE` 발생 → fallback도 유사한 경로 → quarantine. 결국 모든 defacing 대상 스터디가 격리됨.
- **우선순위**: Low (단위 테스트는 mock 사용, live 테스트는 skip). 단 파일럿 배포 전 반드시 해결.

### Low #2 — FR-28 SOPInstanceUID-preserving DICOM 재인코딩 미구현

- Defacing 결과를 NIfTI → DICOM으로 되돌리는 레이어가 없음. 위 Low #1과 함께 pydeface 경로 전체가 미완성.

### Low #3 — CLI `pixel-selftest --help`에 exit code 표기 부재

- Click 제약으로 docstring의 exit code 정보가 `--help` 본문에 렌더되지 않음. design-spec §2.4.1 예시처럼 `Exit codes:` 섹션을 help 문자열에 inlining 필요.

### Low #4 — Dockerfile.pixel의 FSL 패키지명 오류 가능성

- `fsl-5.0-flirt`은 Debian bookworm에서 가용한지 미확인(`contrib` or `non-free` 저장소 필요). `trivy image` HIGH 0개 게이트와 FSL 런타임 크기(수백 MB) 검증 필요. CI 빌드 기록 없음.

---

## 5. 보안 발견

### 5.1 PHI 오염 금지 (FR-38) — **PASS**

- `grep -rn "box\.text\|\.text" src/radivault_gateway/deid/pixel`: 모두 내부 연산(residual recheck에서 `d.text.strip()` 조건만), logging·audit·DB 기록 경로 없음.
- `OcrBox.text`를 `log.info(extra=...)`나 `audit.append(meta=...)`에 넘기는 코드 경로 0건.
- `box_hash` 유틸(`engine.py:516-518`)은 `sha256[:16]` 고정 — 재식별 실질 불가(접미 16 hex = 64 bit).
- `pixel_audit_event` 컬럼 목록(`state/db.py:80-97`): 원문 텍스트, 원본 UID/PID 컬럼 부재. 좌표 컬럼 부재(box_count 만 존재, 상대·절대 좌표 모두 기록 안 함 — spec 요건보다 더 보수적).
- `--show-boxes`는 "stats-only" 한 줄만 출력 — AC-D-18 PASS.

### 5.2 Over-Redaction / Over-Defacing 리스크 (§12.2)

- 의료 제외 매칭(FR-25/26): default 영문 7 패턴 + `(?i)` case-insensitive. `test_pixel_exclusion.py`가 7 카테고리 전부 parametrized로 검증.
- **잔여 리스크 (스펙 가이드와 일치)**: 한국어 키워드(`치과`·`부비동`·`안와`)는 기본 부재 — AC-11 명시. 파일럿 수집 후 보강 필요를 config 주석에 기록.
- "최소 50건 임상 리뷰어 sign-off"(design-spec §8.3)는 운영 프로세스이며 **코드 강제 없음** — 예상대로이며 위반 없음.

### 5.3 격리 폴백 견고성

- `Pipeline._run_pixel_stage`의 `except Exception` 블록(`pipeline.py:539-578`)이 `quarantine_on_failure=true`일 때 예상치 못한 예외도 격리로 폴백. Tests verify graceful quarantine. **PASS**.
- OCR 엔진 crash/timeout은 `PixelDeidEngineError`로 래핑되어 `quarantine_on_failure=true`일 때 격리. Tests cover `ERR_PIXEL_OCR_ENGINE_FAILURE`, `ERR_PIXEL_RESIDUAL_TEXT`, `ERR_PIXEL_RESIDUAL_FACE_VOXELS`, `ERR_PIXEL_DEFACE_FAILURE`, `ERR_PIXEL_MEDICAL_EXCLUSION` 5경로.

### 5.4 입력 검증

- OCR 엔진은 `np.ndarray` 입력 dtype/shape를 명시 검증하지 않음(`ocr_engine.py:92-118`). Tesseract `image_to_data`가 내부 변환함. 이론상 악성 dtype 전달해도 Tesseract 바이너리 경계까지 단계적으로 떨어짐. Low risk.
- `_pick_defacing_volume`는 staged_dir 내부 파일만 대상 — arbitrary path read 없음. PASS.

### 5.5 의존성 가드 임포트

- `pytesseract`, `pydeface`, `paddleocr`, `nibabel` 모두 메서드 내부 지연 import + `ImportError → PixelDeidEngineError` 래핑. 모듈 import 시 raise 없음 확인(`ocr_engine.py`, `deface_engine.py`, `engine.py:189, 344, 353`).
- `shutil.which()` 기반 is_available 체크. PASS.

### 5.6 비밀 관리

- 신규 비밀 없음 — salt는 기존 v0.1 경로. 라이선스 키·API 키 신규 도입 없음. PASS.

---

## 6. 컴플라이언스 발견 (개인정보보호법 / HIPAA)

### 6.1 완전 익명 게이트 (개인정보보호법 §28조의8)

- `UploadClient.build_manifest`(`upload/client.py:145`)는 항상 `"anonymization_flag": "fully_anonymized"`를 설정. v0.1 이후 유지.
- **우려 1 (Critical #1 종속)**: pixel 경로가 실행되지 않으므로 번인 YES 스터디는 여전히 격리되고 업로드 대상이 되지 않는다 — 역설적으로 *현 구현은 안전*. 그러나 이 안전성은 feature 미작동에서 파생된 것이며 스펙 의도가 아니다.
- **우려 2 (Critical #2 종속)**: Defacing 태그가 DICOM에 기록되지 않으므로 Central/Metadata Index가 "pixel-defaced 여부"를 판별할 수 없다. manifest의 `method_code_sequence` 배열에도 pixel code가 반영되지 않음 — dev-spec §6.5 "자연스럽게 포함" 약속 위반. 단, Central 계약상 새 코드는 "unknown codes allowed"이므로 **압축 파이프라인 crash 없음은 보증**. PASS(Central 호환성). FAIL(추적성).

### 6.2 HIPAA Safe Harbor

- 번인 텍스트 검출·마스킹은 Safe Harbor §164.514(b)(2)의 "identifying numbers, characteristics, codes" 제거에 해당. 현 기능이 실제 동작했다면 강화 효과. 현재는 Critical #1 때문에 미발효.

### 6.3 변조 방지 감사

- pixel 이벤트의 audit hash-chain inclusion — PARTIAL(§4 Medium #1). `pixel_audit_event`는 secondary bookkeeping으로만 동작(법적 증거는 audit.log). hash-chain integrity에 pixel 이벤트가 포함은 되지만 세분 이벤트가 부재.

### 6.4 WORM/철회 경로

- 기존 v0.1 audit WORM 패턴 그대로 유지. 변경 없음. 데이터 철회 경로는 v0.1 quarantine + manual deletion, pixel 변경사항 없음. PASS.

---

## 7. 품질 관찰 (non-blocking)

1. `tests/unit/test_pipeline_mock.py`를 개별 파일 경로로 호출 시 순환 import ImportError 발생(`RetainOptions`). 디렉터리 전체 경로로 호출 시 정상. conftest/suite import 순서 의존성 — 장기적 개선 대상.
2. `_run_ocr`(engine.py:183)는 모든 프레임을 순회 + 각 프레임에 대해 residual recheck — 대형 US 시리즈(50프레임)에서 ×2 OCR 호출. NFR 성능 p95 ≤ 60초 가능 범위이나 파일럿 측정 필수.
3. `PaddleOcrEngine`은 `engine.ocr(image)`를 pragma: no cover로 남겼으며 실 호출 경로 미검증. 현재 기본 엔진이 tesseract이므로 당장 영향 없음 — v0.2.1 이전 별건 검증 필요.
4. `_run_defacing`의 fallback 시 `removed_voxel_ratio` 재검증이 fallback 결과에도 적용됨 — 이중 검증(primary + fallback 둘 다 quarantine 체크 통과해야). 설계적으로 안전.
5. dev-spec `gateway-agent` CLI 네이밍이지만 구현은 `python -m radivault_gateway` (또는 `radivault-gateway`). 문서 예시와 실 바이너리명 혼선 — 기존 v0.1부터 존재하는 문제이므로 본 feature 범위 밖.

---

## 8. 권고 (재작업 항목)

본 리포트는 **FAIL** 판정. @developer가 다음 순서로 수정 후 재검수(@qa round 2) 필요.

### P0 (Critical — 차단)
1. **Critical #1 해결**: `DeidEngine._check_quarantine`이 `pixel.enabled` 상태에 따라 조건부로 raise하도록 리팩토링. 또는 `Pipeline._process_study`의 `except QuarantineRequired` 블록 내부에서 `pixel.enabled=true && reason=="burned_in_yes"`일 때 quarantine 대신 pixel 경로로 재라우팅하는 분기 추가. 회귀 테스트 추가: `test_pipeline_reroutes_burn_in_to_pixel_when_enabled`, `test_pipeline_still_quarantines_burn_in_when_pixel_disabled`.
2. **Critical #2 해결**: `_run_defacing` 성공 경로에 `_mark_dicom_defaced` 호출 추가. 테스트: defacing 성공 DICOM을 pydicom으로 재읽어 `(0012,0063)`에 `Defaced` 포함, `(0012,0064)`에 `RV_DEFACE_01` 코드 존재 확인.

### P1 (High)
3. AC-18 크래시 복구 구현 — 시동 시 `pixel_processing` state로 남은 study 감지 → `DEIDED`로 롤백 → 다음 tick 재큐잉.
4. AC-14 `pixel.deface.fallback_used` audit append 추가.
5. Prometheus deferral 명시 — Kyle에게 v0.2 MVP 범위 축소 승인 또는 별건 feature 분리 결정 요청.

### P2 (Medium)
6. AC-19 세분 audit 이벤트 추가 (`pixel.triage.decided`, `pixel.ocr.started/completed`, `pixel.deface.started/completed`, `pixel.medical_exclusion.matched`, `pixel.skipped`).
7. AC-21 `audit_seq` 교차 참조 — `AuditLogger.append` 반환 seq를 `add_pixel_audit_event`에 전달.
8. AC-16 `PIXEL_DEIDED` state 전이 및 summary.pixel_deided 카운트 실제 증가 경로 수정.
9. AC-D-1 신규 flag 설명 ko+en 병기로 수정.
10. AC-25 환경변수 명명 — 3자(dev-spec/design-spec/구현) 중 하나로 통일. 우선 구현 실제값으로 스펙 문서 보정 or 구현을 스펙 맞게 수정. Kyle 결정.

### P3 (Low)
11. `_pick_defacing_volume`의 DICOM→NIfTI 변환 레이어 구현 (FR-27) — pydeface 라이브 경로 완성.
12. Dockerfile.pixel의 FSL 패키지명 CI 빌드 검증.
13. `pixel-selftest --help`에 Exit codes 섹션 inline.

---

## 9. 회귀 및 크로스-feature

- Gateway unit: **122 passed** (dev 보고 일치, +67 vs v0.1 baseline 55).
- Central unit: **50 passed** (변경 없음).
- Central integration: **17 passed** (변경 없음).
- Search unit: **49 passed** (변경 없음).
- Search integration: **20 passed** (변경 없음).
- 전체: `pytest tests -q` → **258 passed, 4 skipped, 16 warnings**.
- Ruff: `check src tests` → All checks passed. `format --check src tests` → 162 files already formatted.
- Central/Search 회귀 무결성 확인 — `manifest.json` 스키마 변경 없음, method_code_sequence만 기존과 동일.
- AC-32 (manifest 신규 필드 없음) 코드 그레핑 + 테스트 직접 확인: PASS.

---

## 10. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|-----|------|-------|-----|
| 1 | 2026-04-22 | @qa (Claude Opus 4.7 1M) | 최초 검수. 35 dev AC + 20 design AC 전수. FAIL 판정 (Critical 2건: burn-in 재라우팅 부재, defacing DICOM 태그 미기록). |

---

### NEXT_STEP

- **완료 산출물**: `docs/qa/qa-report-de-id-pixel.md`
- **판정**: **FAIL**
- **Critical 이슈**:
  1. BurnedInAnnotation=YES 스터디가 pixel 경로로 재라우팅되지 않음 (FR-31, AC-1 pipeline level) — 기능 전체 미작동.
  2. Defacing DICOM 태그 `_mark_dicom_defaced` 호출 사이트 부재 — AC-28 FAIL.
- **제안 다음 단계**:
  - **FAIL**: @developer — 권고 §8 P0 (2건) → P1 (3건) → P2 (5건) 순 재작업. 재수정 후 @qa round 2 재검수 요청.
  - @marketer 병렬 **금지** — 핵심 기능 미작동 상태에서 런칭 콘텐츠 작성 불가.
- **Kyle 결정 필요**:
  - Prometheus 메트릭 v0.2 MVP 범위 외 deferral 승인 여부.
  - 환경변수 네이밍(`RADIVAULT_DEID_PIXEL_*` vs `RADIVAULT_DEID__PIXEL__*`) 통일 방향.
  - 한국어 exclusion 패턴 기본 포함 여부(오픈 질문 #4).
  - FSL 상업 라이선스 법무 재확인(오픈 질문 #3) — 미해소 시 pilot 배포 보류.
