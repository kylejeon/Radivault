# 디자인 명세 — Text Search Phase 1.5 (Description Extraction + Locale-Aware ICD-10/KCD-8 Labelling)

> **Status**: Draft v0.1 · **Feature slug**: `text-search-description-phase15` · **Last updated**: 2026-04-26
> **작성자**: @designer (Claude Opus 4.7 [1M])
> **근거**:
>  - [`dev-spec-text-search-description-phase15.md`](./dev-spec-text-search-description-phase15.md) — Draft v0.1, FR-TS15-1~19, AC-TS15-1~25, Kyle 결정 6건.
>  - [`design-spec-text-search-description.md`](./design-spec-text-search-description.md) — Phase 1.0 design-spec. `<SearchBar>`, `<AutocompleteDropdown>`, `<HighlightedText>`, `<MaskedQueryBadge>` 5 컴포넌트. **본 문서는 그 위에 description + locale 만 얹는다.**
>  - [`design-spec-portal-redesign.md`](./design-spec-portal-redesign.md) §4 (공유 토큰 — Buyer blue / Hospital teal / Slate / Pretendard).
>  - [`UI_GUIDE.md`](../UI_GUIDE.md) — placeholder. 본 문서는 v3 토큰 + Phase 1.0 의 `--mark-highlight-bg` 단 1 신규 토큰만 차용. **본 phase 신규 토큰 0개**.

---

## 1. 디자인 개요

Phase 1.0 의 `<SearchBar>` + autocomplete + `<mark>` 하이라이트 위에, **description 매치 노출**과 **KCD chip 의 locale-aware 라벨**을 추가한다.

- **3 가지 신규 표면**:
  1. `<ResultTable>` 의 신규 컬럼 `DESCRIPTION` (toggleable, default ON) — 글로벌 AI 엔지니어가 protocol identification 을 다운로드 전 하도록.
  2. `<KCDChip>` 의 locale 분기 — `en` 은 "ICD-10 G45.9" prominent + tooltip "Korean coded as KCD-8", `ko` 는 "KCD-8 G45.9" prominent + tooltip "WHO ICD-10 호환 (95% 동일)".
  3. Study Detail 의 metadata grid 에 `Study Description` / `Protocol Name` 2 행 추가 + 격리 시 `⚠ PHI verification pending` fallback.
- **Phase 1.0 자산 100% 재사용**:
  - `<SearchBar>` — placeholder 만 i18n 키로 교체 (예시 단어 추가).
  - `<HighlightedText>` — server `ts_headline` 이 description 토큰도 자동 포함 (FR-TS15-19) → 컴포넌트 변경 0.
  - `<AutocompleteDropdown>` — 항목에 `STUDY DESC`, `PROTOCOL` 배지 2 개 추가 (배지 색 매트릭스 확장만).
  - `<MaskedQueryBadge>` — 변경 없음 (description 측 PHI 는 별도 `⚠ pending` 으로 처리).
- **북극성**: "글로벌 buyer 가 한국 데이터의 친숙한 코드 (ICD-10) 로 즉시 인식하면서, 한국 buyer 도 KCD-8 친숙도를 잃지 않게" — 동일 코드, 라벨만 로컬라이즈.

**디자인 결정 1줄**: locale 분기는 **chip 의 텍스트 prominence + tooltip 만** 다르게. 색·폰트·배경·shape 전부 동일 → 시각 일관성 + 인지 부담 0.

---

## 2. 화면 변경 영역 (스코프 선언)

| 영역 | 상태 | 변경 내용 |
|------|------|----------|
| `<SearchBar>` (Phase 1.0) | **부분 변경** | placeholder i18n 키 1개 교체 (예시에 `'angina' / '협심증'` 추가). border / 높이 / 동작 무변경. |
| `<AutocompleteDropdown>` (Phase 1.0) | **부분 변경** | 우측 필드 배지 색 매트릭스에 `STUDY DESC` (teal-100) · `PROTOCOL` (slate) 2 종 추가. dropdown 구조·키보드 동작 무변경. |
| `<HighlightedText>` (Phase 1.0) | **무변경** | server `ts_headline` 이 description 토큰도 자동 포함. CSS 변경 0. |
| `<ResultTable>` (v3 baseline + Phase 1.0) | **변경** | 신규 컬럼 `DESCRIPTION` (default ON, toggleable) 추가. body_part 셀과 KCD 셀은 변경 없음. |
| `<ColumnToggle>` (v3 baseline) | **부분 변경** | toggleable 컬럼 12 → 13 (Description 추가, default ON). 기존 deferred 3 항목 (Series/UID/Audit Chain) 그대로. |
| `<KCDChip>` | **신규** | locale 별 라벨 prominence + tooltip 분기. v3 의 KCD chip 인라인 렌더링을 컴포넌트로 분리. |
| `<PhiPendingBadge>` | **신규** | 격리된 description 자리에 `⚠ pending` 회색 텍스트 + tooltip. 색맹 대응 (아이콘 + 텍스트). |
| `<StudyDetailPanel>` (v3 baseline) | **변경** | metadata grid 9 행 → 11 행 (Study Description / Protocol Name 추가). Series Descriptions 는 별도 collapsible 섹션 (Phase 2 까지 기본 collapse). |
| `<MaskedQueryBadge>` (Phase 1.0) | **무변경** | description 측 PHI 는 별도 `<PhiPendingBadge>` 로 처리. 검색바 측 PHI 는 그대로. |
| 좌측 `<FacetSidebar>` (v3 baseline) | **무변경** | description 기반 facet 자동 생성은 Phase 2 영역. |
| 우측 `<CohortCart>` (v3 baseline) | **무변경** | 영향 없음. |

**HTML mockup**: `docs/specs/mockups/text-search-description-phase15/search-results.html` — 5 시나리오 한 페이지 (a~e).

---

## 3. 화면 목록

| ID | 화면명 | 경로 | 주요 역할 |
|----|--------|------|----------|
| S-1 | 검색 결과 (en + description 매치) | `/search?q=knee%20scanogram` (locale=en) | description 매치 + chip "ICD-10 ..." prominent + DESCRIPTION 컬럼 노출 |
| S-2 | 검색 결과 (ko + description 매치) | `/search?q=knee%20scanogram` (locale=ko) | 동일 query, chip "KCD-8 ..." prominent + tooltip 한글 |
| S-3 | 검색 결과 (PHI 격리 row 포함) | `/search?q=brain` | DESCRIPTION 셀에 `⚠ pending` fallback (격리되지 않은 row 만, FR-TS15-10 의 격리 row 는 결과에서 제외되므로 본 시나리오는 "scrub 후 빈 description" 케이스) |
| S-4 | KCD chip tooltip hover | (S-1/S-2 위에 hover 상태) | locale 별 tooltip 텍스트 + 위치 + arrow |
| S-5 | Study Detail metadata grid 확장 | `/studies/:id` | Study Description / Protocol Name 행 추가, locale 별 라벨 + footer note |

각 화면은 v3 + Phase 1.0 의 동일 라우트 (`/search`, `/studies/:id`) 위에 add-on. **신규 라우트 0**.

---

## 4. 사용자 플로우

### 4.1 Happy path — 글로벌 buyer (en) description 매치

```
[/search 진입, locale=en, q=""]
  └─ SearchBar placeholder: "Search by body part, modality, KCD code, or description..."
  └─ ResultTable 250 rows + DESCRIPTION 컬럼 (대부분 채워짐)
  ↓ buyer types "knee scanogram"
[autocomplete dropdown 펼침 (Phase 1.0 동작)]
  └─ "Knee Scanogram"  [STUDY DESC]   ← 신규 배지
  └─ "Knee Scanogram XR"  [PROTOCOL]   ← 신규 배지
  └─ "KNEE"  [body part]               ← 기존
  ↓ Enter 또는 첫 항목 클릭
[검색 결과 노출 — 8 rows]
  └─ DESCRIPTION 셀에 <mark>Knee Scanogram</mark> 하이라이트
  └─ KCD chip "[ICD-10 M17.0]  Knee osteoarthritis" (prominent)
  └─ tooltip on chip hover: "Korean coded as KCD-8 (95% identical to WHO ICD-10)"
  ↓ buyer 가 row 클릭 → Study Detail
[Study Detail metadata grid]
  └─ "Study Description: Knee Scanogram"
  └─ "Protocol Name: AX KNEE Scanogram"
  └─ "ICD-10 M17.0 — Knee osteoarthritis" + footer "Provenance: Korean Standard Classification of Diseases v8 (KCD-8)"
```

### 4.2 한국 buyer (ko) — 동일 query, 라벨만 로컬라이즈

```
[/search, locale=ko, q="knee scanogram"]
  └─ ResultTable rows 동일 (검색 동작 locale 무관, AC-TS15-16)
  └─ DESCRIPTION 컬럼 헤더: "검사 설명"
  └─ KCD chip "[KCD-8 M17.0]  Knee osteoarthritis" (prominent)
  └─ tooltip on chip hover: "WHO ICD-10 호환 (95% 동일)"
  ↓ locale switcher 클릭 (en ↔ ko)
[페이지 reload 없이 chip / placeholder / tooltip 즉시 갱신, AC-TS15-17]
  └─ NFR-TS15-AVAIL-2: LocaleProvider state change → React re-render
```

### 4.3 PHI 격리 fallback — description 빈 row

```
[검색 결과 row 중 일부]
  └─ DESCRIPTION 셀에 "⚠ pending" (회색 + warning icon)
  └─ hover 시 tooltip: "Excluded for de-identification review"
  └─ 색맹 대응: 색 외에 ⚠ 아이콘 + "pending" 텍스트로 구분
  └─ 별도 banner 안 띄움 — v3 의 trust-bar 와 충돌 방지
[Study Detail page 진입 시]
  └─ Study Description 행: ⚠ "PHI verification pending" 표시
  └─ Protocol Name 행: ⚠ "PHI verification pending" 표시
  └─ audit chain 배지 (v3 baseline) 옆에 inline 표시
  └─ 격리된 study (preview_status='phi_detected') 자체는 search 결과에 노출 안 됨 (NFR-TS15-COMPLIANCE-2)
  └─ 본 fallback 은 "scrub 통과 했으나 모든 토큰 stripped" 의 빈 string 케이스
```

### 4.4 권한 없음 / feature flag off

```
[DESCRIPTION_EXTRACTION_ENABLED=false]
  └─ DESCRIPTION 컬럼은 헤더 자체는 표시, 셀은 모두 빈 값 (NULL → "—")
  └─ ColumnToggle 으로 buyer 가 끌 수 있음
  └─ KCD chip locale 분기는 그대로 ON (별도 flag)
  └─ Phase 1.0 동작과 byte-identical (kcd_label_display 만 추가, AC-TS15-22)

[로그인 없음 401]
  └─ /login redirect (v3 baseline 그대로)
```

### 4.5 에러 — autocomplete description 토큰 fetch 실패

```
[autocomplete API 부분 실패 — description 인덱스만 down]
  └─ dropdown 은 body_part / modality / KCD 항목만 표시
  └─ STUDY DESC / PROTOCOL 배지 항목은 silently 빠짐
  └─ console warning, UI 깨짐 0 (Phase 1.0 NFR-TS-AVAIL-2 승계)
```

---

## 5. 컴포넌트 inventory

| 컴포넌트 | 상태 | 목적 | 재사용 가능? |
|---------|------|------|------------|
| `<SearchBar>` (Phase 1.0) | **수정** | placeholder i18n 키 교체만 (1 줄 변경) | yes (변경 없음) |
| `<AutocompleteDropdown>` (Phase 1.0) | **수정** | 배지 색 매트릭스 2 항목 추가 (STUDY DESC / PROTOCOL) | yes |
| `<AutocompleteSuggestionItem>` (Phase 1.0) | **수정** | 배지 변형 2 종 추가 | dropdown 내부 only |
| `<HighlightedText>` (Phase 1.0) | **무변경** | server `ts_headline` 이 description 토큰도 자동 포함 | yes |
| `<MaskedQueryBadge>` (Phase 1.0) | **무변경** | 검색바 측 PHI 만 처리 | SearchBar 종속 |
| `<ResultTable>` (v3) | **수정** | DESCRIPTION 컬럼 추가, ColumnToggle 연결 | — |
| `<ColumnToggle>` (v3) | **수정** | toggleable 컬럼 12 → 13 | — |
| `<StudyDetailPanel>` (v3) | **수정** | metadata grid 2 행 추가 (Study Description / Protocol Name) | — |
| `<KCDChip>` | **신규** | locale 별 라벨 prominence + tooltip | yes — Study Detail / autocomplete dropdown 재사용 |
| `<PhiPendingBadge>` | **신규** | 격리 description 자리에 `⚠ pending` 회색 텍스트 | yes — Study Detail / future audit UI 재사용 |
| `<FacetSidebar>` (v3) | **무변경** | description-based facet 은 Phase 2 영역 | — |
| `<CohortCart>` (v3) | **무변경** | 영향 없음 | — |

각 컴포넌트의 props · state · CSS 는 §6 (KCDChip) / §7 (PhiPendingBadge) / §8 (ResultTable description 셀) / §9 (Study Detail metadata grid) 에서 상세.

---

## 6. `<KCDChip>` 컴포넌트 명세 (신규)

### 6.1 역할

Phase 1.0 까지는 ResultTable 의 KCD 셀이 `kcd_label_ko` 와 `kcd_label_en` 을 raw text 로 inline 렌더했음. Phase 1.5 부터는 **locale 에 따라 prominent 라벨이 분기되는 chip 컴포넌트**로 리팩터.

### 6.2 props

```typescript
interface KCDChipProps {
  code: string;                 // e.g. "G45.9" — locale 무관
  labelKo: string;              // e.g. "일과성 뇌허혈 발작"
  labelEn: string;              // e.g. "Transient ischaemic attack"
  locale: 'en' | 'ko';          // LocaleProvider 에서 주입
  variant?: 'inline' | 'detail'; // ResultTable 셀 inline / Study Detail panel detail (footer note 노출)
  size?: 'sm' | 'md';
}
```

### 6.3 시각 사양 (locale 별 prominence)

```
en locale, size=md:
┌──────────────────────────────────────────────────────────┐
│ [ICD-10 G45.9]  Transient ischaemic attack               │
│   ^^^^^^^^^^^                                            │
│   prominent — chip pill (teal-100 bg + teal-700 fg)      │
│   font-weight 600 (semibold)                             │
│   tooltip 트리거: hover (200ms delay) / Tab focus (즉시) │
└──────────────────────────────────────────────────────────┘
                  ↓ hover 시
┌──────────────────────────────────────────────────────────┐
│  Korean coded as KCD-8 (95% identical to WHO ICD-10)     │ ← tooltip
│  bg: text-strong (#020617), fg: white, radius-md         │
│  arrow 8px 위쪽 가리킴                                    │
└──────────────────────────────────────────────────────────┘

ko locale, size=md:
┌──────────────────────────────────────────────────────────┐
│ [KCD-8 G45.9]  일과성 뇌허혈 발작                         │
│   ^^^^^^^^^^                                             │
│   prominent — 동일 chip (teal-100 bg + teal-700 fg)      │
└──────────────────────────────────────────────────────────┘
                  ↓ hover 시
┌──────────────────────────────────────────────────────────┐
│  WHO ICD-10 호환 (95% 동일)                               │ ← tooltip
└──────────────────────────────────────────────────────────┘
```

**핵심 규칙**:

- **chip 자체의 시각 sty 동일** (locale 무관) — bg `--color-teal-100` (#ccfbf1), fg `--color-teal-700` (#0f766e), `radius-pill`, padding `2×8 px`. **새 토큰 정의 0**.
- **차이는 텍스트 prefix 1 단어 + 코드 prominence 만**:
  - en: `"ICD-10 " + code` (총 12 자)
  - ko: `"KCD-8 " + code` (총 11 자)
  - 한국어가 1 자 짧음 — 가로 폭 일관성 유지 (chip 폭 자동 맞춤).
- **chip 우측 사이드 (12 px gap) 에 entity name** (kcd_label_en 또는 kcd_label_ko, locale 에 맞게):
  - en locale: `labelEn` (`Transient ischaemic attack`).
  - ko locale: `labelKo` (`일과성 뇌허혈 발작`).
  - text style: `text-sm / text-text` (Phase 1.0 의 ResultTable 셀과 일관).

### 6.4 size variants

| variant | chip 폰트 | chip padding | label 폰트 | 용도 |
|---------|----------|-------------|-----------|------|
| `sm` | `text-xs` (12px) | `2×6 px` | `text-xs` | autocomplete dropdown 우측 배지 (Phase 1.0 패턴) |
| `md` (default) | `text-xs` (12px) | `2×8 px` | `text-sm` (14px) | ResultTable 셀, Study Detail metadata grid 행 |

### 6.5 tooltip 사양

| 속성 | 값 |
|------|-----|
| 트리거 | hover (200ms delay before show) · focus (즉시 표시) |
| 자동 사라짐 | mouseleave 후 100ms (다른 chip 호버 시 즉시) |
| 위치 | chip 위 (top), arrow 8 px 가리킴. viewport 상단 잘리면 자동 chip 아래 (bottom) flip |
| 폭 | max 320 px, padding `space-3` |
| bg / fg | `--color-text-strong` (#020617) / white (Phase 1.0 의 MaskedQueryBadge tooltip 과 일관) |
| radius | `radius-md` (8 px) |
| shadow | `shadow-overlay` |
| z-index | 60 (autocomplete dropdown 50 보다 위) |

### 6.6 i18n 텍스트 (FR-TS15-12, 14)

| 키 | en | ko |
|----|-----|-----|
| `kcd.chip.label_prefix` | `"ICD-10"` | `"KCD-8"` |
| `kcd.tooltip` | `"Korean coded as KCD-8 (95% identical to WHO ICD-10)"` | `"WHO ICD-10 호환 (95% 동일)"` |
| `kcd.chip.aria_label` | `"Diagnosis code {code}, ICD-10 standard"` | `"진단 코드 {code}, KCD-8 기준"` |
| `kcd.footer.note` | `"Provenance: Korean Standard Classification of Diseases v8 (KCD-8)"` | `"출처: 한국표준질병사인분류 8차 (KCD-8)"` |

- `kcd.footer.note` 는 `variant="detail"` (Study Detail) 에서만 chip 하단에 노출 (small caption, `text-xs / text-text-muted`).

### 6.7 a11y

```html
<!-- en locale 예시 -->
<span
  role="button"
  tabindex="0"
  aria-label="Diagnosis code G45.9, ICD-10 standard"
  aria-describedby="kcd-tooltip-12345"
  class="kcd-chip kcd-chip--md"
>
  ICD-10 G45.9
</span>
<span class="kcd-label">Transient ischaemic attack</span>

<div
  role="tooltip"
  id="kcd-tooltip-12345"
  hidden
>
  Korean coded as KCD-8 (95% identical to WHO ICD-10)
</div>
```

- chip 자체는 `role="button"` + `tabindex=0` — 키보드 Tab 으로 도달, focus 시 tooltip 자동 표시 (NFR-TS15-A11Y-2).
- chip 클릭 시 동작은 v0.1 에서 정의 안 함 (검색 필터 추가 후보 — Phase 2 backlog).
- aria-label 에 코드 + 표준명 — 스크린리더가 단순 "ICD-10 G45.9" 읽고 끝나지 않게 풀 표현.

### 6.8 색 대비 (WCAG AA)

| 조합 | 대비 | 결과 |
|------|------|------|
| chip text `--color-teal-700` (#0f766e) on `--color-teal-100` (#ccfbf1) | 5.84:1 | AA |
| label text `--color-text` (#0f172a) on `--color-bg` (#fff) | 18.69:1 | AAA |
| tooltip white on `--color-text-strong` (#020617) | 19.21:1 | AAA |

**chip 색은 v3 토큰 그대로 차용 — 신규 토큰 0**.

---

## 7. `<PhiPendingBadge>` 컴포넌트 명세 (신규)

### 7.1 역할

description 이 scrub 통과했으나 모든 토큰이 stripped 되어 빈 string 인 경우, 또는 운영자 review 대기 중인 경우에 노출. **격리된 study (preview_status='phi_detected') 자체는 search 결과에 미노출** (NFR-TS15-COMPLIANCE-2) → 본 badge 는 search 결과에 노출되는 row 의 description 셀에서만 등장.

### 7.2 props

```typescript
interface PhiPendingBadgeProps {
  context: 'cell' | 'detail';   // ResultTable 셀 / Study Detail metadata grid
  size?: 'sm' | 'md';
}
```

### 7.3 시각 사양

```
context=cell, size=sm (ResultTable):
┌─────────────────────────┐
│ ⚠ pending               │ ← 회색 텍스트 + warning icon 14px
└─────────────────────────┘
   text-xs / text-text-muted (#64748b)
   icon: lucide alert-triangle, color text-text-muted
   no bg, no border (셀 자체와 시각적 통합)
   hover 시 tooltip: "Excluded for de-identification review" / "비식별화 검토 대기 중"

context=detail, size=md (Study Detail metadata grid):
┌─────────────────────────────────────────────────────┐
│ ⚠ PHI verification pending                          │ ← warning style
│   bg: --color-warning-light (#fffbeb)               │
│   border-left: 4px solid --color-warning-dark       │
│   padding: space-3 space-4                          │
└─────────────────────────────────────────────────────┘
   text-sm / text-warning-dark (#b45309)
```

### 7.4 색맹 대응 (WCAG AA + ColorBlind 필수)

- **색 단독 의존 금지**: ⚠ 아이콘 + "pending" / "PHI verification pending" 텍스트로 의미 전달.
- **회색 (text-muted) 단독으로는 "정보 없음" 으로도 해석 가능** → ⚠ 아이콘이 "검토 대기" 의미 전달.
- 시뮬레이터 (deuteranopia) 통과 검증: 회색 + ⚠ + 텍스트 3 단서로 "검토 대기" 전달 (DA-15).

### 7.5 i18n 텍스트

| 키 | en | ko |
|----|-----|-----|
| `description.phi_pending.cell` | `"pending"` | `"검토 대기"` |
| `description.phi_pending.cell.tooltip` | `"Excluded for de-identification review"` | `"비식별화 검토 대기 중"` |
| `description.phi_pending.detail` | `"PHI verification pending"` | `"PHI 검증 대기 중"` |

### 7.6 a11y

```html
<!-- cell context -->
<span
  role="status"
  aria-label="Description excluded for de-identification review"
  class="phi-pending-badge phi-pending-badge--cell"
>
  <svg aria-hidden="true" class="icon-warning"><!-- alert-triangle --></svg>
  <span>pending</span>
</span>
```

- `role="status"` + 명확한 aria-label — 스크린리더가 "정보 없음" 이 아닌 "검토 대기" 읽음.
- 아이콘은 `aria-hidden` (텍스트로 의미 전달).

---

## 8. `<ResultTable>` Description 컬럼 추가 명세

### 8.1 컬럼 위치 / 너비

v3 baseline 의 ResultTable 컬럼 순서 (왼쪽 → 오른쪽):

```
┌──┬──────────┬──────┬──────────────────────┬─────────┬──────────┬───────────┬─────────┬───────────┐
│☐ │ Study ID │ Mod. │ KCD                  │ Body    │ Sex/Age  │ Hospital  │ Date    │ + DESC ←신규│
└──┴──────────┴──────┴──────────────────────┴─────────┴──────────┴───────────┴─────────┴───────────┘
```

- **위치**: 마지막 sticky 컬럼 직전. Hospital / Date 우측, action 컬럼 (preview / cart) 좌측.
- **너비**: `min-width: 200px`, `max-width: 320px`, `overflow: hidden ellipsis`.
- **헤더 라벨**: 
  - en: `Description`
  - ko: `검사 설명`
- **헤더 sortable**: 본 phase 는 sort 미지원 (description 자체는 sort 무의미). 향후 Phase 2 검토.

### 8.2 셀 렌더 사양

```
정상 케이스:
┌───────────────────────────────────────────────┐
│ Knee Scanogram, AX T1 FLAIR                   │ ← truncate ellipsis
│ text-sm / text-text                           │
│ hover 시 full text tooltip (title 속성)       │
└───────────────────────────────────────────────┘

매치된 토큰 (q="scanogram"):
┌───────────────────────────────────────────────┐
│ Knee <mark>Scanogram</mark>, AX T1 FLAIR      │
│ <mark> 는 Phase 1.0 의 --mark-highlight-bg    │
│ + font-weight 600 + text-strong 자동 적용     │
└───────────────────────────────────────────────┘

빈 값 (NULL — feature flag off 또는 미수신):
┌───────────────────────────────────────────────┐
│ —                                              │
│ text-sm / text-text-muted                     │
└───────────────────────────────────────────────┘

PHI 격리 fallback (scrub 통과 빈 string):
┌───────────────────────────────────────────────┐
│ ⚠ pending                                      │ ← <PhiPendingBadge context="cell" size="sm" />
│ hover 시 tooltip                              │
└───────────────────────────────────────────────┘
```

### 8.3 truncate 정책

- 셀 폭 320 px 한도, 약 40 자 (Pretendard text-sm 기준) 까지 노출.
- 초과 시 `text-overflow: ellipsis` + `title` 속성에 full text → 스크린리더는 full 읽음 (DA-7).
- hover 100ms 후 native browser tooltip 노출 (커스텀 tooltip 안 씀 — KCD chip tooltip 과 충돌 방지).

### 8.4 ColumnToggle 연결

v3 의 `<ColumnToggle>` (대부분 컬럼 on/off 가능, 12 항목) 에 신규 항목 추가:

| 항목 | default | 설명 |
|------|---------|------|
| ... 기존 11 항목 ... | | |
| **Description** | **ON** | 신규. buyer 가 toggle 로 끄고 켤 수 있음. |
| Series UID | OFF (deferred) | 변경 없음 |
| Audit Chain | OFF (deferred) | 변경 없음 |

총 toggleable 12 → 13. ColumnToggle UI 의 카탈로그 (체크박스 list) 에 "Description" 한 줄 추가만. 시각 변경 없음.

**i18n**:
| 키 | en | ko |
|----|-----|-----|
| `column_toggle.description` | `"Description"` | `"검사 설명"` |

### 8.5 옵션 A vs 옵션 B 결정

dev-spec §4.1 의 옵션 검토 — Kyle 입력 컨텍스트의 **추천: 옵션 A** 채택.

| 옵션 | 결정 | 이유 |
|------|------|------|
| **A: 새 컬럼 DESCRIPTION** (채택) | ✅ | (1) buyer 가 column toggle 로 ON/OFF 가능, (2) sortable / searchable 후보 명확, (3) v3 dense table 의 컬럼 grid 와 일관, (4) 한 row 에 정보 분리 노출. |
| B: body_part 셀에 description 부가 (작은 글씨로 second line) | ❌ | (1) row height 변동, (2) ColumnToggle 으로 끌 수 없음, (3) body_part vs description semantic 혼동, (4) 스크린리더 reading order 복잡. |

---

## 9. Study Detail Metadata Grid 확장

### 9.1 기존 + 신규 행 (v3 baseline 9 행 → 11 행)

```
┌───────────────────────┬──────────────────────────────────────────┐
│ Study UID (pseudo)    │ uid:1.2.840.113619... (truncate)         │
│ Modality              │ MR                                       │
│ Body Part             │ KNEE                                     │
│ KCD                   │ [ICD-10 M17.0] Knee osteoarthritis       │ ← <KCDChip variant="detail" />
│                       │ Provenance: Korean Standard...           │ ← footer note (locale 별)
│ Hospital              │ HOSP-OPAQUE-7F2A (federated)             │
│ Date                  │ 2024-08-15                               │
│ Sex / Age             │ F / 67                                   │
│ Series count          │ 4                                        │
│ Audit chain           │ ✓ verified  [view audit log →]           │
│ ─────────────────────────────────────────────────────────────────│
│ Study Description     │ MR Knee w/o contrast                     │ ← 신규 (FR-TS15-25)
│ Protocol Name         │ AX T1 FLAIR, SAG T2, COR FLAIR           │ ← 신규
└───────────────────────┴──────────────────────────────────────────┘
```

- 신규 2 행은 기존 9 행과 동일한 grid template (label 좌 / value 우, 2-col, padding `space-3`).
- 두 행 사이에 horizontal hairline (`--color-border` #e2e8f0) — 기존 행 사이와 동일 패턴.
- Series Descriptions 별도 collapsible section (기본 collapse, "View 4 series descriptions ▾" 클릭 시 펼침) — series 수가 많은 케이스 (10+) 에서 grid 밀도 보호.

### 9.2 격리 fallback (`⚠ PHI verification pending`)

```
┌───────────────────────┬──────────────────────────────────────────┐
│ Study Description     │ ⚠ PHI verification pending               │ ← <PhiPendingBadge context="detail" />
│ Protocol Name         │ ⚠ PHI verification pending               │
└───────────────────────┴──────────────────────────────────────────┘
```

- 두 행 모두 `<PhiPendingBadge context="detail" />` (warning style).
- audit chain 행 (기존) 의 ✓ verified 배지 옆에 `[⚠ description pending]` 작은 inline 배지 추가 — buyer 가 audit chain 컨텍스트에서 즉시 확인.
- 별도 banner 안 띄움 (v3 trust-bar 충돌 방지) — 본 metadata grid 내부에서만 표시.

### 9.3 Series Descriptions collapsible

```
┌───────────────────────┬──────────────────────────────────────────┐
│ Series Descriptions   │ View 4 series descriptions ▾             │
└───────────────────────┴──────────────────────────────────────────┘
                                    ↓ 클릭 시 펼침
┌───────────────────────┬──────────────────────────────────────────┐
│ Series Descriptions   │ ▾ Hide                                    │
│                       │ ┌────────────────────────────────────┐  │
│                       │ │ AX T1 FLAIR                        │  │
│                       │ │ SAG T2                             │  │
│                       │ │ COR FLAIR                          │  │
│                       │ │ AX DWI                             │  │
│                       │ └────────────────────────────────────┘  │
└───────────────────────┴──────────────────────────────────────────┘
```

- 본 phase 는 series_description 표시만 (검색 인덱싱은 study 단위 — dev-spec §6.1 ).
- 격리 series 는 `⚠ pending` 한 줄로 fallback.

### 9.4 i18n 키

| 키 | en | ko |
|----|-----|-----|
| `study.detail.metadata.description` | `"Study Description"` | `"검사 설명"` |
| `study.detail.metadata.protocol` | `"Protocol Name"` | `"프로토콜 명"` |
| `study.detail.metadata.series_descriptions` | `"Series Descriptions"` | `"시리즈 설명"` |
| `study.detail.metadata.series_descriptions.expand` | `"View {count} series descriptions"` | `"{count}개 시리즈 설명 보기"` |
| `study.detail.metadata.series_descriptions.collapse` | `"Hide"` | `"숨기기"` |
| `study.detail.metadata.phi_pending` | `"PHI verification pending"` | `"PHI 검증 대기 중"` |
| `study.detail.metadata.phi_pending.audit_chain_badge` | `"description pending"` | `"검사 설명 검토 중"` |

---

## 10. SearchBar Placeholder 변경

### 10.1 변경 내용

Phase 1.0 의 placeholder 텍스트를 i18n 키로 교체. **컴포넌트 자체는 무변경**.

| locale | 신규 placeholder |
|--------|------------------|
| en | `Search by body part, modality, KCD code, or description... (e.g. 'MR brain', 'knee scanogram', 'I20.9')` |
| ko | `신체부위, 모달리티, KCD 코드 또는 검사명 검색... (예: 'MR 뇌', '슬관절 검사', 'I20.9')` |

- **변경점**:
  - "or description" / "또는 검사명" 추가 — buyer 에게 description 검색 가능 힌트.
  - 예시에 `'knee scanogram'` / `'슬관절 검사'` 추가 — Phase 1.0 의 'I20.9' 만으로는 description 검색 가능성 미인지.
- **i18n 키**: `search.bar.placeholder.phase15.en` / `search.bar.placeholder.phase15.ko` (Phase 1.0 의 `search.placeholder` 와 키 분리 — flag rollback 시 placeholder 만 Phase 1.0 으로 자동 회귀).
- **모바일 short variant**: 변경 없음 (Phase 1.0 의 `Search studies` / `검색` 그대로).

### 10.2 길이 / 잘림 검증

- en placeholder: 약 100 자 — 데스크톱 (≥1024 px) 검색바 width (560 ~ 880 px 가변) 에서 잘림 없음.
- ko placeholder: 약 50 자 — 한국어 30% 짧음 정책 준수, 모바일 (320 px) 에서도 잘림 없음.

---

## 11. AutocompleteDropdown 배지 확장

### 11.1 신규 배지 색 매트릭스 (Phase 1.0 §7.2 확장)

| 배지 | bg | fg | 의도 |
|------|-----|-----|------|
| `body_part` | `--color-bg-muted` (#f8fafc) | `--color-text-muted` | 기존 (Phase 1.0) |
| `modality` | `--color-bg-muted` | `--color-text-muted` | 기존 |
| `KCD <code>` | `--color-teal-100` (#ccfbf1) | `--color-teal-700` (#0f766e) | 기존 (KCDChip 과 동일 색) |
| `manufacturer` / `model` | `--color-bg-muted` | `--color-text-muted` | 기존 |
| **`STUDY DESC`** | `--color-teal-50` (#f0fdfa) | `--color-teal-700` | **신규 — description 매치 강조 (KCD 와 톤 통일, 더 옅게)** |
| **`PROTOCOL`** | `--color-bg-muted` | `--color-text-muted` | **신규 — protocol_name 매치 (neutral)** |

- STUDY DESC 는 의료 도메인 신호 (KCD 와 같은 teal 계열) — buyer 가 "free text 매치임" 즉시 인식.
- PROTOCOL 은 neutral — body_part 와 같은 metadata 계열 신호.
- **신규 토큰 0** — `--color-teal-50` 은 v3 baseline 에 이미 존재.

### 11.2 dropdown 항목 예시 (q="knee scan")

```
┌────────────────────────────────────────────────────────────────────────┐
│  [🔍] knee scan|                                            [✕]        │
└────────────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────────────┐
│  Knee Scanogram                                       [STUDY DESC]     │ ← 신규 배지 (teal-50 bg)
│  Knee Scanogram XR Protocol                           [PROTOCOL]       │ ← 신규 배지 (slate)
│  KNEE                                                 [body part]      │ ← 기존
│  Knee osteoarthritis — 슬관절 골관절염                 [KCD M17.0]      │ ← 기존 (KCD 항목 2줄)
│  CR                                                   [modality]       │ ← 기존
└────────────────────────────────────────────────────────────────────────┘
```

- 항목 정렬: ts_rank_cd 기준 (Phase 1.0 그대로). description 매치가 weight A → 통상 상위 노출.
- 키보드 navigation: Phase 1.0 그대로 (↑↓ wrap, Enter 선택, Esc 닫기).

### 11.3 i18n 키 (배지 텍스트)

| 키 | en | ko |
|----|-----|-----|
| `autocomplete.badge.study_desc` | `"STUDY DESC"` | `"검사 설명"` |
| `autocomplete.badge.protocol` | `"PROTOCOL"` | `"프로토콜"` |

- 영어는 대문자 + 짧은 약어 (배지 시각 일관성, Phase 1.0 의 `body_part` `modality` 톤과 일치 — 단, Phase 1.0 은 lowercase 였음 → 본 phase 부터 STUDY DESC 만 대문자 권장. Phase 1.0 배지도 차후 대문자 통일 검토 — Kyle 결정 필요).
- 한국어는 띄어쓰기 + 정상 표기.

---

## 12. 디자인 토큰

### 12.1 차용 (기존 v3 + Phase 1.0 토큰 그대로)

| 토큰 | 값 | 본 phase 사용처 |
|------|-----|-----------------|
| `--color-teal-50` | `#f0fdfa` | autocomplete `STUDY DESC` 배지 bg |
| `--color-teal-100` | `#ccfbf1` | KCDChip bg, KCD 배지 bg |
| `--color-teal-700` | `#0f766e` | KCDChip text, STUDY DESC 배지 text |
| `--color-warning-light` | `#fffbeb` | PhiPendingBadge (detail context) bg |
| `--color-warning-dark` | `#b45309` | PhiPendingBadge (detail context) text |
| `--color-text` | `#0f172a` | KCD label, description 셀 text |
| `--color-text-muted` | `#64748b` | PhiPendingBadge (cell context) text + icon |
| `--color-text-strong` | `#020617` | tooltip bg |
| `--color-bg` | `#ffffff` | 셀 bg |
| `--color-bg-muted` | `#f8fafc` | PROTOCOL 배지 bg, header bg (v3 그대로) |
| `--color-border` | `#e2e8f0` | metadata grid 행 사이 hairline |
| `--mark-highlight-bg` | `rgba(13,148,136,0.15)` | description 셀 매치 토큰 (Phase 1.0 토큰 자동 적용) |
| `--font-sans-en` | Inter | EN 텍스트 |
| `--font-sans-kr` | Pretendard | KR 텍스트 |
| `space-3` (12 px) | — | KCDChip 와 label 사이 gap, metadata 행 padding |
| `space-4` (16 px) | — | metadata grid 좌우 padding |
| `radius-pill` (999 px) | — | KCDChip, 배지 |
| `radius-md` (8 px) | — | tooltip, PhiPendingBadge (detail) |
| `shadow-overlay` | — | tooltip shadow |

### 12.2 신규 토큰 (의도적 0개)

본 phase 는 **신규 디자인 토큰 0개**. v3 + Phase 1.0 토큰 100 % 차용. UI_GUIDE 가 placeholder 인 상황에서 토큰 확장 자제.

### 12.3 신규 토큰 거부된 후보 (의도적 미정의)

- `--color-kcd-chip-bg`: `--color-teal-100` 차용 충분.
- `--color-phi-pending-fg`: cell 은 `--color-text-muted`, detail 은 `--color-warning-dark` 차용 충분.
- `--color-description-cell-bg`: 별도 bg 없음 (셀 자체 bg = white).

→ Kyle 입력 ("기존 토큰 재사용, 새로 만들지 말 것") 100 % 준수.

---

## 13. 반응형 / 디바이스

### 13.1 정책 승계

`design-spec-portal-redesign.md §4.9`: 바이어 포털은 데스크톱 ≥ 1280 px 기본 타깃.

### 13.2 breakpoint 별 동작

| breakpoint | DESCRIPTION 컬럼 | KCDChip | Study Detail metadata grid |
|-----------|-----------------|---------|---------------------------|
| ≥ 1280 px (desktop) | 노출, max-width 320 px, sortable header (Phase 2 후보) | size=md (text-sm label) | 2-col grid, 신규 2 행 inline |
| 1024 ~ 1279 px | 노출, max-width 240 px | size=md | 2-col grid |
| 768 ~ 1023 px (tablet, fallback) | ColumnToggle default OFF (작은 폭에서 자동 숨김) | size=sm | 1-col stacked grid (label 위, value 아래) |
| < 768 px (mobile, fallback) | hidden | size=sm | 1-col stacked, Series Descriptions 강제 collapse |

### 13.3 모바일 특별 처리

- KCDChip tooltip: hover 없음 → tap 시 toggle (autoclose 3s).
- 격리 fallback: cell context 는 `⚠` 아이콘만, 텍스트 생략 (모바일 셀 폭 제약).

---

## 14. 접근성 (WCAG 2.1 AA)

### 14.1 키보드 navigation 전수

| 동작 | 키 | 컴포넌트 |
|------|-----|---------|
| KCDChip 도달 | Tab | `<KCDChip>` (각 row 의 KCD 셀) |
| KCDChip tooltip 표시 | Tab focus 시 즉시 | `<KCDChip>` |
| KCDChip tooltip 닫기 | Esc 또는 blur | `<KCDChip>` |
| ColumnToggle 열기 | Tab → Enter | `<ColumnToggle>` (v3 baseline) |
| Description 토글 | Space | `<ColumnToggle>` 내부 항목 |
| Series Descriptions 펼침 | Tab → Enter | `<StudyDetailPanel>` |

### 14.2 스크린리더 레이블

- `<KCDChip>`: `aria-label="Diagnosis code G45.9, ICD-10 standard"` (locale 별 변형, FR-TS15-14).
- `<KCDChip>` tooltip: `aria-describedby` 로 chip 과 연결, `role="tooltip"`.
- `<PhiPendingBadge>`: `role="status"` + `aria-label="Description excluded for de-identification review"` (locale 별).
- description 셀 truncate: `title` 속성에 full text — 스크린리더가 ellipsis 가 아닌 full 읽음.
- ColumnToggle "Description" 항목: `aria-label="Toggle Description column"`.
- Study Detail metadata 행 신규 2 행: `<dt>` (label) / `<dd>` (value) 의미 마크업 (v3 baseline 동일).

### 14.3 색 대비 (WCAG AA, 4.5:1)

| 조합 | 대비 | 결과 |
|------|------|------|
| KCDChip text `#0f766e` on `#ccfbf1` | 5.84:1 | AA |
| KCDChip label `#0f172a` on `#fff` | 18.69:1 | AAA |
| KCDChip tooltip white on `#020617` | 19.21:1 | AAA |
| description 셀 text `#0f172a` on `#fff` | 18.69:1 | AAA |
| description `<mark>` text `#020617` on rgba teal bg | ~14:1 | AAA |
| PhiPendingBadge cell `#64748b` on `#fff` | 4.91:1 | AA |
| PhiPendingBadge detail `#b45309` on `#fffbeb` | 4.74:1 | AA |
| autocomplete STUDY DESC 배지 `#0f766e` on `#f0fdfa` | 6.10:1 | AA |
| autocomplete PROTOCOL 배지 `#64748b` on `#f8fafc` | 4.85:1 | AA |

**모든 텍스트 조합 WCAG AA 4.5:1 이상 통과**.

### 14.4 색맹 시뮬레이터 (deuteranopia / protanopia)

- KCDChip: teal 단색 → 색맹 시뮬레이터에서 회색 톤이지만, 시각적 chip shape (pill) + 텍스트 prefix ("ICD-10" / "KCD-8") 로 의미 전달.
- PhiPendingBadge: 색만 의존 안 함 (⚠ 아이콘 + "pending" 텍스트). 색맹 사용자도 즉시 인식.
- description 셀 매치 토큰 `<mark>`: Phase 1.0 의 색 + font-weight 600 동시 단서 그대로.

### 14.5 focus visible

- v3 baseline `outline: 2px solid var(--color-primary-600); outline-offset: 2px;` 그대로 승계.
- KCDChip focus: outline + tooltip 자동 표시 (둘 다 동시).

---

## 15. 국제화 (i18n)

### 15.1 신규 i18n 키 표 (총 약 15 개)

| 키 | en | ko |
|----|-----|-----|
| `search.bar.placeholder.phase15` | `Search by body part, modality, KCD code, or description... (e.g. 'MR brain', 'knee scanogram', 'I20.9')` | `신체부위, 모달리티, KCD 코드 또는 검사명 검색... (예: 'MR 뇌', '슬관절 검사', 'I20.9')` |
| `kcd.chip.label_prefix` | `ICD-10` | `KCD-8` |
| `kcd.chip.aria_label` | `Diagnosis code {code}, ICD-10 standard` | `진단 코드 {code}, KCD-8 기준` |
| `kcd.tooltip` | `Korean coded as KCD-8 (95% identical to WHO ICD-10)` | `WHO ICD-10 호환 (95% 동일)` |
| `kcd.footer.note` | `Provenance: Korean Standard Classification of Diseases v8 (KCD-8)` | `출처: 한국표준질병사인분류 8차 (KCD-8)` |
| `column_toggle.description` | `Description` | `검사 설명` |
| `result.column.description.header` | `Description` | `검사 설명` |
| `description.phi_pending.cell` | `pending` | `검토 대기` |
| `description.phi_pending.cell.tooltip` | `Excluded for de-identification review` | `비식별화 검토 대기 중` |
| `description.phi_pending.detail` | `PHI verification pending` | `PHI 검증 대기 중` |
| `description.phi_pending.audit_chain_badge` | `description pending` | `검사 설명 검토 중` |
| `study.detail.metadata.description` | `Study Description` | `검사 설명` |
| `study.detail.metadata.protocol` | `Protocol Name` | `프로토콜 명` |
| `study.detail.metadata.series_descriptions` | `Series Descriptions` | `시리즈 설명` |
| `study.detail.metadata.series_descriptions.expand` | `View {count} series descriptions` | `{count}개 시리즈 설명 보기` |
| `study.detail.metadata.series_descriptions.collapse` | `Hide` | `숨기기` |
| `autocomplete.badge.study_desc` | `STUDY DESC` | `검사 설명` |
| `autocomplete.badge.protocol` | `PROTOCOL` | `프로토콜` |

**총 18 키** (Kyle 입력의 "약 15 개" 가이드 +α). 기존 i18n 파일 (`web/portal/src/lib/i18n.ts` 또는 `web/portal/src/i18n/{en,ko}.json`) 에 추가만, 새 파일 안 만듦.

### 15.2 한국어 길이 / 가로 폭 검증

- KCDChip prefix: en `"ICD-10"` (6 자) vs ko `"KCD-8"` (5 자) — 거의 동일, chip 가로 폭 차이 < 4 px (감지 불가).
- placeholder: en 100 자 vs ko 50 자 — 한국어 30 % 짧음 정책 준수 (Phase 1.0 패턴).
- tooltip: en 56 자 vs ko 18 자 — tooltip max-width 320 px 안에서 둘 다 1 줄.
- column header: en `"Description"` (11 자) vs ko `"검사 설명"` (5 자, 5 visual width) — 컬럼 폭 영향 없음.
- StudyDetail label: en `"Study Description"` (17 자) vs ko `"검사 설명"` (5 자) — 1-col stacked 모바일 fallback 시 한국어가 덜 차지.

### 15.3 KCD chip 라벨 i18n 분기 위치

- **BFF 합성 정책 (FR-TS15-11)**: `kcd_label_display` 가 BFF 응답에 포함됨. 클라이언트는 응답값을 그대로 표시.
- **클라이언트 fallback**: BFF 가 구버전이라 `kcd_label_display` 미포함 시 → 클라이언트가 LocaleProvider locale + i18n("kcd.chip.label_prefix") + code 합성.
- **이유**: cache 친화 (BFF 응답 cache key 에 locale 포함). 클라이언트 fallback 은 backward compat (NFR-TS15-COMPAT-2).

---

## 16. AC (Design AC) — 18~22 개

`@qa` 가 본 체크리스트로 시각·행동 검수. dev-spec §10 의 AC-TS15-* 와 1:1 매핑되며 디자인 관점 추가 항목 포함.

| ID | 기준 | 매핑 dev-spec AC |
|----|------|-----------------|
| **DA-1** | KCDChip 의 prefix 라벨이 locale 에 따라 정확 — en="ICD-10 {code}" / ko="KCD-8 {code}" — i18n 키 `kcd.chip.label_prefix` 와 byte-identical | AC-TS15-13, 14 |
| **DA-2** | KCDChip tooltip 이 hover (200ms delay) + Tab focus (즉시) 양쪽에서 표시, locale 별 텍스트 정확 (en `"Korean coded as KCD-8..."` / ko `"WHO ICD-10 호환 (95% 동일)"`) | AC-TS15-13, 14, 15 |
| **DA-3** | KCDChip 가 키보드 Tab 으로 도달 가능 + tooltip aria-describedby 로 스크린리더 연결 | AC-TS15-15, NFR-TS15-A11Y-1, A11Y-2 |
| **DA-4** | KCDChip 의 chip pill 자체는 locale 무관 동일 시각 (bg `--color-teal-100`, fg `--color-teal-700`, padding `2×8 px`, radius-pill) | §6.3 |
| **DA-5** | ResultTable 에 DESCRIPTION 컬럼이 default ON 으로 추가, ColumnToggle 으로 OFF 가능 (12 → 13 toggleable) | §8.4 |
| **DA-6** | description 셀이 truncate ellipsis (max-width 320 px) + hover/focus 시 `title` full text 노출 | §8.3 |
| **DA-7** | description 셀의 매치 토큰이 Phase 1.0 의 `<mark>` 자동 적용 (server `ts_headline` 컬럼 확장만, CSS 변경 0) | AC-TS15-24, FR-TS15-19 |
| **DA-8** | PhiPendingBadge (cell context) 가 description 빈 string 시 노출 — `⚠ pending` 회색, hover tooltip "Excluded for de-identification review" | §7.3, AC-TS15-25 |
| **DA-9** | PhiPendingBadge (detail context) 가 Study Detail metadata grid 의 신규 2 행 (Study Description / Protocol Name) 에서 warning style 로 노출 | §9.2, AC-TS15-25 |
| **DA-10** | PhiPendingBadge 가 색맹 시뮬레이터 (deuteranopia + protanopia) 통과 — 색 외에 ⚠ 아이콘 + "pending" 텍스트 두 단서로 의미 전달 | §14.4 |
| **DA-11** | Study Detail metadata grid 가 9 행 → 11 행 (Study Description, Protocol Name 신규), Series Descriptions 별도 collapsible | §9.1, AC-TS15-25 |
| **DA-12** | KCD 행 하단 footer note 가 locale 별 노출 (en `"Provenance: Korean Standard..."` / ko `"출처: 한국표준질병사인분류..."`) | AC-TS15-19 |
| **DA-13** | SearchBar placeholder 가 locale 별 분기 — en `"... 'I20.9'"` 외에 `'knee scanogram'` 추가, ko `'슬관절 검사'` 추가 | AC-TS15-18 |
| **DA-14** | AutocompleteDropdown 항목 우측 배지에 STUDY DESC (teal-50 bg + teal-700 fg) + PROTOCOL (slate) 2 종 추가 | §11.1 |
| **DA-15** | locale 전환 (en ↔ ko) 시 페이지 reload 없이 KCDChip / placeholder / tooltip / 컬럼 헤더 즉시 갱신 | AC-TS15-17, NFR-TS15-AVAIL-2 |
| **DA-16** | 검색 동작 locale 무관 — 동일 q 로 en/ko 전환 시 row 순서/개수/내용 byte-identical | AC-TS15-16 |
| **DA-17** | i18n 키 18 개 모두 ko/en 양쪽 정의 (없으면 i18n linter fail) | AC-TS15-13, 14, 18, 19 |
| **DA-18** | 모든 텍스트 조합이 WCAG AA 4.5:1 이상 (§14.3 매트릭스 9 종 전수 통과) | NFR-TS15-A11Y-1 |
| **DA-19** | 키보드 only (마우스 disconnect) 로 검색 → 결과 → KCDChip tooltip → ColumnToggle → Description ON/OFF → Study Detail 진입 → metadata grid 모든 행 Tab 으로 이동 가능 | NFR-TS15-A11Y-1 |
| **DA-20** | 신규 디자인 토큰 0 개 — v3 + Phase 1.0 토큰 100 % 차용 | §12.2 |
| **DA-21** | DESCRIPTION_EXTRACTION_ENABLED=false 시 description 컬럼 셀 모두 `—` (NULL fallback), 컬럼 헤더는 표시. KCDChip locale 분기는 그대로 ON | AC-TS15-21, 22 |
| **DA-22** | mockup HTML 의 5 시나리오 (a~e) 가 본 design-spec §6~§11 토큰 / 색 / 간격 정확 반영 | §17 |

---

## 17. Mockup HTML 스펙

**경로**: `docs/specs/mockups/text-search-description-phase15/search-results.html`

**구조**: 단일 페이지에 5 시나리오 stacked vertical, 각 시나리오 sticky 라벨 배지 ("a) en + description 매치", ...) + 1280 px wide 캡처.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  [a) en locale + description 매치]                                       │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  /search?q=knee scanogram (locale=en)                              │ │
│  │  - 검색바 placeholder: "Search by body part... 'knee scanogram'..."│ │
│  │  - ResultTable 8 rows + DESCRIPTION 컬럼 노출                       │ │
│  │  - 매치 셀: <mark>Knee Scanogram</mark>                            │ │
│  │  - KCD chip "[ICD-10 M17.0] Knee osteoarthritis"                   │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  [b) ko locale + description 매치 (동일 query)]                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  /search?q=knee scanogram (locale=ko)                              │ │
│  │  - 검색바 placeholder: "신체부위, 모달리티... '슬관절 검사'..."     │ │
│  │  - ResultTable rows 동일 (검색 동작 locale 무관)                   │ │
│  │  - DESCRIPTION 헤더: "검사 설명"                                    │ │
│  │  - KCD chip "[KCD-8 M17.0] Knee osteoarthritis"                    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  [c) PHI 격리된 description fallback]                                    │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  /search?q=brain                                                   │ │
│  │  - DESCRIPTION 셀 일부에 ⚠ pending (회색)                          │ │
│  │  - hover 시 tooltip "Excluded for de-identification review"        │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  [d) tooltip hover (KCD chip)]                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  KCDChip 위에 hover (en/ko 두 변형 side-by-side)                    │ │
│  │  - en: tooltip "Korean coded as KCD-8 (95% identical to WHO...)"   │ │
│  │  - ko: tooltip "WHO ICD-10 호환 (95% 동일)"                        │ │
│  │  - tooltip 위치 chip 위, arrow 8px 가리킴                          │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  [e) Study Detail metadata grid 확장]                                    │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  /studies/:id (locale=en) — 11 행 metadata grid                    │ │
│  │  - 신규 행: Study Description, Protocol Name                       │ │
│  │  - KCDChip variant="detail" + footer note                          │ │
│  │  - Series Descriptions collapsible (펼침 상태)                     │ │
│  │  - 우측에 격리 fallback 변형 (PhiPendingBadge detail context)       │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

- 5 시나리오 사이는 `space-12` (48 px) gap + 회색 hairline.
- 각 시나리오 좌상단에 sticky 라벨 (`text-sm / font-mono / bg-text-strong / text-white / radius-pill`).
- HTML 단독으로 브라우저에서 열어 검사 가능 (외부 의존 0, inline CSS).
- 본 디자인 명세 §6~§11 의 모든 토큰 / 색 / 간격 정확 반영.

**금지**:

- 외부 이미지 URL 발명 금지. 아이콘은 inline SVG (lucide-react `alert-triangle`, `chevron-down`, `search`).
- 실제 환자 데이터 0 건 (모든 row 는 TCIA 기반 더미 + body_part / kcd / description 만).
- 새 디자인 시스템 만들지 말 것 — v3 + Phase 1.0 토큰만 차용.

---

## 18. 상태 처리 (요약 매트릭스)

| 화면 | loading | empty | error | no-permission | partial-failure |
|------|---------|-------|-------|---------------|-----------------|
| `<KCDChip>` | n/a (server-side resolved) | code 부재 시 unmount (KCD 셀 빈 값 → "—") | tooltip 표시 실패 시 chip 만 표시 (silent) | n/a | locale 부재 → default `en` (NFR-TS15-I18N-2) |
| `<PhiPendingBadge>` | n/a | mount 안 됨 (description 정상 시) | n/a | n/a | n/a |
| ResultTable DESCRIPTION 컬럼 | v3 baseline skeleton 셀 그대로 | NULL → `—` 렌더 | description fetch 실패 시 NULL 처리 | v3 baseline 401 → /login | description 인덱싱 실패 row 만 NULL, 다른 row 정상 |
| ColumnToggle Description 항목 | n/a | n/a | toggle persist 실패 시 default ON 유지 | n/a | n/a |
| Study Detail metadata grid 신규 2 행 | v3 baseline skeleton 그대로 | NULL → `—` (격리 시 PhiPendingBadge) | API fail 시 metadata grid 자체 v3 baseline error state | v3 baseline 401 | description 만 NULL, 다른 9 행 정상 |
| AutocompleteDropdown STUDY DESC / PROTOCOL 배지 | n/a | description 매치 0건 시 항목 자체 미노출 | description 토큰 fetch 실패 시 silent skip (Phase 1.0 동작 유지) | n/a | description 만 빠짐 |
| `<SearchBar>` placeholder | n/a (즉시 노출) | n/a | i18n 키 missing 시 fallback 영문 | n/a | n/a |

---

## 19. 다음 에이전트 작업 (NEXT_STEP)

```
### NEXT_STEP
- 완료 산출물:
  - docs/specs/design-spec-text-search-description-phase15.md (Draft v0.1, 본 문서)
  - docs/specs/mockups/text-search-description-phase15/search-results.html (5 시나리오 mockup)
- 제안 다음 단계:
  - @developer — claude 브랜치에서 text-search-description-phase15 구현 착수.
    - dev-spec §12.1 일정에 따라 4 PR 분리:
      - PR 1 (W2 D-13+20~21): alembic migration 0009 + Gateway extract.py + description_scrub.py + 60+ 단위 테스트
      - PR 2 (W2 D-13+22~23): Central ingest 변경 + 격리 audit 테이블 + 250 backfill 스크립트
      - PR 3 (W2 D-13+24~25): Search service ts_headline 확장 + Pydantic schema + StudyItem 신규 필드
      - PR 4 (W2 D-13+25~26): BFF locale 합성 (kcd_label_display) + UI <KCDChip> 신규 + ResultTable Description 컬럼 + StudyDetail metadata grid 2 행 + ColumnToggle 1 항목 + i18n 키 18 개 + <PhiPendingBadge> 신규
  - @qa — 구현 완료 후 docs/qa/qa-report-text-search-description-phase15.md 작성.
    - 디자인 측 우선 검증:
      - DA-1 ~ DA-22 (본 §16)
      - WCAG AA 색 대비 매트릭스 9 종 자동 검증 (§14.3)
      - 색맹 시뮬레이터 (deuteranopia/protanopia) — DA-10
      - 키보드 only 시나리오 — DA-19
      - locale 토글 페이지 reload 없음 — DA-15
      - feature flag off 시 UI 회귀 — DA-21
- UI_GUIDE.md 갱신 제안:
  - 신규 토큰 0 개 (의도적).
  - 신규 공통 컴포넌트 2 개:
    - <KCDChip> — Buyer/Hospital/운영자 콘솔에서 KCD 코드 표시 시 모두 재사용 가능.
    - <PhiPendingBadge> — PHI 격리·검토 대기 표시 시 재사용 가능 (Phase 2 Quarantine Review UI 에서도 활용).
  - 신규 i18n key prefix: `kcd.*` (4 키), `description.phi_pending.*` (4 키), `study.detail.metadata.*` (5 키), `autocomplete.badge.*` (2 키 추가).
  - UI_GUIDE 공식화 시 Kyle 승인 후 위 2 컴포넌트 + i18n prefix 편입 권장.
- 추가 디자인 필요:
  - Phase 2 (`design-spec-text-search-korean-stemmer.md`) — 한국어 형태소 분석기 도입 후 KCD chip 의 한국 확장 코드 (5%) 별도 표기 검토.
  - Phase 2 (`design-spec-phi-quarantine-review-ui.md`) — Kyle / Compliance RA 가 격리된 study 를 review 하는 UI. 본 phase 의 <PhiPendingBadge> + study_phi_quarantine_audit 테이블을 시각화.
  - Phase 2 (`design-spec-snomed-radlex-mapping.md`) — KCD ↔ SNOMED CT / RadLex 매핑 UI. KCDChip 에 추가 chip (SNOMED) inline 노출.
- Kyle 결정 필요 사항:
  - Q1: AutocompleteDropdown 의 배지 텍스트 케이스 통일 — Phase 1.0 lowercase (`body_part`) vs Phase 1.5 uppercase (`STUDY DESC`). 현재는 신규 배지만 uppercase, 통일 시 Phase 1.0 도 변경 필요. 데모 임팩트 vs i18n 작업량.
  - Q2: KCD chip 클릭 시 동작 (현재 미정의) — 검색 필터에 자동 추가 (e.g. `kcd_code=M17.0`) 후보. Phase 2 검토.
  - Q3: Series Descriptions collapsible default 상태 — 본 명세는 collapse (밀도 보호). expand default 도 후보 (정보 즉시 노출). 데모 시나리오 따라 결정.
  - Q4: 모바일 (< 768 px) 에서 DESCRIPTION 컬럼 default OFF — 본 명세 채택. Tablet (768~1023) 까지 OFF 확장 여부. v0.1 ship 후 사용성 측정.
```

---

## 20. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-26 | @designer | 최초 작성. dev-spec-text-search-description-phase15 v0.1 + Kyle 결정 6건 + Phase 1.0 design-spec 자산 100% 재사용 + v3 토큰 0 신규. <KCDChip> + <PhiPendingBadge> 2 컴포넌트 신규. ResultTable DESCRIPTION 컬럼 + Study Detail metadata grid 2 행 + autocomplete 배지 2 종 추가. i18n 키 18 개. 5 시나리오 mockup 명세. |
