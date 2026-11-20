#!/usr/bin/env bash
# Chạy backend fast tests trên database test riêng.
#
#   ./scripts/test_backend.sh
#   ./scripts/test_backend.sh tests/fast/test_auth.py -q
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

: "${POSTGRES_USER:?thiếu POSTGRES_USER}"
: "${POSTGRES_PASSWORD:?thiếu POSTGRES_PASSWORD}"

TEST_DB="${TEST_DB:-eyetracking_test}"
log() { printf '[test_backend] %s\n' "$*"; }

log "tạo database $TEST_DB"
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS \"$TEST_DB\";" >/dev/null
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
    -c "CREATE DATABASE \"$TEST_DB\";" >/dev/null

log "build migrate + backend-test"
docker compose build migrate backend-test >/dev/null

log "chạy migrations cho $TEST_DB"
docker compose run --rm -e PGDATABASE="$TEST_DB" migrate >/dev/null

log "chạy pytest"
docker compose --profile test run --rm backend-test \
    python -m pytest -m fast -q --tb=short "$@"
log "OK"
