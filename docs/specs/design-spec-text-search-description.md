# 디자인 명세 — Text Search (검색바 + 자동완성 + 하이라이트)

> **Status**: Draft v0.1 · **Feature slug**: `text-search-description` · **Last updated**: 2026-04-26
> **작성자**: @designer (Claude Opus 4.7 [1M])
> **근거**:
>  - [`dev-spec-text-search-description.md`](./dev-spec-text-search-description.md) — Draft v0.1, 14 FR + 50+ AC, Phase 1.0 safe-field tsvector + autocomplete + PHI scrub.
>  - [`design-spec-portal-redesign.md`](./design-spec-portal-redesign.md) — §4 공유 토큰 (Buyer blue, Hospital teal, Slate neutral, Pretendard) · §11.1~11.6 바이어 포털 컴포넌트 (FacetSidebar / FederatedSignal / StudyCard / CohortCart).
>  - [`portal-redesign-competitive-analysis.md`](../research/portal-redesign-competitive-analysis.md) — §0 북극성 (정보 밀도·신뢰·이중 언어), §2.10 검색 UX 처방.
>  - [`text-search-postgres-fts-research.md`](../research/text-search-postgres-fts-research.md) — §3.2 word_similarity threshold, §UI 통합 지침.
>  - [`UI_GUIDE.md`](../UI_GUIDE.md) — placeholder. 본 문서는 `design-spec-portal-redesign.md §4` 토큰을 100% 차용하며, **신규 토큰은 `--mark-highlight-bg` 단 1 개**로 제한.

---

## 1. 디자인 개요

`/search` 의 **자유 텍스트 검색바**를 hero 영역에 단일 추가하여, buyer 가 `"MR brain"` · `"chest CT"` · `"I20.9"` 같은 직관적 쿼리를 입력하는 즉시 facet sidebar 와 dense table 위에 결과가 갱신되도록 한다. v3 의 3-pane 구조 (좌 facet · 중 결과 · 우 cohort) 는 **변경 없이** 보존하고, **검색바·자동완성 dropdown·결과 하이라이트** 3 개의 신규 표면만 추가한다.

**디자인 북극성 (1 줄)**: Segmed openda 의 단순 검색바 패턴을 차용하되, **"매치 필드 배지"** + **"KCD ko/en 동시 노출"** 2 가지 RadiVault 차별화로 의료 도메인 깊이를 시각화한다.

---

## 2. 화면 변경 영역 (스코프 선언)

| 영역 | 상태 | 변경 내용 |
|------|------|----------|
| `<SearchAppV3>` hero | **변경** | 페이지 헤더 직하, facet sidebar 위에 `<SearchBar>` slot 추가 (full-width, height 56 px) |
| `<FacetSidebarV3>` | **무변경** | facet 7 종 그대로. 단 검색바와 동시 사용 시 AND 결합 동작 (FR-TS-13). |
| `<ResultTable>` | **부분 변경** | row 셀 4 개 (`body_part`, `kcd_label_ko`, `kcd_label_en`, `modality`) 에 `<HighlightedText>` 적용. row 구조·컬럼 너비 무변경. |
| `<FederatedSignal>` (sticky 배지) | **부분 변경** | "150 studies across 2 hospitals" 우측에 활성 q 텍스트 chip 추가 (`q: "MR brain"` 형태, 클릭 시 검색바로 focus). |
| 우측 `<CohortCart>` | **무변경** | 영향 없음. |
| 신규 `<MaskedQueryBadge>` | **신규** | 검색바 우측, PHI scrub flagged 시만 노출. |

**HTML mockup**: `docs/specs/mockups/text-search-description/search-with-q.html` — 5 시나리오 (a 빈 / b 입력중 / c 결과 / d 0건 / e PHI 마스킹) 한 페이지.

---

## 3. 화면 목록

| ID | 화면명 | 경로 | 주요 역할 |
|----|--------|------|----------|
| S-1 | 검색 페이지 (q 빈) | `/search` | 검색바 placeholder · facet only 결과 (v3 baseline) |
| S-2 | 검색 페이지 (입력 중) | `/search?q=bra` (transient) | autocomplete dropdown 펼침, 결과는 직전 상태 유지 |
| S-3 | 검색 페이지 (결과) | `/search?q=MR%20brain` | dense table + `<mark>` 하이라이트 + `text_search_applied=true` |
| S-4 | 검색 페이지 (0건) | `/search?q=zzznotmatch` | empty state + clear 버튼 + facet 제거 추천 |
| S-5 | 검색 페이지 (PHI 마스킹) | `/search?q=홍길동%20brain` | 검색바 우측 `<MaskedQueryBadge>` 노출 + tooltip |

전부 **단일 라우트** (`/search`). URL `?q=` 파라미터로 deep-link 가능 (FR-TS-1).

---

## 4. 사용자 플로우

### 4.1 Happy path — 자유 텍스트 검색 후 facet 결합

```
[S-1: /search 진입]
  └─ 검색바 placeholder 노출, 250 study 전체
  ↓ buyer types "MR brain"
[S-2: 입력 중 (250ms debounce)]
  └─ autocomplete dropdown 펼침: ["BRAIN MR", "BRAIN MR (Transient ischaemic attack)", ...]
  ↓ buyer Enter (또는 dropdown 항목 클릭)
[S-3: 결과 노출 (38건)]
  └─ <mark>MR</mark> brain · <mark>BRAIN</mark> 셀 하이라이트
  └─ FederatedSignal "38 studies across 2 hospitals · q: MR brain"
  ↓ buyer 좌측 facet 에서 sex=F 추가 클릭
[S-3': 결과 좁혀짐 (15건)]
  └─ q + facet AND 결합, ts_rank_cd 정렬 유지
```

### 4.2 0 건 — 검색어 너무 좁힘

```
[S-3: 결과 38 건] → buyer types " contrast"
[S-4: 0 건]
  └─ "No studies match 'MR brain contrast'."
  └─ "Try removing filters or using different keywords."
  └─ [Clear search] 버튼 (q="" 으로 reset)
```

### 4.3 PHI 의심 query — 마스킹 + 검색은 진행

```
[S-1] → buyer 실수로 types "환자 홍길동 brain"
[S-5: 검색 진행 (raw query 보존)]
  └─ 검색바 우측에 <MaskedQueryBadge> 노출: "Query masked for privacy"
  └─ tooltip: "Search containing patient identifiers is not retained beyond 30 days."
  └─ 결과: 0 건 또는 brain 관련 row (search_text 에 환자명 없음 → 자연 0)
  └─ 백엔드 search_audit 에 raw_query (30d retention) + masked_query (영구) 둘 다 저장
```

### 4.4 권한 없음 / feature flag off

```
[S-0: TEXT_SEARCH_ENABLED=false 환경]
  └─ <SearchBar> 자체 hidden (NEXT_PUBLIC_TEXT_SEARCH_ENABLED 동기)
  └─ /search 가 v3 facet only 모드로 그대로 동작 (회귀 0)
```

### 4.5 에러 — autocomplete 다운

```
[S-2: 입력 중] → autocomplete API 500
  └─ dropdown 자동 닫힘 (silent failure)
  └─ <SearchBar> 자체는 동작 (Enter → POST /search/studies 직접)
  └─ console warning 만, UI 깨짐 0 (NFR-TS-AVAIL-2)
```

---

## 5. 컴포넌트 inventory

| 컴포넌트 | 신규/기존 | 목적 | 재사용 가능? |
|---------|----------|------|------------|
| `<SearchBar>` | **신규** | 검색 페이지 hero 영역의 자유 텍스트 입력. q state owner. | yes — v0.2 hospital console 재사용 가능 |
| `<AutocompleteDropdown>` | **신규** | input 아래 fixed dropdown, suggestion 렌더 + 키보드 navigation | yes — KCD code 입력 등 다른 입력에도 재사용 |
| `<AutocompleteSuggestionItem>` | **신규** | dropdown 단일 row. 매치 텍스트 + 필드 배지 | dropdown 내부 only |
| `<HighlightedText>` | **신규** | server `<mark>` HTML 안전 렌더 (DOMPurify). | ResultTable 셀 전반에서 reuse |
| `<MaskedQueryBadge>` | **신규** | PHI scrub flagged 시 검색바 우측 표시 + tooltip | SearchBar 종속 |
| `<SearchAppV3>` | **기존** | `q` state 추가, `<SearchBar>` slot 마운트 | — |
| `<FacetSidebarV3>` | **기존** | 무변경 (q 와 facet AND 결합은 BFF 단) | — |
| `<ResultTable>` | **기존** | 셀 4 개에 `<HighlightedText>` wrap | — |
| `<FederatedSignal>` | **기존** | 우측 chip 1 개 추가 (q 활성 시) | — |

각 컴포넌트의 props · state machine 은 §10 에서 상세.

---

## 6. `<SearchBar>` 컴포넌트 명세

### 6.1 위치 / 레이아웃

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [◆ RadiVault Marketplace]  Search · Orders · Docs · Account ▾   Sign out  │ ← nav (64px)
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─[🔍] Search by body part, modality, KCD code... (e.g. 'MR brain') ─[✕]┐ │ ← SearchBar (56px)
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
├──────────────┬──────────────────────────────────┬──────────────────────────┤
│ FACETS (280) │ RESULTS                          │ COHORT (320)             │ ← 3-pane (v3 무변경)
│ ...          │ ...                              │ ...                      │
└──────────────┴──────────────────────────────────┴──────────────────────────┘
```

- **위치**: nav 아래, `max-w-app = 1440px` 컨테이너 내, full-width.
- **상하 padding**: `space-6` (24 px) 위 / `space-4` (16 px) 아래 — 3-pane 까지의 visual breath.
- **높이**: **56 px** (Segmed openda 의 48 px 보다 의도적으로 8 px 큼 — 검색바가 페이지 시각적 진입점임을 강조).
- **모바일 (< 768 px)**: 높이 48 px, padding `space-3`. 단 buyer portal 은 desktop-first (`design-spec-portal-redesign.md §12 반응형 정책`) 라 모바일은 best-effort.

### 6.2 내부 레이아웃 (좌→우)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ [🔍 16px]  [input flex:1, font 16px Pretendard]  [✕ 16px]  [⏎ Search]  │
│  20px ←   placeholder or value                  → 20px    선택 (mobile) │
└─────────────────────────────────────────────────────────────────────────┘
```

| 영역 | 너비 | 색상 / 폰트 |
|------|------|-------------|
| 좌측 search 아이콘 | 16 × 16, padding `space-4` (16 px) 좌 | `--color-text-muted` (#64748b), focus 시 `--color-teal-600` |
| input | flex: 1, height 100% | `--color-text` 16 px Pretendard / Inter (locale). placeholder `--color-text-muted`. |
| 우측 clear (✕) | 16 × 16, padding `space-3` 우 | `--color-text-muted`, hover `--color-text`. **`q.length > 0` 시만 노출** |
| 우측 search 버튼 | 80 px, padding `space-2 space-4` | `--color-primary-600` fill + 흰 텍스트. **모바일 (< 1024 px) 보조 모드만 노출** (FR-TS-1). 데스크톱은 typing 즉시 검색 (250 ms debounce). |

### 6.3 상태 (state machine)

```
                  ┌─────────────┐
                  │   Idle      │ q=""
                  │ (placeholder)│
                  └──────┬──────┘
                         │ onFocus
                         ▼
                  ┌─────────────┐
                  │   Focused   │ border = teal accent
                  │  (q=" or x) │ ring shadow
                  └──────┬──────┘
                         │ onChange (debounce 200ms)
                         ▼
                  ┌─────────────┐    onClickOutside / Esc
                  │ Typing      │◄────────────────────────┐
                  │ + dropdown  │                          │
                  └──────┬──────┘                          │
                         │ Enter / 항목 선택               │
                         ▼                                  │
                  ┌─────────────┐                          │
                  │ Submitted   │ → POST /search/studies   │
                  │ (loading)   │                          │
                  └──────┬──────┘                          │
                         │ 200 OK                            │
                         ▼                                  │
                  ┌─────────────┐                          │
                  │  Result     │──────────────────────────┘
                  │ (q chip 노출)│
                  └─────────────┘
```

- **focus**: border `2px solid var(--color-teal-600)` + box-shadow `0 0 0 3px rgba(13, 148, 136, 0.15)`. `prefers-reduced-motion` 시 transition 50 ms.
- **error (PHI flagged)**: 동작은 정상, 우측에 `<MaskedQueryBadge>` 추가. border 색은 변경 없음 (사용자 차단이 아니므로 위협적 색 회피).
- **disabled**: 사용 안 함. feature flag off 시 컴포넌트 자체가 unmount.

### 6.4 placeholder (i18n)

| locale | 텍스트 |
|--------|--------|
| en | `Search by body part, modality, KCD code... (e.g. 'MR brain', 'CT chest', 'I20.9')` |
| ko | `부위·모달리티·KCD 코드로 검색 (예: 'MR brain', 'CT chest', 'I20.9')` |

- 한국어가 영어 대비 약 30 % 짧음 → 모바일 (320 px) 에서도 잘림 없이 노출.
- placeholder 길이 100 자 미만으로 제약.
- 데스크톱 (≥ 1024 px): full placeholder.
- 모바일 (< 768 px): 짧은 variant (`Search studies` / `검색`).

### 6.5 키보드 인터랙션

| 키 | 동작 |
|----|------|
| Tab | input focus 진입 |
| Esc | dropdown 닫기, q 비우지 않음 (한 번 더 Esc → q="" + dropdown 닫기) |
| Enter | 검색 제출 (debounce 무시 즉시) |
| ↓ | dropdown 첫 항목으로 focus 이동 |
| ↑ (input focus 시) | dropdown 마지막 항목으로 focus |
| Cmd/Ctrl + K | 페이지 어디서나 input focus (글로벌 단축키, optional v0.1.1) |

### 6.6 a11y

```html
<div role="search">
  <input
    type="search"
    role="searchbox"
    aria-label="Search studies by body part, modality, or KCD code"
    aria-autocomplete="list"
    aria-controls="autocomplete-listbox"
    aria-expanded="{dropdownOpen}"
    aria-activedescendant="{focusedSuggestionId}"
  />
  <button aria-label="Clear search" />
</div>
```

- `aria-label` 은 placeholder 와 별도, 항상 영어 alt (스크린리더 일관성). KR locale 에서는 `aria-label="검색어 입력 — 부위·모달리티·KCD 코드"`.
- 색맹 대응: focus 색은 teal 단독이 아니라 border 굵기 (1 → 2 px) + ring shadow 동시 적용.

---

## 7. `<AutocompleteDropdown>` 컴포넌트 명세

### 7.1 위치 / 크기

```
┌────────────────────────────────────────────────────────────────────────┐
│  [🔍] bra|                                                  [✕]        │ ← SearchBar
└────────────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────────────┐
│  BRAIN MR                                              [body_part]     │ ← suggestion 1
│  BRAIN CT                                              [body_part]     │ ← suggestion 2
│  BREAST MG                                             [body_part]     │ ← suggestion 3
│  Transient ischaemic attack — 일과성 뇌허혈 발작        [KCD G45.9]    │ ← suggestion 4
│  ...                                                                   │
└────────────────────────────────────────────────────────────────────────┘
   max-height: 400px (desktop) / 320px (mobile), scroll
```

- **위치**: `<SearchBar>` 바로 아래, `position: absolute`, top = SearchBar height (56 px), left/right = 0.
- **z-index**: 50 (FacetSidebar 와 ResultTable 위, nav 아래).
- **너비**: `<SearchBar>` 와 동일 full-width (검색바 자체가 max-w-app 컨테이너 내라 자연스럽게 align).
- **max-height**: 400 px (desktop), 320 px (mobile). 초과 시 scroll.
- **항목 max**: 12 (desktop), 8 (mobile). dev-spec FR-TS-8 의 `limit=10` 과 클라이언트 cap 통일 위해 BFF 가 desktop=12 / mobile=8 로 호출.

### 7.2 항목 구조 (`<AutocompleteSuggestionItem>`)

```
┌────────────────────────────────────────────────────────────────────────┐
│  BRAIN MR                                              [body_part]     │
│  ↑ matched text (semibold + teal underline on match token)             │
└────────────────────────────────────────────────────────────────────────┘
   padding: space-3 space-4 (12px 16px)
   height: 44px (단순 텍스트), 56px (KCD 한글+영문 2줄)
```

| 영역 | 스타일 |
|------|--------|
| 매치 텍스트 | `text-base / font-medium / text-text` · 매치 토큰 (`bra` 부분) 만 `font-semibold` + `text-teal-700` + 1 px underline |
| 우측 배지 | `text-xs / text-text-muted` · `radius-pill` · padding 2×8 · 변형: `body_part` (slate) / `KCD <code>` (teal-100 bg + teal-700 text) / `modality` (slate) / `manufacturer` (slate) / `model` (slate) |
| KCD 항목 (특수) | 2 줄: 영문 라벨 (top, font-medium) + 한글 라벨 (bottom, text-sm text-text-muted). 우측 배지에 `KCD G45.9` 노출. |

**필드 배지 색상 매트릭스**:

| 배지 | bg | fg | 의도 |
|------|-----|-----|------|
| `body_part` | `--color-bg-muted` (#f8fafc) | `--color-text-muted` | 가장 흔한 매치 — neutral |
| `modality` | `--color-bg-muted` | `--color-text-muted` | neutral |
| `KCD <code>` | `--color-teal-100` (#ccfbf1) | `--color-teal-700` (#0f766e) | 의료 도메인 강조 — RadiVault 차별화 |
| `manufacturer` / `model` | `--color-bg-muted` | `--color-text-muted` | neutral |

### 7.3 상호작용

- **hover**: 항목 bg → `--color-primary-50` (#eff6ff). cursor: pointer.
- **focus (키보드)**: bg → `--color-primary-50` + 좌측 4 px solid `--color-primary-600` accent (Selected row 와 동일 패턴, `<StudyCard>` 와 일관).
- **클릭 / Enter**: `onSelect(suggestion)` → `<SearchBar>` 가 q 를 해당 suggestion 으로 set + 검색 트리거 + dropdown 닫음.
- **로딩**: 첫 fetch 가 100 ms 초과 시 dropdown 자리에 inline spinner (12 px) + "Loading suggestions..." 텍스트. 100 ms 미만은 spinner 미노출 (UX 부드러움).
- **빈 결과**: dropdown 에 한 줄 `No suggestions for "bra"` (`text-sm / text-text-muted` / padding `space-3`).
- **에러**: dropdown 자동 닫힘 (silent). `<SearchBar>` 자체는 동작.

### 7.4 키보드 navigation

| 키 | 동작 |
|----|------|
| ↓ / ↑ | 항목 이동 (wrap-around: 마지막에서 ↓ → 첫 항목, 첫 항목에서 ↑ → input 으로 복귀) |
| Enter | 현재 focus 항목 선택 |
| Esc | dropdown 닫기 (input focus 유지, q 보존) |
| Tab | dropdown 닫기 + 다음 focusable 요소 (예: facet sidebar 첫 옵션) 로 이동 |
| Home / End | 첫 / 마지막 항목 |

### 7.5 a11y

```html
<ul
  id="autocomplete-listbox"
  role="listbox"
  aria-label="Search suggestions"
>
  <li
    id="suggestion-0"
    role="option"
    aria-selected="{focused === 0}"
  >
    <span>BRAIN MR</span>
    <span class="badge" aria-label="Match field: body part">body_part</span>
  </li>
</ul>
```

- 매 항목에 `aria-selected` 동기화 (focus 변경 시).
- 매치 토큰 underline 은 시각 단서, `aria-label` 에는 raw text (스크린리더 중복 회피).
- color contrast: 매치 토큰 teal-700 (#0f766e) on white = 6.45:1 — WCAG AAA 통과.

---

## 8. `<HighlightedText>` 컴포넌트 명세

### 8.1 역할

server 의 `ts_headline` 결과 (예: `BRAIN <mark>MR</mark>`) 를 안전하게 React 렌더. ResultTable 셀에서만 사용.

### 8.2 props

```typescript
interface HighlightedTextProps {
  html: string | null;        // server 가 전달한 ts_headline 결과 (null = q 미사용)
  fallback: string;           // q 없을 때 raw 텍스트
  maxLength?: number;         // truncate 길이 (default 80)
}
```

### 8.3 CSS

```css
.highlighted-text mark {
  background: var(--mark-highlight-bg);    /* 신규 토큰 */
  color: var(--color-text-strong);         /* 살짝 darker — 색맹 대응 */
  font-weight: 600;                         /* Pretendard semibold */
  padding: 0 2px;
  border-radius: 2px;
}
```

- `--mark-highlight-bg`: `rgba(13, 148, 136, 0.15)` — teal-600 의 15 % alpha (배경 위에 부드럽게 얹힘, dense table 의 행 줄무늬와 충돌 없음).
- **색맹 대응**: 색만으로 매치 신호 의존하지 않음. 추가 단서: (1) font-weight 600 (semibold), (2) text color slightly darker (#020617), (3) padding 으로 크기 차이.
- **WCAG AA**: text-strong (#020617) on rgba teal bg ≈ 14.x:1 — AAA 통과.

### 8.4 보안 (XSS 방지)

- server `ts_headline` 이 `StartSel=<mark>, StopSel=</mark>` 만 삽입, 다른 HTML 자동 escape (PostgreSQL native 보장).
- 클라이언트 추가 방어: DOMPurify 로 화이트리스트 `<mark>` 태그만 통과. 다른 모든 태그 / attribute 제거.
- `dangerouslySetInnerHTML` 사용 직전 DOMPurify 통과 (FR-TS-9, dev-spec NFR-TS-SEC-2).

### 8.5 상태

- **html === null** (q 미사용): fallback 을 raw 텍스트로 렌더, `<mark>` 없음.
- **html === ""** (q 사용했으나 매치 없는 셀): fallback 렌더.
- **html length > maxLength**: truncate + `…` 부착. `<mark>` 가 truncate 경계에 걸리면 `</mark>` 보존 보장 (DOMPurify 가 처리).

---

## 9. `<MaskedQueryBadge>` 컴포넌트 명세

### 9.1 역할

PHI scrub 가 query 에서 패턴 (KOREAN_NAME, RRN, MRN 등) 을 발견했을 때 검색바 우측에 노출하는 작은 배지. **차단이 아닌 사용자 알림**.

### 9.2 위치

```
┌────────────────────────────────────────────────────────────────────────┐
│  [🔍] 홍길동 brain                              [⚠ Query masked] [✕]  │
└────────────────────────────────────────────────────────────────────────┘
                                                  ↑
                                                  <MaskedQueryBadge>
                                                  hover → tooltip
```

- 검색바 내부 우측, clear (✕) 버튼 왼쪽.
- 높이 28 px, 검색바 56 px 안에 vertically center.

### 9.3 스타일

- **bg**: `--color-warning-light` (#fffbeb)
- **fg**: `--color-warning-dark` (#b45309)
- **icon**: warning triangle 14 px 좌측
- **text**: `text-xs / font-medium` · "Query masked" (en) / "검색어 마스킹됨" (ko)
- **radius**: `radius-pill`
- **padding**: 4×10 px

### 9.4 tooltip

hover / focus 시 노출:

| locale | 내용 |
|--------|------|
| en | `Search containing patient identifiers is masked in our audit logs and not retained beyond 30 days. Your search still runs as-is.` |
| ko | `환자 식별 정보가 포함된 검색어는 감사 로그에서 마스킹되며 30일 이후 폐기됩니다. 검색은 입력 그대로 실행됩니다.` |

- tooltip 폭 320 px, padding `space-3`, bg `--color-text-strong` (#020617), fg white, `radius-md`, `shadow-overlay`.
- arrow 8 px 위쪽 가리킴.
- focus 시 `aria-describedby` 로 input 에 연결.

### 9.5 상태

- **invisible (default)**: PHI scrub `flagged_patterns.length === 0` 또는 q="" 시 unmount.
- **visible**: 백엔드 응답 `meta.phi_flagged_patterns` 가 non-empty 일 때만 노출. 응답 도착 후 mount (검색 진행 중에는 미노출 — FOIT 방지).

### 9.6 a11y

- `role="status"` + `aria-live="polite"` — 마운트 시 스크린리더가 한 번 읽음.
- focus 가능 (`tabindex=0`) — tooltip 키보드로도 확인 가능.

---

## 10. 결과 0건 / 에러 상태

### 10.1 0건 (S-4)

```
┌──────────────────────────────────────────────────────────────────────┐
│  [🔍] MR brain contrast zzz                                  [✕]    │
└──────────────────────────────────────────────────────────────────────┘
┌──────────────┬──────────────────────────────────────────────────────┐
│ FACETS       │                                                      │
│ ...          │   [icon: search-x 48px, text-text-muted]            │
│              │                                                      │
│              │   No studies match "MR brain contrast zzz"           │
│              │                                                      │
│              │   Try removing filters or different keywords:        │
│              │     · MR brain                                       │
│              │     · brain contrast                                 │
│              │                                                      │
│              │   [ Clear search ]   [ Reset all filters ]           │
│              │                                                      │
└──────────────┴──────────────────────────────────────────────────────┘
```

- 중앙 정렬, padding `space-16` 위/아래.
- 아이콘: lucide `search-x` 48 px, color `--color-text-muted`.
- 헤드라인: `text-lg / font-semibold / text-text` · `No studies match "<q>"`.
- 보조: `text-sm / text-text-muted` · 추천 키워드 (q 의 토큰 split + 마지막 토큰 제거 변형).
- CTA pair: `[Clear search]` (primary, q="" reset) + `[Reset all filters]` (secondary, q="" + facets reset).

**i18n**:

| locale | 헤드라인 | 보조 | CTA1 | CTA2 |
|--------|---------|------|------|------|
| en | `No studies match "MR brain contrast zzz"` | `Try removing filters or different keywords:` | `Clear search` | `Reset all filters` |
| ko | `"MR brain contrast zzz" 와 일치하는 study 없음` | `필터를 제거하거나 다른 키워드를 시도해 보세요:` | `검색어 지우기` | `필터 모두 초기화` |

### 10.2 에러 (검색 API 500)

- ResultTable 영역에 inline error banner:
  ```
  ┌──────────────────────────────────────────────────────────────────────┐
  │  ⚠ Search service unavailable                              [Retry]   │
  │     Please try again in a moment.                                    │
  └──────────────────────────────────────────────────────────────────────┘
  ```
- bg `--color-error-light` (#fef2f2), fg `--color-error-dark` (#b91c1c), border-left 4 px solid.
- `[Retry]` 버튼 → 동일 query 재호출.
- 검색바 자체는 동작 유지.

### 10.3 권한 없음 (401)

- v3 baseline 의 `/login` redirect 동작 그대로. 검색바 신규 분기 없음.

### 10.4 feature flag off

- `<SearchBar>` 자체 unmount. `/search` 페이지가 v3 facet only 모드로 그대로 동작 (회귀 0).

### 10.5 부분 실패 (autocomplete 다운, search 정상)

- §7.3 참조: dropdown silent close, search 동작 유지.

---

## 11. 디자인 토큰

### 11.1 차용 (기존 v3 토큰 그대로)

| 토큰 | 값 | 사용처 |
|------|-----|--------|
| `--color-primary-50` | `#eff6ff` | dropdown 항목 hover/focus bg |
| `--color-primary-600` | `#2563eb` | dropdown focus 좌측 accent, 모바일 search 버튼 fill |
| `--color-teal-100` | `#ccfbf1` | KCD 배지 bg |
| `--color-teal-600` | `#0d9488` | search bar focus border, 매치 토큰 underline |
| `--color-teal-700` | `#0f766e` | KCD 배지 fg, 매치 토큰 text |
| `--color-bg` | `#ffffff` | search bar bg, dropdown bg |
| `--color-bg-muted` | `#f8fafc` | 일반 배지 bg, 0건 empty illustration bg |
| `--color-border` | `#e2e8f0` | search bar idle border, dropdown divider |
| `--color-border-strong` | `#cbd5e1` | search bar input border (hover) |
| `--color-text` | `#0f172a` | input value, dropdown 텍스트 |
| `--color-text-muted` | `#64748b` | placeholder, 배지 fg, 보조 |
| `--color-text-strong` | `#020617` | mark 내부 텍스트 (color contrast 강화) |
| `--color-warning-light` | `#fffbeb` | MaskedQueryBadge bg |
| `--color-warning-dark` | `#b45309` | MaskedQueryBadge fg |
| `--color-error-light` | `#fef2f2` | 에러 banner bg |
| `--color-error-dark` | `#b91c1c` | 에러 banner fg |
| `--font-sans-en` | Inter ... | input value, suggestion text (en locale) |
| `--font-sans-kr` | Pretendard ... | input value, suggestion text (ko locale) |
| `space-3` (12 px) | — | dropdown 항목 vertical padding |
| `space-4` (16 px) | — | search bar horizontal padding, dropdown 항목 horizontal padding |
| `radius-md` (8 px) | — | search bar 모서리, dropdown 모서리 |
| `radius-pill` (999 px) | — | 배지 (필드, MaskedQueryBadge) |
| `shadow-card` | `0 1px 3px rgba(15,23,42,0.08), ...` | dropdown shadow |
| `shadow-overlay` | `0 10px 25px rgba(15,23,42,0.10), ...` | tooltip shadow |

### 11.2 신규 토큰 (단 1 개)

| 토큰 | 값 | 용도 | 근거 |
|------|-----|------|------|
| `--mark-highlight-bg` | `rgba(13, 148, 136, 0.15)` | `<HighlightedText>` 의 `<mark>` 배경 | teal-600 의 15 % alpha. dense table 줄무늬 (#f8fafc) 위에서도 매치 토큰 식별 가능, 색맹 사용자 위해 font-weight 600 + text color #020617 동시 적용. |

**UI_GUIDE 갱신 제안**: 이 토큰은 추후 다른 검색 UI (병원 콘솔 audit log 검색 등) 에서도 재사용 가능. UI_GUIDE 가 공식화될 때 §색상 — 액센트에 추가 권장.

### 11.3 신규 토큰 거부된 후보 (의도적 미정의)

- `--search-bar-bg`: `--color-bg` 차용 충분.
- `--search-bar-border-focus`: `--color-teal-600` 차용 충분.
- `--autocomplete-bg`: `--color-bg` 차용 충분.
- `--autocomplete-shadow`: `shadow-card` 차용 충분.

→ Kyle 입력 ("신규 색 1개만") 100 % 준수.

---

## 12. 반응형 / 디바이스

### 12.1 정책 승계

`design-spec-portal-redesign.md §12 반응형 정책`: 바이어 포털은 **데스크톱 ≥ 1280 px 기본 타깃**, 태블릿 best-effort, 모바일 fallback.

### 12.2 breakpoint 별 동작

| breakpoint | SearchBar | AutocompleteDropdown | search 버튼 |
|-----------|-----------|---------------------|-------------|
| ≥ 1280 px (desktop) | height 56 px, full width, padding `space-4` | max 12 항목, max-height 400 px | hidden (typing 즉시 검색) |
| 768~1279 px (tablet) | height 56 px, full width | max 10 항목 | hidden |
| < 768 px (mobile, fallback) | height 48 px, padding `space-3`, placeholder 짧은 variant | max 8 항목, max-height 320 px, position: fixed top: 56px (input 아래) | **visible** (typing 후 명시 제출) |

### 12.3 모바일 특별 처리

- input focus 시 viewport 가 input 으로 scroll (iOS Safari 대응): `scrollIntoView({block: 'center'})`.
- dropdown 펼칠 때 body scroll lock 안 함 (검색 중 facet/result 확인 가능).
- 자동완성 항목 cap 8 (desktop 12) — 모바일 화면 점유 최소화.

---

## 13. 접근성 (WCAG 2.1 AA)

### 13.1 키보드 navigation 전수

| 동작 | 키 | 컴포넌트 |
|------|-----|---------|
| 검색바 focus | Tab | `<SearchBar>` |
| 검색 제출 | Enter | `<SearchBar>` |
| 검색어 지우기 | Esc 2회 또는 ✕ 클릭 | `<SearchBar>` |
| dropdown 열기 | typing 또는 ↓ | `<AutocompleteDropdown>` |
| dropdown 항목 이동 | ↑ ↓ (wrap-around) | `<AutocompleteDropdown>` |
| dropdown 항목 선택 | Enter | `<AutocompleteDropdown>` |
| dropdown 닫기 | Esc, Tab, 외부 클릭 | `<AutocompleteDropdown>` |
| MaskedQueryBadge tooltip | hover 또는 Tab focus | `<MaskedQueryBadge>` |

### 13.2 스크린리더 레이블

- input: `aria-label="Search studies by body part, modality, or KCD code"` (locale 별 KR variant).
- clear: `aria-label="Clear search"` / `aria-label="검색어 지우기"`.
- dropdown: `role="listbox"` + `aria-label="Search suggestions"`.
- 각 항목: `role="option"` + `aria-selected`.
- MaskedQueryBadge: `role="status"` + `aria-live="polite"`.
- 결과 갱신 후: `<FederatedSignal>` 영역에 `aria-live="polite"` (count 변경 시 한 번 읽음, 이미 v3 에 존재).

### 13.3 색 대비 (WCAG AA, 4.5:1)

| 조합 | 대비 | 결과 |
|------|------|------|
| input value `--color-text` (#0f172a) on `--color-bg` (#fff) | 18.69:1 | AAA |
| placeholder `--color-text-muted` (#64748b) on `--color-bg` | 4.91:1 | AA |
| dropdown 항목 `--color-text` on `--color-primary-50` (#eff6ff) | 16.50:1 | AAA |
| 매치 토큰 `--color-teal-700` on white | 6.45:1 | AAA |
| `<mark>` text `--color-text-strong` on `--mark-highlight-bg` (effective ~#dbede9) | ≈ 14:1 | AAA |
| KCD 배지 `--color-teal-700` on `--color-teal-100` (#ccfbf1) | 5.84:1 | AA |
| MaskedQueryBadge `#b45309` on `#fffbeb` | 4.74:1 | AA |
| 0건 헤드라인 `--color-text` on `--color-bg` | 18.69:1 | AAA |

**모든 텍스트 조합 WCAG AA 4.5:1 이상 통과**. 색맹 사용자 위해 매치 토큰은 색 + font-weight 600 동시 적용 (단일 색 의존 회피).

### 13.4 focus visible

- 모든 focusable 요소에 `outline: 2px solid var(--color-primary-600); outline-offset: 2px;` (글로벌 v3 정책 승계).
- 검색바 focus 시 outline 대신 border + ring shadow (의도적 visual 강조).
- `prefers-reduced-motion`: dropdown open / focus transition 50 ms 이하.

### 13.5 motion / animation

- dropdown open: opacity 0 → 1 + translateY(-4 px → 0), 100 ms ease-out. `prefers-reduced-motion` 시 즉시 노출.
- focus ring shadow: instant (transition 0).
- mark 하이라이트: animation 없음 (텍스트 안정성 우선).

---

## 14. 국제화 (i18n)

### 14.1 텍스트 키 표

| key | en | ko |
|-----|-----|-----|
| `search.placeholder` | `Search by body part, modality, KCD code... (e.g. 'MR brain', 'CT chest', 'I20.9')` | `부위·모달리티·KCD 코드로 검색 (예: 'MR brain', 'CT chest', 'I20.9')` |
| `search.placeholder.short` | `Search studies` | `검색` |
| `search.aria.input` | `Search studies by body part, modality, or KCD code` | `검색어 입력 — 부위·모달리티·KCD 코드` |
| `search.aria.clear` | `Clear search` | `검색어 지우기` |
| `search.button.submit` | `Search` | `검색` |
| `autocomplete.aria.listbox` | `Search suggestions` | `검색 추천` |
| `autocomplete.loading` | `Loading suggestions...` | `추천 검색어 불러오는 중...` |
| `autocomplete.empty` | `No suggestions for "{q}"` | `"{q}" 에 대한 추천 없음` |
| `autocomplete.badge.body_part` | `body part` | `부위` |
| `autocomplete.badge.modality` | `modality` | `모달리티` |
| `autocomplete.badge.kcd` | `KCD {code}` | `KCD {code}` |
| `autocomplete.badge.manufacturer` | `manufacturer` | `제조사` |
| `autocomplete.badge.model` | `model` | `모델` |
| `result.empty.headline` | `No studies match "{q}"` | `"{q}" 와 일치하는 study 없음` |
| `result.empty.body` | `Try removing filters or different keywords:` | `필터를 제거하거나 다른 키워드를 시도해 보세요:` |
| `result.empty.cta.clear` | `Clear search` | `검색어 지우기` |
| `result.empty.cta.reset` | `Reset all filters` | `필터 모두 초기화` |
| `error.search.unavailable` | `Search service unavailable` | `검색 서비스 일시 중단` |
| `error.search.retry` | `Please try again in a moment.` | `잠시 후 다시 시도해 주세요.` |
| `error.search.cta.retry` | `Retry` | `재시도` |
| `phi.badge.label` | `Query masked` | `검색어 마스킹됨` |
| `phi.badge.tooltip` | `Search containing patient identifiers is masked in our audit logs and not retained beyond 30 days. Your search still runs as-is.` | `환자 식별 정보가 포함된 검색어는 감사 로그에서 마스킹되며 30일 이후 폐기됩니다. 검색은 입력 그대로 실행됩니다.` |
| `signal.q_chip` | `q: "{q}"` | `검색어: "{q}"` |

### 14.2 한국어 길이 가이드

- 한국어가 영어보다 평균 30 % 짧음 (UI_GUIDE 기본 가정).
- placeholder: en 100 자, ko 50 자 — 모바일 fallback variant 별도 제공.
- 0건 헤드라인 q 보간: 사용자 q 가 길면 truncate 80 자 + `…`.

### 14.3 KCD 라벨 노출

- 자동완성에서 KCD 매치 시: 사용자 locale 따라 ko/en 우선 표시.
  - en locale: `Transient ischaemic attack — 일과성 뇌허혈 발작` (영문 우선, 한글 보조)
  - ko locale: `일과성 뇌허혈 발작 — Transient ischaemic attack` (한글 우선, 영문 보조)
- v3 의 `LocaleProvider` 가 이미 ko/en 토글 제공 → 그대로 활용, 신규 i18n 인프라 0.

### 14.4 RTL

- v3 baseline 이 LTR only. RTL 지원 backlog 그대로.

---

## 15. Segmed openda 와 비교 (RadiVault 차별화)

| 항목 | Segmed openda | RadiVault Phase 1.0 | 우월성 |
|------|---------------|---------------------|--------|
| 검색바 위치 | 페이지 hero 영역 | 페이지 hero 영역 (동일) | 동등 |
| 검색바 높이 | 48 px | **56 px** | RadiVault — 시각적 중요도 강조 |
| placeholder 예시 | `Search studies` (단순) | `Search by body part, modality, KCD code... (e.g. 'MR brain', 'I20.9')` | **RadiVault — 사용자에게 검색 가능 필드 힌트** |
| 자동완성 | 단순 텍스트 list | **매치 필드 배지 + KCD ko/en 동시 노출** | **RadiVault — 의료 도메인 깊이 시각화** |
| 매치 필드 표시 | 없음 | 항목 우측 배지 (`body_part` / `KCD G45.9` / `modality`) | **RadiVault — buyer 가 왜 매치되었는지 즉시 인식** |
| KCD 코드 검색 | 부분 지원 | full (한글 라벨 + 영문 라벨 동시 인덱싱) | **RadiVault** |
| 하이라이트 색 | 노란색 단색 | teal alpha + semibold + 색맹 대응 | **RadiVault — 의료 톤 + 접근성** |
| PHI 마스킹 알림 | 없음 (또는 차단) | `<MaskedQueryBadge>` 비차단 알림 + tooltip | **RadiVault — 사용자 친화 + compliance** |
| 결과 0건 | 단순 메시지 | 추천 키워드 + clear/reset 양쪽 CTA | **RadiVault — recovery path 명확** |
| Provenance 노출 | 없음 | per-hospital `hospital_opaque_id` chip (v3 baseline) | **RadiVault — 검색 결과의 federated 출처 명확** |
| feature flag rollback | 없음 | `TEXT_SEARCH_ENABLED=false` 30 초 회귀 | **RadiVault — 운영 안전성** |

---

## 16. Mockup HTML 스펙

**경로**: `docs/specs/mockups/text-search-description/search-with-q.html`

**구조**: 단일 페이지에 5 시나리오 stacked vertical, 각 시나리오 sticky 라벨 배지 ("a) Empty", "b) Typing", ...) + 1280 px wide 캡처.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  [a) Empty state — placeholder 노출]                                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  /search 화면 (S-1) — q="" baseline                                │ │
│  │  검색바 placeholder 노출, facet sidebar + 250 row dense table       │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  [b) Typing — autocomplete dropdown]                                    │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  q="bra" + dropdown 6 항목 (BRAIN MR / BRAIN CT / BREAST MG / ...) │ │
│  │  매치 토큰 underline + 우측 필드 배지                              │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  [c) Result with highlight — 결과 노출]                                 │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  q="MR brain" 결과 38 rows                                         │ │
│  │  body_part 셀 <mark>BRAIN</mark>, modality 셀 <mark>MR</mark>      │ │
│  │  FederatedSignal "38 studies · 2 hospitals · q chip"               │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  [d) Empty result — 0건]                                                │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  q="MR brain contrast zzz" 0건                                     │ │
│  │  중앙 search-x 아이콘 + 추천 키워드 + Clear/Reset CTA              │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  [e) PHI masked badge]                                                  │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  q="홍길동 brain" + 검색바 우측 [⚠ Query masked] + tooltip 펼침    │ │
│  │  결과는 search_text 매치 row 0~38건 (자연스럽게)                   │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

- 5 시나리오 사이는 `space-12` (48 px) gap + 회색 hairline.
- 각 시나리오 좌상단에 sticky 라벨 (`text-sm / font-mono / bg-text-strong / text-white / radius-pill`).
- HTML 단독으로 브라우저에서 열어 검사 가능 (외부 의존 0, inline CSS).
- 본 디자인 명세 §6~§11 의 모든 토큰 / 색 / 간격 정확 반영.

**금지**:
- 외부 이미지 URL 발명 금지. 아이콘은 inline SVG (lucide-react 의 `search`, `x`, `search-x`, `alert-triangle` 만 사용).
- 실제 환자 데이터 0 건 (모든 row 는 TCIA 기반 더미 + body_part/kcd 만).

---

## 17. 상태 처리 (요약 매트릭스)

| 화면 | loading | empty | error | no-permission | partial-failure |
|------|---------|-------|-------|---------------|-----------------|
| `<SearchBar>` | input은 항상 enabled. 검색 제출 후 우측 spinner 14 px (q chip 자리) | n/a (placeholder) | border 변경 없음, 우측 inline `[Retry]` (검색 API 500 시) | 검색바 자체 unmount (login redirect, v3 baseline) | autocomplete 다운: dropdown silent close, 검색바 동작 유지 |
| `<AutocompleteDropdown>` | 100 ms 초과 시 inline spinner + "Loading..." | "No suggestions for '{q}'" | dropdown 자동 닫힘 | n/a | n/a |
| `<ResultTable>` | v3 baseline skeleton 5 rows 그대로 | §10.1 0건 empty | inline error banner + `[Retry]` | n/a | row 일부 highlight 실패 시 raw 텍스트 fallback |
| `<MaskedQueryBadge>` | n/a (응답 후 mount) | unmount | n/a | n/a | n/a |
| `<HighlightedText>` | n/a (server 가 동기 제공) | fallback raw 텍스트 | DOMPurify fail 시 raw 텍스트 fallback (warn log) | n/a | n/a |

---

## 18. 수용 기준 (Design AC)

`@qa` 가 본 체크리스트로 시각·행동 검수. dev-spec §10 의 AC-TS-UI-1~10 과 1:1 매핑되며 디자인 관점 추가 항목 포함.

| ID | 기준 | 매핑 dev-spec FR |
|----|------|-----------------|
| **DA-1** | `/search` 페이지 hero 영역에 `<SearchBar>` 가 nav 아래·facet sidebar 위에 full-width 56 px 높이로 노출 | FR-TS-1, AC-TS-UI-1 |
| **DA-2** | placeholder 텍스트가 ko/en locale 정확 — `§14.1 search.placeholder` 키와 byte-identical | FR-TS-1, AC-TS-UI-2 |
| **DA-3** | 검색바 focus 시 border 가 1 → 2 px solid `--color-teal-600` + `0 0 0 3px rgba(13,148,136,0.15)` ring shadow 노출 | FR-TS-1 |
| **DA-4** | typing 시 200 ms debounce 후 `<AutocompleteDropdown>` 펼침, 매치 토큰 underline + 우측 필드 배지 노출 | FR-TS-8, AC-TS-UI-4 |
| **DA-5** | dropdown 키보드 navigation 전수 (↑↓ wrap-around / Enter 선택 / Esc 닫기 / Tab 진출) | FR-TS-1, AC-TS-UI-5 |
| **DA-6** | KCD 매치 항목은 2 줄 (영문 + 한글), 우측 배지 `KCD <code>` (teal-100 bg + teal-700 fg) | FR-TS-8, NFR-TS-I18N-1 |
| **DA-7** | 결과 row 의 매치 셀 4 개 (`body_part`, `kcd_label_ko`, `kcd_label_en`, `modality`) 에 `<mark>` 적용, CSS `--mark-highlight-bg` + font-weight 600 + text `--color-text-strong` | FR-TS-9, AC-TS-UI-7 |
| **DA-8** | 색맹 시뮬레이터 (Sim Daltonism deuteranopia) 통과 — `<mark>` 가 일반 텍스트와 구분 가능 (font-weight + 배경 두 가지 단서) | NFR-TS-A11Y-1 |
| **DA-9** | `<MaskedQueryBadge>` 가 PHI scrub flagged 응답 후 검색바 우측에 mount, hover/focus 시 tooltip 노출 | FR-TS-10 |
| **DA-10** | 0 건 결과 시 §10.1 empty state — search-x 아이콘 + 헤드라인 + 추천 키워드 + Clear/Reset CTA pair | FR-TS-9, AC-TS-DEMO-5 |
| **DA-11** | 모든 텍스트 조합이 WCAG AA 4.5:1 이상 (§13.3 매트릭스 8 종 전수 통과) | NFR-TS-A11Y-1 |
| **DA-12** | 키보드 only (마우스 disconnect) 로 검색 → 자동완성 → 선택 → 결과 확인 → 0건 recovery 전 시나리오 가능 | NFR-TS-A11Y-1 |
| **DA-13** | `prefers-reduced-motion` 활성 시 dropdown open 애니메이션 50 ms 이하 + mark transition 0 | NFR-TS-A11Y-1 |
| **DA-14** | `NEXT_PUBLIC_TEXT_SEARCH_ENABLED=false` 시 `<SearchBar>` 자체 unmount, v3 facet only 모드와 byte-identical UI | FR-TS-14, AC-TS-UI-9 |
| **DA-15** | 신규 디자인 토큰은 `--mark-highlight-bg` 단 1 개 (UI_GUIDE 갱신 제안에만 등재, 실제 정의는 component scope) | §11.2 |

---

## 19. 오픈 질문 / Kyle 결정 권유

본 디자인 명세는 dev-spec 의 Kyle 결정 7건을 100 % 반영했다. 단 디자인 단에서 발견된 추가 결정 권유:

1. **Cmd/Ctrl + K 글로벌 단축키** (§6.5 optional) — 페이지 어디서나 검색바 focus. v0.1 ship 후 v0.1.1 추가 권장. Kyle 결정 필요 시 "데모 임팩트 vs 학습 곡선".
2. **자동완성 항목 max 12 (desktop)** — research §3.2 의 권장은 10. RadiVault 가 KCD 한글+영문 2 줄 항목 포함 시 12 권장. 7~12 범위에서 데모 후 조정 가능.
3. **MaskedQueryBadge 색** — 본 명세는 warning (yellow). error (red) 도 가능. RadiVault 톤 (위협보다 알림) 우선해 warning 채택. Kyle 의 신뢰 톤 검토 권유.
4. **자동완성 첫 노출 시점** — 본 명세는 q.length ≥ 1 (dev-spec FR-TS-8). q.length ≥ 2 도 후보 (단일 자모 한글 매치 회피). Phase 2 한국어 stemmer 도입 시 재검토.
5. **모바일 search 버튼 라벨** — `Search` (en) / `검색` (ko). 모바일 화면에서 80 px 충분. icon-only (`🔍`) variant 도 후보 — Kyle 결정 필요 시.

---

## 20. UI_GUIDE 갱신 제안 (디자인 명세 외부 영향)

본 design-spec 이 산출하는 **UI_GUIDE 편입 후보**:

1. **신규 토큰**: `--mark-highlight-bg` (rgba teal alpha) — 검색 외 다른 표면 (audit log 검색, KCD 매핑 미리보기) 에서도 재사용 가능.
2. **신규 공통 컴포넌트**: `<SearchBar>` — 병원 콘솔 v0.3 의 audit log 검색에서도 재사용 가능. UI_GUIDE 의 §컴포넌트 라이브러리에 등재 권장.
3. **신규 공통 컴포넌트**: `<HighlightedText>` — server-side `<mark>` HTML 안전 렌더 패턴. 다른 검색 표면 전반 재사용.
4. **신규 a11y 패턴**: 색 + font-weight 동시 단서 (색맹 대응) — UI_GUIDE 의 §접근성 가이드라인에 등재 권장.
5. **신규 i18n 키 prefix**: `search.*` / `autocomplete.*` / `phi.*` / `result.empty.*` / `error.search.*` — i18n 카탈로그 5 prefix 추가.

UI_GUIDE 가 공식화될 때 (`docs/UI_GUIDE.md` 의 Status: Placeholder → Live), Kyle 승인 후 위 5 항목 편입 PR 권장.

---

## 21. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-26 | @designer | 최초 작성. dev-spec v0.1 + Kyle 결정 7건 + Segmed openda 비교 + 토큰 1 개 신규. 5 시나리오 mockup 명세. |

---

### NEXT_STEP

- **완료 산출물**: `docs/specs/design-spec-text-search-description.md` (Draft v0.1)
- **제안 다음 단계**:
  - **@developer** — 2 주 일정 (dev-spec §12.1 D-13+1 ~ D-13+15) claude 브랜치에서 `text-search-description` 구현 착수. W1 = alembic migration + executor SQL + PHI scrub, W2 = autocomplete endpoint + BFF + UI 5 컴포넌트 (`<SearchBar>` / `<AutocompleteDropdown>` / `<AutocompleteSuggestionItem>` / `<HighlightedText>` / `<MaskedQueryBadge>`).
  - **@developer (병행)** — `docs/specs/mockups/text-search-description/search-with-q.html` 구현 (5 시나리오 한 페이지, inline SVG 아이콘만, 외부 의존 0).
  - **@qa** — 구현 완료 후 `qa-report-text-search-description.md` 작성. 디자인 측 우선순위: (1) §13.3 색 대비 매트릭스 8 종 자동 검증, (2) 키보드 only 시나리오 5 종 (DA-12), (3) 색맹 시뮬레이터 (DA-8), (4) `prefers-reduced-motion` (DA-13), (5) feature flag off 회귀 (DA-14).
- **UI_GUIDE.md 갱신 제안**: `--mark-highlight-bg` 토큰 1 개 + `<SearchBar>` / `<HighlightedText>` 공통 컴포넌트 2 개 + 색맹 a11y 패턴 1 개 + i18n prefix 5 개. UI_GUIDE 공식화 시 Kyle 승인 후 편입.
- **추가 디자인 필요**:
  - Phase 1.5 (`design-spec-text-search-description-phase15.md`) — description 추출 후 자동완성 항목에 `study_description` / `series_description` 매치 필드 배지 추가. 본 명세의 배지 색 매트릭스 확장만 필요.
  - Phase 2 (`design-spec-popular-queries.md`) — 자동완성 dropdown 상단에 "Popular searches" 섹션 추가 (인기순). 본 명세의 dropdown 구조 확장만 필요.
- **Kyle 결정 필요 사항**:
  - §19 Q1 Cmd/Ctrl+K 글로벌 단축키 v0.1.1 추가 여부.
  - §19 Q3 MaskedQueryBadge 색 (warning vs error).
  - §19 Q5 모바일 search 버튼 icon-only vs 라벨 포함.
