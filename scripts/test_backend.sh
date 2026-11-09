#!/usr/bin/env bash
# Chạy backend integration tests trên database tạm.
#
#   ./scripts/test_backend.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

: "${POSTGRES_USER:?thiếu POSTGRES_USER}"
: "${POSTGRES_PASSWORD:?thiếu POSTGRES_PASSWORD}"
: "${POSTGRES_DB:?thiếu POSTGRES_DB}"

TEST_DB="${TEST_DB:-eyetracking_test}"
POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-5435}"

log() { printf '[test_backend] %s\n' "$*"; }

cleanup() {
    docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
        -c "DROP DATABASE IF EXISTS \"$TEST_DB\";" >/dev/null 2>&1 || true
}
trap cleanup EXIT

log "tạo database $TEST_DB"
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS \"$TEST_DB\";" >/dev/null
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
    -c "CREATE DATABASE \"$TEST_DB\";" >/dev/null

log "chạy migrations"
docker compose run --rm -e PGDATABASE="$TEST_DB" migrate

log "chạy pytest"
cd backend
TEST_DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:${POSTGRES_HOST_PORT}/${TEST_DB}" \
    .venv/bin/pytest -q

log "OK"
