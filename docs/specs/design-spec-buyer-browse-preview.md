# 디자인 명세 — Buyer Browse → Preview → Download Workflow

> **Status**: Draft v0.1 · **Feature slug**: `buyer-browse-preview` · **Last updated**: 2026-04-25
> **작성자**: @designer (Claude Opus 4.7)
> **근거**:
> - [`dev-spec-buyer-browse-preview.md`](./dev-spec-buyer-browse-preview.md) v0.1 — FR-PREVIEW-1..4, FR-DOWNLOAD-1..2, FR-API-1..2, FR-DATA-1, FR-OPS-1, NFR 11, AC 40+, Q-flag 7 (본 spec 의 단일 원본)
> - [`research/buyer-browse-preview-download.md`](../research/buyer-browse-preview-download.md) v1.0 — §3.2 Gradient 하이브리드 / §4.1 PS3.18 Sup 203 / §4.4 OHIF MVP 단축 경로 / §5.3 PHI 게이트 / §6.4 presigned TTL / §7.3 SaMD 비분류 / §8.1 D-13 MVP
> - [`design-spec-portal-redesign.md`](./design-spec-portal-redesign.md) v0.2 — §4 디자인 토큰 (Buyer blue · Slate · Status), §5 공유 컴포넌트 (CTA Pair · Compliance Badge), §11.3 StudyCard / DataTable Row, §11.4 StudyDetailPanel (본 spec 으로 **확장**)
> - [`design-spec-buyer-auth.md`](./design-spec-buyer-auth.md) v0.1 — 폼 인터랙션 톤 (focus ring, helper text 배치), modal 패턴 (ApiKeyRevealModal)
> - [`UI_GUIDE.md`](../UI_GUIDE.md) — placeholder. portal-redesign §4 가 사실상 단일 원본
>
> **Supersedes (시각)**:
> - 현 production `web/portal/src/components/StudyCard.tsx` (썸네일 영역 0) → 본 spec §6 으로 좌측 thumbnail slot 추가
> - 현 production `web/portal/src/app/studies/[uid]/StudyDetailClient.tsx` 의 `<StudyDetailPanel>` "DICOM viewer not included in v0.1" 스텁 → 본 spec §7 의 `<SliceViewer>` 로 교체

---

## 1. 디자인 개요

dev-spec §1 인용:
> "RadiVault Buyer 가 로그인 후 검색 카드 → 상세 슬라이스 viewer → 샘플 1 study 즉시 다운로드 까지 한 번에 흐를 수 있는 시각 preview 워크플로우. D-13 MVP 는 사전 렌더링된 JPEG 시퀀스 + 수동 OCR 검증된 5 sample study 만 노출."

본 디자인 명세는 다음 산출물을 정의한다:

- **신규 컴포넌트 6 개** — `<StudyThumbnail>`, `<SliceViewer>`, `<SaMDFooter>`, `<SampleDownloadButton>`, `<QuotaIndicator>`, `<ModalityFallback>`.
- **수정 컴포넌트 2 개** — `<StudyCard>` (썸네일 slot 추가), `<StudyDetailPanel>` (viewer + 우측 사이드바 전면 개편).
- **신규 화면 0 개** — 기존 `/search`, `/studies/[uid]`, `/account` 의 in-place 확장.
- **i18n 키 신규 28 개** (EN+KR 페어, 14 키 × 2 언어).
- **디자인 토큰 신규 0 개 (제안 2 개 — Kyle 승인 후)** — 기존 portal-redesign §4 토큰 100% 재사용.
- **wireframe 항목 10 개** — planner 권고 1~10 전건.

**북극성**: D-13 무대에서 글로벌 AI 의사결정자가 "Gradient Atlas / Segmed 와 동급의 buyer self-serve preview 경험" 으로 인식하도록, 다음 3 가지를 시각적으로 선명히 한다.
1. **Gradient 의 "instant image previews"** 에 견줄 수 있는 카드 썸네일 (256×256 JPEG, lazy-load, < 30 KB).
2. **"표시 only — 진단 아님"** 의 SaMD 비분류 보장을 footer 배너 + viewer 의 측정 도구 부재로 명시.
3. **"Cohort 주문 (5-phase)" vs "Sample 1-click 다운로드"** 의 두 CTA 를 시각적으로 명확히 분리.

---

## 2. 화면 목록

| ID | 화면명 | 경로 (EN) | 경로 (KR) | 주요 역할 | dev-spec FR |
|----|--------|-----------|-----------|-----------|-------------|
| S-1 | Search results (썸네일 추가) | `/search` | `/ko/search` | 카드 좌측 썸네일 + verified placeholder 분기 | FR-PREVIEW-1 |
| S-2 | Study detail (viewer 전면 개편) | `/studies/[uid]` | `/ko/studies/[uid]` | SliceViewer + Sample download CTA + SaMD footer | FR-PREVIEW-2·4, FR-DOWNLOAD-1 |
| S-3 | Account (Quota indicator 추가) | `/account` | `/ko/account` | 일일 sample-download 잔여 표시 | FR-DOWNLOAD-1 (Q-6) |

**화면 신규 0** — 모두 기존 라우트의 in-place UI 확장. 라우터 변경·신규 페이지 0 건.

---

## 3. 사용자 플로우

### 3.1 Happy path — Sample 다운로드 (60–90 초, 데모 Scene 5 와 동일)

```
[/dashboard]
   ↓ "Open search" 클릭
[/search]                                     ← S-1
   ↓ verified study (5 건) 카드에 thumbnail 표시
   ↓ 1 건 카드 클릭
[/studies/{verified_uid}]                     ← S-2
   ↓ SliceViewer 첫 슬라이스 로드 (< 500 ms)
   ↓ 슬라이더 drag · ↑↓ 키 · 마우스 wheel 로 슬라이스 navigation
   ↓ SaMD footer 항상 노출 (sticky bottom)
   ↓ 우측 사이드바 [Download sample DICOM] 클릭
[POST /api/studies/{uid}/sample-download]
   ↓ 200 + presigned URL → spinner → toast "Download started"
   ↓ <a download> 자동 트리거 → 새 탭/브라우저 download bar
[Quota indicator 0 → 1 즉시 갱신]
   ↓ 사용자가 (선택) `/account` 진입
[/account]                                    ← S-3
   ↓ "Today: 1/1 sample downloads" 표시
```

### 3.2 권한 없음 — 비로그인 buyer 가 thumbnail URL 직접 접근

```
[브라우저 주소창] /api/studies/{uid}/thumbnail
   ↓ BFF middleware: BuyerSession 없음
[401 ERR_AUTH_INVALID]
   ↓ HTTP 401 (브라우저는 빈 이미지 렌더 — 카드에서 placeholder 로 대체)
또는
[/search] → 비로그인 상태 진입
   ↓ middleware redirect
[/signin?next=/search]
   ↓ signin 후 search 복귀, 모든 thumbnail 정상 로드
```

### 3.3 에러 — verified 외 study 의 viewer 진입

```
[/studies/{pending_uid}]                      ← URL 직접 입력 또는 245 study 중 하나
   ↓ GET /api/search/studies/{uid} (metadata) → 200 (메타는 그대로 노출)
   ↓ <SliceViewer> 자리에 <ModalityFallback>:
     ┌─────────────────────────────────────────┐
     │  [icon: monitor-off]                    │
     │  Preview unavailable for this study     │
     │  PHI verification pending.              │
     │  [ Browse verified studies → ]          │
     └─────────────────────────────────────────┘
   ↓ 우측 사이드바 [Download sample DICOM] 버튼 disabled + 툴팁
     "Sample download requires verified preview status."
   ↓ [Add to cohort] 버튼은 정상 활성 (cohort order 흐름은 verified 무관)
```

### 3.4 에러 — sample-download 일일 quota 초과

```
[/studies/{verified_uid}]
   ↓ [Download sample DICOM] 클릭 (오늘 2번째)
[POST /api/studies/{uid}/sample-download]
   ↓ 429 ERR_QUOTA_EXCEEDED + Retry-After: <seconds>
[버튼 disabled 전환 + toast]
   "Daily limit reached. Resets at 00:00 KST."
   ↓ 우측 QuotaIndicator "Today: 1/1" → red status
   ↓ 사용자는 cohort 주문은 계속 가능 ([Add to cohort] 활성)
```

### 3.5 에러 — Thumbnail 로드 5xx (네트워크 일시 장애)

```
[/search]
   ↓ IntersectionObserver fire → GET /api/studies/{uid}/thumbnail
[503 또는 timeout]
   ↓ 컴포넌트 자동 1회 재시도 (NFR-PERF-1)
   ↓ 재시도 실패 시 placeholder + 작은 "Retry" 링크
     ┌─────────────────────┐
     │  [icon: image-off]  │
     │  Preview unavailable│
     │  [ Retry ]          │
     └─────────────────────┘
   ↓ Retry 클릭 → 다시 GET → 200 시 thumbnail 교체
```

### 3.6 부분 실패 — viewer 로딩 중 일부 frame 5xx

```
[/studies/{verified_uid}]
   ↓ <SliceViewer> 첫 frame OK (slice 1)
   ↓ slice 2 preload → 5xx
   ↓ 슬라이더는 정상 표시 (slice_count 는 메타에서 옴)
   ↓ slice 2 navigation 시: 메인 영역에 inline error
     ┌─────────────────────────┐
     │  Slice 2 of 18          │
     │  Failed to load. Retry? │
     │  [ Retry ] [ Skip ]     │
     └─────────────────────────┘
   ↓ 다른 슬라이스 navigation 은 차단 X
```

---

## 4. 디자인 토큰 (재사용 선언)

> **본 spec 은 신규 토큰을 정의하지 않는다.** [`design-spec-portal-redesign.md`](./design-spec-portal-redesign.md) §4 의 토큰을 전면 승계. 아래 표는 본 spec 컴포넌트가 사용하는 토큰의 cross-reference.

### 4.1 색상 토큰 매핑

| 사용처 | portal-redesign §4 토큰 | 값 | WCAG AA 검증 |
|--------|------------------------|-----|--------------|
| `<StudyThumbnail>` border (default) | `--color-border` | `#e2e8f0` | UI 컴포넌트 3:1 ✓ |
| `<StudyThumbnail>` placeholder bg | `--color-bg-muted` | `#f8fafc` | — |
| `<StudyThumbnail>` placeholder icon | `--color-text-muted` | `#64748b` | 4.83:1 on bg-muted ✓ |
| `<StudyThumbnail>` skeleton gradient | `--color-bg-muted` → `--color-border` | `#f8fafc → #e2e8f0` | — |
| `<SliceViewer>` canvas bg | `#000000` | black (DICOM viewer 관행) | — |
| `<SliceViewer>` slider track | `--color-border-strong` | `#cbd5e1` | 3.14:1 ✓ |
| `<SliceViewer>` slider thumb | `--color-primary-600` | `#2563eb` | 4.54:1 on viewer-bg ✓ |
| `<SliceViewer>` slider focus ring | `--color-primary-700` + 3px ring at 40% | `#1d4ed8` | 6.80:1 ✓ |
| `<SliceViewer>` keyboard hint text | `--color-text-muted` | `#64748b` | 4.83:1 on bg-muted ✓ |
| `<SaMDFooter>` bg | status `Warning` light bg | `#fffbeb` | — |
| `<SaMDFooter>` text | status `Warning` dark fg | `#b45309` | **4.74:1 on warning bg ✓** |
| `<SaMDFooter>` border-top | status `Warning` darker | `#92400e` | 6.5:1 separator ✓ |
| `<SampleDownloadButton>` primary | `--color-primary-600` → hover `--color-primary-700` | `#2563eb → #1d4ed8` | 4.54 → 6.80 ✓ |
| `<SampleDownloadButton>` disabled | `--color-bg-muted` + `--color-text-muted` | `#f8fafc + #64748b` | — |
| Cohort secondary CTA (`<Button variant="ghost">`) | `--color-text` border | `#0f172a outline` | 18.69:1 text ✓ |
| `<QuotaIndicator>` "0/1" 정상 | `--color-text-muted` | `#64748b` | — |
| `<QuotaIndicator>` "1/1" 만료 | status `Error` dark fg | `#b91c1c` | 5.94:1 ✓ |
| `<ModalityFallback>` icon | `--color-text-muted` | `#64748b` | — |
| Toast (download started) | status `Info` light bg + dark fg | `#eff6ff + #1d4ed8` | 6.80:1 ✓ |
| Toast (quota exceeded) | status `Error` light bg + dark fg | `#fef2f2 + #b91c1c` | 5.94:1 ✓ |

### 4.2 Spacing 토큰 매핑

| 사용처 | 토큰 | 값 |
|--------|------|-----|
| `<StudyThumbnail>` 카드 내부 gap | `--space-4` | 16 px |
| `<StudyThumbnail>` 자체 크기 (모든 변형) | `space-64 = 256 px` | 256 px (정사각) |
| `<SliceViewer>` 내부 padding | `--space-4` | 16 px |
| `<SliceViewer>` slider 와 hint 사이 gap | `--space-2` | 8 px |
| 우측 사이드바 너비 | `space-80 = 320 px` | 320 px (StudyDetail 우측) |
| `<SaMDFooter>` 내부 padding | `--space-3` y · `--space-6` x | 12 / 24 px |
| `<SampleDownloadButton>` padding | `--space-3` y · `--space-4` x | 12 / 16 px |
| Sample CTA 와 Cohort CTA 사이 gap | `--space-3` | 12 px |

### 4.3 Typography 토큰 매핑

| 사용처 | 토큰 |
|--------|------|
| `<StudyThumbnail>` placeholder label | `text-xs / text-text-muted` |
| `<SliceViewer>` slice counter ("Slice 5 of 18") | `text-sm / font-mono / text-text-muted` |
| `<SliceViewer>` keyboard hint | `text-xs / text-text-muted` |
| `<SaMDFooter>` 본문 | `text-xs / font-medium / 12-13 px` (dev-spec FR-PREVIEW-4) |
| `<SampleDownloadButton>` label | `text-sm / font-medium` |
| `<QuotaIndicator>` 본문 | `text-xs / font-mono` (숫자 정렬) |

### 4.4 Radius / Shadow 토큰 매핑

| 사용처 | 토큰 | 값 |
|--------|------|-----|
| `<StudyThumbnail>` corner | `--radius-md` | 8 px |
| `<SliceViewer>` 컨테이너 corner | `--radius-md` | 8 px |
| `<SampleDownloadButton>` corner | `--radius-md` | 8 px |
| Toast corner | `--radius-md` | 8 px |
| Skeleton thumbnail 펄스 → no shadow | — | — |
| `<StudyThumbnail>` hover shadow | `--shadow-card` | §4.7 portal-redesign |
| `<SliceViewer>` 자체 shadow | none (canvas 자체 강조) | — |

### 4.5 신규 토큰 제안 (Kyle 승인 후 UI_GUIDE 등재 후보)

본 spec 에서는 정의하지 않고 **제안만**. dev-spec Q-flag 와는 별도 디자인 결정 사항.

| # | 토큰 | 값 (제안) | 근거 |
|---|------|-----------|------|
| **D-1** | `--surface-viewer-bg` | `#000000` | DICOM viewer 관행 — 의료 영상은 검정 배경에서 contrast 최대. portal-redesign §4 에는 검정 토큰 없음. |
| **D-2** | `--text-samd-warning` | `#b45309` (= status Warning dark fg) | 현재는 status warning dark fg 재사용 중. 의미 분리 필요 시 별도 alias. |

→ Kyle 결정 보류. 본 spec 코드 구현은 위 표 §4.1 의 "직접 hex 값" 또는 "기존 status 토큰 재사용" 으로 진행.

---

## 5. 컴포넌트 인벤토리

### 5.1 신규 6 개

| 컴포넌트 | 목적 | 상태 정의 | 우선순위 (P0/P1/P2) | dev-spec FR |
|----------|------|-----------|---------------------|-------------|
| `<StudyThumbnail>` | 256×256 JPEG / placeholder / skeleton 분기 | default · loading · verified · placeholder · error | **P0** | FR-PREVIEW-1 |
| `<SliceViewer>` | 슬라이스 시퀀스 navigation + zoom/pan/WL | loading · ready · partial-error · empty (single-frame) | **P0** | FR-PREVIEW-2 |
| `<SaMDFooter>` | "Display only — not for diagnostic use" sticky 배너 | default · (dismiss 불가) | **P0** | FR-PREVIEW-4 |
| `<SampleDownloadButton>` | 1-click DICOM 다운로드 CTA | default · downloading · disabled-not-verified · disabled-quota · error | **P0** | FR-DOWNLOAD-1 |
| `<QuotaIndicator>` | "Today: 0/1 sample downloads" 표시 | normal (0/1) · exhausted (1/1) · loading · error | **P1** | FR-DOWNLOAD-1 (Q-6) |
| `<ModalityFallback>` | viewer/thumbnail 자리의 placeholder | unavailable-pending · unavailable-phi · unavailable-modality · single-frame | **P1** | FR-PREVIEW-1·2 |

### 5.2 수정 2 개

| 컴포넌트 | 현 상태 | 변경 | 우선순위 |
|----------|---------|------|----------|
| `<StudyCard>` (`web/portal/src/components/StudyCard.tsx`) | 좌측 checkbox + ModalityBadge + 텍스트 메타 (썸네일 0) | 좌측에 `<StudyThumbnail>` slot 추가 (256×96 row 변형) — **§6 와이어 1 참조** | **P0** |
| `<StudyDetailPanel>` (`web/portal/src/components/buyer/StudyDetailPanel.tsx` + `web/portal/src/app/studies/[uid]/StudyDetailClient.tsx`) | 메타데이터 grid + Series list + ViewerStub ("DICOM viewer not included") | ViewerStub → `<SliceViewer>` 교체. 우측 사이드바 신규 — `<SampleDownloadButton>` + `<QuotaIndicator>` (mini) + 기존 `[Add to cohort]` 분리 배치. SaMDFooter 페이지 sticky bottom — **§7 와이어 참조** | **P0** |

### 5.3 재사용 (변경 0)

| 컴포넌트 | 출처 | 본 spec 사용처 |
|----------|------|----------------|
| `<MarketplaceNav>` | `web/portal/src/components/buyer/MarketplaceNav.tsx` | S-1, S-2, S-3 모두 상단 |
| `<ModalityBadge>` | `web/portal/src/components/ModalityBadge.tsx` | StudyCard, ModalityFallback (CT/MR/CR…) |
| `<ErrorBanner>` | `web/portal/src/components/ErrorBanner.tsx` | viewer 5xx, sample-download 5xx |
| Footer (KR 법적 블록 / EN minimal) | portal-redesign §5.7·5.8 | 페이지 하단 (SaMDFooter 와 별도. SaMDFooter 는 viewer-only sticky) |
| `<Button variant="primary"|"ghost">` | shadcn (portal-redesign §5.6 CTA Pair) | SampleDownloadButton, AddToCohortButton |
| Toast 시스템 | `react-hot-toast` (또는 portal 내 기본 alert — Kyle 결정) | "Download started", "Daily limit reached" |

---

## 6. Wireframe 1 — `<StudyThumbnail>` (StudyCard 좌측 영역)

**dev-spec 근거**: FR-PREVIEW-1, planner 권고 항목 #1.

**위치**: `<StudyCard>` 의 좌측. checkbox 우측, ModalityBadge 좌측. 256×256 정사각 영역 (정사각 가독성 우선; row 컴포넌트는 row-height 96 px 로 letterbox 표시).

### 6.1 두 상태 ASCII 와이어

#### 6.1.1 verified — JPEG 표시

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ☐  ┌─────────┐  [CT]  …a3b4c5d6  CHEST                                     │
│     │         │                                                              │
│     │  [JPEG] │  287 instances · 142.0 MB · 2023 · HOSP-A2                  │
│     │         │                                                              │
│     │         │                                                              │
│     └─────────┘                                                              │
│      96×96 px    ← row 카드 변형 (검색 결과 list)                            │
└──────────────────────────────────────────────────────────────────────────────┘
```

- **이미지 src**: `/api/studies/[uid]/thumbnail` (BFF 라우트, JPEG stream).
- **렌더 방식**: `<img>` 태그 + `loading="lazy"` (브라우저 native lazy) + IntersectionObserver fallback (Safari 14 미만 호환).
- **alt 속성**: `alt="${StudyDescription || modality + ' study'} preview thumbnail"` — 의미 있는 콘텐츠 (장식 X). dev-spec FR-PREVIEW-1 준수.
- **object-fit**: `cover` (256×256 → 96×96 letterbox 시 가운데 crop).
- **border**: `1px solid --color-border`, hover 시 `--color-primary-600` (StudyCard 와 일관).
- **radius**: `--radius-md` (8 px).

> **검색 결과 row 와 카드 그리드의 두 변형**:
> - row 변형 (현재 `/search` default): 96×96 letterbox. 한 줄 row 내 fit.
> - grid 변형 (v0.2 future): 256×256 full size. grid view 토글 시.
> - **D-13 MVP 는 row 변형만 구현**. grid 변형은 v0.2.

#### 6.1.2 placeholder — modality 아이콘 + "Preview unavailable"

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ☐  ┌─────────┐  [MR]  …7e8f9a01  BRAIN                                     │
│     │ ┌──────┐│                                                              │
│     │ │  ▦   ││  142 instances · 88.4 MB · 2024 · HOSP-B1                  │
│     │ │ MR   ││                                                              │
│     │ └──────┘│                                                              │
│     │ Preview │                                                              │
│     │ unavail.│                                                              │
│     └─────────┘                                                              │
│   bg: bg-muted    ← preview_status != 'verified' (245 / 250 study)           │
│   icon + label                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

- **bg**: `--color-bg-muted` (#f8fafc).
- **center icon**: 32 px modality glyph (CT 아이콘 / MR 아이콘 / 기본 monitor-off). 색상 `--color-text-muted`.
- **label below icon**: `text-xs / text-text-muted` — EN: `Preview unavailable` / KR: `미리보기 없음` (i18n key `preview.unavailableShort`).
- **interactive**: 클릭 가능 (study detail 진입). detail 페이지에서도 동일 fallback 표시.
- **modality 글리프 매핑** (`<ModalityFallback>` §10 와 공유):
  - CT: stacked-rectangles
  - MR: brain icon
  - CR/DR: chest x-ray icon
  - MG: mammography icon
  - PT/PET: dot-grid icon
  - US: wave icon
  - 기본: monitor-off icon (그 외 + null)

### 6.2 Loading skeleton

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ☐  ┌─────────┐  [   ]  ░░░░░░░░  ░░░░░░░                                   │
│     │░░░░░░░░░│                                                              │
│     │░ ░ ░ ░ ░│  ░░░ ░░░░░░░░░ · ░░░░ ░░ · ░░░░ · ░░░░░░░                  │
│     │ ░ ░ ░ ░ │                                                              │
│     │░ ░ ░ ░ ░│                                                              │
│     └─────────┘                                                              │
│  gradient pulse, 1.5s ease-in-out infinite                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

- **gradient**: linear `--color-bg-muted` → `--color-border` → `--color-bg-muted`, 1.5 s 무한 반복.
- **`prefers-reduced-motion: reduce`**: 펄스 비활성, 정적 `--color-bg-muted` 단색.
- **표시 시점**: IntersectionObserver fire 직후, fetch 완료 전.

### 6.3 5xx 에러 — Retry 링크

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ☐  ┌─────────┐  [CT]  …a3b4c5d6  CHEST                                     │
│     │ ┌──────┐│                                                              │
│     │ │  ⚠   ││  287 instances · 142.0 MB · 2023 · HOSP-A2                 │
│     │ └──────┘│                                                              │
│     │ Preview │                                                              │
│     │ failed  │                                                              │
│     │ [Retry] │  ← text-xs / text-primary-600 / underline                    │
│     └─────────┘                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

- **자동 재시도**: 1 회 (NFR-PERF-1 의 fallback chain 구현). 자동 재시도 실패 후 위 표시.
- **수동 Retry**: 클릭 시 컴포넌트 state reset → fetch 재시도.
- **에러 분기**:
  - 404 → 즉시 placeholder (재시도 X).
  - 5xx / network → 재시도 1회 → 실패 시 위 위 와이어.
  - 401 → silent placeholder (세션 가드 다른 곳에서 처리).
  - 403 (`ERR_PREVIEW_NOT_VERIFIED`) → placeholder (verified 아닌 study, 정상 분기).

---

## 7. Wireframe 2 — `<SliceViewer>` (StudyDetail main viewer)

**dev-spec 근거**: FR-PREVIEW-2, planner 권고 항목 #2. SaMD 비분류 (FR-PREVIEW-4) 의 핵심 enforce 지점.

**위치**: `/studies/[uid]` 페이지의 메인 영역 (좌측 큰 영역). 우측은 사이드바 (320 px). 페이지 헤더는 메타데이터 + Series 리스트 (기존 StudyDetailPanel 일부 유지).

### 7.1 SliceViewer 풀 와이어 (multi-slice CT/MR)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│  [◆ RadiVault Marketplace]   Search  Orders  Docs  Account            [Sign out]    │  ← MarketplaceNav (재사용)
├──────────────────────────────────────────────────────────────────────────────────────┤
│  ← Back to results              StudyInstanceUID: 1.2.840.…1234                      │  ← Header bar
├──────────────────────────────────────────────────────────────────────────────────────┤
│  ◆ HOSP-A2 · From this hospital's pool of 87 studies                                 │  ← Hospital origin (재사용)
├──────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌────────────────────────────────────────────────────┐  ┌────────────────────────┐ │
│  │                                                    │  │ Sample download        │ │
│  │                                                    │  │ ──────────────────     │ │
│  │                                                    │  │                        │ │
│  │                                                    │  │ [ Download sample      │ │
│  │                                                    │  │   DICOM ]              │ │
│  │             [JPEG slice — 512×512]                 │  │  primary, full-width   │ │
│  │                                                    │  │                        │ │
│  │             black bg (#000000)                     │  │ Get one DICOM file     │ │
│  │                                                    │  │ for pydicom inspection.│ │
│  │                                                    │  │                        │ │
│  │                                                    │  │ Today: 0/1             │ │
│  │                                                    │  │ ──────────────────     │ │
│  │                                                    │  │                        │ │
│  │                                                    │  │ Add to cohort          │ │
│  │                                                    │  │ ──────────────────     │ │
│  └────────────────────────────────────────────────────┘  │                        │ │
│                                                          │ [ Add to cohort + ]    │ │
│  ◀  ●━━━━━━━━━●━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ▶   │  ghost, full-width     │ │
│     1                  9                              18 │                        │ │
│  Slice 9 of 18                                           │ Place a full order for │ │
│                                                          │ all studies in cohort. │ │
│  ↑↓ Slices  +/- Zoom  Drag Pan  Wheel Slices            │                        │ │
│                                                          │ ──────────────────     │ │
│                                                          │                        │ │
│                                                          │ Series                 │ │
│                                                          │  ① CHEST AXIAL 1.0mm   │ │
│                                                          │     287 imgs · 142 MB  │ │
│                                                          │  ② CHEST CORONAL MIP   │ │
│                                                          │     64 imgs · 32 MB    │ │
│                                                          └────────────────────────┘ │
│                                                                                      │
│  ──────────────────────────────────────────────────────────────────────────────      │
│  Modality   CT          Body Part   CHEST       Manufacturer  SIEMENS  Model SOMATOM│
│  Age        50-59       Sex         M           Study Date    2023-08-14            │
│  Slice Thk  1.0 mm      KVP         120         Pixel Spacing 0.78×0.78  ...        │
├──────────────────────────────────────────────────────────────────────────────────────┤
│  Display only — not for diagnostic use. RadiVault is not a medical device.   [SaMD] │  ← <SaMDFooter> sticky
│  Refer to your DICOM-conformant viewer for clinical decisions.                       │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 SliceViewer 컴포넌트 분해 (계층 트리)

```
<StudyDetailPanel>                                 (수정 컴포넌트 — §11.4 portal-redesign 확장)
├─ <Header>                                        (재사용)
│   ├─ <BackLink href="/search">                   ("← Back to results")
│   └─ <StudyUidDisplay>                           (text-mono / text-text-muted)
├─ <HospitalOriginBar>                             (재사용 — design-spec-portal-redesign §11.4)
├─ <main className="grid grid-cols-[1fr_320px] gap-6">
│   ├─ <SliceViewer>                               ★ 신규
│   │   ├─ <ViewerCanvas>
│   │   │   └─ <img src=`/api/studies/[uid]/series/${s}/frames/${f}`
│   │   │           className="object-contain bg-black"
│   │   │           aria-label={`Slice ${currentFrame} of ${totalFrames}`} />
│   │   ├─ <ViewerControls>
│   │   │   ├─ <SliderRow>
│   │   │   │   ├─ <PrevButton aria-label="Previous slice">◀</PrevButton>
│   │   │   │   ├─ <input type="range" min=1 max=N value=current
│   │   │   │            aria-label={dict.viewer.sliderLabel}
│   │   │   │            aria-valuemin=1 aria-valuemax=N aria-valuenow=current />
│   │   │   │   └─ <NextButton aria-label="Next slice">▶</NextButton>
│   │   │   ├─ <SliceCounter>"Slice 9 of 18"</SliceCounter>
│   │   │   └─ <KeyboardHint>"↑↓ Slices  +/- Zoom  Drag Pan  Wheel Slices"</KeyboardHint>
│   │   ├─ <ZoomControls>           (overlaid top-right of canvas)
│   │   │   ├─ <ZoomIn aria-label="Zoom in">+</ZoomIn>
│   │   │   ├─ <ZoomOut aria-label="Zoom out">−</ZoomOut>
│   │   │   └─ <ResetZoom aria-label="Reset zoom">⟲</ResetZoom>
│   │   └─ <WindowLevelControls>     (overlaid top-left of canvas, 작은 텍스트)
│   │       ├─ <BrightnessSlider aria-label="Brightness">
│   │       └─ <ContrastSlider aria-label="Contrast">
│   └─ <Sidebar>                     (right, 320 px width)
│       ├─ <SampleDownloadCard>      (★ §8 와이어)
│       │   ├─ <SampleDownloadButton>
│       │   ├─ <SampleDescription>
│       │   └─ <QuotaIndicator variant="inline">
│       ├─ <Divider />
│       ├─ <CohortCard>              (★ §9 와이어 — 명확히 분리)
│       │   ├─ <AddToCohortButton variant="ghost">
│       │   └─ <CohortDescription>
│       ├─ <Divider />
│       └─ <SeriesList>              (재사용 — 기존 StudyDetailPanel)
├─ <MetadataGrid>                    (재사용 — 기존 14 필드 grid)
└─ <SaMDFooter sticky />             (★ §8 와이어 — 페이지 sticky bottom)
```

### 7.3 viewer 기능 — 허용 / 금지

dev-spec FR-PREVIEW-2 의 SaMD 비분류 enforce. 디자인 명세에서 **시각적으로 부재** 를 보장한다.

| 기능 | 허용? | 디자인 표현 |
|------|-------|-------------|
| Zoom in/out | ✅ | 우상단 +/- 버튼 + 키보드 +/- |
| Pan (drag) | ✅ | canvas 위 mousedown→drag, cursor: grab/grabbing |
| Window-level (밝기/대비) | ✅ | 좌상단 brightness/contrast 미니 슬라이더 (CSS filter 적용) |
| Slice navigation | ✅ | 하단 슬라이더 + 키보드 ↑↓ + 마우스 wheel |
| **측정 (선/각도/거리/면적/ROI)** | ❌ | **컴포넌트에 측정 도구 버튼 0**. CI lint enforce. |
| **AI overlay / segmentation / heatmap** | ❌ | overlay layer 자체 없음. canvas 1 layer only. |
| **DICOM SEG / SR / RTSTRUCT 표시** | ❌ | series 리스트에서 SEG/SR series 자동 필터 (전송 0). |
| **진단 보조 텍스트 / quantitative readout** | ❌ | viewer 화면에 numeric overlay 0 (slice counter 만 허용). |

**디자인 enforce**:
- viewer 컴포넌트 폴더 (`web/portal/src/components/SliceViewer/`) 내 코드에 `measure` / `segment` / `diagnose` / `annotate` 키워드 0 건 (NFR-COMPLIANCE).
- code review checklist 에 "SaMD scope 위반 여부" 항목 추가 권고.

### 7.4 viewer 인터랙션 패턴 (키보드 / 마우스 / 터치)

#### 키보드

| 키 | 동작 |
|----|------|
| ↑ | 다음 슬라이스 (+1) |
| ↓ | 이전 슬라이스 (−1) |
| Page Up | +5 슬라이스 |
| Page Down | −5 슬라이스 |
| Home | 첫 슬라이스 (1) |
| End | 마지막 슬라이스 (N) |
| `+` 또는 `=` | Zoom in (×1.25) |
| `-` 또는 `_` | Zoom out (÷1.25) |
| `0` | Zoom reset (1.0×) |
| Tab | viewer ↔ 우측 사이드바 ↔ slider focus 전환 |
| Esc | viewer focus 해제 (page-level focus 복귀) |

#### 마우스

| 동작 | 결과 |
|------|------|
| Wheel up/down | 다음/이전 슬라이스 (±1, accel 옵션 X — D-13 MVP) |
| Click + drag (canvas) | Pan (cursor: grab → grabbing) |
| Click + drag (slider thumb) | 슬라이스 직접 jump |
| Hover (canvas) | cursor: grab |
| Click (slider track) | 클릭 위치로 jump |

#### 터치 (mobile best-effort)

| 제스처 | 결과 |
|--------|------|
| Swipe left/right | 다음/이전 슬라이스 (단 1 손가락) |
| Pinch | Zoom in/out |
| Two-finger drag | Pan |
| Tap & hold | (예약 — D-13 MVP 미구현) |

### 7.5 Loading / Error / Single-frame variants

#### 7.5.1 Loading (첫 슬라이스 fetch 중)

```
┌────────────────────────────────────────────────────┐
│                                                    │
│                                                    │
│                  ◐                                 │
│              spinner 32 px                         │
│           --color-primary-600                      │
│                                                    │
│         Loading slice 1 of 18                      │
│         text-sm / text-text-muted                  │
│                                                    │
│                                                    │
└────────────────────────────────────────────────────┘
  black bg (canvas-bg)
```

#### 7.5.2 Full error (5xx, viewer 자체 로드 실패)

```
┌────────────────────────────────────────────────────┐
│                                                    │
│              [icon: image-off 48 px]               │
│              --color-text-muted                    │
│                                                    │
│         Could not load slice viewer                │
│         text-base / text-text                      │
│                                                    │
│   The preview service is temporarily unavailable.  │
│   text-sm / text-text-muted                        │
│                                                    │
│              [ Retry ]                             │
│              primary button                        │
│                                                    │
│   request_id: req_01HX...                          │
│   text-xs / font-mono / text-text-muted            │
│                                                    │
└────────────────────────────────────────────────────┘
  bg: bg-muted (canvas-bg → bg-muted, 의도적 분리)
```

#### 7.5.3 Single-frame (CR/DR/MG) — 슬라이더 hidden

```
┌────────────────────────────────────────────────────┐
│                                                    │
│                                                    │
│                                                    │
│             [JPEG full-resolution]                 │
│                                                    │
│             zoom/pan/WL 동작 그대로                │
│                                                    │
│                                                    │
└────────────────────────────────────────────────────┘
  ◀ slider hidden (slice_count = 1)               ▶
  +/- Zoom  Drag Pan  ← 키보드 hint 도 슬라이스 제외
  
  Single-frame study (CR/DR/MG)
```

- **결정 로직**: `study.preview_slice_count === 1` → `<SliderRow>` 숨김 + `<SliceCounter>` 숨김 + `<KeyboardHint>` 에서 "Slices" 제거.
- **modality 별 분기 (§9 ModalityFallback 와 함께)**:
  - CT, MR, PT, NM (multi-slice): 슬라이더 enabled.
  - CR, DR, DX, MG, US (single-frame): 슬라이더 hidden, 큰 단일 이미지.

#### 7.5.4 Partial frame error (slice navigation 중 일부 frame 5xx)

```
┌────────────────────────────────────────────────────┐
│                                                    │
│                                                    │
│              [icon: alert-circle 24 px]            │
│              status Warning fg                     │
│                                                    │
│         Slice 7 failed to load                     │
│         text-sm                                    │
│                                                    │
│      [ Retry ]   [ Skip to slice 8 ]               │
│                                                    │
└────────────────────────────────────────────────────┘
  black bg (canvas-bg 유지)
  슬라이더 / 우측 사이드바 / SaMD footer 모두 정상
```

- **표시 조건**: 단일 frame fetch 실패 (다른 frame 은 정상 표시 가능).
- **Retry**: 해당 frame 재 fetch.
- **Skip**: 다음 frame 으로 navigation.

### 7.6 Visual hierarchy (StudyDetail 페이지 전체)

dev-spec 권고 (planner 항목 #1) 의 시각 계층:

1. **헤더** — `<MarketplaceNav>` (sticky top, h 64 px, z-20).
2. **Back link + StudyInstanceUID** (h 48 px).
3. **Hospital origin bar** (h 40 px, ◆ HOSP-A2 …).
4. **메인 영역** — `grid-cols-[1fr_320px] gap-6 px-6 py-6`:
   - 좌측 (1fr): **SliceViewer** — 가장 큰 시각 요소 (실 viewport 기준 600~800 px height).
   - 우측 (320 px): Sidebar — Sample download (top) → Cohort (mid) → Series list (bottom).
5. **Metadata grid** — viewer 아래 14 필드 (기존 그대로 유지, 2-col grid).
6. **SaMD footer** — 페이지 sticky bottom (`position: sticky; bottom: 0; z-30`).

**rationale**: viewer 가 페이지의 60–70% 시각 weight. SaMD footer 는 항상 보이되 viewer 만큼 강조하지 않음 (warning bg + small text). Sample download 는 우측 사이드바 최상단으로 "primary action".

---

## 8. Wireframe 3 — `<SaMDFooter>`

**dev-spec 근거**: FR-PREVIEW-4, planner 권고 항목 #3. SaMD 비분류 정책의 시각 enforce.

### 8.1 풀 와이어

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│  ⚠  Display only — not for diagnostic use. RadiVault is not a medical device.        │
│     Refer to your DICOM-conformant viewer for clinical decisions.                    │
│                                                                                      │
│                          Demo data based on TCIA — CC BY 3.0/4.0.                    │
└──────────────────────────────────────────────────────────────────────────────────────┘
  bg: status Warning light (#fffbeb)
  border-top: 1px solid status Warning darker (#92400e)
  padding: 12 px y · 24 px x
  text: 12-13 px / font-medium / status Warning dark fg (#b45309)
  position: sticky bottom-0 z-30 (viewer page)
  role="contentinfo"
  data-testid="samd-disclaimer"
```

### 8.2 i18n 변형

| locale | 본문 (warning) | TCIA attribution |
|--------|----------------|------------------|
| `en` | `Display only — not for diagnostic use. RadiVault is not a medical device. Refer to your DICOM-conformant viewer for clinical decisions.` | `Demo data based on TCIA — CC BY 3.0/4.0.` |
| `ko` | `표시 전용 — 진단 용도 사용 금지. RadiVault 는 의료기기가 아닙니다. 임상 판단은 DICOM 인증 뷰어에서 수행해주세요.` | `데모 데이터는 TCIA 기반 — CC BY 3.0/4.0.` |

### 8.3 디자인 결정

- **항상 표시**: viewer 페이지 (`/studies/[uid]`) 전체에서 sticky bottom. `dismiss` 버튼 0 (dev-spec 명시). fullscreen viewer mode (v0.2) 에서도 dismiss 불가.
- **Z-index**: `z-30` — toast (`z-40`) 보다 낮음, viewer canvas (`z-0`) 보다 높음.
- **Role**: `<footer role="contentinfo" data-testid="samd-disclaimer">`.
- **반응형**: mobile (≤ 768 px) 은 본문이 자동 줄바꿈 (`word-break: keep-all` for KR).
- **포커스 트랩 X**: footer 자체는 link/button 0 — focus 진입 점 없음 (장식 배너).
- **TCIA attribution**: viewer 페이지 한정 footer 우측. dev-spec §11.7 요구사항. 다른 페이지의 TCIA attribution 은 portal-redesign §6.6 Metrics 섹션의 단일 표시로 처리 (홈페이지/마케팅).

---

## 9. Wireframe 4 — `<SampleDownloadButton>` 과 우측 사이드바

**dev-spec 근거**: FR-DOWNLOAD-1, planner 권고 항목 #4·5.

### 9.1 우측 사이드바 풀 와이어 (Sample vs Cohort 분리)

```
┌────────────────────────┐
│ Sample download        │  ← section heading: text-base / font-semibold
│ ──────────────────     │
│                        │
│ ┌────────────────────┐ │
│ │ ↓ Download sample  │ │  ← <SampleDownloadButton variant="primary" full-width>
│ │   DICOM            │ │     bg: --color-primary-600
│ └────────────────────┘ │     hover: --color-primary-700
│                        │     text: white / font-medium / text-sm
│ Get one DICOM file     │  ← description: text-xs / text-text-muted
│ for pydicom            │     "Sample = 1 SOPInstanceUID, 단일 .dcm"
│ inspection.            │
│                        │
│ Today: 0/1             │  ← <QuotaIndicator variant="inline">
│ text-xs / font-mono    │     0/1: text-text-muted
│                        │     1/1: text-error / "Resets at 00:00 KST"
│ ──────────────────     │  ← Divider (--color-border)
│                        │
│ Add to cohort          │  ← section heading
│ ──────────────────     │
│                        │
│ ┌────────────────────┐ │
│ │ + Add to cohort    │ │  ← <Button variant="ghost" full-width>
│ └────────────────────┘ │     border: --color-border-strong
│                        │     hover: bg --color-bg-muted
│ Place a full order for │  ← description: text-xs / text-text-muted
│ all studies in cohort. │     "5-phase fulfillment, 24h–7d TTL"
│ 5-phase delivery.      │
│                        │
│ ──────────────────     │
│                        │
│ Series                 │  ← section heading
│ ──────────────────     │
│                        │
│ ① CHEST AXIAL 1.0mm    │
│   287 imgs · 142 MB    │
│ ② CHEST CORONAL MIP    │
│   64 imgs · 32 MB      │
│                        │
└────────────────────────┘
  width: 320 px (fixed)
  padding: --space-4
  divider style: 1px --color-border, vertical margin --space-4
```

### 9.2 Sample CTA 와 Cohort CTA 의 시각 분리 (planner 항목 #5)

**디자인 원칙**: 두 CTA 가 같은 화면에 있으나 **혼동 방지** 가 critical. dev-spec FR-DOWNLOAD-2 강조.

| 차원 | Sample download | Add to cohort |
|------|-----------------|---------------|
| **위치** | 사이드바 최상단 | 사이드바 두 번째 섹션 (divider 아래) |
| **버튼 variant** | `primary` (filled, --color-primary-600) | `ghost` (outlined) |
| **버튼 leading icon** | `↓` (download arrow) | `+` (plus) |
| **section heading** | "Sample download" | "Add to cohort" |
| **description text** | "Get one DICOM file for pydicom inspection." | "Place a full order for all studies in cohort. 5-phase delivery." |
| **응답 시간 시그널** | "Today: 0/1" — 즉시 다운로드 | "5-phase delivery" — 시간 소요 시그널 |
| **버튼 width** | full sidebar width (320 px) | full sidebar width (320 px) |
| **divider** | 두 섹션 사이 1px `--color-border` | — |

→ **시각적 우선순위**: filled vs outlined 로 즉시 구분. 색상 동일 (둘 다 primary 톤) 으로 브랜드 일관성 유지.

### 9.3 SampleDownloadButton — 5 가지 상태

#### 9.3.1 Default (verified study, quota 잔여)

```
┌────────────────────────┐
│ ↓ Download sample DICOM│   bg: --color-primary-600
└────────────────────────┘   text: white / text-sm / font-medium
                             padding: 12px y · 16px x
                             radius: --radius-md
                             cursor: pointer
                             focus: ring-3 --color-primary-700/40
```

#### 9.3.2 Downloading (spinner)

```
┌────────────────────────┐
│ ◐ Preparing…           │   bg: --color-primary-700 (slightly darker)
└────────────────────────┘   spinner 16px left of label
                             cursor: wait
                             aria-busy="true"
                             pointer-events: none (재클릭 방지)
```

#### 9.3.3 Disabled — verified 아님

```
┌────────────────────────┐
│ ↓ Download sample DICOM│   bg: --color-bg-muted
└────────────────────────┘   text: --color-text-muted
                             cursor: not-allowed
                             opacity: 0.6
                             aria-disabled="true"

  Tooltip on hover:
  ┌──────────────────────────────────────────┐
  │ Preview unavailable for this study.      │
  │ PHI verification pending.                │
  └──────────────────────────────────────────┘
  bg: --color-text (dark) / text: white / text-xs
  position: above button (popover top)
  arrow pointing down to button
```

#### 9.3.4 Disabled — quota 초과

```
┌────────────────────────┐
│ ↓ Download sample DICOM│   bg: --color-bg-muted
└────────────────────────┘   text: --color-text-muted
                             cursor: not-allowed
                             aria-disabled="true"

  Tooltip on hover:
  ┌──────────────────────────────────────────┐
  │ Daily limit reached.                     │
  │ Resets at 00:00 KST.                     │
  └──────────────────────────────────────────┘
```

#### 9.3.5 Error (5xx 또는 ERR_PRESIGN_FAILED)

버튼 자체는 default 로 복귀 (에러 상태는 toast 로 표시).

```
Toast (top-right, z-40):
┌──────────────────────────────────────────┐
│ ⚠ Sample download failed                 │
│   The download service is temporarily    │
│   unavailable. Please try again.         │
│                                          │
│   request_id: req_01HX...                │
│                          [ Dismiss ]     │
└──────────────────────────────────────────┘
  bg: status Error light (#fef2f2)
  border-left: 4px status Error dark (#b91c1c)
  text: --color-text
  request_id: text-xs / font-mono / text-text-muted
  duration: 8s (auto-dismiss) 또는 manual dismiss
```

### 9.4 micro-interaction (1-click happy path)

```
t=0       사용자 click [Download sample DICOM]
          → 버튼 즉시 "Downloading" 상태 전환 (spinner 표시)
t=0~300ms BFF/Central 처리 (DB lookup + Redis quota + S3 sign + audit INSERT)
t=300ms   Response 200 + presigned URL JSON 도착
          → toast "Download started" 표시 (info, top-right, 4s auto-dismiss)
          → invisible <a download href={presigned_url}> 자동 트리거
          → 브라우저 download bar 출현 (또는 새 탭)
t=300ms   QuotaIndicator 0→1 즉시 갱신 (optimistic, server confirm 무관)
          → "Today: 1/1" 표시 + status text-text-muted
          → 버튼 즉시 disabled (quota exhausted) 전환
t=300ms+  버튼 default 상태 (disabled-quota) 로 복귀
```

**toast 위치**: page-level top-right, `z-40`. SaMDFooter (z-30) 보다 위.

**toast 문구 (i18n)**:
- EN: `Download started — your browser will save the file.`
- KR: `다운로드를 시작했습니다 — 브라우저에서 파일이 저장됩니다.`

---

## 10. Wireframe 5 — `<QuotaIndicator>` (위치 2 곳)

**dev-spec 근거**: FR-DOWNLOAD-1 (Q-6, Redis quota), planner 권고 항목 #7.

### 10.1 위치 1: viewer 사이드바 (inline variant)

§9 와이어에 포함. "Today: 0/1" 또는 "Today: 1/1".

### 10.2 위치 2: `/account` 페이지 (full variant)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Account                                                                     │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Profile                                                                     │
│  ────────────────────                                                        │
│  Buyer ID:        buy_…1234                                                  │
│  Email:           kyle@radivault.io                                          │
│  Tier:            free                                                       │
│  Created:         2026-04-20                                                 │
│  Quota remaining: see below                                                  │
│                                                                              │
│  ────────────────────                                                        │
│                                                                              │
│  Daily quota                                                                 │
│  ────────────────────                                                        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Sample DICOM downloads                                             │    │
│  │                                                                     │    │
│  │  ████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░     │    │
│  │  Used: 0 / 1                                                        │    │
│  │                                                                     │    │
│  │  Resets at 00:00 KST · 8h 24m remaining                             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  API keys                                                                    │
│  ────────────────────                                                        │
│  (existing buyer-auth §6.5 wireframe — 변경 없음)                            │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 10.3 QuotaIndicator 변형 (3 variant)

#### 10.3.1 inline (viewer 사이드바)

```
Today: 0/1 sample downloads      ← text-xs / font-mono / text-text-muted
```

또는 quota 만료:

```
Today: 1/1 · Resets 00:00 KST    ← text-xs / font-mono / text-error
```

#### 10.3.2 full (account 페이지)

위 §10.2 와이어. progress bar (8px height, --color-primary-600 fill, --color-bg-muted track) + label + reset time.

#### 10.3.3 mini (header — v0.2 future)

```
[1/1 ●]                          ← red dot + count
```

D-13 MVP 미구현. v0.2 에서 MarketplaceNav 우측에 표시 검토.

### 10.4 데이터 소스

- BFF endpoint 신규 권고: `GET /api/account/quota` → `{daily_used: 0, daily_limit: 1, resets_at: "2026-04-26T00:00:00+09:00"}`.
- 또는 `POST /api/studies/[uid]/sample-download` 응답 envelope 에 `quota_after: {used: 1, limit: 1, resets_at: ...}` 포함 (단일 round-trip).
- D-13 MVP 권고: 후자 (round-trip 1 회로 즉시 갱신). dev-spec FR-API-2 의 sample-download response 확장 제안 (1 줄).

### 10.5 Loading / Error 상태

#### Loading

```
Today: …/1                       ← skeleton ellipsis
```

#### Error (BFF 5xx)

```
Today: ?/1 · [Retry]             ← question mark + retry link
```

---

## 11. Wireframe 6 — `<ModalityFallback>` (modality-specific viewer fallback)

**dev-spec 근거**: planner 권고 항목 #9.

5 sample study 의 modality 가 다양 (CT axial 시퀀스 / MR T1 / CR/DR 단일 frame). modality 별 다른 fallback 시각.

### 11.1 modality 별 시연

#### 11.1.1 CT (multi-slice axial) — multi-slice viewer

`<SliceViewer>` 풀 (§7.1) — 슬라이더 enabled.

#### 11.1.2 MR T1 (multi-slice) — multi-slice viewer

CT 와 동일 (`<SliceViewer>`, 슬라이더 enabled). modality 표시만 [MR] 배지.

#### 11.1.3 CR / DR (single-frame chest x-ray) — single-frame viewer

```
┌────────────────────────────────────────────────────┐
│                                                    │
│                                                    │
│             [JPEG full-resolution]                 │
│                                                    │
│             single chest x-ray                     │
│                                                    │
│                                                    │
└────────────────────────────────────────────────────┘
  ◀ slider hidden (slice_count = 1)               ▶
  +/- Zoom  Drag Pan  ← 슬라이스 키 hint 제외
  
  Single-frame study (CR)
```

#### 11.1.4 MG (mammography) — single-frame viewer

CR/DR 와 동일 (single-frame, 슬라이더 hidden). modality 배지 [MG].

#### 11.1.5 PT/PET, NM, US (multi-frame 가능) — multi-slice viewer

CT/MR 와 동일 패턴.

### 11.2 ModalityFallback (verified 아님 + modality 별 placeholder)

`<StudyThumbnail>` 의 placeholder 변형과 동일 글리프 (§6.1.2 매핑 표 재사용). viewer 페이지의 메인 영역에서:

```
┌────────────────────────────────────────────────────┐
│                                                    │
│                                                    │
│              [icon: mr-brain 64 px]                │
│              --color-text-muted                    │
│                                                    │
│         Preview unavailable for this study         │
│         text-base / text-text                      │
│                                                    │
│         PHI verification pending. Metadata is      │
│         visible below.                             │
│         text-sm / text-text-muted                  │
│                                                    │
│              [ Browse verified studies → ]         │
│              ghost button → /search?verified=1     │
│                                                    │
└────────────────────────────────────────────────────┘
  bg: --color-bg-muted
  height: 600 px (viewer canvas 자리 동일 유지)
```

### 11.3 모드 결정 표

| `preview_status` | `preview_slice_count` | 표시 |
|------------------|------------------------|------|
| `verified` | NULL or 0 | `<ModalityFallback variant="single-frame">` (sample DICOM 만 가능) |
| `verified` | 1 | `<SliceViewer>` single-frame variant (슬라이더 hidden) |
| `verified` | ≥ 2 | `<SliceViewer>` multi-slice variant (슬라이더 enabled) |
| `pending` | (any) | `<ModalityFallback variant="unavailable-pending">` |
| `phi_detected` | (any) | `<ModalityFallback variant="unavailable-phi">` (sample DL 도 disabled) |
| `not_applicable` | (any) | `<ModalityFallback variant="unavailable-modality">` (특수 modality) |

---

## 12. Wireframe 7 — `<StudyCard>` (수정) — 전후 비교

### 12.1 Before (현 production, dev-spec §0.2-1)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ☐  [CT]  …a3b4c5d6  CHEST                                                  │
│                                                                              │
│           287 instances · 142.0 MB · 2023                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 12.2 After (본 spec, FR-PREVIEW-1)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ☐  ┌─────────┐  [CT]  …a3b4c5d6  CHEST                                     │
│     │         │                                                              │
│     │  [JPEG] │  287 instances · 142.0 MB · 2023 · HOSP-A2                  │
│     │         │                                                              │
│     │  96×96  │                                                              │
│     │ verified│                                                              │
│     └─────────┘                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 12.3 변경 props

```typescript
// Before
type StudyCardProps = {
  pseudoStudyUid: string;
  modality: string | null;
  bodyPart: string | null;
  nInstances: number;
  sizeMb: number;
  studyYear: number | null;
  selected?: boolean;
  onToggle?: () => void;
};

// After (4 props 추가)
type StudyCardProps = {
  pseudoStudyUid: string;
  modality: string | null;
  bodyPart: string | null;
  nInstances: number;
  sizeMb: number;
  studyYear: number | null;
  selected?: boolean;
  onToggle?: () => void;
  // ★ 신규
  previewStatus?: "verified" | "pending" | "phi_detected" | "not_applicable";
  thumbnailUrl?: string;          // = `/api/studies/${uid}/thumbnail` (자동 생성 가능)
  studyDescription?: string | null;  // alt 텍스트 + 카드 본문 라벨
  hospitalOpaqueId?: string;      // HOSP-A2 chip (재사용 — design-spec-portal-redesign §11.3)
};
```

### 12.4 레이아웃 변경

- **gap**: `--space-4` (16 px) — checkbox 와 thumbnail 사이.
- **thumbnail slot 자체 너비**: 96 px (row 변형, 정사각).
- **flex-shrink: 0** — thumbnail 영역은 viewport 좁아도 96 px 유지. 우측 텍스트만 truncate.
- **선택 상태 (selected)**: 기존 `ring-2 ring-primary` 유지 + thumbnail 자체 outline 동기화.

---

## 13. 디자인 토큰 (재정의 — 본 spec 에서 신규 정의 0)

§4 에서 이미 cross-reference 표로 정리. 본 spec 은 **신규 토큰을 정의하지 않는다**. portal-redesign §4 의 토큰을 100% 재사용.

**향후 UI_GUIDE 등재 후보** (Kyle 승인 후):
- D-1: `--surface-viewer-bg` (= #000000)
- D-2: `--text-samd-warning` (= #b45309, status Warning dark fg alias)

---

## 14. i18n 문자열 표

i18n key 신규 14 개 × 2 언어 = **28 신규 entries**. `web/portal/src/lib/i18n.ts` 의 `Dict` 타입에 `viewer` 네임스페이스 (신규) + `preview` 네임스페이스 (신규) 추가 필요.

### 14.1 `preview.*` (썸네일 / 일반)

| key | EN | KR |
|-----|-----|-----|
| `preview.unavailableShort` | `Preview unavailable` | `미리보기 없음` |
| `preview.unavailablePending` | `PHI verification pending` | `PHI 검증 대기 중` |
| `preview.unavailablePhi` | `Preview blocked — PHI detected` | `미리보기 차단 — PHI 감지` |
| `preview.unavailableModality` | `Preview not available for this modality` | `이 모달리티는 미리보기 미지원` |
| `preview.thumbnailRetry` | `Retry` | `재시도` |
| `preview.thumbnailFailed` | `Preview failed` | `미리보기 실패` |
| `preview.browseVerified` | `Browse verified studies` | `검증된 study 보기` |

### 14.2 `viewer.*` (SliceViewer)

| key | EN | KR |
|-----|-----|-----|
| `viewer.sliderLabel` | `Slice number` | `슬라이스 번호` |
| `viewer.sliceCounter` | `Slice {n} of {total}` | `슬라이스 {n} / {total}` |
| `viewer.keyboardHint` | `↑↓ Slices  +/- Zoom  Drag Pan  Wheel Slices` | `↑↓ 슬라이스  +/- 확대  드래그 이동  휠 슬라이스` |
| `viewer.keyboardHintSingleFrame` | `+/- Zoom  Drag Pan` | `+/- 확대  드래그 이동` |
| `viewer.loadingFirstSlice` | `Loading slice {n} of {total}` | `슬라이스 {n} / {total} 로딩 중` |
| `viewer.loadFailedTitle` | `Could not load slice viewer` | `슬라이스 뷰어를 불러올 수 없습니다` |
| `viewer.loadFailedBody` | `The preview service is temporarily unavailable.` | `미리보기 서비스가 일시적으로 응답하지 않습니다.` |
| `viewer.loadFailedRetry` | `Retry` | `재시도` |
| `viewer.frameFailedShort` | `Slice {n} failed to load` | `슬라이스 {n} 로드 실패` |
| `viewer.frameFailedRetry` | `Retry` | `재시도` |
| `viewer.frameFailedSkip` | `Skip to next slice` | `다음 슬라이스로` |
| `viewer.zoomIn` | `Zoom in` | `확대` |
| `viewer.zoomOut` | `Zoom out` | `축소` |
| `viewer.zoomReset` | `Reset zoom` | `확대 초기화` |
| `viewer.brightnessLabel` | `Brightness` | `밝기` |
| `viewer.contrastLabel` | `Contrast` | `대비` |
| `viewer.previousSlice` | `Previous slice` | `이전 슬라이스` |
| `viewer.nextSlice` | `Next slice` | `다음 슬라이스` |

### 14.3 `samd.*` (SaMD footer)

| key | EN | KR |
|-----|-----|-----|
| `samd.disclaimer` | `Display only — not for diagnostic use. RadiVault is not a medical device. Refer to your DICOM-conformant viewer for clinical decisions.` | `표시 전용 — 진단 용도 사용 금지. RadiVault 는 의료기기가 아닙니다. 임상 판단은 DICOM 인증 뷰어에서 수행해주세요.` |
| `samd.tciaAttribution` | `Demo data based on TCIA — CC BY 3.0/4.0.` | `데모 데이터는 TCIA 기반 — CC BY 3.0/4.0.` |

### 14.4 `sampleDownload.*` (Sample download CTA)

| key | EN | KR |
|-----|-----|-----|
| `sampleDownload.sectionTitle` | `Sample download` | `샘플 다운로드` |
| `sampleDownload.cta` | `Download sample DICOM` | `샘플 DICOM 다운로드` |
| `sampleDownload.ctaPreparing` | `Preparing…` | `준비 중…` |
| `sampleDownload.description` | `Get one DICOM file for pydicom inspection.` | `pydicom 검증용 DICOM 파일 1 건을 받습니다.` |
| `sampleDownload.tooltipNotVerified` | `Preview unavailable for this study. PHI verification pending.` | `이 study 는 미리보기를 사용할 수 없습니다. PHI 검증 대기 중.` |
| `sampleDownload.tooltipQuotaExceeded` | `Daily limit reached. Resets at 00:00 KST.` | `일일 한도에 도달했습니다. 00:00 KST 에 초기화됩니다.` |
| `sampleDownload.toastStarted` | `Download started — your browser will save the file.` | `다운로드를 시작했습니다 — 브라우저에서 파일이 저장됩니다.` |
| `sampleDownload.toastFailed` | `Sample download failed — please try again.` | `샘플 다운로드에 실패했습니다 — 잠시 후 다시 시도해 주세요.` |
| `sampleDownload.toastQuotaExceeded` | `Daily limit reached. Try again tomorrow.` | `일일 한도에 도달했습니다. 내일 다시 시도해 주세요.` |

### 14.5 `cohortCta.*` (Add to cohort 분리)

| key | EN | KR |
|-----|-----|-----|
| `cohortCta.sectionTitle` | `Add to cohort` | `코호트에 추가` |
| `cohortCta.description` | `Place a full order for all studies in cohort. 5-phase delivery.` | `코호트의 모든 study 에 대한 정식 주문. 5 단계 배송.` |

### 14.6 `quota.*` (QuotaIndicator)

| key | EN | KR |
|-----|-----|-----|
| `quota.todayInline` | `Today: {used}/{limit}` | `오늘: {used}/{limit}` |
| `quota.todayInlineSuffix` | `sample downloads` | `샘플 다운로드` |
| `quota.resetsAt` | `Resets at 00:00 KST` | `00:00 KST 에 초기화` |
| `quota.resetsIn` | `Resets in {h}h {m}m` | `{h}시간 {m}분 후 초기화` |
| `quota.dailySectionTitle` | `Daily quota` | `일일 쿼터` |
| `quota.sampleDownloadsLabel` | `Sample DICOM downloads` | `샘플 DICOM 다운로드` |
| `quota.usedLabel` | `Used: {used} / {limit}` | `사용: {used} / {limit}` |

### 14.7 i18n 키 신규 합계

- `preview.*`: 7
- `viewer.*`: 19
- `samd.*`: 2
- `sampleDownload.*`: 9
- `cohortCta.*`: 2
- `quota.*`: 7
- **합계: 46 EN entries × 2 언어 = 92 신규 entries**

> **dev-spec 권고 (NFR-I18N) 와의 정합**: dev-spec 은 "viewer UI 영어 fixed. SaMD 면책 배너만 EN/KR 토글" 명시. 본 design-spec 은 **모든 viewer UI 도 i18n** 함을 권고 (한국 buyer 가 KR locale 시 viewer 도 한글 표시). dev-spec 권고 vs design-spec 권고 충돌 — Kyle 결정 필요 (Q-flag 1, §17 참조).

---

## 15. 접근성 체크리스트 (WCAG 2.1 AA)

dev-spec NFR-A11Y 의 시각적 enforce. 각 항목 binary-testable.

### 15.1 색 대비 (4.5:1 이상)

| 항목 | 전경 | 배경 | 비율 | 준수 |
|------|------|------|------|------|
| `<StudyThumbnail>` placeholder text | `--color-text-muted` (#64748b) | `--color-bg-muted` (#f8fafc) | 4.83:1 | ✓ |
| `<SliceViewer>` slice counter | `--color-text-muted` (#64748b) | `--color-bg-muted` (#f8fafc) | 4.83:1 | ✓ |
| `<SaMDFooter>` text | `--color-text-samd` (#b45309) | status Warning bg (#fffbeb) | 4.74:1 | ✓ |
| `<SampleDownloadButton>` text | white (#fff) | `--color-primary-600` (#2563eb) | 4.54:1 | ✓ |
| `<SampleDownloadButton>` disabled text | `--color-text-muted` (#64748b) | `--color-bg-muted` (#f8fafc) | 4.83:1 | ✓ |
| `<QuotaIndicator>` exhausted | status Error fg (#b91c1c) | `--color-bg` (#fff) | 5.94:1 | ✓ |
| Toast (info) | `--color-primary-700` (#1d4ed8) | status Info bg (#eff6ff) | 6.80:1 | ✓ |
| Toast (error) | status Error fg (#b91c1c) | status Error bg (#fef2f2) | 5.94:1 | ✓ |
| `<SliceViewer>` slider thumb | `--color-primary-600` (#2563eb) | `--color-border-strong` track (#cbd5e1) | 3:1 (UI 경계) | ✓ |
| `<SliceViewer>` slider focus ring | `--color-primary-700` (#1d4ed8) at 40% | viewer-bg (#000) or page-bg (#fff) | 6.80:1 | ✓ |

### 15.2 키보드 탐색 순서 (StudyDetail page)

```
Tab 1:  Skip-link "Skip to main content"
Tab 2:  MarketplaceNav 로고 → /dashboard
Tab 3:  MarketplaceNav 메뉴 (Search · Orders · Docs · Account)
Tab 4:  Sign out 버튼
Tab 5:  ← Back to results 링크
Tab 6:  StudyInstanceUID copy 버튼 (있으면)
Tab 7:  SliceViewer canvas (focusable, tabindex=0)
Tab 8:  SliceViewer slider (Tab in → Arrow keys 활성)
Tab 9:  SliceViewer < (previous) 버튼
Tab 10: SliceViewer > (next) 버튼
Tab 11: ZoomIn 버튼
Tab 12: ZoomOut 버튼
Tab 13: ResetZoom 버튼
Tab 14: BrightnessSlider
Tab 15: ContrastSlider
Tab 16: SampleDownloadButton (또는 disabled tooltip 영역)
Tab 17: AddToCohortButton
Tab 18: Series list 항목들 (각 항목 focusable, Enter → series 단독 view — v0.2)
Tab 19: 메타데이터 grid 의 copyable 필드 (있으면)
Tab 20: SaMD footer link (있으면) — 현재는 0 (장식)
```

- **Skip-link**: `<a href="#viewer" class="sr-only focus:not-sr-only">Skip to viewer</a>` — viewer 직접 진입.
- **Focus visible**: 모든 focusable 요소에 3px `--color-primary-700/40` ring + 2px offset (portal-redesign §8.2).
- **Focus trap 없음**: viewer 는 modal 아님. fullscreen mode (v0.2) 시에만 trap 검토.

### 15.3 ARIA 레이블 / 역할

| 요소 | ARIA |
|------|------|
| `<SliceViewer>` 컨테이너 | `role="region" aria-label="Slice viewer"` |
| `<img>` slice canvas | `aria-label={`Slice ${current} of ${total} — ${modality} ${bodyPart}`}` |
| `<input type="range">` slider | `aria-label="Slice number"` `aria-valuemin="1"` `aria-valuemax={N}` `aria-valuenow={current}` `aria-valuetext={`Slice ${current} of ${N}`}` |
| `<button>` previous / next | `aria-label="Previous slice"` / `aria-label="Next slice"` |
| `<button>` zoom in/out/reset | `aria-label="Zoom in"` / `"Zoom out"` / `"Reset zoom"` |
| `<input type="range">` brightness | `aria-label="Brightness"` `aria-valuemin="0"` `aria-valuemax="200"` (백분율) |
| `<input type="range">` contrast | `aria-label="Contrast"` 동일 패턴 |
| `<SaMDFooter>` | `role="contentinfo"` `data-testid="samd-disclaimer"` `aria-label="Medical device disclaimer"` |
| `<SampleDownloadButton>` | `aria-busy={downloading}` `aria-disabled={!verified || quotaExceeded}` `aria-describedby={tooltipId}` |
| `<QuotaIndicator>` (account) | `role="status" aria-live="polite"` (다운로드 후 갱신 announce) |
| `<StudyThumbnail>` `<img>` | verified: `alt={studyDescription || `${modality} preview thumbnail`}` / placeholder: `alt=""` (장식) + label 별도 |
| `<ModalityFallback>` | `role="region" aria-label="Preview unavailable"` |
| Toast (info / error) | `role="alert" aria-live="assertive"` (즉시 announce) |

### 15.4 스크린리더 시나리오

#### Slice navigation (NVDA / VoiceOver)

```
사용자: Tab 으로 slider focus
SR:    "Slice number, slider, 9 of 18, slice 9 of 18"
사용자: Arrow Down
SR:    "Slice 8 of 18"   (aria-valuetext 동적 갱신)
사용자: Arrow Up
SR:    "Slice 9 of 18"
```

#### Sample download (성공)

```
사용자: Tab 으로 SampleDownloadButton focus
SR:    "Download sample DICOM, button"
사용자: Enter
SR:    "Download sample DICOM, button, busy" (aria-busy=true)
        잠시 후 →
SR:    (aria-live="assertive" toast) "Download started — your browser will save the file."
SR:    "Download sample DICOM, button, disabled" (quota 1/1)
```

#### Sample download (verified 아님)

```
사용자: Tab 으로 SampleDownloadButton focus
SR:    "Download sample DICOM, button, disabled, Preview unavailable for this study. PHI verification pending."
        (aria-describedby tooltip 즉시 announce)
```

### 15.5 prefers-reduced-motion 대응

- `<StudyThumbnail>` skeleton 펄스 → 정적 단색 표시.
- 카드 hover translateY → 비활성.
- toast slide-in animation → fade-only.
- `<SliceViewer>` slice navigation 시 transition → 즉시 교체 (no fade).

---

## 16. 인터랙션 패턴 (요약)

§7.4 (viewer 키보드/마우스/터치) 와 중복되지 않는 항목만.

### 16.1 페이지 진입 시 자동 동작

- `/studies/[uid]` 진입 → `<SliceViewer>` 가 첫 슬라이스 (frame_num=1, series_num=1) 자동 로드.
- IntersectionObserver: viewer canvas 가 viewport 진입 시 **현재 frame ±3** 사전 fetch (NFR-PERF-2).
- Cohort sidebar: `loadCohort()` 로 sessionStorage 읽기 → `inCohort` 초기 상태 결정 (기존 패턴).

### 16.2 사용자 액션 → UI 반응 표

| 사용자 액션 | UI 반응 (즉시) | 비동기 후속 |
|-------------|----------------|-------------|
| Search 카드 클릭 | router push `/studies/{uid}` | metadata fetch + viewer 첫 슬라이스 fetch |
| Slider drag | 슬라이스 표시 변경 (preload cache hit 즉시) | preload window 갱신 (±3) |
| ↑↓ 키 | 슬라이스 ±1 (즉시) | preload 갱신 |
| `+`/`-` 키 | Zoom transform (즉시) | none |
| Sample download click | 버튼 spinner + downloading state | POST → toast → quota 갱신 |
| Add to cohort click | sidebar 카운터 +1 + sessionStorage 저장 (즉시) | none (cohort 는 client-side state) |
| Series 항목 클릭 | (v0.1: noop, v0.2: series 단독 viewer) | none |
| Sign out click | 즉시 redirect + cohort 유지 (sessionStorage) | POST /api/session/delete |

### 16.3 Toast 시스템 사용 규약

기존 `react-hot-toast` 또는 신규 `<Toast>` 컴포넌트 (Kyle 결정 — Q-flag 2). 본 spec 은 다음을 가정:

- **위치**: top-right, page-level (z-40).
- **자동 dismiss**: info=4s, error=8s, success=4s.
- **manual dismiss**: 우상단 X 버튼 (모든 variant).
- **stack**: 최대 3 개. 4번째 토스트는 가장 오래된 것 자동 dismiss.
- **screen reader**: `role="alert" aria-live="assertive"`.

---

## 17. 에러 / 로딩 / 빈 상태

§3 (사용자 플로우) + §6/§7 의 각 컴포넌트 변형에서 이미 정의. 본 절은 행렬 요약.

### 17.1 상태 행렬

| 화면 | loading | empty | error (4xx) | error (5xx) | no-permission | partial-failure |
|------|---------|-------|-------------|-------------|---------------|-----------------|
| **S-1 `/search` cards** | thumbnail skeleton (§6.2) | 기존 portal-redesign §15.1 (no studies match) | 401 → /signin redirect (middleware) | thumbnail Retry 링크 (§6.3) | 401 동일 | 일부 thumbnail 만 placeholder, 나머지 정상 |
| **S-2 viewer** | "Loading slice 1 of 18" spinner (§7.5.1) | single-frame variant (§7.5.3) | 404 study → notFound (기존) / 403 verified 아님 → ModalityFallback (§11.2) | full error (§7.5.2) + Retry | viewer disabled + ModalityFallback unavailable | 일부 frame inline error (§7.5.4) |
| **S-2 SampleDownloadButton** | spinner (§9.3.2) | (해당 없음, study 단위) | 403 verified 아님 → disabled+tooltip / 404 sample 누락 → toast "Sample missing" | toast "Sample download failed" (§9.3.5) | 401 동일 / 403 → disabled | n/a (단일 트랜잭션) |
| **S-2 sample-download** | (BFF round-trip 300ms) | n/a | 429 quota → toast "Daily limit reached" + button disabled | toast "Sample download failed" | n/a | n/a |
| **S-3 `/account` quota** | "Today: …/1" skeleton ellipsis | "Today: 0/1" (정상) | 401 → /signin | "Today: ?/1 [Retry]" | 401 → /signin | quota 표시 실패 시 progress bar 회색 |

### 17.2 에러 메시지 i18n (§14 i18n 표 참조)

모든 에러 메시지는 EN/KR 페어. `<ErrorBanner>` (재사용) 와 `request_id` 노출 패턴은 portal-redesign §7.5 envelope 그대로.

### 17.3 Empty state 결정 표

| 조건 | 표시 |
|------|------|
| `/search` 결과 0 건 | 기존 emptyTitle + emptyBody (변경 없음) |
| `/search` 결과 N 건 중 verified 0 건 | 모든 카드에 placeholder thumbnail (§6.1.2). 별도 empty 메시지 X (cards 자체는 표시). |
| `/search` 결과 N 건 중 verified 일부 | mixed 상태 — 시각적으로 verified 5 / placeholder 245 명확히 구분 |
| Study detail 의 series 0 건 | 기존 (변경 없음) |
| Cohort 0 건 (다른 study 추가 안 함) | 기존 cohortEmptyTitle (변경 없음) |
| Quota 0/1 (정상) | 정상 표시, 강조 X |
| Quota 1/1 (소진) | red status + reset time 강조 |

---

## 18. 데모 Scene 5 스토리보드 (60–90 초)

**dev-spec 근거**: planner 권고 항목 #10 + dev-spec §12 골든패스.

### 18.1 단계별 스크린 전환

```
┌───────────────────────────────────────────────────────────────────────────┐
│ Step 1 [t=0~10s]  /search 카드 썸네일 강조                                │
└───────────────────────────────────────────────────────────────────────────┘
  화면: /search (3-pane)
  강조: 좌측 facet · 중앙 결과 카드들 (5 verified 썸네일 highlight, 245 placeholder)
  발화: "RadiVault 카탈로그를 시각으로 한 눈에 — 5 개 verified preview 가
         즉시 보입니다. PHI 검증을 통과한 study 만 thumbnail 노출."

┌───────────────────────────────────────────────────────────────────────────┐
│ Step 2 [t=10~15s]  카드 클릭 → /studies/[uid] 진입                       │
└───────────────────────────────────────────────────────────────────────────┘
  Action: verified CT chest study 카드 클릭
  화면 전환: SPA navigation (instant)
  로딩: SliceViewer "Loading slice 1 of 18" spinner (< 500ms)

┌───────────────────────────────────────────────────────────────────────────┐
│ Step 3 [t=15~30s]  Viewer 슬라이더 시연                                   │
└───────────────────────────────────────────────────────────────────────────┘
  화면: /studies/[uid] (SliceViewer 풀)
  Action: 슬라이더 drag (1 → 18 → 9)
         + 키보드 ↑↓ (시연)
         + 마우스 wheel (시연)
         + +/- zoom 시연
         + drag pan 시연
  발화: "DICOM PS3.18 Sup 203 표준 thumbnail. Buyer 가 데이터의 화질,
         해부학 영역, 슬라이스 두께를 self-serve 로 30 초 내에 평가합니다."

┌───────────────────────────────────────────────────────────────────────────┐
│ Step 4 [t=30~40s]  SaMD footer 강조                                       │
└───────────────────────────────────────────────────────────────────────────┘
  화면: 동일 viewer (SaMD footer zoom-in 스크린샷 가능)
  강조: footer "Display only — not for diagnostic use" 배너
  발화: "표시 전용 — 진단 용도 아님. 식약처 SaMD 분류 회피를 위해
         측정·진단·AI overlay 도구는 일체 없습니다. 단순 시각 평가."

┌───────────────────────────────────────────────────────────────────────────┐
│ Step 5 [t=40~50s]  Sample download 클릭                                   │
└───────────────────────────────────────────────────────────────────────────┘
  화면: viewer + 우측 사이드바
  강조: 사이드바 [Download sample DICOM] primary 버튼
  Action: 클릭 → spinner (300ms) → button "Preparing…"

┌───────────────────────────────────────────────────────────────────────────┐
│ Step 6 [t=50~60s]  다운로드 toast + quota 갱신                           │
└───────────────────────────────────────────────────────────────────────────┘
  화면: viewer + toast "Download started" (top-right)
        + 사이드바 quota "Today: 1/1" red 전환
        + 브라우저 download bar (sample.dcm)
  발화: "1-click presigned URL — TTL 1 시간, audit log 100% 기록.
         일일 1 회 quota 로 재식별 위험 누적 방지."

┌───────────────────────────────────────────────────────────────────────────┐
│ Step 7 [t=60~90s]  (선택) 터미널 pydicom 검증                            │
└───────────────────────────────────────────────────────────────────────────┘
  화면: 데모 시연자 터미널 split-screen
  Code:
    >>> import pydicom
    >>> ds = pydicom.dcmread("sample.dcm")
    >>> print(ds.Modality, ds.BodyPartExamined, ds.PixelSpacing)
    CT CHEST [0.78, 0.78]
    >>> ds.pixel_array.shape
    (512, 512)
  발화: "5 분 안에 buyer 가 데이터 호환성을 검증합니다. 영업 콜 없이."
```

### 18.2 시연자 cues

- **Step 3 의 슬라이더 drag**: 18→1 풀 sweep 한 번, 9 로 복귀 (preload hit 시연).
- **Step 4 의 SaMD zoom**: 시연용 스크린샷에서 footer 만 highlight (실제 데모는 cursor hover 만으로 충분).
- **Step 5 의 click**: 사이드바 primary 버튼 vs ghost 버튼의 시각 분리 강조 (planner 항목 #5).
- **Step 7 (선택)**: 터미널 시연이 시연 시간 부족 시 생략 가능. 포스터 배경에 코드만 표시.

### 18.3 Q&A 대비 시각

| 예상 질문 | 시각 대응 |
|-----------|-----------|
| "OHIF 와 무엇이 다른가?" | 사이드바 Series 리스트 + viewer 단순함 강조. "v0.2 에서 OHIF iframe 통합 예정." |
| "SaMD 분류는 어떻게 회피?" | SaMD footer 풀스크린 + "측정 도구 0" 강조. |
| "PHI 검증은?" | placeholder 245 카드 vs verified 5 카드 대비. "수동 OCR 검증 + v0.1.5 자동 Presidio." |
| "Cohort 주문은?" | 우측 사이드바 [Add to cohort] 별도 시연 (5-phase tracker — Scene 8). |

---

## 19. 수용 기준 (시각 · 행동)

dev-spec §10.6 (Demo AC) 의 3 항목 + 본 spec 의 시각 wireframe 1:1 검증 항목.

### 19.1 시각 일치

- [ ] **AC-DESIGN-1.1** `/search` 카드 좌측에 96×96 thumbnail slot 표시 (verified 5 건은 JPEG, 245 건은 placeholder).
- [ ] **AC-DESIGN-1.2** thumbnail placeholder 의 modality 글리프 7 종 매핑 (CT/MR/CR/DR/MG/PT/US/기본).
- [ ] **AC-DESIGN-1.3** thumbnail loading 시 skeleton 펄스 (1.5s ease-in-out) 표시.
- [ ] **AC-DESIGN-1.4** thumbnail 5xx 시 Retry 링크 표시 + 재시도 1회 자동 후 수동.
- [ ] **AC-DESIGN-2.1** `/studies/[uid]` 페이지 grid 레이아웃: 좌 viewer (1fr) · 우 sidebar (320px) · 상 header · 중 metadata grid · 하 SaMD footer (sticky).
- [ ] **AC-DESIGN-2.2** SliceViewer 의 slider · prev/next 버튼 · counter · keyboard hint 4 요소 모두 표시.
- [ ] **AC-DESIGN-2.3** SliceViewer canvas bg = #000000 (검정).
- [ ] **AC-DESIGN-2.4** SliceViewer 의 zoom 컨트롤 (좌상단 또는 우상단 overlay) + brightness/contrast 컨트롤 표시.
- [ ] **AC-DESIGN-2.5** SliceViewer 에 측정·segmentation·AI 도구 버튼 0 (시각 inspection + CI lint).
- [ ] **AC-DESIGN-3.1** SaMD footer 가 viewer 페이지 sticky bottom 으로 항상 표시 (스크롤 무관).
- [ ] **AC-DESIGN-3.2** SaMD footer 색상: bg `#fffbeb`, text `#b45309`, 4.74:1 대비.
- [ ] **AC-DESIGN-3.3** SaMD footer EN/KR 정확한 i18n 문구 (§14.3).
- [ ] **AC-DESIGN-4.1** Sample download 버튼 = primary filled, [Add to cohort] = ghost outlined — 시각 분리 명확.
- [ ] **AC-DESIGN-4.2** Sample download 버튼 5 상태 (default/downloading/disabled-not-verified/disabled-quota/error) 모두 시각 정의.
- [ ] **AC-DESIGN-4.3** Sample download 클릭 → 300ms 안에 spinner + toast 노출.
- [ ] **AC-DESIGN-5.1** QuotaIndicator inline (viewer sidebar) + full (account) 두 위치 모두 표시.
- [ ] **AC-DESIGN-5.2** Quota 0→1 전환 즉시 (download 후 round-trip 1회 내) UI 갱신.

### 19.2 상호작용 상태

- [ ] **AC-DESIGN-6.1** 모든 버튼 / link / input 에 `:hover` `:focus` `:disabled` 시각 정의 (focus ring 3px).
- [ ] **AC-DESIGN-6.2** Slider focus 시 thumb 에 focus ring 표시 (4.5:1 대비).
- [ ] **AC-DESIGN-6.3** thumbnail card hover 시 border 색 변경 (`--color-border` → `--color-primary-600`).

### 19.3 다국어

- [ ] **AC-DESIGN-7.1** locale='ko' 시 SaMD footer 한글 표시 (`viewer.samdDisclaimer.ko`).
- [ ] **AC-DESIGN-7.2** locale='ko' 시 SampleDownloadButton 한글 표시.
- [ ] **AC-DESIGN-7.3** 모든 viewer UI 문자열 KR 번역 누락 0 건 (i18n.test.ts 통과).

### 19.4 접근성

- [ ] **AC-DESIGN-8.1** Lighthouse Accessibility ≥ 95 (`/studies/[uid]`).
- [ ] **AC-DESIGN-8.2** 키보드 only 로 viewer 전체 navigation 가능 (Tab + Arrow + Enter).
- [ ] **AC-DESIGN-8.3** SR (NVDA / VoiceOver) 로 slice 변경 시 "Slice {n} of {N}" announce.
- [ ] **AC-DESIGN-8.4** SampleDownloadButton disabled 시 tooltip 이 SR 로 announce (`aria-describedby`).
- [ ] **AC-DESIGN-8.5** prefers-reduced-motion 활성 시 skeleton 펄스 + hover translateY 비활성.
- [ ] **AC-DESIGN-8.6** 모든 색 대비 WCAG AA (§15.1 표 전건 통과).

### 19.5 회귀

- [ ] **AC-DESIGN-9.1** 기존 `/search` row 카드의 텍스트 메타 (instances, MB, year) 정확히 동일 위치.
- [ ] **AC-DESIGN-9.2** 기존 `/studies/[uid]` 의 metadata grid (14 필드) + Series list 동일 표시.
- [ ] **AC-DESIGN-9.3** 기존 `<MarketplaceNav>` 색상·focus·active 상태 변경 0.
- [ ] **AC-DESIGN-9.4** 기존 `<ModalityBadge>` 색상 매핑 변경 0.

---

## 20. 반응형 / 디바이스

dev-spec NFR + 기능 우선순위:

### 20.1 데스크톱 (≥ 1280 px) — 기본 타깃

위 §6~§9 와이어 그대로. 컨테이너 `max-w-app = 1440 px` (portal-redesign §4.9).

- `/search`: 3-pane 그대로. 카드 row 96 px height + thumbnail 96×96.
- `/studies/[uid]`: viewer 좌 (1fr ≈ 800–900 px) + sidebar 320 px.

### 20.2 태블릿 (768 ~ 1279 px) — best-effort

dev-spec §3.2 제외 항목: "모바일 viewer 최적화 — desktop 1280px+ 우선. mobile 은 best-effort."

- `/search`: 3-pane 유지하되 facet pane 280 px → 240 px 축소. thumbnail 96×96 유지.
- `/studies/[uid]`: viewer 와 sidebar 세로 스택 가능 (1280 px 미만에서). sidebar는 viewer 아래로 이동.
- SaMD footer: 동일 sticky.

### 20.3 모바일 (≤ 767 px) — fallback only

기존 buyer portal `<MobileFallback>` 패턴 유지. viewer 페이지에서:

```
┌──────────────────────────────────────┐
│  [icon: monitor]                     │
│                                      │
│  Best viewed on desktop              │
│                                      │
│  RadiVault Marketplace is optimized  │
│  for ≥ 1280 px screens. Slice viewer │
│  experience is limited on mobile.    │
│                                      │
│  [ View metadata only → ]            │
│   (단순 metadata grid 만 표시)       │
└──────────────────────────────────────┘
```

- 단, 비기능 우선순위: D-13 데모 환경 (1920×1080 데스크톱) 100% 동작이 critical.
- 모바일 thumbnail (검색 카드) 는 기존 i18n `account.mobileFallback*` 문구 재사용 + viewer 만 fallback.

### 20.4 와이드 (≥ 1920 px)

- 컨테이너 `max-w-app = 1440 px` 고정 (가독성). viewer canvas 만 확대 가능 (CSS scale fit).

---

## 21. 변경 영향 (개발 / QA 핸드오프)

### 21.1 신규 파일 권고 (developer 가 생성)

```
web/portal/src/components/SliceViewer/
├── SliceViewer.tsx              ★ P0
├── SliceViewer.module.css       (또는 Tailwind classes)
├── ViewerCanvas.tsx             ★ P0
├── ViewerControls.tsx           ★ P0
├── ZoomControls.tsx             ★ P0
├── WindowLevelControls.tsx      ★ P0
└── index.ts

web/portal/src/components/preview/
├── StudyThumbnail.tsx           ★ P0
├── ModalityFallback.tsx         ★ P1
├── SampleDownloadButton.tsx     ★ P0
├── QuotaIndicator.tsx           ★ P1
└── SaMDFooter.tsx               ★ P0
```

### 21.2 수정 파일

```
web/portal/src/components/StudyCard.tsx                       (썸네일 slot 추가)
web/portal/src/components/buyer/StudyDetailPanel.tsx          (viewer + sidebar)
web/portal/src/app/studies/[uid]/StudyDetailClient.tsx        (SaMDFooter wrap)
web/portal/src/lib/i18n.ts                                    (i18n key 46 추가)
web/portal/src/app/account/AccountClient.tsx                  (QuotaIndicator full)
```

### 21.3 신규 BFF 라우트 (dev-spec §4.3 FR-API-2)

본 design-spec 은 BFF 신규 라우트 디자인을 변경하지 않음. dev-spec 그대로 구현:
- `GET /api/studies/[uid]/thumbnail`
- `GET /api/studies/[uid]/series/[seriesNum]/frames/[frameNum]`
- `POST /api/studies/[uid]/sample-download`
- (권고) `GET /api/account/quota` — quota 단독 조회 endpoint (Q-flag 3, §22 참조)

### 21.4 컴포넌트 우선순위 (P0/P1/P2)

**P0 (D-13 demo 필수 — Day 1 구현)**:
1. `<StudyThumbnail>` — verified/placeholder/loading/error 4 상태
2. `<SaMDFooter>` — sticky bottom 배너
3. `<SliceViewer>` (multi-slice variant) — slider + canvas + 키보드 + 마우스 wheel
4. `<SampleDownloadButton>` — 5 상태
5. `<StudyCard>` 수정 — thumbnail slot 추가

**P1 (D-13 demo 권고 — Day 2 구현)**:
6. `<QuotaIndicator>` (inline + full) — quota 표시
7. `<ModalityFallback>` — verified 아닌 study 의 viewer placeholder
8. `<StudyDetailPanel>` 수정 — sidebar 우측 분리 (Sample / Cohort / Series)
9. `<SliceViewer>` zoom/pan/window-level controls
10. Toast 시스템 (info / error 2 variant)

**P2 (D-13 demo 미포함 — v0.1.5)**:
11. `<SliceViewer>` single-frame variant 최적화
12. 터치 제스처 (swipe / pinch / two-finger drag)
13. Series 단독 viewer (series 항목 클릭 시)
14. Header mini quota indicator
15. Grid view variant (StudyCard 256×256 grid)

---

## 22. 오픈 질문 (Q-flag — Kyle 결정 필요)

### 22.1 본 spec 신규 (designer 발기)

| # | 항목 | designer 기본값 | 근거 / 결정 필요 이유 |
|---|------|-----------------|----------------------|
| **K-1** | viewer UI i18n 범위 | **viewer UI 도 EN/KR i18n** (§14 권고) | dev-spec NFR-I18N: "viewer UI 영어 fixed. SaMD 면책 배너만 EN/KR 토글" 와 충돌. KR locale 사용자가 viewer slider/buttons 도 한글로 봐야 일관성 있음. dev-spec 변경 vs 본 spec 변경 결정 필요. |
| **K-2** | Toast 시스템 | **`react-hot-toast` 신규 도입** (또는 기존 alert) | 기존 portal 에 toast 시스템 없음 (alert/banner 만). D-13 까지 신규 라이브러리 도입 vs 자체 구현. Bundle size: react-hot-toast ~4KB. |
| **K-3** | Quota 조회 endpoint | **sample-download 응답 envelope 에 `quota_after` 포함** (round-trip 1회) | 대안: `GET /api/account/quota` 별도 endpoint. 전자가 단순 + 즉시 갱신, 후자가 RESTful. |
| **K-4** | Sidebar 위치 (viewer 페이지) | **우측 320px** (§7 와이어) | 대안: 좌측 / 하단. 우측이 일반적 (PACS/OHIF 관행). focus order 도 자연스러움 (viewer → sidebar → series). |
| **K-5** | Viewer 의 series 다중 표시 | **첫 series (series_num=1) 만 표시** (D-13 MVP) | 5 sample 중 일부 study 가 multi-series (CT axial + coronal). v0.1 은 series 1 만, v0.2 에서 series picker. 시연 시 "axial 만 표시" 명시 필요. |
| **K-6** | Window-level 의 정밀도 | **CSS filter brightness/contrast** (0~200%) | dev-spec FR-PREVIEW-2 명시. 단 DICOM raw window center/width 와 다른 표현. SaMD 회피 의도 명확화 필요 — UI 라벨에 "Display brightness" 명시 권고 (clinical "window-level" 단어 회피). |
| **K-7** | SampleDownload 후 즉시 disabled 인지, Refresh 인지 | **즉시 disabled (optimistic)** | quota INCR 성공 가정. 만약 백엔드 quota INCR 실패 시 button 재활성 (서버 confirm 후). 데모 안정성 우선. |
| **K-8** | placeholder 카드의 modality 글리프 (245 study) | **modality 별 7 종 글리프** (§6.1.2) | 대안: 모두 동일 monitor-off 글리프 (단순). modality 별이 더 정보성 있으나 디자인 부담 +. SVG 7 종 신규 제작 필요. |
| **K-9** | thumbnail row variant 너비 | **96×96** (row card) | 대안: 64×64 (더 compact) / 128×128 (더 가시). 기존 row height 유지 vs 카드 height 증가 trade-off. |
| **K-10** | dark mode 대응 | **v0.1 라이트 고정** (portal-redesign K-7 승계) | viewer 가 검정 bg 인 점은 viewer 자체 한정. 페이지 전체 dark mode 는 v0.1.1+. |

### 22.2 dev-spec Q-flag 와의 cross-reference

dev-spec §14.1 의 Q-1 ~ Q-7 은 본 design-spec 에서 다음과 같이 시각화:

| dev-spec Q | 본 spec 시각화 |
|------------|----------------|
| Q-1 (Sample 가격 free) | QuotaIndicator "Today: 0/1" (free tier 시각화) |
| Q-2 (Sample 5 study) | 245 placeholder vs 5 verified 시각 분기 |
| Q-3 (SaMD 표시 only) | viewer 측정 도구 0 + SaMD footer |
| Q-5 (MinIO bucket) | (UI 영향 없음) |
| Q-6 (Redis quota) | QuotaIndicator + sample-download 응답 envelope |
| Q-7 (단일 .dcm) | sample CTA 라벨 "Download sample DICOM" (단수) |

### 22.3 법무 자문 cross-reference (dev-spec §11.8)

본 design-spec 은 dev-spec L-1 ~ L-6 에 대한 시각적 enforce:
- L-1 (SaMD 분류): viewer 측정 도구 0 + SaMD footer 항상 표시.
- L-2 (thumbnail PIPA): verified 5 study 만 thumbnail 노출 (placeholder 분기).
- L-3 (sample DICOM 익명화): sample-download 호출 시 audit log 시각 미표시 (백엔드만).
- L-4 (면책 효력): SaMD footer 의 EN/KR 정확한 문구 (§14.3).
- L-5 (TCIA CC-BY): viewer footer 우측 attribution (§8.1 와이어).
- L-6 (quota 약관): QuotaIndicator UI 와 ToS 일관성 (§17.1 행렬).

---

## 23. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-25 | @designer (Claude Opus 4.7) | 최초 작성. wireframe 10 항목 (StudyThumbnail · SliceViewer · SaMDFooter · SampleDownloadButton · CTA 분리 · Loading/Error/Empty · QuotaIndicator · 접근성 · ModalityFallback · 데모 Scene 5) 전건. 신규 컴포넌트 6 + 수정 2. i18n 키 46 EN×2 = 92 entries 신규. 디자인 토큰 신규 0 (제안 2). dev-spec FR-PREVIEW-1..4 / FR-DOWNLOAD-1·2 / FR-API-2 / FR-DATA-1 전건 매핑. AC 25개 (§19). Q-flag 10. |
