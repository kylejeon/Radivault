# RadiVault — One Pager (CEO Deck D-13)

> **Status**: Draft v0.2 · **작성자**: @marketer · **작성일**: 2026-04-25
> **§0 Changelog (v0.2)**: Kyle K-3 결정 반영 — 데모 flow 표현에서 "Live API call" → "API key issuance via reveal-once flow" 로 다운그레이드. Demo flow 단계수 추상화 ("9-step golden path" 명시). Differentiation 섹션의 "Stripe-style developer experience" 메시지 보존.
> **레이아웃**: A4 1장, 영문 우선 + 핵심 문구 한국어 병기. leave-behind 인쇄 가능.
> **근거**: `docs/prd.md`, `docs/qa/qa-report-buyer-auth.md`, `docs/qa/qa-report-portal-redesign-v2.md`, `docs/research/portal-redesign-competitive-analysis.md`
> **외부 배포**: Kyle 승인 후 가능. 파트너 병원명·구체 가격은 포함하지 않음.

---

## RadiVault

**Korea's medical imaging data, compliantly delivered for global AI.**
*한국의 의료영상 데이터를 글로벌 AI 에 컴플라이언트하게 전달합니다.*

---

### Problem · 문제

Global AI and pharma teams need **Korean diversity** in medical imaging — population characteristics, equipment mix, and reading conventions distinct from US/EU datasets. But cross-border transfer of Korean medical data is gated by **PIPA Article 28-8** and the de-identification chain that comes with it. Today there is no production-grade route from a Korean PACS to a global AI buyer.

> 글로벌 AI·제약사는 한국 의료영상의 인구·장비·판독 다양성을 필요로 한다. 그러나 한국 의료데이터의 국외이전은 개인정보보호법 제28조의8 과 익명화 체인의 규제를 받는다. 이 두 요건을 production-grade 로 풀어낸 사업자는 현재 한국에 사실상 부재.

---

### Solution · 해결

**Model 3 Hybrid** federated marketplace: Zone 1 (Hospital Gateway, on-premise) → Zone 2 (RadiVault Central, anonymized index) → Zone 3 (Buyer Portal, search/order/download). Hospitals retain raw data sovereignty; buyers receive only anonymized DICOM that has passed three layers of de-identification (PHI tag scrubbing per DICOM PS3.15 Annex E + burn-in OCR masking + 3D defacing).

> 본병원·튼튼병원이 각각 자기 PACS 옆 Gateway 에서 1차 익명화, RadiVault 중앙에서 인덱싱·검증, 글로벌 buyer 는 포털에서 검색·주문·다운로드. 원본 raw data 는 끝까지 병원 측에 잔존.

---

### Demo Flow · 데모 흐름 (9-step golden path)

The D-13 demonstration walks an audience end-to-end through the live product in roughly 7 minutes, leaving 5+ minutes for Q&A. The 9 steps:

1. Landing page — value proposition, trust ladder, Sign in.
2. `/signup` — Korean PIPA four-way consent separation (collection, third-party transfer, cross-border, marketing).
3. `/signin` — Argon2id-hashed credentials, HttpOnly + SameSite session cookies.
4. `/search` — 250 studies federated across two hospitals, faceted filtering, "From 2 hospitals" cohort badge. *(This screen is itself the live evidence of the search backend, since the portal UI calls the same search service that the API exposes.)*
5. `/account` — **API key issuance via reveal-once flow** (Stripe-style `rv_live_*` prefix, plaintext exactly once, then masked; rotation invalidates the prior key immediately).
6. Cross-tenant isolation — buyer sees a merged view, but neither hospital can access the other's raw data; double-defended at portal and central layers, e2e-tested per commit.
7. `/contact` — PIPA-consent-gated lead capture with 422 / 429 / 202 envelope standard.
8. EN / KR toggle — bilingual UI with a Korean-style legal footer for hospital DPOs.
9. Roadmap and ask — v0.1.5 / v0.2 plan plus an audience-tailored single-line ask.

> Live programmatic API calls from a buyer backend are handed off to a separate week-1 onboarding session by design — the same buyer-integration sequence Stripe, Vercel, and Hugging Face use.

---

### Traction · 현재 상태 (2026-04-25)

| 지표 | 값 | 출처 |
|---|---|---|
| Federated hospitals in working demo | **2** (Bon, Tunteun) | progress.txt |
| Studies indexed (TCIA-seeded) | **250** | demo seed |
| Buyer-auth full pipeline (Argon2id, PIPA 4-way consent, reveal-once API key issuance) | **READY-TO-DEMO** | `docs/qa/qa-report-buyer-auth.md` |
| Portal redesign (23 components, 10+ routes, EN/KR) | **READY-TO-DEMO** | `docs/qa/qa-report-portal-redesign-v2.md` |
| Test pass rate | **158 / 158** (vitest 81 + pytest 39 + playwright 38) | qa-report-portal-redesign-v2 §8 |
| Cross-tenant isolation (HOSP-001 vs HOSP-002) | e2e-verified per commit | qa-report-portal-redesign-v2 §5 |
| Pilot hospital contracts signed | **TBD** — pre-revenue, demo phase |
| Paid buyers | **TBD** — pre-revenue, demo phase |

**Numbers we do not claim**: contracted partners, ARR, FDA-cleared customers, hospital count beyond 2. Anything not in the table above is not yet true.

---

### Compliance · 규정 준수

| Standard | Posture | Evidence |
|---|---|---|
| Korean PIPA (개인정보보호법) §15 collection consent | Implemented in signup form (KR mode) | `docs/specs/dev-spec-buyer-auth.md` §FR-AUTH-1 |
| Korean PIPA §17 third-party transfer consent | Implemented as separate checkbox | dev-spec-buyer-auth §11.1 |
| Korean PIPA §28-8 cross-border transfer | Designed to align — anonymized data only crosses borders | PRD §8 |
| Korean Information Network Act §50 (마케팅 수신 동의) | Implemented as separate optional checkbox | dev-spec-buyer-auth §FR-AUTH-1 |
| OWASP Argon2id password hashing (m=19 MiB, t=2, p=1) | Implemented | qa-report-buyer-auth §3 (AC-AUTH-3.x PASS) |
| Session: HttpOnly + SameSite cookie | Implemented | qa-report-buyer-auth §3 (AC-AUTH-7.2) |
| HIPAA Safe Harbor de-identification | Designed to align (Safe Harbor + Expert Determination path) | dev-spec-portal-redesign §FR-HP-8 |
| SOC 2 Type II | **In preparation** (Phase 2 target) | PRD §7 |
| ISO 27001 | **Aligned** (formal cert Phase 3 target) | PRD §7 |

> 보수형 어휘 사용: "designed to meet … standards", "in preparation". 단정형 ("HIPAA-compliant", "certified") 미사용.

---

### Differentiation · 차별점 (vs Segmed, Gradient Health)

1. **Korean imaging specialist** — 미국·유럽 데이터 위주의 글로벌 경쟁사가 가지지 못한 한국 환자 풀, 한국 장비 다양성, 한국 판독 컨벤션.
2. **Federated by default** — 원본 raw data 는 병원에 잔존. 경쟁사 다수가 사용하는 "central data lake" 모델 대비 데이터 주권 우위.
3. **PIPA-native** — 한국법으로 설계됨. 글로벌 사업자가 사후에 PIPA 매핑하는 것과 다른 출발점.
4. **Stripe-style developer experience** — reveal-once API key issuance with `rv_live_*` prefix convention, dual-credential model (web sign-in for humans, API key for ML pipelines), 422 / 429 / 202 envelope standard. Familiar to any team that has integrated Stripe, Vercel, or Hugging Face.

---

### Ask · 요청

청중별 1줄 (Kyle 발화):
- **Investor**: 30-min follow-up to discuss seed terms.
- **Hospital partner**: 60-min on-site with your IT and legal teams.
- **Global AI buyer**: NDA-gated paid pilot, 1,000 studies.
- **Regulator**: closed-door technical briefing on de-id chain of custody.

---

### Contact

Kyle Jeon · Founder & CEO · kylejeon83@gmail.com
RadiVault Inc. (incorporation in progress — Delaware C-corp pending)
Demo URL: TBD (provided per-meeting under NDA)

---

### Roadmap · v0.1.5 → v0.2 (2026 Q3–Q4)

- v0.1.5: PostgresAuthStore (currently in-memory), AWS SES email OTP, hard-delete cron (GDPR Art.17), CSV/Manifest download tooling.
- v0.2: Stripe Billing & revenue share settlement, OHIF DICOM viewer embed, Google Workspace SSO, hospital count 2 → 5–10.

---

| 버전 | 날짜 | 작성자 | 변경 |
|---|---|---|---|
| 0.1 | 2026-04-25 | @marketer | 최초 작성. PRD/QA 문서에서 검증된 수치만 인용. Kyle 리뷰 대기. |
| 0.2 | 2026-04-25 | @marketer | Kyle K-3 결정 반영. Demo flow 섹션 신설 (9-step golden path). 단계 5 표현을 "API key issuance via reveal-once flow" 로 다운그레이드, 라이브 API 호출은 onboarding handoff 로 명시. Differentiation 에 "Stripe-style developer experience" 4번 항목 추가 (가치 메시지 보존). Traction 표 'reveal-once API key' → 'reveal-once API key issuance' 명확화. |
