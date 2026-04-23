# RadiVault — 미팅 후 Leave-behind 큐레이션 (한국어)

> **Status**: Draft v0.1 — Kyle 리뷰 후 미팅 당일 전달.
> **문서 버전**: v0.1 (2026-04-24) · **작성자**: @marketer
> **청중**: 대표님 (미팅 종료 후 혼자 재확인·의사결정 모드)
> **목적**: 대표님이 "투자 결정" 전 / "파일럿 서명" 전에 **혼자 다시 확인**할 자료의 우선순위·경로·소요시간을 정리한 가이드
> **포맷**: 3-티어 독서 경로. "15분 overview → 1시간 deep dive → 반나절 due diligence"
> **연동**: 데모 미팅 종료 직후 이메일 전달. 본 문서가 첨부 자료들의 "표지" 역할.

---

## §0 어떻게 사용하는가

이 문서는 단순한 파일 목록이 아닙니다. 대표님이 미팅 끝난 뒤 **혼자 앉아서 재확인**할 때, 어떤 순서로 무엇을 볼지 안내하는 지도입니다.

사용 방식:

1. **시간이 15분뿐이라면** → §1 Tier 1만 읽으세요. 결정의 80%가 여기서 판단됩니다.
2. **시간이 1시간 있다면** → §1 + §2 Tier 2. 기술·법률 근거까지.
3. **반나절 due diligence** → §1 + §2 + §3 Tier 3. QA 리포트·리서치 원문·dev-spec 전체.

각 자료에는 **(a) 경로, (b) 소요시간, (c) 읽는 목적, (d) 우선 확인 포인트** 를 함께 표시합니다.

---

## §1 Tier 1 — 15분 Overview (결정의 핵심 80%)

**목표**: "이 회사에 투자할 가치가 있나?" 와 "우리 병원이 파일럿에 합류할 가치가 있나?" 를 **한 자리에서** 판단 가능한 최소 자료군.

### T1-1. **CEO 미팅용 1-Pager (KR)** ⭐ 출발점

- **경로**: `docs/marketing/one-pager-ceo-meeting-kr.md`
- **소요**: **3~5분**
- **목적**: 미팅에서 본 모든 메시지를 A4 1장으로 압축 재확인. 투자자+병원 두 렌즈 병치.
- **우선 확인 포인트**:
  1. "두 공백이 2026년 같은 해에 겹쳤다"는 Why Now 논리가 본인께 설득력 있는가.
  2. Unit economics (MG ₩500~1,000만, revenue share 25~50%) — 귀원 대입 시 수익 가늠.
  3. Ask (시드 `[X]M` placeholder) — Kyle과 조율할 숫자.

### T1-2. **CEO 미팅용 1-Pager (EN)** (선택)

- **경로**: `docs/marketing/one-pager-ceo-meeting-en.md`
- **소요**: **3~5분**
- **목적**: 영문 투자자 라운드 공유 시, 또는 해외 자문위원에게 전달 시. 한국어 버전과 동일 내용.
- **우선 확인 포인트**: 영문 표현의 컴플라이언스 가드 언어 ("designed to align", "in preparation") 일관성 확인.

### T1-3. **피치덱 초안 (KR)**

- **경로**: `docs/marketing/pitch-deck-ceo-meeting-kr.md`
- **소요**: **5~10분** (ASCII mock 빠른 훑기. 장면 1·7만 집중이면 3분)
- **목적**: 미팅에서 본 슬라이드를 혼자 다시 따라가며 talking points 확인. 특히 장면 7 "Dual Ask" 를 본인 모자 둘 다로 재독.
- **우선 확인 포인트**:
  1. §7 장면 7 (Dual Ask) S13 — 투자자 ask와 병원 ask가 **대칭적으로** 나열됐는가.
  2. §5 장면 5 (Compliance) S8 — PIPA §28-8 + 2026 CEO 개인책임 인용이 과장인가 정확한가.
  3. §10 법률 검토 flag 4+2건 — 본인 법무와 공유할 항목.

### Tier 1 요약

이 3개 자료만으로 **투자 Go/No-go 예비 판단 + 파일럿 MOU 논의 개시 여부** 결정 가능. 구체 숫자 조율은 후속 미팅에서.

---

## §2 Tier 2 — 1시간 Deep Dive (기술·법률·시장 근거)

**목표**: "이 회사가 주장하는 기술·법률·시장 포지셔닝이 실제로 근거 있는가" 를 원문 기반으로 검증.

### T2-1. **PRD (Product Requirements Document)**

- **경로**: `docs/prd.md`
- **소요**: **15분**
- **목적**: 제품 범위 전체를 한 문서에서. 비전·타깃·핵심 가치 제안·범위·비기능 요구사항·Non-goals.
- **우선 확인 포인트**:
  1. §6 Non-goals — "환자 직접 업로드 C2B2B 폐기", "자체 AI 모델 비판매" 등 **하지 않기로 한 것** 이 명확한가.
  2. §8 제약 — PIPA §28-8, HIPAA, revenue share 25~50%, 파일럿 MG ₩500~1,000만 — 공개 문서에 이미 담긴 숫자와 1-pager 일치 확인.
  3. §10 리스크·가정 — 회사가 자기 리스크를 정직하게 공개하는가 판단.

### T2-2. **ARCHITECTURE (아키텍처 문서)**

- **경로**: `docs/ARCHITECTURE.md`
- **소요**: **10분**
- **목적**: 3-Zone Hybrid Model이 실제 소프트웨어 아키텍처로 어떻게 구현되는가. 데모에서 본 Zone 1/2/3 슬라이드의 원문.
- **우선 확인 포인트**:
  1. Zone 1 / 2 / 3 경계와 실제 구성요소 (Gateway, Central, Portal) 매핑.
  2. 이벤트 해시 체인 설계 — 병원 CPO가 "이 구조면 우리도 ISO 27001 준비에 활용 가능한가" 검토 가능한 수준인지.

### T2-3. **리서치 — K-MedData 시장·규제 종합**

- **경로**: `docs/research/k-meddata-research-summary.md`
- **소요**: **15분** (§2 시장, §4 왜 한국인가, §5 규제만 집중 시 10분)
- **목적**: 미팅에서 본 "Korean imaging depth + PIPA 해자" 주장의 1차·2차 출처 확인.
- **우선 확인 포인트**:
  1. §2 시장 규모 숫자 ($1.65~2.5B, CAGR 30%) 의 근거 — Grand View Research·IMARC 등.
  2. §4 한국 PACS 보급률·FDA-cleared Korean AI 벤더 — Lunit, VUNO 등 실제 인허가 기록.
  3. §5 PIPA §28-8 원문·해석 — 법무 자문 없이도 본인이 조문 구조 이해 가능한 수준.

### T2-4. **리서치 — 데모·피치 레퍼런스**

- **경로**: `docs/research/demo-pitch-references-radivault.md`
- **소요**: **15분** (§2 경쟁사 연출 패턴, §8 Anti-patterns 집중 시 10분)
- **목적**: 미팅에서 본 "Segmed/Gradient/Truveta/Rhino/Flywheel" 비교의 원문 근거 + 금기 23건.
- **우선 확인 포인트**:
  1. §2 5개 경쟁사 공개 자료 기반 연출 패턴 — 로고 월, 48시간 SLA, De-ID 네이밍 등 업계 관행.
  2. §5.4 "한국 병원 경영진의 불편한 질문 5건" — 본인 병원에서 IRB·CISO가 던질 실제 질문 매핑.
  3. §8 Anti-patterns 23건 — 특히 §8.4 "법률·규제 리스크 발언 주의" — 공개 발표 시 자기 검열 기준.

### T2-5. **병원 경영진용 제안서 요약 (KR)**

- **경로**: `docs/marketing/proposal-summary-hospital-ko.md`
- **소요**: **10분**
- **목적**: 귀원을 **실제 파일럿 병원으로 가정**했을 때 받는 제안 조건 전체. 병원 내부 의사결정자 (전산실장·CISO·영상의학과장) 에게 포워딩 가능한 문서.
- **우선 확인 포인트**:
  1. §4 귀원이 얻는 것 — 수익 공유, 데이터 주권, 기술 부담 제로, 레퍼런스.
  2. §5 귀원이 해줘야 할 것 — Gateway 서버 제공, DICOMweb 연동, 담당자 지정 — 실제 부담 수준 가늠.
  3. §7 파일럿 조건 (6개월, MG ₩500~1,000만 범위, 30~45% 배분) — 본인 병원 volume 기준 재계산.
  4. §8 FAQ 5건 — "법적 리스크", "환자 동의", "수익 지급", "해지", "책임 소재" — 이사회 보고 시 예상 질문 커버리지.

### T2-6. **구매자용 1-Pager (EN)**

- **경로**: `docs/marketing/one-pager-buyer-global-en.md`
- **소요**: **5분**
- **목적**: "RadiVault가 글로벌 AI 구매자에게 어떻게 어필하는가" 본인 눈으로 확인. 투자자 모자로 "이 회사가 실제로 미국 AI 회사에 팔 수 있는 언어로 말하는가" 검증.
- **우선 확인 포인트**:
  1. §5 차별화 표 — Segmed/Gradient 대비 "Korean specialist" 포지셔닝.
  2. §6 컴플라이언스 자세 — "aligned with HIPAA Safe Harbor" 언어 일관성 (단정 금지 원칙).
  3. §9 CTA — 실제 buyer intro call 어떻게 트리거되는가.

### Tier 2 요약

기술·법률·시장 주장이 **원문 근거를 가진 claim**인지, 아니면 **슬라이드용 과장**인지 판별 가능. 본인 법무·기술 자문위원에게 공유 가능한 단계.

---

## §3 Tier 3 — 반나절 Due Diligence (투자·파일럿 결정 직전)

**목표**: 실제 투자 체결 / MOU 체결 직전에, "코드·테스트·QA 로그가 실제로 존재하는가" 까지 전부 확인.

### T3-1. **개발지시서 5건 (dev-spec)**

- **경로**: `docs/specs/dev-spec-*.md` (5 파일)
  - `dev-spec-gateway-agent.md`
  - `dev-spec-central-ingest.md`
  - `dev-spec-metadata-index.md`
  - `dev-spec-de-id-pixel.md`
  - `dev-spec-order-fulfillment.md`
- **소요**: **각 20~40분, 전체 2~3시간** (FR 테이블·DB 스키마·API 계약 중심 읽으면 각 15분)
- **목적**: "5 컴포넌트 shipped" 주장의 실제 설계 명세. 외부 CTO 자문위원이 기술 실사할 때 읽는 자료.
- **우선 확인 포인트**:
  1. 각 dev-spec의 Functional Requirements 표 — 어떤 기능이 FR로 정의되어 있고 어떤 것이 backlog인가.
  2. DB 스키마 ER 다이어그램 — 실제 운영에 사용될 table·column.
  3. API 계약 OpenAPI 스펙 — 구매자·병원에 노출되는 엔드포인트.

### T3-2. **디자인 명세 5건 (design-spec)**

- **경로**: `docs/specs/design-spec-*.md`
- **소요**: **각 15~30분, 전체 1~2시간** (스크린 와이어프레임·디자인 토큰 중심 읽으면 각 10분)
- **목적**: UI/UX가 어떤 디자인 결정 근거로 이뤄졌는가. 특히 `design-spec-buyer-portal-demo.md` 는 데모에서 본 Buyer Portal + Hospital Dashboard의 모든 화면 설계.
- **우선 확인 포인트**:
  1. 디자인 토큰 (Buyer blue `#1D4ED8` / Hospital teal `#0F766E`) — 브랜드 일관성.
  2. 6-tile Hospital Dashboard 구조 — 실제 이사장 시점에서 1-scroll 작동.
  3. 접근성 (WCAG AA) 준수 표시 — 대외 공개 시 법적 방어.

### T3-3. **QA 리포트 5건**

- **경로**: `docs/qa/qa-report-*.md`
  - `qa-report-gateway-agent.md`
  - `qa-report-central-ingest.md`
  - `qa-report-metadata-index.md`
  - `qa-report-de-id-pixel.md`
  - `qa-report-order-fulfillment.md`
- **소요**: **각 10~15분, 전체 약 1시간**
- **목적**: **"407 tests pass" 주장의 증거**. 각 feature가 외부 검수자의 수용 기준 대조에서 PASS 받은 기록.
- **우선 확인 포인트**:
  1. 각 리포트의 요약 판정 (PASS / PASS with minor / FAIL) — RadiVault는 전부 PASS 또는 PASS with minor.
  2. 보안 리뷰 섹션 — 실제 발견된 이슈·해결 기록. 투명성 지표.
  3. 수용 기준 매트릭스 — dev-spec의 FR과 테스트 결과 1:1 대조.

### T3-4. **데모 스크립트 v0.2 (17분 본 데모 전체 대사)**

- **경로**: `docs/specs/demo-script-radivault.md`
- **소요**: **30분** (장면 1~7 + Q&A 20건)
- **목적**: 미팅에서 본 17분 데모의 원문 대사·연출·실패 런북 전체. 대표님이 직접 "연출 품질" 을 복기할 수 있는 자료.
- **우선 확인 포인트**:
  1. §2 장면 1~7 — 각 장면 프레젠터 대사 + 연출 (pause, eye contact, 손동작) 세부.
  2. §5 FAQ 20건 상세 답변 — 본인이 묻고 싶은 질문이 이미 답변되어 있는가 확인.
  3. §3 실패 런북 R-1~R-5 — 네트워크 다운·PHI 노출 등 극한 상황 대응 설계.

### T3-5. **구현 개발지시서 — Buyer Portal + Hospital Dashboard 데모 키트**

- **경로**: `docs/specs/dev-spec-buyer-portal-demo.md`, `docs/specs/design-spec-buyer-portal-demo.md`
- **소요**: **각 30분** (총 1시간)
- **목적**: 데모에서 본 두 포털 실물의 설계·구현 근거 명세. "Demo kit" 전체 구조.
- **우선 확인 포인트**:
  1. dev-spec §9 "데모 운영 요구사항" — Demo Operator Mode, Canned overlay 등 실패 복구 기능.
  2. design-spec §5 "화면 A-1~A-8, B-1~B-6" — 데모에서 본 모든 화면의 와이어프레임.
  3. §15 "리허설 가이드" — 미팅 전 준비 체크리스트.

### T3-6. **개별 리서치 문서 (기술 foundations)**

- **경로**:
  - `docs/research/gateway-agent-technical-foundations.md`
  - `docs/research/central-ingest-technical-foundations.md`
  - `docs/research/metadata-index-technical-foundations.md`
  - `docs/research/de-id-pixel-technical-foundations.md`
  - `docs/research/order-fulfillment-technical-foundations.md`
- **소요**: **각 20~30분, 전체 2시간**
- **목적**: 각 컴포넌트가 어떤 업계 best practice · 오픈소스 · 표준 · 규제에 근거해 설계됐는가. 외부 기술 자문위원이 읽는 자료.
- **우선 확인 포인트**:
  1. de-id-pixel foundations — DICOM PS3.15 Annex E, pydeface, Tesseract OCR 등 참조 기술 목록. 법적 방어력.
  2. central-ingest foundations — WORM 저장·audit chain·outbox 패턴 등 금융급 감사 설계 근거.
  3. gateway-agent foundations — outbound-only 아키텍처·mTLS 구성의 보안 근거.

### T3-7. **마케팅 문서 기존 자산 (컴플라이언스 언어 검증)**

- **경로**:
  - `docs/marketing/one-pager-buyer-global-en.md` (108줄)
  - `docs/marketing/proposal-summary-hospital-ko.md` (261줄)
  - `docs/marketing/order-fulfillment-one-pager-buyer-en.md` (141줄)
  - `docs/marketing/compliance-upgrade-buyer-en.md` (184줄)
  - `docs/marketing/changelog-v02-pixel-deid-ko.md` (336줄)
- **소요**: **각 5~15분, 전체 1시간**
- **목적**: "RadiVault가 대외 공개할 때 일관된 컴플라이언스 언어를 유지하는가" 전수 확인. 특히 `compliance-upgrade-buyer-en.md` 는 인증·규제 언어의 표준.
- **우선 확인 포인트**:
  1. "SOC 2", "ISO 27001", "HIPAA compliant" 단정 표현이 **어디에도 없는지**.
  2. 가격·revenue share 숫자의 공개 수준 일관성.
  3. 경쟁사 비교 표현의 어조 (비방 없음 원칙).

### Tier 3 요약

**투자 체결 / MOU 서명 직전 due diligence 완료**. 법무·기술 자문위원까지 자료 공유 후 최종 판단.

---

## §4 독서 경로 요약표

| 티어 | 자료 수 | 누적 시간 | 목적 | 결과물 |
|---|---|---|---|---|
| **Tier 1 (15분)** | 3건 (1-pager KR/EN + 피치덱) | 15분 | 투자 Go/No-go 예비 + 파일럿 관심 확정 | 후속 미팅 요청 메일 가능 |
| **Tier 2 (1시간)** | +6건 (PRD, ARCHITECTURE, 리서치 2, 병원 제안서, 구매자 1-pager) | 1시간 15분 | 기술·법률·시장 주장 근거 검증 | 법무·기술 자문위원에 포워딩 가능 |
| **Tier 3 (반나절)** | +전체 dev-spec 5, design-spec 5, QA 5, 데모 스크립트, 데모 키트, 기술 foundations 5, 마케팅 자산 5 | 약 6~8시간 | 투자 체결 / MOU 서명 직전 due diligence | 최종 결정 |

---

## §5 대표님께 드리는 추천 경로

### 시나리오 A — "투자 먼저 판단하시는 경우" (Tier 1 → §1 peek of Tier 2)

1. T1-1 (1-pager KR) — 5분
2. T1-3 (피치덱) — 10분, 특히 §6 Numbers + §7 Ask
3. T2-3 (K-MedData 리서치) — 시장 근거 15분
4. T2-4 (Demo-pitch 리서치 §2 경쟁사 패턴만) — 10분

**총 40분**. 시드 투자 의사결정 예비 판단 가능.

### 시나리오 B — "병원 파일럿 먼저 판단하시는 경우" (Tier 1 → T2-5 집중)

1. T1-1 (1-pager KR) — 5분
2. T2-5 (병원 제안서) — 10분 (§4 귀원이 얻는 것, §7 파일럿 조건 중심)
3. T1-3 (피치덱 §5 Compliance + §3 Hospital Flow) — 10분
4. T2-4 (Demo-pitch 리서치 §5 한국 병원 경영진 proof points) — 10분

**총 35분**. 병원 내부 (CISO·영상의학과장) 와 1차 논의 시작 가능.

### 시나리오 C — "두 판단을 같이 하시는 경우" (Braided, 권장)

Tier 1 전체 (15분) → T2-5 (병원) + T2-3 (시장) (25분) → T1-3 피치덱 §7 Ask 슬라이드 S13~S14 재독 (5분) = **총 45분**.

"하나의 서명에 두 결정" — 미팅 톤을 그대로 독서에 유지.

### 시나리오 D — "일단 기술 자문위원에게 먼저 공유" (Tier 2 외부 forward)

1. 본인: T1-1 (5분) — 핵심 메시지만 확인.
2. 외부 CTO: T2-1 (PRD) + T2-2 (ARCHITECTURE) + T3-1 (dev-spec 5건) 포워드 — 외부 3시간 리뷰.
3. 외부 법무: T2-3 + T2-4 + T2-5 + 1-pager 컴플라이언스 footnote 포워드 — 외부 2시간 리뷰.

자문 결과 회수 후 Tier 2 본인 직독.

---

## §6 미팅 종료 직후 즉시 전달 이메일 템플릿

미팅 끝나고 Kyle이 본 문서 + 관련 자료를 대표님께 보낼 때 쓸 메일 초안. (demo-script §6.2 한국어 템플릿과 연동.)

```
제목: [RadiVault 데모] follow-up 자료 — [미팅 날짜]

[대표님 존함]께,

오늘 [시간] 귀중한 시간 내주셔서 감사합니다.

17분 데모에서 다룬 내용을 혼자 재확인하실 수 있도록,
"15분 → 1시간 → 반나절" 3단계 독서 경로로 정리해
아래 큐레이션 문서에 묶어두었습니다.

▶ 시작 지점: docs/marketing/leave-behind-curation-kr.md
  - §1 Tier 1 (15분) — 핵심만 보시려면 여기만.
  - §5 "시나리오 C" — 대표님 두 모자 모두에 맞춘 45분 경로.

3가지 추천 다음 단계:
  1. 기술 딥다이브 — 90분, CISO·전산실장 배석
  2. 법무 Opinion walkthrough — 자문 요약 + MSA 초안 리뷰
  3. 파일럿 MOU 1차 초안 — 이메일로 72시간 내 전달

각 단계는 독립적으로 진행 가능하며, 순서도 유연합니다.

이번 주 내 회신 가능하신 시간대 2~3 옵션 주시면
조율드리겠습니다.

감사합니다.

Kyle Jeon
Founder / CEO, RadiVault
kylejeon83@gmail.com

[첨부]
- 피치덱 PDF (redacted version)
- 통합 1-pager KR + EN
- 데모 녹화 MP4 (Google Drive, 72h 만료)
- MSA 초안 v0.1 (법무 자문 진행 중 표기)
```

---

## §7 문서 간 교차참조 지도

본 큐레이션의 자료들이 서로 어떻게 연결되는가:

```
                    [Tier 1: 3분]
                         │
                    1-pager KR ─── 1-pager EN
                         │
                         ▼
                   피치덱 KR (16 slides)
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    [Tier 2: 1시간]
      PRD           ARCHITECTURE    리서치 2종
       │                │               │
       └────────┬───────┴───────┬───────┘
                │               │
                ▼               ▼
         병원 제안서 (KR)    구매자 1-pager (EN)
                │
                ▼
          [Tier 3: 반나절]
                │
       ┌────────┼────────┬────────┬────────┐
       ▼        ▼        ▼        ▼        ▼
    dev-spec  design-   QA      데모      기술
     5건       spec 5   리포트  스크립트   foundations
              (demo-   5건      v0.2      5건
              kit 포함)
```

---

## §8 법률 검토 flag (본 큐레이션 전용)

기존 마케팅 문서 flag 승계 + 본 문서 전용 추가:

1. **경쟁사 비교 표현** (T1-3 피치덱 S5, T2-4 리서치 §2) — 공정거래위원회 표시광고법 준수.
2. **PIPA §28-8 + "3% 벌금" 수치** (T1-1/T1-2 1-pager, T1-3 피치덱 S8) — 법무 재확인 필수.
3. **"파일럿 병원 in discussions"** (전 문서) — 허위 표시 방지 기준.
4. **가격·revenue share·MG 수치** (1-pager, 피치덱, 병원 제안서) — 공개 수준 일관성.
5. **Leave-behind 자체 배포 범위** (본 문서) — 외부 유출 시 구매자·병원 측 반응 우려. 본 문서 footer에 "For recipient's eyes only" 표기 고려.
6. **MSA 초안 첨부 여부** — 법무 자문 완료 전 배포 시 법적 구속력 암시 리스크. 표기 필수: "법무 자문 진행 중 · 법적 구속력 없음".

---

## §9 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|---|---|---|---|
| 0.1 | 2026-04-24 | @marketer | 최초 드래프트. 3-tier 독서 경로 (15분 → 1시간 → 반나절), Tier 1 3건 + Tier 2 6건 + Tier 3 7건 = 총 16+ 자료 큐레이션. 시나리오 A~D 독서 경로 4종, 이메일 템플릿, 교차참조 지도, 법률 검토 flag 6건. |

---

### NEXT_STEP (본 파일)

- 완료 산출물: `docs/marketing/leave-behind-curation-kr.md`
- **Kyle 리뷰 필요 사항**:
  1. Tier 1~3 분류에서 **누락된 자료 / 과다 포함된 자료** 확인.
  2. §6 이메일 템플릿 — 본인 발화 스타일로 수정 (demo-script §6.2 한국어 템플릿과 비교).
  3. §8 flag 5·6 — Leave-behind 자체 배포 범위·MSA 초안 첨부 여부 결정.
  4. 시드 `[X]M` / `Q[?]` placeholder 확정 후 전 문서 일괄 치환.
  5. PDF export 목록 — 어떤 문서를 PDF화해서 미팅 당일 실물로 전달할지.
- **@designer 2차 세션** (선택):
  - 본 큐레이션의 교차참조 지도 (§7) 를 시각 다이어그램으로 변환.
  - 3-tier 시간 배지 (15분 / 1시간 / 반나절) 를 문서 각 섹션에 추가 삽입.
- 제안 다음 단계:
  - (즉시) Kyle 검토 + placeholder 확정.
  - (미팅 D-1) PDF export 자료 패키지 제작 (Google Drive 공유 링크 72h).
  - (미팅 D-0) 이메일 템플릿 (§6) 에 실제 자료 링크 삽입 후 대기.
  - (미팅 종료 직후) Kyle이 본 이메일 전송.
