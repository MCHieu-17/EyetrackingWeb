#!/usr/bin/env bash
# Test migration trên database tạm, không đụng DB chính.
#
#   ./scripts/test_migrations.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

: "${POSTGRES_USER:?thiếu POSTGRES_USER}"
: "${POSTGRES_DB:?thiếu POSTGRES_DB}"

TEST_DB="${TEST_DB:-eyetracking_migration_test}"

log() { printf '[test_migrations] %s\n' "$*"; }

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

log "kiểm tra schema"
count="$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -tAc \
    "SELECT count(*) FROM schema_migrations;")"
[ "$count" = "1" ] || { echo "expected 1 migration, got $count" >&2; exit 1; }

generation="$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -tAc \
    "SELECT value FROM app_metadata WHERE key = 'schema_generation';")"
[ "$generation" = "6" ] || { echo "expected schema_generation=6, got $generation" >&2; exit 1; }

identity_table="$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -tAc \
    "SELECT to_regclass('public.user_identities');")"
[ "$identity_table" = "user_identities" ] || {
    echo "user_identities missing (got $identity_table)" >&2
    exit 1
}

log "OK"
