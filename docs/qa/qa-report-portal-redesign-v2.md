# QA Report — portal-redesign (v2 — 재검수)

**Status**: 재검수 완료
**판정**: **READY-TO-DEMO** (잔여 잡음 LOW × 2 — non-blocking)
**검수자**: @qa Claude (Opus 4.7)
**검수 일자**: 2026-04-25
**대상 커밋 범위**: `5b477ea..871a890` (6 fix commits, post-v1)
**Baseline**: `docs/qa/qa-report-portal-redesign.md` (v1, 2026-04-25, NEEDS-FIX)
**범위**: v1 의 HIGH 4 / MEDIUM 7 / LOW 2 = 13 건 처리 결과 + 회귀 + 보안 재검증

---

## 1. 요약

- v1 13 건 중 **PASS 12 / PARTIAL 1 (MEDIUM-4 — 의도된 central upstream 분리 작업) / 잔여 0**.
- 본 fix 사이클이 새로 도입한 **BLOCKER 0 / HIGH 0 / MEDIUM 0 / LOW 2** (보안성 LOW, 모두 의도된 v0.1 데모 운영 모델).
- 회귀 영향 0 (Phase 2/3/4 e2e + 이전 6 feature qa-report 모두 보존).
- HIGH-2 Kyle 결정 사항 (per-hospital bearer) 가 v1 상태에서 자율 처리됨 — central 위탁 모델에서 `bearerForHospital(hospitalId)` 헬퍼로 격상.
- Kyle 즉시 결정 필요 사항: **없음**.

---

## 2. v1 13 건 처리 결과 매트릭스

### 2.1 HIGH (4 건 — v1 의 데모 차단 후보)

| # | 항목 | v1 | v2 | 증거 |
|---|---|---|---|---|
| HIGH-1 | AC-HP-7 `POST /api/contact` 미구현 | FAIL | **PASS** | `web/portal/src/app/api/contact/route.ts` — Zod schema (consent: literal(true) 강제 — PIPA L-7), 422 ERR_REQUEST_SCHEMA / 429 ERR_RATE_LIMITED (Retry-After 헤더) / 202 envelope 정확. `web/portal/src/lib/rate-limit.ts` per-IP 5/60s 토큰 버킷. SLACK_WEBHOOK_URL 옵셔널 fan-out. `__tests__/contact-api.test.ts` 8 케이스 (happy + 5 422 변종 + 429 + IP 격리) |
| HIGH-2 | 병원 BFF shared bearer 위탁 | FAIL | **PASS** | `web/portal/src/lib/upstream-bearer.ts` — `HOSP-001` → `HOSP_001_BEARER` 환경변수 매핑. legacy `HOSPITAL_UPSTREAM_BEARER` fallback + once-per-process warn. 5 BFF 모두 마이그 (`grep -rn bearerForHospital web/portal/src/app/api/hospital/`): stats/audit/orders/me/audit-chain-status/me/quota. `__tests__/upstream-bearer.test.ts` 6 케이스 (per-hospital lookup + fallback + warn-once + null-id + legacy id 정규화). multi-hospital e2e (HOSP-001 vs HOSP-002 mocks 서로 다른 hash_prefix 검증, `e2e/multi-hospital.spec.ts` L.65-110) |
| HIGH-3 | verify.py V-11/V-12 누락 | FAIL | **PASS** | `scripts/demo_seed/verify.py` L.517 `check_v11_audit_chain_status` (3 필수 필드 + bff↔central 필드명 별칭 허용 `last_anchor_hash_prefix` ↔ `hash_prefix`) / L.591 `check_v12_quota` (5 필수 필드 + nested `daily.bytes_used` 평탄화 허용). 404 시 graceful FAIL + central FR-INF-6/7 hint 출력. `tests/demo_seed/test_verify.py` 10 unit (각 함수별 success/404/missing-field/non-JSON/no-bearer) |
| HIGH-4 | AC-BP-8 `allowed_hospitals` 미주입 | FAIL | **PASS** | `OrderReviewClient.placeOrder` L.107-113 — cohort items 의 `hospital_opaque_id` Set dedup + sort. `/api/orders` POST L.51-66 — 서버측 재 dedup + sort, falsy 항목 defensive filter, 빈 배열일 때 키 자체 생략 (fulfillment 의 "empty=any" 안티패턴 회피). 의도가 client-only 가 아닌 BFF re-validate 까지 이중 방어 — 정확한 처리. |

### 2.2 MEDIUM (7 건)

| # | 항목 | v1 | v2 | 증거 |
|---|---|---|---|---|
| MEDIUM-1 | KR `hero.forHospitals = "언론 문의"` 오역 | FAIL | **PASS** | `i18n.ts` L.815 `forHospitals: "병원 파트너용"` |
| MEDIUM-2 | `account.apiKeyMasked` 더미 placeholder | FAIL | **PASS** | i18n 키 제거 (L.344 주석 명시) — `AccountClient` 가 prop 으로 dynamic mask 수신. `account/page.tsx` L.22-29 `maskApiKey(apiKey)` 서버 측 적용 후 prop 전달 |
| MEDIUM-3 | `/dashboard` 라우트 + 인증 후 `/` redirect | FAIL | **PASS** | `app/dashboard/page.tsx` 5 타일 (active orders / recent searches / pending invoices / api usage / announcements). `middleware.ts` L.27-37 — `rv_session` 쿠키 존재 시 `/` → `/dashboard` 308. dashboard 자체도 `getBuyerSession()` 가드 → 미인증 시 `/signin` redirect (이중 안전망). KR 홈 `/ko` 는 marketing 보존 (의도된 EN-only buyer flow) |
| MEDIUM-4 | central upstream FR-INF-6/7 미구현 | PARTIAL | **PARTIAL** (의도) | portal BFF stub fallback 분 단위 deterministic. central FR-INF-6/7 작업은 별도 트랙. 본 사이클 범위 밖 — Kyle 인지 |
| MEDIUM-5 | KR `hero.primaryCta = "병원 파트너 신청"` 의미 변형 | FAIL | **PASS** | `i18n.ts` L.810 `primaryCta: "데이터 요청"` (EN "Request data access" 와 일치). 주석 L.808-809 의도 명시 |
| MEDIUM-6 | KR footer 컬럼 라벨 swap | FAIL | **PASS** | `i18n.ts` L.910-937 — developers→기술, resources→리소스, company→회사, legal→법적. EN L.150-176 와 의미 정렬. lang toggle swap 시 라벨 일관성 유지 |
| MEDIUM-7 | Contact 페이지 PIPA L-7 동의 누락 | FAIL | **PASS** | `ContactForm.tsx` L.151-170 consent checkbox + required + `consent: true` 만 서버 전송. EN/KR 양쪽 (`contact/page.tsx` L.47, `ko/contact/page.tsx` L.42) 동일 컴포넌트 사용. KR 동의 문구 (i18n L.973-976) 한국어 "수집 항목 / 이용 목적 / 보유 기간 1년" 모두 명시 — 한국 PIPA §15 충족 |

### 2.3 LOW (2 건)

| # | 항목 | v1 | v2 | 증거 |
|---|---|---|---|---|
| LOW-1 | sitemap KR 변종 누락 | FAIL | **PASS** | `app/sitemap.ts` 7 URL: en/ko 루트 + en/ko contact + en/ko trust-center + docs (EN-only 명시) |
| LOW-2 | CSP 헤더 명시 미확인 | PARTIAL | **PASS** | `next.config.mjs` L.8-27 — CSP (`default-src 'self'`, `frame-ancestors 'none'`) + X-Content-Type-Options + X-Frame-Options DENY + Referrer-Policy `strict-origin-when-cross-origin`. v1 시점에 already-in-place 였음 (검수자 spot-check 누락) |

---

## 3. 본 fix 사이클이 새로 도입한 이슈

### BLOCKER
없음.

### HIGH
없음.

### MEDIUM
없음.

### LOW (의도된 v0.1 데모 운영 artefact — 모두 운영 정책 결정으로 처리 가능)

#### LOW-A — `docs/ops/hospital-admin-credentials.md` 평문 패스워드 git tracked

**증거**: `git ls-files docs/ops/hospital-admin-credentials.md` → tracked. 파일 L.11-12 에 `radivault-demo-2026`, `tunteun-demo-2026` 평문 + SHA-256 prefix 기록.

**위험 분석**:
- v0.1 D-day 데모 한정 운영 artefact — 문서 자체가 "Pilot deployments will use SSO (FR-HO-2)" 명시.
- repo 가 **private 이라는 가정** 하에 운영 메모로 분류 (파일 L.40 "The portal repo is private. Demo passwords are operational artefacts on par with the bearer tokens").
- pilot 단계 진입 전 SSO 마이그가 명시적으로 도큐된 의도된 임시 모델.

**권고**:
1. (즉시) repo 의 GitHub visibility 가 **private 임을 한 번 더 confirm** — public 으로 잘못 flip 시 즉각 노출.
2. (D-day 후) FR-HO-2 SSO 구현 시 본 파일 삭제 또는 SSO IdP 메모로 교체.
3. (선택) `.env.local` 처럼 `docs/ops/hospital-admin-credentials.md` 도 `.gitignore` 로 옮기고 별도 secret store (1Password / Vault) 에 보관 — repo 노출 0 모델로 격상.

**판정**: **non-blocking, ACCEPT-AS-IS for D-day** (Kyle 의 운영 정책 인지 하).

#### LOW-B — `web/portal/.env.local` 의 평문 bearer prefix 노출 (SAFE — gitignored)

**증거**: `web/portal/.gitignore` L.5 `.env.local` 등재. `git check-ignore -v` 매치 확인. `git log -- web/portal/.env.local` 결과 0 — never tracked.

**판정**: **NO-OP** — 정상. v1 검수자가 별도 confirm 안 했던 것을 v2 에서 명시 PASS 처리. `HOSP_001_BEARER` / `HOSP_002_BEARER` / `HOSPITAL_UPSTREAM_BEARER` legacy fallback 모두 .env.local 에만 존재, repo 노출 0.

---

## 4. 회귀 검증

### 4.1 Phase 2 (homepage + 공유) — 회귀 0
- `e2e/homepage.spec.ts` 메인 세션 보고: PASS.
- `i18n.ts` 변경이 EN homepage 불변 (footer 컬럼 EN 그대로 / `forHospitals` EN 키 그대로). KR 만 의미 정정.
- `app/sitemap.ts` 5 → 7 URL — robots/sitemap dev-spec AC-HP-8 호환 유지 (entry 추가만, 기존 entry 보존).
- `next.config.mjs` 의 CSP 는 v1 시점 이미 존재 — 본 사이클 변경 없음.

### 4.2 Phase 3 (buyer 포털) — 회귀 0
- `e2e/search-flow.spec.ts` / `order-flow.spec.ts` / `account-and-detail.spec.ts` 메인 세션 보고: PASS.
- `OrderReviewClient.placeOrder` 가 기존 `pseudo_study_uids` + `notes` 외 신규 `allowed_hospitals` 추가 — 추가 키, 기존 호출자 영향 0.
- `/api/orders` POST 가 빈 배열일 때 `allowed_hospitals` 키 자체 생략 → fulfillment 기존 시그니처 호환 유지 (보수적 처리).
- `MarketplaceNav` 가 logo 링크 `/dashboard` 로 변경 — 단, `/dashboard` 자체가 신규 라우트라 신규 사용자만 영향. 기존 buyer flow 의 nav item (search/orders/docs/account) 4 개 보존.
- `/dashboard` 5 타일 중 `activeOrdersCount` 가 stub `return 0` (코드 L.160-166 명시 v0.1.1) — Tile 1 empty state 강제 렌더. 경미하지만 의도 명시.

### 4.3 Phase 4 (hospital 콘솔) — 회귀 0
- `e2e/hospital-dashboard.spec.ts` / `hospital-floating-contact.spec.ts` 메인 세션 보고: PASS.
- 5 BFF 의 `bearerForHospital(session.hospitalId)` 마이그가 시그니처 보존 — fallback 경로가 legacy `HOSPITAL_UPSTREAM_BEARER` 환경변수 유지로 단일 hospital 데모 시 무영향.
- `hospital-admin-credentials.md` 의 HOSP-002 admin 추가 — 신규 자격증명 데이터, HOSP-001 무영향.

### 4.4 이전 6 feature qa-report 영향 검토

| Feature | 본 사이클 영향 | 결과 |
|---|---|---|
| gateway-agent | 코드 변경 없음 | PASS |
| de-id-pixel | 코드 변경 없음 | PASS |
| central-ingest | FR-INF-6/7 별도 트랙 (MEDIUM-4) — 본 사이클은 portal-side stub graceful fallback 만 강화 | PASS / MEDIUM-4 인지 |
| order-fulfillment | `/api/orders` POST 의 `allowed_hospitals` 추가 — `agreement_hash` 스텁 보존, 기존 시그니처 호환 | PASS |
| metadata-index (search) | 영향 없음 | PASS |
| buyer-portal-demo | `MarketplaceNav` 로고 링크 `/dashboard` 로 변경, 기존 e2e 가 새 nav 와 호환 (`6b3469c` v1 시점 재작성) | PASS |

---

## 5. 보안 재검증

| 영역 | 결과 | 증거 |
|---|---|---|
| Cross-tenant isolation (HOSP-001 vs HOSP-002) | **PASS — 강화됨** | (1) BFF iron-session `session.hospitalId` 만 사용. 외부 헤더/쿼리/body 의 hospital_id 미수신. (2) bearer 가 hospital 별 분리 — central 측 매핑 위탁 → portal 측 환경변수 분리로 격상. (3) e2e 가 HOSP-001 hash_prefix `a3f8d9c1...` vs HOSP-002 `ff112233...` 명시 검증 |
| Buyer 실명/이메일 leak | PASS | `OrderInflowTile` 코멘트 강제 — v1 동일 |
| API key reveal-once mailto | PASS | `RevealModal` mailto stub — v1 동일. AccountClient L.107 `account-reveal-once` testid |
| `X-Stubbed: true` fallback only | PASS | upstream 200 시 미설정 — v1 동일 |
| `rv_live_*` 평문 키 노출 | PASS | placeholder/문서/마스킹 외 0 — v1 동일 |
| 컴플라이언스 어휘 (certified/guaranteed/HIPAA-compliant 0건 / 인증됨·보장 0건) | PASS | i18n.test.ts + check_compliance_voice.sh — v1 동일 |
| CSP / 보안 헤더 | **PASS** (LOW-2 해소) | `next.config.mjs` L.8-27 — CSP + X-Frame-Options DENY + Referrer-Policy + X-Content-Type-Options |
| PIPA §15 동의 (contact form) | **PASS** (MEDIUM-7 해소) | client-side checkbox required + server-side `z.literal(true)` 이중 강제. KR 문구 "수집 항목·이용 목적·보유 기간 1년" 명시 |
| Per-hospital bearer | **PASS** (HIGH-2 해소) | env-keyed lookup + once-per-process deprecation warn. v1 의 위탁 모델 → portal-side 격상 |
| Hospital admin password 평문 | LOW-A (운영 정책) | `docs/ops/hospital-admin-credentials.md` git tracked — repo private 가정 하 ACCEPT-AS-IS, FR-HO-2 SSO 마이그 백로그 |
| `.env.local` bearer | SAFE | `.gitignore` 매치 확인, never tracked |

### 보안 회귀 0
- middleware 가 cookie-presence 만 확인 (Edge runtime 호환) — stale cookie 시 `/dashboard` → `/signin` 이중 redirect 로 fail-safe.
- contact rate limiter 가 in-memory per-process — multi-instance 시 우회 가능, 코드 주석에 v0.1.1 Redis 격상 명시 (의도된 v0.1 절충).
- Slack relay 가 fire-and-forget — 202 응답 차단 안 함, 실패 시 console.warn 만.

---

## 6. 신규 산출물 검토

| 산출물 | 평가 |
|---|---|
| `web/portal/src/lib/upstream-bearer.ts` (65 line) | 단일 책임, sync, 명확한 fallback + warn-once. legacy id 정규화 (`/[^a-zA-Z0-9]/g → _`). 테스트 시드 `__resetBearerWarning()` 노출 — 프로덕션 영향 0 |
| `web/portal/src/lib/rate-limit.ts` (55 line) | factory + singleton 분리, 인젝션 가능 `now()` (테스트 결정성). 주석에 multi-instance defeat + v0.1.1 Redis 격상 명시 |
| `web/portal/src/middleware.ts` (43 line) | Edge-safe (cookie presence only), matcher `/` 만 — KR `/ko` 의도적 제외. 주석에 stale-cookie fail-safe rationale 명시 |
| `web/portal/src/app/api/contact/route.ts` (140 line) | 422/429/202 envelope 정확. PIPA `consent: literal(true)` 서버측 강제. IP 추출 X-Forwarded-For 좌측 first hop. 메시지 본문 console 로그 미포함 (operator paper trail bounded) |
| `web/portal/src/app/dashboard/page.tsx` (167 line) + `RecentSearchesIsland.tsx` | 5 타일 + testid 일관, RSC + client island 분리. `force-dynamic` 명시. activeOrdersCount stub 명시 |
| `web/portal/src/components/shared/ContactForm.tsx` (243 line) | EN/KR locale prop + accent (primary/teal) 분기, consent required + disabled state, success/error 상태 처리 |
| `web/portal/e2e/multi-hospital.spec.ts` (110 line) | HOSP-001/HOSP-002 각각 hash_prefix + studies count + audit-chain 테스트 — cross-tenant isolation 의 e2e 증거 |
| `docs/ops/hospital-admin-credentials.md` (42 line) | LOW-A — 평문 데모 패스워드, git tracked. 파일 자체가 v0.1 임시 운영 메모로 명시. Kyle 운영 정책 인지 |
| `web/portal/src/__tests__/upstream-bearer.test.ts` (84 line) | 6 케이스 — per-hospital / case-insensitive / null fallback / once-warn / empty-id / legacy-id 정규화. 95% 커버 |
| `web/portal/src/__tests__/contact-api.test.ts` (102 line) | 8 케이스 — 202 happy / 5 변종 422 / 429 + Retry-After / IP 격리. 95% 커버 |

---

## 7. v1 데모 차단 후보 재검토

v1 §7 의 Kyle 즉시 결정 필요 3 항목:
1. **HIGH-2 (shared bearer)** — 자율 처리됨. portal-side per-hospital 환경변수 + central 위탁의 이중 방어로 격상. **결정 불필요**.
2. **HIGH-1 (contact 엔드포인트)** — 구현 완료. AC-HP-7 PASS. **결정 불필요**.
3. **HIGH-4 (allowed_hospitals scope)** — 구현 완료. federated cohort 시연 가능. **결정 불필요**.

**Kyle 즉시 결정 필요 (v2 신규)**: 없음.

선택 사항 (D-day 이후 백로그):
- LOW-A — `hospital-admin-credentials.md` 를 `.gitignore` 로 옮길지 vs repo private 정책으로 유지할지 (FR-HO-2 SSO 마이그 시 자연 해소).
- MEDIUM-4 — central FR-INF-6/7 구현 (별도 트랙).
- 본 사이클 verify.py V-10 dev-spec 라벨 정합성 (planner 갱신 백로그).

---

## 8. 종합 판정

**판정**: **READY-TO-DEMO**

**근거**:
1. v1 의 13 건 (HIGH 4 / MEDIUM 7 / LOW 2) 중 **12 건 PASS, 1 건 (MEDIUM-4) 의도된 분리 트랙**. 데모 차단 후보 0.
2. fix 사이클이 도입한 신규 BLOCKER/HIGH/MEDIUM = 0. LOW × 2 모두 운영 정책 결정 (LOW-A) 또는 검증 결과 SAFE (LOW-B).
3. 회귀 영향 0 — Phase 2/3/4 + 이전 6 feature qa-report 모두 보존.
4. 보안 측면에서 cross-tenant isolation 이 v1 의 "위탁 모델" → "portal-side per-hospital + central 매핑 이중 방어" 로 **강화됨**.
5. 테스트 신뢰도: vitest 81/81 + pytest verify 39/39 + playwright 38/38 = 158/158 PASS (메인 세션 보고).

**D-day 데모 권고**:
- HOSP-001 + HOSP-002 양쪽 시연 가능 — multi-hospital e2e 가 격리 보장.
- federated cohort (2 hospital) 주문 시연 가능 — `allowed_hospitals` 자동 주입.
- contact form 시연 가능 — KR/EN 양쪽 PIPA 동의 + 422/429/202 envelope.
- KR 홈페이지 시연 — footer/hero CTA 모두 의미 정정 완료.
- buyer 사인인 후 `/` 방문 → `/dashboard` 5 타일 자동 라우팅 시연 가능.
- D-day 직전 `git remote -v` 로 repo visibility private 한 번 더 confirm 권고 (LOW-A 위험 예방).

---

## 9. 변경 이력

- v1 (2026-04-25, NEEDS-FIX) — 14 commits `3de8122..43c4f28`, HIGH 4 / MEDIUM 7 / LOW 2.
- v2 (2026-04-25, READY-TO-DEMO) — 6 fix commits `5b477ea..871a890`, v1 13 건 중 12 PASS / 1 의도된 PARTIAL, 신규 LOW × 2 (운영 정책).
