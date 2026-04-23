# Buyer Portal Web UI — Competitive UX Research

> **Status**: Draft v0.1
> **작성일**: 2026-04-24
> **작성자**: @researcher (Claude Opus 4.7)
> **근거 요청**: Kyle — RadiVault Buyer Portal MVP(웹 UI) 2~3주 스코프 확정을 위한 경쟁사 UX 레퍼런스 수집 (대표님/병원 경영진 데모용).
> **선행 리서치**: [`metadata-index-technical-foundations.md` §4.7](./metadata-index-technical-foundations.md) — 이 문서는 API UX(Gradient/Segmed/TCIA/OpenNeuro REST·GraphQL 계약)를 비교했음. **본 문서는 웹 UI UX에만 집중**하여 중복 회피.
> **톤·용어 일관성 앵커**: [`one-pager-buyer-global-en.md`](../marketing/one-pager-buyer-global-en.md), [`order-flow-quickstart-buyer-en.md`](../marketing/order-flow-quickstart-buyer-en.md) — "in preparation"·"aligned with" 등 보수적 컴플라이언스 어투 유지.

---

## 0. TL;DR

1. **경쟁사 웹 UI의 공통 패턴은 "Gen3 스타일 왼쪽 패싯 + 중앙 결과 + 오른쪽 cohort 카트"**. TCIA·MIDRC·IDC가 모두 같은 3-pane 레이아웃. Segmed/Gradient도 유사 (공개 스크린샷 한정 추정). RadiVault가 이 패턴을 채택하면 **2주 내 "전문가용"으로 즉시 인식**됨.
2. **DICOM 뷰어 통합은 MVP 스코프 밖 강력 권고**. OHIF 임베드 자체는 1일 작업이지만, 완전 익명화된 프리뷰 DICOM을 별도 Zone 2 bucket에 준비하는 파이프라인이 아직 없음. Buyer-facing 샘플 프리뷰는 **v0.2 Flow C(Hot Storage 자동 promotion)와 함께 묶어서** 릴리즈.
3. **"Wow" 화면은 데이터 규모 카운터와 지도(한국 행정구역 히트맵)**. IDC 포털이 "161 Collections, 79,889 Cases" 같은 실시간 카운트를 타일로 노출; Gradient Atlas 2는 "20M studies, 30M in progress" 같은 숫자를 마케팅 톱-라인으로 사용. 대표님/경영진 데모엔 **숫자 카운트 + 한국 지도 + 최근 주문 라이브 피드** 3요소가 가성비 최고.
4. **주문 상태 UI는 Shopify 스타일 6-step 스텝퍼 권장**. 우리 12-state FSM을 그대로 노출하면 구매자가 "왜 상태가 이렇게 많냐"로 혼란. 내부 FSM → buyer-facing 5~6 단계로 접는 **state-to-phase 매핑**을 UI 레이어에서 해야 함.
5. **DUA 동의는 주문 생성 시 체크박스 + MSA_hash 자동 채움**. 클릭랩 단일 방식이 업계 관행. 전자서명(DocuSign)은 MSA 1회성이면 외부 시스템으로 분리 권고.

---

## 1. Scope

### 1.1 범위
- **대상**: Buyer(구매자)가 브라우저에서 접근하는 웹 UI. 병원 대시보드는 §12에서 별도 논의.
- **제외**: API UX·SDK·CLI. 이들은 선행 리서치([`metadata-index-technical-foundations.md` §4.7](./metadata-index-technical-foundations.md), [`order-fulfillment-technical-foundations.md`](./order-fulfillment-technical-foundations.md) §7)에 이미 정리.
- **관심 영역**: 검색·필터·카드·상세·장바구니·상태 추적·다운로드·공통 shell·데모 장면.

### 1.2 조사 방법
- 공개 제품 페이지(랜딩, 블로그, 사용자 가이드), 업계 프레스릴리스, 학술 논문 초록, 경쟁사가 공개한 스크린샷/캡처(대부분 마케팅 자료 1~2장 수준).
- 플랫폼 10종 중 **직접 로그인 가능한 것은 공개 포털 3종(TCIA, MIDRC, IDC)만**. 상용(Segmed Openda, Gradient Atlas, Flywheel)은 NDA/미팅 요구 → **공개 UI 문구·블로그·프레스 릴리스 + 추정** 표시.
- 일반 B2B SaaS 대시보드 패턴(shadcn/ui·Vercel 템플릿·Stripe Customer Portal)과 클래식 데이터 마켓플레이스(AWS Data Exchange, Snowflake Marketplace)를 **인접 산업 레퍼런스**로 활용.

### 1.3 한계
- Segmed Openda의 실제 로그인 후 화면은 **확인 불가**. blog/press release 기반 서술에는 "추정" 라벨.
- 경쟁사 UI는 분기별로 변함 → 본 문서는 2026-04-24 시점 스냅샷.
- 이 문서는 법률 자문이 아니다. DUA UX 패턴의 법적 유효성은 Kyle + 외부 변호사 확인 필요.

---

## 2. Competitor inventory

### 2.1 접근 가능성 매트릭스

| # | 플랫폼 | 타입 | 공개 로그인 | 공개 스크린샷 | 문서 접근 | RadiVault 유사성 |
|---|--------|------|-----|------------|---------|----------|
| 1 | **Segmed Openda** | 상용 B2B | 요청 기반 | 제한적 (블로그 내 1~2장) | 블로그만 | ★★★★★ 직접 경쟁 |
| 2 | **Gradient Health Atlas 2** | 상용 B2B | 요청 기반 + GCP Marketplace | 제한적 (Atlas 제품 페이지) | 블로그·프레스 | ★★★★★ 직접 경쟁 |
| 3 | **NIH TCIA Radiology Portal** | 공공 무료 | 공개 | 사용자 가이드 wiki 풍부 | 완전 공개 | ★★★★ 기능 레퍼런스 |
| 4 | **NIH IDC** | 공공 무료 | 공개 | 사용자 가이드 풍부 | 완전 공개 | ★★★★ 기능 레퍼런스 |
| 5 | **RSNA MIDRC** (Gen3) | 공공 무료 | 공개 | 스크린샷·노트북 데모 | 완전 공개 | ★★★ Gen3 템플릿 참고 |
| 6 | **OpenNeuro** | 공공 무료 | 공개 | 공개 | 공개 (docs.openneuro.org) | ★★ 학술 포커스 |
| 7 | **UK Biobank Showcase** | 컨트롤 액세스 | 승인 필요 | 공개 | 공개 | ★ 옛 UI, 반면교사 |
| 8 | **NIH All of Us Researcher Workbench** | 컨트롤 액세스 | 승인 필요 | 공개 튜토리얼 | 공개 | ★★ 컨트롤드 액세스 참고 |
| 9 | **AWS Data Exchange** | 상용 데이터 마켓 (인접 산업) | AWS 계정 | 공개 (AWS 콘솔) | 공개 | ★★ 구독·카트 패턴 |
| 10 | **Snowflake Marketplace** | 상용 데이터 마켓 (인접 산업) | Snowflake 계정 | 공개 | 공개 | ★★ 리스팅 페이지 패턴 |
| 11 | **Flywheel** | 연구기관 imaging PaaS | 고객사만 | 매우 제한적 | 일부 공개 | ★★ 기능 레퍼런스 |

### 2.2 공통 아키텍처 관찰

- **Gen3 계열(MIDRC, IDC)**: 좌측 필터 패싯(숫자 오벌 뱃지) · 중앙 결과 테이블/차트 토글 · 우측 Cohort Summary + "Manifest 다운로드" 버튼. 오픈소스 기반이라 **무료로 참고 가능한 UI 템플릿**.
- **상용 마켓(Segmed/Gradient)**: 대시보드 → 검색 → 코호트 저장 → Export 로 흐름은 동일. **차이점은 심미성·비즈니스 대시보드(예: 이전 주문, 유저 그룹)·지원 티켓 통합**.
- **공공 포털(TCIA/OpenNeuro)**: 검색 + 무료 다운로드. 빌링·계약 컴포넌트 없음. RadiVault는 **TCIA 검색 UX + Gradient 비즈니스 shell** 조합이 목표.

---

## 3. 검색·필터 UI 패턴

### 3.1 Common pattern

**좌측 패싯 필터 패널 + 중앙 결과 + 상단 검색 입력** 레이아웃. TCIA/MIDRC/IDC 3종 모두 이 구조.

- **필터 카테고리 순서 (경쟁사 공통 빈도순)**:
  1. Modality (CT·MR·CR·MG·US·XA·DX)
  2. Body part examined / Anatomy
  3. Collection / Source / Dataset name
  4. Patient sex
  5. Patient age (범위 슬라이더 혹은 10년 단위 버킷)
  6. Date released / Study date (범위)
  7. Manufacturer
  8. Diagnosis / Disease (ICD-10 또는 자유 텍스트)
- **패싯 카운트 표시**: 필터 라벨 옆 회색 타원(oval badge) 안에 숫자. 예: `CT (12,478)`. IDC가 "grayed ovals next to the search filters" 명문화.
- **활성 필터 칩**: 상단에 `modality=CT ×` `body_part=CHEST ×` 형태 dismissible chip. 초기화는 "Clear all" 링크.
- **결과 카운트**: 상단에 `12,478 studies across 94 collections` 고정 표시. 필터 변경 시 실시간 업데이트.
- **검색 입력창**: 상단 하나 + 상세 모달("Advanced Search"). TCIA는 Simple/Advanced/Dynamic 3 모드를 탭으로 분리하나 이는 과하다(권고 — §3.3).

### 3.2 Variations

| 플랫폼 | 특징 | 관찰 |
|--------|-----|------|
| **TCIA** | 3 탭 (General / Patients / Images), Result Charts 파이 차트 (각 조각 = 추가 필터) | 파이 차트 기능은 "wow" 요소 — BI 도구 같은 인상. Gen Z 인턴 취향. |
| **IDC** | Search Scope / Filter Definition / Search Configuration / Collections 4 패널 | 과도한 중첩, 학습 곡선 가파름 — RadiVault는 피해야 함 |
| **MIDRC (Gen3)** | Explorer 페이지, 시각적 공간 분배 균형 좋음 | 오픈소스라 **RadiVault v0.1 레이아웃 1:1 벤치마킹 가능** |
| **OpenNeuro** | 검색창 + 태그 · 정렬 옵션. 데이터셋 단위라 modality 대신 task 필터 | 학술 UX. B2B 바이어에게는 "캐주얼해 보임" |
| **UK Biobank** | 2000년대 UX. 드롭다운 + 년도 범위 2 필드. | 반면교사. 카운트 없고 패싯 없음. "우리가 이것보다 낫다" 증명 쉬움. |
| **Gradient Atlas 2** | "Filter across hundreds of DICOM tags", "Saved searches" 기능 강조 | DICOM 태그 전수 노출은 **전문가 타겟**의 차별화. RadiVault v0.1은 5~8 필드로 시작, v0.1.1에 태그 기반 확장 고려. |
| **Segmed Openda** | "Dynamic SNOMED term dropdown"으로 진단명 동의어 자동 포함 (블로그 주장) | NLP 라벨 엔진(v0.2)의 미래 UX 힌트 |
| **Snowflake Marketplace** | "카테고리 + 필터" 좌측, 리스팅 카드 중앙 | 데이터 도메인(Healthcare, Finance) 카테고리 내비. RadiVault v0.1은 데이터 "종류"가 하나이므로 생략 가능. |

### 3.3 Cohort preview (결과 샘플링)

- **TCIA**: 검색 후 Collection→Patient→Study→Series 트리로 계층 탐색. 각 시리즈에 썸네일 + OHIF animation.
- **IDC**: 결과 테이블 + 썸네일 컬럼. **"i" 버튼**으로 개별 항목 정보 모달.
- **Segmed Openda**: 블로그 상 "group by patient, then sort by date/modality/body part" — 환자 단위 묶음 정렬이 기본.
- **Gradient Atlas 2**: "Instant image previews" + "built-in visual analytics tools to assess diversity" — 연령·성별 분포 차트를 **검색 결과 페이지 내**에 bar/pie로 노출.

**RadiVault 적용 권고 (§3)**:
- **v0.1 MVP**:
  - 좌측 패싯: modality · body_part · sex · age_bucket · study_year · manufacturer · hospital_group (6~7 필드).
  - 각 필터 옆 회색 배지 카운트.
  - 상단 활성 필터 칩 (dismissible), "Clear all".
  - 결과 카운트 `N studies across M hospitals` — **min_hospitals**(single-site bias 가드)를 원페이지에 보여주면 `one-pager-buyer-global-en.md §4` 문구와 정확히 일치 → 마케팅 일관성.
- **v0.1 제외**:
  - 파이 차트 / 시각 분석 (v0.1.1).
  - Advanced Search 모달 (v0.1.1).
  - Saved searches (v0.1.1).
  - SNOMED 자동 동의어 (NLP v0.2 이후).
- **기술 레버리지**: 이미 metadata-index의 `/v1/search/studies/facets` 엔드포인트가 **GROUP BY 화이트리스트 6 필드를 반환** ([`dev-spec-metadata-index.md` §FR-9](../specs/dev-spec-metadata-index.md))하므로 프론트는 fetch → 렌더만 하면 됨.

---

## 4. 결과 리스트·카드 디자인

### 4.1 Common pattern

**의료영상 마켓플레이스는 "Study 카드"를 쓰지 않는다**. 이유: (a) 썸네일 1장이 대표성 없음(한 study는 수십~수백 인스턴스), (b) PHI 리스크로 평문 썸네일 어려움. 대부분 **테이블 뷰가 디폴트**.

- **테이블 컬럼 (경쟁사 공통)**:
  - Study ID (opaque, 우리 경우 `pseudo_study_uid` 잘린 형태)
  - Modality 배지
  - Body part
  - Instance 수 (files)
  - Size (MB/GB)
  - Study date (yyyy-MM, shift 후 연월만)
  - Hospital (opaque alias; 우리는 anonymized_code `H001` 등)
  - 체크박스 (cart add)

### 4.2 Variations

- **TCIA**: 계층 테이블 (Collection > Patient > Study > Series > Images). 다단계 펼침. **정밀하지만 과함** — B2B 바이어에겐 학술 포털 인상.
- **IDC**: 플랫 테이블 + 썸네일 컬럼 + 계층은 상세 페이지로.
- **OpenNeuro**: 카드 뷰 (데이터셋 단위). Summary card 메타: participants·modalities·tasks.
- **Gradient Atlas 2**: "instant image previews" (썸네일 + 호버 팝업 추정). 커리큘럼 데이터는 "사전 검토된 익명" 전제로 썸네일 노출.
- **AWS Data Exchange**: 리스팅 카드(데이터 제공자 로고 + 제목 + 카테고리 뱃지 + "Subscribe" 버튼).

### 4.3 썸네일 없이 시각성 확보

- **Modality 배지 색상 코딩**:
  - CT = 파랑, MR = 보라, CR/DR = 초록, MG = 분홍, US = 주황, PT = 빨강 (경쟁사 관례 대략).
- **미니 차트**: 카드 한쪽에 sparkline (이 코호트의 연령 히스토그램 등). Gradient의 "visual analytics"가 이 방향.
- **크기·밀도 아이콘**: GB 수치를 bar로.

### 4.4 리스트 vs 그리드 토글

- IDC·TCIA: 테이블만.
- Segmed Openda (블로그 표현): "group by patient then sort" — 테이블 확장 모드.
- Snowflake Marketplace: 그리드 디폴트.

**RadiVault 적용 권고 (§4)**:
- **v0.1 MVP**: 테이블 뷰 단일. 리스트/그리드 토글 없음. 컬럼 6개: check · pseudo_study_uid(8자 잘림) · modality(색 배지) · body_part · n_instances · size_mb · study_year(shift된 연도만). **썸네일 컬럼 없음** (MVP 스코프; §11 참조).
- **v0.1.1**: 호버 시 연령/성별 마이크로 차트.
- **v0.2**: Gradient 스타일 aggregate analytics 패널 (filter 변경 시 age pyramid 업데이트).
- **의도적 차별화**: 테이블 디자인을 **shadcn/ui DataTable** (TanStack 기반)으로 구현하면 정렬·페이지네이션·선택 상태가 무료. 2주 스코프 내 실현 가능.

---

## 5. 스터디 상세 페이지

### 5.1 Common pattern — "상세 페이지"의 존재 여부는 제품 종류에 따라 다름

| 플랫폼 | 상세 페이지 유무 | 섹션 구성 |
|--------|--------------|---------|
| **TCIA** | △ (계층 테이블로 대체) | Series 선택 시 우측 패널에 DICOM header 미리보기 |
| **IDC** | ○ Case 페이지 | 환자 메타 · 모든 studies/series · 뷰어 링크 |
| **Segmed Openda** | ○ (추정) | group-by-patient 확장 |
| **Gradient Atlas** | ○ | 메타 + 리포트 텍스트(익명화) + 썸네일 |
| **OpenNeuro** | ○ Dataset 페이지 | BIDS 구조 · participants.tsv · README · versions |
| **Snowflake Marketplace** | ○ 리스팅 페이지 | 프로바이더·업데이트 주기·샘플·라이센스·스키마 |

### 5.2 DICOM 뷰어 통합 사례

- **TCIA**: 공식 OHIF Viewer 임베드 — 시리즈 thumbnail 클릭 시 새 탭에 OHIF 로드. 무료 공개 데이터이므로 가능.
- **IDC**: 자체 "IDC Viewer" + "IDC SliM Viewer" (병리). Cornerstone.js 기반 추정.
- **MIDRC**: 공식 뷰어는 없음 (cohort export → 로컬 viewer 사용).
- **Segmed/Gradient**: **Buyer-facing 뷰어 공개 확인 불가**. 구매 전 미리보기는 "썸네일 + 리포트 요약" 수준으로 추정 (PHI 노출 위험 때문).

### 5.3 판독문 / 라벨 미리보기

- **TCIA**: 리포트 없음 (메타만). 대신 Annotations/Segmentations 데이터셋 별도 제공.
- **Gradient Atlas**: "keyword search on radiological report" 주장 — 리포트 검색은 되지만 **원문 노출은 익명화 레벨에 따라 다름** (확인 불가).
- **Segmed Openda**: FHIR + DICOMweb 기반 — 리포트는 FHIR DocumentReference로 제공 추정.
- RadiVault 현 상태: **리포트 NLP 라벨 엔진은 Phase 2(PRD §4.2)에 계획, v0.1에선 메타만**. 리포트 미리보기는 v0.2+ 결정 사항.

### 5.4 "샘플 다운로드" vs "전체 주문" 구분

- **Gradient Atlas**: CSV download of metadata + radiological report = 무료 샘플. DICOM 실 파일은 "Export" 후 cohort 단위로 결제.
- **Segmed Openda**: 블로그상 불명확. 전체 주문 중심.
- **TCIA/IDC**: 전체가 무료이므로 구분 없음.
- **OpenNeuro**: 전체 무료.

**RadiVault 적용 권고 (§5)**:
- **v0.1 MVP**: 상세 페이지 **최소 구성**.
  - 섹션 1: 메타데이터 (modality, body_part, sex, age_bucket, study_year, n_instances, size_mb, hospital_code).
  - 섹션 2: 보유 시리즈 목록 (series UID 8자 잘림 + modality + count).
  - 섹션 3: CTA — "Add to cohort" 버튼 + 수량 배지.
- **v0.1 제외 (강력 권고)**:
  - **DICOM 뷰어 임베드** — 이유: (a) buyer-facing 샘플 프리뷰 DICOM을 준비하는 파이프라인(Hot Storage Flow C, `order-fulfillment` v0.1.1)이 없음. (b) 임베드 자체는 1일 작업이나 **버이어에게 썸네일을 보여주는 정책 결정**이 선결 과제 — 완전 익명화된 DICOM이라도 "구매 전 노출"은 추가 DPA 조항 필요. **§13 Open Question**.
  - 리포트 미리보기 — NLP 라벨 엔진(Phase 2) 이후.
- **v0.2**:
  - "샘플 dataset" (10 studies 랜덤 선택, 무료 OHIF 뷰어 임베드 + CSV export). Gradient의 "CSV download" 패턴 차용. **이것이 "wow" 데모 요소 #1**.
- **§11 DICOM 뷰어 통합 가부 상세 판정** 참조.

---

## 6. 장바구니·주문 확정 플로우

### 6.1 Cohort 단위 vs 개별 스터디 단위

- **TCIA/IDC**: 개별 스터디/시리즈를 카트에 추가, 최종적으로 Manifest 파일 다운로드 (= 우리의 "cohort export").
- **Gradient Atlas**: "Cohort" 명시 단위 — 검색 결과 전체를 cohort로 저장, export로 처리. 개별 스터디 단위 pick-up은 약함 (확인 불가).
- **Segmed Openda**: 블로그상 cohort 단위 중심.
- **Snowflake Marketplace**: 전체 리스팅을 "구독" — 개별 row 단위 아님.

RadiVault는 이미 `order-fulfillment` dev-spec에서 **`pseudo_study_uids` 배열로 주문** 구조를 택했음 ([`dev-spec-order-fulfillment.md §6`](../specs/dev-spec-order-fulfillment.md)) — 즉 개별 스터디 단위. 이는 TCIA/IDC 스타일과 일치.

### 6.2 가격 표시 시점

| 플랫폼 | 검색 단계 | 상세 페이지 | 주문 확정 |
|-------|-------|---------|----------|
| **Gradient** | 불명확 (추정 X) | 불명확 | sales 미팅 |
| **Segmed** | X (contact sales) | X | sales 미팅 |
| **AWS Data Exchange** | ○ 리스팅에 $/월 표시 | ○ | ○ checkout |
| **Snowflake Marketplace** | ○ 리스팅 | ○ | ○ 구독 |
| **TCIA/IDC** | 무료 | 무료 | 무료 |

상용 데이터 마켓(AWS/Snowflake)은 가격 선공개가 표준. 의료영상 상용(Segmed/Gradient)은 **sales-led**로 숨김.

**RadiVault 현 설계 준수**: `order-flow-quickstart-buyer-en.md §13`은 `total_estimated_usd` 를 주문 생성 응답에 노출 (v0.1 billing stub). 경쟁사 대비 **transparent한 stance**. 단 paid tier API key만 노출 가능. `one-pager-buyer-global-en.md §8`도 "Pricing transparency in the procurement call" 명시 — 검색 단계에서는 unit price 숨기고 **Studies 단위만 보이다가 주문 확정 시 `$5/study × N`** 로 집계.

### 6.3 수량 할인·Tier 표시

- 경쟁사 공개 공식 없음. 대부분 sales 협상.
- AWS/Snowflake은 구독 tier (monthly/annual) UI.

**RadiVault v0.1**: Tier 구조는 이미 metadata-index에 있음 (free/preview/paid). **웹 UI에는 "Paid tier required for order" 힌트만 노출**. 실 할인은 MSA 협상 단계.

### 6.4 DUA / License 동의 절차

- **TCIA**: Collection별로 다른 라이센스 (CC-BY, TCIA Restricted 등). 다운로드 전 라이센스 선택 페이지에서 체크박스 1회.
- **OpenNeuro**: 다운로드 전 license accept 체크박스.
- **Gradient/Segmed**: MSA 1회 체결 후 추가 클릭 없음 (추정).
- **UK Biobank**: Application-level 승인 → 사전 전자서명.
- **AWS Data Exchange**: Subscribe 버튼 + Terms 체크박스 (클릭랩).

**RadiVault 현 설계**: `order-fulfillment` v0.1은 **주문 생성 시 `agreement_hash`(SHA-256 of MSA body)를 요구**. MSA 자체는 외부(DocuSign 등)에서 1회 체결. 매 주문마다 `agreement_hash`를 payload에 포함 → **웹 UI는 agreement_hash 자동 채움 + 체크박스 "I confirm this order is governed by MSA {id}"**.

### 6.5 주문 요약 (영수증 스타일)

- **AWS Data Exchange / Stripe Checkout**: 표준 영수증 — 아이템·수량·소계·세금·총액.
- **의료영상 포털**: TCIA/IDC는 "manifest with N studies, estimated M GB" 수준.
- **RadiVault**: 이미 `POST /v1/orders` 응답이 `{order_id, state, total_estimated_usd, state_billing: "pending_billing", expires_at}`. 웹 UI는 이걸 **영수증 모달**로 렌더.

**RadiVault 적용 권고 (§6)**:
- **v0.1 MVP**:
  - 우측 persistent sidebar "Cohort (N studies, X.X GB)" (Gen3 스타일).
  - 체크박스 선택 → 실시간 sidebar 업데이트.
  - 상단 "Review order" 버튼 → 모달에 (a) 코호트 summary (b) agreement_hash 자동 채움 (c) DUA 체크박스 (d) "Confirm order" CTA.
  - 주문 생성 성공 시 영수증 모달 (order_id, N studies, estimated_usd, ETA).
- **v0.1.1**:
  - Saved cohorts ("저장된 검색") — metadata-index backlog에 이미 있음.
- **v0.2**:
  - Stripe Checkout 통합 (billing v0.2 옵션 G).

---

## 7. 주문 상태 추적 UI

### 7.1 Common pattern

- **Shopify/FedEx 스타일**: 4~6 step 수평 stepper (Ordered → Paid → Preparing → Shipped → Out for delivery → Delivered).
- **Stripe Customer Portal**: 영수증 + 타임라인 (PaymentIntent 상태 이벤트별 타임스탬프).
- **Gen3 marketplaces**: 주문 개념 없음 (무료 export만).
- **Gradient Atlas**: "Export" 후 처리 → 메일 알림 + 진행 모달 추정 (확인 불가).

### 7.2 FSM 노출 정책

우리는 12-state FSM이 있음 (`order-fulfillment` dev-spec §5):

```
draft → queued → validating → transfer_pending → transfer_in_progress →
staging_in_progress → staging_complete → ready_for_download → downloading →
completed → (cancelled | expired | failed)
```

**경쟁사 관행**: 내부 상태 전수 공개 없음. 버이어는 "Preparing / Ready / Done / Failed" 수준만 본다.

**권장 buyer-facing 5-step phase 매핑**:

| Phase (UI 표시) | 내부 FSM state |
|-----|-----|
| 1. **Accepted** | `queued`, `validating` |
| 2. **Fetching from hospital** | `transfer_pending`, `transfer_in_progress` |
| 3. **Preparing download** | `staging_in_progress`, `staging_complete` |
| 4. **Ready to download** | `ready_for_download`, `downloading` |
| 5. **Completed** | `completed` |
| — (별도) | `cancelled`, `expired`, `failed` — 빨간 뱃지 |

### 7.3 Progress bar vs step tracker vs timeline

- **Step tracker** (Shopify 스타일 수평 dots) → 5 phase에 적합. **추천 선택**.
- **Progress bar** (%) → 과장 (transfer 진행률 표시는 어려움).
- **Timeline** (Stripe 스타일 수직 이벤트 로그) → 디버그용. "Details" 드로어에 배치.

### 7.4 ETA 표시 정책

- **order-fulfillment dev-spec**: Hot path 30초, cold path ~1시간 ([`order-flow-quickstart-buyer-en.md §0`](../marketing/order-flow-quickstart-buyer-en.md)).
- **경쟁사 ETA**: Gradient Atlas는 "within 24-48h" 수준만 (구체 시계 없음).
- **권장**: phase별 평균 소요 시간을 tooltip으로. `Expected ready by: 2026-04-24 18:34 KST` 같은 절대 시각 1개.

### 7.5 알림 (이메일·in-app·webhook)

- **Shopify**: 이메일 + SMS + push.
- **Gradient/Segmed**: 이메일 (추정).
- **AWS Data Exchange**: CloudWatch Events + SNS.
- **RadiVault 현 상태**: v0.1에 이메일·webhook 없음 (v0.1.1 backlog, Session 8 progress.txt). 웹 UI는 **폴링 + toast notification**로 대체.

**RadiVault 적용 권고 (§7)**:
- **v0.1 MVP**:
  - 5-phase step tracker (수평 dots with labels).
  - 현재 phase highlight + ETA tooltip.
  - "View details" 드로어 → 12-state 타임라인 (SRE/advanced buyer용).
  - polling 5초 간격 (백오프는 `order-flow-quickstart-buyer-en.md §5`와 일치).
  - In-app toast on state change.
  - 실패 상태에 에러 코드 + "Contact support" 링크.
- **v0.2**:
  - 이메일 알림 (v0.1.1 이후).
  - Webhook (v0.1.1 이후).

---

## 8. 다운로드 UI

### 8.1 Common pattern

- **Presigned URL + 매니페스트 JSON**: TCIA, IDC, Gradient 모두 **"download manifest" 파일 + per-object URL 리스트** 패턴.
- **CLI 명령 snippet**: IDC는 `s5cmd cp --source-region us-east-1 ...` 블록을 복붙 가능하게 렌더. TCIA는 NBIA Data Retriever (Java GUI) — 구식.
- **SDK snippet**: Gradient 블로그상 Python SDK 언급. RadiVault v0.1은 SDK 없음, REST + httpx example only ([`order-flow-quickstart-buyer-en.md §7`](../marketing/order-flow-quickstart-buyer-en.md)).

### 8.2 체크섬 노출

- **TCIA/IDC**: 각 object에 MD5 or SHA-256 제공.
- **RadiVault**: SHA-256 per object ([`dev-spec-order-fulfillment.md §FR-52`](../specs/dev-spec-order-fulfillment.md)). 웹 UI는 매니페스트 JSON 내 필드 렌더.

### 8.3 대용량 재시도 UX

- **AWS S3 console**: 단일 object → 브라우저 네이티브 재시도.
- **TCIA NBIA Retriever**: 자체 resume.
- **RadiVault**: httpx 병렬 예제 + sha256sum 검증 stub ([`order-flow-quickstart-buyer-en.md §7.2`](../marketing/order-flow-quickstart-buyer-en.md)). 웹 UI 자체는 **다운로더를 포함하지 않음** — "Copy curl/Python snippet" 버튼.

### 8.4 URL 만료·재발급

- **TCIA/IDC**: 만료 개념 약함 (대부분 NCI 계정으로 재접근).
- **RadiVault**: 24h 기본, 7d 최대, `POST /v1/orders/{id}/download-urls/refresh` 엔드포인트 ([`dev-spec-order-fulfillment.md §6.6`](../specs/dev-spec-order-fulfillment.md)). 웹 UI는 "URLs expire in 23h 47m — Refresh" 버튼.

**RadiVault 적용 권고 (§8)**:
- **v0.1 MVP**:
  - 주문 Ready 후 다운로드 페이지:
    - 상단 "Expires in 23h 47m" 카운트다운 + Refresh 버튼.
    - 탭 3개: "Browser download (object list)" / "Copy curl" / "Copy Python (httpx)".
    - 각 object row: filename · size · SHA-256(8자 잘림, 클릭하면 전체 복사) · Download button.
    - "Download all (.json manifest)" 상단 CTA — `order-flow-quickstart-buyer-en.md §7`의 manifest 그대로.
- **v0.1 제외**: 브라우저 내 대용량 zip 다운로드 (Zone 2 egress 비용).
- **v0.2**: 진행률 표시 (service worker 기반 stream download).

---

## 9. 공통 Shell·내비게이션

### 9.1 Top nav 구성 (경쟁사 공통)

왼쪽에서 오른쪽으로:
1. 로고 (홈으로)
2. 주요 섹션 (Search · Orders · Downloads · Docs)
3. 검색 shortcut (⌘K 패턴; Linear/Vercel 같은 최신 B2B)
4. 프로필 드롭다운 (Account · API keys · Billing · Sign out)

### 9.2 API key 관리

- **Stripe Dashboard 스타일**: "Developer" 섹션에 key 리스트 · Create key · Roll · Revoke.
- **RadiVault**: `search-admin` CLI에 이미 key 발행 커맨드 있음. 웹 UI는 **key 리스트 + 마스킹(`rv_live_****_...ef12`) + Revoke 버튼만** (신규 발행은 SRE CLI로).

### 9.3 빌링 섹션

- v0.1은 billing stub ([`order-flow-quickstart-buyer-en.md §13`](../marketing/order-flow-quickstart-buyer-en.md)). 웹 UI "Billing" 탭은 **"Pending invoices" 리스트 + "Total pending: $X.XX USD" 요약 + "v0.2에서 Stripe 연동 예정" 배너**.

### 9.4 빈 상태·에러 상태·로딩 상태

- **Empty state 패턴 (2025-2026 트렌드)**: 정적 메시지 → 인터랙티브 전환. 예: "No orders yet → Start browsing" + inline CTA.
- **Loading**: 스켈레톤 UI (shadcn/ui Skeleton 컴포넌트).
- **Error**: 에러 코드 + 한국어·영어 메시지 + "Contact support" — metadata-index·order-fulfillment `design-spec` 에러 taxonomy와 1:1 매핑.

### 9.5 Docs / FAQ 인라인

- **Intercom 스타일 widget**: 대기업 레퍼런스. 그러나 v0.1 스코프 오버.
- **shadcn HoverCard + 링크**: 각 복잡 필드(filter_sha256, min_hospitals 등) 옆 (?) 아이콘 → HoverCard. docs.radivault.io 해당 섹션으로 링크.

**RadiVault 적용 권고 (§9)**:
- **v0.1 MVP**:
  - Top nav: Logo · Search · Orders · Downloads · Docs · ⌘K command palette placeholder · Profile.
  - Sidebar(optional) on Orders·Downloads.
  - Profile dropdown: Account · API Keys(read-only) · Billing(stub) · Sign out.
  - Empty state 3종 (No orders / No search results / No downloads ready) with CTA.
  - Error state 매크로 컴포넌트 — metadata-index·order-fulfillment 에러 코드 테이블을 i18n JSON으로 import.
  - Loading: shadcn Skeleton.
- **v0.1 제외**: Intercom widget, help center, in-app tour.

---

## 10. Must-have vs Nice-to-have for Buyer Portal MVP (2~3주 스코프)

### 10.1 Must-have (MVP / 2주 핵심)

| # | 화면 | 대략 작업량 | 근거 |
|---|-----|--------|------|
| 1 | **Login + session** (opaque API key → session cookie) | 1일 | auth는 metadata-index가 이미 처리 |
| 2 | **Search page** (좌 패싯 / 중앙 테이블 / 우 cohort sidebar) | 3일 | §3, §4, §6 |
| 3 | **Study detail modal** (메타 + 시리즈 목록) | 0.5일 | §5 (뷰어 제외) |
| 4 | **Review order modal + Confirm** | 1일 | §6 |
| 5 | **Orders list page** (FSM phase badge) | 1일 | §7 |
| 6 | **Order detail page** (5-step tracker + 타임라인 드로어) | 1.5일 | §7 |
| 7 | **Download page** (만료 카운트다운 + 3탭 + 매니페스트) | 1일 | §8 |
| 8 | **Top nav + Profile dropdown + Empty/Error/Loading 컴포넌트** | 1일 | §9 |
| 9 | **README + .env.example + docker-compose + shadcn init** | 0.5일 | — |
| 10 | **QA + 데모 시나리오 폴리시** | 1~2일 | — |

**Total: ~12~14일 개발 + 2~3일 QA + 폴리시 = 2.5~3주. 2주 하드 데드라인은 빡빡. Kyle 결정: 뷰어(§11) 포함 여부와 데이터 스케일.**

### 10.2 Nice-to-have (v0.1.1 백로그)

- 저장된 코호트 (Saved searches)
- 결과 시각화 (연령 피라미드, 성별 bar)
- Advanced Search 모달
- ⌘K command palette
- 다크 모드
- 반응형 모바일 (3주 스코프에는 데스크톱 only 권고)
- 이메일 알림
- 한국어 i18n 전수 (MVP는 영어 only, 한국어 탐색 후 v0.1.1)
- Saved payment method
- 스터디 프리뷰 (썸네일 + OHIF)

### 10.3 Out of scope (v0.2+)

- DICOM 뷰어 인라인 (§11)
- 실 결제 (옵션 G)
- NLP 진단명 기반 검색
- 다중 유저 팀 워크스페이스
- 감사 로그 자체 노출

---

## 11. DICOM 뷰어 통합 가부 판정

### 11.1 기술적 옵션

| 옵션 | 설명 | 공수 | 위험 |
|------|-----|----|------|
| **A. OHIF iframe** | [OHIF docs](https://v2.docs.ohif.org/deployment/recipes/embedded-viewer/) 공식 임베디드 방법. iframe + postMessage. | 0.5~1일 | 데이터 소스 필요. 프리뷰 DICOM 준비 파이프라인 없음. |
| **B. Cornerstone.js 직접** | 더 세밀한 제어. Gradient/IDC가 이 경로 추정. | 3~5일 | 2주 스코프 초과. |
| **C. Ambra / PostDICOM 서드파티** | SaaS 뷰어. | 1일 | 월 구독료. 외부 서비스 의존. |
| **D. 서드파티 링크 (Orthanc + OHIF self-host)** | 공식 OHIF를 자체 호스팅. | 2일 | 별도 인프라. |

### 11.2 데이터 소스 제약

- OHIF는 **DICOMweb (QIDO-RS, WADO-RS)** 를 데이터 소스로 요구.
- RadiVault 현 아키텍처:
  - Zone 1 (병원) Gateway: DICOMweb 지원 (Orthanc 기반).
  - Zone 2 (Central): 완전 익명화된 DICOM은 S3 + 메타만. 버이어-facing DICOMweb 서버 없음.
- 즉 **버이어가 OHIF로 프리뷰하려면 Zone 2에 buyer-facing DICOMweb gateway를 새로 구축**해야 함. 이는 **새로운 dev-spec** 필요.

### 11.3 정책 제약

- 현재 `order-fulfillment` 는 **주문 확정 후에만** DICOM을 presigned URL로 제공.
- "프리뷰" = 주문 전 노출 = **현 익명화 정책(post-purchase view)과 충돌 가능**.
- 대표님/법률 결정 필요: 완전 익명화 DICOM이 "구매 전 공개" 가능한지. **법률 자문 flag**.

### 11.4 판정

**v0.1 MVP: 뷰어 미포함. 강력 권고.**

근거:
1. 2~3주 스코프에서 **buyer-facing DICOMweb gateway 구축 + OHIF 임베드 + 프리뷰 DICOM 선별 파이프라인**을 모두 올리는 건 불가.
2. "프리뷰 = 주문 전 노출"의 법적·비즈니스 정책 결정이 선행되어야 함.
3. 데모에서 없어도 치명적이지 않음 — **"구매 후 다운로드된 DICOM을 로컬 viewer로 열어보는 GIF"** 한 장으로 데모 아쉬움 해소 가능.

**v0.2 로드맵 스케치**:
- "Sample Dataset" 기능: 각 병원에서 **10 study 랜덤 pre-released 익명 샘플**을 Zone 2에 배치.
- 이 샘플만 OHIF iframe으로 노출.
- 샘플 접근은 "Preview Dataset" 버튼 → 30초 trial → expire.
- 이 방식이 Gradient Atlas의 "instant preview" 와 동일한 UX를 안전하게 재현.

---

## 12. Hospital Dashboard 권장 화면 구성 (병원 경영진 관점, 1 페이지)

### 12.1 목적

- 병원 경영진(이사장·기획실장·전산실장)이 RadiVault 가동 **"보람"을 느낄 수 있는 1-screen view**.
- 투자자 데모에서도 "실제 병원이 이런 걸 본다"로 어필.

### 12.2 6-tile 레이아웃

```
┌────────────────────────────────────────────────────────────┐
│  [RadiVault Hospital Partner Dashboard — Kim's Hospital]   │
├────────────┬────────────┬───────────────┬─────────────────┤
│  Studies   │  Cumulative│   Orders      │  Gateway Status │
│  indexed   │  revenue   │   last 30d    │  ● Online 23h   │
│    42,190  │  ₩ 18.4M   │    12         │  last sync 2m   │
├────────────┴────────────┴───────────────┴─────────────────┤
│  Revenue by month (bar chart, last 12m)                    │
├────────────────────────────────────────────────────────────┤
│  Opt-out queue   │   Data quality ratio                    │
│  3 pending       │   burn-in flagged 1.2%                  │
└────────────────────────────────────────────────────────────┘
```

### 12.3 각 타일 설명

| 타일 | 데이터 소스 | 비고 |
|-----|---------|------|
| **Studies indexed** | central-ingest `study` 테이블 (hospital_id 필터) | 병원이 "우리가 얼마나 기여했나" 직관적 인식 |
| **Cumulative revenue** | billing v0.2 이후 실수치. v0.1은 **"pending_billing 누계 × 병원 revenue share %"** 스텁 | v0.1은 "Estimated, settlement pending v0.2" 작은 글씨 |
| **Orders last 30d** | order-fulfillment `order` 테이블에서 해당 병원 studies 포함 주문 COUNT | buyer 프라이버시 보호 — buyer 이름 미노출 |
| **Gateway status** | Gateway heartbeat (Session 3 구현). last sync timestamp. | ● 초록 / ● 노랑 / ● 빨강 |
| **Revenue by month** | 월별 집계 bar chart | 12m 범위, Recharts |
| **Opt-out queue** | scope_json.exclude_hospitals 요청 (v0.1.1 backlog) | 수량만, 세부 buyer 미노출 |
| **Data quality** | de-id-pixel `burn_in_flagged_pct` 집계 | 병원에게 품질 피드백 |

### 12.4 경쟁사 비교

- **Segmed/Gradient**: 병원용 대시보드 공개 확인 불가. 실제 있어도 NDA.
- **Flywheel**: "encrypted cloud-based storage" 통계 대시보드 제공 — 우리 참고.
- **UK Biobank**: 연구자 대시보드만, 기관 대시보드 아님.

### 12.5 "병원 경영진 감동 포인트"

- **수익 숫자 대문짝** (위 6-tile 중앙 상단). 대부분 병원은 아직 데이터 수익을 본 적이 없어서 **₩ 단위 실숫자가 설령 적어도 임팩트 큼**.
- **Gateway Online/초록 점** + heartbeat — 병원 전산실장이 즉시 안심하는 신호.
- **Data quality ratio** — "우리가 준 데이터 품질이 검증된다"는 품격.
- 페이지는 **1 스크롤 내 완료**. 복잡한 네비게이션 금지 (경영진 대상).

### 12.6 v0.1 MVP 스코프

- Hospital Dashboard는 **MVP 2~3주 스코프에 포함 여부가 Kyle 결정**.
- **권고**: **별도 3~4일 추가 스프린트**로 분리. Buyer Portal이 완성된 뒤 재활용 컴포넌트(shadcn Card, Recharts)로 매우 빠르게 가능.
- 투자자 데모에서는 "Coming soon" 렌더된 mock 대시보드 스크린샷만 1장 있어도 "병원 파트너십 전략 있음" 어필 충분.

---

## 13. Open questions for Kyle

### 13.1 법률·정책 결정 필요

1. **프리뷰 DICOM 공개 정책**: 완전 익명화 DICOM을 주문 전 버이어에게 "sample preview"로 노출해도 되는가? PIPA §28-8 "완전 익명 정보 국외이전" 예외 안에 프리뷰도 포함되는지. **법률 자문 flag**.
2. **MSA 외부 vs 내부 서명**: MSA 체결을 외부 DocuSign에 맡기고 포털은 `agreement_hash` 클릭랩만 할지, 내부 전자서명까지 할지. 후자는 v0.2+.
3. **병원 opt-out의 버이어 가시성**: 버이어가 검색 시 "hospital X's data is excluded by your scope" 힌트를 볼 수 있는가? (§3.1 hospital_group facet 관련)
4. **가격 표시 레벨**: 검색 페이지 · 상세 페이지 · 주문 확정 중 어디서부터 `$5/study` 노출? (§6.2)

### 13.2 UX 결정 필요

5. **Portal 언어 정책**: v0.1 MVP 영어 only? 한국어 번역은 v0.1.1에 후행? (병원 대시보드는 한국어 우선, Buyer Portal은 영어 우선 권고)
6. **대시보드 내 토스트 vs 이메일**: v0.1에서는 어디까지 지원? (이메일 v0.1.1 백로그 권고)
7. **Dark mode**: 데모 시 다크모드가 인상 강함 (의료영상 산업 관례). 단 shadcn 기본 생성된 토큰으로도 1일 공수. v0.1 MVP 포함 여부.
8. **Hospital Dashboard MVP 스코프 포함?**: §12.6 — Buyer Portal 2주 + Hospital Dashboard 3~4일 추가 3주 스프린트 여부.
9. **Gradient 스타일 aggregate analytics 차트**: v0.1 vs v0.1.1? (연령 피라미드, 성별 bar)
10. **Viewer**: §11 판정 수용? (v0.1 미포함, v0.2 sample preview)

### 13.3 기술·보안 결정 필요

11. **세션 인증 방식**: opaque API key → 세션 쿠키 변환 레이어 (BFF) vs API key 헤더만 (SPA fetch). BFF 권고 (CSP, 쿠키 분리).
12. **웹 도메인**: `portal.radivault.io`? `buyer.radivault.io`? 기존 `search.radivault.io` · `fulfillment.radivault.io`와 구분 필요.
13. **CORS 정책**: metadata-index M-2 (QA backlog)에 CORS가 아직 미구현. Buyer Portal이 **동일 도메인 BFF**를 쓴다면 CORS 불필요. SPA + 크로스 도메인 API 직접 호출이면 CORS 먼저.
14. **Public 마케팅 페이지 vs 인증 포털 분리**: radivault.io (마케팅) + portal.radivault.io (인증). 두 레포인지 단일 모노레포인지.

---

## 14. Change history

| 버전 | 날짜 | 작성자 | 변경 |
|-----|------|------|------|
| 0.1 | 2026-04-24 | @researcher (Claude Opus 4.7) | 최초 작성. 경쟁사 11종 + 인접 산업 2종 웹 UI UX 패턴 수집. §1~§14. |

---

## 출처

### 1차 (공식 제품 페이지·docs)

- Segmed Openda: https://openda.segmed.ai/, https://www.segmed.ai/solutions/openda
- Segmed 블로그 "How Segmed Streamlines Access to RWD": https://www.segmed.ai/resources/blog/how-segmed-streamlines-access-to-rwd
- Segmed 블로그 "Introducing Segmed Insight": https://www.segmed.ai/resources/blog/introducingsegmedinsight
- Gradient Health Atlas (AI developers 페이지): https://gradienthealth.io/atlas/
- Gradient Health "Launches Atlas 2" 프레스릴리스: https://gradienthealth.io/gradient-health-launches-atlas-2-setting-a-new-standard-for-medical-imaging-data-access/
- Gradient Health "Launches Atlas Product Suite": https://gradienthealth.io/2024/02/20/gradient-health-launches-atlas-product-suite-for-ai-developers/
- TCIA Radiology Portal User's Guide: https://wiki.cancerimagingarchive.net/display/NBIA/TCIA+Radiology+Portal+User's+Guide
- TCIA Browse Collections: https://www.cancerimagingarchive.net/browse-collections/
- NIH IDC Portal: https://portal.imaging.datacommons.cancer.gov/
- IDC User Guide "Exploring imaging data": https://learn.canceridc.dev/portal/data-exploration-and-cohorts/exploring-imaging-data
- IDC Release Notes: https://learn.canceridc.dev/portal/release-notes
- MIDRC Data Commons: https://data.midrc.org/
- MIDRC Cohort Building RSNA 2023: https://data.midrc.org/dashboard/Public/notebooks/MIDRC_Cohort_Building-DLL_RSNA_2023.html
- OpenNeuro docs: https://docs.openneuro.org/user-guide/
- OpenNeuro API: https://docs.openneuro.org/api.html
- UK Biobank Showcase: https://biobank.ndph.ox.ac.uk/showcase/
- UK Biobank Showcase Search: https://biobank.ndph.ox.ac.uk/showcase/search.cgi
- AWS Data Exchange: https://aws.amazon.com/data-exchange/
- AWS Marketplace 구매자 가이드: https://docs.aws.amazon.com/marketplace/latest/buyerguide/buyer-getting-started.html
- Snowflake Marketplace (UI 소개): https://docs.snowflake.com/en/user-guide/ui-snowsight-marketplace.html
- Flywheel Research Data Management: https://flywheel.io/flywheel-is-research-data-management/

### 2차 (프레스·뉴스·업계 분석)

- Segmed + Openda 프레스릴리스 (2024): https://www.prnewswire.com/news-releases/segmed-unveils-new-brand-identity-and-introduces-openda-the-next-evolution-for-its-insight-platform-302185953.html
- Imaging Technology News — Gradient Atlas 2: https://www.itnonline.com/content/gradient-health-releases-upgrade-self-service-medical-imaging-data-platform
- HT World — Gradient Atlas 2 launch: https://www.htworld.co.uk/news/ai/gradient-health-launches-atlas-2-imaging-platform-evolene/
- DOTmed — Gradient Atlas 2: https://www.dotmed.com/news/story/65771

### 3차 (UX 패턴 일반)

- PatternFly Empty State: https://www.patternfly.org/components/empty-state/design-guidelines/
- NN/g — Empty States in Complex Applications: https://www.nngroup.com/articles/empty-state-interface-design/
- Eleken — Empty state UX: https://www.eleken.co/blog-posts/empty-state-ux
- Userpilot — SaaS Empty States: https://userpilot.com/blog/empty-state-saas/
- Pencil & Paper — Empty State examples: https://www.pencilandpaper.io/articles/empty-states/
- Medium — Designing a cohort marketplace (Piyush Petkar): https://medium.com/design-bootcamp/designing-a-cohort-marketplace-ux-ui-case-study-56a642ec92ae
- Fruto.design — Medical imaging UI case study: https://fruto.design/case-studies/medical-imaging-ui-radiology-tech-startup
- shadcn/ui: https://ui.shadcn.com/
- shadcn Dashboard starter (Kiranism): https://github.com/Kiranism/next-shadcn-dashboard-starter
- Vercel Next.js + shadcn admin template: https://vercel.com/templates/next.js/next-js-and-shadcn-ui-admin-dashboard
- OHIF Deployment Overview: https://docs.ohif.org/deployment/
- OHIF Embedded Viewer: https://v2.docs.ohif.org/deployment/recipes/embedded-viewer/
- Stripe Customer Portal: https://docs.stripe.com/customer-management/integrate-customer-portal
- Shopify Order Status Page: https://help.shopify.com/en/manual/fulfillment/setup/order-status-page
- AWS S3 presigned URL: https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html

### 법률·정책 맥락 (비결론, 자문 flag)

- 개인정보보호법 제28조의8: https://www.law.go.kr/법령/개인정보보호법
- Harvard — Data Use Agreements: https://researchdatamanagement.harvard.edu/data-use-agreements
- MIT Admin Data Handbook — Model DUAs: https://admindatahandbook.mit.edu/book/v1.0-rc4/dua.html

**Disclaimer**: 본 문서는 법률 자문이 아니다. Segmed·Gradient 등 상용 제품의 버이어-facing UI 세부는 공개 자료 기반 **추정** 포함. 상세 dev-spec 단계에서 NDA 하 실 제품 로그인 또는 공식 demo 요청 후 재검증 권고.

---

### NEXT_STEP

- **완료 산출물**: `docs/research/buyer-portal-ux-competitive.md` (본 문서)
- **제안 다음 단계**: **@planner** — `docs/specs/dev-spec-buyer-portal.md` 작성. 본 리서치의 §10(Must-have) · §11(뷰어 미포함) · §12(Hospital Dashboard 별도 스프린트) · §13(Kyle 결정) 을 근거로 다음을 요구사항화:
  1. **기술 스택**: Next.js 14 + TypeScript + shadcn/ui + Tailwind + TanStack Query + Recharts 권고 (§9, §10).
  2. **도메인·세션**: `portal.radivault.io` + BFF 패턴 (API key 서버측 보관 세션 쿠키 교환).
  3. **페이지 구조**: Search · Orders · Order detail · Downloads · Billing(stub) · Account 6 페이지 + Hospital Dashboard(별도).
  4. **FSM-to-phase 매핑**: 본 리서치 §7.2 표 그대로 dev-spec FR로 확정.
  5. **DUA 클릭랩 UX**: `agreement_hash` 자동 채움 + 체크박스 (§6.4).
  6. **에러·Empty·Loading 공통 컴포넌트 목록**: §9.4.
  7. **MVP 제외 기능**: viewer·preview·saved cohort·dark mode·email·한국어 i18n (§10, §11).
  8. **Hospital Dashboard**: 별도 3~4일 sub-spec (§12).
- **제안 병렬 단계** (planner 와 동시 가능): **@designer** 가 컨셉 목업 (디자인 토큰·Top nav·Search layout 3 화면 mid-fi) 을 병렬 시작 — dev-spec 확정 전에라도 shadcn/Tailwind 토큰 선정 가능. `_template/design-spec-template.md` §0 pre-dev-spec exploration 모드.
- **Kyle 결정 필요 사항**:
  1. §13.1 법률 4건 (프리뷰 공개 / MSA 서명 / opt-out 가시성 / 가격 노출 레벨) — **법률 자문 flag**
  2. §13.2 UX 5건 (언어·토스트·다크모드·Hospital Dashboard 포함·aggregate chart) — 빠른 결정 가능
  3. §13.3 기술 4건 (세션 방식·도메인·CORS·레포 구조)
  4. **우선순위**: Buyer Portal MVP 2주 빡빡 vs 2.5~3주 여유? Hospital Dashboard 포함? Viewer 보류 (§11) 확정?
