# 개발지시서 — RadiVault 포털 전면 리디자인 (Homepage + Buyer + Hospital)

> **Status**: Draft v0.1 · **Feature slug**: `portal-redesign` · **Last updated**: 2026-04-25
> **작성자**: @planner (Claude Opus 4.7) · **근거**:
>  - [`docs/research/portal-redesign-competitive-analysis.md`](../research/portal-redesign-competitive-analysis.md) (599 줄, 15 경쟁사) — 리서치 §0·§6·§7·§8.6·§2.5 전면 인용
>  - [`docs/research/buyer-portal-ux-competitive.md`](../research/buyer-portal-ux-competitive.md) — 포스트-로그인 3-pane·FSM 매핑
>  - [`docs/prd.md`](../prd.md) — 제품 요구 tagline·KPI
>  - [`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) §3/§4/§5 — Model 3 Hybrid 3-Zone
>  - 선행 dev-spec: `dev-spec-buyer-portal-demo.md` (기존 포털 골격) · `dev-spec-metadata-index.md` (검색 API `SearchRequest` 스키마) · `dev-spec-central-ingest.md` (hospital 엔드포인트) · `dev-spec-order-fulfillment.md` (주문 FSM 12→5 phase) · `dev-spec-gateway-agent.md` (감사 앵커 체인)

> **선행 상태 요약 (2026-04-25 기준)**:
>  - `web/portal/` Next.js 14 App Router + iron-session BFF 존재 — `/search` `/orders` `/hospital` 골격 구현됨 (Session 9, H-1 fix 완료)
>  - Central DB 는 2 병원 (HOSP-001 Bon Hospital, HOSP-002 Tunteun Hospital) × 약 250 study 실 TCIA 시드 — Flow A metadata-only 완료 (Session 19~21)
>  - 감사 앵커 체인, pixel de-ID, order-fulfillment, metadata-index 모두 PASS
>  - **search 서비스의 `buyer` / `buyer_api_key` 테이블이 central DB 에 없어 bootstrap 실패** — 본 dev-spec 의 FR-INF-* 로 해소

---

## 1. 기능 개요

RadiVault 의 세 공개·준공개 표면(①마케팅 홈페이지, ②바이어 포털 `portal.radivault.io`, ③병원 포털 `hospital.radivault.io`) 을 **CEO 미팅 D-14 기준으로 "투자자 + 병원 경영진 1인 겸임" 청중에게 시연 가능한 수준까지** 전면 리디자인한다. 기존 `web/portal/` 은 폐기하지 않고 정보구조·시각·카피·BFF 계약을 재작업한다.

리서치 §0 의 북극성 **"정보 밀도 높음 · 신뢰 우선 · 이중 언어 · compliance 강조"** 를 구현 수준의 제약으로 풀어 `dev-spec-buyer-portal-demo` 보다 한 단계 외연을 넓힌다. 기존 dev-spec 이 "로그인 이후 UI" 만 다뤘다면 본 dev-spec 은 **비로그인 홈페이지 + 2 병원 Federated 시연** 을 포함한다.

---

## 2. 사용자 스토리

- **As a** 글로벌 AI 기업 바이어(영어권, 개발자 또는 의사결정자), **I want** RadiVault 홈페이지에서 "한국 의료영상 데이터의 compliance 증거와 실제 제품 UI" 를 30 초 안에 확인하고 `Request data access` 로 리드를 남기고 **so that** 이후 바이어 포털에서 두 병원 풀 검색·주문·다운로드까지 한 브랜드로 흘러갈 수 있다.
- **As a** 한국 대형·중견 병원 C-레벨(CTO/DPO/기획실장), **I want** 한국어 페이지에서 사업자등록·대표자·1544 전화·KISMS 배지·PIPA §28-8 설명을 우선 확인하고 **so that** "검증되지 않은 스타트업" 인상 없이 병원 파트너 상담을 시작할 수 있다.
- **As a** 바이어 Dana (개발자, 영어), **I want** 검색 결과가 "1 검색 = N 병원 집계" 로 보이고 동일 코호트에 HOSP-001 과 HOSP-002 의 study 가 섞여서 나와 **so that** Federated 구조의 가치를 한 화면에서 체감한다.
- **As a** 병원 HOSP-001 운영자, **I want** 대시보드에 우리 병원이 업로드한 study 수 / 데이터 용량 / 모달리티 분포 / 이번 달 수익 시뮬 / 주문 들어온 study 수 / Gateway heartbeat / audit chain 상태 / 감사 앵커 최근 시각 / 쿼터 / ruleset-salt 버전 을 한 화면에서 확인 **so that** PIPA §28-8 CEO 개인책임 대응 증거로 바로 사용한다.
- **As a** 데모 운영자(Kyle), **I want** D-day 에 `?demoop=1` + Cmd+1~7 로 장면 전환을 안정적으로 시연 **so that** 시연 실패 런북을 발동할 일이 없다.

---

## 3. 범위

### 포함 (In-scope)

1. **트랙 1 — 마케팅 홈페이지** (비로그인, 공개).
   - 영문 기본 (`/`), 한국어 (`/ko`) 라우트.
   - Hero / Trust bar / Value prop / How it works / Metrics / Security & Compliance / Korean B2B footer.
   - 이중 CTA: 영문 `Request data access`, 한국어 `병원 파트너 신청`.

2. **트랙 2 — 바이어 포털** (`portal.radivault.io` 단일 호스트 내 `/` 포함, 또는 동일 도메인 `/portal` sub-path — §Q1 결정).
   - 로그인, 검색(3-pane), Study detail, Cart/Order flow, Order tracking, Downloads, Account/Billing placeholder.
   - 핵심 가치: "1 검색 = N 병원" first-class metric.

3. **트랙 3 — 병원 포털** (`hospital.radivault.io` 또는 `/hospital` sub-path).
   - HOSP-001 / HOSP-002 각 담당자 로그인.
   - 확장 대시보드 (현재 6-tile → 9-tile + audit preview + 쿼터 + ruleset·salt 버전).

4. **트랙 4 — 인프라·부트스트랩 (FR-INF-*)**.
   - search 서비스의 `buyer` / `buyer_api_key` 테이블 central DB 에 마이그레이션 (현재 누락).
   - `seed_buyer.py` 가 실제로 동작하도록 DSN 정렬.
   - `verify.py` V-8 체크에 buyer 로그인 왕복 성공이 포함되도록 확장.
   - `scripts/demo_setup/bootstrap_search_roles.sql` 이 테이블 DDL 도 포함하도록 확장.

5. **이중 언어 (bilingual-by-design)**.
   - 홈페이지: EN 기본, KR 완전 번역 (UI 카피 + footer 법적 블록).
   - 바이어 포털: EN 기본, KR 은 i18n 토큰만 예약 (v0.1.1 deferred).
   - 병원 포털: KR 기본, EN 은 메뉴 라벨 수준 (SRE 접근 시).

6. **Federated 시연 문법** (2 병원).
   - 검색 결과 row 에 `hospital_opaque_id` 표시 + hover 시 병원 총 study 수.
   - Cohort sidebar 에 "From 2 hospitals" first-class metric.
   - Order flow 가 선택된 study 들의 소속 병원을 `allowed_hospitals` 로 scope 하여 발송.

### 제외 (Out-of-scope)

1. **DICOM 뷰어 통합** (OHIF embedded) — v0.2, 별 기능 (`dev-spec-dicom-viewer`).
2. **실제 결제** (Stripe / 국내 PG) — v0.2, `dev-spec-billing-revenue-share`.
3. **Self-serve 바이어 가입 (웹 회원가입)** — 의료 데이터 접근의 self-serve 는 컴플라이언스 리스크 (리서치 §2.7). 초대 기반 유지.
4. **SOC 2 Type II / ISO 27001 배지 실제 취득** — 본 dev-spec 은 "in preparation" 보수 어투 카피만 확정. 실제 취득은 Kyle 외부 트랙.
5. **3 도메인 완전 분리** (radivault.io + portal.radivault.io + hospital.radivault.io) — 단일 도메인 sub-path 시작 권고, 도메인 분리는 §Q1 결정.
6. **1:1 카카오톡·Zendesk 채널 연동** — "Contact us" 폼 + mailto 만 v0.1 (리서치 §2.7).
7. **Saved cohorts · 뉴스레터 가입 · Investor box · Pricing table · Changelog RSS** — v0.1.1 backlog.
8. **추후 3개 이상 병원 확장 UI 변경** — v0.2, 현재는 N=2 가정 하에 "N 병원" 라벨만 유지.
9. **다크모드** — `dev-spec-buyer-portal-demo` Q-UI-1 과 동일, v0.1.1 deferred.
10. **Figma source file** — ASCII 와이어 + CSS 토큰만 유지 (design-spec 이 담당).

---

## 4. 기능 요구사항

### 4.1 FR-HP-* — 홈페이지 (Homepage)

> 대상: 비로그인 공개. 리서치 §2·§6 기반.

- **FR-HP-1** (Hero): `/` 경로에 영문 Hero 섹션 렌더. Headline 은 **옵션 A** 기본값 `"Korea's medical imaging data, compliantly delivered for global AI."` (리서치 §2.10 A-1). §Q4 결정 전까지 옵션 A 고정. Subhead 는 리서치 §2.10 A-1 subhead 문안 그대로.
- **FR-HP-2** (Hero CTA): 좌측 `Request data access` (primary) → `/contact?intent=buyer` mailto 또는 문의 폼. 우측 `View technical overview` (secondary) → `/docs` 또는 PDF 다운로드 (§Q5).
- **FR-HP-3** (Hero 시각): 우측에 **실제 바이어 포털 `/search` 스크린샷 1 장** (완전 익명 TCIA seed 기반). 리서치 §2.6 권고. placeholder 아이콘 금지.
- **FR-HP-4** (Trust Bar): 파일럿 병원 로고 없음. 대체로 리서치 §2.10 A-2 "컴플라이언스 status ladder" 4 칼럼 — `PIPA §28-8 compliant` / `SOC 2 Type II in preparation` / `ISO 27001 aligned` / `HIPAA-aligned de-identification`. 각 칼럼 클릭 시 `/trust-center` anchor 스크롤. 어투는 "in preparation" / "aligned" 보수 어투 고수 (리서치 §2.2·§2.10).
- **FR-HP-5** (How It Works): 4-step diagram 렌더 — (1) DICOM PHI 태그 제거 PS3.15 Annex E / (2) Burn-in OCR 마스킹 / (3) 3D defacing / (4) Outbound-only TLS 1.3 업로드. 각 스텝에 `gateway-agent` / `de-id-engine-v0.2` GitHub-style 앵커 링크 (리서치 §2.9 #1).
- **FR-HP-6** (Chain of Custody 뷰): 5-step 수평 flow — 병원 PACS → Gateway → De-ID → Central → Buyer. 각 화살표에 "WORM audit log event" 라벨 (리서치 §2.9 #2).
- **FR-HP-7** (Metrics 섹션): 본격 메트릭은 **real-small-honest** 원칙 (리서치 §2.4). 표시 값:
  - `2 hospitals federated in demo` (실측, Bon + Tunteun).
  - `~250 studies indexed (TCIA CC-BY seed)` — "Demo dataset based on public TCIA" 라벨 필수.
  - `p95 search latency < 2s` (metadata-index SLA).
  - `14 DICOM modalities supported` (실측, metadata-index facet).
  - 구매자 실명·실 숫자 0 건 (§L-1 위반 금지).
- **FR-HP-8** (Security & Compliance 섹션): 별도 섹션으로 (a) PIPA §28-8 요약 (b) HIPAA-aligned Safe Harbor 단계 (c) outbound-only 네트워크 원칙 (d) 감사 WORM + 5년 보존 (ARCHITECTURE §4.7). 링크: `/trust-center` (v0.1 stub).
- **FR-HP-9** (Korean B2B 풋터, 한국어 페이지 전용): `/ko` 경로는 리서치 §8.6 전면 수용 — 대표자(Kyle Jeon) / 사업자등록번호 [TBD §Q8] / 주소 [TBD §Q8] / 고객센터 전화 [TBD §Q8] / 개인정보처리방침 링크 / ISMS-P 준비 중 / ISO 27001 aligned 배지. §Q8 결정 전까지 `[TBD]` 플레이스홀더 허용하되 빌드 시 `NODE_ENV=production` 이면 `[TBD]` 문자열 감지 시 CI fail.
- **FR-HP-10** (Footer 구조):
  - EN (`/`): 6 컬럼 (Product / Solutions / Developers / Resources / Company / Legal). Stripe/Vercel 스타일 (리서치 §2.5).
  - KR (`/ko`): 4 컬럼 (제품·솔루션 / 기술 / 회사 / 법적) + 하단 법적 블록 (FR-HP-9). Ncloud 스타일.
- **FR-HP-11** (Language Switch): 우측 상단 `EN | KR` 토글. 쿠키 `radivault_locale` 로 선호 저장 (365 일 TTL). 초기 접속 시 `Accept-Language` 헤더 first-match.
- **FR-HP-12** (Contact Form): `/contact` 에 간단 폼 (이름 · 회사 · 이메일 · 의도 `[buyer|hospital|press|investor|other]` · 메시지). POST `/api/contact` 는 FR-INF-4 의 최소 이메일 릴레이. 파일업로드·스팸방지 reCAPTCHA 는 out-of-scope, mailto 링크도 병기.
- **FR-HP-13** (투자자 / 파트너십 박스, 리서치 §2.9 #4): Hero 옆 소형 링크 `For investors →` `For hospital partners →` 2 개. §Q6.

### 4.2 FR-BP-* — 바이어 포털 (Buyer Portal)

> 대상: 로그인 후 공개. 기존 `web/portal/src/app/(search|orders)/` 리디자인.

- **FR-BP-1** (브랜드명): 바이어 포털 UI 상단 로고 옆 워드마크. **권고 `RadiVault Marketplace`** (§Q2). 쓰지 않는 명: `Data Atlas` (Gradient 충돌), `Hub`, `Exchange`.
- **FR-BP-2** (로그인 화면 `/signin`): 기존 유지하되 Hero 우측에 "Request data access" 보조 링크 추가 (self-serve 가입 금지 — 리서치 §2.7).
- **FR-BP-3** (검색 3-pane 레이아웃, 리서치 §7.3 + §3.1~3.3):
  - 좌 패싯 (280 px 고정, collapsible 1280 px 이하).
  - 중앙 결과 리스트 (DataTable).
  - 우 Cohort sidebar (320 px 고정, "Selected N · From 2 hospitals" first-class).
- **FR-BP-4** (검색 결과 row 정보 밀도, 리서치 §3.3): 한 row 에 **최소 7 개 필드** — check · modality badge(색상 코드화) · body_part · age_bucket · sex · n_instances · size_mb · study_year · hospital_opaque_id. row hover 시 마이크로 툴팁 (study 의 병원 누적 study 수).
- **FR-BP-5** (Modality 색상 토큰, 리서치 §3.3): CSS 변수 추가 — CT=blue(#2563eb) / MR=purple(#7c3aed) / CR/DR=green(#059669) / MG=pink-darker(#9d174d) / US=orange(#ea580c) / PT=red(#dc2626) / XA=gray(#4b5563). `--color-modality-{key}`. design-spec-buyer-portal-demo §10 접근성 WCAG 3:1 대비 보정 승계.
- **FR-BP-6** (Federated Signal, "1 검색 = N 병원"): 검색 결과 상단 sticky 배지 — `<X> studies across 2 hospitals` (값 server-side 계산: `COUNT(DISTINCT hospital_opaque_id)`). 리서치 §0 northstar.
- **FR-BP-7** (Facet 기본값): modality / body_part / age_bucket / sex / manufacturer / year. **`min_hospitals`** slider 를 facet 상단에 배치 (1~20, 기본 1). 리서치 §3.3 + metadata-index `SearchRequest.min_hospitals` 스키마.
- **FR-BP-8** (Study detail `/studies/[id]`): 신규 페이지. FR-BP-4 의 row click 에서 진입. 렌더:
  - 메타데이터 테이블 (StudyItem 필드 전체).
  - Series 리스트 (SearchStudyDetail.series[]).
  - Hospital origin 배지 (`hospital_opaque_id`).
  - 뷰어 없음 (§Out-of-scope #1) — placeholder `<ViewerStub>` 컴포넌트.
  - "Add to cohort" 버튼 (FR-BP-9 로 연결).
- **FR-BP-9** (Cart/Cohort flow `/orders/new`): 기존 ReviewOrderModal 을 풀페이지로 승격. 렌더:
  - 선택된 study 테이블.
  - "From 2 hospitals" 분포 pie.
  - Total estimated cost (마스킹 `—` 또는 "Contact for pricing", §Q3).
  - DUA checkbox + Submit. Submit 이 `POST /v1/orders` (order-fulfillment) 로 넘어가며 `allowed_hospitals` scope 자동 주입.
- **FR-BP-10** (Order tracking `/orders` + `/orders/[id]`): 기존 5-phase stepper + "View timeline" drawer 승계. drawer 에 12-state FSM + download_event 로그 표시 (리서치 §3.4·§3.6 B-3).
- **FR-BP-11** (Downloads `/orders/[id]/downloads`): 기존 tab (browser / curl / python) + TTL countdown 승계. Stripe 수준의 "마스킹된 API 키 리스트 + revoke" 는 Account 페이지에서 (FR-BP-13).
- **FR-BP-12** (Top Nav): 로고 · Search · Orders · Docs · Account · Sign out. EN 고정. Account 드롭다운에 API keys / Billing / Sign out.
- **FR-BP-13** (Account `/account`): 최소 스펙:
  - Profile (buyer_id · email · tier · created_at).
  - API Keys 리스트 (kid prefix · created_at · last_used_at · revoke 버튼).
  - Billing placeholder ("Invoicing handled offline in v0.1").
  - Stripe 수준 마스킹 `rv_live_****...` (리서치 §3.5).
- **FR-BP-14** (Empty / Error / Loading states, 리서치 §3.1): Linear 수준 일러스트 + CTA. `design-spec-buyer-portal-demo` §7 에러 taxonomy 21 코드 전건 승계.
- **FR-BP-15** (Saved searches — Local storage, 리서치 §3.2): 최근 5 검색 로컬 저장 + `/search` 좌측 상단 "Recent searches" 미니 섹션. Saved cohorts 는 v0.1.1 backlog.
- **FR-BP-16** (성능): 초기 로딩 후 search p95 < 2s (metadata-index SLA 승계), navigation TTFB < 500 ms (BFF cache).
- **FR-BP-17** (BFF 계약 — 기존 유지 + 확장):
  - `POST /api/search/studies` → upstream search:8001 `POST /v1/search/studies` (페이로드 field name 은 spec 의 `limit` 로 통일, 기존 구현의 `page_size` 는 제거).
  - `GET /api/search/facets` → upstream `POST /v1/search/studies` with `limit=0 include_facets=true` wrapper.
  - 신규: `GET /api/search/studies/[id]` → upstream `GET /v1/search/studies/{uid}`.
  - 신규: `GET /api/hospitals` → upstream `POST /v1/search/studies` with `include_facets=true`, `.facets.hospital` projection (리서치 §0 federated 시각화).
- **FR-BP-18** (정보 구조 sitemap):
  ```
  portal.radivault.io/
    /signin                     — FR-BP-2
    /                           — Dashboard (FR-BP-20)
    /search                     — 3-pane (FR-BP-3)
    /studies/[id]               — FR-BP-8 신규
    /orders                     — list
    /orders/new                 — FR-BP-9 신규 (modal → 풀페이지)
    /orders/[id]                — tracker (FR-BP-10)
    /orders/[id]/downloads      — FR-BP-11
    /account                    — FR-BP-13 신규
    /docs                       — stub
  ```
- **FR-BP-19** (Logo / 워드마크 사용): 바이어 포털은 Buyer blue (#2563eb). 홈페이지와 동일 톤. Hospital teal 금지.
- **FR-BP-20** (`/` 로그인 이후 대시보드, 리서치 §3.2·§3.6 B-1): 기존 `/search` 리디렉트 → 대시보드로 전환. 타일 5 개:
  1. Active orders (count + phase mini stepper).
  2. Recent searches (FR-BP-15).
  3. Pending invoices (stub, "offline").
  4. API usage this month (rate limit / quota, metadata-index `/v1/search/hospitals` 는 여기 사용 X — buyer_quota_remaining 은 `SearchResponse.meta` 에서).
  5. Platform announcements (changelog `docs/marketing/changelog-v02-pixel-deid-ko.md` MDX import 또는 stub).

### 4.3 FR-HO-* — 병원 포털 (Hospital Portal)

> 대상: HOSP-001 / HOSP-002 운영자. 한국어 기본. 기존 `web/portal/src/app/hospital/` 확장.

- **FR-HO-1** (브랜드명): 병원 포털 상단 워드마크 `RadiVault 병원 콘솔` (한국어). Hospital teal (#0d9488). design-spec-buyer-portal-demo §2 승계.
- **FR-HO-2** (로그인 `/hospital/signin`): 기존 토큰 기반 유지. 파일럿 이관 시 SSO (§Q10).
- **FR-HO-3** (대시보드 `/hospital` — 9 타일, 기존 6 → +3):
  1. **우리 병원 업로드 study 수** (기존 FR-B-1, sparkline 추가) — FR-HO-4.
  2. **Total bytes** (신규 본 dev-spec) — 월별 증분 + 누적.
  3. **이번 달 수익 시뮬** (기존 FR-B-2) — disclaimer 고정 "시뮬레이션 — v0.2 정산 대기".
  4. **주문 들어온 study 수** (기존 FR-B-3, buyer 실명 마스킹).
  5. **Gateway heartbeat** (기존 FR-B-4, 24h uptime bar 추가) — <5m online / <30m warning / else offline.
  6. **월별 수익 추세** (기존 FR-B-5) — bar + stacked by tier.
  7. **Modality 분포 도넛** (기존 FR-B-6).
  8. **Audit chain 상태 (신규)** — FR-HO-5.
  9. **Quota & ruleset 정보 (신규)** — FR-HO-6.
- **FR-HO-4** (타일 1 sparkline): Recharts 또는 순수 SVG. 최근 12 월 + `today` 강조.
- **FR-HO-5** (타일 8 — Audit chain 상태, 신규): 표시 필드:
  - 마지막 audit anchor 시각 (UTC → KST 표시).
  - 최근 anchor hash prefix 16 자 (PHI 아님).
  - 체인 연속성 ok/break (gateway-agent 의 `post_audit_anchor` 결과).
  - `audit_hash_chain_last_anchor_age_seconds` Prometheus 메트릭 mirror.
- **FR-HO-6** (타일 9 — Quota & ruleset, 신규): 표시 필드:
  - 일일 업로드 한도 / 사용량 (central-ingest `FR-45` 일일 byte quota 참조 — 현재 v0.1.1 backlog, **본 dev-spec 이 UI-level stub 로 선행 노출 + 실 집행은 v0.1.1**).
  - 월간 업로드 한도 / 사용량.
  - `max_concurrent_uploads` (Gateway config).
  - 현재 ruleset 버전 (Gateway de-id config).
  - 현재 salt 버전 (Gateway config).
- **FR-HO-7** (Audit 로그 미리보기 섹션 `/hospital` 하단, 리서치 §4.3·§4.6 C-2): 최근 20 이벤트 리스트 (type · 시각 · hash prefix). "전체 로그 →" 링크는 `/hospital/audit` (v0.1.1 full view, v0.1 은 페이지 stub 만).
- **FR-HO-8** (Korea heatmap 타일, 기존 유지): 실명 노출 금지 (§L-1). 2 병원만 시드 표시 (HOSP-001 서울, HOSP-002 경기 예시). 실 좌표는 §Q7.
- **FR-HO-9** (Top Nav 한국어): 로고 · 대시보드 · 주문 · 감사 · 설정 · 로그아웃. 라벨 짧게 (한국어 4 자 이하, 리서치 §4.4).
- **FR-HO-10** (풋터 한국어): FR-HP-9 동일 법적 블록. 우측 하단 플로팅 "1:1 문의" 버튼 (mailto 만 v0.1, 리서치 §4.6 C-3).
- **FR-HO-11** (정보 구조 sitemap):
  ```
  hospital.radivault.io/
    /hospital/signin
    /hospital                   — 9-tile 대시보드
    /hospital/orders            — 주문 (마스킹)
    /hospital/audit             — stub, v0.1.1
    /hospital/settings          — stub (ruleset·salt 읽기 전용 view)
  ```
- **FR-HO-12** (2 병원 격리, CRITICAL SECURITY): 로그인 세션 `hospital_id` 로 scope. 다른 병원 데이터 절대 유출 금지. `GET /api/hospital/*` BFF 는 `hospital_id` 쿠키 추출 후 central-ingest `/v1/hospital/me/*` 토큰 치환. design-spec-buyer-portal-demo AC-B-8 / qa-report-buyer-portal-demo 공격 시나리오 #2 승계.
- **FR-HO-13** (한국어 날짜·통화): `toLocaleString('ko-KR')`, KRW 는 `₩ 18,400,000` 풀스펠 (리서치 §4.4).
- **FR-HO-14** (BFF 엔드포인트 확장):
  - 기존 `GET /api/hospital/me/stats` 유지.
  - 신규 `GET /api/hospital/me/audit-chain-status` → upstream central-ingest `GET /v1/hospital/me/audit-chain-status` (FR-INF-6 로 central-ingest 에 신규 엔드포인트 요구).
  - 신규 `GET /api/hospital/me/quota` → upstream central-ingest `GET /v1/hospital/me/quota` (FR-INF-7).
- **FR-HO-15** (정보 밀도, 리서치 §4.4): 카드 타이틀 한국어 굵게 + 큰 폰트. 라벨 4 자 이하. "주문 내역" "수익 추세" 등.

### 4.4 FR-INF-* — 인프라·부트스트랩 (Bootstrap)

> **쿠리티컬 블로커**: search 서비스가 현재 buyer 로그인 왕복 불가. 본 트랙 없으면 트랙 2 가 데모에서 동작 안 함.

- **FR-INF-1** (`buyer` / `buyer_api_key` / `search_audit` 테이블 DDL central DB 적용): metadata-index `dev-spec-metadata-index §6` 의 3 테이블 스키마를 central DB (`radivault_central`) 에 적용. 방법: Alembic migration (search repo 또는 central repo 중 하나에 귀속).
  - 결정: **search repo 에 Alembic revision 추가**. 근거: `dev-spec-metadata-index §6` 가 이미 search-side 테이블이라고 정의. central Alembic 은 central 테이블만 관할.
  - 마이그레이션 파일: `alembic/versions/000X_search_tables.py`.
- **FR-INF-2** (`scripts/demo_setup/bootstrap_search_roles.sql` 확장): 기존 role 생성에 더해 테이블 DDL 도 포함하거나 Alembic 을 선행 실행. 선택: **Alembic 을 `inject_all.sh` 에 추가 (STEP 0)**. SQL 파일에 테이블 DDL 추가 시 Alembic 과 drift 위험.
- **FR-INF-3** (`seed_buyer.py` 확장): 기존 `buy_demo001` + key 발급 그대로. 추가 검증 — key 발급 후 `POST /v1/search/studies` 왕복 smoke test 1회 (401 아니면 통과). 실패 시 exit 2.
- **FR-INF-4** (`verify.py` V-8 확장): 기존 V-1..V-8 유지 + **V-9 신설** — "buyer login roundtrip" — `.buyer_key.local.txt` 로 `POST /v1/search/studies` 호출 → 200 + `items` 배열 존재 확인. 실패 시 demo_seed_ready.lock 생성 보류.
- **FR-INF-5** (contact form 릴레이, `POST /api/contact`): FR-HP-12 지원. 최소 구현 — 환경변수 `CONTACT_INBOX_EMAIL` + SMTP 릴레이 (또는 Zendesk/Slack webhook 추후). v0.1 은 구조화 JSON 로그만 + stdout 으로 충분. 실 이메일 발송은 §Q5.
- **FR-INF-6** (central-ingest 신규 엔드포인트 `GET /v1/hospital/me/audit-chain-status`): 응답 shape:
  ```json
  {
    "hospital_id": "HOSP-001",
    "last_anchor_at": "2026-04-25T10:23:00Z",
    "last_anchor_age_seconds": 312,
    "last_anchor_hash_prefix": "a3f8d9c1b2e4f5a6",
    "chain_continuous": true,
    "anchor_count_24h": 48
  }
  ```
  - 구현: gateway-agent 가 이미 `post_audit_anchor` 으로 중앙에 전송 중. central-ingest 측에서 `audit_anchor` 테이블 (central-ingest dev-spec §6) query + 직전 앵커 연속성 재확인.
- **FR-INF-7** (central-ingest 신규 엔드포인트 `GET /v1/hospital/me/quota`): 응답 shape:
  ```json
  {
    "hospital_id": "HOSP-001",
    "daily": { "bytes_used": 123456789, "bytes_limit": 10737418240, "resets_at": "2026-04-26T00:00:00+09:00" },
    "monthly": { "bytes_used": 987654321, "bytes_limit": 322122547200, "resets_at": "2026-05-01T00:00:00+09:00" },
    "max_concurrent_uploads": 4,
    "ruleset_version": "v0.1.0",
    "salt_version": "2026-01",
    "pixel_engine_version": "v0.2.0"
  }
  ```
  - v0.1 구현: `bytes_used` 는 `study.total_bytes` SUM (시간 범위). `_limit` 는 central-ingest `FR-45` 백로그 (실 집행 없이 config const 로 시작).
- **FR-INF-8** (기존 portal `SearchApp.tsx` 의 `page_size` 사용 수정): 검색 요청 페이로드를 `dev-spec-metadata-index §6.4` 의 `SearchRequest.limit` 로 통일. 기존 `{ page_size: 25 }` → `{ limit: 25 }`. 이는 현재 구현이 spec 불일치 상태.
- **FR-INF-9** (기존 portal `SearchResp` 타입 수정): 현재 `{ items, total, next_cursor? }` → dev-spec-metadata-index `SearchResponse` 전 필드 타입 사용 (`pagination.next_cursor` / `pagination.has_more` / `meta.total_hint` / `meta.facets_suppressed` / `items: StudyItem[]`). BFF 층은 그대로 통과시키되 TypeScript 타입 정합성 확보.
- **FR-INF-10** (search-admin CLI 준비 확인): `search-admin buyer create` / `search-admin buyer key issue` 가 FR-INF-1 후 정상 작동 확인 (이미 구현 존재, FR-INF-1 블로커만 해소하면 됨).

### 4.5 FR-SH-* — 공유 (Shared UI · tokens · i18n)

- **FR-SH-1** (디자인 토큰 공유): `design-spec-buyer-portal-demo §2` 전면 승계 — Buyer cool blue + Hospital teal 분리, Inter + Pretendard Variable, WCAG AA 대비. 홈페이지는 Buyer blue 기본 + 한국어 페이지만 Teal 액센트 (리서치 §2.6 권고).
- **FR-SH-2** (shared `<Footer>` 컴포넌트): 3 variant — `buyer` (EN, 6 컬럼), `hospital` (KR, 4 컬럼 + 법적 블록), `homepage` (locale 에 따라 두 variant 스위치).
- **FR-SH-3** (shared `<ComplianceBadge>` 컴포넌트): 4 variant (PIPA / SOC 2 / ISO 27001 / HIPAA). 각각 "in preparation" / "aligned" 어투 강제. 단정적 "certified" / "guaranteed" 타이포 시 lint rule (eslint plugin 또는 grep 기반 CI check — FR-NFR-7).
- **FR-SH-4** (TCIA CC-BY attribution, 홈페이지 Metrics 섹션 + Hero 하단): 문구 `"Demo data based on The Cancer Imaging Archive (TCIA) — CC BY 3.0/4.0."` — `dev-spec-buyer-portal-demo §L-3` 승계.
- **FR-SH-5** (PHI 0 건 렌더 보장): 모든 병원·환자·구매자 실명 0 건. assertion 테스트 (Playwright + grep).

---

## 5. 비기능 요구사항

| 항목 | 요구 |
|------|------|
| **성능 — LCP** | Homepage `/` 와 `/ko` LCP p75 < 2.5 s (Lighthouse 모바일 + 데스크탑). Buyer Portal 내부 페이지 TTFB p75 < 500 ms. 초기 JS bundle < 250 KB gzipped (홈페이지). |
| **성능 — Search** | `/search` first paint < 1 s (cached facets) / 검색 요청 p95 < 2 s (metadata-index SLA 승계). |
| **접근성** | WCAG 2.1 AA (design-spec-buyer-portal-demo §10 승계). 키보드 전체 탐색. 색 대비 4.5:1 (텍스트), 3:1 (UI 컴포넌트). modality-MG #9d174d 승계. |
| **국제화** | EN · KR 두 언어 완전. `next-intl` 또는 순수 dictionary (§Q9). 한국어 폰트 Pretendard Variable self-hosted. |
| **브라우저** | Chrome 110+ / Safari 16+ / Firefox 115+ / Edge 110+. Desktop 최적화 ≥ 1280 px, tablet best-effort, mobile fallback (홈페이지만 mobile-friendly 필수). |
| **보안** | iron-session cookie HttpOnly + Secure (prod) + SameSite=Lax · 12h TTL. CSP `default-src 'self'; script-src 'self' 'unsafe-inline'; img-src 'self' data: https:;`. API keys never in browser bundle. |
| **로깅·감사** | 모든 BFF 요청에 `request_id` · `buyer_pk` or `hospital_id` · 경로 · 상태코드 · 지연시간 JSON 로그. PHI 절대 금지 (FR-SH-5). search_audit 테이블 (metadata-index) 유지. |
| **홈페이지 SEO** | meta tags (title / description / OpenGraph / Twitter Card / canonical / hreflang). `/sitemap.xml` + `/robots.txt` (바이어·병원 포털은 `Disallow`). JSON-LD Organization schema. |
| **가용성** | v0.1 best-effort. 홈페이지는 static export 가능하면 SSG. Buyer/Hospital 은 SSR (세션 필요). |
| **컴플라이언스 어투** | "certified" / "guaranteed" / "HIPAA-compliant" 단정 단어 0 건. "aligned" / "in preparation" / "designed to support" 보수 어투만. lint 검사 (FR-SH-3). |
| **FR-NFR-7 CI 체크** | CI 단계에 `grep -ri 'certified\|guaranteed\|HIPAA-compliant' web/portal/src/` 가 0 건이어야 PASS. placeholder `[TBD]` / `[X]M` 은 `NODE_ENV=production` 빌드에서 fail. |

---

## 6. 데이터 모델

### 6.1 기존 테이블 재사용 (수정 없음)

- `study`, `series`, `instance` (central-ingest)
- `audit_ingest_event`, `audit_anchor` (central-ingest, gateway-agent)
- `order`, `transfer_job`, `download_event`, `order_outbox` (order-fulfillment)
- `hospital`, `auth_token` (central-ingest)

### 6.2 신규 테이블 (FR-INF-1 — search-side, central DB 에 적용)

**`dev-spec-metadata-index §6` 그대로 승계. 본 dev-spec 은 그 적용만 요구.**

```sql
-- alembic/versions/000X_search_tables.py (search repo) — upgrade()
CREATE TABLE buyer (
  buyer_pk BIGSERIAL PRIMARY KEY,
  buyer_id TEXT UNIQUE NOT NULL,          -- "buy_demo001" 형식
  email TEXT NOT NULL,
  tier TEXT NOT NULL DEFAULT 'preview',   -- preview | paid | enterprise
  scope_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at TIMESTAMPTZ,
  UNIQUE (buyer_id)
);

CREATE TABLE buyer_api_key (
  api_key_pk BIGSERIAL PRIMARY KEY,
  buyer_pk BIGINT NOT NULL REFERENCES buyer(buyer_pk),
  kid TEXT UNIQUE NOT NULL,                -- "rv_live_<8hex>" prefix
  secret_argon2id TEXT NOT NULL,           -- argon2id 해시
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ,                  -- 180d default (§Q14)
  last_used_at TIMESTAMPTZ,
  revoked_at TIMESTAMPTZ
);
CREATE INDEX idx_buyer_api_key_kid ON buyer_api_key(kid) WHERE revoked_at IS NULL;

CREATE TABLE search_audit (
  audit_pk BIGSERIAL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  buyer_pk BIGINT NOT NULL,
  kid TEXT,
  endpoint TEXT NOT NULL,
  filter_sha256 TEXT,
  filter_json_sha256 TEXT,
  result_count INTEGER,
  cache_hit BOOLEAN,
  status_code INTEGER,
  error_code TEXT,
  latency_ms INTEGER,
  request_id TEXT,
  cursor_presence BOOLEAN,
  PRIMARY KEY (audit_pk, created_at)       -- composite PK (qa-report-metadata-index Round 2 fix 승계)
);
CREATE INDEX idx_search_audit_buyer_time ON search_audit(buyer_pk, created_at DESC);
```

> ERD 는 `dev-spec-metadata-index §6.3` 참조.

### 6.3 신규 컬럼 · 필드 (없음)

본 dev-spec 의 데이터 모델 변경은 **FR-INF-1 의 기존-미적용 테이블 적용만**. 신규 컬럼 / 신규 테이블 / 신규 인덱스 없음.

---

## 7. API 계약

### 7.1 홈페이지 (신규)

```
GET /
  Request:  (공개)
  Response: HTML (SSG/SSR)
  Errors:   none (정적)

GET /ko
  Request:  (공개)
  Response: HTML (한국어 locale)
  Errors:   none

GET /contact
  Request:  (공개)
  Response: HTML (폼)
  Errors:   none

POST /api/contact
  Request:  {
    name: string, company: string, email: string,
    intent: "buyer"|"hospital"|"press"|"investor"|"other",
    message: string
  }
  Response: 202 { accepted: true, request_id: string }
  Errors:   400 (validation), 429 (rate limit — 1/min/IP)
```

### 7.2 바이어 포털 BFF (수정·신규)

```
POST /api/search/studies                    # 수정: payload field 정정 (FR-INF-8)
  Request:  SearchRequest (dev-spec-metadata-index §6.4 — limit / cursor / ...)
  Upstream: search:8001 POST /v1/search/studies (Authorization: Bearer rv_live_*)
  Response: SearchResponse (dev-spec-metadata-index §6.4)
  Errors:   401 (signin redirect), 422 (ERR_QUERY_TOO_BROAD), 429, 5xx

GET  /api/search/facets                     # 수정: wrapper 유지하되 타입 정합
  Upstream: search:8001 POST /v1/search/studies { include_facets: true, limit: 0 }
  Response: FacetsResponse
  Errors:   401, 429, 5xx

GET  /api/search/studies/[id]               # 신규 (FR-BP-8)
  Upstream: search:8001 GET /v1/search/studies/{uid}
  Response: SearchStudyDetail
  Errors:   401, 404 (ERR_STUDY_NOT_FOUND), 5xx

GET  /api/hospitals                         # 신규 (FR-BP-17 "From N hospitals")
  Upstream: search:8001 GET /v1/search/hospitals (구현 존재)
  Response: HospitalsResponse
  Errors:   401, 5xx

POST /api/orders                            # 수정 없음 (order-fulfillment 계약)
GET  /api/orders                            # 수정 없음
GET  /api/orders/[id]                       # 수정 없음
GET  /api/orders/[id]/downloads             # 수정 없음
```

### 7.3 병원 포털 BFF (수정·신규)

```
GET /api/hospital/me/stats                  # 기존 (central-ingest /v1/hospital/me/stats)
GET /api/hospital/me/gateway-health         # 기존
GET /api/hospital/me/orders                 # 기존 (fulfillment)
GET /api/hospital/me/audit                  # 기존 (최근 감사 이벤트)

GET /api/hospital/me/audit-chain-status     # 신규 (FR-HO-14 + FR-INF-6)
  Upstream: central-ingest GET /v1/hospital/me/audit-chain-status
  Response: 위 FR-INF-6 shape
  Errors:   401, 5xx

GET /api/hospital/me/quota                  # 신규 (FR-HO-14 + FR-INF-7)
  Upstream: central-ingest GET /v1/hospital/me/quota
  Response: 위 FR-INF-7 shape
  Errors:   401, 5xx
```

### 7.4 세션 BFF

```
POST /api/session                           # 기존
POST /api/hospital/session                  # 기존
POST /api/demoop/enable                     # 기존 (H-1 fix 적용 완료, Session 12)
POST /api/demoop/disable                    # 기존
DELETE /api/session                         # 기존
DELETE /api/hospital/session                # 기존
```

### 7.5 에러 envelope

모든 BFF 에러는 `design-spec-central-ingest §2` envelope 형식 유지:

```json
{
  "error": "ERR_QUERY_TOO_BROAD",
  "detail_en": "estimated rows exceed limit",
  "detail_ko": "예상 결과 수가 한도를 초과합니다",
  "hint": "add modality filter",
  "request_id": "req_01HX...",
  "doc": "https://docs.radivault.io/errors/ERR_QUERY_TOO_BROAD"
}
```

---

## 8. 시퀀스·플로우

### 8.1 홈페이지 첫 방문 → Request Data Access

```
User Browser               Next.js /              BFF /api/contact         Email Relay
    │ GET /                    │                        │                       │
    │────────────────────────▶ │                        │                       │
    │ 200 HTML (SSG)           │                        │                       │
    │◀──────────────────────── │                        │                       │
    │ Click "Request data"     │                        │                       │
    │ GET /contact             │                        │                       │
    │────────────────────────▶ │                        │                       │
    │ 200 HTML form            │                        │                       │
    │◀──────────────────────── │                        │                       │
    │ POST /api/contact (JSON) │                        │                       │
    │─────────────────────────────────────────────────▶ │                       │
    │                                                    │ rate-limit (1/min/IP) │
    │                                                    │ validate (zod)        │
    │                                                    │ log {intent, hash(email)}
    │                                                    │─────────────────────▶ │ (stub v0.1)
    │                                                    │ 202 {accepted, rid}   │
    │                                                                             │
    │ 202 + inline toast "We'll reach out within 2 biz days"                       │
    │◀────────────────────────────────────────────────── │                       │
```

### 8.2 바이어 검색 (Federated 2 병원)

```
Buyer               Portal /search         BFF /api/search/*           search:8001          PG (central DB)
  │ /search             │                        │                            │                    │
  │────────────────────▶│                        │                            │                    │
  │ SearchApp render    │ GET /api/search/facets │                            │                    │
  │                     │───────────────────────▶│ POST /v1/search/studies    │                    │
  │                     │                        │ { include_facets:true,     │                    │
  │                     │                        │   limit:0 }                │                    │
  │                     │                        │───────────────────────────▶│                    │
  │                     │                        │                            │ query filters+GROUP │
  │                     │                        │                            │───────────────────▶│
  │                     │                        │                            │◀────────────────── │
  │                     │                        │◀────────────────────────── │                    │
  │ facets + initial    │◀───────────────────────│                            │                    │
  │ results             │                        │                            │                    │
  │                     │                        │                            │                    │
  │ toggle facet CT+MR  │                        │                            │                    │
  │                     │ POST /api/search/studies                            │                    │
  │                     │───────────────────────▶│ POST /v1/search/studies    │                    │
  │                     │                        │ { modality:["CT","MR"],    │                    │
  │                     │                        │   min_hospitals:1,limit:25}│                    │
  │                     │                        │───────────────────────────▶│                    │
  │                     │                        │                            │ keyset + federated  │
  │                     │                        │                            │ GROUP BY hospital_opaque_id
  │                     │                        │                            │───────────────────▶│
  │                     │                        │◀────────────────────────── │◀────────────────── │
  │ render              │◀───────────────────────│                            │                    │
  │ "150 studies across │                        │                            │                    │
  │  2 hospitals"       │                        │                            │                    │
```

### 8.3 병원 운영자 로그인 → audit-chain-status 타일 렌더

```
Hospital Op       Portal /hospital        BFF /api/hospital/*        central-ingest:8000     PG
    │ /hospital signin     │                      │                          │                 │
    │─────────────────────▶│                      │                          │                 │
    │ POST session         │                      │                          │                 │
    │ {hospital_id=HOSP-001│                      │                          │                 │
    │  token=...}          │                      │                          │                 │
    │ cookie rv_hospital_s │                      │                          │                 │
    │◀──────────────────── │                      │                          │                 │
    │ GET /hospital        │                      │                          │                 │
    │─────────────────────▶│                      │                          │                 │
    │                      │ GET /api/hospital/me/stats                      │                 │
    │                      │─────────────────────▶│ GET /v1/hospital/me/stats│                 │
    │                      │ GET /api/hospital/me/audit-chain-status         │                 │
    │                      │─────────────────────▶│ GET /v1/hospital/me/audit-chain-status     │
    │                      │ GET /api/hospital/me/quota                      │                 │
    │                      │─────────────────────▶│ GET /v1/hospital/me/quota│                 │
    │                      │                      │                          │ query audit_anchor
    │                      │                      │                          │ WHERE hospital_pk=1
    │                      │                      │                          │────────────────▶│
    │                      │                      │                          │◀───────────────│
    │                      │                      │◀──────────────────────── │                 │
    │ 9 타일 + 감사 프리뷰│◀──────────────────── │                          │                 │
```

---

## 9. 의존성

### 9.1 상위 모듈

- 없음 (RadiVault 최상위 포털 레이어).

### 9.2 하위 모듈·서비스

- **search** (metadata-index) — `POST /v1/search/studies`, `GET /v1/search/studies/{uid}`, `GET /v1/search/hospitals`, `GET /v1/search/facets` (또는 wrapper). **블로커 FR-INF-1 해소 필수**.
- **central-ingest** — 기존 4 엔드포인트 (stats / gateway-health / orders / audit) + 신규 2 엔드포인트 (audit-chain-status / quota, FR-INF-6 / FR-INF-7).
- **order-fulfillment** — 주문 5-phase, hospital orders 마스킹, downloads presigned. 수정 없음.
- **gateway-agent** — audit anchor 체인을 중앙에 지속 전송 (기존 동작).

### 9.3 외부 서비스

- **TCIA** seed (CC-BY, 공개) — 홈페이지 Metrics 라벨 + 바이어 포털 데모 data.
- **SMTP / 이메일 릴레이** (FR-INF-5) — §Q5 확정 후. v0.1 은 stdout stub 허용.

### 9.4 선행 기능 (이미 완료)

- `dev-spec-buyer-portal-demo` v0.1 + QA PASS (Session 10).
- `dev-spec-metadata-index` v0.1 + QA PASS.
- `dev-spec-central-ingest` v0.1 + QA PASS.
- `dev-spec-order-fulfillment` v0.1 + QA PASS.
- `scripts/demo_seed/*` TCIA 시드 파이프라인 (Session 13~16).

### 9.5 기술 스택 — 본 dev-spec 에서 **확정** 하는 것

| 영역 | 확정 | 근거 |
|---|---|---|
| 웹 프론트엔드 | **Next.js 14 App Router + TypeScript** | `dev-spec-buyer-portal-demo §14 Annex C` 와 동일 재확정. ARCHITECTURE.md §9 "웹 프론트엔드 TBD" 해소. |
| CSS | **Tailwind CSS + shadcn/ui 선택적** | 기존 portal 구현 재활용. |
| 상태 / 쿼리 | **@tanstack/react-query ^5** | 기존 설치. |
| 세션 | **iron-session v8 (HttpOnly + Secure + SameSite=Lax)** | 기존 구현. |
| i18n | **순수 dictionary (EN / KR)** v0.1, `next-intl` 은 v0.1.1 | §Q9 |
| 차트 | **Recharts 또는 순수 SVG sparkline** | FR-HO-4 |
| 폰트 | **Inter (EN) · Pretendard Variable (KR)** self-hosted | design-spec-buyer-portal-demo §2 승계 |
| 테스트 | **Vitest + Playwright** | 기존 파이프라인 |

**ARCHITECTURE.md §9 갱신 제안**: Kyle 승인 시 `"웹 프론트엔드 | React/Next.js/Vue/Svelte 등"` 행을 `"웹 프론트엔드 | Next.js 14 App Router + TypeScript (확정: dev-spec-portal-redesign §9.5)"` 로 갱신.

**PRD 갱신 제안**: `docs/prd.md` 에 "홈페이지 / 트랙 2 / 트랙 3" 명시 필요. 현재 PRD 는 Phase 2 Buyer Portal 로만 참조 — v0.1.5 로 분리 승격 권고.

---

## 10. 수용 기준 (Acceptance Criteria)

> `@qa` 는 이 체크리스트를 기준으로 검수. binary-testable 로 작성.
> 기존 `verify.py` V-1..V-8 전부 PASS 유지 + 신설 V-9..V-12 충족 필요.

### 10.1 verify.py 기존 유지

- [ ] **V-1..V-8 전부 PASS** 유지 (tcia-seed 검수 기준).

### 10.2 신설 verify 체크 (portal-redesign 전용)

- [ ] **V-9 buyer login roundtrip**: `.buyer_key.local.txt` 로 `POST /v1/search/studies` (limit=1) → 200 + `items` 배열 존재 (FR-INF-4).
- [ ] **V-10 federated signal**: `POST /v1/search/studies {limit:50, include_facets:true}` 응답의 `items` 가 **2 종 이상 `hospital_opaque_id`** 포함 (HOSP-001 + HOSP-002 시드 확인).
- [ ] **V-11 hospital audit-chain-status**: HOSP-001 토큰으로 `GET /v1/hospital/me/audit-chain-status` → 200 + `chain_continuous: true` + `last_anchor_age_seconds < 3600`.
- [ ] **V-12 hospital quota**: HOSP-001 토큰으로 `GET /v1/hospital/me/quota` → 200 + `ruleset_version` · `salt_version` 비어있지 않음.

### 10.3 홈페이지 AC (FR-HP-*)

- [ ] **AC-HP-1** `GET /` 응답 200, Lighthouse Performance ≥ 85 (mobile) / ≥ 95 (desktop), LCP p75 < 2.5 s.
- [ ] **AC-HP-2** `GET /ko` 한국어 완전 번역 렌더 (Hero / Trust bar / How it works / Footer 법적 블록). `grep -r 'TBD\|\[X\]M' .next/` 프로덕션 빌드에서 0 건.
- [ ] **AC-HP-3** Trust bar 4 칼럼에 "certified" / "guaranteed" / "HIPAA-compliant" 단정어 0 건. `FR-NFR-7` grep check PASS.
- [ ] **AC-HP-4** Hero 우측 스크린샷이 실 `/search` 화면 캡처. 해당 이미지 EXIF / 메타데이터에 실명·파일럿 병원 이름 0 건.
- [ ] **AC-HP-5** Korean 풋터 법적 블록에 대표자 / 사업자등록 / 주소 / 고객센터 / 개인정보처리방침 링크 5 개 항목 모두 존재 (값은 §Q8 TBD 허용하되 빌드 시 env 로 주입).
- [ ] **AC-HP-6** Language toggle 클릭 시 쿠키 `radivault_locale` 설정, 다음 방문 시 해당 locale 자동 선택.
- [ ] **AC-HP-7** `POST /api/contact` 422 (validation) / 429 (rate-limit) / 202 (성공) 3 경로 모두 응답 envelope 준수.
- [ ] **AC-HP-8** `/robots.txt` 존재 + `/portal` / `/hospital` path `Disallow` 포함. `/sitemap.xml` 에 `/` `/ko` `/contact` `/docs` `/trust-center` 5 URL 포함.
- [ ] **AC-HP-9** JSON-LD Organization schema `<script type="application/ld+json">` 렌더 (SEO).
- [ ] **AC-HP-10** hreflang 태그 `<link rel="alternate" hreflang="en" href="https://radivault.io/">` + `"ko"` 존재.

### 10.4 바이어 포털 AC (FR-BP-*)

- [ ] **AC-BP-1** `/signin` → 로그인 → `/` 가 **대시보드 5 타일** 렌더 (기존 /search 리디렉트 동작이 **대시보드로** 전환). FR-BP-20.
- [ ] **AC-BP-2** `/search` 3-pane 레이아웃 (facet 280 px / results flex / cohort 320 px). Playwright viewport 1280 + 1920 에서 레이아웃 assert.
- [ ] **AC-BP-3** 검색 결과 row 가 7 개 이상 필드 렌더 (check + modality + body_part + age + sex + n_instances + size + year + hospital). `data-testid="search-row-{uid}"` + per-cell testid.
- [ ] **AC-BP-4** 검색 sticky 배지 `From 2 hospitals` 가 HOSP-001 + HOSP-002 시드에서 정확히 "2" 표시 (server-side COUNT).
- [ ] **AC-BP-5** `min_hospitals=2` 필터 적용 시 결과 변화 (N 병원 이상 study 만). FR-BP-7 + metadata-index 스키마.
- [ ] **AC-BP-6** Modality 색상 7 종 CSS 변수 `--color-modality-ct` 등이 DevTools Computed 에서 해시 값으로 존재. MG #9d174d 승계.
- [ ] **AC-BP-7** `/studies/[id]` 메타데이터 + series 리스트 렌더. hospital_opaque_id 배지 표시. Viewer placeholder `data-testid="viewer-stub"` 존재.
- [ ] **AC-BP-8** `/orders/new` 가 선택된 N study 테이블 + From N hospitals pie + DUA checkbox + Submit 렌더. Submit 이 `POST /api/orders` 로 `allowed_hospitals` scope 포함.
- [ ] **AC-BP-9** `/orders/[id]` 5-phase stepper + "View timeline" drawer 에서 12-state FSM + download_event 표시.
- [ ] **AC-BP-10** `/account` API Keys 리스트가 `rv_live_****...` 마스킹 포맷 + revoke 버튼 렌더.
- [ ] **AC-BP-11** Saved searches 최근 5 건이 localStorage `radivault_recent_searches` 에 저장 + 대시보드 타일 2 에 렌더.
- [ ] **AC-BP-12** Empty / Error / Loading 상태 3 종 전부 스크린샷 가능 (Playwright). design-spec-buyer-portal-demo §7 승계.
- [ ] **AC-BP-13** API bundle 에 `rv_live_*` 평문 키 0 건 (`grep -r 'rv_live_' .next/static/` 0 건).
- [ ] **AC-BP-14** BFF 페이로드가 `limit` 필드 사용 (기존 `page_size` 제거). Playwright request interception assert.

### 10.5 병원 포털 AC (FR-HO-*)

- [ ] **AC-HO-1** `/hospital` 9 타일 렌더. 각 타일 `data-testid="tile-ho{1..9}-*"` 존재.
- [ ] **AC-HO-2** HOSP-001 로그인 세션에서 HOSP-002 데이터 0 건 유출. Playwright 크로스 hospital 시나리오 테스트.
- [ ] **AC-HO-3** Audit chain 타일이 `last_anchor_age_seconds` < 3600 && `chain_continuous: true` 시 green, 외 red.
- [ ] **AC-HO-4** Quota 타일이 daily / monthly / concurrent / ruleset / salt 5 필드 전부 렌더.
- [ ] **AC-HO-5** Audit 프리뷰 섹션 (하단) 에 최근 20 이벤트 렌더. hash prefix 만 (PHI 0 건).
- [ ] **AC-HO-6** 한국어 라벨 길이 < 5 자 (주요 메뉴).
- [ ] **AC-HO-7** KRW 표시가 `₩ 18,400,000` 풀스펠 포맷 (리서치 §4.4).
- [ ] **AC-HO-8** 한국 풋터 법적 블록 5 항목 모두 렌더.
- [ ] **AC-HO-9** Korea heatmap 에 병원 실명 0 건. choropleth 또는 2 dot 만.
- [ ] **AC-HO-10** 플로팅 "1:1 문의" 버튼 mailto 또는 `/contact?intent=hospital` 링크.

### 10.6 인프라·부트스트랩 AC (FR-INF-*)

- [ ] **AC-INF-1** Alembic `alembic upgrade head` 로 `buyer` / `buyer_api_key` / `search_audit` 3 테이블 생성 확인 (psql `\dt`).
- [ ] **AC-INF-2** `inject_all.sh` 가 STEP 0 에서 Alembic upgrade 자동 실행 (또는 idempotent skip).
- [ ] **AC-INF-3** `seed_buyer.py` 성공 실행 후 `.buyer_key.local.txt` (0600) 생성 + smoke roundtrip PASS.
- [ ] **AC-INF-4** `verify.py` V-9 `.buyer_key.local.txt` + `POST /v1/search/studies` 왕복 200 + items 존재.
- [ ] **AC-INF-5** central-ingest `GET /v1/hospital/me/audit-chain-status` 엔드포인트 200 + 스키마 FR-INF-6 준수.
- [ ] **AC-INF-6** central-ingest `GET /v1/hospital/me/quota` 엔드포인트 200 + 스키마 FR-INF-7 준수.
- [ ] **AC-INF-7** 기존 AC 회귀 0 건 — qa-report-buyer-portal-demo / qa-report-metadata-index / qa-report-central-ingest / qa-report-order-fulfillment 전건 재실행 PASS.

### 10.7 공유·비기능 AC (FR-SH-* / NFR)

- [ ] **AC-SH-1** `<ComplianceBadge>` 컴포넌트 4 variant 렌더 + "in preparation" / "aligned" 어투 고정.
- [ ] **AC-SH-2** CI lint `grep -ri 'certified\|guaranteed\|HIPAA-compliant' web/portal/src/` 결과 0 건.
- [ ] **AC-SH-3** TCIA CC-BY attribution 문구가 홈페이지 Metrics 섹션 + 바이어 포털 footer 2 곳에 존재.
- [ ] **AC-SH-4** Playwright e2e 시나리오 3 종 (기존) + 신규 3 종 (homepage EN / homepage KR / 9-tile hospital) 총 6 시나리오 PASS.
- [ ] **AC-SH-5** Lighthouse Accessibility ≥ 95 (홈페이지 + Buyer + Hospital 각각).
- [ ] **AC-SH-6** `next build` 22 routes → 예상 신규 33 routes (+ homepage 3 + account + studies/[id] + orders/new + audit stub + settings stub + contact + trust-center + docs + api/contact + api/search/studies/[id] + api/hospitals + api/hospital/me/audit-chain-status + api/hospital/me/quota) 모두 빌드 성공.
- [ ] **AC-SH-7** CSP 헤더가 production 에서 `script-src 'self' 'unsafe-inline'` (dev-only `'unsafe-eval'` 예외는 `NODE_ENV !== 'production'` 조건). design-spec-buyer-portal-demo FR-X-5 승계.

---

## 11. 법적·보안 고려

> 본 섹션은 `@planner` 가이드 §6 의 의무. PHI·PII·국외이전·표시광고법·CC-BY attribution 등 법적 표면을 명시.

### 11.1 PHI · PII 처리

- 홈페이지·포털 어디에서도 **실 환자 PHI 렌더 0 건**. 모든 UI 가 pseudo_uid / hospital_opaque_id / masked order id 만 사용 (FR-SH-5).
- 데모 데이터는 TCIA CC-BY 공개 datasets 만. 파일럿 병원 실 환자 데이터는 v0.1 미사용.
- CI grep assertion: `grep -ri 'PatientName\|PatientID\|BirthDate' web/portal/src/` 0 건.

### 11.2 개인정보보호법 (PIPA) §28-8

- 홈페이지 `/ko` §Security & Compliance 섹션에 PIPA §28-8 조문 요약. "2026년 개정 CEO 개인책임" 인용은 법무 자문 후 §L-2.
- 컴플라이언스 어투는 "aligned with" / "designed to support" 보수 표현. "certified" / "guaranteed" 금지 (FR-NFR-7 lint).

### 11.3 HIPAA (Safe Harbor + Expert Determination)

- "HIPAA compliant" 어구 금지. "HIPAA-aligned de-identification (Safe Harbor + Expert Determination)" 만 사용. 리서치 §2.2.

### 11.4 표시광고법 (한국)

- 경쟁사 비교 (Segmed · Gradient · Truveta 등) 금지 — 홈페이지에는 포지셔닝 quadrant 넣지 않음. `docs/marketing/competitive-positioning-buyer-en.md` 의 비교는 login-gated leave-behind 전용.
- "국내 1위" · "유일한 플랫폼" 단정 금지.

### 11.5 TCIA CC-BY attribution

- `FR-SH-4` 의 attribution 문구가 모든 시드 데이터 노출 지점에 반드시 존재. 빠지면 라이선스 위반.

### 11.6 병원 로고 사용

- 파일럿 확정 시 MSA 에 로고 사용 허락 조항 포함 필요 (리서치 §8.2). v0.1 에서는 로고 0 건.

### 11.7 국외이전 차단

- 바이어 포털에서 "데이터 다운로드" 플로우는 기존 order-fulfillment 의 presigned URL 을 그대로 사용. anonymization_flag 게이트는 central-ingest 측 유지.

### 11.8 요약 리스트 (Kyle 법무 자문 필요)

| # | 항목 | 위치 |
|---|---|---|
| L-1 | 병원·환자·구매자 실명·로고 노출 0 건 assertion | 모든 UI |
| L-2 | PIPA §28-8 + 2026 CEO 개인책임 인용 법리 정확성 | 홈페이지 §Security |
| L-3 | "in preparation" 어투 의 법적 경계 (SOC 2 / ISO 27001) | Trust bar |
| L-4 | TCIA CC-BY attribution 문구 완전성 | Metrics + footer |
| L-5 | 사업자등록·대표자·주소·전화 공개 의무 (전자상거래법) | 한국어 footer |
| L-6 | 경쟁사 비교 표현 홈페이지 사용 금지 재확인 (공정거래법) | 모든 공개 페이지 |
| L-7 | contact form 개인정보 수집 동의 문구 + 보존 기간 | /contact 폼 |
| L-8 | 데이터 처리 위탁 (search / central-ingest 등) 내부 위탁 계약 범위 | 병원 MSA |

---

## 12. 시퀀스·플로우 (계속) — 데모 전용

§8 에서 주요 3 개 이미 다룸. §9 Demo Script 는 `docs/specs/demo-script-radivault.md` v0.2 를 그대로 승계. 본 dev-spec 은 다음 추가 사항만:

- **홈페이지 → 바이어 포털 전환 씬 (Scene 2.5 신설 권고)**: 대표 17분 스토리보드 A 에서 "공개 홈페이지를 30 초 보여주고 → 로그인" 단계 추가 (§Q11). Braided 구조에서 자연.
- **데모 전환 문법 shortcut**: 기존 `Ctrl+1..7` 에 추가 `Ctrl+0` = 홈페이지 (EN/KR 토글 데모).

---

## 13. 의존성·마이그레이션 계획

### 13.1 롤아웃 순서 (D-14 → D-day)

| 단계 | 범위 | 일정 | 책임자 |
|---|---|---|---|
| P0 (블로커) | FR-INF-1..4 (buyer 테이블 + Alembic + seed_buyer + verify V-9) | D-14 ~ D-10 | @developer |
| P1 (홈페이지) | FR-HP-1..13 | D-10 ~ D-7 | @developer + @designer |
| P2 (바이어 포털) | FR-BP-1..20 | D-10 ~ D-5 (병렬 P1) | @developer + @designer |
| P3 (병원 포털) | FR-HO-1..15 + FR-INF-6/7 | D-7 ~ D-3 | @developer |
| P4 (shared / NFR / QA) | FR-SH-*, NFR, AC 전수 | D-5 ~ D-1 | @qa |
| P5 (리허설) | R-1..R-9 (demo-script v0.2) | D-3 ~ D-1 | Kyle |

### 13.2 롤백 계획

- 각 P 단계는 git revert 가능한 단위. claude 브랜치 상에서만.
- 블로커 (FR-INF-1) 롤백 시: `DROP TABLE buyer, buyer_api_key, search_audit CASCADE` (Alembic `downgrade -1`). 이 경우 search 서비스 기동 불가 상태로 복귀.
- 홈페이지 롤백: `/` 라우트를 바이어 포털 `/signin` redirect 로 복구 (기존 동작).
- 9 타일 → 6 타일 롤백: HospitalDashboard.tsx git revert.

### 13.3 데이터 마이그레이션

- FR-INF-1 의 3 테이블 생성은 **destructive 0 건** (신규 테이블만). 기존 study / order / audit_* 테이블 무수정.
- FR-INF-6 / 7 의 central-ingest 엔드포인트는 **read-only** (기존 audit_anchor / study 테이블 SELECT).

---

## 14. 리스크·미해결 질문 (Open Questions)

### 14.1 Kyle 결정 필요 (긴급, D-10 이내)

- **Q1** (도메인 구조): `radivault.io/{portal,hospital}` 단일 도메인 sub-path vs `portal.radivault.io` / `hospital.radivault.io` 분리. **권고: 단일 도메인 sub-path 로 v0.1, 도메인 분리는 v0.2**. 이유: DNS · SSL · 쿠키 scope 복잡도 관리.
- **Q2** (바이어 포털 브랜드명): `RadiVault Marketplace` vs `RadiVault Atlas` vs `RadiVault Data Exchange`. **권고: Marketplace** (리서치 §3.4 "Order = Marketplace 멘탈 모델" + 타사 충돌 최소).
- **Q3** (Pricing 가시성): 홈페이지 `Pricing` 메뉴 존재 여부. **권고: 메뉴 있음 + 클릭 시 `Contact for pricing` 폼 (Segmed 패턴)**. 리서치 §2.8.
- **Q4** (Hero headline 최종): A (PRD tagline) / B (48h SLA) / C (PIPA 법적) / D (파트너십). **권고: A 고정** (리서치 §2.1).
- **Q5** (Contact relay): SMTP (SES / SendGrid) vs Zendesk vs Slack webhook. **권고: v0.1 stdout log + mailto, 실 릴레이는 v0.1.1**.
- **Q6** (Investor / Hospital partnership 박스): 홈페이지 노출 여부. **권고: noon — `For investors →` 텍스트 링크만 (박스 없이)**.
- **Q7** (Korea heatmap 좌표): HOSP-001 / HOSP-002 의 실 지역 매핑 (서울 / 경기 / 부산 ...). **권고: 서울 + 경기 2 점 dot + opt-out 까지 실명 숨김**.
- **Q8** (Korean footer 법적 블록 값): 대표자 / 사업자등록번호 / 주소 / 고객센터 전화. **권고: Delaware 법인 설립 전까지는 한국 법인(R&D 법인 또는 개인사업자) 정보. 없으면 "설립 준비 중" 플레이스홀더 + `NODE_ENV=production` 빌드 fail**.
- **Q9** (i18n 도구): `next-intl` (3.x) vs 순수 dictionary vs `react-i18next`. **권고: v0.1 은 순수 dictionary 2 file (en.json / ko.json), v0.1.1 은 next-intl 도입 검토**.
- **Q10** (병원 SSO 이관): 파일럿 시점. v0.1 은 토큰 기반 (기존 `dev-spec-buyer-portal-demo` D-5 계약). SSO (SAML / OIDC) 는 v0.2.
- **Q11** (데모 스토리보드 Scene 2.5): 홈페이지 30 초 씬 추가 여부. **권고: yes — 투자자 모자 대상**.

### 14.2 법무 자문 flag (Kyle)

- **L-1** ~ **L-8** (§11.8) 전건 법무 확인.
- 특히 **L-5 사업자등록** 공개 의무가 Delaware 법인 설립 전까지 한국법인만으로 충족되는지.

### 14.3 아키텍처·PRD 갱신 필요

- **A-1** `ARCHITECTURE.md §9` "웹 프론트엔드 TBD" → "Next.js 14 확정" 갱신 PR 필요 (Kyle 승인).
- **A-2** `docs/prd.md §4.3` "구매자 포털 Phase 2" → "v0.1.5 출시 (홈페이지 + 바이어 + 병원)" 분리 승격 PR 필요.

### 14.4 기술 리스크

- **R-1** (FR-INF-1 블로커): Alembic migration 을 search repo 에 추가 시 central repo 와 마이그레이션 순서 꼬임. 해결: `inject_all.sh` STEP 0 에서 둘 다 upgrade head.
- **R-2** (기존 `SearchApp.tsx` 의 `page_size` 버그): 현재 구현이 잘못된 필드명을 쓰고 있음에도 테스트는 통과 (Vitest 의 mock 이 같은 잘못된 필드를 사용). 실 API 에서 `extra="forbid"` 로 400 반환. FR-INF-8 + FR-INF-9 로 동시 수정 필수.
- **R-3** (CEO 미팅 D-14 타임라인): 본 dev-spec 은 기존 `dev-spec-buyer-portal-demo` 대비 **확장** 이지 전면 교체 아님. 15 영업일 schedule 초과 위험. Mitigation: Homepage 만이라도 P1 우선 완료.
- **R-4** (2 병원 Federated 시그널): 현재 시드 data 가 HOSP-001 과 HOSP-002 에 **동일 modality / body_part 로 겹치는 study** 가 있어야 "From 2 hospitals" 값이 의미 있음. verify.py V-10 이 이를 assert.

### 14.5 디자인·UX 리스크

- **D-1** (홈페이지 첫 스크린샷 품질): 리서치 §2.6 권고가 "실 UI 스크린샷" 인데 demo seed data 가 충분히 다양해야 설득력 있음. Canned JSON 10 종 (Session 12) 활용.
- **D-2** (이중 언어 톤 불일치): EN / KR 두 언어가 같은 Hero 에서 동일 톤을 유지하기 어려움. design-spec 에서 tone guidelines 확정 필요.

---

## 15. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-25 | @planner (Claude Opus 4.7) | 최초 작성. 리서치 §0·§2·§3·§4·§6·§7·§8 전면 인용. 4 트랙 (홈페이지 FR-HP / 바이어 FR-BP / 병원 FR-HO / 인프라 FR-INF) + 공유 FR-SH. 58 FR + 44 AC. 기존 dev-spec-buyer-portal-demo 위에 얹는 확장. CEO 미팅 D-14 타겟. |

---

### NEXT_STEP
- **완료 산출물**: `/Users/yonghyuk/Radivault/docs/specs/dev-spec-portal-redesign.md` (v0.1 Draft)
- **제안 다음 단계**:
  - 먼저 **@developer** — FR-INF-1..4 (P0 블로커) 착수. 이것 없으면 나머지 데모 불가능.
  - 병렬 **@designer** — `design-spec-portal-redesign.md` 작성 — 홈페이지 ASCII 와이어 (Hero · Trust · How it works · Metrics · Security · Footer 2 variant) + 바이어 포털 리디자인 델타 (대시보드 5 타일 · Study detail · /orders/new 풀페이지 · Account) + 병원 포털 9 타일.
  - 병렬 **@marketer** — 홈페이지 EN / KR 카피 초안 (Hero subhead · Trust bar · Value props · Security 섹션).
- **아키텍처 영향**: `ARCHITECTURE.md §9` 갱신 필요 (Kyle 승인 대기). Next.js 14 확정 항목.
- **PRD 영향**: `docs/prd.md §4.3` 갱신 필요 (Kyle 승인 대기). v0.1.5 분리 승격.
- **Kyle 결정 필요 사항**:
  1. Q1 도메인 구조 (권고 단일 sub-path)
  2. Q2 바이어 포털 브랜드명 (권고 Marketplace)
  3. Q3 Pricing 메뉴 여부 (권고 yes + contact form)
  4. Q4 Hero headline (권고 A)
  5. Q5 Contact relay (권고 v0.1 stdout)
  6. Q6 Investor 박스 (권고 텍스트 링크만)
  7. Q7 Korea heatmap 좌표 (권고 서울+경기 2점)
  8. Q8 한국 법적 블록 (권고 Delaware 전 한국 법인 또는 설립 준비 중 stub)
  9. Q9 i18n 도구 (권고 v0.1 순수 dict)
  10. Q10 병원 SSO (권고 v0.2)
  11. Q11 데모 Scene 2.5 (권고 추가)
  12. L-1..L-8 법무 자문 전건.
