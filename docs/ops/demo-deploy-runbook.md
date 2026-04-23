# RadiVault Demo Deploy Runbook

> **Status**: v0.1 · **Last updated**: 2026-04-24
> 대상: Kyle 또는 데모 운영자가 대표님 미팅 전 로컬(macOS)에서 전체 스택을
> 띄우고 데모를 실행할 때 따르는 절차. 프로덕션 배포는 아직 범위 밖.

---

## 0. 전제

- macOS 13+ / Apple Silicon. Linux (Ubuntu 22.04) 도 동작하나 경로 예시는 macOS.
- Docker Desktop 24+, Python 3.11 (uv 또는 venv), Node.js 20 LTS, openssl, jq.
- 저장소 루트에서 실행: `/Users/yonghyuk/Radivault` (또는 사용자 경로).
- 모든 경로는 리포지토리 루트 기준.

## 1. 시크릿 생성 (한 번)

```bash
./scripts/demo_setup/generate_demo_secrets.sh
```

출력:
- `web/portal/.env.local` 파일 생성 (권한 600, `.gitignore` 보호).
- `DEMOOP_TOKEN`, `SESSION_PASSWORD`, `RV_HOSPITAL_ADMIN_TOKENS` (sha256 해시)
  자동 주입.
- **Hospital 원본 admin 토큰**이 표준출력에 한 번 표시됨 → 1Password
  등에 즉시 옮기고 터미널 스크롤백 제거 (`clear && printf '\e[3J'`).

재생성 필요 시 `--force` 플래그:

```bash
./scripts/demo_setup/generate_demo_secrets.sh --force
```

## 2. 백엔드 스택 기동

### 2.1 central-ingest

```bash
cd src/radivault_central
docker-compose up -d postgres redis minio ingest
# 또는 존재하는 compose 파일 경로에 맞게. 기존 dev-spec-central-ingest §9.3 참조.
```

- Postgres 5432, Redis 6379, MinIO 9000/9001, ingest API 8001.
- 헬스체크: `curl -s localhost:8001/healthz`.

### 2.2 search (metadata-index)

```bash
# 로컬 uvicorn 으로 띄우는 경우
cd src/radivault_search
uvicorn radivault_search.app:app --port 8003 --reload
```

또는 Dockerfile.search 기반 compose.

### 2.3 fulfillment (order-fulfillment)

```bash
uvicorn radivault_fulfillment.app:app --port 8002 --reload
```

## 3. Hospital Upstream Bearer 발급

`web/portal/.env.local` 의 `HOSPITAL_UPSTREAM_BEARER` 는 **생성 스크립트가
채워주지 않는다** — central-ingest DB에 auth_token row 가 실제로 존재해야
하기 때문. 다음 절차로 한 번 발급.

```bash
# central-ingest 컨테이너 또는 로컬 실행 환경에서:
ingest-admin token issue \
    --hospital-id HOSP-001 \
    --label "demo-rehearsal-$(date +%Y%m%d)"
```

출력 예시:
```
Issued token: rv_live_ABCDEF... (shown once, copy now)
Token hash:   argon2id$...
DB row id:    42
```

`rv_live_...` 값을 `web/portal/.env.local` 의 `HOSPITAL_UPSTREAM_BEARER=` 에
붙여넣는다.

## 4. 샘플 데이터 시딩 (Rehearsal R-1)

TCIA 공개 DICOM 300~500 스터디를 다운로드 → Orthanc 로드 → Gateway 실행 →
Central ingest → Search 인덱싱.

**현재 상태**: `scripts/demo_seed/download_tcia.py` 는 `NotImplementedError`
블록으로 스텁만 있음. 데모 D-3 영업일 전 리허설 R-1 단계에서 연결 예정
(dev-spec §8.4).

임시 대안: 기존 테스트 픽스처 재활용 — `tests/gateway/fixtures/*` 의
샘플 DICOM 을 Orthanc 에 수동 로드하여 Flow A 파이프라인으로 Search 에
10~20 스터디 인덱싱 가능.

## 5. 포털 기동

```bash
cd web/portal
npm install            # 최초 한 번
npm run build          # production build (데모 권장) — 느리지만 안정적
npm run start          # 포트 3000
# 또는 개발 모드 (HMR, 느림):
# npm run dev
```

브라우저:
- Buyer Portal: http://localhost:3000
- Hospital Dashboard: http://localhost:3000/hospital
  - Sign-in 화면에서 `hospital_id=HOSP-001` + admin_token (1.단계에서
    보관한 원본 값) 입력.

## 6. 데모 전 체크리스트 (D-1)

### 기능 점검
- [ ] `/healthz` 3개 서비스 전부 200 응답.
- [ ] Buyer Portal Home 에서 `Search` 클릭 → 결과 카드 10+ 건 표시.
- [ ] 필터 2개 적용 → 결과 변화 즉시 반영.
- [ ] 임의 결과 선택 → `Review & Order` 모달 → `Confirm` → 주문 생성.
- [ ] `/orders/<id>` 5-phase stepper 점진적 전이 확인 (로컬 스텝 수동 촉진
  가능 — `fulfillment-admin` CLI).
- [ ] Downloads 페이지 presigned URL 표시, SHA-256 체크섬 렌더, curl
  snippet 토글 동작.
- [ ] Hospital Dashboard 6-tile 모두 값 렌더. B-2 타일 "시뮬레이션" 배지
  육안 확인.
- [ ] Demo Operator Mode 토글 (`Cmd+Shift+D`) 배지 표시.

### 데모 화면 안전성
- [ ] 모든 타일에 PHI 추정 텍스트 없음 (원본 PatientName, PatientID,
  StudyInstanceUID 등).
- [ ] 병원/경쟁사 로고·상호 없음 (placeholder 이미지만).
- [ ] 수익 타일 disclaimer "시뮬레이션 — v0.2 정산 대기" 표시.
- [ ] Brand copy "certified" / "HIPAA-compliant" / "guaranteed" 단정 0건.

### 백업·리커버리
- [ ] Canned output JSON 파일 `web/portal/public/demo-canned/` 존재 확인
  (리허설 R-1 에서 녹화).
- [ ] 녹화본 데모 영상 (데모 실패 백업) — 로컬 재생 1회 테스트.
- [ ] 미팅 노트북 배터리 ≥ 80%, 전원 어댑터 지참.
- [ ] Wi-Fi 대비: 모바일 핫스팟 켜 두기.
- [ ] `demo-script-radivault.md` §3 실패 런북 5건 프린트 or 별 모니터.

## 7. 데모 직후 cleanup

```bash
# BFF 세션 쿠키 로그에 PII 가 들어갔을 가능성 — 로그 디렉토리 삭제 (없을 때
# 무시).
rm -rf web/portal/.next/trace web/portal/.next/cache 2>/dev/null || true

# Demo secrets 는 미팅 다음날까지 유지, 이후 재생성 권고:
# ./scripts/demo_setup/generate_demo_secrets.sh --force

# 스택 정지
cd src/radivault_central && docker-compose down
```

**절대 하지 말 것**:
- `.env.local` 파일 Git 커밋 (`.gitignore` 가 보호하지만 이중 확인).
- 원본 hospital admin 토큰을 Slack / 이메일 평문 전송.
- 데모용 DEMOOP_TOKEN 을 프로덕션·파일럿 환경에서 재사용.

## 8. 변경 이력

| 버전 | 날짜 | 변경 |
|------|------|------|
| 0.1 | 2026-04-24 | 최초 작성. Session 12 마무리 일환. |
