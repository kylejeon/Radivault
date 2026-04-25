#!/usr/bin/env bash
# check_tbd_in_build.sh — FR-HP-9 / AC-HP-2.
#
# After `next build` produces the `.next/` output, this script scans the
# rendered HTML / static chunks for the literal `[TBD]` placeholder. Any
# hit fails CI — production builds must have the legal block populated
# from the `NEXT_PUBLIC_LEGAL_*` environment variables.
#
# Run this only when NODE_ENV=production. The dev server intentionally
# allows `[TBD]` so a developer building features unrelated to the
# Korean footer is not blocked.

set -euo pipefail

if [[ "${NODE_ENV:-}" != "production" ]]; then
  echo "[SKIP] check_tbd_in_build.sh — NODE_ENV is not production"
  exit 0
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="${ROOT}/.next"

if [[ ! -d "${BUILD_DIR}" ]]; then
  echo "[FAIL] .next/ build dir not found at ${BUILD_DIR}" >&2
  exit 1
fi

# Scan static + server chunks. Use `-l` first to avoid spamming the log
# with the actual placeholder snippets.
if grep -rIl '\[TBD\]' "${BUILD_DIR}" 2>/dev/null; then
  echo "[FAIL] '[TBD]' literal detected in production build (FR-HP-9)" >&2
  echo "       populate NEXT_PUBLIC_LEGAL_* env vars before building." >&2
  exit 1
fi

echo "[PASS] no [TBD] literals in production build"
