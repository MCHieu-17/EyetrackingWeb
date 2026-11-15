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

log "kiểm tra migration đã áp khớp file nguồn"
expected_migrations="$(
    cd "$ROOT_DIR/db/migrations"
    for file in *.sql; do
        printf '%s|%s\n' "$file" "$(sha256sum "$file" | cut -d' ' -f1)"
    done | sort
)"
actual_migrations="$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -tAc \
    "SELECT filename || '|' || checksum FROM schema_migrations ORDER BY filename;")"
[ "$actual_migrations" = "$expected_migrations" ] || {
    echo "applied migrations/checksums do not match db/migrations" >&2
    printf 'expected:\n%s\nactual:\n%s\n' "$expected_migrations" "$actual_migrations" >&2
    exit 1
}

log "kiểm tra chạy lại migration là idempotent"
docker compose run --rm -e PGDATABASE="$TEST_DB" migrate >/dev/null
after_rerun="$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -tAc \
    "SELECT filename || '|' || checksum FROM schema_migrations ORDER BY filename;")"
[ "$after_rerun" = "$actual_migrations" ] || {
    echo "migration rerun changed schema_migrations" >&2
    exit 1
}

log "kiểm tra schema generation 12"
generation="$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -tAc \
    "SELECT value FROM app_metadata WHERE key = 'schema_generation';")"
[ "$generation" = "12" ] || { echo "expected schema_generation=12, got $generation" >&2; exit 1; }

core_tables="$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -tAc \
    "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'
       AND tablename <> 'schema_migrations';")"
[ "$core_tables" = "24" ] || {
    echo "expected 24 core tables, got $core_tables" >&2
    exit 1
}

for table in oauth_accounts background_jobs aois content_views view_layouts slides; do
    exists="$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -tAc \
        "SELECT to_regclass('public.$table');")"
    [ "$exists" = "$table" ] || {
        echo "$table missing (got $exists)" >&2
        exit 1
    }
done

legacy_tables="$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -tAc \
    "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'
       AND tablename IN (
         'course_versions', 'lesson_versions', 'slide_versions',
         'course_version_items', 'lesson_version_slides', 'quiz_specs',
         'gaze_batches', 'aoi_sets', 'aoi_hits', 'analysis_runs',
         'presentation_metrics', 'slide_documents'
       );")"
[ "$legacy_tables" = "0" ] || {
    echo "legacy versioning/analysis tables still present (got $legacy_tables)" >&2
    exit 1
}

log "OK"
