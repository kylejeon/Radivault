# 디자인 명세 — Buyer Portal + Hospital Dashboard + Demo Kit v0.1 MVP (웹 UI · 데모 연출 · 시각 디자인 시스템)

> **Status**: Draft v0.1 · **Feature slug**: `buyer-portal-demo` · **Last updated**: 2026-04-24
> **작성자**: @designer (Claude Opus 4.7)
> **근거 (필수 선행)**:
> - [dev-spec-buyer-portal-demo](./dev-spec-buyer-portal-demo.md) — 본 디자인의 **유일한 source of truth** (§3 화면 · §4 FR 120+ · §5 AC 47 · §7 계약 델타 D-1..D-5 · §9 장면 표)
> - [demo-script-radivault](./demo-script-radivault.md) — 본 세션에서 v0.2 로 갱신 (영어 대사 · FAQ 20 상세 · 연출)
> - [research/demo-pitch-references-radivault](../research/demo-pitch-references-radivault.md) — 스토리보드 변형 A, Live+Canned Hybrid, 금기 23건, 금기 코드 6건
> - [research/buyer-portal-ux-competitive](../research/buyer-portal-ux-competitive.md) — Gen3 3-pane, must-have §10, Hospital Dashboard 6-tile §12
> **근거 (톤·포맷 상속)**:
> - [design-spec-metadata-index](./design-spec-metadata-index.md) — envelope · 에러 5-field 테이블 · Runbook 포맷 · buyer DX 문맥
> - [design-spec-order-fulfillment](./design-spec-order-fulfillment.md) — 12-state FSM DX · 에러 코드 · presigned URL UX · 5-phase plain-English
> - [design-spec-central-ingest](./design-spec-central-ingest.md) — JSON 로그 스키마 · 5-field 에러 테이블 포맷
> - [design-spec-gateway-agent](./design-spec-gateway-agent.md) — ASCII status UI · 디자인 토큰 CSS 변수 서술
> - [UI Guide (placeholder)](../UI_GUIDE.md) — 신뢰/밀도/감사가시성/이중언어/WCAG 2.1 AA 원칙 상속. 본 문서가 UI_GUIDE 의 §2 "디자인 원칙" 을 처음으로 실체화한다.

---

## §0 Scope and platform

### 0.1 디자인 대상 표면

본 design-spec 은 RadiVault 6번째 feature `buyer-portal-demo` 의 UI/UX 명세다. 이전 5개 feature 가 전부 "backend service · CLI · 로그" 였던 반면, 본 기능은 **최초의 GUI 레이어**다. 따라서 본 문서는 다음 6 영역을 정의한다:

1. **Buyer Portal Web UI (영어)** — 화면 A-1..A-9 (`/`, `/signin`, `/search`, `/search?study=...`, `/search → modal`, `/orders`, `/orders/{id}`, `/orders/{id}/downloads`, `/account`).
2. **Hospital Dashboard (한국어)** — 화면 B-1..B-6 (`/hospital/{gateway_id}` 단일 페이지 6-tile).
3. **공통 디자인 시스템** — 디자인 토큰 (색상 · 타이포 · 간격 · 그림자 · 라운드), shadcn/ui 기반 컴포넌트 인벤토리 10~20종.
4. **상태 taxonomy** — Loading · Empty · Error (4xx / 5xx / network / PHI suspect) · No-permission · Partial-failure · Stale — 각 화면별 매핑.
5. **Demo Operator Mode UX** — `?demoop=1` 배지 · Ctrl+1..7 shortcut · Canned overlay · Reset 버튼 · Scene progress.
6. **Demo Script 갱신 (별 파일)** — `demo-script-radivault.md` v0.2. 영어 대사, 연출 지침 (청중 pause/eye contact/질문 유도), FAQ 20 건 상세 답변, 실패 런북 5 건 세부화, 리허설 체크 R-1~R-9 구체화.

### 0.2 플랫폼 · 비대상

- **플랫폼**: **Web, desktop browser only**. 근거: dev-spec §0.2-6.
  - 타깃 브라우저: Chrome 120+, Safari 17+, Edge 120+ (Firefox best-effort, IE 미지원).
  - 해상도: 1280×720 min, **1920×1080 권장 (데모 기준)**, 4K scaled OK.
- **네이티브/모바일 아님**: 반응형은 tablet (≥ 768px) 까지 best-effort, mobile (< 768px) 은 "please use desktop" 1 페이지로 폴백 (§11 상세).
- **DICOM 뷰어 아님**: OHIF/Cornerstone.js 임베드는 v0.2 (dev-spec §0.2-1).
- **디자인 토큰 저장소는 본 문서 + `/apps/portal/styles/tokens.css`**. Figma 원본 · PNG 목업 · 스프라이트 SVG 는 v0.1.5 때 자산 트랙으로 분리.
- **이 문서는 코드를 포함하지 않는다** — CSS 변수 이름·권장 값만 제시. 구현은 @developer 가 shadcn init + tailwind.config 로 수행.

### 0.3 기술 스택 (dev-spec Annex C 승계 확정 제안)

| 레이어 | 제안 | 디자인 관점 이유 |
|---|---|---|
| Framework | Next.js 14 App Router | 서버컴포넌트로 BFF route handler 분리 → API key 브라우저 누출 차단 (L-2) |
| Styling | Tailwind CSS 3.4 + **shadcn/ui** (Radix + CVA 기반) | 토큰 기반 · 접근성 기본 · 다크모드 즉시 확장 가능 |
| Icons | `lucide-react` (shadcn 표준) | 500+ 아이콘, 1 stroke-width 일관, modality 배지와 조화 |
| Charts | Recharts 2 | B-2 bar chart · Home 3-tile sparkline 호환 |
| Data fetching | TanStack Query 5 | 폴링·캐시·백오프 내장 (Order tracker 5s, Dashboard 60s) |
| i18n | next-intl | `messages/en.json`, `messages/ko.json` 분리, 서버컴포넌트 호환 |
| Fonts | **Inter** (영어) + **Pretendard** (한국어) self-hosted woff2 | 의료 산업 관례 "중립적 sans", Pretendard 는 한국어 가변 대응 |
| Session | iron-session v8 | dev-spec FR-A-4, AC-A-3 (HttpOnly/Secure/SameSite=Lax) 그대로 충족 |

본 design-spec 은 위 스택을 디자인 결정의 제약으로 수용한다.

---

## §1 디자인 원칙

UI Guide §2 플레이스홀더를 본 feature 로 **처음 실체화**한다. 아래 7 원칙은 모든 화면·컴포넌트·카피에 우선한다.

### 1.1 신뢰 우선 (Trust-first)

- **의료 데이터 플랫폼** — 색채 채도 낮춤 (pastel/neon 금지). Primary 는 중성 슬레이트 + 차분한 파랑. Hospital Dashboard 는 **한국 의료 톤에 맞게 더 낮은 채도 + 더 차분한 파랑** (Pantone 7462C 계열 근접).
- 아이콘은 outline 1-stroke only. filled/gradient 금지. 근거: Segmed/Gradient/Truveta 공통 관례 (리서치 `demo-pitch-references-radivault.md §2.6`).
- 스큐어모피즘·뉴모피즘·글래스모피즘 금지.

### 1.2 데이터 밀도 (Information-dense)

- 연구자·AI 엔지니어가 주 사용자 → 표·숫자·메타 필드를 많이 보여주되 **계층 구조로 조직**.
- Search 결과 테이블 행 높이 44px (shadcn 기본 48px 대비 타이트). padding 12/16px.
- 불필요한 장식 (배경 이미지, 큰 빈 영역) 배제. Home 의 Hero 는 예외적으로 breathing space 유지.

### 1.3 감사 가능성 시각화 (Auditable at a glance)

- Hospital Dashboard B-6 Audit tile — 해시 8자 + 타임스탬프 + 이벤트 타입 = 1 라인. 해시 색상은 mono gray (정보 전용, 링크 아님).
- Buyer Portal 주문 상세 (A-7) 의 "View details" 드로어에 내부 12-state 타임라인 노출 → SRE 수준 투명성.
- "마지막 업데이트 HH:MM" 문자열이 모든 폴링 타일 우상단에 **반드시** 표시.

### 1.4 이중언어 (Buyer=en / Hospital=ko 분리)

- Buyer Portal 영어 전용 (dev-spec §0.2-5). 한국어 탭/토글 없음. 이유: 구매자는 글로벌 AI 기업.
- Hospital Dashboard 한국어 전용. 영어 토글 없음. 이유: 병원 경영진 한국어 네이티브.
- 양쪽 모두 에러 코드는 `message_ko` + `message_en` 동반 (design-spec-metadata-index §5 envelope 계승) — 브라우저 locale 에 따라 둘 중 하나를 렌더.
- 한국어는 영어 대비 평균 30% 짧음 → 버튼 너비는 **영어 기준 min-width 계산 + 한국어는 centering 로 자연스럽게 축약** (별 width 지정 불필요).
- 공통 Top nav 레이블은 Buyer 쪽만 존재 (영어). Hospital 쪽은 단일 페이지 (네비 없음).

### 1.5 접근성 (WCAG 2.1 AA)

- 모든 텍스트·아이콘 대비 **4.5:1 이상** (large text 3:1). 아래 팔레트는 이 기준 검증됨 (§2.1 주석).
- 키보드 전수 탐색 가능 (`Tab` / `Shift+Tab` / `Enter` / `Esc`). Focus ring 은 2px offset + primary-500.
- ARIA label 의무 영역: `<EmptyState>`, `<ErrorBanner>`, `<PhaseStepper>`, `<MapHeatmap>`, `<TileCard>`, modality 배지 (색상만 의존 금지 — 텍스트 동반).
- 스크린리더: 폴링 타일은 `aria-live="polite"`, 에러 배너는 `aria-live="assertive"`.
- 색맹 대응 — modality 배지는 색 + 2자 알파벳 (`CT`, `MR`, `CR`, `MG`, `US`, `PT`). 색 단독으로 의미 전달 금지.

### 1.6 5-phase 축약 원칙 (12-state → 5-phase)

- 내부 FSM 은 12 상태 (order-fulfillment) 지만 **buyer 는 5 phase 만** 본다. 리서치 `buyer-portal-ux-competitive.md §7.2` 관찰: 12-state 직접 노출 시 "왜 이리 많냐" 혼란 → 신뢰 하락.
- 매핑은 dev-spec FR-A-43 에 고정. 본 design-spec 은 phase 의 **영/한 레이블 · 색 · 아이콘 · ETA 톤** 을 §5.A-7 에 정의.
- 5-phase 는 `<PhaseStepper>` 컴포넌트로 재사용 (Buyer A-7, Hospital B-5 양쪽).

### 1.7 PIPA · 출처 고지 (Korean medical privacy + provenance)

- Hospital Dashboard B-2 revenue tile 의 "시뮬레이션 — v0.2 정산 대기" 라벨은 **footer 고정 · 제거 불가 · 폰트 기본 색상 대비 4.5:1** — 법적 disclaimer 기능 (dev-spec L-3, AC-B-5).
- TCIA 출처 고지 — Buyer Portal Home footer `"Data demo powered by TCIA CC-BY collections. Production data from Korean hospital partners under MSA."` (§5.A-1).
- 병원 로고 벽 금지 (dev-spec L-8).
- PHI 의심 데이터는 화면에 렌더되지 않도록 디자인 — pseudo_study_uid 는 8자 잘림만 노출, 전체는 clipboard copy tooltip 으로.

---

## §2 디자인 토큰

CSS 변수 규약 (실제 파일 `apps/portal/styles/tokens.css` 권장). 값은 예시 · Kyle/디자이너 승인 후 확정.

### 2.1 색상 팔레트

**두 서피스 공통 톤 (Buyer + Hospital)** — 의료 신뢰 기조는 동일하게 유지한다. Buyer 와 Hospital 의 차별화는 **primary 계열 hue 시프트 + 중립색 warm/cool 차이** 로만 표현 (대시보드를 보는 순간 "다른 제품"이 아닌 "다른 모드" 인상).

```
/* Neutrals — shadcn slate-scale 베이스 */
--color-neutral-50:  #f8fafc;   /* page bg */
--color-neutral-100: #f1f5f9;
--color-neutral-200: #e2e8f0;   /* border light */
--color-neutral-300: #cbd5e1;
--color-neutral-400: #94a3b8;   /* muted text */
--color-neutral-500: #64748b;   /* secondary text */
--color-neutral-600: #475569;
--color-neutral-700: #334155;   /* primary text */
--color-neutral-800: #1e293b;   /* heading */
--color-neutral-900: #0f172a;   /* max contrast */

/* Buyer Portal — cool blue, global tech tone */
--color-buyer-primary-50:  #eff6ff;
--color-buyer-primary-100: #dbeafe;
--color-buyer-primary-500: #3b82f6;   /* CTA idle */
--color-buyer-primary-600: #2563eb;   /* CTA hover */
--color-buyer-primary-700: #1d4ed8;   /* CTA active */
--color-buyer-primary-900: #1e3a8a;   /* link, heading accent */

/* Hospital Dashboard — teal-leaning, Korean medical tone */
--color-hospital-primary-50:  #f0fdfa;
--color-hospital-primary-100: #ccfbf1;
--color-hospital-primary-500: #14b8a6;  /* tile accent */
--color-hospital-primary-600: #0d9488;  /* active tile border */
--color-hospital-primary-700: #0f766e;
--color-hospital-primary-900: #134e4a;  /* heading */

/* Status colors — Buyer + Hospital 공통 */
--color-status-success-500: #10b981;   /* green-500 (Gateway Online, Completed) */
--color-status-success-100: #d1fae5;
--color-status-warning-500: #f59e0b;   /* amber-500 (stale, Gateway Warning) */
--color-status-warning-100: #fef3c7;
--color-status-danger-500:  #ef4444;   /* red-500 (Failed, Gateway Offline, DEMO MODE badge) */
--color-status-danger-100:  #fee2e2;
--color-status-info-500:    #0ea5e9;   /* sky-500 (Fetching, animated) */
--color-status-info-100:    #e0f2fe;

/* Modality badges (dev-spec FR-A-23 고정) */
--color-modality-CT: #2563eb;   /* 파랑 */
--color-modality-MR: #7c3aed;   /* 보라 */
--color-modality-CR: #059669;   /* 초록 */
--color-modality-DR: #059669;   /* CR 와 동일 */
--color-modality-MG: #ec4899;   /* 분홍 */
--color-modality-US: #ea580c;   /* 주황 */
--color-modality-PT: #dc2626;   /* 빨강 */

/* 대비 검증 (AA, 4.5:1 이상)
 * - neutral-700 on neutral-50   : 11.9:1  PASS
 * - buyer-primary-600 on white  : 5.2:1   PASS
 * - hospital-primary-700 on white: 6.6:1  PASS
 * - status-danger-500 on white  : 4.7:1   PASS (boundary, 굵게 권장)
 * - modality-MG(#ec4899) on white: 3.3:1  FAIL — 배지 텍스트는 darkend #9d174d 로 사용
 */
```

**색 사용 규칙**:

- Primary CTA 는 반드시 `*-primary-600` + white text.
- Destructive 액션 (Cancel order, Sign out) 은 `--color-status-danger-500` outline + text (solid 금지).
- Gateway/Phase 상태는 **dot(●) + 색상 + 텍스트 라벨** 3요소 동시 — 색 단독 의미 금지 (색맹 대응).
- Hospital 전용 `--color-hospital-primary-*` 는 Buyer 화면에 나타나지 않는다. 반대도 같음.

### 2.2 타이포그래피

```
/* Font stacks */
--font-sans-en: 'Inter', ui-sans-serif, system-ui, sans-serif;
--font-sans-ko: 'Pretendard Variable', 'Pretendard', 'Apple SD Gothic Neo',
                 'Noto Sans KR', ui-sans-serif, system-ui, sans-serif;
--font-mono:    'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace;

/* Scale — 1.125 modular (medical apps 관례 1.2 대비 타이트) */
--text-xs:   12px / 16px / 0;      /* metadata, footer, timestamp */
--text-sm:   14px / 20px / 0;      /* body default, table cells */
--text-base: 16px / 24px / 0;      /* paragraph */
--text-lg:   18px / 28px / -0.01em; /* subheading */
--text-xl:   20px / 28px / -0.01em; /* tile title */
--text-2xl:  24px / 32px / -0.015em; /* page title */
--text-3xl:  30px / 38px / -0.02em; /* hero subhead */
--text-4xl:  36px / 44px / -0.025em; /* B-1/B-2 tile big number */
--text-5xl:  48px / 56px / -0.03em; /* Home hero headline */

/* Weights */
--font-regular: 400;
--font-medium:  500;   /* Hospital 타이틀 표준 */
--font-semibold: 600;   /* 버튼 · 테이블 헤더 · Buyer 타이틀 표준 */
--font-bold:    700;   /* Hero headline, B-2 revenue big number */
```

**용법**:

- 영어 화면 (Buyer) body/table 는 `font-sans-en` + `font-regular` + `text-sm`.
- 한국어 화면 (Hospital) body/tile 는 `font-sans-ko` + `font-medium` + `text-sm` (Pretendard 는 medium 이 영어 regular 와 비주얼 weight 등가).
- 숫자 전용 영역 (revenue tile, study count) 은 **tabular-nums** 활성화 — `font-variant-numeric: tabular-nums;`.
- Hash/UID 등 기술 문자열은 `font-mono` + `text-xs`.

### 2.3 간격 · 라운드 · 그림자

```
/* Spacing (8px 그리드, shadcn 승계) */
--space-0: 0;       --space-1: 4px;    --space-2: 8px;
--space-3: 12px;    --space-4: 16px;   --space-5: 20px;
--space-6: 24px;    --space-8: 32px;   --space-10: 40px;
--space-12: 48px;   --space-16: 64px;  --space-20: 80px;

/* Radius */
--radius-sm:  4px;    /* chip, small button */
--radius-md:  6px;    /* button, input (default) */
--radius-lg:  8px;    /* card, modal (default) */
--radius-xl:  12px;   /* tile (Hospital Dashboard) */
--radius-full: 9999px; /* pill badge, dot indicator */

/* Shadows — 의료 톤, 은은함 유지 */
--shadow-xs: 0 1px 2px rgba(15, 23, 42, 0.04);
--shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04);
--shadow-md: 0 4px 6px rgba(15, 23, 42, 0.05), 0 2px 4px rgba(15, 23, 42, 0.04);
--shadow-lg: 0 10px 15px rgba(15, 23, 42, 0.06), 0 4px 6px rgba(15, 23, 42, 0.04);
/* Hospital tile 은 --shadow-sm 고정. Buyer modal 은 --shadow-lg. 그림자 남용 금지 */

/* Z-index 스케일 */
--z-base:     0;
--z-sticky:  10;   /* Top nav */
--z-drawer:  40;   /* Study detail drawer */
--z-modal:   50;   /* Review order modal */
--z-toast:   60;
--z-demoop:  70;   /* Demo Operator badge */
```

### 2.4 모션

```
--duration-fast:    150ms;   /* hover, focus ring */
--duration-base:    200ms;   /* button press, toggle */
--duration-slow:    300ms;   /* modal open, drawer slide */
--duration-slower:  500ms;   /* phase stepper transition */
--easing-out:  cubic-bezier(0.16, 1, 0.3, 1);   /* 기본 ease-out */
--easing-inout: cubic-bezier(0.4, 0, 0.2, 1);
```

- 과도한 motion 금지 — skeleton shimmer · phase transition · modal 만 허용. parallax, 스크롤 애니메이션, 3D 없음.
- `prefers-reduced-motion: reduce` 대응 — 모든 transition 을 1ms 로 단축.

### 2.5 디자인 토큰 거버넌스 (UI_GUIDE 승격 제안)

- 위 4개 섹션 토큰은 **UI_GUIDE.md §2 "디자인 원칙" · §3 "디자인 토큰" 으로 승격** 제안. Kyle 승인 후 본 design-spec 은 참조로 축약.
- 추후 design-spec 은 본 토큰만 사용하며 **신규 토큰 추가는 UI_GUIDE PR 을 거친다**.

---

## §3 컴포넌트 인벤토리

shadcn/ui (Radix 기반) 원시 12종 + 본 feature 고유 확장 11종 = 23종. 각 컴포넌트의 **재사용 여부 · 소유 화면** 을 명시.

### 3.1 shadcn/ui 표준 (재사용)

| # | 컴포넌트 | 소유 화면 | 커스터마이징 |
|---|---|---|---|
| 1 | `Button` | 전 화면 | size: sm/md/lg. variant: default/outline/destructive/ghost. loading prop 추가 |
| 2 | `Input` | Signin, Search (search bar placeholder), Review modal (nothing yet) | type: text/password. error state: 빨간 border + helper text |
| 3 | `Dialog` | A-5 Review order | size: md (640px) |
| 4 | `Sheet` (drawer) | A-4 Study detail | side: right, width: 480px |
| 5 | `DropdownMenu` | Top nav Profile | align: end |
| 6 | `Tabs` | A-8 Downloads (Browser/curl/Python) | orientation: horizontal |
| 7 | `Skeleton` | 전 화면 loading | animation: pulse |
| 8 | `Toast` (sonner) | 주문 ready · 에러 · 복사 확인 | position: bottom-right |
| 9 | `HoverCard` | 복잡 필드 (?) 아이콘 | delay: 300ms |
| 10 | `Checkbox` | Search 결과 row · DUA 동의 | — |
| 11 | `Separator` | 섹션 구분 | — |
| 12 | `DataTable` (TanStack Table 조합) | A-3 Search, A-6 Orders | sort · pagination · row-select 내장 |

### 3.2 RadiVault 커스텀 컴포넌트

#### C-1 `<Brand />` (로고 / 워드마크)

- 목적: Top nav 좌측, Home hero.
- v0.1: 텍스트 마크 `RadiVault` (Inter SemiBold, letter-spacing -0.02em, color neutral-900). 로고 심볼은 v0.1.5 (§13 Q-Brand-1).
- ASCII 레이아웃:
```
[ RadiVault ]
```
- Variant: `<Brand size="sm" />` (nav) / `size="lg"` (hero) / `size="hospital" />` (Hospital Dashboard, 한국어 부제 "병원 파트너 대시보드" 추가).

#### C-2 `<TopNav />`

- 소유: Buyer Portal 전 페이지 (A-1 제외 optional).
- 레이아웃 (ASCII, 1280px):
```
┌───────────────────────────────────────────────────────────────────────┐
│ [Brand]   Search  Orders  Downloads  Docs          [⌘K]  [ Profile ▾ ]│
└───────────────────────────────────────────────────────────────────────┘
height: 56px · sticky top · bg: white · border-bottom: neutral-200
```
- Downloads 는 ready 주문 없을 때 `disabled` (aria-disabled, muted 색).
- ⌘K 는 v0.1 placeholder — 클릭 시 "Coming soon" toast (dev-spec FR-A-68).
- Mobile fallback (< 768px): hamburger 아이콘 + 전체 full-screen menu. v0.1 은 "please use desktop" 페이지 대체.

#### C-3 `<HospitalHeader />`

- 소유: Hospital Dashboard 전 화면.
- 레이아웃 (ASCII):
```
┌───────────────────────────────────────────────────────────────────────┐
│ 병원 파트너 대시보드                            마지막 업데이트 18:32  │
│ 김씨병원 · Gateway H001                                      [로그아웃]│
└───────────────────────────────────────────────────────────────────────┘
height: 72px · bg: neutral-50 · border-bottom: neutral-200
```
- 좌측 큰 제목 (`text-xl`, medium) + 부제 (`text-sm`, neutral-500).
- 우측 상단 업데이트 타임 (`text-xs`, neutral-400). 아래 [로그아웃] 버튼 (ghost, sm).

#### C-4 `<PhaseStepper>` (5-phase)

- 소유: A-7 Order detail, B-5 Orders tile (간이 배지만).
- 변형: horizontal (A-7) / inline-badge (B-5, 테이블 cell).
- Phase 정의 (dev-spec FR-A-43):

| Phase | 영어 레이블 | 한국어 레이블 | 색 | 아이콘 | 애니메이션 |
|---|---|---|---|---|---|
| 1. Accepted | Accepted | 접수 | neutral-400 | `Circle` (outline) | 없음 |
| 2. Fetching from hospital | Fetching | 병원에서 가져오는 중 | info-500 | `Download` | pulse (0.6~1.0 opacity, 2s) |
| 3. Preparing download | Preparing | 준비 중 | info-500 | `Package` | 없음 (색만 active) |
| 4. Ready to download | Ready | 다운로드 준비 완료 | success-500 | `CheckCircle` | 1회 scale 1→1.1→1 (300ms) |
| 5. Completed | Completed | 완료 | success-700 | `CheckCircle2` (filled) | 없음 |
| (별도) Cancelled | Cancelled | 취소 | neutral-400 | `XCircle` | 없음 |
| (별도) Expired | Expired | 만료 | neutral-400 | `Clock` | 없음 |
| (별도) Failed | Failed | 실패 | danger-500 | `AlertCircle` | 1회 shake (200ms) |

- Horizontal 레이아웃 (ASCII, A-7):
```
 ●━━━━━━━●━━━━━━━●━━━━━━━●━━━━━━━●
 1         2         3         4         5
 Accepted  Fetching  Preparing Ready    Completed
 ✓         ◉ active  ○         ○         ○
           18:12 KST → ETA 18:34 KST
```
- 현재 phase: 색 채움 + 라벨 굵게. 이전 phase: 색 채움 + 체크. 이후 phase: 회색 outline.
- ETA tooltip은 현재 phase 아래 "Estimated ready by: 2026-04-24 18:34 KST" (영어) / "예상 완료: 2026-04-24 18:34 KST" (한국어).
- a11y: `role="list"` + 각 step `role="listitem" aria-current="step"` (active).

#### C-5 `<FacetGroup>` (좌측 패싯 필터)

- 소유: A-3 Search.
- 레이아웃 (ASCII, single group):
```
┌─────────────────────────────┐
│ Modality                    │
├─────────────────────────────┤
│ ☐ CT            (12,478)    │
│ ☐ MR             (3,290)    │
│ ☐ CR/DR          (2,104)    │
│ ☐ MG               (892)    │
│ ─ show more ─               │
└─────────────────────────────┘
width: 240px · padding: 12px · border-bottom: neutral-200
```
- 각 옵션: checkbox + label + count badge (oval, neutral-100 bg, neutral-600 text).
- 4개 이상 옵션 시 "show more" 확장. 기본 첫 4 노출.
- 적용 중 필터는 상단 체크박스 굵게 + 배경 primary-50.
- 로딩 중: 각 옵션 skeleton.

#### C-6 `<CohortSidebar>` (우측 코호트 요약)

- 소유: A-3 Search.
- 레이아웃 (ASCII):
```
┌─────────────────────────────┐
│ Your cohort                 │
│                             │
│     ┌───────────┐           │
│     │    12     │           │
│     │  studies  │           │
│     └───────────┘           │
│                             │
│ Total size   1.2 GB         │
│ Hospitals    3 sites        │
│ Price        —              │
│                             │
│ [  Review order       →  ]  │
│                             │
│ ─ cleared on session end ─  │
└─────────────────────────────┘
width: 280px · padding: 16px · position: sticky · top: 72px
```
- 숫자는 `text-4xl bold tabular-nums`.
- Price `—` 는 neutral-400, tooltip "Billing is a v0.1 stub. Contact sales@radivault.io for paid tier." (Q-Legal-3 승인 전까지).
- Review order 버튼은 0 study 시 disabled + "Select at least 1 study" helper.
- Footer `cleared on session end` 는 `text-xs neutral-400`.

#### C-7 `<StudyRow>` (Search 결과 테이블 행)

- 소유: A-3 Search (DataTable row).
- 컬럼 7개 (dev-spec FR-A-13): checkbox · pseudo_uid (8자) · modality badge · body_part · n_instances · size · study_year.
- 행 높이 44px. hover 시 neutral-50 bg. selected 시 primary-50 bg.
- 클릭 (row, not checkbox) → Study detail drawer 오픈.
- ASCII:
```
│ ☐ │ 3f4a9b12 │ [CT] │ SPINE    │ 384  │ 312 MB │ 2024 │
│ ☑ │ 7c2d1e98 │ [MR] │ BRAIN    │ 420  │ 890 MB │ 2025 │
│ ☐ │ a1b2c3d4 │ [MG] │ BREAST   │  12  │  34 MB │ 2023 │
```
- modality badge = pill, 2자 (CT/MR/CR/MG/US/PT), 배경 해당 modality 색의 10% alpha, 텍스트 해당 modality 색 darker 500 (WCAG 4.5 보정).

#### C-8 `<ModalityBadge>` (재사용 atom)

- 소유: StudyRow · Study detail · Orders phase column · Hospital B-5 Orders tile.
- Props: `modality: 'CT'|'MR'|'CR'|'DR'|'MG'|'US'|'PT'`.
- Size: sm (20px) / md (24px).
- ARIA: `aria-label="Modality: CT"` (색 의미 보강).

#### C-9 `<TileCard>` (Hospital Dashboard 6-tile base)

- 소유: B-1..B-6 공통.
- 레이아웃 (ASCII, 기본 variant):
```
┌────────────────────────────────────┐
│ 오늘/누적 제공 스터디   18:32 ↻   │ ← 제목 sm medium · 우상단 업데이트
├────────────────────────────────────┤
│                                    │
│        42                          │ ← big number: text-4xl bold
│        스터디 / 오늘                │ ← sub: text-sm neutral-500
│                                    │
│    누적   12,478                    │ ← secondary metric row
│                                    │
└────────────────────────────────────┘
min-height: 200px · padding: 20px · radius-xl · shadow-sm · border: neutral-200
```
- Variants:
  - `variant="metric"` (B-1): big number + sub + secondary metric.
  - `variant="chart"` (B-2): big number + Recharts bar chart + footer disclaimer.
  - `variant="map"` (B-3): SVG map full-bleed.
  - `variant="status"` (B-4): dot + status text + last-sync.
  - `variant="list"` (B-5, B-6): 10-row list, no big number.
- Stale indicator: 폴링 실패 시 border 2px warning-500 + 우상단 ⚠ 아이콘.

#### C-10 `<RevenueDisclaimer />` (B-2 전용, 제거 불가)

- 고정 footer: `시뮬레이션 — v0.2 정산 대기`.
- 스타일: `text-xs font-medium`, 색 neutral-500.
- **Storybook snapshot test 로 회귀 방지** (dev-spec AC-B-5 재확인).

#### C-11 `<KoreaHeatmap />` (B-3)

- SVG 한국 17 광역 (베이스 공개 SVG 재가공, neutral-200 stroke, white fill).
- 포인트: 파일럿 병원 1~2 곳 위치를 small circle (r=6) + 파랑 glow.
- Tooltip (hover): `{병원명} — {지역}` 1줄.
- 데모 연출: 장면 3~6 내내 Hospital Dashboard 배경으로 고정 노출.
- a11y: `role="img" aria-label="한국 지도 — 현재 파일럿 병원 2곳 표시"`. 상세 기여도 텍스트 리스트는 `<VisuallyHidden>`.

#### C-12 `<EmptyState variant>` 공통

- 소유: 빈 검색결과 · 빈 주문 · 다운로드 대기.
- 레이아웃 (ASCII):
```
┌──────────────────────────────┐
│          [아이콘]            │
│                              │
│   No studies match these     │
│   filters.                   │
│                              │
│   Try widening date range    │
│   or removing min_hospitals. │
│                              │
│   [ Clear all filters ]      │
└──────────────────────────────┘
padding: 48px · text-align: center
```
- 아이콘: lucide `SearchX` (no-results), `Inbox` (no-orders), `Clock` (no-downloads).
- Copy 는 English (Buyer) / Korean (Hospital). §7 상세.

#### C-13 `<ErrorBanner variant>` 공통

- 소유: 전 화면 4xx / 5xx / network / PHI-suspect.
- 레이아웃 (ASCII):
```
┌────────────────────────────────────────────────────────────────┐
│ ⚠  ERR_AUTH_INVALID                                            │
│    Your API key is invalid or revoked.                         │
│    API 키가 유효하지 않거나 회수되었습니다.                      │
│                                                                │
│    Request ID: req_01HXYZ...    [ Copy ]  [ Contact support ]  │
└────────────────────────────────────────────────────────────────┘
bg: danger-100 · border-left: 4px danger-500 · padding: 16px
```
- 4 variants: business (4xx, 노랑) / system (5xx, 빨강) / offline (네트워크, 회색) / phi-suspect (빨강 full, 자동 Cmd+W 안내).
- Request ID 복사 버튼 → clipboard + toast.
- Contact support 링크 → `mailto:support@radivault.io?subject=Error%20ref%20{request_id}`.

#### C-14 `<DemoOperatorBadge />`

- 소유: Demo Operator Mode 활성 시 Buyer + Hospital 공통.
- 위치: 우상단 고정 (z-demoop = 70).
- 레이아웃 (ASCII):
```
              ┌─────────────────┐
              │ ● DEMO MODE     │
              │ Scene 3/7       │
              │ 08:23 / 17:00   │
              └─────────────────┘
bg: danger-500 · text: white · radius-md · text-xs bold · padding: 8px 12px
pulse animation: opacity 0.8→1 (1s loop)
```
- 내부 상태: 현재 scene · 경과시간.
- 클릭 시 작은 panel expand (shortcut 목록, Reset, Canned toggle). Ctrl+Shift+D 로 toggle.

#### C-15 `<PhaseBadge />` (inline, B-5 / A-6)

- 소유: Orders 테이블 cell.
- Phase 별 색/레이블/아이콘 C-4 표와 동일.
- Pill shape, padding 2/8px.

#### C-16 `<ChecksumCell />` (A-8 Downloads)

- 소유: Downloads 테이블 row.
- 표시: `3f4a9b12...` (8자 + ...) + click to expand full + copy.
- Font: `font-mono text-xs neutral-500`.

#### C-17 `<ExpirationCountdown />` (A-8)

- 소유: Downloads 상단.
- 포맷: `Expires in 23h 47m 12s`.
- < 10분 남으면 bg warning-100 + hint "Consider refreshing".
- 만료 시 `Expired` + bg danger-100 + `Refresh URLs` 버튼만 enabled.

#### C-18 `<ApiSnippetTab />` (A-8 Downloads Tabs)

- 3 탭: Browser / curl / Python.
- 각 탭 내부 `<pre><code>` 블록 + 우상단 Copy 버튼.
- Font: JetBrains Mono 14px. line-height 1.6.
- Syntax highlighting: shikijs light theme (v0.1 무색도 OK).

#### C-19 `<AuditRow />` (B-6 Audit tile)

- 소유: B-6 Audit tile list row.
- 레이아웃: `18:30:12 · 입수 · 3f4a9b12`.
- Font: mixed — 시각 tabular, 이벤트 한글, 해시 mono.
- 호버 시 subtle bg highlight (neutral-50). 클릭 없음 (정보 전용).

#### C-20 `<GatewayStatusDot />` (B-4)

- 3 states: Online (green dot + "● Online") / Warning (amber + "● Warning — last sync 15m ago") / Offline (red + "● Offline — last sync 2h ago").
- Pulse animation on Online: subtle 1s loop (opacity 0.9→1).
- Offline: no animation (정적 강조).

#### C-21 `<LoginCard />` (A-2 Signin, B signin)

- Buyer variant (영어): API key 입력 masked.
- Hospital variant (한국어): 병원 관리자 토큰 입력 + gateway_id dropdown (single H001 v0.1).
- 공통 레이아웃 (ASCII, centered 420px):
```
┌──────────────────────────────────┐
│         [Brand]                  │
│                                  │
│    Sign in with API key          │
│                                  │
│  ┌────────────────────────────┐  │
│  │ rv_live_...                │  │
│  └────────────────────────────┘  │
│                                  │
│  [  Sign in                  →]  │
│                                  │
│  Don't have a key?               │
│  Contact sales@radivault.io      │
└──────────────────────────────────┘
```

#### C-22 `<PriceMask />` (A-4, A-5, A-6 cohort sidebar)

- 렌더: `—` (em dash neutral-400) + hover tooltip "Contact sales@radivault.io".
- 이유: dev-spec §0.2-3 가격 마스킹 정책.

#### C-23 `<CannedOverlay />` (Demo Operator only)

- 소유: Demo Operator Mode.
- 활성 시 모든 BFF route handler 응답을 `public/demoop/canned/scene-{n}/*.json` 에서 주입.
- UI 표시: 우하단 작은 stamp `canned` (text-xs amber). 관객에게는 안 보이지만 presenter 는 자각.

---

## §4 사용자 플로우

### 4.1 Happy path — Buyer (장면 4 + 5)

```
[Home /]
  │  "Sign in with API key" 클릭
  ▼
[Signin /signin]
  │  rv_live_... 붙여넣기 → Submit
  ▼
[Search /search]       ← cold state, 3-pane 로드
  │  좌: 패싯 {modality=CT, body_part=SPINE, min_hospitals=3} 선택
  │  중앙: 결과 테이블 갱신 (12 studies)
  │  우: cohort sidebar 갱신, "Review order" enable
  │  테이블에서 체크박스 10개 선택
  ▼
[Search + Detail Drawer]  ← (optional, row 클릭 시)
  │  메타 확인 → "Add to cohort" or 닫기
  ▼
[Review Order Modal]
  │  cohort summary 확인
  │  DUA 체크박스 ☑
  │  "Confirm order" 클릭
  ▼
[Order detail /orders/{id}]  ← 202 응답 → 자동 redirect (3s)
  │  5-phase stepper: Accepted ● ○ ○ ○ ○
  │  5s 폴링 → Fetching ● ● ○ ○ ○
  │  → Preparing ● ● ● ○ ○
  │  → Ready ● ● ● ● ○   (toast: "Order ready — go to downloads")
  ▼
[Downloads /orders/{id}/downloads]
  │  만료 카운트다운 23h 59m
  │  Browser tab → per-object "Download" 클릭 or
  │  "Copy curl" / "Copy Python" → 로컬 실행
  ▼
완료 (Completed ● ● ● ● ●)
```

### 4.2 Permission denied — 세션 만료

```
[Search /search]
  │  60s 후 cohort "Review order" 클릭
  │  BFF → 401 ERR_AUTH_EXPIRED
  ▼
[Signin /signin]  ← 자동 redirect
  │  + toast "Your session expired. Please sign in again."
  │  재로그인 → cohort 는 sessionStorage 로 복구 시도 (v0.1.1)
  │  v0.1 은 빈 cohort 로 /search 복귀
```

### 4.3 Error path — 주문 Confirm 실패 (422 validation)

```
[Review Order Modal]
  │  "Confirm order" 클릭
  │  BFF → 422 ERR_QUOTA_STUDIES_EXCEEDED
  ▼
[Review Order Modal (unchanged, error banner 노출)]
  │  <ErrorBanner>
  │    ⚠ ERR_QUOTA_STUDIES_EXCEEDED
  │    Your order exceeds the per-order study limit (1000).
  │    주문이 1회 상한 (1,000건) 을 초과합니다.
  │    Request ID: req_...
  │    [Copy] [Contact support]
  │  모달 유지 — 사용자가 cohort 줄이거나 취소 선택
```

### 4.4 Network failure — 포털 폴링 중단

```
[Order detail /orders/{id}]  ← phase = Fetching, 5s 폴링 중
  │  3회 연속 fetch failure (BFF → 502)
  ▼
Banner 상단: <ErrorBanner variant="offline">
  │  ⚠ You're offline. Reconnecting...
  │  + 폴링 백오프: 5s → 10s → 20s → 30s
  ▼
복구 시 자동 재개 + toast "Reconnected."
```

### 4.5 Happy path — Hospital (장면 3 + 6)

```
[/hospital/H001] 미인증
  ▼
[/hospital/signin]
  │  hospital admin token 입력
  ▼
[/hospital/H001]  ← 6 tile 병렬 렌더
  │  B-1 Studies (skeleton 500ms → 42/12,478)
  │  B-2 Revenue (skeleton → bar chart + disclaimer)
  │  B-3 Map (SVG + 1 포인트)
  │  B-4 Gateway (● Online 2m ago)
  │  B-5 Orders (list 10 rows)
  │  B-6 Audit (list 10 rows)
  │  각 tile 우상단 "18:32 ↻" 업데이트 타임
  ▼
60s 마다 tile 별 독립 폴링 refresh
```

### 4.6 Hospital — Gateway offline 시

```
[/hospital/H001]
  │  B-4 Gateway tile — last_sync 2h ago
  ▼
B-4 tile:
  │  [● Offline — last sync 2시간 전]
  │  bg: danger-100
  │  CTA (v0.1.1 예정): "연락 → 전산실장" — v0.1 은 정보만
  │  다른 tile 5개는 정상 (캐시된 최근 데이터 + stale indicator 없음)
```

### 4.7 Demo Operator — 장면 전환

```
[Ctrl+Shift+D] → DEMO MODE 활성 (이미 on 상태)
  ▼
[Ctrl+3] → /hospital/H001?_seed=demo  ← pre-warmed URL
  │  BFF 가 canned overlay on 이면 public/demoop/canned/scene-3/*.json 반환
  │  6 tile 10초 이내 로드 (FR-R-4)
  ▼
[Ctrl+4] → /search?modality=CT&body_part=SPINE
  │  canned search results 주입
  ▼
[Ctrl+.] → scene timer advance
```

---

## §5 Buyer Portal 화면 명세

각 화면: (a) URL · (b) ASCII 와이어프레임 · (c) 컴포넌트 계층 · (d) 상태 매트릭스 · (e) i18n 카피 · (f) 접근성 비고 · (g) 데모 장면 연결.

### 5.A-1 Home (`/`, public)

**목적**: 첫 인상 + Sign-in CTA + 증명 수치 3개.

**ASCII 와이어 (1440px 기준)**:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [RadiVault]              Search  Orders  Downloads  Docs    [ Sign in → ]   │ ← Top nav (public simplified)
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                                                                             │
│          Korea's medical imaging data,                                      │
│          compliantly delivered to the world's AI.                           │
│                                                                             │
│          Hospital-grade DICOM, fully anonymized, PIPA §28-8 aligned.        │
│          Production pipeline. Browser-first procurement.                    │
│                                                                             │
│          [  Sign in with API key  →  ]    [  Read API docs  ]               │
│                                                                             │
│                                                                             │
├─────────────────────┬─────────────────────┬─────────────────────────────────┤
│                     │                     │                                 │
│     12,478          │        2            │     < 48h                       │
│  Studies indexed    │  Hospitals          │  Turnaround (designed for)      │
│                     │  contributing       │                                 │
│                     │                     │                                 │
├─────────────────────┴─────────────────────┴─────────────────────────────────┤
│                                                                             │
│  Footer:                                                                    │
│  Data demo powered by TCIA CC-BY collections. Production data from Korean   │
│  hospital partners under MSA. © RadiVault 2026. We use essential cookies    │
│  for session. No tracking.                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**컴포넌트 계층**:
- `<TopNav variant="public">` (Sign in 만 노출, 나머지 링크는 여전히 있으나 클릭 시 signin)
- `<Hero>` — headline + sub + 2 CTA
- `<ProofTiles>` — 3 tiles (grid-cols-3, gap-6)
- `<Footer>` — TCIA attribution + cookie note + copyright

**i18n 카피 (영어)**:
- Headline: `Korea's medical imaging data, compliantly delivered to the world's AI.`
- Sub: `Hospital-grade DICOM, fully anonymized, PIPA §28-8 aligned. Production pipeline. Browser-first procurement.`
- CTA primary: `Sign in with API key` `→`
- CTA secondary: `Read API docs`
- Tile 1 label: `Studies indexed`
- Tile 2 label: `Hospitals contributing`
- Tile 3 label: `Turnaround (designed for)` + small footnote `p95 target, not guaranteed`
- Footer: 위 ASCII 본문 그대로.

**상태**:
- Loading: tiles skeleton (3 rect, 80px tall).
- Error (facets 실패): tiles 값 `—` 폴백, 에러 toast 표시 **안 함** (public 페이지라 noise 최소화, dev-spec FR-A-10).
- Empty: N/A — tiles 항상 "Studies indexed ≥ 0".

**접근성**:
- Headline `<h1>`, subsequent `<h2>` 없음 (비주얼 계층).
- CTA 버튼: `aria-label` 없음 (텍스트 자체가 라벨).
- TCIA 출처 footer: `<small>` tag + neutral-500.

**데모 연결**: 장면 2 후반 (slide 에서 Cmd+Tab 으로 이 화면 노출).

---

### 5.A-2 Signin (`/signin`)

**ASCII 와이어**:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [RadiVault]                                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                                                                             │
│                      ┌──────────────────────────────────┐                   │
│                      │         [RadiVault]              │                   │
│                      │                                  │                   │
│                      │    Sign in with your API key     │                   │
│                      │                                  │                   │
│                      │  ┌────────────────────────────┐  │                   │
│                      │  │ rv_live_...                │  │                   │
│                      │  └────────────────────────────┘  │                   │
│                      │                                  │                   │
│                      │  [  Sign in                  →]  │                   │
│                      │                                  │                   │
│                      │  Don't have a key?               │                   │
│                      │  Contact sales@radivault.io      │                   │
│                      └──────────────────────────────────┘                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**컴포넌트**: `<LoginCard variant="buyer">` (C-21).

**i18n 카피**:
- Title: `Sign in with your API key`
- Placeholder: `rv_live_...`
- Hint (below input): `Paste your key. It's never stored in the browser.`
- Submit: `Sign in` `→`
- Below submit: `Don't have a key? Contact sales@radivault.io`

**상태**:
- Idle: submit disabled (input empty or < 10 chars).
- Loading: submit button loading spinner. Input disabled.
- Error 1 — `ERR_AUTH_FORMAT` (형식 오류):
  - Banner: `Invalid key format. Keys start with rv_live_.`
  - Input border: danger-500.
- Error 2 — `ERR_AUTH_INVALID` (서버 거부):
  - Banner: `Your API key is invalid or revoked.`
  - `Request ID: req_...` + Copy 버튼.
- Error 3 — network/5xx: generic `<ErrorBanner variant="system">` + Contact support.

**데모 연결**: 오프스크린 (세션 pre-warmed).

---

### 5.A-3 Search (`/search`) — 3-pane Gen3 스타일

**ASCII 와이어 (1440px)**:
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ [RadiVault]   Search  Orders  Downloads  Docs                  [⌘K]  [ Dana ▾ ]│
├─────────────────┬──────────────────────────────────────────┬────────────────────┤
│                 │ Active filters: [modality=CT ×][body=SPINE ×]  Clear all     │
│  FACETS         │                                          │  YOUR COHORT       │
│                 │ ┌──────────────────────────────────────┐ │                    │
│ Modality        │ │ Coming in v0.2 — use filters on left │ │     12             │
│  ☑ CT   (12478) │ └──────────────────────────────────────┘ │   studies          │
│  ☐ MR    (3290) │                                          │                    │
│  ☐ CR    (2104) │ 12 studies across 3 hospitals            │  Total  1.2 GB     │
│  ─ show more ─  │                                          │  Sites  3          │
│                 │ ┌──────────────────────────────────────┐ │  Price  —          │
│ Body part       │ │ ☐│  ID      │Mod│ Body    │ N  │MB  │ │                    │
│  ☑ SPINE (  892)│ │ ☑│ 3f4a9b12 │CT │ SPINE   │384 │312 │ │ [ Review order → ] │
│  ☐ CHEST ( 4521)│ │ ☑│ 7c2d1e98 │CT │ SPINE   │420 │890 │ │                    │
│  ☐ BRAIN ( 2918)│ │ ☑│ a1b2c3d4 │CT │ SPINE   │512 │456 │ │ ─ cleared on        │
│  ─ show more ─  │ │ ☐│ b2c3d4e5 │CT │ SPINE   │298 │234 │ │   session end ─     │
│                 │ │ ... (8 more rows)                   │ │                    │
│ Sex             │ └──────────────────────────────────────┘ │                    │
│  ☐ M      (8231)│                                          │                    │
│  ☐ F      (4247)│ [◁ Prev]  Page 1 of 42  [Next ▷]         │                    │
│                 │                                          │                    │
│ Age bucket      │                                          │                    │
│  ☐ 0-17  (  120)│                                          │                    │
│  ☐ 18-40 ( 3120)│                                          │                    │
│  ...            │                                          │                    │
│                 │                                          │                    │
│ Study year      │                                          │                    │
│  ☐ 2025  ( 5218)│                                          │                    │
│  ☐ 2024  ( 4981)│                                          │                    │
│  ☐ 2023  ( 2279)│                                          │                    │
│                 │                                          │                    │
│ Manufacturer    │                                          │                    │
│  ☐ Siemens      │                                          │                    │
│  ☐ GE           │                                          │                    │
│  ☐ Philips      │                                          │                    │
│                 │                                          │                    │
│ Min hospitals   │                                          │                    │
│  [ 1  2 (3) 4 5]│                                          │                    │
│                 │                                          │                    │
└─────────────────┴──────────────────────────────────────────┴────────────────────┘
  240px             flex (approx 820px)                        280px
```

**컴포넌트 계층**:
- `<TopNav>`
- 3-pane container (grid-cols: 240px 1fr 280px, gap-4)
  - Left: 7 개 `<FacetGroup>` (Modality, Body part, Sex, Age bucket, Study year, Manufacturer, Min hospitals)
  - Center:
    - 상단: `<ActiveFilterChips />` (dismissible)
    - 상단: `<SearchBar>` v0.2 placeholder (disabled)
    - 결과 카운트 라인: `12 studies across 3 hospitals`
    - `<DataTable>` (TanStack) with 7 columns
    - `<KeysetPagination>` (cursor based)
  - Right: `<CohortSidebar>` (sticky, top: 72px)

**상태 매트릭스**:

| 상태 | 중앙 | 좌측 | 우측 |
|---|---|---|---|
| Initial loading | Skeleton 10 rows | Skeleton 7 groups | Skeleton cohort card |
| No filters applied | "Apply filters to see results" + CTA "Pick a modality" | facets 전체 | `0 studies` |
| Results | Table | facets | cohort (live update) |
| 0 results (필터 좁음) | `<EmptyState variant="no-results">` — "No studies match these filters. Try widening date range or removing `min_hospitals ≥ 3`." + "Clear all" CTA | facets 0 count | cohort 유지 (기존 선택) |
| 4xx (쿼터 초과) | `<ErrorBanner ERR_BUYER_QUOTA>` | facets disabled | cohort 유지 |
| 5xx / network | `<ErrorBanner variant="system">` + retry button | facets disabled | cohort 유지 |
| Cohort Review 진행 중 | 테이블 유지, 체크박스 disabled | 유지 | "Review order" → loading spinner |

**i18n 카피 (영어)**:
- Pane header 라벨: `Modality`, `Body part`, `Sex`, `Age bucket`, `Study year`, `Manufacturer`, `Min hospitals`
- Result count: `{n} studies across {m} hospitals` — n=0 일 때 EmptyState 전환.
- Active chips: `modality=CT ×` / `body=SPINE ×` / ...
- Clear all link: `Clear all`
- Cohort header: `Your cohort`
- Cohort metrics: `{n} studies`, `Total {size}`, `Sites {m}`, `Price —`
- CTA: `Review order` `→`
- Search bar placeholder (v0.2 stub): `Coming in v0.2 — use filters on the left for now`

**접근성**:
- Pane order: facets → table → cohort (Tab 순서 논리적).
- Table row: `role="row"`, checkbox `aria-label="Select study {pseudo_uid}"`.
- Cohort sidebar: `aria-live="polite"` — 선택 변경 시 스크린리더 공지.
- Modality 배지: `aria-label="Modality: CT"`.

**데모 연결**: 장면 4 시작. Ctrl+4 로 `/search?modality=CT&body_part=SPINE` pre-warmed.

---

### 5.A-4 Study Detail Drawer (right `<Sheet>` on `/search`)

**ASCII 와이어 (width 480px slide from right)**:
```
┌────────────────────────────────────────┐
│ Study detail                      [×]  │
├────────────────────────────────────────┤
│                                        │
│  ┌─────┐                               │
│  │ CT  │   pseudo_study_uid            │
│  └─────┘   3f4a9b12abcd...  [copy]     │
│                                        │
│  Body part         SPINE               │
│  Sex               F                   │
│  Age bucket        41-60               │
│  Study year        2024                │
│  Instances         384                 │
│  Size              312 MB              │
│  Hospital          H001                │
│  Manufacturer      Siemens             │
│  Station           CT01                │
│                                        │
│  Series (3)                            │
│  ┌──────────────────────────────────┐  │
│  │ 1.2.840...abc  CT  128 inst     │  │
│  │ 1.2.840...def  CT  128 inst     │  │
│  │ 1.2.840...ghi  CT  128 inst     │  │
│  └──────────────────────────────────┘  │
│                                        │
│  ┌──────────────────────────────────┐  │
│  │ Preview available in v0.2        │  │
│  │ (sample dataset program)         │  │
│  └──────────────────────────────────┘  │
│                                        │
│  Price  —                              │
│                                        │
│  [ Add to cohort                  +  ] │
│                                        │
└────────────────────────────────────────┘
```

**컴포넌트**:
- `<Sheet side="right">` (shadcn)
- Header: modality 대형 배지 (96x96) + pseudo_uid copy
- Metadata grid (2 col: label / value, 10 rows)
- Series list (max 10 rows, "show more" 확장)
- Preview placeholder card (light gray, 중앙 정렬 텍스트)
- Footer: Price `—` + "Add to cohort" / "Remove" 토글 CTA

**상태**:
- Loading: metadata skeleton (10 rows) + series skeleton.
- Error 404 (`ERR_STUDY_NOT_FOUND`): `<ErrorBanner>` + "Study not found" + "Close" 버튼.
- Added 상태: CTA label 이 `Remove from cohort` (minus 아이콘, destructive outline).

**접근성**:
- Drawer open 시 focus trap. 첫 포커스는 닫기 버튼.
- ESC 로 닫기. `aria-modal="true"` + `aria-labelledby="study-detail-title"`.

**데모 연결**: 장면 4 중반 (1-2 study row 클릭 → drawer 보여주고 닫음).

---

### 5.A-5 Review Order Modal (`/search` → Dialog)

**ASCII 와이어 (modal 640px centered)**:
```
┌────────────────────────────────────────────────────┐
│ Review your order                           [×]    │
├────────────────────────────────────────────────────┤
│                                                    │
│  Cohort summary                                    │
│  ┌───────────────────────────────────────────────┐ │
│  │  12 studies across 3 hospitals                │ │
│  │  Total size: 1.2 GB                           │ │
│  │  Modalities: CT (12)                          │ │
│  │  Study years: 2023 (4), 2024 (5), 2025 (3)    │ │
│  └───────────────────────────────────────────────┘ │
│                                                    │
│  Agreement                                         │
│  ┌───────────────────────────────────────────────┐ │
│  │  MSA hash: sha256:abcd1234...abcdef  [copy]   │ │
│  │                                               │ │
│  │  ☐ I confirm this order is governed by MSA    │ │
│  │    msa_...ef12 and agree to the terms.        │ │
│  └───────────────────────────────────────────────┘ │
│                                                    │
│  Estimated ready: 28-45 min (cold) / 30s (hot)     │
│  Billing: v0.1 stub — no charge will occur.        │
│  Contact sales@radivault.io for paid tier.         │
│                                                    │
│  Total:  —                                         │
│                                                    │
│  [   Cancel   ]        [   Confirm order     →  ]  │
│                                                    │
└────────────────────────────────────────────────────┘
```

**컴포넌트**:
- `<Dialog>` (size md 640px)
- `<CohortSummaryCard>`
- `<AgreementSection>` — hash 표시 + 체크박스
- `<BillingNote>` — gray box, info variant
- Price `—` (PriceMask) + 2 buttons (Cancel ghost / Confirm primary)

**상태**:
- Initial: Confirm disabled (DUA unchecked).
- DUA checked + submitting: Confirm loading spinner, 다른 버튼 disabled, backdrop 방지 (beforeunload 경고).
- Success (202): modal 영수증 뷰로 전환:
  ```
  ✓  Order placed
  ord_01HX... · 12 studies
  Estimated ready: 2026-04-24 19:05 KST
  Redirecting to order details in 3s...
  ```
- Error 422 (validation): inline `<ErrorBanner>` 내부.
- Error 409 (idempotency replay): banner "This order already exists" + "Go to existing order" 링크.
- Error 429 (quota): banner + `X-Quota-Reset-Daily` 기반 "Resets at 09:00 UTC tomorrow".

**접근성**:
- Focus trap. 첫 focus: DUA checkbox (스킵 가능하도록 Cancel 순서 먼저).
- `aria-describedby="billing-note"` on Confirm — 스크린리더가 "v0.1 stub" 읽음.

**데모 연결**: 장면 4 후반.

---

### 5.A-6 Orders List (`/orders`)

**ASCII 와이어**:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [RadiVault]   Search  Orders  Downloads  Docs                 [⌘K]  [ Dana ▾]│
├─────────────────────────────────────────────────────────────────────────────┤
│ Orders                                                                      │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ Order ID       Phase           N  Created     ETA / Ready              │ │
│ ├─────────────────────────────────────────────────────────────────────────┤ │
│ │ ord_5a3f12 ⧉  ● Ready          12  18:30       Ready                   │ │
│ │ ord_7c2e98 ⧉  ● Fetching       24  18:27       ~15 min                 │ │
│ │ ord_a1b2c3 ⧉  ● Accepted        8  18:32       ~30 min                 │ │
│ │ ord_b2c3d4 ⧉  ● Completed      30  17:45       Completed 18:20         │ │
│ │ ord_c3d4e5 ⧉  ● Expired        50  2026-04-17  Expired                 │ │
│ │ ord_d4e5f6 ⧉  ● Failed          5  18:10       Failed (see details)    │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ [◁ Prev]  Page 1  [Next ▷]                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**컴포넌트**:
- `<TopNav>`
- Page heading `Orders`
- `<DataTable>` 5 cols: order_id (mono, 8자 + clipboard icon) · `<PhaseBadge>` · N · Created (relative) · ETA/Ready

**Phase Badge 색상** (C-15 규칙):
- Ready: success-500 bg-success-100
- Fetching: info-500 bg-info-100 (animated)
- Accepted: neutral-500 bg-neutral-100
- Completed: success-700 bg-success-100
- Cancelled / Expired: neutral-400 bg-neutral-100
- Failed: danger-500 bg-danger-100

**상태**:
- Empty (첫 방문): `<EmptyState variant="no-orders">` + "Go to Search" CTA.
- Loading: 10 skeleton rows.
- Error: `<ErrorBanner>` 상단.

**카피**:
- Heading: `Orders`
- Column headers: `Order ID`, `Phase`, `N`, `Created`, `ETA / Ready`
- Empty: `You haven't placed any orders yet.` + `Start by searching for a cohort.` + CTA `Go to Search →`

**데모 연결**: 장면 5 시작 (Ctrl+5 로 pre-seeded ready order 로 직행).

---

### 5.A-7 Order Detail + Tracker (`/orders/{id}`)

**ASCII 와이어**:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [RadiVault]   Search  Orders  Downloads  Docs                 [⌘K]  [ Dana ▾]│
├─────────────────────────────────────────────────────────────────────────────┤
│ ← Orders                                                                    │
│ Order ord_5a3f1234... ⧉                              [ Cancel order ]       │
│ 12 studies · 1.2 GB · Created 2026-04-24 18:30 · MSA sha256:abcd...         │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │                                                                         │ │
│ │    ●━━━━━━━━●━━━━━━━━●━━━━━━━━◉━━━━━━━━○                                │ │
│ │    1        2        3        4        5                                │ │
│ │    Accepted Fetching Preparing Ready    Completed                       │ │
│ │    ✓        ✓        ✓        ● active ○                                │ │
│ │                                                                         │ │
│ │    Estimated ready by: 2026-04-24 19:05 KST                             │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ [ View timeline (advanced) ]                                                │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │  Go to Downloads  →                                                     │ │
│ │  (Enabled once phase reaches Ready)                                     │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

**컴포넌트**:
- `<TopNav>`
- Back link to /orders
- Order header: ID (mono) + copy + Cancel button (Accepted phase 에만 enabled)
- Meta line: n_studies · size · created · MSA hash (mono short)
- `<PhaseStepper variant="horizontal">` (C-4)
- ETA tooltip 아래 고정 출력
- "View timeline (advanced)" — ghost button → drawer (12-state history)
- Large "Go to Downloads →" CTA — ready 이전 disabled, ready 되면 enabled (color transition 500ms)

**상태 매트릭스**:

| Phase | Header CTA | Main CTA | 폴링 | Banner |
|---|---|---|---|---|
| Accepted | Cancel enabled | Disabled "Go to Downloads" | 5s | 없음 |
| Fetching | Cancel disabled (+tooltip "Too late to cancel") | Disabled | 5s | 없음 |
| Preparing | Cancel disabled | Disabled | 5s | 없음 |
| Ready | Cancel disabled | Enabled (primary, pulse 1x) | 중단 | toast "Order ready — go to downloads" 1회 |
| Completed | Cancel hidden | "View downloads" | 중단 | 성공 banner (녹색) "Order completed" |
| Cancelled | Cancel hidden | Hidden | 중단 | "Order cancelled" (neutral) |
| Expired | Cancel hidden | Hidden (refresh 버튼 대신) | 중단 | "Order expired. Place a new order for the same cohort." |
| Failed | Cancel hidden | Hidden | 중단 | `<ErrorBanner>` + err code + Contact support |

**타임라인 드로어 (View timeline)**:
```
┌────────────────────────────────────────┐
│ Timeline (advanced)             [×]    │
├────────────────────────────────────────┤
│  18:30:02   queued                     │
│  18:30:04   validating                 │
│  18:30:05   validated                  │
│  18:30:07   submitted                  │
│  18:30:12   fetching                   │
│  18:45:23   staging_partial (45%)      │
│  18:55:10   staging_complete           │
│  18:55:12   ready_for_download         │
│  -- polling continues --               │
└────────────────────────────────────────┘
```
- 12-state 모두 표시 (neutral-500 text, mono).
- Each row with micro-pulse when newly arrived.

**i18n 카피**: 영어 (Buyer). phase 레이블 C-4 표 그대로.

**데모 연결**: 장면 5 중반.

---

### 5.A-8 Downloads (`/orders/{id}/downloads`)

**ASCII 와이어**:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [RadiVault]   Search  Orders  Downloads  Docs                 [⌘K]  [ Dana ▾]│
├─────────────────────────────────────────────────────────────────────────────┤
│ ← Order ord_5a3f1234...                                                     │
│                                                                             │
│ Downloads                                                                   │
│ 12 files · 1.2 GB total                                                     │
│                                                                             │
│ ┌──────────────────────────────────────────────────────────────┐            │
│ │ Expires in 23h 47m 12s                        [ Refresh URLs ]│           │
│ └──────────────────────────────────────────────────────────────┘            │
│                                                                             │
│ [ Download all (.json manifest) ]                                           │
│                                                                             │
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │ [ Browser ][ curl ][ Python ]                                            │ │
│ ├─────────────────────────────────────────────────────────────────────────┤ │
│ │                                                                         │ │
│ │ [Browser tab]                                                           │ │
│ │                                                                         │ │
│ │ File                         Size      SHA-256        Action            │ │
│ │ study_3f4a9b12/001.dcm      312 MB    3f4a9b12⧉     [Download]         │ │
│ │ study_3f4a9b12/002.dcm      312 MB    7c2d1e98⧉     [Download]         │ │
│ │ ... (10 more)                                                           │ │
│ │                                                                         │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

**컴포넌트**:
- `<TopNav>`, back link
- Header meta
- `<ExpirationCountdown>` (C-17) + Refresh button
- "Download all" secondary CTA (manifest blob generate)
- `<Tabs>` 3개
  - Browser: `<DataTable>` with filename · size · `<ChecksumCell>` · Download button (target=_blank)
  - curl: `<ApiSnippetTab>` with for-loop snippet + Copy
  - Python: `<ApiSnippetTab>` with httpx parallel example + Copy

**curl snippet template** (Copy tab):
```bash
#!/usr/bin/env bash
set -eu
URLS=(
  "https://storage.radivault.io/...sig=..."
  "https://storage.radivault.io/...sig=..."
)
SHA=(
  "3f4a9b12..."
  "7c2d1e98..."
)
for i in "${!URLS[@]}"; do
  curl -fL "${URLS[$i]}" -o "$(basename "${URLS[$i]%%\?*}")"
done
# Verify
paste <(printf '%s\n' "${SHA[@]}") <(ls *.dcm) | sha256sum -c
```

**Python snippet template**:
```python
import httpx
import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

URLS = [...]   # injected
SHA = [...]
OUT = Path("./download")
OUT.mkdir(exist_ok=True)

def fetch(i, url, expected_sha):
    fn = OUT / url.split("?")[0].rsplit("/", 1)[-1]
    with httpx.stream("GET", url, timeout=60) as r:
        r.raise_for_status()
        h = hashlib.sha256()
        with fn.open("wb") as f:
            for chunk in r.iter_bytes(chunk_size=1 << 20):
                h.update(chunk)
                f.write(chunk)
    assert h.hexdigest() == expected_sha, f"sha mismatch {fn}"
    return fn

with ThreadPoolExecutor(max_workers=12) as pool:
    futs = [pool.submit(fetch, i, u, SHA[i]) for i, u in enumerate(URLS)]
    for f in futs:
        print(f.result())
```

**상태**:
- Expires < 10 min: countdown bg warning-100 + hint "Consider refreshing."
- Expired: `Expired` + all Download buttons disabled + only Refresh enabled + bg danger-100.
- Refresh loading: button spinner.
- Refresh 429: `<ErrorBanner>` "Refresh limit reached. Wait 60s."

**카피**:
- Tab labels: `Browser`, `curl`, `Python`
- Table column: `File`, `Size`, `SHA-256`, `Action`
- Download all CTA: `Download all (.json manifest)`
- Refresh CTA: `Refresh URLs`
- Expired state: `Expired` + `Refresh URLs`

**접근성**:
- Tabs: ARIA tabs pattern (arrow key nav between tabs).
- Countdown: `aria-live="off"` (초당 업데이트 noise 회피). 마지막 5분에만 `aria-live="polite"` 로 전환.

**데모 연결**: 장면 5 후반 (Ctrl+5 → tracker → Downloads tab → Copy curl).

---

### 5.A-9 Account (`/account`)

**ASCII 와이어**:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [RadiVault]   Search  Orders  Downloads  Docs                 [⌘K]  [ Dana ▾]│
├─────────────────────────────────────────────────────────────────────────────┤
│ Account                                                                     │
│                                                                             │
│ API key                                                                     │
│   rv_live_****_***************ef12                              [ Copy ]    │
│   Managed by RadiVault SRE. Contact support for rotation.                   │
│                                                                             │
│ Tier                                                                        │
│   Paid · 10,000 studies / day                                               │
│                                                                             │
│ Today's usage                                                               │
│   127 / 10,000 studies · resets in 04h 17m                                  │
│                                                                             │
│ ─────                                                                       │
│                                                                             │
│ [ Contact support ]      [ Sign out ]                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**컴포넌트**: 단순 stat list + 2 footer buttons.

**카피**:
- Heading: `Account`
- Sections: `API key`, `Tier`, `Today's usage`
- Masking: `rv_live_****_***************ef12` (첫 8 + 마지막 4 노출, 나머지 `*`, dev-spec FR-A-60)
- Bottom: `Contact support` (mailto), `Sign out` (destructive ghost)

**데모 연결**: 미노출 (존재 증명만).

---

## §5-B Hospital Dashboard 화면 명세

### 5.B 전체 레이아웃 (`/hospital/{gateway_id}`)

**ASCII 와이어 (1920x1080, 1-scroll 완결, dev-spec FR-B-8)**:
```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│ 병원 파트너 대시보드                                                 마지막 업데이트 18:32   │
│ 김씨병원 · Gateway H001                                                          [로그아웃] │
├───────────────────────────┬───────────────────────────┬─────────────────────────────────────┤
│                           │                           │                                     │
│  B-1 오늘/누적 스터디     │  B-2 예상 수익 (시뮬)     │  B-3 기여 지역                      │
│                           │                           │                                     │
│     42                    │   ₩ 18,450,000            │      ┌────── KOREA MAP ──────┐      │
│   오늘                    │                           │      │                       │      │
│                           │   [bar chart 12m]         │      │   ● 서울 강남         │      │
│   누적  12,478            │   . . . ▌▌▌▌▌▌▌▌▌        │      │                       │      │
│                           │                           │      │                       │      │
│                           │   시뮬레이션 — v0.2 정산  │      └───────────────────────┘      │
│                           │   대기                    │                                     │
│                           │                           │                                     │
│  ↻ 18:32                  │  ↻ 18:32                  │  ↻ 18:32                           │
├───────────────────────────┼───────────────────────────┼─────────────────────────────────────┤
│                           │                           │                                     │
│  B-4 Gateway 상태         │  B-5 최근 주문            │  B-6 최근 감사 이벤트               │
│                           │                           │                                     │
│  ● Online                 │  ord_5a3f · 12 · 완료     │  18:30:12 · 입수 · 3f4a9b12        │
│  last sync 2분 전         │  ord_7c2e · 24 · 준비 중  │  18:29:45 · 업로드 · 7c2d1e98      │
│                           │  ord_a1b2 ·  8 · 접수     │  18:27:03 · 앵커 · a1b2c3d4        │
│  Heartbeat 180s           │  ord_b2c3 · 30 · 완료     │  18:22:11 · 주문 배송 · b2c3d4e5   │
│                           │  ord_c3d4 ·  5 · 실패     │  18:18:50 · 입수 · c3d4e5f6        │
│                           │  ... (5 more)             │  ... (5 more)                       │
│                           │                           │                                     │
│  ↻ 18:32                  │  ↻ 18:32                  │  ↻ 18:32                           │
└───────────────────────────┴───────────────────────────┴─────────────────────────────────────┘
 640px                        640px                        640px          (3-column grid, gap 20)
 min-height: 320px each, total ~680px with header (72px) → fits 1080p
```

**컴포넌트 계층**:
- `<HospitalHeader>` (C-3)
- `<DashboardGrid>` (CSS Grid 3 cols × 2 rows, gap-5)
  - `<TileCard variant="metric" id="B-1">` — Studies
  - `<TileCard variant="chart" id="B-2">` — Revenue + `<RevenueDisclaimer>` + Recharts BarChart
  - `<TileCard variant="map" id="B-3">` — `<KoreaHeatmap>`
  - `<TileCard variant="status" id="B-4">` — `<GatewayStatusDot>` + heartbeat
  - `<TileCard variant="list" id="B-5">` — 10 `<PhaseBadge>` rows
  - `<TileCard variant="list" id="B-6">` — 10 `<AuditRow>`

### 5.B-1 Studies Tile

**레이아웃 (tile 내부)**:
```
┌────────────────────────────────────┐
│ 오늘 / 누적 제공 스터디  18:32 ↻  │ (title small · update timestamp)
├────────────────────────────────────┤
│                                    │
│       42                           │ (big number, 48px bold tabular-nums,
│     오늘                           │  sub 14px neutral-500)
│                                    │
│   ─ 누적  12,478 ─                 │ (secondary metric row, 14px)
│                                    │
└────────────────────────────────────┘
```

**상태**:
- Loading: 숫자 skeleton (hatch rect 80×48).
- Stale (polling 실패): 마지막 값 유지 + 외곽 border warning-500 2px + ⚠ 아이콘.
- 0 or no data: "아직 데이터가 없습니다" gray center.

**카피**:
- Title: `오늘 / 누적 제공 스터디`
- Sub: `오늘`, `누적`
- Empty: `아직 데이터가 없습니다`

### 5.B-2 Revenue Tile (+ Disclaimer)

**레이아웃**:
```
┌────────────────────────────────────┐
│ 예상 수익 (시뮬레이션)     18:32 ↻ │
├────────────────────────────────────┤
│                                    │
│     ₩ 18,450,000                   │ (big, 48px bold)
│     누적 12개월                    │
│                                    │
│   ▌▌▌▌▌▌▌▌▌▌▌▌                   │ (Recharts horizontal bar chart)
│   │││││││││││││                   │ (12 months, hospital-primary-500)
│   J F M A M J J A S O N D          │
│                                    │
│                                    │
│   시뮬레이션 — v0.2 정산 대기      │ (disclaimer, text-xs medium neutral-500)
└────────────────────────────────────┘
```

**상태**:
- Loading: 숫자 skeleton + chart shimmer.
- Stale: 동일 warning border.
- Disclaimer: **항상 표시, 제거 불가, snapshot test 로 회귀 보장** (AC-B-5).

**카피**:
- Title: `예상 수익 (시뮬레이션)`
- Sub: `누적 12개월`
- Disclaimer: `시뮬레이션 — v0.2 정산 대기` (dev-spec FR-B-10 고정)
- Bar chart x-axis: `1월 2월 ... 12월` (한국어 월 표기)

### 5.B-3 Map Tile (KoreaHeatmap)

**레이아웃**:
```
┌────────────────────────────────────┐
│ 기여 지역                 18:32 ↻  │
├────────────────────────────────────┤
│                                    │
│          ┌──────────────┐          │
│          │   [한국 지도] │          │
│          │              │          │
│          │       ●서울강남│         │
│          │              │          │
│          └──────────────┘          │
│                                    │
│   1개 파일럿 병원 기여 중          │
│                                    │
└────────────────────────────────────┘
```

**상태**:
- Loading: 전체 영역 neutral-100 pulse.
- Static (v0.1): 1~2 point 하이라이트 고정. 드릴다운 없음 (dev-spec §0.2-13).

**접근성**: `role="img" aria-label="한국 지도 — 현재 파일럿 병원 1곳 서울 강남"`.

**카피**:
- Title: `기여 지역`
- Sub: `{n}개 파일럿 병원 기여 중`
- Tooltip (hover point): `김씨병원 — 서울 강남`

### 5.B-4 Gateway Status Tile

**레이아웃**:
```
┌────────────────────────────────────┐
│ Gateway 상태               18:32 ↻ │
├────────────────────────────────────┤
│                                    │
│     ● Online                       │ (green dot + text)
│                                    │
│     last sync 2분 전               │ (neutral-500)
│                                    │
│     heartbeat 180s                 │
│                                    │
│                                    │
└────────────────────────────────────┘
```

**3-state 상세**:

| State | Dot color | Text | 조건 | bg |
|---|---|---|---|---|
| Online | success-500 | `● Online` | last_sync < 5m | 없음 |
| Warning | warning-500 | `● Warning — 최근 동기화 15분 전` | 5m ≤ last_sync < 30m | warning-100 (tile 전체) |
| Offline | danger-500 | `● Offline — 최근 동기화 2시간 전` | ≥ 30m | danger-100 |

**상태**: pulse animation on Online dot only.

**카피**:
- Title: `Gateway 상태`
- Sub fields: `최근 동기화 {N}분 전`, `heartbeat {seconds}s`
- 상세 states 위 표.

### 5.B-5 Recent Orders Tile

**레이아웃**:
```
┌────────────────────────────────────┐
│ 최근 주문                 18:32 ↻  │
├────────────────────────────────────┤
│ ord_5a3f · 12 ·[완료] · 3분 전     │
│ ord_7c2e · 24 ·[준비 중] · 5분 전   │
│ ord_a1b2 ·  8 ·[접수] · 10분 전     │
│ ord_b2c3 · 30 ·[완료] · 45분 전     │
│ ord_c3d4 ·  5 ·[실패] · 1시간 전    │
│ ...                                │
└────────────────────────────────────┘
```

- Row: `order_id_masked (4자) · n_studies · <PhaseBadge ko> · relative time`.
- 최대 10 row. 초과 시 `→ 전체 보기 (v0.1.1)` placeholder link (clickable X, ghost).
- Phase 한국어 매핑 (C-4 표).

**카피**:
- Title: `최근 주문`
- Phase labels: `접수`, `병원에서 가져오는 중`, `준비 중`, `다운로드 준비 완료`, `완료`, `취소`, `만료`, `실패`
- Relative time: `방금`, `3분 전`, `45분 전`, `1시간 전`, `2025-04-23` (24h 이상 절대 날짜)

### 5.B-6 Recent Audit Tile

**레이아웃**:
```
┌────────────────────────────────────┐
│ 최근 감사 이벤트        18:32 ↻    │
├────────────────────────────────────┤
│ 18:30:12 · 입수 · 3f4a9b12         │
│ 18:29:45 · 업로드 · 7c2d1e98        │
│ 18:27:03 · 앵커 · a1b2c3d4         │
│ 18:22:11 · 주문 배송 · b2c3d4e5    │
│ 18:18:50 · 입수 · c3d4e5f6         │
│ ...                                │
└────────────────────────────────────┘
```

- Row: `HH:MM:SS · event_type_ko · hash_short(8)`.
- Font mix: 시각 tabular-nums, 타입 한글, 해시 mono.
- 클릭 불가 (info-only).

**event_type 한영 매핑**:

| dev-spec type | 한국어 | 영어 (tooltip) |
|---|---|---|
| `ingest.accepted` | 입수 | Ingest accepted |
| `ingest.rejected` | 입수 거부 | Ingest rejected |
| `upload.completed` | 업로드 | Upload completed |
| `anchor.recorded` | 앵커 | Anchor recorded |
| `order.delivered` | 주문 배송 | Order delivered |

### 5.B-7 Hospital Signin (`/hospital/signin`)

**ASCII**:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│              ┌──────────────────────────────────┐                           │
│              │      병원 파트너 대시보드         │                          │
│              │                                  │                           │
│              │  Gateway ID                      │                           │
│              │  [ H001 ▾ ]                      │                           │
│              │                                  │                           │
│              │  병원 관리자 토큰                  │                          │
│              │  ┌────────────────────────────┐  │                           │
│              │  │ ••••••••••••               │  │                           │
│              │  └────────────────────────────┘  │                           │
│              │                                  │                           │
│              │  [  로그인                   →]  │                           │
│              │                                  │                           │
│              │  토큰 분실 시 전산실장에게 문의     │                         │
│              └──────────────────────────────────┘                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**카피**:
- Title: `병원 파트너 대시보드`
- Labels: `Gateway ID`, `병원 관리자 토큰`
- CTA: `로그인` `→`
- Hint: `토큰 분실 시 전산실장에게 문의`
- Errors (한국어):
  - `토큰이 올바르지 않습니다.` (403)
  - `세션이 만료되었습니다. 다시 로그인해 주세요.` (401)
  - `일시적 오류입니다. 잠시 후 다시 시도해 주세요.` (5xx)

### 5.B-8 Empty / Gateway 미연결 상태

**Gateway 미연결 (초기 설정 전) 시 대시보드 전체**:
```
┌──────────────────────────────────┐
│                                  │
│       ⚠  Gateway 미연결          │
│                                  │
│  Gateway Agent 설치가 아직        │
│  완료되지 않았습니다.             │
│                                  │
│  전산실장에게 연락하거나          │
│  온보딩 가이드를 참고하세요.      │
│                                  │
│  [  온보딩 가이드 보기  →  ]      │
│                                  │
└──────────────────────────────────┘
(centered, full page, 전체 tile 대체)
```

- `docs/marketing/onboarding-hospital-it-admin-ko.md` 링크.
- 데모 시나리오에는 절대 도달하지 않음. 실 파일럿 초기 1~2시간 노출 가능.

---

## §6 Demo Operator Mode UX

### 6.1 활성 조건

- `?demoop=1` + `demoop_token=<sha>` 쿼리 (or `X-Demoop-Token` 헤더)
- 환경변수 `DEMOOP_TOKEN` 설정된 배포에서만 동작
- 프로덕션 배포 (환경변수 미설정) 에서는 `?demoop=1` 무시

### 6.2 시각 요소 (5종)

#### OP-1 DEMO MODE 배지

- 위치: 우상단 고정. 모든 페이지.
- 컴포넌트: `<DemoOperatorBadge>` (C-14).
- 색상: danger-500 bg, white text, pulse animation 1s loop.
- 크기: 160×64px, z-index 70.
- 한국어/영어 구분 없음 — 전부 영어 (`DEMO MODE`).

#### OP-2 Shortcut Panel (Ctrl+Shift+D)

- 위치: 우상단 배지 클릭 or Ctrl+Shift+D → panel expand.
- 레이아웃 (ASCII):
```
┌────────────────────────────────────────┐
│ ● DEMO MODE                            │
│ Scene 3/7 · 08:23 / 17:00              │
├────────────────────────────────────────┤
│ Shortcut                               │
│   Ctrl+1  Home                         │
│   Ctrl+2  Search (seeded)              │
│   Ctrl+3  Hospital Dashboard           │
│   Ctrl+4  Search CT Spine              │
│   Ctrl+5  Order tracker (ready)        │
│   Ctrl+6  Hospital revenue focus       │
│   Ctrl+7  Home (closing)               │
│   Ctrl+.  Next scene                   │
│   Ctrl+R  Soft reset                   │
├────────────────────────────────────────┤
│ [ Canned overlay: OFF ▸ ]              │
│ [ Reset demo data       ]              │
└────────────────────────────────────────┘
width: 320px · shadow-lg
```

#### OP-3 Reset Button

- Soft: DB truncate + staging clear, Orthanc 보존 (~1 min).
- 클릭 시 confirm dialog `Reset demo data? This truncates orders and download URLs.` + 2 btn (Cancel / Confirm).
- Progress: loading overlay + "Resetting... 00:45" timer.

#### OP-4 Canned Overlay Toggle

- 토글 시 BFF route handler 가 canned JSON 파일에서 응답 로드.
- UI 표시: 우하단 `canned` stamp (text-xs amber, 정적).
- 네트워크 탭에서 /api/* 호출이 local JSON 반환 (observable via QA, AC-D-3).

#### OP-5 Scene Progress Indicator

- 좌하단 고정: `Scene 3/7 — 08:23 / 17:00`.
- 색상: neutral-600 bg-neutral-100.
- Ctrl+. 로 다음 scene 으로 타이머 advance.

### 6.3 프레젠터 편의 UX

- Ctrl+1~7 pre-warmed URL (dev-spec FR-D-7) — 각 shortcut 눌린 순간 해당 URL 로 이동 + scene indicator 증가.
- 각 shortcut 은 미리 정의된 쿼리 파라미터 포함 — 예: Ctrl+4 → `/search?modality=CT&body_part=SPINE&_seed=canned`.
- Scene timer 는 페이지 새로고침 시 리셋 X (sessionStorage).

### 6.4 보안·관객 은닉

- DEMO MODE 배지는 관객이 보는 화면에서 **작게 (16px text)** 유지 — 혼란 최소화.
- Shortcut panel 은 기본 숨김 (Ctrl+Shift+D 로만 토글) — 관객에게는 안 보임.
- Canned stamp 는 presenter 본인만 확인용 (관객은 못 본다고 전제, 화면 구석 2px × 2px 점 가능).

### 6.5 데모 중 권장 행동 (연출)

- 장면 시작 전 Ctrl+Shift+D 로 panel expand → 자신 확인 → 다시 닫기.
- Canned overlay 는 **기본 OFF**. 실패 감지 시 3초 내 toggle (dev-spec R-3).
- Scene 전환은 Ctrl+1~7 사용 — 수동 URL 입력 금지 (마찰 회피).
- Reset 은 D-0 직전 1회, 데모 중에는 **사용 금지** (panic 유발).

---

## §7 상태 / 에러 / 로딩 / 빈 상태 taxonomy

### 7.1 상태 매트릭스 (화면 × 상태)

| 화면 | Loading | Empty | 4xx | 5xx | Network | No-permission | Partial |
|---|---|---|---|---|---|---|---|
| A-1 Home | Skeleton 3 tiles | N/A | tiles "—" | tiles "—" | banner | N/A | — |
| A-2 Signin | Submit spinner | N/A | inline banner | system banner | offline banner | N/A | — |
| A-3 Search | Skeleton table + facets | EmptyState no-results | ERR_*  banner, table disabled | system banner | offline banner | redirect /signin | facet 일부만 로드 → 나머지 skeleton |
| A-4 Study Detail | Skeleton 10 rows | Not found banner | inline banner | system banner | offline banner | redirect | — |
| A-5 Review Modal | Submit spinner | N/A | inline banner | system banner | offline banner | redirect | — |
| A-6 Orders | Skeleton 10 rows | EmptyState no-orders | banner | system banner | offline | redirect | — |
| A-7 Order Detail | Skeleton stepper + meta | N/A (항상 1 order) | 404 "Order not found" | system | offline | redirect | timeline 실패 → 스텝퍼만 |
| A-8 Downloads | Skeleton table | N/A | Expired banner | system | offline | redirect | URL 일부 mint 실패 → 해당 row error |
| A-9 Account | Skeleton 4 fields | N/A | banner | system | offline | redirect | — |
| B-1..B-6 (tile) | Skeleton tile | 타일 내부 "아직 데이터가 없습니다" | 타일 내부 error icon | 타일 내부 stale border | tile stale | redirect /hospital/signin | tile 개별 독립 — 일부 성공/일부 stale |

### 7.2 에러 코드 → 사용자 메시지 매핑 (발췌)

dev-spec §7 및 기존 design-spec-metadata-index §5, design-spec-order-fulfillment §5 에러 taxonomy 를 **재사용** 한다. 본 document 는 신규 환경 (포털 UI) 에서의 **메시지 rendering 규약** 만 정의.

**환경**: 포털 BFF route handler 는 업스트림 에러 envelope 을 그대로 브라우저에 전달 + 본 표에 정의된 UI 렌더링 규칙 적용.

| Code | HTTP | 영어 메시지 | 한국어 메시지 | 렌더 위치 | 복구 CTA |
|---|---|---|---|---|---|
| `ERR_AUTH_FORMAT` | 400 | Invalid API key format. Keys start with `rv_live_`. | API 키 형식이 올바르지 않습니다. 키는 `rv_live_` 로 시작합니다. | signin inline | Retry |
| `ERR_AUTH_INVALID` | 401 | Your API key is invalid or revoked. | API 키가 유효하지 않거나 회수되었습니다. | signin inline | Contact support |
| `ERR_AUTH_EXPIRED` | 401 | Your session expired. Please sign in again. | 세션이 만료되었습니다. 다시 로그인해 주세요. | toast + redirect | Sign in |
| `ERR_SCOPE_FORBIDDEN` | 403 | You don't have access to this hospital's data. | 이 병원 데이터에 접근 권한이 없습니다. | banner | Contact support |
| `ERR_REQUEST_SCHEMA` | 400 | Your request has invalid fields. | 요청 필드가 올바르지 않습니다. | banner (detail 상세) | Inspect request |
| `ERR_FILTER_TOO_MANY` | 400 | Too many filters selected. Maximum 10. | 필터를 너무 많이 선택했습니다. 최대 10개. | banner | Clear some filters |
| `ERR_QUERY_TOO_BROAD` | 400 | Your search is too broad. Narrow with modality or body_part. | 검색 범위가 너무 넓습니다. modality 또는 body_part 로 좁혀 주세요. | banner | Refine filters |
| `ERR_QUERY_TIMEOUT` | 504 | Search timed out. Try narrowing your filters. | 검색 시간이 초과되었습니다. 필터를 좁혀 주세요. | banner | Retry |
| `ERR_BUYER_QUOTA` | 429 | Daily quota reached. Resets at {X}. | 일일 쿼터를 초과했습니다. {X} 에 재설정됩니다. | banner | Wait / contact sales |
| `ERR_BUYER_CONCURRENCY` | 429 | Too many concurrent requests. | 동시 요청이 너무 많습니다. | banner | Retry later |
| `ERR_STUDY_NOT_FOUND` | 404 | Study not found or out of your scope. | 스터디를 찾을 수 없거나 접근 범위 밖입니다. | drawer inline | Close |
| `ERR_ORDER_NOT_FOUND` | 404 | Order not found. | 주문을 찾을 수 없습니다. | page | Back to orders |
| `ERR_ORDER_EXPIRED` | 410 | This order expired. Place a new order for the same cohort. | 주문이 만료되었습니다. 동일 코호트로 새 주문을 등록하세요. | page banner | New order |
| `ERR_ORDER_CANCELLED` | 410 | This order was cancelled. | 주문이 취소되었습니다. | page banner | — |
| `ERR_ORDER_FAILED` | 500 | This order failed. Contact support. | 주문 처리에 실패했습니다. 지원팀에 문의하세요. | page banner | Contact support |
| `ERR_QUOTA_STUDIES_EXCEEDED` | 422 | Order exceeds per-order study limit (1000). | 주문이 1회 상한 (1,000건) 을 초과합니다. | modal inline | Reduce cohort |
| `ERR_IDEMP_MISMATCH` | 409 | This idempotency key was used with different payload. | 동일 idempotency 키가 다른 본문으로 이미 사용되었습니다. | modal inline | Go to existing order |
| `ERR_URL_REFRESH_RATE` | 429 | Refresh limit reached. Wait {N}s. | 재발급 상한 초과. {N}초 대기. | downloads banner | Wait |
| `ERR_URL_MINT_FAILED` | 500 | Couldn't mint download URLs. Retry or contact support. | 다운로드 URL 발급 실패. 재시도 또는 지원팀 문의. | downloads banner | Retry |
| `ERR_UPSTREAM_TIMEOUT` | 502 | Upstream service timed out. Please retry. | 업스트림 서비스가 응답하지 않습니다. 재시도해 주세요. | system banner | Retry |
| `ERR_UPSTREAM_UNAVAILABLE` | 503 | Service temporarily unavailable. | 서비스가 일시적으로 이용 불가입니다. | system banner | Retry in 1 min |

전체 코드 사전은 dev-spec §7 + design-spec-metadata-index §5 + design-spec-order-fulfillment §5 를 참조.

### 7.3 로딩 스켈레톤 패턴

- **Table skeleton**: 10 rows, 각 row 높이 44px, 각 cell 의 rect width 가 실제 컬럼 width 의 60~80% 랜덤.
- **Tile skeleton**: 전체 rect neutral-100 pulse, 중앙 작은 rect (big number 자리).
- **Stepper skeleton**: 5 개 작은 circle + line, neutral-100.
- **Chart skeleton**: 12 개 vertical rect, 랜덤 높이 (20~80%), neutral-100 pulse.
- **Map skeleton**: 전체 영역 neutral-100 solid (pulse 없음 — SVG 가 크면 pulse 가 distracting).

Shimmer 방향: LTR, 1.5s loop. `prefers-reduced-motion` 시 pulse 로 대체 (일정 opacity 0.6→1 2s).

### 7.4 Empty 상태 3 종

**Buyer**:
- No results (`variant="no-results"`): 아이콘 `SearchX`, 제목 `No studies match these filters.`, 본문 `Try widening the date range or removing min_hospitals ≥ 3.`, CTA `Clear all filters`.
- No orders (`variant="no-orders"`): 아이콘 `Inbox`, 제목 `You haven't placed any orders yet.`, 본문 `Start by searching for a cohort.`, CTA `Go to Search →`.
- No downloads ready (`variant="no-downloads"`): 아이콘 `Clock`, 제목 `Your order is still preparing.`, 본문 `Average ETA for 100 studies: ~30 minutes. Refresh in 30s.`, CTA `Refresh` (auto-timer 30s).

**Hospital**:
- Tile empty (`"아직 데이터가 없습니다"`, 모든 타일 공통): 아이콘 `Inbox`, 중앙 텍스트만. CTA 없음 (경영진 대상 행동 촉구 회피).
- Gateway 미연결 (전체 페이지): 위 §5.B-8.

### 7.5 Partial failure — Hospital Dashboard 6 tile 개별 독립

- 각 tile 은 독립 폴링. 1개 tile 실패 → 해당 tile 만 stale indicator (warning border + ⚠).
- 5xx 연속 실패 시 tile 내부 "데이터 로드 실패 · {N}초 후 재시도" + subtle retry button.
- 2개 이상 tile 동시 실패 시 페이지 상단 globa banner: `일부 데이터 로드에 실패했습니다.` + `전체 새로고침` CTA.

### 7.6 PHI-suspect variant (비상)

- 발생 조건: 브라우저 쪽 샘플링 (dev-spec AC-X-4) 에서 의심 필드 감지 (`PatientName`, `PatientID`, 비-shifted date 등).
- UI: `<ErrorBanner variant="phi-suspect">` 전체 페이지 overlay (z-modal), 빨강 full bleed.
- 메시지: `Sensitive field detected. This window will close in 3 seconds.` → auto `window.close()` after 3s.
- 동시: client → BFF `/api/report-phi` POST (request_id 포함) → SRE 알람.
- **데모 중 트리거 시**: 런북 dev-spec §9.3 "PHI 의심" 5초 액션과 일치 — Cmd+W.

---

## §8 Top nav / Navigation / URL 구조

### 8.1 Buyer Portal URL

| URL | Public/Auth | 화면 |
|---|---|---|
| `/` | Public | Home (A-1) |
| `/signin` | Public | Signin (A-2) |
| `/search` | Auth | Search (A-3) |
| `/search?study={uid}` | Auth | Search + Study drawer (A-3 + A-4) |
| `/orders` | Auth | Orders list (A-6) |
| `/orders/{id}` | Auth | Order detail (A-7) |
| `/orders/{id}/downloads` | Auth | Downloads (A-8) |
| `/account` | Auth | Account (A-9) |
| `/404` | N/A | Not found |
| `/500` | N/A | Error |
| `/api/*` | BFF | Internal only (브라우저 navigate 금지) |

### 8.2 Hospital Dashboard URL

| URL | Public/Auth | 화면 |
|---|---|---|
| `/hospital/signin` | Public (ko) | Signin (B-7) |
| `/hospital/{gateway_id}` | Auth | Dashboard (B-1..B-6) |
| `/hospital/{gateway_id}/signin` | alias of /hospital/signin | — |
| `/api/hospital/*` | BFF | Internal only |

### 8.3 Top nav 레이블 (Buyer 영어)

- Logo → `/`
- `Search` → `/search`
- `Orders` → `/orders`
- `Downloads` → `/orders/{id}/downloads` (latest ready) or disabled
- `Docs` → external (v0.1: `/docs/api-quickstart` placeholder)
- `⌘K` command palette placeholder (disabled + tooltip "Coming soon")
- Profile dropdown:
  - `Account` → `/account`
  - `API docs` → external
  - `Sign out` → POST + redirect `/`

### 8.4 Hospital 상단 (단일 페이지, 네비 없음)

- 좌측: `병원 파트너 대시보드 / 김씨병원 · Gateway H001`
- 우측: `마지막 업데이트 18:32` + `[로그아웃]`

### 8.5 라우팅 가드

- `/search|/orders|/orders/*|/account` → 쿠키 없으면 307 → `/signin` (dev-spec FR-A-2).
- `/hospital/{id}` → 쿠키 없으면 307 → `/hospital/signin`.
- `/api/session` → BFF only, 브라우저 navigate 시 405.
- 404 → 커스텀 페이지 (영어/한국어 locale 자동).

### 8.6 Breadcrumb

- Orders detail (A-7): `← Orders`
- Downloads (A-8): `← Order ord_5a3f...`
- Study drawer: 독립 드로어, breadcrumb 없음 (닫기 X).

---

## §9 국제화 정책

### 9.1 언어 분리

- Buyer Portal: 영어 전용. 한국어 탭·토글 없음. 이유: dev-spec §0.2-5, 구매자 글로벌.
- Hospital Dashboard: 한국어 전용.
- 공통 에러 코드 페이로드: `message_ko` + `message_en` 모두 포함 → 표시는 해당 locale 기준 1개만.

### 9.2 파일 구조

```
apps/portal/messages/
  en.json        # Buyer 전체
  ko.json        # Hospital 전체 + Buyer 내 에러 병기용 일부
```

### 9.3 텍스트 확장 규칙

- 한국어는 영어 대비 평균 30% 짧음 (CJK 글자 밀도).
- 버튼: `Sign in` (영어) vs `로그인` (한국어) — 영어 기준으로 min-width 지정, 한국어는 자연 centering.
- 테이블 컬럼 헤더: 영어는 약어 (`N`, `Size`, `ETA`), 한국어는 풀 (`스터디 수`, `크기`, `예상 완료`).
- 에러 메시지: 한국어는 문장 끝 마침표 + 존댓말 (`...하세요.`, `...됩니다.`).

### 9.4 날짜·시간·숫자·통화

| 항목 | 영어 (Buyer) | 한국어 (Hospital) |
|---|---|---|
| 절대 날짜 | `2026-04-24 18:34 KST` | `2026년 4월 24일 18:34` |
| 상대 시간 | `3m ago` | `3분 전` |
| 숫자 | `1,234,567` | `1,234,567` (동일) |
| 통화 | 마스킹 `—` | `₩ 18,450,000` |
| 파일 크기 | `312 MB`, `1.2 GB` | 동일 |
| SHA-256 | `3f4a9b12...` | 동일 (mono) |

### 9.5 RTL / 세계화

- v0.1 LTR only. 아랍어/히브리어 대응 없음.
- next-intl `formatjs` 사용. number/currency/date ICU message syntax 준수.

---

## §10 접근성

### 10.1 WCAG 2.1 AA 준수 체크리스트

- **1.4.3 Contrast (Minimum)**: body text ≥ 4.5:1, large text ≥ 3:1, UI component ≥ 3:1. §2.1 주석에서 핵심 대비 검증.
- **1.4.11 Non-text Contrast**: modality 배지 색상은 텍스트(2자) 대비 4.5 이상 보정 색 쓸 것 (예: MG 배지의 text 는 `#9d174d` 로 어둡게).
- **2.1.1 Keyboard**: 모든 interactive 요소 Tab 도달. Search 3-pane 순서: facets → table → cohort → top nav → profile.
- **2.4.3 Focus Order**: DOM 순서 = 논리 순서.
- **2.4.7 Focus Visible**: 2px offset primary-500 ring.
- **3.2.1 On Focus**: focus 만으로 컨텍스트 변경 금지 (drawer/modal auto-open 금지).
- **3.3.1 Error Identification**: 에러 발생 시 `role="alert"` or `aria-live="assertive"`.
- **4.1.2 Name, Role, Value**: 커스텀 컴포넌트는 Radix primitive 기반 → ARIA 자동.

### 10.2 키보드 탐색 순서

**A-3 Search**:
```
1. Top nav (Logo → Search → Orders → Downloads → Docs → ⌘K → Profile)
2. Active filter chips (dismissible)
3. Facet groups (7개 순차, 각 group 내 checkbox 순차)
4. DataTable (sort headers → row 1 checkbox → row 1 link → row 2 checkbox → ...)
5. Pagination
6. Cohort sidebar (links + Review order button)
```

**A-7 Order detail**:
```
1. Top nav
2. Back link
3. Copy order_id
4. Cancel order (if enabled)
5. View timeline
6. Go to Downloads (if enabled)
```

**B (Hospital)**:
```
1. 로그아웃
2. Tile 1 → Tile 2 → ... → Tile 6 (focusable region)
3. 각 tile 은 interactive 요소 있을 때만 Tab 진입 (v0.1 대부분 정보 전용)
```

### 10.3 스크린리더

- 폴링 타일: `aria-live="polite"` — 값 변경 시 조용히 공지.
- 에러 banner: `aria-live="assertive"` + `role="alert"`.
- 카운트다운 (A-8): `aria-live="off"` 기본, 마지막 5분부터 `"polite"` + 1분 간격으로 공지.
- SVG map: `role="img"` + `aria-label` + `<VisuallyHidden>` 로 상세 텍스트.
- Modality 배지: `aria-label="Modality: CT"`.
- Phase stepper: `role="list"` + 각 step `role="listitem" aria-current="step"` (active 만).

### 10.4 색 대비 핫스팟

| 조합 | 비율 | 판정 | 비고 |
|---|---|---|---|
| neutral-700 on neutral-50 (body) | 11.9:1 | AAA | 기본 텍스트 |
| buyer-primary-600 on white (CTA) | 5.2:1 | AA | 버튼 |
| hospital-primary-700 on white | 6.6:1 | AAA | 타이틀 |
| status-danger-500 on white | 4.7:1 | AA boundary | **굵게 권장**, 작은 텍스트는 `-600` 사용 |
| modality-MG (#ec4899) 배지 text | 3.3:1 | **FAIL** | **수정** — 배지 텍스트는 `#9d174d` (pink-800) 사용 |
| neutral-400 muted | 4.4:1 on white | AA fail | placeholder, secondary 전용 (WCAG 예외 해석) |
| warning-500 (#f59e0b) on white | 2.8:1 | FAIL | 배경으로만, 텍스트로는 `-700` 사용 |

**수정 액션**: 본 design-spec 확정 시 디자이너가 모든 pill/badge 텍스트 색상을 `*-800` 또는 `*-900` 으로 일괄 어둡게 보정한다.

### 10.5 다크 모드 (MVP 여부)

- dev-spec §11 Q-UI-1: Kyle 결정. v0.1 **라이트 only**.
- shadcn/ui 토큰은 `data-theme="dark"` 자동 대응 — 1일 추가 투입으로 확장 가능. **v0.1.1 백로그 권고** (의료영상 업계 dark 관례 — §11 open question).
- 본 design-spec 은 light only 토큰만 정의. dark variant 는 UI_GUIDE 승격 시 별 PR.

---

## §11 반응형 Breakpoint

### 11.1 우선순위

- Buyer Portal: **desktop 우선** (1280–1920px), tablet (768–1279px) best-effort.
- Hospital Dashboard: **desktop only** (1280–1920px). 병원 경영진 디스플레이 가정.
- Mobile (<768px): 양쪽 모두 **"please use desktop" fallback 페이지**.

### 11.2 Breakpoint 값 (Tailwind 기본)

- `sm` 640px
- `md` 768px — tablet 진입
- `lg` 1024px
- `xl` 1280px — desktop 표준
- `2xl` 1536px — 큰 데스크탑

### 11.3 Buyer Portal 반응형 규칙

| Breakpoint | Search (A-3) | Orders (A-6) | Downloads (A-8) |
|---|---|---|---|
| < 768px | fallback 페이지 | fallback | fallback |
| 768–1023px (tablet) | 2-pane (facets hidden in drawer button) + table + cohort bottom sheet | 1 col table | Tabs 스크롤 가능 |
| 1024–1279px | 2-pane 유지 | 1 col | Tabs 정상 |
| ≥ 1280px | **3-pane (디자인 기준)** | 표 + 페이지네이션 | Tabs + Expiration 우측 |
| ≥ 1536px | 3-pane + 테이블 extra padding | 동일 | 동일 |

### 11.4 Hospital Dashboard 반응형

- < 1280px: fallback "데스크탑에서 접속해 주세요" 페이지.
- ≥ 1280px: 3×2 grid (각 tile min-width 400px).
- ≥ 1920px: grid 유지 + gap-6, tile 간격 여유.

### 11.5 Fallback mobile 페이지

**ASCII**:
```
┌──────────────────────┐
│                      │
│      [RadiVault]     │
│                      │
│   RadiVault portal   │
│   is designed for    │
│   desktop browsers.  │
│                      │
│   Please visit on a  │
│   screen ≥ 1280px.   │
│                      │
│                      │
└──────────────────────┘
```
- 영어 기본. URL 이 `/hospital/*` 일 경우 한국어 `데스크탑에서 접속해 주세요.` 로 전환.

---

## §12 Design AC (AC-DG-*)

모든 AC 는 디자인 검증 가능. QA 는 Storybook snapshot test / Playwright visual regression / Lighthouse 로 검증.

- [ ] **AC-DG-1**: Home (A-1) headline 은 `Korea's medical imaging data, compliantly delivered to the world's AI.` 이며 `h1` 태그, text-5xl bold, neutral-900.
- [ ] **AC-DG-2**: A-3 Search 3-pane 레이아웃은 1280px 이상에서 좌 240px / 중앙 flex / 우 280px 그리드로 렌더. < 1280px 에서 tablet fallback (2-pane), < 768px 에서 mobile fallback.
- [ ] **AC-DG-3**: Search 결과 테이블 row 는 44px 높이, hover 시 neutral-50, selected 시 primary-50, modality 배지는 색+2자 텍스트 동반 (색 단독 의미 전달 금지).
- [ ] **AC-DG-4**: Cohort sidebar 는 sticky top: 72px, 스크롤 시 고정. Review order 버튼 0 study 시 disabled + helper.
- [ ] **AC-DG-5**: Review modal (A-5) 가격 영역은 `—` (em dash) 렌더. DUA 체크박스 미체크 시 Confirm 버튼 disabled (aria-disabled=true).
- [ ] **AC-DG-6**: PhaseStepper (A-7) 는 5 phase 가 수평으로 렌더, 현재 phase 색채움+굵게, 이전 phase 체크 + 색채움, 이후 phase neutral-200 outline. 각 phase 하위 `role="listitem"`.
- [ ] **AC-DG-7**: Downloads (A-8) 만료 카운트다운은 23h 기준 초록, 10분 이하 warning-100 bg + hint, 만료 후 danger-100 bg + Refresh 만 enabled.
- [ ] **AC-DG-8**: Hospital Dashboard 6 tile 은 1920×1080 에서 1-scroll 완결 (총 height ≤ 1008, 헤더 72 + grid 680 + padding 256).
- [ ] **AC-DG-9**: B-2 Revenue tile footer 디스클레이머 `시뮬레이션 — v0.2 정산 대기` 는 storybook snapshot test 와 DOM textContent 로 회귀 보장. 수동 CSS 숨김 시도 시 e2e fail.
- [ ] **AC-DG-10**: B-4 Gateway tile 은 last_sync 값에 따라 3 상태 색 전환 — Online(green) / Warning(amber) / Offline(red). Mock data 로 상태 전환 e2e 검증.
- [ ] **AC-DG-11**: DEMO MODE 배지 (C-14) 는 `DEMOOP_TOKEN` 환경변수 설정 + `?demoop=1` 쿼리 시에만 렌더. 프로덕션 (env 미설정) 환경에서는 DOM 에 존재하지 않음 (not hidden, 완전 없음).
- [ ] **AC-DG-12**: 모든 에러 배너는 code + 영어 메시지 + 한국어 메시지 + request_id + Copy 버튼을 포함. Copy 클릭 시 clipboard 에 request_id 복사 + toast "Copied".
- [ ] **AC-DG-13**: 키보드 Tab 탐색으로 모든 interactive 요소 도달, focus ring 가시 (2px offset primary-500). 테스트: Playwright axe scan 위반 0.
- [ ] **AC-DG-14**: Lighthouse (desktop, production build) accessibility ≥ 90, performance ≥ 80, best-practices ≥ 90.
- [ ] **AC-DG-15**: 색 대비 스캔 (Storybook a11y addon) 위반 0. modality-MG text color 는 `#9d174d` 이상 어두움.
- [ ] **AC-DG-16**: i18n — Buyer 영어, Hospital 한국어. locale 강제 전환 불가 (URL path 로 분리 / cookie 로 덮어쓰기 금지).
- [ ] **AC-DG-17**: 폰트 — 영어 Inter, 한국어 Pretendard Variable. self-hosted woff2. FOUT 방지 `font-display: optional`.
- [ ] **AC-DG-18**: 다크모드 — v0.1 라이트만. `prefers-color-scheme: dark` 응답 없음 (v0.1.1 대비 CSS 토큰 구조는 준비).
- [ ] **AC-DG-19**: 애니메이션 — `prefers-reduced-motion: reduce` 시 모든 transition 1ms, pulse/shimmer 정적으로 전환.
- [ ] **AC-DG-20**: demo-script-radivault.md v0.2 — §2 장면 1~7 영어 대사 채워짐, §5 Q&A 20건 상세 답변 채워짐, §4 리허설 R-8 (한·영 대사 정리) 완료 체크.

---

## §13 Open questions

dev-spec §11 오픈 퀘스천 18건 외 디자인 신규 4건:

### 13.1 dev-spec 에서 계승 (재확인 필요)

- **Q-Legal-1**: TCIA CC-BY attribution 문구 Home footer 1줄 충분한가? (§5.A-1)
- **Q-Legal-3**: Hospital B-2 Revenue disclaimer `시뮬레이션 — v0.2 정산 대기` 법적 충분성? (§5.B-2)
- **Q-Demo-2**: B-2 revenue 공식 기본값 — unit_price $5, hospital_share 35%, 환율 1350? (§5.B-2)
- **Q-UI-1**: 다크 모드 v0.1 포함 여부? (§10.5) — 디자이너 권고: v0.1.1. 단 의료 dark 관례는 투자자 인상에 도움.
- **Q-UI-2**: Buyer 한국어 i18n v0.1 포함? 디자이너 권고: v0.1.1. locale detect + 로케이션 스위처 필요.
- **Q-UI-3**: B-2 bar chart 12m vs 6m? 데이터가 초기 3개월만 있을 경우 8개월 공백이 시각적으로 약함 → **디자이너 권고: v0.1 데모는 6m** (Kyle 결정).
- **Q-UI-4**: Study detail drawer vs route? 디자이너 권고: drawer (현 디자인). URL deep-link 필요 시 `?study=...` 쿼리로 drawer auto-open.
- **Q-Brand-1**: Brand logo — v0.1 텍스트 마크 유지 vs 심볼? 디자이너 작업분 0.5일로 간단 lockup 가능. Kyle 결정.
- **Q-Brand-2**: Primary color — Buyer 파랑 + Hospital 틸 분리 (본 design-spec 채택) vs 단일? 현 디자인 권고 유지.
- **Q-Brand-3**: 5 components ("Platform" 단일 vs 분리 표기) — Home 3-tile 및 docs 에서 노출. 디자이너 권고: Home 에서는 "Platform" 단일, Docs 에서는 분리.

### 13.2 디자인 신규 오픈 퀘스천

- **Q-Design-1**: B-3 Korea Map — 17 광역 전체 SVG 출처? 정부 공개 SVG 이미지 라이선스 확인 필요. 대안은 react-simple-maps + topojson.
- **Q-Design-2**: 빈 상태 일러스트 vs lucide 아이콘 only? v0.1 은 아이콘 only 로 단순화 (custom illustration 은 v0.1.1). Kyle 승인.
- **Q-Design-3**: 중립 색 warm vs cool — 현 설계는 slate (cool). Hospital 한국 의료 톤은 slightly warm 권장 관례 있음. Kyle 결정 (현재는 cool 로 통일).
- **Q-Design-4**: 폰트 라이선스 — Pretendard Variable 은 SIL OFL 1.1 (상업 OK), Inter 는 OFL (상업 OK). self-hosted 배포 OK. 단 TCIA 처럼 "Data powered by" 류 attribution 문구는 디자인 footer 에서 다룰 것인가?

---

## §14 Assets needed

본 design-spec 구현에 필요한 자산 목록. 디자이너 (또는 Kyle) 가 v0.1 착수 전 공급.

| # | 자산 | 형식 | 출처 | 타겟 |
|---|---|---|---|---|
| A-1 | RadiVault 워드마크 | SVG (인라인) | 신규 · v0.1 텍스트만, v0.1.5 심볼 | Top nav, Home hero, Hospital header |
| A-2 | Favicon 32×32, 16×16 | ICO + PNG | 신규 | 브라우저 탭 |
| A-3 | Lucide icons subset | npm `lucide-react` | 공개 | 전 화면 (약 40종 사용) |
| A-4 | Korean map SVG (17 광역) | SVG | 공개 gov 데이터 → 단순화 | B-3 Heatmap |
| A-5 | Modality 배지 SVG stub | 인라인 (2자 텍스트) | 자체 | StudyRow, Detail |
| A-6 | Placeholder DICOM thumbnail | SVG 회색 박스 | 자체 | A-4 Study drawer (v0.2 viewer 대체) |
| A-7 | Inter woff2 (Regular/Medium/SemiBold/Bold) | self-hosted | Google Fonts OFL | 영어 |
| A-8 | Pretendard Variable woff2 | self-hosted | 공식 CDN → self | 한국어 |
| A-9 | JetBrains Mono woff2 | self-hosted | OFL | 기술 텍스트 |
| A-10 | OG 이미지 (포털 Home) | PNG 1200×630 | 신규 | 링크 미리보기 |
| A-11 | Demo canned JSON 10종 | JSON file | dev-spec §9.2 | `public/demoop/canned/` |
| A-12 | Demo rehearsal MP4 (17분) | MP4 1080p | D-13 리허설 녹화 | Failure runbook backup |
| A-13 | Color palette Figma tokens | Figma / JSON | 본 design-spec §2.1 → 토큰 export | 디자이너 핸드오프 |

**공급자**:
- A-1, A-2, A-10: @designer 본인 (0.5일)
- A-4: Kyle or 공개 데이터 (0.5일)
- A-3, A-7, A-8, A-9: npm / Google Fonts (0일)
- A-11: @developer + Kyle 데모 리허설 (D-13)
- A-12: Kyle 리허설 (D-13)
- A-13: UI_GUIDE 승격 PR 시점

---

## §15 Change history + NEXT_STEP

### 15.1 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|---|---|---|---|
| 0.1 | 2026-04-24 | @designer (Claude Opus 4.7) | 최초 작성. §0 scope / §1 7 원칙 / §2 디자인 토큰 (색 · 타이포 · 간격 · 모션) / §3 컴포넌트 인벤토리 23종 (shadcn 12 + 커스텀 11) / §4 사용자 플로우 7개 (happy/permission/error/network/hospital/offline/demo) / §5.A Buyer 9 화면 ASCII 와이어 · 상태 · i18n · 접근성 / §5.B Hospital 6-tile + signin + empty 상세 / §6 Demo Operator Mode 5 오버레이 / §7 에러 taxonomy 21 코드 UI 렌더 규칙 / §8 URL 구조 / §9 i18n 정책 (Buyer en / Hospital ko) / §10 WCAG 2.1 AA 체크리스트 + 대비 핫스팟 수정 액션 / §11 반응형 (데스크탑 우선, <768 fallback) / §12 AC-DG-1..20 / §13 open questions (dev-spec 승계 10 + 디자이너 신규 4) / §14 assets 13종. |

### 15.2 demo-script-radivault.md v0.2 동반 갱신 예정

본 design-spec 세션 내에서 `docs/specs/demo-script-radivault.md` 를 v0.2 로 갱신 한다:

- §2 장면 1~7 각 프레젠터 영어 대사 채움 (한국어는 planner skeleton 유지).
- §2 장면별 청중 반응 연출 추가 (pause · eye contact · 질문 유도 지점).
- §5 Q&A 20건 답변 상세화 (placeholder 제거).
- §3 실패 런북 5건 세부화 (각 항목에 구체 키/UI 지점 명시).
- §4 리허설 체크 R-1~R-9 구체 측정 기준 추가.

### 15.3 UI_GUIDE.md 승격 제안

다음 항목은 UI_GUIDE.md 로 승격 가능 — Kyle 승인 후 별 PR:

- §1 7 디자인 원칙 → UI_GUIDE §2
- §2 디자인 토큰 전체 → UI_GUIDE §3
- §3.1 shadcn 컴포넌트 표 → UI_GUIDE §4 (커스텀 11종은 feature 별 design-spec 유지)
- §7 에러 UI 렌더 규약 → UI_GUIDE §5
- §10 접근성 체크리스트 → UI_GUIDE §6
- §11 반응형 breakpoint → UI_GUIDE §7

### NEXT_STEP

- **완료 산출물**: `docs/specs/design-spec-buyer-portal-demo.md` v0.1 (본 파일)
- **동시 갱신**: `docs/specs/demo-script-radivault.md` v0.2 (본 세션에서 patch)
- **제안 다음 단계**:
  - **@developer** — `claude` 브랜치에서 `buyer-portal-demo` 구현 착수. Week 1 D1 scaffold 부터. dev-spec + design-spec 두 문서 기반. Kyle 결정 대기 항목은 기본값 수용 (§0.1).
  - **@developer (backend 병렬)** — dev-spec §7 Contract deltas D-2, D-3, D-4 를 별 PR 로 central-ingest / order-fulfillment 에 선-반영. Week 1 D2~D3 크리티컬 패스.
  - **@marketer 병렬** — 피치덱 PPT placeholder 구조 (장면 1/2/7) 초안. 본 design-spec §5.A-1 Home wire 및 §5.B 대시보드 톤 일관.
- **UI_GUIDE.md 갱신 제안**: 본 design-spec §1 원칙 · §2 토큰 · §3 컴포넌트 표 · §7 에러 규약 · §10 접근성 · §11 반응형 = 6 섹션. Kyle 승인 후 별 PR.
- **추가 디자인 필요**:
  - Figma source file (v0.1.5) — 디자이너 추가 작업분.
  - Brand logo 심볼 (v0.1.5 Q-Brand-1 결정 후).
  - Korean heatmap 상호작용 (v0.2, dev-spec §0.2-13).
- **Kyle 결정 필요 사항**:
  1. §13.1 Q-UI-1 다크 모드 v0.1 포함 (권고: v0.1.1)
  2. §13.1 Q-UI-2 Buyer 한국어 i18n v0.1 포함 (권고: v0.1.1)
  3. §13.1 Q-UI-3 bar chart 6m vs 12m (권고: 6m for demo)
  4. §13.1 Q-Brand-1 logo 심볼 (권고: v0.1.5)
  5. §13.2 Q-Design-1 Korean map SVG 출처
  6. §13.2 Q-Design-3 중립 색 warm vs cool (현 cool)
  7. UI_GUIDE 승격 PR 수용 여부
