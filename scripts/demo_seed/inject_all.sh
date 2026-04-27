#!/usr/bin/env bash
# Inject the full demo-seed pipeline end-to-end.
#
# Dev-spec buyer-portal-demo §8 FR-S-8. One-liner entry point for the demo
# operator — assumes docker-compose stacks are already up (install-guide §4).
#
# Steps:
#   1. download_tcia.py           — TCIA → local cache (idempotent)
#   2. load_orthanc.py            — cache  → Orthanc STOW-RS (idempotent)
#   3. radivault-gateway sync-once — Orthanc → De-ID → Central
#   4. seed_buyer.py              — demo buyer + API key
#   5. seed_hospital.py           — demo hospital row (token optional)
#   6. verify.py                  — V-1..V-8 checks + demo_seed_ready.lock
#
# Environment variables (all optional):
#   DEMO_SEED_SKIP_DOWNLOAD=1      # skip step 1 (cache already populated)
#   DEMO_SEED_SKIP_ORTHANC=1       # skip step 2 (Orthanc already loaded)
#   DEMO_SEED_SKIP_GATEWAY=1       # skip step 3 (gateway already ran)
#   DEMO_SEED_ACCEPT_RESTRICTED=1  # pass --accept-restricted to download
#   DEMO_SEED_ISSUE_HOSPITAL_TOKEN=1  # also mint HOSPITAL_UPSTREAM_BEARER
#   DEMO_SEED_CONTAINER=radivault-central-1  # central container name
#   DEMO_SEED_SEARCH_CONTAINER=radivault-search-1
#
# Exit codes:
#   0 on all PASS (lock file created)
#   non-zero: whichever step failed first (we use `set -e`)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
mkdir -p "${LOG_DIR}"
TS="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/inject_all_${TS}.log"

PY="${PY:-python3}"
CENTRAL_CONTAINER="${DEMO_SEED_CONTAINER:-radivault-central-1}"
SEARCH_CONTAINER="${DEMO_SEED_SEARCH_CONTAINER:-radivault-search-1}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ts() { date +"%Y-%m-%d %H:%M:%S"; }
say() { printf "[%s] %s\n" "$(ts)" "$*" | tee -a "${LOG_FILE}"; }
die() { printf "[%s] FATAL: %s\n" "$(ts)" "$*" | tee -a "${LOG_FILE}" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "command not found on PATH: $1"
}

require_cmd "${PY}"
require_cmd docker

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

say "===== RadiVault demo-seed injection — $(ts) ====="
say "log file: ${LOG_FILE}"
say "repo root: ${REPO_ROOT}"

# --- Step 1: TCIA download -------------------------------------------------
if [[ "${DEMO_SEED_SKIP_DOWNLOAD:-0}" == "1" ]]; then
  say "STEP 1/6 SKIPPED: download_tcia.py (DEMO_SEED_SKIP_DOWNLOAD=1)"
else
  say "STEP 1/6: download_tcia.py"
  ACCEPT_FLAG=""
  if [[ "${DEMO_SEED_ACCEPT_RESTRICTED:-0}" == "1" ]]; then
    ACCEPT_FLAG="--accept-restricted"
  fi
  # shellcheck disable=SC2086
  "${PY}" "${SCRIPT_DIR}/download_tcia.py" ${ACCEPT_FLAG} 2>&1 | tee -a "${LOG_FILE}"
fi

# --- Step 2: Orthanc STOW-RS load -----------------------------------------
if [[ "${DEMO_SEED_SKIP_ORTHANC:-0}" == "1" ]]; then
  say "STEP 2/6 SKIPPED: load_orthanc.py (DEMO_SEED_SKIP_ORTHANC=1)"
else
  say "STEP 2/6: load_orthanc.py"
  "${PY}" "${SCRIPT_DIR}/load_orthanc.py" 2>&1 | tee -a "${LOG_FILE}"
fi

# --- Step 3: Gateway flow A (once) ----------------------------------------
GATEWAY_CONFIG="${REPO_ROOT}/configs/demo_gateway.yaml"

# jpg-preview-defacing FR-PREVIEW-3 — host CLI 데모 경로용 env wiring.
# docker-compose.yml 의 gateway-agent 환경변수는 컨테이너 모드 전용이라 host
# 에서 `radivault-gateway sync-once` 를 직접 실행하는 본 스크립트와는 무관.
# 따라서 여기서 명시적으로 export 한다. 이미 정의된 값은 덮어쓰지 않는다.
#
# - PREVIEW_PIPELINE_ENABLED:  src/radivault_gateway/preview_pipeline.py의
#   is_pipeline_enabled() 가 읽는 feature flag (FR-PREVIEW-3).
# - DEFACE_SIDECAR_URL:        head/neck CT/MR 시리즈에서 게이트웨이가 호출하는
#   AFNI sidecar HTTP 엔드포인트. docker-compose.yml 에 127.0.0.1:8090 host
#   port 가 매핑돼 있어 host 모드에서 도달 가능.
# - RV_CENTRAL_DATABASE_URL:   preview_clients.PgFrameWriter 가 사용하는
#   central Postgres DSN. docker-compose.central.yml 의 central_app/central_app
#   기본 자격증명 + host 5432 포트.
# - RV_MINIO_ENDPOINT/_ACCESS_KEY/_SECRET_KEY: MinioJpegClient 가 frame JPG 를
#   업로드하는 MinIO. docker-compose.central.yml 의 minioadmin/minioadmin +
#   host 9000 포트.
export PREVIEW_PIPELINE_ENABLED="${PREVIEW_PIPELINE_ENABLED:-true}"
export DEFACE_SIDECAR_URL="${DEFACE_SIDECAR_URL:-http://127.0.0.1:8090}"
export RV_CENTRAL_DATABASE_URL="${RV_CENTRAL_DATABASE_URL:-postgresql+psycopg://central_app:central_app@127.0.0.1:5432/central}"
export RV_MINIO_ENDPOINT="${RV_MINIO_ENDPOINT:-http://127.0.0.1:9000}"
export RV_MINIO_ACCESS_KEY="${RV_MINIO_ACCESS_KEY:-minioadmin}"
export RV_MINIO_SECRET_KEY="${RV_MINIO_SECRET_KEY:-minioadmin}"

if [[ "${DEMO_SEED_SKIP_GATEWAY:-0}" == "1" ]]; then
  say "STEP 3/6 SKIPPED: radivault-gateway sync-once (DEMO_SEED_SKIP_GATEWAY=1)"
else
  say "STEP 3/6: radivault-gateway sync-once (host-side CLI, config=${GATEWAY_CONFIG})"
  say "  PREVIEW_PIPELINE_ENABLED=${PREVIEW_PIPELINE_ENABLED} DEFACE_SIDECAR_URL=${DEFACE_SIDECAR_URL}"
  if ! command -v radivault-gateway >/dev/null 2>&1; then
    say "WARN: radivault-gateway not on PATH — skipping step 3."
    say "      Install with: pip install -e . (from repo root)"
    say "      Or activate the venv: source .venv/bin/activate"
  elif [[ ! -f "${GATEWAY_CONFIG}" ]]; then
    say "WARN: gateway config missing: ${GATEWAY_CONFIG} — skipping step 3."
    say "      Expected path: configs/demo_gateway.yaml (install-guide §6)."
  else
    # --since 2000-01-01 overrides the pacs.query.lookback_days cap (max 365).
    # TCIA historic StudyDate spans ~2000-2020, so we cast a wide net here.
    radivault-gateway -c "${GATEWAY_CONFIG}" sync-once --since 2000-01-01 \
      2>&1 | tee -a "${LOG_FILE}" || {
        say "WARN: radivault-gateway sync-once returned non-zero. Continuing — verify.py will catch residual failures."
      }
  fi
fi

# --- Step 4: seed_buyer ----------------------------------------------------
say "STEP 4/6: seed_buyer.py"
"${PY}" "${SCRIPT_DIR}/seed_buyer.py" \
  --container "${SEARCH_CONTAINER}" \
  --skip-if-key-file-exists \
  2>&1 | tee -a "${LOG_FILE}"

# --- Step 5: seed_hospital -------------------------------------------------
say "STEP 5/6: seed_hospital.py"
ISSUE_FLAG=""
if [[ "${DEMO_SEED_ISSUE_HOSPITAL_TOKEN:-0}" == "1" ]]; then
  ISSUE_FLAG="--issue-token"
fi
# shellcheck disable=SC2086
"${PY}" "${SCRIPT_DIR}/seed_hospital.py" \
  --container "${CENTRAL_CONTAINER}" \
  ${ISSUE_FLAG} \
  2>&1 | tee -a "${LOG_FILE}"

# --- Step 6: verify --------------------------------------------------------
say "STEP 6/6: verify.py"
if "${PY}" "${SCRIPT_DIR}/verify.py" 2>&1 | tee -a "${LOG_FILE}"; then
  say "===== ALL CHECKS PASSED — demo_seed_ready.lock created ====="
  exit 0
else
  rc=$?
  say "===== VERIFICATION FAILED (rc=${rc}) — see ${LOG_FILE} ====="
  exit "${rc}"
fi
