# RadiVault Portal 전면 리디자인 — 경쟁사·베스트 프랙티스 분석

> **Status**: Draft v0.1 · **Last updated**: 2026-04-24
> **작성자**: @researcher (Claude Opus 4.7)
> **근거 요청**: Kyle — CEO 미팅 D-14 대응, RadiVault 포털/웹사이트 전면 리디자인을 위한 시각/마케팅/브랜드 레이어 리서치. 후속 @planner·@designer (feature-slug: `portal-redesign`) 가 dev-spec·design-spec(mockup 포함) 작성 시 본 문서를 근거로 사용.
> **선행 리서치 (재활용)**:
> - [`buyer-portal-ux-competitive.md`](./buyer-portal-ux-competitive.md) — 검색/주문 플로우 중심의 **포스트-로그인 UX 패턴** (Gen3/TCIA/IDC/MIDRC). 본 문서는 그 위에 얹는 **랜딩·시각·브랜드·마케팅 레이어**.
> - [`demo-pitch-references-radivault.md`](./demo-pitch-references-radivault.md) — 경쟁사 데모 연출. 본 문서는 **상시 공개 웹 경험**에 초점.
> - [`k-meddata-research-summary.md`](./k-meddata-research-summary.md) — 시장·규제 배경.
> - [`../marketing/competitive-positioning-buyer-en.md`](../marketing/competitive-positioning-buyer-en.md) — 경쟁사 vs RadiVault 포지셔닝.

---

## 0. Executive Summary

RadiVault 는 **두 개의 대단히 다른 타깃에 하나의 브랜드** 로 접근한다. 글로벌 AI 기업 바이어(영어, 개발자·의사결정자 혼재)와 한국 대형·중견 병원 C-레벨(한국어, 신뢰·규정준수 최우선). 본 리서치는 이 이중 전선을 감당할 수 있는 포털/웹사이트 패턴을 15 개 경쟁·인접·베스트 프랙티스 사이트에서 추출했다.

**세 가지 핵심 발견**:

1. **의료 데이터 시장은 "sales-led, metric-rich, compliance-deferred" 가 표준**. Segmed·Gradient·Aidoc·Annalise 4 개 모두 (a) 헤로에는 큰 숫자 + 실명 병원 로고 / (b) 본문에 구체 수치 임팩트 ("31% faster time-to-notification", "2,800+ healthcare partner sites") / (c) 컴플라이언스 배지는 헤더·헤로에 없음 — 별도 페이지(Security & Compliance 또는 Trust Center)로 이동. **즉 RadiVault 는 메트릭을 숨길 이유가 없다** (현재 홈페이지 부재가 오히려 불리).

2. **베스트 인 클래스 SaaS 랜딩 (Stripe, Linear, Vercel, Supabase) 은 제품 스크린샷과 실제 UI 를 과감히 노출**. 반면 의료 데이터 경쟁사는 스크린샷이 적거나 "stylised" 디스클레이머. RadiVault 는 **현재 구현된 `/search` `/orders` `/hospital` 의 실제 렌더를 정면으로 노출** 하는 전략이 차별화(단, 완전 익명 데모 데이터로). 이는 "sales-led 인데 정말 작동하는지 알 수 없다" 의심을 차단.

3. **한국 B2B SaaS 관행은 "footer 에 사업자등록번호·대표자명·전화 1544-xxxx·ISMS/ISO 배지"**. Ncloud·KINX·VUNO 3 개 모두 동일. 한국 병원 CTO/DPO 는 이 요소의 **부재** 만으로도 "검증되지 않은 스타트업" 인상을 받는다. 서구 SaaS 관행("minimal footer") 을 한국 병원 타깃 화면에 그대로 복제하면 **신뢰 손실**.

**북극성 (자세히는 §6)**: **"정보 밀도 높음 · 신뢰 우선 · 이중 언어 · compliance 강조"**. 모던한 Vercel/Linear 톤이 아닌, Stripe 의 **"데이터로 설득하는 엔터프라이즈 폴리시"** 쪽에 가까워야 한다.

---

## 1. 방법론

### 1.1 분석 대상 (15 개)

| 카테고리 | 사이트 | 분석 깊이 | 비고 |
|---|---|---|---|
| **Direct competitor (의료영상 데이터)** | Segmed (segmed.ai), Gradient Health (gradienthealth.io, Atlas 제품 페이지), Truveta, Rhino FCP, Flywheel, Centaur Labs | ★★★ 헤로·트러스트·풋터 분석 | 법률상 비판 금지, 객관 패턴만 |
| **Adjacent (의료 AI 제품)** | Lunit, VUNO, Harrison.ai (Annalise 모회사), Aidoc | ★★ | 규제 의료기기 SaaS 의 vocabulary 참고 |
| **Best-in-class SaaS polish** | Stripe, Linear, Vercel, Supabase, Plaid | ★★★ | 바이어 포털 포스트-로그인 폴리시 기준선 |
| **Enterprise compliance-centric** | OneTrust, Snowflake, Databricks | ★★ | Trust Center·컴플라이언스 섹션 패턴 |
| **API-first marketplace** | Hugging Face, Replicate | ★★ | 데이터·모델 마켓 discovery UX |
| **한국 B2B** | Ncloud (Naver Cloud Platform), KINX, VUNO, JLK | ★★★ | 병원 한국어 포털 토대 |

**접근 제약**: Toss Payments 는 SPA 렌더 미로드로 WebFetch 실패. 해당 부분은 일반적 한국 B2B 관행으로 우회 서술 (ncloud/kinx/vuno 3 개 공통점 기반). Openda(Segmed) 제품 페이지도 콘텐츠 미반환 → Segmed 메인 + Security & Compliance 페이지로 대체.

### 1.2 각 사이트에서 확인한 체크리스트

1. Hero 섹션 (headline, subhead, CTA 한 쌍, 시각 모티프)
2. Trust bar (고객 로고, 몇 개, 헤더/헤로 아래/중단 위치)
3. Compliance 배지 (SOC2/HIPAA/ISO/KISMS-P 노출 여부·위치)
4. Value prop 섹션 (icon vs screenshot, 몇 단, metric 강조 여부)
5. Social proof (실명 testimonial, 숫자, 케이스 스터디)
6. Footer 아키텍처 (컬럼 수, legal/보안·개발자·회사 구분)
7. Visual language (색상 팔레트, 타이포, 일러스트 vs 제품 UI)
8. Lead capture (데모 요청 vs 이메일 뉴스레터 vs 무료 트라이얼)
9. Pricing 가시성 (self-serve vs contact sales)

### 1.3 한계·주의

- 경쟁사 제품 내부 포스트-로그인 UI 는 공개 스크린샷 1~2 장 한도로만 참조. NDA 미체결 상태라 **추정**에 " (추정)" 명시.
- 본 문서는 법률 자문이 아니다. 브랜드·카피 참고 시 **표시광고법 비교광고 규정** 관점에서 Kyle + 법무 확인 필수 (자세히 §8).
- 2026-04-24 스냅샷. 경쟁사 사이트는 분기마다 변함.

---

## 2. A. 마케팅 홈페이지 패턴 (Pre-login Landing)

> RadiVault 현재 `web/portal` 은 로그인 이후 화면만 존재. **마케팅 홈페이지는 아예 미구현 상태**. 이 섹션은 **0 → 1** 을 만드는 근거.

### 2.1 Hero 섹션 패턴

| 사이트 | Headline | 패턴 분류 |
|---|---|---|
| Segmed | "Real-World Imaging Data for Health Innovation" | **수요자 정체성 + 데이터 유형** |
| Gradient | "Access to millions of medical studies, simplified" | **규모(수치) + 효용 동사** |
| Truveta | "Saving Lives with Data" | **정서적 미션** |
| Rhino | "Activate data for good" / "Take AI to the Edge with Federated Computing" | **차별 기술 명시** |
| Flywheel | "The Medical Imaging Data Management and Analysis Platform" | **범주 점유형 (the ... platform)** |
| Aidoc | "See what matters. Less noise. More focus." | **유저 체험 리듬 (3 phrase)** |
| Annalise / Harrison.ai | "Reimagining the future of healthcare with AI" | **비전형** |
| Stripe | "Financial infrastructure to grow your revenue." | **범주 점유 + 결과 동사** |
| Linear | "The product development system for teams and agents" | **범주 점유 + 시대 태그 (for AI era)** |
| Vercel | "Build and deploy on the AI Cloud" | **아키텍처 점유** |
| Supabase | "Build in a weekend, Scale to millions" | **극단 대비 (속도 ↔ 규모)** |
| Plaid | "Turn data into revolutionary financial products" | **데이터 → 제품 전환** |
| Hugging Face | "The AI community building the future." | **커뮤니티형** |
| Replicate | "Run AI with an API" | **7단어 기능 선언** |

**공통 요소**:
- **주 CTA 두 개 구조**: 자발적 탐색용 1 개 + 세일즈 리드 1 개. 예: Stripe `Get started` + `Contact sales`, Vercel `Start Deploying` + `Get a Demo`, Segmed `Book a Call` (단일).
- **서브헤드 15~30 단어**: 타깃 페르소나 + 가치 + 구체 기대효과. Segmed 는 "regulatory-grade medical images to streamline innovation and meet the evidence needs of researchers at life sciences and technology companies" — **"regulatory-grade"** 가 키 차별어.

**RadiVault 헤로 옵션 (dev-spec 로 전달할 후보)**:

| 옵션 | Headline (영문) | 뉘앙스 | 리스크 |
|---|---|---|---|
| A. 범주+지역 | "Korea's medical imaging data, compliantly delivered for global AI." | PRD §1 의 taglien 을 그대로. 가장 보수적. | 경쟁사 Segmed 와 톤 유사. |
| B. 규모+신뢰 | "Compliant Korean DICOM data for AI — from hospital to AI in 48 hours." | 메트릭 노출 | 48시간 SLA 는 current assumption, 실제 hot path 경과 시 수정. |
| C. 차별 기술 | "The only medical imaging dataset platform built for Korean PIPA §28-8." | 법적 차별성 | 바이어(글로벌) 에게는 PIPA 용어 모호. |
| D. 파트너십 | "Built with Korean hospitals. Trusted by global AI." | 양쪽 페르소나 호출 | 파트너가 아직 없음 — 오도. |

**권고 (v0.1)**: **A 또는 B**. C 는 Korean-domain page 전용 세그먼트에서만 사용. D 는 Phase 2 파트너 확보 후.

### 2.2 Trust Bar (고객 로고 + 컴플라이언스)

**관찰**:
- **Segmed**: 헤로 바로 아래 "~13 로고" (Bayer, Fujifilm, GE, Microsoft, Siemens, Johnson & Johnson, Stryker 등). 컴플라이언스 배지는 헤더·헤로에 **없음**; footer 에 "Trust Center" (Vanta) 링크만.
- **Gradient**: 로고 바 약함. 대신 footer 에 HIPAA + SOC 2 Type II 배지.
- **Truveta**: "Trusted by leading life science, public health, and healthcare organizations" + ~30 멤버 헬스 시스템 로고.
- **Aidoc**: "Trusted by more than 1,600 medical centers worldwide" + 20+ 로고. **가장 임팩트 큰 트러스트 바.**
- **Harrison.ai / Annalise**: 구체 수치 병렬. "40+ countries with clearance", ">130 hospitals in UK across 45+ NHS Trusts". **병원 이름 + 숫자 조합**.
- **Rhino**: 로고 없음. **컴플라이언스 배지 (GDPR + ISO 27001 + SOC 2 + HIPAA) 를 footer 에 강하게 노출** — 로고 없을 때 대체 신뢰 신호.
- **Stripe**: 헤로 바로 아래 carousel 형식 (Amazon, Shopify, Figma, Anthropic, Cursor, OpenAI, Nvidia, Ford, Google 등). **rotating 이 핵심 — 항상 14+ 로고를 보여주면 지루**.

**RadiVault 의 현실**: **파일럿 병원도 아직 없음**. 경쟁사처럼 "bayer, GE" 급 로고가 당장 없다.

**대안 패턴 (권고)**:
1. **"In conversation with" 섹션**: 익명 "Tier 1 Korean university hospital — NDA" + 병원 타입별 집계 (3개 상급종합, 4개 종합 = 7 hospitals in discussion). 마케팅 과장 없이 진실 가능.
2. **Pre-launch: 규정·인증 신호로 대체**: Rhino 스타일. 하단 배지 4개 (HIPAA compliant design · SOC 2 in preparation · ISO 27001 aligned · PIPA §28-8 compliant). "in preparation", "aligned" 라는 보수 어투 — `docs/marketing/one-pager-buyer-global-en.md` §4 와 동일 톤.
3. **파트너 에코시스템**: DICOM 라이브러리 (Orthanc, DCMTK, pydicom), 클라우드 (AWS, GCP), OHIF — "Built on trusted open standards" 섹션. 참고: Flywheel 이 "University of California" 등 학술을 노출하는 패턴.

**주의 — Kyle 법무 flag**: "HIPAA compliant" 같은 표현은 미국 OCR 에 공식 등록 개념이 없어서 보통 "HIPAA-aligned" 또는 "designed to support HIPAA compliance" 로 표기. 이미 `docs/marketing/*-en.md` 는 이 보수 어투를 지키고 있음. 홈페이지도 동일해야.

### 2.3 Value Prop 섹션 구조

| 사이트 | 구성 | 시각 도구 |
|---|---|---|
| Segmed | 4 섹션 (Life Sciences R&D / Medical Devices / Data Mgmt / Providers) | 번호만, 아이콘·스크린샷 없음 |
| Gradient | 4-step process (Sourcing → De-ID → Organization → Delivery) | 아이콘 |
| Truveta | 4 pillars (Safety / HEOR / Clinical trials / R&D) | 아이콘 |
| Rhino | 3 pillars ("Eliminate Barriers" / "Maintain Security" / "Let Insights Break Free") | 대시보드 스크린샷 1장 |
| Flywheel | 6 capability cards (Cohort Discovery / Dataset Curation / ... / Model Training) | 아이콘 placeholder |
| Aidoc | 4 specialty cards (Radiology/Cardio/Neurovascular/Vascular) + 각 **구체 메트릭** | "31% faster time-to-notification for PE patients" |
| Stripe | 6 product category 섹션 + abstract wave 배경 | 스크린샷 대신 abstract motion |
| Linear | 5 modules (Intake/Plan/Build/Diffs/Monitor) + **실제 UI 스크린샷** | product screenshots |
| Vercel | Use case 5 tiles (AI Apps / Web / E-commerce / Marketing / Platforms) | 카테고리별 svg |
| Supabase | 6 modular product cards (Database/Auth/Edge/Storage/Realtime/Vector) | 아이콘 + 라이트/다크 |

**결정 포인트**:

- **Aidoc 식 "capability × 구체 메트릭" 이 RadiVault 에 가장 적합**. 예:
  - "Full PIPA §28-8 chain — from hospital PACS to buyer in <48 hours"
  - "Every study passes 3-layer de-ID: DICOM PHI + burn-in OCR + 3D defacing"
  - "Korean imaging diversity: 14 modalities × 500K+ indexed studies" (현재 실수치 아님 — 실수치 확정 후 공개)
- **Linear 식 "실제 제품 UI" 이 차별화 지렛대**. 경쟁사 대부분 UI 숨김. RadiVault 는 `/search` 의 실제 facet pane + 결과 테이블 + cohort sidebar 스크린샷을 **과감히 노출** (완전 익명 데모 데이터 `scripts/demo_seed/` 활용).

### 2.4 Social Proof (Testimonial, 숫자, 케이스)

**메트릭 전시 패턴**:

| 사이트 | 수치 유형 | 위치 |
|---|---|---|
| Segmed | 2,800+ partner sites · 150M+ studies · 50+ FDA-cleared products · 5 continents | 헤로 아래 "Empowering Health" 섹션 |
| Gradient | 19M+ studies · 22M+ delivered · 100+ AI customers | 헤로 바로 아래 |
| Truveta | 130M+ patients · 200M claims · 30 member health systems | 페이지 중단 "Trusted by" 근처 |
| Harrison.ai | 3,500 clinicians · 1,000+ sites · 40+ countries · $240M funding | 페이지 여러 위치에 반복 노출 |
| Aidoc | 1,600+ medical centers · "31% faster"·"34% reduction" | 헤로 + capability cards 에 분산 |
| Databricks | "60% of Fortune 500" · "20,000 customers" · "5x Gartner Leader" | 헤로 아래 |
| Stripe | 135+ currencies · $1.9T processed 2025 · 99.999% uptime · 200M+ subscriptions | 산재 |
| Hugging Face | 2M+ models · 500k+ datasets · 50,000 organizations · Transformers 159k GitHub stars | 페이지 전반 |

**RadiVault 초기에 사용할 수 있는 수치 (실측 기반)**:

| 수치 | 실근거 | 노출 가능성 |
|---|---|---|
| **TCIA seed 400 studies · 5 컬렉션** | scripts/demo_seed/ + seed_config.yaml | ○ "Demo dataset based on public TCIA" 라벨 필수 |
| **metadata-index 6 facet, <2초 p95** | dev-spec-metadata-index §FR-9, 성능 SLA | ○ |
| **Gateway Agent outbound-only + TLS 1.3** | ARCHITECTURE §3.3 | ○ |
| **12-state FSM → 5-phase buyer view** | order-fulfillment dev-spec | ○ |
| **Pilot hospital: 0 contracted (as of 2026-04-24)** | progress.txt 진실 | ✗ 공개 금지 |

**권고**: 홈페이지 v0.1 은 **"technology-first" 방식** — "Built on open DICOM standards, tested against the TCIA reference dataset (400 studies, 5 collections)" 스타일. 경쟁사 수치 흉내 내는 대신 **real, small, honest**.

### 2.5 Footer 아키텍처

**컬럼 수 분포**:

| 사이트 | 컬럼 | 주요 섹션 |
|---|---|---|
| Segmed | 4 | Main / Technology / Publications & News / Legal & Regulatory |
| Gradient | 3 | AI developers / Data Partners / About Us (docs, API, 가격 없음) |
| Stripe | 7 | Products, Solutions, Developers, Integrations, Resources, Company, Support |
| Vercel | 6 (+ 하위 columns) | Get Started / Build / Scale / Secure / Resources / Learn |
| Linear | 7 | Product, Features, Company, Resources, Connect, Legal |
| Supabase | 7 | Product, Solutions, Resources, Developers, Community, Company, Legal |
| Ncloud (KR) | 4 + 법적 푸터 | Ncloud 소개 / 리소스 / 전문가 지원 / 도움 + **사업자등록·대표자·주소·전화** |
| KINX (KR) | — | + 사업자등록번호 + 02-526-0900 |
| VUNO (KR) | — | + 02-515-6646 + 사업자등록 + 개인정보 16 섹션 |

**핵심 차이 (영미 vs 한국)**:

- **영미 SaaS**: "Legal" 섹션에 Privacy / Terms / Cookie Policy 만. 회사 대표·주소·사업자번호 **미표기**.
- **한국 B2B**: 풋터 하단에 반드시 **대표이사·사업자등록번호·통신판매업 신고번호·주소·전화 1544-xxxx** 표기. 법적 의무 (전자상거래법, 통신판매업자 정보표시) + 문화적 신뢰 신호.

**RadiVault 적용**:
- **글로벌 영문 페이지** (`/` 또는 `/en`): Stripe/Vercel 스타일 다컬럼. Trust Center · SOC 2 status · Security whitepaper 링크 필수.
- **한국어 페이지** (`/ko` 또는 `hospital.radivault.io`): 풋터 하단에 법적 섹션. "RadiVault Inc. 대표자: Kyle Jeon · 사업자등록번호: [TBD] · 주소: [TBD] · 고객센터: [TBD]". 없으면 **병원 CTO 가 "실체 없는 스타트업" 으로 인식**.

### 2.6 Visual Language

**색상 팔레트 스펙트럼**:

- **보수적 파랑/네이비 (의료·금융 정석)**: Segmed (teal/blue), Aidoc (teal/blue), Snowflake, Databricks 레드만 예외.
- **차가운 블루+틸 (의료 SaaS 기본값)**: Truveta (teal + 블랙), Rhino (navy/white), Flywheel (blue/gray).
- **단색 + 제스처 (모던 SaaS)**: Linear 다크, Vercel 다크 기본 + 네온 그라디언트, Stripe 라이트 + subtle wave.
- **친근한 브랜드**: Hugging Face 이모지 🤗 + grays, Replicate 바나나 🍌, Plaid Franklin 일러스트 + 그라디언트 레인보우.
- **한국**: Ncloud 네이버 그린, VUNO 그레이스케일 + 미니멀, Lunit 화이트+블루+미니멀.

**이미 확정된 RadiVault 토큰** (Session 12, buyer-portal-demo v0.1):
- **Buyer blue**: 로그인 이후 글로벌 바이어 포털 주 색상.
- **Hospital teal**: 로그인 이후 국내 병원 콘솔 주 색상.

**결정 포인트 (디자이너에게)**:
- **홈페이지는 어떤 톤?** Buyer blue 로 통일 (글로벌 톤) vs Blue/Teal 듀얼톤 (이중 페르소나 가시화).
  - 권고: **Blue 톤 기본 + 한국 병원 페이지만 Teal 액센트**. 이미 확정된 토큰 재사용, 새로 도입 금지.
- **다크모드 디폴트?** Vercel/Linear 는 다크. Stripe·Segmed 라이트. **의료·컴플라이언스 타깃이라 라이트 권고** (야간 대시보드는 예외).

**타이포그래피**:
- 영문: Inter, IBM Plex Sans, 또는 Geist (Vercel). **시스템 폰트 중립적**.
- 한글: Pretendard 또는 Spoqa Han Sans. 이미 Ncloud·VUNO 가 자체 한국어 특화 폰트.
- **본문 행간 1.6~1.8**, Ncloud 관찰.

**일러스트 vs 제품 UI**:
- 경쟁사 다수: 일러스트·아이콘 (Segmed·Gradient·Rhino·Flywheel). 스크린샷 약함.
- Linear·Stripe·Supabase: **실제 UI 중심**.
- **권고: UI 중심 (Linear 스타일)**. 이미 `web/portal` 이 있음. "demo fixture 로 캡처한 실 화면" 을 영웅 이미지로.

### 2.7 Lead Capture 패턴

| 패턴 | 사이트 | 특징 |
|---|---|---|
| **뉴스레터 (이메일 only)** | Segmed, Flywheel ("Join over 6,000 researchers"), Gradient ("Stay in the know"), OneTrust ("Be in the know") | 정기 콘텐츠 배포 ROI 필요 |
| **"Book a call / Request demo"** | Segmed, Aidoc, Rhino, Harrison.ai, Lunit, VUNO | 의료 산업 표준 |
| **Self-serve 가입 바로** | Stripe, Vercel, Supabase, Replicate, HF | 개발자 제품 |
| **Free trial** | Gradient ("7-day free trial, no CC") | B2B 하이브리드 |
| **"Contact us" 만** | Truveta, Databricks 일부 | 엔터프라이즈 sales-led |

**RadiVault 현 상태**:
- Buyer 는 API key 발급을 `search-admin` CLI 로만. 웹 self-serve 가입 **미구현**.
- 홈페이지 첫 번째 리드 채널 필요: **"Request data access" 폼** (B2B sales-led 정석). 의료영상 데이터 특성상 **self-serve 가입은 컴플라이언스 리스크** — 누가 다운받는지 검증 필요.

**권고**:
- **Primary CTA**: `Request data access` 또는 `Book a call` (B2B 표준)
- **Secondary CTA**: `Read the technical overview` (`docs.radivault.io` 또는 whitepaper PDF 다운로드) — Segmed 의 white paper gate 패턴.
- **Tertiary**: 뉴스레터 — CEO 미팅 준비엔 우선순위 낮음. Phase 2 이후.

### 2.8 Pricing 가시성

| 레벨 | 사이트 |
|---|---|
| **전액 공개 (tier table)** | Stripe, Supabase, Vercel (부분), Hugging Face ($20/user/month), Replicate (GPU $/sec) |
| **부분 공개 (시작가)** | HF ($0.60/hr GPU), Stripe (Pro $0.01/1K tokens) |
| **"Contact sales" 전액 숨김** | Segmed, Gradient (일부), Truveta, Rhino, Databricks, Aidoc, Annalise, Lunit, Flywheel, Centaur, OneTrust |

**의료영상 데이터 업계는 100% sales-led**. 이유: (a) 데이터셋 크기·라이선스 범위 협상 변수, (b) 규제 관리 비용 variable, (c) MSA 협상 필요.

**권고**: RadiVault v0.1 공개 홈페이지는 **"Contact for pricing"**. `order-flow-quickstart-buyer-en.md §13` 의 paid tier `total_estimated_usd` 는 **로그인 이후 주문 플로우에서만** 노출. Segmed/Aidoc 와 동일.

### 2.9 차별화 섹션 — RadiVault 가 가져야 할 것

경쟁사 분석을 관통하는 공통점: **"어떻게 익명화되는지 기술적 프루프 없이 컴플라이언스 배지만 전시"**. RadiVault 는 이 공백을 직접 친다.

**권고 추가 섹션 (홈페이지)**:

1. **"How compliance works" (기술 증거)**: 3-step diagram (1) DICOM PHI 태그 제거 PS3.15 Annex E / (2) burn-in OCR 마스킹 / (3) 3D defacing (pydeface). 각 단계에 GitHub repo 링크 (오픈소스 컴포넌트 투명성). Rhino 의 "Share Insights NOT Raw Data" 와 대조 — 우리는 **실제 어떻게** 를 보여준다.

2. **"Chain of custody" 뷰**: 병원 PACS → Gateway → De-ID → 중앙 → 바이어. 로그 이벤트 스크린샷. 이미 dev-spec 에 WORM audit log 있음.

3. **"Korean advantage"**: 데이터 다양성 맥락 (Segmed "5 continents" 와 차별). "Korea's 53M population · 98% health insurance coverage · OECD-top hospital density · K-pop-level imaging equipment installs per capita". **한국 특유 가치 제안**.

4. **Investor / partnership box**: 메인 CTA 옆 소형 "For investors" 링크 — CEO 미팅 후속으로 자연스럽게.

### 2.10 A. 섹션 추천 3 가지

**A-1. 헤로는 "범주 점유 + 48h SLA 실제 수치"**
- Headline: "Korea's medical imaging data — compliantly delivered to global AI in 48 hours."
- Subhead: "RadiVault indexes anonymized DICOM metadata from Korean hospitals, delivering regulatory-grade imaging datasets under PIPA §28-8. Search, verify, and receive — without ever exposing raw patient data."
- 좌측 CTA `Request data access`, 우측 `View technical overview (PDF)`.
- 오른쪽 시각: **실제 `/search` 스크린샷 1 장 (demo fixture 기반)** + 왼쪽 facet + 중앙 테이블 + 우측 cohort sidebar.

**A-2. Trust bar 는 "컴플라이언스 status ladder" (로고 없을 때 대체)**
- 4 칼럼: "PIPA §28-8 compliant" / "SOC 2 Type II in preparation (Phase 2)" / "ISO 27001 aligned (Phase 3)" / "HIPAA-aligned de-identification (Safe Harbor + Expert Determination)".
- 각 배지 클릭 → `/trust-center` 페이지 (Segmed/Vanta 패턴).
- **"in preparation" / "aligned" 보수 어투 고수** — `docs/marketing/one-pager-buyer-global-en.md` §4 와 1:1 동일.

**A-3. 한국어 홈페이지 (`/ko` 또는 `hospital.radivault.io`) 는 Ncloud 관습 100% 적용**
- 풋터 최하단 법적 블록: 대표자 / 사업자등록 / 주소 / 고객센터 전화 / ISMS·ISO 인증 배지.
- 고객 상담 채널 이원화 (sales@·tech@·legal@ 3 개 이메일 + 1:1 문의 폼 + 카카오채널 준비).
- 한국식 "회사소개 → 솔루션 → 도입사례 → 채용 → 문의" IA (국내 대기업 의사결정자 회피 클릭 최소).

---

## 3. B. 구매자 포스트-로그인 UX 폴리싱

> `buyer-portal-ux-competitive.md` 가 이미 Gen3/TCIA/IDC 3-pane 레이아웃 · FSM phase 매핑 · 다운로드 3탭 정리 완료. 여기선 **시각 폴리시·정보 밀도·베스트 프랙티스 bezel** 보강.

### 3.1 현재 `web/portal` vs 목표 수준

| 화면 | 현재 | 타깃 폴리시 수준 |
|---|---|---|
| `/search` | minimal table + facet pane (Session 12 blue tokens) | Linear 수준의 UI 일관성 + Aidoc 수준의 metric 비주얼 |
| `/orders` | list + detail | Stripe Dashboard 수준의 phase stepper + timeline drawer |
| `/orders/:id` | PhaseStepper + 기본 상태 | Stripe "Payment Intent details" 수준 |
| `/hospital` | 6-tile | 데이터 밀도 높이고, Ncloud 풍 한국어 카드 |
| Billing · Settings | stub only | 일단 v0.1 은 placeholder + clear "coming soon" |
| **Empty state** | 빈 페이지 | Linear/Supabase 수준 일러스트 + CTA |
| **Error state** | alert-only | Stripe 수준 — 에러 코드 + 설명 + 다음 단계 |

### 3.2 Dashboard 첫 화면 구성 패턴 (관찰)

| 사이트 | 포스트-로그인 첫 화면 |
|---|---|
| Stripe Dashboard | KPI 타일 (가용 잔액·처리량·고객 수) + 최근 payments 리스트 + 알림 카드 |
| Linear | 현재 사이클 이슈 리스트 + 에이전트 활동 |
| Vercel Dashboard | 프로젝트 그리드 + 최근 deploy 상태 |
| Supabase | 프로젝트 선택 → 프로젝트별 overview (리소스·API usage) |
| Hugging Face | 내 models / spaces / datasets 그리드 |
| AWS Data Exchange | 구독한 datasets + 최근 download |
| Gradient Atlas (추정) | 최근 cohort · 주문 이력 |

**RadiVault `/search` 가 곧 첫 화면이 되어야 하나?**
- 경쟁사 관행: **첫 화면은 "무엇이 벌어지고 있는가" 대시보드** (Stripe, Linear, Vercel).
- 현재 `web/portal` 은 로그인 → `/search` 리디렉트. 이것은 "유저가 뭘 할지 이미 안다" 가정.
- **권고**: `/` (로그인 이후) 는 **대시보드**로 전환. 타일:
  - **Active orders** (count + phase progress mini)
  - **Saved cohorts** (v0.1.1 backlog — v0.1 은 placeholder)
  - **Recent searches** (로컬 storage 로 일단 구현 가능, 0.5 day)
  - **Platform announcements** (changelog — `docs/marketing/changelog-v02-pixel-deid-ko.md` 가 이미 존재, RSS·MDX import)
  - **Pending invoices** (v0.1 stub)
  - **API usage this month** (rate limit ← metadata-index)

### 3.3 검색 결과 시각화 (경쟁사 비교)

`buyer-portal-ux-competitive.md §3~4` 에 이미 자세히 정리. 여기선 **시각 밀도** 만 추가:

- **Linear issue list**: 한 row = status icon(8px) + title + assignee avatar(20px) + cycle label(4×12 badge) + priority dot(6px) + updated relative time. **정보 7 개를 한 row 에**.
- **Stripe payments list**: amount · currency · customer · status badge · method icon · date · receipt link (hover).
- **현재 RadiVault `/search` row**: check + pseudo_UID + modality badge + body_part + n_instances + size_mb + study_year. 7 컬럼, **Linear 수준 정보 밀도**.

**폴리시 포인트**:
- row hover 시 **마이크로 차트** (연령 분포 mini-sparkline, Gradient 스타일). v0.1.1.
- 색상 코드화된 modality 배지 (CT=blue, MR=purple, CR/DR=green, MG=pink, US=orange, PT=red). 이미 색상 토큰만 추가하면 끝.

### 3.4 주문 플로우 멘탈 모델

| 사이트 | 비유 |
|---|---|
| TCIA/IDC | Manifest 다운로드 |
| Gradient | Cohort export |
| Stripe | PaymentIntent (이벤트 기반) |
| AWS Data Exchange | Subscription (구독) |
| Replicate | Pay-per-use 실행 |
| **RadiVault** | Order (FSM 12 state → 5 buyer phase) |

경쟁사 중 **Stripe PaymentIntent 의 phase stepper + details drawer** 가 RadiVault 12-state FSM 을 가리면서 SRE 에게는 내부 노출이 가능한 가장 가까운 모델. 이미 `buyer-portal-ux-competitive.md §7.2` 에 매핑 있음.

### 3.5 API Key · Billing · Usage UI

- **Stripe**: "Developers" 탭 — Publishable/secret keys, rotation, webhook secrets. **마스킹 (`sk_live_****...abcd`)** + 발급 후 단 한 번 평문 노출 경고.
- **Supabase**: Project API settings — anon key, service_role key, JWT secret. 비슷.
- **HF**: Settings → Access Tokens — 토큰 expire date + usage.
- **Vercel**: Teams → Members · API Tokens separated.

**RadiVault 현**: `rv_live_*` 키 발급은 CLI 전용. 포털에는 **마스킹 리스트 + revoke 만** 이미 `buyer-portal-ux-competitive.md §9.2` 에 있음. Stripe 수준 복제 필요.

### 3.6 B. 섹션 추천 3 가지

**B-1. `/` (로그인 이후) 를 대시보드로 전환**
- Stripe 수준 5~6 타일 (active orders / recent searches / pending invoices / API usage / announcements).
- 현재 `/search` 로 리디렉트는 **검색이 곧 유일한 작업** 오해를 준다. Kyle 결정 (§5 참고).

**B-2. 검색 테이블 polish — Linear 수준의 hover state + 색 배지**
- Modality 색상 토큰 6 개 추가 (tokens CSS var).
- Row hover 시 마이크로 차트 (v0.1.1, 1day).
- 페이지네이션·정렬은 이미 dev-spec-metadata-index 있음 — UI 는 shadcn/ui DataTable 로 통합.

**B-3. Order detail 페이지 drawer (Stripe 스타일)**
- 5-step phase stepper (메인) + **"View raw events" 우측 드로어** (12-state 타임라인 + event log).
- SRE·디버그용. 이미 FSM 구조는 `order-fulfillment` dev-spec 있음.

---

## 4. C. 병원 사용자 포털 (Hospital Admin Post-login)

> 한국어 우선. 현재 `web/portal/src/app/hospital/HospitalDashboard.tsx` 는 6 타일.

### 4.1 한국 B2B 대시보드 관습 (Ncloud·KINX·VUNO 관찰)

**공통 IA**:
- **좌측 네비 (collapsed 가능)** + 중앙 콘텐츠. Ncloud 의 16 카테고리 → 단계적 드릴다운.
- **상단 탑 바**: 로고 · 주요 메뉴 · 알림 · 사용자 계정 · 고객센터 링크 **(반드시)**.
- **하단 법적 풋터**: 사업자등록 · 주소 · 전화 · 개인정보처리방침 링크.

**한국 B2B 신뢰 신호**:
- **전화번호 항상 노출** (고객센터 · 영업 · 기술지원 각각).
- **개인정보처리방침 섹션 16 개 (VUNO)** ← 이 정도 밀도를 갖춰야 "진지한 업체".
- **1:1 문의 · 온라인 문의 폼 · 카카오톡 · 이메일** 다채널.
- **보안 인증 (ISMS-P · ISO 27001) 로고** — 한국 병원 DPO 가 찾는 첫 번째 신호.

**과도하게 모던한 스타일 지양** (Kyle 원 명세):
- Linear·Vercel 의 다크모드 네온은 **"신뢰감 부족"** 으로 해석될 가능성.
- Ncloud·VUNO 가 택한 **라이트 테마 + 약간 정돈된 그레이스케일 + 액센트 컬러 절제** 가 한국 병원 CTO/DPO 에게 친숙.

### 4.2 기존 6-tile 대시보드 업그레이드 방향

`buyer-portal-ux-competitive.md §12.2` 의 6-tile 레이아웃은 유지하되, **시각 밀도 +30%**:

**현 타일 → 개선안**:

| 현 타일 | 개선 |
|---|---|
| Studies indexed | + 연월별 증분 sparkline (Recharts, 1day) |
| Cumulative revenue | + "예상 정산일 YYYY-MM-DD" (Toss Payments 스타일) |
| Orders last 30d | + 바이어 산업 분포 (no 실명, "Life Sciences 40% · AI Devices 35% · Academic 25%") 도넛 |
| Gateway status | + 최근 24h uptime bar (Stripe 99.999% 스타일) |
| Revenue by month | bar + stacked by tier (free/preview/paid) |
| Opt-out queue | + 평균 처리 시간 |
| **+ 추가 타일: Data quality trend** | burn-in flag / de-id reject 비율 라인차트 (7d · 30d 전환) |
| **+ 추가 타일: Hospital-specific news** | 운영자 공지 (de-id 정책 변경·계약 갱신·세금계산서) |

### 4.3 감사 로그 뷰어 (compliance 신뢰 시각화)

- **Stripe**: Events 탭 — API 요청·webhook 이벤트 시간순 리스트 + 필터. JSON 상세.
- **AWS CloudTrail**: 시간 기반 + source IP + service + action + resource.
- **Snowflake Access History**: 테이블 단위 SELECT/UPDATE 이력.

**RadiVault Hospital 포털 권고**:
- 6-tile 아래에 **"감사 로그 미리보기" 섹션** — 최근 20 이벤트 (order fulfillment · opt-out · de-id run · revenue settlement).
- "전체 로그" 링크 → 필터 가능 (날짜 범위·이벤트 타입·연관 order_id).
- 이미 `ARCHITECTURE §4.7` 에 WORM 감사 저장 있음. UI 만 추가.
- **이것이 병원 CTO 에게 "진짜로 추적된다" 신뢰 심음**.

### 4.4 한국어 레이아웃 주의사항

- **한국어는 영문보다 10~20% 짧음** (글자 수). 타이틀 줄바꿈 없이 한 줄 유지 쉬움.
- **자간·행간**: Ncloud 관찰 — 행간 1.6~1.8, 자간 기본값. 과한 자간은 "번역투".
- **라벨 길이**: "주문 내역" (4자) vs "Order history" (13자). **카드 타이틀에서 한글은 굵게 + 큰 폰트** 가능 (영문은 조절 필요).
- **숫자 표시**: "₩ 18,400,000" vs "₩ 18.4M" — 한국 대기업 대시보드는 **원 단위 풀스펠** 선호 ("18,400,000원"). 병원 경영진 친숙.

### 4.5 지도 시각화 (B-3 한국 병원 위치)

현재 이미 있는 타일. 업그레이드:
- **한국 행정구역 choropleth** (시도별 스터디 수). `react-simple-maps` + `topojson-maps` 또는 Naver/Kakao Maps API.
- 병원 실명 노출 금지 (opt-in 병원만). **집계 heatmap** 으로 대체.
- 외국 바이어 포털과 대칭: 바이어 페이지 헤로에도 작은 한국 지도 일러스트 → "지리적 다양성" 시각화.

### 4.6 C. 섹션 추천 3 가지

**C-1. 6-tile → 7~8 타일 + 각 타일에 sparkline**
- Ncloud 수준의 정보 밀도. Recharts + shadcn Card. 추가 공수 2~3 day.

**C-2. 감사 로그 뷰어 프리뷰 섹션**
- Hospital Dashboard 하단에 "최근 감사 로그" 섹션. Link to `/hospital/audit-log` (v0.2 전체 뷰).
- 병원 DPO·CTO 의 신뢰 획득 키.

**C-3. 한국식 풋터 + 고객 상담 패널**
- 풋터 하단 법적 블록 (대표자·사업자등록·주소·전화).
- 우측 하단 플로팅 상담 버튼 — "1:1 문의" (Ncloud 패턴). Phase 1 은 mailto 또는 Zendesk 등 간단 SaaS.

---

## 5. RadiVault 디자인 북극성

### 5.1 네 개의 디자인 원칙

1. **정보 밀도 높음 (high density)** — Linear·Stripe 수준. 의료·B2B 타깃은 "정보 숨기기" 보다 "정보 정돈" 선호. 공백 넉넉 + 정보 계층 명확.
2. **신뢰 우선 (trust first)** — Segmed·Rhino 보다 더 **구체 증거**. 기술·법률 프루프 링크를 아끼지 않음. "in preparation" 보수 어투 유지.
3. **이중 언어 (bilingual by design)** — 영어 전용/한국어 전용 페이지를 각각 **완전**히 지원. 번역만 한 느낌 금지. 특히 한국어 페이지는 한국 B2B 관습 (법적 풋터·전화번호·ISMS 배지) 고수.
4. **Compliance 강조 (compliance-first)** — 컴플라이언스 배지를 헤더·헤로에 전진 배치. Trust Center 링크 눈에 띄게. OneTrust·Rhino·Snowflake 수준.

### 5.2 브랜드 톤

- **보수적이되 자신감 있게**. Segmed 의 "regulatory-grade" 어투 차용.
- **겸양하되 명확히**. "in preparation" · "aligned" 같은 보수 어투 유지 (이미 `docs/marketing/*-en.md` 컨벤션).
- **기술적이되 접근 가능하게**. Stripe 의 "code-first but readable" 밸런스.

### 5.3 안 하는 것 (anti-patterns)

- **이모지 남발** (HF·Replicate 스타일) — 의료·규제 산업엔 부적합.
- **다크 네온 그라디언트** (Linear·Vercel 기본) — 신뢰성 우위 산업 아님.
- **"We are disrupting" 톤** — Segmed·Aidoc·Lunit 모두 회피. RadiVault 도 동일.
- **"Free trial" 전면 CTA** — Gradient 만 유일. 의료 데이터 접근의 self-serve 는 규제 위험. RadiVault 는 "Request access" 유지.
- **무의미한 그라디언트·blob 일러스트** — 경쟁사 Rhino 가 그런 경향. 실 제품 UI 보여주는 게 더 강력.

---

## 6. 후속 design-spec 에 전달할 핵심 결정 포인트 10 개

| # | 결정 | 옵션 | 권고 |
|---|---|---|---|
| 1 | **홈페이지 도메인 구조** | 단일 (radivault.io) vs 분리 (radivault.io + portal.radivault.io + hospital.radivault.io) | 분리 3도메인. 이미 `buyer-portal-ux-competitive.md §13.3` 결정 flag. |
| 2 | **Hero headline 후보** | A (PRD tagline), B (48h SLA), C (PIPA 법적 차별), D (파트너십) | **A 또는 B**. C 는 한국 전용 세그먼트. |
| 3 | **Trust bar 패턴** | 고객 로고 / 컴플라이언스 배지 / 기술 스택 / 하이브리드 | **컴플라이언스 배지 + 기술 스택 (오픈소스)**. 파일럿 확정 후 로고 추가. |
| 4 | **Value prop 섹션 개수·시각** | 3 / 4 / 5 · 아이콘 / 스크린샷 / 하이브리드 | **4 섹션 + 실 제품 스크린샷** (Linear 스타일). 완전 익명 데모 데이터 사용. |
| 5 | **Primary CTA 카피** | "Request data access" / "Book a call" / "Get started" | **"Request data access"** (B2B 표준). Secondary: "View technical overview (PDF)". |
| 6 | **색상 톤** | Blue 통일 / Blue+Teal 듀얼 | **Blue 기본 + 한국 페이지만 Teal 액센트**. Session 12 토큰 재사용. |
| 7 | **타이포** | 영문 Inter / Geist / Pretendard · 한글 Pretendard / Spoqa | **영문 Inter, 한글 Pretendard**. 시스템 폰트 대체 안전성 |
| 8 | **라이트/다크** | 라이트 기본 / 다크 기본 / 토글 | **라이트 기본 + 토글 (optional v0.1.1)**. 의료 컴플라이언스 타깃. |
| 9 | **풋터 구조** | Stripe 식 7컬럼 / Segmed 식 4컬럼 | **한국어 페이지는 4컬럼 + 법적 블록, 영문 페이지는 6~7컬럼**. |
| 10 | **가격 표시** | 전액 / 시작가 / Contact sales | **Contact for pricing** (의료 데이터 업계 100% 표준). 로그인 후 주문 플로우에서만 per-study 단가. |

---

## 7. 참고 URL 일람 (인용처)

### 1차 (경쟁사 공식)

- Segmed 메인: https://www.segmed.ai/
- Segmed Security & Compliance: https://www.segmed.ai/security-compliance
- Segmed Trust Center (Vanta): https://app.vanta.com/segmed/trust/hrgkv68wzt5g55jzugqmy
- Gradient Health 메인: https://gradienthealth.io/
- Gradient Atlas 제품: https://gradienthealth.io/atlas/
- Truveta: https://www.truveta.com/
- Rhino Federated Computing: https://www.rhinofcp.com/ (rhinohealth.com 에서 301)
- Flywheel: https://flywheel.io/
- Centaur Labs: https://centaur.ai/ (centaurlabs.com 에서 301)

### 1차 (의료 AI 제품)

- Aidoc: https://www.aidoc.com/
- Harrison.ai (Annalise 모회사): https://harrison.ai/ (annalise.ai 에서 301)
- Lunit: https://www.lunit.io/en
- VUNO: https://www.vuno.co/
- JLK: https://www.jlkgroup.com/

### 1차 (SaaS polish 기준선)

- Stripe: https://stripe.com/
- Linear: https://linear.app/
- Vercel: https://vercel.com/
- Supabase: https://www.supabase.com/
- Plaid: https://www.plaid.com/

### 1차 (Enterprise compliance)

- OneTrust: https://www.onetrust.com/
- Snowflake: https://www.snowflake.com/en/
- Databricks: https://www.databricks.com/

### 1차 (API-first marketplace)

- Hugging Face: https://huggingface.co/
- Replicate: https://replicate.com/

### 1차 (한국 B2B)

- Naver Cloud Platform: https://www.ncloud.com/
- KINX: https://kinx.net/

### 2차 (이미 있는 RadiVault 내부 docs)

- `docs/research/buyer-portal-ux-competitive.md` — 포스트-로그인 UX 13 개 경쟁사 분석
- `docs/research/demo-pitch-references-radivault.md` — 데모 연출 레퍼런스
- `docs/marketing/competitive-positioning-buyer-en.md` — 경쟁사 대비 포지셔닝
- `docs/marketing/one-pager-buyer-global-en.md` — 현재 영문 마케팅 어투 앵커
- `docs/specs/design-spec-buyer-portal-demo.md` — 현재 포털 디자인 스펙 (125KB)

---

## 8. 한계·오픈 퀘스천 (Kyle 결정 필요)

### 8.1 Kyle 결정 필요 (UX)

1. **홈페이지 도메인 분리** — `radivault.io` (마케팅) + `portal.radivault.io` (바이어 로그인) + `hospital.radivault.io` (국내 병원) 3도메인으로 분리할지, 아니면 `radivault.io/{ko|en|portal|hospital}` 단일 도메인으로 유지할지.
2. **Hero headline 최종 카피** — A / B / C / D 중. `docs/marketing/one-pager-buyer-global-en.md` 카피와 1:1 동기화 필수.
3. **헤로 시각 모티프** — 실제 포털 스크린샷 (demo fixture 기반) vs abstract 일러스트. 전자 권고.
4. **Pricing 페이지 존재 여부** — "Pricing" 메뉴 자체를 제공할지. 권고: "Pricing" 링크 있되 클릭 시 `Contact for pricing` 폼으로.

### 8.2 Kyle 결정 필요 (법무·브랜드)

5. **컴플라이언스 어투** — "HIPAA-compliant" vs "HIPAA-aligned" vs "designed to support HIPAA compliance". 법무 자문 필요. 현재 `docs/marketing/*-en.md` 는 보수 어투 선택. 홈페이지도 동일 유지 권고.
6. **로고 공개 정책** — 파일럿 병원 확정 시 로고 사용 허락 조항을 MSA 에 포함할지. 병원 측 거부 가능성 높음 (한국 병원 관행).
7. **법률 페이지 구조** — `/terms` · `/privacy` · `/cookies` · `/security` · `/trust-center` · `/legal/pipa-28-8` 각각 별도 페이지 여부. 법무 자문.
8. **사업자등록·주소·대표자 공개** — 한국 페이지 풋터. 의무. 단, Delaware 법인 설립 전까지 한국 법인만 표기할지.

### 8.3 추가 조사 필요

9. **Toss Payments·KB국민카드·한국 결제 게이트웨이** 한국 B2B 풋터 관습 실제 샘플 — 본 리서치에서 Toss Payments SPA 접근 실패, 추가 조사 필요.
10. **파일럿 병원 후보 기관 웹사이트** — 그들의 IT 포털 컨벤션 (AMC, SNUH, 연세대의료원) 을 따로 분석. 병원 CTO 가 "친숙" 하다고 느끼는 레퍼런스 확정 필요.
11. **LIG Survey · KAIT 한국 B2B 웹사이트 트렌드 리포트** — 한국 B2B SaaS 고객 경험 지수 같은 외부 리포트 확인.
12. **경쟁사 NDA 요청 → Segmed·Gradient 실 제품 데모** — Kyle 이 sales 미팅 잡고 포털 내부 스크린샷 확보. 공개 문서로는 한계.

### 8.4 본 리서치의 한계

- 경쟁사 **포스트-로그인 실제 UI** 는 공개 스크린샷 1~2 장에 의존. **추정** 비중 높음. 이는 `buyer-portal-ux-competitive.md` 에도 동일 한계 명시.
- 한국 의료기관 **IT 포털 레퍼런스** (AMC, SNUH, 연대세브란스 등) 는 본 리서치에 포함 안 됨 — 이는 별도 태스크로 분리.
- 이모지·애니메이션 같은 **모션 그래픽 가치** 는 정적 분석으로 판단 어려움. 디자이너 단계에서 prototype 필요.
- **접근성 (WCAG 2.2 AA)** 관점 리서치 제외. design-spec 에서 별도 check.

---

## 9. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|---|---|---|---|
| 0.1 | 2026-04-24 | @researcher (Claude Opus 4.7) | 최초 작성. 15 개 경쟁·인접·베스트 사이트 분석. §1~§8 완결. CEO 미팅 D-14 근거 문서. |

---

**Disclaimer**: 본 문서는 법률 자문이 아니다. "HIPAA-compliant" · "PIPA-aligned" · 비교 광고 표시 등 모든 컴플라이언스·브랜드 어투는 Kyle + 외부 변호사 재검증 필요. 경쟁사 이름 언급은 객관적 관찰 한도 내이며 표시광고법 관점에서 leave-behind 배포 시 재검토 권고.
