#!/usr/bin/env bash
# demo_live_upload.sh
#
# D-13 demo live-flow helper. Pushes one or both prepared sample DICOMs
# into Orthanc-A (HOSP-001) and/or Orthanc-B (HOSP-002) so the audience
# can watch a study propagate through the gateway daemon (poll_interval=
# 30s) into Central Ingest, then surface in the Buyer Portal /search
# facets within ~1 minute.
#
# Usage:
#   ./demo_live_upload.sh a            # upload MG sample to Orthanc-A
#   ./demo_live_upload.sh b            # upload MG sample to Orthanc-B
#   ./demo_live_upload.sh a ct         # upload CT sample to Orthanc-A
#   ./demo_live_upload.sh b ct         # upload CT sample to Orthanc-B
#   ./demo_live_upload.sh both         # MG to A, CT to B (split modalities
#                                        for clearer side-by-side facets)
#
# Prereqs:
#   * docker compose stack is up (orthanc + orthanc-b)
#   * gateway-a + gateway-b daemons running on host:
#       RADIVAULT_CONFIG=$PWD/configs/demo_gateway.yaml \
#         radivault-gateway start &
#       RADIVAULT_CONFIG=$PWD/configs/demo_gateway_b.yaml \
#         radivault-gateway start &
#   * Sample DICOMs in ./demo_dicoms/ (committed alongside this script).
#
# Notes:
#   * Both Orthanc instances default to basic auth orthanc:orthanc even
#     with ORTHANC__AUTHENTICATION_ENABLED=false, so credentials are
#     hard-coded for the demo. NEVER reuse for production.
#   * Re-uploading the same instance is a no-op on Orthanc (DICOM UID
#     dedup) — pick a fresh sample if you need a second visible push.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DICOM_DIR="${SCRIPT_DIR}/demo_dicoms"
SAMPLE_MG="${DICOM_DIR}/sample_MG_CBIS-DDSM.dcm"
SAMPLE_CT="${DICOM_DIR}/sample_CT_Spine-Mets.dcm"

ORTHANC_A_URL="http://localhost:8042"
ORTHANC_B_URL="http://localhost:8043"
ORTHANC_USER="orthanc"
ORTHANC_PASS="orthanc"

usage() {
  sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 1
}

push() {
  local target="$1"   # a | b
  local file="$2"
  local url
  case "${target}" in
    a) url="${ORTHANC_A_URL}";;
    b) url="${ORTHANC_B_URL}";;
    *) echo "unknown target: ${target}" >&2; exit 2;;
  esac
  if [[ ! -f "${file}" ]]; then
    echo "missing sample file: ${file}" >&2
    exit 3
  fi
  echo "==> Uploading $(basename "${file}") to Orthanc-${target^^} (${url})"
  curl -fsSL \
    -u "${ORTHANC_USER}:${ORTHANC_PASS}" \
    -X POST "${url}/instances" \
    --data-binary "@${file}" \
    -H "Content-Type: application/dicom" | python3 -m json.tool
  echo "==> done. Watch the gateway daemon log; next tick should report uploaded>=1."
}

target="${1:-}"
modality="${2:-mg}"

case "${target}" in
  a|b)
    case "${modality}" in
      mg) push "${target}" "${SAMPLE_MG}";;
      ct) push "${target}" "${SAMPLE_CT}";;
      *)  echo "unknown modality: ${modality}" >&2; usage;;
    esac
    ;;
  both)
    push a "${SAMPLE_MG}"
    push b "${SAMPLE_CT}"
    ;;
  *) usage;;
esac
