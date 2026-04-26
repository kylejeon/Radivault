# QA Report — D-13 CEO 데모 최종 리허설

**Status**: 검수 완료 → **재검수 완료 (post-fix)**
**판정**: ~~NEEDS-FIX (BLOCKER 2건 — D-13 데모 차단)~~ → **READY-TO-DEMO (BLOCKER 0건, §12 참조)**
**검수자**: @qa Claude (Opus 4.7)
**검수 일자**: 2026-04-25 (v1) → 2026-04-25 (v2 재검수, post-fix)
**대상 데모일**: 2026-05-08 (D-13)
**대상 커밋 범위**: `5b477ea..03196cd` (v1) → `5b477ea..e7dde74` (v2, BLOCKER fix 2건 추가)
**Baseline 회귀 기준**:
- `docs/qa/qa-report-portal-redesign-v2.md` (READY-TO-DEMO, PASS 12)
- `docs/qa/qa-report-buyer-auth.md` (READY-TO-DEMO, 23 PASS / 5 PARTIAL / 2 FAIL)

---

## 1. 요약 (3줄)

1. 누적 자동화 테스트 121 unit + 67 pytest = **188 PASS**, 그러나 **playwright 41 중 2 FAIL** (signup confirm-password 미동기화 + signin → /search 무한리다이렉트).
2. 라이브 dev server 골든패스 1회 실주행 결과 **golden #3 (signin → /search) 와 #4 (검색 250 study) 가 무한 리다이렉트로 BLOCK**. cookie 는 정상 발급되지만 `/search`/`/dashboard`/`/studies` 가드가 v0.1 legacy `apiKey` 필드만 보고 v0.2 `buyerPk` 세션을 redirect 으로 보냄 → `/signin` ↔ `/search` ping-pong.
3. `pnpm build` (production build) 가 HIGH-1 fix 의 over-strict guard 로 **prerender 단계에서 throw → 빌드 실패**. dev mode (`pnpm dev`) 로 데모 시연하면 우회되지만 deploy 경로 깨짐.

---

## 2. D-13 데모 골든패스 10단계 매트릭스

| # | 단계 | 결과 | 증거 / 비고 |
|---|---|---|---|
| 1 | 홈(/) → 우상단 Sign in 버튼 → /signin | **PASS** | `MarketingNav.tsx` L.73-78 — 항상 노출되는 primary-600 버튼. 라이브 `curl /` → 200, `<a href="/signin" class="...bg-primary-600">Sign in</a>` 확인. KR `/ko` 도 동일 위치에 "로그인" |
| 2 | /signup confirm-password + eye toggle + 일치 검증 + consent → /search | **PARTIAL** | UI 로직 정상 (commit `03196cd` SignupForm L.62-72 `passwordsMatch && formReady`, PasswordInput L.130-165 `z-10` + SVG icons). e2e `signup → reveal-once modal → /search` 가 **FAIL** — confirm-password 도입 전 작성된 spec 이라 신규 필드 미입력으로 `signup-submit` disabled. 회귀 테스트 자체가 신규 UX 와 동기화 안 됨. 실제 UI 는 정상이나 자동화 증거 없음 → 데모 직전 수동 1회 시연 필수. 또한 가입 성공 시 `/search` 도달은 #3/#4 BLOCKER 와 같은 redirect-loop 에 걸려 실패 가능 |
| 3 | /signin → demo@buyer.example / radivault-demo-2026 → /search + HttpOnly 쿠키 | **FAIL — BLOCKER #1** | signin endpoint 는 `HTTP 200`, `Set-Cookie: rv_session=...; HttpOnly; SameSite=lax; Max-Age=86400` 정상. 그러나 클라이언트 follow 시 `/search → /signin → /search → /signin` **무한 리다이렉트** (curl --max-redirs 5 hit). 원인: `web/portal/src/app/search/page.tsx:17` 가드 `if (!session?.apiKey) redirect("/signin")` 이 v0.2 email/password 세션의 `buyerPk` 필드를 인지 못함. `signin/page.tsx:19` 는 `buyerPk \|\| apiKey` 둘 다 인지하므로 cookie 보고 `/search` 로 보냄 → `/search` 가 다시 `/signin` 으로 → 영구 루프. 데모 핵심 단계 차단 |
| 4 | /search → 250 study (HOSP-001 150 + HOSP-002 100) + multi-hospital 필터 | **FAIL — BLOCKER #1 결합** | `/search` 자체에 도달 불가 (#3 무한 루프). search service 자체는 정상 — `seed_buyer.py` 시드 키로 `POST /v1/search/studies` 직접 호출 시 250 study + 2 hospital_opaque_id (`1d3fed8642a2bf73`, `20ce581775a234c8`) + modality facets (MR 103, CT 97, MG 50) 응답 확인. **search 백엔드 PASS, portal frontend 가드 BLOCKER** |
| 5 | /account → API key 발급 → 1회 reveal → 재방문 시 마스킹 | **PARTIAL** | `/account/page.tsx` 만 가드가 v0.2 인지 (L.25 `!buyerPk && !apiKey`). 라이브 200 PASS. signup 직후 reveal-once modal 자동 오픈은 코드 검증으로 동작 (apiKeyRevealOnce 응답 + ApiKeyRevealModal). 그러나 #3 의 redirect-loop 가 modal 닫기 후 `/search` 이동을 깨뜨림. 자동화 e2e 도 #2 와 동일 이유로 FAIL |
| 6 | 발급된 rv_live_* 키로 /api/search 호출 (curl 또는 e2e) | **FAIL — BLOCKER #2** | `seed_buyer_auth.py` 시드 키 `rv_live_itE2kdBL...` 로 search service `POST /v1/search/studies` 호출 시 `HTTP 401 ERR_AUTH_FORMAT`. 원인: `/api/auth/signup` 가 portal in-memory `auth/store` 에만 INSERT, **search service 의 `buyer_api_key` 테이블에는 등록 없음**. dev-spec-buyer-auth Q15 (L.1010) 가 "portal SSR 이 INTERNAL_SEARCH_KEY 로 search 호출, buyer kid 는 audit 용" 으로 의도 명시되어 있으나, **데모 시연 시 buyer 가 reveal 받은 키를 직접 curl 시연하면 401 — 데모 narrative 와 코드 의도 불일치**. 별도 `seed_buyer.py` (search-admin CLI 경로) 시드 키는 250 study 정상 응답 확인. |
| 7 | 2병원 federated HOSP-001/HOSP-002 cross-tenant 격리 (per-hospital bearer) | **PASS** | `web/portal/src/lib/upstream-bearer.ts` per-hospital 매핑 + `e2e/multi-hospital.spec.ts` (110줄) 전체 PASS. unit `__tests__/upstream-bearer.test.ts` 8 케이스 PASS. search service 응답에서 2개 hospital_opaque_id 확인 (`1d3fed8642a2bf73`, `20ce581775a234c8`) |
| 8 | /contact → PIPA consent + 5/min rate limit | **PASS** | 라이브: `consent:true` → `HTTP 202`, `consent:false` → `HTTP 422 ERR_REQUEST_SCHEMA path:consent`, 동일 IP 6번째 → `HTTP 429`. 코드 `api/contact/route.ts` Zod `consent: z.literal(true)` + `rate-limit.ts` 토큰 버킷. ContactForm.tsx L.151-170 client-side checkbox required + EN/KR 양쪽 |
| 9 | i18n EN/KR 토글 + KR hero/footer 검수 wording | **PASS** | 라이브: `/ko` HTTP 200, hero "데이터 요청" + "병원 파트너용" 모두 노출. KR signin CTA "로그인". MEDIUM-1/5/6 fix 검증. KR home 의 sitemap 변종 7 URL (`app/sitemap.ts`) |
| 10 | Sign in CTA 가시성 (모든 marketing 페이지) | **PASS** | `MarketingNav.tsx` 가 `/`, `/ko`, `/contact`, `/trust-center`, `/docs` 등 marketing 표면 공통 헤더. EN/KR 양쪽에서 라이브 확인 |

**요약**: 10 중 **PASS 4 / PARTIAL 3 / FAIL 3 (BLOCKER 2건 + 1건 spec-vs-demo-narrative 불일치)**.

---

## 3. 자동화 회귀 카운트 (이전 vs 현재)

| 영역 | 이전 (qa-report-buyer-auth) | 현재 (이번 리허설) | Δ |
|---|---|---|---|
| typecheck | PASS | **PASS** | 0 |
| lint + voice | PASS | **PASS** ("No ESLint warnings or errors" + compliance-voice clean) | 0 |
| vitest unit | 121 PASS | **121 PASS** (10 files / 1.22s) | 0 |
| pytest demo_seed | 39 PASS | **67 PASS** (verify 38 + load_orthanc 5 + seed_buyer 8 + seed_hospital 6 + format 3 / 0.31s) | +28 |
| playwright e2e | 41 PASS | **39 PASS / 2 FAIL** | **−2 회귀** |
| `pnpm build` (production) | (미보고) | **FAIL** — prerender `/signup` + `/ko/signup` 깨짐 | **신규 BLOCKER** |

**회귀 발견 2건** (e2e) **+ 1건 신규 BLOCKER** (production build).

### 3.1 e2e 실패 상세

**e2e #1 — `signup → reveal-once modal → /search` (buyer-auth.spec.ts L.42)**
```
TimeoutError: locator.click: Timeout 10000ms exceeded.
  - locator resolved to <button disabled type="submit" data-testid="signup-submit">
```
- **원인**: 03196cd 가 confirm-password 필드를 추가하면서 form-ready 조건에 `confirmPassword && passwordsMatch` 가산. e2e 가 confirm 필드를 안 채워서 영구 disabled.
- **수정 방향**: spec 에 `await page.getByLabel(/Confirm password/).fill("correct-horse-staple-9");` 라인 추가 (spec 한 줄 변경, 코드 변경 0).

**e2e #2 — `signin happy path lands on /search` (buyer-auth.spec.ts L.72)**
```
Expected pattern: /\/search/
Received string:  "http://localhost:3000/signin"
```
- **원인 (코드 BLOCKER 와 동일 root)**: signup → signout → signin 200 OK + cookie 발급 → `/search` 가드가 v0.2 `buyerPk` 세션 인지 못해 `/signin` 으로 redirect → spec 의 `expect(page).toHaveURL(/\/search/)` 영구 실패.
- **수정 방향**: 스펙 fix 로는 못 잡음 — `/search/page.tsx` 의 가드를 `/account/page.tsx` 패턴 (`!buyerPk && !apiKey`) 으로 통일 필요.

---

## 4. D-13 즉시 차단 항목 (BLOCKER)

### BLOCKER #1 — v0.2 email/password 세션이 `/search`/`/dashboard`/`/studies` 가드를 통과 못함 (무한 redirect)

**위치**:
- `web/portal/src/app/search/page.tsx:17` — `if (!session?.apiKey) redirect("/signin");`
- `web/portal/src/app/dashboard/page.tsx:30` — `if (!session?.apiKey) redirect("/signin");`
- `web/portal/src/app/dashboard/page.tsx:37` — `fetchActiveOrdersCount(session.apiKey)` (apiKey 가 undefined 면 NaN/throw)
- `web/portal/src/app/studies/[uid]/page.tsx:21` — `if (!session?.apiKey) redirect("/signin");`

**대조 정상 사례**:
- `web/portal/src/app/account/page.tsx:25` — `if (!session?.buyerPk && !session?.apiKey) redirect("/signin");` ← **v0.2 인지하는 올바른 패턴**
- `web/portal/src/app/signin/page.tsx:19` — `if (session?.buyerPk || session?.apiKey) redirect("/search");` ← signed-in 확인은 둘 다 인지

**증거 (라이브 트레이스)**:
```
POST /api/auth/signin 200 (Set-Cookie: rv_session=Fe26.2*...; HttpOnly; SameSite=lax)
GET /search 307 → /signin     # search 가드 fail (apiKey 없음)
GET /signin 307 → /search     # signin 가드 success (buyerPk 있음)
GET /search 307 → /signin     # 영구 루프
... (curl --max-redirs 5 exit code 47)
```

**왜 어제 buyer-auth qa-report 가 PASS 로 판정했나**:
- 라이브 `curl /api/auth/signin` 만 검증 (`docs/qa/qa-report-buyer-auth.md` §1: "라이브 signin smoke 200 확인"). 200 응답 + cookie 발급 까지만 보고 종료 — `/search` 까지 follow 안 함.
- e2e #2 가 같은 문제를 잡고 있었으나 (동일 spec) 이전 메인 세션 보고 ("playwright 38/38 PASS") 가 **신규 e2e 추가 전 시점** 또는 cookie cleanup 차이로 우연히 통과한 것. 이번 리허설에서 처음 노출.

**수정 권고** (코드 수정 금지 원칙 → @developer 후속):
1. `/search`, `/dashboard`, `/studies/[uid]` 의 가드를 `!session?.buyerPk && !session?.apiKey` 패턴으로 통일.
2. `/dashboard` 의 `fetchActiveOrdersCount(session.apiKey)` 는 v0.2 세션에서 `session.apiKey` 가 undefined 이므로 별도 분기 필요 (예: `session.apiKey ? fetchActiveOrdersCount(session.apiKey) : 0` — stub 이미 0 반환하므로 no-op 변경).
3. e2e `buyer-auth.spec.ts` 의 두 spec 수정 (confirm-password 필드 채우기 + signin 후 `/search` 가 정상 도달함을 확인하는 단계).
4. 회귀 보호: 신규 e2e `e2e/buyer-auth-redirect-loop.spec.ts` — `signin → cookie 발급 → /search 200 (302/307 chain 0)` 단언.

**소요 추정**: 코드 ~30분 (4 라우트 1줄씩 + dashboard 한 분기), 스펙 ~30분, 검증 ~30분. **D-13 까지 충분**.

---

### BLOCKER #2 — production build 깨짐 (HIGH-1 over-strict env guard)

**위치**: `web/portal/src/lib/env.ts:68-72` (commit `a954313`)

```ts
get buyerAuthSkipEmailVerify() {
  const raw = optional("BUYER_AUTH_SKIP_EMAIL_VERIFY", "true");
  if (process.env.NODE_ENV === "production" && raw !== "false") {
    throw new Error("BUYER_AUTH_SKIP_EMAIL_VERIFY must be explicitly set to 'false' in production builds (AC-DEMO-4)");
  }
  return raw === "true";
}
```

**증상**:
- `pnpm build` (NEXT 가 자동으로 `NODE_ENV=production` 설정) → prerender 단계에서 `/signup`, `/ko/signup` 컴파일 시 throw → "Export encountered errors on following paths: /ko/signup/page, /signup/page" → exit 1.
- `BUYER_AUTH_SKIP_EMAIL_VERIFY=true pnpm build` 도 동일 fail (조건 `raw !== "false"` 가 너무 엄격).
- `BUYER_AUTH_SKIP_EMAIL_VERIFY=false pnpm build` → PASS (build 정상).

**왜 데모 차단인가**:
- 데모 운영은 `pnpm dev` 로 가능 (NODE_ENV=development) — 즉시 차단 아님.
- 그러나 **(a) 데모 직전 production build artifact 가 필요한 경우** (예: Vercel/EC2 deploy, 데모 안정화 위한 prod build), **(b) CI 가 build 단계 포함 시** 즉시 차단.
- 더 심각한 의도 측면 위배: HIGH-1 fix 의 의도가 "production 에서 default 가 fail-open 이지 않도록" 인데, 현재 코드는 **"production 에서 skip-flag 자체가 어떤 값이든 무조건 'false' 가 아니면 build 실패"** — 데모 환경 (skip=true) 을 production build 로 못 만듦. 즉 데모 buyer (`demo@buyer.example`) 를 OTP 우회 모드로 prod 빌드해서 deploy 하는 시나리오 자체가 막힘.

**수정 권고**:
1. (간단) 조건 반전: `if (NODE_ENV === "production" && raw === "true") throw ...` — production 에서 explicit "true" (== skip OTP) 만 차단. default `"true"` 는 dev 에서만 적용되도록 default 도 환경 분기.
2. (안전) default 를 `process.env.NODE_ENV === "production" ? "false" : "true"` 로 분기. 그러면 production 에서는 default 가 fail-closed, dev 에서는 fail-open. throw 제거.
3. **둘 중 어느 쪽이든 commit 1줄 변경 + unit test 1건 추가** (production NODE_ENV + flag 미설정 → no-throw + skip=false).

**소요 추정**: 코드 5분 + 테스트 10분. **D-13 까지 충분**.

---

## 5. HIGH (블로킹 아니나 Launch 전 필수)

### HIGH-A — buyer-auth signup 이 발급한 키가 search service 에서 인증 불가 (데모 narrative 불일치)

**증거**:
- 라이브 `seed_buyer_auth.py` 가 발급한 `rv_live_itE2kdBL...` 로 `POST :8001/v1/search/studies` → `401 ERR_AUTH_FORMAT`.
- 한편 `seed_buyer.py` (search-admin CLI 경로) 가 발급한 `rv_live_cf4ec164...` → 200 + 250 study + 2 hospital_opaque_id 정상.

**원인**: `/api/auth/signup/route.ts:137-150` 가 `store.createBuyerWithCredentials({apiKeyKid, apiKeyTokenHash, ...})` 만 호출. portal in-memory `auth/store` (또는 v0.1.5 PostgresAuthStore) 에만 INSERT. **search service 의 central DB `buyer_api_key` 테이블에는 등록 없음**.

**dev-spec 의도 (Q15, L.1010)**:
> "portal SSR 이 INTERNAL_SEARCH_KEY 로 search 호출, buyer 의 buyer_api_key.kid 는 audit metadata 로만 전달"

즉 spec 의도는 buyer 가 reveal 받은 키를 **직접 사용 안 하는** 모델. 그러나:
- D-13 데모 narrative #6 는 "발급된 rv_live_* 키로 /api/search 호출 (curl 예시 또는 e2e)" — 데모 시연 시 buyer 가 직접 curl 하면 401.
- 데모 시 portal UI 검색 (#4) 만 시연하면 narrative 충돌 0. curl 시연을 빼거나 별도 `seed_buyer.py` 키 (search-admin CLI 경로) 를 사용해야 함.

**Kyle 결정 필요**:
- (A) D-13 데모에서 "buyer 가 받은 키로 직접 API call" 을 빼고 portal UI 검색만 시연 → 본 HIGH-A non-blocking.
- (B) "buyer 가 받은 키 = 직접 API 사용 가능" 모델로 변경 (signup route 가 search-admin CLI 호출 또는 central DB 양쪽 INSERT) → @developer 1일 작업 + 데모 narrative 정합.
- (C) seed_buyer.py 키와 seed_buyer_auth.py 키를 같은 key 로 통일 (수동 운영 SOP) → 데모 직전 추가 작업.

@qa 권고: **(A)**. spec 의 internal-key 격리 모델이 보안 측면 우월 + D-13 까지 변경 최소화.

---

## 6. MEDIUM (관찰 — non-blocking)

### MEDIUM-A — `/dashboard/page.tsx:37` v0.2 세션에서 `session.apiKey` undefined 시 동작
- v0.2 signin 후 (`apiKey` undefined) `fetchActiveOrdersCount(session.apiKey)` 호출 → arg 가 `undefined`. stub 자체는 0 반환 (`return 0` v0.1.1) 하지만 향후 실 구현 시 NPE 위험.
- BLOCKER #1 fix 시 같이 수정 권장.

### MEDIUM-B — buyer-auth in-memory store 는 dev server 재시작 시 휘발
- 데모 직전 `pnpm dev` 재기동 후 `python scripts/demo_seed/seed_buyer_auth.py` 재실행 필수. SOP 명문화 필요.
- 라이브 검증: 본 리허설에서 dev server 띄운 후 시드 안 해서 첫 signin 401 발생, 시드 후 200. 운영자 mistake-prone.

### MEDIUM-C — e2e fail #1 (signup confirm-password) 단순 spec 갱신으로 해소 가능
- `e2e/buyer-auth.spec.ts:51` 다음에 `await page.getByLabel(/Confirm password/).fill("correct-horse-staple-9");` 한 줄 추가.

### MEDIUM-D — secure cookie attribute 가 development 에서 unset (정상이나 launch 전 검증)
- `session.ts:71` `secure: env.nodeEnv === "production"` 정상. dev 에서 `Secure` 미설정 (HTTP localhost 허용용) — 의도된 동작. production deploy 시 HTTPS 강제 인프라 (LB/CloudFront) 필요.

---

## 7. LOW (D-day 후 백로그)

### LOW-A — qa-report-portal-redesign-v2 의 LOW-A (`hospital-admin-credentials.md` git tracked) 잔존
- 본 리허설에서 `git ls-files` 로 재확인. private repo 가정 하 ACCEPT-AS-IS.

### LOW-B — `pnpm build` 가 BLOCKER #2 외 lint/voice/typecheck 모두 통과
- BLOCKER #2 해소 후 "Export encountered errors" 0 검증 필수.

### LOW-C — 데모 buyer 시드 자동화 hook 부재
- `pnpm dev` 부팅 시 `BUYER_AUTH_DEMO_SEED=true` 가 기본인데 **자동 seed 코드가 없음** (`env.ts:79` getter 만 있음, 호출자 0). dev-spec FR-AUTH-12 의 "자동 시드" 의도가 미구현. 운영자가 수동 실행해야 함.

---

## 8. 회귀 — qa-report-portal-redesign-v2 PASS 12 + qa-report-buyer-auth PASS 23

### qa-report-portal-redesign-v2 PASS 12 (HIGH 4 + MEDIUM 6 + LOW 2)

| 항목 | 회귀 결과 | 증거 |
|---|---|---|
| HIGH-1 contact endpoint | **PASS — 보존** | 라이브 202/422/429 확인 |
| HIGH-2 per-hospital bearer | **PASS — 보존** | unit 8 + e2e multi-hospital PASS |
| HIGH-3 verify.py V-11/V-12 | **PASS — 보존** | pytest 67/67 PASS (V-11/V-12 10 케이스) |
| HIGH-4 allowed_hospitals scope | **PASS — 보존** | 코드 무변화 |
| MEDIUM-1/5/6 KR i18n | **PASS — 보존** | 라이브 KR home 에서 "데이터 요청" + "병원 파트너용" + 로그인 확인 |
| MEDIUM-2 apiKeyMasked dynamic | **PASS — 보존** | account 페이지 200 |
| MEDIUM-3 /dashboard + middleware | **PARTIAL — 회귀** | 라이브 `/` → 308 → `/dashboard` 정상이나 `/dashboard` 자체가 BLOCKER #1 으로 redirect-loop |
| MEDIUM-7 contact PIPA consent | **PASS — 보존** | Zod literal(true) + 라이브 422 |
| LOW-1 sitemap KR | **PASS — 보존** | 7 URL |
| LOW-2 CSP header | **PASS — 보존** | next.config.mjs |

### qa-report-buyer-auth PASS 23 의 핵심 회귀

| AC | 결과 | 비고 |
|---|---|---|
| AC-DEMO-1 signup → /search | **회귀 — FAIL** | BLOCKER #1 (e2e #1 도 회귀) |
| AC-DEMO-2 signin → /search | **회귀 — FAIL** | BLOCKER #1 (e2e #2 도 회귀) |
| AC-DEMO-3 reveal-once → /search | **회귀 — FAIL** | BLOCKER #1 의 redirect-loop 가 modal close 후 navigation 깸 |
| AC-DEMO-4 production fail-closed | **PARTIAL — 회귀 (over-correction)** | HIGH-1 fix 가 가족-친화 default 까지 막아 BLOCKER #2 |
| AC-AUTH-1.x signup form + zod | PASS | 03196cd 의 confirm 필드도 zod 외 client-only |
| AC-AUTH-3.x Argon2id | PASS | 121 unit 보존 |
| AC-AUTH-4.2 timing-safe signin | PASS | 라이브 200 응답 시간 21ms |
| AC-AUTH-9.x KR PIPA 4종 | PASS | 코드 무변화 |
| AC-AUTH-11.1 회원탈퇴 30일 grace | PASS | 코드 무변화 |
| AC-NFR-3 plaintext log 0 | PASS | dev server log 에 password 0 hit |

**회귀 양상**: 어제 PASS 였던 AC-DEMO-1/2/3 3개가 **오늘 FAIL** — buyer-auth 단독 검증 (in-memory + signin 200 까지) 으로는 잡히지 않고, **portal-redesign 의 redirect 가드와의 통합 검증** 시점에 처음 노출되는 결합 결함.

---

## 9. 보안 재검증 (Critical 0)

| 영역 | 결과 | 비고 |
|---|---|---|
| Cross-tenant isolation (HOSP-001 vs HOSP-002) | **PASS** | upstream-bearer + multi-hospital e2e + 라이브 search response 의 2 hospital_opaque_id |
| Argon2id m=19MiB t=2 p=1 | PASS | 코드 무변화 |
| Plaintext password log 0 | PASS | dev server log 에 비밀번호 0 hit |
| API key reveal-once | PASS (코드) | UI 코드 정상, 라이브 modal flow 는 BLOCKER #1 차단 |
| HttpOnly + SameSite=lax cookie | PASS | 라이브 Set-Cookie 헤더 확인 |
| Secure cookie | PASS (의도) | dev=false (HTTP localhost), production=true (env.nodeEnv 분기) |
| CSP / 보안 헤더 | PASS | next.config.mjs L.8-27 |
| PIPA §15 consent | PASS | Zod literal(true) + 라이브 422 |
| compliance-voice (certified/HIPAA-compliant 0건) | PASS | lint:voice clean |
| 비밀번호 timing-safe verify | PASS (코드) | dummy hash 항상 verify |

**보안 회귀 0건. critical 0건.**

---

## 10. Kyle 결정 필요 항목

### D-13 전 즉시 (BLOCKER fix 트리거)
- **K-1**: BLOCKER #1 fix 를 @developer 에게 즉시 위임 (권장: 오늘 중) — 4 라우트 가드 통일 + e2e 2건 갱신.
- **K-2**: BLOCKER #2 fix 방향 — (a) 조건 반전 vs (b) NODE_ENV 분기 default. @qa 권고 (b) (default 가 환경 따라 달라지는 게 의도 명확).

### D-13 데모 narrative 결정
- **K-3**: 골든패스 #6 ("buyer 가 받은 키로 직접 API call") 시연 여부 — @qa 권고: **시연 빼고 portal UI 검색만**. spec Q15 의 internal-key 격리 모델이 보안 우월 + 변경 최소.
- **K-4**: 데모 운영 SOP — `pnpm dev` 재기동 시 `seed_buyer_auth.py` 자동 호출 hook 추가 vs 수동 SOP 문서화. @qa 권고: 자동 hook (5분 작업).

### D-13 후 백로그 (Kyle 인지 단계)
- v0.1.5: BUYER_AUTH_SKIP_EMAIL_VERIFY 의 production-grade fix (default 분기 + SES 결합)
- v0.1.5: PostgresAuthStore (현재 in-memory)
- v0.1.5: buyer-auth/portal-redesign 의 세션 가드 패턴 통일 (lib/session.ts 에 `requireBuyerSession()` helper 추출 → 모든 RSC 가 동일 가드 호출)

---

## 11. @developer 후속 권고 (재작업 항목 목록)

### P0 — D-13 데모 직전 (BLOCKER 해소)

1. **세션 가드 통일** — 4 파일 1줄씩 수정:
   - `web/portal/src/app/search/page.tsx:17` → `if (!session?.buyerPk && !session?.apiKey) redirect("/signin");`
   - `web/portal/src/app/dashboard/page.tsx:30` → 동일
   - `web/portal/src/app/dashboard/page.tsx:37` → `session.apiKey ? fetchActiveOrdersCount(session.apiKey) : 0`
   - `web/portal/src/app/studies/[uid]/page.tsx:21` → 동일 패턴
   - 회귀 e2e 추가: `e2e/auth-redirect-no-loop.spec.ts` — signin 후 `/search` 200 (no redirect chain)

2. **production build fix** — `web/portal/src/lib/env.ts:64`:
   - 권고 (b): `const raw = optional("BUYER_AUTH_SKIP_EMAIL_VERIFY", process.env.NODE_ENV === "production" ? "false" : "true"); return raw === "true";`
   - throw 제거. unit test 1건 추가 (NODE_ENV=production + flag 미설정 → no-throw + getter false).

3. **e2e fix** — `web/portal/e2e/buyer-auth.spec.ts`:
   - L.51 다음에 confirm-password fill 라인 추가 (signup test).
   - signin test 는 위 #1 fix 후 자동 PASS.

### P1 — D-day 운영 안정성

4. **seed 자동 hook** — `pnpm dev` 부팅 시 `BUYER_AUTH_DEMO_SEED=true` 면 5초 후 `seed_buyer_auth.py` 자동 호출하는 lifecycle script (predev or instrumentation).

### P2 — Launch 전 (v0.1.5)

5. PostgresAuthStore — in-memory → DB persistence.
6. session 가드 helper 추출 — `requireBuyerSession()` 단일 함수로 4 라우트 + dashboard apiKey 분기 흡수.
7. SES 결합 + buyer-auth + search-admin CLI 통합 (HIGH-A) 모델 결정.

---

## 12. Re-verification (2026-04-25, post-fix) — v2 재검수

### 12.0 검수 트리거

@developer 가 v1 §11 P0 1+2+3 을 commit `6795800` (BLOCKER#1) + `e7dde74` (BLOCKER#2) 로 처리. 본 §12 는 두 fix 가 v1 BLOCKER 를 실제 해소했는지 + 회귀 0 인지 + 잔여 1건이 D-13 데모 차단성인지 독립 재검증.

### 12.1 BLOCKER #1 — 가드 통일 (commit `6795800`) — **HEALED**

**코드 검증**:
- `web/portal/src/app/search/page.tsx:21` → `if (!session?.buyerPk && !session?.apiKey) redirect("/signin");` ✓
- `web/portal/src/app/dashboard/page.tsx:34` → 동일 패턴 ✓
- `web/portal/src/app/dashboard/page.tsx:43-45` → `session.apiKey ? await fetchActiveOrdersCount(session.apiKey) : 0` ✓ (MEDIUM-A 동시 해소)
- `web/portal/src/app/studies/[uid]/page.tsx:25` → 동일 패턴 ✓
- 권고 #4 회귀 spec `e2e/auth-redirect-no-loop.spec.ts` 신규 141 줄 — v0.2 cookie 3건 + legacy paste-mode 2건, 총 5 cases ✓
- `e2e/fixtures/session.ts` 에 `sealBuyerSessionV2()` + `injectBuyerSessionV2()` 헬퍼 추가 — sealed cookie injection 으로 1/min/IP signup rate-limit 우회 (test-infra 측면 합리적 선택) ✓

**라이브 dev smoke (이번 검수에서 직접 실행)**:
```
POST /api/auth/signin {"email":"demo@buyer.example",...}
→ HTTP 200, Set-Cookie: rv_session=Fe26.2*1*5fc4ce...; HttpOnly; Max-Age=86400 ✓

curl -b cookie /search           → HTTP 200, redirects: 0  ✓ (v1 은 무한 루프)
curl -b cookie /dashboard        → HTTP 200, redirects: 0  ✓
curl -b cookie /studies/1.2.3    → HTTP 200, redirects: 0  ✓
curl -L --max-redirs 5 /search   → HTTP 200, redirects: 0  ✓ (chain hit 제거)

curl /search (no cookie)         → HTTP 307, location: /signin  ✓ (가드 negative case 정상)
curl -b cookie /signin           → HTTP 307, location: /search  ✓ (반대 가드도 정상)
```

**e2e 검증** (이번 검수에서 isolation 실행):
- `pnpm exec playwright test e2e/auth-redirect-no-loop.spec.ts` → **5 passed (4.0s)** — 모든 5 cases (v0.2 /search, v0.2 /dashboard, v0.2 /studies, legacy /search, legacy /dashboard) PASS ✓

**판정**: BLOCKER #1 **완전 해소**. 가드 패턴 통일 + 회귀 spec 영구 보호 + 라이브 트레이스 무한 루프 사라짐 확인.

### 12.2 BLOCKER #2 — production build (commit `e7dde74`) — **HEALED**

**코드 검증** (`web/portal/src/lib/env.ts:63-80`):
```ts
get buyerAuthSkipEmailVerify() {
  const isProduction = process.env.NODE_ENV === "production";
  const fallback = isProduction ? "false" : "true";
  const raw = optional("BUYER_AUTH_SKIP_EMAIL_VERIFY", fallback);
  return raw === "true";
}
```
- v1 권고 (b) 그대로 채택 ✓ (NODE_ENV-aware default 분기, throw 제거)
- HIGH-1 의도 보존: production 에서 ENV 미설정 → fallback `"false"` → fail-closed (AC-DEMO-4 만족)
- BLOCKER#2 의도 보존: explicit `"true"` 또는 `"false"` 둘 다 throw 없이 honor — operator 가 demo build artifact 만들 수 있음

**unit test 검증** (`web/portal/src/lib/__tests__/env.test.ts`):
- 4 cases — dev default true / prod default false (no throw) / prod explicit true (no throw) / prod explicit false ✓
- vitest 실행: `env.test.ts (4 tests) 1ms` → **4/4 PASS** ✓

**라이브 build 검증**:
- `pnpm build` (NODE_ENV=production 자동 설정) → **exit 0, 0 errors, 0 warnings** ✓
  - 빌드 산출물 페이지 목록에 `/signup`, `/ko/signup`, `/search`, `/dashboard`, `/studies/[uid]` 모두 정상 (ƒ Dynamic) ✓
- `BUYER_AUTH_SKIP_EMAIL_VERIFY=true pnpm build` → **exit 0** ✓ (v1 에서는 fail 하던 explicit-true override 도 정상)

**판정**: BLOCKER #2 **완전 해소**. AC-DEMO-4 의도 보존 + operator 우회 경로 회복 + unit test 회귀 보호.

### 12.3 자동화 회귀 카운트 (v1 → v2)

| 영역 | v1 (rehearsal) | v2 (post-fix, 본 검수) | Δ |
|---|---|---|---|
| typecheck | PASS | **PASS** | 0 |
| lint + voice | PASS | **PASS** ("No ESLint warnings or errors" + compliance-voice clean) | 0 |
| vitest unit | 121 PASS | **125 PASS** (11 files / 1.21s — 신규 env.test.ts 4 cases) | **+4 ✓** |
| pytest demo_seed | 67 PASS | (재실행 안 함, 백엔드 무변화) | 0 |
| playwright e2e (full suite) | 39 PASS / 2 FAIL | **45 PASS / 1 FAIL** (46 total — 신규 5 + 1 잔여) | **+6 PASS, −1 FAIL** ✓ |
| playwright auth-redirect-no-loop (isolation) | (신규) | **5/5 PASS** | ✓ |
| playwright buyer-auth.spec (isolation) | (단독 미실행) | **3/3 PASS** | ✓ |
| `pnpm build` | FAIL (BLOCKER#2) | **PASS (exit 0)** | ✓ |
| `BUYER_AUTH_SKIP_EMAIL_VERIFY=true pnpm build` | FAIL | **PASS (exit 0)** | ✓ |

### 12.4 잔여 1건 — `e2e/buyer-auth.spec.ts:75` 풀 스위트 시 429 — **non-blocking, test-infra 만**

**증상**:
- 풀 스위트 실행 시: spec #1 (`signup → reveal-once`) 다음 spec #2 (`signin happy path`) 가 spec 내부 setup 의 `page.request.post("/api/auth/signup")` 에서 `429 Expected 201` 으로 실패.
- isolation 실행 시: `pnpm exec playwright test e2e/buyer-auth.spec.ts` → 3/3 PASS (이번 검수에서 직접 실행 확인) ✓

**근본 원인 (코드 추적으로 확정)**:
1. `web/portal/src/lib/auth/responses.ts:47-54` `resolveClientIp(headers)` 가 `cf-connecting-ip` / `x-forwarded-for` / `x-real-ip` 부재 시 literal `"ip:unknown"` 반환.
2. `web/portal/src/app/api/auth/signup/route.ts:40` 가 `signupRateLimiter.check(\`ip:${ip}\`)` 호출 → bucket key = `"ip:ip:unknown"`.
3. `web/portal/src/lib/rate-limit.ts:64-67` `signupRateLimiter` max=1/60s.
4. 풀 스위트에서 spec #1 의 form-driven signup (browser via Playwright) 가 첫 번째 호출 → bucket count=1. spec #2 의 setup 내 직접 `page.request.post("/api/auth/signup")` 가 두 번째 호출 (같은 process, 같은 헤더 무) → bucket key 동일 → 429.
5. spec #1 와 spec #2 사이 storageState reset 은 cookie 만 정리, in-memory rate-limit bucket 은 process-shared 라 유지됨.

**D-13 데모 차단성 분석**:
- 데모 narrative: 1 buyer (demo@buyer.example) 만 시연. signup 은 시연 시점에 0회 호출 (이미 시드된 buyer 로 signin 만). signin 은 별도 rate-limiter (`signinIpRateLimiter` max=5/min) 적용 → 1/min 충돌 시나리오 없음.
- 라이브 운영: 실제 브라우저 요청에는 `x-forwarded-for` 또는 `cf-connecting-ip` 헤더가 LB/CDN 으로부터 정상 전달 → 다른 buyer = 다른 bucket key → 충돌 없음.
- 이 collision 은 **playwright test-infra 환경에서만** 재현 (헤더 부재 + 동일 process 내 2회 signup). 데모 시 영향 0.

**판정**: 잔여 1건 = **test-infra 한계, BLOCKER 와 무관, D-13 차단 아님**. v0.1.1 백로그 (signup spec 별도 file 분리 또는 setup 에서 `signupRateLimiter.reset()` 노출 + 호출).

### 12.5 골든패스 10단계 재매트릭스 (v1 → v2 변경분만)

| # | v1 결과 | v2 결과 | 증거 |
|---|---|---|---|
| 1 | PASS | **PASS** | 회귀 0 (코드 무변화) |
| 2 | PARTIAL (e2e #1 disabled submit) | **PASS** | buyer-auth.spec.ts:53 confirm-password fill 라인 추가됨, isolation 실행 시 spec #1 PASS (1.2s) ✓. 풀 스위트에서도 signup spec PASS (signin spec 만 429 — §12.4) |
| 3 | **FAIL — BLOCKER #1** | **PASS** | 라이브 trace: signin 200 + cookie → /search 200 (0 redirects) ✓. e2e auth-redirect-no-loop 5/5 PASS |
| 4 | **FAIL — BLOCKER #1 결합** | **PASS (가드 측면)** | /search 도달 가능, 가드 통과 확인. 250 study 응답은 v1 search-backend smoke 에서 이미 PASS — 회귀 없음 |
| 5 | PARTIAL (modal close 후 navigation 깨짐) | **PASS** | apikey-reveal-done click → /search 가 §12.1 fix 로 정상 도달. e2e signup spec (#1) 의 `await page.getByTestId("apikey-reveal-done").click(); await expect(page).toHaveURL(/\/search/);` (L.71-72) 가 isolation 시 PASS ✓ |
| 6 | FAIL — HIGH-A narrative 불일치 | (변경 없음) | HIGH-A 는 본 fix 범위 외, Kyle 결정 (A/B/C) 대기. §12.7 참조 |
| 7 | PASS | **PASS** | 회귀 0 (multi-hospital e2e 2/2 PASS in 풀 스위트) |
| 8 | PASS | **PASS** | 회귀 0 (vitest contact-api 8/8 PASS) |
| 9 | PASS | **PASS** | 회귀 0 (homepage KR 5/5 PASS in 풀 스위트) |
| 10 | PASS | **PASS** | 회귀 0 |

**v2 요약**: 10 중 **PASS 9 / FAIL 1 (HIGH-A narrative 불일치, Kyle 결정 대기, 데모 narrative 변경으로 회피 가능)**.

### 12.6 회귀 — v1 PASS 항목 보존

- qa-report-portal-redesign-v2 PASS 12: **모두 보존** (HIGH-1/2/3/4 + MEDIUM-1/2/3/5/6/7 + LOW-1/2). MEDIUM-3 (/dashboard 가 v1 에서 redirect-loop) 은 §12.1 fix 로 회복 → PARTIAL → PASS.
- qa-report-buyer-auth PASS 23: **모두 보존**. AC-DEMO-1/2/3 회귀 3건은 §12.1 fix 로 회복. AC-DEMO-4 (PARTIAL — over-correction) 는 §12.2 fix 로 회복.

### 12.7 HIGH-A 잔존 — 데모 narrative 결정만 남음

- 본 검수 범위 외 (Kyle 결정 대기). §5/§10 K-3 그대로 유효.
- 데모 #6 (curl 호출) 시연 시 401 발생 확률 = **100%** (search service `buyer_api_key` 테이블에 등록 없음, dev-spec Q15 internal-key 격리 모델).
- 시연 빼는 경우 (@qa 권고 A): 데모 narrative 영향 **0** — #5 reveal-once modal 시연 + #4 portal UI 검색 시연 으로 "키 발급 + 사용" 양쪽 demonstrate. curl 시연을 빼는 게 보안 측면 우월 + 데모 narrative 단순화.

### 12.8 보안 회귀 0건 — Critical 0

- BLOCKER#1 fix 가 가드 조건을 OR 로 완화했으나 **인증 자체의 강도는 동일** (buyerPk 또는 apiKey 둘 중 하나라도 있어야 통과, 없으면 redirect). 신규 e2e legacy paste-mode 2 cases 가 legacy 경로 비회귀 보장.
- BLOCKER#2 fix 가 throw → fallback 으로 변경. AC-DEMO-4 production fail-closed 의도는 fallback `"false"` 로 보존. unit test 4 cases 가 회귀 보호.
- 라이브 dev server log smoke (이번 검수): password / API key plaintext 노출 0건.

### 12.9 종합 판정 (v2)

**판정**: **READY-TO-DEMO**

**근거**:
1. v1 BLOCKER 2건 모두 라이브 + e2e + unit + build 다층 검증으로 해소 확인.
2. 골든패스 10 중 PASS 9 (v1: PASS 4). 잔여 1건 (#6) 은 데모 narrative 조정으로 회피 가능 (Kyle 결정 K-3, @qa 권고 A).
3. 회귀 0 — 이전 portal-redesign-v2 PASS 12 + buyer-auth PASS 23 모두 보존.
4. 자동화 +4 unit, +6 e2e, build 회복.
5. 잔여 1 e2e 실패 (`signin happy path` 풀 스위트 429) 는 코드 추적으로 test-infra collision 확정 — 데모 차단성 0.
6. 보안 critical 0, compliance-voice clean.

**다음 단계 권고**:
1. (Kyle) K-3 결정 — 골든패스 #6 시연 여부 (권고 A).
2. (Kyle) K-4 결정 — seed 자동 hook (권고: 자동 hook).
3. (D-day 직전) `git remote -v` private 재확인 (LOW-A 회귀 잔존).
4. (v0.1.1) signup spec rate-limit collision 분리 — `signupRateLimiter.reset()` 노출 또는 spec 파일 split (non-blocking).

**D-13 추가 fix 필요 여부**: **없음** (Kyle K-3/K-4 결정 외).

---

## 13. 변경 이력

- v1 (2026-04-25, NEEDS-FIX) — D-13 최종 리허설 검수, BLOCKER 2건, e2e 2건 회귀, build 1건 회귀.
- v2 (2026-04-25, READY-TO-DEMO) — post-fix 재검수 (commits `6795800` + `e7dde74`), §12 추가. BLOCKER 2건 해소 확인 (라이브 + e2e + unit + build), 회귀 0, 잔여 1 e2e 는 test-infra collision (D-13 차단 아님).
