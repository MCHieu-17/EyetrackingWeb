#!/usr/bin/env bash
# Smoke test nhanh sau khi stack đã chạy.
#
#   ./scripts/smoke.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

log() { printf '[smoke] %s\n' "$*"; }

check() {
    local name="$1"
    local url="$2"
    log "$name -> $url"
    curl -fsS --max-time 10 "$url" >/dev/null
}

check "nginx" "http://localhost:3000/nginx-health"
check "backend" "http://localhost:8001/health"
check "gaze" "http://localhost:3000/gaze/health"
check "chatbot" "http://localhost:8002/health"

log "OK"
