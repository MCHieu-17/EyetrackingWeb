#!/usr/bin/env bash
# Chạy Playwright E2E trên stack đang chạy.
#
#   ./scripts/e2e.sh
#   E2E_BASE_URL=http://localhost:3000 ./scripts/e2e.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${E2E_BASE_URL:-http://localhost:3000}"

if ! curl -fsS --max-time 5 "$BASE_URL/nginx-health" >/dev/null; then
    echo "[e2e] stack chưa sẵn sàng tại $BASE_URL" >&2
    exit 1
fi

cd "$ROOT_DIR/frontend"
E2E_BASE_URL="$BASE_URL" npx playwright test "$@"
