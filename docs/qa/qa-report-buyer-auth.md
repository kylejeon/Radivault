# QA Report — buyer-auth

**Status**: 검수 완료
**판정**: **READY-TO-DEMO** (HIGH-1 launch 전 fix 권고)
**검수자**: @qa Claude (Opus 4.7)
**검수 일자**: 2026-04-25
**대상 커밋**: `4cc67af..5f84fa8` (7 commits, Sub-phase A→F)
**근거**: dev-spec-buyer-auth.md §10 (32 AC + 7 NFR + 4 DEMO = 43)

## 1. 요약

- 43 AC: **PASS 23 / PARTIAL 5 / N/A 2 / FAIL 2**
- 이슈: **BLOCKER 0 / HIGH 1 / MEDIUM 4 / LOW 4**
- D-13 데모 골든 패스 5종 모두 PASS
- 121 unit + 41 e2e PASS, 라이브 signin smoke 200 확인, 회귀 0
- 보안 핵심 (Argon2 OWASP / plaintext 0 leak / timing-safe / rate limit / PIPA 4종 분리 / reveal-once) 모두 PASS

## 2. 발견 사항

### HIGH-1 — `BUYER_AUTH_SKIP_EMAIL_VERIFY` production fail-open

**위치**: `web/portal/src/lib/env.ts` L.63-64

```ts
get buyerAuthSkipEmailVerify() {
  return optional("BUYER_AUTH_SKIP_EMAIL_VERIFY", "true") === "true";
}
```

**위험**: NODE_ENV=production 시에도 default `"true"`. ENV 누락 시 OTP 검증 자동 스킵 → email 미검증 signup. AC-DEMO-4 위반.

**데모 영향 0** (의도된 default 가 데모와 일치). **launch 직전 필수 fix**.

**권고**: getter 에 `if (nodeEnv === "production" && raw !== "false") throw new Error(...)` 추가, 또는 default 를 `"false"` 로 뒤집고 demo compose 의 ENV 에 명시적으로 `"true"` 지정.

### MEDIUM-1 — sessionVersion 미들웨어 미배선 (AC-AUTH-6.3 PARTIAL)

`bumpSessionVersion()` 은 password-reset 시 호출되지만, 다른 요청에서 cookie 의 sessionVersion vs store 의 현재 값 비교 미들웨어 부재. password-reset 후 도난 cookie 가 30일까지 유효.

**v0.1.5 백로그**.

### MEDIUM-2 — ABSOLUTE_SESSION_MS 30일 cap 미enforce (AC-AUTH-7.1 PARTIAL)

cookie sliding 24h 만 동작. 30일 absolute cap 미enforce → 매일 활동 시 영구 세션.

**v0.1.5 백로그**.

### MEDIUM-3 — `__Host-` cookie prefix 미적용 (AC-AUTH-7.2 PARTIAL)

cookieName="rv_session". 90일 legacy paste-mode 종료 후 `__Host-rv_session` 으로 변경 가능.

### MEDIUM-4 — AC-AUTH-10.1 marketing-pref UI/API 미배선 (FAIL)

AccountClient 에 marketing toggle 부재. signup 시 1회만 결정 가능, 추후 변경 경로 0. 정통망법 §50 마찰 가능.

**v0.1.5 백로그 또는 운영 SOP**.

### LOW

- LOW-1: dummy hash plaintext 공개 (이론적 collision, 위험 매우 낮음)
- LOW-2: account reveal/KR signup e2e 자동화 부재 (데모 직전 수동 시연 1회 권고)
- LOW-3: seed credentials 가 spec 과 다름 (`demo@buyer.example` vs spec `demo@radivault.io`) — planner spec 갱신 권고
- LOW-4: hard-delete cron 부재 (GDPR Art.17 launch 전 fix)

## 3. AC 매트릭스 핵심 항목

| AC | 결과 | 비고 |
|---|---|---|
| AC-AUTH-1.x signup 폼 + zod + 평문 미포함 | PASS | EN 7필드, KR 8필드 |
| AC-AUTH-3.x Argon2id m=19MiB t=2 p=1 | PASS | OWASP 표준 |
| AC-AUTH-4.2 timing-safe signin | PASS | dummy hash 항상 verify (코드 검증), 20ms 측정 미실행 |
| AC-AUTH-6.3 password reset sessionVersion | PARTIAL | 증분 발생, enforce 안 됨 (MEDIUM-1) |
| AC-AUTH-7.1 sliding+absolute cap | PARTIAL | sliding ✓, absolute cap 미enforce (MEDIUM-2) |
| AC-AUTH-7.2 cookie attribute | PARTIAL | HttpOnly+Secure+SameSite ✓, `__Host-` prefix 부재 (MEDIUM-3) |
| AC-AUTH-9.x KR PIPA 4종 분리 | PASS | 수집·제3자·위탁·국외이전 + 광고성 별도 |
| AC-AUTH-10.1 marketing-pref 변경 + audit | FAIL | UI/API 부재 (MEDIUM-4) |
| AC-AUTH-11.1 회원탈퇴 30일 grace | PASS | soft-delete + email mangle + 409 ERR_EMAIL_RECENTLY_DELETED |
| AC-NFR-3 plaintext password log 0 | PASS | grep 0 hit |
| AC-DEMO-1..3 골든 패스 | PASS | signup→/search, signin→/search, reveal-once |
| AC-DEMO-4 production fail-open guard | FAIL | HIGH-1 |

## 4. 회귀

qa-report-portal-redesign-v2 의 PASS 12건 모두 보존:
- HIGH-1 contact / HIGH-2 per-hospital bearer / HIGH-3 V-11/V-12 / HIGH-4 allowed_hospitals
- MEDIUM 1-7 / LOW 1-2
- 81 unit + 38 e2e (이전) → 121 + 41 (현재, 신규 40 unit + 3 e2e 추가)
- /api/session legacy paste-mode 보존 (90일 backwards-compat)

**회귀 0**.

## 5. Deferred 5건 데모 차단 판정

| 항목 | 데모 차단 | launch 전 |
|---|---|---|
| MemoryAuthStore (vs Postgres) | NO (시연 직전 seed 재실행 필수) | YES |
| sessionVersion 미들웨어 미배선 | NO | YES (MEDIUM-1) |
| SES 미배선 (skip-flag 우회) | NO | YES (HIGH-1 와 결합 위험) |
| Hard-delete cron 부재 | NO | YES (LOW-4, GDPR Art.17) |
| AC-NFR-1/2 k6 perf 미실행 | NO | 권고 (1회 측정) |

**5건 모두 데모 차단 NO**.

## 6. 종합 판정

**판정**: **READY-TO-DEMO**

- 골든 패스 5종 PASS, 보안 핵심 PASS, 회귀 0
- HIGH-1 1건만 launch 전 fix 필요 (데모 영향 0)

**Kyle 즉시 결정 필요**:
- HIGH-1 fix 시점: (a) 데모 전 즉시 / **(b) 데모 후 launch 전** (@qa 권고)

**v0.1.5 백로그**: MEDIUM-1/2/4 + LOW-4
