# Follow-up Email Templates — D-13 미팅 직후

> **Status**: Draft v0.2 · **작성자**: @marketer · **작성일**: 2026-04-25
> **§0 Changelog (v0.2)**: Kyle K-3 결정 반영 — 양 템플릿에서 "Live API integration" / "live API call" 등 라이브 호출 단정 표현 제거. "API key issuance demo + integration handoff in week 1" 으로 다운그레이드. 양 템플릿에 "30분 onboarding 일정" 라인 신설 ("Want to integrate? Schedule a 30-min onboarding").
> **목적**: 미팅 종료 직후 24시간 이내 발송할 follow-up 이메일 템플릿 2종.
> **언어 규칙**:
> - **Template A**: 영어. 글로벌 투자자 / 글로벌 AI 구매자 / 영어권 stakeholder 용.
> - **Template B**: 한국어. 한국 병원 파트너 / 한국 정부 규제기관 / 국내 투자자 용.
> **사용 원칙**:
> 1. 발송 전 Kyle 검토 필수 (특히 가격·자금 조달 단계 언급 부분).
> 2. 첨부 파일은 `ceo-deck-d13-onepager.md` 의 PDF 변환본만 (다른 내부 spec 미첨부).
> 3. 24시간 룰: 미팅 다음 영업일 오전까지 발송.
> 4. CC 라인 사용 금지 — 1:1 stakeholder 별 개별 발송.
> 5. 미팅에서 합의되지 않은 약속·수치 추가 금지.

---

## Template A — Investor / Global AI Buyer (English)

**Subject**: RadiVault — follow-up to our [today / yesterday / DATE] conversation

```
Dear [First name],

Thank you for the time today. I wanted to send a brief recap and the materials I promised on stage.

What we showed:
- A working federated marketplace across two Korean hospitals (Bon Hospital, Tunteun Hospital — internal codenames HOSP-001 and HOSP-002), 250 studies indexed end-to-end.
- Buyer signup with Korean PIPA four-way consent separation, OWASP Argon2id password hashing, HttpOnly + SameSite session cookies — designed to meet the standards regulators expect from a Korean data broker.
- Stripe-style dual-credential model: web sign-in for humans, plus API key issuance demo via the reveal-once flow (rv_live_* prefix, plaintext exactly once, then masked) for ML pipelines. Buyer-side backend integration is handed off in a week-1 onboarding session by design — the same sequence Stripe, Vercel, and Hugging Face use.
- Cross-tenant isolation between the two hospitals, double-defended at portal and central layers, verified by automated end-to-end tests on every commit.
- Bilingual portal (English / Korean) with hospital-side and buyer-side optimized for their respective audiences.

What we did not claim:
- We did not show contracted pilot revenue. We are pre-revenue.
- We did not show third-party security certifications (SOC 2, ISO 27001) — those are Phase 2 / Phase 3 targets, and we use the conservative phrasing "in preparation" / "aligned" until external audits complete.
- We did not name partner hospitals publicly. Internal codenames only until partners give written consent.

Attached:
- RadiVault one-pager (PDF) — problem, solution, current traction, compliance posture, ask.

[Pick ONE of the asks below — must match what you actually asked on stage]

Ask (Investor):
We discussed a 30-minute follow-up with your investment team to walk through the data room. I have availability [DATE A], [DATE B], [DATE C] — please let me know what works.

Ask (Global AI Buyer):
We discussed an NDA-gated paid pilot of 1,000 anonymized studies in the modality mix you mentioned. I will send our standard mutual NDA in a separate email today; once signed we can scope the pilot in a 60-minute working session.

Ask (Regulator):
We discussed a closed-door technical briefing on our de-identification chain of custody. I can prepare a 45-minute walkthrough at your office at a date of your choosing. Please let me know who else from your team should attend.

Want to integrate?
If your team wants to wire RadiVault into your own backend, schedule a 30-min onboarding with us — we walk through endpoint, auth, rate limits, and response envelopes, and you'll be calling the search API from your own service in week 1.

If anything in today's demo needs a deeper technical drill-down, I am happy to send the relevant engineering document under NDA — just reply with the topic.

Best regards,
Kyle Jeon
Founder & CEO, RadiVault Inc.
kylejeon83@gmail.com
[phone — TBD per Kyle]
```

**금지 사항 (체크 후 발송)**:
- [ ] 가격 단가·tier 표 미포함
- [ ] 구체 자금 조달 금액·valuation 단정 미포함
- [ ] 파트너 병원 실명 미포함
- [ ] "HIPAA-compliant" / "PIPA-certified" / "fully secure" 단정형 어휘 미포함
- [ ] Kyle 미합의 일정 미기재
- [ ] (v0.2) "Live API integration shown" / "live API call demonstrated" 등 단정형 미포함 — 실제로는 키 발급 데모까지만 진행했음

---

## Template B — 한국 병원 파트너 / 국내 stakeholder (한국어)

**제목**: RadiVault — [오늘 / 어제 / 날짜] 미팅 후속 안내

```
[직책] [이름]님께,

오늘 귀중한 시간 내어주셔서 진심으로 감사드립니다. 미팅 중 설명드린 내용과 약속드린 자료를 정리해 보내드립니다.

오늘 보여드린 내용:
- 본병원·튼튼병원 (내부 코드명 HOSP-001 / HOSP-002) 두 곳을 federated 로 묶어 250 study 까지 검색·주문 흐름이 작동하는 데모
- 한국 개인정보보호법 제15조·제17조·제28조의8, 정보통신망법 제50조의 4종 분리 동의를 회원가입 화면 자체에 구현
- OWASP 표준 Argon2id 비밀번호 해싱, HttpOnly + SameSite 세션 쿠키 — 한국 보안 감사에서 기대되는 기본 항목
- Stripe 스타일 dual-credential 모델 — 웹 로그인 (사람용) + API key 발급 데모 (reveal-once 흐름; rv_live_* prefix, 평문 1회 노출 후 마스킹). 구매자 백엔드와의 실제 통합은 첫 주 onboarding 세션에서 handoff 로 진행되는 정상 시퀀스 (Stripe·Vercel·Hugging Face 동일 모델).
- 두 병원 간 데이터 격리 — 한 병원 운영자가 다른 병원의 raw data 에 절대 접근할 수 없는 구조, e2e 테스트로 매 커밋마다 검증
- 한국어 / 영어 양언어 포털 — 한국 페이지는 한국 B2B 관습 (대표자·사업자등록·고객센터) 에 맞춰 별도 풋터 구성

오늘 단정해서 말씀드리지 않은 부분:
- 파일럿 병원 계약 매출은 아직 발생 전입니다.
- SOC 2 Type II, ISO 27001 같은 외부 인증은 Phase 2 / Phase 3 목표이고, 그 전까지는 "준비 중 (in preparation)" / "표준 정렬 (aligned)" 표현만 사용합니다.
- 파트너 병원명은 병원 측 서면 동의 전까지 외부에 공개하지 않습니다 — 본 메일에도 가명만 사용한 이유입니다.

첨부:
- RadiVault one-pager (PDF) — 문제 정의, 해결, 현재 상태, 컴플라이언스, 요청 사항.

[아래 후속 요청 중 ONE 만 선택 — 실제 미팅에서 합의된 것과 일치해야 함]

후속 요청 (병원 파트너):
다음 단계로, 귀 병원의 IT·법무·임상연구지원실 담당자와 60분 정도의 현장 미팅을 제안드립니다. RadiVault 의 Gateway Agent 가 귀 병원 PACS 와 어떻게 outbound-only 로 연동되는지, 표준 계약서의 데이터 주권·revenue share·철회권 조항을 함께 검토드릴 수 있습니다. [날짜 A], [날짜 B], [날짜 C] 중 가능한 시간을 알려주시면 일정 잡겠습니다.

후속 요청 (정부 규제기관):
PIPA §28-8 익명화 체인의 기술 증거 (DICOM PHI 태그 제거 → burn-in OCR 마스킹 → 3D defacing → WORM 감사 로그) 를 비공개 기술 브리핑 형태로 45분 안에 시연드릴 수 있습니다. 귀 부서에서 추가로 참석하실 분이 있으시면 함께 안내해 주시면 일정 조율하겠습니다.

후속 요청 (국내 투자자):
시드 라운드 관련 후속 30분 미팅을 제안드립니다. 데이터룸 (시장 분석, 경쟁 포지셔닝, 컴플라이언스 근거 문서) 을 NDA 체결 후 공유드릴 예정입니다.

통합 (Integration) 을 원하실 경우:
귀사 백엔드에서 RadiVault search API 를 직접 호출하는 통합을 검토하실 경우, 30분 onboarding 세션을 별도로 제안드립니다 — endpoint, 인증, rate limit, 응답 envelope 표준을 walkthrough 하고, 첫 주 안에 귀사 시스템에서 실제 호출이 가능한 상태가 되도록 셋업해드립니다.

오늘 데모 중 추가로 깊이 보고 싶으신 기술 영역이 있으시면 답신만 주시면 NDA 하 관련 엔지니어링 문서를 보내드리겠습니다.

감사합니다.

전용혁 (Kyle Jeon) 드림
RadiVault Inc. 대표
kylejeon83@gmail.com
연락처: [Kyle 결정 필요]
```

**발송 전 체크**:
- [ ] 병원명 가명 (HOSP-001 / HOSP-002) 만 사용
- [ ] revenue share 구체 % 단정 미포함 (계약 협상 전)
- [ ] 외부 인증 단정 어휘 미포함 ("준비 중" / "정렬" 만)
- [ ] 사업자등록번호·주소·전화번호는 Kyle 결정 후 (`docs/specs/dev-spec-portal-redesign.md` Q8 동일 미결)
- [ ] Kyle 미합의 일정·약속 미기재
- [ ] 경쟁사 (Segmed, Gradient Health) 비방 표현 미포함
- [ ] (v0.2) "라이브 API 호출 시연됨" 등 단정형 미포함 — 실제로는 키 발급까지만 데모

---

## 부록 — 발송 운영 SOP

### 시간 룰
- 미팅 종료 후 **24시간 이내** (다음 영업일 오전 11시 전).
- 24시간 초과 시 첫 문장에 "회신이 늦어 죄송합니다" 추가.

### 전송 채널
- **Primary**: 1:1 이메일.
- **Secondary**: 미팅 중 LinkedIn 연결 합의가 있었으면 LinkedIn 메시지로도 한 번 더.
- **금지**: SMS, 카카오톡 (해당 채널이 미팅에서 명시적 합의된 경우 제외).

### CC / BCC
- **CC 금지** — 1:1 stakeholder 별 개별 발송. 같은 회사 다인일 경우에도 1:1 분리 발송 후 본문에 "[이름]님께도 별도로 동일 내용 보내드렸습니다" 명시.
- **BCC 금지** (Kyle 본인의 자기 BCC 외).

### 첨부 정책
- **허용**: `ceo-deck-d13-onepager.pdf` (one-pager 의 PDF 변환).
- **NDA 후만**: dev-spec, qa-report, research, 시연 비디오.
- **절대 금지**: progress.txt, .env.local 발췌, 데모 자격증명, 파트너 병원 실명, 가격 단가표, 자금 조달 텀시트.

### 후속 미팅 일정 제시
- **3 옵션 룰**: [날짜 A], [날짜 B], [날짜 C] 형태로 3개 제시 (받는 사람이 거꾸로 제안하기 부담스러우면 자연스럽게 선택).
- 각 옵션은 미팅 후 7~14 영업일 안.

### 트래킹
- 발송한 follow-up 은 별도 spreadsheet 또는 CRM 에 기록 (보낸 날짜 / 받는 사람 / 회사 / ask 종류 / 회신 여부 / 회신 받은 날짜 / 다음 행동).
- 7 영업일 회신 없으면 한 번 nudge.
- 14 영업일 회신 없으면 cold lead 처리, 분기마다 newsletter 만 발송.

### Slack / 내부 알림
- 외부 발송 후 Kyle 만 보는 internal log 에 "발송 완료 + ask 종류" 한 줄 기록.
- 외부 채널 (회사 내부 Slack) 미팅명·stakeholder 명 노출 금지.

---

## 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|---|---|---|---|
| 0.1 | 2026-04-25 | @marketer | 최초 작성. Template A (영문 투자자/구매자) + Template B (한국어 병원 파트너) + 운영 SOP. Kyle 리뷰 대기 (특히 ask 가변 라인의 가격·일정 부분, 본문 전화번호·법인 주소). |
| 0.2 | 2026-04-25 | @marketer | Kyle K-3 결정 반영. 양 템플릿의 dual-credential 설명에서 "live API call" 등 라이브 호출 단정 표현 → "API key issuance demo + week-1 onboarding handoff" 다운그레이드. 양 템플릿에 "Want to integrate? Schedule a 30-min onboarding" 라인 신설. 발송 전 체크리스트에 라이브 호출 단정 금지 항목 추가. |
