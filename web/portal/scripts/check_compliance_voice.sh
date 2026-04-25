#!/usr/bin/env bash
# check_compliance_voice.sh — FR-NFR-7 / dev-spec-portal-redesign §9.4
#
# Fails CI if any forbidden compliance vocabulary appears in the portal
# source. The forbidden ladder mirrors the design-spec lint:
#   EN: certified | guaranteed | HIPAA-compliant
#   KR: 인증됨 | 보장
#
# Allowed vocabulary (do not flag):
#   "aligned" / "in preparation" / "compliant with PIPA §28-8" /
#   "designed to support" / "기준 비식별화" / "준수" / "정렬" / "준비 중"
#
# The script intentionally limits its search to `src/` so that demo
# fixtures, package metadata, lockfiles, and node_modules cannot cause
# false positives.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${ROOT}/src"

# Patterns: standalone "certified" / "guaranteed" / "HIPAA-compliant"
# We allow "compliant with PIPA §28-8" and "compliant" so we have to be
# precise: forbid "HIPAA-compliant" specifically (hyphenated form), and
# the bare words "certified" / "guaranteed".
PATTERN_EN='\b(certified|guaranteed)\b|HIPAA-compliant'
PATTERN_KR='인증됨|보장'

EXIT=0

# Files that intentionally reference the forbidden vocabulary so the
# lint rule itself can be expressed and tested. Add absolute paths
# (relative to TARGET) one per line.
EXCLUDES=(
  "${TARGET}/__tests__/i18n.test.ts"
  "${TARGET}/lib/i18n.ts"
)
EXCLUDE_ARGS=()
for f in "${EXCLUDES[@]}"; do
  EXCLUDE_ARGS+=(--exclude="$(basename "$f")")
done

if grep -RInE --include='*.ts' --include='*.tsx' --include='*.json' --include='*.md' \
    "${EXCLUDE_ARGS[@]}" \
    "${PATTERN_EN}" "${TARGET}" 2>/dev/null; then
  echo "[FAIL] forbidden EN compliance vocabulary detected (FR-NFR-7)" >&2
  EXIT=1
fi

if grep -RIn --include='*.ts' --include='*.tsx' --include='*.json' --include='*.md' \
    "${EXCLUDE_ARGS[@]}" \
    -e "인증됨" -e "보장" "${TARGET}" 2>/dev/null; then
  echo "[FAIL] forbidden KR compliance vocabulary detected (FR-NFR-7)" >&2
  EXIT=1
fi

if [[ "${EXIT}" -eq 0 ]]; then
  echo "[PASS] compliance-voice lint clean"
fi

exit "${EXIT}"
