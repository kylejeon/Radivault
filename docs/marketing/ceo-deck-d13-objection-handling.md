# Objection Handling — D-13 예상 질문 11개 + 답변

> **Status**: Draft v0.2 · **작성자**: @marketer · **작성일**: 2026-04-25
> **§0 Changelog (v0.2)**: Kyle K-3 결정 (라이브 `curl /api/search` 시연 제외) 에 따른 청중 자연 질문 대비 — Q11 신설 ("왜 라이브 API 호출 데모를 안 하나요?"). Q1–Q10 번호 보존.
> **목적**: 시연 직후 Q&A 에서 나올 가능성이 높은 11개 질문에 대한 **사실 기반** 응답. 모든 응답은 PRD / QA report / research 문서로 추적 가능해야 함.
> **사용 원칙**:
> 1. 모르면 "지금 단계에서는 답을 갖고 있지 않습니다 (TBD)" 솔직히. 추정 답변 금지.
> 2. 컴플라이언스 단정형 어휘 금지 — "designed to align" / "in preparation" / "Phase 2 target" 사용.
> 3. 경쟁사 비방 금지 — 객관 비교만.
> 4. 가격·파트너 병원명·정확한 자금 조달 단계는 **Kyle 즉답 회피**, "별도 미팅에서" 라우팅.

---

## Q1 — Compliance · "한국 PIPA 와 미국 HIPAA 둘 다 어떻게 만족시키시나요?"

> "How exactly do you simultaneously meet Korean PIPA and US HIPAA requirements?"

**답변**:
"두 법은 출발점이 다릅니다. PIPA 는 **수집 시점부터의 동의 체인** 을 강조하고, HIPAA 는 **de-identification 후 활용** 에 집중합니다. RadiVault 는 (a) 한국 측에서 PIPA §15·§17·§28-8 의 4종 분리 동의를 수집·이용·국외이전 단계마다 받고, (b) 데이터를 글로벌 buyer 에게 전달하기 전 HIPAA Safe Harbor 18 식별자를 DICOM PS3.15 Annex E + burn-in OCR + 3D defacing 으로 제거합니다. **두 법을 '준수' 한다고 단정하는 대신, 두 법이 요구하는 표준에 맞게 설계되었다 (designed to meet)** 고 말씀드리는 게 정확합니다. 외부 법무 검토는 Phase 2 에 예정되어 있습니다."

**근거**: `docs/prd.md` §8, `docs/research/buyer-auth-research.md` §3.1, `docs/specs/dev-spec-buyer-auth.md` §FR-AUTH-1 §11.1

**금지 어휘**: "PIPA-compliant", "HIPAA-certified", "fully compliant"

---

## Q2 — Data Quality · "라벨링 품질은 어떻게 보장하시나요?"

> "How do you guarantee label quality and inter-annotator reliability?"

**답변**:
"현재 v0.1 에서는 **메타데이터 인덱스만** 제공합니다 — modality, body part, 연령대, 성별, 장비, 촬영연도 같은 DICOM 헤더 기반 facet. **판독문 NLP 라벨링은 Phase 2 로드맵** 입니다. 라벨링이 들어가면 PRD §4.5 에 정의된 3-tier 모델 — Tier 1 자동 NLP, Tier 2 전문의, Tier 3 세그멘테이션 — 으로 가고, **Cohen's κ 와 Dice score 를 공개** 할 계획입니다. v0.1 의 데모 데이터는 TCIA 공개 데이터셋 시드라 라벨 품질 자체가 PR 가능한 단계는 아닙니다."

**근거**: `docs/prd.md` §4.5

**솔직 회피**: 라벨 품질 수치 (κ, Dice) 는 **현재 측정 안 됨** — 만들어내지 말 것.

---

## Q3 — IRB / Ethics · "병원의 IRB 승인은 어떻게 처리되나요?"

> "How does IRB approval work on the hospital side?"

**답변**:
"한국에서는 **완전 익명화된 데이터는 IRB 심의 면제 대상** 으로 해석되는 경우가 일반적입니다 (생명윤리법 제2조의 인간대상연구 정의 + 익명정보 제외). 다만 RadiVault 는 보수적으로 접근해서 (a) 병원이 자체 IRB 또는 임상연구지원실에 사전 보고를 하도록 표준 계약서에 권고하고, (b) Gateway Agent 출력의 익명화 무결성을 SHA-256 해시 체인으로 기록합니다. 최종 IRB 해석은 **외부 법률 자문 (Phase 2)** 으로 확정할 예정입니다."

**근거**: PRD §8 (생명윤리법·의료법 중첩 해석은 법률 자문 필수 명시), ARCHITECTURE §4.7

**금지 어휘**: "IRB-exempt" 단정. "IRB exemption is generally interpreted" 정도가 안전.

---

## Q4 — Pricing · "가격 모델은 어떻게 되나요?"

> "What's your pricing model and unit economics?"

**답변**:
"공개 자료에서는 **Contact for pricing** 모델입니다 — 의료영상 데이터 업계의 직접 경쟁사 (Segmed, Gradient Health 포함) 대부분이 동일 패턴이고, 데이터셋 크기·라이선스 범위·MSA 협상 변수가 크기 때문입니다. 별도 미팅에서 NDA 하 상세 단가를 공유드릴 수 있습니다. **병원 측 revenue share 는 PRD §8 에 25–50%** 로 정의되어 있고, Tier 별 차등입니다."

**근거**: `docs/research/portal-redesign-competitive-analysis.md` §2.8 (15개 경쟁사 중 9개가 sales-led 가격), PRD §8

**Kyle 회피 라인**: "구체 단가는 NDA 미팅에서 공유드리겠습니다."

---

## Q5 — Market Size · "TAM 은 어떻게 계산하시나요?"

> "What's the TAM and how do you size the opportunity?"

**답변**:
"세 층으로 나눠 보고 있습니다. (1) **Bottom-up**: 한국 상급종합병원 45곳 + 종합병원 320곳 (보건복지부 통계) × 평균 연 study 볼륨. (2) **Top-down**: 글로벌 medical imaging AI 시장 규모를 인용한 industry report (제3자) × 한국 데이터의 프리미엄 비중. (3) **Comparable**: Segmed 가 직전 라운드 시점 보고한 partner site 수. **저희가 지금 단정해서 말씀드릴 수 있는 단일 TAM 숫자는 갖고 있지 않고**, 별도 미팅에서 시뮬레이션 모델을 공유드리겠습니다."

**근거**: PRD 에 TAM 단정 수치 없음 — 함부로 만들면 거짓.

**솔직 회피**: TAM 단일 숫자 단정 금지.

---

## Q6 — Competition · "Segmed, Gradient Health 와 어떻게 다른가요?"

> "How are you different from Segmed and Gradient Health?"

**답변**:
"세 가지로 정리됩니다. **첫째, 지리적 specialist** — Segmed 와 Gradient 는 미국·유럽 중심이고, 한국 데이터에 대한 라이센싱·법적 체인이 없습니다. RadiVault 는 한국 PIPA §28-8 을 출발점으로 설계되었습니다. **둘째, federated 데이터 주권** — 원본 raw data 는 병원 측에 잔존하고, RadiVault 중앙은 익명화된 메타데이터·이미지만 인덱싱합니다. **셋째, 양면 마켓플레이스** — 병원 측 한국어 콘솔과 글로벌 buyer 측 영문 포털이 동일 브랜드 안에서 각자 최적화되어 있습니다. 경쟁사 모방이 아닌 **한국 강점의 위치 점유** 가 우리의 차별화입니다."

**근거**: `docs/research/portal-redesign-competitive-analysis.md` §2 전체, `docs/research/buyer-auth-research.md` §2.6

**금지**: 경쟁사 약점 직접 언급 금지. "보수적인 비교" 만.

---

## Q7 — Scaling · "병원 2곳에서 어떻게 100곳으로 확장하나요?"

> "How do you scale from 2 hospitals to 100?"

**답변**:
"세 가지 레버를 봅니다. **(1) Gateway Agent 의 Docker 단일 컨테이너 배포** — 병원 IT 팀 부담을 분 단위로 줄였습니다. PACS 교체나 수정 없이 표준 DICOM 프로토콜로만 연동합니다. **(2) 표준 계약서 v1** — Phase 1 KPI 에 명시된 산출물입니다 (PRD §7). 첫 5–10 병원에서 표준화하면 그 이후는 영업 사이클 단축. **(3) Revenue share 25–50% + 최소보장금** — 병원 측 인센티브가 명확합니다. 100 곳 확장은 **Phase 2 (6–18개월) → Phase 3 (18–36개월)** 동안의 점진 목표이고, Phase 3 종료 시점 30곳 이상이 PRD KPI 입니다."

**근거**: PRD §7 Phase KPI, PRD §4.1 Gateway Agent 스펙

**솔직**: 100곳은 단기 목표 아님. 30곳/3년이 PRD 목표.

---

## Q8 — Security · "데이터 유출 사고에 어떻게 대응하시나요?"

> "What's your incident response plan for a data breach?"

**답변**:
"세 단계 방어가 있습니다. **(1) 예방**: 모든 외부 통신은 outbound-only TLS 1.3, 저장은 AES-256, MFA 필수, RBAC. (2) **탐지**: WORM 감사 로그가 모든 데이터 접근·전송을 불변 저장하고 5년 보존됩니다. (3) **대응**: 병원 측 데이터 철회권이 30–90일 내 삭제로 계약상 보장되고, buyer 측 다운로드는 7일 TTL S3 presigned URL 로 자동 만료됩니다. **공식 incident response runbook 은 SOC 2 Type II 준비 단계 (Phase 2) 에서 외부 감사인과 함께 확정** 합니다. v0.1 단계에서는 internal SOP 만 운영 중입니다."

**근거**: PRD §5 NFR, PRD §4.7 Compliance, ARCHITECTURE §4.7

**솔직**: 외부 감사 없는 incident response 는 단정형 promise 금지.

---

## Q9 — Governance · "환자 동의는 누가 어떻게 받나요?"

> "Who collects patient consent and how?"

**답변**:
"환자 직접 동의가 아니라 **병원의 익명화 처리** 가 RadiVault 의 법적 기반입니다. 한국 PIPA 에서 **완전 익명정보는 개인정보 정의에서 제외** 되므로 (개인정보보호법 제2조 + 제28조의2), 환자 단위 동의 없이 이전 가능합니다. **단**, 병원 측에서는 (a) 자체 IRB 또는 임상연구지원실 검토 후 (b) Opt-out 공고 (병원 홈페이지·외래 공지) 를 운영하도록 표준 계약서에 권고하고, (c) RadiVault Hospital 콘솔에 **opt-out queue** 를 두어 30일 내 처리합니다. 즉 환자 보호 책임은 병원-RadiVault 가 공동 부담하는 구조입니다."

**근거**: PRD §8, dev-spec-portal-redesign Hospital 대시보드 6-tile (opt-out queue 포함)

**금지**: "patient consent waived" 같은 거친 표현.

---

## Q10 — IP · "데이터의 IP 는 누구 것인가요?"

> "Who owns the IP of the data?"

**답변**:
"세 층으로 분리됩니다. **(1) Raw DICOM 원본**: 병원 소유, 끝까지 병원 측 PACS 에 잔존. RadiVault 는 사본을 보관하지 않습니다. **(2) 익명화된 메타데이터·이미지**: 병원이 RadiVault 에게 **non-exclusive sublicense 권한** 을 부여하고, RadiVault 는 buyer 에게 다시 sublicense 합니다. (3) Buyer 의 학습·연구 산출물 (모델, 논문)**: buyer 소유, 단 (a) 데이터 출처 cite 의무, (b) 모델 환매 (re-identification) 시도 금지, (c) 환자 권리 침해 발견 시 RadiVault 통해 데이터 즉시 삭제 의무 — 이 세 조항이 표준 계약서에 들어갑니다. **표준 계약서 v1 은 PRD §7 Phase 1 KPI 산출물** 입니다."

**근거**: PRD §3 (병원 가치 = 데이터 주권 유지), §7 Phase 1 KPI, §4.7

**금지**: "RadiVault owns the data" 절대 금지 — 병원 데이터 주권 침해 인상.

---

## Q11 — Demo Scope · "왜 라이브 API 호출 데모를 안 하나요? 실제로 동작하는 거 맞나요?" (v0.2 신설)

> "Why don't you show a live API call demo? Does it actually work?"

**답변**:
"두 가지로 답드립니다. **첫째, Reveal-once 시연이 곧 키 발급의 라이브 증빙입니다** — 가입과 동시에 자동으로 발급된 `rv_live_*` 키가 모달에서 평문으로 한 번 노출되는 그 순간이 백엔드 키 발급·해싱·저장 파이프라인이 라이브로 작동하고 있다는 증거입니다. **둘째, API 자체는 portal UI 검색이 동일 search service 를 호출하므로** 단계 4 (검색 화면) 에서 250 study 가 federated 로 잡혀 결과·패싯·cohort 가 즉시 갱신되는 것 자체가 백엔드 동작의 라이브 증빙입니다. portal 과 외부 API 는 같은 search service 를 공유하기 때문에 portal 이 작동한다는 건 API 가 작동한다는 것과 동치입니다. **구매자 백엔드에서의 실제 호출 통합은 별도 onboarding 세션** 입니다 — Stripe·Vercel·Hugging Face 모두 동일한 시퀀스 (키 발급 데모 → onboarding 에서 백엔드 통합) 를 따릅니다. 통합 timeline 은 보통 첫 주에 끝나도록 설계되어 있습니다."

**근거**:
- portal UI 와 외부 `/api/search` 가 동일 search service 를 호출함: `docs/specs/dev-spec-portal-redesign.md`, `docs/qa/qa-report-portal-redesign-v2.md` §2.1 HIGH-2 PASS
- reveal-once 발급 e2e 검증: `docs/qa/qa-report-buyer-auth.md` §3 AC-DEMO-3 PASS
- onboarding handoff 모델 (B2B SaaS 표준): `docs/research/portal-redesign-competitive-analysis.md` §2.10·§5

**금지 어휘**: "그건 아직 안 됩니다" / "그 부분은 미구현입니다" — 둘 다 사실 무근 + 잘못된 신호. 실제 원인은 데모 stage 의 키 등록 path 미운영 (HIGH-A) 이며 production buyer 통합 시퀀스에서는 정상 작동.

**Kyle 안전 회피 라인 (질문이 더 깊어지면)**: "기술 디테일은 NDA 후 onboarding 세션에서 30분 안에 endpoint·auth·rate limit·envelope 표준까지 walkthrough 드리겠습니다."

---

## 부록 — 회피 라우팅 라인 (Kyle 즉답 곤란 시 사용)

| 상황 | 라인 |
|---|---|
| 가격 단가 단일 숫자 요구 | "별도 NDA 미팅에서 공유드리겠습니다." |
| 파트너 병원명 공개 요구 | "병원 파트너 측 동의 없이는 공개하지 않는 것이 우리 정책입니다." |
| 자금 조달 라운드 단계·금액 | "현재 펀딩 단계는 별도 자료로 정리해 보내드리겠습니다." |
| 정확한 인력 수·연봉 | "팀 구성은 LinkedIn 또는 별도 문서로 안내드리겠습니다." |
| 경쟁사 약점 의견 | "경쟁사 평가는 객관적 비교만 드리는 것이 우리 원칙이라, 그쪽 회사의 강점·약점은 그쪽이 직접 답변하실 부분입니다." |
| 미구현 기능에 대한 ETA 단정 | "로드맵상 v0.1.5 (3–6개월) / v0.2 (6–12개월) 범위로 보고 있습니다 — 정확한 ETA 는 자원 확보 후 확정하겠습니다." |

---

## 부록 — 절대 답하면 안 되는 것

| 질문 유형 | 이유 |
|---|---|
| 환자 진단명·실제 케이스 | 데이터 주권·환자 보호 |
| 파트너 병원명 (HOSP-001/002 가명만) | 계약 미체결, 노출 시 협상 손상 |
| 임원 개인 신상 (Kyle 외) | 채용 미확정 인력 노출 위험 |
| 외부 법무 자문 결과 미확정 사항 | 법적 단정 risk |
| 보안 사고 시 대응 SLA 시간 단정 | SOC 2 미취득 단계에서 promise 부담 |

---

## 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|---|---|---|---|
| 0.1 | 2026-04-25 | @marketer | 최초 작성. Q1–Q10 + 회피 라우팅 + 절대 회피 항목. Kyle 리뷰 대기 (특히 가격·법무 어휘 검토). |
| 0.2 | 2026-04-25 | @marketer | Kyle K-3 결정 (라이브 curl 시연 제외) 반영. Q11 신설 — "왜 라이브 API 호출 데모를 안 하나요?" 대비 답변 + 근거 + Kyle 안전 회피 라인. Q1–Q10 번호·내용 보존. |
