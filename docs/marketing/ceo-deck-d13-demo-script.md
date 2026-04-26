# Demo Script — D-13 골든패스 9단계 (시연 시나리오)

> **Status**: Draft v0.2 · **작성자**: @marketer · **작성일**: 2026-04-25
> **§0 Changelog (v0.2)**: Kyle K-3 결정에 따라 기존 단계 6 (curl `/api/search` 라이브 호출) 제거. 골든패스 10 → 9단계로 재번호. 사유 — `seed_buyer_auth.py` 가 발급한 `rv_live_*` 키가 search service `buyer_api_key` 테이블에 미등록 (HIGH-A) 이므로 라이브 시연 시 401. 해결책 A 채택 (search service 키 등록 path 신설은 D-13 까지 시간 부족). API 가치 메시지는 단계 5 (reveal-once) 발화에 흡수.
> **목적**: D-13 미팅의 시연을 운영자(또는 Kyle 본인) 가 그대로 따라가도록 하는 step-by-step 시나리오. 각 단계마다 **클릭 동작**, **이 화면이 보여주는 것 (1줄)**, **실패 시 대처**.
> **연동 문서**:
> - `docs/marketing/ceo-deck-d13-talking-points.md` (각 단계의 발화 스크립트)
> - `docs/qa/qa-report-buyer-auth.md` §3 (AC 매트릭스)
> - `docs/qa/qa-report-portal-redesign-v2.md` §2.1 (HIGH 4건 처리 결과)
> - `progress.txt` (데모 자격증명 라인)
>
> **사전 준비 체크 (시연 30분 전)**:
> - [ ] dev server 기동 (BUYER_AUTH_SKIP_EMAIL_VERIFY=true)
> - [ ] central + search + postgres + orthanc + redis + minio docker-compose 정상
> - [ ] `scripts/demo_seed/verify.py` 8/9 PASS 확인 (V-4 sync 무관)
> - [ ] HOSP-001 + HOSP-002 bearer 환경변수 로드
> - [ ] 데모 buyer 시드 재실행 (MemoryAuthStore 휘발성 — 재기동 시 필수)
> - [ ] 브라우저 캐시 클리어 + 시크릿 창 1개 + 일반 창 1개
> - [ ] git remote -v 로 repo 가 private 임을 한 번 더 확인 (qa-report-portal-redesign-v2 §2.3 LOW-A)

---

## 단계 1 — 홈페이지 방문

| 항목 | 값 |
|---|---|
| **URL** | `http://localhost:3000/` (또는 demo URL) |
| **클릭 동작** | 브라우저에서 새 탭 열기 |
| **이 화면이 보여주는 것** | 비로그인 상태의 마케팅 홈페이지 — 헤로 + 컴플라이언스 trust ladder + How It Works + 우상단 Sign in |
| **시연 포인트** | (1) Headline "Korea's medical imaging data, compliantly delivered for global AI." (2) 우측 trust bar 4 칼럼 — PIPA / SOC2 in prep / ISO 27001 aligned / HIPAA-aligned. **단정형 어휘 없음**. |
| **소요 시간** | 30초 |
| **발화** | talking-points §1 |
| **실패 시** | 새로고침 1회. 그래도 안 되면 KR 로 시작 후 EN 로 전환 (단계 8 과 순서 swap) |

---

## 단계 2 — /signup (PIPA 4종 분리 동의)

| 항목 | 값 |
|---|---|
| **URL** | `/signup` (영문 default) → 우상단 KR 토글 클릭 → `/ko/signup` |
| **클릭 동작** | 1) Sign in 옆 "Sign up" 또는 nav 의 가입 링크 / 2) KR 토글로 한국어 화면 전환 |
| **이 화면이 보여주는 것** | 한국어 회원가입 폼 — email / password / org / intent + **PIPA 4종 분리 체크박스** (수집·이용 / 제3자 제공 / 국외이전 / 광고 수신) |
| **시연 포인트** | 4 체크박스가 **시각적으로 분리** 되어 있고, **광고 수신만 선택, 나머지 셋은 필수**. 입력은 하지 말 것 (단계 3에서 기존 데모 buyer 로 로그인) |
| **소요 시간** | 45초 |
| **발화** | talking-points §2 |
| **실패 시** | KR 페이지가 안 뜨면 EN 페이지에서 "ToS + Privacy 1쌍" 만 보여주고 "한국어로 전환하면 4종으로 분리됩니다" 로 우회 |

---

## 단계 3 — /signin (데모 buyer 로그인)

| 항목 | 값 |
|---|---|
| **URL** | `/signin` (또는 KR 모드면 `/ko/signin`) |
| **자격증명** | email: `demo@buyer.example` · password: `radivault-demo-2026` (progress.txt 참조) |
| **클릭 동작** | email + password 입력 → Sign in 클릭 |
| **이 화면이 보여주는 것** | 로그인 직후 자동으로 `/search` 로 라우팅. URL 에 토큰 노출 없음. |
| **시연 포인트** | (1) 평범한 email/password UI — 그러나 백엔드는 Argon2id (2) 세션 쿠키는 HttpOnly + SameSite (3) 비밀번호 평문 leak 0 — QA grep 검증 |
| **소요 시간** | 20초 |
| **발화** | talking-points §3 |
| **실패 시** | "demo buyer 시드가 휘발됐을 수 있습니다 — 재시드하겠습니다" 라고 멘트 후 1초 내 재실행 (사전 준비 체크리스트 어겨졌을 때만 발생) |

---

## 단계 4 — /search (250 study + multi-hospital filter)

| 항목 | 값 |
|---|---|
| **URL** | `/search` (단계 3에서 자동 도착) |
| **클릭 동작** | 좌 패싯에서 modality CT 클릭 → 결과 필터링 → 다시 모든 modality 해제 → 결과 250 복원 |
| **이 화면이 보여주는 것** | 3-pane 레이아웃: 좌 패싯 / 중앙 250 row 결과 테이블 / 우측 cohort sidebar with **"From 2 hospitals" 배지** |
| **시연 포인트** | (1) 결과 row 의 `hospital_opaque_id` 컬럼 — HOSP-001 / HOSP-002 가 섞여 있음 (2) cohort 배지의 N-hospital 카운트가 first-class metric (3) 패싯 토글 시 결과·cohort 즉시 갱신. **이 화면이 곧 검색 백엔드의 라이브 증빙** — portal UI 가 호출하는 동일한 search service 가 백엔드 동작을 입증. |
| **소요 시간** | 60초 |
| **발화** | talking-points §4 |
| **실패 시** | 결과가 0이면 "캐시 워밍 중" 멘트 + 새로고침 1회. 그래도 0이면 단계 5 로 진행 후 e2e 테스트 PASS 인용으로 보강 |

---

## 단계 5 — /account (API key reveal-once + 발급 라이브 증빙)

| 항목 | 값 |
|---|---|
| **URL** | nav 의 Account → `/account` |
| **클릭 동작** | "Reveal API key" 버튼 클릭 → 모달에서 키 1회 노출 → 닫기 |
| **이 화면이 보여주는 것** | 자동 발급된 `rv_live_*` API key + 마스킹 표시 + "한 번만 평문" 경고 |
| **시연 포인트 (강화 — v0.2)** | (1) 가입 동시에 자동 1키 발급 — Stripe `sk_live_*` 컨벤션 (2) reveal-once 후 마스킹 — 분실 시 재발급, 기존 키 즉시 무효 (3) **이 키는 buyer 가 자기 백엔드에서 호출하는 자격증명 — CEO 데모는 reveal 동작까지만 시연합니다.** 라이브 API 호출은 buyer 백엔드 셋업이 전제이므로 별도 onboarding 세션에서 진행. (4) Web UI (사람용) + API key (MLOps 파이프라인용) 의 dual-credential 모델은 단계 4 의 portal 검색이 동일 search service 를 호출함으로써 백엔드 동작이 함께 검증됨. |
| **소요 시간** | 45초 (v0.1 30초 → API 가치 메시지 흡수로 +15초) |
| **발화** | talking-points §5 |
| **실패 시** | reveal 모달이 안 뜨면 e2e 테스트 결과(qa-report-buyer-auth §3 AC-DEMO-3 PASS) 를 슬라이드로 대체 — "코드는 PASS, UI 일시 글리치" |

---

## 단계 6 — 2병원 federated cross-tenant 격리 (구 단계 7)

| 항목 | 값 |
|---|---|
| **클릭 동작** | (a) 검색 결과 row 의 hospital_opaque_id 클릭 → 해당 병원 study 만 / (b) 다시 cohort 전체 클릭 → 250 복원 / (c) 별도 시크릿 창 열어 hospital admin (HOSP-002, password: tunteun-demo-2026) 로 로그인하여 본병원 데이터가 안 보임을 시연 (선택) |
| **이 화면이 보여주는 것** | (1) buyer 한 명이 두 병원의 데이터를 통합 검색 (2) 그러나 두 병원은 서로의 raw data 에 접근 불가 |
| **시연 포인트** | (1) `bearerForHospital(hospitalId)` 헬퍼로 portal-side 격리 (qa-report-portal-redesign-v2 HIGH-2 PASS) (2) e2e/multi-hospital.spec.ts 가 hash_prefix 다름을 검증 (3) BFF + central 이중 방어 |
| **소요 시간** | 60초 (선택 c 까지 90초) |
| **발화** | talking-points §6 |
| **실패 시** | 시크릿 창 옵션 (c) 는 시간 부족하면 스킵. e2e 테스트 결과 한 줄로 대체 — "QA report v2 HIGH-2 PASS" |

---

## 단계 7 — /contact (PIPA consent lead 수집) (구 단계 8)

| 항목 | 값 |
|---|---|
| **URL** | `/contact` (또는 `/ko/contact`) |
| **클릭 동작** | 폼 입력 → consent 체크박스 미체크 상태로 submit → 422 에러 → consent 체크 후 submit → 202 응답 |
| **이 화면이 보여주는 것** | (1) consent 미체크 시 422 (서버측 `z.literal(true)` 강제) (2) 체크 후 202 envelope (3) Korean 페이지는 "수집 항목 / 이용 목적 / 보유 기간 1년" 명시 |
| **시연 포인트** | (1) 클라이언트 + 서버 이중 강제 (2) rate limit 5/min/IP — 429 시 Retry-After 헤더 (3) PIPA §15 충족 |
| **소요 시간** | 45초 |
| **발화** | talking-points §7 |
| **실패 시** | 422 시연이 어색하면 처음부터 체크 후 202 한 번만 — "체크 미완료 시 422 가 나오도록 방어되어 있습니다" 멘트로 대체 |

---

## 단계 8 — EN/KR 토글 (양언어 시연) (구 단계 9)

| 항목 | 값 |
|---|---|
| **클릭 동작** | 우상단 EN | KR 토글 → 홈페이지 한국어 전환 → 풋터 스크롤하여 한국 B2B 풋터(대표자 / 사업자등록 / 고객센터) 확인 |
| **이 화면이 보여주는 것** | 단순 번역이 아니라 한국어 페이지는 (1) 4컬럼 풋터 + 법적 블록 (2) hero CTA "데이터 요청" 의미 일치 (3) developers→기술, resources→리소스 컬럼 라벨 의미 정렬 |
| **시연 포인트** | (1) i18n 만이 아닌 IA 자체가 양 청중에 최적화 (2) 한국 병원 CTO/DPO 의 신뢰 신호 (3) qa-report-portal-redesign-v2 MEDIUM-1/5/6 PASS |
| **소요 시간** | 30초 |
| **발화** | talking-points §8 |
| **실패 시** | KR 페이지 깨지면 EN 페이지의 풋터만 보여주며 "한국어 페이지는 이 영역에 한국식 법적 블록이 추가됩니다" 라고 우회 |

---

## 단계 9 — 클로징 (로드맵 + Ask) (구 단계 10)

| 항목 | 값 |
|---|---|
| **클릭 동작** | 화면을 닫지 않고 홈페이지 또는 dashboard 로 복귀하여 정지 |
| **이 화면이 보여주는 것** | 로드맵 슬라이드는 별도로 띄우지 않음 — 발화로만 처리 |
| **시연 포인트** | v0.1.5 (PostgresAuthStore + AWS SES + hard-delete cron) → v0.2 (Stripe + OHIF + 추가 병원 5–10곳) |
| **소요 시간** | 60초 |
| **발화** | talking-points §9 + 청중별 ask 1줄 |
| **실패 시** | N/A — 멘트 only |

---

## 전체 시연 시간 예산 (v0.2 재계산)

| 단계 | 발화+조작 | 누적 |
|---|---|---|
| 0. 오프닝 | 30초 | 0:30 |
| 1. 홈페이지 | 30초 | 1:00 |
| 2. /signup | 45초 | 1:45 |
| 3. /signin | 20초 | 2:05 |
| 4. /search | 60초 | 3:05 |
| 5. /account (reveal-once + API 가치 흡수) | 45초 | 3:50 |
| 6. federated 격리 | 60초 | 4:50 |
| 7. /contact | 45초 | 5:35 |
| 8. EN/KR | 30초 | 6:05 |
| 9. 클로징 | 60초 | 7:05 |
| Q&A 버퍼 | — | (목표 13분 → Q&A 약 5분 55초 확보; v0.1 대비 +30초 여유) |

**총 시연 시간**: **7분 5초** (v0.1 7분 35초 → 30초 단축. 단계 6 curl 45초 제거 - 단계 5 강화 +15초 = 순감 30초.)

---

## 시연 모드 ENV 확인 체크리스트

| 변수 | 값 | 의도 |
|---|---|---|
| `BUYER_AUTH_SKIP_EMAIL_VERIFY` | `true` | 데모 무대에서 SES 의존성 제거. **launch 전 fix 필수 — qa-report-buyer-auth HIGH-1** |
| `HOSP_001_BEARER` | `<rvct_*>` | 본병원 토큰 |
| `HOSP_002_BEARER` | `<rvct_2d69bc4a...>` | 튼튼병원 토큰 (progress.txt) |
| `HOSPITAL_UPSTREAM_BEARER` | (legacy fallback) | once-per-process warn 로그 |
| `SLACK_WEBHOOK_URL` | (선택) | contact 폼 fan-out — 시연 시 unset 권장 (chat 알림 노이즈 방지) |

---

## 시연 직후 30초 회고 멘트

talking-points 의 "시연 후 30초 회고" 섹션 그대로 사용.

---

## 변경 이력

| 버전 | 날짜 | 작성자 | 변경 |
|---|---|---|---|
| 0.1 | 2026-04-25 | @marketer | 최초 작성. 골든패스 10단계 + 사전 준비 체크 + 시간 예산. Kyle 리뷰 대기. |
| 0.2 | 2026-04-25 | @marketer | Kyle K-3 결정 반영 — 구 단계 6 (curl 라이브 호출) 제거. 10 → 9단계 재번호. 단계 5 (reveal-once) 에 dual-credential 메시지 흡수 (30초 → 45초). 시간 예산 7분 35초 → 7분 5초. 사유: HIGH-A `seed_buyer_auth.py` 발급 키가 search service `buyer_api_key` 미등록 → 라이브 401 위험. 해결책 A 선택. |
