#!/usr/bin/env bash
# Chạy backend tests với DATABASE_URL trỏ đúng DB test riêng.
# Yêu cầu: postgres đang chạy + DB `eyelearning_refactor_test` đã được dựng
# bằng `./scripts/test_db.sh` (baseline Phase 1).
#
#   ./scripts/test_backend.sh
#   ./scripts/test_backend.sh -k auth -v
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

: "${POSTGRES_USER:?thiếu POSTGRES_USER}"
: "${POSTGRES_PASSWORD:?thiếu POSTGRES_PASSWORD}"

TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5435/eyelearning_refactor_test}"

PYTHON="${PYTHON:-$ROOT_DIR/backend/.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python3"
fi

cd "$ROOT_DIR/backend"
if [ "$#" -eq 0 ]; then
  set -- tests
fi
DATABASE_URL="$TEST_DATABASE_URL" "$PYTHON" -m pytest "$@"
