# RadiVault 로컬 개발·데모 설치 가이드 v0.1

**목적**: 새 개발자·데모 진행자가 macOS/Linux 로컬에서 RadiVault 백엔드 스택과 Buyer Portal을 처음부터 띄우고 Hospital Dashboard를 검증하기까지 모든 절차.

**대상 독자**: 개발자, 데모 오퍼레이터
**난이도**: 중급 (Docker · Python · Node 경험 가정)
**예상 소요 시간**: 30~60분 (첫 빌드 기준)
**마지막 검증**: 2026-04-24, Session 13, HOSP-001 토큰 발급 PASS

관련 문서:
- [docs/ops/demo-deploy-runbook.md](demo-deploy-runbook.md) — 고객 미팅 당일 배포 런북
- [docs/specs/dev-spec-buyer-portal-demo.md](../specs/dev-spec-buyer-portal-demo.md) — Portal 개발지시서
- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) — Model 3 Hybrid 아키텍처

---

## 1. 사전 요구사항

| 도구 | 최소 버전 | 확인 명령 |
|---|---|---|
| Docker Desktop (또는 colima) | 24.x | `docker --version` |
| Docker Compose | v2.x | `docker compose version` |
| Python | 3.11 | `python3 --version` |
| Node.js | 20.x | `node --version` |
| npm | 10.x | `npm --version` |
| Git | 2.x | `git --version` |

**macOS 주의**: Docker Desktop에서 메모리 최소 8GB 할당 (central + postgres + minio + redis + search + portal 동시 기동).

**포트 요구사항** (이 포트들이 비어있어야 함):

| 포트 | 서비스 |
|---|---|
| 3000 | Next.js portal (dev) |
| 5432 | Postgres |
| 6379 | Redis |
| 8000 | central-ingest API |
| 8001 | metadata-index (search) |
| 8002 | order-fulfillment (선택) |
| 9000 | MinIO S3 |
| 9001 | MinIO 콘솔 |

**k3d·Kubernetes 클러스터 실행 중이면 충돌 주의**: `k3d-*-serverlb` 컨테이너가 80/443/3306/6379/9000/9001을 점유함. 데모 전에 `k3d cluster stop <name>` 실행.

---

## 2. 저장소 준비

```bash
git clone <repo-url> Radivault
cd Radivault
git checkout claude     # 작업 브랜치. main 직접 사용 금지.
```

---

## 3. 보안 비밀 생성 (`web/portal/.env.local`)

RadiVault Portal은 BFF에서 upstream 호출과 세션 관리에 비밀 값들을 사용합니다. 전용 스크립트로 생성합니다.

```bash
./scripts/demo_setup/generate_demo_secrets.sh
```

결과: `web/portal/.env.local` 생성 (이미 있으면 거부, `--force` 플래그로 덮어쓰기 가능).

스크립트가 자동 생성하는 값:
- `DEMOOP_TOKEN` (32자 base64url, Demo Operator Mode 쿠키)
- `SESSION_PASSWORD` (64자, iron-session 암호화 키)
- `RV_HOSPITAL_ADMIN_TOKENS` — 병원 관리자 토큰 원본은 stdout에만 찍힘, 파일엔 sha256 해시만 저장. **stdout 원본 값을 별도 메모에 저장 필수** (브라우저 `/hospital` 로그인 시 입력).
- Upstream URL 세 개 (`CENTRAL_INGEST_URL`, `SEARCH_URL`, `FULFILLMENT_URL`)
- Revenue 시뮬레이션 파라미터

**수동으로 채워야 하는 값**: `HOSPITAL_UPSTREAM_BEARER` — 섹션 6에서 발급 후 붙여넣음.

---

## 4. Docker 백엔드 스택 기동

RadiVault는 `docker-compose.*.yml` 4개로 분리돼 있습니다. 각각의 역할:

| 파일 | 포함 서비스 | 필수 여부 |
|---|---|---|
| `docker-compose.central.yml` | postgres, redis, minio, minio-setup, central | **필수** (나머지의 기반) |
| `docker-compose.search.yml` | metadata-index (search) | **필수** (Buyer Portal /search) |
| `docker-compose.fulfillment.yml` | order-fulfillment | 선택 (주문 플로우 사용 시) |
| `docker-compose.yml` | gateway-agent, orthanc, mock-central | Gateway 개발 시만 |

### 4.1 Central 스택 기동

```bash
docker compose -f docker-compose.central.yml up -d
```

첫 실행 시 `radivault-central` 이미지 빌드 (약 2~3분). 이후 기동은 15초 내외.

### 4.2 Metadata-index 기동

```bash
docker compose -f docker-compose.search.yml up -d
```

### 4.3 상태 확인

```bash
docker compose -f docker-compose.central.yml ps
docker compose -f docker-compose.search.yml ps
```

모든 컨테이너가 `Up ... (healthy)`여야 합니다. `Created` 상태로 멈춰있으면 `depends_on` 헬스체크가 실패한 것 — 섹션 12 (트러블슈팅) 참조.

### 4.4 Central API 생존 확인

```bash
curl -sS http://localhost:8000/healthz
```

200 응답 (body는 서비스별 포맷)이 나오면 OK.

---

## 5. DB 마이그레이션

Central 컨테이너는 부팅 시 `Base.metadata.create_all()`로 테이블을 자동 생성합니다 (cli.py:46, dev 편의). 프로덕션에서는 alembic 마이그레이션을 명시적으로 돌려야 합니다.

**현재 상태 확인** (선택):
```bash
docker exec radivault-central-1 ingest-admin migrate current 2>&1
```

**주의**: 2026-04-24 시점 `alembic.ini`에 `script_location` 누락으로 `migrate current`가 에러 반환. 테이블 자동 생성은 정상 동작하므로 데모는 영향 없음. 이슈: 추후 v0.1.1에서 수정.

---

## 6. 병원 생성 및 Bearer 토큰 발급

Portal의 Hospital Dashboard가 central `/v1/hospital/me/*`를 호출할 때 사용할 Bearer 토큰을 발급합니다.

### 6.1 병원 row 생성

```bash
docker exec radivault-central-1 \
  ingest-admin init-hospital \
    --hospital-id HOSP-001 \
    --name "데모병원 (Demo Hospital)"
```

성공 출력: `[OK] enrolled HOSP-001`. 이미 있으면 `[EXISTS] HOSP-001` (idempotent).

**옵션**:
- `--allowed-ruleset-versions` — De-ID 룰셋 버전 (기본 `v0.1.0`)
- `--salt-version` — Pseudonymization salt 버전 (기본 `1`)

### 6.2 Bearer 토큰 발급

```bash
docker exec radivault-central-1 \
  ingest-admin token issue \
    --hospital-id HOSP-001 \
    --note "buyer-portal-demo rehearsal $(date +%Y-%m-%d)" \
    --json
```

JSON 출력 예:
```json
{
  "hospital_id": "HOSP-001",
  "kid": "rvct_1a8fe44e",
  "plaintext": "rvct_1a8fe44e.dEiQrif9moLY69D5XY7SJtGusAvNe-P7YIpBRodyh1UhJtjv",
  "expires_at": null,
  "note": "buyer-portal-demo rehearsal 2026-04-24"
}
```

**치명적 주의사항**:
- `plaintext` 값은 **이 한 번만 출력됨**. 복사 실패 시 재발급해야 함 (기존은 revoke).
- DB에는 argon2id 해시만 저장, plaintext 불가역.
- `--json` 없이 호출하면 박스 형태 사람용 포맷으로 출력됨 (grep·파이프 처리 시 `--json` 권장).

**옵션**:
- `--expires-days N` — N일 후 만료 (기본 무기한, 데모용 권장)
- `--dry-run` — DB 저장 없이 발급 시뮬레이션

### 6.3 토큰 목록/폐기

```bash
# 목록
docker exec radivault-central-1 ingest-admin token list --hospital-id HOSP-001

# 폐기
docker exec radivault-central-1 ingest-admin token revoke --kid rvct_1a8fe44e --reason "compromised"
```

---

## 7. `.env.local`에 토큰 붙여넣기

`web/portal/.env.local` 파일을 편집해서 `HOSPITAL_UPSTREAM_BEARER` 값을 6.2의 `plaintext`로 대체합니다.

```bash
# 예시: 텍스트 에디터로 직접 편집
$EDITOR web/portal/.env.local
```

수정할 줄:
```bash
# 수정 전
HOSPITAL_UPSTREAM_BEARER=

# 수정 후 (plaintext 복사본 붙여넣기)
HOSPITAL_UPSTREAM_BEARER=rvct_1a8fe44e.dEiQrif9moLY69D5XY7SJtGusAvNe-P7YIpBRodyh1UhJtjv
```

**다른 변수 검증**: `generate_demo_secrets.sh` v0.1 구버전에서 upstream URL이 잘못 기록될 수 있음. 아래 값 재확인:

| 변수 | 올바른 값 |
|---|---|
| `CENTRAL_INGEST_URL` | `http://localhost:8000` |
| `SEARCH_URL` | `http://localhost:8001` |
| `FULFILLMENT_URL` | `http://localhost:8002` |

---

## 8. Portal dev 서버 기동

### 8.1 의존성 설치

```bash
cd web/portal
npm install
```

### 8.2 Dev 모드

```bash
npm run dev
```

출력에 `Ready in X.Ys` + `Local: http://localhost:3000` 확인.

### 8.3 Production 모드 (데모 당일 권장)

```bash
npm run build
npm run start
```

Production 빌드는 HMR 없고 최적화된 번들 사용. 데모 시연 시 더 안정적.

---

## 9. 스모크 테스트

### 9.1 Central 직접 (Bearer 유효성)

```bash
curl -sS -H "Authorization: Bearer ${HOSPITAL_UPSTREAM_BEARER}" \
  http://localhost:8000/v1/hospital/me/stats | jq .
```

200 응답 + `hospital_id: "HOSP-001"` 포함. 데이터 0은 정상 (아직 TCIA seed 없음).

### 9.2 Portal BFF 경유

브라우저에서 `http://localhost:3000/hospital/HOSP-001` 접속 → Sign-in 화면 → `.env.local`의 `RV_HOSPITAL_ADMIN_TOKENS` 원본 값 (스크립트 실행 시 stdout에 찍힌 값) 입력 → 6-tile 대시보드 렌더.

대시보드에서 확인할 것:
- B-1 Studies: 오늘 0, 누적 0
- B-4 Gateway: `unknown` (Gateway agent 미기동 상태)
- 나머지 타일: 빈 상태여도 레이아웃 렌더 정상

### 9.3 브라우저 DevTools Network 탭

Hospital Dashboard 로드 시 네 개 API 호출 확인:
- `GET /api/hospital/stats` → 200
- `GET /api/hospital/gateway-health` → 200
- `GET /api/hospital/orders` → 200 또는 503 (fulfillment 미기동 시)
- `GET /api/hospital/audit` → 200

Status 401이면 `HOSPITAL_UPSTREAM_BEARER` 값 잘못. 503이면 upstream URL 잘못.

---

## 10. (선택) Order-fulfillment 기동

주문 플로우까지 시연하려면 fulfillment도 띄웁니다.

**알려진 이슈**: `docker-compose.fulfillment.yml`이 사용하는 DB 이름·역할(`radivault_central` DB, `radivault_fulfillment_app` 사용자)이 central 기본값과 다릅니다. 현재 (2026-04-24) 이 갭을 메우는 자동 init 스크립트가 없어 수동 setup 필요. 별도 PR로 정리 예정.

임시 회피 (Kyle 결정 대기): fulfillment 없이 Hospital Dashboard + Buyer Search까지만 데모. 주문 플로우는 Demo Operator Mode canned output으로 fallback.

---

## 11. (선택) 시드 데이터 (TCIA) 주입

현재 (v0.1) TCIA 실 fetch는 `NotImplementedError` 블록 상태입니다.
- 파일: [scripts/demo_seed/download_tcia.py](../../scripts/demo_seed/download_tcia.py) line 122
- 구현 시점: 리허설 R-1 (데모 D-3 영업일 전)
- 구현 후 절차: `inject_all.sh` → 400 studies 주입 → `verify.py` V-1~V-8 PASS

---

## 12. 트러블슈팅

### 12.1 포트 이미 점유됨 (`Bind for 0.0.0.0:XXXX failed`)

k3d 등 다른 서비스가 포트를 잡고 있을 확률 높음.

```bash
# 어떤 프로세스가 점유 중인지
lsof -i :9000 -P

# k3d 멈추기
k3d cluster stop <cluster-name>

# 또는 충돌 컨테이너 확인
docker ps -a --filter publish=9000 --format "table {{.Names}}\t{{.Ports}}"
```

### 12.2 `no such service: postgres` (compose 명령 실패)

기본 `docker-compose.yml`이 아니라 `docker-compose.central.yml`을 써야 합니다. 반드시 **repo 루트**에서:

```bash
# OK
cd ~/Radivault
docker compose -f docker-compose.central.yml up -d

# NG
cd ~/Radivault/src/radivault_central
docker compose up -d postgres   # 이 경로에 compose 파일 없음
```

### 12.3 Container 상태가 `Created`에서 멈춤

`depends_on: service_healthy` 조건이 통과 못 했을 때 발생. 로그 확인:

```bash
docker logs radivault-minio-1 2>&1 | tail -30
docker logs radivault-central-1 2>&1 | tail -30
```

전체 강제 재기동:
```bash
docker compose -f docker-compose.central.yml down
docker compose -f docker-compose.central.yml up -d
```

### 12.4 Bearer 토큰 분실

복구 불가. 기존 kid를 revoke한 뒤 재발급:

```bash
docker exec radivault-central-1 ingest-admin token list --hospital-id HOSP-001
docker exec radivault-central-1 ingest-admin token revoke --kid <kid>
docker exec radivault-central-1 ingest-admin token issue --hospital-id HOSP-001 --note "replacement" --json
```

새 plaintext를 `.env.local`에 반영 후 Portal 재기동 (`npm run dev` 재시작).

### 12.5 Portal이 `Missing required env var` 에러

`web/portal/.env.local` 파일이 존재하나, 필수 키가 비어있음. `env.ts:14-22` 의 `required()` 함수가 던짐. 섹션 3을 다시 실행하거나 수동으로 값 채우기.

### 12.6 `alembic CommandError: No 'script_location' key found`

알려진 v0.1 이슈 (섹션 5 참조). 데모는 영향 없음 (테이블 자동 생성). 무시하거나 수동으로 `alembic.ini`에 `script_location = alembic` 추가.

---

## 13. 정리

완료 후 컨테이너 중지 (데이터는 볼륨에 유지):

```bash
docker compose -f docker-compose.search.yml down
docker compose -f docker-compose.central.yml down
# 볼륨까지 날리려면 down -v (데이터 소실 주의)
```

k3d 재기동:

```bash
k3d cluster start <cluster-name>
```

---

## 변경 이력

| 날짜 | 세션 | 변경 |
|---|---|---|
| 2026-04-24 | Session 13 | 초판. HOSP-001 발급 절차 검증 완료, k3d 포트 충돌·CLI 플래그 정확성·generate_demo_secrets.sh upstream URL 버그 반영. |
