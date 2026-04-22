# Gateway Agent — 기술적 기반 리서치

## 0. 메타

- **Status**: Draft v0.1
- **작성일**: 2026-04-22
- **작성자**: @researcher (Claude)
- **근거 요청**: 메인 세션 — "@planner가 Gateway Agent dev-spec을 쓰기 위해 필요한 기술 기반 리서치" (Phase 2 진입)
- **선행 문서**: [`docs/research/k-meddata-research-summary.md`](./k-meddata-research-summary.md), [`docs/ARCHITECTURE.md §3`](../ARCHITECTURE.md), [`docs/prd.md §4.1`](../prd.md)
- **PRD/ARCHITECTURE 영향**: 본 문서는 신규 결정을 내리지 않고 **기술 선택의 근거 범위**만 제시. ARCHITECTURE.md §9 "기술 스택 — 미확정" 표에 dev-spec 작성 후 귀결 반영 필요.

---

## 1. TL;DR

- **PACS 연동 방식**: v0.1은 **DICOMweb(QIDO-RS·WADO-RS·STOW-RS) 우선**이 합리적. DIMSE(C-FIND/C-MOVE)는 벤더 비의존성·방화벽 친화성·최신 한국 대형 PACS(INFINITT 등)의 공식 지원 명시라는 3가지 근거로 후순위.
- **익명화**: DICOM PS3.15 **Annex E — Basic Application Level Confidentiality Profile**를 1차 기준으로, `pydicom/deid` YAML 레시피 + 결정적 UID 해시(per-hospital salt, SHA-256/512) + 환자별 고정 날짜 오프셋 조합을 권고. 번인(burn-in) 픽셀 텍스트는 v0.1에서 **플래그·격리**하고 OCR 마스킹은 v0.2로 분리.
- **배포**: Ubuntu 22.04 LTS에 **Docker Compose + systemd 래핑**(Type=oneshot, RemainAfterExit=yes). 베이스 이미지는 v0.1 `python:3.11-slim-bookworm`(디버깅·지원 용이) → v1.0에 distroless 전환 검토.
- **감사 로그**: 로컬 append-only JSON-lines + SHA-256 hash chain(prev_hash + canonicalized_line). 중앙 업로드는 시간당 배치.
- **모킹**: CI에서 **Orthanc + DICOMweb plugin**(Docker)로 QIDO/WADO/STOW 3개 모두 실제 응답 검증. 단위 테스트 계층은 Python stub.
- **리갈 플래그**: UID 매핑 테이블과 날짜 오프셋은 병원 내부에 잔존, **중앙·국외로 절대 미전송**. "완전 익명정보" 해당성 최종 판단은 변호사 자문 필요.

---

## 2. 조사 질문

1. 한국 병원 PACS를 Docker 기반 on-premise 에이전트로 연동할 때, DICOMweb과 DIMSE 중 무엇을 v0.1 기본으로 둘 것인가?
2. DICOM 메타데이터 익명화의 최소 준수 기준은 무엇이고, 어떤 오픈소스 라이브러리·레시피가 프로덕션에 적합한가?
3. Ubuntu 22.04 기반 on-premise 장수(long-running) 에이전트의 표준적 배포·보안 패턴은?
4. 로컬 감사 로그의 변조 방지를 어떻게 가벼운 방식으로 구현하는가?
5. CI에서 DICOMweb PACS를 재현 가능하게 모킹하려면 어떤 옵션이 있는가?

---

## 3. 방법론

- **1차 자료**: DICOM Standard PS3.15 / PS3.18 (nema.org, dicomstandard.org), Orthanc Book, pydicom/deid 공식 문서, INFINITT 공식 제품 페이지.
- **2차 자료**: arXiv/PMC 논문(De-ID 및 번인 텍스트), Censinet 2025 De-ID 도구 벤치마크, pythonspeed.com (Itamar Turner-Trauring) 베이스 이미지 비교.
- **3차 자료**: 커뮤니티 예제(orthanc-users, GitHub gists) — 구체 구현 패턴 참고만.
- **접근 한계**: 한국 로컬 PACS 벤더(Maroo, PiViewSTAR, ZiPACS 등)의 DICOMweb 지원 범위는 공개 자료만으로는 버전별 확정 불가 → 파일럿 착수 시 현장 conformance statement로 확정. 본 문서는 **"업계 공개 표명" 수준**만 기록.

---

## 4. 결과

### 4.1 DICOMweb vs DIMSE — v0.1 권고

#### 4.1.1 프로토콜 대응표

| 기능 | DIMSE (전통) | DICOMweb (REST) |
|------|-------------|-----------------|
| 검색(Query) | C-FIND | QIDO-RS (`GET /studies?...`) |
| 가져오기(Retrieve) | C-MOVE + C-STORE(SCP 역연결) | WADO-RS (`GET /studies/{uid}/series/{uid}/instances/{uid}`) |
| 보내기(Store) | C-STORE | STOW-RS (`POST /studies`, multipart/related) |
| 트랜스포트 | DICOM Upper Layer over TCP (자체 포트, 기본 104/11112) | HTTP/HTTPS (443) |
| 인증 | AE Title + IP whitelist | Basic / Bearer(JWT/OAuth2) / mTLS |
| 페이지네이션 | `offset/limit`(확장 필드) | `?limit=&offset=` 쿼리 파라미터(표준) |

#### 4.1.2 v0.1에 DICOMweb을 1순위로 두는 근거

1. **방화벽 친화성**: DICOMweb은 HTTPS 443 단일 아웃바운드. DIMSE C-MOVE는 **되돌아오는 C-STORE SCP 포트 인바운드**가 필요 → 병원 보안팀이 거부하기 쉬움. ARCHITECTURE §3.3 "outbound-only"와 직접 부합.
2. **인증 현대화**: JWT/mTLS가 표준. AE Title/IP 기반 인증은 감사·회전이 취약.
3. **한국 대형 PACS 공개 지원 표명**: INFINITT는 자사 제품이 "DICOM, DICOMweb, HL7, FHIR, RESTful Open API 지원"을 공식 표명(infinittna.com 제품 페이지). 단, **구체 버전·엔드포인트 레벨 conformance는 현장 확인 필요**.
4. **벤더 중립 구현체 풍부**: 서버(Orthanc, dcm4chee-arc-light), 클라이언트(`dicomweb-client` Python, `cornerstone.js`, `dcm4che3`) 모두 활발히 유지.

#### 4.1.3 DIMSE를 Fallback으로 유지하는 근거

- 한국 지역·중소병원 PACS 중 **DICOMweb 미지원** 장비가 존재할 수 있음(연식·라이선스 이슈). 이 경우 Gateway는 `pynetdicom` 기반 DIMSE SCU 모듈로 폴백해야 함.
- Gateway Agent는 **프로토콜 어댑터 추상화 계층**을 두고 연결 설정에서 `pacs.protocol = dicomweb | dimse`로 토글하는 설계가 바람직(구체 설계는 dev-spec).

#### 4.1.4 한국 PACS 벤더 DICOMweb 지원 — 공개 정보 범위

| 벤더 | 공개 표명 | 주의 |
|------|----------|------|
| INFINITT Healthcare | DICOMweb 공식 지원 (INFINITT PACS 7.0+, infinittna.com) | 구체 엔드포인트·버전은 conformance statement 요청 필요 |
| 기타 국산 PACS | **공개 자료로는 버전별 확정 불가** | 파일럿 착수 시 conformance statement 개별 요청 |
| 해외(GE, Philips, Agfa, Fujifilm) | 대부분 DICOMweb 지원 | 한국 설치본이 구버전일 가능성 존재 |

> **본 문서의 원칙**: 특정 한국 병원과 벤더의 배포 실태를 단정하지 않음. `@planner`의 dev-spec은 **"DICOMweb 우선 + DIMSE 폴백"** 이중 어댑터를 요구사항으로 기술해야 함.

---

### 4.2 DICOM 익명화 — Basic Application Level Confidentiality Profile (Annex E)

#### 4.2.1 기준 프로파일

DICOM PS3.15 **Annex E.1 Table E.1-1**은 수백 개의 태그별 처리 action(X=제거, Z=공백값 유지, D=더미, U=UID 재발급, C=청소, K=유지 등)을 규정. 흔히 "HIPAA Safe Harbor 18 식별자"라 불리는 것은 **미국 HIPAA 45 CFR §164.514(b)(2)**의 18개 식별자 카테고리이며, DICOM Annex E는 이를 **DICOM 태그 수준으로 매핑해 더 엄격하게 포괄**한다.

**대표 PHI 태그 카테고리(요약 — 실제 적용은 Table E.1-1 전수 기준)**:

- Patient 식별: `PatientName (0010,0010)`, `PatientID (0010,0020)`, `IssuerOfPatientID (0010,0021)`, `OtherPatientIDs`, `PatientBirthDate (0010,0030)`, `PatientAddress (0010,1040)`, `PatientTelephoneNumbers (0010,2154)`
- 시설/의료진 식별: `InstitutionName (0008,0080)`, `InstitutionAddress (0008,0081)`, `ReferringPhysicianName (0008,0090)`, `PerformingPhysicianName (0008,1050)`, `OperatorsName (0008,1070)`
- 검사/스터디 식별: `AccessionNumber (0008,0050)`, `StudyID (0020,0010)`
- UID 체계: `StudyInstanceUID (0020,000D)`, `SeriesInstanceUID (0020,000E)`, `SOPInstanceUID (0008,0018)`, `FrameOfReferenceUID (0020,0052)` — U action (재발급)
- 날짜·시각: `StudyDate/Time`, `SeriesDate/Time`, `AcquisitionDate/Time`, `ContentDate/Time`, `PatientBirthDate` — D action (환자별 고정 오프셋 시프트)
- 자유 텍스트 위험: `ImageComments (0020,4000)`, `StudyComments`, `RequestedProcedureComments` — X (제거) 권고

> **NEXT_STEP**: 전수 태그 매트릭스는 dev-spec의 "De-ID 규칙 부록"으로 `pydicom/deid` YAML 레시피와 **1:1 대응표**를 planner가 생성.

#### 4.2.2 Annex E 옵션 — RadiVault 적용 권고

Annex E는 Basic Profile에 **선택적 Retain 옵션**을 중첩 적용할 수 있게 함. 글로벌 AI 판매 유틸리티와 재식별 리스크의 균형이 핵심.

| 옵션 | 권고 | 근거 |
|------|------|------|
| Retain Safe Private Option | **제외(X)** | 벤더별 private 태그에 PHI 잔존 사례 다수. 초기에는 전량 제거가 안전. |
| Retain UIDs Option | **제외** | 원본 UID 보존 시 출처 병원 PACS에서 역조회 가능 → 재식별 벡터. U(재발급) 유지. |
| Retain Device Identity Option | **부분 유지** | 장비 제조사·모델(`Manufacturer`, `ManufacturerModelName`)은 AI 학습 공변량으로 중요. 시리얼·MAC은 제거. |
| Retain Patient Characteristics Option | **유지** | 연령대(5년 bin), 성별, 체중, 키, 인종(있을 시)은 AI 학습에 유용. 단 **정확 DoB는 연도만 유지 또는 연령대로 변환**. |
| Retain Longitudinal Temporal Info with Modified Dates | **유지 (핵심)** | 환자별 고정 오프셋(예: −N일)으로 모든 날짜를 시프트 → 시계열 관계 보존하면서 절대 날짜 재식별 방지. |
| Retain Institution Identity Option | **제외** | 병원명은 중앙 인덱스에서 내부 해시 ID로만 관리. 구매자에게 노출 금지. |
| Clean Descriptors Option | **병용** | `StudyDescription`, `SeriesDescription`은 자유 텍스트 PHI 위험 → 화이트리스트 사전 매칭 또는 제거. |
| Clean Structured Content Option | **Phase 2** | DICOM SR(판독문) 본격 연동 시. |
| Clean Graphics Option | **유지** | 그래픽 오버레이에 환자명 등 존재 가능 → 제거. |

> 비고: 옵션 적용은 `DeidentificationMethodCodeSequence (0012,0064)` 및 `DeidentificationMethod (0012,0063)`에 기록해야 Annex E 준수 선언 가능.

#### 4.2.3 UID 가명화 — 결정적 해시 + per-hospital salt

**원칙**: 동일 원본 UID는 **동일 병원 내·시간에 걸쳐** 항상 동일 가명 UID로 매핑되어야 함(종단적 일관성). 매핑 테이블은 병원 내부에만 존재.

**권고 알고리즘**:

```
pseudo_uid = ORG_ROOT + "." + truncate(SHA256(salt || original_uid), N_digits)
```

- `ORG_ROOT`: RadiVault 전용 등록 OID root (예: `2.25.x` UUID 변환 또는 IANA 등록 OID) — **DICOM UID 최대 64자** 제한 준수.
- `salt`: 병원별 고유, 최소 32바이트 랜덤. Gateway 컨테이너 외부 secret(systemd credential 또는 host filesystem `chmod 600`)으로 주입.
- truncate: hex → 10진수 변환 후 상위 N자리. SHA-256 기준 충돌 확률은 N≥32자리면 무시 가능.
- **매핑 저장**: 로컬 SQLite + `UNIQUE(original_uid)`. 인덱스 `pseudo_uid`. 백업 암호화.
- 추가로 `pydicom.uid.generate_uid(entropy_srcs=[original_uid], prefix=ORG_ROOT)`도 사용 가능하나 명시적 salt 기반이 감사·회전에 더 유리.

#### 4.2.4 날짜 시프트

- **환자별 고정 오프셋**: `offset_days = (SHA256(salt || patient_id) mod 365*10) − 365*5` 같은 결정적 함수로 ±5년 범위 내 정수 일 시프트.
- 동일 환자의 모든 스터디는 동일 오프셋 → 시계열(f/u) 관계 보존.
- 환자 간에는 독립 → 다환자 코호트에서 특정 사건(재난, 유행) 기반 재식별 곤란.
- **시각(time)**: 분 단위까지만 유지, 초·밀리초 0 채움 권고. 근무 시프트 기반 추론 완화.

#### 4.2.5 번인 텍스트 — v0.1 정책, v0.2 OCR

- DICOM 태그 `(0028,0301) BurnedInAnnotation = YES`는 **선택 필드**이며 신뢰 불가. 미기재인데 실제 번인된 사례 다수 보고(PMC 11522224, 2024).
- **v0.1 정책**:
  1. 모달리티·장비 모델 블랙리스트 기반 1차 플래깅(예: Secondary Capture, 초음파 US 일부, 스크린샷류).
  2. `BurnedInAnnotation == YES` 또는 의심 모달리티는 **자동 격리(quarantine queue)**, 중앙 전송 차단.
  3. 격리된 영상은 수동 QA → v0.2 OCR 파이프라인으로 순차 처리.
- **v0.2 OCR 후보**: Tesseract + 경량 텍스트 감지(EAST) 조합, 또는 `pydicom/dicom-cleaner`(개발 중) 추적. 2024년 논문(Springer JIIM) 방법이 benchmark.
- **얼굴 defacing**: 두개부 CT/MRI는 `pydeface`, `mri_deface`(FreeSurfer) 계열. v0.1 범위에서 제외하고 v0.2에 묶는 것이 리스크/가치 비율상 합리적 — 척추 등 Kyle 도메인 먼저 커버하면 번인·defacing 모두 낮은 우선순위.

#### 4.2.6 라이브러리 선택

| 라이브러리 | 용도 | 평가 |
|-----------|------|------|
| `pydicom` (core) | DICOM 파싱/직렬화 | 사실상 표준. 필수. |
| `pydicom/deid` | YAML 레시피 기반 De-ID | **v0.1 권고**. 해시·염(salt) 내장, 커스텀 함수 hook. |
| `dicom-anonymizer` (PyPI) | 간단 CLI | 기능 제한, 커스텀 규칙 부족 → 비추천. |
| `dicognito` | 빠른 기본 익명화 | 감사·결정성 부족 → 비추천. |
| CTP (RSNA Clinical Trial Processor) | Java 기반 풀스택 | 검증된 도구지만 JVM 의존. 참고 구현으로만. |
| `pynetdicom` | DIMSE 프로토콜 | DIMSE 폴백 시 사용. |
| `dicomweb-client` | DICOMweb 클라이언트 | v0.1 HTTP 어댑터 기본. |

---

### 4.3 Ubuntu 22.04 / Docker 배포 패턴

#### 4.3.1 베이스 이미지

| 옵션 | 크기(참고) | 장점 | 단점 |
|------|-----------|------|------|
| `python:3.11-slim-bookworm` | ~150MB | Debian 12 기반, glibc, 디버깅 용이, `apt` 사용 가능 | 공격면 distroless보다 큼 |
| `gcr.io/distroless/python3-debian12:nonroot` | ~65MB | 최소 공격면, non-root 기본 | 셸/패키지 매니저 부재, 빌드 복잡 |
| `ubuntu:22.04` | ~77MB | 친숙 | Python 수동 설치 필요, 크기 역전 가능 |

**권고**: v0.1 `python:3.11-slim-bookworm` (파일럿 디버깅 편의) → 프로덕션 일반화 단계에서 distroless 전환 검토. Multi-stage 빌드로 빌드 산출물만 런타임 이미지에 복사.

#### 4.3.2 Multi-stage Dockerfile 원칙

- Stage 1 (`builder`): `pip wheel` 또는 `pip install --prefix=/install` 로 의존성 컴파일.
- Stage 2 (`runtime`): 최소 베이스 + builder에서 산출물만 `COPY --from=builder`.
- `USER 10001` (고정 UID non-root), `WORKDIR /app`, `ENTRYPOINT ["python","-m","radivault_gateway"]`.
- `HEALTHCHECK --interval=30s --timeout=5s CMD python -m radivault_gateway.health || exit 1`.
- `.dockerignore`로 `.venv`, `tests/fixtures/*.dcm`, `.git` 등 제외.

#### 4.3.3 systemd — Docker Compose 래핑

```
[Unit]
Description=RadiVault Gateway Agent
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/radivault
EnvironmentFile=/etc/radivault/gateway.env
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
ExecReload=/usr/bin/docker compose pull && /usr/bin/docker compose up -d
Restart=on-failure
RestartSec=30s

[Install]
WantedBy=multi-user.target
```

- `Type=oneshot + RemainAfterExit=yes`가 docker compose 패턴의 표준(다수 커뮤니티 가이드 일치).
- 로그는 journald로 집계, `journalctl -u radivault-gateway -f`.
- `systemctl enable --now radivault-gateway` 로 부팅 시 자동 기동.

#### 4.3.4 시크릿 관리

| 방식 | 장점 | 단점 | 권고 |
|------|------|------|------|
| 환경 변수 (docker compose `.env`) | 단순 | 프로세스 목록·덤프에서 노출 가능 | 평문 보관 요주의 |
| Docker secrets (Swarm 전용) | 격리 | 단일 노드 Compose에서는 제한적 | v0.1 부적합 |
| systemd credentials (`LoadCredential=`) | 메모리 전용, 디스크 흔적 최소 | Ubuntu 22.04 systemd 249 지원 | **v0.1 권고** |
| sops + age | Git 안전 보관, 수동 복호화 | 운영 시 수동 단계 | 시드 secret(`salt`, DB 패스프레이즈) 보관용 |
| HashiCorp Vault / AWS Secrets Manager | 감사·회전 강력 | 인프라 추가 비용 | v1.0+ |

**권고 조합**: sops(암호화된 리포)로 시크릿을 배포 → 설치 스크립트가 `/etc/radivault/credentials/`에 `chmod 600`으로 해제 → systemd `LoadCredential=salt:/etc/radivault/credentials/salt` 로 컨테이너에 주입.

#### 4.3.5 로그 회전

- 컨테이너 stdout: Docker log driver `json-file` + `max-size=50m`, `max-file=5`. 또는 `journald` driver로 변경해 host journald에 위임.
- 앱 레벨 감사 로그(§4.4): Python `logging.handlers.RotatingFileHandler` 또는 host `logrotate.d/radivault` 설정. **단, 감사 로그는 hash chain 무결성 때문에 회전 시 체인 단절 지점을 명시적으로 기록**해야 함(회전 파일명에 마지막 해시 포함 등).

#### 4.3.6 네트워크 — egress-only 자세

- Gateway 호스트 UFW/nftables: 아웃바운드 443 → RadiVault 중앙 엔드포인트 도메인·IP 허용, 그 외 전면 차단. 인바운드 전면 차단(SSH는 점프호스트·VPN 경유 권고).
- 병원망 → 인터넷 egress proxy가 있으면 HTTP_PROXY/HTTPS_PROXY 환경변수 지원 필수.
- DNS 유출 방지: 필요 시 중앙 IP 고정 + `/etc/hosts` pin. TLS SNI·certificate pinning 검토(v1.0).

---

### 4.4 변조 방지 감사 로그 — Hash Chain

#### 4.4.1 요구사항

- **append-only**: 파일 끝에만 추가, 기존 라인 수정 금지.
- **tamper-evident**: 과거 라인 수정 시 이후 모든 라인의 체인 hash 불일치 → 즉시 탐지 가능.
- **외부 앵커링**: 시간당/일별로 head hash를 중앙 Audit Log(WORM)에 업로드 → 로컬 단독 조작 불가.
- **JSON-lines**: 한 줄 = 한 JSON 객체, 줄바꿈 구분. 표준 도구(`jq`)와 호환.

#### 4.4.2 레코드 구조

```json
{
  "seq": 12345,
  "ts": "2026-04-22T10:15:03.412Z",
  "actor": "gateway",
  "event": "deid.completed",
  "target": {"study_pseudo_uid": "2.25.xxx"},
  "meta": {"n_instances": 184, "ruleset_version": "v0.1.2"},
  "prev_hash": "sha256:a1b2...",
  "hash":      "sha256:c3d4..."
}
```

- `hash = SHA256( canonicalize({seq, ts, actor, event, target, meta, prev_hash}) )` — `hash` 필드 자신은 계산 대상에서 제외.
- `canonicalize`: JCS(RFC 8785) 또는 최소 `json.dumps(..., sort_keys=True, separators=(",",":"), ensure_ascii=False)`.
- Genesis 라인: `seq=0`, `prev_hash="sha256:0"*64`.

#### 4.4.3 Python 구현 스케치 (참고용)

```python
import hashlib, json, os, threading

class HashChainLogger:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._seq, self._prev = self._recover_tail()

    def _recover_tail(self):
        if not os.path.exists(self.path):
            return 0, "sha256:" + "0"*64
        last = None
        with open(self.path, "rb") as f:
            for line in f:
                last = line
        if not last:
            return 0, "sha256:" + "0"*64
        obj = json.loads(last)
        return obj["seq"], obj["hash"]

    def append(self, event: str, actor: str, target: dict, meta: dict):
        with self._lock:
            self._seq += 1
            rec = {
                "seq": self._seq,
                "ts": _utc_now_iso(),
                "actor": actor,
                "event": event,
                "target": target,
                "meta": meta,
                "prev_hash": self._prev,
            }
            canonical = json.dumps(rec, sort_keys=True,
                                   separators=(",", ":"),
                                   ensure_ascii=False).encode("utf-8")
            digest = "sha256:" + hashlib.sha256(canonical).hexdigest()
            rec["hash"] = digest
            with open(self.path, "ab") as f:
                f.write(json.dumps(rec, ensure_ascii=False).encode("utf-8"))
                f.write(b"\n")
                f.flush()
                os.fsync(f.fileno())
            self._prev = digest
            return digest
```

- **파일 권한**: `chmod 600`, owner=gateway uid.
- **중앙 앵커링**: 시간마다 `(seq_range, head_hash)`를 중앙 Audit Log에 POST. 중앙에서는 append-only WORM에 보관(ARCHITECTURE §4.7).
- **검증 CLI**: `radivault-gateway audit verify <file>` — 전체 라인을 재해싱해 체인 일관성 검사.
- **한계**: 공격자가 파일 전체를 교체하면 로컬에서는 일관성 있어 보임 → **앵커 업로드된 head hash와 비교**해야 탐지. 이것이 "시간당 배치 업로드"의 핵심 이유.
- **참고 구현**: Google Trillian(대규모 Merkle 트리), Attest(append-only hash chain, 멀티테넌트) — 본 MVP 범위에서는 hash chain 단독으로 충분, Merkle은 v1.0+에서 다수 로그 집계 시 검토.

---

### 4.5 DICOMweb PACS 모킹 (CI·로컬 테스트)

#### 4.5.1 옵션 비교

| 옵션 | 장점 | 단점 | CI 적합성 |
|------|------|------|----------|
| **Orthanc + DICOMweb plugin (Docker)** | WADO-URI/WADO-RS/QIDO-RS/STOW-RS 전부 공식 지원, Docker Hub 공식 이미지, JSON 설정 간결, 실제 PACS와 가까운 동작 | JVM 불요지만 C++ 바이너리, 리소스 소모 약간 | **권고 (통합 테스트)** |
| dcm4chee-arc-light | 풀스펙, 엔터프라이즈 | JVM, 설정 복잡, CI 부담 큼 | 부적합 |
| `knopkem/dicomweb-pacs` (Node) | 가벼움, SQLite | 커버리지 제한, 유지관리 규모 작음 | 보조용 |
| `pynetdicom` 예제 서버 | 파이썬 단일 | DIMSE만, DICOMweb 부재 | DIMSE 폴백 테스트 전용 |
| 자체 Flask/FastAPI stub | 실패 시나리오 주입 자유 | 프로토콜 정합성 보증 부담 | **권고 (단위 테스트)** |

#### 4.5.2 권고 스택

- **단위 테스트**: Python `pytest` + 자체 FastAPI stub으로 특정 오류 케이스(404, 408, 429, 잘못된 DICOM multipart) 주입.
- **통합 테스트**: `docker compose` 파일에 Orthanc 서비스 포함 → `pytest` fixture가 부팅·시드(test DICOM) 로드 → Gateway를 실제 HTTP로 호출. CI는 GitHub Actions에서 `services:` 또는 `docker compose up -d` 프리스텝.
- **시드 데이터**: CC0 또는 공개 샘플(TCIA 공개 샘플 일부, pydicom 내장 `get_testdata_files()` 분량) 사용. 환자 식별자 포함 금지.
- **회귀 테스트**: 익명화 전/후 DICOM을 `deepdiff` 또는 pydicom dataset 비교로 골든 테스트화.

---

## 5. 시사점 (RadiVault에의 함의)

1. **dev-spec 요구사항**: PACS Connector를 "DICOMweb 우선 + DIMSE 폴백" 어댑터 추상화로 명세할 것. Connection config 예시 YAML을 spec 부록에 포함 권고.
2. **De-ID 규칙표가 dev-spec 핵심 산출물**: Annex E Table E.1-1에 대한 RadiVault 적용 규칙 표(유지/제거/시프트/재발급)를 `pydicom/deid` YAML 레시피와 1:1로 매핑. 이게 없으면 구현자가 임의 판단으로 PHI 누출 위험.
3. **Secret 구조 초기 결정 필요**: per-hospital salt를 **어디서 생성하고 어떻게 배포하며 어떻게 회전하는지** dev-spec 또는 별도 운영 지침에 명시. 회전 시 UID 매핑 체계 호환성(복수 salt 세대 병용) 정책 필요.
4. **번인 텍스트 v0.2 분리 정당화**: v0.1은 자동 격리 + 수동 QA. 파일럿에서 "번인 비율" 실측 후 OCR 파이프라인 ROI 결정.
5. **감사 로그 앵커링 엔드포인트**: 중앙 Audit Log API 스펙은 Gateway dev-spec과 같은 타이밍에 설계되어야 함. 별개 spec(`dev-spec-central-audit-log.md`)으로 분리 권고.
6. **법률·컴플라이언스 플래그 (변호사 자문 필요)**:
   - (a) UID 매핑 테이블과 날짜 오프셋이 병원에만 남아도 "완전 익명정보" 요건을 충족하는가 — 개인정보보호위원회 보건의료데이터 가이드라인 2024.12 개정 기준.
   - (b) Annex E 채택만으로 한국법상 "익명정보" 판단이 자동 성립하지 않음. k-익명성·l-다양성 추가 검증 의무 여부.
   - (c) "Retain Patient Characteristics" 적용 시 희귀질환·소수 민족 코호트의 재식별 가능성 별도 검토.

> **PRD/ARCHITECTURE 갱신 제안**: ARCHITECTURE §9 기술스택 표의 "Gateway Agent — 언어(Python 유력), 컨테이너 런타임, PACS 라이브러리"를 planner dev-spec 확정에 맞춰 다음 문구로 대체 제안 — "Python 3.11 + Docker(Compose) + pydicom + pynetdicom + dicomweb-client + pydicom/deid (dev-spec-gateway-agent 근거)". 본 문서에서는 제안만, 직접 수정은 하지 않음.

---

## 6. 한계 · 오픈 퀘스천

- **한국 PACS 벤더 DICOMweb 버전별 conformance**: 공개 자료만으로는 엔드포인트·파라미터 레벨 확정 불가. 파일럿 병원별 conformance statement 수집 필수.
- **판독문 연동**: DICOM SR 보관 형태 vs RIS/EMR 분리 저장 형태 비율. 본 문서 범위 밖, Phase 2 별도 리서치 필요(한국어 판독문 NER 포함).
- **Gateway 하드웨어 요구사항**: 스테이징 스토리지 용량, CPU/메모리 산정은 평균 스터디 크기·주문량 실측 전까지 가정만 가능.
- **OHIF/Cornerstone 뷰어 통합**: Zone 3 범위. 본 문서 불포함.
- **다국어 인코딩**: 한국어 PatientName의 `SpecificCharacterSet = ISO_IR 149` 처리. De-ID에서 값은 제거하지만 태그 존재·문자셋은 유지 권고.
- **희귀질환 k-익명성 정책**: 정량 임계(예: k≥5) 결정은 데이터 QA 팀 + 변호사 합의 필요.

---

## 7. 출처 목록

### 1차 (표준·공식 문서)

- DICOM Standard PS3.15, Annex E "Attribute Confidentiality Profiles" — https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_e.html
- DICOM Standard PS3.18 "Web Services" — https://dicom.nema.org/medical/dicom/current/output/chtml/part18/PS3.18.html
- DICOMweb 공식 개요 — https://www.dicomstandard.org/using/dicomweb
- Orthanc Book, DICOMweb plugin — https://orthanc.uclouvain.be/book/plugins/dicomweb.html
- INFINITT North America, INFINITT PACS 제품 페이지 — https://www.infinittna.com/solutions/radiology/infinitt-pacs/
- pydicom/deid 공식 문서 — https://pydicom.github.io/deid/
- pydicom/deid GitHub — https://github.com/pydicom/deid
- pydicom/dicom-cleaner (burn-in OCR, 개발 중) — https://github.com/pydicom/dicom-cleaner

### 2차 (논문·벤치마크)

- "A Method for Efficient De-identification of DICOM Metadata and Burned-in Pixel Text", J Imaging Inform Med, 2024 — https://pmc.ncbi.nlm.nih.gov/articles/PMC11522224/
- "De-Identification of Medical Imaging Data: A Comprehensive Approach", arXiv 2410.12402 — https://arxiv.org/pdf/2410.12402
- Censinet, "2025 Benchmark: De-Identification Tools" — https://censinet.com/perspectives/2025-benchmark-de-identification-tools
- "Pseudonymization of Radiology Data for Research Purposes", PMC3043895 — https://pmc.ncbi.nlm.nih.gov/articles/PMC3043895/

### 3차 (운영·구현 레퍼런스)

- Python Docker 베이스 이미지 비교, pythonspeed.com (2026-02) — https://pythonspeed.com/articles/base-image-python-docker-images/
- Distroless Python — https://github.com/alexdmoss/distroless-python
- Docker Compose as systemd unit (TechOverflow) — https://techoverflow.net/2018/12/15/a-systemd-service-template-for-docker-compose/
- "Building a Tamper-Evident Audit Log with SHA-256 Hash Chains" (DEV) — https://dev.to/veritaschain/building-a-tamper-evident-audit-log-with-sha-256-hash-chains-zero-dependencies-h0b
- Google Trillian (append-only ledger) — https://transparency.dev/
- MIRC DICOM Anonymizer — https://mircwiki.rsna.org/index.php?title=The_MIRC_DICOM_Anonymizer

### 규제 (참고, 직접 인용은 최소)

- 개인정보보호법 제28조의8 (국외이전) — 법제처 국가법령정보센터
- 보건복지부·개인정보보호위원회 "보건의료데이터 활용 가이드라인" (2024.12 개정)
- HIPAA 45 CFR §164.514(b) "De-identification"

> 본 문서는 법률 자문이 아니다. 규제 적합성 최종 판단은 담당 법무법인 자문 필요.

---

## 8. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-22 | @researcher (Claude) | 초안. DICOMweb/DIMSE, Annex E 적용 권고, Ubuntu/Docker 배포, hash chain 감사 로그, Orthanc 모킹 스택. |

---

### NEXT_STEP
- 완료 산출물: docs/research/gateway-agent-technical-foundations.md
- 제안 다음 단계: @planner — `docs/specs/dev-spec-gateway-agent.md` 작성. 본 리서치 §4.1(PACS 어댑터 이중화), §4.2(Annex E 규칙표 + UID 해시 + 날짜 시프트), §4.3(Docker + systemd + 시크릿), §4.4(hash chain 감사 로그), §4.5(Orthanc CI 스택)를 요구사항으로 전개. De-ID 태그 매트릭스(Annex E Table E.1-1 대비 pydicom/deid YAML)는 spec 부록으로 포함.
- Kyle 결정 필요 사항:
  1. per-hospital salt 생성·배포·회전 책임 주체(플랫폼 운영팀 vs 병원 IT) 및 회전 주기.
  2. 번인 텍스트 OCR를 v0.2로 분리하는 방안 승인(v0.1은 자동 격리 + 수동 QA).
  3. 법무법인 자문 의뢰 타이밍 — dev-spec 초안 완성 전/후. 자문 항목: (a) UID 매핑·날짜 오프셋 보관이 "완전 익명정보" 성립에 영향이 있는지, (b) Annex E 옵션 선택의 한국법상 충분성, (c) k-익명성 정량 임계.
