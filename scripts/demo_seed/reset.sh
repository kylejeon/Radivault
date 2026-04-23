#!/usr/bin/env bash
# Soft / hard reset for the demo environment (dev-spec §8.4).
#
#   reset.sh soft   — truncate demo tables + staging; keep Orthanc + cache.
#   reset.sh hard   — docker-compose down -v + wipe demo_data/cache.
#
# soft mode is the operator's friend — it runs in under a minute and leaves
# the TCIA cache + Orthanc intact so reseeding only repopulates the DB.

set -euo pipefail
MODE="${1:-soft}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

case "$MODE" in
  soft)
    echo "[reset] soft: truncating demo tables + staging"
    # Wired to docker-compose-demo.yml which is pending (Week 3 of dev-spec).
    # The exec invocations below intentionally no-op when the compose file
    # is absent so the script is safe to stage before the demo stack is
    # lit up.
    if [[ -f "$ROOT_DIR/docker-compose-demo.yml" ]]; then
      docker-compose -f "$ROOT_DIR/docker-compose-demo.yml" exec -T postgres \
        psql -U postgres -d radivault -f /scripts/truncate_demo.sql
      docker-compose -f "$ROOT_DIR/docker-compose-demo.yml" exec -T minio \
        mc rm -r --force minio/radivault/staging/ || true
    else
      echo "[reset] docker-compose-demo.yml not present; skipping container steps."
    fi
    ;;
  hard)
    echo "[reset] hard: docker-compose down -v + cache wipe"
    if [[ -f "$ROOT_DIR/docker-compose-demo.yml" ]]; then
      docker-compose -f "$ROOT_DIR/docker-compose-demo.yml" down -v
    fi
    rm -rf "$ROOT_DIR/demo_data/cache"
    ;;
  *)
    echo "Usage: $0 [soft|hard]" >&2
    exit 2
    ;;
esac
echo "[reset] done ($MODE)"
