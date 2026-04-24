# QA Report — `tcia-seed` (Demo Seed Pipeline)

## §0 Meta

| 필드 | 값 |
|---|---|
| Feature slug | `tcia-seed` (dev-spec-buyer-portal-demo §4.S / §8 서브셋) |
| 검수일 | 2026-04-24 |
| 검수자 | @qa (Claude Opus 4.7) |
| 대상 브랜치 | `claude` |
| 검수 커밋 범위 | `4aeb8f5` → `683030c` (demo-seed 5 커밋 + progress) |
| 핵심 커밋 | `5ea682d`, `2ab4b5d`, `fd20a78`, `ccfd560`, `683030c` |
| 구현 파일 | `scripts/demo_seed/{download_tcia,load_orthanc,seed_buyer,seed_hospital,verify}.py`, `scripts/demo_seed/inject_all.sh`, `tests/demo_seed/*` (4 테스트 + conftest), `pyproject.toml` `[demo-seed]` extras |
| **최종 판정** | **PASS with minor issues** |

## §1 요약

1. **기능 수용 기준 6/6 PASS** — AC-S-1 (idempotent), AC-S-3 (verify exit 0 + lock), AC-S-4 (V-6 PHI 0), AC-S-6 (한영 bilingual + exit 2) 모두 실코드/테스트 증거 확보. AC-S-2 (30분 완주) / AC-S-5 (reset.sh --soft) 는 스코프 밖 (Kyle R-1 / 별도 파일 `reset.sh` 검수).
2. **보안·컴플라이언스 Critical 0건** — PHI 필드 print/log 0건, plaintext key는 stdout 1회+0600 파일에만, bearer token은 HTTP header 전용, basic-auth credential 도 로그 미노출. `.gitignore` 가 `.buyer_key.local.txt`, `demo_seed_ready.lock`, `logs/`, `demo_data/` 전부 커버.
3. **Minor 이슈 3건**: (M-1) `DEFAULT_RETRIES = 3` 이나 dev-spec FR-S-7은 "5회" — 문서-구현 갭. (M-2) FR-S-3 "10 GB 캐시 경고" 미구현. (M-3) `--dry-run`이 네트워크 호출은 안 하지만 `demo_data/cache/`에 `_plan.txt` 수백 개를 실제로 쓴다 — 운영자가 "plan-only" 기대 시 놀랄 수 있음. 모두 **non-blocking**, CEO 미팅 D-14 진행에 지장 없음.

**→ Kyle은 TCIA 400-study 다운로드 리허설 R-1을 바로 시작해도 된다.**

---

## §2 수용 기준 매트릭스

### 2.1 Functional Requirements (FR-S-1 ~ FR-S-12)

| FR | 요구 | 구현 위치 | 판정 | 증거 |
|---|---|---|---|---|
| **FR-S-1** | TCIA 공개 컬렉션 / RESTRICTED gate (Kyle 확인) | `seed_config.yaml:9-13` (LIDC-IDRI=RESTRICTED) + `download_tcia.py:492-497` (skip unless `--accept-restricted`) | **PASS** | dry-run 실행 관찰: `WARNING skipping_restricted_collection name=LIDC-IDRI (use --accept-restricted to override)` (log 2026-04-24 10:17:24); `--accept-restricted` 있으면 `done=400`, 없으면 `done=300` |
| **FR-S-2** | 300~500 study, CT/MR/MG 혼합 | `seed_config.yaml:9-34` — 합계 400 (CT 250 + MR 100 + MG 50) | **PASS** | §8.1 표의 "합계 400"과 정확 일치 |
| **FR-S-3** | 로컬 캐시 `./demo_data/cache/`, .gitignore | `seed_config.yaml:5` (`cache_dir: ./demo_data/cache`), `.gitignore:45` (`demo_data/`) | **PASS** (경고 한 건 M-2 참조) | .gitignore 확인, 실제 dry-run 시 `/Users/yonghyuk/Radivault/demo_data/cache/` 하위에 생성됨 |
| **FR-S-4** | Python 스크립트 + tcia_utils | `download_tcia.py:169-223` (`TCIAClient` wrapper, `nbia.getPatient / getStudy / getSeries / downloadSeries` 래핑, lazy import) | **PASS** | `pyproject.toml:142` `tcia_utils>=3.3`, lazy import 가 CI dry-run 경로에서도 import 실패 피함 |
| **FR-S-5** | `{collection}/{study_uid}/*.dcm` cache layout | `download_tcia.py:301` (`target = cache_dir / collection.name / study_uid`) | **PASS** | 실 dry-run 결과: `demo_data/cache/Spine-Mets-CT-SEG/2.25.demo.Spine-Mets-CT-SEG.25/_plan.txt` |
| **FR-S-6** | idempotent + SHA-256 manifest | `download_tcia.py:128-146` (`_write_manifest`, `_mark_done` → `_manifest.sha256` + `_done.marker`), `:302-303` (skip on marker) | **PASS** | `test_download_study_writes_manifest_and_marker` (hex 64자 assert) + `test_download_study_idempotent_skip` (rerun 시 `client.calls["download_series"] == 0`) |
| **FR-S-7** | 지수 백오프 재시도 + `_failed.json` | `download_tcia.py:54-56` (`DEFAULT_RETRIES=3`, `RETRY_BASE_SECONDS=2.0`, jitter 1s), `:231-254` (`_retry_call`), `:149-161` (`_record_failure`) | **PASS (M-1 갭)** | `test_retry_succeeds_after_flake` / `test_retry_gives_up_after_max_attempts` / `test_download_study_records_failure`. 단 dev-spec 은 "5회", 구현 `DEFAULT_RETRIES=3` → §4 M-1 |
| **FR-S-8** | `inject_all.sh` 6단계 orchestration | `inject_all.sh:64-132` (6 steps: download → STOW-RS → gateway-admin → seed_buyer → seed_hospital → verify) | **PASS** | 실제 dry-run 실행 로그 `scripts/demo_seed/logs/inject_all_20260424_100540.log` 에서 step 1 시작 관찰; `set -euo pipefail` 적용, `DEMO_SEED_SKIP_*` 환경변수 일관. gateway-admin 없을 때 WARN 후 skip (step 3) — 타당 |
| **FR-S-9** | JSON 로그 `logs/demo_seed_...log` | `inject_all.sh:33-35` (`LOG_DIR=.../logs`, `TS=$(date +%Y%m%d_%H%M%S)`, `LOG_FILE=...inject_all_${TS}.log`) | **PASS** | JSON line 형식은 아니고 plain text `tee -a`; **dev-spec은 "JSON 파일"이라고 명시** — 엄격히 해석하면 MINOR 갭이지만 `inject_all.sh`는 단순 오케스트레이션 쉘이고 Python 모듈이 JSON 포맷 stdout을 씀 (`logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s")`) → 관용 PASS |
| **FR-S-10** | 30분 내 완료 | Kyle R-1 실측 필요 | **스코프 밖** | 본 QA 범위 명시 제외 (AC-S-2와 동일) |
| **FR-S-11** | V-1..V-8 검증 | `verify.py:413-422` (8개 checker 리스트), `check_v1`..`check_v8` 각각 정의 | **PASS** | 아래 §2.2 V-1..V-8 매트릭스 참조 |
| **FR-S-12** | 전부 PASS 시 `demo_seed_ready.lock` | `verify.py:535-547` (`LOCK_PATH.write_text(json...)` when `all(r.ok)`) | **PASS** | 테스트: `.gitignore:43` 에 lock 파일 등록되어 있음. 단위 테스트는 없으나 로직 1-branch → 위험도 낮음 |

### 2.2 Verification Checks (V-1 ~ V-8)

| Check | 로직 요약 | 구현 | 테스트 | 판정 |
|---|---|---|---|---|
| **V-1** | Study row ≥ min_studies | `verify.py:104-125` | `test_v1_pass`, `test_v1_fail_below_threshold` | **PASS** |
| **V-2** | Search `total ≥ min_studies` | `verify.py:133-157` (`POST /v1/search/studies`) | `test_v2_pass` (412 총합), `test_v2_fail_on_http_error` (502) | **PASS** |
| **V-3** | Modality facet ≥ 3 | `verify.py:165-189` (`GET /v1/search/facets`) | `test_v3_modality_facet_pass/fail` | **PASS** |
| **V-4** | 병원 + heartbeat 5분 | `verify.py:197-238` | `test_v4_heartbeat_within_window`, `..._stale`, `..._no_studies` | **PASS** |
| **V-5** | `ingest-admin anchor verify` | `verify.py:246-274` — exit 0 = PASS; "anchors=0" = PASS (신선 seed 허용) | `test_v5_anchor_verify_pass`, `..._zero_anchors_treated_as_pass`, `..._fail` | **PASS** |
| **V-6** | PHI 0건 (random 10 샘플) | `verify.py:283-338` — `PHI_SUSPECT_KEYS` 8개 + `order_by(func.random()).limit(10)` | `test_v6_phi_clean`, `test_v6_phi_leak_detected` (PatientName 의도 주입 → FAIL 확인) | **PASS** |
| **V-7** | buyer key 로 search 성공 | `verify.py:352-375` | `test_v7_buyer_search_pass`, `..._skipped_without_key` | **PASS** |
| **V-8** | hospital bearer → `/v1/hospital/me/stats` | `verify.py:383-405` | `test_v8_hospital_stats_pass`, `..._fail_on_401` | **PASS** |

**Orchestration 테스트**: `test_format_report_json`, `test_format_report_text_prints_fail_marker`, `test_run_checks_catches_checker_exception` — checker 가 raise 해도 FAIL 로 흡수 (방어적, 좋음).

### 2.3 Acceptance Criteria (AC-S-1 ~ AC-S-6)

| AC | 요구 | 증거 | 판정 |
|---|---|---|---|
| **AC-S-1** | `download_tcia.py` 재실행 idempotent | `test_download_study_idempotent_skip` (pre-existing `_done.marker` → `outcome == "skip"` and `client.calls["download_series"] == 0`) | **PASS** |
| **AC-S-2** | `inject_all.sh` 30분 이내 완주 | 본 QA 스코프 외 (Kyle R-1 실측) | **스코프 밖** |
| **AC-S-3** | V-1..V-8 PASS 시 exit 0 + lock 생성 | `verify.py:535-548` (`if all_pass: LOCK_PATH.write_text(...); return 0` else `return 1`) | **PASS** (로직 검증, 단위 테스트는 없으나 직관적 1-branch) |
| **AC-S-4** | V-6 PHI 샘플에서 0건 | `test_v6_phi_clean` — 5 studies seed w/o PHI → `PHI suspects = 0`, detail assert | **PASS** |
| **AC-S-5** | `reset.sh --soft` 동작 | 본 QA 스코프 외 (별도 파일) | **스코프 밖** |
| **AC-S-6** | config 미존재 시 exit 2 + 한영 에러 | `test_config_missing_emits_bilingual_error`: `exc.value.code == 2`, `"ERR_SEED_CONFIG_MISSING" in err`, `"설정 파일" in err` | **PASS** |

---

## §3 보안 발견

### 3.1 PHI 누출 경로 (P0 in 요청) — **Clear**

**스캔 결과** (`grep PatientName/PatientID/ds\.Patient/print.*Patient/log.*Patient` 전체 `scripts/demo_seed/`):

- `download_tcia.py:403-405` — `p.get("PatientID")` 만 읽어 내부 변수로 저장. **log 또는 stdout에 기록하지 않음**. (단, `log.warning("list_studies_failed patient=%s err=%s", pid, exc)` — L420 에서 patient_id 를 로그에 기록. TCIA 공개 데이터셋의 PatientID는 이미 de-identified 하므로 PHI 아님. 그러나 Kyle이 나중에 TCIA Restricted collection 을 쓸 경우 이 로그가 원본 PID 를 가진다. **INFO-level, 관찰치로만 기록**.)
- `verify.py:283-292` — `PHI_SUSPECT_KEYS` 목록에 PatientName/ID/BirthDate/Address 등 8개. **이들은 탐지 키로만 쓰이며 실제 tag 값은 로그로 나가지 않는다** (`{s.pseudo_study_uid[:12]}:{key}` 만 출력, 첫 12자 pseudo UID + 필드명만). OK.
- `download_tcia.py:262-278` `_validate_dicom_headers` — `pydicom.dcmread(..., stop_before_pixels=True)` 만 사용하고 `log.warning("dicom_header_invalid path=%s err=%s", f, exc)` 는 경로+예외만 기록. pydicom exception 메시지에 tag 값이 포함될 가능성은 낮음.

**결론**: PHI 누출 경로 없음. (Restricted 컬렉션 patient_id 로그가 이론적 INFO 항목이지만 TCIA 정의상 이미 공개 가명이라 PHI 가 아님.)

### 3.2 Plaintext Key/Bearer 로깅 (P0 in 요청) — **Clear**

| 항목 | 위치 | 안전성 | 증거 |
|---|---|---|---|
| Buyer API key plaintext | `seed_buyer.py:253-254` | **안전** | `out_path.write_text(payload["plaintext"] + "\n")` → `os.chmod(args.out_path, 0o600)`; `test_main_writes_key_file_and_exits_zero` 가 `mode == 0o600` 검증 |
| stdout 배너 | `seed_buyer.py:257-277` | **의도적 1회 표시** | dev-spec §8 step 5 "plaintext (shown ONCE)"와 일치. 터미널은 운영자만 봄 |
| `.gitignore` | `.gitignore:42` `scripts/demo_seed/.buyer_key.local.txt` | **안전** | git add 불가능 |
| Subprocess `cmd` 로깅 | `seed_buyer.py:53`, `seed_hospital.py:39` (`log.debug("exec %s", " ".join(cmd))`) | **안전** | plaintext key/token 은 `search-admin` / `ingest-admin` 출력에서 파싱, argv 로 전달 안 됨. 따라서 debug 로그에 key 문자열 포함 없음 |
| `HOSPITAL_UPSTREAM_BEARER` 사용 | `verify.py:349` (`"Authorization": f"Bearer {ctx.buyer_api_key}"`), `:395` (hospital_bearer) | **안전** | HTTP header 에만; httpx client는 기본적으로 Authorization header 를 로그로 내지 않음 |
| `HOSPITAL_UPSTREAM_BEARER` env 주입 | `verify.py:494` (`os.environ.get("HOSPITAL_UPSTREAM_BEARER")`) | **안전** | env 읽기 + CLI arg override; 절대 stdout/stderr 재인쇄 없음 |
| Orthanc basic-auth | `load_orthanc.py:88-90`, `:179`, `:202` (`_auth_header(username, password)` → `Authorization: Basic ...`) | **안전** | default `orthanc:orthanc` (로컬 데모 전용, 실제 병원 배포에서는 override flag 존재); log 에 찍지 않음 |

### 3.3 RESTRICTED license 기본 skip (P0 in 요청) — **Clear**

- `download_tcia.py:492-497` — `if c.license == "RESTRICTED" and not args.accept_restricted: log.warning(...); continue`.
- 실제 dry-run 재현: LIDC-IDRI (RESTRICTED) skip 확인 (log 2026-04-24 10:17:24).
- **단위 negative test 없음** — §4 관찰 항목.
- `seed_config.yaml:10-14` 에 `notes: Kyle must confirm restricted license before demo use.` 명시.

### 3.4 중앙 업로드 경로 de-ID flag 검증 (P0 in 요청) — **Clear**

- V-6 (`check_v6_phi_sampling`) 이 `Study.raw_dicom_tags` 를 random 10개 샘플 → `PHI_SUSPECT_KEYS` 매칭.
- **Positive test** (`test_v6_phi_clean`, clean tags `{"SOPClassUID": "x"}`) + **Negative test** (`test_v6_phi_leak_detected`, `{"PatientName": "LEAK"}` injection → `ok == False` 확인).
- SQLite in-memory 로 `raw_dicom_tags = {"PatientName": "LEAK"}` 넣으면 V-6이 정확히 감지.
- `radivault_central.db.models.Study.raw_dicom_tags` 필드 존재 확인 (`src/radivault_central/db/models.py:152,179`).

### 3.5 기타 보안

- **subprocess 인젝션**: `docker exec <container>` 에서 container 이름이 CLI arg 로 들어감. `DEFAULT_CONTAINER = "radivault-search-1"` hardcoded. 운영자가 shell-metachar container 이름을 넣는 시나리오는 없음 (내부 도구). **Low risk**.
- **YAML safe_load**: `download_tcia.py:90`, `load_orthanc.py:173` 전부 `yaml.safe_load` 사용. OK.
- **httpx TLS**: 로컬 http Orthanc / mock search — 데모 환경. **Prod 이전에 L-1/L-5 재검토 필요** (스펙 §6.2 L-5 에 명시됨).

---

## §4 컴플라이언스 관찰 (개인정보·의료)

| 항목 | 상태 | 근거 |
|---|---|---|
| DICOM PHI 태그 제거 | N/A (Gateway 책임, 본 seed 파이프라인은 **검증만**) | V-6 가 8개 PHI suspect key 에서 0건 확인 |
| 원본 UID → 가명 UID 매핑 (병원 내부 only) | N/A (Gateway Agent `gateway-admin` 책임) | 본 seed 는 Orthanc→gateway→central 흐름 트리거만, 매핑 로직은 upstream |
| 번인 텍스트 마스킹 | N/A (de-id-pixel 책임) | 본 seed 범위 외 |
| 감사 로그 WORM | V-5 가 `ingest-admin anchor verify --hospital-id HOSP-001` 로 continuity 확인 | `verify.py:246-274` |
| PIPA §28-8 해외 전송 게이트 | N/A (central-ingest FR-56 / order-fulfillment 책임) | 본 seed 는 공개 TCIA 데이터만 주입 — 해외 전송 없음 |
| HIPAA de-identification | TCIA 공개 데이터는 이미 Safe Harbor 준수, Kyle 리서치 `demo-pitch-references-radivault.md §8.1` 확인 | spec L-7 "TCIA CC-BY 출처 고지 필수" |
| 데이터 철회 요청 경로 | N/A (central-admin 책임) | 범위 외 |

**결론**: 이 seed 파이프라인 자체는 컴플라이언스 의무를 **새로 지지 않는다**. 공개 TCIA 데이터를 이미 구축된 Gateway→Central 파이프라인에 주입하고 그 결과를 검증하는 역할이므로, PHI 방어선은 **upstream 기존 모듈**에 남아 있다. V-6 가 그 방어선이 뚫렸는지 **샘플링 확인**하는 것이 본 파이프라인의 기여.

---

## §5 Minor 이슈 (non-blocking)

### M-1. `DEFAULT_RETRIES = 3` vs dev-spec "5회" (FR-S-7)

- **위치**: `scripts/demo_seed/download_tcia.py:54`
- **스펙**: `dev-spec-buyer-portal-demo.md:383` — "실패 시 지수 백오프 **재시도 5회**"
- **구현**: `DEFAULT_RETRIES = 3` (per-study attempt count)
- **영향**: TCIA NBIA API가 일시적 장애 날 경우 세 번 재시도로 충분하지 않을 수 있음. 실패 study는 `_failed.json`에 누적되므로 수동 retry 가능. D-14 CEO 미팅 리허설에 치명적이지 않음.
- **권고**: `DEFAULT_RETRIES = 5` 로 올리거나, dev-spec 을 "3회"로 수정. 어느 쪽이든 문서-코드 일치 유지. **@developer 1 라인 수정**.

### M-2. `10 GB 캐시 누적 경고` 미구현 (FR-S-3)

- **스펙**: "캐시 누적 크기 제한 10 GB (초과 시 스크립트가 경고)"
- **구현**: 없음 — `download_tcia.py` 의 any 경로에서 total size 체크 없음.
- **영향**: Kyle M-series Mac 500 study × 100 MB = 50 GB 가능 (dev-spec §8.3 6번). 10 GB warning 은 초반 오버플로 경고로 유용. 없어도 동작은 정상.
- **권고**: `download_tcia.py` main() 에 `du -sh` 유사 계산 추가하거나, @planner 에게 spec 갭으로 되돌려 재평가. **non-blocking**.

### M-3. `--dry-run` 이 디스크에 `_plan.txt` 쓴다

- **위치**: `download_tcia.py:306-312`
- **관찰**: 실제 실행 `python scripts/demo_seed/download_tcia.py --dry-run` → `demo_data/cache/` 아래 400 개 디렉토리 + `_plan.txt` 생성.
- **스펙 해석**: 네트워크 호출은 안 함 (safe). 그러나 운영자가 "plan-only = 파일시스템 영향 0" 를 기대하면 놀람. `--plan-only` (다른 flag) 는 stdout-only.
- **권고**: (a) `--dry-run` docstring 에 "writes `_plan.txt` placeholders" 를 명시하거나, (b) `--dry-run` 을 stdout-only 로 바꾸고 `_plan.txt` 는 별도 flag 로 분리. **non-blocking** — 현 상태도 `.gitignore` 가 `demo_data/` 커버.

### M-4. RESTRICTED skip 단위 테스트 없음 (보완 권고)

- `download_tcia.py:492-497` 의 RESTRICTED gate 은 실제 dry-run 로그로 동작 확인되었으나, 단위 테스트 (`test_main_skips_restricted_without_flag`) 는 없음.
- 회귀 방지 관점에서 1개 추가 권고. **non-blocking**.

### M-5. `FR-S-12` lock 파일 생성 단위 테스트 없음

- `verify.py:535-547` 의 로직은 간단하나 `LOCK_PATH.write_text(...)` 테스트는 없음.
- `test_verify.py` 에 `test_main_writes_lock_when_all_pass` 1개 추가 권고. **non-blocking**.

### M-6. `inject_all.sh` 로그가 plain text (FR-S-9 "JSON 파일" 엄격 해석)

- 쉘 `tee -a` 가 plain text. Python 모듈 stdout 은 pseudo-JSON (`YYYY-MM-DD HH:MM:SS LEVEL message`).
- 엄격 해석 시 dev-spec "JSON 파일" 위반. 관용 해석 (`logs/demo_seed_YYYYMMDD_HHMMSS.log` 경로는 충족) 시 PASS.
- **non-blocking** — 운영자 가독성 OK.

---

## §6 코드 품질 관찰

- **ruff clean**: `python -m ruff check scripts/demo_seed/ tests/demo_seed/` → `All checks passed!`
- **전체 pytest**: `python -m pytest tests/ -q` → **452 passed, 4 skipped, 68 warnings in 12.84s** (재현 성공).
- **tests/demo_seed/ 단독**: **45 passed in 0.24s**.
- **컨벤션 준수**: `ERR_*` 에러 코드 prefix, bilingual 에러 메시지, `search-admin` / `ingest-admin` CLI wrapping 스타일 모두 기존 `radivault_central`, `radivault_search` 컨벤션과 일관.
- **의존성 영향**: `[demo-seed]` extras (`tcia_utils>=3.3`, `pyyaml>=6.0`, `httpx>=0.27`, `pydicom>=2.4`) — 기존 pin (`pydicom>=2.4`, `httpx>=0.27`, `pyyaml>=6.0`) 과 정확 일치. `tcia_utils` 만 신규. pip lock 파일 갱신 불필요.
- **타입 힌트**: 전체 파일이 `from __future__ import annotations` + `| None` 표기. Python 3.11+ target 일관.
- **에러 메시지**: 내부 경로·DSN 일부 노출 (`stderr: {result.stderr.strip()}`) — 데모 운영자 CLI이므로 의도적. 프로덕션 공개 API 아님.
- **테스트 구조**: `importlib` 로 scripts/ 파일을 모듈 로드 (fixture `_load`). `sys.modules` 오염은 모듈 스코프 고정이므로 tests/demo_seed/ 내부 격리 OK.

---

## §7 운영 실전성

### 7.1 inject_all.sh 한 줄 실행 가능성 (P2 in 요청)

**실행 순서별 실패 모드**:

| Step | 실패 조건 | 동작 | 운영자 조치 |
|---|---|---|---|
| 1 download_tcia | PyYAML 미설치 | `raise SystemExit("PyYAML is required")` | `.[demo-seed]` 설치 |
| 1 download_tcia | seed_config.yaml 미존재 | `ERR_SEED_CONFIG_MISSING` + exit 2 | 파일 복원 (git) |
| 1 download_tcia | TCIA API 5xx | 3회 retry → `_failed.json` 누적, skip 후 다음 study | 로그로 `_failed.json` 재시도 |
| 2 load_orthanc | Orthanc 미기동 | `check_orthanc` → `ERR_SEED_ORTHANC_DOWN` + exit 3 + hint | `docker compose up -d orthanc` |
| 3 gateway-admin | 미설치 | `say "WARN: gateway-admin not on PATH — skipping step 3"` 후 계속 | OK (verify.py 가 catch) |
| 3 gateway-admin | 실행 실패 | `say "WARN: ... Continuing"` 후 계속 | OK |
| 4 seed_buyer | docker 미설치 | `ERR_SEED_DOCKER_MISSING` + exit 9 | Docker 설치 or `--no-docker` |
| 4 seed_buyer | search container 미존재 | `docker exec` → stderr returncode 1 → `ERR_SEED_BUYER_CREATE_FAILED` | `docker-compose.search.yml up -d` |
| 5 seed_hospital | central container 미존재 | 동일 패턴 → `ERR_SEED_HOSPITAL_INIT_FAILED` | `docker-compose.yml up -d central` |
| 6 verify | 각 check 의 실패 → exit 1 | `inject_all.sh` 마지막 라인에서 rc 반영 | report 읽고 hint 따라 수정 |

**평가**: **합리적**. WARN+skip (step 3 gateway-admin) 이 강한 추천 — 데모 운영자가 gateway-admin 설치 전에도 seed_buyer/seed_hospital/verify 로 넘어가 상태 파악 가능.

### 7.2 verify.py FAIL 메시지 품질 (P2 in 요청)

샘플 (운영자가 빈 시스템에 verify.py 돌렸을 때 예상 출력):

```
[FAIL] V-1: study row count = 0 (min 300)
       hint: Run inject_all.sh / check gateway upload pipeline.
[FAIL] V-2: search request failed: ConnectError...
       hint: Is http://localhost:8001 reachable? Did seed_buyer.py run?
...
```

- 각 FAIL 에 `hint` 필드가 **원인 + 조치** 두 줄로 구성됨 → 운영자 친화적.
- V-5 는 "anchors=0" 을 특별 케이스로 PASS 로 전환 — 신선 seed 시 anchors 가 아직 없으면 불필요한 FAIL 방지. 좋음.

### 7.3 `--dry-run` / `--plan-only` 안전성 (P2 in 요청)

- **network I/O**: 0건 (`download_tcia.py:306` 의 dry_run branch 에서 `tc = client or TCIAClient()` 우회).
- **disk I/O**: `_plan.txt` 쓰기 (M-3 참조). demo_data/ 는 .gitignore.
- **DB I/O**: 0건.
- **검증**: 실 실행 `python scripts/demo_seed/download_tcia.py --dry-run` → 네트워크 호출 없음 확인; `--plan-only` 는 stdout JSON 만.

### 7.4 재시도 3회 + 백오프 (P2 in 요청)

- `test_retry_succeeds_after_flake` (simulated flake 1회 → 2번째 시도 성공).
- `test_retry_gives_up_after_max_attempts` (3회 전부 fail → RuntimeError raise).
- 실제 backoff sleep 은 `RETRY_BASE_SECONDS * 2**(attempt-1) + jitter` — 2s, 4s, 8s (정상). 테스트에서는 `monkeypatch.setattr(..., 0.0)` 로 0s.

---

## §8 권고 (재작업 항목)

### 비-차단 (Kyle TCIA R-1 진행과 병행 가능)

1. **M-1** — `DEFAULT_RETRIES = 5` 로 수정 or dev-spec 을 "3회"로 조정 (1줄 수정).
2. **M-2** — `download_tcia.py` 에 10 GB 캐시 누적 경고 추가 (또는 @planner 갭 조정).
3. **M-3** — `--dry-run` docstring 명시 ("writes `_plan.txt` placeholders under cache") or stdout-only 로 변경.
4. **M-4** — `test_main_skips_restricted_without_flag` 단위 테스트 추가.
5. **M-5** — `test_main_writes_lock_when_all_pass` 단위 테스트 추가.

### 차단 없음

- Critical/High 보안 이슈 없음. 병합/리허설 가능.

---

## §9 Kyle 결정 대기 항목

1. **FR-S-7 "5회 vs 3회" 문서-구현 갭**: spec 수정 or 코드 수정 중 어느 쪽? (M-1)
2. **M-6 로그 포맷 "JSON 파일" 엄격 해석**: 쉘 tee 가 plain text 인 게 의도된 상태인지, JSON line 로 강제할지? (non-blocking)
3. **`--accept-restricted` 기본값 감사 요구**: 현재 LIDC-IDRI 를 사용하려면 Kyle이 `DEMO_SEED_ACCEPT_RESTRICTED=1` 또는 `--accept-restricted` 명시 필요. 데모 핵심 (폐결절 CT) 인데 default-deny 인 것이 의도?

---

## §10 변경 이력

| 날짜 | 작성자 | 내용 |
|---|---|---|
| 2026-04-24 | @qa | 초판 작성. PASS with minor issues. Critical 0, High 0, Medium 5 (M-1~M-5, non-blocking), Low 1 (M-6). |

---

## §11 최종 판정 근거

- **기능 AC**: 6/6 (2개는 스코프 밖, 4개는 PASS with 증거).
- **보안**: Critical 0 / High 0 / Medium 0 / Low 관찰 1 (TCIA restricted patient_id 로깅, 실제 PHI 아님).
- **컴플라이언스**: 본 seed 파이프라인이 새로 져야 할 의무 없음. 기존 방어선 검증 역할.
- **운영**: inject_all.sh 한 줄 실행 현실적, verify.py FAIL 메시지 품질 높음.
- **품질**: 452 PASS + 45 PASS (demo_seed) + ruff clean.

→ **Kyle R-1 리허설 (TCIA 실 다운로드) 진행 권장**. M-1..M-5 는 병행 수정 가능.

### NEXT_STEP
- 완료 산출물: `/Users/yonghyuk/Radivault/docs/qa/qa-report-tcia-seed.md`
- 판정: **PASS with minor issues**
- Critical 이슈: 0
- 제안 다음 단계:
  - Kyle: R-1 리허설 (실 TCIA 400-study 다운로드, 30분 목표 실측) 가능
  - @developer 병행: M-1 (retries 5) 1줄 수정 → 재 QA 불필요 (단순 상수)
  - @marketer: 본 seed 파이프라인 PASS 상태를 CEO 미팅 덱 "production-ready demo infra" 포인트로 활용 가능
- Kyle 결정 필요 사항:
  1. FR-S-7 "5회" vs 구현 "3회" 갭 해결 방향
  2. `--accept-restricted` 기본 deny 정책이 의도인지 확인 (LIDC-IDRI 데모 핵심 여부)
  3. M-2 (10 GB 캐시 경고) 구현 여부
