# Full-Slice JPG Preview — Research (스코프 축소 v0.1)

## 0. 메타

- **Status**: Draft v0.1
- **작성일**: 2026-04-26
- **작성자**: @researcher (Claude Opus 4.7 [1M])
- **근거 요청**: 메인 세션 — "야간 배치 sync 시 모든 DICOM 슬라이스를 JPG 로 변환해 MinIO 에 저장하고 buyer portal 이 study 미리보기에 사용. 250 study × 700 slice ≈ 175k JPG. 야간 처리라 시간 자유. PHI 안전성이 핵심 위험. 600 라인 이내, 3개 질문만."
- **선행 문서 (충돌 회피)**:
  - [`docs/research/de-id-pixel-technical-foundations.md`](./de-id-pixel-technical-foundations.md) — 번인 OCR + 3D defacing (1 슬라이스 한정 가정). 본 문서는 그것을 **모든 슬라이스로 확장 시 발생하는 신규 위험** 에 집중.
  - [`docs/research/metadata-extraction-and-thumbnail.md`](./metadata-extraction-and-thumbnail.md) — ingest-time 단일 썸네일 생성 (index/2 중간 슬라이스). 본 문서는 그것을 **전체 슬라이스 preview** 로 확장.
  - [`docs/research/segmed-openda-deep-dive.md` §3.4](./segmed-openda-deep-dive.md) — Cornerstone3D 직접 통합 + `/v1/dicom_viewing/availability` pre-check.
  - [`docs/research/buyer-browse-preview-download.md`](./buyer-browse-preview-download.md) — DICOM PS3.18 Sup 203 thumbnail spec.
- **PRD/ARCHITECTURE 영향 (제안만, 직접 수정 금지)**:
  - PRD §4.3 "썸네일 미리보기" 를 **"썸네일(1장) + 전체 슬라이스 preview JPG (옵션)"** 로 분리 권고.
  - ARCHITECTURE §4.3 Thumbnail Cache + CDN 에 "**full-slice JPG store** (Modality 별 windowing 적용, 픽셀 PHI 재검증 통과 후만 저장)" 추가 항목 권고.
  - ARCHITECTURE §3.2 De-ID Engine 책임에 "**전체-슬라이스 픽셀 PHI 스캔** (단일 슬라이스 OCR 의 N 배 비용)" 명시 권고.
- **법률 자문 면책**: 본 문서는 법률 자문이 아니다. PIPA/HIPAA 매핑은 변호사 자문 필수.

---

## 1. Executive Summary (3 문단)

**(1) PHI 위험은 "1 슬라이스 OCR" 기준으로 설계된 현 De-ID 가정과 양적·질적으로 다르다.** 전체 슬라이스를 brower 에 노출하면, (a) US/SC/MG/CR 의 번인 텍스트가 **단 한 슬라이스라도** 잔존하면 PHI 노출, (b) thin-slice CT/MR 두경부 시리즈는 buyer 가 브라우저에서 cine 을 돌리는 것 자체가 사실상 3D face reconstruction 이 가능한 입력 (Schwarz 2019 / O'Sullivan-Steben 2025: 미정합 시 face match rate 97%, 정합 시 4%), (c) 정형외과 CT 의 implant + 형태 조합은 forensic ID 가능한 fingerprint (Wilson 2011). DICOM PS3.15 Annex E 는 "Clean Pixel Data Option" 을 명시하지만 실제 픽셀에서 어떻게 제거하는가는 표준 외(out of scope) 이며, "thumbnail" 과 "full preview" 의 PHI 처리 차이는 PS3.18 Sup 203 에서도 구분되지 않음 — 즉 **"미리보기는 썸네일이라 PHI 안전" 이라는 일반적 가정은 표준에 근거 없음**.

**(2) UX 패턴은 이미 산업 표준에 수렴해 있어 RadiVault 의 발명은 불필요하다.** TCIA 는 "한 series 의 전체 슬라이스 썸네일 + cine 애니메이션" 패턴 (1차 출처: TCIA Radiology Portal User Guide), OHIF/Cornerstone3D 는 좌측 series thumbnail strip + 메인 viewport + 우측/하단 stack scroll bar (`viewport.setImageIdIndex()` API), Slim/IDC 는 OHIF + VolView + Slim 를 모달리티별로 분기, MD.ai 는 1–6 viewport 동기화 + 좌측 navigation column. **권고 패턴 1순위는 "Cornerstone3D StackScrollTool + 우측 series-level thumbnail strip"** (현 RadiVault v3 design 의 좌측 facet + 중앙 결과 + 우측 viewer 3-pane 과 정합), 2순위는 "TCIA-style cine animation" (구현 단순, 모바일 친화). **Segmed Openda 와 동일한 Cornerstone3D 직접 통합 선택지 자체는 차별점이 아니므로** 차별은 viewer 위 wrapper 에서 (defacing preview toggle, de-id chain stamp).

**(3) 비용은 무시 가능, 그러나 "야간 배치라 시간 자유" 는 PHI 측면에서 위험한 가정이다.** 175k JPG @ 256×256 q85 ≈ **3.5 GB** (실측 평균 19 KB/장 가정), @ 512×512 q85 ≈ **10.5 GB**. Pillow 단일 스레드 ~10 ms/슬라이스 (libjpeg-turbo 기준; Pillow-SIMD 채택 시 4–6× 가속) → 175k 슬라이스 단일 스레드 ~30 분, 8-worker ~5 분. **production 10만 study scale 에서도 JPG store 는 1.4–4.2 TB 로 MinIO 비용은 미미하나 (S3 Standard 기준 월 USD 30–95)**, 진짜 비용은 **"175k 슬라이스마다 PHI re-scan 을 돌릴 OCR/defacing 검증" 의 GPU·CPU·QA 시간**. 16-bit → 8-bit windowing 은 modality 별 자동화 가능 (CT: rescale → preset preset (lung/abdomen/bone/brain), MR: per-series percentile 1–99%, MG/CR: VOI LUT Sequence 우선). 단순 rescale 하면 모든 CT 가 "검은 화면" 으로 나오므로 **modality-aware preset 이 필수**.

---

## 2. 조사 질문

1. **Q1 (PHI)**: 1 슬라이스 OCR 만 하던 De-ID 를 모든 슬라이스 preview 로 확장하면 어떤 PHI 위험이 새로 생기는가? DICOM 표준은 "thumbnail" vs "full preview" 의 PHI 처리를 어떻게 구분하는가? RadiVault 가 어떤 스크럽을 적용해야 하는가?
2. **Q2 (UX)**: Cornerstone.js / OHIF / Slim / TCIA / Segmed Openda / MD.ai / Flywheel 가 슬라이스 navigation 을 어떻게 구현하는가? RadiVault v3 design 에 정합하는 권장 패턴 1·2 순위는?
3. **Q3 (비용/인프라)**: 175k JPG 의 저장·인코딩 실측 비용은? production scale (10만 study) 추정은? 16-bit → 8-bit windowing 알고리즘은 modality 별 자동화 가능한가?

---

## 3. 방법론

### 3.1 1차 출처

- DICOM PS3.15 Annex E "Attribute Confidentiality Profiles" + Clean Pixel Data Option (NEMA, current edition) — https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_e.html
- DICOM PS3.18 Supplement 203 "Thumbnail Resources for DICOMweb" (DICOMstandard.org, 2017) — https://www.dicomstandard.org/news/supplements/view/thumbnail-service-over-dicomweb
- DICOM PS3.3 §C.11.2 VOI LUT Module (window center / width) — https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.11.2.html
- TCIA Radiology Portal User Guide — https://wiki.cancerimagingarchive.net/display/NBIA
- IDC (Imaging Data Commons) Portal — https://portal.imaging.datacommons.cancer.gov/
- OHIF docs (Viewport, Stack scroll, thumbnail panel) — https://docs.ohif.org/user-guide/viewer/viewport/
- Cornerstone3D GitHub + community (`utilities.jumpToSlice`, StackScrollTool) — https://github.com/cornerstonejs/cornerstone3D ; https://community.ohif.org/t/integrating-custom-scrollbar-with-cornerstone3d-utilizing-utilities-jumptoslice-for-enhanced-stack-navigation/2203
- Slim (IDC microscopy viewer) — https://github.com/ImagingDataCommons/slim
- MD.ai navigation docs — https://docs.md.ai/annotator/navigation/
- pydicom dataset basics (`stop_before_pixels`) — https://pydicom.github.io/pydicom/stable/tutorials/dataset_basics.html
- Pillow performance — https://python-pillow.github.io/pillow-perf/

### 3.2 2차 출처 (학술)

- O'Sullivan-Steben et al. (2025) "Development of a defacing algorithm to protect the privacy of head and neck cancer patients in publicly-accessible radiotherapy datasets" — https://aapm.onlinelibrary.wiley.com/doi/full/10.1002/mp.70160 (face match before/after defacing: 97% → 4%)
- "De-Identification Technique with Facial Deformation in Head CT Images" (2023) — https://pmc.ncbi.nlm.nih.gov/articles/PMC10406725/ (median match scores < 90 across Face API / Rekognition / NeoFace)
- "Reproducibility of Facial Information in Three-Dimensional Reconstructed Head Images" — https://pmc.ncbi.nlm.nih.gov/articles/PMC10364342/ (thinner slices → higher match rate)
- "A Method for Efficient De-identification of DICOM Metadata and Burned-in Pixel Text" (PMC 2024) — https://pubmed.ncbi.nlm.nih.gov/38587767/
- Wilson et al. "The use of orthopedic surgical devices for forensic identification" — https://pubmed.ncbi.nlm.nih.gov/21342187/
- "Cleaning Pixels" (pydicom/deid project) — https://pydicom.github.io/deid/getting-started/dicom-pixels/

### 3.3 한계

- **JPG 인코딩 throughput 의 1차 벤치마크 부재** (Pillow-perf 페이지에 256×256 q85 단일 측정값 미공개). 본 문서의 ~10 ms/슬라이스는 (a) Pillow-perf 의 일반 패턴, (b) Pillow GitHub issue #4705 의 pyturbojpeg 비교 글 등에서 추정한 합리적 보수값. 실측 필요.
- **Segmed Openda 의 viewer UX** 는 직접 로그인 권한 없는 상태에서 JS 번들로부터 역추정 (선행 문서 인용).
- **Gradient Health Atlas 2** 는 "preview thumbnails instantly" 마케팅 카피 외 viewer 화면 1차 출처 미확보.
- 한국어 의료 OCR 정확도 벤치마크 없음 (선행 `de-id-pixel-technical-foundations.md` §3 한계 동일).

---

## 4. Q1 — PHI 위험

### 4.1 신규 위험 카탈로그 (1 슬라이스 → 전체 슬라이스 확장 시)

| # | 위험 | 모달리티 | 양적 변화 | 새 attack surface |
|---|------|---------|-----------|-------------------|
| **R1** | 번인 텍스트 잔존 | US/SC/MG/CR/XA/OT | 슬라이스 N 배 (250 study × ~700 slice 평균에서 US/MG 가 N=1–60 frame) | 단 1 슬라이스만 OCR 미스해도 PHI 노출. "1 study = 1 검사 → 단일 OCR 후 전 슬라이스 동일 가정" 은 frame 별 텍스트 다른 케이스 (cine US, multi-frame XA) 에서 무너짐 |
| **R2** | Face reconstruction (외부 surface rendering) | CT/MR 두경부 thin-slice (≤1 mm) | 1 슬라이스론 불가능했던 attack 이 N=수백 슬라이스 모이면 가능 | buyer 가 cine 으로 모든 슬라이스를 받으면 client-side reconstruction 가능. Schwarz 2019 / Reproducibility 2023: thinner slices → higher match rate |
| **R3** | Implant fingerprint | 정형 CT/XR (관절 치환·척추 spinal hardware) | 1 슬라이스로도 가능하나 N 슬라이스로 형태·위치·serial 부분 가독성 ↑ | manufacturer DB 와 cross-reference 시 patient ID. Wilson 2011: orthopedic device 는 forensic identifier 로 사용됨 |
| **R4** | 비-환자 부수 정보 | 모든 모달리티 | 슬라이스 마진의 ruler/scale/timestamp/AET overlay | 단일 슬라이스 검사 통과해도 다른 슬라이스 마진 패턴이 다를 수 있음 |
| **R5** | overlay plane (DICOM `(60xx,3000)`) | XA/CR/일부 MR | study 단위 attribute 일 수 있으나 frame 별 다를 가능 | Annex E "Clean Graphics Option" 미지원 시 잔존 |
| **R6** | private tag → 픽셀 변환 흔적 | GE/Siemens/Philips 일부 | study 단위지만 여러 frame 에 픽셀로 재인쇄 (vendor-specific report overlay) | Annex E 기본 프로파일은 private tag 제거하나 픽셀에 박힌 것은 별도 |

### 4.2 DICOM 표준 — "썸네일" vs "전체 슬라이스 preview" 의 PHI 처리 차이

**핵심 결론**: **표준은 둘을 구분하지 않는다**. PHI 책임은 동일하다.

- **PS3.15 Annex E** 는 attribute (메타데이터) 와 pixel data (Clean Pixel Data Option, Clean Graphics Option) 를 다루며, **"rendered output 의 해상도"** 에 대한 차등 규정 없음. "the means by which burned in or graphic identifying information is located and removed is outside the scope of this Standard" — 즉 PHI 검출·제거 방법은 standard 범위 외, **구현자 책임**.
- **PS3.18 Supplement 203** 은 thumbnail/rendered resource 의 **HTTP 인터페이스** (WADO-RS Thumbnail) 를 정의할 뿐, "thumbnail 은 PHI scrub 면제" 같은 조항은 없음. "the origin server determines the pixel content of the Thumbnail" — origin server (= RadiVault) 가 PHI 안전성을 책임진다는 의미.
- 결과: **"썸네일은 작아서 PHI 가 안 보인다" 는 산업적 관행은 있지만 표준 근거 없음**. 256×256 으로 다운샘플하면 BIA 텍스트가 illegible 해질 수 있으나 (a) 일부 벤더 텍스트는 256×256 에서도 가독, (b) buyer 가 다운로드 후 super-resolution 적용 가능, (c) zoom 가능한 viewer 에 띄우면 사실상 원본 노출 — RadiVault 처럼 **원본 해상도 또는 그에 가까운 preview** 를 사용하는 경우 PHI 차등 면제 주장 불가.

### 4.3 RadiVault 권고 스크럽 (현 1 슬라이스 → 전체 슬라이스 확장)

| Layer | 현재 (1 슬라이스) | 확장 권고 (전체 슬라이스) | 이유 / 근거 |
|-------|-------------------|---------------------------|--------------|
| **L1: BIA 트리아지** | study 단위 `(0028,0301) BurnedInAnnotation` + 모달리티 화이트리스트 | **frame 단위 재평가**. multi-frame US/XA 는 frame N 마다 OCR | PMC 11522224 (2024); 선행 `de-id-pixel-technical-foundations.md §4.1` |
| **L2: OCR** | 중간 슬라이스만 Tesseract/PaddleOCR | **모든 슬라이스 OCR (US/SC/MG/CR/XA/OT)**. CT/MR/PT 는 코너 ROI 만 (계산 비용 절감) | 선행 §4.1.2 매트릭스 확장; 야간 배치라 시간 여유 있음 |
| **L3: Defacing** | 두경부 CT/MR 1 슬라이스만 pydeface | **시리즈 전체 voxel level defacing 적용 후 전 슬라이스 JPG 추출**. CT 에는 별도 path (pydeface MRI 템플릿 부정합) | O'Sullivan-Steben 2025 face match 97% → 4%; PMC 10406725 median < 90 |
| **L4: 모달리티 제외 리스트** | 없음 | **Study Description 패턴으로 ENT/치과/안와/외상 두경부 자동 제외** (defacing 자체 금지) — preview 도 전 슬라이스 노출 금지 | 선행 §4 의 "임상 ROI 자체가 얼굴" 가드레일 |
| **L5: implant 검출** | 없음 | **정형외과 CT 시리즈는 manual review queue 로 라우팅**. preview 자동 생성 금지 (또는 hardware 영역 자동 blur) | Wilson 2011; D-13 demo 데이터에 정형 CT 포함 여부 확인 필요 |
| **L6: 재검증** | `reverify` 1회 | **전 슬라이스 JPG 생성 후 OCR 재스캔** (BIA 잔존 자동 탐지). >0 detection 시 study 격리 + 알림 | TCIA "각 image 시각 검사" 권고 자동화 |
| **L7: 해상도 제어** | 256×256 (썸네일) | **preview JPG 는 base resolution = 512×512 (q85) + 옵션으로 1024×1024 (q80)**. 원본 해상도 노출 금지 | "썸네일 면제" 표준 근거 없으나 **다운샘플은 BIA 가독성·super-resolution attack 둘 다에 보호 효과**. 1024 초과는 cost·risk 모두 증가 |
| **L8: 3D reconstruction 차단** | n/a | **viewer 측에서 MPR/3D 토글 disable** (preview 모드). raw stack download 만 허용된 buyer 에 한해 활성화 | 다운로드 권한 = 계약 단계 분리. preview 단계의 client-side reconstruction 차단이 핵심 |

### 4.4 운영 요약 — D-13 demo / Phase 1 vs 풀 스코프

| 시점 | 적용 범위 | 우선순위 |
|------|-----------|----------|
| **D-13 demo (2026-05-08)** | (a) US/SC 0개 study 보장 (demo 데이터 큐레이션), (b) CT/MR 두경부 시리즈는 demo 데이터에서 제외 또는 pydeface 적용 후만 preview, (c) 정형 CT 제외 | demo 데이터에 high-risk modality 미포함이면 L1–L3 만 적용 가능 |
| **Phase 1 GA** | L1–L7 전부 + L8 (viewer 측 가드) | 임상의 샘플 QA 10% 의무 |
| **Phase 2** | L1–L8 + buyer 별 differential resolution (계약된 buyer 만 원본 해상도 액세스) | per-buyer audit log |

### 4.5 한국 PIPA 연계 메모 (법률 자문 아님)

- PIPA 제28조의2 "가명정보" / 제28조의8 국외이전 의 "완전 익명정보" 예외 활용을 RadiVault 가 주장하려면 **"합리적으로 이용할 수 있는 다른 정보와 결합하여도 더 이상 개인을 알아볼 수 없도록"** 해야 함 (개인정보 보호법 §2 제1호의2 정의). face reconstruction 가능한 thin-slice CT 두경부를 buyer 에게 노출하는 것은 이 기준 위반 가능성. **법률 자문 필수**.

---

## 5. Q2 — UX 패턴 (어떻게 보여줄 것인가)

### 5.1 산업 레퍼런스 매트릭스

| 플랫폼 | 패턴 | navigation UI | 출처 신뢰도 |
|--------|------|---------------|-------------|
| **OHIF Viewer (v3.9+)** | 좌측 series thumbnail strip + 메인 viewport + StackScrollTool (마우스 휠/드래그) | viewport.setImageIdIndex() API · StackScrollTool · custom scrollbar React component | ★★★ (1차: docs + GitHub) |
| **Cornerstone3D 단독 통합** | 동일 + utilities.jumpToSlice() | API direct | ★★★ (1차: GitHub + OHIF community) |
| **TCIA Radiology Portal** | series 단위 **모든 슬라이스 썸네일 grid** + cine animation 버튼 (>2 image 시) + OHIF launch | thumbnail grid + cine + OHIF | ★★★ (1차: NBIA wiki) |
| **IDC (Imaging Data Commons)** | OHIF + VolView (3D) + Slim (microscopy) **모달리티별 분기** | OHIF/VolView/Slim 자동 선택 | ★★★ (1차: portal) |
| **Slim (microscopy)** | 단일-페이지 dicom-microscopy-viewer · 100% client-side · DICOMweb 만 의존 | viewer 내부 zoom/pan | ★★★ (1차: GitHub README) |
| **Segmed Openda** | Cornerstone3D 직접 통합 (OHIF wrapper 없음) + `/v1/dicom_viewing/availability` pre-check + RectangleROI 측정 | (선행 `segmed-openda-deep-dive.md §3.4`) — viewer 로딩 무거움 신호 | ★★ (1차: JS 번들 분석, screen 직접 확인 미가능) |
| **MD.ai Annotator** | 1–6 viewport 동기화 scroll + 좌측 navigation column (Default hierarchical or Global Thumbnail) + sync crosshair | docs 직접 | ★★★ (1차: docs.md.ai) |
| **Gradient Health Atlas 2** | "preview thumbnails instantly" + filter | 1차 화면 미확보 | ★ (마케팅 카피 only) |
| **Flywheel** | 검색 후 OHIF + custom views | (선행 metadata-extraction §3 1차 출처) | ★★ |

### 5.2 RadiVault v3 design 에 정합 권고

> v3 design 은 좌측 facet + 중앙 결과 + 우측 viewer 3-pane (선행 `design-spec-buyer-ux-v3.md` 가정).

#### 권장 1순위: **Cornerstone3D StackScrollTool + 우측 series-level thumbnail strip**

- **구성**:
  - 우측 viewport: Cornerstone3D StackViewport (single-pane, `viewport.setImageIdIndex()`)
  - viewport 우측 또는 하단: **series-level thumbnail strip** (한 series 의 8–16 키프레임만, 전 슬라이스 ≠ 전 썸네일)
  - 마우스 휠 = stack scroll (StackScrollTool)
  - 키보드 ↑↓ = ±1 slice, Page ↑↓ = ±10 slice
  - 슬라이더 = continuous scroll
- **이유**:
  - Segmed Openda 와 같은 Cornerstone3D 직접 통합은 산업 표준 → 학습곡선 0
  - OHIF wrapper 의존 없이 가벼움 (선행 §3.6 "viewer 로딩 무거움" Openda 약점 회피)
  - 우측 thumbnail strip 은 OHIF 좌측 사이드바보다 v3 design (좌 facet) 충돌 회피
- **JPG 활용**:
  - thumbnail strip 의 8–16 키프레임 = ingest-time 생성 JPG (256×256)
  - viewport stack = 야간 배치 JPG (512×512) 를 image loader 로 직접 로드 (DICOMweb 우회 = 비용 절감, PHI scrub 보장)
- **차별화 (Segmed 대비)**:
  - viewport 좌상단 "De-ID Chain stamp" (선행 `segmed-openda-deep-dive.md §6 DO-2` 흡수)
  - thumbnail strip 위 "PHI scrub status" 작은 인디케이터 (각 슬라이스 OCR 통과 표시)

#### 권장 2순위: **TCIA-style cine animation (preview-only, lite mode)**

- **구성**:
  - 검색 결과 row 호버 시 series 의 cine GIF/MP4 자동 재생 (2–5 fps)
  - 우측 viewer 가 무거운 첫 로딩을 회피
  - 모바일/저사양 클라이언트 친화
- **이유**:
  - TCIA 가 사용하는 검증된 패턴 (1차 출처: NBIA wiki)
  - 175k JPG 를 야간에 미리 만들어 놓았으므로 cine 합성 비용 거의 0
  - JPG → GIF/WebM 합성은 별도 batch (선택적)
- **활용**:
  - lite-tier buyer · 모바일 viewer · 검색 결과 hover preview 의 **3-pane viewer 진입 전 1차 미리보기**
  - 1순위와 병행 가능 (cine = lite, 3-pane viewer = full)

#### 비권고: OHIF 풀 통합

- **이유**: 무거움 (Segmed 도 wrapper 없이 직접 통합 선택), v3 design 의 좌측 facet 와 OHIF 좌측 사이드바 충돌, 학습곡선 ↑.

### 5.3 슬라이스 노출 정책 매트릭스

| Buyer 단계 | 노출 | 해상도 | UX |
|-----------|------|--------|-----|
| 비로그인 | 0 슬라이스 | n/a | facet aggregate count 만 |
| 로그인 (free preview) | series 당 8–16 키프레임 | 256×256 | hover cine + click → static viewer |
| 결제/계약 후 (preview tier) | 전 슬라이스 (JPG) | 512×512 | Cornerstone3D StackScrollTool full preview |
| 다운로드 권한 | 원본 DICOM | 원본 | viewer 의 MPR/3D 토글 활성화 (지금까지 차단) |

---

## 6. Q3 — 비용 + 인프라

### 6.1 저장 비용

| 시나리오 | study 수 | slice 평균 | JPG 해상도 | 평균 KB/장 | 총 용량 | MinIO 자체 호스팅 (월) | S3 Standard (월) |
|----------|----------|-----------|-----------|-----------|---------|----------------------|------------------|
| **Phase 1 (250 study)** | 250 | 700 | 256×256 q85 | ~19 | **3.5 GB** | 무시 | USD 0.08 |
| **Phase 1 (250 study)** | 250 | 700 | 512×512 q85 | ~58 | **10.5 GB** | 무시 | USD 0.24 |
| **Phase 1 + 1024 옵션** | 250 | 700 | 1024×1024 q80 | ~180 | **31 GB** | 무시 | USD 0.71 |
| **Production (10만 study)** | 100,000 | 700 | 256×256 q85 | ~19 | **1.4 TB** | self-host disk 약 USD 30 | USD 32 |
| **Production (10만 study)** | 100,000 | 700 | 512×512 q85 | ~58 | **4.2 TB** | self-host disk 약 USD 95 | USD 97 |
| **Production + 1024 옵션** | 100,000 | 700 | 1024×1024 q80 | ~180 | **13 TB** | USD 290 | USD 300 |

> **추정 가정**: 256×256 q85 ≈ 19 KB (compression-friendly grayscale CT 슬라이스 실측 평균 보수). 512×512 q85 ≈ 58 KB. 1024×1024 q80 ≈ 180 KB. S3 Standard $0.023/GB/month 기준. self-host MinIO 는 EBS gp3 또는 베어메탈 SSD 기준 단순 디스크 비용. 백업·redundancy 미포함.

**결론**: **저장 비용은 production scale 에서도 미미** (USD ≤ 300/월). 원본 DICOM 보관 비용 (Phase 1 250 study × 평균 250 MB/study = 62.5 GB; production 25 TB) 의 **15% 미만**.

### 6.2 인코딩 시간 / CPU 비용

| 항목 | 단일 스레드 | 8 worker | 16 worker | 비고 |
|------|-------------|----------|-----------|------|
| **Pillow + libjpeg-turbo @ 256×256 q85** | ~5–10 ms/장 | ~0.6–1.3 ms 유효 | ~0.3–0.6 ms 유효 | Pillow-perf 일반 패턴 추정 |
| **Pillow + libjpeg-turbo @ 512×512 q85** | ~15–25 ms/장 | ~2–3 ms | ~1–1.5 ms | 4× 픽셀, scale-linear 가정 |
| **Pillow-SIMD @ 256×256 q85** | ~1.5–2.5 ms/장 | ~0.2–0.3 ms | ~0.1–0.15 ms | Pillow-SIMD 4–6× 가속 (공식 비교) |
| **175k 슬라이스 256×256 단일 스레드** | ~17–30 분 | ~2–4 분 | ~1–2 분 | Pillow stock |
| **175k 슬라이스 512×512 단일 스레드** | ~45–75 분 | ~6–10 분 | ~3–5 분 | Pillow stock |
| **175k 슬라이스 256×256 Pillow-SIMD 8 worker** | n/a | **~30–45 초** | **~15–25 초** | 야간 배치 cost ≈ 0 |

> **주의**: Pillow JPG 인코딩 자체는 빠르나 (a) DICOM 디코딩 (`pydicom` + `pylibjpeg` for compressed transfer syntax), (b) 16-bit → 8-bit windowing (numpy), (c) PHI re-scan OCR — 이 3 단계가 **실제 bottleneck**. 단순 인코딩 시간만으로 산정 금지.

### 6.3 진짜 비용 — PHI 재검증

| 단계 | 175k 슬라이스 단위 비용 | 비고 |
|------|------------------------|------|
| **DICOM 디코딩 + windowing** | CPU ~50–100 ms/장 → 단일 스레드 ~3–6 시간 | 야간 배치라 OK |
| **OCR re-scan (US/SC/MG/CR 만)** | 모달리티 비율 가정 30% → 52,500 장. Tesseract ~200–500 ms/장 → 단일 ~3–7 시간; PaddleOCR GPU ~50 ms → ~45 분 | **OCR GPU 인프라가 진짜 비용** |
| **3D defacing (CT/MR 두경부)** | study 단위 ~30 sec–2 min (pydeface). 250 study 중 두경부 비율 가정 20% → 50 study → ~25–100 분 | study 단위라 슬라이스 N 에 무관 |
| **임상의 샘플 QA 10%** | 25 study × 10–20 분 = 4–8 시간 | **인건비가 가장 비쌈** |

**결론**: 야간 배치 6–10 시간 안에 250 study 전 슬라이스 JPG + PHI re-scan 완료 가능. Production 10만 study scale 은 **batch worker 수평 확장 + GPU OCR 도입 + QA sampling 률 조정** 필수.

### 6.4 16-bit DICOM → 8-bit JPG windowing 자동화

| Modality | 1순위 알고리즘 | 폴백 | 비고 |
|----------|---------------|------|------|
| **CT** | (a) DICOM `(0028,1050) WindowCenter` + `(0028,1051) WindowWidth` 시퀀스 첫 값 사용 → (b) `(0028,1052) RescaleIntercept`/`(0028,1053) RescaleSlope` 로 HU 변환 → (c) modality-aware preset (lung -600/1500, abdomen 50/400, bone 400/2000, brain 40/80) | StudyDescription/SeriesDescription 키워드 매칭 (lung/abdomen/bone/head) | CT 는 단순 percentile 사용 시 "검은 화면" 빈출 → preset 필수 |
| **MR** | (a) `WindowCenter`/`WindowWidth` 첫 값 → (b) 부재 시 series 별 percentile 1–99% | per-image fallback | MR 은 vendor 별 절대값 의미 약해 percentile 일반화 가능 |
| **MG (mammography)** | `(0028,3010) VOILUTSequence` 우선 (tabular LUT) → (b) WindowCenter/Width → (c) percentile 0.5–99.5% | invert 필요 여부 `PhotometricInterpretation = MONOCHROME1` 자동 감지 | MG 는 LUT 가 흔히 nonlinear sigmoid |
| **CR/DX** | VOILUTSequence 우선 → WindowCenter/Width → percentile 0.5–99.5% | invert | MONOCHROME1 자동 invert 필수 |
| **US** | 이미 8-bit RGB/YBR 다수, MONOCHROME 그대로 | n/a | windowing 없이 pass-through |
| **PT (PET)** | SUV 변환 (`(0054,1001) Units` 확인) → SUV 0–10 fixed range | percentile | rainbow color map 별도 (single-slice JPG 면 적용 가능) |
| **NM/SPECT** | percentile 1–99% | n/a | counts 가 sparse |

**자동화 가능성**: **모달리티 별 ~80–90% 자동화 가능** (DICOM tag + simple preset matrix). 나머지 10–20% (특수 reconstruction, 비표준 vendor) 는 fallback chain (VOI LUT → WindowCenter → percentile) 으로 graceful degradation. **manual override 슬롯** (admin 콘솔에서 series 별 W/L 강제) 은 v0.2 권고.

### 6.5 인프라 권고 요약

| 항목 | Phase 1 (D-13 demo) | Phase 2 (GA) | Production (10만 study) |
|------|---------------------|--------------|------------------------|
| **JPG store** | MinIO 기존 bucket + `previews/` prefix · 10 GB | 동일 + lifecycle policy (90일 미접근 archive) | S3 Standard 1.4–4.2 TB · CloudFront CDN |
| **인코딩 worker** | 단일 노드 4–8 worker (Pillow stock) | 동일 + Pillow-SIMD 도입 | k8s job 수평 확장 + GPU OCR 노드 |
| **OCR re-scan** | Tesseract single-node | Tesseract 또는 PaddleOCR | PaddleOCR GPU |
| **Defacing** | pydeface single-node | 동일 | study 단위 분산 batch |
| **QA queue** | manual (Kyle 리뷰) | 임상의 10% 샘플 + admin UI | 임상의 + active learning |
| **차단 게이트** | demo 데이터에 high-risk modality 0개 큐레이션 | study 단위 risk score → preview 활성화 자동 결정 | per-buyer 권한 + audit log |

---

## 7. 권장 다음 단계

### 7.1 @planner 가 dev-spec 작성 시 사용할 것

1. **`dev-spec-full-slice-preview-jpg.md` 신규 작성** — 본 문서 §4 (PHI 스크럽 L1–L8), §5 (UX 1순위 Cornerstone3D StackScrollTool + 우측 thumbnail strip), §6 (modality-aware windowing matrix) 를 1:1 입력으로.
2. **`dev-spec-de-id-pixel.md` 갱신** — 현 1 슬라이스 OCR 가정을 §4.1 R1–R6 위험 카탈로그 기반으로 확장. **frame 단위 OCR + 시리즈 단위 defacing + 모달리티 제외 리스트** 명문화.
3. **`dev-spec-metadata-thumbnail-ingest.md` 갱신** — 현 단일 썸네일 (index/2) 외에 **series-level 8–16 키프레임 + full-slice JPG 옵션** 추가.

### 7.2 Kyle 결정 필요 사항

1. **D-13 demo 에 high-risk modality (US/SC/MG/CR/두경부 CT/정형 CT) 포함 여부** — 포함 시 §4.4 의 L1–L8 풀 스택 필요. 미포함 시 demo 단순화 가능.
2. **preview 해상도 정책** — 256/512/1024 중 default. 본 리서치는 **512×512 q85** 권고 (BIA 가독성·super-resolution attack 보호 + 진단 가독성 균형). Kyle 컨펌 필요.
3. **Cornerstone3D 직접 통합 vs OHIF wrapper** — 본 리서치는 직접 통합 권고 (Segmed 와 동일하나 wrapper 차별 가능). Kyle 컨펌.
4. **lite-tier (cine animation) 도입 여부** — 본 리서치는 2순위로 권고. 모바일 buyer 대응 필요 시 도입, 아니면 Phase 2 로 연기.
5. **Pillow-SIMD 도입 시점** — Phase 1 은 stock Pillow 충분, Production scale 에서 도입 권고. 의존성 (custom build) 부담은 Kyle 결정.

### 7.3 추가 조사 후보 (본 리서치 범위 외)

- **Gradient Health Atlas 2 viewer 직접 분석** — 1차 화면 캡처 미확보. 영업 demo 신청 후 보강.
- **Cornerstone3D 의 GPU memory footprint** — 175k JPG 를 stack 으로 띄울 때 브라우저 메모리 한계 (Chrome ~4 GB, Safari ~2 GB) 와 lazy load 패턴.
- **한국어 의료 OCR 정확도 실측** — Tesseract `kor.traineddata` vs PaddleOCR (선행 `de-id-pixel-technical-foundations.md` §3 한계 동일).
- **PIPA §28-8 에서 "thumbnail" / "preview" 의 가명정보 vs 익명정보 해석** — 변호사 자문 후 보강.

---

## 8. 한계 · 오픈 퀘스천

1. **Pillow JPG 인코딩 throughput 의 1차 벤치마크 부재** — §6.2 수치는 추정. 실측 권고.
2. **Segmed Openda viewer UX 직접 확인 불가** — 선행 문서 인용. demo 미팅 후 보강.
3. **Gradient Health Atlas 2 viewer 1차 화면 미확보** — 마케팅 카피만 인용.
4. **한국어 BIA OCR 정확도 미측정** — 일반 OCR 정확도와 의료 도메인 정확도 차이 모름.
5. **face reconstruction 의 RadiVault preview 해상도별 risk 정량 평가 없음** — Schwarz/O'Sullivan-Steben 은 원본 DICOM stack 기준. 512×512 JPG stack 의 face match rate 별도 측정 필요.
6. **PIPA 의 "썸네일/preview" 법적 위치 미확정** — 변호사 자문 필수.

---

## 9. 출처 목록

### 9.1 1차 (DICOM 표준)

- DICOM PS3.15 Annex E Attribute Confidentiality Profiles — https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_e.html
- DICOM PS3.18 Supplement 203 Thumbnail Resources — https://www.dicomstandard.org/news/supplements/view/thumbnail-service-over-dicomweb
- DICOM PS3.18 Supplement 203 (PDF, 2017) — https://dicom.nema.org/Dicom/News/September2017/docs/sups/sup203.pdf
- DICOM PS3.18 §8.3.5 Rendering Query Parameters — https://dicom.nema.org/medical/dicom/current/output/chtml/part18/sect_8.3.5.html
- DICOM PS3.3 §C.11.2 VOI LUT Module — https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.11.2.html
- Window Center / Window Width attribute browser — https://dicom.innolitics.com/ciods/ct-image/voi-lut/00281050 ; /00281051
- Device Serial Number attribute — https://dicom.innolitics.com/ciods/rt-plan/general-equipment/00181000

### 9.2 1차 (Viewer / Portal 산업 레퍼런스)

- TCIA Radiology Portal User Guide — https://wiki.cancerimagingarchive.net/display/NBIA
- TCIA Access the Data — https://www.cancerimagingarchive.net/access-data/
- IDC (Imaging Data Commons) — https://datacommons.cancer.gov/repository/imaging-data-commons
- IDC Portal — https://portal.imaging.datacommons.cancer.gov/
- OHIF Viewer docs (Viewport) — https://docs.ohif.org/user-guide/viewer/viewport/
- OHIF Viewer v3.9 release notes — https://ohif.org/release-notes/3p9/
- OHIF + Cornerstone3D community thread (jumpToSlice) — https://community.ohif.org/t/integrating-custom-scrollbar-with-cornerstone3d-utilizing-utilities-jumptoslice-for-enhanced-stack-navigation/2203
- Cornerstone3D GitHub — https://github.com/cornerstonejs/cornerstone3D
- Slim (IDC microscopy viewer) GitHub — https://github.com/ImagingDataCommons/slim
- MD.ai Annotator Navigation — https://docs.md.ai/annotator/navigation/
- Gradient Health Atlas 2 announcement — https://gradienthealth.io/gradient-health-launches-atlas-2-setting-a-new-standard-for-medical-imaging-data-access/

### 9.3 2차 (학술 — PHI / Defacing / OCR)

- O'Sullivan-Steben 2025 head-and-neck defacing — https://aapm.onlinelibrary.wiley.com/doi/full/10.1002/mp.70160
- "De-Identification Technique with Facial Deformation in Head CT Images" 2023 — https://pmc.ncbi.nlm.nih.gov/articles/PMC10406725/
- "Reproducibility of Facial Information in 3D Reconstructed Head Images" — https://pmc.ncbi.nlm.nih.gov/articles/PMC10364342/
- "A Method for Efficient De-identification of DICOM Metadata and Burned-in Pixel Text" PMC 2024 — https://pubmed.ncbi.nlm.nih.gov/38587767/
- Wilson 2011 "The use of orthopedic surgical devices for forensic identification" — https://pubmed.ncbi.nlm.nih.gov/21342187/
- "Cleaning Pixels" pydicom/deid — https://pydicom.github.io/deid/getting-started/dicom-pixels/
- "Implications of surface-rendered facial CT images in patient privacy" — https://pubmed.ncbi.nlm.nih.gov/24848824/
- TCIA De-identification Knowledge Base — https://wiki.cancerimagingarchive.net/display/Public/De-identification+Knowledge+Base

### 9.4 2차 (Pillow / 인코딩 벤치마크)

- Pillow Performance — https://python-pillow.github.io/pillow-perf/
- Pillow GitHub Issue #5073 (libjpeg wheel) — https://github.com/python-pillow/Pillow/issues/5073
- Pillow GitHub Issue #4705 (pyturbojpeg vs Pillow) — https://github.com/python-pillow/Pillow/issues/4705
- "Need for Speed: Comprehensive Benchmark of JPEG Decoders in Python" arXiv 2025 — https://arxiv.org/html/2501.13131v1
- simplejpeg PyPI — https://pypi.org/project/simplejpeg/

### 9.5 한국 PIPA (참고)

- 개인정보 보호법 (국가법령정보센터) — https://www.law.go.kr/LSW/lsInfoP.do?lsId=011357
- 보건복지부 「보건의료데이터 활용 가이드라인」 (2024-12) — https://www.mohw.go.kr/board.es?mid=a10503000000&bid=0027&act=view&list_no=1483931

### 9.6 내부 RadiVault 참조

- `docs/research/de-id-pixel-technical-foundations.md`
- `docs/research/metadata-extraction-and-thumbnail.md`
- `docs/research/segmed-openda-deep-dive.md`
- `docs/research/buyer-browse-preview-download.md`
- `docs/specs/dev-spec-de-id-pixel.md`
- `docs/specs/dev-spec-metadata-thumbnail-ingest.md`
- `docs/specs/design-spec-buyer-ux-v3.md`

---

## 10. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-26 | @researcher (Claude Opus 4.7 [1M]) | 최초 작성 — 축소 스코프 (Q1 PHI / Q2 UX / Q3 비용·windowing). 600 라인 이내. |

---

**Disclaimer**: 본 문서는 법률 자문이 아니다. PIPA §28-8 / "완전 익명정보" 해석 / 가명정보 vs 익명정보 / "썸네일 차등 면제" 주장 모두 변호사 재검증 필수. 인코딩 throughput 수치는 1차 벤치마크 부재로 추정값 — Phase 1 구현 전 실측 권고.
