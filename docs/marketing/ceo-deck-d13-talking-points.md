# CEO Deck — D-13 Talking Points (시연 발화 스크립트)

> **Status**: Draft v0.2 · **작성자**: @marketer · **작성일**: 2026-04-25
> **§0 Changelog (v0.2)**: Kyle K-3 결정 반영 — 구 §6 (curl `/api/search` 라이브 호출) 발화 라인 제거. 10 → 9단계 재번호. "API 호출" 가치 메시지는 §5 (reveal-once) 발화에 흡수 (Stripe-style dual-credential 모델 메시지 보존). 위기 발화 섹션에 "왜 라이브 curl 안 보여주나요?" 대비 라인 신설.
> **사용처**: Kyle 본인의 시연 무대 발화. 각 슬라이드/장면 전환 시 1–2 문장으로 그대로 읽어도 자연스럽도록 작성.
> **언어 정책**: 한국어 본문 + 영문 병기. 영문 카피는 무대 청중이 한국어 미해득자일 경우 그대로 발화 가능.
> **근거**: `docs/prd.md` §1·§3·§7, `docs/qa/qa-report-buyer-auth.md` §6, `docs/qa/qa-report-portal-redesign-v2.md` §2.1, `docs/research/portal-redesign-competitive-analysis.md` §2.10·§5
> **컴플라이언스 어투**: 한국 PIPA(개인정보보호법) 제15조·제17조·제28조의8, 정보통신망법 제50조, OWASP Argon2id 표준만 인용. "certified/guaranteed/HIPAA-compliant" 단정형 금지. "designed to meet … standards" 보수형 사용.
> **외부 배포 가능 여부**: 무대 외 배포는 Kyle 승인 후. 본 문서는 leave-behind 가 아닌 화자용.

---

## 0. 무대 진입 — 30초 오프닝

> **한**: "안녕하세요, RadiVault 의 Kyle Jeon 입니다. 오늘 보여드릴 것은 한국 의료영상 데이터를 전 세계 AI 기업이 합법적으로 받을 수 있도록 만든 **B2B 데이터 마켓플레이스** 의 첫 작동 데모입니다. 슬라이드 없이 실제 제품을 13분 안에 끝까지 보여드립니다."
>
> **EN**: "Good morning. I'm Kyle Jeon, founder of RadiVault. What you're about to see is a working B2B data marketplace that delivers Korean medical imaging data to global AI teams under Korean PIPA Article 28-8 cross-border standards — the entire flow, end to end, in 13 minutes."

**의도**: 슬라이드 부재를 약점이 아닌 차별점으로. "working product" 강조.

---

## 1. 홈페이지 도착 — 가치 제안 + Sign in

> **한**: "이게 RadiVault 의 첫 화면입니다. 헤드라인은 **'한국의 의료영상 데이터, 글로벌 AI 에 컴플라이언트하게.'** 우측 상단의 **Sign in** 으로 30초 안에 실제 검색까지 들어갑니다."
>
> **EN**: "This is the RadiVault landing page. The headline reads: *Korea's medical imaging data, compliantly delivered for global AI.* The Sign in button on the upper right takes us inside in under 30 seconds."

**시각 포인트**: 헤로 우측의 실제 `/search` 스크린샷을 손가락으로 가리키며 "이게 곧 보실 그 화면입니다."

---

## 2. /signup — 신규 buyer 가입 (PIPA 4종 분리 동의)

> **한**: "신규 가입 화면입니다. 한국어 모드로 보시면 **개인정보 수집·이용 / 제3자 제공 / 국외이전 / 광고 수신** 네 가지 동의가 분리되어 있습니다. 이건 한국 개인정보보호법 제15조·제17조·제28조의8, 그리고 정보통신망법 제50조를 한 화면에서 만족시키는 구조입니다. 광고 수신만 선택, 나머지 셋은 필수입니다."
>
> **EN**: "This is the signup screen. In Korean mode you'll see four separate consent checkboxes — collection, third-party transfer, cross-border transfer, and marketing — each mapped to a specific clause of Korean privacy law. Marketing is optional; the other three are required. This is what regulators expect from a serious data broker."

**의도**: 컴플라이언스를 디자인의 일부로 보여줌. 단정형 어휘 금지 — "이렇게 설계되어 있다(designed)" 중심.

---

## 3. /signin — 데모 buyer 로그인

> **한**: "로그인 자체는 평범한 email + password 입니다. 보이지 않는 부분에서 **OWASP 권고대로 Argon2id (m=19MiB, t=2, p=1)** 로 해싱하고, 세션은 **HttpOnly + SameSite cookie** 로만 발급합니다. 화면 어디에도 비밀번호가 평문으로 새지 않는다는 걸 QA 가 grep 으로 확인했습니다."
>
> **EN**: "Sign-in is plain email and password — but underneath, passwords are hashed with Argon2id at OWASP-recommended parameters, and sessions ride on HttpOnly + SameSite cookies. Our QA verified zero plaintext password leakage by grepping the entire codebase."

**시각 포인트**: 로그인 직후 자동 라우팅. "URL 보세요, 토큰이 URL 에 노출되지 않습니다."

---

## 4. /search — 250 study + 2병원 federated 필터

> **한**: "검색 화면입니다. 지금 **두 병원에서 federated 로 250 study** 가 잡혀 있습니다 — 본병원 150 건, 튼튼병원 100 건. 좌측 패싯에서 modality, body part, 연령대로 필터링하고, 우측 cohort sidebar 가 'From 2 hospitals' 라고 알려주는 게 핵심입니다. 이게 RadiVault 의 first-class metric, '1 검색 = N 병원 집계' 입니다. 그리고 이 화면이 곧 검색 백엔드의 라이브 증빙입니다 — portal UI 가 호출하는 search service 가 동일하므로 이 화면이 작동한다는 건 백엔드가 작동한다는 뜻이기도 합니다."
>
> **EN**: "Search. We have 250 studies federated across two hospitals right now — 150 and 100 respectively. The left pane is faceted filtering, the center is the result table, and the right pane shows the cohort summary with a 'From 2 hospitals' badge. That cross-hospital aggregation is RadiVault's first-class metric. And this screen itself is the live evidence of our search backend — the portal UI calls the very same search service, so a working screen means a working backend."

**의도**: federated 가 "vapor" 가 아니라 실제로 두 격리된 데이터 소스에서 합쳐진 결과임을 강조. + 라이브 백엔드 증빙을 portal UI 자체로 흡수.

---

## 5. /account — API key 발급 + reveal-once (dual-credential 메시지 흡수, v0.2 강화)

> **한**: "이제 API 접근입니다. **Account** 페이지에서 가입과 동시에 자동으로 발급된 API key 가 보이는데, **딱 한 번만 평문으로 노출되고** 그 후로는 마스킹 처리됩니다. 이게 Stripe 스타일 reveal-once 순간입니다. 구매자는 이 키를 복사해서 자기 백엔드에서 `/api/search` 를 호출합니다 — **Web UI 는 사람용, API key 는 ML 파이프라인용** 의 dual-credential 모델은 Stripe·Vercel·Hugging Face 가 모두 채택한 B2B SaaS 표준입니다. 오늘은 키 발급까지 시연하고, 실제 API 호출은 구매자 백엔드 셋업이 전제라 별도 onboarding 세션입니다. 분실 시 재발급은 가능하지만 기존 키는 즉시 무효화됩니다."
>
> **EN**: "Account page. Each buyer gets one API key auto-issued at signup, revealed exactly once — same reveal-once pattern as Stripe. This is the Stripe-style reveal-once moment — buyers see their key here, copy it, and call our /api/search from their own backend. Today we'll show the reveal; live API calls require their backend setup, so we handle integration in a separate onboarding session. Web UI is for humans, API key is for ML pipelines — the standard two-credential model used by Stripe, Vercel, Hugging Face. Lose the key, you rotate it; the old one is invalidated immediately."

**시각 포인트**: 키 형식 `rv_live_*` 를 손가락으로. "Stripe 의 `sk_live_*` 와 같은 prefix 컨벤션입니다."

**의도 (v0.2)**: 구 §6 의 "프로그래매틱 호출" 가치 메시지를 이 단계에 흡수. "라이브 호출을 안 하는 것이 약점이 아니라 onboarding handoff 라는 정상 시퀀스" 라는 톤.

---

## 6. 2병원 federated — Cross-tenant 격리 시연 (구 §7)

> **한**: "여기서 매우 중요한 부분입니다. 본병원과 튼튼병원은 각각 다른 bearer token 으로 분리되어 있습니다. 같은 buyer 가 두 병원의 데이터를 한 화면에서 보지만, 한쪽 병원이 다른 쪽 병원의 raw data 에는 절대 접근할 수 없습니다. **격리는 portal 측 환경변수 + central 측 매핑, 이중으로 방어**되고, e2e 테스트가 hash prefix 가 다르다는 걸 매번 검증합니다."
>
> **EN**: "Critical detail. Each hospital has its own bearer token — Bon Hospital, Tunteun Hospital, fully separated. The buyer sees one merged search, but neither hospital can access the other's raw data. Isolation is enforced both at the portal layer via per-hospital env keys and at the central API layer, double-defended, with end-to-end tests verifying distinct hash prefixes on every commit."

**시각 포인트**: e2e 테스트 통과 메시지를 미리 띄워두면 강력. (`docs/qa/qa-report-portal-redesign-v2.md` §5 인용 가능)

---

## 7. /contact — PIPA 동의 기반 lead 수집 (구 §8)

> **한**: "마지막 lead 수집 채널입니다. Contact 폼에도 PIPA 동의 체크박스가 있습니다 — **수집 항목, 이용 목적, 보유 기간 1년** 을 명시했고, 클라이언트와 서버 양쪽에서 `consent: true` 만 통과시킵니다. 422 / 429 / 202 envelope 표준 응답까지 갖춰져 있어 외부 SI 가 통합하기에 친숙합니다."
>
> **EN**: "Contact form. Even here, PIPA consent is enforced — collection items, purpose, one-year retention, all spelled out. Both client and server reject submissions without explicit consent. Response envelopes follow the 422 / 429 / 202 standard so any SI partner can integrate cleanly."

---

## 8. EN/KR 토글 — 양언어 시연 (구 §9)

> **한**: "오른쪽 상단의 **EN | KR 토글** 입니다. 단순 번역이 아니라 한국어 페이지는 풋터에 사업자등록·대표자·고객센터 까지 한국 B2B 관습에 맞춰 별도 구성되어 있습니다. 이게 한국 병원 CTO·DPO 가 처음 보고 '실체 있는 회사' 라고 인식하는 첫 신호입니다."
>
> **EN**: "Top-right EN | KR toggle. This isn't a translation — Korean pages carry a Korean-style legal footer (corporate registration, CEO name, customer service line) because that's what Korean hospital CTOs and DPOs look for in the first three seconds. Without it, you're not a serious vendor."

**의도**: 단순 i18n 이 아니라 양면 마켓플레이스의 양 청중에 각각 최적화되어 있음을 강조.

---

## 9. 클로징 — 로드맵 + Ask (구 §10)

> **한**: "지금 보신 게 D-13 시점의 RadiVault 입니다. 다음 단계는 **Postgres 기반 영구 인증 저장소, AWS SES 이메일 인증, Stripe 정산, 그리고 추가 병원 온보딩** 입니다. 우리가 검증한 가설은 단순합니다 — **한국의 의료영상은 글로벌 AI 가 가지지 못한 다양성을 가지고 있고, 그 다양성을 컴플라이언트하게 흘려보낼 수 있는 회사가 지금 한국에 거의 없다.** 오늘 미팅 후속으로 [질문/제안] 을 부탁드립니다. 감사합니다."
>
> **EN**: "What you saw is RadiVault as of today, D-13. Next on the roadmap: a Postgres-backed auth store, AWS SES for email verification, Stripe-based revenue settlement, and onboarding additional hospitals. Our thesis is simple — Korean medical imaging carries diversity that global AI doesn't have, and almost no one in Korea today can route that diversity compliantly. The follow-up I'd ask of you is [tailor per audience]. Thank you."

**Ask 가변 부분 (청중별 1줄 교체)**:
- 투자자: "a 30-min follow-up to discuss seed terms" / "30분 후속 미팅으로 시드 조건을 논의"
- 병원 파트너: "a 60-min site visit to your IT/legal team next week" / "다음 주 귀 병원 IT·법무팀 방문"
- 글로벌 AI 구매자: "a paid pilot dataset of 1,000 studies under NDA" / "NDA 하 1,000 study 유료 파일럿"
- 정부 규제기관: "a closed-door technical briefing on de-id chain of custody" / "비공개 기술 브리핑 — de-id chain of custody"

---

## 시연 중 위기 발화 (network/screen 문제 발생 시)

| 상황 | 발화 |
|---|---|
| 로그인 실패 | "데모 환경 일시 지연입니다. 1초만 기다려주세요." / "Brief demo lag — one moment." |
| 검색 결과 0건 | "캐시 초기화 중입니다. 데이터 자체는 250 study 가 인덱싱되어 있습니다." / "Cache warming up — 250 studies are indexed in the database." |
| 화면 freeze | "다시 시작해도 같은 250 study 풀로 들어갑니다 — 상태가 모두 영속됩니다." / "Restart lands on the same 250-study pool — state is fully persisted." |
| **(v0.2 신설) 청중 질문 — "왜 라이브 API 호출 안 보여주나요?"** | "Reveal-once 시연 자체가 키 발급의 라이브 증빙이고, portal 검색이 동일 search service 를 호출하므로 백엔드 동작은 단계 4 에서 이미 검증됐습니다. 구매자 백엔드 통합은 별도 onboarding 세션으로 분리해 둔 정상 시퀀스입니다." / "The reveal-once flow itself is the live proof of key issuance, and the portal search you saw in step 4 calls the same backend service — so the backend is already verified. Buyer-side integration is a separate onboarding session by design, not a gap." |

---

## 시연 후 30초 회고 (Q&A 직전)

> **한**: "정리하면 — **(1) 자동화된 PIPA 컴플라이언스 / (2) 두 병원 federated 격리 / (3) Stripe 급의 dual credential 모델 / (4) 양언어 B2B UI**. 이 네 가지는 데모 데이터가 아니라 production code 입니다. 질문 받겠습니다."
>
> **EN**: "To recap — (1) automated PIPA compliance, (2) two-hospital federated isolation, (3) Stripe-grade dual-credential model, (4) bilingual B2B UI. None of this is demo scaffolding; it's production code. Questions?"

---

## CTA (시연 후 followup)

→ `docs/marketing/ceo-deck-d13-followup-email.md` 의 청중별 템플릿 사용.

---

## 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|---|---|---|---|
| 0.1 | 2026-04-25 | @marketer | 최초 작성. 골든패스 10단계 + 위기 발화 + 청중별 ask 가변 라인. Kyle 리뷰 대기. |
| 0.2 | 2026-04-25 | @marketer | Kyle K-3 결정 반영. 구 §6 (curl 라이브 호출) 발화 제거. §5 에 dual-credential 가치 메시지 흡수 (Stripe-style reveal-once moment + onboarding handoff). 단계 6–9 재번호. 위기 발화 섹션에 "왜 라이브 curl 안 보여주나요" 대비 라인 신설. 시연 후 30초 회고는 그대로 유지 (4가지 메시지 변동 없음). |
