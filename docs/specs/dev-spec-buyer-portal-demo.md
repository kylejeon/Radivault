# 개발지시서 — Buyer Portal + Hospital Dashboard + Demo Kit v0.1 MVP

> **Status**: Draft v0.1 · **Feature slug**: `buyer-portal-demo` · **Last updated**: 2026-04-24
> **작성자**: @planner (Claude Opus 4.7)
> **근거**:
> - [리서치 — 데모·피치 레퍼런스 (Segmed/Gradient/Truveta/Rhino/Flywheel 5사, dual-audience 구조, 스토리보드 A/B/C, 금기 23건, Kyle 결정 30+건)](../research/demo-pitch-references-radivault.md) — **primary upstream for demo scenes**
> - [리서치 — Buyer Portal UX Competitive (Gen3 3-pane, must-have §10, DICOM viewer exclusion §11, Hospital Dashboard 6-tile §12)](../research/buyer-portal-ux-competitive.md) — **primary upstream for portal screens**
> - [리서치 — K-MedData 요약 (PIPA §28-8, 시장)](../research/k-meddata-research-summary.md)
> - [PRD §4.2, §4.3, §4.4](../prd.md)
> - [ARCHITECTURE §4 Zone 2, §5 Zone 3](../ARCHITECTURE.md)
> - [dev-spec-metadata-index (7 buyer-facing endpoints, buyer_api_key, scope_json, envelope 계승)](./dev-spec-metadata-index.md)
> - [design-spec-metadata-index §2 envelope, §5 error taxonomy](./design-spec-metadata-index.md)
> - [dev-spec-order-fulfillment (FSM 12-state, presigned URL, download audit, agreement_hash)](./dev-spec-order-fulfillment.md)
> - [design-spec-order-fulfillment §5 error taxonomy](./design-spec-order-fulfillment.md)
> - [dev-spec-central-ingest §6 데이터 모델 (study, hospital_pseudo)](./dev-spec-central-ingest.md)
> - [dev-spec-gateway-agent §8 운영자 status UX](./dev-spec-gateway-agent.md)
> - `docs/marketing/one-pager-buyer-global-en.md`, `docs/marketing/api-quickstart-buyer-en.md`, `docs/marketing/order-flow-quickstart-buyer-en.md`, `docs/marketing/competitive-positioning-buyer-en.md`, `docs/marketing/proposal-summary-hospital-ko.md`, `docs/marketing/onboarding-hospital-it-admin-ko.md` — 톤·용어·포지셔닝 앵커
> - `src/radivault_search/`, `src/radivault_fulfillment/`, `src/radivault_central/`, `src/radivault_gateway/` — 실 코드 기준선

---

## §0 Scope and out-of-scope

### 0.1 포함 (In-scope — v0.1 MVP)

본 dev-spec 은 **3개 상호의존 컴포넌트 + 시연 스크립트** 를 단일 feature slug `buyer-portal-demo` 로 통합 정의한다. 세 요소는 동일 레포(Next.js monorepo) 에서 동일 세션 동안 구현·리허설되기 때문에 분리 불가.

1. **Buyer Portal Web UI (영어)** — 신규 Next.js 14 App Router 서비스. 도메인 권고 `portal.radivault.io` (별칭 `buyer.radivault.io` 예약). 화면 8종 (§3.A). 기존 metadata-index + order-fulfillment API 에 **BFF(Next.js route handlers) 경유 직접 호출**. 세션은 Buyer API key → HttpOnly secure cookie 교환.
2. **Hospital Dashboard (한국어)** — 같은 Next.js 앱의 subpath `/hospital/*`. 병원 경영진 1 페이지 6-tile 레이아웃 (§3.B). 별도 auth (Gateway ID + Hospital admin token, v0.1 config 파일 기반 stub).
3. **Demo Seed Pipeline** — 샘플 DICOM 재현성 있는 주입 스크립트. TCIA 공개 300~500 study, 대표 modality 3~5 (CT Chest, MR Brain, CR Chest, MG, CT Spine 권장). Orthanc → Gateway (실 코드) → Central ingest → Metadata index 전체 파이프라인 자동 실행. 리셋 스크립트 포함 (§8).
4. **Demo Script Package** — `docs/specs/demo-script-radivault.md` 17분 장면별 스크립트 (스토리보드 변형 A "Revenue Loop Proof" 채택). 장면별 프레젠터 대사(한영)·화면 조작 절차·예상 소요시간·실패 시 리커버리·Canned output 경로 (§9).

본 기능은 **데모(1인 대표님, 투자자+병원 경영진 겸임)** 가 1차 목표이며, v0.1.5 경로를 통해 동일 코드가 **실제 파일럿 병원 2곳 · 실제 파일럿 버이어 1~2사** 에도 재사용될 수 있도록 설계한다.

### 0.2 제외 (Out-of-scope — v0.1.1 / v0.2 이상)

하지 않을 것을 명시해 혼동을 차단한다.

1. **DICOM 인라인 뷰어 (OHIF / Cornerstone.js / 서드파티 SaaS)** — Zone 2 buyer-facing DICOMweb gateway 미구축 + 프리뷰 공개 법률 결정 미완 (리서치 `buyer-portal-ux-competitive.md §11`). v0.2 "Sample Dataset" 기능과 함께 별 dev-spec 으로 이관. v0.1 데모에서는 "구매 후 로컬 viewer(OHIF desktop, Horos)로 열어본 GIF" 1 장으로 대체.
2. **실 결제 / Stripe 통합** — billing v0.2 옵션 G dev-spec. v0.1 포털은 `total_estimated_usd` 노출 정책만 확정하고 결제 버튼은 "Confirm order (v0.1 billing stub — no charge)" 로 명시.
3. **가격 비마스킹 표시** — v0.1 포털은 `total_estimated_usd` 를 **마스킹**(`—` 또는 "Contact for pricing") 한다. 주문 확정 응답 본문에만 숫자 노출. 근거: `one-pager-buyer-global-en.md §8` "Pricing transparency in the procurement call" + 리서치 `buyer-portal-ux-competitive.md §6.2` Kyle 결정 항목 §13.1-4.
4. **Saved cohorts / Saved searches / Advanced search modal** — metadata-index v0.1.1 backlog.
5. **한국어 i18n (Buyer Portal 부분)** — v0.1 Buyer 영어 전용. Hospital Dashboard 만 한국어. 이유: 구매자는 글로벌 AI 기업, 병원 경영진은 한국. v0.1.1 에 Buyer 한국어 번역.
6. **반응형 모바일 / 태블릿** — v0.1 데스크톱 1280px+ 전용. 데모 시 프로젝터·27인치 모니터 해상도 가정.
7. **다크 모드** — v0.1 라이트만. Kyle 결정 §11-Q-UI-1 에서 시간 허용 시 포함 재검토.
8. **이메일 · webhook 알림** — order-fulfillment v0.1.1 backlog. 포털은 폴링 + in-app toast 로 대체.
9. **Team workspace · multi-user seats** — v0.1 단일 Buyer API key 세션만.
10. **API key 신규 발급 UI** — SRE CLI (`search-admin key issue`) 만. 포털은 **기존 키 마스킹 표시 + Revoke 링크(SRE 이관)** 만 제공.
11. **Help center · Intercom 위젯 · in-app tour** — v0.1 제외. 각 복잡 필드 옆 shadcn HoverCard (?) 아이콘으로 link to docs 만.
12. **Hospital Dashboard 내 opt-out 관리 UI** — v0.1 은 "3 pending" 카운트만 읽기 전용 표시. 승인/거부 워크플로우는 v0.1.1 (metadata-index scope_json.exclude_hospitals 집행 구현 뒤).
13. **Hospital Dashboard 한국 지도 히트맵 인터랙션** — v0.1 은 정적 SVG + 1~2 포인트만. 드릴다운·확대·툴팁 v0.2.
14. **Service worker 기반 스트림 다운로드 / 브라우저 zip** — `order-fulfillment` 와 동일. 포털은 "Copy curl / Copy Python" 스니펫 + per-object presigned URL 링크만.
15. **Demo 자산 중 투자자 피치 덱 PPT 파일** — @marketer 담당. 본 dev-spec 은 **덱 placeholder 슬라이드 수·주제·시각 자산 위치**만 정의.
16. **실제 법률 자문 결론** — §6.2 법적 고려에서 flag 만 제시. 외부 변호사 결정 문서화는 Kyle 책임.

### 0.3 스코프 시간 목표

**2.5~3주** (구현 + QA + 리허설 + Kyle 승인). §13 Milestones 상세.

- 최소 투입: Dev 10일 + Design 3일 + QA 2일 + Rehearsal 2일 ≈ 17일 (3.4주) 하드.
- 권장: 2.5주 (12 영업일) 내 코드 프리즈 + 1주 리허설 버퍼.

---

## §1 Context

### 1.1 현재 상태 (as-of 2026-04-24)

RadiVault v0.1 누적 feature 5종이 `claude` 브랜치에 구현·검수 완료:

| Feature | 상태 | 노출 표면 |
|---|---|---|
| gateway-agent | PASS, 54 tests | CLI (`gateway-admin`), Docker, systemd. GUI 없음. |
| central-ingest | PASS, 67 tests | HTTP API (5 endpoints), `ingest-admin` CLI. GUI 없음. |
| metadata-index | PASS with minor, 69 tests | HTTP API (7 endpoints), `search-admin` CLI. GUI 없음. |
| de-id-pixel | PASS with minor, 143 gateway tests | Gateway 확장 (CLI + Docker Pixel image). GUI 없음. |
| order-fulfillment | PASS with minor, 84 tests | HTTP API (13 endpoints), `fulfillment-admin` CLI. GUI 없음. |

**Total**: 363 pytest passed, ruff clean, 5 Docker images (gateway, gateway-pixel, central, search, fulfillment), 9 마케팅 문서. **시각적 자산 0건**.

### 1.2 왜 이 기능이 필요한가

**직접 동기**: 2026-05~06 예정 대표님(투자자+병원 경영진 겸임) 1:1 미팅. 17분 안에 "제품이 돌아가고(live), 돈이 되고(revenue loop), 안전하다(anonymization + audit)" 를 증명해야 한다. 현재 API-only + CLI-only 상태로는 **시각적 설득력이 약함** — 리서치 `demo-pitch-references-radivault.md §2.6` 경쟁사 5사 공통 연출 패턴(플로우 다이어그램, live 제품 데모, 병원 로고 벽) 중 RadiVault 가 시각으로 내놓을 수 있는 건 아직 터미널뿐. Kyle 결정 옵션 D-1 (리서치 §9.4) 에 따라 **"Buyer Portal 최소 UI + Hospital Dashboard + 재현 가능한 데모 파이프라인"** 제작이 합의됐다.

**간접 동기**: 본 UI 레이어가 구축되면 (a) 파일럿 구매자 온보딩 시 `curl` 샘플 보다 클릭 가능한 데모가 설득력 있고, (b) 파일럿 병원 경영진 설득 시 "우리 병원이 보게 될 화면" 선제 제시 가능하며, (c) 투자자 후속 미팅에서 재사용 가능. 본 기능은 데모 이후에도 **v0.1.5 공식 릴리즈** 로 잔존한다.

### 1.3 데모 청중·목표 재확인

- **청중**: 1인. 대표님(투자자+병원 경영진 하이브리드). 한국어 네이티브.
- **시나리오**: 스토리보드 변형 A "Revenue Loop Proof" 17 분 + Q&A 3 분 (리서치 `demo-pitch-references-radivault.md §7.2`).
- **모드**: Live + Canned Hybrid. 라이브 경로 + 녹화 백업 둘 다 산출 (§4.3, §9).
- **자산 3종 합동 재생**: Buyer Portal 브라우저 창 + Hospital Dashboard 브라우저 창 + 터미널(CLI, 감사 체인 verify) 3 개가 장면별로 전면 전환된다. 각 장면에서 "지금 무엇을 보는가" 를 명시적으로 프레임 자막으로 띄운다 (§9.3).

### 1.4 데모 성공 기준 (측정 가능)

- **SC-1**: 데모 중 기술적 실패가 0건 (§4.3 런북 Trigger 없음) 또는, Trigger 발생 시 Canned 전환이 5초 이내 완료.
- **SC-2**: 대표님의 질문 중 90%+ 가 §6-Q&A 예상 20건 내에서 커버된다.
- **SC-3**: 데모 종료 시점 대표님이 "다음 단계 미팅"(IRB 심의 경로 논의 또는 시드 텀시트 요청) 을 먼저 제안하거나, RadiVault 측 CTA 에 긍정 응답한다.
- **SC-4**: PHI 의심 장면 0건. 출처 고지 미부착 데이터 0건.

### 1.5 비목표

- Buyer Portal 을 실 파일럿 구매자에게 즉시 판매하지 않는다 (v0.1 GA 는 QA PASS 후 Kyle 결정).
- Hospital Dashboard 를 실 파일럿 병원에 즉시 배포하지 않는다 (Gateway ID 위조 방지 CISO 리뷰 선행).
- 투자자 피치덱 PPT 원본 제작 (@marketer 담당).
- DICOM 뷰어 (§0.2-1).

---

## §2 User personas

본 feature 는 **단일 세션 안에 4 인물이 교차로 나타나는 특수 구조**. persona 마다 기대하는 화면·정보 밀도·언어가 다르다.

### 2.1 Persona P1 — Buyer Integrator ("Dana")

- **역할**: 글로벌 AI 영상진단 스타트업 ML 엔지니어.
- **언어**: 영어 (한국어 독해 불가 가정).
- **방문 목적**: 한국 다양성 데이터가 자사 모델 edge case 에 맞는지 확인.
- **세션 길이**: 첫 방문 10~20 분 (검색·필터·주문 1 건).
- **기대 수준**: Segmed/Gradient 수준의 Gen3-style 3-pane UX. 터미널 `curl` 을 클릭으로 대체하는 수준이면 만족.
- **주요 마찰점**: 가격 비노출(§0.2-3), 뷰어 부재(§0.2-1), API key 자체 발급 불가(§0.2-10).
- **마찰 완화**: 각 제한에 inline hint + link to docs/marketing/ (onepager, quickstart).
- **Buyer Portal 화면 A-1..A-8 전부 해당**.

### 2.2 Persona P2 — Hospital Executive ("Prof. Kim")

- **역할**: 한국 상급종합병원 원장 또는 기획실장 (대표님 본인 포함).
- **언어**: 한국어.
- **방문 목적**: "RadiVault 가 우리 병원을 태울 만한가" 평가. 이후 상시 대시보드처럼 원장실 디스플레이에 띄워 놓는 용도.
- **세션 길이**: 데모 중 2 분, 이후 주 1 회 5 분 수준 glance.
- **기대 수준**: 1-scroll 완결. 복잡 네비 금지. 숫자 대문짝 + 지도 + Gateway 상태.
- **주요 마찰점**: "이 숫자가 진짜인가" 의심, "이 플랫폼이 망하면?"
- **마찰 완화**: 각 숫자 옆 "last updated HH:MM" + Gateway online 초록 점 + 감사 이벤트 10 건 = **라이브 증거**.
- **Hospital Dashboard B-1..B-6 전부 해당**.

### 2.3 Persona P3 — Hospital IT / 전산실장

- **역할**: 병원 전산실 실무자. Gateway Agent 설치·운영 담당.
- **언어**: 한국어.
- **방문 목적**: Gateway 건강도, 최근 실패, 감사 체인 연속성.
- **세션 길이**: 문제 발생 시에만 (알림 수신 후 5~15 분).
- **기대 수준**: Gateway status tile 클릭 시 드로어 (v0.1.1 예정. v0.1 은 tile 에 수치만).
- **Hospital Dashboard B-4, B-6 주로 본다. v0.1 심층 드로어는 미포함** (§0.2 추가, `onboarding-hospital-it-admin-ko.md` 과 역할 분리 — 실 IT 운영은 onboarding 문서 + `gateway-admin` CLI 가 주).

### 2.4 Persona P4 — Internal Demo Operator (Kyle 또는 대리인)

- **역할**: 데모 진행자. 라이브 화면 조작 · Canned 전환 · 런북 대응.
- **언어**: 한영 병행.
- **방문 목적**: 17분 안에 7 장면 각각 성공시키기. 실패 시 5초 내 복구.
- **기대 수준**: 단축키 + 사전 로그인 세션 + Canned output 파일 모두 데스크탑 1 화면에 접근 가능.
- **전용 UX**: "Demo Operator Mode" — URL `?demoop=1` 쿼리 플래그 (쿠키 설정) 로 (a) Demo reset 버튼 (b) Canned output 오버레이 (c) Scene progress indicator 노출 (§3.D).

---

## §3 Screens inventory

### 3.A Buyer Portal screens (영어, 권한: Buyer API key)

| # | Screen ID | URL | 핵심 컴포넌트 | 데이터 소스 | 데모 장면 연결 |
|---|---|---|---|---|---|
| A-1 | Home / Hero | `/` (public) | Hero headline · tagline · "Sign in with API key" CTA · 3-tile proof (studies indexed · hospitals contributing · turnaround p95) | `GET /v1/search/facets` (public 서브셋) + 정적 placeholder | 장면 2 (아키텍처 후반) |
| A-2 | Sign-in | `/signin` | API key 입력 (masked) · "Paste rv_live_... key" · 에러 (`ERR_AUTH_FORMAT`, `ERR_AUTH_INVALID`) | BFF `POST /api/session` → metadata-index `GET /v1/search/facets` (키 검증) → cookie 설정 | (데모 오프스크린, 세션 pre-warmed) |
| A-3 | Search | `/search` | 3-pane: 좌 패싯 필터 (modality/body_part/sex/age_bucket/study_year/manufacturer/min_hospitals) · 중앙 결과 테이블 · 우 cohort sidebar | metadata-index `POST /v1/search/studies` + `GET /v1/search/facets` | 장면 4 시작 (구매자 검색) |
| A-4 | Study detail drawer | `/search?study={pseudo_study_uid}` (side drawer overlay) | 메타데이터 카드 · 시리즈 목록 (UID 8자 잘림) · "Add to cohort" CTA | metadata-index `GET /v1/search/studies/{pseudo_study_uid}` | 장면 4 중반 |
| A-5 | Review order modal | `/search` → "Review order" 버튼 | cohort summary · DUA 체크박스 · `agreement_hash` 자동 채움 · Idempotency-Key 자동 생성 · "Confirm order" CTA · 가격은 **마스킹** (`—`) | order-fulfillment `POST /v1/orders` | 장면 4 후반 |
| A-6 | Orders list | `/orders` | 주문 테이블: order_id(8자), state pill (5-phase), n_studies, created_at, ETA | order-fulfillment `GET /v1/orders` | 장면 5 시작 |
| A-7 | Order detail + tracker | `/orders/{order_id}` | 5-phase step tracker · 현재 phase highlight · ETA tooltip · "View details" 드로어(내부 12-state 타임라인) · "Refresh downloads" 버튼 | order-fulfillment `GET /v1/orders/{id}` | 장면 5 중반 |
| A-8 | Downloads | `/orders/{order_id}/downloads` | 만료 카운트다운 · 3-tab (Browser / curl / Python) · per-object row (filename · size · SHA-256 8자 잘림 · Download) · "Download all (.json manifest)" CTA | order-fulfillment `POST /v1/orders/{id}/download-urls` | 장면 5 후반 |
| A-9 | Account (profile dropdown 내부) | `/account` | API key 마스킹 · tier 표시 · "Contact support" | BFF에 캐시된 buyer context | 데모 미노출 (존재만 증명) |

**Shell (global)**: Top nav (Logo · Search · Orders · Downloads · Docs · Profile dropdown). Empty/Loading/Error 공통 컴포넌트 (§3.C).

### 3.B Hospital Dashboard screens (한국어, 권한: Hospital admin token)

단일 페이지 6-tile. URL `/hospital/{gateway_id}` (path param 으로 multi-hospital 대비, v0.1 은 단일 gateway 만).

| # | Tile ID | 제목 (한국어) | 핵심 지표 | 데이터 소스 | 데모 장면 |
|---|---|---|---|---|---|
| B-1 | Studies | **오늘 / 누적 제공 스터디** | 오늘 N 건 · 누적 NN,NNN | `GET /v1/hospital/me/stats` (§7 D-2 신규) | 장면 6 |
| B-2 | Revenue | **예상 수익 (시뮬레이션)** | ₩ YY,YYY 누계 · 월별 bar chart 12개월 · "시뮬레이션 — v0.2 정산 대기" 푸터 라벨 필수 | `GET /v1/hospital/me/stats` + 클라이언트 사이드 revenue share 공식 | 장면 6 |
| B-3 | Map | **기여 지역 (한국 지도 히트맵)** | 정적 SVG + 1~2 포인트 (데모용). 툴팁 1 라인 | 정적 설정 파일 (v0.1) | 장면 2~6 배경 |
| B-4 | Gateway | **Gateway 상태** | 초록 "● Online" / 노랑 "● Warning" / 빨강 "● Offline" + last sync HH:MM | central-ingest `GET /v1/hospital/me/gateway-health` (§7 D-2 일부) | 장면 3 |
| B-5 | Orders | **최근 주문 스트림** | 최근 10 주문 row: order_id 마스킹 · n_studies · state phase · delivered_at | order-fulfillment `GET /v1/hospital/me/orders?limit=10` (§7 D-2 일부) | 장면 5 |
| B-6 | Audit | **최근 감사 이벤트 10건** | append-only row: ts · event_type (ingest/upload/anchor/order_delivered) · hash 8자 (링크 X) | central-ingest `GET /v1/hospital/me/audit?limit=10` (§7 D-4 신규) | 장면 3 + 7 |

**Shell (hospital)**: 심플 헤더 (병원명 · 마지막 업데이트 · "로그아웃"). Sidebar 없음. 1-scroll 완결.

### 3.C 공통 상태 컴포넌트 (Buyer + Hospital 양쪽)

| 상태 | 컴포넌트 | 내용 | 근거 |
|---|---|---|---|
| Empty — no search results | `<EmptyState variant="no-results">` | "No studies match these filters. Try widening date range or removing `min_hospitals ≥ 3`." · "Clear all filters" CTA | 리서치 §9.4 |
| Empty — no orders yet | `<EmptyState variant="no-orders">` | "You haven't placed any orders. Start by searching for a cohort." · "Go to Search" CTA | 리서치 §9.4 |
| Empty — no downloads ready | `<EmptyState variant="no-downloads">` | "Your order is still preparing. Average ETA for 100 studies: 30 minutes. Refresh in 30s." · auto-refresh 타이머 | 리서치 §7.4 |
| Loading — initial | `<Skeleton />` (shadcn) · 행 수 10개 | 테이블·카드·차트 각각 전용 skeleton | shadcn/ui Skeleton |
| Loading — action (submit/refresh) | 버튼 disabled + spinner | `<Button loading />` 패턴 | — |
| Error — 4xx business | `<ErrorBanner code={ERR_*} />` | 에러 코드 + 한영 메시지 · "Copy request_id" · "Contact support" link | design-spec-metadata-index §5, design-spec-order-fulfillment §5 에러 taxonomy 재사용 (i18n JSON import) |
| Error — 5xx | `<ErrorBanner variant="system" />` | "Something went wrong. Please retry." + request_id · 자동 재시도 1회 | — |
| Error — network | `<ErrorBanner variant="offline" />` | "You're offline. Reconnect to continue." | browser navigator.onLine |

### 3.D Demo Operator Mode 오버레이

쿼리 `?demoop=1` (또는 쿠키 `demoop=1` ) 시:

- **OP-1**: 우상단 "Demo Mode" 배지 (빨강, 페이드).
- **OP-2**: 키보드 shortcut 표시 패널 (Ctrl-Shift-D toggle): 장면 번호 1~7 → 해당 URL 자동 이동 + pre-warmed 데이터 로드.
- **OP-3**: "Reset demo data" 버튼 — `POST /api/demoop/reset` (§8.4 리셋 스크립트 HTTP 래퍼).
- **OP-4**: "Canned output overlay" 토글 — 라이브 호출 실패 시 사전 캡처된 JSON 응답을 브라우저가 대신 렌더 (§4.3 런북 C-1).
- **OP-5**: Scene progress indicator — 좌하단 "Scene 3/7 — 8:00 / 17:00".

Demo Operator Mode 는 **반드시 localhost 또는 `?demoop=1` 쿼리 + 사전 설정된 `DEMOOP_TOKEN` 쿠키** 가 둘 다 있어야 활성. 실 파일럿 환경에서는 `DEMOOP_TOKEN` 미설정 시 완전 비활성.

---

## §4 Functional requirements

FR 번호는 컴포넌트별 prefix: **FR-A-n** (Buyer Portal), **FR-B-n** (Hospital Dashboard), **FR-S-n** (Seed pipeline), **FR-D-n** (Demo script·operator mode), **FR-X-n** (Cross-cutting contract delta).

### 4.A Buyer Portal (영어)

#### 4.A.1 Authentication & session

- **FR-A-1**: 포털은 URL path `/` 로 들어온 미인증 사용자에게 **Home (A-1)** 을 공개 노출한다. 근거: 리서치 `buyer-portal-ux-competitive.md §9.1`.
- **FR-A-2**: 미인증 사용자가 `/search`, `/orders`, `/orders/*`, `/account` 에 접근하면 `/signin` 으로 307 리다이렉트한다.
- **FR-A-3**: `/signin` 폼은 단일 필드 "API key" (password type, `rv_live_` prefix validation). 제출 시 BFF `POST /api/session` 으로 전송. 근거: metadata-index dev-spec §6.2 buyer_api_key 재사용.
- **FR-A-4**: BFF `POST /api/session` 은 (a) key 포맷 검증 → 실패 시 `ERR_AUTH_FORMAT` 반환, (b) metadata-index `GET /v1/search/facets` 에 해당 키 Bearer 로 1 회 호출 → 200 성공 시 쿠키 `rv_session` (HttpOnly, Secure, SameSite=Lax, 12h TTL) 에 **암호화된 API key** 저장. 원 키는 브라우저에 전달되지 않는다. 실패 시 `ERR_AUTH_INVALID` 반환. 근거: 리서치 §13.3-11 BFF 권고.
- **FR-A-5**: 모든 인증 필요 페이지는 **BFF route handler** 경유 (`/api/search/*`, `/api/orders/*`). route handler 는 쿠키를 서버측에서 복호화 → 원 API key 를 Bearer 로 업스트림에 전달. 브라우저 네트워크 패널에는 원 API key 가 노출되지 않는다.
- **FR-A-6**: 로그아웃 `POST /api/session/delete` 는 쿠키 파기만 수행 (업스트림 key revoke 는 SRE CLI 전용).
- **FR-A-7**: 쿠키 TTL 만료 시 모든 BFF route handler 는 401 envelope (`ERR_AUTH_EXPIRED`) 반환 → 포털은 `/signin` 으로 자동 리다이렉트 + 토스트 "Your session expired. Please sign in again."

#### 4.A.2 Home (A-1)

- **FR-A-8**: Hero 섹션 — headline `"Korea's medical imaging data, compliantly delivered to the world's AI."` (한 줄, PRD §1 원문) + sub-copy 2 줄 + "Sign in with API key" primary CTA + "Read API docs" secondary CTA (link to `api-quickstart-buyer-en.md`).
- **FR-A-9**: 3-tile proof 섹션 — (a) "Studies indexed" 실수치 (facets 공개 서브셋) (b) "Hospitals contributing" 실수치 (c) "Turnaround p95" 목표치 "< 48h" 단정 아님("designed for"). 리서치 `demo-pitch-references-radivault.md §8.1` 금기 준수 (허위 수치 0건).
- **FR-A-10**: Home 의 facets 호출 실패 시 tile 은 "—" 로 폴백, 에러 토스트 표시 안 함 (public 페이지이므로).

#### 4.A.3 Search (A-3)

- **FR-A-11**: 좌측 패싯 패널 7 필드. 각 필드 옆 회색 원형 카운트 배지. 필드 목록: modality, body_part, sex, age_bucket, study_year, manufacturer, min_hospitals(select 1..5). 근거: metadata-index `GET /v1/search/facets` 화이트리스트 6 + UI 전용 min_hospitals.
- **FR-A-12**: 검색 상자 상단 1 개 (free text는 v0.2). v0.1 은 자리만 확보, placeholder `"Coming in v0.2 — use filters on the left for now"`.
- **FR-A-13**: 결과 테이블 컬럼 7 개: 체크박스 · pseudo_study_uid(8자 잘림 + 전체 복사 툴팁) · modality(색 배지) · body_part · n_instances · size_mb · study_year. 근거: 리서치 §4.3.
- **FR-A-14**: 테이블은 shadcn/ui DataTable (TanStack Table) 기반. 정렬·페이지네이션 내장.
- **FR-A-15**: 페이지네이션은 **keyset cursor** (metadata-index FR-20). 브라우저 측은 cursor 문자열을 URL 쿼리에 저장하지 않는다 (filter_sha256 노출 회피) — 세션 메모리만.
- **FR-A-16**: 결과 카운트 상단에 `"N studies across M hospitals"` 형태 (M = distinct hospital_group). 필터 변경 시 실시간 업데이트.
- **FR-A-17**: 활성 필터는 검색 상자 위에 dismissible chip 으로 표시 (`modality=CT ×`). "Clear all" 링크 제공.
- **FR-A-18**: 우측 cohort sidebar 는 persistent (고정). 선택된 스터디 수 · total size · "Review order" primary CTA.
- **FR-A-19**: cohort 는 sessionStorage 저장 (새로고침 시 유지, 브라우저 종료 시 소실). v0.1.1 server-side saved cohorts 에 대비.
- **FR-A-20**: 테이블 row 클릭 시 Study detail drawer (A-4) 슬라이드인.
- **FR-A-21**: 빈 결과 시 `<EmptyState variant="no-results">` 표시 (§3.C).
- **FR-A-22**: 썸네일 컬럼 **없음** (§0.2-1). 각 row 좌측에 modality 색 배지가 시각 대체 (§0.2 FR-A-23 참조).
- **FR-A-23**: modality 배지 색상 코드 — CT 파랑(#2563eb), MR 보라(#7c3aed), CR/DR 초록(#059669), MG 분홍(#ec4899), US 주황(#ea580c), PT 빨강(#dc2626). 출처: 리서치 `buyer-portal-ux-competitive.md §4.3`.

#### 4.A.4 Study detail drawer (A-4)

- **FR-A-24**: 우측 슬라이드 드로어 (shadcn Sheet). 닫기 X 또는 ESC.
- **FR-A-25**: 섹션 1 — 메타데이터: modality, body_part, sex, age_bucket, study_year, n_instances, size_mb, hospital_code, manufacturer, station_name. 근거: metadata-index `GET /v1/search/studies/{uid}` 응답 필드.
- **FR-A-26**: 섹션 2 — 시리즈 목록: series_uid 8 자 · modality · n_instances. 최대 10 행, 이상은 "show more".
- **FR-A-27**: 섹션 3 — CTA 영역: "Add to cohort" 버튼 (이미 cohort 내라면 "Remove" 로 토글) + "—" 가격 자리 (§0.2-3).
- **FR-A-28**: DICOM 뷰어 **없음** (§0.2-1). 대신 회색 박스 "Preview available in v0.2 (sample dataset program)." 1 줄.
- **FR-A-29**: Thumbnail placeholder — modality 배지 96×96 확대판 + pseudo_study_uid 4자 (§7 D-1 계약 델타 옵션 b 선택 시에만).

#### 4.A.5 Review order modal + Confirm (A-5)

- **FR-A-30**: "Review order" 버튼 클릭 시 shadcn Dialog. 닫기 X 또는 ESC.
- **FR-A-31**: 모달 섹션 — (a) cohort summary (N studies, total size, hospital distribution 1줄), (b) agreement section (agreement_hash 자동 채움 + "I confirm this order is governed by MSA {masked_id}" 체크박스), (c) total price `—` (마스킹) · sub-text "Billing is v0.1 stub — no charge will occur. Contact sales@radivault.io for paid tier." (d) Primary CTA "Confirm order".
- **FR-A-32**: agreement_hash 는 BFF 에서 시점 기반 deterministic stub (`sha256("rv-v0.1-msa-stub")` 의 hex) 를 자동 주입. 실 MSA 파일 업로드는 v0.2.
- **FR-A-33**: Idempotency-Key 는 BFF 가 `crypto.randomUUID()` 로 생성, 모달 lifecycle 동안 유지. 같은 cohort 재제출 시 새 키 재생성 (사용자 명시적 "Confirm" = 새 주문 의도). 근거: `order-fulfillment` FR-31.
- **FR-A-34**: "Confirm order" 클릭 시 BFF `POST /api/orders` → `order-fulfillment POST /v1/orders` 전달. 응답 수신 시:
  - 성공 (202 or 201): 모달을 영수증 뷰로 전환 (order_id · state · estimated ETA · "Go to order" CTA). 3 초 후 자동 `/orders/{id}` 이동.
  - 실패 (4xx): 모달 내 `<ErrorBanner>` 표시 + code + hint (design-spec-order-fulfillment §5 매핑).
- **FR-A-35**: DUA 체크박스 미체크 시 "Confirm order" 버튼은 disabled (aria-disabled=true).
- **FR-A-36**: 모달이 열려 있는 동안 브라우저 뒤로가기 방지 (beforeunload 경고) — 주문 중복 방지.

#### 4.A.6 Orders list (A-6)

- **FR-A-37**: 테이블 컬럼 5 개: order_id(8자 잘림 + 복사) · phase badge (5-phase) · n_studies · created_at (relative, "3m ago") · ETA or "Ready" / "Expired".
- **FR-A-38**: phase badge 색상: Accepted(회색) · Fetching(파랑 animated) · Preparing(파랑) · Ready(초록) · Completed(진초록) · Cancelled(회색) · Expired(회색) · Failed(빨강).
- **FR-A-39**: 페이지 당 20 row, keyset cursor pagination.
- **FR-A-40**: 빈 상태 시 `<EmptyState variant="no-orders">` (§3.C).

#### 4.A.7 Order detail + tracker (A-7)

- **FR-A-41**: 상단 — order_id · created_at · n_studies · total size · (cancelled 등) status chip.
- **FR-A-42**: 5-phase 수평 step tracker (dots with labels): Accepted → Fetching from hospital → Preparing download → Ready to download → Completed. 근거: 리서치 `buyer-portal-ux-competitive.md §7.2`.
- **FR-A-43**: 내부 12-state FSM → 5-phase 매핑 (§7 D-3 Contract delta 로 서버가 `buyer_phase` 필드를 반환. 서버 미반환 시 **포털 클라이언트가 매핑 수행**).
  | Phase | 내부 state |
  |---|---|
  | Accepted | queued, validating, validated, submitted, draft |
  | Fetching from hospital | fetching |
  | Preparing download | staging_partial, staging_complete |
  | Ready to download | ready_for_download, delivering |
  | Completed | delivered |
  | (별도) Cancelled / Expired / Failed | cancelled, expired, failed |
- **FR-A-44**: 현재 phase 는 색상 highlight + "Estimated ready by: 2026-04-24 18:34 KST" tooltip (ETA 계산: Hot hit 30초, cold 1시간 기본 + n_studies × 2초).
- **FR-A-45**: "View details" 드로어 — 내부 12-state 타임라인 (`order_state_history` 조회) + Prometheus style 이벤트 로그 (SRE 용).
- **FR-A-46**: state 가 `cancelled`, `expired`, `failed` 시 상단 red banner + 에러 코드 표시 + "Contact support" 링크.
- **FR-A-47**: 자동 폴링 — `GET /api/orders/{id}` 5 초 간격 (phase 가 `Accepted`/`Fetching`/`Preparing` 동안). `Ready` 도달 시 폴링 중단. `Completed` 전이 시 toast "Order ready — go to downloads".
- **FR-A-48**: 폴링 백오프 — 3 회 연속 오류 시 10 초, 20 초, 30 초로 지수 백오프. 근거: `order-flow-quickstart-buyer-en.md §5`.
- **FR-A-49**: "Cancel order" 버튼 — `Accepted` phase 에서만 활성. 클릭 시 확인 dialog → `POST /api/orders/{id}/cancel`.

#### 4.A.8 Downloads (A-8)

- **FR-A-50**: 페이지 진입 시 자동 `POST /api/orders/{id}/download-urls` 호출 → per-object URL 배열 수신.
- **FR-A-51**: 상단 — 만료 카운트다운 "Expires in HH:MM:SS" + "Refresh URLs" 버튼 (수동 재발급).
- **FR-A-52**: 카운트다운이 10 분 이하 남을 시 배경 노랑 + "Consider refreshing" hint.
- **FR-A-53**: 만료 후에는 카운트다운 "Expired" + "Refresh URLs" 버튼만 노출. 다른 버튼 disabled.
- **FR-A-54**: 3 tabs: (a) Browser download (object list) (b) Copy curl (c) Copy Python (httpx).
- **FR-A-55**: Browser tab — 각 row: filename · size (human) · SHA-256 (8자 + click to copy full) · "Download" 버튼 (presigned URL 직접 열기, target=_blank, rel="noopener").
- **FR-A-56**: "Download all (.json manifest)" 상단 CTA — 클라이언트가 manifest 전체를 Blob 으로 만들어 download 트리거. 포맷은 `order-flow-quickstart-buyer-en.md §7` 재사용.
- **FR-A-57**: Copy curl tab — 단일 `for` loop snippet (presigned URL 리스트가 배열로 렌더). 클릭 시 clipboard 복사 + toast "Copied".
- **FR-A-58**: Copy Python tab — httpx parallel 다운로드 예제 (12 concurrent). 근거: `order-flow-quickstart-buyer-en.md §7.2`.
- **FR-A-59**: 페이지 떠날 시 presigned URL 은 메모리에만 보관된 상태에서 GC (sessionStorage X).

#### 4.A.9 Account (A-9)

- **FR-A-60**: API key 마스킹 `rv_live_****_***************ef12` (첫 8·마지막 4 노출, 나머지 `*`).
- **FR-A-61**: Tier 레벨 (preview / paid) · 일일 쿼터 소비 (BFF `GET /v1/search/quota-status` — metadata-index 가 제공하는 필드 그대로 표시) · 다음 리셋까지 HH:MM.
- **FR-A-62**: "Contact support" link to `mailto:support@radivault.io`.
- **FR-A-63**: "Sign out" 버튼.
- **FR-A-64**: API key 관리 (new · revoke) UI 없음 (§0.2-10). 안내 문구 "Managed by RadiVault SRE. Contact support for rotation."

#### 4.A.10 Shell (global)

- **FR-A-65**: Top nav — 좌 Logo (home link) · 중앙 Search · Orders · Downloads (disabled when no ready order) · Docs (외부 링크 `docs.radivault.io` placeholder, v0.1 은 marketing 폴더 `/docs/api-quickstart`) · 우 Profile dropdown.
- **FR-A-66**: Logo 디자인 — `<Brand />` 컴포넌트. 실 로고는 designer 가 v0.1 에 제공. 임시는 text mark "RadiVault" 굵은 체.
- **FR-A-67**: Profile dropdown — "Account" · "API docs" · "Sign out".
- **FR-A-68**: ⌘K command palette placeholder — v0.1 는 렌더만 하고 "Coming soon" (§0.2).
- **FR-A-69**: Keyboard — ESC 닫기, Cmd+K(ignore), Cmd+/ (focus search, search 페이지에서만).
- **FR-A-70**: 404 페이지 — "This page doesn't exist" + home 링크.
- **FR-A-71**: 500 페이지 — "Something went wrong" + request_id + home 링크.

### 4.B Hospital Dashboard (한국어)

#### 4.B.1 Authentication

- **FR-B-1**: `/hospital/{gateway_id}` 접근 시 미인증이면 `/hospital/signin` 리다이렉트.
- **FR-B-2**: Sign-in 폼: "병원 관리자 토큰" (password). 제출 시 BFF `POST /api/hospital/session`. v0.1 은 **config 파일 기반 stub** — 앱 기동 시 환경변수 `RV_HOSPITAL_ADMIN_TOKENS` (JSON: `{"gateway_id": "token", ...}`) 를 읽어 in-memory compare. 평문 비교 금지 — argon2id 해시로 저장(§7 D-5).
- **FR-B-3**: 세션 쿠키 `rv_hospital_session` (HttpOnly, Secure, SameSite=Strict, 2h TTL). 쿠키에는 gateway_id 만 저장.
- **FR-B-4**: 쿠키 TTL 만료 시 sign-in 리다이렉트 + 토스트 "세션이 만료되었습니다. 다시 로그인해 주세요."

#### 4.B.2 Layout & i18n

- **FR-B-5**: 한국어 전용. 모든 라벨·툴팁·에러 메시지 `ko-KR`.
- **FR-B-6**: 날짜·시간 `ko-KR` locale (2026년 4월 24일 18:34). 숫자 `toLocaleString('ko-KR')` (1,234,567).
- **FR-B-7**: 통화 `₩` prefix, 천단위 쉼표, 소수점 없음 (원 단위).
- **FR-B-8**: 1-scroll 완결 레이아웃 — 타일 6 개가 1920×1080 화면에 모두 보이도록 CSS Grid 3×2 또는 2×3. 스크롤 금지.

#### 4.B.3 Tiles

- **FR-B-9**: **B-1 Studies** — 타일 상단 "오늘" 큰 숫자 + 하단 "누적" 작은 숫자. 데이터 소스: `GET /api/hospital/me/stats` (§7 D-2).
- **FR-B-10**: **B-2 Revenue** — 타일 상단 누계 `₩ YY,YYY` 대문짝 + 하단 월별 bar chart 12 개월 (Recharts). 최하단 고정 푸터 **"시뮬레이션 — v0.2 정산 대기"** 라벨은 **제거 불가** (design-time assert, storybook snapshot test).
- **FR-B-11**: 월별 revenue 계산 — clientside: `studies_month × unit_price × hospital_share_pct`. 기본값: unit_price=$5 (Kyle 결정 대기), hospital_share_pct=35% (tier 중간값). 환율은 display-only fixed 1,350 원/USD (v0.1 하드코딩, Kyle 결정).
- **FR-B-12**: **B-3 Map** — 한국 지도 SVG (17 광역). 기본은 전부 회색. gateway_id → region 매핑 파일 (v0.1 은 2~3 레코드). 해당 region 이 파랑 grad (기여 volume 비례, v0.1 고정 값). 툴팁 1 라인 ("김씨병원 — 서울 강남").
- **FR-B-13**: **B-4 Gateway** — 초록/노랑/빨강 점 + "● Online" / "● Warning (last sync 15m ago)" / "● Offline (last sync 2h ago)". 상태 판단: last_sync < 5m → Online, < 30m → Warning, 이상 → Offline. 데이터 소스: `GET /api/hospital/me/gateway-health` (§7 D-2).
- **FR-B-14**: **B-5 Orders** — 최근 10 주문 row: 주문 ID 마스킹 (4자) · 스터디 수 · phase 한국어 ("접수" · "병원에서 가져오는 중" · "준비 중" · "다운로드 준비 완료" · "완료" · "취소" · "만료" · "실패") · 완료 시각 (relative, "3분 전"). 데이터 소스: `GET /api/hospital/me/orders?limit=10` (§7 D-2).
- **FR-B-15**: **B-6 Audit** — append-only 10 row: 시각 · 이벤트 타입 한국어 ("입수" · "업로드" · "앵커 기록" · "주문 배송") · 해시 8자 (클릭 X, 정보 전용). 데이터 소스: `GET /api/hospital/me/audit?limit=10` (§7 D-4).
- **FR-B-16**: 모든 타일은 60 초 간격 자동 폴링 (각 tile 독립). 폴링 실패 시 tile 내부 silent "—" + 마지막 성공 데이터 유지, tile 외곽 노랑 테두리 (stale indicator).
- **FR-B-17**: 각 타일 우상단 "마지막 업데이트 HH:MM" 작은 글씨.

#### 4.B.4 Empty / error

- **FR-B-18**: 데이터 전부 0 일 때 타일별 empty placeholder ("아직 데이터가 없습니다"). Error 는 `<ErrorBanner>` 재사용 (한국어 매핑).

### 4.S Demo Seed Pipeline

#### 4.S.1 Data source

- **FR-S-1**: 데이터 소스는 **TCIA 공개 컬렉션**. 라이선스 CC-BY 또는 Restricted 중 선택 — v0.1 은 **CC-BY 한정** (재배포 자유도 최대, 상업 데모에서도 안전). Kyle 확정 대기 (§11-Q-Data-1). 권장 컬렉션:
  - CPTAC-PDA (Pancreatic Ductal Adenocarcinoma) — CT Abdomen
  - LIDC-IDRI — CT Chest
  - ACRIN-NSCLC-FDG-PET — CT/PT Chest
  - QIN-BRAIN-DSC-MRI — MR Brain
  - CBIS-DDSM — MG
  - Spine-Mets-CT-SEG — CT Spine (Kyle 배경)
- **FR-S-2**: 총 300~500 study. modality 분포: CT 40%, MR 25%, CR 15%, MG 10%, PT/US 10%. Kyle 확정 후 seed config YAML 작성.
- **FR-S-3**: 데이터는 **로컬 캐시 디렉토리** `./demo_data/cache/` 에 보관. 한 번 다운로드 후 재사용. `.gitignore` 필수. 캐시 누적 크기 제한 10 GB (초과 시 스크립트가 경고).

#### 4.S.2 Download script

- **FR-S-4**: `scripts/demo_seed/download_tcia.py` Python 스크립트. TCIA REST API (`https://services.cancerimagingarchive.net/services/v4/TCIA/query/...`) 또는 `tcia_utils` 라이브러리 사용.
- **FR-S-5**: 입력: `seed_config.yaml` (컬렉션별 target study 수). 출력: 캐시 디렉토리 내 `{collection}/{study_instance_uid}/` 구조 (원본 DICOM 파일들).
- **FR-S-6**: idempotent — 재실행 시 이미 다운로드된 study skip. SHA-256 매니페스트 `_manifest.sha256` 검증.
- **FR-S-7**: 실패 시 지수 백오프 재시도 5회. 최종 실패 study 는 `_failed.json` 에 기록, 프로세스는 계속.

#### 4.S.3 Injection pipeline

- **FR-S-8**: `scripts/demo_seed/inject_all.sh` — 전체 파이프라인 실행:
  1. `docker-compose -f docker-compose-demo.yml up -d` — Orthanc + postgres + redis + minio + gateway + central + search + fulfillment + portal 전체 기동.
  2. `python scripts/demo_seed/load_orthanc.py` — 캐시 DICOM → Orthanc STOW-RS upload.
  3. `gateway-admin run --once --batch-size 500 --target-hospital-id H001` — Gateway Flow A 일회성 실행 (Orthanc → De-ID → Central upload).
  4. `search-admin index rebuild` (있으면) 또는 자연스러운 idx 업데이트 대기.
  5. `python scripts/demo_seed/seed_buyer.py` — 데모용 buyer key 발급 (`rv_live_demo1234_*`), tier=paid, quota 10,000.
  6. `python scripts/demo_seed/seed_hospital.py` — 데모용 hospital admin token + gateway_id 등록.
  7. `python scripts/demo_seed/verify.py` — 검증 체크리스트 (§4.S.4).
- **FR-S-9**: 각 단계 로그는 JSON 파일 `logs/demo_seed_YYYYMMDD_HHMMSS.log` 에 누적. 최종 PASS/FAIL 출력.
- **FR-S-10**: 전체 실행 시간 목표 < 30 분 (500 study 기준, 로컬 M-series Mac). 실제 로깅 필수.

#### 4.S.4 Verification checklist

- **FR-S-11**: `scripts/demo_seed/verify.py` 는 다음을 체크하고 각 항목 PASS/FAIL 출력:
  - V-1: central-ingest `study` 테이블 row count ≥ 300.
  - V-2: metadata-index `GET /v1/search/studies` (빈 필터) 응답 `total ≥ 300`.
  - V-3: modality facet ≥ 3 종류 노출.
  - V-4: `hospital_code` 1 개 이상 + Gateway heartbeat 최근 5 분 내.
  - V-5: 감사 해시체인 `ingest-admin anchor verify --from 1 --to -1` exit 0.
  - V-6: de-ID flag 전체 `fully_anonymized`, PHI leak 0건 (`ingest-admin study inspect --random 10` 샘플링).
  - V-7: 데모 buyer key 로 search 성공.
  - V-8: 데모 hospital admin token 으로 hospital dashboard stats 응답.
- **FR-S-12**: 모든 V-1..V-8 PASS 시 `demo_seed_ready.lock` 파일 생성. 포털은 이 파일 존재 여부를 Home 3-tile 중 "Studies indexed" 수치로 간접 확인 (v0.1 은 단순 facets 호출).

#### 4.S.5 Reset script

- **FR-S-13**: `scripts/demo_seed/reset.sh` — 재현성 위해 제공:
  1. `docker-compose -f docker-compose-demo.yml down -v` (볼륨 제거).
  2. 캐시 DICOM 은 보존 (`./demo_data/cache/` 삭제 금지 — 재다운로드 30분 회피).
  3. `docker-compose -f docker-compose-demo.yml up -d`.
  4. `inject_all.sh` 재실행.
- **FR-S-14**: `reset.sh --hard` 는 캐시까지 삭제 (extreme reset).
- **FR-S-15**: Demo Operator Mode (§3.D) 의 "Reset demo data" 버튼은 `scripts/demo_seed/reset.sh --soft` 를 HTTP 래퍼로 호출. soft 모드는 DB truncate + staging clear 만 수행 (Orthanc 보존) — 1 분 내 복구 목표.

### 4.D Demo script & Operator mode

#### 4.D.1 Demo script file

- **FR-D-1**: `docs/specs/demo-script-radivault.md` 신규 파일 작성. 본 dev-spec 에서는 **스켈레톤 + 장면 요약 표** 까지만 제시 (§9). 실제 대사·연출 상세는 @designer 가 피치 덱과 함께 채운다.
- **FR-D-2**: 파일 구조:
  - §0 Meta (version, target audience, 17+3 minutes, 스토리보드 variant A)
  - §1 사전 준비 체크리스트 (H-day, D-1, D-0)
  - §2 장면 1~7 (시간·제목·시각 자산·프레젠터 대사 한영·조작 절차·예상 질문·Canned 경로)
  - §3 실패 런북 (§4.3 참조)
  - §4 리허설 체크리스트 (2회 이상 권장)
  - §5 사후 follow-up 템플릿
- **FR-D-3**: 장면 1~7 은 §9 스토리보드 표를 복제하여 기본 행 7 개 확보.

#### 4.D.2 Demo Operator Mode

- **FR-D-4**: 포털에 `?demoop=1` 쿼리로 진입 시 Demo Operator Mode 활성화 (§3.D).
- **FR-D-5**: 활성화 조건 — 환경변수 `DEMOOP_TOKEN` 이 설정되어 있고, 요청에 `X-Demoop-Token` 헤더 또는 쿼리 `demoop_token=...` 가 있어야 함. 프로덕션 (환경변수 미설정) 에서는 `?demoop=1` 무시.
- **FR-D-6**: Canned output overlay — 각 장면별 pre-captured JSON 응답 파일을 `public/demoop/canned/scene-{n}/*.json` 에 보관. 활성 시 BFF route handler 가 업스트림 호출 대신 이 파일 반환.
- **FR-D-7**: Scene shortcut — Ctrl+1~7 키보드로 각 장면 pre-warmed URL 로 이동. pre-warmed URL 목록:
  - Ctrl+1 → `/`
  - Ctrl+2 → `/search?_seed=arch` (전체 데이터)
  - Ctrl+3 → `/hospital/H001` (Hospital Dashboard)
  - Ctrl+4 → `/search?modality=CT&body_part=SPINE` (검색 예시)
  - Ctrl+5 → `/orders/{demo_order_id}` (사전 주문 대기)
  - Ctrl+6 → `/hospital/H001` (재방문, revenue tile 강조)
  - Ctrl+7 → `/` (ask 전 환기)
- **FR-D-8**: Ctrl+R 은 Reset demo data 버튼과 동일 (soft reset).
- **FR-D-9**: Scene progress indicator — 좌하단 "Scene X/7 — elapsed MM:SS / target 17:00". Ctrl+. 로 next scene 타이머 스타트.

### 4.X Cross-cutting & non-portal FR

- **FR-X-1**: 포털은 `NEXT_PUBLIC_*` 환경변수만 브라우저에 노출하고, 업스트림 API host URL · SRE token 은 서버측 전용 `RV_*` 변수로 보관한다.
- **FR-X-2**: 모든 외부 API 호출은 timeout 15 초 (BFF → 업스트림). 실패 시 client 에 502 envelope (`ERR_UPSTREAM_TIMEOUT`) 반환.
- **FR-X-3**: 모든 BFF route handler 는 request_id (uuid4) 생성 후 업스트림에 `X-Request-Id` 헤더로 전달. 응답 실패 시 envelope 에 동일 request_id 포함.
- **FR-X-4**: BFF route handler 에러 로깅은 `pino` JSON (Node.js 표준) 으로 stdout 에 출력. 필드: ts, level, request_id, route, upstream_status, err_code. PHI / API key 필드는 **절대 로깅 금지**.
- **FR-X-5**: CSP — `default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'(Next dev only); img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'`.
- **FR-X-6**: HTTPS 강제 — Vercel 프로덕션 자동. 로컬 dev 는 `NEXT_PUBLIC_ALLOW_INSECURE=1` 시에만 http 허용.
- **FR-X-7**: 로그에 API key · agreement_hash · presigned URL · pseudo_study_uid 전체 값 금지. hash 8자 / 마스킹만.

---

## §5 Acceptance Criteria

모든 AC 는 binary-testable. QA 가 자동 또는 수동으로 검증 가능.

### 5.A Buyer Portal

- [ ] **AC-A-1**: `/` 미인증 접근 시 200 OK + Home 렌더. `/search` 미인증 접근 시 307 → `/signin`.
- [ ] **AC-A-2**: Invalid API key 제출 시 signin 페이지에 `ERR_AUTH_INVALID` 에러 메시지 노출. 서버 로그에 해당 key 평문 미기록.
- [ ] **AC-A-3**: 올바른 API key 제출 시 쿠키 `rv_session` 생성 + `/search` 리다이렉트. 쿠키는 HttpOnly=true, Secure=true, SameSite=Lax. 브라우저 JS 에서 `document.cookie` 로 `rv_session` 접근 불가.
- [ ] **AC-A-4**: `/search` 패싯 7 개 노출. 각 필터 옆 카운트 배지 숫자 ≥ 0.
- [ ] **AC-A-5**: 필터 적용 시 테이블 결과 수와 상단 카운트 일치. 필터 변경 시 URL 에 반영되지 않음 (sessionStorage 만).
- [ ] **AC-A-6**: 테이블 row 클릭 시 Study detail drawer 열림, ESC 로 닫힘.
- [ ] **AC-A-7**: cohort 에 스터디 5 개 추가 후 "Review order" 모달 열림. 가격 표시 `—`. DUA 체크 전 Confirm 버튼 disabled.
- [ ] **AC-A-8**: Confirm 성공 시 3 초 내 `/orders/{id}` 이동. order_id 는 응답 본문과 일치.
- [ ] **AC-A-9**: 주문 detail 페이지의 5-phase tracker 가 내부 FSM state 와 FR-A-43 표대로 매핑된다 (QA 는 12-state 각각 mock 응답으로 확인).
- [ ] **AC-A-10**: `ready_for_download` 상태에서 `/orders/{id}/downloads` 접근 시 presigned URL 배열 수신, 만료 카운트다운 표시.
- [ ] **AC-A-11**: Downloads 페이지 "Copy curl" 클릭 시 clipboard 에 snippet 복사됨 (브라우저 테스트).
- [ ] **AC-A-12**: 세션 만료 시뮬레이션 — 쿠키 수동 삭제 후 `/search` 접근 시 signin 리다이렉트 + 토스트 노출.
- [ ] **AC-A-13**: 네트워크 오류 시뮬레이션 (BFF 502 mock) — `<ErrorBanner>` 노출 + request_id 복사 가능.
- [ ] **AC-A-14**: 페이지 로드 성능 — `/` 와 `/search` 초기 렌더 (skeleton → first data paint) p95 < 2.5s (로컬 프로덕션 빌드, 목데이터 300 rows).
- [ ] **AC-A-15**: Lighthouse (desktop) accessibility score ≥ 90.
- [ ] **AC-A-16**: 키보드 네비 — Tab 으로 모든 인터랙티브 요소 도달 가능, focus ring 가시.
- [ ] **AC-A-17**: BFF 로그 100 줄 수집 후 grep "rv_live_" 결과 0건 (API key 누출 없음).

### 5.B Hospital Dashboard

- [ ] **AC-B-1**: `/hospital/H001` 미인증 접근 시 `/hospital/signin` 리다이렉트.
- [ ] **AC-B-2**: Invalid admin token 제출 시 에러 메시지 "토큰이 올바르지 않습니다" 노출. 쿠키 미생성.
- [ ] **AC-B-3**: 올바른 token 제출 시 dashboard 렌더. 타일 6 개 전부 표시.
- [ ] **AC-B-4**: B-1 studies 숫자가 central-ingest 의 해당 hospital_id study count 와 일치 (±10 건 허용 — 폴링 지연).
- [ ] **AC-B-5**: B-2 revenue 타일의 "시뮬레이션 — v0.2 정산 대기" 라벨 존재. storybook snapshot test 로 회귀 보장.
- [ ] **AC-B-6**: B-3 map SVG 렌더, 1 포인트 이상 하이라이트.
- [ ] **AC-B-7**: B-4 Gateway tile — 5 분 내 sync 시 초록, 30 분 초과 시 빨강 (mock last_sync 시간으로 QA 검증).
- [ ] **AC-B-8**: B-5 Orders tile — 최근 10 주문 노출, phase 한국어 매핑 전수 확인.
- [ ] **AC-B-9**: B-6 Audit tile — 최근 10 감사 이벤트 노출, hash 8자 형식.
- [ ] **AC-B-10**: 60 초 폴링 확인 — network 탭에서 각 tile 별 API 호출 60±5초 간격 확인.
- [ ] **AC-B-11**: 한 tile polling 실패 시 해당 tile 만 stale indicator (노랑 테두리), 다른 tile 영향 없음.
- [ ] **AC-B-12**: 1920×1080 해상도에서 스크롤 없이 6 tile 전부 가시.
- [ ] **AC-B-13**: 통화 렌더 `₩` + `toLocaleString('ko-KR')` — 1234567 → `₩ 1,234,567`.

### 5.S Seed pipeline

- [ ] **AC-S-1**: `scripts/demo_seed/download_tcia.py` 재실행 idempotent — 두 번째 실행 시 기존 파일 skip.
- [ ] **AC-S-2**: `inject_all.sh` 30 분 이내 완료 (500 study 기준, M1 Mac).
- [ ] **AC-S-3**: `verify.py` V-1..V-8 모두 PASS 시 exit 0 + `demo_seed_ready.lock` 생성.
- [ ] **AC-S-4**: V-6 PHI 샘플링에서 PHI 의심 필드 0건.
- [ ] **AC-S-5**: `reset.sh --soft` 실행 후 1 분 내 DB truncate + Orthanc 보존 확인.
- [ ] **AC-S-6**: Seed config YAML 미존재 시 download_tcia.py 는 exit code 2 (config missing) + 한영 에러.

### 5.D Demo script & Operator mode

- [ ] **AC-D-1**: `docs/specs/demo-script-radivault.md` 존재 + §0~§5 뼈대 채워짐 + 장면 1~7 표.
- [ ] **AC-D-2**: Demo Operator Mode 환경변수 `DEMOOP_TOKEN` 미설정 시 `?demoop=1` 쿼리는 정적 무시 (네트워크 탭에 `/api/demoop/*` 호출 0건).
- [ ] **AC-D-3**: Canned overlay 토글 시 BFF 가 업스트림 호출 대신 `public/demoop/canned/*.json` 파일 로드 (QA 네트워크 캡처로 검증).
- [ ] **AC-D-4**: Ctrl+1~7 키 각각 해당 URL 이동.
- [ ] **AC-D-5**: Scene progress indicator 가 Ctrl+. 누를 때마다 장면 번호 증가.
- [ ] **AC-D-6**: 17분 리허설 2회 완주 로그 `logs/rehearsal_*.md` 작성 (각 장면별 실제 소요시간 측정, 목표 대비 ±2분 이내).

### 5.X Cross-cutting & 법적 고려

- [ ] **AC-X-1**: `git grep -i "rv_live_"` 소스 전체에서 하드코딩 키 0건 (데모 fixture 제외, fixture 는 `rv_live_demo1234_*` 형식만).
- [ ] **AC-X-2**: 모든 에러 응답 envelope 에 request_id 포함.
- [ ] **AC-X-3**: 포털 HTML 응답 CSP 헤더 검증.
- [ ] **AC-X-4**: pino 로그 10,000 줄 수집 후 PHI 의심 필드 (PatientName/PatientID/StudyInstanceUID 원본 포맷) 0건.
- [ ] **AC-X-5**: `docs/specs/demo-script-radivault.md §3` 실패 런북 5개 항목 이상 + 각 항목 "첫 5초 액션" 명시.

---

## §6 Non-functional requirements

### 6.1 성능 · 가용성 · 접근성 · 브라우저

| 항목 | 요구 |
|---|---|
| **초기 로드** | Buyer Portal `/`, `/search` p95 < 2.5s (프로덕션 빌드, Vercel edge or 로컬 docker-compose) |
| **Subsequent nav** | 같은 세션 내 라우트 전환 p95 < 500ms (TanStack Query 캐시 활용) |
| **폴링 주기** | Buyer Portal order detail 5초, Hospital Dashboard 60초. 탭 백그라운드 시 2배 완화 |
| **동시 세션** | 데모 단일 세션 기준. v0.1 성능 부하 테스트 0명 수용. v0.1.1 에 k6 시나리오 추가 |
| **가용성 목표** | 데모 세션 100% (SC-1 동치). 프로덕션 99%는 v0.1.1 이후 |
| **브라우저** | Chrome 120+, Safari 17+, Edge 120+ . Firefox best-effort. IE 미지원 |
| **해상도** | 1280×720 최소, 1920×1080 권장. 4K scaled OK |
| **접근성** | WCAG 2.1 AA 목표. Lighthouse ≥ 90. 키보드 네비 전수. Screen reader best-effort (v0.1.1 상세 검증) |
| **국제화** | Buyer 영어, Hospital 한국어. 문자열은 `messages/en.json`, `messages/ko.json` 분리. next-intl 사용 |
| **로깅·감사** | BFF 로그 pino JSON stdout. 실 감사 로그는 업스트림 central-ingest / order-fulfillment 가 보유. 포털은 자체 감사 없음 |
| **보안** | CSP, HSTS(프로덕션), HttpOnly/Secure/SameSite 쿠키, CSRF 방어(SameSite=Lax + BFF 토큰) |
| **데이터 보관** | BFF 메모리 캐시 TTL ≤ 5 분. 영구 저장소 없음 |

### 6.2 법적·보안 고려 (HIPAA / PIPA / PHI)

본 기능은 **PHI 를 직접 저장하지 않지만**, 업스트림 API 응답 본문을 브라우저까지 전달한다. 따라서 다음 가드레일을 강제한다.

- **L-1**: **모든 응답 스키마가 "완전 익명화" 계약을 준수한다는 전제**. metadata-index FR-40 + order-fulfillment FR-52 의 anonymization_flag 게이트가 이미 central-ingest 에서 차단하므로 포털은 추가 게이트를 두지 않는다. 단, QA 는 포털 브라우저 네트워크 탭에서 `PatientName`, `PatientID`, `StudyDate`(비-시프트 포맷) 등의 필드가 노출되지 않음을 샘플링 검증 (AC-X-4).
- **L-2**: **Buyer API key 는 절대 브라우저 JS 메모리에 평문으로 노출되지 않는다**. BFF cookie 암호화 (Next.js iron-session 또는 `@auth/core` 라이브러리)로 서버측만 복호화 가능.
- **L-3**: **presigned URL 은 URL 자체가 단기 자격증명이므로 로그 금지**. BFF 응답에서 브라우저로 전달하지만, BFF 로그에는 URL path + query 의 앞 40 자만 masked 기록 (필요 시).
- **L-4**: **agreement_hash 는 클릭랩 동의의 증거물**. 브라우저는 서버에서 받은 값을 사용자에게 표시·수락 후 `POST /v1/orders` 에 포함 전달. 이 값은 central/fulfillment 서버 감사 테이블에 기록되며 포털 측 재생성 불가.
- **L-5**: **Hospital admin token 은 v0.1 단일 사용 stub 이며, 실 파일럿 배포 전 CISO 리뷰가 필수**. 현재 config file 평문 전제는 **demo 한정**. v0.1.5 실 파일럿 시점에 **SSO / OIDC / 하드웨어 토큰** 중 택 1 마이그레이션. 이 제약은 `docs/marketing/proposal-summary-hospital-ko.md` "데모 vs 파일럿" 구분 섹션에 명시되어야 함 (Kyle 결정 §11-Q-Sec-1).
- **L-6**: **PIPA §28-8 "완전 익명정보 국외이전 안전조치"** — 포털이 내보내는 presigned URL 은 국외 버이어가 접근. 현 아키텍처 (central-ingest FR-56 rejected event 포함) 는 이를 만족하도록 설계됨 ("designed to align with"). 단 프리뷰 DICOM 공개 이슈 (§0.2-1) 는 별도 법률 자문 flag.
- **L-7**: **TCIA 공개 데이터 사용 고지** — Demo Home tile 과 데모 스크립트 장면 1 에 TCIA CC-BY 출처 고지 표기 필수. 다른 데이터인 것처럼 말하는 행위 금지 (리서치 `demo-pitch-references-radivault.md §8.1`).
- **L-8**: **병원 로고 무단 사용 금지** — Home tile 3 번째 "Hospitals contributing" 숫자 옆 로고 벽 **절대 넣지 말 것**. 파일럿 실 병원 MSA 서명 전까지 금지.
- **L-9**: **경쟁사 로고 사용 시 비교광고 준수** — competitive positioning 슬라이드 이미지가 포털에 실제 렌더되지는 않지만, 혹시라도 Docs 링크 내에서 접근된다면 @marketer 가 이미 처리한 `competitive-positioning-buyer-en.md` 포맷 준수.
- **L-10**: **Cookie Consent / GDPR 배너** — Buyer Portal 이 glob 접근이므로 v0.1.1 에 cookie consent 배너 필요. v0.1 은 CMP 미포함 — 이유: 인증된 사용자만 접근 + 트래킹 쿠키 미사용. 단 Home (public) 에는 "We use essential cookies for session. No tracking." 1 줄 Footer 고지 필수 (§11-Q-Legal-1).

### 6.3 감사 가능한 이벤트 기록

포털은 자체 감사 DB 를 갖지 않는다. 모든 주요 이벤트는 **업스트림 API 가 이미 기록**한다:

| 이벤트 | 업스트림 감사 위치 |
|---|---|
| Buyer 검색 | metadata-index `search_audit` |
| Buyer 주문 생성 | order-fulfillment `order_state_history` |
| Buyer presigned URL 발급 | order-fulfillment `download_event` |
| Buyer 주문 취소 | order-fulfillment `order_state_history` |
| Hospital Dashboard 로그인 | BFF pino 로그 (성공/실패 line) |
| Hospital Dashboard stats 조회 | 신규 `hospital_dashboard_audit` (§7 D-4, v0.1.1 optional) |

**FR-X-8**: BFF pino 로그는 `audit=true` flag 가 있는 line 만 filter 하면 포털 레벨 감사 이벤트 추출 가능해야 한다.

---

## §7 API contracts — Contract deltas (D-1 ~ D-5)

**Annex 성격**: 기존 metadata-index, order-fulfillment, central-ingest 에 **최소한의 델타**만 추가한다. 각 델타는 소유 서비스, 신규 엔드포인트, 요청/응답, FR/AC 번호, 기존 AC 영향도 명시. 이 형식은 `dev-spec-central-ingest §13 Annex` 포맷을 따른다.

### D-1: Study preview card (thumbnail 대체)

- **소유 서비스**: metadata-index (권장) 또는 portal BFF 자체 해결.
- **배경**: 리서치 §4.3 — 의료영상 마켓플레이스는 썸네일을 쓰지 않고 modality 색 배지로 대체. v0.1 포털은 **배지 전용 전략 채택 (옵션 a)**. 백엔드 변경 없음.
- **옵션 a (선택)**: 백엔드 변경 없음. 포털 FR-A-23 modality 배지 색 코드만 구현.
- **옵션 b (보류)**: `GET /v1/search/studies/{pseudo_study_uid}/preview-card` 신규 (stub) — placeholder 아이콘 + 핵심 메타 4 필드 + Open Graph 메타. 데모 URL preview 용. 투입 2 시간. v0.1.1 재검토.
- **FR 연결**: FR-A-23, FR-A-29.
- **AC 영향**: 기존 metadata-index AC 없음. 신규 AC-A-4, AC-A-23 해당.
- **결정**: **옵션 a 확정**. 옵션 b 는 §11 Kyle 결정 대기.

### D-2: Hospital aggregate stats API

- **소유 서비스**: **central-ingest** (권장, 이미 `study` 테이블 보유 + hospital_id bearer 인증 소유).
- **배경**: Hospital Dashboard B-1, B-2, B-4, B-5 가 요구하지만 기존 엔드포인트 없음.
- **신규 엔드포인트**: `GET /v1/hospital/me/stats`
  - **인증**: central-ingest 기존 hospital bearer token (`auth_token`) 재사용. scope 검증 — 토큰이 해당 hospital_id 와 연결됐는지.
  - **요청**: header `Authorization: Bearer <hospital_token>`. 쿼리 `?period=today|30d|12m` (기본 `12m`).
  - **응답** (envelope 계승):
    ```json
    {
      "data": {
        "hospital_id": "H001",
        "studies": {
          "today": 42,
          "cumulative": 12478,
          "monthly_12m": [
            {"year_month": "2025-05", "count": 980},
            ...
          ]
        },
        "gateway_health": {
          "status": "online",
          "last_sync_at": "2026-04-24T18:29:12Z",
          "last_sync_delta_seconds": 180
        },
        "as_of": "2026-04-24T18:32:00Z"
      }
    }
    ```
  - **에러**: 401 `ERR_AUTH_INVALID`, 403 `ERR_SCOPE_FORBIDDEN` (다른 hospital 토큰), 429 (기본 rate limit 재사용), 500.
- **신규 엔드포인트**: `GET /v1/hospital/me/orders?limit=10` — **order-fulfillment** 소유.
  - **인증**: central-ingest hospital bearer. order-fulfillment 는 해당 토큰을 central-ingest 에 verify 후 사용 (기존 auth_token 테이블 공유).
  - **응답**:
    ```json
    {
      "data": {
        "orders": [
          {
            "order_id_masked": "ord_5a3f",
            "n_studies": 12,
            "phase": "completed",
            "delivered_at": "2026-04-24T17:45:03Z"
          },
          ...
        ]
      }
    }
    ```
  - **쿼리 규칙**: 해당 hospital 이 공급한 study 가 포함된 주문만 조회. buyer 식별자 노출 금지.
- **FR 연결**: FR-B-9, FR-B-11, FR-B-13, FR-B-14.
- **AC 영향**: central-ingest AC-20 GRANT SELECT 재검증 필요 (신규 endpoint 가 ORM 읽기 수행). 회귀 테스트 필수.
- **구현 note**: v0.1 은 **central-ingest 에 집계 읽기 엔드포인트 2 개 추가**. 쿼리는 ORM aggregate + count distinct. 인덱스 추가 불필요 (월간 집계는 기존 study.created_at 인덱스 활용).

### D-3: Order FSM 5-phase mapping

- **소유 서비스**: order-fulfillment.
- **배경**: 내부 12-state → buyer-facing 5-phase. 리서치 §7.2.
- **옵션 a**: 서버측 응답 필드 추가 — order-fulfillment `GET /v1/orders/{id}` 및 `GET /v1/orders` 응답에 `buyer_phase` enum 필드 추가 (`accepted` · `fetching_from_hospital` · `preparing_download` · `ready_to_download` · `completed` · `cancelled` · `expired` · `failed`).
- **옵션 b**: 포털 클라이언트가 FR-A-43 표를 참고하여 `state` → `buyer_phase` 매핑.
- **결정**: **옵션 a 권장** (서버 truth 보호). 투입 30 분 (pydantic model 필드 추가 + unit test).
- **FR 연결**: FR-A-38, FR-A-42, FR-A-43, FR-B-14.
- **AC 영향**: order-fulfillment AC-13 (GET /v1/orders/{id} 응답 스키마) 갱신 필요. QA 회귀 재실행.

### D-4: Recent audit events (Hospital Dashboard)

- **소유 서비스**: central-ingest (audit_ingest_event 테이블 보유).
- **신규 엔드포인트**: `GET /v1/hospital/me/audit?limit=10`
  - **인증**: central-ingest hospital bearer.
  - **응답**:
    ```json
    {
      "data": {
        "events": [
          {
            "ts": "2026-04-24T18:30:12Z",
            "event_type": "ingest.accepted",
            "hash_short": "3f4a9b12",
            "detail_code": null
          },
          ...
        ]
      }
    }
    ```
  - **이벤트 타입 화이트리스트**: `ingest.accepted`, `ingest.rejected`, `upload.completed`, `anchor.recorded`, `order.delivered`.
- **FR 연결**: FR-B-15.
- **AC 영향**: 기존 audit_ingest_event 읽기 권한 (central_fulfillment_app role) 충분. 신규 권한 불필요.
- **구현 note**: 신규 SQL view `v_hospital_audit_recent` 권장 — WHERE hospital_id = $1 ORDER BY ts DESC LIMIT $2. PHI 금지 컬럼만 SELECT.

### D-5: Hospital admin authentication

- **소유 서비스**: **BFF 내부 (Next.js)** — 신규 서비스 X.
- **배경**: Hospital Dashboard 로그인용. 기존 central-ingest 의 `auth_token` 은 machine-to-machine (Gateway) 용이라 재사용 불가. v0.1 은 web UI 용 별도 토큰.
- **데이터 모델 (v0.1 config-file stub)**:
  - 환경변수 `RV_HOSPITAL_ADMIN_TOKENS` — JSON `{"hospital_id": "argon2id_hash", ...}`
  - 로그인 시 BFF 가 제출 토큰을 argon2id compare
  - 성공 시 쿠키 `rv_hospital_session` 에 `{hospital_id, exp}` JWT-like 구조 암호화 저장
- **BFF 엔드포인트**:
  - `POST /api/hospital/session` — `{hospital_id, admin_token}` → 쿠키 설정
  - `POST /api/hospital/session/delete` — 쿠키 파기
- **v0.1.5 파일럿 이관 경로**: SSO (Auth0 / Keycloak) 또는 하드웨어 키. 관련 dev-spec 분리.
- **FR 연결**: FR-B-1, FR-B-2, FR-B-3, FR-B-4.
- **AC 영향**: 없음 (BFF 내부).
- **보안 주의**: §6.2 L-5 참조. 프로덕션 `RV_HOSPITAL_ADMIN_TOKENS` 는 AWS Secrets Manager 또는 Vercel encrypted env 만 허용. git 저장 금지 (`.gitignore`).

### D-6 (참고): 기존 계약과의 호환성

- metadata-index `POST /v1/search/studies` — **변경 없음**. 포털은 그대로 사용.
- order-fulfillment `POST /v1/orders`, `GET /v1/orders{/id}`, `POST /v1/orders/{id}/cancel`, `POST /v1/orders/{id}/download-urls` — D-3 응답 필드 1개 추가 외 변경 없음.
- central-ingest 기존 엔드포인트 — **변경 없음**. D-2/D-4 는 신규 엔드포인트.

**Summary of deltas affecting other services**:

| Delta | 소유 | 변경 유형 | 투입 | Blocking? |
|---|---|---|---|---|
| D-1 | portal only | 프론트 전용 (옵션 a) | 0h | No |
| D-2 | central-ingest + order-fulfillment | 신규 endpoint 2개 | 1d | **Yes** (Hospital Dashboard blocker) |
| D-3 | order-fulfillment | response field 1개 추가 | 0.5d | **Yes** (Order tracker blocker) |
| D-4 | central-ingest | 신규 endpoint 1개 + SQL view | 0.5d | **Yes** (Hospital Dashboard blocker) |
| D-5 | portal BFF | 자체 구현 | 0.5d | No |

---

## §8 Seed pipeline

### 8.1 데이터셋 목록 (v0.1 권장)

| Collection | Modality | 추정 Study 수 | 라이선스 | 비고 |
|---|---|---|---|---|
| LIDC-IDRI (subset) | CT Chest | 100 | TCIA Restricted → CC-BY 변환 pending | 데모 핵심 (폐결절 인식 가능) |
| CPTAC-PDA (subset) | CT Abdomen | 50 | CC-BY | 희귀 abdomen 예시 |
| QIN-BRAIN-DSC-MRI (subset) | MR Brain | 100 | CC-BY | defacing 데모 (Kyle 결정 §11-Q-Data-2) |
| CBIS-DDSM (subset) | MG | 50 | CC-BY | 여성건강 대표 |
| Spine-Mets-CT-SEG (subset) | CT Spine | 100 | CC-BY | Kyle 도메인 배경 |
| **합계** | CT+MR+MG | **400** | 혼합 | 데모 핵심 |

※ 라이선스가 Restricted 인 경우 **데모 사용 전 Kyle 확인 필요** — `demo-pitch-references-radivault.md §8.1` 안티패턴 준수.

### 8.2 다운로드 스크립트 사양

**파일 경로**: `scripts/demo_seed/download_tcia.py`

```python
# 의사코드
def main(config_path: Path, cache_dir: Path):
    config = yaml.safe_load(config_path)
    for collection in config["collections"]:
        for patient_id in tcia.list_patients(collection["name"])[: collection["target_count"]]:
            for study_uid in tcia.list_studies(patient_id):
                target = cache_dir / collection["name"] / study_uid
                if (target / "_done.marker").exists():
                    continue  # idempotent skip
                downloaded = tcia.download_study(study_uid, target)
                sha256_manifest = compute_manifest(downloaded)
                (target / "_manifest.sha256").write_text(sha256_manifest)
                (target / "_done.marker").touch()
```

- Python 3.11+
- `tcia_utils` 패키지 또는 직접 REST 호출 (`requests`).
- 로그는 JSON line stdout + `logs/demo_seed_download_<ts>.log`.
- 실패 시 지수 백오프 5회, 최종 실패 study 는 `_failed.json`.

### 8.3 Gateway 주입 절차

1. Orthanc 기동 (docker-compose `orthanc` 서비스). 포트 4242 (DIMSE) + 8042 (REST).
2. `scripts/demo_seed/load_orthanc.py` — 캐시 DICOM 을 Orthanc 에 STOW-RS upload.
3. Gateway 설정 파일 `demo_gateway.yaml` 준비 — Orthanc 를 PACS source 로 지정, De-ID rules = Annex E Basic Profile, central URL = `http://central:8000`, hospital token = seed_hospital.py 가 생성한 값.
4. `gateway-admin run --once --config demo_gateway.yaml --batch-size 500` — Flow A 일회성 실행.
5. Gateway 가 De-ID → Central ingest 전체 파이프라인 통과.
6. 예상 소요: 100 MB/study × 400 study = 40 GB, 10 GbE 로컬 기준 30 분 내.

### 8.4 리셋 스크립트

**`scripts/demo_seed/reset.sh`**:
```bash
#!/usr/bin/env bash
set -euo pipefail
MODE="${1:-soft}"
case "$MODE" in
  soft)
    # DB truncate + staging clear, Orthanc + cache 보존
    docker-compose -f docker-compose-demo.yml exec postgres \
      psql -U postgres -d radivault -f /scripts/truncate_demo.sql
    docker-compose -f docker-compose-demo.yml exec minio \
      mc rm -r --force minio/radivault/staging/
    ;;
  hard)
    docker-compose -f docker-compose-demo.yml down -v
    rm -rf ./demo_data/cache
    ;;
  *)
    echo "Usage: reset.sh [soft|hard]" >&2
    exit 2
    ;;
esac
```

**`scripts/demo_seed/truncate_demo.sql`**:
```sql
TRUNCATE TABLE search_audit, download_event, order_state_history,
               order_outbox, transfer_job_dead_letter, transfer_job,
               order_item, "order" CASCADE;
-- study, hospital, buyer_api_key 은 보존 (재주입 비용 회피)
```

### 8.5 검증 체크리스트 (V-1 ~ V-8)

FR-S-11 참조. 각 항목 PASS/FAIL 결과는 `verify.py` 가 JUnit XML 또는 markdown report `demo_seed_verify.md` 로 출력.

---

## §9 Demo script outline (17분)

`docs/specs/demo-script-radivault.md` 내부에 상세. 본 dev-spec 은 skeleton 만 정의.

### 9.1 장면 표 (스토리보드 변형 A — Revenue Loop Proof)

| Scene | Time | 제목 | 화면 | 프레젠터 핵심 문장 | 자산 |
|---|---|---|---|---|---|
| 1 | 0:00–2:00 | Hook + Dual framing | 슬라이드 1 | "한국 의료영상 → 글로벌 AI. 투자자에겐 카테고리, 병원엔 정산 루트." | 피치덱 (external) |
| 2 | 2:00–5:00 | Architecture | 슬라이드 1 + Buyer Portal Home (A-1) | Zone 1/2/3 + 3 flows. 경쟁 비교 미니 표. | 슬라이드 + 포털 Home |
| 3 | 5:00–8:00 | Hospital Gateway live | **Hospital Dashboard (B-1..B-6)** + 터미널 (gateway status, de-id diff) | "이 환자 데이터는 지금 중앙으로 보내기 전, PHI 제거와 해시 기록이 완료됐습니다." | Hospital Dashboard + 터미널 2 개 |
| 4 | 8:00–11:00 | Buyer search & order | **Buyer Portal /search → /orders** (A-3 → A-5) | "구매자가 방금 척추 CT 500건 주문. 첫 정산 이벤트가 쌓입니다." | 포털 search + review modal |
| 5 | 11:00–13:30 | Order tracking & download | **Buyer Portal /orders/{id} + /downloads** (A-7, A-8) | "5단계 phase tracker 가 완료로 전환. 프리사인 URL 24시간 유효." | 포털 order detail + downloads |
| 6 | 13:30–15:30 | Hospital revenue tile | **Hospital Dashboard revenue tile (B-2)** | "이 병원 연 1만 스터디 공급 시 월 정산 ₩YY." | Hospital Dashboard 재방문 |
| 7 | 15:30–17:00 | Dual Ask | 슬라이드 1 | "$X 시드 + 첫 파일럿 병원 합류, 하나의 서명에 두 결정." | 피치덱 (external) |

### 9.2 Canned output 경로 맵

각 장면에 `public/demoop/canned/scene-{n}/` 폴더:

```
public/demoop/canned/
├── scene-2/
│   └── home-facets.json           # /api/search/facets-public 응답
├── scene-3/
│   ├── hospital-stats.json        # /api/hospital/me/stats
│   ├── hospital-gateway-health.json
│   ├── hospital-orders.json
│   └── hospital-audit.json
├── scene-4/
│   ├── search-studies-page1.json  # POST /api/search/studies
│   ├── search-facets.json
│   └── order-create-success.json  # POST /api/orders 성공 응답 (202)
├── scene-5/
│   ├── order-detail-ready.json    # GET /api/orders/{id} ready_for_download
│   └── download-urls.json         # POST /api/orders/{id}/download-urls
└── scene-6/
    └── hospital-stats-after.json  # 장면 4 주문 반영 증분
```

### 9.3 실패 런북

| 증상 | 첫 5초 액션 | 복구 | 프레젠터 멘트 |
|---|---|---|---|
| API 호출 hang (>3초) | Ctrl+Shift+D → "Canned overlay" 토글 ON | 다음 장면 진행 | "실 운영 환경에선 2초 이내. 데모 캐시로 보여드립니다." |
| Hospital Dashboard tile 전체 error | Ctrl+R (soft reset) 또는 Ctrl+Shift+D | 60초 소요. 그 동안 설명 진행 | "폴링 주기가 돌아오는 60초 동안 설명을 이어가겠습니다." |
| 포털 500 / Next.js 크래시 | Ctrl+8 (Kyle 사전 정의) → localhost:3000 재시작 | 15초 | "잠시 재시작하겠습니다. 운영 SLO 는 < 1s recovery 목표입니다." |
| PHI 의심 장면 (합성 데이터 중 실제처럼 보임) | **즉시 브라우저 Cmd+W** | 사전 스크린샷 또는 슬라이드로 전환 | "이건 TCIA 공개 데이터입니다. 실 PHI 는 이 환경에 없습니다." |
| 네트워크 완전 차단 | 녹화본 MP4 플레이 | 즉시 재생 | "네트워크 이슈로 녹화본으로 전환. 동일 환경에서 사전 캡처된 러닝입니다." |

### 9.4 리허설 체크리스트

- R-1: 2 회 이상 드라이런 (녹화 포함).
- R-2: 각 장면 실제 소요 시간 측정 → 목표 ±2 분 이내.
- R-3: Canned overlay 토글 3 초 이내 (손 기억).
- R-4: 장면 3 Hospital Dashboard tile 6 개 전부 로드 완료 10 초 이내.
- R-5: 장면 4 search → review modal → confirm → order detail 자동 이동 15 초 이내.
- R-6: 장면 5 downloads 페이지 만료 카운트다운 정상 렌더.
- R-7: Q&A FAQ 20 건 답변 연습.

---

## §10 Non-functional requirements (상세)

§6 에서 정의. 추가 사항 없음. (요건 중복 제거.)

---

## §11 Open questions for Kyle

리서치 `demo-pitch-references-radivault.md §9` 30+건 중 **planner 가 합리적 기본값을 수용할 수 없는 항목만** 여기에 모은다. 나머지는 §0.1 "합리적 기본값"으로 수용했다.

### 11.1 법무·컴플라이언스 (Blocking for production, Non-blocking for demo)

- **Q-Legal-1**: TCIA 데이터 사용 시 **CC-BY attribution 문구** — Home tile 풋터 "Data powered by TCIA CC-BY" 형태 충분한가, 별도 약관 페이지 필요한가? (법률 자문 flag)
- **Q-Legal-2**: Buyer Portal Home footer 에 "We use essential cookies for session. No tracking." 1 줄 고지 충분한가, GDPR CMP 배너 필요한가? (L-10)
- **Q-Legal-3**: Hospital Dashboard 의 "시뮬레이션 — v0.2 정산 대기" 문구가 **법적 disclaimer** 로 충분한가? 한국 금융/회계 규제상 추가 면책 필요한가? (외부 변호사 자문 권장)
- **Q-Legal-4**: 포털 도메인 `portal.radivault.io` vs `buyer.radivault.io` — 한국 법인 vs 미국 법인 도메인 분리 전략에 영향 있는가? (데모 이후 결정 가능)

### 11.2 데모 콘텐츠·연출 (D-day 전 blocking)

- **Q-Demo-1**: Seed 데이터셋 라이선스 — LIDC-IDRI 가 TCIA Restricted 인 경우 CC-BY 대체 컬렉션은? (§8.1)
- **Q-Demo-2**: Hospital Dashboard B-2 revenue tile 의 기본값 — unit_price $5 vs Kyle 결정값? hospital_share_pct 35% vs ? 환율 1,350 원/USD 하드코딩 OK?
- **Q-Demo-3**: Hospital Dashboard B-3 map highlight region — 데모 시연용 가상 병원 위치 (예: "서울 강남", "대전") 확정?
- **Q-Demo-4**: 장면 7 Ask 슬라이드 시드 ask 금액 — Segmed Series A $10.4M 참조이지만 RadiVault 시드는 얼마로 제시? (피치덱 담당)
- **Q-Demo-5**: 데모 녹화 백업본 저장 경로 3 곳 (로컬 / USB / 클라우드) — 클라우드 어디? (Google Drive vs Dropbox vs 내부 S3)

### 11.3 UX 결정 (Non-blocking, 있으면 좋음)

- **Q-UI-1**: 다크 모드 — v0.1 라이트만 (§0.2-7). shadcn 토큰 덕에 1일 추가 투입으로 가능. 포함? (의료영상 업계는 다크 권장)
- **Q-UI-2**: Buyer Portal 한국어 i18n — v0.1 영어만 (§0.2-5). 2일 추가 투입. 포함?
- **Q-UI-3**: Hospital Dashboard 월별 bar chart 12 개월 vs 6 개월? 12 개월이면 초기 6 개월 데이터 없음.
- **Q-UI-4**: 검색 결과 테이블 row 상세 보기 — drawer 방식 (FR-A-24) vs 별도 페이지 route?

### 11.4 기술·보안 (Blocking for v0.1.5 파일럿, Non-blocking for demo)

- **Q-Tech-1**: 호스팅 — Vercel (권장, BFF 간편) vs 자체 docker-compose (기존 스택 일관)? Vercel 은 한국 리전 부재 (edge) — PIPA 고려?
- **Q-Tech-2**: BFF 세션 암호화 라이브러리 — iron-session vs `@auth/core` vs 자체 AES-GCM? iron-session 권장 (소규모, Next.js 공식 권장 중 하나).
- **Q-Sec-1**: Hospital admin token v0.1.5 이관 경로 — SSO (Auth0/Keycloak) vs 하드웨어 토큰 (YubiKey) vs 단순 rotated long-lived token? CISO 리뷰 필요 (L-5).
- **Q-Tech-3**: D-2/D-4 엔드포인트 — central-ingest 단독 vs order-fulfillment 분담? 현 스펙은 "central-ingest 에 집계 읽기 추가" 권장. 이견?
- **Q-Tech-4**: Demo Operator Mode 활성 URL 쿼리 플래그 `?demoop=1` 이름 (혼선 방지용 대안 `?rehearsal=1`?) 및 `DEMOOP_TOKEN` rotation 정책.

### 11.5 브랜딩 (리서치 Q-브랜드-1 연계)

- **Q-Brand-1**: Buyer Portal logo — 텍스트 마크 "RadiVault" (v0.1 임시) vs designer 가 제공하는 심볼? (@designer 에게 design-spec 단계에서 결정 요청)
- **Q-Brand-2**: 포털 primary 컬러 — Tailwind slate + blue-600 기본 vs Kyle 선호 팔레트?
- **Q-Brand-3**: 5 컴포넌트 (Gateway/Central/Search/De-ID/Fulfillment) 를 포털에서는 "Platform" 단일로 묶을지, 별 섹션으로 표기?

---

## §12 Risks and mitigations

| ID | 리스크 | 영향 | 발생 가능성 | 완화 |
|---|---|---|---|---|
| R-1 | 라이브 데모 네트워크/Docker 실패 | 치명적 (SC-1 위반) | 중 | Hybrid 모드 + Canned overlay + 녹화 백업 3곳 (§9.3) |
| R-2 | PHI 의심 화면 노출 | 치명적 (신뢰 즉시 소멸) | 낮음 (합성/TCIA 사용) | V-6 샘플링 + 사전 검수 + 즉시 Cmd+W 런북 |
| R-3 | 포털 HTTP 500 / Next.js 크래시 | 중 | 중 | localhost:3000 재시작 단축키 + 장면 순서 조정 가능 |
| R-4 | D-2/D-4 엔드포인트 미완 | 높음 (Hospital Dashboard blocker) | 중 | Dev sprint Week 1 최우선. Mock fallback (canned JSON) 준비 |
| R-5 | TCIA 다운로드 실패 (rate limit, URL 변경) | 중 | 중 | 지수 백오프 5회 + failed.json 리포트 + 대체 컬렉션 2순위 보유 |
| R-6 | PIPA 법률 자문 미완료 | 낮음 (데모 용도, 파일럿 blocker) | 높음 | Demo disclaimer ("designed to align with PIPA §28-8"), 프리뷰 DICOM 포함 결정 보류 |
| R-7 | Vercel 한국 리전 부재 → 지연 | 낮음 (데모는 로컬 docker-compose) | 높음 (v0.1.5 파일럿) | 데모는 로컬 docker-compose 고정. v0.1.5 는 한국 리전 자체 호스트 고려 |
| R-8 | 대표님 질문이 Q&A 20건 범위 초과 | 낮음 | 중 | 디자이너가 FAQ 확장 + "좋은 질문입니다, 후속 미팅에서 자료로 돌려드리겠습니다" 런북 |
| R-9 | 1인 시연자 피로 (17분 집중) | 중 | 중 | 리허설 2 회 이상. 장면 3·4·5 사이 10초 breath 마크. |
| R-10 | agreement_hash stub 이 법적 구속력 오해 소지 | 낮음 | 낮음 | Review modal 에 "v0.1 stub — MSA is handled offline" 명시 (FR-A-31) |
| R-11 | 경쟁사 (Segmed/Gradient) 로고 표기 비교광고 위반 | 낮음 | 낮음 | 포털 내 노출 금지. 피치덱만 (marketer 책임). |
| R-12 | Demo Operator Mode 토큰 유출 → 외부에서 Canned 오버레이 조작 | 중 | 낮음 | `DEMOOP_TOKEN` 프로덕션 미설정이면 `?demoop=1` 무시 (FR-D-5) |

---

## §13 Milestones (2.5~3주 분해)

15 영업일 기준 (월~금). 총 투입 ≈ dev 10 + design 3 + QA 2 = 15 man-days. 1 명 전담 시 3 주.

### Week 1 (D1~D5) — Foundation & 계약 델타

| Day | 작업 | 담당 | 선행 | 산출물 |
|---|---|---|---|---|
| D1 | Monorepo scaffold (Next.js 14 + TS + Tailwind + shadcn/ui init) | dev | — | `apps/portal/` 초기 커밋, README |
| D1 | demo-script-radivault.md 스켈레톤 (§9 표) | planner (본 dev-spec 직후 patch) | — | `docs/specs/demo-script-radivault.md` v0.1 |
| D2 | Contract delta D-2, D-4 — central-ingest 신규 엔드포인트 2개 + SQL view | dev (backend) | central-ingest 회귀 통과 | PR to central-ingest, Alembic revision 0005 (필요 시) |
| D3 | Contract delta D-3 — order-fulfillment buyer_phase 필드 추가 | dev (backend) | — | PR to order-fulfillment, unit test 1 건 |
| D3~D4 | Seed pipeline — download_tcia.py + load_orthanc.py + seed_config.yaml 첫 작성 | dev (scripts) | — | `scripts/demo_seed/*`, 로컬 100 study 주입 검증 |
| D4 | BFF 기본 구조 — session 쿠키 (iron-session), route handlers scaffold, pino 로그 | dev (portal) | D1 | `apps/portal/app/api/*` |
| D5 | Shell 컴포넌트 — Top nav, Profile dropdown, Empty/Loading/Error | dev (portal) | D1 | shadcn 기반 컴포넌트 5종 |
| D5 | Designer 킥오프 — design-spec-buyer-portal-demo.md 작성 시작 | designer | 본 dev-spec | design-spec draft v0.1 |

### Week 2 (D6~D10) — 화면 구현

| Day | 작업 | 담당 | 산출물 |
|---|---|---|---|
| D6 | A-1 Home + A-2 Signin | dev (portal) | FR-A-1~10 |
| D7 | A-3 Search (3-pane, 테이블, 패싯, cohort sidebar) | dev (portal) | FR-A-11~23 |
| D7 | Seed pipeline — inject_all.sh 완주, 400 study 주입 검증 (V-1..V-8) | dev (scripts) | AC-S-1~4 |
| D8 | A-4 Study detail drawer + A-5 Review order modal | dev (portal) | FR-A-24~36 |
| D9 | A-6 Orders list + A-7 Order detail + 5-phase tracker | dev (portal) | FR-A-37~49 |
| D10 | A-8 Downloads + A-9 Account | dev (portal) | FR-A-50~64 |

### Week 3 (D11~D15) — Hospital Dashboard, Demo mode, QA, 리허설

| Day | 작업 | 담당 | 산출물 |
|---|---|---|---|
| D11 | Hospital Dashboard B-1~B-4 (signin, studies, revenue, map, gateway) | dev (portal) | FR-B-1~13 |
| D12 | Hospital Dashboard B-5~B-6 + 한국어 i18n | dev (portal) | FR-B-14~18 |
| D12 | Demo Operator Mode 구현 | dev (portal) | FR-D-4~9 |
| D13 | Canned output 파일 캡처 + 사전 녹화 1차 | dev + Kyle | `public/demoop/canned/*`, rehearsal1.mp4 |
| D14 | QA — 전체 AC 체크, ruff + playwright e2e 3 시나리오 | QA agent | qa-report-buyer-portal-demo.md |
| D15 | Fix round + 최종 리허설 2회 + 녹화 백업 3곳 분산 | dev + Kyle | demo ready lock |

### 크리티컬 패스

```
D1 scaffold → D2 D-2/D-4 → D4 BFF → D6 A-1 → D7 A-3 → D8 A-5 → D9 A-7 → D10 A-8 → D11 B-1~4 → D12 D.Op → D13 Canned → D14 QA → D15 Rehearsal
```

### 버퍼

- 15 일 중 2 일 (D13, D15) 는 버퍼 겸용. 총 17~18 일 하드 필요 시 D-day 2 일 앞당기거나 §11 Q-UI-1 (다크) / Q-UI-2 (한국어) 제외로 1 일 절감.

### 병렬화

- D5~D10 사이 @designer 는 design-spec-buyer-portal-demo.md 를 병렬 작성.
- Week 2~3 중 @marketer 는 피치덱 PPT 작성 병렬.
- Week 3 QA 는 @qa 서브에이전트 1 session.

---

## §14 Annex — Contract deltas (D-1 ~ D-5 요약)

§7 본문의 요약. `dev-spec-central-ingest §13 Annex` 포맷 준수.

### Annex A — Delta table

| ID | 소유 서비스 | 변경 유형 | 영향 AC | 투입 | Risk |
|---|---|---|---|---|---|
| D-1 | portal only | 프론트 배지 전략 (옵션 a) | AC-A-4, AC-A-23 | 0h | Low — 순수 클라이언트 |
| D-2 | central-ingest + order-fulfillment | 신규 GET `/v1/hospital/me/stats`, `/v1/hospital/me/gateway-health`, `/v1/hospital/me/orders` | central AC-20 재확인, order-fulfillment 회귀 | 1d | Med — auth scope 검증 재사용 |
| D-3 | order-fulfillment | 응답 필드 `buyer_phase` 추가 | order-fulfillment AC-13 갱신 | 0.5d | Low — additive |
| D-4 | central-ingest | 신규 GET `/v1/hospital/me/audit` + SQL view | central AC-20 재확인 | 0.5d | Low — read-only |
| D-5 | portal BFF | config-file stub auth | 없음 | 0.5d | Med — 보안 L-5 |

### Annex B — 기존 dev-spec 영향

- **dev-spec-central-ingest**: D-2/D-4 엔드포인트 추가 필요 — 해당 dev-spec §7 API 계약에 GET `/v1/hospital/me/*` 3~4 개 추가. Alembic revision 0005 (SQL view `v_hospital_audit_recent`) 선택.
- **dev-spec-order-fulfillment**: D-3 응답 필드 `buyer_phase` 추가. design-spec-order-fulfillment §2 envelope 예시 갱신.
- **dev-spec-metadata-index**: D-1 옵션 a 선택 시 **변경 없음**. 옵션 b 시 신규 `GET /v1/search/studies/{uid}/preview-card`.
- **dev-spec-gateway-agent**: **변경 없음**. Gateway 는 Hospital Dashboard 의 last_sync 소스로만 간접 영향 (central-ingest 가 집계).

### Annex C — 기술 스택 확정 제안 (Kyle 승인 필요)

본 dev-spec 은 Buyer Portal + Hospital Dashboard 용으로 다음 스택을 **확정 제안**한다 (ARCHITECTURE.md §9 TBD 해소 대상):

| 레이어 | 제안 | 근거 | 대안 |
|---|---|---|---|
| Framework | Next.js 14 App Router | 리서치 `buyer-portal-ux-competitive.md §9`, BFF 패턴 네이티브 지원, Vercel 배포 원클릭 | Remix (SSR 동등), SvelteKit (번들 작음) |
| Language | TypeScript 5+ | 팀 표준, shadcn/ui 의 ts-first | JavaScript (v0.1 에서 비권장) |
| Styling | Tailwind CSS 3.4 + shadcn/ui | Gen3 3-pane 레이아웃 구현 용이, 디자이너 토큰 일관 | Chakra UI, MUI |
| Data fetching | TanStack Query 5 | 폴링·캐시·백오프·SSR 모두 지원 | SWR (유사), Apollo (과도) |
| Charts | Recharts 2 | Hospital Dashboard bar chart, 한국 지도 SVG 호환 | Visx, Chart.js |
| Session | iron-session v8 | Next.js 공식 권장 중 하나, 간결 | @auth/core (NextAuth, 과도) |
| Hashing | argon2 (npm `argon2`) | hospital admin token 해시. 업스트림과 동일 알고리즘 | bcrypt (덜 권장) |
| Logging | pino + pino-pretty (dev) | Node 표준, JSON line, Vercel 호환 | winston (덜 권장) |
| Testing | Vitest + Playwright | Vitest — 유닛, Playwright — e2e AC-A/B | Jest (느림), Cypress (Playwright 대체 가능) |
| i18n | next-intl | App Router 지원, 서버 컴포넌트 호환 | next-i18next (pages router) |
| Deployment | 데모: 로컬 docker-compose (`portal` 서비스 추가). 파일럿: Vercel (검토) | 한국 리전 부재 이슈는 §11 Q-Tech-1 | 자체 VPS (오버헤드) |

**이 스택 확정은 ARCHITECTURE.md §9 의 "Zone 3 구매자 글로벌 — Web Portal: TBD" 항목을 해소한다.** 대응 PR: ARCHITECTURE.md §9 갱신 제안.

### Annex D — Out-of-scope 변경 제안 (v0.1.1+)

- metadata-index `POST /v1/search/studies/preview-cards` — 배치 썸네일 메타 (D-1 옵션 b 승격 시).
- order-fulfillment 이메일 notifications + webhooks — v0.1.1 backlog 이월.
- Hospital Dashboard opt-out management — metadata-index scope_json 집행 구현 뒤 v0.1.1.
- Buyer Portal saved cohorts — metadata-index v0.1.1 backlog.

---

## §15 Change history

| 버전 | 날짜 | 작성자 | 변경 |
|---|---|---|---|
| 0.1 | 2026-04-24 | @planner (Claude Opus 4.7) | 최초 작성. Buyer Portal + Hospital Dashboard + Demo Seed Pipeline + Demo Script Package 4 구성요소 단일 feature slug 로 통합. FR 80+ (A-71 + B-18 + S-15 + D-9 + X-8), AC 47 (A-17 + B-13 + S-6 + D-6 + X-5), Contract deltas D-1~D-5, 2.5~3주 15일 분해, Kyle 결정 오픈 퀘스천 18건, Risk 12건. 스토리보드 변형 A + Live+Canned Hybrid + TCIA 400 study + 영어 Buyer / 한국어 Hospital / DICOM 뷰어 제외 / 가격 마스킹 기본값 수용. |

---

### NEXT_STEP

- **완료 산출물**: `docs/specs/dev-spec-buyer-portal-demo.md` v0.1 Draft
- **즉시 후속 (이 dev-spec 직후 본 세션에서)**:
  - Planner patch: `docs/specs/demo-script-radivault.md` v0.1 skeleton 작성 (§4.D FR-D-1~3 충족). 본 세션 범위 내에서 처리 가능.
- **제안 다음 단계**:
  - **@designer** — `design-spec-buyer-portal-demo.md` 작성 (동일 feature slug 유지). 우선 Week 1 D5 착수: 디자인 토큰, Top nav, Search 3-pane, Hospital Dashboard 6-tile, Demo Operator Mode 배지 스타일 5 화면 midfi + 에러·Empty·Loading 상태 가이드.
  - **@developer (backend)** — D-2, D-3, D-4 contract delta 3 건을 별 PR 로 central-ingest / order-fulfillment 에 선-반영. Week 1 D2~D3 크리티컬 패스.
  - **@marketer** — 피치덱 PPT placeholder 구조 (장면 1, 2, 7 슬라이드) 초안. §9 장면 표 참조. 병렬 가능.
- **아키텍처 영향**: **ARCHITECTURE.md §9 (기술 스택 TBD) 갱신 필요** — Annex C 스택 제안 수용 시 "Zone 3 Web Portal" 행 추가 (Next.js 14 + BFF + iron-session). Kyle 승인 후 별 PR.
- **PRD 영향**: **prd.md §4.3 "구매자 포털 (Phase 2)"** 재분류 필요 — 본 dev-spec 은 v0.1.5 로 분리 승격. 리서치 `demo-pitch-references-radivault.md §10` PRD 갱신 제안 3·4 참조.
- **Kyle 결정 필요 사항**:
  1. §11.1 Q-Legal-1~4 (TCIA attribution, cookie consent, revenue disclaimer, 도메인 분리 전략)
  2. §11.2 Q-Demo-1~5 (seed 데이터셋 라이선스 확정, revenue tile 숫자, map region, 시드 ask 금액, 녹화 클라우드)
  3. §11.3 Q-UI-1~4 (다크 모드, 한국어 Buyer, 12m vs 6m chart, drawer vs page)
  4. §11.4 Q-Tech-1~4 + Q-Sec-1 (호스팅, session lib, hospital auth 이관 경로, demoop flag 이름)
  5. §11.5 Q-Brand-1~3 (로고, primary color, 5 컴포넌트 외부 표기)
  6. Annex C 기술 스택 확정 수용 여부 (ARCHITECTURE.md §9 갱신 전제)
- **D-day 역산**: Kyle 이 미팅 날짜 확정 후 **최소 3주 전** 본 dev-spec 승인 필요. 그보다 늦으면 Week 3 리허설 버퍼 소실 → R-9 악화.
