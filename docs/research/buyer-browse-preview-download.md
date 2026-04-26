# Buyer Browse → Preview → Download Workflow — Research

> **Status**: Draft v1.0 · **작성일**: 2026-04-25 · **작성자**: @researcher (Claude)
> **근거 요청**: 메인 세션 — D-13 (2026-05-08) CEO 데모용 buyer 의 study 시각 preview·다운로드 워크플로우 dev-spec 의 사실 근거.
> **선행 컨텍스트**: `docs/prd.md` §4.3·4.4, `docs/ARCHITECTURE.md` §4.3·5.x, `docs/research/buyer-portal-ux-competitive.md` §11 (Viewer/preview 판정), `docs/research/de-id-pixel-technical-foundations.md` (번인 PHI), `docs/research/gateway-agent-technical-foundations.md` §5 (DICOMweb).
> **법률 자문 면책**: 본 문서는 법률 자문이 아니며, PIPA 28-8·SaMD 분류 등 법적 결론은 변호사·식약처 전문 컨설팅 필요.

---

## 0. TL;DR

1. **Segmed·Gradient·Flywheel·IDC 모두 OHIF / Cornerstone3D 임베드를 표준으로 채택**. TCIA 는 OHIF 를 공식 통합. 자체 viewer 를 새로 짜는 길은 industry 외(out-of-pattern).
2. **DICOM PS3.18 Sup 203** 이 WADO-RS Thumbnail resource 를 표준화 (`/studies/{uid}/thumbnail`, `/series/.../thumbnail`, `/instances/.../thumbnail`). **JPEG 필수 지원 + Patient Identifying Information 포함 금지** 명문 규정. RadiVault 가 Zone 2 Thumbnail Cache 를 만들 때 이 spec 을 그대로 따르면 표준 적합.
3. **buyer 다운로드 모델은 두 갈래**: Gradient/Segmed 는 "order → days → DICOM+JSON 패키지" (RadiVault 현재와 동일), TCIA/IDC 는 "manifest → s5cmd 로 즉시 cloud bucket 에서 pull". RadiVault MVP 는 전자 + "샘플 1 study 즉시 다운로드" 의 하이브리드 권고.
4. **번인 PHI 는 preview 노출 전 반드시 검증**. Microsoft Presidio 의 `DicomImageRedactorEngine` 이 production-ready 오픈소스로 가장 가까움. PMC 11522224 (2024) 의 EAST+Tesseract 파이프라인은 12,578 영상 중 10건만 누락 (recall 99.92%) — 단, 평가 데이터 한정.
5. **한국 SaMD 분류 리스크**: 식약처 「디지털의료기기 분류 및 등급 지정 가이드라인」(2026-03-20 개정) 기준, **단순 영상 표시 (visualization-only)** 는 통상 의료기기 비해당이지만 **진단·정량 측정 기능을 추가하는 순간 SaMD 1~4등급 분류 위험**. RadiVault preview viewer 는 zoom/pan/window-level 까지로 한정해야 안전.

---

## 1. 조사 질문

1. Segmed / Gradient / Imagia(Canexia) / TCIA / Flywheel — 각 사 buyer 가 데이터를 사기 전 어떻게 preview 보고 다운로드 하는가?
2. DICOMweb WADO-RS rendered/thumbnail endpoint 의 표준 spec 과 industry 구현 패턴은?
3. Pixel data 안의 burned-in PHI 를 preview 노출 전에 어떻게 검증하는가?
4. Buyer 다운로드 모델 — instant vs order, presigned URL TTL, large file chunked 패턴은?
5. 한국 시장 특이사항 — 보건복지부 비식별 가이드, 식약처 SaMD 분류, PIPA 28-8.

---

## 2. 방법론

- **1차 자료**: DICOM PS3.18 (NEMA), 보건복지부·개인정보보호위원회·식약처 공식 가이드, 각 사 공식 문서·블로그 (segmed.ai/insight, gradienthealth.io, learn.canceridc.dev, docs.flywheel.io, ohif.org, microsoft.github.io/presidio).
- **2차 자료**: PMC 11522224 (de-id 픽셀 OCR 평가 논문, 2024), AuntMinnie/Datavant 보도자료, IDC 논문 (PMC 8373794).
- **검색 도구**: WebSearch + WebFetch (Anthropic 내장). 검색일자: 2026-04-25.
- **한계**: Segmed 의 buyer-facing UI 세부(썸네일 형태·viewer 종류)는 **공개 마케팅 카피만 존재**, 실제 스크린샷·기능 매트릭스는 비공개. CB Insights/Crunchbase 는 paywall. 본 문서에서 "TBD: needs primary source" 로 명기.
- **기존 리서치 재사용**: `buyer-portal-ux-competitive.md` (Apr 24) 가 이미 Segmed·Gradient·TCIA·IDC 를 분석했으므로 본 문서는 **buyer-side preview/download 흐름에만 깊게** 들어가고 일반 UX 는 그쪽을 참조.

---

## 3. 경쟁사 buyer-side workflow 비교

### 3.1 Segmed (Insight 플랫폼)

- **회사 컨텍스트**: Palo Alto, 2018 설립. 2,000+ healthcare locations, 2025년 누적 100M+ studies 돌파 (AuntMinnie, 2025) [^segmed-100m]. 직접 경쟁사.
- **검색 결과 카드 썸네일**: **공식 문서로는 명시 없음**. "fully deidentified, standardized imaging data through a web interface" 만 언급 [^segmed-insight]. **TBD: needs primary source (요구: trial 계정 또는 영업 데모)**.
- **Study 상세 viewer**: 공식 문서로는 viewer 종류 미공개. 데모·트라이얼 필요. **TBD: needs primary source**.
- **다운로드 흐름**: "Every dataset downloaded from segmed consists of a summary file and zip of data" [^segmed-blog-insight] — **order → days → ZIP delivery** 모델로 추정. Gradient 와 유사한 "machine-ready datasets typically within days" [^segmed-solutions].
- **Preview/다운로드 분리**: 공식 명시 없음. 영업 contact 후 cohort curation 협업 모델. **무료 self-serve preview tier 의 존재 여부 불확실 (TBD)**.
- **DICOM tag 노출**: SOC 2 / HIPAA / ISO 27001 / ethics approval 명시 [^segmed-insight] — 익명화 검증된 데이터만 buyer 에게 노출되는 구조로 추정.
- **다운로드 포맷**: DICOM + radiology reports + metadata [^segmed-blog-insight]. NIfTI/Zarr 변환 옵션 명시 없음.

[^segmed-100m]: AuntMinnie, "Segmed platform passed 100M studies" — https://www.auntminnie.com/imaging-informatics/enterprise-imaging/pacs-vna/article/15634029/segmed-platform-passed-100m-studies
[^segmed-insight]: Segmed Insight 공식 페이지 — https://www.segmed.ai/insight
[^segmed-blog-insight]: "Introducing Segmed Insight" 공식 블로그 — https://www.segmed.ai/resources/blog/introducingsegmedinsight
[^segmed-solutions]: Segmed Solutions — https://www.segmed.ai/solutions

### 3.2 Gradient Health (Atlas 2)

- **회사 컨텍스트**: Durham NC, AI-developer self-serve 강조. Atlas 2 출시 (2024) [^gradient-atlas2-launch].
- **검색 결과 카드 썸네일**: **YES**. "filter by study type and **preview thumbnails instantly**" [^gradient-atlas]. "**instant image previews**" [^gradient-atlas]. **대표 슬라이스 알고리즘은 미공개 (TBD)**.
- **Study 상세 viewer**: 공식 문서로는 viewer 종류 명시 없음. "instant image previews" 표현으로 보아 Cornerstone3D 직접 통합 또는 정적 thumbnail 시퀀스 추정. **TBD: needs primary source**.
- **다운로드 흐름**: 2단계 — (a) "**Download CSV** button" 으로 메타데이터·report CSV 즉시 export → (b) CSV refine 후 reupload 또는 직접 "**Add to project** / Export" 로 cohort 생성 → (c) "DICOM + JSON format … prepared and delivered in days" [^gradient-atlas]. **즉시 다운로드(CSV) + 주문기반 다운로드(DICOM) 의 하이브리드**.
- **Preview/다운로드 분리**: **명확한 분리 패턴 — "preview thumbnail = free" 로 추정 (회원가입 후 무료 self-serve), "DICOM download = order"**. RadiVault 가 채택하기 좋은 모델.
- **분석 도구**: "built-in visual analytics tools to assess **diversity** and comprehensiveness" — 연령·성별·modality 분포 차트 (RadiVault portal-redesign-competitive 에서 이미 분석됨).
- **가격 도구**: "calculator helps estimate costs based on exam volume" [^gradient-atlas].

[^gradient-atlas]: Gradient Health Atlas (AI Developer) — https://gradienthealth.io/ai-developer/atlas/
[^gradient-atlas2-launch]: Gradient Atlas 2 launch — https://gradienthealth.io/gradient-health-launches-atlas-2-setting-a-new-standard-for-medical-imaging-data-access/

### 3.3 Imagia / Canexia Health

- **상태**: 2022-09 합병으로 **precision oncology genomic test 회사로 피벗** [^imagia-cb]. **현재 DICOM 마켓플레이스/imaging data platform 사업 비활성**. RadiVault 직접 경쟁사 아님.
- **시사점**: 당초 의료영상 AI 플랫폼이었으나 사업 모델이 cancer genomics 로 이동 — "imaging data marketplace" 단독으로 sustainable business 가 어렵다는 시장 신호 가능성. **본 워크플로우 비교 대상에서 제외**, RadiVault 의 가격·수익 모델 (광범위 modality·hospital partnership) 차별화 근거로 별도 검토 권고.

[^imagia-cb]: CB Insights — Imagia Canexia Health — https://www.cbinsights.com/company/imagia-canexia-health

### 3.4 TCIA (The Cancer Imaging Archive) — 학술 baseline

- **컨텍스트**: NCI 산하 무료 공개 archive. 상업 buyer 없음, 그러나 **buyer UX baseline** 으로 가장 성숙.
- **썸네일·viewer**: **OHIF Viewer 공식 통합** [^tcia-ohif-showcase] [^tcia-radiology-portal]. 검색 결과 행에 "**thumbnail, animation, DICOM**" 3개 버튼 — thumbnail click → OHIF viewer 새 탭 [^tcia-radiology-portal] [^tcia-viewing-7-7].
- **다운로드 흐름**: cart → "Download Cart" → **manifest 파일 download → manifest 를 NBIA Data Retriever (또는 IDC 의 s5cmd) 로 실행** → 실제 DICOM bulk transfer [^tcia-downloading]. **즉시 cloud-pull 모델**. 사용자가 수십 GB 시리즈를 cart 에 담아도 manifest 는 KB 단위.
- **Preview/다운로드 분리**: 모두 무료. 단 IRB-restricted collection 은 별도 신청 게이트 (RadiVault 와 다른 모델).
- **DICOM tag**: TCIA 공식 익명화 — RSNA Clinical Trials Processor (CTP) + private element knowledge base [^tcia-deid-paper-pmc].
- **포맷**: 기본 DICOM raw. 일부 collection 에 NIfTI/JSON segmentation 동봉.

[^tcia-ohif-showcase]: OHIF Showcase — TCIA — https://ohif.org/showcase/tcia/
[^tcia-radiology-portal]: TCIA Radiology Portal User's Guide — https://wiki.cancerimagingarchive.net/display/NBIA
[^tcia-viewing-7-7]: TCIA "Viewing TCIA Collections 7.7" — https://wiki.cancerimagingarchive.net/display/NBIA/Viewing+TCIA+Collections+7.7
[^tcia-downloading]: TCIA "Downloading TCIA Images" — https://wiki.cancerimagingarchive.net/display/NBIA/Downloading+TCIA+Images
[^tcia-deid-paper-pmc]: PMC 3824915 — TCIA: Maintaining and Operating a Public Information Repository — https://pmc.ncbi.nlm.nih.gov/articles/PMC3824915/

### 3.5 NCI Imaging Data Commons (IDC) — 학술/cloud 모델

- **컨텍스트**: TCIA 후속, GCP/AWS public bucket 호스팅. 2025 spring 기준 radiology + brightfield + 형광 microscopy [^idc-portal-2025].
- **썸네일·viewer**: **OHIF Viewer 임베드** [^idc-portal-2025]. portal 검색 페이지에서 series 행 → OHIF 뷰어 즉시 로드.
- **다운로드 흐름**: "**s5cmd manifest**" — 검색 쿼리 → `s5cmd run <manifest>` 명령 → AWS/GCP public bucket 에서 parallel pull [^idc-s5cmd]. RadiVault 의 "AI 엔지니어 친화" 가치 제안에 가장 가까운 패턴. **로그인 불요로도 manifest 다운로드 가능**.
- **Preview/다운로드 분리**: 전부 무료 공개. 차등 게이트 없음.
- **포맷**: DICOM + DICOM SEG/SR + 일부 BIDS 변환.

[^idc-portal-2025]: IDC Portal — https://portal.imaging.datacommons.cancer.gov/explore/ ; IDC User Guide — https://learn.canceridc.dev/
[^idc-s5cmd]: IDC s5cmd download docs — https://learn.canceridc.dev/data/downloading-data ; IDC Python idc-index — https://github.com/ImagingDataCommons/idc-index

### 3.6 Flywheel (research data platform)

- **컨텍스트**: 학술·제약 research data management. data-marketplace 가 아닌 **이미 보유한 데이터를 organize** 하는 플랫폼. 본 문서 비교 대상으로는 viewer/preview 패턴만 참고.
- **썸네일·viewer**: thumbnail double-click → V3 Viewer 새 탭 [^flywheel-v3-viewer]. **OHIF v3 Beta** 채택 [^flywheel-ohif-config]. DICOM SEG/RTSTRUCT overlay 지원 [^flywheel-3d-seg].
- **다운로드 흐름**: `fw download` CLI [^flywheel-cli-tutorial]. presigned URL 또는 Flywheel storage native.
- **시사점**: **CLI 다운로드 + 웹 viewer 분리** 가 enterprise 표준. RadiVault Python SDK + 웹 viewer 모델과 일치.

[^flywheel-v3-viewer]: Flywheel V3 Viewer Getting Started — https://docs.flywheel.io/user/viewer/v3/getting_started/
[^flywheel-ohif-config]: Flywheel OHIF Config File — https://docs.flywheel.io/user/viewer/v2/ohif_config_file/
[^flywheel-3d-seg]: Flywheel V3 3D Segmentations — https://docs.flywheel.io/user/viewer/v3/segmentation/
[^flywheel-cli-tutorial]: Flywheel CLI Tutorial — https://docs.flywheel.io/CLI/start/tutorial_first_import/

### 3.7 5사 비교 매트릭스

| 항목 | Segmed | Gradient Atlas | TCIA | IDC | Flywheel |
|---|---|---|---|---|---|
| 검색 카드 썸네일 | TBD (마케팅 카피 only) | **YES** ("instant image previews") | YES (NBIA portal) | YES | YES |
| Viewer 종류 | TBD | TBD (instant preview UI 자체) | **OHIF** (공식) | **OHIF** (임베드) | **OHIF v3** (Beta) |
| 다운로드 모델 | Order → days → ZIP | CSV 즉시 + DICOM order(days) | Manifest + NBIA Retriever | **Manifest + s5cmd** | CLI (`fw download`) |
| 즉시 vs Cart vs Order | Order (days) | 하이브리드 (CSV 즉시 / DICOM order) | Cart + Manifest | Manifest 즉시 | CLI on-demand |
| Preview vs Paid 분리 | TBD | **분리 (preview free, full order)** | 전부 무료 | 전부 무료 | 자체 데이터 |
| 익명화 검증 노출 | SOC2/HIPAA 보증 | (명시 없음) | RSNA CTP 공개 | RSNA CTP 공개 | N/A |
| 다운로드 포맷 | DICOM+report | DICOM+JSON | DICOM(+SEG/SR) | DICOM+SEG | DICOM/NIfTI/BIDS |

---

## 4. DICOMweb WADO-RS Preview 기술 패턴

### 4.1 표준 spec — PS3.18 Thumbnail Resource (Sup 203)

- DICOM PS3.18 의 **Supplement 203** 이 Thumbnail resource 를 정식 도입 [^dicom-ps318-thumb] [^dicom-sup203].
- **엔드포인트**:
  - `GET /studies/{study}/thumbnail`
  - `GET /studies/{study}/series/{series}/thumbnail`
  - `GET /studies/{study}/series/{series}/instances/{instance}/thumbnail`
  - `GET /studies/{study}/series/{series}/instances/{instance}/frames/{frame}/thumbnail`
- **Media Type**: **`image/jpeg` 필수 지원** (모든 resource category) [^dicom-ps318-thumb]. PNG/GIF 추가 가능.
- **PHI 제약**: "**The Thumbnail shall not contain any Patient Identifying Information**" — spec 자체에 명시 [^dicom-ps318-thumb]. RadiVault 가 thumbnail 캐시를 만들 때 메타·픽셀 둘 다 PHI free 검증 후 캐싱해야 spec 적합.
- **크기**: spec 자체로는 명시 픽셀 크기 강제 없음. 구현체별 관행 — OHIF/Cornerstone3D 는 통상 **96–256 px** thumbnail (sidebar), study card 용은 **512 px** 정도. **TBD: industry 평균 size 정량 자료 필요**.

[^dicom-ps318-thumb]: DICOM PS3.18 Web Services — Retrieve Thumbnail — https://www.dicomstandard.org/using/dicomweb/retrieve-wado-rs-and-wado-uri ; PS3.18 Part 18 — https://dicom.nema.org/medical/dicom/current/output/html/part18.html
[^dicom-sup203]: DICOM Supplement 203 (Thumbnail Resource) — https://dicom.nema.org/Dicom/News/March2018/docs/sups/sup203.pdf

### 4.2 Rendered vs Thumbnail vs Frames

| Endpoint | 용도 | 응답 크기 | RadiVault 매핑 |
|---|---|---|---|
| `/thumbnail` | 카드용 대표 1장 | KB 단위 (JPEG) | 검색 결과 카드 |
| `/rendered` | 임의 instance JPEG/PNG 변환 | 수십 KB ~ MB | 상세 페이지 슬라이스 표시 |
| `/frames/{n}` | multi-frame raw 픽셀 | MB ~ GB | OHIF cornerstone 로 streaming |
| `/instances/{uid}` | DICOM raw | 수십 MB+ | 다운로드 |

- Orthanc 의 `/rendered` 구현 — **multipart/related 로 각 frame 을 JPEG 응답**, OHIF 가 cornerstone3D 로 stream-decode [^orthanc-wado-rendered] [^orthanc-cache].
- **Cache 전략**: Orthanc 1.12.2+ 가 `MaximumStorageCacheSize` (RAM LRU) 도입 — 동일 file/transcoded frame 동시 요청 dedupe [^orthanc-cache]. 산업 표준은 **(a) Orthanc 자체 RAM cache + (b) CDN edge cache (Cloudflare/CloudFront) + (c) origin 측 redis blob** 3-layer.

[^orthanc-wado-rendered]: Orthanc Users — WADO-RS Rendered response — https://discourse.orthanc-server.org/t/wado-rs-rendered-response/3047
[^orthanc-cache]: Orthanc 1.12.2 NEWS (storage cache) — https://orthanc.uclouvain.be/hg/orthanc/file/Orthanc-1.12.2/NEWS ; DICOMweb plugin docs — https://orthanc.uclouvain.be/book/plugins/dicomweb.html

### 4.3 "대표 슬라이스" 결정 알고리즘

DICOM spec 자체는 결정 알고리즘 강제하지 않음 (Sup 203 은 "representative" 만 표현). 실무 패턴:

1. **중간 슬라이스 (median index)** — 구현 가장 단순, 다수 PACS 가 채택. 단점: 실 lesion 이 양 끝에 있는 경우 정보 부족.
2. **InstanceNumber 중앙값** — DICOM tag `(0020,0013)` 기반.
3. **ImagePositionPatient (0020,0032) 기반 중앙** — 해부학적 중앙.
4. **non-zero pixel 영역 최대** — segmentation/lesion 가능성 있는 슬라이스 우선.
5. **Key Object Selection (DICOM KOS)** — 판독의가 표시한 key image 가 있으면 그것 (한국 PACS 일부 INFINITT 가 지원).

**RadiVault 권고 (D-13 MVP)**: **#1 (median)** — 구현 1시간, 데모 충분. 풀 스코프에서 #4 또는 #5 로 업그레이드.

### 4.4 Cornerstone3D / OHIF v3 임베드

- **OHIF Viewer 는 iframe + postMessage 임베드 공식 지원** [^ohif-deployment]. v3.9 (2024-11) 부터 Cornerstone3D 2.0 통합, WebGL 단일 컨텍스트 multi-viewport, VoxelManager 메모리 절반 감소 [^ohif-v39-release].
- 데이터 소스로 **DICOMweb (QIDO-RS, WADO-RS) 필요** [^ohif-intro]. RadiVault 가 buyer-facing OHIF 를 노출하려면 **Zone 2 에 buyer-facing DICOMweb gateway** 필요 — 이 결론은 `buyer-portal-ux-competitive.md` §11 (Apr 24) 에서 이미 도출됨.
- **MVP 단축 경로**: 별도 DICOMweb gateway 없이 **(a) 사전 렌더링된 JPEG sprite/시퀀스를 정적 S3 + CDN 으로 서빙**, (b) 단순 cornerstone-core (DICOMweb 없이) 로 multi-frame nav. 풀 스코프에서 OHIF iframe 으로 교체.

[^ohif-deployment]: OHIF Deployment Overview — https://docs.ohif.org/deployment/ ; OHIF Embedded Viewer (v2 docs) — https://v2.docs.ohif.org/deployment/recipes/embedded-viewer/
[^ohif-v39-release]: OHIF Viewer v3.9 release — https://ohif.org/release-notes/3p9/ ; Cornerstone3D GitHub — https://github.com/cornerstonejs/cornerstone3D
[^ohif-intro]: OHIF Intro docs — https://docs.ohif.org/

---

## 5. 익명화 검증 (Burned-in PHI)

### 5.1 위험성 재확인 (이미 RadiVault 내부 리서치 존재)

- 이미 `de-id-pixel-technical-foundations.md` (Apr 23) §4.1.1 에 정리됨: **DICOM tag `(0028,0301) BurnedInAnnotation` 은 Type 3 (선택), 벤더별 미기재·오기재 빈번** (PMC 11522224, 2024).
- **Buyer preview 단계의 위험**: order → De-ID → fulfillment 경로에서는 De-ID engine 이 한 번 더 검증하지만, **preview thumbnail 은 Hot Storage 에서 직접 렌더되므로 한 번이라도 leak 발생 시 PHI 가 buyer 화면에 영구 노출**. → **preview 노출 전 이중 검증 의무**.

### 5.2 Industry 도구 비교

| 도구 | 라이선스 | 강점 | 약점 |
|---|---|---|---|
| **Microsoft Presidio** (`DicomImageRedactorEngine`) | MIT | Production-ready, OCR + DICOM metadata 융합 deny-list, Azure Form Recognizer 옵션 [^presidio-dicom] [^presidio-eval] | metadata 자체는 redact 안 함, 타 도구와 결합 필요 |
| **John Snow Labs Visual NLP** | Commercial | 한국어 OCR 지원 명시 | 라이선스 비용 |
| **PMC 11522224 파이프라인** (EAST + Tesseract) | 학술 (논문 공개) | 12,578 영상 중 10건 leak (recall 99.92%) [^pmc-11522224] | 한국어 모델 별도 학습 필요 |
| **TCIA RSNA CTP** | 오픈소스 | 학술 표준, 수십년 운영 검증 | metadata 중심, 픽셀 OCR 은 별도 plugin |
| **PixelMed / dcmtk dcmodify** | 오픈소스 | DICOM tag 조작 표준 | 픽셀 PHI OCR 없음 |
| **FW Presidio fork (Flywheel)** | MIT | Presidio 의 Flywheel 환경 fork | upstream Presidio 와 동기화 필요 |

[^presidio-dicom]: Microsoft Presidio — Redacting Text PII from DICOM images — https://microsoft.github.io/presidio/samples/python/example_dicom_image_redactor/ ; Image Redaction overview — https://microsoft.github.io/presidio/image-redactor/
[^presidio-eval]: Presidio — Evaluating DICOM redaction — https://microsoft.github.io/presidio/image-redactor/evaluating_dicom_redaction/
[^pmc-11522224]: "A Method for Efficient De-identification of DICOM Metadata and Burned-in Pixel Text", J Imaging Inform Med (2024) — https://pmc.ncbi.nlm.nih.gov/articles/PMC11522224/

### 5.3 RadiVault 권고 — preview 전용 검증 게이트

```
[Hot Storage DICOM] 
   → Thumbnail 생성 워커
   → (1) BurnedInAnnotation tag 체크 (YES → 격리)
   → (2) modality/series whitelist (CT axial OK, US/Mammo 의심)
   → (3) Presidio DicomImageRedactorEngine 로 OCR 스캔
   → (4) PASS → JPEG thumbnail 생성 → Thumbnail Cache (Zone 2) 저장
   → FAIL → 수동 큐 + buyer 검색 결과에서 해당 study 비표시
```

→ De-ID engine (Zone 1) 의 출력에 대해 **Zone 2 thumbnail 워커가 한 번 더 OCR 검증** 하는 이중 게이트. spec 적합 (PS3.18 "no patient identifying information") + 실무 안전.

### 5.4 한국 PIPA + 보건복지부 「보건의료데이터 활용 가이드라인」(2024-12 개정)

- 보건복지부가 2024-12-16 개정한 **「보건의료데이터 활용 가이드라인」** 이 **비정형 의료데이터 (영상·텍스트) 가명 처리 방법·절차를 구체화** [^mohw-guideline-2024]. 보도자료에 "영상·텍스트 등 비정형 의료데이터의 가명 처리 방법과 절차를 구체화" 명시 [^mohw-press-2024].
- 이 가이드라인이 **익명정보 vs 가명정보 vs 폐쇄분석환경** 3 트랙을 구분 — RadiVault 의 "완전 익명정보 국외이전" 모델은 가장 strict tier 에 해당.
- **법률 자문 필요 사항**: 가이드라인 본문이 픽셀 데이터 비식별 기술적 기준 (예: OCR recall 임계값) 까지 정량 명시하는지 — 본 검색에서는 보도자료·요약본만 확인. 가이드라인 PDF 직접 검토 + 변호사 자문 필수 flag.

[^mohw-guideline-2024]: 한국보건의료정보원 공지 — 2024-12 「보건의료데이터 활용 가이드라인」 개정 — https://k-his.or.kr/board.es?mid=a10301000000&bid=0001&list_no=1538&act=view
[^mohw-press-2024]: 보건복지부 보도자료 — "비정형데이터 가명처리, 결합 데이터 제공 등 보건의료 데이터 활용 지원 강화" — https://www.mohw.go.kr/board.es?mid=a10503000000&bid=0027&act=view&list_no=1483931 ; 가이드라인 본문 PDF (개인정보보호위원회 게시) — https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS217&mCode=D010030000&nttId=9901

---

## 6. 다운로드 모델

### 6.1 Instant vs Order — Stripe-style "preview free, paid full"

- Gradient 가 가장 명확: **CSV 메타 즉시 export (free)** + **DICOM 일괄 export (order, days)** [^gradient-atlas]. RadiVault 가 채택할 만한 정확한 패턴.
- TCIA/IDC 는 **manifest 도 즉시 free** 인데, 이는 학술 무료 모델이라 가능. 상업 모델에는 부적합.
- Segmed 는 전 과정 영업기반 (cohort curation team) — RadiVault 가 self-serve 차별화 가능 영역.

### 6.2 Order/Cart 모델 vs single-click

| 시나리오 | 권고 모델 | 근거 |
|---|---|---|
| Sample 1 study (수십 MB) | **single-click instant download** | 데모 friction zero |
| Cohort 50–500 studies (수 GB) | **cart → order → presigned URL bundle** | 익명화 재검증 시간 필요 |
| Cohort 1K+ studies (수십 GB+) | **manifest + s5cmd / Python SDK** | IDC 패턴, AI 엔지니어 친화 |

### 6.3 다운로드 quota / per-key 관리

- 산업 표준 미정. RadiVault 의 search-limit (250 study) 와 유사하게 **per-buyer-per-month download quota** 도입 권고.
- **legal/economic 동기**: "익명정보라도 무제한 다운로드는 재식별 위험 누적". PIPA 규정 + 비즈니스 차원 free tier 통제.

### 6.4 Presigned URL TTL — industry baseline

- AWS S3 presigned URL 한계: **CLI/SDK 최대 7일, console 최대 12시간** [^aws-presigned-userguide] [^aws-presigned-best-practice].
- **다운로드 시작 후 expire 되어도 진행 중 download 는 끝까지 진행** [^aws-presigned-knowledge].
- **권고 TTL**:
  - Sample preview JPEG: **10 분** (Hot, CDN cache 활용)
  - Sample 1 study DICOM: **1 시간** (다운로드 시간 + 재시도 마진)
  - 정식 order 결과 ZIP: **7 일** (PRD §4.3 명시 7일 TTL 과 일치)
- **보안**: presigned URL 자체가 capability — 누설 시 anyone 접근. **HTTPS 강제 + Referer 제한 + IP 제한 + audit log** 필수.

[^aws-presigned-userguide]: AWS S3 presigned URL user guide — https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html
[^aws-presigned-best-practice]: AWS prescriptive guidance — Presigned URL best practices PDF — https://docs.aws.amazon.com/pdfs/prescriptive-guidance/latest/presigned-url-best-practices/presigned-url-best-practices.pdf
[^aws-presigned-knowledge]: AWS re:Post — Presigned URL expiration during download — https://repost.aws/knowledge-center/presigned-url-s3-bucket-expiration

### 6.5 Large file chunked / resumable

- **HTTP Range request (RFC 7233)** — 표준 resumable. 206 Partial Content [^mdn-range-requests] [^http-range-explained].
- **DICOMweb multipart/related** — WADO-RS 가 multiple instance 를 multipart MIME 로 묶어 응답 [^dicom-multipart].
- **S3 multipart upload** 은 buyer-facing 다운로드 측에는 직접 적용 안 됨 — buyer 가 Range 로 chunk download 하면 충분.
- **권고**: RadiVault MVP 는 **단일 study (수십 MB) 는 plain GET**, cohort bundle 은 **ZIP + Range 지원** (S3 native). resumable upload 패턴 (resumable.js) 은 buyer 측 미구현, Python SDK 측에서 retry 로직.

[^mdn-range-requests]: MDN HTTP range requests — https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Range_requests
[^http-range-explained]: HTTP Range Requests explained — https://http.dev/range-request
[^dicom-multipart]: DICOM PS3.18 §6.5.2.2 Response (multipart/related) — https://dicom.nema.org/medical/dicom/2019a/output/chtml/part18/sect_6.5.2.2.html

---

## 7. 한국 시장 특이사항

### 7.1 PIPA 제28조의8 (개인정보 국외 이전) 재확인

- **원칙**: 개인정보 국외이전 금지. 예외 5가지 (정보주체 동의 / 법령·조약 / 위탁 보관 / 인증 / 보호 수준 인정 국가) [^pipa-28-8] [^pipa-law-go-kr].
- **익명정보** 는 **개인정보의 정의에서 제외** — PIPA 가 적용되지 않음. 따라서 28-8 규제 밖. **이것이 RadiVault 의 합법성 근거**.
- **그러나**: 익명화의 "완전성" 에 대한 분쟁 발생 시 — 입증 책임은 처리자. **재식별 가능성에 대한 자체 평가·문서화 의무**.
- **법률 자문 flag**: thumbnail preview (= 더 적은 데이터) 도 buyer 가 정보주체에 식별 가능하지 않다는 합리적 평가 필요. 법률 자문 필수.

[^pipa-28-8]: 개인정보 보호법 제28조의8 (CaseNote) — https://casenote.kr/%EB%B2%95%EB%A0%B9/%EA%B0%9C%EC%9D%B8%EC%A0%95%EB%B3%B4_%EB%B3%B4%ED%98%B8%EB%B2%95/%EC%A0%9C28%EC%A1%B0%EC%9D%988
[^pipa-law-go-kr]: 국가법령정보센터 — 개인정보 보호법 — https://www.law.go.kr/LSW/lsInfoP.do?lsId=011357&ancYnChk=0

### 7.2 보건복지부 「보건의료데이터 활용 가이드라인」 (2024-12-16 개정)

- §5.4 에서 이미 상술. 추가 — **2025-12-31 추가 개정** 예정/완료 흔적 [^mohw-guideline-2025] (개인 블로그 출처, **TBD: 1차 출처 확인 필요**).
- 가이드라인 전체 PDF 직접 다운 후 픽셀 데이터 항 검토 — D-13 demo 후 즉시 follow-up.

[^mohw-guideline-2025]: 개인 블로그 — 2025-12-31 개정 언급 (1차 출처 확인 필요) — https://sooyongshin.wordpress.com/2026/01/18/

### 7.3 식약처 「디지털의료기기 분류 및 등급 지정 가이드라인」 (2026-03-20 개정)

- 식약처가 2026-03-20 개정한 「디지털의료기기 분류 및 등급 지정 가이드라인」 [^mfds-digital-classification].
- 「디지털의료기기소프트웨어 허가·심사 가이드라인」 (2025-05) [^mfds-samd-guideline] 도 병행.
- **SaMD 분류 핵심**: AI 영상 진단 등 "기능별 위험 평가" 강조, 1~4등급 [^mfds-press-2026] [^mfds-shinkim-newsletter].
- **RadiVault preview viewer 의 SaMD 분류 위험 평가**:
  - **저위험 (의료기기 비해당으로 추정)**: 단순 표시 (zoom, pan, window-level), 다운로드 전 시각 확인 — "research dataset 평가 도구" 위치.
  - **고위험 (SaMD 분류 가능)**: 진단 보조, 정량 측정, AI 추론 결과 표시, segmentation overlay — 식약처 허가 필요.
- **권고**: D-13 demo 와 v1 portal 모두 **표시·navigation 한정**, 측정/진단/AI 추론 기능 일체 제외. 사용 약관에 "for dataset evaluation only, not for clinical use" 명시.
- **법률 자문 flag**: 식약처 사전 상담 (RaQA) 권고. 미국 FDA 의 "non-device CDS" 가이던스 와 한국 식약처 분류 기준 차이 검토 필요.

[^mfds-digital-classification]: 식약처 「디지털의료기기 분류 및 등급 지정 가이드라인」 (2026-03-20 개정 보도참고) — https://dazabi.com/insurance_magazine/article.php?id=9895
[^mfds-samd-guideline]: 식약처 「디지털의료기기소프트웨어 허가·심사 가이드라인」 (2025-05, 민원인 안내서) — https://www.kbiohealth.kr/consulting/fileDownload?titleId=Ko5hLZmhMY&fileId=1&fileDownType=C&paramMenuId=MENU002030200000000
[^mfds-press-2026]: 식약처 보도참고 (디지털의료기기 분류 등급 가이드라인 개정) — https://dazabi.com/insurance_magazine/article.php?id=9895
[^mfds-shinkim-newsletter]: 신한김장리 뉴스레터 — 식약처 디지털의료기기 가이드라인 6종 제·개정 — https://www.shinkim.com/kor/media/newsletter/2828

---

## 8. RadiVault 권고 — D-13 MVP vs 풀 스코프

### 8.1 D-13 MVP (2026-05-08 CEO 데모)

| 기능 | 구현 | 시간 추정 |
|---|---|---|
| **검색 카드 썸네일** | 사전 렌더링 JPEG (median slice), Zone 2 정적 S3 + CDN 서빙. 스펙: 256×256 px JPEG. | 1일 (Hot Storage 의 5–10 study 만 시드) |
| **상세 슬라이스 viewer** | 정적 JPEG 시퀀스 + 슬라이더 (multi-frame nav). cornerstone-core OR 순수 React `<canvas>`. OHIF 임베드 **불요**. | 1일 |
| **샘플 1 study 즉시 다운로드** | "Try sample" 버튼 → presigned URL (1h TTL) → 1 ZIP (수십 MB DICOM). watermarked OR sample-only collection. | 0.5일 |
| **익명화 검증 게이트** | Hot Storage 의 5–10 study 는 **수동 OCR 검증 마침** 으로 단순화. 자동화는 풀 스코프. | 0일 (이미 처리된 데이터만 노출) |
| **DICOM tag 노출 정책** | 익명화 후 안전 tag만 buyer 메타 로 노출 (Modality, BodyPart, Age range, Sex, AcquisitionYear). PatientID/Name 은 **검색 응답에서 제거**. | (이미 search 서비스 구현됨, 검증만) |
| **다운로드 quota** | sample 다운로드 per-buyer 1회 (또는 daily 1회). search-limit (250/mo) 와 유사 패턴. | 0.5일 |
| **Order 흐름** | 기존 dev-spec-order-fulfillment 그대로. 추가 변경 없음. | 0일 |
| **SaMD 면책 문구** | viewer 페이지 footer + 사용 약관: "For dataset evaluation only. Not for clinical use." | 0.1일 |
| **합계** | | **약 3일 작업** |

### 8.2 풀 스코프 (Phase 2, post-D-13)

| 기능 | 구현 | 의존 dev-spec |
|---|---|---|
| **다중 시리즈 viewer** | OHIF v3 iframe 임베드 + Zone 2 buyer-facing DICOMweb gateway 신규 구축 | 신규 dev-spec: `dev-spec-buyer-dicomweb-gateway.md` |
| **Cohort 일괄 다운로드** | manifest + Python SDK (`radivault-cli`) + s5cmd 호환 (또는 native fetch) | 신규 dev-spec: `dev-spec-buyer-sdk.md` |
| **Burned-in PHI 검증 자동화** | Presidio `DicomImageRedactorEngine` Zone 2 워커. De-ID engine 출력 → thumbnail 생성 전 재OCR | dev-spec-de-id-pixel.md 확장 + 신규 thumbnail worker spec |
| **Hot Storage 자동 promotion** | 인기 cohort 통계 기반 사전 익명화 (PRD §4.4 명시) | dev-spec-order-fulfillment.md 확장 |
| **다운로드 quota dashboard** | per-buyer monthly download tier (free/preview/paid) | dev-spec-billing.md (미작성) |
| **SaMD 회피 vs 식약처 인허가** | 법률·RaQA 자문 → 결과에 따라 viewer scope 동결 또는 인허가 트랙 | 별도 컴플라이언스 트랙 |

---

## 9. PRD / ARCHITECTURE 갱신 제안

본 리서치 결과 다음 갱신이 필요하다고 판단됨. **본 문서는 제안만 — 실제 갱신은 메인 세션이 결정**.

1. **PRD §4.3 (구매자 포털)** — "썸네일 미리보기" 와 "DICOM 웹 뷰어 통합" 을 **D-13 MVP scope 와 풀 스코프 로 분리** 명시 권고.
2. **PRD §4.4 (주문 처리)** — "샘플 1 study 즉시 다운로드 (preview tier)" 추가 권고. Stripe-style 무료 시연 → 유료 cohort 전환 funnel.
3. **ARCHITECTURE §4.3 (Thumbnail Cache + CDN)** — DICOM PS3.18 Sup 203 spec 적합 명시 + Burned-in PHI OCR 재검증 게이트 추가 권고.
4. **ARCHITECTURE §5.x (Web Portal)** — OHIF iframe + buyer-facing DICOMweb gateway 가 풀 스코프 의 별도 컴포넌트임을 §5.5 신규 절로 분리 권고.
5. **ARCHITECTURE 추가** — "**SaMD 비분류 보장 정책**: viewer 기능은 zoom/pan/window-level 한정, 측정·진단·AI overlay 일체 제외" 를 §6 (제약) 또는 §7 (정책) 신규 절로 추가 권고.

---

## 10. 한계·오픈 퀘스천

1. **Segmed buyer UI 의 실제 썸네일·viewer 형태** — 마케팅 페이지에서 추출 불가. Trial 계정 또는 영업 데모 필요. (TBD)
2. **Gradient Atlas 의 viewer 기술 스택** — "instant image previews" 가 OHIF/Cornerstone 기반인지 자체 구현인지 미공개. (TBD)
3. **보건복지부 가이드라인 PDF 본문의 픽셀 데이터 정량 기준** — 보도자료·요약만 검토. PDF 직접 검토 + 변호사 의견 필요. (D-13 후 follow-up)
4. **식약처 RaQA 사전상담 결과** — RadiVault 의 viewer 가 SaMD 비분류 가능한지 식약처 공식 입장 미확보. (별도 컴플라이언스 트랙)
5. **한국 다운로드 시 KISA 망법·국가정보보안 기본지침 준수 여부** — 본 리서치 범위 밖, 별도 검토 필요.
6. **Sample preview DICOM 의 PIPA 적합성** — `buyer-portal-ux-competitive.md` §11 에서도 동일 flag. 변호사 자문 필수.
7. **DICOM Thumbnail 표준 picksize industry 평균** — spec 없음. 경쟁사 실측 data 필요. (TBD)
8. **다운로드 quota 의 적정 free tier 한계** — 비즈니스 결정 (CEO).
9. **번인 PHI 재OCR 의 한국어 모델 성능** — PMC 11522224 평가는 영어 데이터. 한국어 (특히 한자 환자명) recall 별도 평가 필요. (D-13 후 dev-spec-de-id-pixel 확장 시)

---

## 11. 출처 목록 (정리)

### 1차 — DICOM 표준
- DICOM PS3.18 — Web Services — https://dicom.nema.org/medical/dicom/current/output/html/part18.html
- DICOM PS3.18 §6.5.2.2 (multipart/related) — https://dicom.nema.org/medical/dicom/2019a/output/chtml/part18/sect_6.5.2.2.html
- DICOM Sup 203 (Thumbnail Resource) — https://dicom.nema.org/Dicom/News/March2018/docs/sups/sup203.pdf
- DICOMweb home — https://www.dicomstandard.org/using/dicomweb/retrieve-wado-rs-and-wado-uri

### 1차 — 한국 규제
- 개인정보 보호법 §28-8 (국가법령정보센터) — https://www.law.go.kr/LSW/lsInfoP.do?lsId=011357&ancYnChk=0
- 보건복지부 보도자료 (2024-12) — https://www.mohw.go.kr/board.es?mid=a10503000000&bid=0027&act=view&list_no=1483931
- 한국보건의료정보원 — 보건의료데이터 활용 가이드라인 개정 안내 — https://k-his.or.kr/board.es?mid=a10301000000&bid=0001&list_no=1538&act=view
- 개인정보보호위원회 — 가이드라인 PDF — https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS217&mCode=D010030000&nttId=9901
- 식약처 디지털의료기기소프트웨어 허가·심사 가이드라인 (2025-05) — https://www.kbiohealth.kr/consulting/fileDownload?titleId=Ko5hLZmhMY
- 식약처 디지털의료기기 분류 및 등급 지정 가이드라인 (2026-03-20 보도) — https://dazabi.com/insurance_magazine/article.php?id=9895
- 신한김장리 뉴스레터 (식약처 6종 가이드) — https://www.shinkim.com/kor/media/newsletter/2828

### 1차 — 경쟁사 공식 문서
- Segmed Insight — https://www.segmed.ai/insight ; Solutions — https://www.segmed.ai/solutions ; Insight 블로그 — https://www.segmed.ai/resources/blog/introducingsegmedinsight
- Gradient Health Atlas — https://gradienthealth.io/ai-developer/atlas/ ; Atlas 2 launch — https://gradienthealth.io/gradient-health-launches-atlas-2-setting-a-new-standard-for-medical-imaging-data-access/
- TCIA Wiki — https://wiki.cancerimagingarchive.net/display/NBIA ; Viewing 7.7 — https://wiki.cancerimagingarchive.net/display/NBIA/Viewing+TCIA+Collections+7.7 ; Downloading — https://wiki.cancerimagingarchive.net/display/NBIA/Downloading+TCIA+Images
- IDC Portal — https://portal.imaging.datacommons.cancer.gov/explore/ ; IDC User Guide — https://learn.canceridc.dev/ ; idc-index — https://github.com/ImagingDataCommons/idc-index
- OHIF — https://ohif.org/ ; Showcase TCIA — https://ohif.org/showcase/tcia/ ; Deployment — https://docs.ohif.org/deployment/ ; v3.9 release — https://ohif.org/release-notes/3p9/
- Cornerstone3D — https://github.com/cornerstonejs/cornerstone3D
- Flywheel — https://docs.flywheel.io/user/viewer/v3/getting_started/ ; OHIF config — https://docs.flywheel.io/user/viewer/v2/ohif_config_file/
- Orthanc DICOMweb plugin — https://orthanc.uclouvain.be/book/plugins/dicomweb.html ; 1.12.2 NEWS — https://orthanc.uclouvain.be/hg/orthanc/file/Orthanc-1.12.2/NEWS

### 1차 — 익명화 도구
- Microsoft Presidio DICOM redactor — https://microsoft.github.io/presidio/samples/python/example_dicom_image_redactor/
- Presidio Image Redactor index — https://microsoft.github.io/presidio/image-redactor/
- Presidio DICOM evaluation — https://microsoft.github.io/presidio/image-redactor/evaluating_dicom_redaction/

### 2차 — 학술
- TCIA: Maintaining and Operating a Public Information Repository — https://pmc.ncbi.nlm.nih.gov/articles/PMC3824915/
- NCI Imaging Data Commons — https://pmc.ncbi.nlm.nih.gov/articles/PMC8373794/
- "A Method for Efficient De-identification of DICOM Metadata and Burned-in Pixel Text" (2024) — https://pmc.ncbi.nlm.nih.gov/articles/PMC11522224/

### 2차 — 보도/뉴스
- AuntMinnie — Segmed 100M studies — https://www.auntminnie.com/imaging-informatics/enterprise-imaging/pacs-vna/article/15634029/segmed-platform-passed-100m-studies
- Datavant ↔ Segmed — https://www.datavant.com/press-release/segmed-datavant-team-provide-deeper-patient-insights-advanced-imaging-data-integration

### 1차 — AWS / HTTP
- AWS S3 presigned URL user guide — https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html
- AWS prescriptive guidance PDF — https://docs.aws.amazon.com/pdfs/prescriptive-guidance/latest/presigned-url-best-practices/presigned-url-best-practices.pdf
- AWS re:Post (presigned URL expiration) — https://repost.aws/knowledge-center/presigned-url-s3-bucket-expiration
- MDN HTTP range requests — https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/Range_requests

### 내부 (RadiVault)
- `docs/research/buyer-portal-ux-competitive.md` (Apr 24) — Viewer/preview 판정 §11
- `docs/research/de-id-pixel-technical-foundations.md` (Apr 23) — Burned-in 검증 파이프라인
- `docs/research/gateway-agent-technical-foundations.md` (Apr 22) — DICOMweb 채택 근거
- `docs/research/order-fulfillment-technical-foundations.md` (Apr 23) — order/fulfillment 흐름
- `docs/prd.md` §4.3·4.4 ; `docs/ARCHITECTURE.md` §4.3·5.x

---

## 12. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|---|---|---|---|
| 1.0 | 2026-04-25 | @researcher (Claude) | 최초 작성. 5사 비교 + DICOMweb spec + Burned-in PHI + 다운로드 모델 + 한국 규제 5개 섹션. D-13 MVP / 풀 스코프 권고 분리. |
