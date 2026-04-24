#!/usr/bin/env bash
# RadiVault 데모 환경 시크릿 생성기.
#
# 한 번 실행하면 web/portal/.env.local 파일을 생성(덮어쓰기)한다.
# 값은 현재 머신의 /dev/urandom 기반 openssl 랜덤이고 데모 localhost 전용.
# 프로덕션·파일럿 병원 배포에 재사용하지 말 것.
#
# Usage:
#   ./scripts/demo_setup/generate_demo_secrets.sh [--force]
#
# --force 없이 기존 .env.local 이 있으면 덮어쓰기를 거부한다.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${REPO_ROOT}/web/portal/.env.local"
FORCE=0

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    *) echo "Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

if [[ -f "$ENV_FILE" && "$FORCE" -ne 1 ]]; then
  echo "Refusing to overwrite $ENV_FILE (pass --force to replace)." >&2
  exit 1
fi

# 32/48/64자 base64url 랜덤 (padding 제거, 특수문자 제거).
rand_token() {
  local bytes="$1"
  local len="$2"
  openssl rand -base64 "$bytes" | tr -d '=+/' | cut -c1-"$len"
}

sha256_hex() {
  printf '%s' "$1" | shasum -a 256 | awk '{print $1}'
}

DEMOOP_TOKEN="$(rand_token 32 32)"
SESSION_PASSWORD="$(rand_token 64 64)"

HOSPITAL_ID="HOSP-001"
HOSPITAL_ADMIN_PLAIN="$(rand_token 48 48)"
HOSPITAL_ADMIN_HASH="sha256:$(sha256_hex "$HOSPITAL_ADMIN_PLAIN")"

umask 077
cat > "$ENV_FILE" <<EOF
# RadiVault 데모 환경 변수 (생성: $(date -u +%FT%TZ))
# 이 파일은 .gitignore 로 보호됨. 커밋 금지.
# 프로덕션/파일럿 배포에서 재사용 금지.

# --- Upstream services (로컬 docker-compose 기본값) ---
CENTRAL_INGEST_URL=http://localhost:8000
SEARCH_URL=http://localhost:8001
FULFILLMENT_URL=http://localhost:8002

# --- BFF 세션 ---
SESSION_PASSWORD=${SESSION_PASSWORD}

# --- Demo Operator Mode ---
DEMOOP_TOKEN=${DEMOOP_TOKEN}

# --- Hospital admin token (BFF stub 검증) ---
# 브라우저 /hospital Sign-in 에 입력할 원본 토큰은 별도 메모에 보관할 것.
# 여기엔 서버 측 해시 매핑만 넣는다 ({hospital_id: "sha256:hex"}).
RV_HOSPITAL_ADMIN_TOKENS={"${HOSPITAL_ID}":"${HOSPITAL_ADMIN_HASH}"}

# --- Gateway → Central upstream Bearer ---
# central-ingest 의 auth_token 테이블에서 발급된 실제 토큰을 여기 채울 것.
# 발급 절차: docs/ops/demo-deploy-runbook.md §3 참조.
HOSPITAL_UPSTREAM_BEARER=

# --- Revenue 시뮬레이션 (Hospital Dashboard 타일 B-2) ---
# 클라이언트 노출 값 — Kyle 결정 전까지 placeholder.
# 모든 타일에 "시뮬레이션 — v0.2 정산 대기" disclaimer 표시됨.
NEXT_PUBLIC_DEMO_UNIT_PRICE_USD=5
NEXT_PUBLIC_DEMO_HOSPITAL_SHARE=0.35
NEXT_PUBLIC_DEMO_KRW_PER_USD=1350

# --- NODE_ENV (production 배포 시 production 으로) ---
NODE_ENV=development
EOF

chmod 600 "$ENV_FILE"

echo "Generated: $ENV_FILE"
echo
echo "===== Hospital admin 브라우저 로그인용 원본 토큰 (이 메시지 한 번만 출력) ====="
echo "hospital_id:   ${HOSPITAL_ID}"
echo "admin_token:   ${HOSPITAL_ADMIN_PLAIN}"
echo "================================================================================"
echo
echo "다음 단계:"
echo "  1. 위 admin_token 을 안전한 곳(1Password 등)에 옮기고 터미널 스크롤백을 지울 것."
echo "  2. central-ingest 를 docker-compose 로 띄우고 ingest-admin 으로 hospital"
echo "     upstream bearer 발급 → .env.local 의 HOSPITAL_UPSTREAM_BEARER 채울 것."
echo "     (절차: docs/ops/demo-deploy-runbook.md §3)"
echo "  3. TCIA 시드 실행: scripts/demo_seed/ (Rehearsal R-1 단계)."
echo "  4. cd web/portal && npm run dev 으로 포털 기동."
