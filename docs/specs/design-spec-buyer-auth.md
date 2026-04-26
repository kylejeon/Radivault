# 디자인 명세 — Buyer Auth (이메일/비밀번호 + API key 이중 모델)

> **Status**: Draft v0.1 · **Feature slug**: `buyer-auth` · **Last updated**: 2026-04-25
> **작성자**: @designer (Claude Opus 4.7)
> **근거**:
> - [`dev-spec-buyer-auth.md`](./dev-spec-buyer-auth.md) — FR-AUTH-1..12, NFR (본 spec 의 단일 원본)
> - [`design-spec-portal-redesign.md`](./design-spec-portal-redesign.md) §4 (디자인 토큰) · §5 (공유 컴포넌트 — Hero / CTA Pair / Footer / Compliance Badge / Language Toggle)
> - [`UI_GUIDE.md`](../UI_GUIDE.md) — 플레이스홀더. portal-redesign §4 를 사실상 단일 원본으로 승계
> **Supersedes (시각)**: 현 production `/signin` 의 50자 raw API key 텍스트 한 줄 입력 — 본 spec 으로 폐기.

---

## 1. 디자인 개요

dev-spec §1 인용:
> "RadiVault Buyer Portal 의 신규 인증 시스템. 웹 UI 는 email + password 로 self-serve 가입·로그인·비밀번호 재설정을 지원하고, 프로그램 접근(curl, SDK) 은 signup 직후 자동 발급되는 API key 1개로 처리한다."

본 디자인 명세는 **5개 폼 컴포넌트 + 2개 모달**을 신규 정의하고, **3개 화면 (signup / signin / account API keys)** 의 ASCII 와이어를 EN/KR 변형으로 제시한다. portal-redesign 의 토큰·공유 컴포넌트 (Hero · CTA Pair · Footer · Compliance Badge · Language Toggle) 는 **재사용**하며 본 spec 에서 재정의하지 않는다.

**북극성**: D-13 무대에서 글로벌 AI 의사결정자가 "Stripe / Vercel / Hugging Face 와 동급의 self-serve B2B SaaS" 로 인식하도록, 폼 미세 인터랙션 (focus ring · helper text · error placement · password show/hide) 을 동급으로 끌어올린다.

---

## 2. 화면 목록

| ID | 화면명 | 경로 (EN) | 경로 (KR) | 주요 역할 | dev-spec FR |
|----|--------|-----------|-----------|----------|-------------|
| S-1 | Signup | `/signup` | `/ko/signup` | 신규 buyer self-serve 가입 + 자동 API key 발급 + (조건부) OTP 모달 | FR-AUTH-1, 9, 10 |
| S-2 | Signin | `/signin` | `/ko/signin` | 재방문 buyer email + password 로그인 | FR-AUTH-4 |
| S-3 | Account → API Keys 섹션 | `/account` (탭 또는 단일) | `/ko/account` | API key 마스킹 표시 + Reveal once / Regenerate / Revoke | FR-AUTH-8 |

**보조 진입 (본 spec 와이어 생략, 컴포넌트만 정의)**:
- `/password-reset` — 이메일 입력 한 줄 폼 (FR-AUTH-6, S-2 에서 링크).
- `/password-reset/confirm?token=…` — 새 비밀번호 2회 입력 (PasswordInput 재사용).
- `/verify` — OTP 입력 단독 페이지 (모바일 또는 새 탭에서 OTP 메일 링크 클릭 시. 데스크톱 happy path 는 모달).

**섹션 외 (dev-spec FR-AUTH-11 회원탈퇴)**: `/account` "Danger zone" 섹션은 §6.5 와이어에 포함하되, 모달 명세는 §11 에서 Kyle 결정 필요로 표시.

---

## 3. 사용자 플로우

### 3.1 Signup happy path (EN)

```
[/]  →  Header "Sign up" 클릭
       →  [/signup S-1]  →  6필드 입력 + ToS+Privacy 체크
                          →  [POST /api/auth/signup 201]
                          →  EmailOtpModal 자동 열림 (skip-flag false)
                          →  6자리 OTP 입력 → success
                          →  ApiKeyRevealModal 자동 열림 (1회)
                          →  Copy + Close
                          →  [/search] redirect
```

### 3.2 Signup happy path (KR · PIPA 4종)

```
[/ko]  →  헤더 "회원가입" 클릭
       →  [/ko/signup S-1-KR]  →  6필드 + PIPA 4종 분리 동의 (필수 3 + 선택 1)
                                →  [POST /api/auth/signup 201]
                                →  EmailOtpModal (한국어 라벨)
                                →  ApiKeyRevealModal (한국어 라벨)
                                →  [/ko/search] redirect
```

### 3.3 Signin (재방문)

```
[/]  →  Header "Sign in"  →  [/signin S-2]  →  email + password
                                              →  [POST /api/auth/signin 200]
                                              →  [/search] redirect
```

### 3.4 권한 없음 (세션 만료)

```
[/orders/new]  →  middleware: session 무효
              →  [/signin?next=/orders/new] redirect
              →  signin 성공 후 next 경로로 복귀
```

### 3.5 에러 — email 중복 (signup)

```
[/signup]  →  submit  →  [POST /api/auth/signup 409 ERR_EMAIL_TAKEN]
                       →  <FormError> top-of-form: "An account already exists for alice@acme.ai. Sign in instead?"
                       →  email 필드 aria-invalid=true + 빨간 테두리 + helper "Already registered"
                       →  "Sign in instead" 링크 → /signin?email=<prefilled>
```

### 3.6 에러 — 비밀번호 불일치 (signin)

```
[/signin]  →  submit  →  [POST /api/auth/signin 401 ERR_AUTH_INVALID]
                       →  <FormError> top-of-form: "Email or password is incorrect."
                       →  email/password 둘 다 aria-invalid=true (timing-safe 노출)
                       →  password 필드 자동 clear + focus
                       →  "Forgot password?" 링크 강조
```

### 3.7 에러 — Rate limit (signin 5회)

```
[/signin]  →  6번째 submit  →  [429 ERR_RATE_LIMITED]
                              →  <FormError>: "Too many attempts. Try again in 1 minute."
                              →  Submit 버튼 disabled + 60초 카운트다운
                              →  카운트다운 종료 시 자동 재활성
```

### 3.8 회원가입 부분 실패 — OTP 발송 실패 (백그라운드)

```
[/signup 201 성공]  →  EmailOtpModal 열림
                    →  10분 내 코드 미수신
                    →  "Resend code" 버튼 클릭 (TTL 60s 쿨다운)
                    →  여전히 미수신 시 "Use API key only — verify later" 링크
                       (검색 자유, /orders/new 진입 시 /verify redirect)
```

---

## 4. 디자인 토큰 (재사용 선언)

> **본 spec 은 신규 토큰을 정의하지 않는다.** [`design-spec-portal-redesign.md`](./design-spec-portal-redesign.md) §4 의 토큰을 전면 승계한다. 아래 표는 본 spec 컴포넌트가 사용하는 토큰의 cross-reference 만 정리.

| 사용처 | portal-redesign §4 토큰 | 값 |
|--------|------------------------|-----|
| Primary CTA fill (Sign up · Sign in 버튼) | `--color-primary-600` | `#2563eb` (4.54:1 on white) |
| Primary CTA hover · focus ring | `--color-primary-700` | `#1d4ed8` (6.80:1) |
| Input border default | `--color-border-strong` | `#cbd5e1` |
| Input border focus | `--color-primary-600` | `#2563eb` |
| Input border error | status `Error` dark fg | `#b91c1c` (5.94:1) |
| Helper text | `--color-text-muted` | `#64748b` |
| Form label | `--color-text` | `#0f172a` |
| Error background tint | status `Error` light bg | `#fef2f2` |
| Success tint (verified 배지) | status `Success` light bg / dark fg | `#ecfdf5` / `#047857` (5.38:1) |
| Modal overlay | `rgba(15,23,42,0.50)` | scrim · §4.7 shadow-overlay 와 다름 |
| Modal shadow | `--shadow-overlay` | §4.7 |
| Modal radius | `--radius-lg` | 12px |
| Input · button radius | `--radius-md` | 8px |
| Card radius (API key 카드) | `--radius-md` | 8px |
| API key masked display 폰트 | `--font-mono` | JetBrains Mono |
| 본문 EN | `--font-sans-en` | Inter |
| 본문 KR | `--font-sans-kr` | Pretendard Variable |
| Form 수직 spacing | `--space-4` (필드 간) · `--space-6` (그룹 간) | 16 / 24px |

**신규 토큰 제안 (UI_GUIDE 공식화 시 등록 후보, 본 spec 에서 정의 금지)**:
- `--color-otp-cell-active` — OTP 6박스 active 외곽 (현재는 `--color-primary-600` 으로 대체)
- `--input-height-md` — 44px (현재는 `padding-y: space-3 + line-height: 24px` 로 도출)

→ 이 두 항목은 §11 Kyle 결정 필요에 ferr.

---

## 5. 컴포넌트 명세 (신규 5개 폼 + 2개 모달)

> 각 컴포넌트는 anchor id 로 v0.2 / 후속 spec 에서 참조. **재사용 원칙**: portal-redesign §5 의 `Button` (primary/ghost/lg/md/sm) · `Hero` · `CTA Pair` · `Footer EN/KR` · `Language Toggle` · `Compliance Badge` 는 그대로 사용.

### 5.1 `<TextInput>` `{#text-input-v1}` — FR-AUTH-1, 4, 6, 11

**역할**: signup / signin / password-reset 의 단일 라인 텍스트 필드 공통 컴포넌트.

**구조**:

```
┌─ Label ──────────────────────────────┐
│ Email                  (* required)  │  ← text-sm / font-medium / text-text
├──────────────────────────────────────┤
│ ┌──────────────────────────────────┐ │
│ │ alice@acme.ai                    │ │  ← text-base · padding 12×16 · border-strong
│ └──────────────────────────────────┘ │     · radius-md · h ≈ 44px
├──────────────────────────────────────┤
│ Helper text or error message.        │  ← text-xs / text-text-muted (or error fg)
└──────────────────────────────────────┘
```

**Props**:
- `id` (required, label `for` 와 input `id` 페어링)
- `label` (required, 시각 + 스크린리더)
- `type` — `email` | `text` | `password` (5.2 별도) | `number`
- `required` — boolean → 라벨 우측 `* required` (visual) + `aria-required="true"`
- `helper` — 정상 상태 보조 설명
- `error` — 에러 메시지 (있으면 helper 자리 차지 + 색·아이콘 변경)
- `autoComplete` — `email` / `current-password` / `new-password` / `organization`
- `maxLength`

**상태**:

| 상태 | border | bg | helper color | aria |
|------|--------|-----|--------------|------|
| default | `--color-border-strong` | `--color-bg` | `--color-text-muted` | — |
| hover | `--color-text-muted` | `--color-bg` | — | — |
| focus | `--color-primary-600` 2px + ring 3px primary-600/40 | `--color-bg` | — | — |
| error | `#b91c1c` 2px | `--color-bg` (또는 `#fef2f2` tint) | `#b91c1c` + ⚠ 아이콘 12px | `aria-invalid="true"`, `aria-describedby={errorId}` |
| disabled | `--color-border` | `--color-bg-muted` | `--color-text-muted` (40% opacity) | `aria-disabled="true"` |
| readonly | `--color-border` | `--color-bg-muted` | — | `aria-readonly="true"` |

**키보드**: Tab in/out, Esc → blur (모달 내에서는 Esc 모달 close 우선).

**i18n**:
- `* required` (EN) / `* 필수` (KR).
- 라벨 길이: KR 가 평균 30% 짧음. 라벨 우측 `* required` 위치는 `flex-justify-between` 으로 자동 정렬.

### 5.2 `<PasswordInput>` `{#password-input-v1}` — FR-AUTH-1, 3, 6

**역할**: 비밀번호 입력 + show/hide toggle + 길이 미터 (NIST 권고: 길이만 강제 8자).

**구조**:

```
┌─ Label ──────────────────────────────────────┐
│ Password               (8–64 characters)     │
├──────────────────────────────────────────────┤
│ ┌──────────────────────────────────┐ ┌────┐ │
│ │ •••••••••                        │ │ 👁 │ │  ← show/hide toggle 24px
│ └──────────────────────────────────┘ └────┘ │
├──────────────────────────────────────────────┤
│ ▰▰▰▰▱▱▱▱  9 / 64 characters                  │  ← 길이 미터 (NIST)
└──────────────────────────────────────────────┘
```

**길이 미터 규칙** (NIST SP 800-63B Rev.4, dev-spec FR-AUTH-3):
- 0 ~ 7 chars → 빨강 막대 + helper "Minimum 8 characters."
- 8 ~ 11 chars → 노랑 막대 + helper "OK. Longer is better."
- 12 ~ 64 chars → 초록 막대 + helper "Strong length."
- > 64 chars → 입력 차단 + helper "Maximum 64 characters."

복잡도 메시지 (대문자/특수문자) 강제 **금지** (dev-spec §3.2 제외 명시).

**show/hide toggle**:
- 아이콘: 👁 (show) / 👁‍🗨 (hide). 16px, color `--color-text-muted`.
- `aria-label="Show password"` / `"Hide password"` 토글.
- 키보드: Tab 으로 도달 가능. Enter / Space 로 토글.
- 토글 시 input `type` `password` ↔ `text` 변경. focus 유지.
- 보안: 토글 후 30초 자동 hide (timer reset on keystroke).

**Props**:
- TextInput 의 모든 props 승계
- `showStrengthMeter` — boolean (default true on signup, false on signin · password-reset confirm)
- `passwordType` — `'new'` (autocomplete=`new-password`) | `'current'` (autocomplete=`current-password`)

**i18n**:
- "Show password" / "Hide password" (EN) / "비밀번호 보기" / "비밀번호 숨기기" (KR)
- "Minimum 8 characters" / "최소 8자"
- 길이 미터 메시지는 `${current} / ${max} characters` (EN) / `${current} / ${max}자` (KR)

### 5.3 `<OtpInput>` `{#otp-input-v1}` — FR-AUTH-2

**역할**: 6자리 숫자 OTP 입력. EmailOtpModal 내부 + (모바일 fallback) `/verify` 페이지에서 단독 사용.

**구조**:

```
  ┌──┐ ┌──┐ ┌──┐   ┌──┐ ┌──┐ ┌──┐
  │  │ │  │ │  │ — │  │ │  │ │  │   ← 각 칸 48×56px · radius-md · border-strong
  └──┘ └──┘ └──┘   └──┘ └──┘ └──┘     · 칸 사이 gap space-2 (8px), 3-3 분리 dash
       ↑ active focus (primary-600 ring)
```

**동작**:
- 각 칸: `<input type="text" inputmode="numeric" maxlength="1" pattern="[0-9]">`.
- 키 입력 → 다음 칸 자동 focus. Backspace → 이전 칸 focus + clear.
- Paste (6자리 숫자 클립보드) → 모든 칸 자동 분배 채움. submit 자동 트리거 (옵션).
- 1자리만 들어가면 모바일 keyboard 가 numeric pad 로 노출 (`inputmode="numeric"`).
- 비숫자 입력 차단 (regex filter on input event).

**상태**:
- empty → border-strong
- filled (해당 칸) → border-text-muted
- active (현재 focus) → border-primary-600 + ring-primary-600/40 3px
- error (전체 6칸) → border #b91c1c + 살짝 흔들림 (shake animation 200ms, prefers-reduced-motion 시 비활성)
- success (전체 6칸) → border-success-fg 일시 표시 후 모달 close

**접근성**:
- `<fieldset>` + `<legend>` "Verification code" / "인증 코드" — 스크린리더 그룹화.
- 각 칸 `aria-label="Digit 1 of 6"` / `"6자리 중 1번째"`.
- 에러 시 fieldset 하단에 `aria-live="polite"` 메시지.
- `prefers-reduced-motion` 시 shake 애니메이션 제거.

**Props**:
- `length` — default 6
- `onComplete(code: string)` — 모든 칸 채워지면 호출
- `onChange(code: string)` — 매 keystroke
- `error` — 외부 제어 boolean (서버 응답 후 ERR_OTP_INVALID 시 true)
- `autoFocus` — 모달 열릴 때 첫 칸 포커스

**i18n**:
- 6자리 숫자는 어느 locale 든 동일.
- legend 만 ko/en 분기.

### 5.4 `<ConsentGroup>` `{#consent-group-v1}` — FR-AUTH-9, 10

**역할**: signup 페이지의 동의 체크박스 묶음. **EN / KR 분기 컴포넌트** (variant 로 분리).

#### 5.4.1 EN variant — `<ConsentGroup variant="en">`

```
┌──────────────────────────────────────────────────────────────┐
│ ☐ I agree to the Terms of Service and Privacy Policy.       │  ← 필수
│                                                              │
│ ☐ Send me product updates and marketing emails. (optional)  │  ← 선택
└──────────────────────────────────────────────────────────────┘
```

- 2개 체크박스 (Terms+Privacy 1쌍 + Marketing 1).
- `Terms of Service` / `Privacy Policy` 는 텍스트 내 링크 (인라인) — 새 탭 (`target="_blank" rel="noopener"`).
- 필수 누락 시 submit 차단 + helper text 빨강.

#### 5.4.2 KR variant — `<ConsentGroup variant="ko">`

```
┌────────────────────────────────────────────────────────────────────┐
│ ☐ 전체 동의 (선택 항목 포함)                                        │  ← 마스터 체크박스
├────────────────────────────────────────────────────────────────────┤
│ ☐ [필수] 개인정보 수집·이용 동의 (PIPA §15)              [자세히 ▼]│
│   이메일, 비밀번호 해시, 기관명, 직책, 이용 의도 / 회원 탈퇴 시까지  │
│                                                                    │
│ ☐ [필수] 개인정보 제3자 제공 동의 (PIPA §17)             [자세히 ▼]│
│   한국 협력 병원 admin / 기관명, 이용 의도                          │
│                                                                    │
│ ☐ [필수] 개인정보 국외이전 동의 (PIPA §28-8)             [자세히 ▼]│
│   미국 (AWS us-east-1), 유럽 (AWS eu-west-1) / 이메일, 검색 로그    │
│                                                                    │
│ ☐ [선택] 광고성 정보 수신 동의 (정통망법 §50, 이메일)    [자세히 ▼]│
│   거부 시에도 가입 가능                                              │
└────────────────────────────────────────────────────────────────────┘
```

- 4개 분리 체크박스 (필수 3 + 선택 1) + 1개 "전체 동의" 마스터.
- 각 항목 우측 `[자세히 ▼]` 토글 → expand 시 dev-spec FR-AUTH-9 의 항목·목적·보유·거부 시 효과 4줄 표시.
- "전체 동의" 체크 → 4개 모두 체크. 4개 모두 체크 → "전체 동의" 자동 체크. 부분 체크 시 indeterminate state.
- **각 체크박스는 시각·논리적으로 분리** (PIPA §15·§17 위반 방지 — researcher §3.1 D 인용).

**상태**:
- 필수 항목 1개라도 unchecked 시 submit 버튼 disabled.
- helper text: "Continue 버튼은 [필수] 항목 3개 모두 동의해야 활성화됩니다."

**접근성**:
- 각 체크박스 `<label>` 클릭 가능 영역 = 라벨 전체.
- "자세히 ▼" 는 `<button aria-expanded>` 별도 버튼 (체크박스와 분리).
- 마스터 체크박스 indeterminate 상태는 `aria-checked="mixed"`.

### 5.5 `<FormError>` `{#form-error-v1}` — FR-AUTH-1, 4, 6 모든 에러 처리

**역할**: 폼 상단 + 필드 인라인의 에러 메시지 표시.

#### 5.5.1 Top-of-form variant

```
┌──────────────────────────────────────────────────────────────┐
│ ⚠  An account already exists for alice@acme.ai.              │  ← bg #fef2f2 · border #b91c1c · padding 12×16
│    Sign in instead →                                         │     · radius-md
└──────────────────────────────────────────────────────────────┘
```

- 위치: `<form>` 최상단, 첫 필드 위.
- 색: bg `#fef2f2` (Error light) / fg `#b91c1c` (Error dark, 5.94:1).
- 아이콘: ⚠ 16px 좌측.
- 액션 링크 (있으면): 우측 또는 다음 줄.
- `role="alert"` + `aria-live="assertive"` — 스크린리더 즉시 읽음.
- 표시 후 첫 invalid 필드로 자동 focus 이동.

#### 5.5.2 Field-level variant

이미 `<TextInput error="...">` / `<PasswordInput error="...">` props 로 처리. helper 자리에 빨강 텍스트 + ⚠ 12px.

#### 5.5.3 에러 코드 → 메시지 매핑 (dev-spec §7.11 기반)

| ERR code | EN message | KR message | 위치 | 액션 |
|----------|-----------|-----------|------|------|
| `ERR_VALIDATION` | (field 별) "Email is required." 등 | "이메일을 입력해주세요." | field-level | 자동 focus |
| `ERR_AUTH_INVALID` | "Email or password is incorrect." | "이메일 또는 비밀번호가 일치하지 않습니다." | top-of-form | password clear + focus |
| `ERR_EMAIL_TAKEN` | "An account already exists for {email}. Sign in instead?" | "이미 가입된 계정입니다 ({email}). 로그인하시겠어요?" | top-of-form + email field | "Sign in instead" 링크 |
| `ERR_EMAIL_RECENTLY_DELETED` | "This email was recently used. Please wait 30 days or contact sales." | "최근 삭제된 계정입니다. 30일 후 재가입 가능합니다." | top-of-form | sales 링크 |
| `ERR_OTP_INVALID` | "Verification code is incorrect. {n} attempt(s) remaining." | "인증 코드가 올바르지 않습니다. {n}회 남음." | OTP 모달 하단 | OTP shake + focus 첫 칸 |
| `ERR_OTP_EXPIRED` | "Code expired. Request a new one." | "인증 코드가 만료되었습니다. 새 코드를 요청해주세요." | OTP 모달 | "Resend" 강조 |
| `ERR_OTP_LOCKED` | "Too many attempts. Request a new code." | "시도 횟수를 초과했습니다. 새 코드를 요청해주세요." | OTP 모달 | "Resend" 강조 |
| `ERR_RATE_LIMITED` | "Too many attempts. Try again in {n} {seconds}." | "요청이 너무 많습니다. {n}초 후 다시 시도해주세요." | top-of-form | submit disabled + 카운트다운 |
| `ERR_ACCOUNT_LOCKED` | "Account locked for 15 minutes due to repeated failures." | "반복된 실패로 계정이 15분간 잠겼습니다." | top-of-form | "Forgot password?" 강조 |
| `ERR_TOKEN_INVALID` | "This password reset link is invalid or expired. Request a new one." | "비밀번호 재설정 링크가 유효하지 않습니다. 새로 요청해주세요." | top-of-form | request 링크 |
| `ERR_INTERNAL` | "Something went wrong. Please try again." | "오류가 발생했습니다. 잠시 후 다시 시도해주세요." | top-of-form | retry 버튼 |

### 5.6 `<ApiKeyMaskedDisplay>` `{#api-key-masked-v1}` — FR-AUTH-8

**역할**: `/account` API Keys 섹션에서 API key 를 Stripe / Vercel 식 마스킹 + Reveal/Copy/Regenerate/Revoke 액션 제공.

**구조 (카드 레이아웃, dev-spec §FR-AUTH-8 단일 키 모델 v0.1)**:

```
┌────────────────────────────────────────────────────────────────────────┐
│ Default API key                                          [tier preview]│
│                                                                        │
│ ┌──────────────────────────────────────────────────┐ ┌────────────┐  │
│ │ rv_live_K8dF…3xQ2                                │ │ [Copy 📋] │  │  ← font-mono · text-base
│ └──────────────────────────────────────────────────┘ └────────────┘  │     · bg-bg-muted · radius-md
│                                                                        │
│ Created Apr 25, 2026 · Last used 2 hours ago                          │  ← text-sm / text-text-muted
│                                                                        │
│ ─────────────────────────────────────────────────────────────────     │
│                                                                        │
│ [Regenerate]   [Revoke]                                               │  ← Button ghost / Button danger
└────────────────────────────────────────────────────────────────────────┘
```

**마스킹 규칙** (dev-spec §FR-AUTH-8):
- 형식: `rv_live_` + 첫 4자 + `…` (U+2026 ellipsis) + 마지막 4자.
- 예: `rv_live_K8dF…3xQ2` (총 17자 시각).
- 평문은 **절대 GET response 에 포함되지 않음** (FR-AUTH-8 명시). Reveal once 는 별도 모달 (5.8).

**액션 버튼**:
- `[Copy 📋]` — 마스킹된 문자열을 클립보드에 복사 (full key 가 아니라 masked — 의도적, full key 는 reveal 모달 한 번만). 토스트 "Masked key copied. Use Regenerate for a new full key."
- `[Regenerate]` — 확인 모달 → POST {action: 'regenerate'} → ApiKeyRevealModal 자동 열림 (새 full key 1회 노출).
- `[Revoke]` — 확인 모달 → POST {action: 'revoke'} → 카드가 "No active key" empty state 로 전환 + `[Generate new key]` CTA.

**상태**:
- **active** (key 존재) — 위 구조.
- **no-active-key** (revoke 후) — 카드 내 empty state:
  ```
  ┌────────────────────────────────────────────────────────────────────┐
  │ No active API key.                                                 │
  │                                                                    │
  │ Programmatic access (curl, SDK) is currently disabled.             │
  │                                                                    │
  │ [ Generate new key ]                                               │
  └────────────────────────────────────────────────────────────────────┘
  ```
- **loading** (GET /api/account/api-key 진행 중) — skeleton 카드 (마스킹 자리 회색 막대).
- **error** (GET 실패) — 카드 내 inline error + retry 버튼.

**i18n (KR)**:
- `Default API key` → `기본 API 키`
- `Created … · Last used …` → `생성: … · 마지막 사용: …`
- `[Regenerate]` → `[재발급]`, `[Revoke]` → `[폐기]`, `[Generate new key]` → `[새 키 발급]`
- 카드 라벨은 KR 30% 짧음 가정 → 카드 너비 동일 유지.

### 5.7 `<EmailOtpModal>` `{#email-otp-modal-v1}` — FR-AUTH-2

**역할**: signup 직후 자동 열림. 6자리 OTP 입력. dev-spec §FR-AUTH-2 의 데모 skip-flag (`BUYER_AUTH_SKIP_EMAIL_VERIFY=true`) 활성 시 본 모달은 **열리지 않음** (signup 직후 ApiKeyRevealModal 만 열림).

**구조** (480px 폭, 데스크톱 중앙 정렬, scrim 50% black):

```
              ╔══════════════════════════════════════════╗
              ║                                       [×]║
              ║  Verify your email                       ║
              ║                                          ║
              ║  We sent a 6-digit code to               ║
              ║  alice@acme.ai. The code expires         ║
              ║  in 9:42.                                ║  ← TTL countdown live
              ║                                          ║
              ║  ┌──┐ ┌──┐ ┌──┐   ┌──┐ ┌──┐ ┌──┐         ║  ← <OtpInput> 5.3
              ║  │  │ │  │ │  │ — │  │ │  │ │  │         ║
              ║  └──┘ └──┘ └──┘   └──┘ └──┘ └──┘         ║
              ║                                          ║
              ║  [ ⚠ Code is incorrect. 2 attempts left.]║  ← 5.5.2 inline error
              ║                                          ║
              ║  ─────────────────────────────────────── ║
              ║                                          ║
              ║  Didn't get it?  [Resend code] (60s)     ║  ← Resend cooldown
              ║                                          ║
              ║  Use API key only — verify later         ║  ← 보조 링크
              ║                                          ║
              ╚══════════════════════════════════════════╝
```

**열림 trigger**:
- signup 201 응답 + `BUYER_AUTH_SKIP_EMAIL_VERIFY=false` 시 자동.
- (모바일) 이메일 OTP 링크 → `/verify` 페이지로 별도 진입 (모달 아님).

**닫기**:
- ⓧ 버튼 → "Skip for now? You can verify later from your account." 확인 토스트 후 close.
- Esc 키 → 동일.
- Backdrop 클릭 → close 비활성 (실수 방지).
- OTP 6자리 정확 입력 + 200 응답 → 자동 close + ApiKeyRevealModal 자동 열림.

**Resend**:
- 버튼 `[Resend code]`. 클릭 시 60초 쿨다운 (counter 표시).
- Rate limit 3/15min/account 초과 시 버튼 disabled + helper "Limit reached. Try again in {n} minutes."

**TTL countdown**:
- 우측 상단 또는 본문에 `mm:ss` 형식 카운트다운 (10:00 → 0:00).
- 0:00 도달 시 OTP 입력 비활성 + "Code expired. Request a new one." 메시지 + Resend 강조.
- `aria-live="off"` (매초 읽지 않게) — 카운트다운은 시각만.

**에러 처리** (5.5.3 에러 코드 표 참조):
- `ERR_OTP_INVALID` — shake + 잔여 시도 횟수 표시 + OTP clear + focus 첫 칸.
- `ERR_OTP_EXPIRED` — Resend 강조.
- `ERR_OTP_LOCKED` — 모달 내 메시지 "Too many attempts. Request a new code." + Resend 강조.

**보조 링크**:
- `Use API key only — verify later` — 모달 close + dashboard 진입 (검색 자유, /orders/new 진입 시 /verify redirect).

**접근성**:
- `role="dialog"` + `aria-modal="true"` + `aria-labelledby="otp-modal-title"`.
- focus trap: Tab 이 모달 내부에서만 순환. Tab 순서: ⓧ → OTP 첫 칸 → ... → OTP 6번째 → Resend → 보조 링크.
- 열릴 때 첫 OTP 칸 자동 focus.
- 닫힐 때 trigger 요소 (signup submit 버튼) 로 focus 복귀.
- ARIA 라이브 영역: 에러 메시지 (`role="alert"`), TTL 만료 알림.

**i18n (KR)**:
- 제목: `이메일 인증`
- 본문: `alice@acme.ai 로 6자리 인증 코드를 보냈습니다. 코드는 9:42 후 만료됩니다.`
- 버튼: `[코드 재전송] (60초)`, 보조 링크 `API 키만 사용 — 나중에 인증`

### 5.8 `<ApiKeyRevealModal>` `{#api-key-reveal-modal-v1}` — FR-AUTH-1, 8

**역할**: signup 직후 + Regenerate 직후 새 API key 평문을 **1회만** 노출. Stripe / Vercel 식.

**구조** (560px 폭, scrim 50% black):

```
        ╔══════════════════════════════════════════════════════════╗
        ║                                                       [×]║
        ║                                                          ║
        ║  🔑  Save your API key                                   ║
        ║                                                          ║
        ║  This is the only time you'll see the full key.          ║  ← Bold warning
        ║  RadiVault does not store the plaintext value.           ║
        ║  If you lose it, you'll need to regenerate.              ║
        ║                                                          ║
        ║  ┌────────────────────────────────────────────┐ ┌──────┐║
        ║  │ rv_live_K8dF7sX9aB2cD4eF6gH8iJ0kL2mN4oP6q… │ │[Copy]║  ← font-mono · text-sm
        ║  │ R8sT0uV2wX3xQ2                             │ │ 📋   ║     · bg #fffbeb (warning tint)
        ║  └────────────────────────────────────────────┘ └──────┘║     · selectable (user-select: all)
        ║                                                          ║
        ║  Use this key in your `Authorization: Bearer …` header.  ║
        ║  See [API documentation →]                               ║
        ║                                                          ║
        ║  ─────────────────────────────────────────────────────── ║
        ║                                                          ║
        ║  ☐ I have saved my key in a secure location.             ║  ← 체크해야 [Done] 활성
        ║                                                          ║
        ║                                            [Done]        ║  ← Primary button, disabled until ☑
        ╚══════════════════════════════════════════════════════════╝
```

**열림 trigger**:
- signup 201 + EmailOtpModal close 직후 (또는 skip-flag true 시 signup 직후 즉시).
- `/account` Regenerate 버튼 → 확인 → POST 200 직후.

**닫기**:
- ⓧ 버튼 → "Are you sure? You won't see this key again." 확인 모달 (이중 확인).
- Esc 키 → 동일 확인 모달.
- Backdrop 클릭 → close 비활성.
- `[Done]` 버튼 → 평문 메모리 클리어 + 모달 close.

**1회 노출 보장**:
- 평문은 frontend `sessionStorage` 에 임시 보관 (signup response → 모달 mount 시점).
- 모달 close 시 `sessionStorage.removeItem('apiKeyRevealOnce')`.
- 새로고침 시 sessionStorage 가 살아 있으면 모달 재표시 (의도적 — close 전 새로고침 사고 방지). close 후 새로고침 시 영구 미노출.

**Copy 버튼**:
- 클릭 시 평문 클립보드 복사 + 토스트 "API key copied to clipboard."
- 30초 후 클립보드 자동 clear (가능한 경우 — Clipboard API 지원 브라우저).

**경고 메시지 (Bold warning)**:
- "This is the only time you'll see the full key." — `text-base / font-semibold / text-text-strong`.
- 배경: `#fffbeb` (warning light) · 좌측 4px border `#b45309` (warning dark).

**확인 체크박스**:
- `☐ I have saved my key in a secure location.`
- 체크해야 `[Done]` 버튼 활성화 (실수 방지).

**접근성**:
- `role="dialog"` + `aria-modal="true"` + `aria-labelledby="apikey-modal-title"`.
- focus trap, 열릴 때 Copy 버튼 focus.
- 평문 표시 input `aria-label="Your API key. This is the only time it will be shown."` — 스크린리더 명시.
- 닫힐 때 (signup 흐름) → `/search` 로 redirect, focus 는 페이지 H1 으로.

**i18n (KR)**:
- 제목: `API 키를 저장하세요`
- 경고: `API 키 평문은 지금 한 번만 표시됩니다. RadiVault 는 평문을 저장하지 않습니다. 분실 시 재발급이 필요합니다.`
- 안내: `이 키를 \`Authorization: Bearer …\` 헤더에 사용하세요. [API 문서 →]`
- 체크박스: `☐ 안전한 위치에 키를 저장했습니다.`
- 버튼: `[완료]`

---

## 6. 화면별 ASCII 와이어프레임 (60+ chars wide, 데스크톱 1280)

### 6.1 `/signup` (EN) — S-1 EN

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [◆ RadiVault]  Product  Solutions  Developers  Docs  Pricing    EN | KR │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                       ┌──────────────────────────────┐                   │
│                       │                              │                   │
│                       │  Create your account         │  ← text-3xl       │
│                       │                              │     bold          │
│                       │  Already have one?           │  ← text-sm muted  │
│                       │  Sign in →                   │     primary link  │
│                       │                              │                   │
│                       │  Email * required            │                   │
│                       │  ┌────────────────────────┐  │  ← <TextInput>    │
│                       │  │ alice@acme.ai          │  │                   │
│                       │  └────────────────────────┘  │                   │
│                       │                              │                   │
│                       │  Password (8–64 chars)       │                   │
│                       │  ┌────────────────────┐ ┌──┐ │  ← <PasswordInput>│
│                       │  │ •••••••••          │ │👁│ │     + meter       │
│                       │  └────────────────────┘ └──┘ │                   │
│                       │  ▰▰▰▰▱▱▱▱  9 / 64 chars      │                   │
│                       │                              │                   │
│                       │  Organization * required     │                   │
│                       │  ┌────────────────────────┐  │                   │
│                       │  │ Acme AI Inc.           │  │                   │
│                       │  └────────────────────────┘  │                   │
│                       │                              │                   │
│                       │  Intended use * required     │                   │
│                       │  ○ Research                  │  ← radio group    │
│                       │  ● Commercial AI             │                   │
│                       │  ○ Clinical trial            │                   │
│                       │  ○ Other                     │                   │
│                       │                              │                   │
│                       │  ─────────────────────────── │                   │
│                       │                              │                   │
│                       │  ☐ I agree to the Terms of   │  ← <ConsentGroup  │
│                       │    Service and Privacy Policy│      variant=en>  │
│                       │                              │                   │
│                       │  ☐ Send me product updates   │                   │
│                       │    (optional)                │                   │
│                       │                              │                   │
│                       │  [    Create account    ]    │  ← Primary CTA lg │
│                       │                              │     (disabled if  │
│                       │                              │      ToS☐)        │
│                       │  By signing up you'll        │                   │
│                       │  receive a free preview      │  ← text-xs muted  │
│                       │  API key.                    │                   │
│                       │                              │                   │
│                       └──────────────────────────────┘                   │
│                                                                          │
│                       single-column card 480px wide                      │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│ [Footer EN minimal — portal-redesign §5.7 재사용]                        │
└──────────────────────────────────────────────────────────────────────────┘
```

**카드 사양**:
- 폭 480px (모바일 < 480 시 padding 16, full width).
- 배경 `--color-bg`, border `--color-border`, `--shadow-card`, `--radius-lg` 12px.
- 페이지 배경 `--color-bg-muted` (signup 폼 강조).
- 페이지 수직 중앙 정렬 (min-height 100vh - header - footer).

### 6.2 `/ko/signup` (KR) — S-1 KR · PIPA 4종

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [◆ RadiVault]  제품  솔루션  기술  문서  가격문의           KR | EN    │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                  ┌──────────────────────────────────┐                    │
│                  │                                  │                    │
│                  │  회원가입                         │                    │
│                  │                                  │                    │
│                  │  이미 계정이 있으신가요?          │                    │
│                  │  로그인 →                        │                    │
│                  │                                  │                    │
│                  │  이메일 * 필수                    │                    │
│                  │  ┌────────────────────────────┐  │                    │
│                  │  │ alice@acme.ai              │  │                    │
│                  │  └────────────────────────────┘  │                    │
│                  │                                  │                    │
│                  │  비밀번호 (8~64자)                │                    │
│                  │  ┌────────────────────┐ ┌──┐    │                    │
│                  │  │ •••••••••          │ │👁│    │                    │
│                  │  └────────────────────┘ └──┘    │                    │
│                  │  ▰▰▰▰▱▱▱▱  9 / 64자              │                    │
│                  │                                  │                    │
│                  │  소속 기관 * 필수                  │                    │
│                  │  ┌────────────────────────────┐  │                    │
│                  │  │ Acme AI Inc.               │  │                    │
│                  │  └────────────────────────────┘  │                    │
│                  │                                  │                    │
│                  │  이용 목적 * 필수                  │                    │
│                  │  ○ 연구                           │                    │
│                  │  ● 상업적 AI 개발                 │                    │
│                  │  ○ 임상 시험                      │                    │
│                  │  ○ 기타                           │                    │
│                  │                                  │                    │
│                  │  ─────────────────────────────── │                    │
│                  │                                  │                    │
│                  │  ☐ 전체 동의 (선택 항목 포함)     │                    │
│                  │  ─────────────────────────────── │                    │
│                  │  ☐ [필수] 개인정보 수집·이용 동의  │  ← <ConsentGroup  │
│                  │     (PIPA §15)        [자세히 ▼] │      variant=ko>  │
│                  │  ☐ [필수] 제3자 제공 동의         │                    │
│                  │     (PIPA §17)        [자세히 ▼] │                    │
│                  │  ☐ [필수] 국외이전 동의           │                    │
│                  │     (PIPA §28-8)      [자세히 ▼] │                    │
│                  │  ☐ [선택] 광고성 정보 수신 동의    │                    │
│                  │     (정통망법 §50)    [자세히 ▼] │                    │
│                  │                                  │                    │
│                  │  [      회원가입       ]          │  ← 필수 3개 미체크 │
│                  │                                  │     시 disabled    │
│                  │                                  │                    │
│                  │  가입 시 무료 프리뷰 API 키가      │                    │
│                  │  자동 발급됩니다.                  │                    │
│                  │                                  │                    │
│                  └──────────────────────────────────┘                    │
│                                                                          │
│                  single-column card 520px (KR PIPA 항목 4 → 약간 넓음)   │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│ [Footer KR — portal-redesign §5.8 재사용 — 한국 법적 블록 포함]         │
└──────────────────────────────────────────────────────────────────────────┘
```

### 6.3 `/signin` (EN) — S-2 EN

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [◆ RadiVault]  Product  Solutions  Developers  Docs  Pricing    EN | KR │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                           ┌────────────────────────┐                     │
│                           │                        │                     │
│                           │  Sign in               │                     │
│                           │                        │                     │
│                           │  Email                 │                     │
│                           │  ┌──────────────────┐  │                     │
│                           │  │ alice@acme.ai    │  │                     │
│                           │  └──────────────────┘  │                     │
│                           │                        │                     │
│                           │  Password              │                     │
│                           │  ┌──────────────┐ ┌──┐ │                     │
│                           │  │ •••••••••    │ │👁│ │                     │
│                           │  └──────────────┘ └──┘ │                     │
│                           │                        │                     │
│                           │  ☑ Remember me         │                     │
│                           │              Forgot    │                     │
│                           │              password? │  ← right-aligned    │
│                           │                        │                     │
│                           │  [   Sign in    ]      │                     │
│                           │                        │                     │
│                           │  ─────────────────     │                     │
│                           │                        │                     │
│                           │  Don't have an account?│                     │
│                           │  Sign up →             │                     │
│                           │                        │                     │
│                           └────────────────────────┘                     │
│                                                                          │
│                        compact card 400px wide                           │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│ [Footer EN minimal]                                                      │
└──────────────────────────────────────────────────────────────────────────┘
```

**Hidden 링크** (dev-spec §FR-AUTH-4):
- "Sign in with API key (deprecated)" → `/signin/legacy` — 본 페이지에서는 노출하지 않음 (deprecated). dev 환경 only.

### 6.4 `/ko/signin` (KR) — S-2 KR

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [◆ RadiVault]  제품  솔루션  기술  문서  가격문의           KR | EN    │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                           ┌────────────────────────┐                     │
│                           │                        │                     │
│                           │  로그인                 │                     │
│                           │                        │                     │
│                           │  이메일                 │                     │
│                           │  ┌──────────────────┐  │                     │
│                           │  │ alice@acme.ai    │  │                     │
│                           │  └──────────────────┘  │                     │
│                           │                        │                     │
│                           │  비밀번호                │                     │
│                           │  ┌──────────────┐ ┌──┐ │                     │
│                           │  │ •••••••••    │ │👁│ │                     │
│                           │  └──────────────┘ └──┘ │                     │
│                           │                        │                     │
│                           │  ☑ 로그인 유지          │                     │
│                           │       비밀번호 찾기 →    │                     │
│                           │                        │                     │
│                           │  [   로그인     ]       │                     │
│                           │                        │                     │
│                           │  ───────────────────   │                     │
│                           │                        │                     │
│                           │  계정이 없으신가요?      │                     │
│                           │  회원가입 →             │                     │
│                           │                        │                     │
│                           └────────────────────────┘                     │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│ [Footer KR]                                                              │
└──────────────────────────────────────────────────────────────────────────┘
```

### 6.5 `/account` API Keys 섹션 — S-3 (EN, KR 동일 구조)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [◆ RadiVault]  Search  Orders  Account                          EN | KR │
├──────────────────────────────────────────────────────────────────────────┤
│ Account                                                                  │
│                                                                          │
│ ┌─ Sidebar ─────┐  ┌─ Main ──────────────────────────────────────────┐  │
│ │               │  │                                                  │  │
│ │ • Profile     │  │  API Keys                                        │  │
│ │ • API Keys ▶  │  │  Use these keys to authenticate programmatic     │  │
│ │ • Billing     │  │  requests (curl, SDK, CI pipelines).             │  │
│ │ • Compliance  │  │                                                  │  │
│ │ • Danger zone │  │  ┌──────────────────────────────────────────┐   │  │
│ │               │  │  │ Default API key            [tier preview]│   │  │
│ │               │  │  │                                          │   │  │
│ │               │  │  │ ┌──────────────────────┐ ┌────────────┐ │   │  │
│ │               │  │  │ │ rv_live_K8dF…3xQ2    │ │ [Copy 📋] │ │   │  │
│ │               │  │  │ └──────────────────────┘ └────────────┘ │   │  │
│ │               │  │  │                                          │   │  │
│ │               │  │  │ Created Apr 25 · Last used 2 hours ago   │   │  │
│ │               │  │  │                                          │   │  │
│ │               │  │  │ ──────────────────────────────────────── │   │  │
│ │               │  │  │                                          │   │  │
│ │               │  │  │ [Regenerate]   [Revoke]                  │   │  │
│ │               │  │  └──────────────────────────────────────────┘   │  │
│ │               │  │                                                  │  │
│ │               │  │  Single key per account (v0.1).                  │  │
│ │               │  │  Multiple labeled keys coming in v0.2.           │  │
│ │               │  │                                                  │  │
│ │               │  │  ──────────────────────────────────────────     │  │
│ │               │  │                                                  │  │
│ │               │  │  Rotate immediately if compromised.              │  │
│ │               │  │  Read [API key best practices →]                 │  │
│ │               │  │                                                  │  │
│ │               │  └──────────────────────────────────────────────────┘  │
│ │               │                                                        │
│ └───────────────┘                                                        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

**상태**:
- **active** — 위 와이어.
- **no-active-key** (revoke 후) — 카드 본문이 5.6 의 empty state 로 교체.
- **loading** — 카드 자리 skeleton (회색 막대 3줄).
- **error** — 카드 inline error + retry.

**Danger zone (sidebar 마지막 항목, 본 spec scope 명시)**:
- `Delete account` 버튼 → 확인 모달 ("type your email to confirm"). 모달 명세 = §11 Kyle 결정 필요 (dev-spec FR-AUTH-11 의 시각 패턴 미정).

---

## 7. EmailOtpModal 상세 (cross-reference §5.7)

§5.7 에 모달 자체 명세 완료. 본 §7 은 화면 흐름 내 위치만 보강.

| 시점 | 동작 |
|------|------|
| signup submit 직후 (skip-flag false) | EmailOtpModal 자동 열림. background 에 `/signup` 폼 어둡게 표시. |
| OTP 6자리 정확 | 모달 close → ApiKeyRevealModal 자동 열림 (chained modal). |
| 닫기 (보조 링크 "verify later") | 모달 close → 직접 `/search` 진입. emailVerified=false 상태로. |
| TTL 만료 | OTP 입력 비활성. Resend 강조. |
| Resend 클릭 | 60초 쿨다운 시작. 새 OTP 발송 (또는 dev/skip 시 stdout). |
| Resend rate limit (3/15min) | Resend 비활성 + helper "Limit reached." |

---

## 8. ApiKeyRevealModal 상세 (cross-reference §5.8)

§5.8 에 모달 자체 명세 완료. 본 §8 은 시나리오 보강.

### 8.1 Signup 직후 (chained from EmailOtpModal close)

```
[POST /api/auth/signup 201]
  ↓
[EmailOtpModal close (verified)]
  ↓
[sessionStorage.setItem('apiKeyRevealOnce', plaintext)]
  ↓
[ApiKeyRevealModal mount + display]
  ↓
[user clicks Copy → toast "API key copied"]
  ↓
[user checks ☑ "I have saved my key"]
  ↓
[Done 활성화] → click → sessionStorage.removeItem → modal close
  ↓
[redirect /search]
```

### 8.2 `/account` Regenerate 직후

```
[user clicks Regenerate]
  ↓
[Confirm modal: "Regenerate API key? Your current key will stop working immediately."]
  ↓
[confirm → POST /api/account/api-key {action:'regenerate'} 200]
  ↓
[sessionStorage.setItem('apiKeyRevealOnce', plaintext)]
  ↓
[ApiKeyRevealModal mount]
  ↓
[Done click] → sessionStorage clear → /account 새 마스킹 카드 표시
```

### 8.3 영구 미노출 보장

- 모달 close 후 새로고침 시 sessionStorage 비어 있음 → 모달 절대 재표시 안 함.
- 사용자가 Copy 안 하고 close 시도 → "Are you sure? You won't see this key again." 확인 모달 (이중 확인).
- 그래도 close 선택 시 → /account 카드만 마스킹 표시. "Lost your key? Regenerate." 안내.

---

## 9. 반응형 (mobile 375 / desktop 1280)

### 9.1 Signup (S-1)

| 디바이스 | 레이아웃 | 카드 폭 | 비고 |
|----------|---------|--------|------|
| Desktop ≥ 1280 | 페이지 중앙 카드 | 480px (EN) / 520px (KR) | 페이지 배경 `--color-bg-muted` |
| Tablet 768~1279 | 페이지 중앙 카드 | 480 / 520px | 동일 |
| Mobile 375~767 | full-width, padding-x 16px | 100% - 32px | 카드 border / shadow 제거, 페이지 배경 `--color-bg` |

dev-spec NFR §5 에 모바일 명시는 없으나, signup 은 **buyer 의 첫 인상** + 글로벌 marketing inbound 가 모바일일 수 있어 mobile 지원 필수. portal-redesign §4.9 의 `bp-mobile ≥ 375px` 따름.

### 9.2 Signin (S-2)

| 디바이스 | 카드 폭 |
|----------|--------|
| Desktop / Tablet | 400px |
| Mobile | full-width - 32px |

### 9.3 Account API Keys (S-3)

dev-spec / portal-redesign 일관 — `/account` 는 **데스크톱 우선**. Mobile 은 sidebar 가 상단 탭으로 변형, 카드는 full-width.

| 디바이스 | sidebar | 카드 |
|----------|---------|------|
| Desktop ≥ 1024 | 좌측 220px sticky | 우측 main, max-w 720px |
| Tablet | 상단 horizontal tab | full-width, max-w 720px |
| Mobile | 상단 horizontal tab (스크롤 가능) | full-width - 32px |

### 9.4 모달 (EmailOtp · ApiKeyReveal)

| 디바이스 | 모달 폭 | 위치 |
|----------|--------|------|
| Desktop / Tablet | 480 / 560px | 페이지 중앙, scrim 50% |
| Mobile < 768 | 100% - 32px | 화면 중앙 또는 bottom sheet 변형 (옵션) |

ApiKeyRevealModal 의 평문 표시 input 은 mobile 에서 줄바꿈 (`word-break: break-all` + `font-mono text-xs`).

---

## 10. 접근성 (WCAG 2.1 AA)

dev-spec §5 NFR a11y "WCAG 2.1 AA — form label-input 페어, focus order, error message ARIA-live, contrast ratio ≥ 4.5:1" 충족.

### 10.1 Form 일반

- 모든 `<input>` 은 `<label for="…">` 명시 페어 (TextInput 5.1 강제).
- `aria-required="true"` (필수), `aria-invalid="true"` (에러 시), `aria-describedby` (helper / error 메시지 id).
- 에러 메시지: `role="alert"` + `aria-live="assertive"` (FormError 5.5).
- 색만으로 정보 전달 금지 — 에러는 색 + ⚠ 아이콘 + 텍스트 3중 시각.

### 10.2 Password show/hide

- 토글 버튼 `<button type="button" aria-label="Show password">` / `aria-pressed="true|false"`.
- 키보드 도달 가능 (Tab 순서: input → toggle → next field).

### 10.3 OTP

- `<fieldset>` + `<legend>` 그룹화.
- 각 칸 `aria-label="Digit N of 6"`.
- 에러 시 fieldset 하단 `aria-live="polite"` 메시지.
- shake 애니메이션 `prefers-reduced-motion: reduce` 시 비활성.

### 10.4 Modal

- `role="dialog"` + `aria-modal="true"` + `aria-labelledby="<title-id>"`.
- focus trap: Tab 이 모달 내부 순환 (첫/마지막 요소 wrap).
- Esc 키로 close (단 EmailOtp 는 confirm 토스트, ApiKeyReveal 은 확인 모달).
- backdrop 클릭으로 close 비활성 (실수 방지).
- 열릴 때 첫 interactive 요소 focus (OTP 첫 칸 / Copy 버튼).
- 닫힐 때 trigger 요소로 focus 복귀.

### 10.5 색 대비 (4.5:1 이상)

| 조합 | 대비 | 상태 |
|------|------|------|
| `--color-text` (#0f172a) on `--color-bg` (#fff) | 18.69:1 | AAA |
| `--color-primary-600` (#2563eb) on `--color-bg` | 4.54:1 | AA |
| `--color-text-muted` (#64748b) on `--color-bg` | 4.79:1 | AA |
| Error fg `#b91c1c` on `--color-bg` | 5.94:1 | AA |
| Error fg on Error bg `#fef2f2` | 5.69:1 | AA |
| Warning fg `#b45309` on Warning bg `#fffbeb` | 4.51:1 | AA (경계) |
| Success fg `#047857` on Success bg `#ecfdf5` | 5.18:1 | AA |

### 10.6 키보드 탐색 순서

#### Signup (S-1)
Skip link → Header nav → Email → Password → Show/hide → Organization → Intent radios (1→4) → ToS checkbox → Marketing checkbox (또는 KR PIPA 4종) → Submit → Footer

#### Signin (S-2)
Skip link → Header → Email → Password → Show/hide → Remember me → Forgot password → Submit → Sign up link → Footer

#### Account API Keys (S-3)
Skip link → Header → Sidebar items → Main heading → Copy → Regenerate → Revoke → Best practices link

#### EmailOtpModal
Close ⓧ → OTP cell 1 → ... → cell 6 → Resend → "verify later" 보조 링크 → (cycle back to ⓧ)

#### ApiKeyRevealModal
Close ⓧ → Copy → API doc link → "I have saved my key" checkbox → Done → (cycle)

---

## 11. 국제화 (i18n) 규칙

dev-spec §5 NFR i18n: "EN + KR 페이지, locale routing (`/ko/...`), 모든 user-facing 문자열 i18n key 추출".

### 11.1 페이지 변형

| EN | KR | 차이점 |
|----|-----|-------|
| `/signup` | `/ko/signup` | Consent 그룹 (5.4 EN 2개 ↔ KR 5개 PIPA) · 카드 폭 480 ↔ 520 |
| `/signin` | `/ko/signin` | 라벨 텍스트만 |
| `/password-reset` · `/password-reset/confirm` | `/ko/...` | 라벨 텍스트만 |
| `/verify` | `/ko/verify` | 라벨 텍스트만 |
| `/account` | `/ko/account` | 라벨 텍스트만 |

### 11.2 KR 라벨 표 (signup S-1)

| 영역 | EN | KR |
|------|-----|-----|
| 페이지 제목 | Create your account | 회원가입 |
| Email | Email | 이메일 |
| Password | Password | 비밀번호 |
| 길이 헬퍼 | (8–64 characters) | (8~64자) |
| Show password | Show password | 비밀번호 보기 |
| Organization | Organization | 소속 기관 |
| Intent group | Intended use | 이용 목적 |
| Intent: research | Research | 연구 |
| Intent: commercial-ai | Commercial AI | 상업적 AI 개발 |
| Intent: clinical-trial | Clinical trial | 임상 시험 |
| Intent: other | Other | 기타 |
| Required marker | * required | * 필수 |
| Submit | Create account | 회원가입 |
| 헬퍼 (free preview key) | By signing up you'll receive a free preview API key. | 가입 시 무료 프리뷰 API 키가 자동 발급됩니다. |
| Sign in 링크 | Already have one? Sign in → | 이미 계정이 있으신가요? 로그인 → |

### 11.3 KR 텍스트 길이 가정

- portal-redesign §5.2 "영문 대비 KR 약 30% 짧음" 따름.
- 단 PIPA 동의 라벨은 법조항 인용 (`PIPA §15`, `정통망법 §50`) 으로 EN 보다 길어짐 → KR 카드 폭 +40px (520).
- 버튼 라벨 KR 짧음 → 버튼 너비 동일 유지 (`min-width: 120px`).
- Pretendard Variable 의 한글 자간이 Inter 영문 자간과 시각 균형이 맞는지 dev 에서 확인 (a11y 검수 사항).

### 11.4 날짜·시간 포맷

- `Created Apr 25, 2026` (EN, MMM D, YYYY) / `생성: 2026년 4월 25일` (KR, YYYY년 M월 D일)
- `Last used 2 hours ago` (EN, relative) / `마지막 사용: 2시간 전` (KR, relative)
- OTP TTL countdown: `9:42` (양 locale 동일)
- 라이브러리: `date-fns` + locale `en-US` / `ko`.

---

## 12. 컴플라이언스 어휘 (lint 대상)

portal-redesign §5.10 (Compliance Badge) + §5.3 의 어휘 lint 규칙을 본 spec 의 모든 텍스트에 동일 적용 (FR-NFR-7).

**금지 어휘** (CI lint fail):
- EN: `certified`, `guaranteed`, `HIPAA-compliant`, `FDA-approved`, `secure 100%`
- KR: `인증됨`, `보장`, `HIPAA 준수 인증`, `FDA 승인`, `100% 안전`

**허용 어휘 (compliance 표현)**:
- EN: `compliant` (PIPA 만), `aligned` (ISO/HIPAA), `in preparation` (SOC 2)
- KR: `준수` (PIPA 만), `정렬` (ISO/HIPAA), `준비 중` (SOC 2), `기준` (HIPAA 비식별화 기준)

**본 spec 텍스트 self-audit** (위 와이어·메시지 검사):
- ✅ "PIPA §28-8 준수" — 허용 (Compliance Badge 컴포넌트 내부)
- ✅ "안전한 위치에 키를 저장했습니다" — "안전" 형용사는 사용자 행위 묘사이므로 허용 (단, "100% 안전" 형식 금지 자체-감시).
- ✅ "Strong length" — 비밀번호 길이 묘사. "Strong password" 형식은 허용 (compliance 표현이 아님).
- ✅ 본 spec 문서 어디에도 "certified" / "guaranteed" / "인증됨" / "보장" 미사용.

**개발자 주의**: API key 안내 메시지에 "guaranteed delivery" 같은 표현 사용 금지. 대신 "RadiVault does not store the plaintext value." 같은 사실 진술 권장.

---

## 13. 컴포넌트 ↔ FR 매핑 cross-reference

dev-spec FR 와 본 spec 컴포넌트의 추적 매트릭스 (QA 검수용):

| FR | 화면 | 컴포넌트 |
|----|------|---------|
| FR-AUTH-1 (Signup 폼 + endpoint) | S-1 EN/KR | TextInput, PasswordInput, ConsentGroup (en/ko), FormError, Button (primary lg) |
| FR-AUTH-2 (Email OTP) | EmailOtpModal | OtpInput, Button (Resend ghost), FormError |
| FR-AUTH-3 (Password 정책) | S-1, password-reset confirm | PasswordInput (showStrengthMeter=true) |
| FR-AUTH-4 (Signin) | S-2 EN/KR | TextInput, PasswordInput, FormError, Button (primary), checkbox (Remember me) |
| FR-AUTH-5 (Signout) | Header dropdown (별도 spec scope) | — (재사용 Button) |
| FR-AUTH-6 (Password reset) | /password-reset, /confirm | TextInput (이메일), PasswordInput (new), FormError |
| FR-AUTH-7 (Session 모델) | (UI 시각 영향 없음, middleware) | — |
| FR-AUTH-8 (API key reveal-once) | S-3 | ApiKeyMaskedDisplay, ApiKeyRevealModal, Button (regenerate ghost / revoke danger) |
| FR-AUTH-9 (PIPA 동의 4종) | S-1 KR | ConsentGroup (variant=ko) |
| FR-AUTH-10 (Marketing opt-in) | S-1 EN | ConsentGroup (variant=en, marketing item) |
| FR-AUTH-11 (회원탈퇴) | S-3 Danger zone (모달 명세는 §14 Kyle 결정 필요) | TextInput (이메일 확인), Button (danger) |
| FR-AUTH-12 (데모 skip-flag) | (UI 분기) | EmailOtpModal 비활성 (skip-flag true 시 모달 미표시) |

---

## 14. Kyle 결정 필요 (Open questions)

다음 항목은 95% 확신 미달 — 메인 세션에서 Kyle 결정 후 본 spec v0.2 에 반영.

### Q1. ApiKeyMaskedDisplay 의 Copy 버튼은 마스킹 문자열을 복사하는가, full key 를 복사하는가?

- **본 spec 기본값 (Stripe 식)**: 마스킹 문자열만 복사 (예: `rv_live_K8dF…3xQ2`). full key 는 Reveal once 모달에서만.
- **대안 (개발자 편의 우선)**: Copy 시 confirm 모달 → "Reveal full key once?" → confirm → API call → full key 복사. (Vercel 식)
- **결정 필요 이유**: 보안 vs UX 트레이드오프. Stripe 패턴이 더 보수적이지만 사용자가 매번 Regenerate 해야 함.

### Q2. Account → "Danger zone" → Delete account 모달의 시각 패턴?

- dev-spec FR-AUTH-11 은 "type your email to confirm" 만 명시. 모달 색·레이아웃·grace period 표시 미정.
- **본 spec 기본값**: 일반 modal + Error 색 (border `#b91c1c`, 헤더 `🚨`). 30일 grace 안내 + hard delete 일자 표시.
- 결정 시 §6.5 Danger zone 와이어 보강 + 신규 모달 컴포넌트 §5.9 추가.

### Q3. 모바일에서 모달이 bottom-sheet 로 변형되는가, 중앙 모달 그대로인가?

- iOS Safari 의 키보드 오버레이로 OTP 모달 가려질 위험.
- **본 spec 기본값**: 중앙 모달 그대로 (모바일도 viewport 100% - 32px). 키보드 노출 시 자동 scroll-into-view.
- 대안: bottom sheet (drag handle + 80% height). 추가 컴포넌트 명세 필요.

### Q4. "전체 동의" 마스터 체크박스 클릭 시 "선택" 항목 (PIPA D · 마케팅) 도 함께 체크되는가?

- 본 spec 기본값: **체크됨** (가장 흔한 한국 SaaS 패턴, Toss · Naver 동일).
- 단 PIPA dark pattern 위반 우려 (선택 항목을 강제 체크 유도). 대안: "전체 동의" 가 필수만 체크 + 선택은 별도 안내.
- 법무 자문 필요.

### Q5. UI_GUIDE 신규 토큰 등록?

- §4 말미에 제안한 `--color-otp-cell-active`, `--input-height-md` 의 공식 등록 여부.
- 본 spec 은 portal-redesign §4 토큰 조합으로 도출 가능 (스킵해도 됨), 하지만 일관성 강화 위해 공식화 권고.

---

## 15. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|------|------|--------|------|
| 0.1 | 2026-04-25 | @designer (Claude Opus 4.7) | 최초 작성. dev-spec-buyer-auth.md FR-AUTH-1..12 기반 5 폼 컴포넌트 + 2 모달 + 3 화면 (EN/KR 변형) 와이어 정의. portal-redesign §4 토큰 / §5 공유 컴포넌트 재사용 명시. Kyle 결정 5건. |

---

### NEXT_STEP

- 완료 산출물: `docs/specs/design-spec-buyer-auth.md`
- 제안 다음 단계: `@developer` — claude 브랜치에서 `buyer-auth` 구현 착수. 우선순위: **(1) S-1 signup (EN+KR PIPA) → (2) S-3 /account API Keys + ApiKeyRevealModal → (3) S-2 signin → (4) EmailOtpModal → (5) password-reset flow** (planner 권고 따름).
- UI_GUIDE.md 갱신 제안: `--color-otp-cell-active`, `--input-height-md` 두 토큰 후보 (Kyle Q5 결정 후 공식 등록).
- 추가 디자인 필요: Delete account 모달 시각 패턴 (Kyle Q2), bottom-sheet 변형 (Kyle Q3) — 후속 design-spec append 또는 본 spec v0.2.
- Kyle 결정 필요 사항: §14 의 Q1~Q5 5건.
