# 디자인 명세 — Full-Slice Preview JPG (전체 슬라이스 미리보기)

> **Status**: Draft v0.1 · **Feature slug**: `full-slice-preview-jpg` · **Last updated**: 2026-04-26
> **작성자**: @designer (Claude Opus 4.7 [1M])
> **근거**:
> - [`dev-spec-full-slice-preview-jpg.md`](./dev-spec-full-slice-preview-jpg.md) v0.1 — FR-FSP-1..17, NFR, AC-1..AC-26
> - [`docs/research/full-slice-jpg-preview-research.md`](../research/full-slice-jpg-preview-research.md) §4 PHI / §5 UX / §6 windowing
> - [`design-spec-portal-redesign.md`](./design-spec-portal-redesign.md) v0.2 — §4 토큰 / §5 공통 컴포넌트 / §11.4 `{#study-detail-v1}`
> - [`UI_GUIDE.md`](../UI_GUIDE.md) — 플레이스홀더. portal-redesign §4 가 사실상 단일 토큰 원본.
>
> **Kyle 결정 (이미 확정 — 2026-04-26)**:
> 1. PHI spot-check Phase 1 = Kyle 본인 5% sample
> 2. MinIO SSE-S3 활성
> 3. PHI 알림 = Kyle 이메일 + Slack DM
> 4. Cornerstone3D 의존성 승인 (~500 KB gz lazy chunk)
> 5. 정형 CT implant Phase 1 = auto_quarantine
> 6. PIPA 변호사 자문 Phase 1 ship 직전 (D-13+25)
> 7. BFF Mode A (presigned URL redirect)

---

## 1. 디자인 개요

본 명세는 dev-spec FR-FSP-12 가 요구하는 **Cornerstone3D StackViewport** 를 `/studies/[uid]` 페이지 안에 통합하기 위한 UI 변경을 정의한다. 변경 범위는 **`design-spec-portal-redesign §11.4 {#study-detail-v1}` 의 ViewerStub 자리** 한 곳에 한정한다 — 메타데이터 grid, Series 리스트, Header bar, Hospital origin row 는 v0.2 디자인 그대로 유지하며 본 명세에서 손대지 않는다.

이 viewport 안에서 RadiVault 가 Segmed Openda · TCIA · MD.ai 와 차별화되는 3 요소가 시각적으로 항상 살아 있어야 한다:
1. **De-ID Chain stamp** — 병원 hash + 익명 study UID 끝 6 자리 + 8-layer 통과 결과를 viewport 우상단 상시 노출.
2. **PHI Scrub indicator** — 슬라이스별 격리 여부를 thumbnail strip 위 작은 dot · 격리 슬라이스는 흐림 처리 placeholder.
3. **Modality-aware windowing 결과 첫 노출** — buyer 가 W/L 슬라이더를 만지지 않아도 첫 화면에서 임상적으로 의미 있는 preview.

차별화 시각 요소는 dev-spec §1.2 의 "RadiVault 차별화 포인트" 4 개와 1:1 대응한다.

---

## 2. 화면 목록

| ID | 화면명 | 경로 | 주요 역할 | dev-spec FR |
|----|--------|------|----------|--------------|
| **S-1** | Study Detail (viewport 통합) | `/studies/[uid]` | 메타데이터 grid + Cornerstone3D StackViewport · 마우스 휠/키보드 navigation · De-ID Chain stamp · PHI 격리 시 fallback | FR-FSP-12 |

본 슬라이스에서 신규 페이지 라우트는 추가하지 않는다. 기존 `{#study-detail-v1}` (portal-redesign §11.4 / §12.2) 의 ViewerStub 영역만 교체된다.

---

## 3. 사용자 플로우

dev-spec §8.2 의 시퀀스를 UI 관점으로 재서술. 5 시나리오 — happy path 1 + 격리 시나리오 2 + 권한/feature flag 시나리오 2.

### 3.1 Happy path — verified study (S-1 정상)

```
[Search results row click]
   ↓
[Study Detail mount]
   ├─ ① Header bar 즉시 렌더 (메타데이터는 server-side prop)
   ├─ ② BFF GET /api/studies/{uid}/slices
   │     ↓ 응답 enabled=true · slice_count=712 · scrub_status=verified
   ├─ ③ FullSlicePreviewViewport mount (skeleton 200ms)
   ├─ ④ Cornerstone3D StackViewport init · imageIds[0..711] 등록
   ├─ ⑤ BFF GET /api/studies/{uid}/slices/0 → 302 presigned URL
   ├─ ⑥ JPG fetch + decode → canvas paint (≤ 500ms LCP)
   ├─ ⑦ Hint overlay 1 초 표시 ("Scroll · ↑/↓ · drag")
   └─ ⑧ Idle: prefetch slice 1..5
```

이후 buyer 가 마우스 휠 1 tick → ⑤–⑥ 만 반복 (≤ 100ms per slice, prefetch hit).

### 3.2 격리 — study 전체 PHI 잔존 (R-2 / R-3 시나리오)

```
[Search results row click]
   ↓
[Study Detail mount]
   ├─ ① Header bar 렌더
   ├─ ② BFF GET /api/studies/{uid}/slices → 451
   ├─ ③ ViewerArea 가 QuarantineBanner 렌더 (page-level error 패턴 §14.3 차용)
   │     "Full-slice preview pending PHI re-verification"
   │     "자동 알림 발송됨"
   ├─ ④ ViewerArea 하단에 single-thumbnail 카드로 회귀 (FR-FSP-17 fallback)
   └─ ⑤ Header / 메타데이터 / Series 리스트는 정상 표시
```

### 3.3 부분 격리 — 일부 슬라이스만 quarantined (quarantined_partial)

```
[Study Detail mount]
   ├─ BFF GET /slices → enabled=true · slice_count=712 · scrub_status=quarantined_partial
   ├─ scrub_layers_summary.per_slice_failures = [{slice_idx:47, ...}, {slice_idx:138, ...}]
   ├─ Viewport 정상 mount
   ├─ slice 0..46 정상
   ├─ slice 47 진입 시 → BFF 404 → viewport 가 placeholder 슬라이스 렌더
   │     (흐림 처리된 회색 패턴 + 중앙 라벨 "Slice 47 quarantined")
   ├─ thumbnail strip 의 slice 47 위치 dot = warn (yellow ⚠)
   └─ slice 48 부터 다시 정상
```

### 3.4 Feature flag off (PREVIEW_FULL_SLICE_ENABLED=false)

```
[Study Detail mount]
   ├─ BFF GET /slices → enabled=false · thumbnail_url=...
   └─ ViewerArea 가 기존 1-thumbnail 카드 렌더 (변경 없음, v0.2 ViewerStub 자리에 thumbnail)
```

화면적으로는 v0.2 디자인의 ViewerStub 위치에 단일 256×256 썸네일 이미지가 들어가는 형태. Cornerstone3D 자체가 lazy chunk 라 이 경우 import 되지 않음.

### 3.5 권한 없음 (403) / 비로그인 (401)

dev-spec §13 의 federated 격리 정책에 따라:
- **401**: middleware redirect → `/signin?return=/studies/{uid}`. ViewerArea 도달 전에 처리.
- **403**: page-level error (`{#study-detail-v1}` 자체가 렌더되지 않고 portal-redesign §14.4 패턴).

본 명세는 401/403 에 별도 viewport UI 를 추가하지 않는다.

---

## 4. S-1 상세 — Study Detail viewport 통합 영역

### 4.1 변경 범위 선언

`{#study-detail-v1}` (portal-redesign §11.4) 의 5 섹션 중 본 명세가 손대는 곳:

| 섹션 | 본 명세에서 변경? | 비고 |
|------|------------------|------|
| 1. Header bar | ✗ 변경 없음 | 그대로 재사용 |
| 2. Hospital origin row | ✗ 변경 없음 | 그대로 재사용 |
| 3. Metadata grid | ✗ 변경 없음 | 그대로 재사용 |
| 4. Series list | △ 약간 수정 | "currently viewing" 표시 1 줄 추가 (§4.4) |
| **5. ViewerStub** | **✓ 전면 교체** | `<FullSlicePreviewViewport>` 로 대체 |

### 4.2 ViewerArea 레이아웃 (S-1 §5 영역 교체분)

데스크톱 ≥ 1280px 기준. ViewerArea 는 `{#study-detail-v1}` 의 마지막 섹션으로 풀폭(`max-w-app = 1440px` 컨테이너 내부) 사용.

```
┌────────────────────────────────────────────────────────────────────────────────┐
│  VIEWER AREA  (height: 640px desktop, height: 480px tablet best-effort)        │
│ ┌────────────────────────────────────────────────────┬─────────────────────┐   │
│ │                                                    │                     │   │
│ │  [De-ID Chain ✓]   [PHI Scrub 8/8 ✓]             │  SERIES THUMBNAILS  │   │
│ │                                                    │                     │   │
│ │                                                    │  ┌────┐ S1 (CT)    │   │
│ │                                                    │  │ 1  │ 287 imgs   │   │
│ │                                                    │  └────┘            │   │
│ │           [ Cornerstone3D StackViewport ]          │  ┌────┐ S2 (CT)    │   │
│ │              (canvas, --viewport-bg #000)          │  │ 64 │ MIP        │   │
│ │                                                    │  └────┘            │   │
│ │                                                    │  ┌────┐ S3 (CT)    │   │
│ │                                                    │  │ 2  │ Scout      │   │
│ │                                                    │  └────┘            │   │
│ │                                                    │                     │   │
│ │                                                    │  Slice dots:       │   │
│ │                                                    │  ●●●●●●●●●⚠●●●●●  │   │
│ │                                                    │  └─ slice 0..15    │   │
│ │                                                    │                     │   │
│ ├────────────────────────────────────────────────────┴─────────────────────┤   │
│ │ TOOLBAR                                                                  │   │
│ │ [◀] Slice  142 / 850   [▶]    [CT Lung ▾]  [100% fit]  [↻ Reset]  [3D⊘]│   │
│ └──────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────┘
```

비율 (1440px max width 컨테이너 내부):
- 메인 viewport: ~64% width (≈ 920px) · height 600px
- 우측 SeriesThumbnailStrip: ~36% width (≈ 320px) · height 600px · 스크롤 가능
- 하단 Toolbar: 풀폭 · height 40px

태블릿 (1024–1279px, best-effort): 우측 strip → viewport 하단으로 이동 (가로 strip).

### 4.3 메인 viewport 영역 상세

**배경 / 캔버스**
- `--viewport-bg = #000` (신규 토큰, dev-spec §6 요구)
- Cornerstone3D `<canvas>` 가 100% 채움. canvas 외 영역은 검정.
- WebGL 2.0 미지원 브라우저: §5.2 fallback 참조.

**우상단 indicator 묶음** (viewport 안에 absolute positioned · `top: 12px · right: 12px`)

```
┌───────────────────────────────┐
│  De-ID Chain   ✓ verified     │  ← `<DeIdChainStamp>`
│  HOSP-A2 · ...1234            │
├───────────────────────────────┤
│  PHI Scrub  8 / 8 ✓           │  ← `<PhiScrubIndicator>`
│  L1 L2 L3 L4 L5 L6 L7 L8      │
└───────────────────────────────┘
```

상세는 §6.5 / §6.6.

**좌상단 modality + KCD 라벨** (viewport 안에 `top: 12px · left: 12px`)

```
[ CT ]  KCD: J18.9
        Pneumonia, unspecified · 폐렴, 상세불명
```

- ModalityBadge `{#modality-badge-v1}` 재사용 (portal-redesign §11.1 토큰 그대로).
- KCD 코드 + EN/KR 진단명 (text-xs / mono / `--color-text-muted`).
- buyer 가 영어 모드면 EN 우선 노출, 한국어 모드면 KR 우선.

**좌하단 hospital + 진행률** (viewport 안에 `bottom: 12px · left: 12px`)

```
HOSP-A2 · Seoul ●●●●●●●○○○  142 / 850
```

- Hospital_opaque_id chip + region (병원이 동의한 권역 라벨만 — 시도 단위 권역, dev-spec PRD compliance 정책 따름).
- 진행률은 SliceCounter `{#slice-counter}` (§6.3) 와 동일 데이터 소스, viewport 내부에 미니 표시.

**첫 진입 hint overlay** (viewport 중앙, mount 후 1 초 fade in/out)

```
┌─────────────────────────────────────┐
│  [ icon: mouse ]  Scroll to navigate│
│  [ icon: keys  ]  ↑↓  Page  Home/End│
│  [ icon: drag  ]  Drag for stack    │
└─────────────────────────────────────┘
```

- 배경 `rgba(15,23,42,0.72)` (slate-900 / 72%) · `radius-md` · padding `space-4`.
- `prefers-reduced-motion` 감지 시 fade 없이 정적 표시 후 1.5 초 후 비표시.
- localStorage `rv_viewport_hint_shown=true` 저장 → 동일 buyer 의 이후 진입에서는 비표시.
- ARIA: `role="status"` · 1 초만 SR 에 announce.

### 4.4 우측 SeriesThumbnailStrip 영역

**조건부 렌더**: dev-spec FR-FSP-12 — series ≥ 2개일 때만 표시. 1 개 series 인 study 는 viewport 가 100% width 사용.

**레이아웃**:

```
┌─────────────────────────────────────────┐
│  SERIES (3)                             │
├─────────────────────────────────────────┤
│  ┌────────────┐  S1 · CT                │
│  │            │  AXIAL 1.0mm            │
│  │  thumb     │  287 instances  ← 현재  │  ← active border 4px primary-600
│  │            │                         │
│  └────────────┘                         │
│  ┌────────────┐  S2 · CT                │
│  │            │  CORONAL MIP            │
│  │  thumb     │  64 instances           │
│  │            │                         │
│  └────────────┘                         │
│  ┌────────────┐  S3 · CT                │
│  │            │  SCOUT                  │
│  │  thumb     │  2 instances            │
│  │            │                         │
│  └────────────┘                         │
├─────────────────────────────────────────┤
│  SLICE INDICATORS (current series)      │
│                                         │
│  ●●●●●●●●●⚠●●●●●●●●●●●●●●●●●●●●●     │
│  └ slice 0                slice 287 ┘   │
│                                         │
│  Legend: ● verified · ⚠ quarantined     │
└─────────────────────────────────────────┘
```

- 각 series 카드: 80×80 thumbnail (해당 series 의 첫 키프레임 JPG, 즉 `previews/{uid}/{series:02d}/0000.jpg` 의 256×256 다운스케일 변형) + 메타.
- Click → 해당 series 첫 슬라이스로 jump (`viewport.setStack(seriesImageIds, 0)`).
- 키보드: Tab으로 카드 진입 후 Enter 로 선택. 좌측 viewport 와 focus 분리.
- 활성 series → 좌측 4 px `--color-primary-600` border + bg `--color-primary-50`.

**Slice indicator dots** (현재 활성 series 만):
- 각 dot = 4×4 px · gap 2 px.
- verified = `--phi-scrub-success` (#15803d, success-fg).
- 격리(quarantined) = `--phi-scrub-warn` (#b45309, warning-fg) + `⚠` 아이콘 superimposed (4px 영역에서 가독 안 되면 hover 시 확대 + tooltip).
- phi_detected = `--phi-scrub-quarantine` (#94a3b8, slate-400) — 이 경우 사실상 viewport 자체가 quarantine banner 로 회귀하므로 거의 노출되지 않음.
- ≥ 200 슬라이스인 series 는 dot 줄을 자동으로 2 줄 또는 3 줄로 wrap. 850 슬라이스 시 약 170 dots/줄 × 5 줄.

### 4.5 하단 Toolbar 영역

```
┌────────────────────────────────────────────────────────────────────────┐
│ [◀]  Slice  142 / 850  [▶]   [CT Lung ▾]   [100%]  [Fit]  [↻ Reset]  [3D ⊘] │
└────────────────────────────────────────────────────────────────────────┘
```

요소별 좌→우:

1. **◀ / ▶ 버튼** (`<SliceCounter>` 의 일부)
   - prev/next 1 슬라이스. disabled 상태 = 첫/마지막 슬라이스에서 회색.
   - aria-label: "Previous slice" / "Next slice".

2. **Slice 142 / 850** — `{#slice-counter}` 본체 (§6.3).
   - 클릭 시 input box 로 토글 → 직접 슬라이스 번호 입력 가능 (Enter 로 jump).

3. **CT Lung ▾** — `<ModalityPresetToggle>` (§6.4).
   - 현재 적용된 windowing preset 표시 + dropdown 으로 변경.
   - Phase 1 = 표시만 + dropdown disabled (자동 적용된 것 read-only).
   - Phase 1.1 = 사용자 변경 가능 (manual W/L 은 v0.2).

4. **100% / Fit** — Zoom 버튼 (`<ZoomControl>` — 신규지만 단순, props만).
   - 100% = 1:1 px ratio · Fit = canvas 에 맞춤.
   - 토글 그룹.

5. **↻ Reset** — view state 리셋 (zoom 100%, pan 0, 슬라이스는 유지).

6. **3D ⊘** — 3D/MPR 토글 (L8 가드).
   - **항상 disabled · 회색** (`opacity 0.4 · cursor-not-allowed`).
   - hover tooltip: EN `3D reconstruction disabled for de-identification` / KR `비식별화를 위해 3D 재구성이 비활성화됨`.
   - aria-disabled="true" + aria-describedby pointing to tooltip.
   - dev-spec FR-FSP-12 L8 가드 시각 표현. 토글이 **존재하되 disabled** 인 게 핵심 — Segmed 와 달리 RadiVault 는 이 정책이 의도적이고 가시화되어 있음을 보여줌.

**Toolbar 스타일**:
- 배경 `--color-bg` · 상단 1 px border `--color-border`.
- 높이 40 px · padding `space-3` 좌우.
- 버튼들은 portal-redesign 의 ghost button variant 재사용.

---

## 5. 상태 처리

`{#study-detail-v1}` 자체의 상태(404, 403, loading) 는 portal-redesign §14 패턴을 그대로 따른다. 본 §5 는 **ViewerArea 한정** 신규 상태만 정의.

### 5.1 Loading

- **단계 1 — viewport 초기화 전 (BFF /slices 응답 대기)**: ViewerArea 영역에 skeleton.
  ```
  ┌────────────────────────────────────────┐
  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
  │ ░░░░░░  Loading preview...  ░░░░░░░ │
  │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
  └────────────────────────────────────────┘
  ```
  - bg `--color-bg-muted` · skeleton lines `--color-border-strong` 1.5s shimmer.
  - 텍스트 `text-sm / text-text-muted`.

- **단계 2 — viewport mount 완료, 첫 슬라이스 fetch 중**: viewport 영역에 `--viewport-bg #000` + 중앙 spinner (16 px white, 200ms 후 표시 — 그 안에 로드되면 미표시).

- **단계 3 — 슬라이스 navigation 중 prefetch miss**: viewport 좌상단에 mini spinner 12 px (덮어쓰지 않고 현재 슬라이스 위에 overlay).

### 5.2 Empty (preview 미생성 / preview_full_slice_status='pending')

BFF 가 503 또는 `enabled=false · status='pending'` 으로 응답.

```
┌────────────────────────────────────────┐
│  [icon: clock]                         │
│                                        │
│  Preview is being prepared             │
│  미리보기 생성 중                      │
│                                        │
│  This study's full-slice preview is    │
│  scheduled for tonight's batch.        │
│  Try again after 03:00 KST.            │
│                                        │
│  [ View single thumbnail ↓ ]           │
└────────────────────────────────────────┘
```

- portal-redesign §14.3 page-level error 패턴 차용 (단 ViewerArea 한정).
- 하단에 기존 1-thumbnail 카드 fallback (FR-FSP-17 — feature flag off 와 시각 동일).

### 5.3 Error — slice fetch 실패 (개별 슬라이스 5xx)

- viewport 가 검정 + 중앙 작은 메시지 `Failed to load slice 142. [Retry]`.
- `[Retry]` 클릭 → 동일 슬라이스 재요청. 3 회 실패 시 → `Persistent failure. request_id: req_01HX...` 표시 + portal-redesign §14.1 toast 동시 발생.
- 다른 슬라이스 navigation 은 정상 동작.

### 5.4 No-permission (451)

dev-spec §11.2 의 R-1 / R-2 시나리오 (PHI 잔존 격리). `<QuarantineBanner>` (§6.7).

```
┌────────────────────────────────────────────────────────────────────────┐
│  [icon: shield-alert · warn fg]                                        │
│                                                                        │
│  Full-slice preview pending PHI re-verification                        │
│  미리보기는 PHI 재검증 대기 중입니다                                   │
│                                                                        │
│  This study's full-slice preview was paused after our automated        │
│  scrub flagged a potential PHI artifact. Our team has been notified    │
│  (자동 알림 발송됨) and will verify within 24 hours.                   │
│                                                                        │
│  Status: phi_detected · Last checked: 2 hours ago                      │
│                                                                        │
│  [ View single thumbnail ↓ ]   [ Contact support → ]                   │
└────────────────────────────────────────────────────────────────────────┘
```

- 배경 `--color-bg` · 좌측 4px solid `--color-warning-fg` (#b45309) 강조.
- 아이콘 24px · color = `--color-warning-fg`.
- 제목 `text-base / font-semibold / text-text` · KR 한 줄 추가.
- 본문 `text-sm / text-text-muted` (영어) + 한국어 한 줄 인라인.
- 하단에 1-thumbnail fallback + "Contact support" mailto.

### 5.5 Partial failure — quarantined_partial (일부 슬라이스만 격리)

viewport 는 정상 mount. 격리된 슬라이스 진입 시:

- viewport canvas 가 **흐림 처리된 placeholder** 렌더 (Cornerstone3D 가 그릴 가짜 이미지 또는 BFF 가 404 시 클라이언트가 그리는 fallback).
- 패턴: 회색 grid (`#e2e8f0` cells, 16px) + 중앙 라벨:
  ```
  [icon: shield-off · 32px · warn fg]
  Slice 47 quarantined
  슬라이스 47 격리됨

  PHI artifact detected by L2 OCR.
  Skipped to preserve patient privacy.
  ```
- thumbnail strip dot 도 yellow ⚠ 로 표시 (§4.4).
- ARIA: viewport `aria-label` 변경 → "Slice 47 of 850, quarantined for PHI protection".

### 5.6 Memory pressure

- prefetch ±5 + LRU cap 100 슬라이스 (dev-spec FR-FSP-12).
- 100 슬라이스 도달 시 가장 오래된 cached 슬라이스 evict.
- buyer 에게 시각화 안 함 (viewport 내부 메커니즘).

---

## 6. 컴포넌트 inventory

7 신규 컴포넌트 + 1 재사용. 각 컴포넌트는 React functional + props 명세 + state machine 요약. 구현은 @developer 위임.

### 6.1 `<FullSlicePreviewViewport>` — 메인 wrapper

**역할**: ViewerArea 전체. 자식으로 §6.2~§6.7 컴포넌트 holding. Cornerstone3D engine lifecycle 관리.

**props**:
```ts
interface Props {
  studyUidPseudo: string;
  sliceCount: number;          // /slices 응답
  series: Array<{
    seriesIdx: number;
    pseudoSeriesUid: string;
    modality: string;
    sliceCount: number;
    keyFrameIndices: number[];
  }>;
  scrubLayersSummary: ScrubSummary;     // dev-spec FR-FSP-5 schema
  perSliceFailures: Array<{sliceIdx: number, layer: string, reason: string}>;
  hospitalOpaqueId: string;
  hospitalRegionLabel: string | null;
  kcdCode: string | null;
  kcdLabelKo: string | null;
  kcdLabelEn: string | null;
  locale: 'en' | 'ko';
}
```

**state machine** (Mermaid 간략):
```
[idle] --mount--> [initializing-engine]
[initializing-engine] --engine-ready--> [loading-first-slice]
[loading-first-slice] --slice-loaded--> [ready]
[loading-first-slice] --error-3x--> [error]
[ready] --user-scroll--> [navigating]
[navigating] --slice-loaded--> [ready]
[ready] --quarantine-detected--> [showing-placeholder]
[showing-placeholder] --user-scroll-away--> [navigating]
[ready] --unmount--> [disposing]
```

**engine 라이프사이클** (§7):
- `useEffect` mount 시 `cornerstoneInit()` + RenderingEngine 인스턴스 생성.
- unmount 시 `engine.destroy()` + `cache.purgeCache()` (메모리 누수 방지, R-6).

### 6.2 `<SeriesThumbnailStrip>` — 우측 navigation

**역할**: series ≥ 2 일 때 우측 320px column 렌더. 카드 + dot indicator.

**props**:
```ts
interface Props {
  series: Props['series'];
  activeSeriesIdx: number;
  activeSliceIdx: number;
  perSliceFailures: Array<{sliceIdx, layer, reason}>;
  onSelectSeries: (seriesIdx: number) => void;
  thumbnailUrlBuilder: (seriesIdx: number) => string; // /api/studies/{uid}/slices/{firstIdx}
  locale: 'en' | 'ko';
}
```

**state**: stateless presentational component. parent 가 active 인덱스 보유.

**조건부 미렌더**: `series.length < 2` → null 반환. parent `<FullSlicePreviewViewport>` 가 viewport width 100% 로 확장.

### 6.3 `<SliceCounter>` — 하단 인덱스

**역할**: `Slice 142 / 850` 표시 + ◀/▶ + 직접 입력 토글.

**props**:
```ts
interface Props {
  current: number;        // 0-base internal, 1-base displayed
  total: number;
  onChange: (newIdx: number) => void;
  locale: 'en' | 'ko';
}
```

**state**: `editing: boolean` (default false). true 시 `<input type=number>` 으로 토글. blur / Enter 시 `onChange` 호출 + `editing=false`.

**라벨**: EN `Slice {current+1} / {total}` · KR `슬라이스 {current+1} / {total}`. 한국어 길이 ~30% 짧으므로 toolbar 너비 충분.

### 6.4 `<ModalityPresetToggle>` — windowing preset 표시

**역할**: 적용된 windowing preset 표시. Phase 1 = read-only.

**props**:
```ts
interface Props {
  modality: 'CT' | 'MR' | 'MG' | 'CR' | 'DX' | 'PT' | 'US' | 'NM' | 'XA' | 'OT';
  preset: string;        // "ct_lung_-600_1500" / "mr_percentile" / ...
  presetLabel: string;   // "CT Lung" / "MR Percentile" / "MG VOI LUT"
  disabled: boolean;     // Phase 1 = always true
  onChange?: (newPreset: string) => void;  // Phase 1.1+
  locale: 'en' | 'ko';
}
```

**시각**: dropdown 아이콘 ▾ 포함하되 click 무반응 (disabled). hover tooltip "Windowing preset is auto-applied in Phase 1."

### 6.5 `<DeIdChainStamp>` — 우상단 verified badge

**역할**: viewport 우상단 absolute. 병원 hash + study UID 끝 6 자리 + 8-layer 통과 여부 ✓ 마크.

**props**:
```ts
interface Props {
  hospitalOpaqueId: string;          // "HOSP-A2"
  studyUidPseudoTail: string;        // "...e8f231" (마지막 6 자)
  scrubAllPassed: boolean;           // L1..L8 모두 통과 = ✓
  scrubFailedLayers: string[];       // failed 시 ["L2"], etc.
  locale: 'en' | 'ko';
}
```

**시각**:
```
┌──────────────────────────┐
│ De-ID Chain   ✓ verified │     ← bg rgba(15,118,110,0.12) (teal-700 12% alpha)
│ HOSP-A2 · ...e8f231      │     ← text-xs / mono / white
└──────────────────────────┘
```

- bg 반투명 teal (Hospital 색 차용 — 차별화 메시지: "병원 → buyer 까지 chain of custody").
- font-mono (provenance 가 기술적 정체성임을 강조).
- click → portal-redesign §14.3 timeline drawer 또는 별도 modal 로 8-layer 상세 표시 (§6.6 PhiScrubIndicator 와 통합 권장).
- aria-label: EN `De-identification chain: hospital HOSP-A2, study ending e8f231, all 8 layers passed`.

**상태**:
- All passed (default): ✓ + 텍스트 `verified` (success fg).
- Some failed: ⚠ + 텍스트 `partial` (warn fg).
- 미실행 (Phase 1 N/A): ⊘ (대시 회색).

### 6.6 `<PhiScrubIndicator>` — 8-layer 통과 status

**역할**: De-ID Chain stamp 바로 아래. L1..L8 8 개 dot + summary.

**props**:
```ts
interface Props {
  layers: {
    L1_bia_triage: 'passed' | 'failed' | 'skipped';
    L2_ocr: 'passed' | 'failed' | 'skipped';
    L3_defacing: 'passed' | 'failed' | 'skipped';
    L4_modality_exclusion: 'applied' | 'na';
    L5_implant_detection: 'passed' | 'failed' | 'skipped';
    L6_reverify: 'passed' | 'failed' | 'skipped';
    L7_resolution_clamp: 'applied' | 'na';
    L8_viewer_3d_block: 'applied';
  };
  totalSlices: number;
  failedSliceCount: number;
  locale: 'en' | 'ko';
}
```

**시각**:
```
┌──────────────────────────┐
│ PHI Scrub  8 / 8  ✓      │
│ L1 L2 L3 L4 L5 L6 L7 L8  │  ← 각 layer name 위에 4px dot
│ ●  ●  ●  ⊘  ●  ●  ●  ●   │     bg 색 = 상태별
└──────────────────────────┘
```

- 각 layer label `text-xs / mono` · dot color:
  - passed/applied = `--phi-scrub-success` (#15803d)
  - failed = `--phi-scrub-warn` (#b45309)
  - skipped/na = `--phi-scrub-quarantine` (#94a3b8)
- aria-label: EN `PHI scrub status: layers L1 L2 L3 L5 L6 L7 L8 passed; L4 not applicable`.

**색맹 대응**: 색 외에 아이콘 (✓ / ⚠ / ⊘) 도 dot 옆에 표시. 4px dot 에 아이콘이 안 들어가므로 hover/focus 시 tooltip 으로 확장.

### 6.7 `<QuarantineBanner>` — 격리 시 fallback (S-1 시나리오 3.2)

**역할**: study 전체가 phi_detected 일 때 viewport 자리에 banner. ViewerArea 한정 page-level error.

**props**:
```ts
interface Props {
  studyUidPseudo: string;
  status: 'phi_detected' | 'failed';
  lastCheckedAt: string;          // ISO timestamp
  thumbnailFallbackUrl: string;   // 기존 1-thumbnail
  contactSupportEmail: string;    // mailto
  locale: 'en' | 'ko';
}
```

**시각**: §5.4 ASCII 와이어 그대로.

- 컨테이너 height 240px · width 100% (ViewerArea 전체 차지).
- bg `--color-bg` · 좌측 4px solid `--color-warning-fg`.
- 본문 ko/en 병기 (한 단락 안에 두 줄).
- `[ View single thumbnail ↓ ]` → 페이지 내 anchor scroll 로 하단 thumbnail fallback 으로 이동.
- `[ Contact support → ]` → mailto + request_id auto-prefill (portal-redesign §14.3 패턴).

### 6.8 (재사용) `<ModalityBadge>`

`{#modality-badge-v1}` (portal-redesign §11.1) 그대로 — viewport 좌상단 modality 라벨에 사용.

---

## 7. Cornerstone3D 통합 패턴

### 7.1 의존성 / 모듈 선택

dev-spec FR-FSP-12 의존성 + 본 명세에서 구체화:

```jsonc
// package.json (BFF buyer portal 측, viewer 페이지 lazy chunk)
"dependencies": {
  "@cornerstonejs/core": "^1.84.0",
  "@cornerstonejs/tools": "^1.84.0"
  // dicom-image-loader 는 미사용 (이미 JPG 라 DICOM 디코딩 불필요)
}
```

- **`@cornerstonejs/core`**: RenderingEngine, StackViewport, image cache.
- **`@cornerstonejs/tools`**: StackScrollTool, PanTool, ZoomTool 만 활성화. WindowLevelTool / VolumeRotateTool / CrosshairsTool 등 **미import** (L8 가드 + bundle size).
- **`@cornerstonejs/dicom-image-loader`**: **미사용**. 본 기능은 JPG 가 이미 디코딩된 상태로 도착하므로 cornerstone3D 의 기본 image loader (web image loader) 재활용.
- **신규 RadiVault loader 등록**: BFF endpoint 호출 → 302 redirect → Image fetch. cornerstone3D `imageLoader.registerImageLoader('radivault-jpeg', radivaultJpegLoader)` 형태. ImageId scheme: `radivault-jpeg:${uid}:${sliceIdx}`.

### 7.2 데이터 소스 (BFF Mode A)

```
[Cornerstone Image Loader]
  imageId = "radivault-jpeg:1.2.840...:142"
  ↓
  fetch("/api/studies/1.2.840.../slices/142")
  ↓ 302 redirect (BFF)
  fetch("https://minio.radivault.kr/...?X-Amz-Signature=...")
  ↓ 200 image/jpeg
  Image() decode
  ↓
  return cornerstone Image object {imageId, getPixelData, ...}
```

- BFF Mode A 는 `Cache-Control: private, max-age=300` 이므로 브라우저가 5분 내 재요청 시 캐시 hit.
- presigned URL TTL 300초 = 브라우저 cache TTL 와 일치.
- WebGL 2.0 이 없는 브라우저 (≤ Safari 14, ≤ Firefox 89) → §5 의 Empty 변형 노출 + 1-thumbnail fallback.

### 7.3 로딩 상태

- **skeleton (단계 1)**: ViewerArea 전체 회색 shimmer (BFF /slices 응답 대기).
- **first slice (단계 2)**: viewport 검정 + 중앙 spinner. LCP 목표 500ms (dev-spec NFR).
- **progressive lazy (단계 3)**: 첫 슬라이스 표시 후 idle 시 ±5 prefetch 시작.

### 7.4 메모리 관리

- `cornerstone.cache.setMaxCacheSize(100 * 512 * 512 * 4)` ≈ 100 MB (100 슬라이스 × 512²×4 byte RGBA).
- LRU eviction 자동 동작 (cornerstone3D 내장).
- 페이지 unmount 시 `engine.destroy()` + `cache.purgeCache()`.
- 디버그용 metric: `window.__rv_viewer_memory_kb` 노출 (dev mode only).

### 7.5 navigation 입력 매핑

| 입력 | 동작 |
|------|------|
| 마우스 휠 ↑/↓ | StackScrollTool ±1 slice |
| 마우스 휠 + Shift | ±5 slice |
| 키보드 ↑ / ↓ | ±1 slice |
| 키보드 PageUp / PageDown | ±10 slice |
| 키보드 Home / End | 첫 / 마지막 |
| 마우스 드래그 (좌클릭) | StackScrollTool drag mode |
| 마우스 드래그 (우클릭) | PanTool |
| 마우스 드래그 (가운데) | ZoomTool |
| Toolbar ◀/▶ | ±1 slice |
| Toolbar 입력 box | jump to N |
| Series strip 카드 click | series jump (해당 series 첫 슬라이스) |

키보드 focus 가 viewport 안에 있을 때만 ↑/↓/PgUp 활성. focus 가 toolbar input 에 있으면 input 본연 동작.

---

## 8. 디자인 토큰

portal-redesign §4 토큰 전부 그대로 차용. 본 명세에서 **신규로 4 개만 추가** (Kyle 승인 후 UI_GUIDE 승격 권고):

| 토큰 | 값 | 용도 |
|------|-----|------|
| `--phi-scrub-success` | `#15803d` (= existing `--color-success-fg`) | 8/8 layer pass dot · slice strip dot verified |
| `--phi-scrub-warn` | `#b45309` (= existing `--color-warning-fg`) | 7/8 (1 layer manual_review) · slice strip dot quarantined |
| `--phi-scrub-quarantine` | `#94a3b8` (= existing slate-400) | 격리 상태 회색 · skipped/na layer dot |
| `--viewport-bg` | `#000000` | Cornerstone3D 캔버스 배경 |

신규 토큰 4 개 모두 **기존 색의 의미 alias** 로, palette 자체에는 새 색을 추가하지 않는다. UI_GUIDE 승격 시 "PHI status semantic alias" 그룹으로 묶어서 등재 권고.

**금지된 신규 토큰**:
- 신규 폰트 (Pretendard + Inter 그대로).
- 신규 spacing/radius/shadow.
- 다크 모드 별도 토큰 (portal-redesign K-7 결정 = v0.1 라이트 고정 그대로).

---

## 9. 반응형 / 디바이스

### 9.1 우선순위

dev-spec NFR + portal-redesign §15.1 K-9 결정 (deferred desktop-only) 그대로:

| 디바이스 | 지원 | 비고 |
|---------|------|------|
| Desktop ≥ 1280px | ✓ 풀 viewport (920×600) + 우측 strip | Phase 1 타깃 |
| Desktop 1024–1279px | ✓ best-effort: viewport 축소 (700×500) + strip 하단 가로 | Phase 1 |
| Tablet (iPad ~1024px) | △ 1-thumbnail fallback + 안내 메시지 | Phase 1 |
| Mobile < 768px | ✗ 1-thumbnail fallback + 안내 메시지 | Phase 1 |

### 9.2 모바일 / lite-tier 처리 (Phase 2 deferred · placeholder)

dev-spec FR-FSP 제외 항목 + 본 명세 §5.4 와 시각적으로 동일:

```
┌────────────────────────────────────────┐
│  [icon: monitor]                       │
│                                        │
│  Full-slice preview available on       │
│  desktop                               │
│                                        │
│  데스크톱에서만 전체 슬라이스          │
│  미리보기를 사용할 수 있습니다         │
│                                        │
│  [ View single thumbnail ↓ ]           │
└────────────────────────────────────────┘
```

- portal-redesign K-9 의 `Best viewed on desktop ≥ 1280px` banner 와 톤 일치.
- Phase 2 에서 cine animation (TCIA-style WebM) 이 이 자리에 들어가도록 **컴포넌트 슬롯 예약**:
  ```tsx
  <ViewerArea>
    {isDesktop ? <FullSlicePreviewViewport ... /> :
      isCineAvailable ? <CineAnimationViewer ... /> :    // ← Phase 2 슬롯
      <SingleThumbnailFallback />}
  </ViewerArea>
  ```

---

## 10. 접근성 (WCAG 2.1 AA)

portal-redesign §8 그대로 + viewport 특수 요구.

### 10.1 키보드 navigation

- 모든 슬라이스 접근 가능 (↑/↓/PgUp/PgDn/Home/End — §7.5).
- Tab 순서: viewport canvas (focusable) → toolbar (◀, slice input, preset, zoom, fit, reset, 3D-disabled) → series strip 카드 (n 개) → 페이지 다음 영역.
- viewport canvas 는 `tabindex="0"` + `role="application"` (custom interactions) + `aria-label` (현재 슬라이스 정보).
- 첫 진입 hint overlay 는 키보드 focus 변화 없음 (passive).

### 10.2 스크린리더 (ARIA)

- viewport canvas `aria-label` 동적 갱신:
  - EN: `Slice {current+1} of {total}, modality {MG}, hospital {SEOUL-A2}, KCD {J18.9}`
  - KR: `슬라이스 {current+1} / {total}, 모달리티 {MG}, 병원 {SEOUL-A2}, KCD {J18.9}`
- 슬라이스 변경 시 SR announce: `aria-live="polite"` 영역에 `Slice {current+1}` 만 출력 (1초 throttle, 휠 연속 입력 시 spam 방지).
- Series strip 카드 = `<button>` semantic + `aria-pressed={active}`.
- DeIdChainStamp / PhiScrubIndicator = `<article aria-labelledby="...">` 으로 SR 묶음 인식.
- Quarantine placeholder slice = `aria-label="Slice {idx} quarantined for PHI protection"`.
- 3D ⊘ 버튼 = `aria-disabled="true"` + `aria-describedby="tooltip-3d-disabled"`.

### 10.3 색 대비 / 색맹

- viewport 위의 텍스트 (De-ID stamp, KCD label, slice counter) → 검정 배경 위 흰색 = 21:1 (AAA 충분).
- PhiScrubIndicator dot color 만으로 상태 구분 금지 — 항상 ✓ / ⚠ / ⊘ 아이콘 동반.
- Slice strip dot 도 격리 시 ⚠ 아이콘 hover 시 표시.
- Toolbar disabled 3D 버튼 = 색 외에 ⊘ 아이콘 + tooltip 이중 표시.

### 10.4 모션

- `prefers-reduced-motion: reduce` 감지:
  - 첫 진입 hint overlay fade 비활성 (정적 표시 후 1.5s 후 비표시).
  - 슬라이스 변경 transition 비활성 (즉시 swap).
  - skeleton shimmer 비활성 (정적 회색).
- Cornerstone3D 자체 rendering 은 reduced-motion 에 영향 받지 않음 (canvas paint).

---

## 11. 국제화 (ko / en)

### 11.1 텍스트 표

| Key | EN | KR |
|-----|----|----|
| `viewport.hint.scroll` | Scroll to navigate | 스크롤로 탐색 |
| `viewport.hint.keys` | ↑↓  Page  Home/End | ↑↓  Page  Home/End |
| `viewport.hint.drag` | Drag for stack | 드래그로 스택 이동 |
| `viewport.deid_chain.label` | De-ID Chain | 비식별 체인 |
| `viewport.deid_chain.verified` | verified | 검증됨 |
| `viewport.deid_chain.partial` | partial | 부분 |
| `viewport.phi_scrub.label` | PHI Scrub | PHI 스크럽 |
| `viewport.phi_scrub.summary` | {passed} / {total} | {passed} / {total} |
| `toolbar.slice_counter` | Slice {n} / {total} | 슬라이스 {n} / {total} |
| `toolbar.preset.ct_lung` | CT Lung | CT 폐 |
| `toolbar.preset.ct_abdomen` | CT Abdomen | CT 복부 |
| `toolbar.preset.ct_bone` | CT Bone | CT 뼈 |
| `toolbar.preset.ct_brain` | CT Brain | CT 뇌 |
| `toolbar.preset.mr_percentile` | MR Auto | MR 자동 |
| `toolbar.preset.mg_voi_lut` | MG VOI LUT | MG VOI LUT |
| `toolbar.preset.us_passthrough` | US 8-bit | US 8-bit |
| `toolbar.zoom.fit` | Fit | 맞춤 |
| `toolbar.zoom.100` | 100% | 100% |
| `toolbar.reset` | Reset | 리셋 |
| `toolbar.3d_disabled.tooltip` | 3D reconstruction disabled for de-identification | 비식별화를 위해 3D 재구성이 비활성화됨 |
| `quarantine.title` | Full-slice preview pending PHI re-verification | 미리보기는 PHI 재검증 대기 중입니다 |
| `quarantine.body` | This study's full-slice preview was paused after our automated scrub flagged a potential PHI artifact. Our team has been notified and will verify within 24 hours. | 자동 스크럽이 잠재 PHI 아티팩트를 감지하여 미리보기가 일시 중지되었습니다. 담당자에게 알림이 발송되었으며 24시간 내에 검증됩니다. |
| `quarantine.fallback_cta` | View single thumbnail | 단일 썸네일 보기 |
| `quarantine.contact_cta` | Contact support | 지원 문의 |
| `quarantine_slice.label` | Slice {n} quarantined | 슬라이스 {n} 격리됨 |
| `mobile_fallback.title` | Full-slice preview available on desktop | 데스크톱에서만 전체 슬라이스 미리보기를 사용할 수 있습니다 |
| `series_strip.title` | Series ({n}) | 시리즈 ({n}) |
| `series_strip.legend.verified` | verified | 검증됨 |
| `series_strip.legend.quarantined` | quarantined | 격리됨 |

### 11.2 길이 / 줄바꿈

- 한국어 평균 30% 짧음 — 모든 toolbar 라벨이 충분히 들어감.
- KCD 진단명 (예: `Pneumonia, unspecified` / `폐렴, 상세불명`) 은 viewport 좌상단 공간이 좁으므로 1 줄로 ellipsis · hover tooltip 으로 풀 텍스트.
- Quarantine banner 본문은 EN/KR 동시 표시 (긴급 메시지의 신뢰성 위해 의도적 중복).
- `word-break: keep-all` 한국어 기본 적용.

### 11.3 KCD 코드 표시

dev-spec §1.2 RadiVault 차별화 #3 (KCD ontology) — viewport 좌상단에 KCD 코드 + 한국어 진단명 동시 표시:

```
[ CT ]   KCD: J18.9
         Pneumonia, unspecified · 폐렴, 상세불명
```

- KCD 가 매핑되지 않은 study 는 KCD 줄 미표시 (modality badge 만).
- locale 우선순위: 영어 모드 = EN 우선 + KR 보조, 한국어 모드 = KR 우선 + EN 보조.

---

## 12. 차별화 — Segmed Openda 와 시각 비교

dev-spec §1.2 + 리서치 §5 의 차별화 포인트를 **mockup HTML 안에서 시각적으로 명시**한다. 이 비교 표는 mockup 우측 또는 별도 anchor 섹션 (`#radivault-vs-segmed`) 에 dev mode 에서만 노출 가능 (production 에서는 마케팅 페이지에 별도 노출).

| 요소 | Segmed Openda | RadiVault |
|------|---------------|-----------|
| 메인 viewport | 단일 Cornerstone3D StackScrollTool | 동일 |
| Series navigation | 좌측 OHIF-style strip | **우측** (좌측 facet 가 search 페이지에서 우선이므로 viewer 진입 후 시각 일관성) |
| Provenance 표시 | 없음 (study UID only) | **De-ID Chain stamp** (병원 hash + UID tail + 8-layer ✓) |
| PHI scrub status | 없음 | **PhiScrubIndicator** (L1..L8 dot per study + per-slice strip dot) |
| Diagnostic ontology | sparse (study description text only) | **KCD-7 코드 + EN/KR 한글 진단명** viewport 안 |
| Hospital region | 없음 (혹은 sparse) | **`HOSP-A2 · Seoul`** viewport 좌하단 (병원 동의 권역만) |
| 3D / MPR | 활성 (옵션) | **항상 disabled · 시각 명시** (L8 가드의 의도성 강조) |
| Modality preset | manual W/L slider | **자동 적용 + 표시** (Phase 1 read-only, 1.1+ override 가능) |

mockup 의 우측 또는 하단에 위 표를 ASCII 또는 HTML 표로 1 회 표시 — **개발 검토용** 으로 시각화.

---

## 13. 컴포넌트 계층 (개발자 위임 트리)

```
<StudyDetailPage> (portal-redesign §11.4 그대로)
  ├── <Header />                         ← 변경 없음
  ├── <HospitalOriginRow />              ← 변경 없음
  ├── <MetadataGrid />                   ← 변경 없음
  ├── <SeriesList />                     ← "currently viewing" 라벨 1줄 추가
  └── <ViewerArea>                       ← 신규 wrapper (기존 ViewerStub 위치)
        ├── (loading) <SkeletonViewport />
        ├── (verified) <FullSlicePreviewViewport>
        │     ├── <Cornerstone3DCanvas />   ← Cornerstone3D StackViewport mount 지점
        │     ├── (overlay layer)
        │     │     ├── <ModalityBadge />          (좌상단, 재사용 §6.8)
        │     │     ├── <KcdLabelStrip />          (좌상단 modality 옆)
        │     │     ├── <DeIdChainStamp />         (우상단, §6.5)
        │     │     ├── <PhiScrubIndicator />      (DeIdChainStamp 아래, §6.6)
        │     │     ├── <HospitalRegionStrip />    (좌하단)
        │     │     └── (mount-only) <HintOverlay />
        │     ├── <SeriesThumbnailStrip />         (우측, §6.2)
        │     └── <ViewportToolbar>                (하단)
        │           ├── <SliceCounter />           (§6.3)
        │           ├── <ModalityPresetToggle />   (§6.4)
        │           ├── <ZoomControl />
        │           ├── <ResetButton />
        │           └── <ThreeDDisabledButton />   (L8 가드 시각)
        ├── (phi_detected | failed) <QuarantineBanner />  (§6.7)
        ├── (pending | processing) <PreviewPendingState />
        ├── (mobile / WebGL N/A) <MobileFallback />
        └── (always) <SingleThumbnailCard />   (모든 fallback 의 하단 공통)
```

---

## 14. 수용 기준 (시각 · 행동)

dev-spec §10 의 AC-11..AC-19 (BFF + UI 영역) 을 시각 관점으로 재기술. 본 §14 는 디자인 검수 (시각·인터랙션) 한정.

- [ ] **DA-1**: ViewerArea 가 `{#study-detail-v1}` ViewerStub 자리에 정확히 들어가고, 기존 메타데이터 grid · Series 리스트 · Header 는 변경되지 않았다.
- [ ] **DA-2**: 데스크톱 1280px 에서 viewport 64% / strip 36% 비율 유지. height 640px ± 20.
- [ ] **DA-3**: viewport 우상단에 De-ID Chain stamp + PHI Scrub indicator 가 항상 표시되고, 검정 배경 위 텍스트 대비 ≥ 4.5:1.
- [ ] **DA-4**: 첫 진입 시 hint overlay 가 1초 후 fade out (또는 `prefers-reduced-motion` 시 정적). localStorage 저장 후 재진입 시 미표시.
- [ ] **DA-5**: 3D 토글 버튼이 disabled 상태로 시각적으로 명백 (회색 + ⊘ 아이콘 + cursor-not-allowed).
- [ ] **DA-6**: hover 시 tooltip "3D reconstruction disabled for de-identification" / "비식별화를 위해 3D 재구성이 비활성화됨" 노출.
- [ ] **DA-7**: 키보드만으로 모든 슬라이스 접근 가능 (↑/↓/PgUp/PgDn/Home/End). focus indicator 명확.
- [ ] **DA-8**: aria-label 이 슬라이스 변경마다 정확히 갱신 (SR 시뮬레이션 확인). live region throttle 1초.
- [ ] **DA-9**: phi_detected study 진입 시 QuarantineBanner 가 viewport 자리에 렌더되고, 하단에 1-thumbnail fallback. ko/en 본문 동시 표시.
- [ ] **DA-10**: quarantined_partial study 의 격리된 슬라이스가 placeholder (회색 grid + ⚠ 라벨) 로 표시되고, strip dot 이 yellow ⚠.
- [ ] **DA-11**: SeriesThumbnailStrip 이 series ≥ 2 일 때만 표시. series=1 study 는 viewport 100% width.
- [ ] **DA-12**: feature flag off 시 ViewerArea 가 ViewerStub (1-thumbnail) 으로 회귀, Cornerstone3D import 발생하지 않음 (network tab 확인).
- [ ] **DA-13**: 모바일 (< 768px) 진입 시 MobileFallback 메시지 + 1-thumbnail. viewport mount 시도 안 함.
- [ ] **DA-14**: KCD 코드가 매핑된 study 는 좌상단에 코드 + 한국어 진단명 표시. locale 따라 우선 순위.
- [ ] **DA-15**: 모든 신규 텍스트가 ko/en dictionary 에 정의되어 있고 (§11.1), 누락 시 빌드 fail (CI lint).
- [ ] **DA-16**: portal-redesign §4 토큰 외에 `--phi-scrub-*` 3 개 + `--viewport-bg` 1 개만 신규로 등장. 그 외 신규 색/spacing/radius 0 건 (CI grep).
- [ ] **DA-17**: WCAG 4.5:1 대비 자동 검증 (axe-core) 통과. viewport 위 모든 텍스트 + toolbar.
- [ ] **DA-18**: mockup HTML (`docs/specs/mockups/full-slice-preview-jpg/study-detail.html`) 이 v3 styles.css 토큰을 import 하여 작성됨. 신규 CSS 정의 5 줄 이내 (신규 토큰 4 개만).

---

## 15. 오픈 질문 / Kyle 결정 필요

K 시리즈 번호 = portal-redesign 의 K-1..K-12 이어서. **K-13..K-18 모두 Kyle 결정 완료 (2026-04-27).**

| # | 항목 | Kyle 결정 | 적용 |
|---|------|-----------|------|
| **K-13** | viewport 우측 strip vs 하단 strip | **우측 OK** | §4 ViewerArea 명세 그대로 유지 |
| **K-14** | KCD 진단명 영문 표기 | **designer 추천 (Phase 2 deferred)** | Phase 1.5 에 별도 dev-spec (`dev-spec-text-search-description-phase15.md`) 으로 locale-aware ICD-10/KCD-8 라벨링 처리. 본 Phase 1 = KCD 한글 + ICD-10 영문 매핑. |
| **K-15** | hint overlay localStorage TTL | **hint overlay 자체 제거** | viewport 하단 SliceCounter ("Slice 142 / 850") 가 이미 명확하므로 1초 hint 불필요. `<NavigationHint>` 컴포넌트 § 6.x 에서 삭제. SliceCounter 만 유지. |
| **K-16** | DeIdChainStamp click 동작 | **DeIdChainStamp 자체 제거** | Kyle: "De-ID 는 무조건 되어야 하는 것 — 왜 알려줘야 하는가?" PHI 정제 = baseline 보장 사항이라 시각 노출 불필요. § 6.5 컴포넌트 삭제, § 4 ViewerArea 우상단 overlay 에서 제거. (PhiScrubIndicator 도 동일 논리지만 PHI 검증 *상태* 표시는 demo trust signal 로 유지 — Kyle 미언급) |
| **K-17** | 3D 토글 버튼 표시 여부 | **버튼 자체 미표시 (Phase 2 활성화 시 추가)** | "추후 진행, 현재는 오버스펙". § 4 viewport toolbar 에서 3D 토글 미렌더. L8 viewer 측 3D 차단 가드는 백엔드만 유지 (응답 헤더 `X-RadiVault-Preview-3D: disabled`). |
| **K-18** | quarantined_partial strip dot 가독성 | **dot grid 제거, SliceCounter 만 사용** | K-15 와 동일 — 영상 위 표시되는 slice number indicator 면 충분. 850 dot 5 줄 wrap 디자인 자체 제거. PhiScrubIndicator 의 8-layer dots 도 동일 정책 → 단순 텍스트 라벨 ("8/8 layers passed") 로 단순화. |

---

## 16. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-26 | @designer (Claude Opus 4.7 [1M]) | 최초 작성. dev-spec FR-FSP-12 + Kyle 7 결정 반영. ViewerArea 1 화면 (S-1), 컴포넌트 7 개 신규 + 1 재사용. 신규 토큰 4 개. mockup 1 HTML. K-13..K-18 신규 6 flag. |
| 0.2 | 2026-04-27 | main (Claude Opus 4.7 [1M]) | Kyle K-13..K-18 결정 반영. 컴포넌트 7 → 4 개 (DeIdChainStamp + NavigationHint + 3D 토글 버튼 제거; PhiScrubIndicator 단순화). 신규 토큰 4 → 3 개 (`--phi-scrub-success/warn/quarantine` 단순 텍스트 라벨로 변경). K-14 Locale 라벨링은 Phase 1.5 dev-spec 으로 분리. |

---

### NEXT_STEP
- **완료 산출물**:
  - `/Users/yonghyuk/Radivault/docs/specs/design-spec-full-slice-preview-jpg.md` (Draft v0.1)
  - `/Users/yonghyuk/Radivault/docs/specs/mockups/full-slice-preview-jpg/study-detail.html` (시각 검토용)
- **제안 다음 단계**:
  - `@developer` — `claude` 브랜치에서 6 주 일정 (W1 Alembic migration → W2 windowing/scrub → W3 Central endpoint + MinIO → W4 BFF + Cornerstone3D loader → W5 viewport UI + 컴포넌트 7 → W6 backfill CLI + e2e). 본 design-spec §6 컴포넌트 inventory 와 §13 계층 트리를 React 파일 분할 가이드로 사용.
  - `@qa` — Cornerstone3D viewport 키보드 navigation 전수 (DA-7), PHI badge 표시 정확도 (DA-3 / DA-9 / DA-10), 3D 가드 시각 (DA-5 / DA-6), feature flag fallback (DA-12), 모바일 fallback (DA-13).
- **UI_GUIDE.md 갱신 제안**:
  - 신규 토큰 3 개 (`--phi-scrub-success` / `--phi-scrub-warn` / `--viewport-bg`) 를 portal-redesign §4 토큰과 함께 UI_GUIDE 정식 편입 시 "PHI status semantic alias" + "Viewer surface" 그룹으로 추가. (v0.2: K-18 결정으로 quarantine 토큰 단순화)
  - 신규 컴포넌트 4 개 (`<FullSlicePreviewViewport>`, `<SeriesThumbnailStrip>`, `<SliceCounter>`, `<PhiScrubIndicator>`) 카탈로그 등재 권고. (v0.2: K-15/K-16/K-17 결정으로 7 → 4)
- **추가 디자인 필요**:
  - **v0.2 (Phase 1.1)** — manual W/L 슬라이더 UI (현 ModalityPresetToggle 의 dropdown 활성화).
  - **v0.3 (Phase 2)** — Cine animation viewer (모바일/lite-tier fallback 슬롯).
  - **별도 slug** — admin manual review queue UI (`/admin/preview-quarantine`, dev-spec FR-FSP-16 Phase 2).
  - **별도 slug** — 3D 토글 활성화 (K-17 Phase 2 — `dev-spec-3d-volume-rendering.md`).
- **Kyle 결정 완료**: K-13 (우측 OK) / K-14 (Phase 1.5 locale 분리) / K-15 (hint 제거) / K-16 (DeIdChainStamp 제거) / K-17 (3D 버튼 미표시) / K-18 (dot grid 단순화). 본 design-spec v0.2 에 모두 반영.
