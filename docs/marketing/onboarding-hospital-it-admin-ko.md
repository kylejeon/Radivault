# RadiVault 온보딩 가이드 — 병원 전산실 실무자용

> **Status**: Draft — Kyle 리뷰 후 공개
> **문서 버전**: v0.1 (2026-04-22)
> **작성자**: @marketer (RadiVault)
> **대상 독자**: 병원 IT/전산실 실무자 (리눅스·Docker 기본 지식 있음)
> **소요 시간**: 최초 설치 30–60분 + 검증 1–2시간
> **외부 배포 금지** — 본 문서는 Kyle 승인 전까지 RadiVault 내부 및 파일럿 계약 체결 병원 전용입니다.

---

## 0. 이 문서를 읽기 전에

이 가이드는 병원의 **전산실 엔지니어**가 RadiVault **Gateway Agent**를 귀원 내부 서버에 설치하고 PACS와 연동하여 첫 데이터 동기화를 수행하기까지의 **실무 절차**를 정리한 것입니다. 마케팅 자료가 아니라 **기술 운영 문서**이며, 각 단계의 목적과 "왜 이렇게 하는가"를 한 줄씩 설명합니다.

이 문서에서 다루지 않는 것:
- 계약·수익 조건 → 별도 제안서 (`proposal-summary-hospital-ko.md`) 참조.
- RadiVault 중앙 서버(Zone 2) 내부 운영 → RadiVault 운영팀 내부 문서.
- 구매자(해외 AI 기업) 포털 사용법 → 본 가이드 범위 외.

v0.1은 **파일럿 단계**임을 먼저 말씀드립니다. 일부 기능(예: 번인 텍스트 자동 OCR 마스킹, 데이터 철회 자동 파이프라인)은 v0.2 이후로 일정화되어 있습니다. v0.1 범위와 v0.2 예정 기능은 본 문서에서 명시적으로 구분합니다.

---

## 1. 개요 — 무엇을 설치하게 되는가

### 1.1 한 문장 요약

귀원 전산실의 Ubuntu 서버 1대에 Docker Compose로 기동되는 **RadiVault Gateway Agent**를 설치합니다. 이 에이전트는 귀원 PACS에서 DICOM 영상을 가져와 **병원 내부에서** 완전히 익명화(de-identification)한 뒤, 익명화가 완료된 데이터만 TLS 1.3 아웃바운드 HTTPS로 RadiVault 중앙 서버에 전송합니다.

### 1.2 데이터가 어디에 남고 어디에 안 남는가 (중요)

```
┌──────────────────────────────── 귀원 내부 전산망 ────────────────────────────────┐
│                                                                                  │
│   ┌──────────┐        ┌───────────────────────────────────┐                     │
│   │   PACS   │───────▶│  Gateway Agent (Docker Compose)  │                     │
│   │  (DICOM) │  PACS  │  · DICOMweb QIDO/WADO client      │                     │
│   └──────────┘  내부  │  · De-ID Engine (PS3.15 Annex E)  │                     │
│                  통신 │  · Staging storage (임시)          │                     │
│                       │  · Audit log (hash-chain, 5년)     │                     │
│                       │  · UID 매핑 DB  ★ 병원 내부 한정   │                     │
│                       └────────────────┬──────────────────┘                     │
│                                        │                                         │
└────────────────────────────────────────│─────────────────────────────────────────┘
                                         │  (아웃바운드 전용 TLS 1.3 HTTPS)
                                         ▼
                     ┌──────────────────────────────────┐
                     │  RadiVault 중앙 (한국 리전 기본) │
                     │  · 익명화 완료 메타·영상만 수령   │
                     │  · 원본 UID·환자 식별자 미보관   │
                     └──────────────────────────────────┘

[병원 내부에만 남는 것]
  · 원본 DICOM(PACS)
  · 원본 UID ↔ 가명 UID 매핑 테이블 (SQLite, chmod 0600)
  · 환자별 날짜 오프셋 (SHA-256 해시 기반)
  · 로컬 감사 로그 (audit.log, hash-chained)
  · salt 파일 (암호화 키, chmod 0600)

[중앙으로 전송되는 것]
  · 가명 UID만 포함된 DICOM (PHI 태그 제거·대체·시프트 완료)
  · 익명화 이력 태그 ((0012,0062/0063/0064))
  · manifest.json (가명 UID, 파일 sha256, 익명화 방법 코드)
  · 감사 로그 head-hash (시간당 1회, 내용 아닌 요약 해시만)

[절대 전송되지 않는 것]
  · 원본 StudyInstanceUID, SeriesInstanceUID, SOPInstanceUID
  · 원본 PatientID, PatientName, 생년월일
  · 판독 의사 이름, 병원명, 내부 PACS 호스트명
  · UID 매핑 테이블 자체
```

이 구조가 **개인정보보호법 제28조의8(개인정보 국외이전 제한)** 에 부합하도록 설계된 핵심입니다. 완전 익명정보 이외의 데이터는 병원 경계를 넘지 않습니다.

### 1.3 v0.1 MVP 범위 (파일럿 단계)

| 포함 | 제외 (v0.2 이후 예정) |
|------|----------------------|
| DICOMweb(QIDO/WADO) 기반 PACS 수집 | DIMSE(C-FIND/C-MOVE) 폴백 |
| DICOM PS3.15 Annex E Basic Profile 메타데이터 익명화 | 번인 텍스트 픽셀 OCR 자동 마스킹 (v0.1은 격리만) |
| UID 가명화(SHA-256 + per-hospital salt) | 3D defacing (두개부 CT/MRI) |
| 환자별 날짜 오프셋 시프트 | 실시간 PACS Push 수신(SCP listener) |
| 번인/의심 모달리티 자동 격리 | RIS/EMR 판독문 연동 (HL7 v2/FHIR) |
| Hash-chained 감사 로그 + 시간당 중앙 앵커 | k-익명성 자동 검증 |
| 아웃바운드 HTTPS(TLS 1.3) 업로드 | Kubernetes/Helm chart |
| CLI 관리 도구, systemd 연동 | Web UI 대시보드 |
| 토큰 수동 회전 절차 | 토큰 자동 회전 |

---

## 2. 사전 준비 체크리스트

이 섹션은 **설치 착수 최소 1주일 전**에 귀원 전산실과 RadiVault 운영팀이 공동으로 확인해야 하는 항목입니다. 한 가지라도 충족되지 않으면 설치 일정 조정이 필요합니다.

### 2.1 서버 사양

| 항목 | 최소 | 권장 | 이유 |
|------|------|------|------|
| OS | Ubuntu 22.04 LTS x86_64 | 동상, 보안 업데이트 최신 | Docker Engine 지원·검증 완료 기준 |
| CPU | 4 vCPU | 8 vCPU | De-ID 병렬 처리 + 업로드 |
| RAM | 8 GB | 16 GB | DICOM 파싱 + SQLite WAL |
| 디스크 | 200 GB SSD | 500 GB SSD | Staging 1주치 + audit log 5년 |
| 네트워크 | 100 Mbps | 1 Gbps | 대용량 스터디 업로드 |

> **참고**: 위 권장값은 파일럿 단계 추정치이며, 실측 후 병원별로 재산정할 수 있습니다(placeholder — 실측 후 갱신 예정).

### 2.2 네트워크·방화벽

- **아웃바운드**: `*.radivault.io:443` 허용 (HTTPS). 전용 도메인은 계약 체결 시 확정.
- **인바운드**: **포트 개방 불필요**. Gateway Agent는 아웃바운드-only 설계.
- **내부**: Gateway 서버 → PACS DICOMweb 엔드포인트 TCP 허용.
- **프록시**: 병원 내 HTTPS 프록시가 있으면 `HTTPS_PROXY`/`NO_PROXY` 환경변수로 지정 가능.
- **DNS**: `*.radivault.io` 이름 해석 가능 여부 확인.

### 2.3 PACS DICOMweb 엔드포인트

- DICOMweb 표준(QIDO-RS, WADO-RS) 지원 확인 필요.
- 엔드포인트 예: `https://pacs.hospital.local/dicom-web`
- 인증 방식: Bearer 토큰 또는 Basic(username/password) 중 하나.
- 자가서명 인증서 사용 시 CA 번들 경로 확보.
- **DIMSE(C-FIND/C-MOVE)** 는 v0.1에서 미지원 — DICOMweb이 없으면 파일럿 일정 조정 필요.
- 벤더 예시: INFINITT, Orthanc, dcm4chee, 그 외 DICOMweb 호환 PACS.
- PACS 벤더의 **Conformance Statement** 문서를 사전에 제공해 주시면 상호 검증 시간이 단축됩니다.

### 2.4 Docker 환경

```
$ docker --version            # 24.0 이상
$ docker compose version       # v2.20 이상
```

- 설치 가이드: Ubuntu 공식 저장소 + Docker 공식 가이드.
- Non-root 사용자로 Docker 실행 가능해야 함 (또는 sudo 권한).

### 2.5 시크릿(자격 정보) 관리 정책

다음 4종의 시크릿이 병원 서버 `/etc/radivault/credentials/` 디렉터리(권한 0700)에 배치됩니다.

| 파일 | 용도 | 발급 주체 |
|------|------|----------|
| `gateway_id` | 중앙이 귀원에 발급한 고유 ID (UUID) | RadiVault 운영팀 |
| `upload_token` | 중앙 업로드 인증 Bearer 토큰 | RadiVault 운영팀 |
| `pacs_token` | 귀원 PACS 접근 자격 (Bearer or Basic) | 귀원 PACS 관리자 |
| `salt` | UID 가명화용 병원별 고유 salt (32 bytes hex) | RadiVault 운영팀 또는 귀원 생성 — 정책 TBD |

모든 파일 권한은 `chmod 0600` 필수. 컨테이너 외부 볼륨에 저장되며, 컨테이너는 non-root(UID 10001)로 읽기 전용 마운트됩니다.

> **salt 발급·회전 정책**은 Kyle 결정 대기 중입니다. 파일럿 초기에는 RadiVault 운영팀이 병원별 salt를 안전 채널(age/1Password)로 전달할 예정이며, 회전 주기는 연 1회를 권장하되 병원 요청 시 임시 회전이 가능합니다.

### 2.6 담당자 지정

| 역할 | 귀원 측 | RadiVault 측 |
|------|--------|--------------|
| 기술 1차 연락 | 전산실 담당자 1명 | SRE 1명 |
| 계약·DPO 승인 | 정보보호책임자 | PM |
| 긴급 장애 대응(24/7) | 전산실 on-call | 운영팀 on-call |

긴급 에스컬레이션 연락처는 §9에 정리됩니다.

---

## 3. 설치 단계 — 역할 분담

설치는 **RadiVault 운영팀(SRE)** 과 **귀원 전산실** 의 공동 작업입니다. 각 단계마다 누가 주도하는지를 명확히 구분합니다.

### 3.1 전체 플로우 요약

```
[1] 계약·법적 검토 완료                ─ RadiVault PM · 귀원 DPO
          │
          ▼
[2] Hospital 레코드 생성 (중앙 DB)     ─ RadiVault SRE
          │
          ▼
[3] 토큰·gateway_id 발급 + 암호화 전달 ─ RadiVault SRE → 귀원 전산실
          │
          ▼
[4] 병원 네트워크·PACS 사전 체크       ─ 귀원 전산실
          │
          ▼
[5] Gateway 번들 배포                  ─ 귀원 전산실
          │
          ▼
[6] 크리덴셜 배치 + gateway.yml 편집   ─ 귀원 전산실
          │
          ▼
[7] de-id-test → sync-once --dry-run   ─ 귀원 전산실 (독립 검증)
          │
          ▼
[8] 첫 실 업로드 (1건 지정)            ─ 공동 (양측 실시간 관찰)
          │
          ▼
[9] 중앙 측 수령 확인                  ─ RadiVault SRE
          │
          ▼
[10] 첫 anchor 수신 확인 (1h 후)        ─ RadiVault SRE
          │
          ▼
[11] systemd 전환 + 상시 운영 인계       ─ 공동
          │
          ▼
[12] 24h 소크 테스트 → GA 승격          ─ 공동
```

### 3.2 Step 1 — 사전 계약 (RadiVault PM)

| 확인 항목 | 책임 |
|----------|------|
| 데이터 제공 계약 체결 (DPO 서명 포함) | RadiVault PM + 귀원 DPO |
| 호스팅 리전 합의 (한국 기본) | 공동 |
| 허용 ruleset 버전 합의 (v0.1.0) | 공동 |
| 모달리티·연도 범위 합의 | 공동 |

왜 먼저: 이후 모든 기술 단계는 계약 범위 안에서만 수행됩니다.

### 3.3 Step 2 — Hospital 레코드 생성 (RadiVault SRE)

RadiVault 운영팀이 중앙 DB에 귀원 엔트리를 생성합니다. 귀원 전산실 측 수행 항목은 없습니다.

```
[SRE] $ ingest-admin init-hospital \
        --hospital-id hosp_<식별자> \
        --name "<귀원 공식명>" \
        --region KR-SE \
        --allowed-ruleset-versions '["v0.1.0"]' \
        --daily-byte-quota 214748364800      # 200 GB
```

왜 먼저: 토큰 발급, 업로드 검증, 감사 로그 모두 이 레코드를 기준으로 작동합니다.

### 3.4 Step 3 — 토큰 발급 및 안전 전달 (RadiVault SRE → 귀원)

```
[SRE] $ ingest-admin token issue \
        --hospital-id hosp_<식별자> \
        --expires-days 365 \
        --note "pilot-onboarding-<YYYY-MM>"
```

발급된 평문 토큰은 **한 번만 화면에 표시**되며, 즉시 `age` 또는 `1Password`로 암호화해 귀원 전산실 담당자 공개키 앞으로 전달됩니다. 평문 토큰은 이메일·메신저로 전달 금지.

귀원 전산실은 수신 후 `/etc/radivault/credentials/upload_token`에 저장하고 `chmod 0600` 적용.

왜 이렇게: 토큰이 한 번이라도 평문 채널(이메일·슬랙·문자)에 노출되면 발급 무효 처리하고 재발급합니다.

### 3.5 Step 4 — 병원 네트워크·PACS 사전 체크 (귀원 전산실)

```
# 아웃바운드 확인
$ curl -v https://ingest.radivault.io/healthz
  → {"status":"ok"}

# 중앙 버전 확인
$ curl -s https://ingest.radivault.io/v1/version | jq .
  → {"version":"0.1.0","git_sha":"...","api_contract_version":"1"}

# PACS DICOMweb 접근 확인 (예: QIDO-RS studies 엔드포인트)
$ curl -s -H "Authorization: Bearer $PACS_TOKEN" \
    "https://pacs.hospital.local/dicom-web/studies?limit=1" | jq .
```

왜 먼저: 네트워크 경계·PACS 인증이 모두 살아 있는 상태에서 시작해야 이후 단계의 실패 원인을 좁힐 수 있습니다.

### 3.6 Step 5 — Gateway 번들 배포 (귀원 전산실)

```
$ sudo mkdir -p /opt/radivault && cd /opt/radivault
$ curl -fsSL https://get.radivault.io/gateway/v0.1.0/bundle.tgz | sudo tar xz
$ ls
docker-compose.yml  .env.example  gateway.yml.example  systemd/  README.md
```

번들 포함 내용:
- `docker-compose.yml` — 서비스 정의
- `.env.example` — 비시크릿 환경 변수
- `gateway.yml.example` — 설정 템플릿
- `systemd/radivault-gateway.service` — systemd 유닛 예시
- `logrotate.d/radivault` — 감사 로그 회전 설정
- `README.md` — 최소 운영 지침

왜 이렇게: 패키지는 RadiVault 공식 서명 배포 경로로만 제공됩니다. 비공식 채널(압축 파일 직접 전달 등)은 금지.

### 3.7 Step 6 — 크리덴셜 배치 + gateway.yml 편집 (귀원 전산실)

```
# 크리덴셜 디렉터리 준비
$ sudo install -d -m 0700 /etc/radivault/credentials

# 중앙 발급 시크릿 배치
$ sudo tee /etc/radivault/credentials/gateway_id    >/dev/null < gateway_id.txt
$ sudo tee /etc/radivault/credentials/upload_token  >/dev/null < upload_token.txt
$ sudo tee /etc/radivault/credentials/pacs_token    >/dev/null < pacs_token.txt

# salt (중앙 제공이 기본, 자체 생성도 가능 — 정책 TBD)
$ sudo openssl rand -hex 32 | sudo tee /etc/radivault/credentials/salt >/dev/null

# 권한 조정
$ sudo chmod 0600 /etc/radivault/credentials/*
$ ls -l /etc/radivault/credentials/
-rw------- 1 root root  36 ... gateway_id
-rw------- 1 root root  72 ... upload_token
-rw------- 1 root root  72 ... pacs_token
-rw------- 1 root root  64 ... salt

# 설정 파일 편집
$ sudo cp gateway.yml.example /etc/radivault/gateway.yml
$ sudo vi /etc/radivault/gateway.yml
```

편집 필수 필드:

| 필드 | 예시 값 | 설명 |
|------|--------|------|
| `agent.hospital_id` | `"hosp_abc"` | 중앙 발급 ID |
| `agent.org_root_oid` | `"2.25.140737488355328"` | 중앙 발급 OID root |
| `pacs.base_url` | `"https://pacs.hospital.local/dicom-web"` | 귀원 PACS DICOMweb 루트 |
| `pacs.auth.type` | `"bearer"` 또는 `"basic"` | PACS 인증 방식 |
| `pacs.query.modalities` | `["CR","CT","MR","DX"]` | 수집 대상 모달리티 |
| `pacs.query.lookback_days` | `7` | 첫 동기화 조회 범위 |
| `central.base_url` | `"https://ingest.radivault.io"` | 중앙 엔드포인트 (계약별) |

왜 이렇게: 시크릿 파일 권한이 틀리면 에이전트가 기동 단계에서 실패하며 구체 에러 코드(`ERR_CFG_011`)로 안내됩니다.

### 3.8 Step 7 — de-id-test + sync-once --dry-run (귀원 전산실)

**설치 후 첫 업로드 이전에 반드시 수행하는 독립 검증 단계**입니다.

```
# (1) 샘플 DICOM 1건에 대한 익명화 시험
$ docker compose run --rm gateway-agent de-id-test /data/sample.dcm --show-diff
Input:  /data/sample.dcm  (CT, 512KB)
Tags removed:  PatientName, PatientID, InstitutionName, ...
UIDs replaced: 12/12  (deterministic pseudo)
Dates shifted: +1423 days
Reverify: PASS  (0 PHI tags remain)

# (2) 최근 1주일 3건 드라이런 — 실제 업로드는 하지 않음
$ docker compose run --rm gateway-agent sync-once \
    --since 2026-04-15 --until 2026-04-21 --dry-run --limit 3
[1/3] 2.25.aaaa  fetch 2.1s  deid 4.1s  UPLOAD-SKIPPED (--dry-run)
[2/3] 2.25.bbbb  fetch 1.8s  deid 3.9s  UPLOAD-SKIPPED (--dry-run)
[3/3] 2.25.cccc  fetch 2.3s  deid 4.4s  QUARANTINED (BurnedInAnnotation=YES)
Dry-run succeeded. No data was sent to central.
```

왜 이렇게: 이 단계는 **DPO와 전산실 담당자가 "우리 병원 데이터에서 어떤 태그가 실제로 사라지는지"를 자체 확인**할 수 있게 합니다. 중앙으로는 어떤 바이트도 전송되지 않습니다. `QUARANTINED` 결과는 번인 텍스트가 의심되어 자동 격리된 케이스이며 이는 정상 동작입니다.

### 3.9 Step 8 — 첫 실 업로드 (공동 작업)

- **귀원 전산실**: `docker compose run --rm gateway-agent sync-once --since <날짜> --until <날짜> --limit 1`
- **RadiVault SRE**: 동시에 중앙 로그 관찰 (`ingest.accepted` 이벤트, `hospital_id` 필터)
- 예상 시간: 30초–2분 (스터디 크기 의존).

기대 결과: 중앙에서 `201 Created` 응답 수신, `central_job_id` 발급, 가명 UID로만 저장. 귀원 쪽 SQLite에 `study_job.state='uploaded'` 기록.

### 3.10 Step 9 — 중앙 측 수령 확인 (RadiVault SRE)

```
[SRE] $ ingest-admin study show --pseudo-study-uid 2.25.xxxxx
# hospital_id, ingested_at, total_bytes, n_instances 가 manifest와 일치 확인
```

왜 이렇게: 수신된 스터디의 메타만 확인하며, 익명화된 데이터에서도 원본 UID·환자명은 DB 어디에도 존재하지 않음을 역검증할 수 있습니다.

### 3.11 Step 10 — 첫 감사 앵커 수신 확인 (1시간 후)

```
[SRE] $ ingest-admin anchor verify --hospital-id hosp_<식별자>
Verifying anchor chain for hosp_<식별자>...
Range: seq [1..1]  anchors=1
Continuity : PASS
Monotonic  : PASS
[OK] chain intact
```

왜 이렇게: Gateway Agent는 시간당 1회 로컬 감사 로그의 head hash를 중앙에 앵커합니다. 중앙 체인이 시작되어야 로컬 단독 변조 탐지가 가동됩니다.

### 3.12 Step 11 — 데몬 전환 + systemd 연동 (공동)

```
# docker compose 상시 기동
$ sudo docker compose -f /opt/radivault/docker-compose.yml up -d

# systemd 유닛 등록
$ sudo cp /opt/radivault/systemd/radivault-gateway.service /etc/systemd/system/
$ sudo systemctl daemon-reload
$ sudo systemctl enable --now radivault-gateway
$ systemctl status radivault-gateway
● radivault-gateway.service - RadiVault Gateway Agent
     Active: active (running) since ...
```

왜 이렇게: systemd로 래핑하면 재부팅·장애 시 자동 복구되며, `journalctl -u radivault-gateway` 로 표준 로그 확인이 가능합니다.

### 3.13 Step 12 — 24시간 소크 테스트 → GA 승격

- P2 이상 알람 없으면 GA(General Availability) 병원 목록에 추가.
- 1주일 뒤 감사 체인 재검증(`audit verify`) 정례 업무로 편성.

---

## 4. 첫 동기화 검증 방법

상기 §3.8~§3.11에서 이미 첫 업로드까지 기술했으므로, 이 섹션은 **운영 중 재검증**용 체크리스트입니다.

### 4.1 병원 측 자체 검증

```
# (a) 오늘 동기화 통계
$ docker compose exec gateway-agent gateway-agent status
Gateway Agent v0.1.0  (hospital_id=hosp_abc)
Last 24h:
  Processed : 342  (success)  /  3 (quarantine)  /  0 (failed)
  Uploaded  : 342  (median 8.2s)
  Staging   : 12% used  /  Stale: 0
  Audit     : head_seq=12847  head_hash=sha256:abcd...
  Errors    : 0

# (b) 감사 체인 주 1회 검증
$ docker compose exec gateway-agent \
    gateway-agent audit verify /var/log/radivault/audit.log
[OK] chain intact  seq_range=[0..12847]

# (c) 최근 1시간 로그
$ docker compose logs --since 1h gateway-agent | head -50
```

### 4.2 중앙 측 교차 검증 (SRE)

```
[SRE] $ ingest-admin anchor verify --hospital-id hosp_abc
[SRE] $ ingest-admin study list --hospital-id hosp_abc --since 24h
```

### 4.3 실패 지표 정의

| 지표 | 정상 | 경보 임계 |
|------|------|----------|
| 업로드 실패율(24h) | < 1% | >= 1% 연속 2회 |
| Staging stale count | 0 | >= 1 |
| Audit 체인 불일치 | 없음 | 1건 발생 시 즉시 P1 |
| Anchor lag | < 3h | >= 3h |

---

## 5. 일상 운영

### 5.1 모니터링 포인트

| 항목 | 위치 | 주기 |
|------|------|------|
| systemd 상태 | `systemctl status radivault-gateway` | 일 1회 |
| status 요약 | `gateway-agent status` | 일 1회 |
| 감사 체인 무결성 | `gateway-agent audit verify` | 주 1회 |
| Staging 디스크 사용률 | `df -h /var/lib/radivault` | 주 1회 |
| 최근 에러 | `journalctl -u radivault-gateway --since "1 day ago" -p err` | 이상 시 |

### 5.2 로그 위치

| 로그 | 경로 | 보존 기간 | 포맷 |
|------|------|----------|------|
| App 로그 | `/var/log/radivault/app.log` + journald | 30일 | JSON-lines |
| 감사 로그 | `/var/log/radivault/audit.log` | 최소 5년 | JSON-lines, hash-chained |
| 회전된 감사 로그 | `/var/log/radivault/audit.log.*` | 최소 5년 | 동상 |
| 격리된 DICOM | `/var/lib/radivault/quarantine/<pseudo_study_uid>/` | 수동 QA 후 삭제 | DICOM 원본 |

감사 로그 파일 권한은 `0600`으로 자동 설정되며, logrotate는 `copy-truncate 금지` — 회전 시 head_hash를 파일명에 포함해 체인을 이어 갑니다. 이 동작은 자동이며 수동 설정 변경을 권장하지 않습니다.

### 5.3 디스크 관리

- **Staging**: `max_disk_pct`(기본 80%) 초과 시 자동 backpressure 발동. 신규 PACS 페치 일시 중단. 해결: 디스크 증설 또는 retention 단축.
- **Audit log**: logrotate로 일 단위 회전. 파일명에 head_hash 포함.
- **격리 디렉터리**: 수동 QA(RadiVault 운영팀과 공동) 후 삭제.

### 5.4 토큰 회전

토큰 만료 30일 전 RadiVault SRE가 사전 통지합니다.

```
# 신규 토큰 발급 후 암호화 전달 수령 → 기존 파일 덮어쓰기
$ sudo tee /etc/radivault/credentials/upload_token >/dev/null < new_upload_token.txt
$ sudo chmod 0600 /etc/radivault/credentials/upload_token
$ sudo systemctl restart radivault-gateway
```

왜 이렇게: Gateway Agent는 기동 시 토큰을 로드하므로 재시작이 필요합니다. 다운타임은 수 초 수준이며 재시도 큐가 유지되므로 데이터 손실은 없습니다.

---

## 6. 장애 시 첫 대응 (티어 1 플레이북)

이 섹션은 귀원 전산실이 **first responder**로 수행할 수 있는 범위만 정리합니다. 2차 이상은 RadiVault 운영팀에 에스컬레이션합니다.

### 6.1 증상별 1차 대응

| 증상 | 1차 확인 | 해결 | RadiVault 호출 시점 |
|------|---------|------|---------------------|
| Gateway 컨테이너 중단 | `systemctl status radivault-gateway` | `systemctl restart radivault-gateway` | 재시작 후 60초 내 다시 중단 시 |
| 업로드 전부 실패 | `gateway-agent status` → `Errors` 섹션 확인 | 네트워크 확인(curl healthz) → 토큰 유효성 | 토큰 유효한데 401 지속 시 |
| 디스크 85% 초과 | `df -h`, staging stale 존재 여부 | 임시 증설 또는 staging 정리 | 30분 내 복구 불가 시 |
| 감사 체인 불일치 | `audit verify` 실패 seq 확인 | **즉시 중단 금지, 증거 보존** | **즉시 P1 — 30분 내** |
| PACS 연결 실패 | PACS 측 자체 점검 | PACS 복구 | Gateway 측 원인 의심 시 |

### 6.2 증거 수집 명령 (RadiVault 지원팀 전달용)

```
# 2개 파일 생성 — PHI 미포함 보장
$ docker compose logs --since 1h gateway-agent > /tmp/gw.log
$ gateway-agent status --json > /tmp/gw-status.json

# 안전 전달: 암호화 후 업로드
$ age -r <radivault_support_pubkey> /tmp/gw.log > /tmp/gw.log.age
$ age -r <radivault_support_pubkey> /tmp/gw-status.json > /tmp/gw-status.json.age
```

왜 이렇게: Gateway Agent의 감사 로그·app 로그는 설계상 가명 UID·해시만 포함합니다. 그러나 전달 채널(이메일 첨부 등)에서의 노출 방지를 위해 암호화 전달을 권장합니다.

### 6.3 에스컬레이션 기준

- **P1 (30분 내 호출)**: 감사 체인 불일치, 데이터 무단 전송 의심, Gateway 프로세스 반복 크래시.
- **P2 (업무시간 내 호출)**: 업로드 실패율 >= 5%, 토큰 401 반복, staging >= 90%.
- **P3 (일 단위 호출)**: 경미한 경고, 통계 이상, 문서 문의.

본 섹션은 의도적으로 RadiVault 내부 runbook 상세(격리 워커 재시작, DB 리페어 등)를 포함하지 않습니다. 2차 이상은 RadiVault 운영팀 책임입니다.

---

## 7. 데이터 철회 요청 대응

환자가 자신의 영상 데이터를 RadiVault 경로에서 제외해 달라고 요청하는 경우의 절차입니다.

### 7.1 원칙

- 본 파일럿은 **완전 익명화된 데이터**만 중앙으로 전송하는 구조입니다. 중앙에서는 원본 환자 식별자로 역추적이 불가능합니다.
- 따라서 철회 요청은 **귀원 내부의 원본 ↔ 가명 매핑 테이블**을 이용해 귀원 측에서 해당 환자의 가명 UID를 조회 → 중앙에 해당 가명 UID 삭제 요청을 보내는 절차로 수행됩니다.

### 7.2 v0.1 절차 (수동)

1. 환자가 귀원 의무기록팀에 철회 요청 접수.
2. 귀원 전산실이 Gateway 서버에서 `uid_map`·`patient_date_offset` 테이블 조회 → 해당 환자의 가명 study UID 추출.
3. RadiVault 운영팀에 가명 UID 목록 + 철회 사유 제출.
4. RadiVault 운영팀이 중앙 DB·객체 스토리지에서 해당 스터디 삭제 처리.
5. 감사 로그에 `withdraw.executed` 이벤트 기록, 귀원에 처리 완료 통지.

목표 처리 기한: 개인정보보호법상 합리적 기한 준수(30–90일 내 권장).

### 7.3 v0.2 예정 (자동화)

- Gateway Agent에 `withdraw` CLI 명령 추가 예정.
- 중앙 측에 공식 `POST /v1/studies/{uid}/withdraw` 엔드포인트 활성화 예정(v0.1은 501 스텁).
- 본 기능이 정식 가동될 때까지는 §7.2의 수동 절차를 적용합니다.

### 7.4 구매자에게 이미 전달된 경우

- 본 파일럿 v0.1은 구매자 포털이 Phase 2이므로 해당 시나리오는 발생하지 않습니다.
- Phase 2부터는 구매자 계약서에 데이터 오너십·철회권 조항을 포함해 계약적 구속을 부과할 예정입니다.

---

## 8. 자주 묻는 질문

### Q1. 정말로 개인정보가 해외로 나가지 않나요?

기술적으로는 Gateway Agent가 **병원 내부에서** DICOM PS3.15 Annex E Basic Profile + RadiVault 추가 옵션으로 익명화를 완료한 뒤, **재검증(reverify)** 을 통과한 데이터만 중앙으로 전송합니다. 재검증에 실패하면 업로드가 차단됩니다. 원본 UID, 환자 식별자, 내부 매핑 테이블은 모두 병원 내부에 남습니다.

법적으로는 본 설계가 **개인정보보호법 제28조의8의 국외이전 제한에 부합하도록** 작성되었으며, HIPAA Safe Harbor 기준과 정합성을 확보하도록 설계되었습니다. 단, 법적 최종 판단은 법무 자문 결과에 따라 확정됩니다. 현재 법무 자문은 진행 중이며, 파일럿 계약 체결 단계에서 자문 요약을 공유드립니다.

### Q2. PACS에 부하가 얼마나 가나요?

v0.1은 DICOMweb(QIDO/WADO) 기반 풀(pull) 방식이며, 동시 WADO-RS 요청 수는 `pacs.max_concurrency`(기본 4)로 상한 조정이 가능합니다. 폴링 주기는 `poll_interval_seconds`(기본 300초). 모두 병원 측 요구 사양에 맞춰 조정 가능합니다. 실사 단계에서 귀원 PACS 벤더의 권고 제한과 맞춰 재설정합니다.

### Q3. 병원이 데이터 소유권을 잃지는 않나요?

아니오. 원본 DICOM은 **귀원 PACS 내부에 그대로** 유지됩니다. RadiVault 중앙은 익명화된 사본만 수령합니다. 귀원은 언제든 파일럿 계약 조항에 따라 본 서비스를 해지할 수 있으며, 해지 시 중앙 보관 데이터 처리 방침도 계약서에 명시됩니다.

### Q4. 컴플라이언스 인증은 어떻게 되나요?

- **v0.1 (파일럿 단계)**: 자체 보안 정책 준수. 파트너(클라우드 사업자 등) 인증 활용.
- **Phase 2**: SOC 2 Type I 준비 중 (목표 시점 TBD — Kyle 결정 대기).
- **Phase 3**: SOC 2 Type II + ISO 27001 준비 중 (목표 시점 TBD).

v0.1 단계에서는 **인증 보유 주장을 하지 않습니다**. "준비 중" 표기만 사용합니다.

### Q5. 수익 정산은 어떻게 되나요?

본 문서는 기술 설치 가이드이며, 정산 조건은 **별도 제안서**(`proposal-summary-hospital-ko.md`)와 계약서에 명시됩니다. 요약: Tier별 25–50% 범위 내에서 계약으로 확정, 파일럿 병원에는 최소보장금(MG) 조항 제공.

### Q6. Gateway Agent가 다운되면 PACS도 영향을 받나요?

아니오. Gateway Agent는 PACS와 **표준 DICOMweb 프로토콜로만 통신**하며, PACS에 어떠한 설정 변경도 가하지 않습니다. Gateway Agent가 완전히 중단되어도 PACS는 정상 운영됩니다. 동기화만 일시 중단되었다가 Gateway 복구 시 자동 재개됩니다.

### Q7. 중단하고 싶을 때는 어떻게 하나요?

```
$ sudo systemctl stop radivault-gateway
$ sudo docker compose -f /opt/radivault/docker-compose.yml down
```

그리고 RadiVault 운영팀에 계약서의 해지 조항에 따라 통지. RadiVault SRE는 중앙 토큰을 즉시 revoke하고 해당 병원 활성 상태를 비활성으로 전환합니다. 이미 업로드된 데이터의 처리 방침은 계약서 조항을 따릅니다(v0.1 파일럿 단계에서는 계약별 합의).

### Q8. 다른 병원의 데이터와 섞이지 않나요?

중앙 DB·객체 스토리지의 모든 쿼리·키는 `hospital_id`로 스코프됩니다. 병원별 토큰, 병원별 salt, 병원별 객체 스토리지 프리픽스가 분리되어 있으며, 한 병원의 토큰으로는 다른 병원의 데이터에 접근할 수 없도록 설계되어 있습니다.

### Q9. 번인 텍스트(픽셀에 찍힌 환자 이름)는 어떻게 처리되나요?

v0.1은 **자동 격리**만 수행합니다. DICOM `BurnedInAnnotation=YES` 태그 또는 의심 모달리티(Secondary Capture 등)는 업로드되지 않고 `/var/lib/radivault/quarantine/` 디렉터리에 보관됩니다. 수동 QA 후 삭제 또는 추가 마스킹 적용 여부를 결정합니다. 자동 OCR 마스킹은 v0.2 범위입니다.

### Q10. 병원 내부에서 담당자가 바뀌면 어떻게 하나요?

신규 담당자 정보를 RadiVault PM에 통지하면 토큰 인수인계 절차(기존 토큰 revoke → 신규 토큰 발급)가 진행됩니다. Gateway Agent 자체 재설치는 불필요하며 토큰 파일 교체 + 재시작만으로 완료됩니다.

### Q11. 운영 중 발견된 버그는 어떻게 보고하나요?

지원 이메일 `pilot@radivault.io` (placeholder) 앞으로 `gw.log` + `gw-status.json`(암호화) 첨부. 48시간 내 1차 응답.

### Q12. 파일럿 종료 후 정식 계약 전환은 어떻게 되나요?

파일럿 6개월(또는 계약 명시 기간) 종료 시점에 귀원·RadiVault 공동 리뷰 → 상호 의사 확인 → 정식 계약 전환 또는 해지. 전환 시 기존 Gateway Agent를 그대로 유지하며 설정·토큰만 갱신합니다.

---

## 9. 연락처 · 에스컬레이션 경로

| 분류 | 연락처 | 응답 목표 |
|------|--------|----------|
| 파일럿 문의·계약 | `pilot@radivault.io` (placeholder) | 영업일 1일 내 |
| 기술 지원 (일반) | `support@radivault.io` (placeholder) | 48시간 내 |
| 장애 (업무시간) | `ops@radivault.io` (placeholder) | 4시간 내 |
| 긴급 (24/7, P1) | `+82-XX-XXXX-XXXX` (placeholder) | 30분 내 |
| 법무·개인정보 문의 | `legal@radivault.io` (placeholder) | 영업일 3일 내 |

> 실제 연락처는 파일럿 계약 체결 시 별도 안내문으로 전달됩니다. 본 문서의 값은 공개용 플레이스홀더입니다.

---

## 10. 부록 — 주요 CLI 명령 요약

| 명령 | 설명 | 종료 코드 |
|------|------|----------|
| `gateway-agent start` | 데몬 foreground 기동 | 0 정상 / 64 설정오류 |
| `gateway-agent sync-once [--since --until --limit]` | 1회 수동 동기화 | 0 전체 성공 / ≠0 부분 실패 |
| `gateway-agent status [--json]` | 24h 처리 통계 | 0 정상 |
| `gateway-agent de-id-test <file> [--show-diff]` | 단일 파일 익명화 검증 | 0 통과 / 2 PHI 잔존 |
| `gateway-agent audit verify <path>` | 감사 체인 무결성 검증 | 0 OK / 1 불일치 / 2 파일 없음 |
| `gateway-agent version` | 버전 · git SHA · ruleset | 0 |

상세는 각 명령의 `--help` 출력 참조.

---

## 11. CTA — 다음 단계

귀원이 본 파일럿 참여에 관심이 있으시면 초도 미팅을 요청해 주십시오.

→ 문의: `pilot@radivault.io` (placeholder)

- 초도 미팅: 기술 실사 (1–2시간)
- 이후 순서: 기술 실사 → MOU → 파일럿 계약 → 설치 (본 문서 §3)

---

## 12. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-22 | @marketer (Claude Opus 4.7) | 최초 작성. v0.1 MVP 기준. QA Round 2 PASS 확인된 기능만 포함. 법률 문구는 "설계됨/준수 목표" 표현. 수치는 리서치 §10/§11 근거만 인용. 인증은 "준비 중" 표기. 연락처는 placeholder. |
