# 디자인 명세 — Buyer UX 평가 + v2 개선안 (HTML 목업 포함)

> **Status**: Draft v0.1 · **Feature slug**: `buyer-ux-evaluation` · **Last updated**: 2026-04-25
> **작성자**: @designer (Claude Opus 4.7 [1M])
> **근거**:
> - 기존 dev-spec: [`dev-spec-portal-redesign.md`](./dev-spec-portal-redesign.md), [`dev-spec-buyer-auth.md`](./dev-spec-buyer-auth.md), [`dev-spec-buyer-browse-preview.md`](./dev-spec-buyer-browse-preview.md)
> - 리서치: [`buyer-browse-preview-download.md`](../research/buyer-browse-preview-download.md) §3·§4·§7, [`portal-redesign-competitive-analysis.md`](../research/portal-redesign-competitive-analysis.md), [`metadata-extraction-and-thumbnail.md`](../research/metadata-extraction-and-thumbnail.md) §4.1, [`buyer-auth-research.md`](../research/buyer-auth-research.md)
> - 기존 design-spec 토큰 승계: [`design-spec-portal-redesign.md`](./design-spec-portal-redesign.md) §4 (Buyer blue / Hospital teal / Slate neutral)
> - PRD: [`docs/prd.md`](../prd.md), UI 가이드: [`docs/UI_GUIDE.md`](../UI_GUIDE.md)
> - 현재 코드: `web/portal/src/app/{search,studies/[uid],account}`, `web/portal/src/components/buyer/{StudyCard,FacetSidebar,MarketplaceNav}`

> **본 문서의 위치**: 이 명세는 **재디자인 평가/제안서** 다. 정상 파이프라인(Phase 2 dev-spec → Phase 3 design-spec)이 아니라, "현재 구현된 buyer 화면이 경쟁사 대비 어디가 부족하고 RadiVault 차별점이 어떻게 더 잘 드러나야 하는가" 를 HTML 목업으로 제시한다. 본 문서가 호의적으로 검토되면 **후속 dev-spec append (`dev-spec-buyer-browse-preview.md` v0.3 또는 신규 `dev-spec-buyer-ux-v2.md`)** 로 이어진다.

---

## 1. 디자인 개요

RadiVault 의 현재 buyer-side 3 화면(`/search`, `/studies/[uid]`, `/account`)은 **기능적으로 작동**하지만, 경쟁사(Segmed, Gradient Health, TCIA, IDC, Flywheel) 대비 (a) 첫 방문자 5초 이해 가능성, (b) RadiVault 만의 차별점(Federated 2 병원, PIPA-native, Stripe-style API) 노출, (c) cohort builder 직관성 측면에서 **3개 모두 개선 여지가 크다**. 본 명세는 평가·흡수·개선안·HTML 목업 4단계로 구성된다.

---

## 2. 현재 buyer 화면 평가 (객관적 비판)

### 2.1 `/search` — 3-pane 검색

**잘된 점**
- 3-pane 레이아웃 (facet sidebar 280px / 결과 list / cohort sidebar 320px) 자체는 IDC·Gen3·Flywheel 의 표준 패턴과 일치 — 정보 밀도 적절.
- `min_hospitals` 슬라이더가 facet 최상단에 위치 — federated 차별점을 facet 으로 노출하는 설계는 좋음 (FacetSidebar.tsx L137-161).
- `FederatedSignal` 컴포넌트로 "X studies across Y hospitals" top banner 노출 (SearchApp.tsx L274-281) — 차별점 시각화 시도 존재.
- Cohort sidebar 가 sticky + sessionStorage 영속화 — TCIA cart 패턴과 일치, 페이지 새로고침 후에도 유지.

**못한 점**
- **첫 방문자가 "여기가 뭐 하는 곳" 5초 안에 모름**: 현재 `/search` 는 로그인 직후 곧바로 노출되는 첫 화면인데, "Korea hospitals"·"PIPA-native"·"de-id verified" 같은 차별점이 **상단 1 화면에 0 회 등장**. `FederatedSignal` 의 "250 studies / 2 hospitals" 만으로는 가치 제안 부족.
- **결과 카드가 너무 텍스트 중심**: StudyCard.tsx 는 9 컬럼 row(checkbox + 64px 썸네일 + modality badge + body_part + age + sex + n_instances + size + year + hospital chip). 썸네일이 64×64 px 로 작아 "preview 가능" 이라는 차별점이 시각적으로 약함. Gradient 의 "instant preview thumbnails" 와 비교 시 임팩트 약함.
- **Federated 신호의 시각적 구분 없음**: 모든 카드가 똑같이 보임. "이 study 는 본병원, 저것은 튼튼병원" 차이가 회색 chip 1개 (`HOSP-XXXXXX`)로만. 색상 구분 없음, 병원 이름 노출 없음(opaque ID).
- **PIPA / de-id audit 트레일 화면에 0 회 노출**: 카드 어디에도 "이 study 는 4-layer de-id 검증 완료" 라거나 "audit chain 보기" 링크가 없음.
- **모바일 fallback 이 사실상 빈 메시지**: SearchApp.tsx L246-249 — `"Mobile fallback ..."` placeholder 한 줄만. 경쟁사는 mobile 비지원이거나 모바일 전용 drawer 가 있는데, 우리는 빈 화면.
- **검색 후 결과 요약이 약함**: "1,247 studies · 31 ms" 형태의 hit + latency 노출이 없음. 데이터 엔지니어 신뢰 신호 부족.
- **Empty state 가 텍스트 한 줄**: SearchApp.tsx L298-303 — `"No results / Adjust filters."` 만. 일러스트 / 추천 facet / "TCIA seed dataset 으로 시작해보세요" 같은 CTA 없음.

**경쟁사 대비 부족**
- vs **TCIA**: TCIA 는 검색 결과 행에 thumbnail+animation+DICOM 3 버튼 = 3 가지 미리보기 진입점. 우리는 썸네일 1 개만.
- vs **IDC**: IDC 는 "Primary Site Location" / "Cancer Type" / "License" 같은 임상·법률 facet 노출. 우리는 modality/body_part/age/sex/manufacturer/year 6 개만 — IDC 가 더 풍부.
- vs **Gradient**: Gradient 는 "instant preview" + "Download CSV" 즉시 export. 우리는 cohort → /orders/new 단계 추가 필요.
- vs **Flywheel**: Flywheel 의 FlyQL 같은 query DSL 전혀 없음 (advanced search 부재).
- vs **Segmed**: Segmed 는 "longitudinal patient" (한 환자의 시간축 study 묶음) 강조. 우리는 study 단위만, patient 누적 없음.

### 2.2 `/studies/[uid]` — Study 상세

**잘된 점**
- `StudyDetailPanel` + `SaMDFooter` 분리 — SaMD 비분류 면책이 footer 에 항상 노출, 컴플라이언스 신뢰 강화.
- Add to cohort 버튼이 sessionStorage 동기화 — search 화면과 cohort 일관성 유지.
- 404 케이스 별도 처리 (StudyDetailClient.tsx L101-117) — graceful empty.

**못한 점**
- **Viewer 가 deferred placeholder**: 실제 DICOM viewer 없음. "이 study 가 어떻게 생겼나" 보려면 thumbnail JPEG 1 장만. Gradient 의 "instant preview" 차별점에서 후퇴.
- **메타데이터 표시 비효율**: 8 개 핵심 필드(modality / body_part / age / sex / manufacturer / model / study_date / n_instances) 가 한 panel 에 다 노출되어야 하는데, 현재 `StudyDetailPanel` 컴포넌트가 어떻게 분리하는지 명확치 않음. **prominent metadata 가 부족** — Segmed/Gradient 는 "2,800+ partner sites" 같은 메트릭을 카드에 박는데, 우리는 메타필드 그대로.
- **Sample download CTA 와 cohort CTA 분리 모호**: `dev-spec-buyer-browse-preview.md` 에서 "sample" tier 와 "order" tier 를 분리했는데, UI 에서 이 둘이 명확히 구분되어 보이지 않음 (현재 컴포넌트 추정).
- **Audit chain 링크 없음**: "이 study 가 본병원 → De-ID Engine → Hot Storage 어떻게 왔는지" 보고 싶은 buyer 가 클릭할 곳 없음. RadiVault 의 가장 큰 차별점 중 하나가 화면에 안 보임.
- **Sibling navigation 없음**: 검색 결과에서 study 1개 클릭 → 상세 → "다음 study" 네비 부재. 한 번 보고 다시 검색 화면으로 가야 함.
- **DICOM tag 노출 정책 불투명**: 어떤 tag 가 보이고 어떤 tag 가 안 보이는지(PHI scrub 결과) buyer 가 모름. "이 데이터의 익명화 수준" 신뢰 신호가 약함.

**경쟁사 대비 부족**
- vs **TCIA / IDC**: 둘 다 OHIF 임베드. 우리는 viewer placeholder.
- vs **Gradient**: "instant preview" 다중 슬라이스 nav. 우리는 1 frame.
- vs **Flywheel**: DICOM SEG / RTSTRUCT overlay. 우리는 raw thumbnail.
- vs **TCIA**: data origin disclosure(어느 컬렉션, 어느 institution). 우리는 hospital_opaque_id 만.

### 2.3 `/account` — 프로필 + API 키 + 위험구역

**잘된 점**
- API key reveal-once + masked display + regenerate/revoke 모달 — Stripe / Supabase 패턴 준수.
- `ApiKeyMaskedDisplay` 와 `ApiKeyRevealModal` 컴포넌트 분리 — 재사용성 좋음.
- Danger zone 분리 + email confirmation — 안전 패턴.
- sessionStorage stash 로 새로고침 시 reveal 모달 복원 (AccountClient.tsx L57-64) — UX 세심.

**못한 점**
- **Buyer onboarding 측면 빈약**: 첫 방문자가 "API key 받았다 → 그래서 어떻게 써?" 모름. curl 한 줄, Python SDK 한 줄 같은 **integration handoff** 가 화면에 없음.
- **Usage / quota 가시화 부재**: 현재 `tier`, `signedInAt` 만 노출. "오늘 검색 0/1, 다운로드 0/3" 같은 quota dashboard 부재. Stripe `Developers` 탭 / Supabase Project usage 와 비교 시 후퇴.
- **Billing section 이 mailto 링크 1줄**: `<a href="mailto:billing@radivault.io">` 하나만. invoice 이력 / payment method placeholder 부재. v0.1 placeholder 라도 "Coming soon" UX 없음.
- **사용자 식별이 buyerId 1줄**: buyerId 16자 hex 가 메인 식별자. 회사 이름 / 계정 owner / API tier 표시는 있으나 **연락처·이메일·organization** 정보 없음. enterprise 신뢰감 떨어짐.
- **Marketplace 진입점 없음**: 계정 페이지에서 "내 최근 cohort", "최근 검색", "최근 다운로드" 같은 버튼 부재. 또 `/search` 로 돌아가야 함.
- **PIPA / de-id audit 정책 링크 없음**: "내 다운로드 audit log 어디?", "이 데이터셋 익명화 어떻게?" buyer 가 클릭할 곳 없음.

**경쟁사 대비 부족**
- vs **Stripe**: Developers 탭 풀 풍부 (publishable key, webhook secret, rotation, usage chart, error log). 우리는 단일 key 만.
- vs **Supabase**: Project API settings — anon/service_role key 분리, JWT secret. 우리는 1 tier.
- vs **HF**: Token expiration / scoped access. 우리는 1 lifetime key.
- vs **Vercel**: Teams 분리 / member invitation. 우리는 1 user.

---

## 3. 경쟁사 강점 흡수 항목

| 경쟁사 | 흡수 항목 1 | 흡수 항목 2 | 적용 위치 |
|--------|------------|-----------|----------|
| **TCIA** | "Data origin disclosure" — 컬렉션·institution·release date 명기, 학술 톤의 신뢰 라벨 | 검색 결과 행에 thumbnail / animation / DICOM 3 버튼 노출 (multi-preview entry) | `/search` 결과 카드 메타 영역 + study detail 상단 origin pane |
| **IDC** | Collection summary 메트릭 ("Primary Site Distribution", "Modality Distribution" 도넛) — 검색 시 facet 위에 시각화 | License facet 노출 (CC-BY 등 재사용 라이선스) | `/search` facet 상단 + 결과 카드 좌상단 license chip |
| **Segmed** | Enterprise B2B 톤 — "2,800+ healthcare locations · 100M+ studies" 식 hero 메트릭 | "Longitudinal patient" 메시지 — 같은 환자 다중 study 묶음 | `/search` top banner ("250 studies · 2 hospitals · 14 modality classes") + study detail "related studies" 섹션 (v2 backlog) |
| **Gradient Health** | Instant preview thumbnail 강조 — 카드 썸네일을 96×96 이상으로 키우고 preview 우선 시각 | "No-IRB-needed" / "Self-serve preview tier" 차별 카피 | StudyCard 썸네일 64→96 px, "Sample download (no order)" CTA 분리 |
| **Flywheel** | Query DSL — `modality:CT AND body_part:CHEST AND age:40-60` 고급 검색 입력창 | Classification ontology — Intent/Measurement/Features 계층 분류 | `/search` top advanced query bar (collapsed by default), 결과 카드 secondary tag |

---

## 4. RadiVault 만의 차별점 부각

| # | 차별점 | 노출 위치 |
|---|-------|----------|
| 1 | **Federated 2 병원** (HOSP-001 본병원 250 + HOSP-002 튼튼병원 N) | (a) `/search` top banner 에 "Sourced from 2 partner hospitals · Korea" 명문화. (b) StudyCard 좌측 4px colored stripe — 본병원=blue / 튼튼병원=teal 2색 구분. (c) Cohort sidebar "Hospital coverage: 2 / 2" mini-stat. |
| 2 | **PIPA-native compliance** (4종 분리 동의 + chain audit) | (a) 모든 화면 footer 좌측 영구 배지 "PIPA §28-8 compliant · Anonymized · K-MOHW guideline 2024-12 aligned". (b) StudyCard 우측에 ✓ verified chip — hover 시 "DICOM PHI scrub + Pixel OCR + Patient consent" 3 단계 해설 tooltip. (c) Study detail 상단 "Audit chain" 링크 → 모달로 hospital→central→buyer 경로 표시. |
| 3 | **Stripe-style developer experience** (API key reveal-once + integration handoff) | (a) Account 페이지 API 키 카드 아래 "Quick start" 섹션 — curl 한 줄 + Python 한 줄 + Postman link, copy 버튼. (b) Reveal modal 직후 "Try it now" 단축 — sample search curl 자동 채움. (c) Tier 별 quota gauge ("Today's quota: 0/1 sample download · 0/250 search calls"). |
| 4 | **De-id chain audit** (병원→central→buyer 전 경로 감사) | (a) Study detail 우측 sidebar 에 "Audit chain ↗" 링크 — 클릭 시 timeline modal: `hospital ingest → De-ID worker (4 layer) → Hot Storage → buyer access`. (b) Account 페이지 "Audit log" 섹션 — 내 최근 search/download 20건 노출 + "Full log →" 링크 (v2 backlog stub). |
| 5 | **Hot Storage thumbnail** (DICOM PS3.18 Sup 203 표준 적합) | (a) StudyCard 썸네일 96×96 px 로 키우고 hover 시 "PS3.18 Sup 203 thumbnail · 256 px JPEG · PHI scrubbed" tooltip. (b) Study detail 상단 "Standards" mini-bar — "DICOM PS3.18 · Sup 203 · IHE-compliant" 3 칩. |
| 6 | **이중 언어 (ko/en) — 한국 시장 차별** | (a) 모든 화면 우상단 명시적 토글 (현재 구현됨, 더 prominent). (b) `/search` 좌측 facet 의 한글 라벨 (예: "신체 부위" 4자) 영문보다 짧은 점 활용 — facet sidebar 280→260 px 절약. (c) Hospital 이름 영문/한글 병기 ("HOSP-001 / 본병원", "HOSP-002 / 튼튼병원"). |

---

## 5. UX 개선안 (3 화면별)

### 5.1 `/search` — 더 빠른 scan, 더 명확한 federated signal, 더 직관적인 cohort builder

| 개선 | 변경 내용 | 근거 |
|-----|----------|------|
| **U-S1. Top hero strip** | 현 `FederatedSignal` 위에 1줄 hero strip 추가: "RadiVault — Korean medical imaging for global AI · 250 studies · 2 partner hospitals · PIPA-native". 5초 이해 보장. | 리서치 §0 북극성 "신뢰 우선" |
| **U-S2. 결과 카드 썸네일 64→96 px** | StudyCard 썸네일 영역 64→96 px. modality glyph fallback 도 같은 크기. cohort sidebar 의 mini-card 는 32 px 유지. | Gradient "instant preview" 흡수 |
| **U-S3. 카드 좌측 hospital stripe** | 좌측 4px 색상 띠로 hospital 식별: 본병원=`#2563eb` (blue-600), 튼튼병원=`#0d9488` (teal-600). + hospital chip 텍스트 한/영 병기 ("HOSP-001 / 본병원"). | RadiVault 차별점 #1, #6 |
| **U-S4. PIPA verified chip** | 카드 우측에 작은 ✓ chip — hover 시 4-layer de-id 해설 tooltip. | 차별점 #2 |
| **U-S5. Cohort builder 직관성** | Cohort sidebar 상단에 mini stat 3 개 (studies / hospitals / total size) + cohort diversity bar (modality 분포 stacked). 현재는 size MB 한 줄만. | IDC "Primary Site Distribution" 흡수 |
| **U-S6. Empty / loading state 개선** | empty: 일러스트 + "Try clearing filters" + "Browse TCIA seed dataset" 2 CTA. loading: 스켈레톤은 현재 OK. | UX 표준 |
| **U-S7. Advanced query bar (v2 backlog)** | 결과 list 위 toggle 가능한 query 입력창 (`modality:CT AND age_bucket:40-49`). 첫 방문자 숨김, "/" 키로 expand. | Flywheel FlyQL 흡수, v2 |
| **U-S8. Search result counter** | "247 studies · 31 ms" — hits + p95 latency. 데이터 엔지니어 신뢰. | 리서치 §3 데이터 밀도 |

### 5.2 `/studies/[uid]` — 메타 풍부, 큰 썸네일, CTA 분리, audit trail

| 개선 | 변경 내용 |
|-----|----------|
| **U-D1. 좌측 viewer 영역 크게** | 좌측 65% 폭에 `<canvas>` viewer placeholder 384×384 px (현재보다 2배). 하단 disabled slice slider + "Slice navigation coming v2" 라벨. SaMD 면책 footer 유지. |
| **U-D2. 우측 메타데이터 patient/study/series 3 카드** | 우측 35% 폭, 3 카드 분리: (1) **Patient** (age_bucket, sex, species). (2) **Study** (modality, body_part, study_date_shifted, hospital). (3) **Series & device** (n_instances, total_bytes, manufacturer, model, slice_thickness_mm). 각 카드 헤더에 작은 icon. |
| **U-D3. CTA 명확 분리 (2 primary)** | 우측 sidebar 하단 (sticky): (a) **Sample download** (1 study DICOM ZIP, 즉시, free preview) — secondary outline 버튼. (b) **Add to cohort & order** — primary blue 버튼. 상호 배타 아니게 둘 다 가능. |
| **U-D4. Audit chain 링크** | sidebar 상단 "View audit chain →" 링크. 클릭 → 모달로 timeline (hospital ingest YYYY-MM-DD → De-ID worker / 4 layer / OK → Hot Storage entry → my access just now). |
| **U-D5. Standards / origin chips** | 헤더에 작은 chip 4개: `DICOM PS3.18` `Sup 203` `Korean PIPA-aligned` `HIPAA Safe Harbor`. |
| **U-D6. Sibling navigation** | 헤더에 `← Prev` / `Next →` (cohort 또는 검색 결과 sequence 기반). `J/K` keyboard. |
| **U-D7. SaMD 면책 그대로 유지** | footer `SaMDFooter` 유지. "For dataset evaluation only. Not for clinical use." |

### 5.3 `/account` — Onboarding 친화 + integration handoff

| 개선 | 변경 내용 |
|-----|----------|
| **U-A1. Profile 카드 강화** | buyer ID(현) + email(현) + tier(현) + **organization name** (옵션) + **signed in since YYYY-MM-DD** (현) + avatar circle (이니셜). |
| **U-A2. API key 카드 + Quick start** | 현 API key 카드 유지. 그 아래 expandable "Quick start integration" 섹션: (a) curl 한 줄 (`curl -H "Authorization: Bearer $API_KEY" https://api.radivault.io/search/studies?modality=CT`), (b) Python 5 줄 (requests example), (c) Postman 링크 placeholder. 각 코드 블록 copy 버튼. |
| **U-A3. Quota & usage 가운지** | 새 섹션: "Today's usage" — search calls (0/250), sample downloads (0/1), cohort orders (0/∞). 진행률 bar. 월별 reset 카운트다운. |
| **U-A4. Audit log preview** | 새 섹션: "Recent activity" — 최근 5 events (search query / sample download / cohort save / api_key regenerate). "Full log →" 링크 (v2 stub). |
| **U-A5. Marketplace shortcuts** | 새 섹션 (Profile 카드와 API 카드 사이): 4 quick-link 그리드 — "Search studies", "My cohorts", "My orders", "Recent downloads". 각 카드 아이콘 + 카운트. |
| **U-A6. Billing placeholder 강화** | 현 mailto 링크 → "Invoice history (coming soon)" placeholder + sample 가격 카드 ("Free preview tier · Paid order from $X / study · Contact billing"). |
| **U-A7. Danger zone 그대로 유지** | 변경 없음. |

### 5.4 공통 개선

| 개선 | 변경 내용 |
|-----|----------|
| **U-C1. Federated badge (top nav)** | MarketplaceNav 우상단에 "🌐 Federated · 2 hospitals" mini-pill. 클릭 → /about/federation 모달 (또는 stub 링크). |
| **U-C2. Compliance footer (모든 화면)** | 글로벌 footer 좌측 영구 배지 — "PIPA §28-8 compliant · K-MOHW 2024 guideline aligned · HIPAA-aligned anonymization". 우측에 audit log link + 영문/한글 토글. |
| **U-C3. Language toggle prominent** | 현재도 토글 있지만, 우상단에 "EN | 한국어" 탭 형식으로 더 명시적. |
| **U-C4. Audit trail link (모든 page)** | top nav 우측 "Audit ↗" 링크 — 자기 활동 audit log 페이지 (v2 stub). |
| **U-C5. Color-coded modality chip** | CT=blue, MR=purple, CR/DR=green, MG=pink, US=orange, PT=red — 이미 portal-redesign-competitive §3.3 에서 권고됨. 시각 밀도 향상. |
| **U-C6. Dark mode 가능 표시** | 우상단 "🌙" 토글 (v2 backlog placeholder, 라이트 기본). |

---

## 6. 디자인 토큰 (기존 + 신규)

> 기존 `design-spec-portal-redesign.md §4` 토큰 100% 승계. 신규 토큰만 본 §6 에 정의. 신규 토큰은 UI_GUIDE.md 정식화 전까지 **제안만** — Kyle 승인 후 정식 편입.

### 6.1 기존 (재사용)

- 색상: `--color-primary-{50,100,500,600,700,900}` (Buyer blue), `--color-teal-{50,100,600,700}` (Hospital teal), `--color-bg/bg-muted/border/border-strong/text/text-muted/text-strong` (Slate neutral), Status (Success/Warning/Error/Info).
- 타이포: 영문 Inter / 한글 Pretendard. 본문 14 px / 행간 1.6.
- 간격: 4 px grid, card padding 20 px.
- 라운드: card 8 px, button 6 px, pill 9999 px.

### 6.2 신규 토큰 (제안)

| 토큰 | 값 | 용도 | 근거 |
|------|-----|------|------|
| `--color-modality-ct` | `#2563eb` (blue-600) | CT modality chip 배경 | portal-redesign §3.3 |
| `--color-modality-mr` | `#7c3aed` (violet-600) | MR modality chip | 동상 |
| `--color-modality-mg` | `#db2777` (pink-600) | MG modality chip | 동상 |
| `--color-modality-cr` | `#16a34a` (green-600) | CR/DR modality chip | 동상 |
| `--color-modality-us` | `#ea580c` (orange-600) | US modality chip | 동상 |
| `--color-modality-pt` | `#dc2626` (red-600) | PT modality chip | 동상 |
| `--color-hospital-stripe-001` | `#2563eb` | StudyCard 좌측 stripe — 본병원 | 차별점 #1 |
| `--color-hospital-stripe-002` | `#0d9488` | StudyCard 좌측 stripe — 튼튼병원 | 차별점 #1 |
| `--space-card-thumb` | `96 px` | StudyCard 썸네일 크기 (현 64→96) | U-S2 |
| `--space-detail-thumb` | `384 px` | Study detail viewer placeholder | U-D1 |
| `--shadow-modal` | `0 20px 25px -5px rgb(0 0 0 / 0.10), 0 8px 10px -6px rgb(0 0 0 / 0.10)` | Audit chain modal | U-D4 |

### 6.3 컴포넌트 재사용 매핑

| 신규 화면 요구 | 기존 컴포넌트 | 재사용 / 신규 |
|---------------|-------------|--------------|
| Top hero strip (`/search`) | `FederatedSignal` 확장 | 재사용 + 1 줄 strip 위로 |
| StudyCard with stripe + verified chip | `StudyCard.tsx` | 수정 (stripe + chip 추가) |
| Cohort diversity bar | 신규 `CohortDiversityBar` | **신규 — Recharts 또는 div stack** |
| Study detail 3-카드 메타 | 기존 `StudyDetailPanel` | 수정 (3 카드 분리) |
| Audit chain modal | 신규 `AuditChainModal` | **신규** |
| Sibling navigation | 신규 `StudyNav` | **신규** |
| Quick start integration | 신규 `QuickStartCodeBlock` | **신규** |
| Quota & usage | 신규 `QuotaCard` | **신규** |
| Audit log preview | 신규 `AuditLogPreview` | **신규** |
| Marketplace shortcuts grid | 신규 `MarketplaceShortcuts` | **신규** |

---

## 7. HTML 목업 가이드

### 7.1 위치 / 열어보는 법

- **루트 디렉토리**: `docs/specs/mockups/buyer-ux-v2/`
- **파일 구성**:
  - `index.html` — 가이드 페이지 + 3 mockup 링크
  - `search.html` — `/search` 개선안
  - `study-detail.html` — `/studies/[uid]` 개선안
  - `account.html` — `/account` 개선안
  - `styles.css` — 공통 스타일 (디자인 토큰 CSS 변수)
- **열어보는 법**: 각 HTML 파일을 브라우저에서 더블클릭으로 열기 (file:// 프로토콜). 외부 의존성: Google Fonts (Inter + Pretendard) CDN 만 사용. 인터넷 없으면 시스템 폰트 fallback.
- **상호작용**: 정적 HTML + 최소 JavaScript (filter chip 토글, 언어 토글, modal open/close, copy button). React/Next.js 미사용.

### 7.2 데이터 출처

- **Lorem study UID 8개**: `1.2.840.{HOSP}.{seq}` 형식 mimic.
- **2 hospital 분포**: HOSP-001 본병원 5 개, HOSP-002 튼튼병원 3 개.
- **Modality 다양**: CT(3), MR(2), MG(1), CR(1), US(1) — 5 종.
- **메타필드**: body_part, age_bucket, sex, manufacturer, model, study_date_shifted, n_instances, total_bytes — 모두 inline 가짜 값.
- **API 응답 형식 mimic**: dev-spec-metadata-index §6 의 SearchRequest/SearchStudy 스키마와 1:1.

### 7.3 인터랙션 사양

| 인터랙션 | 동작 |
|---------|------|
| Facet chip 클릭 | `aria-selected` 토글 + visual highlight (실 검색 X, 카드 dim/highlight 모방) |
| 언어 토글 (EN / 한국어) | `data-locale` 속성 변경 → CSS attr selector 로 텍스트 swap |
| Thumbnail click (study detail) | 큰 viewer placeholder 영역 highlight (실 viewer X) |
| Audit chain link | 모달 open (`<dialog>` 또는 inline div) |
| API key reveal toggle | masked ↔ plaintext swap |
| Copy button | navigator.clipboard.writeText + toast |

### 7.4 한국어/영어 토글 구현

- 우상단 `<button data-locale-toggle>`. JS 로 `<html lang="en|ko">` + `<body data-locale="en|ko">` 변경.
- CSS attr selector: `[data-locale="en"] .ko { display:none } [data-locale="ko"] .en { display:none }`.
- 핵심 카피 모두 `<span class="en">English</span><span class="ko">한국어</span>` 병기.

### 7.5 반응형

- **Desktop (1280+)**: 3-pane full layout.
- **Tablet (768-1279)**: facet sidebar 220 px 로 축소, cohort sidebar 280 px.
- **Mobile (320-767)**: facet sidebar drawer 화 (햄버거 토글), cohort sidebar bottom-fixed bar 로 축약.

---

## 8. 접근성

- **키보드 탐색**: 모든 `<button>`, `<a>`, `<input>` Tab 순서 자연 (HTML order). facet chip은 `<button role="checkbox" aria-checked>`. modal trap 은 `<dialog>` 사용.
- **스크린리더**: `aria-label` 모든 icon-only 버튼에. landmark `<nav>`, `<main>`, `<aside>` 명시.
- **색 대비**: 본문 18.69:1, primary CTA 4.54:1 (이미 §6 토큰 충족). status bg/fg 4.74-6.80:1.
- **Focus ring**: `:focus-visible { outline: 2px solid var(--color-primary-700); outline-offset: 2px; }`.

---

## 9. 국제화

- ko / en 동시 지원. 모든 카피 인라인 병기.
- 한국어가 영문 대비 30% 짧음 → facet sidebar 좁아도 OK, 버튼 라벨 줄바꿈 회피.
- 날짜: `YYYY-MM-DD` 통일. 월·요일 약어 미사용 (한국 사용자 문제 없음).
- 통화: USD 기본. 한글 페이지에서도 sample preview tier 는 무료라 통화 표기 최소.

---

## 10. 수용 기준 (시각·행동)

- [ ] 3 mockup 모두 1280×800 desktop 에서 layout 시안과 일치.
- [ ] 언어 토글 EN ↔ KO 모든 카피 누락 없음.
- [ ] Facet chip 토글, audit modal open/close, API key reveal toggle, copy button 4 가지 인터랙션 작동.
- [ ] 색 대비 WCAG AA (4.5:1 본문) 충족.
- [ ] 외부 의존성: Google Fonts CDN 만, 그 외 0.
- [ ] 더블클릭으로 브라우저 오픈 가능 (file://).
- [ ] 6 차별점 모두 화면에 시각적으로 존재 — federated stripe / PIPA chip / API quick-start / audit chain link / standards chip / 이중언어 토글.

---

## 11. dev-spec 영향

본 평가/개선안이 채택될 경우 다음 dev-spec 변경 / 추가가 필요:

| 영향 받는 dev-spec | 변경 사항 |
|-------------------|----------|
| `dev-spec-buyer-browse-preview.md` | (a) StudyCard 썸네일 64→96 px (FR-PREVIEW-* 영향). (b) Hospital stripe 색상 매핑 추가 (FR-BP-7 확장). (c) PIPA verified chip + tooltip 신규 FR. (d) Cohort diversity bar 신규 FR. |
| `dev-spec-buyer-auth.md` | (a) Account 페이지에 Quick start integration 섹션 신규 FR (curl/python/postman). (b) Quota & usage gauge 신규 FR (오늘 quota / 월 quota). (c) Audit log preview 신규 FR (5 most recent events). (d) Marketplace shortcuts grid 신규 FR. |
| `dev-spec-portal-redesign.md` | (a) MarketplaceNav 에 federated badge + audit link 추가 (FR-SH-* 확장). (b) Global footer 에 PIPA compliance permanent badge 추가. (c) Modality 색상 토큰 6개 정식 등록 (§4 확장). |
| **신규** `dev-spec-buyer-ux-v2.md` (옵션) | 위 변경을 한 dev-spec 으로 묶어 새 feature-slug 으로 진행. v2 patch 묶음. |
| `dev-spec-metadata-index.md` | 응답에 `manufacturer_model_name` (현재 manifest 부재) 추가 — Study detail 카드 #3 에 model 노출 위해. ⚠ 이미 metadata-extraction 리서치 §4.1 에서 권고됨. |
| `docs/UI_GUIDE.md` | 본 §6 신규 토큰 (modality 6 색, hospital stripe 2 색, thumbnail 사이즈) 정식 등록 시점에 편입. |

---

## 12. 오픈 질문 (Kyle 결정 필요)

1. **이 평가/개선안 채택 여부** — 전체 채택 / 부분 채택 / 거절 중 어떤 방향?
2. **신규 dev-spec 단독 vs 기존 확장** — 본 §11 의 변경을 신규 `dev-spec-buyer-ux-v2.md` 로 묶을지, 기존 3 dev-spec 에 분산 append 할지.
3. **HTML mockup 의 후속 처리** — Figma 변환 / Storybook 컴포넌트화 / 그대로 dev 참고용 유지 중 어느 것?
4. **Audit chain 모달의 데이터 출처** — 실제 audit log API (FR-AUTH-? 신규) 가 필요한지, 아니면 stub 으로 v2 backlog?
5. **Quota 정책** — Today's quota 노출 시 실제 quota 값(검색 250/일, sample 1/일, order 무한). 변경 가능?
6. **Hospital 식별 정책** — 본병원/튼튼병원 한글명 buyer-side 노출 OK 인지 (현재는 hospital_opaque_id 만). 한국어 페이지 한정으로 노출, 영문 페이지에서는 opaque ID 만? 또는 둘 다 노출?
7. **Modality 색상 토큰 정식 채택** — 6 색 매핑 OK 인지, 추가 modality (NM, OT) 필요한지.
8. **신규 토큰 (`--color-hospital-stripe-*`) UI_GUIDE 등록 시점** — 본 평가 채택 즉시 / dev-spec 작성 후 / 구현 후 어느 단계?

---

## 13. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-25 | @designer (Claude Opus 4.7) | 최초 작성. 평가(§2) + 흡수(§3) + 차별점(§4) + 개선안(§5) + HTML 목업 4 파일 동반. |

---

### NEXT_STEP

- 완료 산출물: `docs/specs/design-spec-buyer-ux-evaluation.md` + `docs/specs/mockups/buyer-ux-v2/{index,search,study-detail,account}.html` + `styles.css`.
- 제안 다음 단계: **메인 세션이 본 평가를 Kyle 에게 요약 보고 → 채택 여부 결정**. 채택 시 `@planner` 호출하여 dev-spec 변경/신규 작성 (옵션 §11 / §12 Q2 결정).
- UI_GUIDE.md 갱신 제안: 신규 토큰 6 모달리티 색 + 2 hospital stripe + 2 thumbnail 사이즈. **Kyle 승인 후** 정식 편입 권고.
- 추가 디자인 필요: dev-spec 확정 후 v2 정식 design-spec 작성 (본 문서는 평가/제안서 위치).
- Kyle 결정 필요 사항: §12 Q1~Q8 8 개.
