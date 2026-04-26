# Segmed Openda — 심층 분석 + RadiVault 차별 포지션 권고

> **Status**: Draft v0.1 · **Last updated**: 2026-04-25
> **작성자**: @researcher (Claude Opus 4.7, 1M context)
> **근거 요청**: Kyle — `openda.segmed.ai` 직접 로그인 결과 @designer 가 만든 첫 portal 리디자인 HTML mockup 이 "Segmed 와 너무 비슷하고 RadiVault 차별성이 약함" 으로 평가. mockup v2 작성 전, (a) Segmed Openda 의 화면·인터랙션·기술 스택을 가능한 정확히 분석하고 (b) RadiVault 가 따라가지 말아야 할 것 / 흡수해야 할 것 / 명확히 차별화할 것을 도출하기 위함.
> **선행 리서치 (직접 연관)**:
> - [`portal-redesign-competitive-analysis.md`](./portal-redesign-competitive-analysis.md) — 15 사이트 시각·브랜드 분석. Openda 본체는 미접속(공개 콘텐츠만 분석). 본 문서가 Openda 한정으로 깊이 보강.
> - [`buyer-portal-ux-competitive.md`](./buyer-portal-ux-competitive.md) — 포스트-로그인 UX 패턴 (Gen3/TCIA/IDC).
> - [`demo-pitch-references-radivault.md`](./demo-pitch-references-radivault.md) — 데모 연출 레퍼런스.
> - [`k-meddata-research-summary.md`](./k-meddata-research-summary.md) — 시장·규제 배경.

---

## 0. TL;DR (5줄)

1. **Segmed Openda 는 React + Tailwind + Cornerstone3D + Auth0 + AWS 위에 만들어진 "B2B sales-led marketplace"** 다. 메인 컬러 `#2563EB` (Tailwind blue-600), 폰트 Inter, 레이아웃 12-column responsive grid. 자체 SearchUI (`.sui-` 클래스) 로 facet 검색 구현, DICOM 뷰어는 OHIF 가 아닌 **Cornerstone3D 직접 통합**. (출처: `/static/js/main.18d2d2be.js`, `/static/css/main.db5bc966.css` 직접 분석)
2. **검색 UX 의 핵심 차별점은 "SNOMED 동의어 자동 확장" + "환자 단위 그루핑 후 modality/날짜/부위 정렬"**. 단순 facet checkbox 가 아닌, 임상 용어를 알면 검색이 빨라지는 ontology-aware 검색이 marketing 전면. (출처: 2024-07-01 Openda 런칭 PR, segmed.ai/solutions/openda)
3. **Openda 의 약점 3가지**: (a) **프루버넌스 불투명** — "어느 병원에서 왔는지" 표면에 안 드러남, "5 continents" 같은 집계 슬로건만. (b) **법적 차별성 미주장** — HIPAA/SOC2 만 강조, 지역 규제(GDPR/PIPA/PDPA) 별 상세 약속 없음. (c) **자가 검증 불가** — de-id 체인 단계가 마케팅 카피로만 ("Segmed Incognito") 노출, 실제 어떤 태그가 어떻게 처리됐는지 buyer 가 추적 못 함.
4. **RadiVault 가 흡수해야 할 것**: SNOMED-style 동의어 검색 + 환자 단위 그루핑 + Cornerstone3D 직접 통합 + "Try it now! Sign up is free" self-serve 진입로 (Segmed 가 의외로 진입을 낮춤).
5. **RadiVault 가 절대 따라가지 말 것**: (a) facet 을 horizontal pill 로 깔지 말 것 (Tailwind/SearchUI 정석을 그대로 답습하면 Segmed 모방). (b) 메인 컬러 `#2563EB` 회피 — RadiVault buyer 토큰은 별도 blue 셰이드로 차별. (c) "5 continents · 150M studies" 식 집계 슬로건 흉내 금지 — 우리는 **per-hospital provenance** 가 무기.

---

## 1. 조사 질문

1. Segmed Openda 의 검색·결과·상세·다운로드·계정 화면은 어떻게 생겼는가? (가능한 한 정확)
2. Openda 의 기술 스택은 무엇인가? (프레임워크·뷰어·인증·CDN·analytics)
3. Openda 의 facet 필드 / 데이터 모델 / 다운로드 흐름은 어떤가?
4. Openda 가 **드러내는 것** vs **숨기는 것** 은 무엇인가?
5. RadiVault 가 (a) 흡수해야 할 패턴, (b) 따라가지 말아야 할 패턴, (c) 명확히 차별화할 포지션은 무엇인가?

---

## 2. 방법론

### 2.1 1차 출처 (직접 분석)

| 자원 | 분석 방법 | 산출물 |
|---|---|---|
| `https://openda.segmed.ai/` (로그인 게이트) | WebFetch HTML 분석 | 타이틀·메타·번들 URL 추출 |
| `https://openda.segmed.ai/static/js/main.18d2d2be.js` | WebFetch + 문자열 grep | API endpoint 경로, modality 값, 라이브러리 (Cornerstone, Auth0, Amplitude), state 키 |
| `https://openda.segmed.ai/static/css/main.db5bc966.css` | WebFetch + 토큰 추출 | 브랜드 색상 hex, 폰트, 그리드, breakpoint |
| `https://openda.segmed.ai/robots.txt` | 정책 확인 | 전 경로 허용, 크롤링 제한 없음 |
| `https://www.segmed.ai/solutions/openda` | WebFetch | 공식 feature 카피 |
| `https://www.segmed.ai/solutions/for-medical-devices-and-ai-rd` | WebFetch | filter 카테고리 명문화 |
| `https://www.segmed.ai/solutions/for-data-management` | WebFetch | Segmed Incognito · Piper · Openda 3-제품 라인업 |
| `https://www.segmed.ai/security-compliance` | WebFetch | 인증 status |
| `https://www.segmed.ai/about-us` | WebFetch | 창업자·연혁·HQ |
| `prnewswire.com/news-releases/segmed-unveils-new-brand-identity-and-introduces-openda-...-302185953.html` | WebFetch | 2024-07-01 Openda 런칭 공식 PR |

### 2.2 2차 출처 (외부)

- Segmed × Verily 파트너십 (PRNewswire 2026-02-25) — Pre/Workbench 통합 컨텍스트
- Segmed × Datavant 파트너십 — 토큰화·longitudinal 컨텍스트
- Segmed × Bayer (PRNewswire) — Bayer AI 플랫폼 통합
- Segmed RSNA 2025 부스 #5147 — Microsoft 세션·Willemink 강연
- IAPP / Baker McKenzie — 한국 PIPA 2025 가이던스
- TJC Group · Didomi — PIPA 가이드

### 2.3 한계

- **로그인 후 화면 직접 접근 불가** — Kyle 본인 로그인 세션을 본 에이전트가 사용할 수 없음. JS 번들·CSS·공식 마케팅 카피로부터 **역추정**. 상세 화면 일부 항목은 "TBD: needs primary screenshot" 으로 명시.
- WebFetch 가 일부 페이지(`/openda` 별칭 404, Trust Center SPA 미렌더) 에서 빈 응답 — 보조 검색·대체 URL 로 우회.
- 본 문서는 **법률 자문이 아니다**. PIPA·HIPAA 어투는 Kyle + 외부 변호사 재검증 필요.

---

## 3. Segmed Openda — 화면 분석

### 3.1 기술 스택 (1차 직접 확인)

JS 번들·CSS·HTML 헤드 분석 결과:

| 영역 | 기술 | 확정도 | 근거 |
|---|---|---|---|
| **프론트엔드 프레임워크** | React (CRA — `static/js/main.<hash>.js` 패턴) | ★★★ | 번들 패턴, React internals 문자열 |
| **CSS** | Tailwind CSS v3.4.3 (CDN) + 커스텀 `.sui-` 클래스 | ★★★ | `cdn.tailwindcss.com/3.4.3` HTML 참조, CSS 파일 내 Tailwind utility 패턴 |
| **검색 UI 라이브러리** | Elastic Search UI (`.sui-layout`, `.sui-result` 클래스) — 추정 ★★ | 추정 | `.sui-` prefix 는 Elastic SearchUI 의 표준 클래스 |
| **DICOM 뷰어** | **Cornerstone3D 직접 통합** (OHIF 아님) | ★★★ | 번들 내 `cornerstoneimageloadprogress`, `RectangleROI`, `FrameOfReferenceUID`, `photometricInterpretation` 문자열. OHIF wrapper 흔적 없음 |
| **인증** | **Auth0** | ★★★ | 번들 내 Auth0 SDK 문자열 |
| **분석/로깅** | **Amplitude** + **HubSpot** (`js-na1.hs-scripts.com/5697260.js`) | ★★★ | 번들 + HTML script tag |
| **호스팅·인프라** | **AWS** (회사 페이지 명시) | ★★★ | segmed.ai/security-compliance "Utilizes Amazon Web Services (AWS) infrastructure" |
| **폰트** | **Inter var** (`rsms.me/inter/inter.css`) + 시스템 폰트 fallback | ★★★ | HTML link tag, CSS font-family |
| **그리드** | 12-column responsive (`grid-template-columns: repeat(12, minmax(0, 1fr))`) + sm 640 / md 768 / lg 1024 / xl 1280 / 2xl 1536 | ★★★ | CSS 직접 |

**API 경로** (번들 grep):

```
/v1/datasets/<id>/dicom_viewing
/v1/admin/datasets/<id>/dicom_viewing
/v1/dicom_viewing/<study|series ids>
/v1/dicom_viewing/availability
/v1/admin/dicomocr/
/v1/admin/blackout
/v1/report_corrupted_dicom
```

**해석**:
- `dicom_viewing` 엔드포인트가 **public + admin 양쪽 존재** — admin 은 데이터 큐레이션·QA 용 별도 콘솔.
- `blackout` (픽셀 마스킹) + `dicomocr` (번인 OCR) 는 **admin 전용** — buyer 에게는 노출 안 됨. 즉 **buyer 는 de-id 가 어떻게 됐는지 직접 확인 못 함** (단순 마케팅 신뢰).
- `report_corrupted_dicom` — buyer 가 corrupted study 신고 가능. 데이터 품질 피드백 루프 있음. **RadiVault 도 도입 가치 ★★★**.
- `dicom_viewing/availability` — pre-flight check (해당 dataset 이 viewer 로 열 준비 됐는지). UX 측면에서 "예열" 이 필요할 만큼 viewer 로딩이 무겁다는 추정 — Cornerstone3D 의 첫 로딩 비용 시사.

### 3.2 브랜드·시각 토큰 (1차 직접 확인)

| 토큰 | 값 | 비고 |
|---|---|---|
| `--color-primary` | `rgb(37 99 235)` = `#2563EB` | **Tailwind `blue-600` 정석값** |
| `--color-primary-active` | `rgb(29 78 216)` = `#1D4ED8` | Tailwind `blue-700` |
| `--color-secondary` | `rgb(219 234 254)` = `#DBEAFE` | Tailwind `blue-100` |
| `--color-secondary-active` | `rgb(191 219 254)` = `#BFDBFE` | Tailwind `blue-200` |
| 인터랙티브 액센트 | `#3a56e4` | Indigo-ish 보라기 살짝 |
| 페이지네이션 액센트 | `#1890ff` | Ant Design "Daybreak Blue" 시그니처 — Ant Design 컴포넌트 일부 사용 의심 |
| 보더 | `#e5e7eb` | Tailwind `gray-200` |
| 배경 액센트 | `rgb(26 209 205)` 터쿼이즈 + `rgb(39 31 29)` 다크 ebony | 마케팅·데코용 추정 |
| 폰트 | `Inter var` 본문, `ui-monospace` 코드 | **시스템 폰트 fallback 존재** |

**디자이너 인사이트**:
- Segmed 는 **Tailwind 디폴트 팔레트 그대로**. blue-600 + blue-100 만 가져다 씀. **고유성 거의 없음** — RadiVault 가 같은 hex 를 쓰면 즉시 "Segmed 클론" 인상.
- **Ant Design 의 `#1890ff` 흔적** + Tailwind 혼용. UI 컴포넌트 라이브러리가 일관되지 않음. RadiVault 는 **shadcn/ui 통합** 으로 일관성 우위 확보 가능.
- 본문 폰트는 Inter, **한글 폰트 미정의** — Segmed 는 사실상 영어 전용. RadiVault 의 한국어 + 영어 동시 지원이 시각·정보 차별 포인트.

### 3.3 검색/리스트 화면 (A.1) — 공식 카피·번들 신호 기반

> **주의**: 직접 화면 캡처는 본 에이전트 권한 외. 아래는 (1) `solutions/openda` + `solutions/for-medical-devices-and-ai-rd` 마케팅 카피, (2) JS 번들 내 SearchUI/Tailwind 패턴, (3) 2024-07-01 Openda 런칭 PR 의 합산 추정.

#### A.1.1 Facet (필터) 카테고리 — 공식 카피로 확인된 것

| Facet | 공식 카피 출처 | 옵션·값 (확인된 한도) |
|---|---|---|
| **Body part** (해부 부위) | `solutions/for-medical-devices-and-ai-rd` 직접 명시 | TBD: needs primary screenshot. RadLex/SNOMED 부위 코드 추정. |
| **Modality** | 동상 | CT, MR, X-ray, US, MG, PET (PET/CT, PET/MR 2024-07 추가), SPECT, Echocardiography, DEXA (모달리티 9개+ 카피로 확인) |
| **Geographic Source Location** | 동상 | 5 continents · 50 US states (집계 표현) — 실제 facet 옵션은 country/state 단위 추정 |
| **Patient characteristics** | 동상 — "age, gender, etc." | age range, sex, etc. (etc. 가 모호 — race/ethnicity 옵션 여부 TBD) |
| **Clinical findings (SNOMED)** | "Smart Search with Synonym Support · dynamic SNOMED term dropdown" | 자유 입력 + 동의어 자동 확장. 예: "lung cancer" 입력 → "carcinoma of lung" + "pulmonary neoplasm" 등 자동 후보 |
| **Manufacturer / scanner** | TBD: needs primary screenshot | 추정: GE/Siemens/Philips/Canon 등 (DICOM 표준 메타) |
| **Acquisition date / study year** | TBD | 범위 슬라이더 추정 |
| **Contrast / Without contrast** | TBD | radiology 표준 facet, 추정 |

**총 facet 카테고리 개수 (확인+추정 합산)**: **6~8 (확인 4 + 추정 2~4)**. 정확한 개수는 1차 스크린샷 확보 필요.

#### A.1.2 검색 인터랙션

- **Smart Search** (자유 입력 + SNOMED 자동완성 dropdown). PR 인용: "dynamic SNOMED term dropdown, allowing you to easily select synonyms and related terms."
- **그루핑·정렬**: "group studies by patient, then sort by date, modality, or specific body parts" — Openda 차별의 핵심. Patient 가 1차 그루핑 단위, study 는 자식. **Longitudinal patient view 가 기본**.
- **결과 카드 정보** (TBD: needs primary screenshot — 추정):
  - 썸네일 (Cornerstone3D 가 미리보기 키프레임 제공)
  - Modality + body part 배지
  - Patient pseudo ID
  - Study count (그룹 시) 또는 series/instance count (단일 study)
  - Acquisition date (시프트 후)
  - Source 표시 (병원명 노출 안 함 — "USA / California" 정도 집계만 추정)

**페이지네이션**: 번들 CSS 에 `#1890ff` (Ant Design pagination 시그니처) 발견 → 표준 페이지네이션 컴포넌트 사용. 무한 스크롤 아님 추정.

**코호트 (장바구니)**: 카피 "build custom cohorts from scratch" — 명확한 코호트 개념 존재. UX 디테일 (저장 가능 여부, 공유 가능 여부) TBD.

**federated 신호**: **거의 없음**. "5 continents · 2,800+ partner sites" 은 헤더 마케팅 슬로건, 결과 row 단위로 "이 study 는 X 병원에서 옴" 이 표시되는지는 미확인 (확인 시 RadiVault 비교 가치 큼).

#### A.1.3 검색 응답 시간·결과 카운트

- API 패턴 보면 `/v1/datasets/{id}/dicom_viewing` 등이 RESTful — 일반적인 ES/Postgres 인덱스 위 SearchUI. 응답 시간 표시 UI 여부 TBD.

### 3.4 상세 화면 (A.2) — 공식 카피·번들 기반

#### A.2.1 페이지 구조 (추정)

- **헤더**: 환자 pseudo ID + 환자 인구통계 (age range, sex)
- **메인**: Cornerstone3D 뷰어 (multi-pane 추정 — `RectangleROI` 측정 도구, `FrameOfReferenceUID` MPR 가능)
- **사이드**: study/series 트리 (study 내 series 리스트)

#### A.2.2 노출 메타데이터 필드 (확인 + 추정)

번들에 등장하는 식별자 + 표준 DICOM 필드:

| 레벨 | 필드 | 확인도 |
|---|---|---|
| Patient | pseudo ID (UID 가명), age range, sex | ★★ (카피 + DICOM 표준) |
| Study | studyID, study date (시프트), modality(study-level), description | ★★ |
| Series | seriesID, seriesNumber, seriesDescription, modality, imageCount | ★★★ (번들 직접 키 확인) |
| Instance | sopID | ★★★ (번들 키) |
| Pixel/제어 | scope, dimensions, blackout, photometricInterpretation, FrameOfReferenceUID | ★★★ (번들 키) |
| 진단/소견 | TBD: needs primary screenshot. 카피 "structured de-identified medical imaging data with reports" — radiology report 텍스트 노출 가능성 ★★★ (download 시 동봉 명시) |

**총 메타데이터 필드 (확인+추정)**: Patient 3 + Study 4 + Series 5 + Instance 2 + Pixel 5 + Report 1 ≈ **20+ 필드**. 정확한 노출 화면별 분포는 TBD.

#### A.2.3 Viewer

- **Cornerstone3D 직접 통합** (OHIF 아님). 번들 내 OHIF wrapper 문자열 미발견.
- **측정 도구**: RectangleROI 확인. 다른 ROI(Length, Angle, Ellipse) 도 가능성 높음.
- **MPR**: FrameOfReferenceUID 처리 코드 → MPR/3D 가능성.
- **`/v1/dicom_viewing/availability`** 사전 체크 endpoint → viewer 로딩 latency 가 인지될 만큼 무겁다는 신호. 첫 로딩 시 "Loading…" 상태 노출.

#### A.2.4 다운로드 CTA

공식 카피: **"directly download your dataset (complete with the DICOMs and associated radiology reports) from the Openda platform, or have your data piped to your cloud storage of choice"**

- **방식 1**: 직접 다운로드 (포털 내 zip/manifest 추정)
- **방식 2**: cloud-to-cloud pipe (S3/GCS/Azure Blob — buyer 의 bucket 으로 직접 push 추정)
- **포함물**: DICOMs + radiology reports (텍스트 첨부)

다운로드 카트 UX, presigned URL TTL 등 TBD.

#### A.2.5 Audit / Provenance

- **Buyer 화면에는 거의 노출 안 됨**. de-id 체인이 "Segmed Incognito" 마케팅 라벨로만 표현. 어느 단계에서 어떤 태그가 처리됐는지 buyer 는 모름.
- **`/v1/admin/blackout` `/v1/admin/dicomocr/`** 는 **admin 전용** → buyer 는 de-id 결과만 받음.
- **결정적 공백**: per-study provenance card (이 study 는 어느 hospital · 언제 ingest · 어떤 de-id revision · 어떤 audit hash) 의 부재.

#### A.2.6 관련 Study (Longitudinal)

- "group studies by patient" 은 **Openda 의 핵심 차별 카피**. Patient 단위 그루핑 후 시간순으로 study 나열 → Longitudinal 뷰가 기본.
- 단, 한 patient 가 여러 hospital 에 걸쳐 있을 때 어떻게 처리되는지는 TBD (Datavant 토큰화 의존 추정).

### 3.5 계정/대시보드 (A.3) — 공식 카피 기반

#### A.3.1 진입 모드

- 공식 솔루션 페이지 CTA: **"Try it now! Sign up is free"** (`solutions/openda` 푸터)
- **자가 가입 가능** 으로 확인. Auth0 가 인증. 단, free tier 의 데이터 접근 범위·다운로드 한도 TBD (가설: **검색 + viewer preview 만 free, download 는 결제·계약 필요**).
- "Book a Call" / "Contact Us" CTA 도 병행 — 엔터프라이즈 sales-led + 개발자 self-serve **하이브리드**.

#### A.3.2 API key

- 번들 직접 endpoint 는 admin path 와 dicom_viewing 만 노출 — public buyer API key 는 **별도 dev portal** 또는 enterprise 계약 후 발급 추정.
- API key UI 상세 (마스킹·rotation·usage) TBD.

#### A.3.3 Quota / Billing / Onboarding

- 모두 TBD: needs primary screenshot.

### 3.6 핵심 관찰 정리

| 영역 | Openda 가 잘하는 것 | Openda 의 공백 |
|---|---|---|
| 검색 | SNOMED 동의어 자동 확장, patient 그루핑·정렬 | 한국어/이중언어 미지원, ontology 가 SNOMED 만 (RadLex/ICD-10 별도 facet 인지 TBD) |
| 결과 표시 | 표준 DICOM 메타·sub-modality 다양 | per-hospital provenance row 노출 미확인 (집계 슬로건만) |
| Viewer | Cornerstone3D 직접 통합, MPR/ROI 가능 | viewer 로딩 무거움 (`/availability` pre-check 필요) |
| 다운로드 | 직접 + cloud pipe 양방향 | de-id chain 단계별 audit 노출 부재 |
| 진입 | self-serve sign-up 무료 | free → paid 전환 경로·가격 불투명 |
| 신뢰 | SOC 2 Type II + ISO 27001 + HIPAA + AWS | per-region 규제(GDPR/PIPA/PDPA) 약속 부재, audit log 시각화 부재 |
| 브랜드·시각 | 일관된 Tailwind blue-600, Inter, 12-col grid | Tailwind 디폴트 그대로 → **차별성 없음**, 한글 폰트 미정의 |

---

## 4. RadiVault vs Segmed Openda — 5축 비교

### 4.1 데이터 출처/지역

| 항목 | Segmed Openda | RadiVault |
|---|---|---|
| **출처** | 미국 위주 hospital network + 5 continents 집계 | 한국 의료기관 federated |
| **표시 단위** | 집계 (5 continents · 2,800+ sites · 150M studies) | per-hospital provenance (study row 마다) |
| **다양성 강조** | 지리적 다양성 (5 continents) | 인종·시스템 다양성 (Korean ethnicity · NHIS-covered 98% population · OECD-top hospital density) |
| **약점** | 한국·동아시아 데이터 sparse 추정. 지역별 rep. 약함 | 단일 국가 → 글로벌 representativeness 한계 |
| **강점** | 규모·범용성 | 특이성·한국 ethnicity 가치 (예: ARMD 동아시아 sub-type, 위암 imaging 등) |

**RadiVault 가 흡수**: 글로벌 표준 modality (PET/CT, PET/MR) 커버리지 카탈로그.
**RadiVault 가 따라가지 말 것**: "5 continents" 식 집계 슬로건. 우리는 **per-hospital provenance** 가 무기이므로 row 단위 노출.

### 4.2 컴플라이언스

| 항목 | Segmed Openda | RadiVault |
|---|---|---|
| **인증** | SOC 2 Type II + ISO 27001 + HIPAA + AICPA | (Phase 1) PIPA §28-8 compliant + HIPAA-aligned · (Phase 2) SOC 2 Type I · (Phase 3) SOC 2 Type II + ISO 27001 |
| **국외이전** | HIPAA Safe Harbor + Expert Determination 일반 (미국 → 글로벌) | **PIPA §28-8 native** — 한국 → 해외, "완전 익명정보" 예외 활용 |
| **per-region 약속** | 명문화된 약속 부재 (HIPAA 위주) | **한국 PIPA-native + GDPR aware (Phase 3) + 정통망법** |
| **약점** | 한국 시장 진입 시 PIPA 별도 대응 필요 | SOC 2 / ISO 미취득 (Phase 2~3 까지) |
| **강점** | 미국 buyer 에 대한 친숙도 | 한국 데이터·한국 buyer (병원 측) 양쪽에 native |

**RadiVault 가 흡수**: SOC 2 Type II 로드맵 가속 (Phase 2 우선).
**RadiVault 가 따라가지 말 것**: 일반 HIPAA 카피만 노출. **법령 Article 번호 + 한국 PIPC 가이던스 인용** 까지 깊이 노출.

### 4.3 익명화 (De-ID) chain

| 항목 | Segmed Openda | RadiVault |
|---|---|---|
| **표시 깊이** | "Segmed Incognito" 마케팅 라벨 + admin endpoint 만 (`/blackout`, `/dicomocr`) — buyer 는 단계 미확인 | **Zone 1/2/3 4-layer audit** (PHI tag 제거 → UID 재생성 → date shift → burn-in OCR → 3D defacing) + 각 단계 audit hash + buyer 화면 노출 |
| **Buyer-facing provenance** | **부재** | per-study card 에 "de-id revision X / audit hash Y / processed at Z" 노출 |
| **검증 가능성** | "trust our brand" 모델 | **technical proof** 모델 — pydeface/Orthanc/DCMTK 오픈소스 컴포넌트 명시 |
| **약점** | buyer 의 검증 욕구 좌절 가능성, regulator 입장 audit 어려움 | 운영 복잡도·UI 정보 밀도 |
| **강점** | 단순함 (buyer 는 "처리된 데이터만 받는다" 만 알면 됨) | 신뢰·재현 가능성 (FDA·MFDS submission 시 chain-of-custody 증명 가능) |

**RadiVault 가 흡수**: "de-id 가 끝났다" 의 명료한 success 신호 UI (Segmed 의 단순함은 강점).
**RadiVault 가 따라가지 말 것**: chain 을 숨기는 것. **per-study chain 노출이 우리 차별 포인트**. UI 디자인 결정 — 기본 노출 vs hover/expand 결정 필요.

### 4.4 Buyer 자격 / 진입

| 항목 | Segmed Openda | RadiVault |
|---|---|---|
| **진입 모델** | 하이브리드 — "Try it now! Sign up is free" + "Book a Call" 병행 | 현 dev-spec 은 **CLI-only API key 발급** + sales-led contact. Self-serve sign-up 미구현 |
| **Free tier** | 존재 (sign-up 무료, 다운로드 한도 TBD) | **미정** |
| **API key UX** | TBD (별도 dev portal 추정) | **reveal-once** (`buyer-portal-ux-competitive.md §9.2`) — Stripe 패턴 강화 |
| **약점** | free tier 가 어디까지인지 불투명 | sign-up 자체 미구현 → 첫 인상 약함 |
| **강점** | 개발자 진입 마찰 낮음 | **reveal-once + 마스킹** 보안 폴리시 우위 |

**RadiVault 가 흡수**: "Try it now! Sign up is free" CTA 자체. Self-serve preview-tier 까지는 안전 (raw image 다운로드는 계약 필요).
**RadiVault 가 따라가지 말 것**: free tier 의 가치를 모호하게 두는 것. **명확히 무엇이 free, 무엇이 contract 필요** 인지 표 노출.

### 4.5 데이터 modality 강점

| 항목 | Segmed Openda | RadiVault |
|---|---|---|
| **모달리티 폭** | CT/MR/XR/US/MG/PT/SPECT/Echo/DEXA + PET/CT + PET/MR (9+) | DICOM 표준 모두 지원 가능. 초기 파일럿 따라 다름 |
| **Multimodal** | imaging + report + claims (Datavant) + EHR + genomic 토큰화 통합 진행 중 | 현재 imaging + radiology report (Phase 2) 까지. EHR/claims 미통합 |
| **특화 데이터** | breast (DBT, Verily 통합), oncology longitudinal | **Korean-specific**: 한국인 polyp prevalence, 위암·간암 Korean cohort, 동아시아 안저 (DR/AMD), 한국 외상 imaging |
| **약점** | 한국 ethnicity 데이터 sparse | multimodal 통합 미성숙 |
| **강점** | 폭·깊이 양쪽 | Korean specialty + report 한국어 원문 (translation 부가가치) |

**RadiVault 가 흡수**: longitudinal patient view (Openda 핵심). 한 patient 의 시간순 study 트리.
**RadiVault 가 따라가지 말 것**: 모달리티 nine-fold 카탈로그 슬로건. 우리는 **specialty-first** (예: Korean breast / Korean liver / Korean retina 같은 **vertical** 카드).

---

## 5. 차별 포지션 권고

### 5.1 "RadiVault 가 Segmed 가 아닌 이유" — 한 줄 메시지 5 후보

| # | 영문 (1줄) | 한글 (1줄) | 강점 | 리스크 |
|---|---|---|---|---|
| **M1** | "Per-slice provenance, not per-continent slogans." | "대륙 단위 슬로건이 아니라, 슬라이스 단위 공급원." | 검증 가능성 강조 | "slice" 어휘는 일반 buyer 에 다소 기술적 |
| **M2** | "Korean medical imaging — built for PIPA §28-8, delivered in 48 hours." | "한국 의료영상 — PIPA §28-8 위에서, 48시간 내 전달." | 법적 차별 + 메트릭 | 외국 buyer 에 PIPA 모호 |
| **M3** | "See every de-id step. Trust the chain, not the brand." | "익명화 한 단계 한 단계가 보입니다. 브랜드가 아니라 체인을 신뢰하세요." | de-id 차별 + 신뢰 메시지 | 약간 길다 |
| **M4** | "The specialized vault for Korean imaging — not a marketplace, a curated archive." | "한국 의료영상 전용 vault — 마켓이 아닌 큐레이션된 아카이브." | 카테고리 점유 (vault) | "vault" 는 RadiVault 브랜드 자체 |
| **M5** | "Self-serve preview, contract-grade delivery." | "셀프서브 프리뷰, 계약 기반 본배송." | hybrid 진입 명확화 | "contract-grade" 는 새 어휘 |

**권고 우선순위**: **M3 > M1 > M4** (de-id 차별이 시각적으로도 가장 차별점이 크고, marketing 카피로 변환하기도 쉬움). M2 는 한국 페이지 전용 hero subhead.

### 5.2 Visual / UX 차별 — Segmed 와 다르게 보이게 만드는 5 요소

| # | Segmed 가 하는 것 | RadiVault 가 다르게 할 것 |
|---|---|---|
| **V1 색상** | Tailwind blue-600 (`#2563EB`) 디폴트, blue 단일 톤 | **deeper navy or teal-shifted blue** (예: `#0D2A5C` 네이비 + `#14B8A6` 한국 페이지 액센트). **절대 `#2563EB` 회피**. |
| **V2 폰트** | Inter var (영문 only) | **Inter (영문) + Pretendard (한글) 듀얼**. 한글 페이지에서 한글이 1급 시민. |
| **V3 레이아웃** | 12-column SearchUI 표준 (좌 facet sidebar + 중앙 결과 + 우측 미리보기) | **3-pane 유지하되 좌측 facet 을 collapsible group 으로 재편**. Segmed 가 horizontal pill 이라면 우리는 **vertical accordion + group label 한·영 병기**. |
| **V4 데이터 시각화** | 차트·시각화 약함 (검색 위주) | **per-hospital sparkline + de-id chain timeline + Korean choropleth**. 데이터 시각화로 즉시 차별. |
| **V5 인터랙션 패턴** | "marketplace" feel — 결과 카드는 통일된 stub, 중앙 sales 게이트 | **"specialized vault" feel** — 결과 row 마다 chain-of-custody 작은 stamp + hospital pseudo-brand badge. **물리적 archive 느낌의 절제된 인터랙션**. |

### 5.3 데이터 표시 차별 — Segmed 가 보여주지 않는 것 / 우리만 보여줄 수 있는 것

| # | 정보 | 위치 | 근거 |
|---|---|---|---|
| **D1** | **per-hospital provenance** (hospital pseudo-ID + region) | 결과 row + 상세 헤더 | Openda 는 "5 continents" 집계만 — row 단위 노출 미확인 |
| **D2** | **de-id chain step-by-step** (PHI tag 제거 → UID 가명 → date shift → burn-in OCR → 3D defacing) + 각 단계 audit hash | 상세 페이지 우측 사이드 또는 expandable card | Openda admin endpoint 만 존재, buyer 미노출 |
| **D3** | **PIPA consent provenance** ("이 study 는 hospital A 의 IRB 승인 #YYYY-NN 하에 broad consent 로 수집") | 상세 카드 | Openda 는 consent 정보 노출 미확인 |
| **D4** | **한국어/영어 동시 표시** (radiology report 한국어 원문 + 영어 자동 번역 + LLM annotation) | 상세 본문 | Openda 는 영어 단일 |
| **D5** | **한국 의료 표준 코드** (KCD-8 진단 코드, MoH 진료과 분류, 보험 type — 급여/비급여/실손) | facet + 상세 메타 | Openda 는 SNOMED 위주 — KCD/MoH 미지원 추정 |

### 5.4 포지셔닝 한 줄 (RadiVault tagline 후보 3 개)

**영문 후보**:

1. **"The compliance-native vault for Korean medical imaging."**
2. **"Per-slice provenance. Per-region compliance. Built in Korea, delivered to global AI."**
3. **"Open the vault, see the chain."**

**한글 후보**:

1. **"한국 의료영상의 컴플라이언스-네이티브 vault."**
2. **"슬라이스 단위 공급원, 지역 단위 컴플라이언스. 한국에서 만들어, 세계 AI 에 전달합니다."**
3. **"Vault 를 여세요, 체인이 보입니다."**

**권고**: 영문 #1 + 한글 #1 페어. "compliance-native" 가 Segmed 의 일반 SOC2/HIPAA 와 어휘 차별. "vault" 는 브랜드 강화.

---

## 6. 디자이너 directives — mockup v2 가 따라야 할 10 가지

> 이 섹션이 **본 리서치의 가장 실용적 산출물**. @designer 가 다음 mockup 작성 시 1:1 체크리스트로 활용.

### Don't (절대 하지 마라)

| # | 안 하는 것 | 이유 |
|---|---|---|
| **DON'T-1** | **메인 컬러 `#2563EB` (Tailwind blue-600) 사용 금지** | Segmed primary 와 hex 일치 → 즉시 클론 인상. RadiVault buyer blue 토큰을 darker navy / teal-shift 방향으로. |
| **DON'T-2** | **horizontal pill chip 으로 facet 을 깔지 말 것** | Tailwind/SearchUI 디폴트, Segmed 도 동일. 좌측 vertical accordion 으로 차별. |
| **DON'T-3** | **헤더 슬로건에 "5 continents", "150M studies" 식 집계 수치 흉내 금지** | (1) 우리는 그 규모 아님, (2) 따라하면 카피캣. 우리는 **specialty + per-hospital provenance** 로 가야 함. |
| **DON'T-4** | **결과 카드를 통일된 stub 으로 만들지 말 것** | Openda marketplace 정석. 우리는 **row 마다 hospital badge + chain-of-custody mini stamp** 로 specialized vault 느낌. |
| **DON'T-5** | **Inter 영문 단일 폰트 적용 금지** | Segmed 의 영문 전용 한계. **한글 페이지는 Pretendard 1급**, 한국어가 번역투가 아니라 native 가 되도록. |

### Do (이렇게 해라)

| # | 하는 것 | 이유 |
|---|---|---|
| **DO-1** | **결과 row 에 hospital pseudo-brand badge (예: "H-A1", "H-A2", region tag) 노출** | Segmed 가 못 하는 per-hospital provenance 시각화. opt-in 병원만 실명 노출, 나머지는 anonymized badge + region. |
| **DO-2** | **상세 페이지 우측에 "De-ID Chain" 영구 사이드 (4~5 단계 stepper + 각 단계 hash 해시 4자 prefix)** | de-id chain 차별을 매 페이지에서 보이게. Openda 가 admin only 로 숨긴 것을 우리는 buyer first 로 전진 배치. |
| **DO-3** | **검색 입력은 SNOMED + KCD + RadLex 트리플 ontology 자동완성** (Openda 는 SNOMED only) | ontology 폭을 늘려 임상 친숙도 높임. 한국어·영어 토글로 "협심증 / Angina pectoris / I20" 동시 표시. |
| **DO-4** | **Patient grouping + longitudinal timeline 도입** (Openda 가 잘하는 패턴 흡수) | "study 만 보이는 검색" 에서 "patient 의 시간 축이 보이는 검색" 으로 격차 좁히기. |
| **DO-5** | **풋터·헤더에 PIPA §28-8 + SOC 2 status badge 강한 노출 + Trust Center 링크** | Segmed Trust Center (Vanta 호스팅) 패턴 답습. **"in preparation" 보수 어투** 유지하되 위치는 전진 배치. |

---

## 7. 시사점 (RadiVault 에의 함의)

### 7.1 PRD / ARCHITECTURE 갱신 제안 (직접 수정 금지 — 제안만)

- **PRD §3 가치 제안**: "한국 다양성" 을 보다 구체화 — Korean ethnicity / KCD / MoH 진료과 / 보험 type 4 가지 specialty 를 노출. 현 PRD 는 "한국 다양성 데이터" 한 줄에 그침.
- **PRD §4.3 구매자 포털**: "self-serve preview tier + contract-grade download tier" 분리 명문화. 현재 Phase 2 로 단일 전제.
- **ARCHITECTURE §4.7 Audit Log**: "buyer-facing chain-of-custody view" 추가 항목으로 명시. 현재는 "WORM 보관" 만 있고 buyer UI 표면화 가 빠짐.
- **ARCHITECTURE §5.1 Web Portal**: viewer 후보를 "Cornerstone.js 또는 OHIF" 로 두었으나, **Cornerstone3D 직접 통합** 이 Segmed 와 동일 선택지 — RadiVault 도 같은 선택 시 wrapper layer 에서 차별 (예: defacing preview 토글, chain audit toolbar) 필요. dev-spec 단계 결정.

### 7.2 mockup v2 작성 단계의 결정 포인트 (Kyle 결정 필요)

1. **메인 색상 — navy 셰이드 vs blue-teal 듀얼 vs 기존 buyer blue 유지**. 본 리서치는 navy / teal-shift 권고. Kyle 최종 컨펌 필요.
2. **결과 row 에 hospital badge 노출 여부** — 운영상 opt-out 가능성 (병원이 "익명 badge 도 거부" 할 수 있음). Phase 1 은 region-level 만, hospital-level 은 opt-in 후 v0.2 확장 권고.
3. **De-ID chain 사이드 — default 노출 vs collapse 시작** — 정보 밀도 vs 첫 인상 단순함 사이 trade-off. 본 리서치는 default 노출 권고 (차별 핵심).
4. **Self-serve sign-up 도입 시점** — Phase 1 에 include vs Phase 2 까지 sales-led 만. 본 리서치는 Phase 1 에 **preview-tier sign-up only** (검색·viewer preview 까지, download 는 contract) 권고.

### 7.3 후속 에이전트 핸드오프

- **@designer mockup v2** — 본 §6 의 10 directive + §5 의 컬러·폰트 결정 + §3 의 Segmed 화면 분석을 1:1 참조.
- **@planner — 추가 dev-spec 후보**:
  - `dev-spec-buyer-self-serve-signup.md` — preview tier 가입·인증·tier 분리
  - `dev-spec-deid-chain-buyer-view.md` — buyer-facing chain-of-custody UI + audit hash 노출
  - `dev-spec-ontology-search-snomed-kcd-radlex.md` — 트리플 ontology 자동완성

---

## 8. 한계 · 오픈 퀘스천

### 8.1 본 리서치의 한계

1. **로그인 후 화면 직접 분석 불가** — Kyle 의 직접 스크린샷이 핵심 보강 자료. 본 문서의 A.1~A.3 다수 항목 "TBD: needs primary screenshot".
2. **Openda 의 "free tier" 실제 한도 미확인** — sign-up 만 free 인지, viewer preview 까지 free 인지, download 도 일부 free 인지 미확인.
3. **Openda 의 facet 정확한 카테고리 수 미확인** — 마케팅 카피로 4개 확인, 추정 2~4 추가, 총 6~8 추정.
4. **per-study row 에 hospital 표시 여부** — 본 리서치 결정적 차별 포인트. Kyle 의 직접 확인 필요.
5. **Openda 의 가격 모델** — per-study / per-cohort / subscription / volume tier 어느 것인지 공개 자료 zero. 영업 자료 NDA 필요.

### 8.2 추가 조사 필요

- **Openda admin 콘솔 (`/v1/admin/*` 경로)** — buyer 가 보지 못하는 것을 운영자는 어떤 UI 로 보는지. 본 리서치 범위 외.
- **Segmed Incognito (de-id 제품) 단독 분석** — 기술 스펙 공개 자료 분석. 별도 task.
- **Segmed Piper (data ingestion 제품) 단독 분석** — Gateway Agent 비교용. 별도 task.
- **Gradient Health Atlas vs Segmed Openda 직접 비교** — 두 marketplace 의 UX 차이.
- **NDA 후 demo 미팅** — Kyle 이 sales 잡으면 1차 화면 캡처 + audit feature 직접 확인.

### 8.3 법률 자문 플래그

- 본 문서는 법률 자문이 아니다. PIPA §28-8 인용·"compliance-native" 카피·"chain of custody" claim 모두 **외부 변호사 재검증 필요**.
- "Segmed" 명시적 비교광고 어투는 한국 표시광고법 비교광고 가이드라인 관점에서 leave-behind 배포 시 재검토 필수. 본 문서는 내부 리서치 한정.

---

## 9. 출처 목록

### 9.1 1차 (Segmed 직접)

- Openda 홈: https://openda.segmed.ai/
- Openda JS 번들: https://openda.segmed.ai/static/js/main.18d2d2be.js
- Openda CSS 번들: https://openda.segmed.ai/static/css/main.db5bc966.css
- Openda robots.txt: https://openda.segmed.ai/robots.txt
- Segmed 메인: https://www.segmed.ai/
- Segmed Openda 솔루션: https://www.segmed.ai/solutions/openda
- Segmed AI/Medical Devices: https://www.segmed.ai/solutions/for-medical-devices-and-ai-rd
- Segmed Data Management: https://www.segmed.ai/solutions/for-data-management
- Segmed Security & Compliance: https://www.segmed.ai/security-compliance
- Segmed Trust Center (Vanta): https://trust.segmed.ai/
- Segmed About: https://www.segmed.ai/about-us

### 9.2 1차 (Segmed PR / 파트너십)

- 2024-07-01 Openda 런칭 PR: https://www.prnewswire.com/news-releases/segmed-unveils-new-brand-identity-and-introduces-openda-the-next-evolution-for-its-insight-platform-302185953.html
- Verily 파트너십 (2026-02-25): https://www.prnewswire.com/news-releases/segmed-partners-with-verily-to-expand-access-to-real-world-imaging-data-302696323.html
- Datavant 파트너십: https://www.datavant.com/press-release/segmed-datavant-team-provide-deeper-patient-insights-advanced-imaging-data-integration
- Bayer 파트너십: https://www.prnewswire.com/news-releases/segmeds-real-world-imaging-data-solution-to-be-integrated-into-bayer-platform-to-accelerate-the-development-of-ai-powered-healthcare-solutions-302318341.html
- $10.4M Series A (iGan Partners + Advocate Health): https://www.prnewswire.com/news-releases/segmed-secures-10-4-million-series-a-funding-led-by-igan-partners-and-advocate-health-302236032.html
- RSNA 2025 Segmed 부스 정리 (Medium): https://medium.com/@segmed01/segmed-rsna-2025-39f9c77cf57c

### 9.3 1차 (한국 PIPA / 의료 AI 규제)

- IAPP — South Korea pseudonymization & AI: https://iapp.org/news/a/pseudonymization-as-a-gateway-to-ai-data-use-korea-s-emerging-privacy-governance-model
- Baker McKenzie — PIPC AI 가이드라인 2025: https://connectontech.bakermckenzie.com/south-korea-sets-ai-standard-pipcs-guidelines-for-generative-ai-present-obligations-opportunity/
- TJC Group — PIPA 가이드: https://www.tjc-group.com/blogs/data-privacy-law-a-guide-to-south-koreas-pipa-regulation/
- ICLG — Digital Health Korea 2026: https://iclg.com/practice-areas/digital-health-laws-and-regulations/korea
- Didomi — PIPA 개요: https://www.didomi.io/blog/south-korea-pipa-everything-you-need-to-know

### 9.4 2차 (관련 기술·Cornerstone3D / OHIF)

- OHIF Viewers: https://github.com/OHIF/Viewers
- OHIF docs: https://docs.ohif.org/
- OHIF v3.9 + Cornerstone3D 2.0 release: https://ohif.org/newsletters/2024-11-15-ohif%20viewer%203.9%20with%20cornerstone3d%202.0%20and%203d%20labelmaps--release-note3p9

### 9.5 내부 RadiVault 참조

- `docs/research/portal-redesign-competitive-analysis.md` — 15 사이트 시각·브랜드 분석
- `docs/research/buyer-portal-ux-competitive.md` — 포스트-로그인 UX
- `docs/research/demo-pitch-references-radivault.md` — 데모 연출
- `docs/research/k-meddata-research-summary.md` — 시장·규제 배경
- `docs/marketing/competitive-positioning-buyer-en.md` — 경쟁사 vs RadiVault 포지셔닝
- `docs/marketing/one-pager-buyer-global-en.md` — 영문 마케팅 어투 앵커
- `docs/specs/design-spec-buyer-portal-demo.md` — 현 portal 디자인 스펙

---

## 10. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|---|---|---|---|
| 0.1 | 2026-04-25 | @researcher (Claude Opus 4.7, 1M context) | 최초 작성. Openda JS/CSS 번들 직접 분석 (★★★ confirm 항목 다수) + 마케팅 카피 분석 + 5축 비교 + 디자이너 directive 10개 + tagline 후보 3쌍. mockup v2 직접 입력. |

---

**Disclaimer**: 본 문서는 법률 자문이 아니다. PIPA §28-8 / HIPAA / "compliance-native" / 비교광고 어투는 모두 Kyle + 외부 변호사 재검증 필수. 경쟁사 이름·hex 색상·기술 스택 인용은 객관적 관찰 한도 내이며, 외부 배포·마케팅 자료 활용 시 표시광고법 비교광고 규정 관점에서 사전 검토 필요.
