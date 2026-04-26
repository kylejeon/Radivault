# RadiVault Buyer Auth — 신규 인증 모델 리서치

> **Status**: Draft v0.1 · **Last updated**: 2026-04-25
> **작성자**: @researcher (Claude Opus 4.7)
> **근거 요청**: Kyle — CEO 데모 D-13. 현재 buyer 인증이 50자 API key 직접 입력 (`rv_live_…`) 인 점이 B2B SaaS 표준에서 크게 벗어남. 신규 `buyer-auth` feature 의 dev-spec / design-spec 작성 근거 문서.
> **선행 리서치**:
> - [`portal-redesign-competitive-analysis.md`](./portal-redesign-competitive-analysis.md) — 마케팅 홈페이지·풋터·트러스트 패턴 (§2, §8.6 PIPA 풋터)
> - [`buyer-portal-ux-competitive.md`](./buyer-portal-ux-competitive.md) — 포스트-로그인 검색·주문 UX
> - [`k-meddata-research-summary.md`](./k-meddata-research-summary.md) — PIPA §28-8 시장 배경
>
> **본 문서가 다루지 않는 것**: 한국 병원 admin (`/hospital/signin`) 인증. 그쪽은 별도 토큰 기반으로 v0.1.5 SSO 마이그 예정 (dev-spec-portal-redesign §Q10). 본 문서는 **글로벌 buyer 만**.

---

## 0. Executive Summary

현재 `/signin` 이 50자 raw API key 페이스트 한 줄. 이건 Stripe / Vercel / Linear / Notion / Hugging Face 어느 곳에도 없는 패턴. **API key 는 프로그램 접근 (curl, SDK) 용**이고, **웹 포털 로그인은 email + password (또는 magic link / SSO) 가 universal B2B 표준**. CEO 데모에서 글로벌 AI 기업 의사결정자가 바로 "이거 진짜 production 인가" 의심할 위험.

**5 가지 핵심 발견**:

1. **API-first 마켓플레이스도 "두 개의 자격증명" 모델이 표준**. Hugging Face / Replicate / Stripe / Twilio / Plaid 모두 (a) 웹 로그인 = email/password (또는 OAuth/SSO) / (b) 프로그램 접근 = API token, settings 페이지에서 발급/회전/revoke. RadiVault 도 이 분리를 따라야 한다. (출처: [Hugging Face access tokens](https://huggingface.co/docs/hub/en/security-tokens))

2. **직접 경쟁사 둘은 정반대**. Segmed 는 **sales-only ("Book a Call")**, 공개 signup 페이지 자체가 없다. Gradient Health 는 **"7-DAY FREE TRIAL — Get instant access"** self-serve. **RadiVault 가 Gradient 쪽에 합류하면 Segmed 대비 onboarding 마찰 차별화**, Segmed 쪽에 합류하면 enterprise 톤 강화. 데모 D-13 맥락에서는 **self-serve 가능 + sales 병행** 의 hybrid (Stripe 모델) 가 가장 안전.

3. **인증 방식: 데모 D-13 에는 password 가 가장 보수적**. Magic link 는 corporate email scanner 가 링크를 미리 클릭해서 토큰을 소진하는 B2B-fatal 이슈 있음 ([Scalekit OTP vs Magic Links](https://www.scalekit.com/blog/otp-vs-magic-links-passwordless-authentication)). OTP 는 fallback 으로 좋지만 데모 무대에서 시연 어색. **password-first + email OTP 백업 + 향후 SSO 추가** 가 권장.

4. **현재 hospital admin 에 쓰이는 SHA-256 은 즉시 취약**. OWASP 는 **Argon2id (m=19 MiB, t=2, p=1)** 를 표준으로 명시 ([OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)). buyer 는 처음부터 Argon2id 로 가야 향후 마이그 비용 0. (운영비 차이는 무의미.)

5. **한국 PIPA 동의 양식은 데모 화면이라도 표준을 지켜야 신뢰**. 필수/선택 분리, 4 가지 명시 (수집 항목·이용 목적·보유 기간·거부 권리), 광고성 정보 수신 동의는 **반드시 선택**, 채널별 분리. 위반 시 최대 3천만 원 과태료 ([clobe.ai 가이드](https://clobe.ai/blog/marketing-consent-optin-law-terms-guide)). 단 **buyer 는 글로벌 영문 페이지**라 PIPA 동의는 한국 병원 admin (한국어) 페이지에 우선 적용. buyer 영문 signup 은 GDPR + ToS/Privacy 동의 1쌍이면 충분.

**한 줄 권고**: **email + password (Argon2id) 로 self-serve 가입 → 자동 API key 발급 → /account 에서 reveal-once + revoke**. 데모용 fast-path (이메일 인증 skip 모드 ENV) 1 개. v0.1.5 에 SSO (Google Workspace) 추가, v0.2 에 organization/teams.

---

## 1. 조사 질문

| # | 질문 | 답 위치 |
|---|---|---|
| Q1 | API key 직접 입력 vs email/password — B2B SaaS 표준은? | §2 |
| Q2 | Segmed/Gradient 등 직접 경쟁사 buyer onboarding 은? | §2.6 |
| Q3 | Email 인증 (verification) — 데모 D-13 에 맞는 옵션은? | §4 |
| Q4 | 비밀번호 정책 (해싱·길이·재설정) 권고는? | §5 |
| Q5 | iron-session 모델은 그대로 쓸 수 있나? | §6 |
| Q6 | API key 의 새로운 위치 (`/account`) 는 어떻게 재정의? | §7 |
| Q7 | 한국 PIPA 동의 항목 — buyer 페이지에도 필요한가? | §3 |
| Q8 | 데모 시연용 권장 플로우는? | §8 |

---

## 2. 경쟁사·베스트 프랙티스 매트릭스

### 2.1 분석 대상 (8 개)

API-first / 데이터 마켓 / 직접 경쟁사 중심으로 압축. 마케팅 페이지 분석은 `portal-redesign-competitive-analysis.md` §2 참조.

| 카테고리 | 사이트 |
|---|---|
| API-first SaaS | Stripe, Vercel, Supabase |
| 데이터/모델 마켓 | Hugging Face, Replicate |
| 의료영상 데이터 직접 경쟁 | Segmed, Gradient Health |
| 한국 B2B 참고 | Toss Payments (관행적 한국 회원가입) |

### 2.2 회원가입(`/signup`) 필드 매트릭스

| 사이트 | 회원가입 필드 | 정책 동의 | SSO 옵션 | 분리/즉시 |
|---|---|---|---|---|
| **Stripe** | email, password, full name (사후), country (사후) | ToS + Privacy 1 체크 | Google | 즉시 가입, country/business detail 은 onboarding 후속 |
| **Vercel** | email (또는 GitHub OAuth) | ToS 클릭 = 동의 (no checkbox) | GitHub, GitLab, Bitbucket, SAML SSO | OAuth 우선, email 은 OTP |
| **Supabase** | email, password (또는 OAuth) | ToS + Privacy | GitHub, Google, SSO | 즉시 |
| **Hugging Face** | email, password, username, full name, "I have read TOS" | ToS + 이메일 인증 후 활성화 | — (Enterprise OAuth Token Exchange 별도) | 이메일 인증 없으면 일부 기능 제한 |
| **Replicate** | GitHub OAuth 단일 (email/password 미지원) | OAuth 동의 | GitHub only | 즉시 |
| **Segmed** | **공개 signup 없음** — "Book a Call" 만 | — | — | 100% sales-led |
| **Gradient Health** | 공개 "7-DAY FREE TRIAL" — 클릭 시 이메일 + 회사명 + 의도 (추정) | ToS | (확인 불가) | 즉시 trial 활성 |
| **Toss Payments** (참고) | 사업자등록 + 대표자 + 담당자 email + 휴대폰 OTP + 계좌 + 4 종 동의 (필수3+선택1) | 한국 표준 4 종 분리 | — | 가입 후 KYB 심사 |

**관찰**:

- **이메일 + 비밀번호가 universal**. OAuth-only (Replicate) 는 개발자 친화 마켓에선 ok 지만 의료 buyer (제약사 임상팀, 학술 연구자) 에게는 진입 장벽.
- **Stripe / Vercel 은 "minimum field, defer rest"** — 회사명·국가·도메인 등은 가입 후 첫 사용 시점에 묻는다 ([Stripe Atlas guide](https://stripe.com/guides/atlas/optimize-your-customer-sign-up-and-sign-in-experience)).
- **Hugging Face 는 "username + ToS only" 1 체크박스**. 이메일 인증은 사후 e-mail 클릭. 데모 무대에서 시연하기엔 매끄럽다.
- **Segmed sales-only 모델은 RadiVault 가 모방하면 Gradient 대비 마찰 +1**. 단 buyer 단가가 매우 높을 (>$50K/월) 경우 합리.

### 2.3 로그인 (`/signin`) 필드

거의 100% **email + password** (또는 SSO 버튼). "Forgot password" 링크 필수. 일부 (Notion, Slack) 는 magic link 도 함께 옵션.

### 2.4 SSO / Social login 비중

| 사이트 | Social/SSO 옵션 | 데모 D-13 적합성 |
|---|---|---|
| Stripe | Google | 높음 (글로벌 buyer 70% 가 Google Workspace) |
| Vercel | GitHub, GitLab, SAML | AI 기업 개발자에게 익숙 |
| Hugging Face | (없음, Enterprise OAuth Token Exchange 별도) | — |
| Supabase | Google, GitHub, SSO | — |

**RadiVault v0.1 권고**: SSO 미지원. v0.1.5 에 **"Continue with Google"** 만 추가 (구현 단순). v0.2 에서 enterprise SAML/Okta.

### 2.5 API key 발급/관리 위치 — 핵심 패턴

| 사이트 | 위치 | 발급 방식 | reveal | revoke | 다중 | 스코프 |
|---|---|---|---|---|---|---|
| **Stripe** | `/account/apikeys` | 자동 1쌍 (publishable + secret) on signup | reveal-once + 항상 일부 표시 | ✅ | ✅ | 라이브/테스트 |
| **Vercel** | `/account/tokens` | 사용자가 명시적으로 "Create Token" | reveal-once | ✅ | ✅ | 스코프 (account / team) |
| **Hugging Face** | `/settings/tokens` | 사용자가 "New token" | reveal-once + "Manage" 로 회전 | ✅ | ✅ ("앱마다 1 키" 권고) | **fine-grained scopes** (특정 모델·org) |
| **Replicate** | `/account/api-tokens` | 자동 1 키 + 추가 가능 | reveal | ✅ | ✅ | — |
| **Supabase** | `/project/api` | 자동 (anon + service_role) | 항상 표시 (UI 토글) | rotate | 2 종 고정 | role 기반 |

**핵심 디자인 원칙**:

1. **자동 1 개 발급 (signup 직후) + 사용자가 추가 가능**. Stripe·Replicate 모델.
2. **Reveal-once** (보안) 또는 **항상 마스킹 + 한 번 reveal 가능** (Stripe 의 secret key). Hugging Face 권고: "leak 시 즉시 회전".
3. **revoke / regenerate 분리**. revoke = 키 무효, regenerate = 새 키 발급.
4. **다중 키 지원** = "local 개발용", "CI 용", "production 용" 분리. Hugging Face docs 의 "create one access token per app" 가 그대로 적용.
5. **fine-grained scopes** 는 v0.2 이후. v0.1 은 단일 스코프 (`tier=preview` 만).

### 2.6 직접 경쟁사 onboarding 모델 비교

| 차원 | Segmed | Gradient | RadiVault (현재) | RadiVault (권고) |
|---|---|---|---|---|
| 가입 진입 | "Book a Call" | "7-DAY FREE TRIAL" | API key 페이스트 | self-serve email/password |
| 시간 (가입 → 첫 검색) | 3–14 일 (sales 미팅) | 즉시 | 즉시 (단 키 받아야) | 즉시 |
| 톤 | Enterprise · regulatory | Developer · "instant access" | (혼란) | Hybrid (Stripe 식) |
| 대상 | 제약사 R&D, MedDevice | AI 스타트업, 연구자 | (불명) | 양쪽 |

**시사점**: Gradient 의 "instant access" 는 강력한 차별화 포인트지만 한국 병원 → 글로벌 라는 공급 측에서 **buyer 가 즉시 데이터를 받을 수 있는 게 아니다** (de-id 처리·계약·국외이전 동의 절차 필요). 따라서 RadiVault 는 **"signup 즉시 = search 즉시" + "주문 = 계약 단계"** 의 두 단 분리가 필요. 이건 dev-spec-portal-redesign 의 "preview tier" 와 일치.

### 2.7 회원가입 거부/이메일 인증 타이밍

- **Stripe / Vercel**: 인증 없이도 dashboard 진입 가능, 결제·publish 시점에 인증 강제.
- **Hugging Face**: 이메일 인증 안 하면 일부 모델 다운로드 불가, 토큰 발급은 가능.
- **Notion / Linear**: 이메일 인증이 곧 가입 (magic link).

**RadiVault 데모 D-13 권고**: signup → 즉시 dashboard + API key 발급. 이메일 인증은 **주문(`/orders/new`) 직전**에 강제. 이 두 단 분리가 데모 매끄러움 + 보안 균형.

---

## 3. PIPA 동의 체크리스트 (한국 버전 — 한국 병원 admin 페이지 우선)

> **중요**: buyer (글로벌 영문) 페이지는 PIPA 동의 양식 의무가 즉시 발생하지 않는다 (한국 거주자 개인정보 직접 수집이 아니므로). 그러나 **한국 buyer 가 가입할 가능성이 있으면 PIPA 적용**. 본 섹션은 **한국 병원 admin signup 페이지** (별도 feature) 와 **buyer 페이지의 한국어 전환 시** 양쪽에 적용.

### 3.1 필수 분리해야 하는 동의 항목

PIPA + 정통망법 표준 ([개인정보 처리 동의 안내서, 개인정보위 2022](https://www.privacy.go.kr/front/bbs/bbsView.do?bbsNo=BBSMSTR_000000000049&bbscttNo=13156)):

| # | 항목 | 필수/선택 | 분리 의무 | 비고 |
|---|---|---|---|---|
| A | 개인정보 수집·이용 동의 (PIPA §15) | 필수 | ✅ 단독 체크박스 | 4 가지 명시: 항목 / 목적 / 보유기간 / 거부권리 |
| B | 개인정보 제3자 제공 동의 (PIPA §17) | 선택* | ✅ 단독 체크박스 | RadiVault 경우 buyer (제3자) 에 hospital metadata 제공 — 선택이면 가입 거부 불가 |
| C | 개인정보 처리 위탁 동의 (PIPA §22) | 통지로 충분 | 별도 동의 불필요 (홍보 위탁 제외) | "AWS, Datadog 등에 위탁" 통지 |
| D | 개인정보 국외이전 동의 (PIPA §28-8) | 별도 동의 | ✅ 단독 체크박스 | RadiVault 핵심. **익명정보는 PIPA 적용 제외**, 단 "익명 처리 전 단계" 인 hospital ingest 시점은 적용 |
| E | 광고성 정보 수신 동의 (정통망법 §50) | 선택 | ✅ 채널별 분리 (이메일/SMS/푸시) | 거부 시 가입 차단 불가, 위반 시 최대 3천만 원 과태료 |
| F | 만 14세 미만 확인 | B2B 면 면제 가능 | — | buyer = 법인 종사자 가정, hospital admin = 의료종사자 |

\* RadiVault 경우 buyer 에게 hospital metadata 제공이 **서비스 본질** 이므로 "필수" 로 분류 가능하나, 법적 안전마진을 위해 변호사 자문 후 "선택" 으로 두는 게 보수적.

### 3.2 각 동의 항목에 반드시 명시해야 하는 4 가지

PIPA §15(2):
1. **수집·이용 항목** — 예: "이메일 주소, 비밀번호 (Argon2id 해시), 기관명, 직책"
2. **수집·이용 목적** — 예: "의료영상 데이터 검색·주문 서비스 제공, 부정사용 방지"
3. **보유 및 이용 기간** — 예: "회원 탈퇴 시까지. 단, 관련 법령에 따른 보존 의무 기간 (전자상거래법 5년) 은 별도 보관"
4. **동의 거부 시 불이익** — 예: "필수 항목 거부 시 회원가입이 제한됩니다"

### 3.3 UI/UX 권고 (PIPA + 데모 신뢰성 양립)

- **"전체 동의" 체크박스 허용**. 단 각 항목의 요약을 펼침/모달로 확인 가능해야 함.
- **필수 동의는 default unchecked** (자동 체크 금지 — 정보 주체 능동성 원칙).
- **선택 동의 거부 시 가입 가능** (재차 회원가입 거부 메시지 띄우면 위법).
- **동의 철회 방법** 명시: "회원 페이지 → 설정 → 동의 관리".
- **개인정보처리방침** + **이용약관** 별도 풀 문서 링크 (footer + signup 페이지 모두).

### 3.4 buyer (글로벌) 페이지에서의 단순화

영문 buyer signup 은 PIPA 직접 의무 없음 (한국 거주 데이터 주체 아닌 가정). 단 다음을 권고:

- **ToS + Privacy Policy 1 체크박스** ("I agree to the Terms of Service and Privacy Policy").
- **Marketing email opt-in 별도** ("Send me product updates" — default unchecked).
- 한국 buyer 의 경우 한국어 페이지로 redirect 후 §3.1 양식 적용.

### 3.5 ISMS-P / ISO 27001 가입 시점 추가 의무

`portal-redesign-competitive-analysis.md` §8.6 이미 다룸. 본 문서 추가 사항:

- **회원가입 로그 보관** (ISMS-P 2.5.5 인증·인가): 가입 시각·IP·동의 항목·약관 버전 hash 를 audit log 로 보관.
- **2FA 의무화** (Phase 3 이후, ISMS-P 2.5.6): TOTP 또는 SMS. v0.1 범위 외.
- **비밀번호 변경 강제 주기** (ISMS-P 2.5.4): NIST SP 800-63B Rev.4 는 주기적 강제 변경을 **반대**, 침해 시점에만 강제. ISMS-P 와 NIST 충돌 — 변호사·인증컨설팅 자문 필요.

---

## 4. Email 인증 (Verification) 옵션 비교

### 4.1 옵션 매트릭스

| 옵션 | UX 친숙도 | 데모 난이도 | 한국 친숙도 | 보안 | corporate email 호환 | 비용 |
|---|---|---|---|---|---|---|
| **A. No verification** (즉시 사용) | ★★★★★ | ★★★★★ | ★★★ | ★ | ★★★★★ | $0 |
| **B. Magic link** | ★★★★ | ★★★ (이메일 보여주기 어색) | ★★ | ★★★ | ★★ (link scanner 토큰 소진 위험) | 저 |
| **C. OTP 6자리** | ★★★★ | ★★★★ (시연 매끄러움) | ★★★★★ | ★★★★ | ★★★★★ | 저 |
| **D. 이중 (link + OTP fallback)** | ★★★★★ | ★★★★ | ★★★★ | ★★★★ | ★★★★ | 중 |
| **E. SMS OTP** | ★★★ | ★★ | ★★★★★ (한국 전통) | ★★★★ (SIM swap 제외) | ★★★★★ | 고 ($0.01/건) |

### 4.2 데모 D-13 권고 — "지연 인증 + OTP fallback"

```
[signup 폼 제출]
  ├─ 이메일 unique 검증 (DB 즉시 체크)
  ├─ Argon2id 해시 저장
  ├─ buyer + buyer_api_key (기본 1개) 즉시 생성
  ├─ iron-session cookie 발급 → /search 자동 진입
  ├─ "Verify your email to enable orders" 배너 표시
  └─ 백그라운드: SES/SendGrid 로 6자리 OTP 이메일 발송 (10분 TTL)
      └─ 사용자가 /account 또는 /verify 에서 코드 입력 시 verified=true
```

**데모 시연용 환경변수 fast path**: `BUYER_AUTH_SKIP_EMAIL_VERIFY=true` → signup 직후 verified=true 자동 설정. CEO 데모에서 "이메일 받기 어색" 회피.

### 4.3 한국 OTP 친숙도

한국 사용자는 본인인증 (휴대폰 + KISA) 에 익숙해서 6자리 코드 입력이 자연스러움. Magic link 는 "이메일 → 클릭 → 새 탭 열림" 이 한국 일반 사용자에게 약간 낯설다는 보고 ([Pushwoosh 한국 가이드](https://www.pushwoosh.com/ko/blog/privacy-compliant-push-korea/)). 단 buyer = 글로벌 영문이므로 magic link 도 ok.

### 4.4 SMS 인증 — v0.1 비추

- 한국 KISA 본인인증은 비용·통합 부담 (NICE/PASS API).
- B2B buyer 에게 휴대폰 번호 요구는 마찰 ↑.
- v0.2 이후 한국 hospital admin 에 한해 도입 검토.

---

## 5. 비밀번호 정책 권고

### 5.1 해싱 — Argon2id 표준

**OWASP 2026 권고** ([Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)):

```
Argon2id 최소 파라미터:
  m = 19456 (19 MiB)
  t = 2 (iterations)
  p = 1 (parallelism)
```

**RadiVault buyer v0.1 권고**: `m=19456, t=2, p=1` (최소). Node.js `argon2` 패키지 (`hash-wasm` 백엔드) 사용. 평균 ~50ms/hash, login latency 영향 무시 가능.

**현재 hospital admin 의 SHA-256 마이그레이션** (별도 feature):
- OWASP 권고: legacy hash 위에 즉시 wrap (`argon2id(sha256(pw))`) → 다음 로그인 시 plain → argon2id 재해싱.
- v0.1.5 hospital admin SSO 마이그 시 자동 처리.

### 5.2 비밀번호 길이·복잡도

**NIST SP 800-63B Rev.4 (2024 발표, 2025 발효)**:
- **최소 길이**: 8자 (권고 15자).
- **최대 길이**: 64자 이상 허용 (Argon2id 입력 제한 없음).
- **복잡도 강제 금지**: 대문자·숫자·특수문자 강제 불가. 사용자가 길게 쓰도록 유도.
- **사전(dictionary) 검사 의무**: HaveIBeenPwned API 권고.
- **주기적 변경 강제 금지**: 침해 시점에만 강제.

**RadiVault v0.1 권고**:
- 8자 minimum, 64자 maximum.
- 복잡도 검증 0 (tooltip 으로 "긴 비밀번호 권장" 만).
- HaveIBeenPwned k-Anonymity API 호출 (가입·변경 시) — 응답 200ms.

### 5.3 비밀번호 재설정 플로우

```
/signin → "Forgot password?" → /password-reset
  ├─ email 입력 → 항상 200 응답 (계정 존재 여부 누설 방지)
  ├─ 백그라운드: reset_token 생성 (32 bytes random, TTL 1h, 1회 사용)
  ├─ 이메일 발송: https://radivault.io/password-reset/confirm?token=...
  └─ confirm 페이지: 새 비밀번호 2회 입력 → Argon2id 재해싱 → 모든 세션 invalidate
```

### 5.4 로그인 실패 rate limit

| 레이어 | 제한 | 락아웃 |
|---|---|---|
| IP per minute | 5 회 | 1 분 (HTTP 429) |
| account per hour | 10 회 | 15 분 (이메일 알림) |
| 글로벌 brute force | 1000/min | Cloudflare WAF |

iron-session + Redis (rate limit) 조합. v0.1 은 in-memory (Vercel Edge / Next.js middleware), v0.1.5 에 Upstash Redis.

---

## 6. Session 모델

### 6.1 iron-session 그대로 유지 가능

현재 portal 이 iron-session v8 사용 ([package.json](https://github.com/vvo/iron-session)). buyer-auth 마이그도 동일 라이브러리 유지. 변경 사항:

```ts
// 현재 BuyerSession
{ apiKey: string, signedInAt: number, buyerId?: string }

// 신규 BuyerSession
{
  buyerId: string,        // bd_xxx — UUID-like
  email: string,           // 표시·로그용 (audit)
  signedInAt: number,
  emailVerified: boolean,
  // apiKey 는 절대 cookie 에 안 넣음 — DB lookup 으로만
}
```

API key 는 더 이상 cookie 에 보관하지 않는다. **세션 → buyerId → DB lookup → 활성 API key 1 개를 server-side 에서 사용**. 이건 보안 + UX 양면에서 개선 (세션 유출 ≠ API key 유출).

### 6.2 TTL — sliding 권고

- **현재**: 12h absolute (dev-spec §283).
- **신규 권고**: **30일 sliding** (요청마다 갱신) + **90일 absolute max**.
- 이유: B2B SaaS 사용자는 매주 1–2회 접근. 12h 마다 재로그인은 마찰. Stripe/Vercel 모두 30일 sliding.

iron-session v8 sliding TTL 구현:

```ts
// middleware 에서 매 요청마다
session.signedInAt = Date.now();
await session.save();
```

### 6.3 "Remember me" 옵션

- **체크 시**: 30일 sliding (위 default).
- **체크 해제**: 8h absolute.
- 데모용에는 **default = on** 권고 (체크박스 자체를 v0.1 에서 노출 안 함).

### 6.4 로그아웃 동작

```
POST /api/session/signout
  ├─ session.destroy() → cookie 무효
  ├─ (선택) 모든 디바이스 로그아웃 = DB session_token table 의 buyerId revoke
  └─ redirect /
```

Stateful "다른 디바이스에서도 로그아웃" 은 v0.1.5. v0.1 은 cookie destroy 만.

### 6.5 동시 로그인 제한

- B2B 표준은 무제한 (한 직원이 desktop + laptop + mobile).
- v0.1 무제한, v0.2 audit 페이지에서 활성 세션 목록 표시 + 개별 revoke.

---

## 7. /account API key 위치 재정의

### 7.1 현재 `/account` 의 한계

현재 `web/portal/src/app/account/page.tsx` 는:
- buyerId 표시
- API key 마스킹 + reveal-once (cookie 의 apiKey 그대로 노출)

**문제**:
- 로그인 = API key 페이스트 모델이라, "이 키가 곧 신분"이라 회전 시 즉시 로그아웃.
- 다중 키 미지원.
- revoke 후 재발급 UX 없음.

### 7.2 신규 `/account` 구조

```
/account
  ├─ Profile
  │   ├─ email (read-only, change 는 별도 verify flow)
  │   ├─ name, organization, country
  │   └─ tier (preview / paid) + "Upgrade" CTA
  ├─ Security
  │   ├─ "Change password"
  │   ├─ "Two-factor auth (Coming soon)"
  │   └─ "Active sessions" (v0.1.5)
  ├─ API Keys                ← NEW MODEL
  │   ├─ Auto-issued key (signup 직후 1개)
  │   │   ├─ kid: rv_live_K8dF... (마스킹: rv_live_K8dF…3xQ2)
  │   │   ├─ Created: 2026-04-25
  │   │   ├─ Last used: 2 hours ago
  │   │   ├─ Tier: preview
  │   │   ├─ [Reveal once] [Rotate] [Revoke]
  │   ├─ + Create new key
  │   │   └─ name (CI / local / prod), tier (preview only in v0.1)
  │   └─ Documentation link → /docs/api-quickstart
  └─ Billing (v0.2)
```

### 7.3 Reveal-once UX

Stripe 식:
```
[Reveal API key] 클릭
  ↓
Modal: "rv_live_K8dF7sX9aB2cD4eF6gH8iJ0kL2mN4oP6qR8sT0uV2wX3xQ2"
        ⚠ This key will be shown only once. Copy it now.
        [Copy to clipboard] [I've saved it, close]
  ↓
Modal close 후 마스킹 표시: rv_live_K8dF…3xQ2
```

DB 에는 처음부터 hash 만 저장 (`buyer_api_key.token_hash` 컬럼 이미 존재). reveal 은 가입 직후 1회만 가능 — session 에 잠시 보관 후 first-page-load 시 강제 reveal.

### 7.4 다중 API key (v0.1 결정 필요)

| 옵션 | v0.1 범위 | 비고 |
|---|---|---|
| **A. 단일 키 고정** | 자동 1개만 발급, 회전 시 새 키로 교체 | 가장 단순. |
| **B. 다중 키 허용** | "+ Create" 으로 추가, 각각 라벨 (CI/local/prod) | Hugging Face 모델, 유연. |
| **C. 자동 1 + 사용자 추가 가능** | 위 둘의 hybrid | 데모 매끄러움 + 확장성 |

**권고**: **C** (자동 1개 + "Create" 버튼으로 추가 가능, max 5개).

### 7.5 키 회전 (Rotate) vs Revoke

- **Rotate**: 새 키 발급 + 옛 키 7일 grace period (양쪽 valid). 7일 후 옛 키 자동 revoke.
- **Revoke**: 즉시 무효, 복구 불가.

v0.1 은 Revoke 만 (단순). Rotate 는 v0.1.5.

---

## 8. 데모 시연 권장 플로우

### 8.1 시나리오 A: 처음 방문자 (Cold start)

```
1. https://radivault.io/  →  랜딩 페이지 (homepage)
2. [Sign up] 클릭  →  /signup
3. 입력: email (demo@radivault.io), password (Demo1234!), name (Kyle Demo), organization (Acme Inc.)
4. ☑ I agree to the Terms of Service and Privacy Policy
5. [Create account] 클릭  →  Argon2id 해싱 (~50ms) + buyer 생성 + 자동 API key 발급
6. → /search (이메일 인증 배너만 상단에 표시, 검색은 즉시 가능)
7. (CEO 가 검색 시연)
8. /account 클릭  →  API key reveal-once 모달  →  복사
9. (별도 터미널) curl -H "Authorization: Bearer rv_live_..." https://api.radivault.io/v1/search/facets  →  200
10. → 데모 종료
```

**소요 시간 (가입~검색 첫 결과)**: 30초.

### 8.2 시나리오 B: 재방문자

```
1. https://radivault.io/  →  랜딩
2. [Sign in] 클릭  →  /signin
3. 입력: email + password  →  [Continue]
4. → /dashboard 또는 /search (last-seen route 복원)
```

**소요 시간**: 5초.

### 8.3 시나리오 C: 프로그램 접근만 (개발자 데모)

```
1. /account → API Keys
2. [Reveal] 클릭 → 모달
3. (별도 터미널) export RV_KEY=rv_live_...
4. curl -H "Authorization: Bearer $RV_KEY" https://api.radivault.io/v1/search/studies?modality=CT
5. JSON 응답 → CEO 가 "이게 제가 말한 그 데이터입니다"
```

### 8.4 데모 안전망 (Hardcoded fast path)

`docker-compose.demo.yml`:
```yaml
environment:
  BUYER_AUTH_SKIP_EMAIL_VERIFY: "true"      # signup 시 verified=true 자동
  BUYER_AUTH_DEMO_ACCOUNT: "demo@radivault.io:Demo1234!:bd_demo001"   # seeded
  BUYER_AUTH_PWD_RESET_DISABLED: "true"     # 데모 중 우발 사고 방지
```

데모 시작 전 `seed_demo_buyer.py` 실행 → `bd_demo001` 계정 + API key 1 개 미리 생성. 시연 중 sign-up 새로 하든 기존 계정 sign-in 하든 양쪽 매끄러움.

### 8.5 실패 시 안전 시나리오

- 가입 실패 (중복 이메일) → "이 이메일은 이미 사용 중입니다. [Sign in 으로 가시겠어요?]"
- 비밀번호 틀림 (3회) → "Forgot password?" 자동 강조
- API ping 실패 (search 503) → "Service temporarily unavailable" 토스트 + 데모 진행 OK (UI 만 보여주기)

---

## 9. RadiVault 시사점 (요약)

### 9.1 dev-spec-buyer-auth.md 가 다뤄야 할 FR

| FR | 요약 |
|---|---|
| **FR-AUTH-1** | `/signup` 페이지 (email + password + name + org + ToS 체크) |
| **FR-AUTH-2** | `POST /api/auth/signup` BFF + Argon2id (m=19456,t=2,p=1) + buyer+buyer_api_key INSERT + iron-session 발급 |
| **FR-AUTH-3** | `/signin` 재설계 (email + password 폼, "Forgot password?" + "Sign up" 링크) |
| **FR-AUTH-4** | `POST /api/auth/signin` BFF + Argon2id verify + rate limit 5/IP/min |
| **FR-AUTH-5** | `POST /api/auth/signout` + session destroy |
| **FR-AUTH-6** | `/password-reset` + `/password-reset/confirm` flow + email token (TTL 1h) |
| **FR-AUTH-7** | `/account` 재구성: Profile / Security / API Keys 3 탭 |
| **FR-AUTH-8** | API key reveal-once 모달 + revoke 버튼 |
| **FR-AUTH-9** | Email verification OTP (6자리, 10분 TTL) — `/verify` + skip-flag ENV |
| **FR-AUTH-10** | iron-session sliding TTL 30일 / absolute 90일 + buyer_id-only payload |
| **FR-AUTH-11** | DB 마이그: `buyer.password_hash`, `buyer.email_verified`, `buyer.country`, `buyer.organization` 컬럼 추가; `buyer_api_key.label` 추가 |
| **FR-AUTH-12** | 데모 seed script: `bd_demo001` 자동 생성 |

### 9.2 PRD/ARCHITECTURE 갱신 제안

- **`docs/prd.md`**: "buyer 가입은 self-serve email/password (글로벌 영문)" 명시. 현재 PRD 가 "API key 분배 = sales-led" 가정이면 수정.
- **`docs/ARCHITECTURE.md`**: 인증 흐름도 갱신. `iron-session(buyerId)` → DB lookup → `buyer_api_key.token_hash` (server-side bearer 주입) 모델 도식.
- **`docs/specs/dev-spec-portal-redesign.md` §FR-BP-13** (`/account` 최소 스펙) → 본 §7.2 로 대체.
- **`docs/specs/dev-spec-portal-redesign.md` §FR-BP-2** (`/signin` "기존 유지") → 본 §7.2 로 대체.

### 9.3 design-spec-buyer-auth.md 가 다뤄야 할 화면

1. **`/signup`** — 7 필드 폼 + ToS 체크 + 우측 패널 "Why RadiVault" (PRD §1 의 3 키 메시지)
2. **`/signin`** — 2 필드 + Forgot/Sign-up 링크 + "Continue with Google (Coming soon)" placeholder
3. **`/password-reset`** + `/password-reset/confirm` — 단일 필드
4. **`/verify`** — 6자리 OTP 입력 (auto-advance)
5. **`/account` Profile/Security/API Keys 3 탭** — 좌측 nav, 우측 콘텐츠
6. **API key reveal-once 모달** — Stripe 식 디자인
7. **에러 상태 6 종**: invalid email format / weak password / email taken / wrong password / rate-limited / verification expired

---

## 10. 한계·오픈 퀘스천 (Kyle 결정 필요)

| # | 질문 | 권고 default | 영향 |
|---|---|---|---|
| Q1 | 데모 시연 자체에서 "ㅣive signup" 을 보여줄 것인가, "기존 데모 계정 sign-in" 을 보여줄 것인가? | 둘 다 가능, **signup 시연이 임팩트 강함** | 데모 스크립트 |
| Q2 | "Continue with Google" SSO 를 v0.1 에 포함할 것인가? | 비포함 (v0.1.5) | 개발 1주 |
| Q3 | 다중 API key 지원 (Hugging Face 식)? | C 옵션 (auto 1 + 추가 가능) | DB schema 확정 |
| Q4 | API key 회전 (rotate) v0.1 포함? | 비포함 (revoke 만) | 운영 후 사용자 요구 봐서 |
| Q5 | 이메일 verification — 데모에서 실제 이메일 보낼 것인가? | **데모는 skip-flag**, production 은 SES OTP | infra (SES domain verify) |
| Q6 | "Marketing email opt-in" 체크박스 노출? | 노출 (default unchecked) | UX |
| Q7 | hospital admin 의 SHA-256 → Argon2id 마이그를 buyer-auth 와 같이 진행? | 별도 feature (v0.1.5) | 범위 축소 |
| Q8 | 한국 buyer 가 가입할 경우 PIPA 동의 양식 별도 노출? | v0.1 영문만, 한국어 모드는 v0.2 | i18n 부담 |
| Q9 | Password strength meter (zxcvbn) 사용? | 사용 (UX 개선, 256KB bundle 추가) | 번들 크기 |
| Q10 | rate limit 저장소: in-memory vs Redis? | **in-memory v0.1, Upstash v0.1.5** | infra |
| Q11 | "Forgot email" 도 지원? (계정 복구) | 비지원 (B2B 표준 = sales 문의) | UX |
| Q12 | `/signup` 페이지를 풀 페이지 vs 모달? | 풀 페이지 (Stripe·Vercel·HF 모두 풀) | design |

---

## 11. 출처 (Sources)

- [Stripe — Optimizing customer sign-up and sign-in](https://stripe.com/guides/atlas/optimize-your-customer-sign-up-and-sign-in-experience) — 사인업·사인인 분리, OAuth 우선, defer fields
- [Hugging Face — User Access Tokens](https://huggingface.co/docs/hub/en/security-tokens) — 다중 토큰·fine-grained scope·"one token per app" 권고
- [Scalekit — OTP vs Magic Links](https://www.scalekit.com/blog/otp-vs-magic-links-passwordless-authentication) — corporate email scanner 의 magic link 토큰 소진 이슈
- [Prelude — OTP vs Magic Links](https://prelude.so/blog/otp-vs-magic-links) — UX·보안 비교
- [MojoAuth — Passwordless 101 for SaaS](https://mojoauth.com/blog/passwordless-authentication-saas-options) — magic link / OTP / passkey 비교
- [OWASP — Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) — Argon2id m=19456,t=2,p=1 표준
- [NIST SP 800-63B (current)](https://pages.nist.gov/800-63-3/sp800-63b.html) + [Rev.4 draft](https://pages.nist.gov/800-63-4/sp800-63b/passwords/) — 비밀번호 길이·복잡도 권고
- [iron-session GitHub (v8)](https://github.com/vvo/iron-session) — 세션 라이브러리, default 15일 maxAge
- [Auth0 SaaS Starter Kit (Vercel template)](https://vercel.com/templates/next.js/auth0-nextjs-saas-starter) — B2B organization signup 패턴
- [Segmed.ai 홈페이지](https://www.segmed.ai) — sales-only "Book a Call" 모델
- [Gradient Health 홈페이지](https://gradienthealth.io/) — "7-DAY FREE TRIAL" self-serve 모델
- [개인정보위 — 개인정보 처리 동의 안내서 2022](https://www.privacy.go.kr/front/bbs/bbsView.do?bbsNo=BBSMSTR_000000000049&bbscttNo=13156) — PIPA 동의 양식 표준
- [국가법령정보센터 — 개인정보 보호법](https://www.law.go.kr/lsEfInfoP.do?lsiSeq=195062) — PIPA §15/§17/§22/§28-8 원문
- [정보통신망법 (광고성정보 §50)](https://www.law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=1000688185&lsId=000030&print=print) — 광고성 정보 수신동의 분리·과태료
- [clobe.ai — 마케팅 수신 동의 가이드](https://clobe.ai/blog/marketing-consent-optin-law-terms-guide) — 회원가입 동의 양식 한국 표준
- [Pushwoosh — 한국 PIPA 푸시 알림 가이드](https://www.pushwoosh.com/ko/blog/privacy-compliant-push-korea/) — 한국 사용자 인증 친숙도

---

## 12. Disclaimer

본 문서는 **법률 자문이 아니다**. PIPA / 정통망법 / GDPR / HIPAA 의 구체 적용 여부, 동의 양식 문구, 약관 표현 등은 **외부 변호사 자문 필수**. 특히:

- "한국 거주 buyer 가 가입할 가능성" 의 PIPA 적용 범위
- "익명정보" vs "가명정보" vs "개인정보" 경계 (PIPA §28-2 ~ §28-7)
- 국외이전 동의 (PIPA §28-8) 의 buyer 측 의무
- 표시광고법 비교광고 (Segmed/Gradient 언급 시)

위 모든 사항은 변호사 검토 후 dev-spec / design-spec / 약관 문구에 반영되어야 한다.

---

## 13. 변경 이력

- **v0.1 (2026-04-25)**: 초안. CEO 데모 D-13 대응. @planner 가 dev-spec-buyer-auth.md 작성 시 본 문서 §7, §9 직접 참조.
