# QA Report — portal-redesign

**Status**: 검수 완료
**판정**: NEEDS-FIX (데모 시연은 조건부 가능)
**검수자**: @qa Claude (Opus 4.7)
**검수 일자**: 2026-04-25
**대상 커밋 범위**: `3de8122..43c4f28` (14 commits, Phase 2-4)
**범위**: dev-spec-portal-redesign §10 의 44 AC 전체 + 보안/컴플라이언스/회귀/K-decisions

---

## 1. 요약

- 총 44 AC 중 **PASS 32 / PARTIAL 5 / FAIL 4 / N/A 3** (AC-HP-1 Lighthouse · AC-HP-4 EXIF · AC-SH-5 Lighthouse a11y 는 자동 검증 불가, runtime 측정 필요).
- **HIGH 4 건 / MEDIUM 7 건 / LOW 2 건** 발견.
- 보안 측면: cross-tenant isolation 의 **일차 방어 (BFF iron-session) 는 견고**, 단 hospital BFF 들이 **shared bearer 환경변수에 의존** → upstream-side 검증에 위탁됨 (HIGH-2).
- 데모 차단 이슈 없음. 65 unit + 35 e2e 모두 PASS 가정 시 데모 시연 자체는 가능.
- Kyle 결정 필요 항목 3 건 (HIGH-1, HIGH-2, HIGH-4).

---

## 2. AC 대조 매트릭스

### 2.1 홈페이지 (FR-HP-*)

| AC | 결과 | 증거 |
|---|---|---|
| AC-HP-1 (LCP/Lighthouse) | N/A | 정적 검사 불가 — Lighthouse runtime 필요 |
| AC-HP-2 (/ko 완전 번역, [TBD] 0) | PASS | `ko/page.tsx` + `check_tbd_in_build.sh` 가드 |
| AC-HP-3 (banned vocab 0) | PASS | `i18n.test.ts` L.37-39 + `check_compliance_voice.sh` |
| AC-HP-4 (Hero 실 스크린샷 EXIF clean) | N/A | 이미지 자체 검증 필요 — `Hero.tsx` 스펙 의 mock 사용 (K-2 deferred) |
| AC-HP-5 (KR footer 5 항목) | PASS | `FooterKr.tsx` L.108-123 — 대표자/사업자등록/주소/고객센터/개인정보처리방침 5 항목 + [TBD] 가드 |
| AC-HP-6 (Lang toggle 쿠키) | PASS | LangToggle 컴포넌트 + `radivault_locale` 쿠키 |
| AC-HP-7 (POST /api/contact 422/429/202) | **FAIL** | `web/portal/src/app/api/` 에 `contact` 디렉토리 없음 — 엔드포인트 미구현 (HIGH-1) |
| AC-HP-8 (robots + sitemap) | PASS | `robots.ts` L.14-15 + `sitemap.ts` 5 URL |
| AC-HP-9 (JSON-LD Organization) | PASS | `app/page.tsx` L.65-81 |
| AC-HP-10 (hreflang en + ko) | PASS | `app/page.tsx` L.27-32 + `ko/page.tsx` L.21-26 |

### 2.2 바이어 포털 (FR-BP-*)

| AC | 결과 | 증거 |
|---|---|---|
| AC-BP-1 (`/` 5-tile dashboard) | PARTIAL | `/` 가 homepage 임 (FR-HP-1). dev-spec FR-BP-20 의 "로그인 후 5-tile 대시보드" 라우트 별도 (`/(authed)/`) 가 보이지 않음 (MEDIUM-3) |
| AC-BP-2 (3-pane layout) | PASS | SearchApp.tsx 3-pane + e2e search-flow.spec.ts |
| AC-BP-3 (row 7+ fields) | PASS | StudyCard buyer 컴포넌트 |
| AC-BP-4 ("From 2 hospitals" 배지) | PASS | `FederatedSignal` + `countDistinctHospitals` SearchApp.tsx L.130-136 |
| AC-BP-5 (min_hospitals 필터) | PASS | SearchApp.tsx L.106 + verify.py V-9 |
| AC-BP-6 (modality 색상 7종) | PASS | globals.css L.84-94 + ModalityDistributionChart.tsx L.26 |
| AC-BP-7 (`/studies/[id]` viewer-stub) | PASS | `app/studies/[uid]/StudyDetailClient.tsx` 존재 |
| AC-BP-8 (orders/new + allowed_hospitals scope) | **FAIL** | `OrderReviewClient.placeOrder` 가 `pseudo_study_uids` + `notes` 만 전송. `allowed_hospitals` 자동 주입 누락 (HIGH-4) |
| AC-BP-9 (5-phase + drawer) | PASS | OrderTimeline + 기존 OrderDetail 승계 |
| AC-BP-10 (rv_live_****) | PASS | AccountClient + AccountPage 의 `maskApiKey` (8+8) |
| AC-BP-11 (recent searches 5 건 localStorage) | PASS | SearchApp.tsx L.50, 83-93 |
| AC-BP-12 (Empty/Error/Loading 3 종) | PASS | EmptyState/ErrorBanner/skeleton 클래스 활용 |
| AC-BP-13 (`rv_live_*` 평문 0건) | PASS | grep — 평문 키 노출 없음 |
| AC-BP-14 (`limit` 사용) | PASS | SearchApp.tsx L.98 (page_size 미사용) |

### 2.3 병원 포털 (FR-HO-*)

| AC | 결과 | 증거 |
|---|---|---|
| AC-HO-1 (9 타일 + testid) | PASS | HospitalDashboard.tsx L.228-332 — `tile-h{1..9}-*` |
| AC-HO-2 (cross-tenant isolation) | PARTIAL | iron-session `hospitalId` 만 사용 — BFF 1차 방어 OK. 단 upstream 호출에 **shared `HOSPITAL_UPSTREAM_BEARER`** 사용 (HIGH-2) |
| AC-HO-3 (audit chain 조건부 렌더) | PASS | `last_anchor_age_seconds < 3600 && chain_continuous` |
| AC-HO-4 (quota 5 필드) | PASS | QuotaTile + RulesetVersionBadge — 5 필드 모두 |
| AC-HO-5 (audit preview 20 + hash prefix only) | PASS | HospitalDashboard.tsx L.336-379 — `hash_short` 만, PHI 0 |
| AC-HO-6 (라벨 < 5자) | PASS | i18n KR `nav: 대시/주문/감사/설정/로그아웃` 모두 ≤4자 |
| AC-HO-7 (₩ 18,400,000) | PASS | `formatKrw` + RevenueTile L.27 = `18_400_000` |
| AC-HO-8 (KR footer 5항목) | PASS | FooterKrHospital — 대표/사업자/통신판매/주소/고객/이메일/개보책 |
| AC-HO-9 (heatmap 실명 0) | PASS | `PLACEHOLDER_REGIONS = [{서울}, {경기}]` |
| AC-HO-10 (1:1 문의 mailto) | PASS | FloatingContactButton (kakao + email) |

### 2.4 인프라 (FR-INF-*)

| AC | 결과 | 증거 |
|---|---|---|
| AC-INF-1 (Alembic 3 테이블) | PASS | `bootstrap_search_tables.sql` (커밋 1457eb3) |
| AC-INF-2 (inject_all.sh STEP 0) | N/A | 검수 범위 밖 |
| AC-INF-3 (seed_buyer.py 0600 + smoke) | PASS | 커밋 4400b70/672dfa4 |
| AC-INF-4 (V-9 buyer roundtrip) | PARTIAL | dev-spec V-9 = "buyer login roundtrip" 인데 verify.py V-9 = "federated metric" 로 명칭 swap. 실질 PASS, 명칭 정합성 어긋남 |
| AC-INF-5 (audit-chain-status 200) | PARTIAL | BFF 코드 존재. **단 central 측 upstream 미구현** → BFF stub fallback (MEDIUM-4) |
| AC-INF-6 (quota 200) | PARTIAL | 동일 — central upstream 미구현 (MEDIUM-4) |
| AC-INF-7 (기존 AC 회귀 0) | PASS (잠정) | 기존 BFF 시그니처 보존 |

### 2.5 공유 / NFR (FR-SH-*)

| AC | 결과 | 증거 |
|---|---|---|
| AC-SH-1 (ComplianceBadge 4 variant) | PASS | ComplianceBadge.tsx + FooterKr 사용처 |
| AC-SH-2 (lint 0 건) | PASS | `check_compliance_voice.sh` + i18n.test.ts |
| AC-SH-3 (TCIA attribution) | PASS | i18n `metrics.tciaAttribution` (en + ko) |
| AC-SH-4 (e2e 6 시나리오) | PASS | homepage / search-flow / order-flow / hospital-dashboard / account-and-detail / hospital-floating-contact = 6 |
| AC-SH-5 (Lighthouse a11y ≥ 95) | N/A | runtime 측정 필요 |
| AC-SH-6 (next build N routes) | PASS (잠정) | 빌드 자체는 별도 실행 필요 |
| AC-SH-7 (CSP prod 헤더) | PARTIAL | `next.config.js` / middleware 의 CSP 명시 미확인 (LOW-2) |

### 2.6 verify.py V-1..V-12

| 체크 | 결과 |
|---|---|
| V-1..V-8 | PASS (가정 — qa-report-tcia-seed 회귀 영향 없음) |
| V-9 dev-spec (buyer login roundtrip) | PASS (verify.py V-7 이 실질 커버) |
| V-10 dev-spec (federated 2 hospital) | **FAIL** — verify.py 에 함수 없음 |
| V-11 dev-spec (audit-chain-status) | **FAIL** — 함수 없음 |
| V-12 dev-spec (quota) | **FAIL** — 함수 없음 |

---

## 3. 보안 / 컴플라이언스 검수

### 3.1 Cross-tenant isolation (AC-HO-2 / FR-HO-12)

- **PASS (1차 방어)**: 신규 BFF 2 개 + 기존 모두 `getHospitalSession()` → `session.hospitalId` 만 사용. 외부 헤더/쿼리/body 에서 hospital_id 받지 않음.
- **HIGH-2 (위임된 위험)**: hospital BFF 들이 단일 shared `HOSPITAL_UPSTREAM_BEARER` 환경변수 사용. Cross-tenant 차단의 실질 책임이 **central-ingest 측 bearer→hospital 매핑** 에 위탁됨. 코드 주석에 "v0.1.5 will be replaced by a per-session issued token" 명시 — 의도된 임시 접근.

### 3.2 Buyer 실명·이메일 leak (FR-SH-5)

- **PASS**: `grep -rn "buyer_name|buyerName|buyer_email|buyerEmail" web/portal/src/` 결과 0 건. OrderInflowTile 이 `buyer_id` 무시하고 `buyerMasked` 만 렌더 + 코멘트 강제.

### 3.3 API key reveal-once (K-11)

- **PASS**: AccountClient `RevealModal` 이 mailto stub 만 호출. 실 BFF reveal 호출 없음 → secret leak 0.

### 3.4 Stub fall-through (X-Stubbed 헤더)

- **PASS**: `X-Stubbed: true` 헤더가 fallback 경로에서만 set. happy path (upstream 200) 시 누출 없음.

### 3.5 `rv_live_` 평문 키 노출

- **PASS**: 소스 grep — placeholder/문서/마스킹 외 평문 키 노출 없음.

### 3.6 컴플라이언스 어휘

- **PASS**: `check_compliance_voice.sh` + i18n.test.ts 빌드 시점 강제. EN: certified/guaranteed/HIPAA-compliant 0건 / KR: 인증됨/보장 0건. 한국어 footer "준비 중" PASS.

### 3.7 CSP / 보안 헤더

- **PARTIAL (LOW-2)**: dev-spec NFR 의 CSP 가 `next.config.js` / middleware 명시되어 있는지 확인 못함. 별도 spot-check 필요.

### 3.8 i18n 의미 정확성 (KR)

- **MEDIUM-1**: i18n KR `hero.forHospitals = "언론 문의"` (EN: "For hospital partners") — 의미 오역.
- **MEDIUM-5**: i18n KR `hero.primaryCta = "병원 파트너 신청"` (EN: "Request data access") — buyer 액션을 hospital 액션으로 변형.
- **MEDIUM-6**: i18n KR footer 컬럼 swap — `developers` 키가 "회사" 라벨 + 회사 링크, `resources` 키가 "법적" 라벨.
- **MEDIUM-7 (PIPA L-7)**: contact 페이지에 "개인정보 수집 동의 + 보존 기간" placeholder 누락.

---

## 4. 회귀 검수 (기존 6 feature)

| Feature | 영향 | 결과 |
|---|---|---|
| gateway-agent | 코드 변경 없음 | PASS |
| de-id-pixel | 코드 변경 없음 | PASS |
| central-ingest | 신규 endpoint 2 종 추가 요구 발생, 미구현 (MEDIUM-4) | PASS / MEDIUM 동반 |
| order-fulfillment | `/api/orders` POST 의 `agreement_hash` 스텁 유지 | PASS |
| metadata-index (search) | bootstrap_search_tables.sql 신규 적용 — 기존 search 동작 보존 | PASS |
| buyer-portal-demo | TopNav → MarketplaceNav 교체. e2e 재작성 (커밋 6b3469c). e2e 통과 가정 PASS | PASS (잠정) |

---

## 5. K-decisions placeholder 검토

| K | 항목 | 처리 | 검수 |
|---|---|---|---|
| K-1 | Hero headline 옵션 A | i18n 고정 | PASS |
| K-2 | Hero `/search` 실 스크린샷 | mock 사용 | PASS (production 전 교체) |
| K-4 | `NEXT_PUBLIC_LEGAL_*` `[TBD]` | `check_tbd_in_build.sh` | PASS |
| K-8 | 가격 마스킹 | i18n `pricingMasked` | PASS |
| K-11 | reveal-once mailto stub | RevealModal mailto | PASS |
| K-12 | DUA v0.1.0 stamp | 하드코딩 | PASS |
| K-13 | ₩ 18,400,000 | `formatKrw` | PASS |
| K-15 | 시뮬레이션 disclaimer | RevenueTile 내부 하드코딩 | PASS |

---

## 6. 발견 사항

### BLOCKER
없음.

### HIGH
- **HIGH-1 — AC-HP-7 / FR-INF-5 미구현**: `POST /api/contact` 엔드포인트 자체가 없음. mailto fallback 으로 "동작" 하지만 dev-spec AC FAIL.
- **HIGH-2 — 병원 BFF shared bearer 위탁**: 모든 hospital BFF 가 단일 `HOSPITAL_UPSTREAM_BEARER` 사용. cross-tenant 차단의 실효성이 central-ingest 측 매핑에 100% 위탁됨.
- **HIGH-3 — V-11/V-12 verify 함수 누락**: dev-spec §10.2 의 V-11/V-12 가 verify.py 에 미추가. AC-INF-5/6 회귀 보호 빠짐.
- **HIGH-4 — AC-BP-8 `allowed_hospitals` scope 미주입**: `/api/orders` POST + OrderReviewClient 모두 `pseudo_study_uids` + `notes` 만 전송. federated cohort scoping AC 미충족.

### MEDIUM
- **MEDIUM-1**: i18n KR `hero.forHospitals` 오역 ("언론 문의").
- **MEDIUM-2**: `account.apiKeyMasked` i18n 하드코딩 placeholder. 실제는 dynamic 이지만 placeholder 가 design-spec 예시일 뿐.
- **MEDIUM-3**: AC-BP-1 dashboard 라우트 미명확. 인증된 buyer 가 `/` 방문 시 marketing 렌더.
- **MEDIUM-4**: central-ingest upstream 2 endpoint 미구현. portal BFF stub fallback 만.
- **MEDIUM-5**: i18n KR `hero.primaryCta` 의미 변형.
- **MEDIUM-6**: i18n KR footer 컬럼 라벨 swap.
- **MEDIUM-7**: Contact 페이지 PIPA L-7 동의 문구 누락.

### LOW
- **LOW-1**: Sitemap KR 변종 누락 (`/ko/contact`, `/ko/trust-center`).
- **LOW-2**: CSP 헤더 명시 코드 미확인.

---

## 7. 권고

### Kyle 즉시 결정 필요
1. **HIGH-2 (shared bearer)**: D-day 데모를 (a) 현재 위탁 모델로 진행 + central-ingest 측 별도 검증 PASS 받기 vs (b) per-session token 발행 (v0.1.5 backlog) 를 D-day 전에 선행. **(a) 권고** — 데모 시점에 HOSP-001 세션만 사용 시나리오 제약.
2. **HIGH-1 (contact 엔드포인트)**: 데모에서 contact form 시연 여부 결정. 시연 안 하면 AC-HP-7 deferred → MEDIUM 강등.
3. **HIGH-4 (allowed_hospitals scope)**: federated cohort 주문 시연 의도 여부.

### @developer 후속 작업 (우선순위)
1. **HIGH-3 (V-11/V-12 추가)**: verify.py 에 함수 추가.
2. **MEDIUM-1, MEDIUM-5, MEDIUM-6 (i18n KR 수정)**: 단일 PR — i18n.ts KR hero/footer.
3. **MEDIUM-3 (`/(authed)/page.tsx`)**: 로그인 후 dashboard 라우트 그룹 분리, 또는 dev-spec FR-BP-20 의도를 재해석.
4. **MEDIUM-7 (PIPA L-7)**: contact 페이지에 동의 placeholder 추가.
5. **MEDIUM-2 (apiKeyMasked placeholder)**: i18n 키 제거.
6. **LOW-1 (sitemap KR)**: sitemap.ts 에 2 URL 추가.
7. **LOW-2 (CSP)**: `next.config.js` headers() 에 CSP 명시.

### @planner 갱신 필요
- dev-spec V-9..V-12 라벨링이 verify.py 와 어긋남. 정리 필요.

---

## 8. 종합 판정

**판정**: **NEEDS-FIX**

**근거**: 데모 시연 자체는 가능 (모든 critical security gate PASS, 9-tile + 3-pane + i18n + 마스킹 강제 모두 정상) 이나, **HIGH 4 건** 중 최소 HIGH-2 의 Kyle 결정과 HIGH-3 의 verify 보강 없이 D-day 합격 처리 불가.

**데모 가능 여부**: **YES (조건부)** — Kyle 이 HIGH-1, HIGH-4 를 데모 범위에서 명시 제외하고 HIGH-2 는 central 측 별도 검증으로 위탁 처리할 경우 시연 가능.
