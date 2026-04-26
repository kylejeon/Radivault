# 디자인 명세 — Buyer UX v3 (Dense list redesign)

> **Status**: Draft v0.1 · **Feature slug**: `buyer-ux-v3` · **Last updated**: 2026-04-25
> **작성자**: @designer (Claude Opus 4.7 [1M])
> **본 문서가 대체**: `design-spec-buyer-ux-v2.md` 의 §9.1 search 와 §9.2 study-detail. v2 파일은 보존(추후 비교용), 본 v3 가 현재 권고.
> **근거**:
> - Kyle 직접 평가 (2026-04-25): "search 에서 썸네일 이미지는 필요없어. 오히려 속도 저하와 리스트가 적게 보여서 별로야" / "각 검사마다 더 보여줄 값을 추가해줘" / "openda 링크 보내줬자나. 좀 참고해서 잘좀 해봐" / "리스트에서 view를 클릭했을 때, de-id chain은 왜 보여주는거야? 구매자에게 구매시 필요한 정보가 아닌거 같은데?"
> - dev-spec: [`dev-spec-portal-redesign.md`](./dev-spec-portal-redesign.md) — FR-BP-3 / FR-BP-4 / FR-BP-7 / FR-BP-8
> - 리서치 1차: [`segmed-openda-deep-dive.md`](../research/segmed-openda-deep-dive.md) — Segmed Openda 의 dense list / admin-only De-ID / SNOMED autocomplete
> - 리서치 1차: [`metadata-extraction-and-thumbnail.md`](../research/metadata-extraction-and-thumbnail.md) — TCIA + IDC facet 8 필드 교집합, MVP 12 필드, v0.1.5 6 필드
> - v2 보고서 (보존): [`design-spec-buyer-ux-v2.md`](./design-spec-buyer-ux-v2.md)
> - v2 mockup (anti-pattern): `mockups/buyer-ux-v2/v2/{search,study-detail}.html`
> - v3 mockup (본 명세 구현): `mockups/buyer-ux-v2/v3/{index,search,study-detail,account}.html` + `styles.css`
> - UI Guide: [`UI_GUIDE.md`](../UI_GUIDE.md) — v2/v3 토큰은 §6 Kyle 승인 후 정식 편입

> **본 문서의 위치**: v2 mockup 의 두 판단 잘못을 시정한다. ① **search 결과의 썸네일 96px 카드 → 썸네일 0의 dense table 11 컬럼 25 행** (Segmed Openda 정석 흡수, 단 hospital stripe + region badge 로 차별 보존). ② **study-detail 우측 sticky De-ID Chain stepper → footer collapsible "Compliance & audit"** (Segmed 가 admin-only 로 두는 이유와 동일 — buyer 구매 의사결정과 무관, 행정 정보로 격하). 동시에 study-detail 의 rich metadata (Acquisition / Pixel / Quality metrics / Series mini-cards) 를 신규로 도입해 **buyer 가 AI 학습 적합성을 판단할 수 있는 정보** 를 보강.

---

## 1. 디자인 개요

RadiVault buyer-side 검색·상세를 **데이터 밀도 우선 + buyer 의사결정 정보 우선** 으로 재설계한다. v2 의 anti-Segmed 시각 시그니처(navy/teal · Pretendard · vertical accordion · hospital region badge · KCD/SNOMED/RadLex 트리플 ontology · PIPA/정통망법 footer)는 모두 보존하되, **결과 리스트 정보 밀도** 와 **상세 페이지 메타데이터 풍성도** 두 영역에서 Segmed Openda 의 dense table 정석을 흡수한다. De-ID chain 은 행정 정보로 격하하여 footer 에 collapse 한다.

---

## 2. v2 → v3 변경 (5축)

| 축 | v2 (이전) | v3 (현재) | 근거 |
|---|---|---|---|
| **A1. 리스트 밀도** | card row · 96 px thumbnail · 8 visible · ~140 px row height | dense table · NO thumbnail · 25 visible · 52 px row height | Kyle: "썸네일은 속도 저하 + 리스트 적게 보임". Segmed Openda 도 썸네일 없음. |
| **A2. 행당 정보** | ~7 fields · narrative meta (`F·54 312 inst SIEMENS 2024-08`) | 11 columns · grid (Hospital · Modality · Body · KCD · Patient · Mfg/Model · Date · Series/Inst · Size · UID · View) | Buyer 가 다수 study 빠르게 비교 — column 단위 시야 효율. |
| **A3. De-ID 체인** | sticky right-rail · default 노출 (5단계 + audit hash) | footer 격하 · `<ComplianceCollapse>` collapsed by default · "5/5 verified" 1줄 신뢰 신호만 노출 | Kyle: "buyer 의사결정에 De-ID detail 불필요". Segmed admin-only 정책 흡수. 단 **완전 숨김이 아니라 collapse → expand** — buyer 가 원할 때 검증 가능. |
| **A4. 상세 메타** | Patient/Study/Series/device 9 필드 | + Acquisition (KVP·mAs·contrast / MR field strength) + Pixel/spatial + Quality metrics 카드 = **14 필드** | Buyer 가 AI 학습 적합성 (acquisition param·resolution·completeness) 판단에 필수. metadata-extraction 리서치 §4.1.7 수치형 facet + §4.2.4 series-level. |
| **A5. Longitudinal** | 1줄 timeline · 날짜만 | + 병원 (각 단계) + current marker(teal) + "n prior · n follow-up" 캡션 | Segmed 의 patient grouping 차별 (Openda 미시각화) 강화. |

---

## 3. Segmed Openda 흡수 vs 차별 보존 (5 항목)

| # | 흡수한 것 | v3 위치 | 차별 보존 |
|---|---|---|---|
| 1 | **Dense table 리스트 (썸네일 없음)** | search.html `<ResultTable>` | 행마다 4 px **hospital stripe** + **region badge** (Segmed 둘 다 없음) |
| 2 | **Sortable column header** | search.html — 9 컬럼 정렬 가능 | 컬럼 라벨 한·영 동시 + KCD chip 컬럼 (RadiVault 만) |
| 3 | **Customize columns 토글** | search.html "Show columns ▾" | v0.1.5 advanced col (slice thickness · KVP · MR field) future-enable 표기 — 점진 노출 |
| 4 | **De-ID 를 buyer 화면에서 숨김** | study-detail.html footer collapse | RadiVault 는 **숨기지 않고 격하** (collapse → expand). Segmed 완전 숨김과 차별. 신뢰 사다리 보존. |
| 5 | **Rich metadata cards (Acquisition + Pixel)** | study-detail.html right rail | **PIPA consent provenance + IRB 번호** 추가 (RadiVault 만) — audit info 카드. |

---

## 4. 화면 목록

| ID | 화면명 | 경로 (목업) | 주요 역할 |
|----|---|---|---|
| S-0 | Guide / Index | `mockups/buyer-ux-v2/v3/index.html` | v2→v3 차별 표 + 화면 링크 + 컴포넌트 인벤토리 |
| S-1 | Search & Cohort | `mockups/buyer-ux-v2/v3/search.html` | dense table 11 컬럼 25 행 + 좌측 facet accordion + cohort drawer |
| S-2 | Study Detail | `mockups/buyer-ux-v2/v3/study-detail.html` | viewer + slice slider + rich metadata + longitudinal + footer compliance collapse |
| S-3 | Account | `mockups/buyer-ux-v2/v3/account.html` | profile · API key · quota · audit · onboarding (v2 그대로) |

---

## 5. 사용자 플로우

### 5.1 Happy path — buyer 가 dense list 에서 25 행 스캔 → AI 학습용 study 선택

```
[로그인 직후] → S-1 (검색)
   ↓ KCD autocomplete "협심증" 선택 (KCD/SNOMED/RadLex 3 결과)
[결과 250건 노출 — 25 행 dense table, hospital stripe 다중 색]
   ↓ "Date ↓" 정렬 확인 (default), "Show columns ▾" 에서 KVP 활성화
[KVP 컬럼 추가 노출 — CT 행만 값 표시]
   ↓ row3 "View →" 클릭
S-2 (study detail)
   ↓ 우측 rail 에서 Quality metrics 확인 (98% completeness, slice 1.0 mm)
   ↓ Acquisition 카드에서 SIEMENS SOMATOM Drive · 120 kV · 220 mAs 확인
   ↓ "Sample download (ZIP)" — preview tier 무료
[ZIP 1 slice DICOM 다운로드 토스트]
   ↓ "Add to cohort" 클릭
[cohort drawer 카운트 +1]
```

### 5.2 권한 없음 — preview tier 가 contract-only study 시도

```
[S-1 결과 row 중 "🔒 contract-only" 배지된 row 클릭]
S-2 viewer placeholder + "Contract required" 오버레이
→ 우측 sticky CTA 가 "Sample download" 비활성 + "Request contract upgrade" primary
→ 안내문: "PIPA §28-8 expert determination 에 따라 계약이 필요합니다"
```

### 5.3 에러 — autocomplete API 500

```
[S-1 검색 입력]
   ↓ 트리플 ontology API 500
[autocomplete dropdown 회색 박스 + "ontology temporarily unavailable · search by free text"]
→ free-text 검색은 그대로 작동, KCD chip 매칭만 비활성
```

### 5.4 부분 실패 — 한 병원만 응답

```
[S-1 검색]
   ↓ SEOUL-A OK, BUSAN-B timeout
[results header "250 → 142 / partial: 1 of 2 hospitals" + amber dot]
[BUSAN-B facet count 자리 "—" + tooltip "BUSAN-B unreachable, retrying"]
```

### 5.5 행정 정보 확인 — 구매 후 De-ID chain 검증

```
[S-2 study detail · 구매 완료 study]
→ 페이지 footer "Compliance & audit ▾" trust bar (5/5 verified) 보임
→ 클릭 → expand
→ De-ID 5 단계 stepper (a3f0… b71c… c08f… d92a… e51b…) 각 hash 노출
→ Audit info: IRB #2024-0388 · broad consent · WORM 5y · chain continuous 3,824 events
```

---

## 6. 디자인 토큰 (v3 — v2 보존 + 신규 3)

> **Status**: 제안. UI_GUIDE.md 정식 등록은 Kyle 승인 후. **v2 토큰 모두 그대로 유지**, 본 v3 는 dense table 전용 3 토큰만 신규.

### 6.1 신규 (v3)

| 토큰 | 값 | 용도 |
|---|---|---|
| `--rv-row-h` | `52px` | dense list row 높이 (default) — v2 카드 ~140 px 대비 약 1/3 |
| `--rv-row-h-sm` | `44px` | compact 모드 (toggle) |
| `--rv-table-zebra` | `rgba(15, 23, 42, 0.018)` | 짝수 행 미세 zebra striping (가독성) |
| `--rv-table-divider` | `#EDECEA` | row 간 구분선 (stone-200 보다 옅음) |
| `--rv-col-stripe-w` | `4px` | per-row hospital stripe 너비 (v2 stripe 보존) |

### 6.2 보존 (v2 그대로)

- 컬러: `--rv-navy-{900,800,700,500,100}` · `--rv-teal-{700,500,300,100}` · `--rv-amber-{600,500,100}` · `--rv-stone-{50,100,200,300,400,500,600,700,900}`
- modality dot: `--mod-{ct,mr,mg,cr,us,pt}` 6 색
- 폰트: `--font-en` Inter / `--font-ko` Pretendard / `--font-mono` JetBrains Mono
- 레이아웃: `--rv-sidebar-w 320px` / `--rv-rightbar-w 380px` / `--rv-cohort-drawer-w 360px`
- 라디우스: `--radius-{sm 4, md 6, lg 10}`
- 그림자: `--shadow-{card, pop}`

---

## 7. 와이어프레임 (ASCII, 4 화면)

### 7.1 S-1 search.html (dense table)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ NAV [navy bg]  R RadiVault  [PIPA chip]   Search Cohorts Orders Docs   EN│한 [acme-ai]│
├────────────────────────────────────────────────────────────────────────────────────────┤
│ SUB [🔍 협심증 / Angina / I20 _____________ ]  [Save] [Search]                          │
│     ┌─ AUTOCOMPLETE (KCD/SNOMED/RadLex 트리플) ──────────────────────────────┐        │
│     │ I20.9      협심증, 상세불명     Angina pectoris        [KCD-8]          │        │
│     │ 194828000  협심증 (안정형)      Angina (disorder)      [SNOMED]         │        │
│     │ RID3501    관상동맥 (해부)      Coronary artery        [RadLex]         │        │
│     └────────────────────────────────────────────────────────────────────────┘        │
├────────────────────┬───────────────────────────────────────────────────────────────────┤
│ SIDEBAR (320px)    │ RESULTS                                                            │
│ vertical accordion │ 250 studies · 38 ms · across 2 hospitals    [Sort: Date ↓] [▾Cols]│
│                    │ ─────────────────────────────────────────────────────────────────  │
│ ▾ 데이터 출처      │ ░ ☐ HOSP   MOD  BODY    KCD/Dx              PT      MFG·MODEL  DATE   SR·INST  SIZE   UID    │
│   ☑ ●SEOUL-A 142   │ ─────────────────────────────────────────────────────────────────  │
│   ☑ ●BUSAN-B 108   │ █ ☐ SEOUL-A ●CT CHEST  [I20.9] 협심증…       F·50-54 SIEMENS·SOMATOM Drive 2024-08  3·312  478MB …a3f0  [View→]│
│   ☐ ●DAEGU-C —     │ █ ☐ BUSAN-B ●MR CHEST  [I20.9] 협심증…       M·45-49 PHILIPS·Ingenia 3.0T  2024-09  5·188  312MB …9c1e  [View→]│
│   ☑ De-ID verified │ █ ☐ SEOUL-A ●CT HEAD   [I63.9] 뇌경색…        F·60-64 SIEMENS·TrioTim       2024-08  3·245  480MB …b71c  [View→]│
│ ▾ 임상 정보        │ █ ☐ BUSAN-B ●CT CHEST  [I25.1] 관상동맥경화   M·55-59 GE·Revolution CT      2024-08  4·412  680MB …c08f  [View→]│
│   KCD ☑ I20.9 38   │ █ ☐ SEOUL-A ●MR HEAD   [I63.9] 뇌경색…        F·65-69 SIEMENS·Skyra 3.0T    2024-07  6·524  920MB …d92a  [View→]│
│   KCD ☐ I25.1 21   │ █ ☐ BUSAN-B ●CR CHEST  [J18.9] 폐렴…          F·70-74 CANON·CXDI-720C       2024-07  1·2     8MB …e51b  [View→]│
│   부위:흉부 112    │ █ ☐ SEOUL-A ●MG BREAST [C50.9] 유방암         F·50-54 HOLOGIC·Selenia Dim. 2024-07  2·8   128MB …7b22  [View→]│
│   부위:두부 58     │ █ ☐ BUSAN-B ●CT ABDOMEN[K85.9] 급성 췌장염   M·50-54 GE·Revolution CT      2024-07  4·368  560MB …1f4d  [View→]│
│ ▾ 환자 정보        │ █ ... 17 more rows ...                                              │
│   F 128 / M 122    │                                                                    │
│   40-49 ☑ 50-59☑   │                            ┌─ COHORT DRAWER ──┐                    │
│ ▾ 영상 기술        │                            │ 3 in cohort       │                    │
│   ●CT 98           │                            │ 2 hosp · 756 inst │                    │
│   ●MR 62           │                            │ 412 MB            │                    │
│   ●CR 48           │                            │ [Save] [Order →] │                    │
│   slice ≤1.5mm 82  │                            └───────────────────┘                    │
│ ▸ 시간             │ ──────────────────────────────────────────────────────────────────  │
│                    │ Showing 1-25 of 250 · 25 rows/page    ‹ 1 2 3 4 … 10 ›             │
├────────────────────┴───────────────────────────────────────────────────────────────────┤
│ FOOTER [stone-900]  ●PIPA §28-8  ●정통망법  ●KCD-8  ●MoH HIRA       Trust Center ↗     │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 S-2 study-detail.html (rich metadata + footer collapse)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ NAV  R RadiVault  [PIPA]  Search Cohorts Orders Docs        EN│한 [acme-ai]            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ SUB [← Back] [SEOUL-A] [I20.9] ●CT · 1.2.840.HOSP1.7392.20240815.001    ← Prev 3/250 → │
├──────────────────────────────────────────────┬─────────────────────────────────────────┤
│ VIEWER (dark)                                │ RIGHT RAIL                              │
│  ┌─ overlay TL ─ SEOUL-A·CT·WW350/WL50 ─┐   │ ─ Data quality ─────────── v0.1.5 ──    │
│  │ overlay TR: SIEMENS SOMATOM Drive     │   │ ┌──────────────┬──────────────┐         │
│  │             2024-08-15 · kVp 120     │   │ │ Image count  │ Slice thck   │         │
│  │ ◉ tools (pan/zoom/wl/measure)        │   │ │ 312          │ 1.0 mm       │         │
│  │ ╭─ chest CT placeholder ─╮          │   │ │ 3 series     │ range 1.0-2.5│         │
│  │ │   [synthetic image]    │          │   │ ├──────────────┼──────────────┤         │
│  │ ╰────────────────────────╯          │   │ │ Resolution   │ Completeness │         │
│  │ overlay BL: F·50-54 PT-7392-A        │   │ │ 512×512      │ 98% ✓        │         │
│  │ overlay BR: ▣ De-ID a3f0…           │   │ │ 0.69 mm/px   │ 12/12 fields │         │
│  └──────────────────────────────────────┘   │ └──────────────┴──────────────┘         │
│  [────────●───── slice 156/312 ─────────]  │ ─ Metadata ──────── DICOM tags ↗ ──     │
│  Display only — not for diagnostic use      │ ┌─ Patient ───────────────────┐         │
│                                              │ │ Pseudo ID  PT-7392-A         │         │
│                                              │ │ Sex        F                 │         │
│                                              │ │ Age        50-54             │         │
│                                              │ │ Consent    PIPA §28-8         │         │
│                                              │ └──────────────────────────────┘         │
│                                              │ ┌─ Study ─────────────────────┐         │
│                                              │ │ Date(shifted) 2024-08-15     │         │
│                                              │ │ Modality      ●CT            │         │
│                                              │ │ Body part     CHEST          │         │
│                                              │ │ Description   Chest CT…      │         │
│                                              │ └──────────────────────────────┘         │
│                                              │ ┌─ Series ──────── 3·312 inst ┐         │
│                                              │ │ ① Topogram        CT 1.0  2  │         │
│                                              │ │ ② Pre-contrast    CT 1.0 155│         │
│                                              │ │ ③ Post-contrast   CT 1.0 155│         │
│                                              │ └──────────────────────────────┘         │
│                                              │ ┌─ Acquisition ───────────────┐         │
│                                              │ │ Manufacturer  SIEMENS        │         │
│                                              │ │ Model         SOMATOM Drive  │         │
│                                              │ │ KVP (CT)      120 kV         │         │
│                                              │ │ Tube current  220 mAs        │         │
│                                              │ │ Contrast      Iohexol 350    │         │
│                                              │ └──────────────────────────────┘         │
│                                              │ ┌─ Pixel & spatial ───────────┐         │
│                                              │ │ PhotomtrInterp MONOCHROME2  │         │
│                                              │ │ PixelSpacing   0.69 / 0.69  │         │
│                                              │ │ FrameOfRef     1.2.840…7392 │         │
│                                              │ └──────────────────────────────┘         │
│                                              │ ─ Related (longitudinal) PT-7392-A ─    │
│                                              │  CR ─ CT ─ ◉CT ─ MR                     │
│                                              │ 22-03 23-06 24-08 25-01                 │
│                                              │  SEOUL-A · all 4                         │
│                                              │ ─────────────────────────────────       │
│                                              │ [⬇ Sample download (ZIP)]   [navy]      │
│                                              │ [+ Add to cohort]      [teal-bd]        │
│                                              │ Sample = 1 representative slice DICOM,  │
│                                              │ preview tier · free.                    │
├──────────────────────────────────────────────┴─────────────────────────────────────────┤
│ ▾ ✓ 5/5 De-ID stages verified · Compliance & audit (administrative — view post-purchase)│  ← collapsed by default
│   [click → expands to De-ID stepper + audit info IRB/consent/WORM]                      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ FOOTER (PIPA §28-8 · 정통망법 · KCD-8 · MoH HIRA · Trust Center ↗)                     │
│ SaMD disclaimer (ko/en)                                                                │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 7.3 S-3 account.html

v2 그대로 유지 (Kyle 명시 — 이번 변경 0). v2 명세 §9.3 와 동일.

### 7.4 S-0 index.html (가이드)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ NAV  R RadiVault   Buyer UX v3 — dense list redesign            Search Detail Account│
├────────────────────────────────────────────────────────────────────────────────────────┤
│ RadiVault Buyer UX v3 — Dense list redesign                                            │
│ v2 was too low-density and over-emphasized De-ID provenance to buyers.                 │
│                                                                                         │
│ ┌── S-1 Search ──┐ ┌── S-2 Detail ──┐ ┌── S-3 Account ──┐                              │
│ │ dense 25 rows  │ │ rich metadata   │ │ identical to v2 │                              │
│ │ 11 cols · sort │ │ De-ID footer ▾  │ │                 │                              │
│ │ NO thumbnail   │ │ longitudinal+   │ │                 │                              │
│ └────────────────┘ └────────────────┘ └─────────────────┘                              │
│                                                                                         │
│ "What changed from v2" — 5 axes table                                                  │
│ "What v3 absorbs from Segmed Openda" — 5 patterns table                                │
│ Component inventory — NEW · CHANGED · REMOVED · PRESERVED                              │
│ Result table column spec (11 visible + 4 toggle)                                       │
│ Study-detail rich metadata fields (14)                                                 │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. 컬럼 정의 표 (search 결과 — 11 + 4 toggle)

| # | Column EN | Column KO | Width | Sortable | Default visible | DICOM tag (impl) |
|---|---|---|---|---|---|---|
| — | (stripe) | (스트라이프) | 4 px | — | always | — (hospital-derived) |
| — | (checkbox) | (선택) | 32 px | — | always | — |
| 1 | Hospital | 병원 | 96 px | YES | YES (locked) | (custom: hospital_region) |
| 2 | Modality | 모달리티 | 72 px | YES | YES | (0008,0060) |
| 3 | Body part | 부위 | 96 px | YES | YES | (0018,0015) |
| 4 | KCD · Diagnosis | KCD · 진단 | min 140 px (1.4fr) | YES | YES | (custom: kcd_8) |
| 5 | Patient (sex · age) | 환자 (성별·연령) | 96 px | YES | YES | (0010,0040) + age_bucket |
| 6 | Manufacturer · Model | 제조사 · 모델 | min 140 px (1.2fr) | YES | YES | (0008,0070) + (0008,1090) |
| 7 | Date | 촬영일 | 80 px | YES (default ↓) | YES | (0008,0020) shifted YYYY-MM |
| 8 | Sr · Inst | 시리즈 · 인스턴스 | 96 px | YES | YES | (derived) |
| 9 | Size | 용량 | 72 px | YES | YES | (derived) |
| 10 | UID (last 6) | UID (말미 6자) | 72 px | YES | YES | (0020,000D) re-gen tail |
| — | View action | 보기 액션 | 72 px | — | YES (hover) | — |
| 11 | Slice thickness | 슬라이스 두께 | — | YES | NO (v0.1.5) | (0018,0050) |
| 12 | KVP (CT) | KVP (CT) | — | YES | NO (v0.1.5) | (0018,0060) |
| 13 | Field strength (MR) | 자기장 (MR) | — | YES | NO (v0.1.5) | (0018,0087) |
| 14 | Audit hash | 감사 해시 | — | NO | NO (collapse) | (custom: audit_hash_prefix) |

**총 grid-template-columns 정의** (CSS): `4px 32px 96px 72px 96px minmax(140px,1.4fr) 96px minmax(140px,1.2fr) 80px 96px 72px 72px 72px` — 13 트랙 (stripe + check + 10 visible col + action).

---

## 9. study-detail rich metadata 필드 (14)

| Card | Field | DICOM tag | MVP / v0.1.5 |
|---|---|---|---|
| **Patient** | Pseudo ID | (0010,0020) re-gen | MVP |
| | Sex | (0010,0040) | MVP |
| | Age bucket (5y) | (0010,1010) bucket | MVP |
| | Consent (PIPA §28-8) | (custom) | MVP |
| **Study** | Date (shifted) | (0008,0020) shift | MVP |
| | Accession (masked) | (0008,0050) | MVP |
| | Description | (0008,1030) | v0.1.5 (Clean Descriptors) |
| | Modality | (0008,0060) | MVP |
| | Body part | (0018,0015) | MVP |
| **Series (×N)** | Title / description | (0008,103E) | v0.1.5 |
| | Modality · slice · resolution | (0008,0060) (0018,0050) (0028,0010) | v0.1.5 |
| | # instances | (derived) | MVP |
| **Acquisition** | Manufacturer | (0008,0070) | MVP |
| | Model | (0008,1090) | MVP |
| | KVP (CT) | (0018,0060) | MVP (CT only) |
| | Tube current (mAs) | (0018,1151) | v0.1.5 |
| | Magnetic field (MR) | (0018,0087) | v0.1.5 |
| | Contrast bolus | (0018,0010) | v0.1.5 |
| **Pixel & spatial** | PhotomtrInterp | (0028,0004) | v0.1.5 |
| | PixelSpacing | (0028,0030) | v0.1.5 |
| | FrameOfReferenceUID prefix | (0020,0052) | v0.1.5 |
| **Quality (NEW)** | Image count | (derived) | MVP |
| | Slice thickness range | (0018,0050) min/max | v0.1.5 |
| | Resolution | (0028,0010)×(0028,0011) | MVP |
| | Completeness score (12-field fill rate) | (derived) | v0.1.5 |

총 4 + 5 + 3 + 6 + 3 + 4 = **25 필드** (시리즈별 정보 포함). Card 단위 14 시각 카드. metadata-extraction 리서치 §3 MVP 12 + v0.1.5 6 = 18 필드를 모두 표면에 노출 + Quality metrics 4 derived 필드 신규.

---

## 10. 컴포넌트 인벤토리

| 상태 | 컴포넌트 | 목적 | 위치 |
|---|---|---|---|
| **NEW** | `<ResultTable>` | Dense sortable result table (11 cols + 2 fixed) | search.html |
| **NEW** | `<ColumnToggle>` | Show/hide column dropdown (advanced cols flagged v0.1.5) | search.html header |
| **NEW** | `<QualityMetricsCard>` | Image count · slice thickness range · resolution · completeness score | study-detail right rail |
| **NEW** | `<AcquisitionCard>` | Modality-specific acquisition (KVP / mAs / MR field / contrast) | study-detail right rail |
| **NEW** | `<SeriesMiniCard>` | Per-series compact row (n series within one card) | study-detail right rail |
| **NEW** | `<PixelSpatialCard>` | PhotometricInterpretation · PixelSpacing · FrameOfReferenceUID | study-detail right rail |
| **NEW** | `<SliceSlider>` | Range slider for viewer slice navigation | study-detail viewer pane |
| **NEW** | `<ComplianceCollapse>` | Collapsible footer wrapping De-ID + audit (default collapsed) | study-detail footer |
| **CHANGED** | `<DeIDChainStepper>` | `props.collapsed` default `true` (was `false`) — context: footer | study-detail footer (was right rail) |
| **CHANGED** | `<LongitudinalTimeline>` | + hospital per-step + current marker (teal) + caption | study-detail right rail |
| **REMOVED** | `<StudyThumbnail>` (search list) | 96×96 dark thumbnail per row | search.html (was result-row) |
| **REMOVED** | `<AuditHashChip>` (search row) | Per-row teal hash chip | search.html (was result-meta__top) |
| **PRESERVED** | `<HospitalBadge>` | Region pseudo-brand (SEOUL-A / BUSAN-B / DAEGU-C / INCHEON-?) | row · header · facet · drawer |
| **PRESERVED** | `<KCDAutocomplete>` | Triple ontology dropdown (KCD/SNOMED/RadLex, ko/en) | search subbar |
| **PRESERVED** | `<PIPATrustBar>` | Header mini + footer compliance pills | all pages |
| **PRESERVED** | `<CohortDrawer>` | Bottom-right sticky cohort stat (3 metric + 2 action) | search.html |
| **PRESERVED** | `<ModalityDot>` | 8 px colored dot per modality (CT/MR/MG/CR/US/PT 6색) | row · facet · viewer overlay |
| **PRESERVED** | `<TabsCodeBlock>` | curl/Python/Postman tabs + copy | account.html |
| **PRESERVED** | `<QuotaGauge>` | Bar fill + count | account.html |
| **PRESERVED** | `<AuditList>` | Recent 5 events row | account.html |
| **PRESERVED** | `<OnboardChecklist>` | 5-step todo | account.html |

---

## 11. 상태 처리 (전수)

| 화면 | loading | empty | error | no-permission | partial-failure |
|---|---|---|---|---|---|
| **S-1** | result table 스켈레톤 25 행 (각 row 회색 grid stripe) + cohort drawer count "—" | 일러스트 + "Adjust filters" + "Try TCIA seed" CTA 2개 | 결과 영역 inline error card + retry · facet 영역 정상 | "Preview tier — upgrade for contract data" banner 결과 위 (전체 row 잠금 없음) | hero strip "Showing 142 / partial: 1 of 2 hospitals" + amber dot, miss 병원 facet count "—" |
| **S-2** | viewer dark + spinner + "Loading DICOM…" · 메타 카드 스켈레톤 · footer "verifying chain…" | "Study not found" + 검색으로 돌아가기 CTA | viewer "Failed to load · retry" · 메타·footer 정상 | viewer 영역 lock icon + "Contract required" + Sample 버튼 disabled · 메타 정상 노출 | De-ID stepper (footer 내) step 1~3 done, 4 amber, 5 pending. footer trust bar "verification in progress" |
| **S-3** | profile 카드 스켈레톤 · API key "loading…" | (해당 없음, 신규 가입 즉시 채움) | quota gauge "—" + retry · audit list inline error | (Preview tier 자체가 본 화면 default) | usage gauge 일부 metric "—" |
| **S-0** | 정적 페이지 (해당 없음) | — | — | — | — |

---

## 12. 반응형·디바이스

dev-spec-portal-redesign FR-BP-3 의 buyer 포털 정책상 **데스크톱 우선**. 본 v3 의 dense table 11 컬럼은 1280 px 이상 가정.

- **데스크톱 (1280+)**: 기본. sidebar 320 / 우측 rail 380 / cohort drawer 360 모두 full.
- **랩톱 (1024-1279)**: sidebar 280 / 우측 rail 340 으로 축소. result table 컬럼 자동 축소 — `Sr·Inst` 와 `Size` 가 우선 hide candidate (column toggle 자동 적용 권고).
- **태블릿 (768-1023)**: sidebar collapse-by-default (햄버거). result table 은 horizontal scroll 허용. 권고: "Open on desktop for full search experience" 미니 안내.
- **모바일 (320-767)**: dev-spec FR-BP-3 정책상 비대상. "Open on desktop for full experience" 안내 페이지만 제공.

근거: dev-spec-portal-redesign §3 In-scope — buyer 포털 i18n 토큰만 예약, 모바일 비대상.

---

## 13. 접근성

- **키보드 탐색**: nav → subbar 검색 input → autocomplete (↑↓ Enter) → facet accordion (Tab/Space toggle) → result table (Tab → row, Enter → detail, Space → checkbox toggle, T → cohort) → cohort drawer.
- **컬럼 헤더 정렬**: `<button role="columnheader" aria-sort="ascending|descending|none">` 시맨틱. 화살표 indicator 는 `aria-hidden`, sort 상태는 `aria-sort` 로 SR 전달.
- **컬럼 토글 dropdown**: `<button aria-expanded aria-controls>` + `<div role="menu">`. 각 항목 `<label><input type="checkbox" /></label>`.
- **Sticky 컬럼 헤더**: `position: sticky; top: 0;` — SR 에는 변경 없음, 시각적 효과만.
- **스크린리더**: `<aside aria-label="Filters">`, `<aside aria-label="Cohort drawer">`, `<main>`, `<nav>`. result table 은 `<div role="table">` + 각 row `<div role="row">` + 각 cell `<div role="cell">`. 모든 icon-only 버튼에 `aria-label`.
- **포커스 트랩**: 모달 (audit log full / API key reveal / delete confirm) 은 `<dialog>` 또는 `inert` 처리.
- **색 대비**: 본문 `--rv-stone-700` on `--rv-stone-50` = 9.34:1 (AA pass). primary CTA 흰색 on `#0B2545` = 13.0:1. teal `#14B8A6` 은 hover 한정 사용 (3.1:1, AA fail) — 본문 텍스트로 사용 금지, 항상 배지/액센트만. KCD chip amber 색 대비 `--rv-amber-600` on `--rv-amber-100` = 5.32:1 (AA pass).
- **Focus ring**: `:focus-visible { outline: 2px solid var(--rv-teal-500); outline-offset: 2px; }`.
- **모션**: accordion expand/collapse 0.2s ease, modal fade 0.15s, row hover background 0.12s. `prefers-reduced-motion` 시 transition 0.

---

## 14. 국제화

- **언어**: ko / en. 토글 `<button data-set-locale>`. `<body data-locale="en|ko">` + CSS attr selector 로 즉시 swap.
- **폰트 스왑**: `body[data-locale="ko"] { font-family: var(--font-ko); }` → Pretendard 자동.
- **카피 길이**: 한국어가 영문 대비 평균 30% 짧음. result table 컬럼은 모두 fixed/min-width 로 잡혀 있어 길이 변동에 강함. 단 "Manufacturer · Model" 컬럼은 영문 mfg 명이 길어질 수 있어 `text-overflow: ellipsis` 적용.
- **KCD chip**: 코드는 mono font 로 언어 무관, label 은 한·영 swap (예: "협심증, 상세불명" / "Angina, unspec.").
- **컬럼 헤더**: 한·영 동시 표기 (`<span class="ko">병원</span><span class="en">Hospital</span>`).
- **숫자·날짜**: `YYYY-MM-DD` (또는 `YYYY-MM`) 통일. 인스턴스 카운트는 mono font 로 정렬 우선. 용량 단위 ko 도 "MB" 그대로 (일반 표준).
- **Audit hash**: 4자 prefix + ellipsis (예 `a3f0…`) — 모노폰트, 언어 무관.

---

## 15. 인터랙션 패턴 (vanilla JS)

| 패턴 | 구현 |
|---|---|
| 언어 토글 | `body.dataset.locale = 'ko'` → CSS `[data-locale="ko"] .en { display:none }` |
| Accordion expand/collapse | `.accordion__group` 클릭 시 `.is-open` 토글 |
| KCD autocomplete | search input `focus`/`input` 시 dropdown open, 클릭 시 input value 채움 + close |
| **Column sort** (NEW) | `.col-sort` 클릭 시 모든 sort indicator 초기화 + 클릭한 컬럼 toggle asc/desc. mockup 에서는 indicator 만 토글, 실 구현 시 `<ResultTable>` data 정렬 |
| **Column toggle** (NEW) | `#colToggle` 클릭 시 dropdown open. 각 checkbox 변경 시 `[data-col="<key>"]` 의 visible class 토글 (mockup) → 실 구현 시 grid-template-columns 동적 재정의 |
| Row hover highlight | CSS `.result-table__row:hover { background: var(--rv-stone-50); }` |
| Row checkbox → cohort | checkbox `change` → row `.is-selected` 토글 → cohort drawer count update (실 구현 sessionStorage) |
| Select all | header `#selAll` → 모든 row checkbox 동기화 |
| **Slice slider** (NEW) | range input `input` 이벤트 → label 동기화 (mockup), 실 구현 viewer frame seek |
| **Compliance collapse** (NEW) | header 클릭 → `.compliance-collapse.is-open` 토글, body display swap |
| Hospital badge | 정적 클래스 + tooltip은 `title` 속성 |
| Audit modal | (account 페이지 전용, 본 v3 스코프 외) |
| API key reveal-once | 첫 클릭 시 mask → plaintext, 버튼 disabled + opacity 0.5 |
| Tabs (curl/Python/Postman) | 클릭 시 `is-active` swap, panel display swap |
| Copy button + toast | `navigator.clipboard.writeText` + `<div>` toast 1.8s |

---

## 16. 수용 기준 (시각·행동)

- [ ] 4 mockup 모두 Chrome 1280×800 desktop 에서 layout 시안 ASCII §7 와 일치.
- [ ] 메인 컬러 hex grep 검사: `#2563EB` 0회 등장 (anti-Segmed, v2 정책 보존).
- [ ] Pretendard CDN 로드 확인 (한글 페이지에서 시각적으로 산세리프 한글).
- [ ] 언어 토글 EN ↔ KO 모든 카피 swap (누락된 `.en` / `.ko` 0건).
- [ ] **search.html 의 결과 row 에 썸네일 0** (grep `result-thumb` → search.html 내 0건).
- [ ] **search.html 의 result-table 25 row 노출** (1280 px 화면에서 페이지 하단 도달 전).
- [ ] **각 row 11 컬럼 모두 노출** (stripe + checkbox 제외하고 11 visible cell).
- [ ] **각 row hospital stripe 4px** + region badge 동시 노출.
- [ ] 컬럼 헤더 정렬 indicator 표시 + 클릭 시 asc/desc 토글.
- [ ] "Show columns ▾" 토글 dropdown 14 항목 (10 default + 4 advanced flagged v0.1.5/collapse).
- [ ] **study-detail.html 첫 진입 시 De-ID Chain stepper default 노출 X** (footer collapsed, 5/5 verified trust bar 만 노출).
- [ ] **study-detail.html 우측 rail 에 Quality metrics 4 카드 + Patient/Study/Series/Acquisition/Pixel 5 메타 카드** 노출.
- [ ] **study-detail.html footer "Compliance & audit ▾" 클릭 시 De-ID 5 단계 + audit info 카드 expand**.
- [ ] longitudinal timeline 4 step + current marker (teal) + 병원 라벨 노출.
- [ ] KCD autocomplete dropdown 에서 한·영·코드 3 컬럼 모두 표시.
- [ ] 색 대비 본문 4.5:1, primary CTA 4.5:1 모두 충족.
- [ ] 외부 의존성: Google Fonts (Inter) + jsdelivr (Pretendard) CDN 만, 그 외 0.
- [ ] `file://` 더블클릭으로 4 파일 모두 작동.
- [ ] vanilla JS 만 사용, React/Next/jQuery 0건.

---

## 17. dev-spec 영향

| 영향 받는 dev-spec | 변경/추가 사항 |
|---|---|
| `dev-spec-portal-redesign.md` | **(a)** FR-BP-4 "검색 결과 row 정보 밀도" 의 "최소 7 개 필드" → **"11 개 컬럼 dense table + 4 컬럼 toggle"** 로 갱신. **(b)** `<StudyThumbnail>` 컴포넌트 search list 에서 제거 (study-detail viewer placeholder 만 보존). **(c)** FR-BP-8 study detail 우측 De-ID rail → footer collapse 로 전환 + Quality/Acquisition/Pixel 카드 신규. **(d)** 신규 컬럼 토글 토큰 `--rv-row-h`, `--rv-table-zebra`, `--rv-table-divider` UI_GUIDE 추가. |
| 신규 `dev-spec-deid-chain-buyer-view.md` (v2 시점 제안) | UI 위치를 **footer collapse** 로 명시. WORM 5y 연계 그대로. props.collapsed default true. |
| 신규 `dev-spec-ontology-search-snomed-kcd-radlex.md` (v2 시점 제안) | 변경 없음 (autocomplete 자체는 v3 도 보존). |
| `dev-spec-metadata-index.md` | SearchResponse 에 추가 필드 enumeration: `body_part_examined`, `manufacturer`, `model_name`, `study_date_shifted_yyyymm`, `n_series`, `n_instances`, `total_bytes`, `study_uid_tail6`, `kvp` (CT), `slice_thickness_mm`, `magnetic_field_strength_t` (MR). 행당 11 컬럼 노출 위함. metadata-extraction 리서치 §3 MVP 12 필드와 정렬. |
| `dev-spec-buyer-auth.md` | 변경 없음 (account 페이지 v2 그대로). |
| `docs/UI_GUIDE.md` | 본 §6.1 신규 토큰 5개 (`--rv-row-h`, `--rv-row-h-sm`, `--rv-table-zebra`, `--rv-table-divider`, `--rv-col-stripe-w`) Kyle 승인 후 정식 편입. |

---

## 18. 오픈 질문 / Kyle 결정 필요

1. **컬럼 토글 default visible 정책** — 본 v3 는 11 default + 4 advanced. v0.1.5 advanced (slice thickness · KVP · MR field) 를 v0.1 출시 시점에 default visible 로 올릴지 여부.
2. **컬럼 너비 — 자동 vs 고정** — 현재 mockup 은 fixed-width + min(140px, 1.4fr). buyer 가 "Manufacturer · Model" 너비 조절 (drag) 을 원할 가능성. v0.2 backlog 후보.
3. **page size — 25 vs 50 vs infinite scroll** — 현 mockup 25/page + 페이지네이션. Segmed Openda 는 25/page 추정. infinite scroll 은 buyer 피로도 ↑·검색 audit 어려움. 본 권고: 25 default + 50/100 toggle.
4. **De-ID footer collapse — default closed 확정?** — 본 권고: closed (Kyle 직접 피드백 반영). 단, "구매 후" 진입 시 자동 open 로직 도입 여부 dev-spec 결정 필요.
5. **Quality completeness score 정의** — 본 mockup "98% (12/12 fields)". 분모 12 필드는 metadata-extraction MVP 12 와 일치. 분자 정의 (null 0 + non-null 1)·표시 임계 (90% 미만 amber 등) Kyle 결정.
6. **Sample download 의 "1 representative slice"** — 현 카피. 분모/분자 명시 필요 ("1 slice / 312") 여부.
7. **컬럼 header 한·영 동시 표기 vs locale-aware swap** — 현 v3 는 locale swap. Segmed 는 영어 전용. 한국어 모드일 때 컬럼 라벨이 짧아져 빈 공간 발생 가능 — 한·영 병기 (예 "병원 / Hospital") 도 후보.
8. **Audit hash 컬럼 toggle 위치** — 본 v3 는 column toggle 의 4번째 advanced 로 두되 "collapse" 라벨로 표기 (footer 와 일관). buyer 가 직접 활성화하면 row 에 chip 노출. Kyle 결정: 이 노출을 허용 vs footer 만 노출.
9. **반응형 1024-1279 px 컬럼 자동 hide 우선순위** — 본 권고: Sr·Inst → Size → UID 순. Kyle 검토.

---

## 19. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|---|---|---|---|
| 0.1 | 2026-04-25 | @designer (Claude Opus 4.7 [1M]) | 최초 작성 (v2 대체). v2→v3 5축 차별 (썸네일 제거 / dense list / De-ID 격하 / rich detail / longitudinal 강화) + Segmed Openda dense table 흡수 5 + 컴포넌트 인벤토리 (NEW 7 / CHANGED 2 / REMOVED 2 / PRESERVED 9) + wireframe 4 화면 + 컬럼 정의 표 14 + 상세 메타 25 필드 + 신규 토큰 5 + Kyle 결정 9개. v3 mockup 4 신규 (`mockups/buyer-ux-v2/v3/`), v1·v2 보존. |

---

### NEXT_STEP

- 완료 산출물:
  - `docs/specs/design-spec-buyer-ux-v3.md` (본 문서, v2 대체)
  - `docs/specs/mockups/buyer-ux-v2/v3/{index,search,study-detail,account}.html` + `styles.css` (신규 디렉토리, v1·v2 보존)
- 제안 다음 단계: **메인 세션이 본 v3 mockup 을 Kyle 에게 시연 → 채택 결정 → 채택 시 `@planner` 호출하여 §17 의 dev-spec-portal-redesign FR-BP-4/-8 갱신 + dev-spec-metadata-index 의 SearchResponse 필드 11개 추가 정식화**.
- UI_GUIDE.md 갱신 제안: 본 §6.1 신규 토큰 5개 (`--rv-row-h`, `--rv-row-h-sm`, `--rv-table-zebra`, `--rv-table-divider`, `--rv-col-stripe-w`) 만 추가. v2 토큰은 변경 없음.
- 추가 디자인 필요: 채택 시 hospital console / operator console 에 동일 dense table 패턴 적용할지 별도 결정 (별 slug `dev-spec-portal-redesign` 트랙 3 영향).
- Kyle 결정 필요 사항: §18 Q1~Q9 9 개.
