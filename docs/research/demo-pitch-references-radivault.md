# 데모·피치 레퍼런스 리서치 — RadiVault (투자자 + 병원 경영진 하이브리드 청중)

> **Status**: Draft v0.1 · **작성일**: 2026-04-24 · **작성자**: @researcher
> **근거 요청**: 메인 세션 — "투자자이면서 병원 경영진을 겸하는 대표님 한 분에게 15~20분 데모로 '제품이 돌아가고, 돈이 되고, 안전하다'를 증명하고 싶다"
> **선행 문서**:
> - `docs/research/k-meddata-research-summary.md` (시장·경쟁·규제 베이스)
> - `docs/research/{gateway-agent,central-ingest,metadata-index,de-id-pixel,order-fulfillment}-technical-foundations.md` (기술 기반)
> - `docs/prd.md`, `docs/ARCHITECTURE.md`
> - `docs/marketing/*` (현재까지 제작된 buyer/hospital 콘텐츠 자산)
> - `progress.txt` §Session 3–8 (v0.1 MVP 5-feature 구현 경과)
>
> **중복 회피**: 시장 TAM·경쟁 지형·PIPA 조문 해석·de-ID 기술 깊이는 전부 위 선행 문서에 기재되어 있다. 본 문서는 **데모 연출·피치 스토리텔링·장면 순서·청중 설득 실행** 측면만 다룬다. 필요한 경우 선행 문서 참조 포인터만 남긴다.

---

## §1 Scope and out-of-scope

### 1.1 In-scope

- 15~20분 1회 미팅에 맞춘 라이브/녹화 데모 플레이북.
- **청중 1인 = 투자자 + 병원 경영진** (한 사람이 두 역할 겸임) 전제의 피치 구조.
- 현재 v0.1 MVP의 실행 가능한 표면(CLI, API, 로그, 감사 해시체인, Prometheus 메트릭)을 "시각적 자산"으로 포장하는 전략.
- 한국 병원 경영진 특유의 감수성(PIPA CEO 개인책임, IRB, 국외이전) 대응.
- 데모 중 실패·장애 복구 프로토콜.
- Segmed, Gradient Health, Truveta, Rhino Health, Flywheel 공개 자료에서 추출 가능한 연출 패턴.

### 1.2 Out-of-scope (다른 문서로 위임)

- 기술 스택 선택, 구현 우선순위 → `@planner`
- Buyer Portal Web UI 전체 디자인 토큰/컴포넌트 → `@designer`
- 실제 피치덱 PPT 파일 제작 → `@marketer`
- 법률 자문 결론 → 외부 변호사 (본 문서는 법적 결론을 내리지 않음)
- RadiVault v0.2+ 로드맵 확정 → `@planner` + Kyle

### 1.3 방법론 선언

본 문서의 근거는 3종으로 구분:

1. **1차 자료**: Segmed/Gradient Health/Truveta/Rhino Health/Flywheel 공식 공지·블로그·보도자료, 한국 개인정보보호법 조문, Kim & Chang FAQ, RSNA 공식 안내.
2. **2차 자료**: Fierce Healthcare, Radiology Business, VentureBeat, IAPP, IClG 등 업계·법률 매체.
3. **3차 자료/실무 가이드**: Y Combinator 공개 라이브러리, Forum VC, Pitch Deck Fire, Gong, Demio 등 피치·데모 실무 콘텐츠.

수치·주장은 출처 URL을 각 섹션 또는 §8 종합 출처 목록에 명시했다. 한국 병원 내부 의사결정 구조는 공개 자료가 제한적이므로 "추정" 또는 "실무 통념" 라벨을 달았다. 대표님이 보유한 내부 지식이 있다면 §9 오픈 퀘스천에서 확인을 요청한다.

**법적 주의**: 본 문서에 등장하는 법령 해석 문구는 법률 자문이 아니다. 실제 데모 멘트·계약 문구 확정 전에는 반드시 변호사 검토가 필요하다. §9 Q-법무-1 참조.

---

## §2 Comparable company demo/pitch patterns

경쟁사가 공개한 자료에서 역산할 수 있는 연출 패턴을 추출한다. 피치덱 원본은 대부분 비공개지만, 프레스 릴리스·보도자료·제품 페이지·RSNA 발표에서 어떤 장면을 "외부에 보여주기로 결정했는지"는 관찰 가능하다. 이는 곧 그들이 투자자·고객 앞에서 반복 재생하는 레퍼토리다.

### 2.1 Segmed (Stanford·Palo Alto, Series A $10.4M, 2024-09)

**관찰 가능한 연출 축**:

| 축 | 공개 근거 | RadiVault 시사점 |
|----|----------|----------------|
| "67개 병원 네트워크 Advocate Health가 **동시에 투자자**" | [PR Newswire](https://www.prnewswire.com/news-releases/segmed-secures-10-4-million-series-a-funding-led-by-igan-partners-and-advocate-health-302236032.html), [Radiology Business](https://radiologybusiness.com/topics/artificial-intelligence/segmed-startup-gathers-medical-imaging-data-ai-development-raises-10m) | 공급자=주주 동맹 구조가 "병원 경영진이 투자 근거를 납득하는 최단거리"다. 대표님 미팅의 본질도 이와 동일. |
| 자체 de-ID 툴 "Incognito" 브랜딩 | [Segmed.ai news](https://www.segmed.ai/news/segmed-secures-10-4-million-series-a-funding) | 파이프라인의 가장 위험한 단계(PHI 제거)에 **고유명사**를 부여해 기술적 해자 인상을 심는다. RadiVault의 "Gateway Agent + De-ID Pixel v0.2"도 브랜딩 대상. |
| "regulatory-grade de-identification and tokenization" 문구 | Segmed 공식 소개문 | "certified"라고 말하지 않고 "regulatory-grade"라는 **가드레일 언어** 사용. 법적 리스크 최소화하면서 감각적 신뢰를 전달. |
| Y Combinator 트랙 레코드 | Crunchbase | 초기 데모는 YC Demo Day 스타일(10~12슬라이드, 슬라이드당 1 아이디어)로 시작된 흔적. |

**RadiVault에 복제 가능한 패턴**:
- **장면 A**: 병원 네트워크 슬라이드 1장 + "공급자 동맹" 내러티브 — 대표님이 2번째 파일럿 병원에 접근할 수 있는 루트가 있는지를 데모 중 자연스럽게 질문화.
- **장면 B**: De-ID를 **명사화**한 1장 다이어그램 — "PHI in → De-ID Pixel v0.2 → Anonymized out" 단일 흐름.

### 2.2 Gradient Health (Durham NC, Seed $2.75M 공식, Atlas 2 제품)

**관찰 가능한 연출 축**:

| 축 | 공개 근거 | RadiVault 시사점 |
|----|----------|----------------|
| "48시간 이내 전달" SLA 명시 | [ITN Online](https://www.itnonline.com/content/gradient-health-releases-upgrade-self-service-medical-imaging-data-platform), [Gradient Health 공식](https://gradienthealth.io/gradient-health-launches-atlas-2-setting-a-new-standard-for-medical-imaging-data-access/) | 구매자 설득의 핵심은 속도. RadiVault PRD §5의 "p95 <48h" 목표와 동일. 데모 중 타이머 연출 가능. |
| "20M 스터디 즉시 접근 + 30M 계약 중" | 동일 | 숫자는 **현재 접근 가능**과 **파이프라인 중**을 분리해서 제시. RadiVault도 "Gateway 배치 중 병원 N곳 / 계약 논의 M곳"으로 이원화 권장. |
| **"free 7-day trial"** RSNA 2025 프로모션 | Gradient Health RSNA 페이지 | 구매자 B2B에서 트라이얼 허들을 낮춤. RadiVault v0.2에서도 "Sample cohort free download" 실험 후보. |
| Python SDK + REST API + Google Cloud Marketplace | 동일 | 개발자 접근성을 **카탈로그 등재**로 증명. Segmed보다 개발자 지향 정체성. |
| Atlas 2 데모는 RSNA 부스에서 **every-day live session** | 동일 | 녹화가 아닌 **반복 가능한 라이브 시나리오**를 갖춰두고 실수 없이 연주한다. |

**RadiVault에 복제 가능한 패턴**:
- **장면 C**: "검색 → 클릭 → CSV 다운로드" 20초 시연 — 현재 `curl` + `search-admin` + `fulfillment-admin` CLI로 가능하나, 시각적으론 약함. §7의 스토리보드에서 변형 제시.
- 데모의 핵심은 "API-only임에도 **한 화면에서** end-to-end가 보인다"는 인상.

### 2.3 Truveta (Bellevue WA, Series C $320M, 2025-01, valuation $1B+)

**관찰 가능한 연출 축**:

| 축 | 공개 근거 | RadiVault 시사점 |
|----|----------|----------------|
| 17개 health system이 **창립 파트너 + 투자자** | [Fierce Healthcare](https://www.fiercehealthcare.com/tech/health-systems-backed-truveta-closes-95m-to-fund-its-data-analysis-platform), [Crunchbase](https://www.crunchbase.com/organization/truveta) | Segmed보다 더 극단적인 "consortium-owned" 구조. 대표님 미팅의 무게가 "첫 consortium 멤버 후보"라는 프레임으로 재구성 가능. |
| 1.2억 환자 데이터, cardiovascular·neurology·oncology 중심 | Truveta 공식 | 도메인 특화 슬로건(RadiVault는 "spine·imaging specialty") 가능. Kyle의 척추 배경과 연결. |
| Regeneron·Illumina 전략 투자 | [Fierce Healthcare](https://www.fiercehealthcare.com/tech/health-systems-backed-truveta-closes-95m-to-fund-its-data-analysis-platform) | 제약/바이오가 공급자가 아닌 **구매자**로 전략투자. RadiVault는 한국 제약사(Lunit·VUNO 포함 AI 기업군) 타깃 가능성. |

**RadiVault에 복제 가능한 패턴**:
- **장면 D**: "병원 consortium 초대" 프레임 — 대표님 병원을 **첫 번째 창립 멤버**로 포지셔닝. 투자 + 데이터 공급 + 이사회 옵션을 하나로 묶는다 (법무 검토 필요).

### 2.4 Rhino Health / Rhino Federated Computing (Boston·Tel Aviv, Seed $5M 공식)

**관찰 가능한 연출 축**:

| 축 | 공개 근거 | RadiVault 시사점 |
|----|----------|----------------|
| "데이터는 병원을 떠나지 않는다" 핵심 메시지 | [VentureBeat](https://venturebeat.com/business/rhino-health-emerges-from-stealth-to-bring-hospital-data-to-federated-learning/), [Rhino FCP](https://www.rhinofcp.com/) | Federated Learning이 "국외이전 없음"의 최대 무기. RadiVault의 Hybrid Model 3 (Zone 1 on-prem + Zone 2 익명 메타만)도 동일 메시지의 완화판. |
| ACR·AstraZeneca 파트너십 | [GlobeNewswire](https://www.globenewswire.com/en/news-release/2022/05/05/2436894/0/en/Rhino-Health-Platform-Powers-Hospital-Based-Federated-Learning-Consortium.html) | 학회·제약사 브랜드를 우산으로 활용. RadiVault는 v0.2에서 대한영상의학회·대한의료정보학회 자문위원 확보 고려. |
| 60+ 기관, Newsweek Best Smart Hospitals 14/20 | Rhino FCP 공식 | "권위 병원 로고 벽"이 투자자·병원 양쪽에 동시 작동. 대표님 병원이 초기에 합류하면 이 벽의 **왼쪽 끝 로고**가 된다는 게 오퍼. |

**RadiVault에 복제 가능한 패턴**:
- **장면 E**: "영상 원본은 병원 전산망을 떠나지 않는다 — 떠나는 것은 완전 익명화된 파생 데이터 뿐" — 아키텍처 슬라이드 1장에서 Zone 1/2/3 경계를 **빨간 점선 = 병원 네트워크 경계**로 강조.

### 2.5 Flywheel.io (Medical imaging data management SaaS)

**관찰 가능한 연출 축**:

| 축 | 공개 근거 | RadiVault 시사점 |
|----|----------|----------------|
| RSNA 매년 **viewer 업데이트 공개** | [Flywheel.io RSNA viewer](https://flywheel.io/insights/articles-research-data-management/flywheel-unveils-new-viewer-updates-at-rsna), [Flywheel SaaS announcement](https://flywheel.io/insights/blog/flywheel-unveils-saas-platform-for-advancing-medical-imaging-ai-at-scale) | DICOM viewer가 **데모의 스타**. 구매자 WOW 포인트. RadiVault는 OHIF/Cornerstone 통합이 Phase 2이므로, v0.1 데모에선 **thumbnail grid**로 대체 필요. |
| volumetric segmentation, 3D rendering, PET fusion, RTStruct | 동일 | 고급 시각화는 구매자 데모에서 강력. RadiVault는 **현재 없음** — 솔직히 로드맵으로 돌리는 것이 정직하다. |
| SaaS 포지셔닝 전환 (온프렘 → SaaS, 2023-11) | [Flywheel.io SaaS 공지](https://flywheel.io/2023/11/21/flywheel-saas/) | RadiVault의 Hybrid Model 3은 "on-prem + SaaS 중간형"으로 **차별화 문구**로 포장 가능. |

**RadiVault에 복제 가능한 패턴**:
- **장면 F (선택)**: Cornerstone.js 기반 **정적 DICOM 썸네일 grid + 1개 study 열람** 프리뷰를 v0.2 모크업으로 제작해 "로드맵" 슬라이드 안에 삽입. 거짓말 아님.

### 2.6 공통 패턴 종합 — 5개사 반복 연출

| 패턴 | 5사 중 사용 | RadiVault v0.1 데모 복제 여부 |
|------|-----------|---------------------------|
| 병원 로고 월(벽) | Segmed, Truveta, Rhino | v0.1에선 **로고 미확보** → "partnership in progress" 플레이스홀더로 대체 (§8의 금기 §1과 주의 교차) |
| 네트워크/플로우 다이어그램 1장 | 전원 | **RadiVault 핵심 자산**. Zone 1/2/3 + 3 플로우 명확 (docs/ARCHITECTURE.md §2 기반) |
| "48시간 SLA" 또는 그 변형 | Gradient, Segmed | v0.1 설계값 <48h. 실제 측정치는 미확보 → 데모에서는 "설계 목표"로 명시 |
| 규제/컴플라이언스 우산(HIPAA/SOC 2/ISO) | Segmed | RadiVault는 "in preparation" 뿐. **단정 금지** (§8 금기 §2) |
| 환자 프라이버시 내러티브 | Rhino, Truveta | "데이터는 병원을 떠나지 않는다" 변형이 가장 효과적 |
| 숫자 2단 제시(현재 / 파이프라인) | Gradient | RadiVault: "배치 진행 1곳 / 논의 N곳 / 대기 M곳" (정직하게 작은 숫자 허용) |
| 자체 툴 네이밍 | Segmed "Incognito", Gradient "Atlas" | RadiVault: 이미 "Gateway Agent · De-ID Pixel · Central Ingest · Metadata Index · Order Fulfillment" 5개 코드네임 보유. **외부용 단일 브랜드 통합** 고려 (§9 Q-브랜드-1) |

---

## §3 Dual-audience structure templates

### 3.1 문제 정의 — 왜 dual-audience가 어려운가

> "Rather than using the same presentation for both audiences, you might have different versions of your deck, or at least plug and play slides that you can use for different audience groups."
> — [Pitch Deck Fire, Beyond the Investor Presentation](https://pitchdeckfire.com/resources/beyond-the-investor-presentation-different-pitch-deck-audiences/)

업계 실무 가이드는 **"덱을 분리하라"**를 강력 권고한다. 하지만 RadiVault의 상황은 **청중 1인이 두 역할을 겸임**하는 특수 케이스. 분리 불가능.

투자자 뇌와 경영진 뇌는 **같은 사실에서 다른 질문**을 한다:

| 장면 | 투자자 뇌가 묻는 것 | 병원 경영진 뇌가 묻는 것 |
|------|------------------|--------------------|
| 아키텍처 1장 | "이게 해자(moat)냐?" | "우리 전산망 침투 범위가 뭐냐?" |
| De-ID 데모 | "PHI 누출 시 플랫폼 리스크는?" | "**내 환자** 데이터 어떻게 보호되냐? CEO 처벌?" |
| 주문 플로우 | "매출 루프 완결?" | "우리 병원 수익 정산은 어떻게 되냐?" |
| 숫자 | "TAM × take-rate × 파트너 수?" | "내 병원 월 ₩얼마?" |
| 경쟁 | "왜 Segmed·Gradient보다 나은가?" | "이 플랫폼이 망하면 내 계약 어떻게 되냐?" |

**같은 슬라이드가 두 질문에 동시에 답해야 한다.**

### 3.2 Dual-audience 구조 3가지 템플릿

#### 3.2-A. **Braided(땋기) 구조** — 매 장면마다 두 관점 병치 (권장 1안)

각 슬라이드/장면에서 상단은 투자자 앵글, 하단은 병원 앵글을 **한 프레임 안에** 제시. 프레젠터는 두 문장을 순차로 말한다:

> "투자자 관점에서 이건 [moat/margin/TAM]입니다. 병원 관점에서 이건 [수익/안전/부담]입니다."

- **장점**: 청중의 뇌가 한 장면에서 둘 다 만족 → 인지 부조화 없음.
- **단점**: 연출 스킬 요구. 15분에 5~7 장면이면 **매 장면 2 문장**만 허용(각 30~40초). 연습 필수.
- **선례**: Truveta 창립 발표문은 "health systems gain research infrastructure, investors gain platform equity"를 한 문장에 병치 ([Healthcare Finance News](https://www.healthcarefinancenews.com/news/leading-health-systems-form-truveta-aggregate-and-sell-anonymized-patient-data)).

#### 3.2-B. **Sandwich(샌드위치) 구조** — 투자자 열기·병원 본론·투자자 닫기

```
[0–3분]  투자자 열기:        시장·해자·숫자 (왜 RadiVault가 "카테고리 스타"가 되는가)
[3–13분] 병원 본론:          데이터 흐름·De-ID·계약 안전·병원 수익 시뮬
[13–18분] 투자자 닫기:        traction·roadmap·ask
[18–20분] Q&A
```

- **장점**: 병원 설득에 **최장 10분** 확보. 대표님이 실제로 "내 병원을 태울 것인가"를 판단할 수 있는 시간이 생김.
- **단점**: 청중이 중간에 빠져나갈 리스크. 투자자 뇌가 10분 간 쉬는 동안 집중 저하.
- **언제**: 대표님이 **병원을 태우는 결정을 먼저, 투자는 병원 합류 이후** 판단하겠다는 시그널이 있을 때.

#### 3.2-C. **Lens-switch(렌즈 전환) 구조** — 프레젠터가 2회 명시적 선언

```
[0–1분]   Hook: 혼합 장면 (both lenses)
[1–8분]   "이제 병원 경영진 관점으로 말씀드리겠습니다" — 안전·수익·부담·철회권
[8–16분]  "이제 투자자 관점으로 전환하겠습니다" — TAM·unit economics·로드맵·ask
[16–18분] 통합: 왜 두 관점이 같은 결론으로 수렴하는가
[18–20분] Q&A
```

- **장점**: 청중이 자기 뇌를 어느 모드로 써야 할지 혼란 없음.
- **단점**: "렌즈 전환" 자체가 어색할 수 있음. 1인 청중일 때 특히 과장처럼 느껴질 위험.

### 3.3 RadiVault 권장 — **Braided + Sandwich 하이브리드**

현재 청중 프로파일(1인, 두 역할, 처음 듣는 상태 가정)을 고려하면:

```
[0–2분]   Hook (Braided):  "한국 의료영상 데이터 → 글로벌 AI. 투자자에겐 카테고리,
                             병원엔 정산 루트." 1문장 2 lens.
[2–5분]   아키텍처 (Braided):  Zone 1/2/3 1장 + 두 관점 병치.
[5–13분]  라이브 데모 (Sandwich, 병원 우선):
              - 병원 Gateway 관점 (4분): 설치 → 스캔 → De-ID → 감사 로그
              - 구매자 관점 (2분): 검색 → 주문 → 다운로드
              - 병원 수익 관점 (2분): 월간 정산 대시보드 목업
[13–17분] 숫자·로드맵 (Braided):  Y1–Y3 매출 & 병원별 수익 시뮬 (같은 슬라이드)
[17–19분] Ask (Lens-switch):   투자자 ask + 병원 ask 각각 명시
[19–20분] Q&A 트리거 질문
```

- **근거**: YC Series A 가이드 권고(15분 피치 내 "문제→해법→증거→질문 끌어내기") ([YC Library: Series A Pitch](https://www.ycombinator.com/library/8d-how-to-build-a-great-series-a-pitch-and-deck)) + 엔터프라이즈 SaaS 15-min 데모 구조 ([Demio blog](https://www.demio.com/blog/compelling-product-demo-script), [Contrast Learn](https://www.getcontrast.io/learn/product-demo-script))를 RadiVault 특수성에 맞게 조정.

---

## §4 Live vs recorded decision framework

### 4.1 업계 통념

B2B SaaS 시드~시리즈A 데모는 **라이브 선호**가 주류:
- "Include visuals, a short demo, or screenshots to make your solution tangible" ([Forum VC Pitch Deck Guide](https://www.forumvc.com/thought-pieces/the-essential-guide-to-creating-a-compelling-b2b-saas-pitch-deck-for-pre-seed-and-seed-stage-founders))
- "Pre-recorded or self-serve demos should stay under 15 minutes" ([Contrast Learn](https://www.getcontrast.io/learn/product-demo-script)) — 즉 녹화는 자기주도 열람용.

의료·규제 산업 특유의 감수성: **라이브 실패가 치명적**. PHI 화면에 번쩍이면 한 번에 신뢰 소멸. Tonic.ai 업계 가이드는 "test/demo 환경에서 PHI 누출 방지를 수동 검사에 의존하지 말 것"을 경고 ([Tonic.ai Healthcare Solutions](https://www.tonic.ai/solutions/industry/healthcare)).

### 4.2 결정 매트릭스 — RadiVault v0.1 맥락

| 축 | Live | Recorded video | Interactive guided (Storylane/Walnut 스타일) |
|----|------|--------------|------------------------------------------|
| WOW factor | 높음 | 중간 | 중간 (클릭감) |
| 실패 리스크 | **높음** (CLI 오타, 네트워크, Docker not ready) | 없음 | 낮음 |
| 맞춤 질의 대응 | 가능 | 불가 | 부분 |
| 준비 비용 | 리허설 2일+ | 편집 3~5일 | 툴 학습 + 구성 3일 |
| 대표님이 "이게 진짜냐?" 의심할 여지 | 낮음 (실시간이 신뢰) | 중간 (편집 가능성) | 중간 |
| PHI 누출 리스크 | **있음** (합성 데이터여도 실수 시 의심) | 사전 검수로 0 | 사전 검수로 0 |

### 4.3 RadiVault 권장 — **Hybrid Live + Pre-rendered Canned Output**

구조:

1. **라이브 셸**: 터미널·브라우저·1 슬라이드 덱을 실시간 조작. 대표님이 **실시간임을 인지**하도록 화면 상단에 시계/날짜/호스트명 노출.
2. **Canned output**: 각 명령의 출력은 **사전에 실제로 실행해둔 재현 가능 로그**. 즉, 실패해도 미리 준비한 "정상 출력" 터미널 탭으로 즉시 전환.
3. **백업 녹화**: 네트워크 완전 차단·Docker 다운 상황 대비, 전체 데모를 MP4로 **사전 녹화** 하여 즉시 재생 가능한 상태로 보관 (PC 로컬, USB, 클라우드 3곳).

**근거**: 3-2-1 backup 원칙(데이터 백업이지만 원리 동일: 3 copies, 2 media, 1 offsite) ([Acronis 3-2-1 Backup](https://www.acronis.com/en/blog/posts/backup-rule/))을 **데모 자산 자체**에 적용.

### 4.4 실패 시나리오 런북 (데모 중 실시간 대응)

| 증상 | 첫 5초 액션 | 복구 | 멘트 예시 |
|------|-----------|-----|---------|
| 명령 hang (>3초) | Ctrl-C, "로컬 데모 캐시로 전환하겠습니다" | 두 번째 터미널 탭의 사전 실행 로그 표시 | "실제 운영 환경에선 이 단계가 ~초 소요됩니다. 사전 측정 결과를 보여드리죠." |
| 에러 raw 노출 | 터미널 즉시 clear | 녹화본 해당 장면으로 점프 | "이 데모 환경의 일시적 이슈입니다. 프로덕션 런북은 RB-XX에 정리되어 있습니다." |
| 네트워크 다운 | 노트북 로컬 데모로 스위치 | Docker-compose up 사전 기동 필수 | — |
| **PHI 의심 화면** (합성 데이터 중 실제처럼 보이는 정보) | **즉시 Cmd-W / 화면 공유 중단** | 사전 검수된 다른 스크린샷으로 설명 | "이건 Orthanc 공개 테스트 데이터입니다. 실 PHI는 이 환경에 없습니다. 데이터셋 출처는 공개 리포지토리 X입니다." |

**골든 룰**: 데모 중 **실 병원 데이터·실 환자 식별자·실 병원 로고 미확보 상태에서의 로고 사용** 절대 금지 (§8 참조).

---

## §5 Hospital executive proof points (한국 맥락)

### 5.1 한국 상급종합병원 의사결정 구조 (실무 통념 + 공개 가이드 기반 추정)

> **주의**: 아래는 공개 자료(병원 IRB 포털, 산학협력단 페이지)와 업계 통념 기반 재구성. 특정 병원의 실제 거버넌스와 다를 수 있음. §9 Q-병원-1에서 대표님 내부 지식 확인 요청.

데이터 제공 계약 한 건에 전형적으로 관여하는 주체:

- **원장(의료원장)**: 최종 서명. 이사회 보고 대상.
- **영상의학과장**: 데이터 품질·PACS 운영 관점. 사실상 거부권자.
- **임상연구심의위원회(IRB)**: 재식별 리스크·환자 동의 범위 심의. [가톨릭대 서울성모병원 IRB 안내](https://cmcirb.cmcnu.or.kr/irb_contact_information.do), [이화의대부속서울병원 IRB](https://www.r-bay.co.kr/agency/main/ZDZxdUxtWlZqRTYwWjRocTUwRWY3UT09) 참조.
- **정보보호책임자(CISO/CPO)**: PIPA 제28조의8 + 병원 자체 보안 정책. 2026-04 기준 한국 개정 PIPA는 **CEO 개인책임 (최대 10%)** 강화 ([IAPP, Korea PIPA Overhaul](https://iapp.org/news/a/south-korea-overhauls-pipa-and-ties-fines-to-ceo-accountability), [Captain Compliance 요약](https://captaincompliance.com/education/south-korea-just-made-the-ceo-personally-responsible-for-data-breaches/)).
- **산학협력단**: 계약·기술이전 권리 관리. [세브란스 산학협력단](https://research.severance.healthcare/research/index.do) 참조.
- **전산실/IT본부**: Gateway 설치·PACS VLAN·방화벽. 실제 운영.

대표님 1인이 투자자·경영진을 겸임할 경우, **원장 권한 + 경영진 시각**을 가지나 **IRB·CISO 동의는 여전히 필요**. 이는 RadiVault가 데모에서 "**IRB/CISO 승인 획득 경로**까지 미리 설계되어 있다"를 증명해야 함을 의미.

### 5.2 병원 경영진이 데모에서 확인하려는 8 proof points

| # | Proof point | v0.1 증거 현황 | 데모에서의 노출 방식 |
|---|-----------|--------------|------------------|
| P-H-1 | **환자 사생활 기술 가드** | De-ID Pixel v0.2 동작 (OCR 번인 마스킹 + defacing), Annex E 18개 태그 제거, UID 재생성, 날짜 시프트 (docs/research/de-id-pixel-technical-foundations.md) | 장면 3에서 단일 DICOM 1장의 **before/after** 비교 (메타 diff + 픽셀 마스킹) |
| P-H-2 | **PIPA 제28조의8 대응 구조** | 완전 익명정보 전제, 매핑 테이블은 병원 내부 잔존, anonymization_flag 게이트 (docs/specs/dev-spec-central-ingest.md FR) | 장면 3 아래쪽에 "raw data never leaves hospital network" 화살표 강조. **단정 금지** — "designed to align with" 표현 |
| P-H-3 | **CEO 개인책임 리스크 완화** | 감사 해시체인(SHA-256 anchor), append-only audit_ingest_event, WORM 보존 설계 | 장면 4에서 해시체인 검증 CLI 실행 — `ingest-admin anchor verify --from X --to Y` → "연속성 OK" 출력 |
| P-H-4 | **철회권 운영 가능성** | withdraw-stub 엔드포인트 (501, v0.1), 계약 상 30–90일 삭제 조항 (PRD §4.7) | 장면 4에서 "철회 요청 시 30일 내 삭제" 로드맵 명시. v0.1은 **스텁**임을 정직하게 공개 |
| P-H-5 | **병원 월 수익 가시성** | 아직 billing 모듈 없음 (v0.2 옵션 G). 현재는 단순 시뮬 가능 | 장면 5에서 Google Sheets / Excel 기반 **수익 시뮬레이터** (파일럿 MG ₩500만~1,000만/년 기준, 티어별 revenue share 25–50%) 직접 계산 시연 |
| P-H-6 | **운영 부담 최소화** | Gateway = outbound-only Docker 컨테이너. inbound 포트 미개방. PACS VLAN 내부 배치 (docs/specs/design-spec-gateway-agent.md §8 hospital walkthrough) | 장면 3 "설치 walkthrough" 30초 — `docker-compose up` 실행 후 status 출력 |
| P-H-7 | **병원 계약 안전장치** | 표준 계약서 v1 **아직 없음** (PRD §7 Phase 1 KPI). 법무 자문 미완 | 슬라이드 1장 "계약 구조 로드맵" — MSA/DPA/데이터 제공 각서 3단. 데모 중 법무 변호사 명시 요청 수용. |
| P-H-8 | **플랫폼 지속성** | 시드 전 단계, v0.1 5-feature 완료, 363 테스트 통과 | 장면 7 ask 부분에서 "이 미팅이 첫 파일럿 투자/공급 조합" 명시. 파일럿 망할 경우 **병원 Gateway 데이터 그대로 잔존** 원칙 재확인 (Zone 1 분리 설계의 진짜 가치) |

### 5.3 병원 경영진에게 "보여주면 안 되는 것"

- **다른 병원 로고** — 확보 전 사용 시 신뢰 즉시 소멸.
- **구체 경쟁 병원 데이터 언급** — 동료 병원이 이미 우리와 거래 중일 것 같은 오해 금지.
- **"SOC 2 획득" 단정** — "in preparation"만 허용 (docs/marketing/* 전체 이 원칙 이미 적용 중).
- **"FDA 승인" 단정** — RadiVault는 의료기기 아님. 데이터 판매 플랫폼.

### 5.4 한국 병원 경영진의 "불편한 질문" 사전 대응

| 질문 | 대표님이 묻지 않아도 속으로 하는 것 | 사전 준비 답변 |
|------|---------------------------------|------------|
| "만약 재식별이 되면 누가 책임지나?" | CEO 개인책임 | 표준 계약서에 **면책·보증·보험 조항** 포함 예정 (법무 자문 후). 데이터 제공 전 IRB 심의 통과를 조건으로 함. |
| "판매 대상 구매자가 중국 기업이면?" | 중국 위협 인식 | v0.1은 구매자 화이트리스트 방식. 국가·엔티티별 차단 가능 설계 (buyer_api_key.scope_json 확장). |
| "경쟁 병원이 먼저 합류하면 우리가 손해 아닌가?" | 선점 인센티브 | **파일럿 병원 한정 MG ₩500~1,000만 + revenue share 프리미엄 tier 1–2%p**. |
| "이 플랫폼이 6개월 후 망하면?" | 리스크 | Gateway는 병원 내부 시스템이며, **연결 끊어져도 원본은 건드리지 않음**. 데이터 추출/전송만 중단. |
| "우리 병원 IT팀이 3일 이상 시간 쓸 수 있나?" | 운영 부담 | docs/marketing/onboarding-hospital-it-admin-ko.md의 8단계 walkthrough는 **절반일 ~ 1일** 실제 소요 설계. |

---

## §6 Investor proof points

### 6.1 시드~시리즈A 벤치마크 (업계 표준)

[Metal Playbook 2025](https://www.metal.so/collections/2025-b2b-saas-seed-round-fundraising-playbook): 52% 의 SaaS 시드 라운드가 $1–4M, 평균 12주 소요. 시드 기대치는 $0–500K ARR, 초기 cohort retention, 명확 ICP, GTM 가설.

시리즈A 기대치: $1–5M ARR, 반복 가능한 영업 프로세스, NRR 100%+.

### 6.2 Marketplace 특유 지표

a16z 마켓플레이스 가이드(13 Metrics) 및 Bowery Capital 가이드에 따르면:

- **GMV** (Gross Merchandise Value): 플랫폼 상의 총 거래 가치. RadiVault = 총 판매 dataset dollar 합.
- **Take rate**: 플랫폼이 가져가는 % (RadiVault 설계: 50–75%, 병원 25–50%).
- **CM1 / Gross margin**: RadiVault PRD §11 타깃 = **60–70%**. Segmed·Gradient는 비공개지만 데이터 마켓플레이스 업계 통념은 65~80% 가능.
- **LTV/CAC**: RadiVault v0.1 시점 CAC 측정 불가 (첫 고객 없음). 시드 초기 예외 허용.

출처: [Andreessen Horowitz — 13 Metrics for Marketplace Companies](https://a16z.com/13-metrics-for-marketplace-companies/), [Bowery Capital B2B Marketplace Metrics](https://bowercap.com/blog/insights/measuring-b2b-marketplace-key-metrics-for-success).

### 6.3 투자자가 RadiVault 데모에서 확인하려는 8 proof points

| # | Proof point | v0.1 증거 현황 | 데모에서의 노출 |
|---|-----------|--------------|-------------|
| P-I-1 | **매출 루프 완결성** | Gateway→Central→Metadata→Order→Download 5-feature 완주. 363 테스트 PASS | 장면 5 "full stack one-flow" — 검색→주문→다운로드 20초 |
| P-I-2 | **Regulatory moat** | 완전 익명정보 + PIPA §28-8 게이트 + 감사 해시체인. Segmed/Gradient 대비 **한국 특화** 해자 | 장면 2 아키텍처에서 "한국 법인 수집 / Delaware 법인 판매" 이중 구조 강조 |
| P-I-3 | **Gross margin 구조** | Y1 60%, Y3 70% 타깃 (PRD §11) | 장면 6 재무 슬라이드 1장. 클라우드 비용이 on-prem storage로 억제됨(Hybrid Model 3)을 강조 |
| P-I-4 | **TAM 신빙성** | 의료영상 AI $1.65–2.5B (2025), 한국 의료 AI $0.37B→$6.67B 2030 (CAGR 50.8%) — 근거 docs/research/k-meddata-research-summary.md §2 | 슬라이드 1장. **bottom-up 계산** 병행 ("한국 파일럿 N곳 × 연 Y만 스터디 × 단가 $Z = $M 매출 잠재") |
| P-I-5 | **Go-to-market 반복성** | 아직 0 병원 운영. 파일럿 2곳 착수 전. | **정직하게 공개** — "오늘 이 미팅이 첫 파일럿 결정 기회" |
| P-I-6 | **Competitive positioning vs Segmed/Gradient** | Segmed: 2,000+ 병원/글로벌 / Gradient: 20M+ 스터디/셀프서비스 / RadiVault: **한국 다양성 데이터 + 한국 법 우회 경로** | 장면 2에 1-slide 비교표 (docs/marketing/competitive-positioning-buyer-en.md 기반) |
| P-I-7 | **Team** | Kyle (의료영상 QA/SW, DICOM 전문) + 1인? | 슬라이드 1장. 도메인 신뢰성 강조. |
| P-I-8 | **Runway & ask** | 시드 규모 ask (금액 Kyle 결정) + 파일럿 병원 2곳 확보 + SOC 2 Type I 1년 내 | 장면 7 ask 부분. Segmed Series A $10.4M 참조로 RadiVault 시드 적정 규모 제시. |

### 6.4 투자자 "불편한 질문" 사전 대응

| 질문 | 사전 준비 답변 |
|------|------------|
| "Segmed이 한국 진출하면?" | 한국 법인·한국어 판독문 NLP·한국 병원 IT 문화 3 barrier. 일부는 공급 파트너십 가능 (리서치 §10 Phase 1). |
| "첫 파일럿 병원 없는데 어떻게 검증?" | 오늘 이 미팅이 그 결정. 대표님이 **첫 투자자+첫 공급자** 겹침 구조 (Advocate Health + Segmed 모델 차용). |
| "FSL 상업 라이선스 문제?" | v0.2 pydeface 의존. 법무 flag 중. mridefacer 폴백 및 상업 라이선스 acquisition 옵션 있음. |
| "Hot Storage 확장 시 비용?" | Flow C 인기 코호트만 선제적 보관. 비인기 데이터는 on-prem 잔존 → 스토리지 비용 선형 증가 방지. |
| "SOC 2 없이 미국 구매자가 살까?" | Phase 1은 연구기관·한국 AI 기업부터. Phase 2 SOC 2 Type I 이후 미국 엔터프라이즈 진입. |

---

## §7 Scene-by-scene storyboard templates

### 7.1 공통 제약

- 총 15~20분 (권장 **17분 + Q&A 3분 = 20분**).
- 청중 1인, 대화형 가능. 중간 질문 허용.
- v0.1 자산: Gateway CLI, Central Ingest API, Metadata Search API + search-admin, Order Fulfillment API + fulfillment-admin, Prometheus metrics dump, 감사 해시체인 verify, Alembic migration 로그, 363 테스트 실행 가능.
- **UI 없음** → 시각적 자산은 (a) 터미널, (b) 아키텍처 다이어그램 슬라이드, (c) Google Sheets 수익 시뮬, (d) curl 응답 JSON, (e) v0.2 목업 이미지(정직 표기).

### 7.2 변형 A — **"Revenue Loop Proof"** (권장, 매출 루프 중심)

| 장면 | 시간 | 제목 | 시각 자산 | 프레젠터 핵심 문장 |
|------|-----|------|---------|-----------------|
| 1 | 0:00–2:00 | Hook + Dual framing | 1 슬라이드: "한국 의료영상 → 글로벌 AI: 두 관점, 하나의 제품" | "투자자에겐 카테고리 스타, 병원엔 정산 루트입니다. 같은 15분에 두 이야기 모두 드리겠습니다." |
| 2 | 2:00–5:00 | 시장 + 아키텍처 1장 | 1 슬라이드: Zone 1/2/3 + 3 플로우. 한국법 모트 + 경쟁비교 미니표 | "법적 해자는 '데이터가 병원을 떠나지 않는다', 기술적 해자는 '완전 익명화 후에만 밖으로'." |
| 3 | 5:00–8:00 | 병원 Gateway 라이브 (P-H-1,2,3,6) | 터미널 1: `gateway status`, De-ID 명령, PHI before/after, 해시체인 verify | "이 환자 데이터를 지금 중앙으로 보내기 전, PHI 제거와 해시 기록 완료를 보시죠." |
| 4 | 8:00–11:00 | 구매자 라이브 (P-I-1) | 터미널 2 + curl: 검색 → 주문 → 다운로드 → 감사 다시 확인 | "한 구매자가 방금 척추 CT 500건 주문했습니다. 이제 첫 번째 정산 이벤트가 쌓였습니다." |
| 5 | 11:00–13:30 | 병원 수익 시뮬 (P-H-5) | Google Sheets 실시간 편집: 병원별 연 수익 추정 | "이 병원이 연 1만 스터디 공급 시 tier 1~2 혼합 가정 월 정산 ₩Y." |
| 6 | 13:30–15:30 | 재무 + 로드맵 (P-I-3,4,8) | 1 슬라이드: Y1/Y2/Y3 매출 + gross margin + v0.1→v0.3 기능 | "Gradient $2.75M seed, Segmed $10.4M Series A. RadiVault의 창구는 한국." |
| 7 | 15:30–17:00 | Dual Ask | 1 슬라이드: 투자자 ask + 병원 ask 좌우 | "$X seed 수혈 + 첫 파일럿 병원 합류, 하나의 서명에 두 결정이 붙습니다." |
| Q&A | 17:00–20:00 | — | 미리 준비한 FAQ 5건 + 실시간 | — |

**장면 3 상세 (데모 백본)**:

```
# Terminal 1 — Hospital Gateway
$ docker-compose up  # 사전 기동 상태에서 status만 호출
$ gateway-admin status
  # 출력: PACS connected, stale=0, pending=12, deided=154, uploaded=154

$ gateway-admin deid --study SAMPLE-001 --show-diff
  # Before:
  #   PatientName: DOE^JOHN
  #   PatientID:   12345678
  #   StudyDate:   20240315
  # After:
  #   PatientName: (removed)
  #   PatientID:   RV-000001
  #   StudyDate:   20240128  (shifted -46d)
  # Burn-in OCR: 3 regions masked (text="DOE, JOHN" detected)
  # Face defacing: N/A (spine CT)

$ ingest-admin anchor verify --from 1 --to 100
  # Chain OK: 100 seqs, SHA-256 continuous, no gap, last_anchored=2026-04-24T...
```

### 7.3 변형 B — **"Safety-First for Hospital Exec"** (병원 경영진 우선)

P-H-1..P-H-8이 전면. 투자자 관점은 brackets로만.

| 장면 | 시간 | 제목 |
|------|-----|------|
| 1 | 0:00–1:30 | Hook: 환자 사생활 + 병원 매출 동시 달성 프레임 |
| 2 | 1:30–4:00 | Zone 1/2/3 + "데이터는 병원을 떠나지 않는다" |
| 3 | 4:00–8:00 | De-ID 라이브 (before/after) + 해시체인 + IRB 워크플로우 |
| 4 | 8:00–11:00 | 계약 구조 1장 (MSA/DPA/철회권/MG) + 법무 자문 타임라인 |
| 5 | 11:00–14:00 | 수익 시뮬 + 운영 부담 walkthrough |
| 6 | 14:00–16:00 | 투자자 관점 요약 (TAM·moat·traction·ask — **간결**) |
| 7 | 16:00–17:00 | Ask |
| Q&A | 17:00–20:00 | — |

**언제 사용**: 대표님이 투자보다 병원 경영에 더 무게를 두는 시그널(예: 미팅 세팅 시 "원장으로서 먼저 판단하겠다"고 말한 경우).

### 7.4 변형 C — **"Investor-First with Hospital Evidence"** (투자자 우선)

| 장면 | 시간 | 제목 |
|------|-----|------|
| 1 | 0:00–1:30 | Hook: 카테고리 + 숫자 |
| 2 | 1:30–3:30 | 시장 + 경쟁지형 |
| 3 | 3:30–5:30 | 해자: 한국법 + Hybrid 아키텍처 |
| 4 | 5:30–10:30 | 제품 데모 (Gateway + Central + Search + Order 통합) |
| 5 | 10:30–13:00 | 재무 모델 + unit economics |
| 6 | 13:00–15:30 | Go-to-market 증거로 병원 관점 (수익 시뮬 + proof points) |
| 7 | 15:30–17:00 | Ask + team + timeline |
| Q&A | 17:00–20:00 | — |

**언제 사용**: 대표님이 "투자자 모자를 먼저 쓰고 심사"라고 말한 경우. RadiVault가 아직 customer 없어 traction이 약하므로 **기본 권장은 변형 A**.

### 7.5 세 변형 비교

| 기준 | A (권장) | B (병원 우선) | C (투자자 우선) |
|------|---------|------------|-------------|
| 적합 시그널 | 대표님 dual hat 인정 | 병원 경영 우선 | 투자 우선 |
| 매출 루프 노출 | **최강** | 중간 | 강 |
| 병원 안전장치 | 강 | **최강** | 중간 |
| 숫자 밀도 | 중간 | 약 | **강** |
| 실행 리스크 | 중 | 중 | 중 |

---

## §8 Anti-patterns and risks

### 8.1 데모 자체의 금기

1. **실 PHI 노출**
   - 이유: 한 번 본 것은 되돌릴 수 없음. CEO 개인책임 맥락에서 즉시 "저런 회사 못 쓴다" 판정.
   - 대응: 데모 데이터는 **Orthanc 공식 테스트 세트 · TCIA 공개 데이터 · 합성 DICOM** 중 하나. 출처를 화면 모서리에 노출. Tonic.ai 가이드 따라 컬럼명 의존 detection 피하고 pattern matching 병행 ([Tonic.ai Healthcare](https://www.tonic.ai/solutions/industry/healthcare)).
2. **과장된 컴플라이언스 주장**
   - 금기어: "SOC 2 인증", "HIPAA compliant", "FDA 승인", "GDPR 인증", "정부 지정".
   - 허용어: "aligned with", "designed to meet", "in preparation", "following XX standard".
   - 근거: 현재 docs/marketing/* 전체가 이 원칙 적용 중 (Session 5, 7, 8 기록).
3. **미구현 기능 은폐**
   - 예: Buyer Portal Web UI는 **없다**. v0.2 로드맵. 데모 중 "이건 아직 없고, 구매자는 지금 API로 접근합니다" 정직 고지.
   - 예: Billing은 v0.1 **stub** (charge 없음). quickstart §13에 명시됨.
   - 예: Hot Storage 자동 promotion v0.1.1 backlog.
4. **라이브 실패 패닉**
   - §4.4 런북 준비 필수. "이건 테스트 환경 이슈입니다. 런북 RB-XX에 정리된 대로 복구됩니다." 멘트로 **런북 존재 자체가 증거**가 되도록 변환.
5. **합성 데이터를 "진짜 병원 데이터"처럼 언급**
   - 예: "이건 아산병원에서 온 데이터입니다" (거짓). 대체: "이건 TCIA 공개 척추 CT입니다. 실제 파일럿 병원 데이터도 동일 포맷으로 흐릅니다."
6. **로고 벽 조작**
   - 확보 미완 병원·구매자 로고를 "파트너" 섹션에 넣는 것 — 대표님이 직접 아는 병원이면 즉시 탄로. "In discussion"으로 라벨링 또는 생략.

### 8.2 한국 병원 경영진 특유의 금기 코드

1. **가격을 먼저 말하지 말 것** — "월 얼마"를 슬라이드 첫 3분에 꺼내면 "상인"으로 프레임됨. 5분 이후에 수익 시뮬 맥락에서 등장시켜야 "파트너십"으로 인식.
2. **경쟁 병원과의 비교** — "A병원 대비 B병원이 더 잘한다"는 구도 금기. 대신 "한국 병원의 집합적 가치" 프레임.
3. **"원장님께 개인적으로 드리는"** 언어 — 뇌물/배임 오해 소지. 병원 법인 차원의 수익·MG를 강조.
4. **급한 서명 요구** — 첫 미팅에서 계약 요구 금지. 대신 "Phase 1 파일럿 MoU(업무협약) → IRB 심의 → MSA → DPA" 단계 구조 공개. 각 단계 예상 기간(4–6주 단계별) 미리 제시.
5. **정부 과제·국비 지원 암시** — 허위 시 치명적. 현재 RadiVault는 국비 참여 무관. "데이터 바우처·AI 허브" 연결 가능성은 탐색 단계로만 언급.
6. **"우리가 모든 걸 대신해드린다"** — 영상의학과장·전산실이 자기 역할을 위협받는다 느끼면 저항. 반대로 "**여러분 팀의 협업 파트너**" 프레임으로 전환.

### 8.3 투자자 특유의 금기 코드

1. **"TAM 계산"에만 30초 이상** — 상향식(bottom-up) 계산 + 병원당 단가 시뮬로 대체.
2. **Segmed·Gradient를 무시** — 반드시 **알고 있음**을 증명 + 차별점을 30초 내 명시.
3. **"향후 3년 1억 명 대상"** 같은 비현실적 성장 — 시드는 **신뢰 가능한 작은 숫자**를 좋아함.
4. **"아직 고객이 없어서"** 방어적 언급 — 대신 "오늘 이 미팅이 첫 고객·첫 투자자 겹침 구조의 논리적 결론" 공격 프레임.
5. **과도한 기술 디테일** — DICOM 18 태그, Annex E, argon2id 등은 **Q&A에 예약**. 메인 데모는 흐름 중심.

### 8.4 법률·규제 리스크 (데모 발언 시 특히 주의)

- "**국외이전 불가**한 한국법을 우리가 해결했다" → "우리는 완전 익명정보 전제로 적법한 경로를 설계했고, 법률 자문 진행 중" 으로 톤다운.
- "**환자 동의 없이**" → 절대 금기. 익명정보도 원천 수집 시점의 동의·고지 구조 필요. IRB 심의 경로 언급.
- "**미국 판매는 HIPAA 자동 해결**" → 완전 익명화가 Safe Harbor·Expert Determination 기준 충족해야 함. 데모 시 "기준 충족을 목표로 설계됨, 검증 진행 중".

---

## §9 Open questions for Kyle (planner 결정 선행 항목)

다음은 `dev-spec-buyer-portal-demo` 또는 `dev-spec-demo-kit` 작성 전에 Kyle이 결정해야 하는 항목이다. 각 항목은 데모 자산 제작 범위·일정에 직접 영향.

### 9.1 미팅 성격 관련

- **Q-미팅-1**: 대표님이 미팅에서 자신을 어떤 모자(투자자 우선 / 병원 경영 우선 / 동등)로 제시하셨는가? → 변형 A/B/C 선택 근거.
- **Q-미팅-2**: 미팅 장소가 대표님 병원 내부(영상의학과 회의실 등)인가, 외부 호텔·공유오피스인가? → 네트워크 리스크·백업 녹화 필요도.
- **Q-미팅-3**: 대표님 외 **다른 병원 관계자**(CISO, 영상의학과장 등)가 배석하는가? → 배석자 맞춤 슬라이드 추가 여부.
- **Q-미팅-4**: 15분 쇼트 컷 vs 45분 풀 미팅 중 어디인가? → 본 문서는 17+3=20분 가정.
- **Q-미팅-5**: 후속 **leave-behind 자료** 원하시는가? → 있으면 pitch deck PDF + docs/marketing/* 링크 묶음 필요.

### 9.2 데모 콘텐츠 결정

- **Q-데모-1**: 변형 A/B/C 중 어느 것? (권장 A)
- **Q-데모-2**: 라이브 vs 녹화 vs 하이브리드? (권장 하이브리드)
- **Q-데모-3**: 데모에 쓸 DICOM 샘플 데이터 소스 확정 — Orthanc 공식 테스트 / TCIA 공개 / 합성 생성 중 하나. 라이선스·출처 표기 방식.
- **Q-데모-4**: 수익 시뮬 숫자 공개 범위 — 티어별 revenue share 25–50% 중 병원 제시값은? MG는 ₩500만 vs ₩1,000만 중?
- **Q-데모-5**: 경쟁사 비교 슬라이드에서 Segmed/Gradient 로고 노출 OK? (공개 브랜드 사용은 적법하나 비교광고 원칙 준수 필요).
- **Q-데모-6**: 데모 시연 중 **"아직 없음"** 고지 대상 7건(Buyer Portal UI, Billing 실결제, Hot Storage promotion, Webhook, Multi-buyer concurrent, SOC 2, FDA 준비 AI) 각각 "v0.2/v0.3/roadmap" 구분 확정.
- **Q-데모-7**: "병원 로고 벽"을 슬라이드에 **비워두는가**, **"In discussion"** 플레이스홀더 쓰는가, **아예 슬라이드 생략**하는가?

### 9.3 브랜딩·언어

- **Q-브랜드-1**: RadiVault 내부 5개 컴포넌트(Gateway Agent, Central Ingest, Metadata Index, De-ID Pixel, Order Fulfillment)를 **외부용 단일 브랜드**로 통합하는가? (예: "RadiVault Platform") 아니면 **2~3 외부 브랜드**로 재정렬(예: "RadiVault Connect = Gateway + De-ID" / "RadiVault Exchange = Search + Order")?
- **Q-브랜드-2**: 한국어 데모 vs 영어 데모 vs 이중언어? (대표님 성향 확인 필요)
- **Q-브랜드-3**: 데모 중 "Segmed·Gradient를 공급 파트너로 삼을 수도 있다" 옵션 언급할 것인가, 경쟁자로만 포지셔닝할 것인가?

### 9.4 자산 제작 범위 (dev-spec 환류 필드)

다음은 `@planner`가 `dev-spec-buyer-portal-demo.md` 또는 `dev-spec-demo-kit.md` 작성 시 반드시 결정해야 할 항목이다:

- **D-1**: 데모 전용 **Buyer Portal 최소 UI** 제작 여부 — 현재 API-only이므로 시각적 임팩트 약함. 최소 1 페이지(검색 → 결과 카드 → 썸네일 목업) 30–40시간 투입 가치 판단.
  - 옵션 (a): v0.1에는 UI 없이 curl + CLI 시연.
  - 옵션 (b): **정적 HTML + fetch** 미니 UI, 백엔드 실 API 연결. 제작 2~3일.
  - 옵션 (c): Next.js 스캐폴드 본격 v0.2 착수.
- **D-2**: **병원 Admin 대시보드** 모크업 — 월간 수익·스터디 수·감사 로그 Grafana 기반 조립 가능. Prometheus 메트릭 17종 이미 존재. 투입 1~2일.
- **D-3**: **DICOM 썸네일 뷰어** 포함 여부 — Cornerstone.js 정적 페이지로 1 study 열람 가능. Flywheel 대비 기본 수준. 투입 1일.
- **D-4**: **감사 체인 시각화 위젯** — 해시체인 verify 출력을 그래픽화. DAG visualization. 투입 2일.
- **D-5**: **수익 시뮬 계산기** — Google Sheets vs 자체 단순 웹 페이지. Sheets면 투입 2시간, 자체 페이지면 1일.
- **D-6**: **데모 백업 녹화본** 제작 — 전체 17분 MP4, 자막, 2회 품질 검수. 투입 2~3일.
- **D-7**: **실패 시 사전 캡처 로그 세트** — 정상 실행 결과를 녹화·텍스트로 보관. 투입 1일.
- **D-8**: **변형 A/B/C 슬라이드 덱 3종** 개별 제작 vs 공용 덱 + plug-and-play 슬라이드 구조. 후자 권장. 투입 3~4일 (덱 자체).
- **D-9**: **Q&A 예상 답변 카드 20장** — 면접 수준 준비. 투입 1~2일.
- **D-10**: **대표님 미팅 이후 follow-up 자료 패키지** — leave-behind PDF + 기술 문서 링크 큐레이션. 투입 1일.

총 투입 추정: **최소 5일 (D-1a 생략, D-3 생략) ~ 최대 15일 (D-1c Next.js 스캐폴드 포함)**. 미팅 D-day와 역산 필요.

### 9.5 법무·계약

- **Q-법무-1**: 데모에서 언급 가능한 "법무 자문 진행 중" 문구의 실제 법무법인·단계. 허위 암시 방지 위해 팩트 체크 필요.
- **Q-법무-2**: 표준 파일럿 MoU 드래프트 (1장짜리) 데모 leave-behind에 포함 가능한가? 포함 시 변호사 리뷰 필요 여부.
- **Q-법무-3**: SOC 2 "in preparation" 시점 근거 — 벤더(Vanta/Drata) 계약 또는 준비 시작일 보유 여부.
- **Q-법무-4**: Segmed·Gradient 로고를 경쟁 비교에서 사용 시 상표권·비교광고 규정 검토.

### 9.6 기술 인프라

- **Q-인프라-1**: 데모 실행 환경 — Kyle 맥북 로컬 vs 클라우드 서버 vs 병원 내 배포. 백업 경로 수.
- **Q-인프라-2**: 363 테스트 suite를 **데모 중 실행**할 것인가? Session 5/7/8 "PASS" 이미지가 시각적 근거로 강력. 실행 시간 및 병렬성 고려.
- **Q-인프라-3**: Prometheus/Grafana 대시보드를 데모에서 공개할 것인가? 비공개면 스크린샷, 공개면 실시간.
- **Q-인프라-4**: 감사 해시체인 tamper 테스트를 **라이브로** 시연할 것인가? 매우 강력한 인상 + 설명 시간 90초.

---

## §10 Change history

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-24 | @researcher | 최초 작성. 데모·피치 레퍼런스 리서치 집중. 시장·기술 기반은 기존 리서치 6종 참조로 대체. Segmed/Gradient/Truveta/Rhino/Flywheel 5사 공개 자료 기반 연출 패턴 추출, dual-audience 3 구조 + RadiVault 권장 하이브리드, live vs recorded 결정 프레임, 병원 경영진·투자자 proof point 각 8건, 스토리보드 변형 A/B/C, 금기 23건, Kyle 결정 항목 30+건 (§9.4 dev-spec 환류 10건 포함). |

---

## 종합 출처 목록

### 경쟁사·산업 (1차·2차)

- Segmed Series A 공지: [PR Newswire, 2024-09](https://www.prnewswire.com/news-releases/segmed-secures-10-4-million-series-a-funding-led-by-igan-partners-and-advocate-health-302236032.html) / [Segmed.ai News](https://www.segmed.ai/news/segmed-secures-10-4-million-series-a-funding) / [Radiology Business](https://radiologybusiness.com/topics/artificial-intelligence/segmed-startup-gathers-medical-imaging-data-ai-development-raises-10m) / [Blumberg Capital News](https://blumbergcapital.com/news-insights/segmed-secures-seriesa-funding/) / [PitchBook profile](https://pitchbook.com/profiles/company/433413-73)
- Gradient Health Atlas 2: [공식 블로그](https://gradienthealth.io/gradient-health-launches-atlas-2-setting-a-new-standard-for-medical-imaging-data-access/) / [ITN Online](https://www.itnonline.com/content/gradient-health-releases-upgrade-self-service-medical-imaging-data-platform) / [PR Newswire Seed $2.75M](https://www.prnewswire.com/news-releases/creating-the-worlds-largest-medical-imaging-library--gradient-health-closes-2-75m-round-301854082.html) / [NIH SEED portfolio](https://seed.nih.gov/portfolio/nih-portfolio-company-showcase/gradient-health) / [Frontlines.io interview](https://www.frontlines.io/the-story-of-gradient-health-building-the-future-of-medical-ai-data/)
- Truveta: [Fierce Healthcare $95M](https://www.fiercehealthcare.com/tech/health-systems-backed-truveta-closes-95m-to-fund-its-data-analysis-platform) / [Fierce Healthcare launch](https://www.fiercehealthcare.com/digital-health/truveta-s-health-data-platform-launches-200m-insights-covid-breakthrough-infections) / [Healthcare Finance News](https://www.healthcarefinancenews.com/news/leading-health-systems-form-truveta-aggregate-and-sell-anonymized-patient-data) / [Crunchbase](https://www.crunchbase.com/organization/truveta) / [PitchBook profile](https://pitchbook.com/profiles/company/442905-85) / [Trinity Health Genome Project](https://www.trinity-health.org/newsroom/press-releases/leading-health-systems-launch-truveta-genome-project-creating-worlds)
- Rhino Health: [VentureBeat stealth emergence](https://venturebeat.com/business/rhino-health-emerges-from-stealth-to-bring-hospital-data-to-federated-learning/) / [PR Newswire Seed $5M](https://www.prnewswire.com/news-releases/rhino-health-raises-5-million-to-improve-ai-workflows-in-healthcare-using-federated-learning-301225750.html) / [Rhino FCP 공식](https://www.rhinofcp.com/) / [GlobeNewswire FL Consortium](https://www.globenewswire.com/en/news-release/2022/05/05/2436894/0/en/Rhino-Health-Platform-Powers-Hospital-Based-Federated-Learning-Consortium.html)
- Flywheel.io: [공식](https://flywheel.io/) / [SaaS 발표 2023-11](https://flywheel.io/2023/11/21/flywheel-saas/) / [SaaS blog detail](https://flywheel.io/insights/blog/flywheel-unveils-saas-platform-for-advancing-medical-imaging-ai-at-scale) / [RSNA viewer 업데이트](https://flywheel.io/insights/articles-research-data-management/flywheel-unveils-new-viewer-updates-at-rsna)

### 한국 규제·법률

- [개인정보 보호법 제28조의8 — CaseNote](https://casenote.kr/%EB%B2%95%EB%A0%B9/%EA%B0%9C%EC%9D%B8%EC%A0%95%EB%B3%B4_%EB%B3%B4%ED%98%B8%EB%B2%95/%EC%A0%9C28%EC%A1%B0%EC%9D%988)
- [국가법령정보센터 — 개인정보 보호법 원문](https://www.law.go.kr/LSW/lsInfoP.do?lsId=011357&ancYnChk=0)
- [Kim & Chang — 개정 PIPA FAQ](https://www.kimchang.com/ko/insights/detail.kc?sch_section=4&idx=21101)
- [개인정보보호위원회 — 국외이전 제도](https://www.privacy.go.kr/front/contents/cntntsView.do?contsNo=367)
- [IAPP — South Korea overhauls PIPA, CEO accountability](https://iapp.org/news/a/south-korea-overhauls-pipa-and-ties-fines-to-ceo-accountability)
- [Captain Compliance — PIPA CEO 개인책임](https://captaincompliance.com/education/south-korea-just-made-the-ceo-personally-responsible-for-data-breaches/)
- [ICLG — Digital Health Laws Korea 2026](https://iclg.com/practice-areas/digital-health-laws-and-regulations/korea)
- [PMC — Privacy Protection and Data Utilization (Korea)](https://pmc.ncbi.nlm.nih.gov/articles/PMC7921570/)

### 한국 병원 IRB·산학협력

- [가톨릭의대 IRB Contact](https://cmcirb.cmcnu.or.kr/irb_contact_information.do)
- [세브란스 산학협력단](https://research.severance.healthcare/research/index.do)
- [서울대학교병원 경영공시](https://www.snuh.org/content/M004006002.do)
- [서울아산병원 IRB landing](https://aris.amc.seoul.kr/irb-landing-site/Home/ContactInfo.html)
- [기관생명윤리위원회 정보포털](https://irb.or.kr/menu02/commonConvention.aspx)

### 피치·데모 실무 (3차 · 실행 가이드)

- [Y Combinator Library — How to build seed pitch deck](https://www.ycombinator.com/library/2u-how-to-build-your-seed-round-pitch-deck)
- [Y Combinator Library — Series A pitch](https://www.ycombinator.com/library/8d-how-to-build-a-great-series-a-pitch-and-deck)
- [Storydoc — YC Pitch Deck Examples](https://www.storydoc.com/blog/y-combinator-pitch-deck-examples)
- [Forum VC — B2B SaaS Pitch Deck Guide](https://www.forumvc.com/thought-pieces/the-essential-guide-to-creating-a-compelling-b2b-saas-pitch-deck-for-pre-seed-and-seed-stage-founders)
- [Metal Playbook 2025 — B2B SaaS Seed Fundraising](https://www.metal.so/collections/2025-b2b-saas-seed-round-fundraising-playbook)
- [Pitch Deck Fire — Beyond the Investor Presentation](https://pitchdeckfire.com/resources/beyond-the-investor-presentation-different-pitch-deck-audiences/)
- [Pitch Deck Fire — Why You Need More Than One Pitch Deck](https://pitchdeckfire.com/resources/why-you-need-more-than-one-pitch/)
- [Andreessen Horowitz — 13 Metrics for Marketplace Companies](https://a16z.com/13-metrics-for-marketplace-companies/)
- [Bowery Capital — B2B Marketplace Metrics](https://bowercap.com/blog/insights/measuring-b2b-marketplace-key-metrics-for-success)
- [Demio — Compelling Product Demo Script](https://www.demio.com/blog/compelling-product-demo-script)
- [Contrast Learn — Product Demo Script](https://www.getcontrast.io/learn/product-demo-script)
- [Gong — Demo Script Examples](https://www.gong.io/blog/demo-script-examples)
- [Walnut — SaaS Demo Script](https://www.walnut.io/blog/product-demos/how-to-write-a-saas-demo-script-that-sells/)
- [Harvard Innovation Labs — One-Minute Healthcare Pitch](https://innovationlabs.harvard.edu/how-to/mastering-the-one-minute-pitch)
- [Acronis — 3-2-1 Backup Rule](https://www.acronis.com/en/blog/posts/backup-rule/)

### 합성 데이터·PHI 안전

- [Tonic.ai — Healthcare Data Solutions](https://www.tonic.ai/solutions/industry/healthcare)
- [PMC — ASQ-PHI adversarial synthetic data benchmark](https://pmc.ncbi.nlm.nih.gov/articles/PMC12926592/)

---

## PRD/ARCHITECTURE 갱신 제안 (읽는 @planner 참조)

본 리서치가 발견한 **기존 문서 갱신 필요 지점**:

1. **docs/prd.md §11 오픈 퀘스천**에 "첫 데모 청중 타깃 확정 (투자자+공급자 겹침 구조의 첫 후보)" 항목 추가 권장.
2. **docs/prd.md §7 KPI Phase 1**에 "파일럿 병원 2곳" 외에 "시드 투자 $X 유치" KPI 추가 고려 (현재 Phase 3에만 "시리즈 A" 명시).
3. **docs/ARCHITECTURE.md §10 미해결 질문**에 "Buyer Portal Web UI Phase 여부 — 데모·영업 가속화를 위한 v0.1.5 분리 고려" 추가 권장.
4. **docs/prd.md §4.3 Buyer Portal**이 "Phase 2"로 명시되어 있으나, 본 리서치 §9.4 D-1/D-2/D-3 결론에 따라 **v0.1.5 "Demo UI slice"**로 분리 검토.

---

### NEXT_STEP
- 완료 산출물: docs/research/demo-pitch-references-radivault.md
- 제안 다음 단계:
  - (즉시) 메인 세션 — Kyle에게 §9 오픈 퀘스천 30+건 중 **미팅 성격 관련 Q-미팅-1~5 + 데모 결정 Q-데모-1~7** 먼저 확인. 결정 없이는 planner가 dev-spec을 시작할 수 없음.
  - (Q-미팅·Q-데모 확정 후) `@planner` — `dev-spec-demo-kit.md` 또는 `dev-spec-buyer-portal-demo.md` 작성. 본 리서치 §9.4 D-1..D-10을 기능 요구로 수용하고 투입 일정(5일 최소 ~ 15일 최대) 중 택일.
  - (병렬 가능) `@designer` — 변형 A 스토리보드 확정 후 17분 데모 덱 + 수익 시뮬 Sheets + 백업 녹화본 스크립트 설계.
  - (병렬 가능) `@marketer` — leave-behind PDF 큐레이션 (docs/marketing/* 기존 자산 9종 중 발췌 + 번역 필요 항목 식별).
- Kyle 결정 필요 사항:
  1. **미팅 성격** Q-미팅-1~5 (특히 대표님 모자 순서, 배석자 유무)
  2. **데모 변형** A vs B vs C (본 리서치 권장: A)
  3. **데모 모드** Live vs Recorded vs Hybrid (권장: Hybrid)
  4. **Buyer Portal UI 자산 투입 범위** (옵션 D-1의 a/b/c 중 선택 — 최소 5일 vs 최대 15일 격차)
  5. **경쟁사 로고 비교 슬라이드 사용 여부** 및 법무 검토
  6. **수익 시뮬 공개 숫자** (MG ₩500만 vs ₩1,000만, revenue share tier별 병원 제시값)
  7. **브랜드 통합 전략** (RadiVault Platform 단일 vs 2~3 서브브랜드)
  8. **미팅 D-day** — 자산 제작 일정 역산 필요
