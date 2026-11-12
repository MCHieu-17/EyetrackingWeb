#!/usr/bin/env bash
# Chạy load test browse bằng k6 (local hoặc Docker).
#
#   ./scripts/loadtest.sh
#   BASE_URL=http://localhost:3000 ./scripts/loadtest.sh
#
# Yêu cầu: k6 đã cài, hoặc Docker để chạy image grafana/k6.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${BASE_URL:-http://localhost:3000}"
SCRIPT="$ROOT_DIR/loadtest/browse.js"

log() { printf '[loadtest] %s\n' "$*"; }

if command -v k6 >/dev/null 2>&1; then
    log "k6 local -> $BASE_URL"
    BASE_URL="$BASE_URL" k6 run "$SCRIPT"
    exit 0
fi

if command -v docker >/dev/null 2>&1; then
    log "k6 docker -> $BASE_URL"
    docker run --rm -i --network host \
        -e BASE_URL="$BASE_URL" \
        -e TEST_EMAIL="${TEST_EMAIL:-student@school.edu.vn}" \
        -e TEST_PASSWORD="${TEST_PASSWORD:-Password123!}" \
        grafana/k6 run - < "$SCRIPT"
    exit 0
fi

log "Không tìm thấy k6 hoặc Docker — bỏ qua (exit 0)."
log "Cài k6: https://k6.io/docs/get-started/installation/"
