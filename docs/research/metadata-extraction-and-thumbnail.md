# Metadata Extraction & Ingest-time Thumbnail — 기술적 기반 리서치

## 0. 메타

- **Status**: Draft v0.1
- **작성일**: 2026-04-25
- **작성자**: @researcher (Claude Opus 4.7 [1M])
- **근거 요청**: 메인 세션 — D-13 (2026-05-08) CEO 데모 BLOCKER. 250 study 모두 `body_part`, `age_bucket`, `sex`, `manufacturer`, `model_name`, `study_date_shifted`, `n_series=0`, `total_bytes=0` null. facet 응답이 modality 외 모두 `null:250`. 썸네일 0장. 이전 researcher 가 "필드 enumeration" 과 "ingest-time 자동화" 를 짚어내지 못해 dev-spec 이 "modality 만 추출" 로 implicit 동작.
- **선행 문서 (필수)**:
  - [`docs/prd.md` §4.2, §4.3](../prd.md)
  - [`docs/ARCHITECTURE.md` §3.2 De-ID, §4.1 Metadata Index, §4.3 Thumbnail Cache](../ARCHITECTURE.md)
  - [`docs/research/metadata-index-technical-foundations.md`](./metadata-index-technical-foundations.md) — buyer-facing search 의 facet 화이트리스트(modality, body_part, sex, age_bucket, manufacturer, year)
  - [`docs/research/buyer-browse-preview-download.md` §4.1, §4.3](./buyer-browse-preview-download.md) — DICOM PS3.18 Sup 203 thumbnail spec
  - [`docs/research/de-id-pixel-technical-foundations.md` §4.1, §5](./de-id-pixel-technical-foundations.md) — burned-in PHI OCR, DICOM Annex E
  - `docs/specs/dev-spec-gateway-agent.md` §6 manifest schema (현재: modality 만)
  - `docs/specs/dev-spec-central-ingest.md` §6.2 study 테이블 스키마 (컬럼은 정의돼 있으나 manifest 가 비어 보냄)
  - `src/radivault_central/manifest/schema.py` (현 manifest Pydantic — body_part/manufacturer/model_name/study_date 필드 부재, n_series 부재)
  - `src/radivault_central/db/models.py:115-180` (study 테이블 — 컬럼 존재하나 ingest 시 null)
- **PRD/ARCHITECTURE 영향 (제안만, 직접 수정 금지)**:
  - PRD §4.1 (Gateway) "DICOM 메타데이터 익명화" 를 **"+ buyer-facet 필드 추출"** 로 보강 권고.
  - PRD §4.2 (Metadata Index) "코호트 검색 API: modality, body part, 연령대, 성별, 진단명, 장비 제조사, 촬영 연도" — 현 manifest 가 이를 못 채우고 있음. 명시 필요.
  - PRD §4.3 (구매자 포털) "썸네일 미리보기" 가 **ingest-time 자동화 의무** 임을 명시 권고.
  - ARCHITECTURE §3.2 De-ID Engine 책임에 "**buyer-facet 화이트리스트 필드 추출 + thumbnail 생성**" 추가 권고.
  - ARCHITECTURE §4.3 Thumbnail Cache + CDN: "**ingest-time 생성** vs lazy generation" 결정 명시 권고.
- **스코프**: 본 문서는 (1) 5사 facet 필드 enumeration, (2) DICOM 표준 필드 catalogue, (3) ingest-time 썸네일 생성 패턴, (4) PIPA/HIPAA 매핑, (5) RadiVault MVP/풀스코프 권고 5개 섹션. 본 문서는 **dev-spec 작성자가 그대로 카피할 수 있는 권고 표** 를 §5 에 명세화한다.
- **법률 자문 면책**: 본 문서는 법률 자문이 아니다. PIPA/HIPAA 분류는 변호사 자문 필수.

---

## 1. TL;DR

1. **현 실패의 근본 원인**: `src/radivault_central/manifest/schema.py` 의 `Manifest` 가 `modalities: list[str]` 한 필드만 가짐. `body_part`/`manufacturer`/`model_name`/`study_date_shifted`/`n_series`/`series[]`/`patient_age`/`patient_sex` 모두 manifest 스키마에 부재. **gateway 가 추출조차 하지 않음**. central 의 `study` 컬럼은 정의돼 있으나 모두 default null. → buyer search facet 응답이 `null:250` 이 되는 것은 정상 동작.
2. **5사 공통 facet 핵심 9개**: **Modality, Body Part Examined, Sex, Age, Manufacturer, Manufacturer Model, Study Date / Year, Slice Thickness, Pixel Spacing**. (TCIA + IDC 1차 출처 교집합. Segmed/Gradient 는 마케팅 카피 only — TBD: needs primary source). free-text 검색 대상 3 필드: **StudyDescription, SeriesDescription, ProtocolName**.
3. **MVP (D-13) 추출 권고 12 필드**: `modality`(이미), `body_part`, `study_date_shifted`(year buckets), `manufacturer`, `model_name`, `age_bucket`(5y), `sex`, `n_series`, `n_instances`, `total_bytes`, `slice_thickness_mm`, `kvp` (CT 만). 모두 DICOM Annex E "Retain Device Identity Option" + "Retain Patient Characteristics Option" 하에서 보존 가능.
4. **풀스코프 (v0.1.5) 추가 권고 6 필드**: `pixel_spacing_mm`, `magnetic_field_strength_t`(MR), `repetition_time_ms`(MR), `echo_time_ms`(MR), `contrast_bolus_used`(boolean), `protocol_name`(자유텍스트, free-text PHI 위험 — Clean Descriptors Option 필요).
5. **금지 필드 (PHI/free-text PHI)**: `PatientName`, `PatientID`, `AccessionNumber`, `ReferringPhysicianName`, `PerformingPhysicianName`, `OperatorName`, `InstitutionName`(또는 hospital_pk 로 대체), `InstitutionAddress`, `DeviceSerialNumber`, raw `StudyDate`/`PatientBirthDate`(date shift/age bucket 으로 대체).
6. **Ingest-time 썸네일**: **Option A (Gateway 가 manifest 만들 때 함께 생성)** 권고. 이유 — (a) 익명화 직후 burned-in PHI 검증을 한 번 더 수행한 픽셀에서 생성, (b) Zone 1 → Zone 2 outbound payload 에 포함되어 별도 backfill worker 불요, (c) lazy generation 은 D-13 demo 첫 클릭 latency 가 최악. JPEG 256×256 + PHI scrub OCR.
7. **중간 슬라이스 알고리즘**: **Kyle 권고 (단순 index/2) 채택**. 이유 — (a) Orthanc 공식 권고가 "ordered-slices middle element" 로 동일, (b) ImagePositionPatient z-median 은 sort/parse 비용이 추가되나 D-13 시점에 수익 없음, (c) v0.2 에 KOS (Key Object Selection) > z-median > index/2 우선순위로 업그레이드. multi-frame DICOM 은 `frame_number = NumberOfFrames // 2`.
8. **Backfill 전략**: **gateway re-ingest 권고**. 이유 — manifest 에 누락 필드가 통째로 없으므로 central 만으로 backfill 불가. 250 study 의 원본 DICOM 이 병원 PACS 에 잔존(RadiVault 의 데이터 주권 원칙) → gateway 재실행. **단축 경로**: D-13 demo 용 5–10 study 만 우선 처리 (manual seed) + 풀 250 study 는 D-13 후 batch.
9. **DICOM PS3.15 Annex E 옵션 채택 권고**: **Basic Profile + Retain Device Identity Option + Retain Patient Characteristics Option + Clean Descriptors Option + Retain Longitudinal Modified Dates Option**. 이 4 옵션 조합으로 본 §3 의 12 MVP 필드가 합법 보존 가능.

---

## 2. 조사 질문

1. TCIA·IDC·Segmed·Gradient·Flywheel 5사가 buyer-facing 검색 화면에 노출하는 facet 필드는 정확히 무엇인가? (마케팅 카피가 아닌 1차 spec/screenshot)
2. DICOM Patient/Study/Series/Instance 4 레벨에서 추출 가능한 모든 표준 필드는 무엇이며, 각각의 (group, element) 와 PHI 위험도는?
3. Ingest-time 썸네일을 (A) gateway 측 / (B) central 워커 / (C) lazy 첫 조회 시 생성할 때의 trade-off?
4. 단순 index/2 vs ImagePositionPatient z-median vs Key Object Selection — 어느 것이 D-13 MVP 에 합당한가?
5. 16-bit DICOM → 8-bit JPEG 변환 시 modality 별 자동 window/level 결정 알고리즘은?
6. PIPA 제28조의8 + HIPAA Safe Harbor 18 식별자에 대해 위 추출 필드 catalogue 는 어떻게 매핑되는가?
7. 250 study backfill 을 manifest 누락 상태에서 어떻게 회복할 것인가?

---

## 3. 방법론

- **1차 자료 (DICOM 표준)**:
  - DICOM PS3.3 §C.7 Patient/Study/Series/Image IE 정의 — https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.html
  - DICOM PS3.15 Annex E Basic Application Confidentiality Profile — https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_e.html
  - DICOM PS3.15 §E.3 Confidentiality Options (Retain Device Identity, Retain Patient Characteristics, Clean Descriptors, etc.) — https://dicom.nema.org/medical/dicom/current/output/chtml/part15/sect_e.3.html
  - DICOM PS3.18 Sup 203 Thumbnail Resource — https://dicom.nema.org/Dicom/News/March2018/docs/sups/sup203.pdf
  - DICOM PS3.3 §C.11.2 VOI LUT Module (window/level) — https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.11.2.html
- **1차 자료 (5사 공식 문서)**:
  - TCIA Radiology Portal User Guide — https://wiki.cancerimagingarchive.net/display/NBIA
  - IDC Portal Explore — https://portal.imaging.datacommons.cancer.gov/explore/
  - IDC Data Organization — https://learn.canceridc.dev/data/organization-of-data
  - Gradient Atlas (AI Developer) — https://gradienthealth.io/ai-developer/atlas/
  - Segmed Insight — https://www.segmed.ai/insight ; Insight 블로그 — https://www.segmed.ai/resources/blog/introducingsegmedinsight
  - Flywheel Basic Search — https://docs.flywheel.io/user/search/user_basic_search/
  - Flywheel Data Classification — https://docs.flywheel.io/user/enhance/user_data_classification/
- **1차 자료 (HIPAA/PIPA)**:
  - 45 CFR §164.514(b)(2)(i) HIPAA Safe Harbor — https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html
  - 한국 개인정보 보호법 제28조의8 — https://www.law.go.kr/LSW/lsInfoP.do?lsId=011357
  - 보건복지부 「보건의료데이터 활용 가이드라인」 (2024-12) — https://www.mohw.go.kr/board.es?mid=a10503000000&bid=0027&act=view&list_no=1483931
- **1차 자료 (구현 도구)**:
  - pydicom 3.0.2 dataset basics (`stop_before_pixels=True`) — https://pydicom.github.io/pydicom/stable/tutorials/dataset_basics.html
  - Orthanc Users — Thumbnails (ordered-slices middle element) — https://discourse.orthanc-server.org/t/thumbnails/361
  - Orthanc `/preview` (linear normalization) — https://discourse.orthanc-server.org/t/cannot-preview-dicom-file/6275/3
- **2차 자료 (학술/뉴스/벤치마크)**:
  - PMC 11522224 (2024) burned-in OCR pipeline (recall 99.92%)
  - PMC 8373794 — NCI Imaging Data Commons
  - Schwarz NEJM 2019 — face surface re-identification (defacing 결정 시 인용)
- **3차 자료**:
  - collectiveminds.health 2024 DICOM metadata extraction guide
  - fast.io 2026 DICOM metadata extraction
  - johndcook blog HIPAA 18 identifiers
- **검색일**: 2026-04-25.
- **한계**:
  - **Segmed Openda** 의 buyer-facing facet UI 는 **마케팅 카피만 공개**. 실제 facet 필드 매트릭스는 trial 계정·영업 데모 없으면 확인 불가. 본 문서 §4.1 의 Segmed 행은 "TBD: needs primary source" 다수.
  - **Gradient Atlas** 의 facet 도 marketing 페이지 이상으로는 미공개. SDK 메서드 시그니처도 비공개.
  - 한국 PACS (INFINITT, Maroo 등) 의 한국형 BodyPartExamined 코드 사용 실태는 별도 파일럿 측정 필요.

---

## 4. 결과

### 4.1 5사 facet/필터 필드 enumeration

#### 4.1.1 TCIA Radiology Portal (NBIA) — **1차 출처 가장 풍부**

> 출처: https://wiki.cancerimagingarchive.net/display/NBIA — 2026-04-25 조회.

**General Tab**
| 필드 | 타입 | DICOM tag (추정) | 비고 |
|------|------|------------------|------|
| Collections | multi-select | (custom) | 데이터셋 큐레이션 단위 |
| Date Released | date range | (custom) | 컬렉션 공개일 |
| Analysis Results | boolean toggle | (custom) | 파생 데이터 포함 여부 |
| Exclude commercial-restricted | boolean | (license) | 라이선스 필터 |
| Identifiers | free-text | (custom) | comma-separated ID 검색 |

**Patients Tab**
| 필드 | 타입 | DICOM tag | 비고 |
|------|------|-----------|------|
| Patient Sex | enum (F/M/Unspecified) | (0010,0040) PatientSex | |
| Patient Age | range slider (max 89, 90+ grouped) | (0010,1010) PatientAge | **HIPAA Safe Harbor: 90+ 단일 버킷** |
| Clinical Time Points | numeric (days since event) | (0012,0050) ClinicalTrialTimePointID | longitudinal |
| Number of DICOM Studies | numeric (min) | (derived count) | per-patient |
| Species | enum | (0010,2201) PatientSpecies | 다종 archive |

**Images Tab**
| 필드 | 타입 | DICOM tag | 비고 |
|------|------|-----------|------|
| Image Description | full-text (wildcard, quoted) | (0008,103E) SeriesDescription, (0008,1030) StudyDescription, (0018,1030) ProtocolName | **3 필드 동시 검색** |
| Image Modality | multi-select (ANY/ALL) | (0008,0060) Modality | TCIA "ALL" 연산자 지원 |
| Body Part Examined | multi-select | (0018,0015) BodyPartExamined | |
| Manufacturer | multi-select | (0008,0070) Manufacturer | |
| Slice Thickness | range slider (mm) | (0018,0050) SliceThickness | **수치형 facet** |
| Pixel Spacing (row) | range slider (mm) | (0028,0030) PixelSpacing[0] | **수치형 facet** |
| Phantoms | enum (only/exclude/include) | (custom) | 팬텀 필터 |

#### 4.1.2 IDC Imaging Data Commons — **1차 출처 직접 확인**

> 출처: https://portal.imaging.datacommons.cancer.gov/explore/ — 2026-04-25 조회.

| facet | 타입 | DICOM tag | 비고 |
|-------|------|-----------|------|
| Collection | multi-select | (custom) | 컬렉션 단위 |
| Analysis Results | multi-select | (custom) | 파생 |
| Primary Site Location | multi-select | (custom: clinical) | 종양 위치 |
| License | multi-select | (custom) | CC-BY 등 |
| Cancer Type | multi-select | (custom: clinical) | 진단명 |
| **Body Part Examined** | multi-select | (0018,0015) | |
| **Modality** | multi-select | (0008,0060) | |
| **Manufacturer** | multi-select | (0008,0070) | |
| **Manufacturer Model Name** | multi-select | (0008,1090) | TCIA 에는 없는 추가 facet |

UI 동작: "Check All / Uncheck All", "Sort by Count / Alphabetical", "Hide zero-count values", expandable sections.

#### 4.1.3 Gradient Atlas — **마케팅 카피 only, TBD**

> 출처: https://gradienthealth.io/ai-developer/atlas/ — 2026-04-25 조회.

| 필드 | 타입 | DICOM tag (추정) | 출처 인용 |
|------|------|-----------------|----------|
| Modality | multi-select | (0008,0060) | "searchable by modality" |
| Disease type | multi-select | (NLP-derived) | "searchable by ... disease type" |
| Keywords (radiology report) | full-text | (외부 RIS) | "search terms ... in the radiological report" |
| Age | range | (0010,1010) | "filter for patient attributes such as age" |
| Gender | enum | (0010,0040) | "and gender" |
| Series Descriptions | full-text | (0008,103E) | "filter ... through the metadata for things like specific series descriptions" |
| Acquisition Protocols | multi-select | (0018,1030) ProtocolName | "different types of acquisition protocols" |
| Study type | multi-select | (0008,1030) StudyDescription (추정) | "Filter by study type" |
| Longitudinal patient search | derived | (0010,0020) + study count | "patients with more than one study matching specific criteria" |

> **TBD: needs primary source** — 위 필드의 정확한 UI 매핑·DICOM tag·연산자(AND/OR/NOT)는 마케팅 페이지에서 추출 불가. trial 계정 또는 영업 데모 필요.

#### 4.1.4 Segmed Insight / Openda — **마케팅 카피 only, TBD 다수**

> 출처: https://www.segmed.ai/insight, https://www.segmed.ai/resources/blog/introducingsegmedinsight — 2026-04-25 조회.

| 필드 | 출처 인용 | DICOM tag (추정) |
|------|-----------|-----------------|
| Patient demographics (Age, gender, race, ethnicity) | "Patient demographics: Age, gender, race, and ethnicity where available" | (0010,1010), (0010,0040), (0010,2160) |
| Longitudinal images | "Screening, diagnosis, follow-up" | (custom: visit type) |
| EHR data (Diagnosis, Treatment history, Outcome) | "Diagnosis, Treatment history, Patient outcome" | (외부 EHR) |
| DICOM images + radiology reports + metadata | "DICOM images and radiology reports with accompanying metadata" | (포괄) |

> **TBD: needs primary source** — Segmed 의 facet UI 는 공개 카피 이상으로는 확인 불가. 영업 demo 또는 conference talk slide 필요.

#### 4.1.5 Flywheel — **research data platform, baseline 비교용**

> 출처: https://docs.flywheel.io/user/search/user_basic_search/, https://docs.flywheel.io/user/enhance/user_data_classification/ — 2026-04-25 조회.

| 필드 | 타입 | DICOM tag | 비고 |
|------|------|-----------|------|
| Project | multi-select | (custom) | Flywheel 컨테이너 |
| File Type | multi-select | (custom) | DICOM/NIfTI/JSON |
| **Modality** | multi-select | (0008,0060) | 표준 DICOM abbreviation (MR/CT/PT/MG/OPT) |
| **Classification** (Intent / Measurement / Features) | multi-select hierarchical | (Flywheel 자체 ontology) | "anatomy_t1w" 등 |
| Session Timestamp | date range | (0008,0020) StudyDate (추정) | |
| **Sex** | enum | (0010,0040) | |
| **Subject Age** (at time of session) | range | (derived) | session-time normalized |
| Custom Fields | free-text | (extensible) | FlyQL 쿼리 가능 |

Flywheel의 **Classification ontology**:
- **Intent**: Localizer, Structural, Functional, Fieldmap, Spectroscopy
- **Measurement**: T1, T2, BOLD, Diffusion, Perfusion, MRA
- **Features**: 3D, Multi-Echo, Motion-Corrected, EPI, Gradient-Echo

Flywheel 은 file-level classification 을 위해 **DICOM modality tag 외에 자체 ontology** 를 추가로 갖는다 — RadiVault 의 NLP Label Engine (PRD §4.2) 향후 설계의 비교 대상.

#### 4.1.6 5사 facet 비교 매트릭스 — 1줄 요약

| facet | TCIA | IDC | Gradient | Segmed | Flywheel | RadiVault MVP 권고 |
|-------|------|-----|----------|--------|----------|--------------------|
| Modality | YES | YES | YES | (포괄) | YES | **YES (이미 있음)** |
| Body Part Examined | YES | YES | (TBD) | (TBD) | (Classification으로 대체) | **YES (신규 추출)** |
| Manufacturer | YES | YES | (TBD) | (TBD) | (TBD) | **YES (신규 추출)** |
| Manufacturer Model Name | (X) | YES | (TBD) | (TBD) | (TBD) | **YES (신규 추출)** |
| Study/Session Date or Year | YES (Date Released) | (X) | (TBD) | (TBD) | YES | **YES (year bucket)** |
| Slice Thickness | YES (range) | (X) | (TBD) | (TBD) | (TBD) | **YES (range, v0.1.5)** |
| Pixel Spacing | YES (range) | (X) | (TBD) | (TBD) | (TBD) | YES (v0.1.5) |
| Patient Sex | YES | (X) | YES | YES | YES | **YES (신규 추출)** |
| Patient Age | YES (max 89, 90+) | (X) | YES | YES | YES | **YES (5y bucket, max 89, 90+)** |
| StudyDescription / ProtocolName | YES (full-text) | (X) | YES | (TBD) | YES | v0.1.5 (PHI 위험, Clean Descriptors 필수) |
| SeriesDescription | YES (full-text) | (X) | YES | (TBD) | YES | v0.1.5 (PHI 위험) |
| Disease Type / ICD-10 / Cancer Type | (Collection) | YES (Cancer Type) | YES | YES | (X) | **v0.2 NLP Label Engine 후** |
| License / Commercial use | YES | YES | (TBD) | (TBD) | (TBD) | v0.2 |
| Longitudinal (multi-study) | (Patients tab) | (X) | YES | YES | (Sessions) | v0.2 |

**핵심 결론**: 5사 교집합 = **Modality, BodyPartExamined, Manufacturer, ManufacturerModelName, Sex, Age, StudyDate/Year, (numeric: SliceThickness)**. 이 8개 + RadiVault 가 이미 표 행으로 갖는 `n_series`, `n_instances`, `total_bytes` = MVP 12 필드.

#### 4.1.7 수치형 facet (range slider/range filter)

| 필드 | 단위 | 출처 (5사 중) | DICOM tag | RadiVault 권고 |
|------|------|---------------|-----------|---------------|
| Patient Age | years (5y bucket) | TCIA, Gradient, Segmed, Flywheel | (0010,1010) | **MVP** (max 89, 90+ HIPAA-safe) |
| Slice Thickness | mm | TCIA | (0018,0050) | v0.1.5 |
| Pixel Spacing (row) | mm | TCIA | (0028,0030)[0] | v0.1.5 |
| Study Date / Year | year | TCIA, Flywheel | (0008,0020) shifted | **MVP** (year bucket) |
| File Size / Total Bytes | bytes | (없음) | (derived) | **MVP** (이미 컬럼 존재) |
| Number of Instances | count | (없음) | (derived) | **MVP** |
| Number of Series | count | (없음) | (derived) | **MVP** |
| KVP (CT) | kV | (없음, but 학계 일반) | (0018,0060) | **MVP for CT only** |
| Tube Current (CT) | mA | (없음) | (0018,1151) XRayTubeCurrent | v0.1.5 (CT) |
| Magnetic Field Strength (MR) | T (1.5/3.0/7) | (없음, but 표준) | (0018,0087) | v0.1.5 (MR) |
| Repetition Time (MR) | ms | (없음) | (0018,0080) | v0.1.5 (MR) |
| Echo Time (MR) | ms | (없음) | (0018,0081) | v0.1.5 (MR) |

#### 4.1.8 자유 텍스트 (full-text) 검색 대상 필드

| 필드 | DICOM tag | PHI 위험 | RadiVault 권고 |
|------|-----------|---------|---------------|
| StudyDescription | (0008,1030) | **중** (의사가 환자명·생년 입력하는 사례 있음) | v0.1.5, Clean Descriptors Option 필수 + PHI scrub |
| SeriesDescription | (0008,103E) | **중** (동일) | v0.1.5, 동일 |
| ProtocolName | (0018,1030) | 저-중 | v0.1.5 |
| ImageComments | (0020,4000) | **고** (자유 텍스트) | **금지** (full PHI 위험) |
| AdditionalPatientHistory | (0010,21B0) | **최고** | **금지** |

> **권고**: free-text 검색은 **v0.1.5 부터** 도입. **Clean Descriptors Option (DICOM PS3.15 §E.3.5)** 을 De-ID Engine 에 활성화하고 정규식 + 한국 이름 dictionary 로 PHI scrub 후 ingest. ImageComments / AdditionalPatientHistory 는 **불추출**.

### 4.2 DICOM 표준 — Patient/Study/Series/Instance 4 레벨 추출 catalogue

> 출처: DICOM PS3.3 §C.7 Information Entity 정의 — https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.html

#### 4.2.1 Patient level (DICOM PS3.3 §C.7.1.1)

| Tag | Keyword | VR | 추출? | RadiVault 처리 | PHI 등급 |
|-----|---------|----|----|---------------|---------|
| (0010,0010) | PatientName | PN | **N (제거)** | 제거 (Annex E Basic) | A** (HIPAA #1 Names) |
| (0010,0020) | PatientID | LO | **N → R(pseudo)** | pseudo_patient_key (gateway-side hash + salt) | A (#19 의료번호) |
| (0010,0030) | PatientBirthDate | DA | **N → B(age bucket)** | age_bucket = floor(age/5)*5, max 89, 90+ 단일 | A (#3 dates) |
| (0010,0040) | PatientSex | CS | **Y** | sex (M/F/O) — Retain Patient Characteristics Option | C (인구통계) |
| (0010,1010) | PatientAge | AS | **Y → B** | age_bucket (DOB 우선, fallback) | C |
| (0010,1020) | PatientSize | DS | Y (v0.2) | height_cm (반올림) | C |
| (0010,1030) | PatientWeight | DS | Y (v0.2) | weight_kg (반올림 5kg) | C |
| (0010,2160) | EthnicGroup | SH | Y (v0.2) | ethnic_group | C (인구통계, 한국 맥락에서는 가치 낮음) |
| (0010,2201) | PatientSpecies | LO | Y (option) | 한국 의료 환경에서는 항상 "Homo sapiens" → 미추출 | — |

#### 4.2.2 Study level (DICOM PS3.3 §C.7.2)

| Tag | Keyword | VR | 추출? | RadiVault 처리 | PHI 등급 |
|-----|---------|----|----|---------------|---------|
| (0020,000D) | StudyInstanceUID | UI | **Y → R(pseudo)** | pseudo_study_uid (SHA256 + per-hospital salt) | (UID 자체는 식별자) |
| (0008,0020) | StudyDate | DA | **N → B(date shift)** | study_date_shifted (per-patient offset) → year bucket facet | A (#3) |
| (0008,0030) | StudyTime | TM | N | (제거) | A (#3) |
| (0008,0050) | AccessionNumber | SH | **N (제거)** | 제거 (Annex E Basic) | A (#19 medical record) |
| (0008,0090) | ReferringPhysicianName | PN | **N (제거)** | 제거 | A (#1) |
| (0008,1030) | StudyDescription | LO | Y (v0.1.5) | Clean Descriptors Option + PHI scrub | **B (free-text PHI)** |
| (0008,1032) | ProcedureCodeSequence | SQ | Y (v0.1.5) | code_value, code_meaning (LOINC/RadLex) | C (코드 표준) |
| (0008,1048) | PhysiciansOfRecord | PN | N | 제거 | A (#1) |
| (0008,1050) | PerformingPhysicianName | PN | N | 제거 | A (#1) |
| (0008,1060) | NameOfPhysiciansReadingStudy | PN | N | 제거 | A (#1) |
| (0008,1080) | AdmittingDiagnosesDescription | LO | N | 제거 | **B (free-text PHI)** |
| (0010,21B0) | AdditionalPatientHistory | LT | N | 제거 | **B** |
| (0008,0080) | InstitutionName | LO | **N → hospital_pk** | RadiVault 의 hospital_pk 로 매핑(별도 테이블) | A (#16 IP/device 와 유사 식별 위험) |
| (0008,0081) | InstitutionAddress | ST | N | 제거 | A (#2) |

#### 4.2.3 Series level (DICOM PS3.3 §C.7.3)

| Tag | Keyword | VR | 추출? | RadiVault 처리 | PHI 등급 |
|-----|---------|----|----|---------------|---------|
| (0020,000E) | SeriesInstanceUID | UI | **Y → R(pseudo)** | pseudo_series_uid | (식별자) |
| (0008,0060) | Modality | CS | **Y** | modality (CT/MR/CR/DX/US/MG/PT/NM/XA/SC/OT) — **이미 추출 중** | C |
| (0008,103E) | SeriesDescription | LO | Y (v0.1.5) | Clean Descriptors + PHI scrub | **B** |
| (0018,0015) | BodyPartExamined | CS | **Y (MVP)** | body_part (CHEST/HEAD/ABDOMEN/PELVIS/SPINE/...) — **누락 필드, 추출 의무** | C |
| (0018,1030) | ProtocolName | LO | Y (v0.1.5) | protocol_name (Clean Descriptors) | B |
| (0008,0070) | Manufacturer | LO | **Y (MVP)** | manufacturer (GE/Siemens/Philips/Canon/Samsung/...) — Retain Device Identity Option | C-D (장비 추적 가능성) |
| (0008,1090) | ManufacturerModelName | LO | **Y (MVP)** | model_name — Retain Device Identity Option | C-D |
| (0018,1000) | DeviceSerialNumber | LO | N | 제거 (Retain Device Identity 가 Y/X 선택 가능 — RadiVault X 권고) | **A (HIPAA #6 device identifiers)** |
| (0008,0080) | InstitutionName | (위 study level 참조) | N → hospital_pk | | A |
| (0018,0050) | SliceThickness | DS | Y (v0.1.5) | slice_thickness_mm | C |
| (0028,0030) | PixelSpacing | DS | Y (v0.1.5) | pixel_spacing_mm[0], [1] | C |
| (0018,0060) | KVP | DS | Y (v0.1.5, CT only) | kvp | C |
| (0018,1151) | XRayTubeCurrent | IS | Y (v0.1.5, CT) | tube_current_ma | C |
| (0018,0010) | ContrastBolusAgent | LO | Y (v0.1.5) | contrast_used (boolean) + agent name | C |
| (0018,0087) | MagneticFieldStrength | DS | Y (v0.1.5, MR) | b0_tesla (1.5/3.0/7) | C |
| (0018,0080) | RepetitionTime | DS | Y (v0.1.5, MR) | tr_ms | C |
| (0018,0081) | EchoTime | DS | Y (v0.1.5, MR) | te_ms | C |
| (0018,1030) | ProtocolName | (위 참조) | Y (v0.1.5) | | B |

#### 4.2.4 Instance level (DICOM PS3.3 §C.7.4)

| Tag | Keyword | VR | 추출? | RadiVault 처리 | PHI 등급 |
|-----|---------|----|----|---------------|---------|
| (0008,0018) | SOPInstanceUID | UI | **Y → R(pseudo)** | pseudo_sop_uid | (식별자) |
| (0008,0016) | SOPClassUID | UI | **Y** | sop_class_uid (CT Image Storage / MR Image Storage / etc.) — **이미 추출 중** | — |
| (0020,0013) | InstanceNumber | IS | **Y** | instance_number — middle slice 결정에 사용 | — |
| (0020,0032) | ImagePositionPatient | DS | Y (v0.2) | image_position_z (썸네일 z-median 알고리즘 v0.2 업그레이드용) | — |
| (0020,0037) | ImageOrientationPatient | DS | Y (v0.2) | image_orientation (axial/coronal/sagittal 분류) | — |
| (0028,0010) | Rows | US | Y (derived) | rows | — |
| (0028,0011) | Columns | US | Y (derived) | cols | — |
| (0028,0100) | BitsAllocated | US | Y (derived) | bits_allocated (8/16) | — |
| (0028,1050) | WindowCenter | DS | Y (썸네일용) | window_center (JPEG 변환 시 자동 적용) | — |
| (0028,1051) | WindowWidth | DS | Y (썸네일용) | window_width | — |
| (0028,1052) | RescaleIntercept | DS | Y (CT) | rescale_intercept (HU 변환) | — |
| (0028,1053) | RescaleSlope | DS | Y (CT) | rescale_slope | — |
| (0028,0301) | BurnedInAnnotation | CS | **Y (게이트)** | burned_in_flag — quarantine/OCR 결정 | — |
| (0028,0008) | NumberOfFrames | IS | Y | n_frames (multi-frame 시 중간 frame 결정) | — |

#### 4.2.5 추출 vs 보존 vs 삭제 — 종합표 (PHI 등급)

PHI 등급 기준 (HIPAA Safe Harbor + PIPA):
- **A**: HIPAA 18 식별자 직접 매칭 또는 의료번호급 식별자 → **불보존 의무**.
- **B**: free-text PHI 잠재 → Clean Descriptors Option + PHI scrub 후 보존 가능.
- **C**: 비식별 인구통계/장비/임상 메타 → 보존 가능.
- **D**: 장비 식별성 (Manufacturer + Model + Hospital 조합 시 institution 추정 가능) → Retain Device Identity Option 명시 필요.

**MVP 12 필드** (D-13 추출 의무):
1. modality (Y, 이미)
2. body_part (Y, 신규)
3. study_date_shifted (Y, year bucket)
4. manufacturer (Y, 신규) — Retain Device Identity Option
5. model_name (Y, 신규) — Retain Device Identity Option
6. age_bucket (Y, 5y, max 89, 90+)
7. sex (Y, M/F/O) — Retain Patient Characteristics Option
8. n_series (Y, derived count)
9. n_instances (Y, derived count)
10. total_bytes (Y, derived sum)
11. slice_thickness_mm (Y, CT/MR — Series-level)
12. kvp (Y, CT only — Series-level)

**v0.1.5 추가 6 필드**:
13. pixel_spacing_mm (Series)
14. tube_current_ma (CT, Series)
15. b0_tesla (MR, Series)
16. tr_ms (MR, Series)
17. te_ms (MR, Series)
18. contrast_used (boolean, Series)

**v0.2 추가 (NLP Label Engine 후)**:
- study_description (Clean Descriptors)
- series_description (Clean Descriptors)
- protocol_name
- icd10_codes (NLP-derived from radiology report)
- radlex_terms

**금지 (불추출)**:
- PatientName, PatientID raw, AccessionNumber
- ReferringPhysicianName, PerformingPhysicianName, OperatorName
- PhysiciansOfRecord, NameOfPhysiciansReadingStudy
- InstitutionName (raw), InstitutionAddress
- DeviceSerialNumber
- AdditionalPatientHistory, AdmittingDiagnosesDescription
- ImageComments
- raw StudyDate, raw PatientBirthDate (대신 shift/bucket)

### 4.3 Ingest-time 썸네일 생성 패턴

#### 4.3.1 DICOM PS3.18 Sup 203 — 표준 재확인

> 출처: https://dicom.nema.org/Dicom/News/March2018/docs/sups/sup203.pdf — RadiVault 의 [`buyer-browse-preview-download.md` §4.1](./buyer-browse-preview-download.md) 에서 이미 정리.

- 엔드포인트 4종: `/studies/{}/thumbnail`, `/series/{}/thumbnail`, `/instances/{}/thumbnail`, `/frames/{n}/thumbnail`.
- Media Type **`image/jpeg` 필수**, PNG/GIF 옵션.
- **"The Thumbnail shall not contain any Patient Identifying Information"** — spec 명문. burned-in PHI 검증 필수.
- 픽셀 크기 강제 없음. 산업 관행: 96–256 px (sidebar), 256–512 px (study card).

#### 4.3.2 중간 슬라이스 선택 알고리즘 — 5 옵션 비교

> 출처: Orthanc Users discourse (https://discourse.orthanc-server.org/t/thumbnails/361), buyer-browse-preview §4.3.

| 알고리즘 | 구현 복잡도 | 진단 정보 적합성 | RadiVault 권고 시점 |
|---------|-----------|------------------|--------------------|
| **A. 단순 인덱스 N/2** (Kyle 권고) | **최저** (1줄) | 다수 series 에서 충분, lesion 양 끝 시 약함 | **MVP D-13** |
| B. InstanceNumber 중앙값 (0020,0013 기반) | 낮음 | InstanceNumber 가 비순차일 때 안전 | v0.1.5 |
| C. ImagePositionPatient z-median (0020,0032) | 중 | **해부학적 중간** (sagittal/coronal 시리즈에 정확) | v0.2 |
| D. Non-zero pixel 영역 최대 (foreground) | 고 | lesion 가능성 슬라이스 우선 | v1.0 |
| E. Key Object Selection (DICOM KOS, 한국 INFINITT 일부 지원) | 중-고 | **판독의가 표시한 key image** — 임상 정확도 최상 | v1.0+ |

**Multi-frame DICOM (예: 일부 X-ray, US 시퀀스, 조영 dynamic)**: `frame_number = NumberOfFrames // 2` (DICOM tag (0028,0008)). Sup 203 의 `/frames/{n}/thumbnail` 엔드포인트 사용.

**Orthanc 공식 권고와의 정합성**:

> "take the middle element in the 'Slices' element of the array returned by the 'ordered-slices' URI associated with the series" (Orthanc Users, https://discourse.orthanc-server.org/t/thumbnails/361)

→ 이는 **InstanceNumber 또는 z-axis 로 sort 한 후 중간** 을 의미. RadiVault MVP 는 **단순 sorted_instances[len//2]** 으로 충분. Orthanc 자체도 sort 기준이 모호한 채로 동작 중이며 문서가 "deliberately vague" 하다.

**권고 파이프라인**:
```
1. series 내 instances 를 InstanceNumber ASC 로 sort
   (InstanceNumber null 이면 SOPInstanceUID lexical sort 로 fallback)
2. middle_idx = len(instances) // 2
3. NumberOfFrames > 1 이면 frame_idx = NumberOfFrames // 2, else 0
4. 해당 instance (또는 frame) 픽셀 추출
5. JPEG 변환 (§4.3.4)
```

#### 4.3.3 Thumbnail 생성 시점 — 3 옵션 trade-off

| Option | 위치 | 첫 조회 latency | 디스크 비용 | Ingest 시간 영향 | 익명화 안전성 |
|--------|------|----------------|------------|-----------------|--------------|
| **A. Gateway ingest 동시** | Zone 1 | ~0ms (사전 캐시) | Zone 2 storage | +200–800ms / study | **최상** (De-ID 직후 동일 픽셀) |
| B. Central background worker | Zone 2 | ~0ms (백필 후) | Zone 2 storage | 0 | 중 (재OCR 필요) |
| C. Lazy 첫 조회 시 | Zone 2 (HotStorage 가져오기) | **2–10초** (cold cache) | 적음 (Hot study 만) | 0 | 중 |

**Option A 권고 근거**:
1. **D-13 demo first-click latency**: lazy generation 은 첫 buyer 클릭 시 2–10초 정지 — demo 살인기. 사전 캐시 필수.
2. **익명화 픽셀과의 일관성**: gateway 가 De-ID 직후 같은 픽셀에서 thumbnail 생성 → "thumbnail 만 PHI 잔존" 위험 제거. Option B 는 central 측에서 다시 OCR 검증 필요 (중복 작업).
3. **Outbound payload 통합**: gateway → central 전송 시 manifest + DICOM + **thumbnail.jpg** 한 번에. 별도 backfill worker / storage round-trip 불요.
4. **Zone 1 outbound-only 원칙 부합**: ARCHITECTURE §3.3 "outbound-only HTTPS" 와 정확히 일치.
5. **현 250 study 의 backfill 도 동일 경로**: gateway re-ingest = thumbnail 자동 생성.

**Option B 의 경우 (참고)**: gateway 가 thumbnail 못 생성하는 환경 (예: 메모리 부족) 에서는 central worker 가 fallback. v0.2 옵션.

**Option C 의 경우 (배제 권고)**: B2B 데모/세일즈 컨텍스트에서 첫 조회 latency 가 치명적. 단, 1년 이상 미조회 study 의 thumbnail 을 **만료/재생성** 하는 cleanup 정책은 v1.0 검토.

#### 4.3.4 Thumbnail 포맷 + 픽셀 변환

**픽셀 크기 권고**:
- **256×256** (study card용, 검색 결과 카드) — MVP
- **512×512** (high-DPI / Retina 대응) — v0.1.5
- 16:9 또는 종횡비 보존: **letterbox black padding** (square 강제 — buyer UI grid 정렬 안정성)

**16-bit DICOM → 8-bit JPEG 자동 window/level**:

> 출처: DICOM PS3.3 §C.11.2 VOI LUT Module — https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.11.2.html

1. **DICOM VOI LUT 우선 적용** — `(0028,1050) WindowCenter` 와 `(0028,1051) WindowWidth` 가 DICOM 헤더에 있으면 그대로 사용. 이는 **장비/판독의가 권장한 표시 설정** 이므로 가장 의료적.
2. **VOI LUT 없으면 modality-default**:
   - **CT**: 헤드 (W:80 L:40), 흉부 (W:1500 L:-600 lung), 복부 (W:400 L:50). BodyPartExamined 기반 자동 선택.
   - **MR**: percentile-based — `min = p1, max = p99` (이미지 통계). T1/T2 자동 분류는 v0.2 NLP.
   - **CR/DX/MG**: VOI LUT 항상 존재 가정.
   - **US**: 이미 8-bit 일반적 — passthrough.
   - **PT (PET)**: SUV scaling — 별도 처리 (v0.2 권고, MVP 는 percentile fallback).
3. **RescaleSlope/Intercept 적용** (CT 한정): `HU = pixel * RescaleSlope + RescaleIntercept` 후 windowing.
4. **출력**: 8-bit grayscale JPEG, quality 85, ICC profile 미포함, EXIF strip.

**구현 라이브러리** (권고):
- **pydicom 3.x** + `apply_voi_lut()` + `apply_modality_lut()` (built-in). https://pydicom.github.io/pydicom/stable/tutorials/dataset_basics.html
- **Pillow** PIL.Image.fromarray + JPEG save.
- 의존 추가 없음 (gateway 가 이미 pydicom 사용 중).

**PHI scrub (burned-in)**:
- ingest-time thumbnail 생성 직전 **(0028,0301) BurnedInAnnotation 검사**.
  - YES → quarantine (썸네일 생성 X).
  - NO/unset 이면서 modality ∈ {US, SC, OT, XA, MG} → **Microsoft Presidio DicomImageRedactorEngine** OCR 1회 (de-id-pixel 리서치 §4.2 참조).
  - 안전 모달리티 (CT/MR/CR/DX) → corner OCR 만 (성능 최적화).
- OCR 양성 → quarantine + 운영자 알람.
- OCR 음성 → JPEG 생성 → Zone 2 업로드.

#### 4.3.5 Manifest / Storage 구조

**Manifest 확장 (gateway → central)**:
```jsonc
{
  "manifest_version": 2,            // bump for new schema
  "gateway_id": "...",
  "hospital_id": "...",
  "pseudo_study_uid": "...",
  "modalities": ["CT"],
  "modality_primary": "CT",         // NEW: 시리즈 다수 modality 시 대표
  "body_part": "CHEST",             // NEW
  "study_date_shifted": "2024-03-15",  // NEW (date, not datetime)
  "study_year": 2024,               // NEW (year bucket)
  "manufacturer": "GE Medical Systems", // NEW
  "model_name": "Revolution CT",    // NEW
  "patient": {                      // NEW (Retain Patient Characteristics)
    "age_bucket": 55,               // 50–54 → bucket 50; 90+ → 90
    "sex": "M",
    "pseudo_patient_key": "..."
  },
  "n_series": 4,                    // NEW (derived)
  "n_instances": 250,
  "total_bytes": 134217728,
  "series": [                       // NEW (per-series detail)
    {
      "pseudo_series_uid": "...",
      "modality": "CT",
      "body_part": "CHEST",
      "series_number": 1,
      "n_instances": 220,
      "slice_thickness_mm": 1.25,
      "kvp": 120,
      "tube_current_ma": 250,
      "contrast_used": true,
      "thumbnail_filename": "thumb_series_1.jpg"  // NEW
    },
    ...
  ],
  "thumbnail": {                    // NEW (study-level representative)
    "filename": "thumb_study.jpg",
    "width": 256,
    "height": 256,
    "source_series_pk_index": 0,   // 어느 series 에서
    "source_instance_index": 110,  // 220//2 = 110
    "phi_scrub_status": "passed",
    "phi_scrub_method": "presidio_dicom_v2.2.x"
  },
  "deid": { ... },
  "anonymization_flag": "FULL",
  "files": [...],
  "generated_at": "...",
  "audit_ref": {...}
}
```

**Storage 구조 (Zone 2 object store)**:
```
s3://radivault-meta/hospitals/{hospital_id}/studies/{pseudo_study_uid}/
  ├── manifest.json
  ├── thumb_study.jpg                    (256×256, study card용)
  ├── thumb_study_512.jpg                (512×512, high-DPI, v0.1.5)
  ├── thumbs/
  │   ├── series_1.jpg                   (series-level)
  │   ├── series_2.jpg
  │   └── ...
  └── (DICOM is in central_object_present=False / hot-storage 별도)
```

CDN cache: Cloudflare/CloudFront edge 24h, presigned read URL 만료 1h (썸네일은 익명정보지만 hot-link 방지).

#### 4.3.6 성능 추정

> 가정: 평균 study = 4 series × 220 instances, CT.

- pydicom dcmread (`stop_before_pixels=False`) + apply_voi_lut + Pillow JPEG: instance 1장 200–500ms (CPU).
- study-level thumbnail (1장) + series-level thumbnail (4장) = 5장 × 300ms = **1.5 초/study** 추가 ingest 시간.
- 250 study backfill: 1.5s × 250 = **6분 25초** (single thread). 4 worker 병렬: **~2분**.
- Burned-in OCR (Presidio): 추가 200–600ms / 평가 대상 instance.
- **결론**: D-13 까지 250 study backfill 충분 가능.

### 4.4 PIPA / HIPAA Safe Harbor 매핑

#### 4.4.1 HIPAA Safe Harbor 18 식별자 (45 CFR §164.514(b)(2)(i))

> 출처: https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html (검색 캐시 기반 — 본 문서 §3 출처 참조)

| # | 식별자 카테고리 | 매핑되는 DICOM tag | RadiVault 처리 |
|---|---------------|-------------------|---------------|
| A | Names | (0010,0010) PatientName, (0008,0090) ReferringPhysician, (0008,1050) PerformingPhysician, (0008,1070) OperatorName, (0008,1060) NameOfPhysiciansReading, (0008,1048) PhysiciansOfRecord | **D (모두 제거)** |
| B | Geographic subdivisions smaller than State (street, city, county, ZIP — 단, 첫 3자리 ZIP > 20K population 시 보존 가능) | (0010,1040) PatientAddress, (0008,0081) InstitutionAddress | **D** |
| C | All elements of dates (except year) for dates directly related to individual; 90+ aggregated | (0010,0030) PatientBirthDate, (0008,0020) StudyDate, (0008,0030) StudyTime, (0008,0022) AcquisitionDate, (0008,0023) ContentDate, (0040,0244) PerformedProcedureStepStartDate | **B (year-only / date shift / age bucket)** |
| D | Telephone numbers | (0010,2154) PatientTelephoneNumbers | **D** |
| E | Fax numbers | (custom) | **D** |
| F | Email addresses | (custom) | **D** |
| G | Social Security numbers | (custom — 한국은 주민등록번호) | **D** |
| H | Medical record numbers | (0010,0020) PatientID, (0008,0050) AccessionNumber | **R (pseudo)** / **D** |
| I | Health plan beneficiary numbers | (custom) | **D** |
| J | Account numbers | (custom) | **D** |
| K | Certificate/license numbers | (custom) | **D** |
| L | Vehicle identifiers | (custom) | **D** |
| M | Device identifiers and serial numbers | (0018,1000) DeviceSerialNumber, (0018,100B) ManufacturerDeviceClassUID | **D** (단, Manufacturer/Model 자체는 **K (보존, Retain Device Identity Option)** — 일대일 식별 가능성 낮음) |
| N | Web URLs | (custom) | **D** |
| O | IP addresses | (custom) | **D** |
| P | Biometric identifiers (finger/voice prints) | (custom) | **D** |
| Q | Full-face photographic images and comparable images | **얼굴 CT/MR 표면 (3D rendering 시 식별 가능)** — Schwarz NEJM 2019 | **C (3D defacing — pydeface)**, dental/ENT/orbit 제외 (de-id-pixel §4.5) |
| R | Any other unique identifying number, characteristic, or code | (0020,000D) StudyInstanceUID, (0020,000E) SeriesInstanceUID, (0008,0018) SOPInstanceUID, raw 환자 코드 | **R (pseudo UID)** |

#### 4.4.2 PIPA 시행령 별표 1 (가명정보 처리 기준) — 요약

> 출처: 개인정보 보호법 시행령 별표 1, 보건복지부 「보건의료데이터 활용 가이드라인」 2024-12. 본 문서 §3 출처.

PIPA 의 "**완전 익명정보**" 는 PIPA 적용 자체에서 제외. 핵심 기준:
- 단독 식별 불가 (HIPAA Safe Harbor 18 식별자 모두 제거)
- 다른 정보와 결합해도 식별 불가 (k-익명성 + l-다양성 권고)
- 재식별 시도 가능성에 대한 합리적 평가 + 문서화 의무

**RadiVault 의 적용**:
- **Manufacturer + Model + Hospital + Date + Age + Sex 조합** 의 재식별 가능성 평가 필요. 한국 의료기관의 경우 동일 modality·동일 model·동일 일자·동일 연령대 환자가 다수 → k≥5 보장 가능성 높음. 단, **희귀질환·소아·매우 고령**은 k 미달 위험 → 정책적 제외 (PRD §8 제약 이미 반영).
- **법률 자문 필수**: thumbnail preview 가 "더 적은 데이터" 임에도 buyer 측 정보주체 식별 가능성에 대한 합리적 평가 필요. (`buyer-browse-preview-download.md` §7.1 와 동일 결론).

#### 4.4.3 K/D/B/R/U 처리 분류 — 종합

기호 정의:
- **K** = Keep (보존)
- **D** = Delete (제거)
- **B** = Bucket (구간화/일반화)
- **R** = Replace with pseudo (가명 대체)
- **U** = UID replace (DICOM-specific)

| Tag | Keyword | 분류 | RadiVault MVP |
|-----|---------|------|---------------|
| (0010,0010) | PatientName | **D** | 제거 |
| (0010,0020) | PatientID | **R** | pseudo_patient_key |
| (0010,0030) | PatientBirthDate | **B** | age_bucket (5y, max 89) |
| (0010,0040) | PatientSex | **K** | sex |
| (0010,1010) | PatientAge | **B** | age_bucket |
| (0008,0020) | StudyDate | **B** | study_date_shifted (year facet) |
| (0008,0030) | StudyTime | **D** | 제거 |
| (0008,0050) | AccessionNumber | **D** | 제거 |
| (0008,0090) | ReferringPhysicianName | **D** | 제거 |
| (0008,1050) | PerformingPhysicianName | **D** | 제거 |
| (0008,1070) | OperatorName | **D** | 제거 |
| (0008,0080) | InstitutionName | **R** | hospital_pk (별도 테이블) |
| (0008,0081) | InstitutionAddress | **D** | 제거 |
| (0020,000D) | StudyInstanceUID | **U** | pseudo_study_uid |
| (0020,000E) | SeriesInstanceUID | **U** | pseudo_series_uid |
| (0008,0018) | SOPInstanceUID | **U** | pseudo_sop_uid |
| (0008,0060) | Modality | **K** | modality |
| (0018,0015) | BodyPartExamined | **K** | body_part |
| (0008,0070) | Manufacturer | **K** | manufacturer (Retain Device Identity Option) |
| (0008,1090) | ManufacturerModelName | **K** | model_name (Retain Device Identity Option) |
| (0018,1000) | DeviceSerialNumber | **D** | 제거 (Annex E 기본) |
| (0018,0050) | SliceThickness | **K** | slice_thickness_mm |
| (0028,0030) | PixelSpacing | **K** | pixel_spacing_mm |
| (0018,0060) | KVP | **K** | kvp (CT) |
| (0018,1151) | XRayTubeCurrent | **K** | tube_current_ma (CT, v0.1.5) |
| (0018,0010) | ContrastBolusAgent | **K** | contrast_used (boolean) (v0.1.5) |
| (0018,0087) | MagneticFieldStrength | **K** | b0_tesla (MR, v0.1.5) |
| (0018,0080) | RepetitionTime | **K** | tr_ms (MR, v0.1.5) |
| (0018,0081) | EchoTime | **K** | te_ms (MR, v0.1.5) |
| (0008,1030) | StudyDescription | **C\*** | Clean Descriptors Option (v0.1.5) — *PHI scrub 후 K |
| (0008,103E) | SeriesDescription | **C\*** | 동일 |
| (0018,1030) | ProtocolName | **C\*** | 동일 |
| (0020,4000) | ImageComments | **D** | 제거 |
| (0010,21B0) | AdditionalPatientHistory | **D** | 제거 |
| (0008,1080) | AdmittingDiagnosesDescription | **D** | 제거 |

> 별표 (\*): "Clean" = Clean Descriptors Option (DICOM PS3.15 §E.3.5) — 기본 제거 대상이나 옵션으로 PHI scrub 후 보존. v0.1.5 권고.

#### 4.4.4 채택 권고 — DICOM Annex E 옵션 조합

**RadiVault 기본 프로파일** = `Basic Profile` + 다음 옵션:

| Option | 채택? | 사유 | 영향 필드 |
|--------|-------|------|----------|
| §E.3.1 Clean Pixel Data Option | **Y** | burned-in PHI 마스킹 (de-id-pixel §4.3) | 픽셀 |
| §E.3.2 Clean Recognizable Visual Features Option | Y (CT 두개부) | 3D defacing (pydeface) | 픽셀 |
| §E.3.3 Clean Graphics Option | Y | overlay/graphic annotation 제거 | (60xx,3000), (0070,...) |
| §E.3.4 Clean Structured Content Option | Y (v0.2) | DICOM SR 정리 (NLP Label Engine 후) | SR |
| **§E.3.5 Clean Descriptors Option** | **Y (v0.1.5)** | StudyDescription/SeriesDescription/ProtocolName PHI scrub 후 보존 | (0008,1030)/(0008,103E)/(0018,1030) |
| §E.3.6 Retain Longitudinal Temporal Information with Full Dates | N | full date 노출 위험 | (0008,0020) |
| **§E.3.7 Retain Longitudinal Temporal Information with Modified Dates** | **Y** | per-patient date shift (이미 v0.1) → year bucket facet 가능 | (0008,0020), (0010,0030) |
| **§E.3.8 Retain Device Identity Option** | **Y (MVP)** | Manufacturer/ModelName 보존 (DeviceSerialNumber 는 그래도 X) | (0008,0070), (0008,1090) |
| §E.3.9 Retain UIDs Option | N | pseudo UID 가 RadiVault 정책 (역추적 매핑 테이블 병원 내부 잔존) | UIDs |
| §E.3.10 Retain Safe Private Option | N (v0.2 검토) | 벤더-특화 private tag 의 안전성 case-by-case | private |
| §E.3.11 Retain Institution Identity Option | N | 병원명 노출 X — RadiVault 의 hospital_pk 매핑으로 대체 | (0008,0080) |
| **§E.3.12 Retain Patient Characteristics Option** | **Y (MVP)** | Age, Sex 보존 (이미 RadiVault search 가 facet 으로 가정) | (0010,0040), (0010,1010), (0010,1020), (0010,1030) |

**DeidentificationMethodCodeSequence (0012,0064)** 기록 권고 (DCM 코드):
- 113100 = "Basic Application Confidentiality Profile"
- 113101 = "Clean Pixel Data Option"
- 113102 = "Clean Recognizable Visual Features Option" (조건부)
- 113103 = "Clean Graphics Option"
- 113105 = "Clean Descriptors Option" (v0.1.5)
- 113106 = "Retain Longitudinal Temporal Information Modified Dates Option"
- 113109 = "Retain Device Identity Option"
- 113111 = "Retain Patient Characteristics Option"

이미 dev-spec-gateway-agent.md FR-12 가 "DeidentificationMethodCodeSequence 기록" 을 요구. 본 옵션 조합으로 기록 코드 확장.

### 4.5 Backfill 전략 — 250 study 회복

#### 4.5.1 현황

- `radivault_central.manifest.schema.Manifest` 가 modality 외 facet 필드를 **수신조차 못함** → DB study row 의 body_part/manufacturer/model_name/study_date_shifted 모두 default null.
- raw_dicom_tags JSONB 컬럼은 존재하나 실 manifest 가 비워 보내고 있을 가능성 (dev-spec §6.5 manifest schema 미확인).
- thumbnail 0장.

#### 4.5.2 옵션 비교

| 옵션 | 작업 | 선결 조건 | 시간 추정 (250 study) | 권고 |
|------|------|-----------|----------------------|------|
| **A. Gateway re-ingest (전체)** | 병원 PACS 에서 250 study 재 fetch → 신 manifest schema 로 upload | gateway dev-spec 확장 + 신 manifest deploy | 평균 study 30s × 250 = **2시간** (4 worker 병렬 30분) | **권고** |
| B. Central-side raw_dicom_tags JSONB 파싱 (기존 데이터에서 facet 컬럼 채움) | central worker 가 raw_dicom_tags 에서 `BodyPartExamined` 등 추출 → study 컬럼 backfill | raw_dicom_tags 가 풍부히 채워져 있어야 함 (현재는 의문) | 250 study × 50ms = 13초 (가능 시) | **확인 필요**: raw_dicom_tags 가 의미있게 채워져 있나? 아니면 A로 |
| C. 5–10 study 만 manual seed (D-13 demo only) | 운영자가 demo 용 5 study 만 신 schema 로 재처리 | gateway dev-spec 일부만 deploy | 5 study × 30s = 2.5분 | **D-13 demo 단축경로** (병행 권고) |

**권고 조합**:
1. **즉시 (D-13 demo 살리기)**: Option C (manual seed 5–10 study) + 옵션 B 가능성 확인 (raw_dicom_tags 검증).
2. **D-13 ~ D-7**: Option A (gateway re-ingest 전체 250) — 권고. dev-spec 확장 후 stage 환경에서 검증, prod 적용.

#### 4.5.3 raw_dicom_tags 검증 SQL (선결)

D-13 dev-spec 작성자가 확인해야 할 SQL:
```sql
-- 250 study 의 raw_dicom_tags 가 비어있는지 확인
SELECT
  COUNT(*) AS total,
  COUNT(raw_dicom_tags) AS with_raw_tags,
  COUNT(raw_dicom_tags->>'(0018,0015)') AS with_body_part,
  COUNT(raw_dicom_tags->>'(0008,0070)') AS with_manufacturer,
  COUNT(raw_dicom_tags->>'(0008,1090)') AS with_model
FROM study;
```
- 결과가 `with_body_part = 250` 이면 Option B 즉시 가능.
- 결과가 `with_body_part = 0` 이면 manifest 가 처음부터 안 보냈음 → Option A 필수.

#### 4.5.4 Manifest schema migration

- `manifest_version: 1 → 2` bump.
- central 의 `Manifest` Pydantic class 에 신 필드 추가 (extra="allow" 이므로 v1 manifest 도 backward-compatible 으로 수신, 신 필드가 빈 채로 들어옴).
- gateway 가 v1 schema 로 보내면 central 은 기존처럼 modality 만 채우고 facet 컬럼 null → backfill 필요.
- gateway 가 v2 schema 로 보내면 central 은 신 필드를 study/series 로 분해 적재.

### 4.6 Facet UX 권고

> 출처: 5사 패턴 (§4.1) + RadiVault 의 [`metadata-index-technical-foundations.md` §4.3 facet whitelist](./metadata-index-technical-foundations.md).

| 필드 | UI 컴포넌트 | 권고 시점 |
|------|------------|----------|
| Modality | multi-select checkbox + count | MVP |
| Body Part Examined | multi-select autocomplete (긴 리스트 가능) | MVP |
| Manufacturer | multi-select checkbox + count | MVP |
| Manufacturer Model | multi-select autocomplete (벤더별 모델 다수) | v0.1.5 |
| Sex | radio (M/F/Other) | MVP |
| Age | range slider (5y bucket, max 89, 90+) | MVP |
| Study Year | range slider (year bucket) | MVP |
| Slice Thickness | range slider (mm, log scale) | v0.1.5 |
| Pixel Spacing | range slider | v0.2 |
| Contrast Used | toggle (Yes/No/Any) | v0.1.5 |
| Magnetic Field Strength (MR only) | radio (1.5T / 3.0T / 7T / Any) | v0.1.5 |
| StudyDescription | search input (full-text, autocomplete) | v0.1.5 (Clean Descriptors 후) |

Facet count UI:
- "Show top 20 / Show all" expand
- Zero-count hide toggle (IDC 패턴)
- Count sort vs Alphabetical sort toggle (IDC 패턴)
- "Selected" sticky 표시

---

## 5. 권고 (For RadiVault — dev-spec 카피용)

### 5.1 MVP (D-13) — 추출/persist 의무 12 필드

**Gateway dev-spec 추가 FR (예시 문구, 카피용)**:

> **FR-META-1 (Study-level extraction)**: Gateway 의 De-ID Engine 은 study 단위로 다음 메타데이터를 추출하여 manifest v2 의 study root + series 배열에 기록한다:
> - **Modality** (DICOM (0008,0060), 시리즈 다수 시 최빈치를 study.modality_primary 에)
> - **BodyPartExamined** (DICOM (0018,0015), 시리즈 다수 시 최빈치를 study.body_part 에). null/empty 시 "UNKNOWN" 으로 정규화.
> - **StudyDate** (DICOM (0008,0020)) → per-patient date shift 적용 후 study_date_shifted (YYYY-MM-DD), study_year (YYYY).
> - **Manufacturer** (DICOM (0008,0070), Retain Device Identity Option). 시리즈 다수 시 첫 series 값.
> - **ManufacturerModelName** (DICOM (0008,1090), Retain Device Identity Option). 동일.
> - **PatientAge / PatientBirthDate** → age_bucket = floor(age / 5) × 5, max 89, 90+ → 90 단일.
> - **PatientSex** (DICOM (0010,0040), Retain Patient Characteristics Option) → "M"/"F"/"O".
> - **n_series, n_instances, total_bytes** (derived counts).
> - Series-level: SliceThickness (mm), KVP (CT only).
>
> 추출 실패 시 (태그 부재) null 허용. 단, manifest 의 modality_primary, n_series, n_instances, total_bytes 는 non-null 필수.

> **FR-META-2 (Manifest schema v2)**: `Manifest` Pydantic class 에 위 필드를 신규 정의. `manifest_version: int = 2`. `extra="allow"` 유지하여 v1 backward-compatible.

> **FR-META-3 (Annex E options)**: Gateway 의 De-ID Engine 은 다음 DICOM Annex E 옵션 조합으로 동작:
> - Basic Profile + Clean Pixel Data + Clean Graphics + Retain Longitudinal Modified Dates + **Retain Device Identity** + **Retain Patient Characteristics**.
> - DeidentificationMethodCodeSequence (0012,0064) 에 코드 113100, 113101, 113103, 113106, 113109, 113111 기록.

> **FR-META-4 (Central ingest 분해)**: Central 의 ingest router 는 manifest v2 의 study root 필드를 study row 에 적재, series 배열을 series row 에 적재. raw_dicom_tags JSONB 에는 manifest 의 study/series 블록 그대로 보존 (감사 추적용).

### 5.2 풀스코프 (v0.1.5) — 추가 6 필드 + 자유 텍스트

**Gateway dev-spec 추가 FR (v0.1.5)**:

> **FR-META-5**: Series-level 추가 추출 — PixelSpacing, XRayTubeCurrent (CT), MagneticFieldStrength (MR), RepetitionTime (MR), EchoTime (MR), ContrastBolusAgent (→ contrast_used boolean).

> **FR-META-6 (Clean Descriptors)**: StudyDescription/SeriesDescription/ProtocolName 보존. PHI scrub 파이프라인 (정규식 + 한국 이름 dictionary + 주민번호 패턴) 통과 후 manifest 적재. Annex E §E.3.5 Clean Descriptors Option 코드 113105 추가.

### 5.3 Ingest-time Thumbnail FR

> **FR-THUMB-1 (Ingest-time generation, Option A)**: Gateway 가 manifest 생성 직전, 각 series 의 중간 instance (sorted_by_instance_number[len // 2], multi-frame 시 frame_number = NumberOfFrames // 2) 에서 256×256 JPEG thumbnail 을 생성하여 manifest 에 첨부 + Zone 2 업로드 payload 에 포함. study-level representative thumbnail 은 series_1 (또는 modality_primary 매칭 first series) 에서 동일 알고리즘.

> **FR-THUMB-2 (Window/level)**: pydicom `apply_voi_lut()` + `apply_modality_lut()` 사용. VOI LUT 부재 시 modality default (CT brain W:80 L:40 / chest W:1500 L:-600 / abdomen W:400 L:50 by BodyPartExamined; MR percentile p1-p99; CR/DX/MG VOI LUT 가정; US passthrough; PT percentile fallback).

> **FR-THUMB-3 (PHI scrub)**: thumbnail 생성 직전 (0028,0301) BurnedInAnnotation == YES → quarantine. 모달리티 ∈ {US, SC, OT, XA, MG} 또는 corner edge density 양성 → Microsoft Presidio DicomImageRedactorEngine OCR. OCR 양성 → quarantine + 운영자 알람. 음성 → JPEG 생성.

> **FR-THUMB-4 (Storage)**: `s3://radivault-meta/hospitals/{hospital_id}/studies/{pseudo_study_uid}/thumb_study.jpg` (256×256), `thumbs/series_{N}.jpg` (series-level). DICOM PS3.18 Sup 203 호환 JPEG. CDN edge cache 24h.

> **FR-THUMB-5 (Manifest)**: manifest v2 의 series 블록에 `thumbnail_filename`, study root 에 `thumbnail` 객체 (filename, width, height, source_series_index, source_instance_index, phi_scrub_status, phi_scrub_method) 기록.

### 5.4 Backfill FR

> **FR-BACKFILL-1 (Diagnostic SQL)**: D-13 dev 작업 시작 전 §4.5.3 SQL 실행하여 raw_dicom_tags 가 의미있게 채워져 있는지 확인. 결과 기록 → 이 결정이 backfill 경로 선택.

> **FR-BACKFILL-2 (Demo seed)**: D-13 demo 용 5–10 study 를 신 manifest schema v2 로 manual re-ingest. body_part/manufacturer/model_name/age_bucket/sex 모두 채워지고 thumbnail 5–10 장 생성된 상태로 demo. central 의 facet API 응답이 `null:5/10` 대신 의미있는 분포 노출.

> **FR-BACKFILL-3 (Full re-ingest, post-D-13)**: 250 study 전체를 gateway re-ingest. 4 worker 병렬, 약 30분 작업. 운영자 CLI 명령 (`radivault-gateway reingest --hospital {id} --since {date}`). 멱등성: pseudo_study_uid 동일 → upsert. raw_dicom_tags JSONB 는 gateway 가 보내는 신 manifest 의 study/series 블록으로 덮어쓴다.

### 5.5 Facet API FR (이미 metadata-index-technical-foundations.md 에 있음, 본 문서에서는 추출 필드만 보강)

기존 `metadata-index-technical-foundations.md §4.3.1` 의 facet whitelist 6 필드 → **8 필드로 확장 권고**:
- modality, body_part, sex, age_bucket, manufacturer, model_name, study_year, contrast_used (v0.1.5).

### 5.6 PRD/ARCHITECTURE 갱신 제안 (planner 가 PR 또는 메인 세션에 전달)

1. PRD §4.1: "DICOM 메타데이터 익명화" 다음에 **"+ buyer-search facet 필드 (Modality, BodyPart, Manufacturer, Model, Age bucket, Sex, StudyDate shifted, n_series, n_instances, total_bytes, SliceThickness, KVP) 추출 + 256×256 thumbnail 생성"** 을 의무 사항으로 명시.
2. PRD §4.2: "코호트 검색 API: modality, body part, 연령대, 성별, 진단명, 장비 제조사, 촬영 연도 범위" — 연도 범위는 buckets 라는 점, "장비 제조사" 가 manufacturer + model 두 facet 인 점 명시.
3. PRD §4.3: "썸네일 미리보기" 가 **ingest-time 자동 생성** 임을 명시. "운영자 수동 작업 불요" 명문.
4. ARCHITECTURE §3.2 De-ID Engine 책임 6번째 항목으로 **"buyer-facet 필드 추출 + thumbnail 생성 (256×256 JPEG, Sup 203 spec)"** 추가.
5. ARCHITECTURE §4.3 Thumbnail Cache + CDN: **"썸네일은 Zone 1 gateway 가 ingest-time 에 생성하여 Zone 2 로 outbound payload 에 포함시켜 송신. Zone 2 는 수신·캐시·CDN 분배만 담당"** 명문화.

---

## 6. 한계 · 오픈 퀘스천

1. **Segmed/Gradient 의 facet UI 매트릭스 미공개** — 본 문서 §4.1 의 두 사 행은 마케팅 카피만. trial 계정 또는 영업 데모로 보강 필요. (D-13 demo 후 follow-up)
2. **한국 PACS 의 BodyPartExamined 코드 사용 실태** — 실제 한국 병원 (INFINITT/Maroo) 이 (0018,0015) 를 일관되게 채우는지 미확인. 비어있는 경우가 다수면 StudyDescription NLP 로 backfill 필요. **파일럿 측정 의무**.
3. **Manufacturer + Model + Hospital 조합의 재식별 가능성 평가** — k-익명성 측정 미실시. PIPA 준수 입증 위해 필수. **법률 자문 + 통계 평가 후 dev-spec 확정** 권고.
4. **`raw_dicom_tags` JSONB 의 현 채움 정도 미확인** — Backfill Option B 가능 여부 결정 (§4.5.3 SQL 실행 필요). **D-13 작업 첫 단계로 수행 의무**.
5. **VOI LUT 기본값 결정** — Brain CT W:80 L:40 등은 industry default 이나 한국 영상의학과의 선호 windowing 이 다를 수 있음. Kyle 의 도메인 지식으로 추후 조정.
6. **PT (PET) thumbnail SUV scaling** — MVP 는 percentile fallback. v0.2 에 SUVbw 계산 정확도 평가.
7. **multi-frame DICOM frame_number = N//2 의 임상 적합성** — US 시퀀스, dynamic contrast 시 첫/마지막 frame 이 더 정보적인 사례 있음. 임상의 자문 권고.
8. **Microsoft Presidio 한국어 OCR 성능** — `de-id-pixel` §4.7 와 동일 한계. 한국어 모델 별도 평가 필요.
9. **Thumbnail 만료 정책** — 미조회 study 의 thumbnail cleanup. v1.0 검토.
10. **Backfill re-ingest 의 감사 로그 영향** — 동일 pseudo_study_uid 에 대해 ingest event 가 2회 발생. audit_ingest_event 의 유니크 제약·중복 표현 확인 필요. (planner 가 dev-spec 작성 시 점검).
11. **법률 자문 트리거**:
    - Annex E 옵션 조합 (Retain Device Identity + Patient Characteristics) 의 PIPA 28-8 합치 검토.
    - thumbnail preview 가 "익명정보" 인지 (buyer 측 식별 가능성) 합리적 평가.
    - StudyDescription Clean Descriptors 후 보존이 PIPA 가명정보 vs 익명정보 경계의 어디인지.

---

## 7. 출처 목록

### 1차 — DICOM 표준
- DICOM PS3.3 §C.7 IE definitions — https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.html
- DICOM PS3.3 §C.11.2 VOI LUT Module — https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.11.2.html
- DICOM PS3.15 Annex E Confidentiality Profiles — https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_e.html
- DICOM PS3.15 §E.3 Confidentiality Options — https://dicom.nema.org/medical/dicom/current/output/chtml/part15/sect_e.3.html
- DICOM PS3.15 §E.3.8 Retain Device Identity Option — https://dicom.nema.org/medical/dicom/current/output/chtml/part15/sect_E.3.8.html
- DICOM PS3.18 Sup 203 Thumbnail Resource — https://dicom.nema.org/Dicom/News/March2018/docs/sups/sup203.pdf
- Innolitics DICOM Standard Browser (Image Position Patient (0020,0032)) — https://dicom.innolitics.com/ciods/ct-image/image-plane/00200032
- Innolitics — Window Width (0028,1051) — https://dicom.innolitics.com/ciods/ct-image/voi-lut/00281051

### 1차 — 5사 공식 문서
- TCIA Radiology Portal User's Guide — https://wiki.cancerimagingarchive.net/display/NBIA
- TCIA Wiki (root) — https://wiki.cancerimagingarchive.net/x/NIIiAQ
- IDC Portal Explore — https://portal.imaging.datacommons.cancer.gov/explore/
- IDC Data Organization — https://learn.canceridc.dev/data/organization-of-data
- Gradient Atlas (AI Developer) — https://gradienthealth.io/ai-developer/atlas/
- Segmed Insight — https://www.segmed.ai/insight
- Segmed Insight 블로그 — https://www.segmed.ai/resources/blog/introducingsegmedinsight
- Flywheel Basic Search — https://docs.flywheel.io/user/search/user_basic_search/
- Flywheel Data Classification — https://docs.flywheel.io/user/enhance/user_data_classification/
- Flywheel Imaging Data Discovery — https://flywheel.io/flywheel-is-data-discovery/

### 1차 — HIPAA / PIPA / 한국 규제
- 45 CFR §164.514(b)(2)(i) HIPAA Safe Harbor (HHS Guidance) — https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html
- 45 CFR §164.514 (Bricker explainer with full text) — https://www.bricker.com/insights/resources/key/HIPAA-Privacy-Regulations-Other-Requirements-Relating-to-Uses-and-Disclosures-of-Protected-Health-Information-Requirements-for-De-Identification-of-Protected-Health-Information-164-514-b
- John D. Cook — 18 HIPAA identifiers explained — https://www.johndcook.com/blog/hipaa-identifiers-explained/
- 한국 개인정보 보호법 제28조의8 (국가법령정보센터) — https://www.law.go.kr/LSW/lsInfoP.do?lsId=011357
- 보건복지부 「보건의료데이터 활용 가이드라인」 (2024-12 개정 보도자료) — https://www.mohw.go.kr/board.es?mid=a10503000000&bid=0027&act=view&list_no=1483931
- 한국보건의료정보원 안내 — https://k-his.or.kr/board.es?mid=a10301000000&bid=0001&list_no=1538&act=view

### 1차 — 구현 도구
- pydicom 3.0.2 dataset basics — https://pydicom.github.io/pydicom/stable/tutorials/dataset_basics.html
- pydicom apply_voi_lut / apply_modality_lut — https://pydicom.github.io/pydicom/stable/tutorials/dataset_basics.html
- Orthanc Users — Thumbnails (ordered-slices middle) — https://discourse.orthanc-server.org/t/thumbnails/361
- Orthanc Users — Cannot preview DICOM file (preview normalization) — https://discourse.orthanc-server.org/t/cannot-preview-dicom-file/6275/3
- OHIF Viewer — https://ohif.org/
- Cornerstone3D — https://github.com/cornerstonejs/cornerstone3D
- Microsoft Presidio DICOM redactor — https://microsoft.github.io/presidio/samples/python/example_dicom_image_redactor/

### 2차 — 학술 / 가이드
- PMC 11522224 (2024) — A Method for Efficient De-identification of DICOM Metadata and Burned-in Pixel Text — https://pmc.ncbi.nlm.nih.gov/articles/PMC11522224/
- PMC 8373794 — NCI Imaging Data Commons — https://pmc.ncbi.nlm.nih.gov/articles/PMC8373794/
- Schwarz CG et al. (NEJM 2019) — Identification of Anonymous MRI Research Participants with Face-Recognition Software — https://www.nejm.org/doi/full/10.1056/NEJMc1908881
- collectiveminds.health — DICOM Metadata Extraction Guide 2024 — https://collectiveminds.health/articles/dicom-metadata-extraction-a-comprehensive-guide-for-medical-imaging-professionals-2024
- fast.io — DICOM Metadata Extraction 2026 — https://fast.io/resources/dicom-metadata-extraction-medical-imaging/

### 내부 (RadiVault)
- `docs/research/buyer-browse-preview-download.md` (2026-04-25) — DICOM PS3.18 thumbnail spec, OHIF integration
- `docs/research/de-id-pixel-technical-foundations.md` (2026-04-22) — burned-in PHI, Tesseract/Presidio, Annex E
- `docs/research/metadata-index-technical-foundations.md` (2026-04-22) — buyer search facet whitelist
- `docs/research/gateway-agent-technical-foundations.md` — DICOMweb, manifest schema v1
- `docs/research/central-ingest-technical-foundations.md` — central ingest 메트릭 / 인덱스
- `docs/research/portal-redesign-competitive-analysis.md` — buyer portal UX
- `docs/prd.md`, `docs/ARCHITECTURE.md`
- `docs/specs/dev-spec-gateway-agent.md` §6 (current manifest schema v1)
- `docs/specs/dev-spec-central-ingest.md` §6.2 (study columns)
- `src/radivault_central/manifest/schema.py` (current Pydantic — modality only)
- `src/radivault_central/db/models.py:115-180` (study/series ORM)

> 본 문서는 법률 자문이 아니다. PIPA/HIPAA/식약처 결론은 변호사·RaQA 자문 필수.

---

## 8. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-25 | @researcher (Claude Opus 4.7 [1M]) | 최초 작성. D-13 BLOCKER 대응 — 5사 facet enum + DICOM 4-level 추출 catalogue + ingest-time thumbnail 3-option + PIPA/HIPAA 매핑 + MVP/v0.1.5 권고 12+6 필드 + backfill 전략 + dev-spec 카피용 FR 문구. |

---

### NEXT_STEP
- 완료 산출물: `docs/research/metadata-extraction-and-thumbnail.md`
- 제안 다음 단계: **@planner** — `docs/specs/dev-spec-gateway-agent.md` 와 `docs/specs/dev-spec-central-ingest.md` 양쪽 확장. 본 리서치 §5.1–§5.5 의 FR 문구를 그대로 카피·번호 부여. **manifest schema v1→v2 bump**. 5–10 study 의 manual seed (D-13 demo 살리기) 명령 + 250 study 전체 backfill 명령 명세.
- Kyle 결정 필요 사항:
  1. **v0.1.5 자유 텍스트 (StudyDescription/SeriesDescription/ProtocolName) 보존 여부** — Clean Descriptors Option 채택 여부. PHI 위험 vs buyer search 가치 trade-off.
  2. **MVP CT-only 필드 (KVP)** 를 MR-only 필드 (b0_tesla, TR/TE) 와 함께 v0.1.5 로 미루는지, MVP 에 같이 넣는지.
  3. **Thumbnail Option A (gateway ingest-time)** 채택 확정. 운영 메모리·CPU 영향 (study 당 +1.5초) 수용 가능 여부.
  4. **중간 슬라이스 알고리즘 — Kyle 안 (단순 N//2)** vs InstanceNumber 중앙값 (Orthanc 권고) — MVP 는 동일 결과지만 정렬 기준 명시 필요.
  5. **Backfill 250 study 전체 re-ingest 시점** — D-13 후 1주 내 vs D-13 직전 risk-on.
  6. **법률 자문 트리거** — Retain Device Identity + Patient Characteristics + Clean Descriptors 옵션 조합의 PIPA 합치 검토.
  7. **k-익명성 측정** — Manufacturer + Model + Hospital + Date + Age + Sex 조합의 재식별 가능성 평가, 희귀 조합 정책적 제외 기준.
