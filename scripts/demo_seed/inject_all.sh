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
if [[ "${DEMO_SEED_SKIP_GATEWAY:-0}" == "1" ]]; then
  say "STEP 3/6 SKIPPED: radivault-gateway sync-once (DEMO_SEED_SKIP_GATEWAY=1)"
else
  say "STEP 3/6: radivault-gateway sync-once (host-side CLI, config=${GATEWAY_CONFIG})"
  if ! command -v radivault-gateway >/dev/null 2>&1; then
    say "WARN: radivault-gateway not on PATH — skipping step 3."
    say "      Install with: pip install -e . (from repo root)"
    say "      Or activate the venv: source .venv/bin/activate"
  elif [[ ! -f "${GATEWAY_CONFIG}" ]]; then
    say "WARN: gateway config missing: ${GATEWAY_CONFIG} — skipping step 3."
    say "      Expected path: configs/demo_gateway.yaml (install-guide §6)."
  else
    radivault-gateway -c "${GATEWAY_CONFIG}" sync-once \
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
