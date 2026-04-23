# 디자인 명세 — De-ID Pixel v0.1 (Gateway Agent v0.2 확장 · CLI · Config · Log · Runbook UX)

> **Status**: Draft v0.1 · **Feature slug**: `de-id-pixel` · **Last updated**: 2026-04-22
> **작성자**: @designer · **근거**: [dev-spec-de-id-pixel](./dev-spec-de-id-pixel.md), [design-spec-gateway-agent](./design-spec-gateway-agent.md), [UI Guide](../UI_GUIDE.md), [리서치](../research/de-id-pixel-technical-foundations.md)

---

## 0. 범위 선언 (Scope Statement)

본 문서는 Gateway Agent v0.1 위에 얹히는 **`de-id-pixel` 확장**(= Gateway Agent v0.2, 픽셀 레벨 De-ID: OCR 번인 마스킹 + 3D Defacing)의 운영자·개발자 표면 디자인이다. **GUI/Web UI 없음**.

**디자인 대상 표면 7종**: (1) CLI 확장(`de-id-test --pixel`, 신규 `pixel-selftest`, `status` 섹션), (2) Config UX(`deid.pixel.*` 3-preset + 검증 에러), (3) 로그/관측(필드 + Prometheus + 알림), (4) 에러 택사노미 8 ERR + 1 WARN + 1 CFG, (5) Runbook 6건, (6) Docker 변종 온보딩, (7) 임상 QA 워크플로우(외부 툴 허용).

**디자인 대상 아님**: 웹 포털, 대시보드 UI, 모바일, 구매자 화면.

**N/A 섹션**: 반응형·디바이스 · 디자인 토큰(색/간격) · WCAG 색 대비 — 모두 backend Gateway extension이므로 해당 없음. CLI 색은 §10 접근성에서 별도 처리.

---

## 1. 사용자 (Users)

### 1.1 Primary A — 병원 IT 운영자 (한국어)

Linux(`docker`, `systemctl`, `vi`) 능숙, Python·DICOM 비전문가, OCR/defacing 개념 모를 수 있음. 전제: Gateway v0.1 운영 경험 있음 — 본 기능은 **upgrade**이지 신규 설치 아님. 반드시 해야 할 것: Docker 이미지 태그 전환, `deid.pixel.enabled` 토글, `pixel-selftest` 실행, 48시간 모니터링, 롤백. 안 해도 되는 것: OCR 모델 튜닝, pydeface 파라미터, Python 코드 수정.

### 1.2 Primary B — RadiVault SRE / 지원 엔지니어

한국어·영어 혼용. 원격 장애 분석(Prometheus + audit log), `pixel-selftest` 결과 해석, 픽셀 이벤트 hash-chain 정합성 확인, 파일럿 병원 StudyDescription 패턴 수집으로 제외 리스트 보강. 요구: 구조화 JSON 로그, deterministic 에러 코드, `status --json`의 pixel 섹션, Prometheus `radivault_gateway_pixel_*` 지표.

### 1.3 Primary C — 임상 리뷰어 (방사선과 전문의) **[v0.2 신규 역할]**

한국어. 과redaction(US caliper, Doppler 속도 가림) · 과defacing(안와·전두엽 침범) 검토 담당. 본 기능과의 접점: 파일럿 초기 2주간 처리된 스터디의 **10–20% 샘플**을 PACS 뷰어/OHIF에서 육안 검토 → 스프레드시트 기록. **파이프라인 코드 안에 UI 없음**(§8). 요구: 샘플링 규칙 reproducible(sample seed 기록), 부적합 판정 시 escalation path 명시.

### 1.4 Secondary — Kyle (CEO) / RadiVault DPO

법적 "완전 익명" 주장 증거(재검증 pass 로그, audit chain, face voxel 제거 비율), 라이선스 안전성(FSL 법무), 임상 리뷰어 서명본 보관.

### 1.5 Non-user

환자, 구매자, 메타데이터 인덱스 소비자, 검색 포털 사용자 — 픽셀 처리 과정에 노출되지 않음(결과 DICOM 태그만 소비).

---

## 2. CLI 확장 (Command Tree)

### 2.1 전체 구조 (v0.2 델타 강조)

기존 v0.1 CLI 트리(design-spec-gateway-agent §3.1)에 **두 지점**만 손댄다.

```
gateway-agent
├── start                                           (변경 없음)
├── sync-once [--since] [--until] [--dry-run]       (변경 없음)
├── status [--json] [--watch]                       (+ pixel 섹션 추가, §2.5)
├── de-id-test <input> [--output] [--show-diff]     (+ --pixel, --ocr-only, --deface-only, --both)
├── pixel-selftest                                  [NEW — §2.4]
├── audit
│   └── verify <audit.log>                          (변경 없음; pixel 이벤트 포함된 동일 체인 검증)
└── version                                         (+ pixel engine 버전 라인 추가)
```

**전역 플래그**는 v0.1 그대로(`-c`, `--log-level`, `--no-color`, `--quiet`, `-h`, `-V`). `pixel-selftest`와 `de-id-test --pixel`은 전역 플래그를 모두 존중한다.

### 2.2 `gateway-agent --help` 최상위 변경

v0.1 출력에 2줄만 append. 전체 블록은 design-spec-gateway-agent §3.2 유지.

```
Commands:
  start           Run as a foreground daemon (주기 동기화 데몬 실행)
  sync-once       One-shot synchronisation run (1회성 동기화)
  status          Show agent status summary (상태 요약)
  de-id-test      Dry-run de-identification on a single DICOM (단일 파일 테스트)
  pixel-selftest  Check OCR + defacing dependencies (픽셀 의존성 자체 점검)   # NEW
  audit verify    Verify the audit log hash chain (감사 로그 체인 검증)
  version         Print agent version and build info (버전 정보)
```

`pixel-selftest`는 `deid.pixel.enabled` 값과 무관하게 **항상 노출**(이미지 진단용이기 때문). v0.1(비 pixel) 이미지에서도 명령 자체는 존재하고 종료 코드만 달라진다(§2.4, AC-D-14).

### 2.3 `gateway-agent de-id-test --pixel` (확장)

v0.1의 `de-id-test`(단일 DICOM 메타 De-ID 드라이런)에 **픽셀 경로를 추가 실행**하는 플래그를 도입한다.

#### 2.3.1 `--help`

```
$ gateway-agent de-id-test --help
Usage: gateway-agent de-id-test INPUT [OPTIONS]

  Dry-run de-identification on a single DICOM file or study directory.
  단일 DICOM 또는 스터디 폴더에 대해 드라이런.

Arguments:
  INPUT                  Path to .dcm file OR directory of .dcm files  [required]

Options:
  -o, --output PATH      Write de-identified DCM(s) to this path
  --show-diff            Show tag-by-tag before/after table (v0.1 동일)
  --ruleset PATH         Override ruleset YAML (개발용)

  --pixel                Also run pixel stage (OCR + defacing, triage 적용)    # NEW
  --ocr-only             Skip defacing even if modality/body_part matches       # NEW
  --deface-only          Skip OCR even if BurnedInAnnotation=YES                # NEW
  --both                 (기본) OCR + defacing 모두 시도 — --pixel과 동일       # NEW
  --show-boxes           Print OCR bbox table (hash + coord %)                  # NEW
  --show-voxel-stats     Print defacing removed_voxel_ratio                     # NEW

  -h, --help             Show this message and exit

Exit codes:
  0   Passed — no PHI detected in meta AND pixel stage accepted
  1   Input file unreadable or invalid DICOM
  2   PHI residue detected in meta reverify (v0.1과 동일)
  3   Pixel stage would route to quarantine (ERR_PIXEL_* — 원문 §13)       # NEW
  4   Pixel engine unavailable (-pixel image 아님) — ERR_PIXEL_OCR_ENGINE_FAILURE / ERR_PIXEL_DEFACE_LIBRARY_MISSING  # NEW

Notes:
  --show-boxes 는 원문 텍스트를 절대 출력하지 않습니다 (SHA256[:16] 해시만).
  --show-boxes never prints raw OCR text (hash + relative coords only).
```

**플래그 관계표**

| 플래그 조합 | 동작 |
|------------|------|
| (플래그 없음) | v0.1과 동일 — 메타 De-ID만. |
| `--pixel` | 메타 De-ID 후 픽셀 트리아지 + OCR + defacing (적용 가능 시). |
| `--pixel --ocr-only` | OCR만. defacing 스킵. |
| `--pixel --deface-only` | Defacing만. OCR 스킵. |
| `--pixel --both` | `--pixel` 단독과 동일(명시성용 alias). |
| `--ocr-only` + `--deface-only` 동시 | 에러 `ERR_CLI_010` (상호배타). |
| `--ocr-only` 단독(`--pixel` 없이) | 에러 `ERR_CLI_011` (`--pixel` 필요). |

#### 2.3.2 Happy-path — US 번인 영상

```
$ gateway-agent de-id-test ./sample_US_burnin.dcm --pixel --show-boxes
Input:  ./sample_US_burnin.dcm  (US, 1.4 MB, 50 frames)
Ruleset: v0.1.0 + pixel v0.1

Meta De-ID: PASS (35 tags modified, reverify OK)

Pixel Stage (v0.2)
  triage          OCR_REQUIRED  (reason: modality_allowlist=US)
  engine          tesseract 5.3.4 (lang=kor+eng)
  frames scanned  50 / 50
  OCR boxes (conf >= 0.60)
    frame  bbox (% of frame)   conf   text_hash
       1   (02,03)-(24,08)     0.91   sha256:a3f8..9c1d
       1   (76,93)-(98,97)     0.88   sha256:b2e7..081a
      12   (02,03)-(22,08)     0.92   sha256:a3f8..9c1d   # dup frame1
      ... (46 boxes across 18 frames) ...
    avg_conf 0.86  min 0.61  max 0.97
  Redaction      fill=solid_black  padding=2px  boxes_applied=46/46
  Residual OCR   re-detected_over_threshold: 0       PASS
  Defacing       SKIP (modality=US, not CT/MR head)
  Exit status    OK   Wrote ./sample_US_burnin.deid.dcm
Exit 0.
```

#### 2.3.3 Happy-path — Head CT defacing

```
$ gateway-agent de-id-test ./sample_CT_head/ --pixel --show-voxel-stats
Input:  ./sample_CT_head/  (CT, 400 instances, 204 MB)
StudyDescription: "Brain CT w/o contrast"     BodyPartExamined: HEAD
Meta De-ID: PASS

Pixel Stage
  triage          SKIP (modality=CT not in OCR allowlist)
  exclusion_match false  (checked 7 patterns)
  defacing
    library       pydeface 2.0.2 (FSL 6.0.7 flirt)
    duration      68.4s
    removed_voxel_ratio  0.318   (min_required 0.050) PASS
    residual_face_voxels below threshold             PASS
  reencoding DICOM (SOPInstanceUID preserved)  OK
  Exit status  OK   Wrote ./sample_CT_head.deid/
Exit 0.
```

#### 2.3.4 에러 시나리오 3종

**(a) 픽셀 이미지 아님 (-pixel variant 부재) — Exit 4**

```
[ERR_PIXEL_OCR_ENGINE_FAILURE] OCR 엔진을 실행할 수 없습니다 / OCR engine unavailable
  reason    : missing_binary — `tesseract` not found on PATH
  image_tag : radivault-gateway:0.2.0     (expected: 0.2.0-pixel)
  수정/Fix  : -pixel 이미지 재배포 또는 deid.pixel.enabled=false.
  문서      : https://docs.radivault.io/gateway-agent/errors/ERR_PIXEL_OCR_ENGINE_FAILURE
```

**(b) 재검증 실패 — 잔여 텍스트 — Exit 3**

```
  Redaction  boxes_applied=12    Residual OCR recheck  re-detected=2 frames [3,14] conf_max=0.74
[ERR_PIXEL_RESIDUAL_TEXT] 마스킹 후 잔여 텍스트 탐지 / Residual text after redaction
  frames_affected : 2
  수정/Fix  : box_padding_px 상향(2→4) 또는 해당 모달리티 샘플 지원팀 송부.
  Note      : 운영 환경에서는 이 스터디가 격리됩니다(state=pixel_failed).
```

**(c) 의료 제외 매칭 — Exit 3**

```
  triage OCR_REQUIRED → OCR redaction PASS
  Defacing  exclusion_match=TRUE  pattern=(?i)dental  StudyDescription="Dental CBCT maxilla"
[ERR_PIXEL_MEDICAL_EXCLUSION] 의료 제외 — defacing 건너뜀 / Medical exclusion
  수정/Fix : 임상 자문 후 사람이 업로드 여부 결정. 오탐이면 exclusion_patterns 조정.
```

### 2.4 `gateway-agent pixel-selftest` [NEW]

**목적**: 운영자가 Docker 이미지가 올바른 variant인지, kor+eng 언어팩이 설치됐는지, pydeface 바이너리와 FSL `flirt`가 호출 가능한지 30초 내로 확인한다. 합성 fixture(작은 PNG + 작은 NIfTI)로 end-to-end 실행까지 검증한다.

#### 2.4.1 `--help`

```
$ gateway-agent pixel-selftest --help
Usage: gateway-agent pixel-selftest [OPTIONS]

  Verify OCR + defacing dependencies are installed and runnable.
  OCR + defacing 의존성 설치·실행 가능 여부 자체 점검.

  Runs a tiny synthetic fixture end-to-end (no PACS, no network, no PHI).
  외부 PACS/네트워크 접근 없이 내장 합성 fixture를 사용합니다.

Options:
  --ocr-only         Only test OCR components                (OCR만 점검)
  --deface-only      Only test defacing components           (defacing만 점검)
  --json             Emit machine-readable report            (기계 파서블)
  -h, --help         Show this message and exit

Exit codes:
  0   All components OK                      (모두 정상)
  1   OCR component missing or failing       (OCR 누락/실패)
  2   Defacing component missing or failing  (defacing 누락/실패)
  3   Both missing                           (둘 다 누락)
  70  Selftest fixture itself corrupt        (내부 픽스처 손상 — bug)
```

#### 2.4.2 Happy-path 출력 (-pixel 이미지)

```
$ gateway-agent pixel-selftest
RadiVault Gateway — pixel dependency selftest
image_tag : radivault-gateway:0.2.0-pixel

[ OCR ]
  tesseract binary          /usr/bin/tesseract          [ OK ] v5.3.4
  language pack: eng        /usr/share/tesseract/eng    [ OK ]
  language pack: kor        /usr/share/tesseract/kor    [ OK ]
  pytesseract wrapper       v0.3.13                     [ OK ]
  fixture kor/eng burn-in   conf 0.93 / 0.96            [ OK ]
  fixture redaction         0 residual boxes            [ OK ]

[ DEFACING ]
  pydeface 2.0.2            nibabel 5.2.1               [ OK ]
  dcm2niix v1.0.20240202    FSL flirt 6.0.7             [ OK ]
  fixture synth head        removed_voxel_ratio=0.27    [ OK ]

Summary   OCR OK   Defacing OK   Fixture elapsed 8.2s
Exit 0.
```

#### 2.4.3 실패 출력 1 — kor 언어팩 누락

```
$ gateway-agent pixel-selftest
[ OCR ]
  tesseract binary      [ OK ]   lang eng [ OK ]   lang kor [ FAIL ] (not found)
  fixture kor burn-in   skipped (kor missing)  [ FAIL ]
[ DEFACING ]            all OK

Summary   OCR FAIL (kor_missing)   Defacing OK
[ERR_PIXEL_OCR_ENGINE_FAILURE] OCR 언어팩 누락 / OCR language pack missing
  missing  : kor.traineddata
  수정     : apt-get install tesseract-ocr-kor (또는 -pixel 이미지 재배포)
  문서     : https://docs.radivault.io/gateway-agent/errors/ERR_PIXEL_OCR_ENGINE_FAILURE
Exit 1.
```

#### 2.4.4 실패 출력 2 — 기본(non-pixel) 이미지

```
$ gateway-agent pixel-selftest
image_tag : radivault-gateway:0.2.0          <-- default variant
[ OCR ]       tesseract  (not on PATH)                [ FAIL ]
[ DEFACING ]  pydeface   (not importable)             [ FAIL ]
              FSL flirt  (not on PATH)                [ SKIP ]
Summary   OCR FAIL   Defacing FAIL
수정 / Fix : docker pull radivault-gateway:0.2.0-pixel
문서 / Docs: https://docs.radivault.io/gateway-agent/pixel-onboarding
Exit 3.
```

#### 2.4.5 `--json` 출력 구조

```json
{
  "image_tag": "radivault-gateway:0.2.0-pixel",
  "ocr":      {"status":"ok","engine":"tesseract","engine_version":"5.3.4",
               "languages":{"eng":"ok","kor":"ok"},
               "fixtures":[{"id":"kor_burn_in","status":"ok","conf":0.93},
                           {"id":"eng_burn_in","status":"ok","conf":0.96},
                           {"id":"redaction_roundtrip","status":"ok","residual_boxes":0}]},
  "defacing": {"status":"ok","library":"pydeface","library_version":"2.0.2",
               "flirt_version":"6.0.7",
               "fixtures":[{"id":"synth_head","status":"ok","removed_voxel_ratio":0.27}]},
  "summary":  {"ocr":"ok","defacing":"ok","exit_code":0}
}
```

### 2.5 `gateway-agent status` 확장 — pixel 섹션

v0.1의 80열 ASCII 박스(design-spec-gateway-agent §6.2)에 **`Pipeline (24h)` 섹션 내부 라인 2개 추가** + **`Pixel stage` 신규 섹션**. 박스 폭 80열 유지.

#### 2.5.1 확장 레이아웃 (v0.1 블록은 생략; v0.2 추가분만 강조)

v0.1 섹션(`Connectivity`, `Last sync`, `Staging`, `Audit log`, `Recent errors`)은 design-spec-gateway-agent §6.2 그대로. 아래는 v0.2에서 추가·변경되는 2지점.

```
║ Pipeline (24h)                                                               ║
║   uploaded          142  quarantined   4  failed   1                         ║
║   in-flight           2  upload queue  1  retry    0                         ║
║   pixel_deided       38  pixel_failed  3                             [v0.2] ║
║   median e2e       14.2s  p95 22.8s (meta)   +54s (pixel p95, 38 studies)   ║
║                                                                              ║
║ Pixel stage                                                          [v0.2] ║
║   config       enabled=true   ocr=tesseract   defacing=pydeface              ║
║   engines      tesseract 5.3.4  pydeface 2.0.2  FSL flirt 6.0.7   [ OK ]     ║
║   24h triage   OCR_REQUIRED 41   SKIP 104   CONDITIONAL 0                    ║
║   24h OCR      studies 41  avg_conf 0.84  p10 0.67  redact_boxes 612         ║
║   24h deface   studies 22  avg_removed_ratio 0.29  min 0.08                  ║
║   quarantine   residual_text 1  residual_face 0  medical_excl 2              ║
║   engine err   ocr 0   deface 1 (fallback succeeded)                         ║
```

최근 에러 섹션의 첫 라인은 pixel 관련 샘플로 대체 가능:
```
║   10:02:11  ERR_PIXEL_RESIDUAL_TEXT  study=2.25.mmmm  frame=3 conf=0.74     ║
```

#### 2.5.2 규칙 — pixel 섹션

- **`Pixel stage` 섹션은 `deid.pixel.enabled=true` 일 때만 출력**. `false` 또는 키 부재 시 완전 생략(v0.1 레이아웃과 동일).
- 섹션 우측 상단 `[v0.2]` 라벨로 신규 섹션임을 표시(운영자가 "v0.1에서 못 보던 게 생겼구나" 즉시 인지).
- 엔진 라인은 한 줄 80자 제한 내에서 `ocr=<engine> defacing=<library>` 형식. 엔진 버전은 두 번째 라인.
- 24h 카운트는 `pixel_audit_event` 테이블에서 집계. p10(10-percentile) 신뢰도는 **하위 신뢰도 꼬리**를 빨리 감지하기 위함(낮은 값이 위험 신호).
- `engine err` 라인의 `(fallback succeeded)` 꼬리표는 pydeface 실패 후 mridefacer로 복구된 경우.

#### 2.5.3 `--json` 추가 필드

v0.1 JSON(design-spec-gateway-agent §6.3)의 `pipeline_24h`에 `pixel_deided`, `pixel_failed`, `p95_e2e_ms_pixel_delta` 필드 추가. 최상위에 `pixel` 블록 추가:

```json
{
  "pixel": {
    "enabled": true,
    "engines": {
      "ocr":      {"name":"tesseract","version":"5.3.4","status":"ok"},
      "defacing": {"name":"pydeface","version":"2.0.2","status":"ok",
                   "flirt_version":"6.0.7"}
    },
    "triage_24h":        {"ocr_required":41,"ocr_conditional":0,"skip":104},
    "ocr_24h":           {"studies":41,"avg_confidence":0.84,
                          "p10_confidence":0.67,"redacted_boxes":612},
    "deface_24h":        {"studies":22,"avg_removed_voxel_ratio":0.29,
                          "min_removed_voxel_ratio":0.08},
    "quarantine_24h":    {"residual_text":1,"residual_face_voxels":0,
                          "medical_exclusion":2,"low_confidence":0},
    "engine_errors_24h": {"ocr":0,"deface":1,"deface_fallback_succeeded":1}
  }
}
```

### 2.6 `gateway-agent audit verify` — pixel 이벤트 상호작용

**변경 없음**. `audit.log`는 v0.1과 동일한 단일 SHA-256 hash chain이며 `pixel.*` 이벤트(dev-spec FR-37)는 동일 체인의 새 seq로 끼어든다. 분리된 `pixel_audit_event` DB 테이블은 **2차 bookkeeping용**이며 법적 증거는 hash-chained `audit.log`. verify 명령은 pixel 확장 여부와 무관하게 동일 동작.

운영자에게 보이는 차이는 verify 성공 출력 하단에 선택적 **event breakdown**(namespace별 count — `agent.*`, `pacs.*`, `deid.*`, **`pixel.*`** (NEW v0.2), `upload.*`, `audit.anchor`) 요약 라인 추가.

### 2.7 `gateway-agent version` 확장

v0.1 출력에 `ruleset v0.1.0 + pixel v0.1` 라벨 추가 + `pytesseract`, `tesseract`, `pydeface`, `FSL flirt` 4개 라인(버전) 추가. 기본(non-pixel) 이미지에서는 이 4라인에 `(absent)` 표기.

### 2.8 종료 코드 요약 (pixel 관련 추가 행 포함)

design-spec-gateway-agent §3.9 표를 확장.

| Command | 0 | 1 | 2 | 3 | 4 | 64 | 69 | 70 |
|---------|---|---|---|---|---|----|----|----|
| `start` | 정상 | — | — | — | — | Config 오류 | PACS 초기 실패 | 내부 오류 |
| `sync-once` | 전체 성공 | 1건 이상 실패 | — | — | — | Config 오류 | — | — |
| `status` | OK | DB 접근 불가 | — | — | — | — | — | — |
| `de-id-test` | 통과 | 파일 오류 | 메타 PHI 잔존 | **픽셀 격리 사유** | **픽셀 엔진 없음** | — | — | — |
| `pixel-selftest` | OK | **OCR 실패** | **Defacing 실패** | **둘 다 실패** | — | — | — | 픽스처 손상 |
| `audit verify` | 체인 OK | 체인 불일치 | 파일 없음 | — | — | — | — | — |
| `version` | 항상 0 | — | — | — | — | — | — | — |

굵은 항목이 v0.2 신규.

---

## 3. Config UX

### 3.1 `deid.pixel.*` 서브트리 — 주석 포함 예시

기존 `/etc/radivault/gateway.yml`의 `deid:` 블록에 추가되는 **주석 포함 production-ready 예시**. 기본값은 **OFF**(opt-in). v0.1 키(`ruleset_version`, `salt`, `retain_options`, `burnin_quarantine_modalities`)는 변경 없음.

```yaml
deid:
  # (v0.1 기존 키 그대로)
  # ─────────── De-ID Pixel (v0.2 신규) ─────────────
  # 번인 텍스트 OCR 마스킹 + 두경부 CT/MR 얼굴 defacing.
  # 반드시 radivault-gateway:0.2.0-pixel 이미지에서만 enabled: true.
  pixel:
    enabled: false                   # 마스터 킬 스위치. 기본 OFF.
                                     # true 로 바꾸기 전 pixel-selftest 실행 필수.
    quarantine_on_failure: true      # 엔진 실패 시 격리 폴백. 기본 true.
    ocr:
      enabled: true                  # pixel.enabled=true 일 때만 유효.
      engine: tesseract              # tesseract | paddleocr
      languages: ["kor", "eng"]      # 빈 배열 금지.
      confidence_threshold: 0.60     # 0..1. 낮추면 재현율↑ 정밀도↓.
      redaction_fill: solid_black    # solid_black | mean_pixel | gaussian_blur
      box_padding_px: 2              # 잔여 텍스트 잦으면 4 로.
      residual_recheck: true         # redaction 후 재OCR. 기본 true.
      modality_allowlist: ["SC", "OT", "US", "XA", "MG"]
    defacing:
      enabled: true
      library: pydeface              # pydeface | mridefacer
      fallback: true                 # pydeface 실패 시 mridefacer 시도.
      on_missing: disable            # disable | fail_start
      modalities: ["CT", "MR"]       # CT 부정합 우려 시 ["MR"] 보수화.
      body_parts: ["HEAD", "BRAIN", "NEURO", "STROKE"]
      exclusion_patterns:            # StudyDescription regex → 매칭 시 defacing 금지 + 격리.
        - "(?i)dental"
        - "(?i)\\bENT\\b"
        - "(?i)facial[ _-]?trauma"
        - "(?i)maxillofacial"
        - "(?i)sinus"
        - "(?i)orbit"
        - "(?i)ophthalm"
        # 한국어 키워드 파일럿에서 실측 후 보강: "치과" / "부비동" / "안와" / "안과"
      min_removed_ratio: 0.05        # 얼굴 bbox 내 제거 복셀 비율 하한.
      residual_voxel_check: true
```

### 3.2 3 단계 프리셋 — 운영자가 복붙해서 시작하는 법

운영자는 다음 3개 블록 중 하나를 **현재 단계에 맞춰** 선택해 `deid.pixel:` 아래에 복사한다.

#### 3.2.1 **Preset A — 기본값 (변경 없음, v0.1 동작 그대로 유지)**

```yaml
deid:
  pixel:
    enabled: false       # 끝. 이거 하나로 v0.1 동작.
```

이 상태에서는 `-pixel` 이미지여도 픽셀 엔진이 생성되지 않고 CPU/메모리 소비도 없다.

#### 3.2.2 **Preset B — 파일럿 활성 (opt-in, 초기 48시간 모니터링)**

```yaml
deid:
  pixel:
    enabled: true
    quarantine_on_failure: true
    ocr:
      enabled: true
      engine: tesseract
      languages: ["kor", "eng"]
      confidence_threshold: 0.70         # 초기 보수(0.60→0.70).
      redaction_fill: solid_black
      residual_recheck: true
      modality_allowlist: ["SC", "OT", "US"]    # XA/MG 는 2주 후 확장.
    defacing:
      enabled: true
      library: pydeface
      fallback: true
      on_missing: disable                # 라이브러리 부재 시 조용히 OFF.
      modalities: ["MR"]                 # CT 는 2주 후 확장 (open Q #11).
      body_parts: ["HEAD", "BRAIN", "NEURO"]
      min_removed_ratio: 0.05
      residual_voxel_check: true
```

#### 3.2.3 **Preset C — 프로덕션 활성 (임상 리뷰 통과 후)**

Preset B 에서 차이점만 표기:

- `ocr.confidence_threshold: 0.60` (기본값 복원)
- `ocr.modality_allowlist: ["SC", "OT", "US", "XA", "MG"]` (전체)
- `defacing.on_missing: fail_start` (의존성 부재를 기동 거부로)
- `defacing.modalities: ["CT", "MR"]` (CT 포함)
- `defacing.body_parts: ["HEAD", "BRAIN", "NEURO", "STROKE"]` (전체)
- `defacing.exclusion_patterns`: §3.1 예시의 7개 영문 + 파일럿에서 확인된 한국어 키워드(`"치과"`, `"부비동"`, `"안와"`).

### 3.3 Config 검증 에러 UX (dev-spec §4.7 FR-40~44)

기존 `ERR_CFG_*` 포맷(design-spec-gateway-agent §4.5)을 재사용한다. pixel 전용 코드는 별도로 번호를 할당하지 않고 기존 `ERR_CFG_003`(타입 오류)/`ERR_CFG_004`(허용 값 아님)를 그대로 사용하며, **YAML 경로 + 수정 예시**로 pixel 컨텍스트를 설명한다.

단, **이미지 mismatch**는 config 검증을 통과한 후 **기동 단계**에 발견되므로 별도 코드 `ERR_CFG_PIXEL_ENGINE_MISSING`를 도입한다(§5 에러 택사노미).

**예시 (a) — engine 값 오타**

```
[ERR_CFG_004] 허용되지 않은 값 / Value not allowed
  파일     : /etc/radivault/gateway.yml
  경로     : deid.pixel.ocr.engine
  현재 값  : "tessaract"
  허용 값  : tesseract | paddleocr
  수정 예시:  engine: tesseract
  문서 링크: https://docs.radivault.io/gateway-agent/config#deid-pixel
```

**예시 (b) — 언어 빈 배열**

```
[ERR_CFG_003] 설정 검증 실패 / Config validation failed
  파일     : /etc/radivault/gateway.yml
  경로     : deid.pixel.ocr.languages
  현재 값  : []
  기대 형식: 1개 이상 항목의 문자열 리스트 (예: ["kor","eng"])
  수정 예시:  languages: ["kor", "eng"]
  문서 링크: https://docs.radivault.io/gateway-agent/config#deid-pixel-ocr
```

**예시 (c) — min_removed_ratio 범위 벗어남**

```
[ERR_CFG_003] 설정 검증 실패 / Config validation failed
  파일     : /etc/radivault/gateway.yml
  경로     : deid.pixel.defacing.min_removed_ratio
  현재 값  : 1.5
  기대 형식: 0.0..1.0 (소수)
  수정 예시:  min_removed_ratio: 0.05
  문서 링크: https://docs.radivault.io/gateway-agent/config#deid-pixel-defacing
```

**예시 (d) — pixel 활성이지만 이미지가 default variant**

```
[ERR_CFG_PIXEL_ENGINE_MISSING] 픽셀 엔진 부재 / Pixel engine missing
  config       : deid.pixel.enabled = true
  image_tag    : radivault-gateway:0.2.0           (expected: 0.2.0-pixel)
  missing      : tesseract binary, pydeface module
  수정 / Fix   : (a) `radivault-gateway:0.2.0-pixel` 로 이미지 전환
                 (b) 또는 deid.pixel.enabled=false
  문서 / Docs  : https://docs.radivault.io/gateway-agent/errors/ERR_CFG_PIXEL_ENGINE_MISSING
Exit 64.
```

**침묵 금지 원칙**: 이미지와 설정이 어긋나면 **즉시 기동 실패**. Silent downgrade 금지(`on_missing=fail_start` 설정 불필요 — 이 경우는 기본값 `disable`라도 OCR 필수이므로 기동 거부). `ocr` 엔진 누락은 기동 거부, `defacing` 엔진 누락만 `on_missing=disable` 시 자동 OFF 다운그레이드.

### 3.4 환경 변수 override

design-spec-gateway-agent §4.4 패턴 준수:

- `RADIVAULT_DEID_PIXEL__ENABLED=true`
- `RADIVAULT_DEID_PIXEL__OCR__CONFIDENCE_THRESHOLD=0.7`
- `RADIVAULT_DEID_PIXEL__DEFACING__MODALITIES=MR` (쉼표 구분 list)

### 3.5 Getting Started — 3-Step (v0.1 배포 운영자용)

기존 Gateway v0.1을 **이미 운영 중**인 병원에서 pixel을 켜는 최소 3 스텝. 풀 온보딩은 §7.

```
┌────────────────────────────────────────────────────────────┐
│ Step 1. 이미지 pull + pixel-selftest 통과                  │
├────────────────────────────────────────────────────────────┤
│ $ docker pull radivault-gateway:0.2.0-pixel                │
│ $ docker run --rm radivault-gateway:0.2.0-pixel \          │
│      pixel-selftest                                        │
│ -> Exit 0 확인. 실패 시 이미지 재다운로드 또는 지원 문의.  │
└────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────┐
│ Step 2. 설정 — Preset B 복사 + 이미지 태그 스위치          │
├────────────────────────────────────────────────────────────┤
│ $ sudo vi /etc/radivault/gateway.yml                       │
│   # deid.pixel: 블록 아래 §3.2.2 Preset B 복붙              │
│ $ sudo vi /opt/radivault/docker-compose.yml                │
│   # image: radivault-gateway:0.2.0  →  :0.2.0-pixel         │
│ $ sudo docker compose up -d                                │
└────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────┐
│ Step 3. 48h 모니터링                                        │
├────────────────────────────────────────────────────────────┤
│ $ gateway-agent status          # Pixel stage 섹션 확인     │
│ $ curl localhost:9090/metrics | grep radivault_gateway_pixel │
│ Prometheus 알림 6개(§4.3) 모두 정상 범위인지 확인.          │
└────────────────────────────────────────────────────────────┘
```

---

## 4. 로그 및 관측성 (Logs & Observability)

### 4.1 로그 필드 추가

기존 pipeline 로그(`radivault.pipeline`) 스키마에 아래 필드 추가. **원문 OCR 텍스트는 절대 기록 금지**(dev-spec FR-38).

| 필드 | 타입 | 예시 | 언제 채워짐 |
|------|------|------|-----------|
| `pixel.stage` | string enum | `triage` \| `ocr` \| `deface` \| `verify` \| `skip` \| `quarantine` | 모든 픽셀 단계 |
| `pixel.library` | string | `tesseract` \| `paddleocr` \| `pydeface` \| `mridefacer` \| null | OCR/deface 실행 시 |
| `pixel.library_version` | string | `5.3.4` | 동일 |
| `pixel.duration_ms` | integer | `4123` | 단계 완료 시 |
| `pixel.confidence_p50` | float 0..1 | `0.84` | OCR 완료 시 |
| `pixel.confidence_p10` | float 0..1 | `0.67` | OCR 완료 시 (꼬리값) |
| `pixel.redaction_count` | integer | `46` | OCR redaction 완료 시 |
| `pixel.defaced_voxel_ratio` | float 0..1 | `0.318` | defacing 완료 시 |
| `pixel.decision` | enum | `OCR_REQUIRED` \| `OCR_CONDITIONAL` \| `SKIP` | triage 단계 |
| `pixel.reason` | string | `modality_allowlist=US` | triage/skip/quarantine 시 |
| `pixel.error_code` | string | `ERR_PIXEL_RESIDUAL_TEXT` | quarantine/failure 시 |

**절대 기록 금지 필드**: OCR 텍스트 원문, box의 절대 pixel 좌표(상대 % 만 허용), 원본 SOPInstanceUID, 원본 PatientID.

### 4.2 로그 레코드 예시 — 5종 현실 시나리오

모두 JSON-lines 한 줄 = 한 이벤트.

**(1) triage → skip (pixel-skip happy-path)**

```json
{"ts":"2026-04-22T10:12:03Z","level":"INFO","logger":"radivault.pipeline","event":"pixel.triage.decided","study":"2.25.aaaa","pixel":{"stage":"triage","decision":"SKIP","reason":"modality=CT burnin_annotation=NO","duration_ms":4}}
```

**(2) triage → OCR → success (US 번인 마스킹)**

```json
{"ts":"2026-04-22T10:14:21Z","level":"INFO","logger":"radivault.pipeline","event":"pixel.ocr.completed","study":"2.25.bbbb","pixel":{"stage":"ocr","library":"tesseract","library_version":"5.3.4","duration_ms":27812,"decision":"OCR_REQUIRED","reason":"modality_allowlist=US","confidence_p50":0.86,"confidence_p10":0.61,"redaction_count":46}}
```

**(3) OCR → 저신뢰 → quarantine**

```json
{"ts":"2026-04-22T10:16:08Z","level":"WARN","logger":"radivault.pipeline","event":"pixel.quarantined","study":"2.25.cccc","pixel":{"stage":"quarantine","library":"tesseract","library_version":"5.3.4","duration_ms":31240,"confidence_p50":0.42,"confidence_p10":0.18,"redaction_count":0,"error_code":"ERR_PIXEL_OCR_LOW_CONFIDENCE","reason":"no_box_above_threshold"}}
```

**(4) deface → 의료 제외 → quarantine**

```json
{"ts":"2026-04-22T10:18:44Z","level":"INFO","logger":"radivault.pipeline","event":"pixel.medical_exclusion.matched","study":"2.25.dddd","pixel":{"stage":"quarantine","library":null,"duration_ms":12,"error_code":"ERR_PIXEL_MEDICAL_EXCLUSION","reason":"exclusion_pattern=(?i)dental"}}
```

**(5) deface → success**

```json
{"ts":"2026-04-22T10:21:02Z","level":"INFO","logger":"radivault.pipeline","event":"pixel.deface.completed","study":"2.25.eeee","pixel":{"stage":"deface","library":"pydeface","library_version":"2.0.2","duration_ms":68412,"defaced_voxel_ratio":0.318}}
```

### 4.3 Prometheus 메트릭 — `radivault_gateway_pixel_*`

`/metrics` 엔드포인트(이미 v0.1에서 노출 가정; 없으면 dev-spec 확장 필요)에 추가되는 **최소 10종**. 모두 `pixel.enabled=true` 일 때만 노출.

| # | 메트릭 | 타입 | 라벨 | 의미 |
|---|-------|------|------|------|
| 1 | `radivault_gateway_pixel_studies_total` | counter | `stage` ∈ {triage,ocr,deface}, `result` ∈ {success,quarantine,fail} | 스터디 단위 스테이지별 결과 집계. |
| 2 | `radivault_gateway_pixel_ocr_duration_seconds` | histogram | `engine` ∈ {tesseract,paddleocr} | OCR 1 스터디 처리 시간(초). |
| 3 | `radivault_gateway_pixel_deface_duration_seconds` | histogram | `library` ∈ {pydeface,mridefacer} | Defacing 1 볼륨 처리 시간(초). |
| 4 | `radivault_gateway_pixel_ocr_confidence` | histogram | — | OCR 박스 단위 신뢰도 분포 0..1. 꼬리(p10) 관측용. |
| 5 | `radivault_gateway_pixel_ocr_redaction_regions` | histogram | — | 스터디당 redaction 박스 수 분포. |
| 6 | `radivault_gateway_pixel_deface_removed_voxel_ratio` | histogram | — | 제거된 얼굴 복셀 비율 분포 0..1. |
| 7 | `radivault_gateway_pixel_residual_text_found_total` | counter | — | 재검증 OCR에서 잔여 텍스트 발견 횟수. **>0 이면 치명**. |
| 8 | `radivault_gateway_pixel_residual_face_voxels_total` | counter | — | 재검증에서 얼굴 복셀 잔존 임계 위반 횟수. |
| 9 | `radivault_gateway_pixel_engine_unavailable_total` | counter | `engine` ∈ {tesseract,paddleocr,pydeface,mridefacer,flirt} | 엔진 호출 실패(바이너리/모듈 부재/crash) 횟수. |
| 10 | `radivault_gateway_pixel_medical_exclusion_hit_total` | counter | `reason` ∈ {dental,ent,facial_trauma,maxillofacial,sinus,orbit,ophthalm,korean_*} | 제외 패턴 매칭 횟수. StudyDescription 드리프트 감지. |

**버킷 권장**:

- `ocr_duration_seconds`: `0.1, 0.5, 1, 3, 5, 10, 30, 60, 120, 300`.
- `deface_duration_seconds`: `1, 5, 10, 30, 60, 90, 120, 180, 300, 600`.
- `ocr_confidence`: `0, 0.1, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0`.
- `deface_removed_voxel_ratio`: `0, 0.01, 0.03, 0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.0`.
- `ocr_redaction_regions`: `0, 1, 2, 5, 10, 25, 50, 100, 250, 1000`.

### 4.4 알림 설계 — 최소 6종

PromQL 식은 제안이며 팀 환경에 맞춰 조정. 알림은 **Slack `#radivault-gateway-ops` 채널 + PagerDuty(critical만)**로 라우팅(기존 v0.1 컨벤션 재사용).

| # | 알림명 | Severity | 조건 (window 5m) | 대응 Runbook |
|---|-------|---------|--------|-------------|
| A1 | **HighQuarantineRate** | warning | `rate(pixel_studies_total{result="quarantine"}[5m]) / rate(pixel_studies_total[5m]) > 0.30` | RB-PX-3 또는 RB-PX-4 (reason 라벨 확인). |
| A2 | **OcrEngineErrorsSpike** | critical | `increase(pixel_engine_unavailable_total{engine=~"tesseract\|paddleocr"}[5m]) > 3` | RB-PX-1 |
| A3 | **DefaceDurationRegression** | warning | `histogram_quantile(0.95, sum by (le) (rate(pixel_deface_duration_seconds_bucket[15m]))) > 180` | RB-PX-4 (성능 회귀 의심) |
| A4 | **ResidualTextDetected** | **critical** | `increase(pixel_residual_text_found_total[5m]) > 0` | RB-PX-3 (PHI 누출 리스크 — 즉시 대응) |
| A5 | **ResidualFaceVoxelsDetected** | **critical** | `increase(pixel_residual_face_voxels_total[5m]) > 0` | RB-PX-4 |
| A6 | **MedicalExclusionSpike** | warning | `increase(pixel_medical_exclusion_hit_total[1h]) > (avg_over_time(pixel_medical_exclusion_hit_total[24h]) * 3)` | RB-PX-5 (StudyDescription 패턴 드리프트) |

추가 보조 알림 (optional):

- **A7 OcrConfidenceP10Drop**: `histogram_quantile(0.10, ...pixel_ocr_confidence_bucket) < 0.40` 5분 지속 → OCR 환경(입력 해상도) 변동 의심.
- **A8 PixelFailedBacklog**: `gateway_studyjob_count{state="pixel_failed"} > 50` → 격리 큐 수동 QA 소진 지연.

---

## 5. 에러 택사노미 UX (5-field)

gateway-agent design-spec §5.5와 동일한 5-field 포맷(`code`, `ko_message`, `en_message`, `suggested_action`, `doc_link`)을 확장한 표. 본 절은 dev-spec §13의 풀 설명을 운영자·SRE가 **한 표에서 스캔**할 수 있게 정리한다.

### 5.1 신규 에러 코드 마스터 표 (8 ERR + 1 WARN + 1 CFG)

| Code | HTTP / CLI Exit | 한국어 | English | 언제 | 운영자 액션 | SRE 액션 | Doc |
|------|----------------|--------|---------|------|-----------|---------|-----|
| `ERR_PIXEL_OCR_LOW_CONFIDENCE` | — (internal; pipeline exit 0, study state=pixel_failed) | OCR 신뢰도가 임계 미만이어서 스터디를 격리했습니다. | OCR confidence below threshold; study quarantined. | OCR 감지 박스 전부 conf < threshold | `deid.pixel.ocr.confidence_threshold` 0.60 → 0.50 실험(임상 리뷰 필수) 또는 해당 모달리티 샘플 지원팀 송부 | 해당 모달리티 입력 해상도·포맷 조사; PaddleOCR 엔진 대체 후보 평가 | /errors/ERR_PIXEL_OCR_LOW_CONFIDENCE |
| `ERR_PIXEL_OCR_ENGINE_FAILURE` | CLI 4 (de-id-test); 1 (pixel-selftest) | OCR 엔진 실행 중 오류가 발생했습니다. | OCR engine runtime failure. | tesseract 바이너리 부재/크래시/kor 언어팩 부재 | `pixel-selftest` 실행으로 부재 컴포넌트 확인 → 이미지 재배포 | Tesseract CVE/버전 drift 조사, 런타임 오류 스택 수집 | /errors/ERR_PIXEL_OCR_ENGINE_FAILURE |
| `ERR_PIXEL_RESIDUAL_TEXT` | CLI 3 (de-id-test); internal | 마스킹 후 잔여 텍스트가 탐지되어 격리합니다. | Residual text detected after redaction; quarantined. | redaction 후 재OCR에서 conf ≥ threshold 텍스트 발견 | `box_padding_px` 2→4 / `redaction_fill` solid_black 강제 확인 / 동일 모달리티 반복 발생 시 지원팀에 샘플(원본 X, 해시만) 송부 | 재현 테스트 구성; 드리프트 원인 조사(입력 뷰어 바뀜?); alert A4 상태 확인 | /errors/ERR_PIXEL_RESIDUAL_TEXT |
| `ERR_PIXEL_DEFACE_LIBRARY_MISSING` | CLI 2 (pixel-selftest); startup (varies) | Defacing 라이브러리를 찾을 수 없습니다. | Defacing library unavailable. | pydeface 모듈 import 실패 또는 FSL flirt not on PATH | `-pixel` 이미지 확인; 또는 `deid.pixel.defacing.enabled=false`; `on_missing=disable`이면 자동 다운그레이드 | 이미지 빌드 파이프라인 점검; FSL 번들 재구성 | /errors/ERR_PIXEL_DEFACE_LIBRARY_MISSING |
| `ERR_PIXEL_DEFACE_FAILURE` | internal; pipeline logs WARN (fallback 시도) / ERROR (둘 다 실패) | Defacing 처리 중 런타임 오류가 발생했습니다. | Defacing runtime error. | FLIRT 수렴 실패 / NIfTI 변환 오류 / OOM | `fallback=true` 유지; 반복 발생 시 원본 샘플(DPO 승인 후)을 지원팀에 송부 | fallback 성공률 확인; mridefacer 단독 경로 회귀 평가; alert A3 | /errors/ERR_PIXEL_DEFACE_FAILURE |
| `ERR_PIXEL_RESIDUAL_FACE_VOXELS` | internal | Defacing 후 얼굴 복셀 잔존 비율이 임계 이상입니다. | Residual face voxels above threshold. | removed_voxel_ratio < min_removed_ratio (기본 0.05) | 해당 모달리티/시리즈 재시도 여부 확인; 임계값(0.05) 현장 적정성 재평가는 SRE 승인 필요 | 볼륨 통계 수집; pydeface 템플릿 정합 실패 패턴 분석; alert A5 | /errors/ERR_PIXEL_RESIDUAL_FACE_VOXELS |
| `ERR_PIXEL_MEDICAL_EXCLUSION` | internal (정책적 격리) | 의료 제외 리스트에 매칭되어 자동 defacing을 건너뛰고 격리합니다. | Medical exclusion match; defacing skipped, quarantined. | StudyDescription이 dental/ENT/orbit 등 패턴에 매칭 | 임상 자문 후 사람이 업로드 판단; 오탐이면 `exclusion_patterns` 조정 | StudyDescription drift 지표 수집; alert A6 | /errors/ERR_PIXEL_MEDICAL_EXCLUSION |
| `ERR_CFG_PIXEL_ENGINE_MISSING` | CLI 64 (startup) | 설정에서 픽셀 처리를 활성화했으나 엔진 바이너리가 없습니다. | Pixel enabled in config but engine binary absent. | `pixel.enabled=true` 이면서 default(non-pixel) 이미지 사용 | 이미지 태그를 `:0.2.0-pixel`로 전환 또는 `enabled=false` | CI에서 이미지-설정 매트릭스 검증 확대 | /errors/ERR_CFG_PIXEL_ENGINE_MISSING |
| `WARN_PIXEL_HEURISTIC_TRIGGER` | — (informational) | 휴리스틱 사전검사가 번인 가능성을 감지했습니다(v0.2.1에서 활성). | Heuristic pre-scan suggests burn-in (enabled in v0.2.1). | v0.2에서는 no-op — 설계 placeholder. | 무시 가능. 잦으면 v0.2.1 우선순위 조정 요청. | 로그 집계만; 실제 동작은 v0.2.1. | /errors/WARN_PIXEL_HEURISTIC_TRIGGER |

### 5.2 출력 포맷 (재확인 — gateway-agent §5.5 재사용)

```
[<CODE>] <한국어 한 줄> / <English one line>
  <필드들 key: value 들여쓰기 2칸>
  수정 / Fix: <1줄 제안>
  문서 / Docs: https://docs.radivault.io/gateway-agent/errors/<CODE>
```

### 5.3 상태·로그 레벨 매핑 (dev-spec §13.9 재정리)

| Code | Log Level | 파이프라인 결과 | state 전이 | Alert |
|------|-----------|----------------|-----------|-------|
| `ERR_PIXEL_OCR_LOW_CONFIDENCE` | WARN | 격리 | `pixel_failed` | A1 |
| `ERR_PIXEL_OCR_ENGINE_FAILURE` | ERROR | 격리 또는 기동 실패 | `pixel_failed` (or startup exit) | A2 |
| `ERR_PIXEL_RESIDUAL_TEXT` | **ERROR** | 격리 | `pixel_failed` | **A4 (critical)** |
| `ERR_PIXEL_DEFACE_LIBRARY_MISSING` | WARN → ERROR(fail_start 모드) | 다운그레이드 또는 기동 실패 | (startup) | A2 side |
| `ERR_PIXEL_DEFACE_FAILURE` | WARN(폴백 시도) → ERROR(둘 다 실패) | 격리 | `pixel_failed` | A3 |
| `ERR_PIXEL_RESIDUAL_FACE_VOXELS` | **ERROR** | 격리 | `pixel_failed` | **A5 (critical)** |
| `ERR_PIXEL_MEDICAL_EXCLUSION` | INFO | 격리(정책적) | `pixel_failed` | A6 |
| `ERR_CFG_PIXEL_ENGINE_MISSING` | ERROR | 기동 실패 | — (exit 64) | — |
| `WARN_PIXEL_HEURISTIC_TRIGGER` | WARN | 무변경(v0.2) | — | — |

---

## 6. Runbooks

각 Runbook 포맷: **증상 / 첫 5분 / 격리 / 복구 / 사후검토**. 실행자는 "운영자 1티어 → SRE 2티어"로 에스컬레이션. Gateway v0.1 runbook은 design-spec-gateway-agent에 존재 가정(없다면 별건).

### 6.1 RB-PX-1 — OCR 엔진 불가 (Tesseract / 언어팩 누락)

- **증상**: `status` `Pixel stage.engines` 라인 `[ FAIL ]`; Alert A2 발사; `pixel-selftest` exit 1/3.
- **첫 5분**: (1) `pixel-selftest --json`으로 누락 컴포넌트 확정. (2) `docker compose images`로 이미지 태그 확인 — `0.2.0-pixel`이 아니면 RB-PX-2로 분기. (3) `docker logs --since 10m | grep ERR_PIXEL_OCR_ENGINE_FAILURE`로 최근 실패 스터디 카운트.
- **격리**: 옵션 A (임시, 권장) `deid.pixel.enabled=false`로 v0.1 동작 복귀 — 신규 스터디는 기존 격리 큐로. 옵션 B (부분) `ocr.enabled=false` 만 끄고 defacing 유지.
- **복구**: (1) `-pixel` 이미지 재pull + 재시작. (2) `pixel-selftest` exit 0. (3) config `enabled=true` 복원, `engines [ OK ]` 확인.
- **사후검토**: 이미지 태그 drift 원인(docker-compose.yml · CI/CD pin). A2 임계 적정성. 격리된 `pixel_failed` 스터디 재처리(open Q #9).

### 6.2 RB-PX-2 — Defacing 라이브러리 누락 (pixel 이미지 미배포)

- **증상**: `ERR_PIXEL_DEFACE_LIBRARY_MISSING` 기동 경고 또는 거부; `pixel-selftest` `[ DEFACING ] [ FAIL ]`. **더 위험한 상태**: Head CT/MR 스터디가 `RESIDUAL_FACE_VOXELS` 에러 없이 통과 업로드되고 있다면 defacing이 조용히 꺼진 상태.
- **첫 5분**: (1) `gateway-agent version`에서 `pydeface/FSL flirt (absent)` 확인. (2) `status --json | jq .pixel.engines.defacing`. (3) `audit.log` 최근 1시간 `pixel.deface.started` 이벤트 0이면 경로 OFF 확정.
- **격리**: 조용히 OFF된 경우 **즉시 `pixel.enabled=false` + Head CT/MR 업로드 중단**. 법적 안전 우선 — Alert 없이 수동 판단.
- **복구**: (1) `-pixel` 이미지 재배포(§7). (2) `pixel-selftest [ DEFACING ]` 전부 `[ OK ]`. (3) `on_missing=fail_start` 로 강화. (4) `enabled=true` 복원.
- **사후검토**: 프로덕션 `on_missing=fail_start` 기본화. Silent OFF 기간 audit.log에서 영향 스터디 추출 → Central과 사후 협의(open Q #9).

### 6.3 RB-PX-3 — 잔여 텍스트 탐지 급증 (OCR 회귀 / 번인 패턴 변화)

- **증상**: Alert A4 `ResidualTextDetected` **critical — 즉시 대응**; `pixel_residual_text_found_total` 증가; `status quarantine:residual_text > 0`.
- **첫 5분**: (1) 최근 1h `audit.log` `pixel.ocr.residual_check.failed` 이벤트 추출, 모달리티/병원 편향 판별. (2) 해당 스터디 모두 `state=pixel_failed` 확인. **이미 업로드된 게 있다면 최우선 Central 삭제 요청**.
- **격리**: `pixel.ocr.enabled=false`로 OCR 경로 차단 (격리 큐 사용). 범위가 넓으면 `pixel.enabled=false` 전면 차단.
- **복구**: 원인 후보 — (a) Tesseract 버전 drift, (b) 입력 뷰어 업데이트로 폰트 변경, (c) `box_padding_px=2` 신규 폰트에 부족. 로컬 `de-id-test --pixel --show-boxes`로 재현, `box_padding_px=4` + `redaction_fill=solid_black` 강제. 회귀 픽스처 추가. `sync-once --limit 10 --dry-run` 검증 후 재활성.
- **사후검토**: "PHI 유출 가능성 사건"으로 DPO 별도 보고. Ruleset bump(`v0.1.0` → `v0.1.1`) 고려. 개인정보보호법 유출 신고 대상 여부 법무 confirm.

### 6.4 RB-PX-4 — 얼굴 복셀 잔존 급증 (Defacing 조용한 실패)

- **증상**: Alert A5 `ResidualFaceVoxelsDetected` **critical**; `status quarantine:residual_face > 0`; `deface_removed_voxel_ratio` 낮은 버킷으로 쏠림.
- **첫 5분**: (1) `audit.log` `pixel.deface.residual_check.failed` 이벤트 카운트. (2) `docker logs`에서 `FLIRT did not converge` 탐색. (3) Alert A3(duration regression)과 상관 확인.
- **격리**: `defacing.library: mridefacer` 임시 전환. 실패 시 `defacing.enabled=false` — Head CT/MR 업로드 중단.
- **복구**: 합성 head 픽스처 `pixel-selftest` 재실행; FSL flirt 버전 drift 확인 후 재빌드. `min_removed_ratio` 임계(0.05)는 SRE 승인 없이 변경 금지.
- **사후검토**: 리서치 §4.7.2의 0.05 값 현장 유효성 재측정(open Q #8). 임상 리뷰어에게 해당 기간 샘플 10건 이상 재검토 요청.

### 6.5 RB-PX-5 — 의료 제외 매칭 비율 급등 (StudyDescription 드리프트)

- **증상**: Alert A6 `MedicalExclusionSpike`(warning); 특정 reason 카운터가 24h 평균의 3배.
- **첫 5분**: `audit.log` `pixel.medical_exclusion.matched` 에서 매칭된 StudyDescription **해시/샘플 패턴** 수집(원문 기록 금지). 모달리티/병원/스캐너 편향 분석.
- **격리**: 당장 PHI 리스크 없음(이 경로는 격리 라우팅). SLA 대응 불필요. 격리 큐 수동 QA 부담 증가만 통보.
- **복구**: 신규 패턴 샘플 → 임상 리뷰어 검토. 오탐이면 regex 좁힘(`(?i)\bdental\b` word boundary). 진짜 ROI 증가면 정상 동작 — open Q #9 재처리 경로와 연결.
- **사후검토**: 분기별 StudyDescription 코퍼스 재수집. dev-spec §11 open Q #4 해소 근거 축적.

### 6.6 RB-PX-6 (Optional) — 과-defacing 의심 (임상 리뷰어 제보)

- **증상**: 임상 리뷰어가 §8 스프레드시트에 `over_deface` 1건 이상 기록. 기계적 감지 없음.
- **첫 5분**: 리뷰어로부터 `pseudo_study_uid` + 문제 슬라이스 좌표 수집(원본 PID 교환 금지). `audit.log` · `pixel_audit_event`에서 해당 study의 deface duration·ratio·fallback 여부 확인.
- **격리**: 동일 모달리티·패턴 세트 반복 시 `modalities: ["MR"]`로 축소 또는 `enabled=false`.
- **복구**: DPO 승인 후 재현 환경에서 `mridefacer` fallback 결과 비교. `exclusion_patterns`에 누락 키워드(e.g. `"trauma w/ eye"`) 추가 검토.
- **사후검토**: 임상 피드백 design-spec 후속에 반영. 과-defacing은 PHI 유출은 아니나 임상 오진 리스크 — open Q #12(법무+영업) 기록.

---

## 7. Docker 이미지 변형 온보딩

기존 `radivault-gateway:0.2.0`(default, slim)에서 `radivault-gateway:0.2.0-pixel`(OCR + defacing 포함)로 **live 운영 중인 병원**이 전환하는 절차.

### 7.1 7 스텝 요약 (flow)

```
1. 사전 체크  →  2. 이미지 pull  →  3. pixel-selftest (network=none)
→  4. config Preset B + compose 이미지 태그 변경  →  5. 48h 모니터링
→  6. Preset C 로 graduate  →  7. (언제든) Rollback
```

### 7.2 단계별 운영자 명령

**Step 1 — 사전 체크**

- `df -h /var/lib/docker` 에 최소 1.5 GB 여유(pixel 이미지 ~1.1 GB + 캐시).
- 파일럿 환자 동의서·DPO 승인 확보.
- v0.1 Gateway가 `radivault-gateway:0.2.0` 태그로 가동 중 확인.
- 파일럿 모달리티 범위 결정(예: US만 먼저, CT/MR 2주 후).
- 임상 리뷰어 확보 + §8 스프레드시트 템플릿 전달.

**Step 2 — 이미지 pull**

```
$ docker pull radivault-gateway:0.2.0-pixel          # ~850 MB 압축 / ~1.1 GB on-disk
$ docker run --rm radivault/gateway:0.2.0-pixel --version
```

**Step 3 — `pixel-selftest` (외부망 차단)**

```
$ docker run --rm --network=none \
    radivault/gateway:0.2.0-pixel pixel-selftest
```

`--network=none`으로 외부 접근 없이 검증 가능. Exit 0이어야 진행. 실패 시 RB-PX-1/RB-PX-2.

**Step 4 — config 전환 (모달리티 1개부터)**

```
# /etc/radivault/gateway.yml : §3.2.2 Preset B 복사, ocr.modality_allowlist: ["US"]로 좁힘.
# /opt/radivault/docker-compose.yml : image 태그를 :0.2.0-pixel 로.
$ sudo docker compose up -d gateway-agent
```

CT/MR는 여전히 v0.1 동작. US 스터디만 OCR 경로 진입.

**Step 5 — 48h 모니터링 체크리스트**

- `gateway-agent status` → `Pixel stage` 섹션 정상.
- Prom: `radivault_gateway_pixel_*` 10개 지표 값 있음.
- Alert A1..A6 정상 범위.
- 임상 리뷰어 샘플 10–20% 이상 검토 완료.
- 매일 `gateway-agent audit verify` pass.

**Step 6 — Graduate to Preset C**

48h 정상 + 임상 리뷰어 sign-off 후 `gateway.yml`을 Preset C(§3.2.3)로 교체 → `docker compose restart gateway-agent`.

### 7.3 Rollback 플랜

**언제**: Alert A4/A5 발사 + 원인 불명; 임상 리뷰어 "부적합" > 5건; 운영팀 판단.

```
# Step R1. 이미지 태그 복귀
$ sudo vi /opt/radivault/docker-compose.yml
  # image: radivault/gateway:0.2.0-pixel  →  :0.2.0
# Step R2. config 비활성화
$ sudo vi /etc/radivault/gateway.yml
  # deid.pixel.enabled: false
# Step R3. 재시작
$ sudo docker compose up -d gateway-agent
# Step R4. 검증
$ gateway-agent status       # Pixel stage 섹션이 사라졌어야 함.
$ gateway-agent version      # pytesseract/pydeface (absent)
```

**데이터**: Rollback 시점까지 pixel 처리된 스터디는 이미 Central에 업로드된 상태. "픽셀 처리 적용 여부"는 `(0012,0063/0064)` DICOM 태그에 남아있어 Central에서 역추적 가능.

---

## 8. 임상 QA 워크플로우

**범위**: 파이프라인 코드 내부에 UI 없음. v0.2 MVP는 **외부 도구(PACS 뷰어 + 공유 폴더 + 스프레드시트)로 충분**. 정식 Clinician QA UI는 별건 dev-spec(`dev-spec-clinician-qa`, 미정).

### 8.1 샘플링 규칙

- **Target 비율**: 파일럿 **첫 2주**는 pixel-처리 스터디의 **10–20%**. 2주 후 임상 리뷰어 sign-off 시 5%로 축소.
- **추출 방법**: `pixel_audit_event` 테이블에서 `outcome='success'` 레코드를 무작위 N개. seed는 운영자가 로그에 명시.

```
$ sqlite3 /var/lib/radivault/state.sqlite3 <<SQL
SELECT pseudo_study_uid, created_at
  FROM pixel_audit_event
 WHERE outcome='success' AND op IN ('ocr','deface')
   AND created_at >= datetime('now','-7 days')
 ORDER BY RANDOM()   -- seed 로그에 기록: 'seed=20260422_sample1'
 LIMIT 50;
SQL
```

- 추출된 pseudo_study_uid 목록을 **공유 폴더**(병원 내부 NAS 또는 RadiVault 제공 S3 private bucket)에 DICOM 패키지로 복사. **원본 PID 절대 함께 쓰지 말 것**.

### 8.2 리뷰 툴 (v0.2 MVP)

- **PACS 뷰어 또는 OHIF**로 defacing/OCR 결과 육안 검토.
- **Google Sheets / Excel (병원 내부)** — 필수 컬럼: `pseudo_study_uid`, `modality`, `study_description_redacted`, `reviewed_by`, `review_date`, `ocr_quality`, `defacing_quality`, `issues_found`, `disposition`.
- 값 enum:
  - `ocr_quality`: `OK` / `over_redaction` / `under_redaction` / `N/A (skip)`.
  - `defacing_quality`: `OK` / `over_deface` / `under_deface` / `N/A`.
  - `disposition`: `PASS` / `FAIL` / `RECHECK`.

### 8.3 Sign-off 기준 (프로덕션 graduation)

**임상 리뷰어가 서명해야 프로덕션(Preset C)로 전환**.

- [ ] 최소 **50건** 샘플 리뷰 완료.
- [ ] `disposition=FAIL` 비율 **< 5%**.
- [ ] `over_redaction` 0건.
- [ ] `over_deface` 1건 이하 (있다면 해당 케이스의 `exclusion_patterns` 보강 플랜 첨부).
- [ ] `under_redaction` (즉 잔여 텍스트) 0건 — 1건이라도 있으면 RB-PX-3 발동, graduation 연기.
- [ ] `under_deface` (즉 얼굴 재식별 가능) 0건 — 1건이라도 있으면 RB-PX-4 발동.

Sign-off 문서: **PDF 1장**(리뷰어 이름·서명·날짜·통계·권고사항). 보관은 DPO 책임.

### 8.4 에스컬레이션 경로

```
임상 리뷰어 "부적합" 발견
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. 스프레드시트 기록 (pseudo_study_uid + issue type + 슬라이스) │
│ 2. Slack #radivault-clinical-qa 에 비식별 요약 포스트            │
│ 3. (if over_redaction/over_deface)                              │
│       RB-PX-6 실행 → exclusion_patterns 검토                    │
│ 4. (if under_redaction)                                          │
│       IMMEDIATE → RB-PX-3 실행 → DPO 통보                       │
│ 5. (if under_deface)                                             │
│       IMMEDIATE → RB-PX-4 실행 → DPO 통보                       │
│ 6. Kyle 결재: 프로덕션 graduation 일정 조정                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. 국제화 (i18n)

design-spec-gateway-agent §8 규칙 확장.

| 표면 | 언어 | 근거 |
|------|------|------|
| CLI `--help` (신규 플래그 `--pixel` 포함) | ko + en 병기 | v0.1과 동일 원칙 |
| `pixel-selftest` 콘솔 출력 | ko + en 병기 | 운영자 한국어·오픈소스 영어 지원 |
| 에러 메시지 (ERR_PIXEL_*) | ko + en 병기 | §5 표 |
| audit log `pixel.*` 이벤트 | **영어 전용** | 기계 처리·중앙 anchor |
| Runbook (§6) | 한국어 전용 | 운영팀 내부 문서 |
| Config 주석 (§3.1) | ko + en 혼용 | 기존 gateway.yml 패턴 |
| Prom metric 이름·라벨 | 영어 | PromQL 호환 |
| Clinician QA 스프레드시트 | 한국어 필드 이름 + 영어 enum | 리뷰어 친화 |

**한국어 길이 규칙 재확인**: 콘솔 80열 기준 한 메시지 120 bytes. pixel 관련 메시지가 가장 긴 건 `ERR_PIXEL_RESIDUAL_FACE_VOXELS` ("Defacing 후 얼굴 복셀 잔존 비율이 임계 이상입니다." = 약 60 bytes) 로 제한 내.

**시간대**: 콘솔은 KST, audit.log·Prom은 UTC — v0.1 원칙 그대로.

---

## 10. 접근성 (Accessibility) — CLI 한정

GUI 관련 WCAG 항목은 **N/A — backend Gateway extension**.

유지해야 할 CLI 접근성:

| 항목 | 지침 | pixel 적용 |
|------|------|-----------|
| 색 의존 금지 | `[ OK ]` / `[ FAIL ]` / `[ WARN ]` 텍스트 라벨. 색은 보조. | `pixel-selftest`, `status` 의 `Pixel stage` 섹션, `de-id-test --pixel` 동일. |
| `--no-color` / `NO_COLOR=1` | 완전 비활성 | 동일 |
| UTF-8 | 한글 출력 + 박스 문자 `╔═╗` | `LANG=C` fallback ASCII 유지 (`+---+`) |
| JSON 출력 옵션 | 기계 파서블 | `pixel-selftest --json`, `status --json`의 `pixel` 블록 |
| 키보드 전용 | `--watch` Ctrl-C 종료 명시 | 신규 명령 없음 (pixel-selftest는 즉시 종료) |
| 키 chord/단축키 | N/A — CLI tool | — |
| 스크린리더 | 일반적 CLI 대상 아님 | — |
| 색각 이상자 | `[ OK ]`/`[ FAIL ]` 텍스트 로 구분 | 동일 |

---

## 11. 수용 기준 (AC — 디자인 측)

`@qa` 가 라인별로 검증. 모두 **binary pass/fail**.

- [ ] **AC-D-1** `gateway-agent de-id-test --help`에 `--pixel`, `--ocr-only`, `--deface-only`, `--both`, `--show-boxes`, `--show-voxel-stats` 플래그가 모두 표기되고 설명이 ko+en 병기이다 (§2.3.1).
- [ ] **AC-D-2** `gateway-agent pixel-selftest --help` 가 §2.4.1 포맷과 일치하며 exit code 0/1/2/3/70 5종이 명시된다.
- [ ] **AC-D-3** `pixel-selftest` 의 happy-path 출력이 `[ OCR ]` / `[ DEFACING ]` 2 섹션 + `Summary` 1 라인 구조를 따른다.
- [ ] **AC-D-4** `pixel-selftest --json` 출력이 `ocr`, `defacing`, `summary` 3 블록 + `exit_code` 키를 포함한다.
- [ ] **AC-D-5** `gateway-agent status` 의 `Pipeline (24h)` 섹션에 `pixel_deided` 와 `pixel_failed` 카운트 라인이 추가되고 `[v0.2]` 라벨이 달린다.
- [ ] **AC-D-6** `gateway-agent status` 의 `Pixel stage` 섹션이 80열 레이아웃을 넘지 않는다(`wc -L` ≤ 80).
- [ ] **AC-D-7** `status --json` 출력에 최상위 `pixel` 블록이 있고, `engines.ocr.{name,version,status}`, `engines.defacing.{name,version,status}`, `triage_24h`, `ocr_24h`, `deface_24h`, `quarantine_24h`, `engine_errors_24h` 7 필드를 포함한다.
- [ ] **AC-D-8** `deid.pixel.enabled=false` 일 때 `status` 출력에 `Pixel stage` 섹션이 **완전히 생략**된다 (v0.1 레이아웃과 byte-equivalent).
- [ ] **AC-D-9** §3.2 3 단계 프리셋(A/B/C) 문서가 그대로 복사 붙여넣기 가능한 YAML 이며 pydantic validation을 통과한다.
- [ ] **AC-D-10** §3.3 config 에러 메시지가 `[코드] 한국어 / English + 파일 + 경로 + 현재 값 + 기대 형식 + 수정 예시 + 문서 링크` 7 항목을 포함한다.
- [ ] **AC-D-11** §4.1 로그 필드 추가 테이블의 11개 필드 중 `pixel.text*` / `pixel.raw_ocr*` / `pixel.absolute_coord*` 와 같은 **PHI/금지 필드가 존재하지 않는다**(네임 grep 검증).
- [ ] **AC-D-12** §4.3 Prometheus 메트릭 10종이 이름 접두사 `radivault_gateway_pixel_`로 시작하며, 각 히스토그램이 문서화된 버킷을 제공한다.
- [ ] **AC-D-13** §4.4 알림 A1–A6 6종이 모두 PromQL 식과 대응 Runbook 링크를 갖는다. A4/A5 2개는 severity=critical.
- [ ] **AC-D-14** `pixel-selftest` 명령은 기본(non-pixel) 이미지에서도 존재하며 exit 3(둘 다 누락)으로 실패한다. 즉 명령 존재 여부가 이미지 variant에 의존하지 않는다.
- [ ] **AC-D-15** §5.1 에러 코드 마스터 표가 `ERR_PIXEL_OCR_LOW_CONFIDENCE`, `ERR_PIXEL_OCR_ENGINE_FAILURE`, `ERR_PIXEL_RESIDUAL_TEXT`, `ERR_PIXEL_DEFACE_LIBRARY_MISSING`, `ERR_PIXEL_DEFACE_FAILURE`, `ERR_PIXEL_RESIDUAL_FACE_VOXELS`, `ERR_PIXEL_MEDICAL_EXCLUSION`, `ERR_CFG_PIXEL_ENGINE_MISSING`, `WARN_PIXEL_HEURISTIC_TRIGGER` 9 코드를 모두 담는다.
- [ ] **AC-D-16** 각 에러 코드 행이 8 필드(code/exit/ko/en/trigger/operator_action/sre_action/doc_link)를 채운다 — 빈 칸 없음.
- [ ] **AC-D-17** §6 Runbook 6건(RB-PX-1..6)이 "증상/첫 5분/격리/복구/사후검토" 5 섹션을 모두 포함하며 각 3문 이상.
- [ ] **AC-D-18** `de-id-test --pixel --show-boxes` 출력에 **OCR 원문 텍스트 문자열이 존재하지 않는다** — 해시(`sha256:...`) + 상대 좌표(%)만.
- [ ] **AC-D-19** Rollback 플랜(§7.3)이 4 스텝(이미지 복귀 → config 비활성 → 재시작 → 검증)으로 명시되며 각 스텝에 구체 명령 또는 편집 지점이 있다.
- [ ] **AC-D-20** 임상 QA 워크플로우(§8)에 sign-off 기준이 5항목 이상 명시되고, under_redaction=0·under_deface=0 이 필수 조건이다.

---

## 12. 오픈 질문 (@designer 차원에서 열어둠 — Kyle/@developer 결정 필요)

dev-spec §11의 12개 중 **디자인 표면 결정이 필요한 것**만 재발췌. 해소되지 않으면 본 문서 v0.2 업데이트에서 반영.

1. **Doc 링크 호스팅 (§5)**: `docs.radivault.io/gateway-agent/errors/ERR_PIXEL_*` 9개 신규 라우트 생성 책임자/타이밍 — gateway v0.1 동일 오픈 질문과 연결. v0.1에서 미해소.
2. **`pixel-selftest` 네이밍 (dev-spec §11 Q7)**: `gateway-agent pixel-selftest` vs `gateway-agent selftest --pixel`. 본 문서는 전자를 채택하나 Kyle 최종 결정 대기.
3. **`--plain` ASCII 폴백**: v0.1 open Q와 동일. Pixel stage 섹션 추가로 박스 렌더링 지점이 1곳 늘어 위험 증가.
4. **`Pixel stage` 섹션의 `[v0.2]` 라벨 표기 방식**: 본 문서는 텍스트 라벨을 제안. 대안: 섹션 헤더에 `✨`/`NEW` 등 기호. 접근성 충돌 가능 — Kyle 결정.
5. **Alert A4/A5 critical severity 채널**: PagerDuty 페이지 즉시 vs 15분 유예. SRE 리소스 계획 의존.
6. **Clinician QA 외부 도구 (§8)**: MVP 스프레드시트 접근 방식(Google Sheets 병원 내부 공유 vs 종이 출력 vs 내부 wiki) — 병원별 상이. 본 문서는 "스프레드시트 허용" 수준만 명시.
7. **Sign-off 샘플 수 50건**: 지나치게 많거나 적을 수 있음. 리서치 §4.7.3의 10–20% 비율과 상충하지 않음을 현장에서 재검증 필요.
8. **`ERR_CFG_PIXEL_ENGINE_MISSING` 신규 코드 번호**: 기존 `ERR_CFG_*` 번호 공간과 충돌 없는지 중앙 레지스트리 필요. 제안: `ERR_CFG_020` 예약.
9. **`--show-boxes` 출력에 bbox 좌표 % 표기 정확도**: 상대 % 만 허용하나 재구성 공격(aspect ratio 역산)이 이론상 가능. 보수적으로 **% 반올림 5 단위**로 제한할지.
10. **PaddleOCR 이미지(`0.2.0-pixel-paddle`)의 온보딩 워크스루**: 본 문서는 기본 pixel(Tesseract)만 다룸. Paddle 파일럿 시 §7 복제 버전 필요.

---

## 13. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-22 | @designer (Claude Opus 4.7) | 최초 작성. dev-spec-de-id-pixel v0.1 기반. CLI(`de-id-test --pixel`, `pixel-selftest`, `status` 확장), Config UX(3-preset + 검증 에러), 로그(11 필드) + Prom 10 메트릭 + 알림 6종, 에러 택사노미 9 코드(5-field), Runbook 6건(RB-PX-1..6), Docker 변종 온보딩 7 스텝 + Rollback, 임상 QA MVP 워크플로우. 20 AC, 10 open Q. v0.1 CLI/로그 형식 하위 호환 확인. |

---

### NEXT_STEP

- 완료 산출물: `docs/specs/design-spec-de-id-pixel.md` (v0.1 Draft, 20 AC / 9 error codes / 6 runbooks / 10 Prom metrics / 6 alerts).
- 제안 다음 단계: **@developer** — `claude` 브랜치에서 `de-id-pixel` 구현 착수. 본 디자인 명세의 §2 CLI 구조, §3 Config 프리셋·검증 에러, §4 로그 필드·메트릭 이름, §5 에러 택사노미(9 코드), §6 Runbook 트리거 조건(alert 정의), §7 Docker 변종 태그 전략을 구현 기준으로 반영. dev-spec §10 AC와 본 문서 §11 AC-D-1..20 을 모두 충족해야 함.
- 병렬 진행 금지: `@developer` 착수 전에 Kyle이 §12 open Q 중 **#1 (doc 링크), #2 (selftest 네이밍), #8 (ERR_CFG_020 번호)** 3건 결정 필요. 나머지 7건은 착수 후 별도 결정.
- Kyle 결정 필요 (긴급 → 착수 전): §12-1 doc site 링크 호스팅; §12-2 `pixel-selftest` vs `selftest --pixel`; §12-8 ERR_CFG_020 예약 번호.
- Kyle 결정 (선택, 파일럿 이후): §12-3 `--plain` 폴백; §12-4 `[v0.2]` 라벨 스타일; §12-5 A4/A5 PagerDuty 채널; §12-6/7 임상 QA 도구; §12-9 bbox % 정확도; §12-10 PaddleOCR 온보딩 문서.
