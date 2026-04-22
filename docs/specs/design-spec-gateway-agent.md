# 디자인 명세 — Gateway Agent v0.1 MVP (CLI · Config · Log UX)

> **Status**: Draft v0.1 · **Feature slug**: `gateway-agent` · **Last updated**: 2026-04-22
> **작성자**: @designer · **근거**: [dev-spec](./dev-spec-gateway-agent.md), [UI Guide](../UI_GUIDE.md), [리서치 — 기술 기반](../research/gateway-agent-technical-foundations.md)

---

## 0. 범위 선언 (Scope Statement)

본 문서는 통상의 GUI 디자인 명세가 **아니다**. Gateway Agent는 병원 전산실에 배포되는 **백엔드 전용 CLI 도구**로 웹/데스크톱 UI가 존재하지 않는다. 그럼에도 "운영자가 실제로 마주하는 표면"은 존재하며, 본 문서는 그 표면의 UX를 정의한다.

**디자인 대상 표면 5종**

1. **CLI 명령 트리** — 서브커맨드, 플래그, `--help`, 종료 코드
2. **Config 파일** — YAML 스키마, 주석, 검증 에러 메시지
3. **로그 출력** — 콘솔(TTY/Docker logs), JSON-lines audit log
4. **`status` 출력** — 1화면 요약의 ASCII 박스 UI
5. **설치·온보딩 워크스루** — 병원 IT 담당자 관점 첫 배포 플로우

**디자인 대상 아닌 것**: 웹 포털, 데스크톱 앱, 모바일 앱, 대시보드, 알림 UI.

표준 design-spec 템플릿의 일부 항목(반응형·색 대비·디자인 토큰·스크린리더)은 CLI 도구 성격상 적용되지 않아 "N/A — CLI tool"로 표기한다.

---

## 1. 디자인 개요

병원 IT 담당자가 **Docker Compose 한 줄**과 **`gateway-agent` CLI 몇 개 명령**만으로 RadiVault 파일럿에 참여할 수 있도록, 설치부터 일상 운영·장애 대응까지 전 과정을 CLI/Config/Log 세 표면에서 일관되게 전달하는 것이 목적이다. 언어·배경 지식이 불균일한 사용자를 위해 **이중 언어(ko+en) 에러 메시지**와 **기계 가독 JSON audit log** 를 동시 제공한다.

---

## 2. 사용자 (Users)

### 2.1 Primary — 병원 IT 운영자 (병원 전산실 담당자)

- **언어**: 한국어 모국어.
- **기술 수준**: Linux 기본(`systemctl`, `docker`, `vi`). Python·DICOM은 비전문가.
- **목표**: 한 번 설치 후 알람 없이 작동. 문제 발생 시 **에러 코드 하나로 구글/사내 위키 검색** 가능해야 함.
- **안 해도 되는 일**: 파이썬 코드 읽기, JSON 수동 파싱, DICOM 태그 해석.
- **반드시 해야 하는 일**: YAML 편집, `docker compose up/down`, `systemctl status/restart`, `gateway-agent status` 조회, 에러 스크린샷·로그 파일 수집해 RadiVault 지원팀에 전달.

### 2.2 Secondary — RadiVault 지원 엔지니어 / 개발자

- **언어**: 한국어/영어 혼용.
- **목표**: 원격(SSH/전화)으로 장애 분석, 체인 검증, ruleset 업그레이드 영향도 점검.
- **요구**: 구조화 로그(JSON), deterministic 에러 코드, 기계 파서블 `status --json` 출력(v0.1 범위), 감사 체인 검증 도구.

### 2.3 Non-user

- 방사선의·연구자·구매자·환자. Gateway Agent는 이들에게 노출되지 않는다(익명화된 결과만 중앙을 통해 도달).

---

## 3. CLI 명령 트리 (Command Tree)

### 3.1 전체 구조

```
gateway-agent
├── start                              데몬 모드 (foreground)
├── sync-once [--since] [--until]      1회성 수동 동기화
│           [--dry-run]
├── status [--json] [--watch]          현재 상태 요약
├── de-id-test <input.dcm>             단일 파일 익명화 드라이런
│            [--output <path>]
│            [--show-diff]
├── audit
│   └── verify <audit.log>             감사 체인 무결성 검증
└── version                            버전 정보
```

**전역 플래그**

| 플래그 | 설명 |
|--------|------|
| `-c, --config <path>` | 기본 `/etc/radivault/gateway.yml` 또는 `$RADIVAULT_CONFIG` |
| `--log-level <level>` | `DEBUG \| INFO \| WARN \| ERROR` (설정 override) |
| `--no-color` | ANSI 색 비활성 (§9 접근성) |
| `--quiet` | WARN 이하 억제 |
| `-h, --help` | 해당 명령 도움말 |
| `-V, --version` | `version` 서브커맨드와 동일 |

### 3.2 `gateway-agent --help` (최상위)

```
$ gateway-agent --help
RadiVault Gateway Agent — PACS → De-ID → Central Upload
병원 내 DICOM 익명화 게이트웨이 / Hospital on-premise DICOM de-identification gateway

Usage:
  gateway-agent [GLOBAL OPTIONS] COMMAND [ARGS]...

Commands:
  start           Run as a foreground daemon (주기 동기화 데몬 실행)
  sync-once       One-shot synchronisation run (1회성 동기화)
  status          Show agent status summary (상태 요약)
  de-id-test      Dry-run de-identification on a single DICOM (단일 파일 테스트)
  audit verify    Verify the audit log hash chain (감사 로그 체인 검증)
  version         Print agent version and build info (버전 정보)

Global Options:
  -c, --config PATH         Path to config YAML  [default: /etc/radivault/gateway.yml]
      --log-level LEVEL     DEBUG | INFO | WARN | ERROR
      --no-color            Disable ANSI colour output
      --quiet               Suppress INFO-level output
  -h, --help                Show this message and exit
  -V, --version             Show version and exit

Docs:   https://docs.radivault.io/gateway-agent
Issues: https://github.com/radivault/gateway-agent/issues
```

### 3.3 `gateway-agent start`

**Invocation pattern**

```
gateway-agent start [--oneshot] [--poll-interval <seconds>]
```

**`--help`**

```
$ gateway-agent start --help
Usage: gateway-agent start [OPTIONS]

  Run the agent as a foreground daemon. Polls PACS every
  pacs.poll_interval_seconds (default 300s) and drains the upload queue.
  주기 동기화 데몬으로 실행합니다. 기본 300초마다 PACS 폴링.

Options:
  --oneshot                   Exit after one full sync cycle (단회 사이클 후 종료)
  --poll-interval INTEGER     Override poll interval in seconds (설정 override)
  -h, --help                  Show this message and exit

Signals:
  SIGTERM / SIGINT            Graceful shutdown; finishes in-flight uploads
  SIGHUP                      Reload config without restart (v0.2; v0.1은 미지원)

Exit codes:
  0   Clean shutdown
  64  Config validation error (EX_USAGE)
  69  PACS unreachable at startup (EX_UNAVAILABLE)
  70  Internal error (EX_SOFTWARE)
```

**Happy-path 콘솔 출력 예시 (TTY, 색상 있음 — 아래는 흑백 텍스트)**

```
2026-04-22T01:03:12Z  INFO  radivault.cli            starting gateway-agent v0.1.0 (build=ab12cd3)
2026-04-22T01:03:12Z  INFO  radivault.config         loaded /etc/radivault/gateway.yml (version=1)
2026-04-22T01:03:12Z  INFO  radivault.identity       gateway_id=gw_7f3a9c hospital_id=hosp_abc
2026-04-22T01:03:12Z  INFO  radivault.pacs           health_check ok base_url=https://pacs.hospital.local/dicom-web
2026-04-22T01:03:12Z  INFO  radivault.central        health_check ok base_url=https://ingest.radivault.io
2026-04-22T01:03:13Z  INFO  radivault.scheduler      poll_interval=300s concurrency=4
2026-04-22T01:03:13Z  INFO  radivault.scheduler      tick #1 start
2026-04-22T01:03:15Z  INFO  radivault.pacs           qido returned 12 studies (lookback=7d)
2026-04-22T01:03:15Z  INFO  radivault.scheduler      new=3 pending=0 quarantined=0
2026-04-22T01:03:18Z  INFO  radivault.pipeline       study=2.25.xxxx fetch ok (184 instances, 94.3MB, 2.1s)
2026-04-22T01:03:22Z  INFO  radivault.pipeline       study=2.25.xxxx deid ok (4.1s)
2026-04-22T01:03:22Z  INFO  radivault.pipeline       study=2.25.xxxx upload ok job_id=ingest_01HXXXX (3.7s)
```

**에러 시나리오**

| 상황 | 종료 코드 | 메시지 (발췌) |
|------|-----------|----------------|
| Config 파싱 실패 | 64 | `ERR_CFG_001 설정 파일을 파싱할 수 없습니다. / Cannot parse config file.` |
| 필수 키 누락 | 64 | `ERR_CFG_002 필수 설정 키가 없습니다: pacs.base_url / Required config key missing.` |
| PACS 기동 health check 실패 | 69 | `ERR_PACS_010 PACS에 연결할 수 없습니다. / Cannot reach PACS.` |
| Central health check 실패 (경고만, 종료 안 함) | — | `WARN_CENT_001 중앙 ingest 엔드포인트 미응답, 큐잉 계속. / Central endpoint unreachable, queuing.` |
| Staging 디스크 90% 초과 | 0(backpressure) | `WARN_STG_001 staging 사용률 90% 초과, 신규 페치 일시중단. / Staging disk > 90%, pausing new fetches.` |
| Salt 파일 없음 | 64 | `ERR_CFG_010 salt 크리덴셜 파일이 없습니다: /run/credentials/salt / Salt credential file missing.` |

### 3.4 `gateway-agent sync-once`

```
$ gateway-agent sync-once --help
Usage: gateway-agent sync-once [OPTIONS]

  Run one synchronisation cycle and exit. Useful for cron or manual backfill.
  1회성 동기화. cron 또는 수동 백필에 사용.

Options:
  --since DATE    Start of StudyDate range (YYYY-MM-DD)  [default: today-lookback_days]
  --until DATE    End of StudyDate range (YYYY-MM-DD)    [default: today]
  --dry-run       Fetch + de-identify but do NOT upload (로컬 검증만)
  --limit INT     Cap at N studies for this run
  -h, --help      Show this message and exit

Exit codes:
  0   All studies in range reached state=uploaded (or quarantined per policy)
  1   One or more studies failed (see `gateway-agent status`)
  64  Config validation error
```

**Happy-path 출력**

```
$ gateway-agent sync-once --since 2026-04-15 --until 2026-04-21
[1/12] 2.25.aaaa  fetch 2.1s  deid 4.1s  upload 3.7s  OK
[2/12] 2.25.bbbb  fetch 1.8s  deid 3.9s  upload 3.2s  OK
[3/12] 2.25.cccc  fetch 2.3s  deid 4.4s  QUARANTINED (BurnedInAnnotation=YES)
...
[12/12] 2.25.llll fetch 1.9s  deid 4.0s  upload 3.4s  OK

Summary  uploaded=10  quarantined=1  failed=1  elapsed=52.4s
1 study failed — run `gateway-agent status` for details.
```

**`--dry-run` 출력**

```
$ gateway-agent sync-once --dry-run --limit 1
[1/1] 2.25.aaaa  fetch 2.1s  deid 4.1s  UPLOAD-SKIPPED (--dry-run)
      staging path: /var/lib/radivault/staging/2.25.pseudoxxxx
      manifest: 184 files, 94.3 MB, sha256 OK
Dry-run succeeded. No data was sent to central.
```

### 3.5 `gateway-agent status`

(상세 레이아웃은 §6 참조)

```
$ gateway-agent status --help
Usage: gateway-agent status [OPTIONS]

  Print a one-screen summary of the agent. Always read-only.
  에이전트 상태 요약 출력 (읽기 전용).

Options:
  --json         Emit machine-readable JSON instead of the ASCII box
  --watch        Refresh every 2s until Ctrl-C (top-like)
  -h, --help     Show this message and exit

Exit codes:
  0   Status retrieved successfully
  1   State DB not accessible
```

### 3.6 `gateway-agent de-id-test`

```
$ gateway-agent de-id-test --help
Usage: gateway-agent de-id-test INPUT [OPTIONS]

  Dry-run de-identification on a single DICOM file. Prints remaining PHI
  tag scan result. Never writes to staging or uploads.
  단일 DICOM 파일 드라이런. PHI 잔존 태그 리포트. 스테이징/업로드 없음.

Arguments:
  INPUT            Path to input .dcm file  [required]

Options:
  -o, --output PATH      Write de-identified DCM to this path
  --show-diff            Show tag-by-tag before/after table
  --ruleset PATH         Override ruleset YAML (for development)
  -h, --help             Show this message and exit

Exit codes:
  0   Passed — no PHI detected in output
  1   Input file unreadable or invalid DICOM
  2   PHI residue detected (reverify failed)
```

**Happy-path 출력**

```
$ gateway-agent de-id-test ./sample.dcm --show-diff
Input:  ./sample.dcm  (MR, 512 KB)
Ruleset: v0.1.0

Tag         Name                         Before             After
(0010,0010) PatientName                  HONG, GILDONG      ANON
(0010,0020) PatientID                    HOSP-P-00123       7f3a9c1d4b2e0912
(0010,0030) PatientBirthDate             19801215           19800101
(0008,0020) StudyDate                    20260401           20260513    (+42d)
(0020,000D) StudyInstanceUID             1.2.840.x.y.z      2.25.14073...
(0008,0080) InstitutionName              Seoul Med Ctr      <removed>
...

Reverify: PASS  (0 PHI tags remain)
Wrote de-identified file to ./sample.deid.dcm
```

**Fail (PHI 잔존)**

```
$ gateway-agent de-id-test ./broken.dcm
Input:  ./broken.dcm
Ruleset: v0.1.0-malicious

Reverify: FAIL
  Residual PHI tags detected:
    (0010,0010) PatientName = 'HONG, GILDONG'
    (0008,0090) ReferringPhysicianName = 'Dr. Kim'
  This file would be BLOCKED from upload in production.
  이 파일은 운영 환경에서 업로드가 차단됩니다.

See: https://docs.radivault.io/gateway-agent/errors/ERR_DEID_020
Exit 2.
```

### 3.7 `gateway-agent audit verify`

```
$ gateway-agent audit verify --help
Usage: gateway-agent audit verify PATH

  Re-hash every line of the audit log and verify the SHA-256 chain.
  감사 로그 SHA-256 체인을 재계산해 무결성을 검증.

Arguments:
  PATH   Path to audit.log (may be rotated file)

Exit codes:
  0   Chain intact
  1   Chain broken (first mismatched seq reported on stderr)
  2   File not found or unreadable
```

**출력 예시**

```
$ gateway-agent audit verify /var/log/radivault/audit.log
Reading 12,345 lines...
PASS  seq range [0, 12344]  head_hash=sha256:c3d4e5f6...
```

```
$ gateway-agent audit verify /var/log/radivault/audit.log.tampered
Reading 12,345 lines...
FAIL  chain broken at seq=4821
      expected prev_hash=sha256:abcdef01...
      actual   prev_hash=sha256:00000000...
      (line has been modified or replaced)
Exit 1.
```

### 3.8 `gateway-agent version`

```
$ gateway-agent version
gateway-agent  0.1.0
build          ab12cd34 (2026-04-22)
ruleset        v0.1.0    (Annex E Basic + Longitudinal Dates + Patient Char + Clean Descriptors)
python         3.11.9
pydicom        2.4.4
platform       Linux x86_64 (Ubuntu 22.04.4 LTS)
```

```
$ gateway-agent version --json
{"agent":"0.1.0","build":"ab12cd34","build_date":"2026-04-22",
 "ruleset":"v0.1.0","python":"3.11.9","pydicom":"2.4.4",
 "platform":"Linux x86_64","distro":"Ubuntu 22.04.4 LTS"}
```

### 3.9 종료 코드 요약 (dev-spec §7.4와 정합)

| Command | 0 | 1 | 2 | 64 | 69 | 70 |
|---------|---|---|---|----|----|----|
| `start` | 정상 종료 | — | — | Config 오류 | PACS 초기 실패 | 내부 오류 |
| `sync-once` | 전체 성공 | 1건 이상 실패 | — | Config 오류 | — | — |
| `status` | OK | DB 접근 불가 | — | — | — | — |
| `de-id-test` | PHI 미탐지 | 파일 오류 | PHI 잔존 | — | — | — |
| `audit verify` | 체인 OK | 체인 불일치 | 파일 없음 | — | — | — |
| `version` | 항상 0 | — | — | — | — | — |

---

## 4. Config 파일 디자인

### 4.1 디자인 원칙

- **주석은 한국어 병기**, 기본값을 반드시 표시.
- **최소 필수 키**는 파일 상단에, 선택 키는 하단에.
- **시크릿은 값으로 직접 쓰지 않고 `${file:...}` 또는 `${env:...}` 로만 참조**.
- 파일 구조가 곧 `gateway-agent status --json`의 섹션 구조와 1:1 대응.

### 4.2 주석 포함 전체 예시 (`/etc/radivault/gateway.yml`)

```yaml
# RadiVault Gateway Agent — /etc/radivault/gateway.yml
# 설정 스키마 버전. 마이그레이션 시 증가 (config schema version).
version: 1

# ─────────── 에이전트 식별 (Gateway identity) ───────────
agent:
  # 중앙이 발급한 gateway_id. 파일로만 주입하길 권장.
  # Issued by central; load from file credential.
  gateway_id: "${file:/run/credentials/gateway_id}"
  hospital_id: "hosp_abc"                       # 중앙 등록된 병원 식별자
  org_root_oid: "2.25.140737488355328"          # UID 가명화 root OID

# ─────────── PACS 연결 (DICOMweb QIDO/WADO) ───────────
pacs:
  base_url: "https://pacs.hospital.local/dicom-web"
  auth:
    type: "bearer"                              # bearer | basic
    token: "${file:/run/credentials/pacs_token}"
    # type=basic 일 때만 사용:
    # username: "radivault"
    # password: "${file:/run/credentials/pacs_password}"
  ca_bundle: "/etc/radivault/ca.pem"            # 자가서명 인증서 신뢰 시
  max_concurrency: 4                            # 동시 WADO 페치 (default 4)
  poll_interval_seconds: 300                    # 폴링 주기 (default 300 = 5분)
  query:
    modalities: ["CR", "CT", "MR", "DX"]        # ModalitiesInStudy 필터
    lookback_days: 7                            # 첫 동기화 lookback

# ─────────── De-ID 엔진 (Annex E Basic + 옵션) ───────────
deid:
  ruleset_version: "v0.1.0"
  salt: "${file:/run/credentials/salt}"         # per-hospital salt (hex, ≥32바이트)
  salt_version: 1                               # salt 회전 세대
  burnin_quarantine_modalities: ["SC", "US", "OT"]
  retain_options:
    longitudinal_dates: true                    # DCM 113107
    patient_characteristics: true               # DCM 113108
    clean_descriptors: true                     # DCM 113111
    clean_graphics: true
    safe_private: false                         # v0.1은 false 고정
    uids: false                                 # UID는 항상 가명화 (변경 금지)
    institution_identity: false
    device_identity: "partial"                  # full | partial | none

# ─────────── Staging 영역 (로컬 임시 저장) ───────────
staging:
  root: "/var/lib/radivault/staging"
  retention_hours: 72                           # 업로드 실패분 최대 보존 시간
  max_disk_pct: 80                              # 이 %를 넘으면 신규 페치 일시중단

# ─────────── 로컬 상태 DB ───────────
state:
  db_path: "/var/lib/radivault/state.sqlite3"

# ─────────── 감사 로그 ───────────
audit:
  path: "/var/log/radivault/audit.log"
  anchor_interval_seconds: 3600                 # 중앙 anchor 주기 (default 1h)

# ─────────── 중앙(RadiVault) 업로드 ───────────
central:
  base_url: "https://ingest.radivault.io"
  upload_token: "${file:/run/credentials/upload_token}"
  upload_timeout_seconds: 600                   # 단일 스터디 업로드 타임아웃
  max_upload_retries: 10                        # FR-20

# ─────────── 로깅 ───────────
logging:
  level: "INFO"                                 # DEBUG | INFO | WARN | ERROR
  json: true                                    # stdout를 JSON으로 방출 (docker/journald 친화)
  console_color: "auto"                         # auto | always | never
```

### 4.3 시크릿 처리 UX — 세 가지 참조 방식

| 구문 | 예시 | 권장도 | 용도 |
|------|------|--------|------|
| `${file:/path}` | `${file:/run/credentials/salt}` | **권장** | systemd `LoadCredential=` 와 결합. 파일 권한 0600. v0.1 기본. |
| `${env:VAR_NAME}` | `${env:RADIVAULT_PACS_TOKEN}` | 허용 | docker-compose `.env` 에 적합. 프로세스 덤프 시 누출 위험. |
| 평문 값 | `"eyJhbGciOi..."` | **금지** | 기동 시 경고 로그. 다음 major 버전에서 거부 예정. |

**권장 예시 표기**: `gateway-agent --help` 및 README 상단에 다음 블록을 **사용자가 복사해 쓸 수 있는 레퍼런스**로 제시.

```
[권장] systemd LoadCredential=:
  LoadCredential=salt:/etc/radivault/credentials/salt
  → config 에서는  salt: "${file:/run/credentials/salt}"

[허용] env var:
  환경변수 RADIVAULT_DEID_SALT 설정
  → config 에서는  salt: "${env:RADIVAULT_DEID_SALT}"

[금지] 평문:
  salt: "abcdef..."     ← 절대 금지. 기동 시 WARN_CFG_005.
```

**sops 옵션**: v0.2 이후 검토. v0.1은 위 3종으로 한정.

### 4.4 환경변수 오버라이드

- 규칙: `RADIVAULT_<SECTION>_<KEY>` (SCREAMING_SNAKE_CASE, 중첩은 `__`).
- 예: `RADIVAULT_PACS__MAX_CONCURRENCY=8`, `RADIVAULT_CENTRAL__BASE_URL=https://ingest-staging.radivault.io`.
- 시크릿은 env 오버라이드보다 `${file:}` 참조 우선.

### 4.5 Config 검증 에러 UX (pydantic → 사용자 친화)

**원시 pydantic 에러(내부 전용, 사용자에게 절대 노출 금지)**

```
pydantic.ValidationError: 1 validation error for GatewayConfig
pacs.max_concurrency
  value is not a valid integer (type=type_error.integer)
```

**사용자에게 보이는 형태**

```
[ERR_CFG_003] 설정 검증 실패 / Config validation failed
  파일     : /etc/radivault/gateway.yml
  경로     : pacs.max_concurrency
  현재 값  : "four"
  기대 형식: 정수 (1..32)
  수정 예시:  pacs.max_concurrency: 4
  문서 링크: https://docs.radivault.io/gateway-agent/config#pacs
```

**UX 원칙 5종**

1. **에러 코드**를 앞에 `[ERR_CFG_xxx]` 형식으로 표시 → 검색 가능.
2. **파일 경로 + YAML 경로**를 항상 함께 표시 (`pacs.max_concurrency`).
3. **기대 형식**을 한국어로 설명.
4. **수정 예시**를 1줄 코드 블록으로 제시.
5. **doc 링크**는 앵커까지 포함.

대표 검증 에러 표본:

| 코드 | 상황 | 메시지 요약 |
|------|------|-------------|
| `ERR_CFG_001` | YAML 파싱 실패 | 설정 파일을 파싱할 수 없습니다. / Cannot parse config file. (줄 번호 표시) |
| `ERR_CFG_002` | 필수 키 누락 | 필수 키 누락: `pacs.base_url` / Required key missing. |
| `ERR_CFG_003` | 타입 오류 | 위 예시 참조. |
| `ERR_CFG_004` | 허용 값 아님 | `deid.retain_options.device_identity`는 full/partial/none 중 하나여야 합니다. |
| `ERR_CFG_005` | 시크릿 평문 감지 | 평문 시크릿 사용 감지. `${file:...}` 또는 `${env:...}` 참조를 사용하세요. |
| `ERR_CFG_010` | 시크릿 파일 없음 | salt 크리덴셜 파일이 없습니다: `/run/credentials/salt`. |
| `ERR_CFG_011` | 시크릿 파일 권한 | `/run/credentials/salt` 권한이 0600이 아닙니다 (현재: 0644). |

---

## 5. 로그 출력 디자인

### 5.1 두 개의 로그 스트림

| 스트림 | 경로 | 포맷 | 독자 | TTL |
|--------|------|------|------|-----|
| Console / app log | stdout (docker logs, journald) | 설정에 따라 human-readable 또는 JSON | 사람 + 관측 시스템 | 일반 logrotate |
| Audit log | `/var/log/radivault/audit.log` | **JSON-lines, SHA-256 chained** | 규제·감사·중앙 anchor | 최소 5년 (회전 체인 유지) |

### 5.2 Console 로그 (human-readable) 10-line 예시

TTY 감지 시 레벨별 **색상 단서**를 사용(색은 보조 신호일 뿐 — §9 참조).

```
2026-04-22T01:03:12Z  INFO   radivault.cli         starting gateway-agent v0.1.0 build=ab12cd3
2026-04-22T01:03:12Z  INFO   radivault.config      loaded /etc/radivault/gateway.yml version=1
2026-04-22T01:03:13Z  INFO   radivault.scheduler   tick=1 poll_interval=300s concurrency=4
2026-04-22T01:03:15Z  INFO   radivault.pacs        qido ok studies=12 lookback=7d
2026-04-22T01:03:18Z  INFO   radivault.pipeline    study=2.25.xxxx fetch ok n=184 bytes=94.3MB dur=2.1s
2026-04-22T01:03:22Z  INFO   radivault.pipeline    study=2.25.xxxx deid ok dur=4.1s
2026-04-22T01:03:25Z  WARN   radivault.pipeline    study=2.25.yyyy BurnedInAnnotation=YES → quarantined
2026-04-22T01:03:26Z  INFO   radivault.pipeline    study=2.25.xxxx upload ok job=ingest_01H... dur=3.7s
2026-04-22T01:03:26Z  INFO   radivault.pipeline    study=2.25.xxxx staging cleaned
2026-04-22T02:03:13Z  INFO   radivault.audit       anchor ok seq=[12000,12345] head=sha256:c3d4e5f6
```

### 5.3 Console 로그 (JSON) — `logging.json: true`

```json
{"ts":"2026-04-22T01:03:22Z","level":"INFO","logger":"radivault.pipeline","event":"deid.completed","study":"2.25.xxxx","duration_ms":4123,"ruleset":"v0.1.0"}
```

- 한 줄 한 JSON 객체. 개행 포함 금지.
- 필드 순서: `ts, level, logger, event, …context`.
- **금지 필드**(PHI 오염 방지, dev-spec §12.5): 원본 UID, 평문 patient_id, 환자명, PACS 내부 호스트명 평문.

### 5.4 Audit 로그 JSON-lines 5줄 예시 (dev-spec §6.3 준수)

```
{"seq":0,"ts":"2026-04-22T01:03:12.001Z","gateway_id":"gw_7f3a9c","actor":"gateway","event":"agent.started","target":null,"meta":{"version":"0.1.0","ruleset_version":"v0.1.0"},"prev_hash":"sha256:0000000000000000000000000000000000000000000000000000000000000000","hash":"sha256:a1b2c3d4e5f60718293a4b5c6d7e8f9001122334455667788990aabbccddeeff"}
{"seq":1,"ts":"2026-04-22T01:03:15.412Z","gateway_id":"gw_7f3a9c","actor":"gateway","event":"pacs.query","target":null,"meta":{"lookback_days":7,"modalities":["CR","CT","MR","DX"],"returned":12},"prev_hash":"sha256:a1b2c3d4e5f60718293a4b5c6d7e8f9001122334455667788990aabbccddeeff","hash":"sha256:b2c3d4e5..."}
{"seq":2,"ts":"2026-04-22T01:03:18.220Z","gateway_id":"gw_7f3a9c","actor":"gateway","event":"pacs.fetch.completed","target":{"pseudo_study_uid":"2.25.xxxx"},"meta":{"n_instances":184,"bytes":94321012,"duration_ms":2108},"prev_hash":"sha256:b2c3d4e5...","hash":"sha256:c3d4e5f6..."}
{"seq":3,"ts":"2026-04-22T01:03:22.340Z","gateway_id":"gw_7f3a9c","actor":"gateway","event":"deid.completed","target":{"pseudo_study_uid":"2.25.xxxx","pseudo_series_uid":null,"pseudo_sop_uid":null},"meta":{"n_instances":184,"ruleset_version":"v0.1.0","salt_version":1,"duration_ms":4123},"prev_hash":"sha256:c3d4e5f6...","hash":"sha256:d4e5f607..."}
{"seq":4,"ts":"2026-04-22T01:03:26.010Z","gateway_id":"gw_7f3a9c","actor":"gateway","event":"upload.completed","target":{"pseudo_study_uid":"2.25.xxxx"},"meta":{"central_job_id":"ingest_01HXXXX","bytes":94321012,"duration_ms":3712},"prev_hash":"sha256:d4e5f607...","hash":"sha256:e5f60718..."}
```

**UX 요점**

- 원본 UID/PID 금지(§6.3 금지 필드).
- 로그 언어는 **영어만** — 기계 처리/중앙 집계용. 한국어는 콘솔로만.
- 감사 이벤트 이름은 `namespace.action` 네이밍(예: `pacs.query`, `deid.completed`).
- `audit verify` 는 본 파일만 대상으로 작동(다른 로그 섞지 않음).

### 5.5 에러 메시지 템플릿

**통일 포맷**

```
[<CODE>] <한국어 한 줄> / <English one line>
  <상황 필드들 key: value 나열, 들여쓰기 2칸>
  수정 / Fix: <가능하면 1줄 제안>
  문서 / Docs: https://docs.radivault.io/gateway-agent/errors/<CODE>
```

**필드 4종 고정**: `code`, `ko_message`, `en_message`, `suggested_action`, `doc_link`.

**예시 (PACS 401)**

```
[ERR_PACS_011] PACS 인증 실패 / PACS authentication failed
  base_url: https://pacs.hospital.local/dicom-web
  http_status: 401
  auth_type: bearer
  수정 / Fix: /run/credentials/pacs_token 값을 확인하세요.
  문서 / Docs: https://docs.radivault.io/gateway-agent/errors/ERR_PACS_011
```

**에러 코드 네임스페이스**

| Prefix | 영역 |
|--------|------|
| `ERR_CFG_*` | 설정 로드·검증 |
| `ERR_PACS_*` | PACS 연결·QIDO·WADO |
| `ERR_DEID_*` | De-ID 엔진·재검증 |
| `ERR_STG_*` | Staging FS |
| `ERR_UP_*` | 중앙 업로드 |
| `ERR_AUD_*` | 감사 로그·체인·anchor |
| `ERR_DB_*` | SQLite 상태 DB |
| `WARN_*` | 동일 네임스페이스, 경고 |

---

## 6. `status` 출력 UX

### 6.1 디자인 목표

- **80열 터미널**에서 한 화면에 수렴(수직 스크롤 허용, 수평 스크롤 금지).
- PACS·중앙·체인·staging **네 가지 건강 신호**가 한눈에 보여야 함.
- 색이 아닌 **라벨 + 기호**로 상태 전달(`OK`, `WARN`, `FAIL`, `N/A`). 색은 보조.
- `--json` 모드는 같은 데이터를 기계 파서블 형태로.

### 6.2 ASCII 박스 레이아웃 (80 columns)

```
$ gateway-agent status
╔══════════════════════════════════════════════════════════════════════════════╗
║ RadiVault Gateway Agent — hosp_abc / gw_7f3a9c                version 0.1.0 ║
║ 2026-04-22 10:15:32 KST · ruleset v0.1.0 · uptime 2d 03h 41m                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Connectivity                                                                 ║
║   PACS      [ OK ]  https://pacs.hospital.local/dicom-web    rtt 42ms        ║
║   Central   [ OK ]  https://ingest.radivault.io              rtt 188ms       ║
║                                                                              ║
║ Last sync                                                                    ║
║   tick started   2026-04-22 10:10:00 KST  (5m ago)                           ║
║   tick finished  2026-04-22 10:10:47 KST                                     ║
║   next tick in   255s                                                        ║
║                                                                              ║
║ Pipeline (24h)                                                               ║
║   uploaded          142  quarantined   3  failed   1                         ║
║   in-flight           2  upload queue  1  retry    0                         ║
║   median e2e       14.2s  p95 22.8s                                          ║
║                                                                              ║
║ Staging                                                                      ║
║   path   /var/lib/radivault/staging                                          ║
║   used   11.3 GB / 200.0 GB  (5.7%)  [=..........]  threshold 80%            ║
║   oldest pending  2026-04-22 09:44:10 KST   (31m — within retention 72h)     ║
║                                                                              ║
║ Audit log                                                                    ║
║   path       /var/log/radivault/audit.log                                    ║
║   seq head   12345   hash sha256:c3d4e5f6…                                   ║
║   chain      [ OK ]  (last verify 2026-04-22 10:00:02 KST)                   ║
║   anchor     [ OK ]  last anchored 2026-04-22 10:00:12 KST  to central       ║
║                                                                              ║
║ Recent errors (last 5)                                                       ║
║   10:02:11  ERR_UP_030  upload failed study=2.25.gggg http=503 retry=3/10    ║
║   09:48:03  WARN_STG_001 staging 82% (auto-recovered at 09:51)               ║
║   (3 older entries elided — see /var/log/radivault/app.log)                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

**규칙**

- 라벨 폭 고정: `PACS`, `Central`, `tick started` 등 같은 섹션은 정렬 기준 열 일치.
- 진행률 바(`[=..........]`)는 **해시 `=`로 채움 + `.`로 빈 칸**. 색상 비의존.
- 절대 시각은 KST 표기 + 상대 시각 `(5m ago)` 병기.
- 80열 초과 방지: `https://…` URL이 길면 `…` 뒤 도메인 유지. 완전 URL은 `--json` 에서 확인.
- 색 (TTY만): `OK` 녹색, `WARN` 황색, `FAIL` 적색, 박스 라인 기본색. `--no-color` 시 완전 해제.

### 6.3 `--json` 출력 구조

```json
{
  "agent": {"version":"0.1.0","gateway_id":"gw_7f3a9c","hospital_id":"hosp_abc",
            "ruleset_version":"v0.1.0","uptime_seconds":185740},
  "connectivity": {
    "pacs":    {"status":"ok","rtt_ms":42,"base_url":"https://pacs.hospital.local/dicom-web"},
    "central": {"status":"ok","rtt_ms":188,"base_url":"https://ingest.radivault.io"}
  },
  "last_sync": {"started_at":"...","finished_at":"...","next_tick_in_seconds":255},
  "pipeline_24h": {"uploaded":142,"quarantined":3,"failed":1,"in_flight":2,
                   "upload_queue":1,"retry":0,"median_e2e_ms":14200,"p95_e2e_ms":22800},
  "staging": {"path":"/var/lib/radivault/staging","used_bytes":12131034,
              "total_bytes":214748364800,"used_pct":5.7,
              "oldest_pending_ts":"2026-04-22T00:44:10Z",
              "retention_hours":72,"threshold_pct":80},
  "audit": {"path":"/var/log/radivault/audit.log",
            "seq_head":12345,"head_hash":"sha256:c3d4e5f6...",
            "chain_status":"ok","last_verify_ts":"2026-04-22T01:00:02Z",
            "last_anchor_ts":"2026-04-22T01:00:12Z"},
  "recent_errors": [
    {"ts":"2026-04-22T01:02:11Z","code":"ERR_UP_030","pseudo_study_uid":"2.25.gggg",
     "detail":"http=503 retry=3/10"}
  ]
}
```

### 6.4 `--watch`

2초 간격 refresh. Ctrl-C 종료. 같은 포맷 유지(깜빡임 최소화하려면 `clear` 대신 ANSI 커서 리셋 사용). `--no-color` 시 전체 재출력 방식 fallback.

---

## 7. 설치·온보딩 워크스루 (Quickstart UX)

대상: **병원 IT 운영자 (한국어)**. 방법: 단일 호스트 Docker Compose. 소요: 약 15–30분.

### 7.1 전체 플로우 ASCII 다이어그램

```
┌───────────────────────────┐   ┌───────────────────────────┐
│ 1. 사전 체크 (네트워크)    │ → │ 2. 패키지 받기             │
│  · 아웃바운드 443 허용     │   │  · docker-compose.yml      │
│  · PACS DICOMweb URL 확인  │   │  · .env 템플릿             │
└─────────────┬─────────────┘   └──────────────┬────────────┘
              │                                │
              ▼                                ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│ 3. 크리덴셜 배치            │ → │ 4. gateway.yml 편집        │
│  · /etc/radivault/         │   │  · pacs.base_url           │
│    credentials/*  0600      │   │  · hospital_id 등          │
└─────────────┬─────────────┘   └──────────────┬────────────┘
              │                                │
              ▼                                ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│ 5. de-id-test (샘플 DICOM)│ → │ 6. sync-once --dry-run    │
│   PHI 잔존 확인             │   │   end-to-end 검증          │
└─────────────┬─────────────┘   └──────────────┬────────────┘
              │                                │
              ▼                                ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│ 7. docker compose up -d   │ → │ 8. systemd / cron 등록    │
│   데몬 기동                 │   │   재기동·감시              │
└───────────────────────────┘   └───────────────────────────┘
```

### 7.2 단계별 "운영자가 보는 화면"

**Step 1 — 사전 체크**

RadiVault 운영팀이 제공하는 체크리스트:

```
[ ] 병원 아웃바운드 방화벽이 *.radivault.io:443 을 허용한다.
[ ] PACS 의 DICOMweb 엔드포인트 URL 을 알고 있다.
    예) https://pacs.hospital.local/dicom-web
[ ] PACS 접근용 Bearer 또는 Basic 자격을 발급받았다.
[ ] OS = Ubuntu 22.04 LTS, docker 24+, docker compose v2.20+ 확인.
```

**Step 2 — 패키지 받기**

```
$ mkdir -p /opt/radivault && cd /opt/radivault
$ curl -fsSL https://get.radivault.io/gateway/v0.1.0/bundle.tgz | tar xz
$ ls
docker-compose.yml  .env.example  gateway.yml.example  README.md
```

**Step 3 — 크리덴셜 배치**

```
$ sudo install -d -m 0700 /etc/radivault/credentials
$ sudo tee /etc/radivault/credentials/gateway_id >/dev/null < /path/to/gateway_id.txt
$ sudo tee /etc/radivault/credentials/upload_token >/dev/null < /path/to/upload_token.txt
$ sudo tee /etc/radivault/credentials/pacs_token >/dev/null < /path/to/pacs_token.txt
$ sudo openssl rand -hex 32 > /etc/radivault/credentials/salt     # 또는 중앙 제공값
$ sudo chmod 0600 /etc/radivault/credentials/*
```

**Step 4 — config 편집**

```
$ sudo cp gateway.yml.example /etc/radivault/gateway.yml
$ sudo vi /etc/radivault/gateway.yml
  # agent.hospital_id, pacs.base_url, pacs.query.modalities, 등 최소 4개 수정
```

**Step 5 — `de-id-test`로 PHI 제거 확인 (중요)**

```
$ docker compose run --rm gateway-agent de-id-test /data/sample.dcm --show-diff
Input:  /data/sample.dcm  (CT, 512KB)
...
Reverify: PASS  (0 PHI tags remain)
```

UX 의의: **첫 업로드 이전에** DPO/병원 운영자가 "내 병원 데이터에서 어떤 태그가 사라지는지"를 스스로 확인할 수 있게 한다.

**Step 6 — `sync-once --dry-run`**

```
$ docker compose run --rm gateway-agent sync-once \
    --since 2026-04-15 --until 2026-04-21 --dry-run --limit 3
[1/3] 2.25.aaaa  fetch 2.1s  deid 4.1s  UPLOAD-SKIPPED (--dry-run)
[2/3] 2.25.bbbb  fetch 1.8s  deid 3.9s  UPLOAD-SKIPPED (--dry-run)
[3/3] 2.25.cccc  fetch 2.3s  deid 4.4s  QUARANTINED (BurnedInAnnotation=YES)
Dry-run succeeded. No data was sent to central.
```

**Step 7 — 데몬 기동**

```
$ docker compose up -d
$ docker compose logs -f gateway-agent | head -20
2026-04-22T01:03:12Z  INFO  radivault.cli      starting gateway-agent v0.1.0
...
```

**Step 8 — systemd로 래핑**

```
$ sudo cp systemd/radivault-gateway.service /etc/systemd/system/
$ sudo systemctl daemon-reload
$ sudo systemctl enable --now radivault-gateway
$ systemctl status radivault-gateway
● radivault-gateway.service - RadiVault Gateway Agent
     Loaded: loaded (/etc/systemd/system/radivault-gateway.service; enabled)
     Active: active (running) since Wed 2026-04-22 01:03:11 KST
```

운영 일상:

```
$ gateway-agent status                  # 지표 확인
$ gateway-agent audit verify /var/log/radivault/audit.log    # 주 1회
$ docker compose logs --since 1h gateway-agent               # 최근 로그
```

### 7.3 에러가 났을 때 "운영자가 해야 할 일" (티어 1 플레이북)

1. `gateway-agent status` 실행 → 어느 신호가 FAIL/WARN인지 확인.
2. Recent errors의 `ERR_XXX_NNN` 코드 → `https://docs.radivault.io/gateway-agent/errors/<CODE>` 열기.
3. 해결되지 않으면 `docker compose logs --since 1h > gw.log`, `gateway-agent status --json > gw-status.json` 두 파일을 RadiVault 지원에 첨부 (PHI 미포함 보장).

---

## 8. i18n (국제화)

| 표면 | 언어 | 근거 |
|------|------|------|
| CLI `--help` | ko + en 병기 | 운영자 한국어, 오픈소스/지원 영어 문서 링크 |
| Console 에러 | ko + en 병기 | 동상 |
| Console INFO 로그 | 영어 | 관측 도구 친화·PHI 누출 최소 |
| Audit log (JSON) | **영어 전용** | 기계 처리·중앙 집계·법적 보존 |
| Config 주석 | ko + en 허용 | 6.2의 예시 참조 |
| 문서 링크 | `/ko/`, `/en/` 경로 제공 (v0.2) | — |

**한국어 길이 규칙**: 터미널 80열 기준 한 메시지 120 bytes 이내(한글 3 bytes 가정). 초과 시 `…` 후 `--help`·`status` 상세 참조 유도.

**시간대 표기**: 콘솔은 KST 기본, audit log·JSON은 UTC. 사용자가 두 곳에서 같은 시각을 볼 수 있도록 `status`는 KST, `status --json`은 UTC ISO8601.

---

## 9. 접근성 (Accessibility)

대부분 GUI 기준은 N/A지만, CLI 도구도 접근성 고려가 필요.

| 항목 | 지침 |
|------|------|
| 색 의존 금지 | 상태 라벨 `OK`/`WARN`/`FAIL`/`N/A`는 **문자열로 표현**. 색은 보조. `--no-color` 플래그로 완전 비활성. `NO_COLOR=1` 환경변수 준수(표준). |
| 고대비 | 흰/검 터미널 모두에서 식별 가능(색 외 기호). |
| 스크린리더 | CLI 는 보통 화면낭독기 대상 아님. 단, `status` 박스 라인(`╔═╗`)이 난독화 우려 → `--plain` 모드에서 아스키 전용(`+---+`)로 fallback. |
| UTF-8 | 기본 출력 UTF-8. 한국어 콘솔(`LANG=ko_KR.UTF-8`) 보장. 터미널이 UTF-8 미지원(`LANG=C`)일 때 자동으로 ASCII 폴백. |
| 키보드 | CLI → 본래 키보드 전용. `--watch` Ctrl-C 명시 안내. |
| 포커스 | N/A — CLI tool. |
| WCAG 색 대비 4.5:1 | N/A — CLI tool (색은 보조만). |

---

## 10. 수용 기준 (Acceptance Criteria — 디자인 측)

- [ ] **AC-D-1** 모든 서브커맨드(`start`, `sync-once`, `status`, `de-id-test`, `audit verify`, `version`)가 `--help`를 구현한다. `--help` 출력이 본 문서 §3의 예시와 **섹션 구성**(Usage/Options/Exit codes 등) 일치.
- [ ] **AC-D-2** 모든 에러 메시지가 `[CODE] 한국어 / English` 2-line 프리픽스 + `수정 / Fix` + `문서 / Docs` 를 포함한다.
- [ ] **AC-D-3** `gateway-agent status` 출력이 80열 터미널에서 가로 스크롤 없이 렌더링된다 (§6.2 레이아웃 준수).
- [ ] **AC-D-4** Config 검증 에러는 `파일 + YAML 경로 + 현재 값 + 기대 형식 + 수정 예시 + 문서 링크` 6 항목을 포함한다.
- [ ] **AC-D-5** 색상에 의존한 정보 전달이 없다. `--no-color`/`NO_COLOR=1` 모두에서 모든 상태가 여전히 읽힌다.
- [ ] **AC-D-6** Audit log는 JSON-lines, 영어 필드만, 원본 UID/평문 PID 없음 (§5.4 금지 필드).
- [ ] **AC-D-7** 콘솔 로그 JSON 모드에서 1 이벤트 = 1 줄, 줄 중간 개행 없음.
- [ ] **AC-D-8** 설치 워크스루(§7)의 8단계를 따라가면 Kyle이 정의한 "파일럿 병원 1곳" 시나리오에서 외부 문서 참조 없이 기동 성공에 도달한다 (도큐먼트/튜토리얼 측 수용).
- [ ] **AC-D-9** 모든 에러 코드(`ERR_*`/`WARN_*`)가 유일 네임스페이스를 가지며 중복 코드가 없다.
- [ ] **AC-D-10** `status --json` 구조가 §6.3 예시 키와 1:1 일치한다 (QA가 JSON Schema 로 검증 가능).
- [ ] **AC-D-11** `--help` 와 본 문서의 exit code 표(§3.9)가 dev-spec §7.4와 서로 모순되지 않는다.
- [ ] **AC-D-12** `de-id-test --show-diff` 출력이 PHI 원문을 포함하는 유일한 출력이며, 로그/파일로 기본 기록되지 않는다(개발자 로컬 검증 전용).

---

## 11. 오픈 질문

1. **Doc 링크 호스팅**: `docs.radivault.io/gateway-agent/errors/<CODE>` 라우트 생성 책임 — 본 지점 문서/마케팅 사이트 미구축. v0.1 소스에서는 링크만 넣어두고 404 허용할지 Kyle 결정 필요.
2. **ASCII 박스 문자 지원**: `╔═╗` 유니코드 박스가 일부 터미널(특히 SSH 구 버전)에서 깨질 우려. `--plain` 플래그 필수로 v0.1에 넣을지, v0.2로 미룰지.
3. **`status --watch` TUI 라이브러리**: stdlib ANSI 수동 조작 vs `rich`·`textual` 의존성 추가. 의존 최소화 원칙 고수면 stdlib 선택. Kyle 성능/룩 선호 확인.
4. **색상 경고 한계**: 색각 이상자(red-green) 대비 `OK`/`FAIL` 추가 기호(예: `✓`/`✗`) 도입 여부. ASCII 터미널 호환 위해 `[OK]` / `[!!]` 텍스트 표기 권장 — 최종 결정 필요.
5. **Error doc 국제화**: `/ko/`, `/en/` 경로 v0.1 에 둘 다 제공할지 en만 우선할지. 한국어 우선 권장.
6. **`sync-once --dry-run` 시 staging 정리 정책**: 드라이런 후 staging 결과를 자동 삭제할지, 개발 편의상 유지할지. 권장: `--keep-staging` 플래그 도입(기본 삭제).

---

## 12. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-22 | @designer (Claude Opus 4.7) | 최초 작성. CLI + Config + Log + status + 설치 워크스루 UX 확정. Web UI 대상 절(반응형·색 대비·토큰)은 N/A 처리. |

---

### NEXT_STEP
- 완료 산출물: `docs/specs/design-spec-gateway-agent.md` (v0.1 Draft)
- 제안 다음 단계: `@developer` — `claude` 브랜치에서 `gateway-agent` 구현 착수. 본 디자인 명세의 §3 CLI 구조, §4.5 Config 에러 UX, §5.5 에러 메시지 템플릿, §6 `status` 레이아웃을 구현 기준으로 반영.
- UI_GUIDE.md 갱신 제안: CLI 도구 디자인 원칙(이중 언어 에러, 에러 코드 네임스페이스, `--no-color`/`NO_COLOR`, JSON-lines 로그) 4 항목을 "부록: CLI 도구 공통 가이드"로 편입 검토. 정식 편입은 Kyle 승인 후.
- 추가 디자인 필요: (a) `dev-spec-central-ingest`가 작성되면 대응 design-spec에서 API 에러 UX·페이지네이션 UX 정의. (b) Hospital admin web console은 별도 slug로 분리(본 기능 범위 아님).
- Kyle 결정 필요 사항:
  1. §11-1 docs 사이트 링크 호스팅 책임자/타이밍.
  2. §11-2 `--plain` ASCII 폴백을 v0.1 필수 범위에 포함할지.
  3. §11-3 `status --watch` 구현에 `rich`/`textual` 도입 허용 여부.
  4. §11-4 상태 기호(`[OK]`/`[!!]` vs `✓/✗`) 최종 스타일.
  5. §11-6 `sync-once --dry-run`의 staging 자동 정리 정책.
