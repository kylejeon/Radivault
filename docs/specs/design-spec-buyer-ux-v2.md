# 디자인 명세 — Buyer UX v2 (Anti-Segmed Redesign)

> **Status**: Draft v0.1 · **Feature slug**: `buyer-ux-v2` · **Last updated**: 2026-04-25
> **작성자**: @designer (Claude Opus 4.7 [1M])
> **근거**:
> - dev-spec: [`dev-spec-portal-redesign.md`](./dev-spec-portal-redesign.md) — FR-BP-* (바이어 포털)
> - 평가서 (대체): [`design-spec-buyer-ux-evaluation.md`](./design-spec-buyer-ux-evaluation.md) — v1 비판
> - 리서치: [`segmed-openda-deep-dive.md`](../research/segmed-openda-deep-dive.md) §3·§4·§5·§6 (1차 직접 분석)
> - v1 mockup (anti-pattern): [`mockups/buyer-ux-v2/{index,search,study-detail,account}.html`](./mockups/buyer-ux-v2/)
> - UI Guide: [`UI_GUIDE.md`](../UI_GUIDE.md) — 토큰은 §4 신규 제안

> **본 문서의 위치**: v1 mockup (`docs/specs/mockups/buyer-ux-v2/`) 이 Segmed Openda 와 시각·구조·데이터·인터랙션 4 축에서 너무 유사하다는 Kyle 의 평가에 따라, **본 v2 는 4 축 모두 차별화** 한다. v1 mockup 은 `mockups/buyer-ux-v2/` 에 보존, v2 mockup 은 `mockups/buyer-ux-v2/v2/` 에 신규 생성.

---

## 1. 디자인 개요

RadiVault buyer-side 3 화면 (`/search`, `/studies/[uid]`, `/account`) 을 **Segmed Openda 와 명확히 다르게** 재디자인한다. 핵심 차별 4 축:

1. **시각** — Segmed `#2563EB` 회피, RadiVault 전용 navy `#0B2545` + teal `#14B8A6` 듀얼.
2. **구조** — Segmed 의 12-col horizontal pill chip 대신 좌측 320px vertical accordion + 우하단 sticky cohort drawer.
3. **데이터** — Segmed 의 집계 슬로건 ("5 continents") 대신 결과 row 마다 hospital region badge (SEOUL-A / BUSAN-B) + per-row De-ID audit hash chip.
4. **인터랙션** — Segmed 가 admin only 로 숨긴 De-ID chain 을 우측 영구 sticky stepper 로 노출. KCD-8 + SNOMED + RadLex 트리플 ontology 자동완성, 한·영 동시.

또한 Patient longitudinal timeline (Segmed 미구현), PIPA + 정통망법 + KCD/MoH 컴플라이언스 풋터, Pretendard 한글 1급 폰트로 RadiVault specialty-first 포지션 강화.

---

## 2. v1 → v2 차별 (5축)

| 축 | v1 (Segmed 클론) | v2 (본 리디자인) | 근거 |
|---|---|---|---|
| **A1. 컬러** | `#2563EB` Tailwind blue-600 (Segmed primary 와 동일) | `#0B2545` navy + `#14B8A6` teal | researcher §6 DON'T-1 |
| **A2. 폰트** | Inter 단일 (Segmed 와 동일, 한글 폰트 미정의) | Inter (영문) + Pretendard 1급 (한글) + JetBrains Mono (코드/UID) | researcher §5.2 V2 |
| **A3. 레이아웃** | 3-pane (좌 facet pill + 중앙 + 우 cart) — Segmed SearchUI 미러 | 2-col 비대칭 (좌 320px vertical accordion / 우 scrollable) + 우하단 sticky cohort drawer | researcher §6 DON'T-2 |
| **A4. 출처** | opaque hospital ID chip 한 줄 | per-row hospital region 배지 (SEOUL-A / BUSAN-B) + 4px 색상 stripe + audit hash chip | researcher §6 DO-1 |
| **A5. 익명화** | PIPA chip + tooltip (수동) | 우측 영구 5단계 De-ID Chain stepper (default 노출) + 각 단계 audit hash 4자 prefix + full audit modal | researcher §6 DO-2 |

---

## 3. Segmed vs v2 visual diff (10 항목)

| # | 요소 | Segmed Openda | RadiVault v2 | 비고 |
|---|---|---|---|---|
| 1 | Primary | `#2563EB` Tailwind blue-600 | `#0B2545` deep navy | hex 100% 다름 |
| 2 | Accent | `#1890FF` Ant Design daybreak | `#14B8A6` teal-500 | 채널 거리 큼 |
| 3 | Canvas | `#FFFFFF` cold | `#FAFAF9` warm stone | 따뜻한 base 로 archive 톤 |
| 4 | Korean font | 미정의 (시스템 fallback) | Pretendard 1급 | 한글 페이지 native |
| 5 | Header bg | white + thin border | `#13315C` navy bar | 어두운 헤더로 sales 톤 회피 |
| 6 | Facet | horizontal pill chip | vertical accordion + 한·영 group label | Segmed SearchUI 정석 회피 |
| 7 | Modality | colored pill | 8px single dot + label | 통일 chip 대신 dot 으로 row 정보밀도 ↑ |
| 8 | Per-row stripe | 없음 | 4px hospital-color 좌측 bar | per-row provenance |
| 9 | Cart UX | top horizontal cart | 우하단 sticky cohort drawer | Segmed cart 와 시각 분리 |
| 10 | Audit display | admin only, buyer 미노출 | row 에 teal hash chip + 상세 sticky stepper | 차별 핵심 |

---

## 4. RadiVault 5 강점 화면 매핑

| # | 강점 | 노출 화면 | 컴포넌트 | dev-spec 영향 |
|---|---|---|---|---|
| **R-1** | 병원별 출처 (region pseudo-brand) | search · study-detail | `<HospitalBadge>` | dev-spec-buyer-browse-preview FR-BP-7 확장 |
| **R-2** | 노출형 5단계 De-ID 체인 + audit hash | study-detail (right rail), search (row chip) | `<DeIDChainStepper>` | 신규 `dev-spec-deid-chain-buyer-view` |
| **R-3** | 트리플 ontology (KCD-8 + SNOMED + RadLex) 자동완성, 한·영 동시 | search (sub-bar) | `<KCDAutocomplete>` | 신규 `dev-spec-ontology-search-snomed-kcd-radlex` |
| **R-4** | 환자 단위 longitudinal timeline | study-detail | `<LongitudinalTimeline>` | dev-spec-metadata-index 에 `patient_pseudo_id` 노출 추가 |
| **R-5** | PIPA + 정통망법 + KCD/MoH 컴플라이언스 푸터/헤더 | 모든 화면 | `<PIPATrustBar>` | dev-spec-portal-redesign FR-HP-9, FR-HP-10 확장 |

---

## 5. 화면 목록

| ID | 화면명 | 경로 (목업) | 주요 역할 |
|----|---|---|---|
| S-1 | Search & Cohort | `mockups/buyer-ux-v2/v2/search.html` | 검색 입력 + 결과 + cohort drawer |
| S-2 | Study Detail | `mockups/buyer-ux-v2/v2/study-detail.html` | viewer + 메타 + De-ID chain + longitudinal |
| S-3 | Account | `mockups/buyer-ux-v2/v2/account.html` | profile + API key + quota + audit log + onboarding |
| S-0 | Guide / Index | `mockups/buyer-ux-v2/v2/index.html` | v1→v2 차별 표 + 화면 링크 |

---

## 6. 사용자 플로우

### 6.1 Happy path — 신규 buyer 첫 검색·다운로드

```
[로그인 직후] → S-1 (검색)
   ↓ KCD autocomplete "협심증" 선택
[결과 250건 노출, hospital stripe 다중 색]
   ↓ row1 "View" 클릭
S-2 (study detail) [De-ID Chain 우측 default 노출]
   ↓ "Sample download" 클릭 (preview tier 무료)
[ZIP 10 instances 다운로드 토스트]
   ↓ "Add to cohort" 클릭
[우하단 cohort drawer 카운트 1 → 2]
```

### 6.2 권한 없음 — preview tier 가 contract-tier 데이터 시도

```
[S-1 결과 row 중 "🔒 contract-only" 배지된 row 클릭]
   ↓
S-2 (study detail) [viewer placeholder + "Contract required" 오버레이]
   → 우측 sticky CTA 가 "Sample download" 비활성 + "Request contract upgrade" primary
   → 안내문: "PIPA §28-8 expert determination 에 따라 계약이 필요합니다"
```

### 6.3 에러 — autocomplete 응답 실패

```
[S-1 검색 입력]
   ↓ 트리플 ontology API 500
[autocomplete dropdown 자리에 회색 박스 + "ontology temporarily unavailable · search by free text"]
   → 입력은 그대로 작동, KCD/SNOMED 칩 매칭만 비활성
```

### 6.4 부분 실패 — 한 병원만 응답

```
[S-1 검색]
   ↓ SEOUL-A OK, BUSAN-B timeout
[hero strip "Showing 142 / partial: 1 of 2 hospitals" + amber dot]
[BUSAN-B 카운트 자리 "—" + tooltip "BUSAN-B unreachable, retrying"]
```

---

## 7. 컴포넌트 인벤토리

| 컴포넌트 | 목적 | 상태 (default → expanded → error) | 재사용 |
|---|---|---|---|
| `<HospitalBadge>` | region pseudo-brand 표시 (SEOUL-A 등) + dot 색 | normal / hover (full name tooltip) / disabled (soon) | row · header · facet · cohort drawer |
| `<DeIDChainStepper>` | 5 단계 De-ID + audit hash 4자 prefix | done(teal) / running / failed | study-detail right rail (sticky), modal 내 expanded |
| `<KCDAutocomplete>` | 한·영·KCD/SNOMED/RadLex 트리플 dropdown | closed / open / loading / empty / error | search subbar |
| `<LongitudinalTimeline>` | 한 환자의 시간순 study dot | empty / single (현재만) / multi (4+) | study-detail 우측 |
| `<PIPATrustBar>` | header mini + footer full 컴플라이언스 배지 | always-on | 모든 페이지 |
| `<ResultRow>` | 검색 결과 row (stripe + thumb + meta + actions) | default / hover / selected (cohort 포함) | search |
| `<CohortDrawer>` | 우하단 sticky 코호트 stat + actions | empty (collapsed) / has items (expanded) | search · cohort 페이지 |
| `<AuditHashChip>` | row · 메타 영역 mini hash chip | default / clicked (modal open) | search · study-detail |
| `<ModalityDot>` | 8px 색상 dot | CT/MR/MG/CR/US/PT 6 색 | row · facet · cohort |
| `<TabsCodeBlock>` | curl/Python/Postman 탭 + copy | tab active 1 / 3 | account |
| `<QuotaGauge>` | bar fill + count | 0% / mid / 100% (warning) | account |
| `<AuditList>` | 최근 5 events row | empty / loaded | account |
| `<OnboardChecklist>` | 5 단계 todo | done(teal) / pending | account |

---

## 8. 디자인 토큰 (v2 신규)

> **Status**: 제안. UI_GUIDE.md 정식 등록은 Kyle 승인 후.

### 8.1 컬러 (모두 신규, segmed 와 hex 다름)

| 토큰 | 값 | 용도 |
|---|---|---|
| `--rv-navy-900` | `#0B2545` | primary navy (CTA · heading) |
| `--rv-navy-800` | `#0E2C56` | hover state |
| `--rv-navy-700` | `#13315C` | header bar bg |
| `--rv-navy-500` | `#1E466A` | secondary navy |
| `--rv-navy-100` | `#DCE7F3` | tinted bg / SEOUL badge bg |
| `--rv-teal-700` | `#0F766E` | accent text on light |
| `--rv-teal-500` | `#14B8A6` | accent (De-ID stepper · audit chip · ghost button) |
| `--rv-teal-300` | `#5EEAD4` | dark-bg highlight |
| `--rv-teal-100` | `#CCFBF1` | audit hash chip bg / BUSAN badge bg |
| `--rv-amber-500` | `#F59E0B` | PIPA badge dot |
| `--rv-amber-100` | `#FEF3C7` | KCD code chip bg / preview tier badge |
| `--rv-stone-50` | `#FAFAF9` | canvas (warm — Segmed cold #fff 와 구분) |
| `--rv-stone-200` | `#E7E5E4` | border |
| `--rv-stone-700` | `#44403C` | body text |
| `--rv-stone-900` | `#1C1917` | heading / footer bg |
| `--mod-ct` | `#0EA5E9` | CT modality dot |
| `--mod-mr` | `#A855F7` | MR modality dot |
| `--mod-mg` | `#EC4899` | MG modality dot |
| `--mod-cr` | `#10B981` | CR/DR modality dot |
| `--mod-us` | `#F97316` | US modality dot |
| `--mod-pt` | `#EF4444` | PET/NM modality dot |

### 8.2 폰트

| 토큰 | 값 | 용도 |
|---|---|---|
| `--font-en` | `'Inter var', 'Inter', -apple-system, sans-serif` | 영문 본문 |
| `--font-ko` | `'Pretendard', 'Inter var', sans-serif` | 한글 본문 (1급) |
| `--font-mono` | `'JetBrains Mono', 'IBM Plex Mono', ui-monospace, monospace` | UID · audit hash · code |

본문 14px / 1.55 행간. Heading 600 weight, body 400. 한글 페이지에서 Pretendard 가 자동 적용 (`body[data-locale="ko"]`).

### 8.3 레이아웃

| 토큰 | 값 | 용도 |
|---|---|---|
| `--rv-sidebar-w` | `320px` | 좌측 facet accordion (Segmed 12-col 회피) |
| `--rv-rightbar-w` | `380px` | study-detail 우측 De-ID rail |
| `--rv-cohort-drawer-w` | `360px` | 우하단 sticky 코호트 drawer |
| `--radius-sm` | `4px` | row · button (Segmed 8px+ 보다 squarer) |
| `--radius-md` | `6px` | card |
| `--radius-lg` | `10px` | drawer |

### 8.4 shadow

| 토큰 | 값 | 용도 |
|---|---|---|
| `--shadow-card` | `0 1px 0 rgb(11 37 69 / 0.04), 0 1px 3px rgb(11 37 69 / 0.06)` | row hover |
| `--shadow-pop` | `0 8px 24px rgb(11 37 69 / 0.10)` | drawer · modal · autocomplete |

---

## 9. 와이어프레임 (ASCII, 4 화면)

### 9.1 S-1 search.html

```
┌───────────────────────────────────────────────────────────────────────────┐
│ NAV [navy bg]  R RadiVault  [PIPA chip]   Search Cohorts Orders Docs   EN│한 [acme-ai] │
├───────────────────────────────────────────────────────────────────────────┤
│ SUB-BAR  [🔍 협심증 / Angina / I20 ____________ ]  [Save] [Search]        │
│         ┌─ AUTOCOMPLETE (open) ──────────────────────────────────────┐   │
│         │ I20.9   협심증, 상세불명     Angina pectoris      [KCD-8]  │   │
│         │ 194828.. 협심증 (안정형)     Angina (disorder)    [SNOMED] │   │
│         │ RID3501 관상동맥             Coronary artery      [RadLex] │   │
│         └────────────────────────────────────────────────────────────┘   │
├──────────────────┬────────────────────────────────────────────────────────┤
│ SIDEBAR (320px)  │ RESULTS                                                │
│ vertical accordn │ 250 studies · 38 ms · across 2 hospitals       Sort ▾  │
│                  │ ─────────────────────────────────────────────────────  │
│ ▾ 데이터 출처    │ ║ [thumb] [SEOUL-A] [I20.9] [hash a3f0]    [View][+] │
│   ☑ ◉ SEOUL-A 142│ ║         ● Chest CT — angina workup                  │
│   ☑ ◉ BUSAN-B 108│ ║         F·54  312 inst  SIEMENS  2024-08            │
│   ☐ ◯ DAEGU-C —  │ ─────────────────────────────────────────────────────  │
│   ☑ De-ID verified│║ [thumb] [BUSAN-B] [I20.9] [hash 9c1e]    [View][+] │
│ ▾ 임상 정보      │ ║         ● Cardiac MR — perfusion stress             │
│   KCD ☑ I20.9 38 │ ║         M·47  188 inst  Philips  2024-09            │
│   KCD ☐ I25.1 21 │ ─────────────────────────────────────────────────────  │
│   부위:흉부 112   │ ║ ... 6 more rows                                     │
│   부위:두부 58    │                                                        │
│ ▾ 환자 정보      │                                  ┌─ COHORT DRAWER ──┐ │
│   F 128 / M 122  │                                  │ 3 in cohort       │ │
│   40-49 ☑ 50-59☑ │                                  │ 2 hosp · 756 inst │ │
│ ▾ 영상 기술      │                                  │ 412 MB            │ │
│   ● CT 98        │                                  │ [Save] [Order →] │ │
│   ● MR 62        │                                  └───────────────────┘ │
│ ▸ 시간            │                                                        │
├──────────────────┴────────────────────────────────────────────────────────┤
│ FOOTER [stone-900]  ●PIPA §28-8  ●정통망법  ●KCD-8  ●MoH HIRA   Trust ↗  │
└───────────────────────────────────────────────────────────────────────────┘
```

### 9.2 S-2 study-detail.html

```
┌───────────────────────────────────────────────────────────────────────────┐
│ NAV  R RadiVault  [PIPA chip]   ← Back Cohorts ...        EN│한 [acme-ai] │
├───────────────────────────────────────────────────────────────────────────┤
│ SUB [SEOUL-A] [I20.9] 1.2.840.HOSP1.7392 [audit a3f0]   ← Prev 3/250 Next│
├──────────────────────────────────────┬───────────────────────────────────┤
│  VIEWER (dark)                       │  RIGHT RAIL (sticky)              │
│  ┌─────────────────────────────┐    │ ─ Metadata ──────── DICOM tags ↗  │
│  │ overlay TL: SEOUL-A · CT     │    │ ┌─ Patient ─────────────────┐    │
│  │ WW 350 / WL 50 · slice 156   │    │ │ Pseudo ID  PT-7392-A       │    │
│  │ overlay TR: SIEMENS Drive    │    │ │ Sex        F               │    │
│  │ ◉ tools: pan/zoom/wl/measure │    │ │ Age        50-59           │    │
│  │ ╭─ chest CT placeholder ─╮  │    │ │ Consent    PIPA §28-8       │    │
│  │ │   [synthetic image]     │  │    │ └────────────────────────────┘    │
│  │ ╰────────────────────────╯  │    │ ┌─ Study ───────────────────┐    │
│  │ overlay BL: F · 50-59        │    │ │ Modality   ● CT             │    │
│  │ overlay BR: ▣ De-ID a3f0     │    │ │ Body part  CHEST            │    │
│  └─────────────────────────────┘    │ │ ...                         │    │
│                                       │ └────────────────────────────┘    │
│                                       │ ┌─ Series & device ─────────┐    │
│                                       │ │ ...                          │   │
│                                       │ └────────────────────────────┘    │
│                                       │ ─ De-ID Chain ── audit log ↗     │
│                                       │ ╔══════════════════════════════╗ │
│                                       │ ║ ✓ 5 stages · all verified    ║ │
│                                       │ ║ ① PHI tag scrub   [a3f0…]   ║ │
│                                       │ ║ ② UID re-gen      [b71c…]   ║ │
│                                       │ ║ ③ Date shift      [c08f…]   ║ │
│                                       │ ║ ④ Burn-in OCR     [d92a…]   ║ │
│                                       │ ║ ⑤ 3D defacing     [e51b…]   ║ │
│                                       │ ║ ruleset v0.2.1 · 2024-08-31  ║ │
│                                       │ ╚══════════════════════════════╝ │
│                                       │ ─ Patient longitudinal ──────    │
│                                       │  CR ─ CT ─ ◉CT ─ MR              │
│                                       │ 22-03 23-06 24-08 25-01          │
│                                       │ ─────────────────────────────    │
│                                       │ [⬇ Sample download (ZIP)] [navy] │
│                                       │ [+ Add to cohort]      [teal-bd] │
│                                       │ Sample = preview tier (free).    │
├───────────────────────────────────────┴───────────────────────────────────┤
│ FOOTER (same as S-1 + SaMD disclaimer ko/en)                             │
└───────────────────────────────────────────────────────────────────────────┘
```

### 9.3 S-3 account.html

```
┌───────────────────────────────────────────────────────────────────────────┐
│ NAV  R RadiVault  [PIPA chip]      Search Cohorts Orders Docs  EN│한 [AC]│
├───────────────────────────────────────────────────────────────────────────┤
│ ┌─ Profile (full) ────────────────────────────  [PREVIEW TIER amber]  ─┐ │
│ │ acme-ai · signed in just now                                           │ │
│ │ Buyer ID  Email          Tier              Member since               │ │
│ │ b_4f2a..  dana@acme...   Preview self-srv  2026-04-12                 │ │
│ │ ⚠ Preview = search + sample (10 inst). Full delivery → contract.       │ │
│ └────────────────────────────────────────────────────────────────────────┘ │
│ ┌─ API key (full) ─────────────────────────  [Rotate] [Reveal once]   ─┐ │
│ │ rv_live_••••••••3kF8a2                                  [Copy]        │ │
│ │ ┌── tabs ── curl  Python  Postman ──┐                                  │ │
│ │ │  curl -X POST .../search/studies   │                                  │ │
│ │ │   -H "Authorization: Bearer ..."   │                                  │ │
│ │ └────────────────────────────────────┘                                  │ │
│ └────────────────────────────────────────────────────────────────────────┘ │
│ ┌─ Usage (left) ─────────────┐  ┌─ Recent activity (right) ──────────┐   │
│ │ Today                       │  │ 12:42 SEARCH    kcd:I20.9 250 hits │   │
│ │  Sample dl  ▱▱▱   0/1       │  │ 12:38 DOWNLOAD  ...HOSP1.7392 12MB │   │
│ │  Search    ▰▱▱  36/250      │  │ 12:35 SEARCH    modality:CT 412    │   │
│ │ This month                  │  │ 11:58 KEY       api revealed       │   │
│ │  Sample dl ▰▱▱   7/30       │  │ 11:52 SEARCH    SEOUL-A 142        │   │
│ │  Cohort   ▰▰▱   3/5         │  │                       Full log →    │   │
│ └─────────────────────────────┘  └─────────────────────────────────────┘   │
│ ┌─ Onboarding · 5 steps (full)  3/5 complete ──────────────────────────┐ │
│ │ ✓ 1. Account created (preview)                                          │ │
│ │ ✓ 2. Email verified                                                     │ │
│ │ ✓ 3. API key revealed                                                   │ │
│ │ ○ 4. First sample download                                              │ │
│ │ ○ 5. Build first cohort (≥10)                                           │ │
│ └────────────────────────────────────────────────────────────────────────┘ │
│ ┌─ Danger zone (red) ──────────────────────────────────────────────────┐ │
│ │  Revoke API key  · 401 immediate                          [Revoke]    │ │
│ │  Delete account  · audit retained 5y per PIPA              [Delete…]  │ │
│ └────────────────────────────────────────────────────────────────────────┘ │
├───────────────────────────────────────────────────────────────────────────┤
│ FOOTER (same)                                                             │
└───────────────────────────────────────────────────────────────────────────┘
```

### 9.4 S-0 index.html (가이드)

```
┌───────────────────────────────────────────────────────────────────────────┐
│ NAV  R RadiVault   Guide  Search  Detail  Account               EN│한    │
├───────────────────────────────────────────────────────────────────────────┤
│  RadiVault Buyer UX v2 — Anti-Segmed Redesign                             │
│  v1 was too close to Segmed. v2 differentiates on 4 axes.                │
│                                                                            │
│  ┌── S-1 Search ──┐  ┌── S-2 Detail ──┐  ┌── S-3 Account ──┐             │
│  │ vertical acc.  │  │ De-ID Chain    │  │ tier-aware       │             │
│  │ KCD/SNOMED/    │  │ longitudinal   │  │ reveal-once      │             │
│  │ RadLex auto.   │  │ patient timeln │  │ quota / audit    │             │
│  └────────────────┘  └────────────────┘  └──────────────────┘             │
│                                                                            │
│  WHY V2 IS NOT SEGMED — 5 axes table                                      │
│  ┌─────────┬─────────────┬──────────────┬──────────────┐                 │
│  │ Axis    │ Segmed       │ v1 mistake    │ v2           │                 │
│  │ Color   │ #2563EB      │ #2563EB (=)   │ #0B2545+teal │                 │
│  │ Layout  │ pill chips   │ pill chips    │ accordion+   │                 │
│  │ ...                                                                      │
│                                                                            │
│  10-item visual diff table                                                 │
│  RadiVault 5 strengths · screen mapping table                              │
│  v1 → v2 changelog (5 items)                                               │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 10. 상태 처리 (전수)

| 화면 | loading | empty | error | no-permission | partial-failure |
|---|---|---|---|---|---|
| **S-1** | result row 스켈레톤 8개 + cohort drawer count "—" | 일러스트 + "Adjust filters" + "Try TCIA seed" CTA 2개 | 결과 영역 inline error card + retry · facet 영역 정상 | "Preview tier — upgrade for contract data" banner 결과 위 | hero strip "1 of 2 hospitals reachable" + amber dot, miss 병원 카운트 "—" |
| **S-2** | viewer dark + spinner + "Loading DICOM…" · 메타 카드 스켈레톤 · De-ID stepper "verifying…" | "Study not found" + 검색으로 돌아가기 CTA | viewer "Failed to load · retry" · 메타·De-ID 는 정상 노출 | viewer 영역 lock icon + "Contract required" + Sample 버튼 disabled · Audit chain 노출 유지 (신뢰 신호) | De-ID step 1~3 done, 4 amber spinner, 5 pending. status footer "verification in progress" |
| **S-3** | profile 카드 스켈레톤 · API key "loading…" | (해당 없음, 신규 가입 즉시 채움) | quota gauge "—" + retry · audit list inline error | (Preview tier 자체가 본 화면 default, 권한 없음 케이스 없음) | usage gauge 일부 metric "—" |
| **S-0** | 정적 페이지 (해당 없음) | — | — | — | — |

---

## 11. 반응형·디바이스

- **데스크톱 (1280+)**: 기본. 좌 sidebar 320 / 우 cohort drawer 360 / 우측 rail 380 모두 full.
- **랩톱 (1024-1279)**: sidebar 280 으로 축소, cohort drawer 320, viewer 영역 우선.
- **태블릿 (768-1023)**: sidebar collapse-by-default (햄버거), cohort drawer 가 bottom bar 로 축소 (높이 56px).
- **모바일 (320-767)**: dev-spec-portal-redesign FR-BP-3 의 buyer 포털 정책상 데스크톱 우선이므로 mobile fallback 은 "Open on desktop for full experience" 안내 페이지만 제공. (researcher 권고: 구매자 포털 = 데스크톱 우선)

근거: dev-spec-portal-redesign §3 In-scope 5 항목 — buyer 포털 i18n 토큰만 예약, 모바일 비대상.

---

## 12. 접근성

- **키보드 탐색**: nav → subbar 검색 input → autocomplete (↑↓ Enter) → facet accordion (Tab/Space toggle) → result row (Enter→detail, T → cohort) → cohort drawer (Tab cycle).
- **스크린리더**: `<aside aria-label="Filters">`, `<aside aria-label="Cohort drawer">`, `<main>`, `<nav>`. 모든 icon-only 버튼에 `aria-label` ("Pan", "Zoom", "Reveal API key once").
- **포커스 트랩**: 모달 (audit log full / API key reveal / delete confirm) 은 `<dialog>` 또는 `inert` 처리.
- **색 대비**: 본문 `--rv-stone-700` on `--rv-stone-50` = 9.34:1 (AA pass). primary CTA 흰색 on `#0B2545` = 13.0:1. teal `#14B8A6` on white 는 hover 한정 사용 (3.1:1, AA fail). 본문 텍스트로 사용 금지 → teal 은 항상 배지/액센트만.
- **Focus ring**: `:focus-visible { outline: 2px solid var(--rv-teal-500); outline-offset: 2px; }`.
- **모션**: accordion expand/collapse 0.2s ease, modal fade 0.15s. `prefers-reduced-motion` 시 transition 0.

---

## 13. 국제화

- **언어**: ko / en. 토글 `<button data-set-locale>`. `<body data-locale="en|ko">` + CSS attr selector 로 즉시 swap (페이지 새로고침 X).
- **폰트 스왑**: `body[data-locale="ko"] { font-family: var(--font-ko); }` → Pretendard 자동.
- **카피 길이**: 한국어가 영문 대비 평균 30% 짧음. 결과 row 의 hospital badge / KCD chip / 모달리티 dot 모두 길이 변동에 강함. 단 onboarding checklist 4·5 항은 한글이 더 길 수 있어 line-height 1.55 로 줄바꿈 허용.
- **숫자·날짜**: `YYYY-MM-DD` 통일. 인스턴스 카운트는 mono font 로 정렬 우선. 용량 단위 ko 도 "MB" 그대로 (일반 표준).
- **Audit hash**: 프리픽스 4자 + ellipsis (예 `a3f0…`) — 모노폰트, 언어 무관.

---

## 14. 인터랙션 패턴 (vanilla JS)

| 패턴 | 구현 |
|---|---|
| 언어 토글 | `body.dataset.locale = 'ko'` → CSS `[data-locale="ko"] .en { display:none }` |
| Accordion expand/collapse | `.accordion__group` 클릭 시 `.is-open` 토글, body display swap |
| KCD autocomplete | search input `focus`/`input` 시 dropdown open, 클릭 시 input value 채움 + close |
| Modality dot | 정적 (CSS class 만), 동적 색은 `mod-dot--{ct,mr,...}` |
| Hospital badge | 정적 클래스 + tooltip은 `title` 속성 |
| De-ID stepper | 정적 (mockup). 실 구현 시 step status 별 class swap |
| Audit modal | `<div id="auditModal">` display none → flex 토글 |
| API key reveal-once | 첫 클릭 시 mask → plaintext, 버튼 disabled + opacity 0.5 |
| Tabs (curl/Python/Postman) | 클릭 시 `is-active` swap, panel display swap |
| Copy button + toast | `navigator.clipboard.writeText` + `<div>` toast 1.8s |
| Cohort drawer count | (mockup) 정적. 실 구현 시 sessionStorage 동기화 |

---

## 15. 수용 기준 (시각·행동)

- [ ] 4 mockup 모두 Chrome 1280×800 desktop 에서 layout 시안 ASCII §9 와 일치.
- [ ] 메인 컬러 hex grep 검사: `#2563EB` 0회 등장 (anti-Segmed).
- [ ] Pretendard CDN 로드 확인 (한글 페이지에서 시각적으로 산세리프 한글).
- [ ] 언어 토글 EN ↔ KO 모든 카피 swap (누락된 `.en` / `.ko` 0건).
- [ ] 결과 row 마다 hospital badge + 4px stripe + audit hash chip 3 요소 모두 노출.
- [ ] study-detail 첫 진입 시 De-ID Chain stepper default 노출 (collapse 시작 금지).
- [ ] KCD autocomplete dropdown 에서 한·영·코드 3 컬럼 모두 표시.
- [ ] 색 대비 본문 4.5:1, primary CTA 4.5:1 모두 충족.
- [ ] 외부 의존성: Google Fonts (Inter) + jsdelivr (Pretendard) CDN 만, 그 외 0.
- [ ] `file://` 더블클릭으로 4 파일 모두 작동.
- [ ] vanilla JS 만 사용, React/Next/jQuery 0건.

---

## 16. dev-spec 영향

| 영향 받는 dev-spec | 변경/추가 사항 |
|---|---|
| `dev-spec-portal-redesign.md` | (a) FR-BP-3 검색 3-pane → 2-col asymmetric 으로 갱신. (b) FR-BP-7 hospital_opaque_id 표시 → region pseudo-brand badge 정책 추가. (c) FR-HP-9/-10 footer 컴플라이언스 배지 navy 톤 적용. (d) 디자인 토큰 §4 에 navy + teal 추가. |
| 신규 `dev-spec-deid-chain-buyer-view.md` | study-detail 우측 영구 De-ID Chain stepper API · audit hash 노출 정책 · WORM 5y 보존 연계. |
| 신규 `dev-spec-ontology-search-snomed-kcd-radlex.md` | KCD-8 + SNOMED + RadLex 트리플 ontology 자동완성 endpoint · 한·영 동시 응답 스키마 · ranking. |
| `dev-spec-metadata-index.md` | SearchResponse 에 `patient_pseudo_id` 추가 (longitudinal timeline 필요). `audit_hash_prefix` (4자) 추가. `hospital_region` 필드 추가 (SEOUL/BUSAN/DAEGU). |
| `dev-spec-buyer-auth.md` | account 페이지 quota gauge / audit list / 5단계 onboarding checklist FR. preview tier 정책 (1 sample/day, 250 search/day) 정식화. |
| `docs/UI_GUIDE.md` | 본 §8 신규 토큰 (navy 5단·teal 4단·amber 2단·stone 5단·modality 6색·layout 3폭·radius 3) Kyle 승인 후 정식 편입. |

---

## 17. 오픈 질문 / Kyle 결정 필요

1. **신규 dev-spec 분리 여부** — `dev-spec-deid-chain-buyer-view`, `dev-spec-ontology-search-snomed-kcd-radlex` 를 별도 slug 으로 갈지, 기존 `dev-spec-portal-redesign` v0.2 에 포함할지.
2. **Region 명칭** — "SEOUL-A" / "BUSAN-B" 가명. 추후 병원 추가 시 명명 규칙 (city-letter 만? hospital-tier 도?) 확정 필요.
3. **Audit hash 노출 형식** — 현 4자 prefix (`a3f0…`). 8자 또는 full 32자 노출 필요 여부.
4. **Pretendard 라이선스 확인** — OFL, 상업용 OK 이나 사내 정책 재검토 권고.
5. **Preview tier 한도 수치** — 1 sample/day · 250 search/day 를 mockup 에 박았음. dev-spec 정식화 시 변경 가능?
6. **Patient longitudinal — 한 환자 ID 가 cross-hospital 일 가능성** — 현 mockup 은 "all 4 from SEOUL-A". cross-hospital token 매칭 (Datavant 유사) 은 v0.2 backlog 로 보임. 확정 필요.
7. **3D defacing 적용 정책** — chest CT 의 경우 "skipped (not applicable)" 로 표시. 표시 어휘 ("skipped" vs "n/a" vs "skipped — body part not head") Kyle 결정.
8. **Trust Center 링크 destination** — 현 `#` placeholder. 별도 route (`/trust`) 신설 vs 외부 (Vanta/Drata 호스팅) vs 자체 페이지.

---

## 18. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|---|---|---|---|
| 0.1 | 2026-04-25 | @designer (Claude Opus 4.7 [1M]) | 최초 작성. v1 → v2 4축 차별 + segmed deep-dive §6 directives 1:1 매핑 + 4 mockup 신규 (`mockups/buyer-ux-v2/v2/`) + 신규 토큰 5개군 + 컴포넌트 13개 + Kyle 결정 4개 default 채택 (navy+teal · region badge · De-ID default · preview-tier sign-up). |

---

### NEXT_STEP

- 완료 산출물:
  - `docs/specs/design-spec-buyer-ux-v2.md` (본 문서)
  - `docs/specs/mockups/buyer-ux-v2/v2/{index,search,study-detail,account}.html` + `styles.css` (v1 보존, 신규 디렉토리)
- 제안 다음 단계: **메인 세션이 본 v2 mockup + spec 을 Kyle 에게 시연 → 채택 결정 → 채택 시 `@planner` 호출하여 §17 Q1 (신규 dev-spec 분리) 결정 후 dev-spec 작성**.
- UI_GUIDE.md 갱신 제안: 본 §8 신규 토큰 (navy 5 + teal 4 + amber 2 + stone 5 + modality 6 + layout 3) Kyle 승인 후 정식 편입.
- 추가 디자인 필요: 채택 시 hospital console / operator console 도 본 navy+teal 토큰으로 정렬할지 별도 결정 (dev-spec-portal-redesign 트랙 3 영향).
- Kyle 결정 필요 사항: §17 Q1~Q8 8 개.
