#!/usr/bin/env bash
# Chạy backend tests với DATABASE_URL trỏ đúng DB test local.
# Yêu cầu: postgres đang chạy + DB `eyetracking_test` đã có migrations.
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

cd "$ROOT_DIR/backend"
DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5435/eyetracking_test" \
  .venv/bin/python -m pytest tests "$@"
