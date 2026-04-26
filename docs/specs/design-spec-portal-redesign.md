# 디자인 명세 — RadiVault 포털 전면 리디자인 (v0.1 · Homepage + Shared)

> **Status**: Draft v0.2 · **Feature slug**: `portal-redesign` · **Last updated**: 2026-04-25
> **작성자**: @designer (Claude Opus 4.7)
> **근거**:
>  - [`dev-spec-portal-redesign.md`](./dev-spec-portal-redesign.md) — FR-HP-1..13, FR-SH-1..5, NFR (이번 호출 스코프)
>  - [`portal-redesign-competitive-analysis.md`](../research/portal-redesign-competitive-analysis.md) — §0 북극성, §2 홈페이지 패턴, §2.10 A-1/A-2/A-3 처방, §5 디자인 원칙, §6 결정 포인트 10
>  - 선행 `design-spec-buyer-portal-demo.md` (Buyer blue / Hospital teal 토큰 승계)
>  - [`UI_GUIDE.md`](../UI_GUIDE.md) — 플레이스홀더. 본 문서가 공통 토큰의 사실상 단일 원본이 됨.

---

## 1. 디자인 개요

RadiVault 의 공개 마케팅 홈페이지 (EN `/` · KR `/ko`) 와, 세 UI 표면 (홈페이지·바이어 포털·병원 콘솔) 이 공유할 **디자인 토큰·공통 컴포넌트**를 이번 v0.1 에서 확정한다. 로그인 이후 UI (바이어 포털 리디자인·병원 콘솔 9 타일) 는 각각 v0.2·v0.3 후속 design-spec 으로 append 된다.

리서치 §0 북극성 — **"정보 밀도 높음 · 신뢰 우선 · 이중 언어 · compliance 강조"** — 을 시각 토큰과 카피 어투로 경직시킨다. 홈페이지는 Stripe 의 "데이터로 설득하는 엔터프라이즈 폴리시" 방향이며, Vercel/Linear 류 다크 네온 그라디언트는 배제한다.

---

## 2. 스코프 선언

| 버전 | 범위 | 상태 |
|------|------|------|
| **v0.1** | 홈페이지 (FR-HP-1..13) + 공유 토큰·컴포넌트 (FR-SH-1..5) + i18n 규칙 | 완료 |
| **v0.2 (본 append)** | 바이어 포털 리디자인 (FR-BP-1..20) — 3-pane, Study detail, /orders/new, Account, 대시보드 5 타일 | 작성 중 |
| **v0.3** | 병원 콘솔 확장 (FR-HO-1..15) — 9 타일, Audit chain status, Quota & ruleset, 한국식 법적 풋터 | 후속 호출에서 append |

**append 규칙**: 본 문서 §4 (공유 토큰) / §5 (공유 컴포넌트) 는 v0.2·v0.3 에서도 **수정 없이 재사용**한다. v0.2·v0.3 은 §11 이후에 새 섹션 (`## 11. 바이어 포털`, `## 12. 병원 콘솔`) 을 추가하는 형태로 확장한다.

---

## 3. 디자인 결정 내역 — Kyle 미확정 Q 기본값 (홈페이지 관련)

dev-spec §14.1 의 Q1..Q11 중 홈페이지 v0.1 에 영향을 주는 항목만 기본값 확정. Kyle 이 번복하면 본 §3 + 관련 섹션 둘 다 수정.

| Q | 항목 | 기본값 (designer 채택) | 근거 |
|---|------|------------------------|------|
| **Q1** 도메인 구조 | 단일 `radivault.io` sub-path (`/`, `/ko`, `/portal`, `/hospital`) | dev-spec 권고 | DNS / SSL / 쿠키 scope 복잡도, 데모 D-14 시한 |
| **Q4** Hero headline | **옵션 A**: `Korea's medical imaging data, compliantly delivered for global AI.` / KR: `한국 의료영상 데이터, 글로벌 AI 를 위한 규정 준수 전달.` | 리서치 §2.1 권고, PRD tagline |
| **Q7** Korea heatmap | 홈페이지에는 노출 X (병원 콘솔 v0.3 에서만). 홈페이지 Hero 시각은 실 `/search` 스크린샷 | 리서치 §2.6 · dev-spec FR-HP-3 |
| **Q8** 한국 footer 법적 블록 | 값 미확정 시 `[TBD]` 플레이스홀더 + `NODE_ENV=production` 빌드 실패 | dev-spec FR-HP-9 |
| **Q11** 데모 Scene 2.5 | 디자인 스콥 외 (스토리보드). 본 문서에서는 Hero 의 EN / KR 30 초 토글 시나리오만 §8 와이어에서 설명 | dev-spec §12 |

---

## 4. 디자인 토큰 (공유)

> `design-spec-buyer-portal-demo §2` 의 Buyer blue / Hospital teal 토큰을 전면 승계하면서, **홈페이지·공유 레이어**에 필요한 추가 토큰만 정의. UI_GUIDE.md 공식화 이전까지는 본 §4 가 단일 원본.

### 4.1 색상 — Primary (Buyer blue)

| 토큰 | 값 | WCAG AA | 용도 |
|------|-----|---------|------|
| `--color-primary-50` | `#eff6ff` | — | Hero 섹션 배경 tint, hover background |
| `--color-primary-100` | `#dbeafe` | — | Card wash, tag background |
| `--color-primary-500` | `#3b82f6` | 3.14:1 / 대형 텍스트만 | Link default |
| `--color-primary-600` | `#2563eb` | **4.54:1 on white** | **Primary CTA fill, 링크 hover, 주 텍스트 액센트** |
| `--color-primary-700` | `#1d4ed8` | 6.80:1 | Primary CTA hover, 포커스 링 |
| `--color-primary-900` | `#1e3a8a` | 10.87:1 | Hero headline emphasis |

### 4.2 색상 — Secondary (Hospital teal, 한국어 페이지 액센트)

| 토큰 | 값 | WCAG AA | 용도 |
|------|-----|---------|------|
| `--color-teal-50` | `#f0fdfa` | — | `/ko` 배경 subtle wash |
| `--color-teal-100` | `#ccfbf1` | — | KR trust bar bullet |
| `--color-teal-600` | `#0d9488` | **4.88:1** | KR 페이지 액센트 (Partnership box, KR CTA secondary) |
| `--color-teal-700` | `#0f766e` | 6.45:1 | Teal hover, KR 페이지 icon |

**규칙**: EN `/` 루트는 Buyer blue 기본. KR `/ko` 는 Buyer blue 기본 + Teal 액센트 (hero 부제 bullet, trust bar icon) 로 "병원 친화" 시각 힌트. 두 색을 같은 화면에 primary-primary 로 쓰지 않음 (브랜드 fragmentation 방지).

### 4.3 색상 — Neutral (Slate 계열, 라이트 테마 기본)

| 토큰 | 값 | 용도 |
|------|-----|------|
| `--color-bg` | `#ffffff` | 페이지 배경 |
| `--color-bg-muted` | `#f8fafc` | 섹션 alternating 배경, card hover |
| `--color-border` | `#e2e8f0` | Hairline divider, card outline |
| `--color-border-strong` | `#cbd5e1` | Input border, facet divider |
| `--color-text-muted` | `#64748b` | 부제·메타 텍스트 |
| `--color-text` | `#0f172a` | 본문 기본 |
| `--color-text-strong` | `#020617` | 헤드라인 (Hero H1) |

대비: `--color-text` (#0f172a) / `--color-bg` (#fff) = **18.69:1** — WCAG AAA.

### 4.4 색상 — Status (light / dark variants, accessible)

| 상태 | Light bg | Dark fg (on light bg) | AA on white |
|------|----------|-----------------------|-------------|
| Success | `#ecfdf5` | `#047857` | 5.38:1 |
| Warning | `#fffbeb` | `#b45309` | 4.74:1 |
| Error   | `#fef2f2` | `#b91c1c` | 5.94:1 |
| Info    | `#eff6ff` | `#1d4ed8` | 6.80:1 |

**용도**: Compliance status ladder 에서 "in preparation" = Warning / "aligned" = Info / "compliant" = Success. dev-spec FR-HP-4 와 1:1.

### 4.5 타이포그래피

**스택** (리서치 §2.6 권고 + §6 결정 Q7 기본값):

```
--font-sans-en: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
--font-sans-kr: "Pretendard Variable", "Pretendard", -apple-system, BlinkMacSystemFont,
                system-ui, Roboto, "Helvetica Neue", "Segoe UI",
                "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif;
--font-mono:    "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
```

**로드 전략**: Pretendard Variable self-hosted (woff2 subset). Inter woff2 subset. Google Fonts 런타임 fetch 금지 (CSP + 성능).

**스케일** (4px 베이스, `1rem = 16px`):

| 토큰 | 값 | line-height | 용도 |
|------|-----|-------------|------|
| `text-xs` | 12px | 16px | 메타 라벨, footer 법적 블록 |
| `text-sm` | 14px | 20px | 보조 본문, facet label |
| `text-base` | 16px | 24px | 본문 기본 |
| `text-lg` | 18px | 28px | 섹션 부제 |
| `text-xl` | 20px | 28px | Trust bar 항목 |
| `text-2xl` | 24px | 32px | Value tile 제목 |
| `text-3xl` | 30px | 36px | Section heading |
| `text-4xl` | 36px | 40px | Hero subhead (desktop) |
| `text-5xl` | 48px | 52px | Hero H1 (mobile) |
| `text-6xl` | 60px | 64px | Hero H1 (desktop) |

Weight: `400` (regular) / `500` (medium, 링크·버튼) / `600` (semibold, 카드 제목) / `700` (bold, Hero H1). **900 black 금지** — 의료 톤 과잉.

### 4.6 Spacing (4px base)

| 토큰 | 값 |
|------|-----|
| `space-0` | 0 |
| `space-0_5` | 2px |
| `space-1` | 4px |
| `space-2` | 8px |
| `space-3` | 12px |
| `space-4` | 16px |
| `space-6` | 24px |
| `space-8` | 32px |
| `space-12` | 48px |
| `space-16` | 64px |
| `space-24` | 96px |

홈페이지 섹션 세로 패딩: 데스크톱 `space-24` / 모바일 `space-16`.

### 4.7 Shadow

| 토큰 | 값 | 용도 |
|------|-----|------|
| `shadow-card` | `0 1px 3px rgba(15,23,42,0.08), 0 1px 2px rgba(15,23,42,0.04)` | Value tile, trust badge |
| `shadow-overlay` | `0 10px 25px rgba(15,23,42,0.10), 0 4px 10px rgba(15,23,42,0.06)` | Dropdown, modal |
| `shadow-hero` | `0 20px 40px rgba(37,99,235,0.12), 0 8px 16px rgba(15,23,42,0.08)` | Hero 우측 제품 스크린샷 액자 |

다크 네온 glow 금지 (의료·신뢰 톤).

### 4.8 Border-radius

| 토큰 | 값 | 용도 |
|------|-----|------|
| `radius-none` | 0 | 표 테두리 |
| `radius-sm` | 4px | Input, tag |
| `radius-md` | 8px | 버튼, card |
| `radius-lg` | 12px | Hero 스크린샷 액자, modal |
| `radius-pill` | 999px | Compliance badge, status chip |

### 4.9 Layout breakpoints

| 토큰 | 값 | 대상 |
|------|-----|------|
| `bp-mobile` | ≥ 375px | Homepage 만 mobile 필수. Buyer/Hospital 은 fallback 안내 |
| `bp-tablet` | ≥ 768px | Homepage 필수, Buyer best-effort, Hospital 비대상 |
| `bp-desktop` | ≥ 1280px | 모든 표면의 기본 타깃 |
| `bp-wide` | ≥ 1920px | 검색 결과 밀도 확장 (v0.2) |

최대 컨테이너 폭: `max-w-content = 1200px` (homepage), `max-w-app = 1440px` (포털 내부 v0.2).

---

## 5. 컴포넌트 명세 (홈페이지 · 공유)

각 컴포넌트는 anchor id 로 v0.2·v0.3 에서 참조. **재사용 원칙**: 같은 semantic 은 한 컴포넌트로.

### 5.1 Hero (EN) `{#hero-en-v1}` — FR-HP-1, FR-HP-2, FR-HP-3, FR-HP-13

**역할**: `/` 경로 최상단. 30 초 안에 "한국 의료영상 데이터 · 글로벌 AI · compliance" 3 요소를 전달.

**좌/우 2-col 레이아웃** (데스크톱 ≥ 1024px), 모바일은 세로 스택.

| 영역 | 내용 |
|------|------|
| Eyebrow | `text-sm / font-medium / text-primary-600` · 문안: `For global AI teams` |
| Headline (H1) | `text-6xl / font-bold / text-text-strong` (desktop) / `text-5xl` (mobile) · 문안: `Korea's medical imaging data, compliantly delivered for global AI.` |
| Subhead | `text-lg / text-text-muted` · 최대 2 줄 (24 단어 이하) · 문안: `RadiVault indexes anonymized DICOM metadata from Korean hospitals and delivers regulatory-grade imaging datasets under PIPA §28-8. Search, verify, and receive — without ever exposing raw patient data.` |
| Primary CTA | `<Button variant="primary" size="lg">` · `Request data access →` · href: `/contact?intent=buyer` |
| Secondary CTA | `<Button variant="ghost" size="lg">` · `View technical overview` · href: `/docs` (v0.1 stub) |
| Tertiary link row | `text-sm / text-text-muted` · `For investors →` + `For hospital partners →` · 박스 없이 2 개 inline 링크 (FR-HP-13, Q6 권고) |
| Hero 시각 (우측) | 실 `/search` 스크린샷 1 장 — 좌 facet / 중앙 결과 테이블 / 우 cohort sidebar 가 보이는 1280px 캡처 → 1.6배 해상도 PNG. `shadow-hero` + `radius-lg`. EXIF · 파일럿 병원 실명 0 건 (AC-HP-4). |
| Hero 시각 caption | `text-xs / text-text-muted` · 문안: `Live demo interface — based on public TCIA dataset` |

**상호작용 상태**:
- CTA hover → `bg-primary-700` + 2px translateY.
- CTA focus → 3px `ring-primary-600/40` outline + 2px offset.
- CTA disabled → opacity 0.5 + `cursor-not-allowed`.
- Loading (contact 이동 중) → spinner 16px 왼쪽, 텍스트 유지.

### 5.2 Hero (KR) `{#hero-kr-v1}` — FR-HP-1, FR-HP-2

**역할**: `/ko` 경로 최상단. 한국 병원 C-레벨 대상. Teal 액센트 포함.

구조는 `{#hero-en-v1}` 와 동일하되:

| 영역 | 내용 (KR) |
|------|-----------|
| Eyebrow | `한국 병원을 위한 데이터 파트너십` · color = `--color-teal-600` |
| Headline (H1) | `한국 의료영상 데이터, 글로벌 AI 를 위한 규정 준수 전달.` · **Pretendard Variable 700** |
| Subhead | `RadiVault 는 한국 병원의 DICOM 메타데이터를 익명화하여 PIPA §28-8 기준으로 글로벌 AI 기업에 전달합니다. 원본 환자 데이터 노출 없이 검색·검증·수령까지.` |
| Primary CTA | `병원 파트너 신청 →` · href: `/contact?intent=hospital` · fill = `--color-teal-600` (EN primary blue 와 톤 구분) |
| Secondary CTA | `기술 개요 보기` · ghost button |
| Tertiary link row | `투자자 문의 →` · `언론 문의 →` |
| Hero 시각 | EN 과 동일 `/search` 스크린샷 (Federated UI 는 병원·바이어 공통). 하단 caption KR: `실제 데모 화면 — TCIA 공개 데이터 기반` |

**한국어 타이포 주의**:
- H1 줄바꿈: `한국 의료영상 데이터,` / `글로벌 AI 를 위한 규정 준수 전달.` (쉼표 기준 2 줄 권고, `word-break: keep-all`).
- 영문 대비 **글자 수 약 30% 짧음** 가정 — Hero 우측 스크린샷 비율 동일 유지 가능.

### 5.3 Trust Bar `{#trust-bar-v1}` — FR-HP-4, FR-SH-3

**역할**: Hero 바로 아래. 고객 로고 없음을 대체하는 **compliance status ladder 4 칼럼** (리서치 §2.10 A-2).

**레이아웃**: 4 칼럼 grid, 데스크톱 horizontal / 모바일 2×2 grid. 섹션 배경 `--color-bg-muted`, 섹션 상하 padding `space-12`.

```
┌───────────────────────────────────────────────────────────────────────┐
│  [ shield-check icon ]   [ shield icon ]   [ badge icon ]   [ lock icon ]  │
│                                                                        │
│  PIPA §28-8             SOC 2 Type II      ISO 27001        HIPAA-aligned │
│  compliant              in preparation     aligned          de-identification │
│                                                                        │
│  Learn more →           Learn more →       Learn more →     Learn more →  │
└───────────────────────────────────────────────────────────────────────┘
```

**각 칼럼 구조**:
- 아이콘 24px · color = 상태 토큰 (compliant=success / in preparation=warning / aligned=info)
- 제목 `text-base / font-semibold / text-text`
- 상태 줄 `text-sm / text-text-muted` — "compliant" / "in preparation" / "aligned" / "de-identification" 어투 **고정** (FR-SH-3 lint 대상).
- "Learn more →" 링크 → `/trust-center#<anchor>` anchor-scroll.

**KR 변형**:
- `PIPA §28-8 준수` / `SOC 2 Type II 준비 중` / `ISO 27001 정렬` / `HIPAA 기준 비식별화`
- "Learn more →" = `자세히 보기 →`

**금지 어휘** (FR-NFR-7 CI lint): `certified` · `guaranteed` · `HIPAA-compliant` · `인증됨` · `보장` (dev-spec §5 NFR).

### 5.4 Value Prop Tile `{#value-tile-v1}` — FR-HP-5 의 단위 카드

**역할**: How it works / Value prop / Security & Compliance 섹션이 모두 사용하는 공통 카드.

**기본 구조**:

```
┌─────────────────────────────────────┐
│  ①  (또는 24px 아이콘)               │
│                                     │
│  Remove DICOM PHI tags              │
│  PS3.15 Annex E                     │
│                                     │
│  53 standard tags stripped on the   │
│  gateway before leaving the hospital│
│  network. No raw DICOM ever sees    │
│  the public internet.               │
│                                     │
│  [ View engine → ] (github link)    │
└─────────────────────────────────────┘
```

**Variants**:
- `variant="numbered"` — 좌상단 원형 숫자 배지 (How it works 1..5 단계).
- `variant="icon"` — 좌상단 24px 아이콘 (Security & Compliance 섹션).
- `variant="metric"` — 숫자 강조 (아래 `{#metric-tile-v1}`).

**사이즈**: 카드 최소 폭 280px, 높이 auto. grid `gap-6`, 3-up 또는 4-up.

**상태**:
- default: `bg-bg` + `border-border` + `shadow-card`
- hover: `border-primary-600` + `shadow-overlay` + 1px translateY.
- focus-within: `ring-primary-600/40` 3px.
- link 없는 카드는 hover 효과 없음 (단순 정보).

### 5.5 Metric Tile `{#metric-tile-v1}` — FR-HP-7 (홈페이지 Metrics 섹션) · 공유

**역할**: 홈페이지 Metrics 섹션 + (v0.3) 병원 콘솔 9 타일 중 숫자 강조 타일에 공통 사용.

```
┌──────────────────────────┐
│                          │
│        2                 │  ← text-5xl / font-bold / text-primary-600
│                          │
│  hospitals federated     │  ← text-sm / text-text-muted
│  in demo                 │
│                          │
└──────────────────────────┘
```

**props (컴포넌트 계약)**:
- `value: string | number` — 큰 숫자
- `unit?: string` — "studies" / "modalities" / "s" (p95 latency)
- `label: string` — 한 줄 설명
- `sublabel?: string` — 보조 주석 (TCIA attribution 등)
- `trend?: {direction: 'up'|'down'|'flat', sparkline?: number[]}` — v0.3 병원 콘솔 확장용, v0.1 홈페이지에서는 미사용

**real-small-honest 원칙** (FR-HP-7, 리서치 §2.4):
- 실 값: `2` · `~250` · `< 2s` · `14`
- 구매자 실명 / 실 숫자 / 파일럿 병원 이름 **0 건** (AC-HP 계열).
- 모든 Metric tile 에 `TCIA CC-BY 3.0/4.0` attribution 이 섹션 하단에 **1 회** 반드시 표시 (FR-SH-4).

### 5.6 CTA Pair `{#cta-pair-v1}` — FR-HP-2, FR-HP-13

**역할**: Hero + 페이지 중단·하단 섹션에서 재사용되는 primary + secondary 버튼 쌍.

```
[ Request data access → ]  [ View technical overview ]
  primary, filled              ghost, outlined
```

- Gap: `space-4` (16px).
- 모바일: 세로 스택, 각 버튼 `w-full`.
- KR 변형: `병원 파트너 신청 →` + `기술 개요 보기`.
- 세 번째 링크는 `{#hero-en-v1}` 의 tertiary link row 로 처리 (버튼 아님).

### 5.7 Footer EN minimal `{#footer-en-v1}` — FR-HP-10 (EN)

**역할**: `/` 영문 페이지 풋터. Stripe / Vercel 스타일 6 칼럼.

```
┌────────────────────────────────────────────────────────────────────────────┐
│  [RadiVault wordmark]                                                      │
│                                                                            │
│  Product       Solutions     Developers    Resources    Company   Legal    │
│  --------      ----------    ----------    ---------    -------   -----    │
│  Marketplace   For AI teams  Docs          Blog         About     Privacy  │
│  Pricing       For hospitals API reference Changelog    Contact   Terms    │
│  Security      For research  GitHub        Trust Center Careers   DPA      │
│                Enterprise    Status                                        │
│                                                                            │
│  ─────────────────────────────────────────────────────────────────────     │
│  © 2026 RadiVault Inc.      EN | KR            [Twitter] [LinkedIn] [GH]   │
└────────────────────────────────────────────────────────────────────────────┘
```

- 배경 `--color-bg-muted`, 상단 border `--color-border`.
- 컬럼 제목 `text-sm / font-semibold / text-text`
- 링크 `text-sm / text-text-muted` → hover `text-primary-600`
- Language toggle: `EN | KR` pill, 현재 locale bold + 밑줄.
- 소셜 아이콘 16px · color `--color-text-muted` → hover `--color-text`.

**금지**: 한국 사업자등록·대표자·전화번호 (EN 페이지에는 표시 X — 영미 관행).

### 5.8 Footer KR 법적 블록 `{#footer-kr-v1}` — FR-HP-9, FR-HP-10 (KR)

**역할**: `/ko` 한국어 페이지 풋터. Ncloud / VUNO 관습 (리서치 §2.5, §8.6).

```
┌────────────────────────────────────────────────────────────────────────────┐
│  [RadiVault 워드마크]                                                       │
│                                                                            │
│  제품·솔루션       기술          회사         법적                          │
│  -----------       ----          ----         ----                          │
│  병원 파트너십     개발자 문서   회사 소개    개인정보처리방침              │
│  바이어 마켓플레이스 API 레퍼런스 언론         이용약관                      │
│  가격 문의         상태 페이지   채용         데이터처리 위탁 계약          │
│  보안              Trust Center  문의                                       │
│                                                                            │
│  ──────────────────────────────────────────────────────────────────────    │
│  RadiVault Inc.                                                            │
│  대표자: Kyle Jeon  |  사업자등록번호: [TBD]  |  통신판매업 신고: [TBD]   │
│  주소: [TBD]        |  고객센터: [TBD]         |  이메일: sales@radivault.io │
│                                                                            │
│  [KISMS-P 준비 중 배지]  [ISO 27001 aligned 배지]  [PIPA §28-8 배지]       │
│                                                                            │
│  © 2026 RadiVault Inc.                       KR | EN                       │
└────────────────────────────────────────────────────────────────────────────┘
```

- 법적 블록은 `text-xs / text-text-muted` · 행간 1.8.
- `[TBD]` 값은 환경변수 `NEXT_PUBLIC_LEGAL_*` 에서 주입. `NODE_ENV=production` 빌드에서 `[TBD]` 문자열 detection 시 CI fail (FR-HP-9, AC-HP-5).
- 배지는 48px 높이 이미지 슬롯 3 개. v0.1 에서는 텍스트 pill 로 대체 가능 (`radius-pill` · `bg-bg` · `border-border-strong`).
- `word-break: keep-all` 로 한국어 끊어읽기 자연스럽게.

### 5.9 Language Toggle `{#lang-toggle-v1}` — FR-HP-11

**역할**: 모든 공개 페이지 상단 우측 + Footer 우측 하단 양쪽에 배치.

- 구조: `[EN] | [KR]` · 현재 locale `font-semibold` + 밑줄 2px `primary-600`.
- 클릭 시:
  1. 쿠키 `radivault_locale = "en" | "ko"` · 365일 TTL · SameSite=Lax · Secure (prod).
  2. 경로 치환: `/` ↔ `/ko`, `/contact` ↔ `/ko/contact`, `/trust-center` ↔ `/ko/trust-center`.
  3. `<html lang="...">` 속성 갱신.
- 초기 접속 시: 쿠키 없음 → `Accept-Language` 헤더 first-match → 기본 `en`.

### 5.10 Compliance Badge `{#compliance-badge-v1}` — FR-SH-3

**역할**: Trust bar + Footer + Trust Center 에서 공통 사용. 어투 강제.

**Variants** (dev-spec FR-SH-3 의 4 개):

| variant | EN 라벨 | KR 라벨 | 상태 토큰 |
|---------|---------|---------|-----------|
| `pipa` | `PIPA §28-8 compliant` | `PIPA §28-8 준수` | success |
| `soc2` | `SOC 2 Type II in preparation` | `SOC 2 Type II 준비 중` | warning |
| `iso27001` | `ISO 27001 aligned` | `ISO 27001 정렬` | info |
| `hipaa` | `HIPAA-aligned de-identification` | `HIPAA 기준 비식별화` | info |

**컴포넌트 구조**:
```
[ 16px icon ] [라벨 텍스트]   ← radius-pill, padding 4×12, status bg-tint + fg-dark
```

**lint**: 이 컴포넌트 외부에서 "certified" / "guaranteed" / "HIPAA-compliant" / "인증됨" / "보장" 문자열 등장 시 CI fail (FR-NFR-7).

---

## 6. 홈페이지 ASCII 와이어프레임 (섹션별)

> **주의**: 각 와이어는 ≥ 60 chars wide, 시각 비율 반영. 데스크톱 ≥ 1280px 기준. 모바일 변형은 §7 에서 설명.

### 6.1 Hero — EN (`/`) — FR-HP-1~3, 13

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [◆ RadiVault]  Product  Solutions  Developers  Docs  Pricing    EN | KR │ ← nav
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  For global AI teams                                                     │
│                                                                          │
│  Korea's medical                      ┌────────────────────────────────┐ │
│  imaging data,                        │                                │ │
│  compliantly delivered                │   [실 /search UI 스크린샷]     │ │
│  for global AI.                       │                                │ │
│                                       │   좌 facet pane (280px)        │ │
│  RadiVault indexes anonymized         │   중 결과 테이블 (7 컬럼)      │ │
│  DICOM metadata from Korean           │   우 cohort sidebar (320px)    │ │
│  hospitals and delivers               │                                │ │
│  regulatory-grade imaging             │   "From 2 hospitals" 배지      │ │
│  datasets under PIPA §28-8.           │   상단 sticky                  │ │
│                                       │                                │ │
│  [ Request data access → ]            │                                │ │
│  [ View technical overview ]          │                                │ │
│                                       └────────────────────────────────┘ │
│  For investors →   For hospital partners →                               │
│                                        Live demo interface — based on TCIA│
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Hero — KR (`/ko`) — 구조 동일, 텍스트·색 바뀜

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [◆ RadiVault]  제품  솔루션  기술  문서  가격문의           KR | EN    │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  한국 병원을 위한 데이터 파트너십   (← teal eyebrow)                     │
│                                                                          │
│  한국 의료영상 데이터,                ┌────────────────────────────────┐ │
│  글로벌 AI 를 위한                    │   [같은 /search 스크린샷]       │ │
│  규정 준수 전달.                      │                                │ │
│                                       │                                │ │
│  RadiVault 는 한국 병원의             │                                │ │
│  DICOM 메타데이터를 익명화하여        │                                │ │
│  PIPA §28-8 기준으로                  │                                │ │
│  글로벌 AI 기업에 전달합니다.         │                                │ │
│                                       │                                │ │
│  [ 병원 파트너 신청 → ]  (← teal)     │                                │ │
│  [ 기술 개요 보기 ]                   │                                │ │
│                                       └────────────────────────────────┘ │
│  투자자 문의 →   언론 문의 →                                             │
│                                        실제 데모 화면 — TCIA 공개 데이터 기반│
└──────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Trust Bar — FR-HP-4

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   [shield-check]     [shield]        [badge]        [lock]               │
│                                                                          │
│   PIPA §28-8         SOC 2 Type II   ISO 27001      HIPAA-aligned        │
│   compliant          in preparation  aligned        de-identification    │
│                                                                          │
│   Learn more →       Learn more →    Learn more →   Learn more →         │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
  배경: --color-bg-muted · padding-y: space-12
```

### 6.4 Value Prop (3-up) — FR-HP-5 축약판 (How It Works 5-step 과 별도)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Why RadiVault                                                           │
│  Three reasons global AI teams choose RadiVault over DIY sourcing        │
│                                                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐           │
│  │ [icon:layers]   │  │ [icon:shield]   │  │ [icon:globe]    │           │
│  │                 │  │                 │  │                 │           │
│  │ Federated       │  │ Compliance      │  │ Korean          │           │
│  │ by design       │  │ you can audit   │  │ imaging depth   │           │
│  │                 │  │                 │  │                 │           │
│  │ One search      │  │ WORM audit log  │  │ 14 modalities   │           │
│  │ across N        │  │ + chain of      │  │ from hospitals  │           │
│  │ hospitals.      │  │ custody proofs. │  │ representative  │           │
│  │ No silos.       │  │ Not just badges.│  │ of the KR pop.  │           │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘           │
└──────────────────────────────────────────────────────────────────────────┘
```

### 6.5 How It Works (5-step) — FR-HP-5, FR-HP-6

```
┌──────────────────────────────────────────────────────────────────────────┐
│  How it works                                                            │
│  From hospital PACS to your AI training loop — 5 steps, fully audited    │
│                                                                          │
│  ┌──────┐     ┌──────┐     ┌──────┐     ┌──────┐     ┌──────┐           │
│  │  1   │ ──> │  2   │ ──> │  3   │ ──> │  4   │ ──> │  5   │           │
│  │PACS  │     │Gateway│    │De-ID  │    │Central│    │Buyer │           │
│  │tags  │     │agent  │    │engine │    │index  │    │portal│           │
│  └──────┘     └──────┘     └──────┘     └──────┘     └──────┘           │
│   WORM         outbound     PHI tags     metadata    presigned           │
│   audit        TLS 1.3      + OCR        searchable   download            │
│   anchor                    + deface                   (24h TTL)         │
│                                                                          │
│  ────────────────────────────────────────────────────────────────────    │
│  Engines: [gateway-agent ↗]  [de-id-engine v0.2 ↗]  (GitHub links)      │
└──────────────────────────────────────────────────────────────────────────┘
```

화살표 위에 "WORM audit log event" 라벨 (FR-HP-6). 모바일은 세로 스택 + 하향 화살표.

### 6.6 Metrics 섹션 — FR-HP-7 (real-small-honest)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  By the numbers                                                          │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │              │  │              │  │              │  │              │  │
│  │     2        │  │   ~250       │  │   < 2s       │  │    14        │  │
│  │              │  │              │  │              │  │              │  │
│  │ hospitals    │  │ studies      │  │ p95 search   │  │ DICOM        │  │
│  │ federated    │  │ indexed in   │  │ latency      │  │ modalities   │  │
│  │ in demo      │  │ TCIA seed    │  │              │  │ supported    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                          │
│  Demo data based on The Cancer Imaging Archive (TCIA) — CC BY 3.0 / 4.0. │
└──────────────────────────────────────────────────────────────────────────┘
```

- 섹션 배경: `--color-bg` (Trust bar 의 muted 와 교차로 visual rhythm).
- 구매자 실명 / 숫자 노출 0 건 (FR-SH-5 AC).
- `~250` 의 물결표는 `±25` 의 근사 표기 — 실 시드 수 변동 대응.

### 6.7 Security & Compliance — FR-HP-8

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Security & Compliance                                                   │
│  Built from the ground up for Korean PIPA §28-8 and HIPAA-aligned       │
│  de-identification.                                                      │
│                                                                          │
│  ┌─────────────────────────┐   ┌─────────────────────────┐              │
│  │ [icon:file-lock]        │   │ [icon:network]          │              │
│  │                         │   │                         │              │
│  │ PIPA §28-8              │   │ Outbound-only network   │              │
│  │                         │   │                         │              │
│  │ All data processed      │   │ Hospital gateways push  │              │
│  │ under Korea's Personal  │   │ over TLS 1.3. No        │              │
│  │ Information Protection  │   │ inbound connections to  │              │
│  │ Act §28-8 (pseudonym).  │   │ hospital networks.      │              │
│  └─────────────────────────┘   └─────────────────────────┘              │
│                                                                          │
│  ┌─────────────────────────┐   ┌─────────────────────────┐              │
│  │ [icon:shield-check]     │   │ [icon:archive]          │              │
│  │                         │   │                         │              │
│  │ HIPAA Safe Harbor +     │   │ 5-year WORM audit       │              │
│  │ Expert Determination    │   │                         │              │
│  │                         │   │ Every event — ingest,   │              │
│  │ 3-layer de-ID: DICOM    │   │ de-id, order, download  │              │
│  │ PHI + burn-in OCR +     │   │ — anchored to an        │              │
│  │ 3D defacing.            │   │ immutable chain.        │              │
│  └─────────────────────────┘   └─────────────────────────┘              │
│                                                                          │
│  [ Visit Trust Center → ]                                                │
└──────────────────────────────────────────────────────────────────────────┘
```

- `{#value-tile-v1}` variant="icon" 4 개 사용.
- "Visit Trust Center →" → `/trust-center` (v0.1 stub 페이지 OK).

### 6.8 Footer (EN minimal) — §5.7 참조

본문 와이어는 §5.7 의 ASCII 와이어 그대로. Metrics 아래, 페이지 최하단.

### 6.9 Footer (KR 법적 블록) — §5.8 참조

`/ko` 전용. EN Footer 자리에 대체 렌더.

### 6.10 섹션 수직 순서 (홈페이지 EN · KR 동일)

```
1. Hero                  (§6.1 또는 §6.2)
2. Trust Bar             (§6.3)
3. Value Prop 3-up       (§6.4)
4. How It Works 5-step   (§6.5)
5. Metrics               (§6.6)
6. Security & Compliance (§6.7)
7. Footer                (§6.8 EN · §6.9 KR)
```

---

## 7. 반응형 (홈페이지만)

Buyer / Hospital 은 desktop-only. 홈페이지만 mobile-friendly 필수 (dev-spec §5 NFR).

### 7.1 Mobile (375 ~ 767px)

- Top nav → 햄버거 메뉴 (우측). Language toggle 은 햄버거 내부 최상단.
- Hero → 2-col → 1-col 세로. 스크린샷은 Hero 텍스트 **하단**에 배치 (위에 H1 가시성 우선).
- Hero CTA pair → 세로 스택, 각각 `w-full`. Tertiary link row 는 세로.
- Trust bar → 4-col → **2×2 grid** (row-gap `space-6`).
- Value prop 3-up → 1-col.
- How it works 5-step → 세로 (↓ arrows), 각 step card `w-full`.
- Metrics 4-up → 2×2 grid.
- Security & Compliance 2×2 → 1-col.
- Footer 6-col → 2-col (EN) / 2-col (KR). 법적 블록은 always 세로 스택.

### 7.2 Tablet (768 ~ 1279px)

- Top nav 노출 유지, 일부 메뉴 축약 (예: "API reference" → "API").
- Hero → 2-col 유지 but 스크린샷 영역 축소 (`max-w-[480px]`).
- Trust bar 4-col 유지.
- Value prop · Metrics · Security 는 2×2 로 축소.
- How it works 5-step → 3 + 2 줄바꿈 가능.

### 7.3 Desktop (≥ 1280px)

- 위 §6 와이어 그대로.
- 컨테이너 `max-w-content = 1200px`, 좌우 auto margin.

### 7.4 Wide (≥ 1920px)

- 홈페이지는 `max-w-content` 고정 (가독성). Hero 스크린샷만 1.2× 확대.

---

## 8. 접근성 (WCAG 2.1 AA)

dev-spec §5 NFR + design-spec-buyer-portal-demo §10 승계.

### 8.1 대비

- 본문 텍스트 / 배경 ≥ **4.5:1** (토큰 §4.3 에서 18.69:1 AAA 확보).
- UI 컴포넌트 경계 / 배경 ≥ **3:1** (`border-strong` #cbd5e1 / white = 3.14:1 ✓).
- CTA primary text (white) / bg (primary-600) ≥ 4.5:1 (4.54:1 ✓).
- 상태 텍스트 (success / warning / error / info) 모두 §4.4 에서 AA 검증.

### 8.2 키보드 탐색

- Tab 순서: Skip-link → Top nav (로고·메뉴·lang toggle) → Hero (eyebrow 제외) → CTA primary → CTA secondary → tertiary links → Trust bar (칼럼 순) → Value prop (순서대로) → How it works → Metrics → Security → Footer.
- **Skip-link** 필수: `<a href="#main" class="sr-only focus:not-sr-only">Skip to main content</a>`.
- 모든 link / button focus → 3px `ring-primary-600/40` + 2px offset (토큰 §4.1).
- 포커스 트랩 없음 (홈페이지는 modal 없음). v0.2 /orders/new 풀페이지에서는 dialog 필요.

### 8.3 스크린리더

- 랜드마크: `<header>` · `<main id="main">` · `<footer>` · `<nav aria-label="Primary">` · `<nav aria-label="Footer">`.
- Hero H1 페이지당 1 개 (SEO + SR 양립).
- 아이콘 단독 버튼은 `aria-label` 필수 (예: 햄버거 `aria-label="Open menu"` · `언어 전환` 토글).
- Trust bar 각 칼럼 → `<article aria-labelledby="trust-pipa-label">`.
- 제품 스크린샷 → `<img alt="Search interface showing facet pane, results table, and cohort sidebar across two hospitals">`.
- 장식 아이콘 → `aria-hidden="true"`.

### 8.4 모션

- `prefers-reduced-motion: reduce` 감지 시 CTA translateY / card hover motion 비활성.
- 자동 재생 carousel 없음.

### 8.5 Lighthouse 타깃

- Accessibility ≥ 95 (dev-spec AC-SH-5).
- Performance ≥ 85 (homepage static export / LCP p75 < 2.5s).

---

## 9. i18n

### 9.1 언어 · 길이

- `en` 기본, `ko` 완전 번역 (홈페이지 한정). `en.json` / `ko.json` 2 파일 dictionary (dev-spec Q9 권고).
- 한국어 문자열 평균 길이 **영어 대비 약 30% 짧음** (리서치 §4.4). 단 조합형 글자로 행 높이는 동일. Hero H1 영어 6 단어 ≈ 한국어 3~4 단어.
- 버튼 라벨: 한국어 4 자 이하 유지 권고 ("신청" · "보기" · "문의"). 영어 `Request data access` 20자는 primary CTA 로 허용.

### 9.2 줄바꿈

- 한국어: `word-break: keep-all; overflow-wrap: break-word;` 필수. 영어: default OK.
- Hero H1 KR: 쉼표 기준 강제 줄바꿈 (`<br>` 허용) — "한국 의료영상 데이터, \n 글로벌 AI 를 위한 \n 규정 준수 전달.".

### 9.3 숫자 · 날짜 · 통화

- 홈페이지는 숫자 전시 최소 (Metrics 4 개). `2` · `~250` · `< 2s` · `14` 는 언어 무관 동일 표기.
- v0.3 병원 콘솔에서 KRW 풀스펠 (`₩ 18,400,000`) 규칙 도입 — 본 v0.1 스코프 외.
- 날짜 포맷: `en` = `Apr 25, 2026` / `ko` = `2026-04-25` (리서치 §4.4 권고).

### 9.4 어휘 lint (FR-SH-3, FR-NFR-7)

CI 에서 `grep -riE '(certified|guaranteed|HIPAA-compliant|인증됨|보장)' web/portal/src/` 결과 0 건 필수.

**허용 어휘**:
- EN: `aligned with` · `in preparation` · `designed to support` · `compliant with` (법률 조항 명시 시만, 예: `PIPA §28-8 compliant`) · `HIPAA-aligned`.
- KR: `정렬` · `준수` · `준비 중` · `기준 비식별화` · `지원하도록 설계됨`.

### 9.5 Hreflang · URL

- `<link rel="alternate" hreflang="en" href="https://radivault.io/">`
- `<link rel="alternate" hreflang="ko" href="https://radivault.io/ko">`
- `<link rel="alternate" hreflang="x-default" href="https://radivault.io/">`

---

## 10. Kyle 확정 필요 + 후속 버전 범위

### 10.1 이번 v0.1 스코프에서 Kyle 결정 필요 항목

| # | 항목 | designer 기본값 | Kyle 결정 필요 이유 |
|---|------|-----------------|----------------------|
| **K-1** | Hero H1 KR 번역 최종 | `한국 의료영상 데이터, 글로벌 AI 를 위한 규정 준수 전달.` | 한국어 subtlety · 브랜드 톤 (특히 "전달" 어색할 수 있음 → "공급" / "제공" 후보). 법무·마케팅 검토 필요. |
| **K-2** | Hero 스크린샷 실물 확정 | 현재 `/search` 3-pane 캡처 권고 | 캡처 해상도 · 포함되는 facet 값 · TCIA seed 구성. Session 12 canned JSON 10 종 중 어떤 것? |
| **K-3** | Trust Center (`/trust-center`) v0.1 내용 | Stub 페이지 + 4 compliance 배지 anchor | v0.1 에서 어느 정도 내용? "coming soon" 만? 아니면 각 badge 별 1 문단? |
| **K-4** | Footer KR 법적 값 (§Q8) | `[TBD]` + prod 빌드 fail | Delaware 법인 설립 전 한국 법인 정보 사용? "설립 준비 중" 명시 허용? |
| **K-5** | 컴포넌트 라이브러리 선택 | shadcn/ui + Radix (Session 12 기존 채택) 그대로 재사용 | 본 문서는 재사용 권고만. 신규 라이브러리 금지 가정. |
| **K-6** | Pretendard / Inter self-host 라이선스 | 둘 다 OFL 1.1 / SIL OFL 가능 | 배포 전 LICENSE 파일 포함 확인. |
| **K-7** | 다크 모드 여부 | **v0.1 라이트 고정**, 토글 v0.1.1+ | 의료 타깃 라이트 권고 (리서치 §2.6). Kyle 반대 시 색 토큰 dark variant 추가. |

### 10.2 v0.2 (후속 호출) — 바이어 포털 리디자인 스코프

다음 design-spec 호출에서 본 문서에 **append** 할 섹션들:

- §11. 바이어 포털 정보 구조 (FR-BP-18 sitemap).
- §12. 컴포넌트 — DataTable (7+ 필드), Facet pane, Cohort sidebar, PhaseStepper, TimelineDrawer, ApiKeyList, `ModalityBadge` (7 variant, FR-BP-5 색상 토큰 추가), `FederatedSignal` sticky 배지.
- §13. 화면 와이어 — `/` 대시보드 5 타일, `/search` 3-pane, `/studies/[id]`, `/orders/new` 풀페이지, `/orders/[id]` + drawer, `/account`.
- §14. 사용자 플로우 — 검색 → 카트 → 주문 → 다운로드 happy path + 3 error path.
- §15. 바이어 포털 상태 — empty / loading / error (21 코드 재사용) / no-permission.

### 10.3 v0.3 (후속 호출) — 병원 콘솔 확장 스코프

- §16. 병원 콘솔 정보 구조 (FR-HO-11 sitemap).
- §17. 컴포넌트 — 9 타일 (Studies count · Bytes · Revenue sim · Orders in · Gateway HB · Revenue trend · Modality donut · Audit chain status · Quota & ruleset), Audit preview list, KRW 풀스펠 number format, Hospital-scoped Korea dot map.
- §18. 한국식 풋터 v2 — §5.8 재사용 + 1:1 문의 플로팅 버튼.
- §19. 병원 콘솔 상태 + SSO 전환 (v0.2 트랙, 현재 토큰).

### 10.4 UI_GUIDE.md 갱신 제안 (Kyle 승인 후)

본 §4 토큰 전체 (색상 · 타이포 · spacing · shadow · radius · breakpoint) 를 UI_GUIDE.md 로 승격. §5 의 `{#hero-en-v1}` / `{#trust-bar-v1}` / `{#compliance-badge-v1}` / `{#footer-en-v1}` / `{#footer-kr-v1}` / `{#metric-tile-v1}` / `{#value-tile-v1}` / `{#cta-pair-v1}` / `{#lang-toggle-v1}` 는 공통 컴포넌트로 UI_GUIDE 카탈로그에 등재 권고.

---

# ════════════════════════════════════════════════════════════════════════
# v0.2 APPEND — 바이어 포털 리디자인 (FR-BP-1..20)
# 작성: 2026-04-25 · @designer (Claude Opus 4.7)
# 근거: dev-spec-portal-redesign §4.2 FR-BP-* + §7.2 BFF + §8.2 검색 시퀀스
# 원칙: §4 토큰 / §5 컴포넌트 전부 재사용. 신규는 컴포넌트 7 + 화면 4 만.
# ════════════════════════════════════════════════════════════════════════

## 11. 바이어 포털 — 컴포넌트 명세 (신규 7 개)

> **재사용 선언**: Hero / Trust Bar / Footer / Compliance Badge / Lang Toggle 등 §5 컴포넌트는 바이어 포털에서 **그대로 재사용** (단 Hero 는 `/signin` 화면에만 축약형). 본 §11 은 로그인 이후 화면 전용 7 개 컴포넌트만 신규로 정의.

### 11.1 ModalityBadge `{#modality-badge-v1}` — FR-BP-4, FR-BP-5

**역할**: 검색 결과 row · Study detail · Cart 의 modality 필드 좌측 색상 배지.

**색상 토큰** (dev-spec FR-BP-5, design-spec-buyer-portal-demo §10 WCAG 3:1 보정 승계):

| variant | bg-tint | fg | label EN/KR |
|---------|---------|-----|-------------|
| `CT` | `#dbeafe` (primary-100) | `#1d4ed8` (primary-700) | CT / CT |
| `MR` | `#ede9fe` (purple-100) | `#6d28d9` (purple-700) | MR / MR |
| `MG` | `#fce7f3` (pink-100) | `#9d174d` (pink-darker, AA 보정) | MG / 유방촬영 |
| `CR` | `#dcfce7` (green-100) | `#15803d` (green-700) | CR / CR |
| `DX` | `#dcfce7` (green-100) | `#15803d` (green-700) | DX / DX |
| `PT` | `#fee2e2` (red-100) | `#b91c1c` (red-700) | PT / PET |
| `US` | `#ffedd5` (orange-100) | `#c2410c` (orange-700) | US / 초음파 |

**구조**: `radius-sm` · padding `2×8` · `text-xs / font-mono / font-medium`. 7 variant 외 modality (XA/NM 등) 는 `--color-bg-muted` + `--color-text-muted` fallback. `aria-label="modality: {value}"` 필수.

### 11.2 FederatedSignal `{#federated-signal-v1}` — FR-BP-6 ("1 검색 = N 병원" northstar)

**역할**: `/search` 결과 영역 최상단 sticky 배지. RadiVault 의 단일 가장 중요한 시각 메시지.

```
┌────────────────────────────────────────────────────────────────────┐
│  ◆  150 studies across 2 hospitals     [filter: CT, MR · age 50+] │
└────────────────────────────────────────────────────────────────────┘
```

- 위치: 결과 리스트 위 sticky (top: 64px, nav 아래).
- 배경: `--color-primary-50` · 좌측 4px solid `--color-primary-600` border.
- 텍스트: `text-base / font-semibold / text-text` — 숫자 (`150`, `2`) 는 `text-primary-700`.
- "From N hospitals" 의 N 값은 server-side `COUNT(DISTINCT hospital_opaque_id)` (FR-BP-6).
- 우측 보조: 현재 활성 filter chip 요약 (3 개 초과 시 "+N more").
- KR variant: `150 study · 2 개 병원에서 집계`.
- **0 건**일 때: 변형 → `No results across our 2 partner hospitals` (Empty state, §15.1).

### 11.3 StudyCard / DataTable Row `{#study-card-v1}` — FR-BP-4

**역할**: `/search` 중앙 결과 영역의 한 row. **최소 7 필드** 정보 밀도 (dev-spec FR-BP-4).

**구조 (DataTable row)**:
```
┌──┬──────┬──────────┬─────────┬─────┬──────────┬──────────┬─────────┬──────────┐
│☐ │[CT]  │ Chest    │ 50-59   │ M   │ 287 imgs │ 142 MB   │ 2023    │ HOSP-A2 │
└──┴──────┴──────────┴─────────┴─────┴──────────┴──────────┴─────────┴──────────┘
   modality body_part age      sex   instances  size       year      hospital
```

| 컬럼 | 너비 | 정렬 | 컴포넌트 |
|------|------|------|----------|
| checkbox | 40px | center | shadcn Checkbox |
| modality | 64px | left | `{#modality-badge-v1}` |
| body_part | flex | left | `text-sm / text-text` |
| age_bucket | 80px | left | `text-sm / text-text-muted` |
| sex | 40px | center | `text-sm / text-text-muted` |
| n_instances | 100px | right | `text-sm / font-mono` |
| size_mb | 100px | right | `text-sm / font-mono` |
| study_year | 80px | right | `text-sm / text-text-muted` |
| hospital | 100px | left | hospital_opaque_id chip · pill · monospace |

**상호작용**:
- Row hover → bg `--color-bg-muted` + tooltip ("HOSP-A2 has 87 studies in current cohort").
- Row click → `/studies/[id]` (FR-BP-8).
- Checkbox 토글 → cohort 우측 sidebar 카운터 즉시 반영.
- Selected row → 좌측 4px `--color-primary-600` accent + bg `--color-primary-50`.
- Keyboard: ↑↓ 이동, Space = checkbox, Enter = detail.

**Empty / Loading / Error**: §15 참조.

### 11.4 StudyDetailPanel `{#study-detail-v1}` — FR-BP-8

**역할**: `/studies/[id]` 풀페이지 메인. 메타데이터 테이블 + Series 리스트 + Hospital origin + ViewerStub.

**섹션 구성** (top → bottom):

```
1. Header bar
   [← Back to results]   StudyInstanceUID: 1.2.840.....1234   [Add to cohort +]

2. Hospital origin row
   ◆ HOSP-A2 · From this hospital's pool of 87 studies   [view all →]

3. Metadata grid (2-col, 14 fields)
   Modality        CT          Body Part       CHEST
   Age Bucket      50-59       Sex             M
   Manufacturer    SIEMENS     Model           SOMATOM Force
   Study Date      2023-08-14  Acquisition     CT
   Slice Thick     1.0 mm      KVP             120
   Pixel Spacing   0.78×0.78   Modality Count  1
   Total Bytes     142 MB      Instance Count  287

4. Series list (table)
   #  | Description           | Modality | Instances | Size
   1  | CHEST AXIAL 1.0mm     | CT       | 287       | 142 MB
   2  | CHEST CORONAL MIP     | CT       | 64        | 32 MB

5. ViewerStub (placeholder)
   ┌─────────────────────────────────────────────────────────┐
   │   [icon: monitor]                                        │
   │                                                          │
   │   DICOM viewer not included in v0.1.                     │
   │   Pixel data available after order fulfillment.          │
   │                                                          │
   │   [ Request demo of viewer integration → ]               │
   └─────────────────────────────────────────────────────────┘
```

- Background: `--color-bg`. Sections separated by `--color-border` hairline.
- Header sticky on scroll (top: 64px nav 아래).
- "Add to cohort" CTA → primary, position: top-right header. 클릭 시 cohort sidebar 카운터 +1 + toast `Added to cohort (1 study)`.
- ViewerStub: `--color-bg-muted` bg, `radius-lg`, `text-text-muted` body.
- Mobile fallback (best-effort): 메타데이터 grid 1-col, ViewerStub 영역 축소.

### 11.5 FacetSidebar `{#facet-sidebar-v1}` — FR-BP-3 (좌), FR-BP-7

**역할**: `/search` 좌측 패싯 (280px 고정, ≤ 1280px collapsible).

**facet 목록** (FR-BP-7, 위→아래):
1. **min_hospitals slider** (1~20, 기본 1) — RadiVault 고유. 라벨 EN: `Federated across at least N hospitals` / KR: `최소 N 개 병원에 분포`.
2. modality (multi-select, 7 variant)
3. body_part (search + multi-select)
4. age_bucket (multi-select)
5. sex (radio)
6. manufacturer (search + multi-select)
7. year (range slider 1990~2026)

**구조**:
- 각 facet section: 제목 (`text-sm / font-semibold`) + collapse caret + count badge ("(247)").
- Selected value → chip pill at top of section + active count.
- "Clear all filters" 링크 sidebar 최하단.
- Border-right `--color-border`, padding `space-4`.

**상호작용**:
- 변경 시 즉시 검색 재실행 (debounce 300ms). 로딩 중 결과 영역만 skeleton, sidebar 는 활성 유지.
- Keyboard: Tab 순서 = section → 내부 옵션. Esc → 현재 section collapse.
- Mobile (홈페이지 스코프 외, best-effort): facet 좌측 drawer → 햄버거.

### 11.6 CartItem / Cohort row `{#cart-item-v1}` — FR-BP-9

**역할**: `/orders/new` 풀페이지의 선택 study 테이블 한 row + `/search` 우측 cohort sidebar 의 mini-list.

**구조 (cart 테이블 row)**:
```
┌──┬──────┬──────────────────────┬──────────┬──────────┬──────┐
│✕ │[CT]  │ Chest · 50-59 · M    │ HOSP-A2  │ 142 MB   │ 2023 │
└──┴──────┴──────────────────────┴──────────┴──────────┴──────┘
   remove modality summary           hospital   size       year
```

- `✕` → cohort 에서 제거 (confirm 없음, undo toast 5s).
- 클릭 시 `/studies/[id]` (새 탭 권고 — cohort 작업 중단 방지).
- `/search` cohort sidebar 의 mini variant: modality badge + body_part 2 줄 only (320px 폭).

**상태**:
- Empty cohort: sidebar 에 placeholder `Select studies from results to build cohort` + illustration.
- 1+ items: 상단 카운터 `Selected 12 · From 2 hospitals` (← `{#federated-signal-v1}` 의 mini variant 재사용).

### 11.7 OrderTimeline `{#order-timeline-v1}` — FR-BP-10

**역할**: `/orders/[id]` 의 5-phase 가로 stepper + "View timeline" drawer 내부 12-state FSM 세로 리스트.

**5-phase Stepper (가로, 항상 표시)**:
```
●━━━━━●━━━━━●━━━━━○─────○
Submitted  Approved  Preparing  Ready  Completed
2 hours ago         in progress         —
```

- 채워진 dot: `--color-primary-600`. 빈 dot: `--color-border-strong`. 진행 중: pulsing animation (reduced-motion 시 정적).
- 각 phase 아래 timestamp (ko: `2시간 전` / en: `2 hours ago` — Intl.RelativeTimeFormat).

**Timeline Drawer (우측 슬라이드 in)**:
- 트리거: stepper 옆 "View timeline →" 링크.
- 12-state FSM 이벤트 시계열 (order-fulfillment dev-spec). 각 이벤트:
  ```
  ●  2026-04-25 10:23:14  state_changed: APPROVED → PREPARING
     by system · transfer_job_id: tj_01HX...
  ```
- Download events (FR-BP-11) 도 같은 timeline 에 inline (state event 와 색 구분: download = `--color-teal-600`).
- Drawer 너비 480px. 닫기: `✕` / Esc / 외부 클릭.

### 11.8 (참고) 기존 design-spec-buyer-portal-demo 에서 승계되는 컴포넌트

본 v0.2 에서 **새로 정의하지 않음** — 그대로 재사용:
- `<PhaseStepper>` (5-phase) — design-spec-buyer-portal-demo §6
- `<DownloadTabs>` (browser / curl / python) — design-spec-buyer-portal-demo §7
- `<ApiKeyList>` (kid mask + revoke) — design-spec-buyer-portal-demo §8
- 21 에러 코드 toast/inline 매핑 — design-spec-buyer-portal-demo §7

---

## 12. 바이어 포털 — 화면 와이어 (4 개, 데스크톱만)

> **반응형 정책 (FR-BP 전반)**: 바이어 포털은 **데스크톱 ≥ 1280px 기본 타깃**. 태블릿 best-effort, 모바일은 v0.3 또는 구현 단계에서 fallback 결정 (dev-spec §5 NFR + Q-K-9 deferred). 본 §12 와이어는 1280px 기준만 제공.

### 12.1 `/search` — 3-pane 검색 (FR-BP-3)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [◆ RadiVault Marketplace]  Search · Orders · Docs · Account ▾   Sign out    │ ← nav
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ ┌──────────────┐ ┌──────────────────────────────────┐ ┌──────────────────┐ │
│ │ FACETS (280) │ │ RESULTS                          │ │ COHORT (320)     │ │
│ ├──────────────┤ ├──────────────────────────────────┤ ├──────────────────┤ │
│ │ Recent       │ │  ◆ 150 studies across 2 hospitals│ │ Selected: 12     │ │
│ │ searches     │ │   [CT, MR · age 50+]    [Save]   │ │ From 2 hospitals │ │
│ │ • CT chest   │ ├──────────────────────────────────┤ │                  │ │
│ │ • MR brain   │ │ ☐ [CT] Chest 50-59 M 287i 142MB │ │ ─────────────── │ │
│ │              │ │ ☑ [CT] Chest 60-69 F 312i 156MB │ │ [CT] Chest       │ │
│ │ Federated    │ │ ☑ [MR] Brain 40-49 M 423i 318MB │ │      60-69 · F   │ │
│ │ ━●─────── 1+ │ │ ☐ [MG] Breast 50-59 F 4i 8MB   │ │ ✕ HOSP-A2        │ │
│ │              │ │ ...                              │ │                  │ │
│ │ Modality     │ │                                  │ │ [MR] Brain       │ │
│ │ ☑ CT (87)    │ │  Showing 25 of 150               │ │      40-49 · M   │ │
│ │ ☑ MR (45)    │ │  [Load more]                     │ │ ✕ HOSP-B7        │ │
│ │ ☐ MG (12)    │ │                                  │ │ ...              │ │
│ │ ☐ PT (3)     │ │                                  │ │                  │ │
│ │ ☐ US (3)     │ │                                  │ │ ─────────────── │ │
│ │              │ │                                  │ │ [Review order →] │ │
│ │ Body part... │ │                                  │ │   primary CTA    │ │
│ │ Age...       │ │                                  │ │                  │ │
│ │ Sex...       │ │                                  │ │                  │ │
│ │ Year...      │ │                                  │ │                  │ │
│ │              │ │                                  │ │                  │ │
│ │ Clear all    │ │                                  │ │                  │ │
│ └──────────────┘ └──────────────────────────────────┘ └──────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

- 좌 facet: `{#facet-sidebar-v1}` (280px 고정).
- 중앙 결과: `{#federated-signal-v1}` 상단 sticky + DataTable rows (`{#study-card-v1}` 반복).
- 우 cohort: `{#cart-item-v1}` mini variant 리스트 + 하단 primary CTA `[Review order →]` (FR-BP-9 진입).
- 1280~1439px 에서는 facet collapsible (햄버거 아이콘 노출).

### 12.2 `/studies/[id]` — Study 상세 풀페이지 (FR-BP-8)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [◆ Marketplace]  Search · Orders · Docs · Account ▾                         │
├──────────────────────────────────────────────────────────────────────────────┤
│ [← Back to results]  StudyUID: 1.2.840...1234       [+ Add to cohort]       │ ← sticky
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ◆ HOSP-A2 · From this hospital's pool of 87 studies   [view all →]         │
│                                                                              │
│  ┌──────────────────────────────────┐  ┌──────────────────────────────────┐ │
│  │ STUDY METADATA                   │  │ SERIES (3)                       │ │
│  │                                  │  │                                  │ │
│  │ Modality        [CT]             │  │ # Description    Mod  Inst Size  │ │
│  │ Body Part       CHEST            │  │ 1 AXIAL 1.0mm    CT   287  142MB │ │
│  │ Age Bucket      50-59            │  │ 2 CORONAL MIP    CT   64   32MB  │ │
│  │ Sex             M                │  │ 3 SCOUT          CT   2    1MB   │ │
│  │ Manufacturer    SIEMENS          │  │                                  │ │
│  │ Model           SOMATOM Force    │  │                                  │ │
│  │ Study Date      2023-08-14       │  │                                  │ │
│  │ Slice Thick     1.0 mm           │  │                                  │ │
│  │ KVP             120              │  │                                  │ │
│  │ Pixel Spacing   0.78 × 0.78      │  │                                  │ │
│  │ Total Bytes     142 MB           │  │                                  │ │
│  │ Instance Count  287              │  │                                  │ │
│  └──────────────────────────────────┘  └──────────────────────────────────┘ │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  [icon: monitor]                                                      │   │
│  │  DICOM viewer not included in v0.1.                                   │   │
│  │  Pixel data available after order fulfillment.                        │   │
│  │  [ Request viewer integration demo → ]                                │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```

`{#study-detail-v1}` (§11.4) 의 풀 화면 적용. 모바일/태블릿 deferred.

### 12.3 `/orders/new` — Cohort review · 주문 풀페이지 (FR-BP-9)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [◆ Marketplace]  Search · Orders · Docs · Account ▾                         │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Review your cohort                                                          │
│  12 studies · From 2 hospitals · ~1.8 GB total                              │
│                                                                              │
│  ┌──────────────────────────────────┐  ┌──────────────────────────────────┐ │
│  │ COHORT (12 studies)              │  │ HOSPITAL DISTRIBUTION            │ │
│  │                                  │  │                                  │ │
│  │ ✕ [CT] Chest 60-69 F  HOSP-A2    │  │     ┌─────────────┐              │ │
│  │ ✕ [MR] Brain 40-49 M  HOSP-B7    │  │     │  HOSP-A2 7  │              │ │
│  │ ✕ [CT] Chest 50-59 M  HOSP-A2    │  │     │  HOSP-B7 5  │              │ │
│  │ ✕ [MR] Brain 50-59 F  HOSP-A2    │  │     │ (donut)     │              │ │
│  │ ✕ [CT] Chest 70-79 M  HOSP-B7    │  │     └─────────────┘              │ │
│  │ ✕ [PT] Whole 60-69 F  HOSP-B7    │  │                                  │ │
│  │ ✕ [MR] Brain 30-39 M  HOSP-A2    │  │  Modality breakdown              │ │
│  │ ✕ [CT] Chest 80-89 F  HOSP-B7    │  │  CT  ████████ 6                  │ │
│  │ ... (4 more)                     │  │  MR  ████ 4                      │ │
│  │                                  │  │  PT  ██ 2                        │ │
│  │ [+ Back to search]               │  │                                  │ │
│  └──────────────────────────────────┘  └──────────────────────────────────┘ │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ ORDER SUMMARY                                                         │   │
│  │                                                                       │   │
│  │ Studies              12                                               │   │
│  │ Hospitals            2  (HOSP-A2, HOSP-B7)                            │   │
│  │ Total size           ~1.8 GB                                          │   │
│  │ Estimated cost       — Contact for pricing                            │   │
│  │                                                                       │   │
│  │ ☐ I agree to the Data Use Agreement (v0.2.1) [view DUA →]            │   │
│  │                                                                       │   │
│  │ [ Submit order → ]   [ Save as draft ]                                │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```

- 좌: cohort 풀 테이블 (`{#cart-item-v1}` 풀 variant).
- 우: hospital donut + modality breakdown bar chart.
- 하: 주문 summary + DUA checkbox + submit. Submit 시 dialog 컨펌 → `POST /api/orders` (FR-BP-9).
- DUA 미체크 → submit disabled + tooltip `Please agree to the Data Use Agreement to continue`.
- 가격: dev-spec §Q3 미정 → "Contact for pricing" 마스킹 (K-8 결정).

### 12.4 `/account` — 계정 / API 키 / Billing stub (FR-BP-13)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [◆ Marketplace]  Search · Orders · Docs · Account ▾                         │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Account                                                                     │
│                                                                              │
│  ┌──────────────────────────────────┐                                       │
│  │ PROFILE                          │                                       │
│  │ buyer_id      buy_demo001        │                                       │
│  │ email         dana@example.ai    │                                       │
│  │ tier          preview            │                                       │
│  │ created       Apr 12, 2026       │                                       │
│  └──────────────────────────────────┘                                       │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ API KEYS                                              [+ Issue new]   │   │
│  │                                                                       │   │
│  │ kid prefix       created       last used      status                  │   │
│  │ rv_live_a3f8...  Apr 12, 2026  2h ago         active   [Revoke]       │   │
│  │ rv_live_b9e1...  Mar 04, 2026  never          active   [Revoke]       │   │
│  │ rv_live_c2d7...  Feb 11, 2026  Mar 30         revoked  —              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────┐                                       │
│  │ BILLING                          │                                       │
│  │ Invoicing handled offline in v0.1│                                       │
│  │ [ Contact billing → ]            │                                       │
│  └──────────────────────────────────┘                                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

- API key 마스킹: 항상 prefix 8 자만 + `...` (Stripe 패턴, FR-BP-13).
- "Issue new" 클릭 → modal → secret 1 회만 표시 + copy + warning `This is the only time you'll see the full key`. 닫으면 secret 사라짐.
- Revoke → confirm dialog (`Type kid prefix to confirm` 강제).
- Billing: v0.1 stub. mailto link.

---

## 13. 라우팅 + 인증 (바이어 포털)

| 경로 | 인증 | iron-session 키 | 비고 |
|------|------|------------------|------|
| `/signin` | 공개 | — | 미인증만. 인증 시 `/` redirect. |
| `/` (대시보드) | 필수 | `rv_buyer_session` | FR-BP-20 (5 타일). v0.1 에서는 `/search` redirect 허용. |
| `/search` | 필수 | `rv_buyer_session` | FR-BP-3 3-pane. |
| `/studies/[id]` | 필수 | `rv_buyer_session` | FR-BP-8. 404 시 §14.3 처리. |
| `/orders/new` | 필수 | `rv_buyer_session` | FR-BP-9. cohort empty 시 `/search` redirect + toast. |
| `/orders` | 필수 | `rv_buyer_session` | 주문 리스트. |
| `/orders/[id]` | 필수 | `rv_buyer_session` | FR-BP-10 stepper + drawer. |
| `/orders/[id]/downloads` | 필수 | `rv_buyer_session` | FR-BP-11. order phase ≥ READY 만 접근 가능. |
| `/account` | 필수 | `rv_buyer_session` | FR-BP-13. |
| `/docs` | 공개 | — | v0.1 stub. |
| `/api/*` | session 검증 | `rv_buyer_session` (HttpOnly) | BFF 전체. 401 시 `/signin?return=<path>` redirect. |

**미인증 → 보호 경로 접근**: middleware 가 `/signin?return=<encoded_path>` 로 302. 로그인 성공 후 `return` 으로 복귀.

**세션 TTL**: 12h (dev-spec §5 NFR). 만료 시 401 → 자동 redirect + toast `Session expired. Please sign in again.`.

**Federated 격리** (CRITICAL, FR-BP 전 화면 공통): buyer scope 의 `allowed_hospitals` 외 study UID 접근 시 → 403 + page-level error `You don't have access to studies from this hospital.` (§14.4). cohort 에 무권한 study 추가 시도 → toast 차단.

---

## 14. 에러 표시 패턴

dev-spec §7.5 의 21 에러 코드 envelope (`error` / `detail_en` / `detail_ko` / `hint` / `request_id` / `doc`) 를 3 가지 UI 패턴으로 매핑. 21 코드 전수 매핑은 design-spec-buyer-portal-demo §7 표 그대로 승계 — 본 v0.2 는 **분류 기준만** 정의.

### 14.1 Toast (5초 자동 dismiss · 비차단)

- 사용 case: 일시적 / 사용자 행동 가능 / 화면 일부만 영향.
- 예시 코드: `ERR_RATE_LIMITED` (429) · `ERR_SAVE_FAILED` · download URL 만료 직전 알림.
- 위치: 우측 하단. 동시 최대 3 개 stack.
- 구조: `[icon][title][detail][action?]`. action 없으면 4초, 있으면 7초.
- 색: warning bg `#fffbeb` + warning fg `#b45309` (§4.4).
- KR/EN: locale 따라 `detail_ko` / `detail_en` 자동 선택.

### 14.2 Inline (form / field 옆)

- 사용 case: 사용자 입력 검증 / 단일 필드 영향.
- 예시 코드: `ERR_QUERY_TOO_BROAD` (422, facet 옆) · `ERR_INVALID_DUA` (`/orders/new` checkbox 옆) · `ERR_VALIDATION` (form field).
- 구조: field 아래 `text-sm / text-error-fg` (§4.4 error fg `#b91c1c`) + `[icon: alert-circle]` 16px 좌측.
- `hint` 필드는 회색 보조 메시지로 표시 (`Try adding a modality filter`).

### 14.3 Page-level (전체 화면 / banner)

- 사용 case: 페이지 전체 렌더 불가 / 권한 없음 / 시스템 장애.
- 예시 코드:
  - `404 ERR_STUDY_NOT_FOUND` → `/studies/[id]` 풀페이지 빈 상태 일러스트 + `[← Back to results]`.
  - `403 ERR_FORBIDDEN_HOSPITAL` → §14.4 (no-permission).
  - `5xx ERR_INTERNAL` / `ERR_UPSTREAM_DOWN` → 풀페이지 banner + `request_id` 표시 + `[Retry]` + `[Contact support]` (mailto + request_id 자동 prefill).
  - Network offline → `Offline` banner top-fixed.
- 구조: `{#value-tile-v1}` variant 차용 — 큰 아이콘 + 제목 + detail + 1~2 action.

### 14.4 No-permission (403 전용)

- `ERR_FORBIDDEN_HOSPITAL` / `ERR_FORBIDDEN_ORDER`:
  - 페이지 진입 시 → page-level error (§14.3 패턴).
  - 액션 시도 시 (cohort add 등) → toast `You don't have access to this hospital. Contact your account manager.` + 액션 차단.
- 401 (세션 만료) 은 별개: 즉시 `/signin?return=<path>` redirect + toast (§13).

### 14.5 Partial failure (일부 실패)

- 검색 결과 일부 hospital upstream 만 실패 → `{#federated-signal-v1}` 옆 warning chip `1 of 2 hospitals temporarily unavailable. Showing partial results.` (`request_id` clickable for support).
- 주문 download 일부 파일 실패 → DownloadTabs 내 row 단위 status 표시 (success / failed / retry).

---

## 15. Kyle 결정 필요 (바이어 한정) + 다음 호출 범위

### 15.1 신규 K-flag (v0.2 스코프)

| # | 항목 | designer 기본값 | Kyle 결정 필요 이유 |
|---|------|-----------------|----------------------|
| **K-8** | 가격 표시 정책 (`/orders/new` Estimated cost) | `— Contact for pricing` 마스킹 (dev-spec §Q3 deferred 그대로) | preview tier 에 실 가격 보여줄지 / Stripe 연결 v0.1.1+? 자율 영업 vs 영업팀 컨택. |
| **K-9** | 바이어 포털 모바일/태블릿 fallback | v0.1 deferred — `Best viewed on desktop ≥ 1280px` banner 만 | 데모 D-14 시한상 모바일 deprioritize OK 인지 / 투자자 미팅 시 iPad 시연 가능성. |
| **K-10** | Empty state 일러스트 톤 | 미니멀 line-art (Linear 스타일) + 1 문장 | shadcn/ui 기본 vs 맞춤 일러스트레이터 외주? 시한상 라이브러리 권고. |
| **K-11** | API key issue 시 secret 1회 표시 정책 | Stripe 패턴 (issue 직후 모달 1회만, 닫으면 사라짐) | UX 안전 vs 사용자 분실 위험. CSV download 옵션 제공 여부. |
| **K-12** | DUA 버전 표시 (`v0.2.1`) | 텍스트 표시 + `[view DUA →]` 링크는 v0.1 stub PDF | 실 DUA 문서 준비 일정 — 법무 검토 종료 시점. |

### 15.2 다음 호출 (v0.3) 범위 — 병원 콘솔

- §16. 병원 콘솔 정보 구조 (FR-HO-11 sitemap, 한국어 4 자 라벨).
- §17. 컴포넌트 — 9 타일 (Studies count + sparkline · Bytes monthly · Revenue sim · Orders in (마스킹) · Gateway HB 24h bar · Revenue trend stacked · Modality donut · `AuditChainStatusTile` 신규 · `QuotaRulesetTile` 신규) + Audit preview list + KRW 풀스펠 number formatter + 한국 dot map.
- §18. 한국식 풋터 — `{#footer-kr-v1}` 재사용 + 1:1 문의 플로팅 버튼 (mailto v0.1).
- §19. 병원 콘솔 상태 (toast/inline/page-level) + SSO 전환 placeholder (FR-HO-2 §Q10).

---

## 16. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-25 | @designer (Claude Opus 4.7) | 최초 작성. Homepage (FR-HP-1..13) + Shared tokens/components (FR-SH-1..5). 9 컴포넌트 + 10 홈페이지 와이어. 13 DA-HP AC. 7 Kyle flag (K-1..K-7). |
| **0.2** | **2026-04-25** | **@designer (Claude Opus 4.7)** | **바이어 포털 append (FR-BP-1..20). §11 컴포넌트 7 개 신규 (`{#modality-badge-v1}`·`{#federated-signal-v1}`·`{#study-card-v1}`·`{#study-detail-v1}`·`{#facet-sidebar-v1}`·`{#cart-item-v1}`·`{#order-timeline-v1}`). §12 화면 와이어 4 개 (`/search`·`/studies/[id]`·`/orders/new`·`/account`). §13 라우팅 + iron-session. §14 에러 패턴 5 분류. §15 K-8..K-12 신규 5 flag. v0.3 (병원 콘솔) 후속 append 예정.** |

---

### NEXT_STEP
- **완료 산출물**: `/Users/yonghyuk/Radivault/docs/specs/design-spec-portal-redesign.md` (v0.2 Draft — Homepage + Shared + Buyer Portal)
- **제안 다음 단계**:
  1. **@designer 후속 호출 v0.3** — 병원 콘솔 확장 (FR-HO-1..15) — 본 문서에 §17~§20 append.
  2. **@developer 병렬 착수 가능** —
     - FR-INF-1..4 (P0 블로커: search-side 테이블 적용 + buyer roundtrip smoke) 는 디자인 무관, 즉시.
     - 바이어 포털 컴포넌트 골격 (`{#modality-badge-v1}`·`{#federated-signal-v1}`·`{#facet-sidebar-v1}`) 은 v0.2 스펙으로 선행 구현 가능.
     - `/orders/new` 풀페이지 승격 (기존 ReviewOrderModal → 라우트) 도 선행 가능.
  3. **@marketer 병렬** — 바이어 포털 EN 마이크로카피 (`Federated Signal` 문안 · cohort empty · DUA stub · "Contact for pricing" 톤).
- **UI_GUIDE.md 갱신 제안**: §11 의 7 신규 컴포넌트 (`modality-badge-v1` / `federated-signal-v1` / `study-card-v1` / `study-detail-v1` / `facet-sidebar-v1` / `cart-item-v1` / `order-timeline-v1`) 를 §5 의 9 개와 함께 카탈로그 등재. ModalityBadge 7-variant 색 토큰은 Buyer blue 와 별개로 `--color-modality-*` 계열로 신규 추가 (§11.1). Kyle 승인 후 UI_GUIDE 공식 이관.
- **추가 디자인 필요**: v0.3 (병원 콘솔 9 타일 + 한국식 풋터 + AuditChainStatusTile / QuotaRulesetTile 신규) — 별도 호출.
- **Kyle 결정 필요 사항**: K-8 (가격 표시 정책) · K-9 (바이어 모바일 fallback) · K-10 (Empty 일러스트 톤) · K-11 (API key secret 1회 표시) · K-12 (DUA 버전·문서 준비). v0.1 의 K-1..K-7 도 미해결 시 prod 빌드 차단 (`[TBD]` detection). dev-spec §14.1 Q1·Q3·Q9·Q10 은 v0.3 (병원 콘솔) 호출에서 다룸.


## §17 Hospital Components

본 섹션은 병원 콘솔(`/hospital/*`) 전용 컴포넌트 7종을 정의한다. 모두 한국어 기본·Hospital teal(`--color-secondary-600` = `#0d9488`) 액센트. 데스크톱 1280 px 우선, mobile best-effort.

### 17.1 `<AuditChainStatusBadge>` {#audit-chain-status-v1}

- **연결 FR**: FR-HO-5 / FR-HO-14 (`GET /api/hospital/me/audit-chain-status`) / FR-INF-6.
- **Variant**: `ok` (teal #0d9488) · `stale` (amber #d97706, age > 1h) · `broken` (red #dc2626, `chain_continuous=false`).
- **Spec**: 64 px tall pill. 좌측 status dot(8 px) + 우측 2-line text. 1행 `최근 앵커 14:23 KST` (KST 변환 필수, FR-HO-13). 2행 hash prefix 16자 monospace (`a3f8d9c1b2e4f5a6`).
- **State 처리**: loading skeleton 64 px. error 시 회색 dot + `상태 확인 불가 — 재시도`. no-permission 은 발생 X (병원 자기 데이터).
- **a11y**: `role="status"` + `aria-live="polite"`. 색만으로 의미 전달 금지 → 아이콘 ✓ / ⚠ / ✕ 병기.

### 17.2 `<GatewayHeartbeatChart>` {#gateway-heartbeat-v1}

- **연결 FR**: FR-HO-3.5 (타일 5).
- **Variant**: `online` (<5 m, teal) · `warning` (<30 m, amber) · `offline` (else, red).
- **Spec**: 24 시간 sparkline (240 × 48 px). 5분 bucket × 288 stripes. 우측에 마지막 hb 시각 텍스트 `마지막 신호 2분 전`. 호버 시 툴팁 (UTC + KST 병기).
- **State 처리**: loading 24 stripe 회색 placeholder. empty (Gateway 미설치 시) `Gateway 미연결`. error → 회색 stripe + 메시지.

### 17.3 `<QuotaTile>` {#quota-tile-v1}

- **연결 FR**: FR-HO-6 / FR-INF-7 (`GET /api/hospital/me/quota`).
- **Variant**: `healthy` (<70%) · `warn` (70–90%, amber) · `critical` (>90%, red).
- **Spec**: 단일 타일 내 3-up 구조 (가로 분할 33/33/33). (a) 일일 byte 진행 bar + `123 MB / 10 GB`. (b) 월간 byte 진행 bar + `987 MB / 300 GB`. (c) 동시 업로드 `4` 큰 숫자. 각 segment 하단 reset 시각 (KST). 단위 변환 `formatBytes()` 공통 유틸.
- **State 처리**: loading 3-up skeleton. error 시 `쿼터 조회 실패`. partial-failure (daily 만 OK, monthly fail) → 실패 segment 만 회색.

### 17.4 `<RulesetVersionBadge>` {#ruleset-badge-v1}

- **연결 FR**: FR-HO-6 / FR-INF-7 응답의 `ruleset_version` + `salt_version` + `pixel_engine_version`.
- **Variant**: `current` (teal) · `outdated` (amber, salt rotate > 90일).
- **Spec**: 3-line stacked badge. `de-id ruleset v0.1.0` / `salt 2026-01` / `pixel engine v0.2.0`. 최하단 `다음 salt rotate: 2026-07-01 (KST)`. 클릭 시 `/hospital/settings` 로 이동 (read-only).
- **State 처리**: loading 3-line skeleton. error → `버전 정보 미수신`.

### 17.5 `<ModalityDistributionChart>` {#modality-dist-v1}

- **연결 FR**: FR-HO-3.7 (타일 7).
- **Spec**: Donut chart 200 × 200 px. 색상은 FR-BP-5 modality 토큰 승계 (CT blue / MR purple / CR·DR green / MG pink-darker / US orange / PT red / XA gray). 도넛 가운데 총 study 수 큰 숫자. 우측 legend (4자 라벨 + count + %).
- **State 처리**: loading 도넛 회색. empty (study 0) → 회색 원 + `데이터 없음`.
- **a11y**: 도넛에 `<title>` `<desc>` SVG 노드. 색맹 대응으로 hover 시 패턴(stripe/dot) 토글 옵션.

### 17.6 `<RevenueTile>` {#revenue-tile-v1}

- **연결 FR**: FR-HO-3.3 (타일 3, 시뮬) / FR-HO-13 (KRW 풀스펠).
- **Spec**: 큰 숫자 `₩ 18,400,000` (32 px Pretendard SemiBold) + 우측 상단 Δ 배지 `▲ 12.3% vs 지난 달` (teal=상승, red=하락). 하단 disclaimer 회색 12 px `시뮬레이션 — v0.2 정산 대기` (FR-HO-3.3 강제).
- **State 처리**: loading 숫자 자리 skeleton. empty (첫 달) → `—` + `이번 달 첫 데이터 누적 중`.
- **K-13 의존**: 표기 형식(풀스펠 vs `150K KRW`)은 §20 K-13 결정 대기.

### 17.7 `<OrderInflowTile>` {#order-inflow-v1}

- **연결 FR**: FR-HO-3.4 (타일 4, buyer 실명 마스킹).
- **Spec**: 큰 숫자 `42 건` + 부제 `이번 달 들어온 주문` 14 px. 하단 mini list 최근 3건 (`buyer ****` 마스킹 + study 수 + 시각). 클릭 → `/hospital/orders`.
- **State 처리**: loading skeleton. empty → `이번 달 들어온 주문 없음` + 일러스트(소형 회색 박스 아이콘).
- **보안**: buyer 실명 0건 보장 (FR-SH-5, FR-HO-3.4).

---

## §18 Hospital Wireframes

데스크톱 1280 px 기준. ASCII 박스는 60 chars 폭. mobile 은 1-column stack (best-effort).

### 18.1 `/hospital` — 9-tile 대시보드

```
+----------------------------------------------------------+
| [logo] RadiVault 병원 콘솔  [대시][주문][감사][설정][ㅗ]|
+----------------------------------------------------------+
|  HOSP-001 본병원 · 안녕하세요, 운영자님              KST|
+----------------------------------------------------------+
| +-------------+ +-------------+ +-------------+         |
| | 업로드 study | | total bytes | | modality 분포|        |
| | 1,247       | | 412 GB      | |   [donut]   |         |
| | [sparkline] | | ▲ 8.2%      | | CT MR DR... |         |
| +-------------+ +-------------+ +-------------+         |
| +-------------+ +-------------+ +-------------+         |
| | audit chain | | gateway HB  | | quota 3-up  |         |
| | ✓ 14:23 KST | | online 2분전 | | 일|월|동시  |         |
| | a3f8...f5a6 | | [24h spark] | | 진행 bar 3개 |        |
| +-------------+ +-------------+ +-------------+         |
| +-------------+ +-------------+ +-------------+         |
| | revenue     | | order inflow| | ruleset/salt|         |
| | ₩18,400,000 | | 42 건       | | v0.1.0      |         |
| | ▲ 12.3%     | | 최근 3건    | | salt 2026-01|         |
| | (시뮬)      | | buyer ****  | | rotate 7/01 |         |
| +-------------+ +-------------+ +-------------+         |
+----------------------------------------------------------+
| 최근 감사 이벤트 (20)               [전체 로그 →]       |
| · 14:23 anchor.posted   a3f8...                         |
| · 14:18 study.ingested  b71c...                         |
| ... (FR-HO-7)                                            |
+----------------------------------------------------------+
| [Korea heatmap, 2병원 시드, 실명 마스킹]                |
+----------------------------------------------------------+
| [한국 B2B Footer — 사업자등록·대표자·1544·PIPA]        |
+----------------------------------------------------------+
                                          [💬 1:1 문의] ← 우하단 floating
```

- **그리드**: 3 × 3, 각 타일 380 × 180 px, gap 16 px. `display: grid; grid-template-columns: repeat(3, 1fr);`.
- **컴포넌트 매핑**: 1=기존 sparkline tile · 2=신규 bytes tile · 3=`<ModalityDistributionChart>` · 4=`<AuditChainStatusBadge>` 확장 카드 · 5=`<GatewayHeartbeatChart>` · 6=`<QuotaTile>` · 7=`<RevenueTile>` · 8=`<OrderInflowTile>` · 9=`<RulesetVersionBadge>` 확장 카드.
- **로딩 우선순위**: 1·5·6·8 우선 fetch (운영 critical) → 2·3·7·9 lazy.
- **반응형**: ≤1280 → 2×5 (마지막 타일 단독 row). ≤768 → 1-column stack.

### 18.2 `/hospital/audit` — 감사 앵커 시간순 리스트

```
+----------------------------------------------------------+
| 감사 로그                              [필터: 24h ▾]    |
+----------------------------------------------------------+
| 시각 (KST)        type            hash prefix    chain  |
+----------------------------------------------------------+
| 2026-04-25 14:23  anchor.posted   a3f8d9c1b2e4  ✓      |
| 2026-04-25 14:18  study.ingested  b71c4e5a8f9d  ✓      |
| 2026-04-25 14:15  pixel.deid.ok   c92d1f3a7b8e  ✓      |
| 2026-04-25 14:12  anchor.posted   d04ef5a9c1b2  ✓      |
| ... (커서 페이지네이션)                                  |
+----------------------------------------------------------+
| [더 보기 →]                                              |
+----------------------------------------------------------+
```

- **State**: loading skeleton row 10개. empty `최근 24시간 감사 이벤트 없음`. error `로그 조회 실패 — 재시도`.
- **컬럼 폭**: 시각 220 / type 200 / hash 240 / chain 80.
- **v0.1 구현 범위**: 페이지 stub + 최근 20 이벤트만 렌더 (FR-HO-7). 풀 페이징·필터는 v0.1.1.

### 18.3 `/hospital/quota` — 쿼터 상세

```
+----------------------------------------------------------+
| 쿼터 상세                            HOSP-001 본병원   |
+----------------------------------------------------------+
| 일일 업로드                                              |
| [████████░░░░░░░░░░░░░] 123 MB / 10 GB (1.2%)           |
| 리셋: 2026-04-26 00:00 KST                              |
+----------------------------------------------------------+
| 월간 업로드                                              |
| [██░░░░░░░░░░░░░░░░░░░] 987 MB / 300 GB (0.3%)          |
| 리셋: 2026-05-01 00:00 KST                              |
+----------------------------------------------------------+
| 동시 업로드 한도                                         |
|   현재 max_concurrent_uploads: 4                         |
|   (Gateway config 기준, 변경은 운영팀 문의)              |
+----------------------------------------------------------+
| Ruleset / Salt / Pixel Engine                            |
|   de-id ruleset    v0.1.0                                |
|   salt version     2026-01  (다음 rotate: 2026-07-01)   |
|   pixel engine     v0.2.0                                |
+----------------------------------------------------------+
| ⓘ v0.1 한도 집행 없음 — 표시만. v0.1.1 부터 enforce.    |
+----------------------------------------------------------+
```

- **State**: loading 4 segment skeleton. partial-failure → 실패 segment 만 `조회 실패` 인라인. critical (>90%) → bar 색을 red 로.
- **a11y**: 진행 bar 에 `role="progressbar"` + `aria-valuenow` / `aria-valuemax`.

---

## §19 한국식 Footer 강화 + 1:1 문의 플로팅

### 19.1 `<Footer variant="hospital">` {#footer-kr-v1}

design-spec-buyer-portal-demo `<Footer>` 4-컬럼 KR variant 재사용. 단, 병원 콘솔에서는 다음 추가 강화:

- **상단 4 컬럼**:
  - **제품·솔루션**: 데이터 마켓플레이스 / 병원 파트너십 / De-ID 엔진
  - **기술**: Gateway Agent / 감사 앵커 체인 / API 문서
  - **회사**: 소개 / 채용 / 뉴스
  - **법적**: 개인정보처리방침 / 이용약관 / 위치기반서비스 약관 / 청소년보호정책

- **하단 법적 블록 (한국 B2B 필수, FR-HP-9 승계 + 강화)**:
  ```
  주식회사 라디볼트 (RadiVault Inc.)
  대표이사: Kyle Jeon  ·  사업자등록번호: [TBD §Q8]
  통신판매업신고: [TBD]  ·  개인정보보호책임자: Kyle Jeon (privacy@radivault.io)
  주소: [TBD §Q8]  ·  고객센터: 1544-[TBD] (평일 09:00–18:00 KST)
  ──────────────────────────────────────────────────────
  [PIPA §28-8 compliant]  [ISMS-P 준비 중]  [ISO 27001 aligned]
  © 2026 RadiVault Inc. All rights reserved.
  ```
- **Spec**: full-bleed, `--color-neutral-900` 배경 + `--color-neutral-100` 텍스트. 좌측 정렬, 컬럼 간 32 px gap. 하단 법적 블록은 11 px 회색.
- **i18n**: 한국어 페이지(병원·홈KR)에서만 이 variant 노출. 한국어 라벨이 영어보다 30% 짧음 가정 → 컬럼 width 240 px (영문 280 px 대비 축소).
- **빌드 가드**: `NODE_ENV=production` + `[TBD]` 문자열 감지 시 CI fail (FR-HP-9).

### 19.2 `<FloatingContactButton variant="korean">` (1:1 문의)

- **연결 FR**: FR-HO-10.
- **위치**: `position: fixed; bottom: 24px; right: 24px; z-index: 50;`. 한국어 페이지(`/ko/*`, `/hospital/*`) 에서만 렌더. 영문 페이지 노출 금지.
- **Closed state**: 56 × 56 px 원형 버튼, teal 배경, 흰 말풍선 아이콘. label `1:1 문의` 호버 툴팁.
- **Open state (클릭 시)**: 위쪽으로 280 × 180 px 카드 펼침. 2 옵션:
  ```
  +------------------------------------+
  | 문의 채널 선택                  ✕ |
  +------------------------------------+
  | [💬 카카오톡으로 문의하기]        |
  |    플러스친구 @radivault           |
  +------------------------------------+
  | [✉ 이메일로 문의하기]              |
  |    contact@radivault.io            |
  +------------------------------------+
  | 평일 09:00–18:00 KST 응답          |
  +------------------------------------+
  ```
- **K-14 의존**: KakaoTalk vs Email vs 둘 다 표시는 §20 K-14 결정 대기. 위 와이어는 "둘 다" 가정 default.
- **Mobile**: 동일 위치, 카드 폭 calc(100vw - 48px).
- **a11y**: 버튼 `aria-label="1:1 문의 열기"`. 카드 펼침 시 focus trap, ESC 키로 닫힘. 첫 옵션에 자동 focus.
- **State**: 단순 toggle, error/loading 없음 (mailto / kakao deeplink 만).

---

## §20 Kyle 결정 (병원 한정) + 변경이력 v0.3

### 새 결정 항목 (K-13 ~ K-15)

| ID | 결정 항목 | 옵션 A | 옵션 B | 옵션 C | 권고 |
|----|-----------|--------|--------|--------|------|
| **K-13** | KRW 표기 방식 (`<RevenueTile>`, FR-HO-13) | 풀스펠 `150,000 원` | 약식 `150K KRW` | 통화기호 `₩ 150,000` | **C (`₩ 150,000`)** — FR-HO-13 의 `₩ 18,400,000` 예시와 일치, 한국 사용자 직관성 + 영문 SRE 접근 시에도 통화 명확. K 단위 약어는 한국어 청중에게 어색. |
| **K-14** | 1:1 문의 채널 (FR-HO-10) | KakaoTalk only | Email only | 둘 다 | **C (둘 다)** — 한국 C-레벨은 카카오톡 선호, 글로벌 SRE 는 email. 다만 v0.1 KakaoTalk 플러스친구 미발급이면 B 로 fallback. |
| **K-15** | 가짜 매출 숫자 표기 (`<RevenueTile>` 시뮬) | 생성형 (Math.random seed 기반 매 세션 재생성) | 정적 더미 (HOSP-001 = ₩18.4M 고정) | 시간 기반 (월별 점진 증가 곡선) | **B (정적 더미)** — 시연 중 숫자 변동은 신뢰도 훼손. 단 disclaimer "시뮬레이션" 강제. C 는 D-day 데모 후 v0.1.1 에서 검토. |

### 기존 K-1 ~ K-12 의존성 (참조만, 본 v0.3 범위 외)

- K-1 (도메인) / K-4 (Hero 헤드라인) / K-8 (한국 법적정보 실값) 등은 §11~§15 (홈KR + 바이어) 에서 정의됨. 병원 콘솔은 K-8 의 `[TBD]` 만 동일하게 차용.

### 변경이력

| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|-----------|
| v0.1 | 2026-04-25 | @designer | 초안 — 홈페이지 + 바이어 포털 (§1~§10) |
| v0.2 | 2026-04-25 | @designer | 홈KR + 바이어 포털 보강 (§11~§16) |
| v0.3 | 2026-04-25 | @designer | 병원 콘솔 §17~§20 추가 |
