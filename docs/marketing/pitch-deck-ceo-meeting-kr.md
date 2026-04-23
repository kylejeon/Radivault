# RadiVault Pitch Deck — CEO (투자자+병원 경영진 겸임) 미팅용

> **Status**: Draft v0.1 — Kyle 리뷰·승인 전 외부 배포 금지.
> **문서 버전**: v0.1 (2026-04-24)
> **작성자**: @marketer
> **청중**: 대표님 1인 (투자자 모자 + 병원 경영진 모자 겸임)
> **Delivery**: 17분 본 데모 + 3분 Q&A, Braided 구조 (매 슬라이드 두 렌즈 병치)
> **연동 문서**:
> - [docs/specs/demo-script-radivault.md v0.2](../specs/demo-script-radivault.md) — 장면 1~7 대사·연출
> - [docs/research/demo-pitch-references-radivault.md](../research/demo-pitch-references-radivault.md) — 스토리보드 A, Anti-patterns, 출처
> - [docs/specs/dev-spec-buyer-portal-demo.md](../specs/dev-spec-buyer-portal-demo.md) — 구현 상태
> - [docs/specs/design-spec-buyer-portal-demo.md](../specs/design-spec-buyer-portal-demo.md) — 토큰·컴포넌트
> - [docs/marketing/one-pager-buyer-global-en.md](./one-pager-buyer-global-en.md), [./proposal-summary-hospital-ko.md](./proposal-summary-hospital-ko.md) — 톤·컴플라이언스 기준
>
> **언어**: 한국어 80% / 영어 quote 20% (demo-script §0 언어 정책 승계)
> **구조 기준**: Braided (매 슬라이드 두 lens 병치) + Storyboard A "Revenue Loop Proof" 7장면
> **Kyle 발화 스타일 옵션**: 각 장면 주요 Talking Point에 **[겸손-안정]** / **[자신감-단호]** 두 버전 드래프트 제공. 본인 낭독 후 택일 또는 믹스.

---

## §0 Deck-wide 규약

### 0.1 슬라이드 토큰 (designer 승계)

- **Buyer 렌즈 색**: `#1D4ED8` (cool blue 700) — 슬라이드 상단 또는 좌측 배지.
- **Hospital 렌즈 색**: `#0F766E` (teal 700) — 슬라이드 하단 또는 우측 배지.
- **Accent**: `#F59E0B` (amber 500) — 핵심 숫자·CTA 강조.
- **Neutral BG**: `#FFFFFF` / text `#0F172A` / subtle `#64748B`.
- **Font**: Sans (Inter / Pretendard). 제목 32–44pt, 본문 18–24pt, disclaimer 12pt.

### 0.2 Braided 마크업 규약

각 슬라이드 하단에 **양면 badge** 고정 배치:

```
┌─────────────────────────────────────────────┐
│  [슬라이드 본문]                              │
│                                             │
│                                             │
│  ┌─────────────────┐ ┌─────────────────┐   │
│  │ 🔵 INVESTOR      │ │ 🟢 HOSPITAL      │   │
│  │ [1줄 hook]        │ │ [1줄 hook]        │   │
│  └─────────────────┘ └─────────────────┘   │
└─────────────────────────────────────────────┘
```

프레젠터는 본문 설명 후 두 badge를 순차 가리키며 "투자자 관점에선 … 병원 관점에선 …" 발화.

### 0.3 Footer (모든 슬라이드 공통)

- 좌측: `RadiVault · v0.1 MVP · 2026-04-24`
- 우측: 슬라이드 `N / 총수`
- 하단 중앙 (필요 시): `Simulation — not a certification claim.` (숫자 슬라이드), `법률 자문 진행 중 · 최종 해석 아님` (컴플라이언스 슬라이드)

### 0.4 총 슬라이드 구성 (17분 기준)

| 장면 | 시간 | 슬라이드 # | 장수 | 목적 |
|---|---|---|---|---|
| 1 | 0:00–2:00 | S1~S2 | 2 | Hook + Dual framing |
| 2 | 2:00–5:00 | S3~S5 | 3 | Market + Architecture + 경쟁 포지셔닝 |
| 3 | 5:00–8:00 | (포털 live) + S6 | 1 (+live) | Hospital Dashboard live — 슬라이드는 backup |
| 4 | 8:00–11:00 | (포털 live) + S7 | 1 (+live) | Buyer Portal live — 슬라이드는 backup |
| 5 | 11:00–13:00 | S8~S9 | 2 | Compliance & Audit (PIPA §28-8, CEO 개인책임, 해시체인) |
| 6 | 13:00–15:00 | S10~S12 | 3 | Numbers & Unit economics (TAM, pricing, revenue share, margin) |
| 7 | 15:00–17:00 | S13~S16 | 4 | Dual Ask (투자자 ask + 병원 ask + team + closing) |
| Q&A | 17:00–20:00 | S17~S18 | 2 | Appendix — 예상 질문 20건, 출처 |

**총 18 슬라이드** (본 데모 16 + appendix 2). 목표 범위 15~20 슬라이드 충족.

---

## §1 장면 1 — Problem & Market (2분)

### S1 — Title + Tagline

```
┌─────────────────────────────────────────────┐
│                                             │
│         RadiVault                           │
│   [로고 placeholder, Kyle 확정 전 wordmark]  │
│                                             │
│   Korea's medical imaging data,             │
│   compliantly delivered to                  │
│   the world's AI.                           │
│                                             │
│   ─────────────────────────────────────     │
│   For investors: a category.                │
│   For hospitals: a settlement route.        │
│                                             │
│                                             │
│  [발표자] Kyle · [날짜] 2026-04-24 · v0.1    │
└─────────────────────────────────────────────┘
```

**Visual spec**:
- 대칭 타이포 중심 구성, 배경 단색 `#0F172A` (짙은 navy) + white text.
- 로고는 현 단계 wordmark만. 브랜드 로고 확정 전.
- 하단 한 줄: `Live demo · 17 min · dual audience`.

**Talking points (프레젠터 대사)**:
- **[겸손-안정]**: "안녕하세요. 오늘 17분 동안, 제품이 돌아가는지, 돈이 되는지, 그리고 지금이 왜 그 시점인지 — 세 가지만 보여드리겠습니다."
- **[자신감-단호]**: "17분입니다. 세 가지만 증명합니다. 돌아가고, 수익이 닫히고, 지금이 시점입니다. 시작합니다."

(demo-script §2 장면 1 참조. 대표님 1초 응시 후 시작.)

**Braided hook** (이 슬라이드는 슬라이드 하단 badge 2개를 **직접 두 문장 발화**로 대체):
- 🔵 **Investor lens**: "카테고리를 정의할 회사를 보시게 됩니다."
- 🟢 **Hospital lens**: "귀 병원이 탈 가장 안전한 정산 루트를 보시게 됩니다."

**Potential objections + response**:
- Obj: "왜 17분인가? 너무 짧지 않나?" → "17분 안에 결정 근거가 충분히 드러나지 않으면, 그건 제품이 아직 준비 안 된 겁니다. 저희는 준비됐습니다."
- Obj: "왜 두 렌즈인가? 하나에 집중해야 하지 않나?" → "대표님께 두 결정이 하나의 서명에 붙어 있기 때문입니다. 분리하면 오히려 혼란스러우실 겁니다."

---

### S2 — Problem & Why Now

```
┌─────────────────────────────────────────────┐
│  The structural moment                       │
│  ─────────────────────────                   │
│                                             │
│  ❶ Global AI demand                         │
│     US-centric imaging data underrepresents │
│     Asian patients · devices · protocols.   │
│     FDA-cleared Korean AI vendors already    │
│     prove Korean data quality.              │
│                                             │
│  ❷ Korean supply ready                      │
│     9,000+ healthcare institutions, OECD    │
│     highest per-capita imaging, single      │
│     payer = standardized corpora.           │
│                                             │
│  ❸ Regulatory trigger — 2026                │
│     Revised PIPA: CEO personal liability    │
│     up to 3% revenue. Board-level audit     │
│     evidence is no longer optional.         │
│                                             │
│  🔵 Investor: a $22M+ Korea TAM, no         │
│     category leader yet.                     │
│  🟢 Hospital: liability protection requires │
│     platform-grade audit chain.             │
│                                             │
│     Sources: research/k-meddata §2·§4,     │
│     IAPP 2025, demo-pitch-references §2    │
└─────────────────────────────────────────────┘
```

**Visual spec**:
- 3단 세로 layout. 각 단은 icon + heading + 2–3줄 증거.
- ❸ PIPA 개정 단에 `2026` 배지 amber 강조.
- 하단 출처 라인 8pt gray.

**Talking points**:
- **[겸손-안정]**: "세 가지가 같은 해에 겹쳤습니다. 글로벌 AI의 다양성 공백, 한국 공급 역량, 그리고 2026 개정 PIPA. 이 겹침이 이 회사를 지금 가능하게 합니다."
- **[자신감-단호]**: "이 세 번째 — CEO 개인책임 — 이 결정타입니다. 병원 이사장이 '감사 증거 없는 데이터 계약'을 더 이상 못 합니다. 저희가 그 증거 구조를 가진 유일한 설계입니다."

**Braided hook**:
- 🔵 **Investor lens**: "카테고리는 아직 비어 있습니다. Segmed는 미국, Gradient도 미국. 한국은 무주공산입니다."
- 🟢 **Hospital lens**: "2026 이후 CEO 개인책임 — 대표님 개인 자산이 걸리는 구조 — 앞에서, '감사 가능한 설계'를 가진 파트너만 안전합니다."

**Potential objections + response**:
- Obj: "CEO 개인책임은 과장 아닌가?" → "IAPP 2025·Kim & Chang FAQ 인용입니다. 단정은 아니지만 법무 업계 공통 해석입니다. 상세는 S8에서."
- Obj: "TAM $22M은 너무 작다." → "한국만입니다. 일본·대만·동남아 PIPA 유사권 포함 시 3~5배. 그러나 저희는 한국에서 먼저 1위를 만든 뒤 확장합니다."

---

## §2 장면 2 — Architecture in One Picture (3분, 슬라이드 3장)

### S3 — The 3-Zone Hybrid Model

```
┌─────────────────────────────────────────────┐
│  Three zones, one flow                       │
│  ──────────────────────                      │
│                                             │
│  ┌───────────────┐   ┌─────────────┐        │
│  │ Zone 1         │   │ Zone 2       │        │
│  │ HOSPITAL       │──▶│ CENTRAL      │        │
│  │ (on-prem)      │   │ (anonymized  │        │
│  │                │   │  index only) │        │
│  │ • PACS         │   │             │        │
│  │ • Gateway      │   │ • Metadata  │        │
│  │   Agent        │   │ • Hash      │        │
│  │ • De-ID Pixel  │   │   chain     │        │
│  │ • Raw DICOM    │   │ • Staging   │        │
│  │   stays here   │   │   S3        │        │
│  └───────────────┘   └──────┬──────┘        │
│                              │               │
│                              ▼               │
│                      ┌─────────────┐         │
│                      │ Zone 3       │         │
│                      │ BUYER PORTAL │         │
│                      │ (global AI)  │         │
│                      │             │         │
│                      │ • Search    │         │
│                      │ • Order     │         │
│                      │ • Download  │         │
│                      └─────────────┘         │
│                                             │
│   ━━━━ red dotted line = hospital network   │
│         boundary (PHI never crosses)        │
│                                             │
│  🔵 Moat: Korea-native, PIPA-first design    │
│  🟢 Sovereignty: raw data never leaves       │
│                                             │
│  [FOOTNOTE] Architecture v1 — docs/         │
│  ARCHITECTURE.md §2. All 5 components       │
│  shipped v0.1 MVP (407 tests pass).         │
└─────────────────────────────────────────────┘
```

**Visual spec**:
- 좌→우 수평 플로우 3박스. Zone 1 박스 주위에 **빨간 점선** (`#DC2626`, dashed) = 병원 네트워크 경계.
- Zone 1 → Zone 2 화살표 위 라벨: `outbound HTTPS only (TLS 1.3, mTLS)`.
- Zone 2 → Zone 3 화살표 위 라벨: `presigned URL · SHA-256 · 24h TTL`.
- 각 zone 박스 하단 작은 회색 라벨: "docs/research/ 근거 있음".

**Talking points**:
- **[겸손-안정]**: "세 개의 zone입니다. Zone 1은 병원 안, Zone 2는 중앙, Zone 3은 구매자. 빨간 점선은 병원 네트워크 경계 — 원본 환자 데이터는 이 선을 **절대** 넘지 않도록 설계되어 있습니다."
- **[자신감-단호]**: "이 점선이 저희 법적 해자입니다. Zone 1 안에서 먼저 익명화합니다. 법은 익명정보에만 국외이전을 허용합니다. 기술과 법이 같은 선을 긋고 있습니다."

**Braided hook**:
- 🔵 **Investor lens**: "이것이 moat입니다. Rhino Federated·Segmed는 중앙 수집형. 저희는 Korea-native hybrid. 한국 PIPA §28-8이 유리하게 작용합니다."
- 🟢 **Hospital lens**: "원본 DICOM은 귀원 PACS에 그대로 있습니다. 저희가 없어져도, 귀원 데이터에는 어떠한 변화도 없습니다."

**Potential objections + response**:
- Obj: "중앙에 staging S3가 있다면 그건 Zone 2 안에서 PHI가 잠시라도 존재하는 거 아닌가?" → "staging에 들어가는 건 이미 Zone 1에서 de-ID된 데이터입니다. Central ingest는 `anonymization_flag != fully_anonymized` 거부하도록 하드 게이트가 있습니다. 재검증 후에만 통과."
- Obj: "outbound only가 정말 outbound only인가?" → "네. inbound 포트 0개. 병원 방화벽에 포트 개방 요청 없음. mTLS 양방향 인증으로 중앙 위장도 차단."

---

### S4 — What's Shipped (v0.1 MVP)

```
┌─────────────────────────────────────────────┐
│  v0.1 MVP — 5 components + portal            │
│  ─────────────────────────────────           │
│                                             │
│  ┌─────────────┐  ┌─────────────┐           │
│  │ Gateway     │  │ Central     │           │
│  │ Agent       │─▶│ Ingest      │           │
│  │ ✓ shipped   │  │ ✓ shipped   │           │
│  └─────────────┘  └──────┬──────┘           │
│                          │                  │
│  ┌─────────────┐  ┌──────▼──────┐           │
│  │ De-ID Pixel │◀─│ Metadata    │           │
│  │ ✓ shipped   │  │ Index       │           │
│  └─────────────┘  │ ✓ shipped   │           │
│                    └──────┬──────┘           │
│                           │                  │
│                    ┌──────▼──────┐           │
│                    │ Order       │           │
│                    │ Fulfillment │           │
│                    │ ✓ shipped   │           │
│                    └──────┬──────┘           │
│                           │                  │
│         ┌─────────────────┴─────────────┐    │
│         ▼                               ▼    │
│  ┌─────────────┐              ┌─────────────┐│
│  │ Buyer Portal │              │ Hospital    ││
│  │ (Next.js)    │              │ Dashboard   ││
│  │ ✓ shipped    │              │ ✓ shipped   ││
│  └─────────────┘              └─────────────┘│
│                                             │
│  ━━━ Headline numbers ━━━                   │
│   407 tests pass · ruff clean · 22 routes   │
│   Stack: FastAPI + Next.js 14 + Postgres    │
│                                             │
│  🔵 Runs today, not slideware.               │
│  🟢 Your data flows through a known stack.   │
└─────────────────────────────────────────────┘
```

**Visual spec**:
- 플로우 다이어그램. 각 컴포넌트 박스 하단 녹색 체크 `✓ shipped`.
- 하단 metrics bar amber 강조: 407 / ruff / 22 routes.

**Talking points**:
- **[겸손-안정]**: "5개 백엔드 컴포넌트와 두 개 웹 포털 — 모두 v0.1에서 돌고 있습니다. 407개 테스트 통과, ruff lint clean, Next.js 빌드 22 routes 컴파일 성공. 이게 오늘 제가 라이브로 보여드릴 근거입니다."
- **[자신감-단호]**: "우리가 '아이디어 단계'를 넘어섰다는 증거입니다. 지금 보시는 박스 7개 — 전부 돌아갑니다. 장면 3·4에서 라이브로 확인하시게 됩니다."

**Braided hook**:
- 🔵 **Investor lens**: "시드 투자 대상이 '구현 리스크'가 아니라 'GTM 리스크' 단계라는 뜻입니다. 기술은 ship됐습니다."
- 🟢 **Hospital lens**: "파일럿 시작 시점에 귀원이 '아직 안 만들어진 거'에 서명하시는 게 아닙니다. 이미 돌아가는 스택에 합류하시는 겁니다."

**Potential objections + response**:
- Obj: "407 테스트가 뭘 검증하나?" → "단위·통합·계약 테스트 전부 포함. Gateway FSM, De-ID 프로파일, Order 12-state machine, 해시 체인 verify까지. 상세는 QA report 5건에 있습니다 (leave-behind)."
- Obj: "Next.js 14 — 왜 그 스택?" → "Buyer Portal은 브라우저 접근성 + SSR SEO. 백엔드 FastAPI는 타입 안전성 + 성능. 스택 선택은 v0.1.5에 재검토 여지 있음."

---

### S5 — Competitive Positioning (1 slide)

```
┌─────────────────────────────────────────────┐
│  Category map — who does what, where        │
│  ──────────────────────────                 │
│                                             │
│               Korea-native  ·  Global       │
│               ────────────     ──────       │
│                                             │
│  On-prem      ┌──────────┐   ┌──────────┐   │
│  federated    │          │   │  Rhino   │   │
│               │          │   │  Health  │   │
│               │          │   │          │   │
│               └──────────┘   └──────────┘   │
│                                             │
│  Hybrid       ┌──────────┐   ┌──────────┐   │
│  (on-prem +   │ RadiVault│   │          │   │
│   anonymized  │  ★       │   │          │   │
│   central)    │          │   │          │   │
│               └──────────┘   └──────────┘   │
│                                             │
│  Central      ┌──────────┐   ┌──────────┐   │
│  warehouse    │          │   │ Segmed   │   │
│               │          │   │ Gradient │   │
│               │          │   │ Truveta  │   │
│               └──────────┘   └──────────┘   │
│                                             │
│  RadiVault = the only Korea-native hybrid.   │
│                                             │
│  🔵 No incumbent occupies this quadrant.     │
│  🟢 A partner built around Korean law, not   │
│     a US model re-exported.                  │
│                                             │
│  Source: demo-pitch-references §2 (public    │
│  materials only, no disparagement intent).   │
└─────────────────────────────────────────────┘
```

**Visual spec**:
- 2×3 positioning matrix. X축: Korea-native / Global. Y축: on-prem / hybrid / central.
- RadiVault 박스만 amber 배경, 나머지 neutral.
- 하단 legal footnote 8pt: "Competitive comparison based on public materials. No disparagement intent."

**Talking points**:
- **[겸손-안정]**: "Segmed, Gradient, Truveta — 모두 훌륭한 회사입니다. 다만 전부 미국에 기반을 두고 중앙 창고형입니다. Rhino는 글로벌 federated. 저희는 한국에서 시작한 hybrid — 이 사분면이 비어있습니다."
- **[자신감-단호]**: "Segmed가 한국에 진출하려면 18~24개월 걸립니다. Korean legal entity, PIPA CEO accountability officer, Korean IT 관계 — 저희가 이미 가진 것들입니다. 저희 head start가 있습니다."

**Braided hook**:
- 🔵 **Investor lens**: "empty quadrant에 먼저 들어가는 회사가 category를 정의합니다."
- 🟢 **Hospital lens**: "한국법을 처음부터 전제로 설계된 파트너 vs. 미국 모델을 한국에 적용해보려는 파트너 — 선택지가 분명합니다."

**Potential objections + response**:
- Obj: "Segmed가 한국 파트너십으로 빠르게 들어오면?" → "가능성 있습니다. 그럴 경우 저희는 오히려 Segmed의 한국 공급 partner가 될 수도 있습니다. 이 시나리오도 시드 자금 활용 계획에 포함."
- Obj: "Lunit, VUNO 같은 한국 AI 회사가 직접 데이터 사업에 진출하면?" → "그들은 AI 모델 회사입니다. 데이터 브로커는 수직 통합 대상이 아니라 인프라 파트너. PRD §6 Non-goals와 정반대 방향이 저희 moat 입니다."
- Obj: "경쟁사 로고를 써도 되나?" → **[Kyle 법무 검토 flag — §10 참조]**

---

## §3 장면 3 — Hospital Flow Live (3분, 실물 포털)

**본 장면은 슬라이드가 아니라 Hospital Dashboard 라이브 시연**이 중심. 슬라이드는 backup S6 1장만.

### S6 (backup) — Hospital Dashboard 6-tile preview

```
┌─────────────────────────────────────────────┐
│  Hospital Dashboard — what the hospital     │
│  executive sees                              │
│  ──────────────────────                      │
│                                             │
│  ┌────────┐ ┌────────┐ ┌────────┐          │
│  │ B-1    │ │ B-2    │ │ B-3    │          │
│  │ Studies │ │ Revenue│ │ Location│          │
│  │ today: │ │ est:   │ │ 서울   │          │
│  │ 42     │ │ ₩18M   │ │ 강남   │          │
│  │        │ │ *sim   │ │        │          │
│  └────────┘ └────────┘ └────────┘          │
│  ┌────────┐ ┌────────┐ ┌────────┐          │
│  │ B-4    │ │ B-5    │ │ B-6    │          │
│  │ Gateway│ │ Recent │ │ Audit  │          │
│  │ ● Online│ │ orders │ │ chain  │          │
│  │ 2m ago │ │ (list) │ │ OK     │          │
│  └────────┘ └────────┘ └────────┘          │
│                                             │
│  🟢 One scroll. Six tiles. No clutter.       │
│  🔵 Executive-grade transparency.            │
│                                             │
│  [FOOTNOTE] B-2 revenue is illustrative      │
│  simulation — settlement pending v0.2.       │
└─────────────────────────────────────────────┘
```

**Visual spec**:
- 3×2 tile grid 스크린샷. Teal `#0F766E` accent. B-2 하단 amber "Simulation" 배지.
- 실 라이브 화면과 동일한 와이어프레임. 백업용.

**Talking points** (라이브 중 대사, demo-script §2 장면 3 승계):
- **[겸손-안정]**: "이것이 김씨병원 — 데모 전용 가상 병원 — 이사장님이 보실 화면입니다. 6개 타일, 한 스크롤. 복잡하지 않게. B-2 수익 타일은 **시뮬레이션**입니다. 실 정산은 v0.2 이후입니다."
- **[자신감-단호]**: "경영진은 시간이 없습니다. 한 스크롤에 모든 게 보여야 합니다. Gateway 상태, 오늘 제공한 스터디 수, 예상 수익, 최근 주문, 감사 이벤트 — 여기 다 있습니다."

**라이브 중 핵심 발화 3 지점** (demo-script §2 장면 3 §핵심 상세):
1. "Gateway Online, 최근 동기화 2분 전 — 이사장님 '오늘 밤 편히 잘 수 있다' 신호."
2. "outbound HTTPS only, inbound 포트 0개 — 병원 방화벽 변경 0."
3. "해시 체인 Chain OK — 사후 조작 불가능." (터미널 `ingest-admin anchor verify`)

**Braided hook**:
- 🔵 **Investor lens**: "병원이 '왜 이 플랫폼에 남을까'의 답 — visible revenue + zero ops burden."
- 🟢 **Hospital lens**: "귀원 IT팀이 주 1회 15분 health check 외에 쓸 시간은 없습니다."

**Potential objections + response**:
- Obj: "실제 병원 IT팀이 이 대시보드를 본다고? 이사장이?" → "Kyle 의사 출신 + 병원 경영 배경에서 설계됨. 이사장님은 2타일(B-2 수익, B-4 Gateway)만 보시면 됩니다. 4타일은 IT·연구지원실용."
- Obj: "gateway 오프라인 되면 그것도 대시보드에 정확하게 표시되나?" → "장면 3 끝에 demo operator mode에서 토글해서 보여드릴 수 있습니다. 'Online'이 'Offline 5분' 으로 즉시 전환됩니다."

**실패 시 대응** (demo-script §3 런북 R-2 참조): 전체 tile 실패 시 → Ctrl+R reset + 60초 동안 S3 architecture 슬라이드로 돌아가 보강 설명.

---

## §4 장면 4 — Buyer Flow Live (4분, 실물 포털)

**본 장면도 슬라이드가 아닌 Buyer Portal 라이브**. 슬라이드는 S7 backup 1장.

### S7 (backup) — Buyer Portal flow preview

```
┌─────────────────────────────────────────────┐
│  Buyer Portal — from search to download     │
│  ─────────────────────────────              │
│                                             │
│  (1) Search                                  │
│  ┌──────────────────────────────────┐       │
│  │ facets: modality=CT, body=SPINE  │       │
│  │ min_hospitals ≥ 3                 │       │
│  │ ─ 12 studies, 3 hospitals, 1.2GB │       │
│  └──────────────────────────────────┘       │
│                   │                          │
│                   ▼                          │
│  (2) Review order                            │
│  ┌──────────────────────────────────┐       │
│  │ MSA hash: sha256:a1b2...          │       │
│  │ DUA: [✓] agreed                   │       │
│  │ [Confirm order]                   │       │
│  └──────────────────────────────────┘       │
│                   │                          │
│                   ▼                          │
│  (3) Track (5 phases)                        │
│  ┌──────────────────────────────────┐       │
│  │ Accepted ─ Fetch ─ Prep ─ Ready  │       │
│  │ (underlying: 12-state FSM)       │       │
│  └──────────────────────────────────┘       │
│                   │                          │
│                   ▼                          │
│  (4) Download                                │
│  ┌──────────────────────────────────┐       │
│  │ presigned URL × 12 (SHA-256)     │       │
│  │ expires: 23h 47m                 │       │
│  └──────────────────────────────────┘       │
│                                             │
│  🔵 From click to curl in < 48h (target).    │
│  🟢 Every step logged to your audit chain.   │
│                                             │
│  v0.1: DICOM viewer NOT included (v0.2).    │
│  v0.1: Stripe payment NOT included (v0.2).  │
└─────────────────────────────────────────────┘
```

**Visual spec**:
- 4단계 수직 플로우. 각 단계 미니 스크린샷 또는 wireframe.
- 하단 amber 박스 "v0.1에서 **아직** 없는 것" 정직 고지 (viewer, Stripe).

**Talking points** (라이브 중, demo-script §2 장면 4 승계):
- **[겸손-안정]**: "관점 전환. 글로벌 AI 엔지니어 Dana가 포털을 엽니다. 필터 — CT, 척추, 최소 3개 병원. 12개 스터디 매칭. Review → Confirm. 주문 생성. **매출 이벤트가 일어난 순간입니다.**"
- **[자신감-단호]**: "Confirm 누르는 그 순간 — 방금 봤습니다 — 병원의 B-5 최근 주문에 한 줄이 추가됩니다. 이게 매출 루프의 닫힘입니다. 지금 돈이 흐르기 시작했습니다."

**라이브 중 핵심 발화 3 지점**:
1. "가격은 마스킹. v0.1 billing stub — Stripe는 v0.2." (**[Kyle 법무 flag — 가격 노출 범위]**)
2. "min_hospitals ≥ 3 — 단일 병원 bias 방지. 경쟁사 Segmed도 유사 metric."
3. "MSA hash — 이미 외부 서명된 계약 본문의 sha256. 클릭랩 동의로 해당 MSA 지배 고정."

**Braided hook**:
- 🔵 **Investor lens**: "end-to-end revenue loop가 한 UI에서 닫힙니다. Unit economics의 기반."
- 🟢 **Hospital lens**: "구매자가 귀원 데이터를 고르는 순간, 귀원 감사 체인에 이벤트가 쌓입니다. 수익 청구권의 증거가 자동 축적."

**Potential objections + response**:
- Obj: "구매자가 12건만 사면 그게 무슨 매출인가?" → "12건은 예시입니다. 실 구매는 코호트 단위 500~5,000건. S10 unit economics에서 계산."
- Obj: "DICOM viewer 없으면 구매자가 품질을 어떻게 검증하나?" → "v0.1은 Research Use Only 샘플 10건 sandbox. 구매자가 자체 뷰어(OHIF, Horos)로 품질 검증 후 본 구매. v0.2에 내장 OHIF."
- Obj: "Stripe 없는데 결제는?" → "v0.1 파일럿은 Purchase Order + 월 인보이스 수동. Stripe는 v0.2. 파일럿 단계에서는 오히려 인보이스가 B2B에 자연스러움."

**실패 시 대응** (demo-script §3 R-3): 포털 500 시 → Ctrl+8 restart 15초. 그 동안 S7 슬라이드로 설명 이어감.

---

## §5 장면 5 — Compliance & Audit (2분, 슬라이드 2장)

### S8 — PIPA §28-8 & 2026 CEO Accountability

```
┌─────────────────────────────────────────────┐
│  The 2026 trigger — why "designed to align"  │
│  matters now                                 │
│  ──────────────────────────────              │
│                                             │
│  Article 28-8 (PIPA, since 2024):            │
│  ┌────────────────────────────────────┐     │
│  │ Cross-border transfer of personal  │     │
│  │ data: restricted.                   │     │
│  │ Fully anonymized info: exempt.      │     │
│  └────────────────────────────────────┘     │
│                                             │
│  2025~2026 revisions:                        │
│  • CEO personal accountability — fines       │
│    up to 3% of revenue (IAPP, 2025).         │
│  • Board-level audit evidence required       │
│    for data outsourcing.                     │
│  • Kim & Chang FAQ: "hospital CEOs now       │
│    need platform-grade audit chains".        │
│                                             │
│  RadiVault posture:                          │
│  ✓ Zone 1 de-ID before exit                  │
│  ✓ Hash-chained audit (SHA-256 anchors)      │
│  ✓ Hospital withdrawal right (30~90 days)    │
│  ✓ "Designed to align with" — not claiming   │
│    certification we do not hold.             │
│                                             │
│  ⚠ Legal opinion in progress · not final.    │
│                                             │
│  🔵 Regulatory moat, auditable.              │
│  🟢 The paperwork your board asks for.       │
└─────────────────────────────────────────────┘
```

**Visual spec**:
- 상단 PIPA 조문 박스 (quoted). 중간 2025~2026 개정 3 bullet.
- 하단 RadiVault posture 4 체크마크 (teal).
- 하단 amber disclaimer.

**Talking points**:
- **[겸손-안정]**: "2026년 개정 PIPA 요점 두 가지. 하나, 완전 익명정보는 여전히 국외이전 예외. 둘, CEO 개인책임이 강화됐습니다. 저희는 두 조문 사이를 기술로 메꿉니다. '준수한다'는 단정이 아니라 '부합하도록 설계됐다'는 표현을 씁니다. 법무 자문 진행 중입니다."
- **[자신감-단호]**: "CEO 개인책임 — 최대 매출 3% 벌금. 대표님이 병원 이사장이시라면, 이 조항은 남의 얘기가 아닙니다. 저희 감사 체인이 대표님의 '이사회 제출용 증거'가 됩니다."

**Braided hook**:
- 🔵 **Investor lens**: "규제 해자 = 진입장벽. 후발 경쟁자도 같은 법을 준수해야 합니다."
- 🟢 **Hospital lens**: "이사회가 묻는 '사후 감사 증거' — RadiVault가 자동 생성."

**Potential objections + response**:
- Obj: "3% 벌금 과장 아닌가?" → "IAPP 2025 기사 기반. 최종 해석은 법무. 저희 마케팅 문서 전체가 '인용'이지 '주장'이 아닙니다."
- Obj: "법무 자문 진행 중 — 언제 끝나나?" → "v0.1.5 (3~6개월) 내 자문 완료 + 법무법인 Opinion Letter 획득 목표. 시드 자금 용도 중 하나."
- Obj: "withdrawal 30~90일 — 그 사이에 데이터가 이미 해외 구매자 손에 가있으면?" → "철회 이벤트 트리거 시 중앙에서 presigned URL 즉시 revoke + 구매자 계약의 DUA 조항으로 사용 중단 + 삭제 obligation. 물리 회수는 불가능 — 이건 업계 전체 공통 한계. 명시적으로 계약서에 담습니다."

---

### S9 — Audit chain proof (live moment backup)

```
┌─────────────────────────────────────────────┐
│  Audit chain — Chain OK, in 15 seconds       │
│  ──────────────────────────                  │
│                                             │
│  Every event → SHA-256 hash                  │
│  Every hash → links to previous             │
│  Tampering → detected at verify time        │
│                                             │
│  ┌──────────────────────────────────┐       │
│  │ $ ingest-admin anchor verify \   │       │
│  │     --from 1 --to -1              │       │
│  │                                   │       │
│  │ Verifying 12,478 events...        │       │
│  │ Anchored every 100 events.        │       │
│  │ Last anchor: 2026-04-24T14:32:08Z │       │
│  │                                   │       │
│  │ Chain OK.                         │       │
│  └──────────────────────────────────┘       │
│                                             │
│  Tamper test (live if time permits):         │
│  $ ingest-admin tamper seq=42                │
│  $ ingest-admin anchor verify                │
│  → Chain broken at seq 42. Expected           │
│    sha256:a1b2..., got sha256:deadbeef.      │
│                                             │
│  🔵 Same primitive used for financial        │
│     audit (WORM, hash chain).                │
│  🟢 Evidence your CPO and internal audit     │
│     team will recognize on sight.            │
│                                             │
│  [FOOTNOTE] 48 tamper-detection unit tests   │
│  pass. docs/qa/qa-report-order-fulfillment.  │
└─────────────────────────────────────────────┘
```

**Visual spec**:
- 터미널 mockup 상 `Chain OK` 부분 amber 강조.
- 하단 tamper test 옵션 블록 (데모 시간 여유 시 라이브).

**Talking points**:
- **[겸손-안정]**: "모든 이벤트에 SHA-256 해시. 앞 해시가 뒤 해시에 묶여 있습니다. 이 한 줄 — 'Chain OK' — 가 이사회 제출용 한 줄 증거입니다. 여유 있으면 tamper test도 라이브로 보여드립니다. 한 이벤트를 수동 변조하면 즉시 'Chain broken at seq X'."
- **[자신감-단호]**: "이게 빈말이 아니라는 증거: 48개 tamper-detection unit test 통과 상태. leave-behind에 QA 리포트 5건 동봉."

**Braided hook**:
- 🔵 **Investor lens**: "SOC 2 Type II 준비 시 이 primitive가 Core Control 증거로 바로 쓰입니다."
- 🟢 **Hospital lens**: "CPO·감사팀이 이 한 줄로 이사회에 '우리 플랫폼은 무결합니다' 보고 가능."

**Potential objections + response**:
- Obj: "SHA-256은 오래된 기술 아닌가?" → "Git, Bitcoin, 대부분 금융 감사에서도 SHA-256. 오래된 게 아니라 검증된 것."
- Obj: "anchor가 분실되면?" → "anchor는 S3 Object Lock + glacier offsite replica. 3-2-1 백업 원칙."

---

## §6 장면 6 — Numbers & Unit Economics (2분, 슬라이드 3장)

### S10 — TAM & Market Sizing

```
┌─────────────────────────────────────────────┐
│  Market — bottom-up, Korea first             │
│  ────────────────────────                    │
│                                             │
│  Top-down (context only):                    │
│  • Global medical imaging AI: $1.65~2.5B     │
│    (2025), CAGR 30%+ (research §2).         │
│  • Korea medical AI: $0.37B → $6.67B by     │
│    2030 (CAGR 50.8%, research §2).          │
│                                             │
│  Bottom-up (Korea TAM):                      │
│                                             │
│  45 tertiary hospitals                       │
│  × 50,000 CT/MR studies/year avg             │
│  × 10% opt-in rate (conservative)            │
│  × $10/study blended price                   │
│  = ~$22.5M TAM (Korea only)                  │
│                                             │
│  Plus: Japan, Taiwan, SE Asia PIPA-like      │
│        = 3~5× expansion.                     │
│                                             │
│  🔵 SAM $5~10M (Korea, assuming dominance).  │
│  🟢 Your hospital's share scales with opt-in.│
│                                             │
│  [FOOTNOTE] All figures illustrative. Based  │
│  on public market reports + internal         │
│  assumptions. See research/k-meddata-        │
│  research-summary.md §2 for sources.         │
└─────────────────────────────────────────────┘
```

**Visual spec**:
- 상단 Top-down (회색, context), 하단 Bottom-up (amber, 계산식).
- 하단 disclaimer.

**Talking points**:
- **[겸손-안정]**: "보수적 가정입니다. 3차 병원 45곳, 연 5만 스터디, 옵트인 10%, 단가 $10 — 한국만 연 $22.5M TAM. 아시아 확장 3~5배. 숫자는 전부 '예시·가정'입니다. 실 파일럿 측정 후 재전망."
- **[자신감-단호]**: "한국 45개 3차 병원 중 2~3곳만 확보해도 의미 있는 traction. 저희가 일하는 숫자는 작게 시작합니다 — 하지만 카테고리를 정의할 수 있는 크기입니다."

**Braided hook**:
- 🔵 **Investor lens**: "시드 → Series A → B까지 3단 성장 가능한 TAM."
- 🟢 **Hospital lens**: "귀원의 연 공급 규모 × revenue share = 월 정산 금액. S11 참조."

**Potential objections + response**:
- Obj: "옵트인 10%가 현실적인가?" → "전체 데이터가 아닙니다. 특정 코호트(주로 신경·근골격·종양)에서 10% opt-in. 상세는 파일럿에서 실측."
- Obj: "$10/study 근거?" → "Segmed·Gradient 공개 정보 없음. 업계 통념 $5~20 range. 중간값 선택. Research tier는 낮고, commercial training tier는 높음."
- Obj: "TAM 숫자를 외부에 이렇게 구체적으로 공개해도 되나?" → **[Kyle 법무 flag — §10 참조]**

---

### S11 — Pricing & Revenue Share (Illustrative)

```
┌─────────────────────────────────────────────┐
│  Pricing tiers — illustrative simulation     │
│  ──────────────────────────                  │
│                                             │
│  Buyer pricing (per study, blended):         │
│  ┌──────────────────────────────────┐       │
│  │ Tier 1 (metadata + auto-label)   │       │
│  │   → $2~5 / study                 │       │
│  │                                   │       │
│  │ Tier 2 (+ expert radiologist     │       │
│  │         label)                    │       │
│  │   → $8~15 / study                │       │
│  │                                   │       │
│  │ Tier 3 (+ segmentation mask)     │       │
│  │   → $20~40 / study               │       │
│  └──────────────────────────────────┘       │
│                                             │
│  Hospital revenue share:                     │
│  ┌──────────────────────────────────┐       │
│  │ Tier 1: 25~30%                    │       │
│  │ Tier 2: 35~45%                    │       │
│  │ Tier 3: 40~50%                    │       │
│  │ + Pilot premium: +1~2%pt          │       │
│  │ + MG floor: ₩500~1,000M/year      │       │
│  │   (pilots only, 1st year)         │       │
│  └──────────────────────────────────┘       │
│                                             │
│  Example: one pilot hospital                 │
│  • 10,000 studies/year, Tier 2 mix           │
│  • Revenue: ~$100K/year gross                │
│  • Hospital share (40%): ~$40K/year          │
│  • ≈ ₩54M/year                               │
│                                             │
│  🔵 Unit economics: see S12.                 │
│  🟢 Your first year floor: guaranteed MG.    │
│                                             │
│  [FOOTNOTE] All figures illustrative.        │
│  Final pricing per buyer/hospital MSA.       │
└─────────────────────────────────────────────┘
```

**Visual spec**:
- 상단 buyer pricing 박스 (blue).
- 중간 hospital revenue share 박스 (teal).
- 하단 예시 계산 박스 (amber).
- Disclaimer 8pt: "All figures illustrative — final per MSA."

**Talking points**:
- **[겸손-안정]**: "3 tier — metadata, expert-label, segmentation — tier별 단가와 병원 revenue share입니다. 파일럿 병원에는 1~2%p 프리미엄 영구 부여. MG는 ₩500만~1,000만/년, 1년차 한정. 전부 예시. 실 확정은 MSA에서."
- **[자신감-단호]**: "연 1만 스터디 × tier 2 중심 mix = 병원 몫 ₩54M. 파일럿 MG 위에 이게 쌓입니다. 대부분 병원은 영상 데이터에서 0원 받았습니다. 이 0을 1로 만드는 겁니다."

**Braided hook**:
- 🔵 **Investor lens**: "take rate 50~75%. Segmed·Gradient 비공개이나 데이터 브로커 업계 중위."
- 🟢 **Hospital lens**: "첫 서명 시 ₩500~1,000만 MG 즉시 효과 + 2년차부터 volume 기반."

**Potential objections + response**:
- Obj: "revenue share 50%는 너무 적다." → "원본 수집·전송은 귀원이 하시지만, de-ID·search index·contract management·audit·support·marketing — 전부 저희. 플랫폼 부담이 큽니다. 파일럿 프리미엄으로 조율."
- Obj: "MG ₩1,000만이면 회사가 손해 아닌가?" → "파일럿 1년차 한정. 이후 volume 기반으로 전환. 1년차 MG는 'risk 공유' 신호."
- Obj: "이 숫자 공개해도 되나?" → **[Kyle 법무 flag — §10]**. 현 문서는 "illustrative" 명시로 방어.

---

### S12 — Unit Economics & Gross Margin

```
┌─────────────────────────────────────────────┐
│  Unit economics — Year 3 target              │
│  ────────────────────────                    │
│                                             │
│  Per-study blended economics (Tier 2 example)│
│                                             │
│  Buyer price:          $10.00                │
│  ─────────────────────────                   │
│  Hospital share (40%): -$4.00                │
│  Cloud storage & egress: -$0.50              │
│  De-ID compute:        -$0.50                │
│  Support & overhead:   -$2.00                │
│  ─────────────────────────                   │
│  Contribution margin:  $3.00 (30%)           │
│                                             │
│  At scale (100K+ studies/yr):                │
│  • Fixed costs amortize → 60~70% gross margin│
│  • Target Year 3: 65~70%                    │
│                                             │
│  Benchmarks:                                 │
│  • Data marketplace industry: 65~80%         │
│  • Segmed/Gradient: not disclosed            │
│    (research §6)                             │
│                                             │
│  Comps funding:                              │
│  • Segmed Series A: $10.4M (2024)            │
│  • Gradient Seed: $2.75M (2023)              │
│  • Truveta Series C: $320M (2025)            │
│                                             │
│  🔵 Margin path realistic, not aggressive.   │
│  🟢 Platform health → hospital stability.    │
│                                             │
│  [FOOTNOTE] All figures illustrative,        │
│  conservative vs industry medians.           │
└─────────────────────────────────────────────┘
```

**Visual spec**:
- 상단 per-study P&L 미니 테이블.
- 중간 at-scale gross margin bullet.
- 하단 comps 3 brands funding (context only).

**Talking points**:
- **[겸손-안정]**: "단위 경제. tier 2 예시. 3달러 CM1 per study, scale up 시 gross margin 65~70%. Segmed Series A $10.4M, Gradient seed $2.75M — 저희가 참고하는 comps입니다."
- **[자신감-단호]**: "margin 60% 달성 시 회사 자립. 70% 달성 시 Series A 레벨의 profitability margin. scale은 병원 10곳 + 구매자 5곳 시점 — v0.2~v0.3 범위."

**Braided hook**:
- 🔵 **Investor lens**: "SaaS 평균 gross margin 70~80% 대비 약간 낮으나 marketplace take rate가 보완."
- 🟢 **Hospital lens**: "플랫폼이 건강해야 정산이 지속. 병원에겐 플랫폼 margin이 곧 '파트너 안정성 신호'."

**Potential objections + response**:
- Obj: "65% gross margin — 실측 근거 있나?" → "아직 없습니다. 파일럿 3개월 후 실측 재전망. 현재는 AWS pricing + comp study + 인건비 할당 기반 추정. 보수적 20% 할인."
- Obj: "Truveta $320M을 왜 넣나?" → "경쟁사가 아닌 category validator. 병원 consortium 모델이 $1B+ valuation까지 간다는 증거. 우리는 Korea-scoped 버전."

---

## §7 장면 7 — What We Need & CTA (2분, 슬라이드 4장)

### S13 — Dual Ask (Core Slide)

```
┌─────────────────────────────────────────────┐
│  One signature, two decisions                │
│  ─────────────────────────                   │
│                                             │
│  ┌────────────────┐   ┌─────────────────┐   │
│  │ 🔵 INVESTOR     │   │ 🟢 HOSPITAL      │   │
│  │                │   │                  │   │
│  │ Seed: $[X]M     │   │ First pilot     │   │
│  │                │   │ hospital MOU    │   │
│  │ Use of funds:   │   │                  │   │
│  │ • 2 pilot       │   │ Included:        │   │
│  │   hospitals     │   │ • MG ₩500~1,000M │   │
│  │ • 1~2 pilot     │   │ • Rev share +1~2%p│  │
│  │   buyers        │   │ • Advisory seat  │   │
│  │ • v0.1.5 GA     │   │ • MSA co-drafting│   │
│  │ • Legal opinion │   │ • 3-month opt-in │   │
│  │   + SOC 2       │   │                  │   │
│  │ • 18-mo runway  │   │ Exit right:      │   │
│  │                │   │ • 30 days notice │   │
│  │ Target close:   │   │ • Data stays in  │   │
│  │ Q[?] 2026       │   │   your PACS      │   │
│  │                │   │                  │   │
│  └────────────────┘   └─────────────────┘   │
│                                             │
│  "One signature, two decisions."             │
│                                             │
│  [FOOTNOTE] Specific $ amount and closing    │
│  timing per Kyle's decision. MG and rev      │
│  share subject to legal review + final MSA.  │
└─────────────────────────────────────────────┘
```

**Visual spec**:
- 좌우 2단 ask. 좌측 blue, 우측 teal. 동일 높이·동일 bullet 수.
- 하단 가운데 한 줄 "One signature, two decisions." (가장 큰 font, 36pt).
- Kyle 미결정 사항 `[X]`, `Q[?]` placeholder 명시.

**Talking points**:
- **[겸손-안정]**: "정리하겠습니다. 투자자 관점 — 시드. 금액은 별도 논의. 용도는 파일럿 병원 2곳, 버이어 1~2사, v0.1.5 GA, 법무 자문 완료, SOC 2 Type I 착수. 병원 관점 — 첫 파일럿 MOU. MG, rev share 프리미엄, 자문 지분, MSA 공동 작성, 3개월 옵트인 + 30일 고지 해지권. **하나의 서명에 두 결정이 붙습니다.**"
- **[자신감-단호]**: "다른 투자자는 이 두 결정을 분리하자고 합니다. 저희는 반대입니다. 대표님이 두 모자를 겸하시니까 — 이 두 결정이 붙어야 **같은 RiSK에 대한 같은 signal**이 됩니다. 하나의 서명. 둘의 약속."

(demo-script §2 장면 7 "하나의 서명에 두 결정" 핵심 hook 승계)

**Braided hook**: 이 슬라이드 자체가 Braided. 별도 badge 불필요.

**Potential objections + response**:
- Obj: "금액이 비어있다 — 얼마인가?" → **[Kyle 결정 — §10]**. "금액은 대표님과의 대화를 통해 조율하고 싶습니다. Segmed Series A $10.4M 참조. 시드 단계로는 그 1/2~1/3 규모."
- Obj: "왜 금액 미리 제시하지 않나?" → "시드 단계에서는 청중 pain-point와 회사 목표의 역계산. 대표님 안에 있는 '이 미팅에서 가능한 티켓 사이즈'에 맞추고 싶습니다."
- Obj: "파일럿과 투자를 분리하면?" → "가능합니다. 둘 중 하나만이라도 진행 가능. 다만 **동시 결정이 최상의 outcome**입니다 — 왜인지는 다음 슬라이드."

---

### S14 — Why Dual Signature Makes Sense (Logic)

```
┌─────────────────────────────────────────────┐
│  Why one signature — the Segmed-Advocate    │
│  precedent                                   │
│  ──────────────────────────                  │
│                                             │
│  Segmed Series A (2024):                     │
│  • Advocate Health (67-hospital network)     │
│  • Simultaneously: investor + first data     │
│    supplier.                                 │
│  • Source: PR Newswire, Radiology Business.  │
│                                             │
│  Truveta (2020+, valuation $1B+):            │
│  • 17 health systems as                      │
│    founding partners AND investors.          │
│                                             │
│  Why this works:                             │
│  ❶ Investor has informed-supplier view.     │
│  ❷ Supplier has board-level commitment.     │
│  ❸ Platform has proof of concept in first   │
│     real partner.                           │
│  ❹ Alignment: if one side fails, both fail. │
│     This removes adversarial dynamics.       │
│                                             │
│  For RadiVault, Kyle's dual-hat meeting      │
│  is this precedent, at Seed scale.           │
│                                             │
│  🔵 Category leaders are built this way.     │
│  🟢 Early mover = founding-partner equity.   │
│                                             │
│  [FOOTNOTE] Segmed/Truveta cited from        │
│  public PR. Structure similarity does not    │
│  imply endorsement.                          │
└─────────────────────────────────────────────┘
```

**Visual spec**:
- 상단 2 case study (Segmed, Truveta) 박스.
- 중간 4 bullet (왜 작동하는가).
- 하단 한 줄: "For RadiVault, this meeting is that precedent — at Seed scale."

**Talking points**:
- **[겸손-안정]**: "이 구조는 제가 발명한 게 아닙니다. Segmed Series A — Advocate Health (67-hospital network)가 투자자이자 첫 공급자. Truveta — 17 health system이 창립 파트너이자 주주. Series A 이전 시드 단계에서 이 구조가 작동한 케이스가 저희입니다."
- **[자신감-단호]**: "이건 precedent가 있는 구조입니다. 그리고 대표님은 Kyle Jeon CEO — 투자자이자 이사장. 정확히 같은 조건입니다. 시드 스케일로."

**Braided hook**:
- 🔵 **Investor lens**: "informed-supplier view = better due diligence than any external research."
- 🟢 **Hospital lens**: "founding partner equity + advisory seat = 플랫폼의 방향 결정에 참여."

**Potential objections + response**:
- Obj: "Advocate·Truveta는 consortium 17곳. 저 혼자 시작하는 건 다르다." → "Consortium은 규모 단계. Seed는 **첫 한 명**. Kyle이 그 첫 한 명입니다. 2~3번째 파트너는 Kyle이 소개해주실 수 있는 range 안에 있습니다."
- Obj: "병원장 겸 투자자 = conflict of interest 아닌가?" → "공개 시 문제 없음. 한국 상법상 이사회 공개 의무 준수. MSA에 특수관계인 조항. 오히려 미공개가 문제."

---

### S15 — Team & Trajectory

```
┌─────────────────────────────────────────────┐
│  Team · what got us here                     │
│  ─────────────────                           │
│                                             │
│  Kyle Jeon (Founder / CEO)                   │
│  • Medical imaging QA background             │
│  • DICOM domain expert (RTOG QA, MIM, etc.)  │
│  • Korean healthcare system knowledge        │
│  • [추가 항목 Kyle 확정]                     │
│                                             │
│  v0.1 MVP (Apr 2026):                        │
│  • 5 backend components shipped              │
│  • Buyer Portal + Hospital Dashboard         │
│  • 407 tests passing                         │
│  • 22 Next.js routes                         │
│  • Full audit hash chain + tamper tests      │
│  • QA reports: 5 on file                     │
│                                             │
│  Building:                                   │
│  • Claude Code as engineering partner        │
│  • Pipeline: research → planner → designer   │
│    → developer → qa → marketer (7 phases)    │
│                                             │
│  Advisors sought (seed use-of-funds):        │
│  • Legal (PIPA · HIPAA cross-border)         │
│  • Korean radiologist consortium             │
│  • B2B healthcare SaaS operator              │
│                                             │
│  🔵 Solo + high-leverage AI tooling = speed. │
│  🟢 Domain credibility + Korean context.     │
└─────────────────────────────────────────────┘
```

**Visual spec**:
- 상단 Kyle 프로필.
- 중간 v0.1 traction 체크마크.
- 하단 advisor sought (자금 용도 tie-back).

**Talking points**:
- **[겸손-안정]**: "팀. 저 혼자 + Claude Code AI partner. v0.1 6주 안에 5 컴포넌트 + 2 포털 + 407 테스트. 시드 자금은 법률 자문, 한국 영상의학 자문위, B2B 헬스케어 SaaS operator 3 direction에 할당 예정."
- **[자신감-단호]**: "의도적으로 얇은 팀을 유지 중입니다. v0.1.5 GA 이후 2~3명 senior 채용. 그 전까지 AI + Kyle + advisors만으로 완주. 이 구조가 seed 단계 capital efficiency의 증거입니다."

**Braided hook**:
- 🔵 **Investor lens**: "1인 + AI = 6주 MVP. capital efficiency 지표."
- 🟢 **Hospital lens**: "도메인 이해 있는 사람이 플랫폼 설계. 귀원 IT팀과 공통 언어."

**Potential objections + response**:
- Obj: "1인 팀 리스크는?" → "Kyle single point of failure은 인정. 시드 클로즈와 함께 co-founder 또는 senior eng #2 탐색. advisor 층이 buffer."
- Obj: "Claude Code로 만들었으면 quality는?" → "407 tests + ruff clean + QA report 5건이 증거. 모든 commit은 Kyle이 review. 상세는 progress.txt."

---

### S16 — Closing · Contact

```
┌─────────────────────────────────────────────┐
│                                             │
│                                             │
│        Korea's medical imaging data,         │
│        compliantly delivered to              │
│        the world's AI.                       │
│                                             │
│                                             │
│        One signature, two decisions.         │
│                                             │
│                                             │
│        ─────────────────                     │
│                                             │
│        Kyle Jeon                             │
│        Founder / CEO, RadiVault              │
│        kylejeon83@gmail.com                  │
│                                             │
│        Next step:                            │
│        • 90-min technical deep dive          │
│        • Legal opinion walkthrough           │
│        • Pilot MOU review                    │
│                                             │
│        Questions?                            │
│                                             │
│                                             │
│  [FOOTNOTE] Leave-behind: 7 documents.       │
│  See docs/marketing/leave-behind-            │
│  curation-kr.md                              │
└─────────────────────────────────────────────┘
```

**Visual spec**:
- 타이포 중심. 단색 배경 `#0F172A`, white text. 대칭.
- "Questions?" 약간 작게 (24pt) — 침묵 유도 용.

**Talking points** (demo-script §2 장면 7 §연출 승계):
- "이상입니다. 질문 받겠습니다."
- **침묵 3초 유지** (프레젠터가 먼저 깨지 말 것).

**Braided hook**: 불필요. 슬라이드 중앙 문장이 hook.

**Potential objections + response** (Q&A 3분용 상세 20건은 demo-script §5에 있음):
- 실전 Q&A는 demo-script §5에서 20건 상세 답변. 본 슬라이드는 질문 개시 trigger 역할.

---

## §8 Appendix 슬라이드 (S17~S18, Q&A 대비)

### S17 — Risks & mitigations (backup)

```
┌─────────────────────────────────────────────┐
│  Top 5 risks — what could go wrong           │
│  ─────────────────────                       │
│                                             │
│  ❶ Legal: PIPA re-interpretation            │
│     → Opinion letter Q[?] 2026.              │
│     → Withdrawal right + hash chain = defense│
│                                             │
│  ❷ Competitive: Segmed enters Korea         │
│     → 18~24 mo head start.                   │
│     → Fallback: become Segmed's Korea supplier│
│                                             │
│  ❸ Supply: pilot hospital signing slow       │
│     → Current meeting is the mitigation.     │
│     → 2~3 backup leads in Kyle's network.    │
│                                             │
│  ❹ De-ID technology: re-identification risk  │
│     → Annex E + pixel OCR + defacing.        │
│     → External audit v0.2.                   │
│     → Buyer MSA liability split.             │
│                                             │
│  ❺ FSL commercial license (v0.2 risk)        │
│     → Alternative mridefacer pathway.        │
│     → $5~15K/yr budget if needed.            │
│                                             │
│  🔵 Mitigations are budget lines, not denial.│
│  🟢 Hospital's own withdrawal right is a     │
│     mitigation for all 5.                    │
└─────────────────────────────────────────────┘
```

---

### S18 — Sources & Appendix

```
┌─────────────────────────────────────────────┐
│  Sources & further reading                   │
│  ─────────────                               │
│                                             │
│  Market · Regulation                         │
│  • IAPP 2025, Korea PIPA Overhaul            │
│  • Kim & Chang PIPA FAQ 2025                 │
│  • ICLG Digital Health Laws Korea 2026       │
│  • docs/research/k-meddata-research-summary  │
│  • docs/research/demo-pitch-references       │
│                                             │
│  Competitors (public materials)              │
│  • Segmed: PR Newswire Series A 2024         │
│  • Gradient: Atlas 2 launch 2025             │
│  • Truveta: Fierce Healthcare 2025           │
│  • Rhino Health: VentureBeat 2021            │
│  • Flywheel.io: SaaS announcement 2023       │
│                                             │
│  Internal docs (leave-behind)                │
│  • PRD v0.1                                  │
│  • ARCHITECTURE v1                           │
│  • 5 dev-specs + 5 design-specs              │
│  • 5 QA reports                              │
│  • Marketing one-pagers (EN / KR)            │
│                                             │
│  Demo assets                                 │
│  • 17-min demo script v0.2                   │
│  • Buyer Portal (live)                       │
│  • Hospital Dashboard (live)                 │
│  • Rehearsal MP4 (72h link)                  │
│                                             │
│  Contact: kylejeon83@gmail.com               │
└─────────────────────────────────────────────┘
```

---

## §9 Kyle 발화 스타일 가이드 — 전체 데크

각 장면의 talking points에 **[겸손-안정]** / **[자신감-단호]** 두 버전을 제공. 리허설 시 Kyle 본인 낭독 후 장면별로 선택 또는 믹스. 권장 조합:

| 장면 | 권장 톤 | 이유 |
|---|---|---|
| 1 (Hook) | 겸손-안정 | 서두에 자신감 과잉은 역효과. 17분의 무게를 설정하는 구간. |
| 2 (Architecture) | 자신감-단호 | 기술 moat는 확신 있게. 경쟁사 명시에서 톤 흔들림 금지. |
| 3 (Hospital live) | 겸손-안정 | 병원 경영진 모자로 전환. "이사장님 시선으로" 공감 톤. |
| 4 (Buyer live) | 자신감-단호 | 구매자 = 효율 중시. 속도감 + 확신. |
| 5 (Compliance) | 겸손-안정 | 법률 이슈는 단정 금지. 겸손한 어조가 오히려 신뢰. |
| 6 (Numbers) | 자신감-단호 | 숫자는 방어적으로 말하면 약해 보임. "illustrative" disclaimer 있으므로 자신감 유지. |
| 7 (Ask) | 자신감-단호 + 마지막 3초 침묵 | ask는 약하게 하면 거절 유도. 단, "질문 받겠습니다" 후 침묵은 깨지 마라. |

---

## §10 법률 검토 flag (Kyle 외부 자문 요청 필요)

이전 마케팅 문서 관행 승계. 본 데크 최종 승인 전 반드시 flag 처리.

1. **경쟁사 비교 슬라이드 (S5)** — Segmed/Gradient/Truveta/Rhino 명시. 공개 브랜드 + 공개 자료만 사용했으나, 한국 비교광고 규정 (공정거래위원회 표시광고법) 리뷰. 특히 "empty quadrant" 프레임이 비방으로 해석될 여지.
2. **PIPA §28-8 + 2026 CEO 개인책임 (S8)** — IAPP·Kim & Chang 인용은 2차 자료. 법리 정확성 법무법인 확인. "최대 3% 벌금" 수치 — 정확한 수치 재검증 필요.
3. **파일럿 병원 placeholder (S15 advisors, S17 risk ❸)** — 아직 서명 병원 없음. "in discussions" 표현 유지. 실명 언급 금지.
4. **가격·revenue share 숫자 공개 (S11, S12)** — MG ₩500~1,000만, revenue share 25~50%, 단가 $10 — 전부 "illustrative" 명시했으나, 파일럿 MSA 확정 전 변경 가능성. 공개 시 후속 협상에서 anchor 될 여지. Kyle 최종 결정.

**추가 고려**:
5. TAM $22.5M (S10) — 숫자 공개 범위. 투자자에게는 OK, 경쟁사 유출 시 도움 줄 가능성.
6. Segmed Series A $10.4M 등 funding comps (S12) — 공개 PR이므로 인용 안전. 다만 비교의 맥락이 "우리도 이만큼 필요" 로 해석될 여지 — 시드 규모 과대 기대 형성 방지.

---

## §11 리허설 리뷰 체크리스트 (본 데크 전용)

demo-script §4 R-1~R-9 승계 + 본 데크 전용:

- [ ] **S1~S2** — 17분 중 첫 2분 리허설 3회. 제목 슬라이드 앞에서 긴장 해소 루틴 완료.
- [ ] **S3** — Zone 경계 빨간 점선 프로젝터 가독성 확인. 일부 프로젝터 dashed 표현 흐림.
- [ ] **S4** — "407 tests" 숫자 자신감 있게 발음 (머뭇거림 없음).
- [ ] **S5** — 경쟁사 로고 노출 최종 결정 (legal flag §10.1). flag 해결 전 ASCII/wordmark로만 제작.
- [ ] **S8** — PIPA 조문 인용 정확성 재확인. "§28-8" vs "제28조의8" 일관성.
- [ ] **S10~S12** — "illustrative" "simulation" 문구 각 슬라이드 3회 확인 (disclaimer 누락 시 legal risk).
- [ ] **S13** — `[X]` `Q[?]` placeholder 실 미팅 전 Kyle 확정 수치로 교체. 대안: 빈칸 유지 후 화이트보드 실시간 작성.
- [ ] **S16** — closing 3초 침묵 리허설 5회. Kyle 본인 불편함 극복 여부 확인.
- [ ] **S17~S18** — Q&A 시 appendix 호출 속도 (슬라이드 점프 1초 이내).

---

## §12 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|---|---|---|---|
| 0.1 | 2026-04-24 | @marketer | 최초 드래프트. 장면 1~7 / 16 본 슬라이드 + 2 appendix. 각 슬라이드 ASCII mock, talking points 2 스타일, Braided hook, objections + response, 법률 검토 flag 4+2건. demo-script §2·§5, research/demo-pitch-references §2·§3·§7 승계. |

---

### NEXT_STEP (본 파일)

- 완료 산출물: `docs/marketing/pitch-deck-ceo-meeting-kr.md`
- **Kyle 리뷰 필요 사항**:
  1. **S13 Dual Ask** — 시드 `[X]M` 금액, 목표 close 분기 `Q[?]` 확정.
  2. **S15 Team** — Kyle 프로필 세부 항목 (경력, 학력, advisor 후보 이름).
  3. **S5 경쟁사 비교** — 로고 사용 여부 법무 flag 해결.
  4. **S8 PIPA 수치** — "3% 벌금" 정확성 법무 재검증.
  5. **Talking points 2 스타일** — 각 슬라이드 [겸손-안정] vs [자신감-단호] 택일 또는 믹스.
  6. **S11 MG·revenue share** — 공개 수치 최종 결정.
- **@designer 2차 세션** (PPT 실물화) 또는 Kyle이 Keynote/Figma 작업:
  - 본 ASCII mock을 시각 slide로 변환.
  - 색상 토큰 (Buyer blue `#1D4ED8` / Hospital teal `#0F766E` / amber `#F59E0B`) 승계.
  - 18 슬라이드 기준 목표 파일 사이즈 < 20MB.
- **리허설 R-1~R-9** — demo-script §4 적용. 본 데크 전용 §11 체크 추가.
- 제안 다음 단계:
  - (즉시) Kyle 본인 낭독 1회, talking points 스타일 택일.
  - (24h 내) @designer PPT 착수 또는 Kyle Keynote.
  - (미팅 D-1) 리허설 R-1 녹화본 보존.
