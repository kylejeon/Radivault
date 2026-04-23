# RadiVault Gateway Agent v0.2 — 픽셀 레벨 익명화 업그레이드 공지 (de-id-pixel)

> **Status**: Draft — Kyle 리뷰 필요, 외부 배포 전 승인 필수
> **문서 버전**: v0.1 (2026-04-22)
> **작성자**: @marketer (RadiVault)
> **대상 독자**: 파일럿 병원 전산실(IT) 운영자, 개인정보보호책임자(DPO), 병원 경영진(의료정보실장·임상연구지원실장)
> **언어**: 한국어 (기술 용어는 영문 병기)
> **배포 범위**: 파일럿 계약 체결 병원 + RadiVault 내부. 외부 공개 자료 아님.
> **근거 문서**: [dev-spec-de-id-pixel](../specs/dev-spec-de-id-pixel.md) §0/§1/§3/§9/§12, [qa-report-de-id-pixel](../qa/qa-report-de-id-pixel.md) Round 2 PASS, [연구 문서](../research/de-id-pixel-technical-foundations.md), [보건의료 연구 §5](../research/k-meddata-research-summary.md#5-법적-구조-및-규제)
> **Kyle 리뷰 필요 사항**: FSL 상업 라이선스 법무 자문, 과마스킹·과defacing 책임 문구, 임상 QA 사전 약정 문구, 수치 TBD 항목(병원별 데이터·처리 시간 실측치).

---

## 0. 한 줄 요약

RadiVault Gateway Agent **v0.2**는 v0.1의 메타데이터 기반 익명화를 **DICOM 픽셀 레벨**까지 확장합니다. 번인(Burned-in) 텍스트를 OCR로 탐지·마스킹하고, 두경부 CT·MR의 얼굴 표면을 3D defacing으로 제거하여, 기존에 **격리(quarantine)로만 처리되던 스터디**를 익명 데이터 공급 경로로 되돌립니다. 기본값은 **OFF(opt-in)** 이며, 각 병원이 준비되셨을 때에만 활성화하시도록 설계되었습니다.

---

## 1. v0.1과 v0.2의 달라진 점 (요약 비교)

| 항목 | v0.1 (현행) | v0.2 (de-id-pixel) |
|---|---|---|
| 메타데이터 익명화 | DICOM PS3.15 Annex E Basic Profile + 확장 | 변경 없음 (유지) |
| 번인 텍스트 (US·SC·OT 등) | **격리 큐 이동** — 수동 QA 대기 | OCR 자동 탐지 + 마스킹 → 익명화 후 송출 (opt-in) |
| 두경부 CT·MR 얼굴 표면 | 별도 처리 없음 — 재식별 위험 잔존 | `pydeface` 기반 3D defacing (opt-in) |
| 의료 ROI(치과·ENT·안과·안와·얼굴외상) | 구분 없음 | 자동 defacing **금지** + 격리(사람 결정) |
| 감사 로그 | hash-chained audit.log (v0.1과 동일 체인) | pixel 이벤트를 동일 체인에 이어서 기록 + `pixel_audit_event` DB 테이블 보강 |
| PACS 연동 프로토콜 | DICOM C-FIND/C-MOVE, DICOMweb | 변경 없음 |
| 중앙 서버와의 통신 계약 | `/v1/ingest/studies`, `/v1/audit/anchor` | **변경 없음** — manifest 스키마 불변 |
| 기본 Docker 이미지 | `radivault-gateway:0.1.x` (slim, 약 150MB) | **`radivault-gateway:0.2.0`** (v0.1 동등, 기본값) |
| 픽셀 처리 이미지 | 해당 없음 | **`radivault-gateway:0.2.0-pixel`** (Tesseract·pydeface 포함, 약 750MB~1.2GB, 별도 다운로드) |

핵심 설계 원칙: **v0.2로 업그레이드해도 `deid.pixel.enabled=false`(기본값)로 두면 v0.1과 바이트 단위로 동일한 익명화 결과**가 생성됩니다(QA Round 2에서 회귀 검증 완료, AC-15). 즉 **기능이 추가되었을 뿐, 기존 동작이 바뀌는 것은 없습니다.**

---

## 2. 무엇이 추가됐는가

### 2.1 OCR 기반 번인 텍스트 자동 마스킹

US(초음파), SC(스크린 캡처), OT 모달리티 등은 픽셀 내부에 환자 이름·ID·장비 라벨 등이 인쇄(burn-in)되는 경우가 많습니다. v0.1에서는 이런 스터디를 **격리 큐**로 라우팅하고 수동으로 결정하도록 설계했습니다. v0.2는 다음과 같이 처리합니다.

- 1차 OCR 엔진: **Tesseract 5** (한국어 + 영어 언어팩 동시 적용, 오픈소스 Apache-2.0 라이선스).
- 탐지된 bounding box에 대해 **신뢰도(conf)**가 설정 임계(기본 0.60) 이상인 경우에만 마스킹 적용.
- 기본 마스킹 방식: **solid black(픽셀값 0)**. 필요 시 mean-pixel·gaussian blur 옵션 제공(기본 아님).
- 마스킹 후 **동일 영역에 대한 재OCR**을 실행해 잔여 텍스트가 탐지되면 자동으로 격리(잔여 검증 게이트).
- 선택 업그레이드로 **PaddleOCR 엔진**을 지원하나, v0.2 기본은 Tesseract이며 PaddleOCR 이미지(`*-pixel-paddle`)는 현재 내부 실험용.

### 2.2 두경부 CT·MR 3D 얼굴 defacing

두개부 CT·MR 볼륨에서 얼굴 표면 복셀을 제거하여 **3D 표면 재구성에 의한 재식별 공격**을 완화합니다.

- 1차 라이브러리: **pydeface** (BSD-3 계열 라이선스). FSL(`flirt`) 런타임에 의존.
- 폴백: **mridefacer** (BSD-3 라이선스).
- 사용 금지: **FreeSurfer `mri_deface`** (비상업 라이선스) — 본 스펙에서 명시 배제.
- 적용 대상: `Modality ∈ {CT, MR}` AND `BodyPartExamined ∈ {HEAD, BRAIN, NEURO, STROKE}` AND 의료 제외 리스트 미매칭.
- 실행 후 **제거된 얼굴 복셀 비율**(removed_voxel_ratio)이 임계(기본 0.05) 미만이면 자동으로 격리.

> **⚠ FSL 라이선스 주의**: FSL은 **학술·비상업 라이선스** 기반으로 배포되며, RadiVault 상업 배포 시 별도 라이선스 검토가 필요합니다. Kyle 측이 **외부 법무 자문**을 진행 중이며, 자문 완료 전까지는 **파일럿 환경 한정 사용**만 허용됩니다. 파일럿 병원의 defacing 활성화 시점은 법무 자문 결과를 반영한 후 별도 안내드립니다.

### 2.3 잔여 검증 게이트 (Residual Re-verification)

마스킹·defacing 이후 결과물을 **다시 스캔**하여 "덜 제거된 경우"를 자동으로 탐지합니다.

- OCR redaction 후: 동일 박스에 대해 재OCR 실행 → 신뢰도 임계 이상 텍스트 발견 시 실패 처리(격리).
- Defacing 후: 얼굴 bounding-box 영역의 복셀 제거 비율을 측정 → 임계 미만 시 실패 처리(격리).
- 이 단계는 **"완전 익명" 주장을 기술적으로 뒷받침**하는 설계이며, 법률적 "완전 익명정보"(개인정보보호법 §28조의8) 판정 자체는 **법무 자문과 DPO 승인**으로 확정됩니다.

### 2.4 품질 기반 자동 격리 폴백

픽셀 처리 경로에서 다음 상황이 발생하면 **자동으로 v0.1 격리 경로로 되돌아갑니다**.

- OCR 신뢰도 전체가 임계 미만 (`ERR_PIXEL_OCR_LOW_CONFIDENCE`)
- OCR 엔진 실행 실패 (`ERR_PIXEL_OCR_ENGINE_FAILURE`)
- 마스킹 후 잔여 텍스트 탐지 (`ERR_PIXEL_RESIDUAL_TEXT`)
- Defacing 라이브러리 미설치·실행 실패 (`ERR_PIXEL_DEFACE_LIBRARY_MISSING`, `ERR_PIXEL_DEFACE_FAILURE`)
- Defacing 후 얼굴 복셀 잔존 (`ERR_PIXEL_RESIDUAL_FACE_VOXELS`)
- 의료 제외 리스트 매칭(`ERR_PIXEL_MEDICAL_EXCLUSION`, 치과·ENT·안과·안와·악안면 등)

즉 **픽셀 파이프라인이 데이터 유실 원인이 되지 않도록** 설계되었습니다(dev-spec §12.3, QA Round 2 Section 5.3). 어느 경우에도 "익명화되지 않은 원본"이 중앙으로 송출되지 않으며, 불확실하면 **격리가 기본값**입니다.

### 2.5 감사 기록 보강

- 기존 v0.1 hash-chained `audit.log`에 pixel 이벤트가 **동일 체인**으로 이어서 기록됩니다(감사 증거 무결성 유지).
- 별도 테이블 `pixel_audit_event`가 신설되어 OCR·defacing·triage 작업 단위의 통계·운영 조회를 지원합니다. **원문 OCR 텍스트는 저장되지 않습니다**(FR-38, QA Round 2 Section 5.1 PHI 오염 금지 PASS). 박스별 `SHA-256[:16]` 해시만 기록됩니다.
- DICOM 태그 `(0012,0063) DeidentificationMethod` 및 `(0012,0064) DeidentificationMethodCodeSequence`에 신규 값이 **추가만** 됩니다(기존 코드 유지).

---

## 3. 왜 필요한가 — 규제·연구 배경

### 3.1 개인정보보호법 — "완전 익명정보"만 국외이전 가능

- **개인정보보호법 §28조의8**은 개인정보·가명정보의 국외이전을 원칙적으로 제한합니다. 오직 **완전 익명정보**(시간·비용·기술을 합리적으로 고려할 때 재식별이 불가능한 상태)만 적용 대상에서 제외됩니다(리서치 §5).
- DICOM **메타 De-ID(Annex E)**만으로는 다음 두 경로가 남습니다:
  1. **번인 텍스트**: 픽셀 내부에 인쇄된 환자 이름·ID·검사일.
  2. **3D 얼굴 표면**: CT·MR의 두개부 시리즈로부터 얼굴 재구성이 가능.
- v0.2는 이 두 경로를 기술적으로 차단하도록 설계된 **보강 레이어**입니다. **법률적 판정**은 여전히 법무 자문이 결정하며, 본 변경은 "완전 익명정보" 주장을 **기술적으로 뒷받침**합니다.

### 3.2 HIPAA Safe Harbor

- 미국 측 구매자가 요구하는 HIPAA Safe Harbor(§164.514(b)(2))는 식별번호·특성·코드 등 18개 카테고리 제거를 요건으로 합니다. 번인 텍스트는 이 요건을 직접 침범할 수 있는 경로였으며, v0.2의 OCR 마스킹이 이를 완화합니다.

### 3.3 학계 재식별 공격 맥락 — NEJM 2019

- **Schwarz CG et al., "Identification of Anonymous MRI Research Participants with Face-Recognition Software", *New England Journal of Medicine*, 2019**에서 defacing을 거치지 않은 MRI 머리 볼륨에 대해 **얼굴 인식 기반 식별률이 70% 이상**임이 보고되었습니다(리서치 §4.4, dev-spec §12.4).
- 이 논문은 **근거 문헌**으로 인용되며 RadiVault의 방어 효과에 대한 "증명"으로 사용되지 않습니다. 본 변경의 실효성은 파일럿 데이터에서의 실측(removed_voxel_ratio, 재식별 시뮬레이션)으로 확인됩니다.

### 3.4 운영 리스크 — 격리 큐 누적

- v0.1 운영 중 파일럿 병원에서 번인·두경부 격리 큐가 누적되어 **최대 40%까지 공급량이 잠길 수 있다는 추정**(리서치 §4.1.2)이 있습니다. v0.2는 이 큐를 **사람이 결정하지 않아도 안전하게 처리 가능한 경로**로 승격시킵니다. 즉 병원의 실질 공급량을 해제하는 효과입니다.

---

## 4. 기본값은 OFF — 왜 그렇게 설계했는가

`deid.pixel.enabled`의 기본값은 **`false`** 입니다.

### 4.1 옵트인 설계 이유

1. **기술적 충격 최소화**: 기존 v0.1 운영 결과에 영향을 주지 않고 업그레이드하실 수 있습니다. 이미지를 0.2.0 slim으로만 교체하면 픽셀 처리는 전혀 실행되지 않으며, 바이트 동등(bit-equivalent) 결과가 보장됩니다(QA AC-15).
2. **법무 자문 선행**: FSL 상업 라이선스 재확인이 진행 중이므로, 법무 자문 완료 전에는 각 병원이 활성화 여부를 결정하지 않아도 됩니다.
3. **임상 QA 선행**: 과마스킹(over-redaction) 또는 과defacing(over-defacing)은 드물지만 이론적으로 임상적 오독을 유발할 수 있습니다. 활성화 전 **파일럿 병원의 영상의학과 전문의 샘플 리뷰**가 필수입니다(§5.4 참고).
4. **모달리티별 점진 활성**: 병원 내에서 US → SC → CT/MR 순서로 점진 활성화하실 수 있도록 config가 설계되어 있습니다.

### 4.2 되돌리기(Rollback)의 기본 보장

`deid.pixel.enabled=false`로 config만 다시 설정하고 재기동하시면 즉시 v0.1 동작으로 복귀합니다. Docker 이미지를 `0.2.0-pixel`에서 `0.2.0`(slim)으로 바꿔 치면 픽셀 의존성 자체도 제거됩니다. 데이터 손실·메타 변경은 발생하지 않습니다.

---

## 5. v0.2 활성화에 필요한 것

### 5.1 새 Docker 이미지

- **기본 업그레이드(픽셀 미사용)**: `radivault-gateway:0.2.0` (slim, 약 150MB). 디스크 증가 미미.
- **픽셀 활성화 배포**: `radivault-gateway:0.2.0-pixel` (약 **750MB~1.2GB**). 첫 다운로드 시 약 +600MB~1GB 디스크 필요. (dev-spec §9.6)
- **PaddleOCR variant**: `radivault-gateway:0.2.0-pixel-paddle` (약 2GB+). 현재 내부 실험용이며 파일럿 배포 대상 아님.

이미지 간 전환은 `docker compose pull` + `docker compose up -d`만으로 완료됩니다. Config만 동일하면 UID 매핑 DB·감사 로그·staging 디렉터리는 그대로 승계됩니다.

### 5.2 Config 변경

- `deid.pixel.enabled: true` — 픽셀 파이프라인 전체 스위치.
- `deid.pixel.ocr.engine: tesseract` — 기본 엔진(Tesseract 5).
- `deid.pixel.ocr.confidence_threshold: 0.60` — OCR 박스 채택 임계.
- `deid.pixel.defacing.enabled: true` — 두경부 defacing 활성.
- `deid.pixel.defacing.min_removed_ratio: 0.05` — 잔여 얼굴 복셀 임계(리서치 §4.7.2 경험값, 파일럿 실측 후 조정).
- `deid.pixel.defacing.exclusion_patterns: [...]` — 의료 제외 리스트(기본 7개 영문 패턴, 한국어 패턴은 **v0.2.1에서 파일럿 수집 후 보강 예정**).
- `deid.pixel.quarantine_on_failure: true` — 실패 시 자동 격리(권장 고정).

예시 `configs/gateway.pixel.example.yaml`이 함께 제공되며, 파일럿 별 커스터마이즈는 RadiVault 운영팀과 함께 진행됩니다.

### 5.3 모달리티별 점진 활성화 (권장)

처음부터 모든 모달리티를 활성화하지 마시고, 다음 순서를 권장드립니다.

1. **1주차**: `US` 또는 `SC`만 OCR 마스킹 활성 (`deid.pixel.ocr.modalities_allowlist: ["US"]` 등).
2. **2–3주차**: `BurnedInAnnotation=YES` 스터디 전수 활성.
3. **4주차 이후**(법무 자문 완료 후): 두경부 CT·MR defacing 활성.
4. **파일럿 수집 후**: 한국어 의료 제외 패턴 보강 → v0.2.1 롤아웃.

### 5.4 임상 QA 사전 약정 (중요)

픽셀 처리 활성 이후 **초기 10–20%의 스터디 샘플에 대해 영상의학과 전문의의 리뷰**(리서치 §4.7.3, dev-spec §12.2)가 필요합니다. 구체적으로:

- **최소 50건 샘플** — OCR 마스킹 결과에 진단적 텍스트(US caliper, Doppler 값 등)가 가려졌는지 전문의 확인.
- **최소 50건 샘플** — defacing 결과에 안와·전두엽 등 진단 영역 침범이 있는지 확인.
- 리뷰어 1인 이상의 **서명된 문서**(샘플 리뷰 Sign-off)가 프로덕션 전환 전 필수.

샘플링 비율·리뷰어 지정 방식은 병원과 개별 약정합니다(오픈 질문 #10, Kyle 결정 대기).

### 5.5 FSL 라이선스 사전 확인

- pydeface가 런타임에 호출하는 **FSL(FMRIB Software Library)**는 학술·비상업 배포 라이선스입니다.
- 상업 배포 시 FMRIB(옥스퍼드 대학)로부터 **별도 상업 라이선스**가 필요한지 Kyle 측이 **법무 자문**을 진행 중입니다.
- 자문 결과에 따라 defacing 활성화 시점·조건이 확정됩니다. 법무 자문 완료 전까지는 **OCR 마스킹만 활성화**하시고, defacing은 보류하시는 것을 권장드립니다.
- mridefacer 단독 사용(FSL 비의존 경로)도 대안으로 검토 중이며, 파일럿 병원별 기술 옵션으로 제공 가능할 수 있습니다(오픈 질문 #3).

---

## 6. 성능·비용 영향 (참조치, 파일럿 실측 필요)

아래 수치는 **dev-spec §10.7 NFR 성능 AC 기반 설계 목표**이며 파일럿 환경에서의 **실측치는 아직 검증 중**입니다(QA AC-29/30/31 NOT VERIFIABLE 상태).

| 항목 | 설계 목표 (4 vCPU / 8GB RAM 기준) | 비고 |
|---|---|---|
| US 50프레임 1 스터디 OCR | p95 **≤ 60초** | 프레임별 순회 + 재검증 포함 |
| 두개부 CT 400슬라이스 defacing | p95 **≤ 90초** | pydeface 전체 볼륨 기준 |
| 단일 스터디 처리 중 워커 RSS 피크 | **≤ 2 GB** | resource.getrusage 측정 |
| pixel-eligible 스터디의 E2E p95 추가 지연 | v0.1 대비 **+120초 이내** | 전체 pipeline 비교 |
| pixel-skip 스터디 (triage=SKIP) 추가 지연 | **+1초 이내** | 대상 아닌 스터디는 영향 미미 |

**디스크**: Docker 이미지 +600MB~1GB (일회성). staging 영역은 v0.1 대비 증가 없음.

**CPU**: OCR·defacing은 CPU-bound이며 기본 설계는 **동기 in-process 워커**(v0.2 MVP 범위). 병렬 처리량이 필요한 경우 워커 풀 도입은 **v0.2.1**로 예정되어 있습니다. 파일럿 단계에서는 기존 병원 서버 CPU 사양이 4 vCPU 이상이면 목표 지연 범위를 만족할 것으로 예상됩니다(실측 필요).

**파일럿 수집 이후**: 실측 기반으로 NFR 임계 조정, 한국어 OCR 품질 벤치마크, CT/MR 템플릿 정합률을 공유해드립니다.

---

## 7. Rollback 경로

문제 발생 시 **두 단계 모두 병원 측에서 단독 수행 가능**합니다.

### 7.1 Config 즉시 OFF (1단계)

```yaml
# configs/gateway.yaml
deid:
  pixel:
    enabled: false        # ← false로 변경 후 재기동
```

```bash
docker compose restart gateway-agent
```

**효과**: 픽셀 파이프라인 전체 skip. v0.1과 바이트 단위 동일 동작(AC-15 검증). 이미 익명화·전송 완료된 데이터에 변경 없음.

### 7.2 Docker 이미지 교체 (2단계, 의존성 자체 제거)

```yaml
# docker-compose.yml
services:
  gateway-agent:
    image: radivault-gateway:0.2.0          # ← slim 이미지로 복귀
    # image: radivault-gateway:0.2.0-pixel  # 제거
```

```bash
docker compose pull && docker compose up -d
```

**효과**: Tesseract·pydeface·FSL 의존성 모두 제거. 공격 표면 축소. UID 매핑 DB·감사 로그·staging은 그대로 승계.

### 7.3 v0.1로 전면 복귀 (3단계, 비상시)

매우 드문 경우이지만 v0.2 자체를 철회하셔야 한다면 v0.1 이미지(`radivault-gateway:0.1.x`)로 교체하시면 됩니다. 이 경우에도 데이터 손실·메타 변경은 없습니다. 교체 전 RadiVault 운영팀에 연락 주시면 Config schema 호환성을 사전 점검해드립니다.

---

## 8. 의료 제외 리스트 (자동 defacing 금지 대상)

얼굴 자체가 진단 ROI인 스터디는 **자동 defacing을 적용하지 않습니다**. 대신 **격리**로 라우팅되어 사람(영상의학과 전문의)이 업로드 여부를 결정합니다(`ERR_PIXEL_MEDICAL_EXCLUSION`).

기본 제외 패턴(StudyDescription 기반, 대소문자 무시, 영문 7 카테고리):

| 카테고리 | 예시 키워드 |
|---|---|
| 치과 | `DENTAL`, `DENTAL CBCT`, `TOOTH` |
| ENT (이비인후과) | `ENT`, `SINUS`, `TEMPORAL BONE`, `MASTOID` |
| 안와·안과 | `ORBIT`, `OPHTHALM` |
| 얼굴 외상 | `FACIAL TRAUMA`, `FACE FRACTURE` |
| 악안면 | `MAXILLOFACIAL`, `MANDIBLE` |
| 부비동 | `SINUS`, `PARANASAL` |
| 안와 바닥 | `ORBITAL FLOOR` |

**한국어 키워드**(`치과`, `부비동`, `안와` 등)는 기본 패턴에 포함되어 있지 않습니다(QA AC-11 확인). 파일럿 병원의 실제 StudyDescription 수집 후 **v0.2.1에서 병원별 `extra_patterns`로 보강** 예정입니다. 파일럿 초기에 한국어 StudyDescription을 사용하시는 병원은 **수동으로 `extra_patterns`를 추가**하시거나 RadiVault 운영팀과 공동 수집·리뷰하시도록 권장드립니다.

> **⚠ 책임 경계**: 의료 제외 리스트는 "사람이 결정"하는 경로입니다. 과제거로 인한 임상적 오독 리스크와 판매 계약의 면책 조항은 **법무 자문·영업 협의 사항**이며(오픈 질문 #12), 본 공지문이 확정하지 않습니다.

---

## 9. 자주 묻는 질문 (FAQ)

**Q1. v0.2 업그레이드는 의무인가요?**
아닙니다. v0.2 기본 이미지(`0.2.0` slim)로 이미지만 교체하시면 v0.1 동작이 유지됩니다. 픽셀 기능 활성화는 병원이 준비되셨을 때 결정하시는 **opt-in**입니다.

**Q2. 업그레이드 시 기존 데이터 전송 내역이 재처리되나요?**
아닙니다. 이미 전송된 메타데이터·영상은 **재처리 대상이 아닙니다**(dev-spec §3 Out-of-scope #7). 과거 격리된 스터디의 재처리는 **v0.3 이후** 별도 스펙으로 설계됩니다.

**Q3. 픽셀 처리 중 원본 DICOM이 병원 밖으로 나가나요?**
아닙니다. 픽셀 처리는 v0.1과 동일하게 **병원 내 Gateway Agent 내부**에서 완료됩니다. 익명화 완료 데이터만 TLS 1.3 아웃바운드로 RadiVault 중앙에 송출됩니다. UID 매핑 테이블·salt 파일·감사 로그는 병원 내부에만 잔존합니다.

**Q4. OCR이 환자 이름을 잘못 읽거나 건너뛴 경우는 어떻게 되나요?**
OCR 신뢰도가 임계 미만이면 자동으로 **격리**됩니다(`ERR_PIXEL_OCR_LOW_CONFIDENCE`). 또한 마스킹 후 **재OCR 검증**을 통과하지 못하면 역시 격리됩니다(`ERR_PIXEL_RESIDUAL_TEXT`). 즉 **불확실하면 중앙으로 보내지 않는 것이 기본 설계**입니다.

**Q5. defacing이 두개부 병변을 가리지는 않나요?**
pydeface는 얼굴 표면 **피부·근육층** 복셀만 제거하도록 템플릿 정합으로 설계됩니다. 다만 정합 실패 시 안와·전두엽 부근 조직까지 영향을 줄 가능성이 있으므로(리서치 §4.4.2), 활성화 전 **영상의학과 전문의 샘플 리뷰**가 필수이며(§5.4), `min_removed_ratio` 임계 미만은 자동 격리로 처리됩니다.

**Q6. 중앙 서버나 구매자 포털 쪽은 바뀌나요?**
아닙니다. **Gateway ↔ Central 계약은 불변**입니다(dev-spec §1.2). `/v1/ingest/studies`, `/v1/audit/anchor` API, manifest.json 스키마, 메타데이터 인덱스 저장 구조가 변경되지 않습니다. v0.2 활성화 병원과 v0.1 병원이 혼재 운영됩니다.

**Q7. 감사 로그는 어떻게 바뀌나요?**
기존 `audit.log`(hash-chained) 체인이 그대로 유지되며, pixel 이벤트가 같은 체인에 이어서 기록됩니다(무결성 보존). 별도 테이블 `pixel_audit_event`가 운영 통계·조회용으로 추가됩니다. **OCR로 추출된 텍스트 원문은 절대 저장되지 않습니다**(FR-38, QA Round 2 Section 5.1 PASS). 박스별 SHA-256[:16] 해시만 기록됩니다.

**Q8. 이미지 다운로드 시간·디스크가 많이 늘어나나요?**
이미지 자체는 약 **+600MB~1GB**의 일회성 다운로드가 필요합니다. 장기 운영 시 staging·DB 크기 증가는 v0.1 대비 유의미한 차이가 없습니다.

**Q9. 국내 내부 AI 학습 용도로만 사용하려 해도 v0.2가 필요한가요?**
국외이전을 하지 않는 내부 연구·학습 용도라면 개인정보보호법 §28조의8 제약이 직접 적용되지는 않습니다. 다만 **번인 PHI 잔존**은 내부 유통에서도 리스크이며, v0.2의 OCR 마스킹은 "사내에서의 재식별 위험"도 함께 줄여 드립니다. 활성화 여부는 DPO·법무 판단 대상입니다.

**Q10. v0.2.1에서 예정된 항목은 무엇인가요?**
주요 예정: 한국어 의료 제외 패턴 기본 포함(파일럿 수집 기반), 휴리스틱 번인 탐지(태그 누락 시 엣지 밀도·히스토그램 검사), 비동기 워커 풀, 세분 감사 이벤트(triage/ocr/deface started·completed 분리), `PIXEL_DEIDED` state 활용, bilingual CLI help, 환경변수 네이밍 통일, DICOM→NIfTI 변환 레이어(파일럿 head CT/MR 투입 이전 필수 해결). (QA Round 2 §2.6 v0.2.1 backlog 참조)

---

## 10. 지원 및 다음 단계

- **기술 문의**: `support@radivault.io` *(배포 전 실제 계정 확정 필요 — Kyle 리뷰 항목)*
- **파일럿·계약 문의**: `pilot@radivault.io` *(placeholder)*
- **컴플라이언스·DPO 문의**: `compliance@radivault.io` *(placeholder)*
- **업그레이드 일정 협의**: 파일럿 병원 담당자께 별도 개별 안내드립니다.

**권장 다음 행동 (CTA)**: 귀원 DPO·IT·영상의학과와 **30분 활성화 사전 미팅**을 잡아 주시면, RadiVault 운영팀이 귀원의 모달리티·볼륨을 기준으로 점진 활성화 플랜과 임상 QA 샘플 리뷰 일정을 함께 설계해드립니다.

---

## 11. Kyle 리뷰 필수 항목 (외부 배포 전)

1. FSL 상업 라이선스 법무 자문 결과 반영(오픈 질문 #3).
2. 과마스킹·과defacing 책임 경계 문구 확정(오픈 질문 #12).
3. 임상 QA 샘플 리뷰 비율·리뷰어 지정 방식 확정(오픈 질문 #10).
4. 한국어 의료 제외 패턴 포함 정책(오픈 질문 #4).
5. 수치 TBD 항목 실측 치환 — OCR/defacing 지연 p95, 파일럿 병원별 격리 큐 비율.
6. 지원 이메일 주소(placeholder) 실제 운영 계정으로 교체.
7. 파일럿 계약 병원 명단 비공개 원칙 재확인(본 문서는 병원명 미포함).

---

## 12. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|---|---|---|---|
| 0.1 | 2026-04-22 | @marketer (Claude Opus 4.7 1M) | 최초 작성. de-id-pixel v0.2(= Gateway Agent v0.2) 병원 공지 초안. QA Round 2 PASS 후 작성. 10개 FAQ + 모달리티별 점진 활성화 + rollback 3단계 + 의료 제외 리스트 정리. FSL 라이선스·임상 QA·한국어 패턴 미확정 항목은 명시 플래그. Kyle 리뷰 대기. |

---

### NEXT_STEP
- 완료 산출물: `docs/marketing/changelog-v02-pixel-deid-ko.md` (Draft)
- 청중·채널: hospital-korea / changelog (v0.2 공지)
- Kyle 리뷰 필요 사항: §11 7개 항목 (FSL 법무·책임 경계·임상 QA·한국어 패턴·TBD 수치·이메일·병원명 정책)
- 제안 다음 단계: Kyle 승인 후 파일럿 병원 담당자 개별 전달. 실측 수치 확보 후 v0.2 정식 공지로 승격.
- Kyle 결정 필요 사항: FSL 상업 라이선스 법무 결과, 한국어 exclusion 패턴 기본 포함 여부, 임상 QA 샘플 비율 공식화.
