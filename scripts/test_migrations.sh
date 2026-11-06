#!/usr/bin/env bash
# Test runner migration trên PostgreSQL tạm (không dùng DB development).
#
#   ./scripts/test_migrations.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CONTAINER="eyelearning-migrate-test-$$"
DB="eyelearning_migrate_test"
TMP_DIR="$(mktemp -d)"
cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

docker run --name "$CONTAINER" --rm -d \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB="$DB" \
  pgvector/pgvector:0.8.7-pg16 >/dev/null
for attempt in $(seq 1 50); do
  if docker exec "$CONTAINER" pg_isready -U postgres >/dev/null 2>&1; then break; fi
  sleep 0.2
done

run_migrate() {
  docker exec -e PGHOST=127.0.0.1 -e PGUSER=postgres -e PGPASSWORD=postgres \
    -e PGDATABASE="$DB" "$CONTAINER" bash /db/migrate.sh /db/migrations
}

psql_db() {
  docker exec -e PGPASSWORD=postgres "$CONTAINER" \
    psql -U postgres -d "$DB" -v ON_ERROR_STOP=1 -tA "$@"
}

# Bản sao db để có thể sửa file migration trong test.
rm -rf "$TMP_DIR/db"
cp -a "$ROOT_DIR/db" "$TMP_DIR/db"
docker exec "$CONTAINER" rm -rf /db
docker cp "$TMP_DIR/db" "$CONTAINER:/db" >/dev/null

# 1) Bootstrap rỗng
run_migrate >/dev/null
COUNT="$(psql_db -c 'SELECT count(*) FROM schema_migrations')"
[ "$COUNT" = "2" ] || fail "bootstrap phải có 2 migration, có $COUNT"
pass "bootstrap rỗng"

# 2) Rerun idempotent
run_migrate >/dev/null
COUNT="$(psql_db -c 'SELECT count(*) FROM schema_migrations')"
[ "$COUNT" = "2" ] || fail "rerun không được nhân bản migration"
pass "rerun idempotent"

# 3) Checksum mismatch
echo "-- tampered" >> "$TMP_DIR/db/migrations/001_baseline.sql"
docker exec "$CONTAINER" rm -rf /db
docker cp "$TMP_DIR/db" "$CONTAINER:/db" >/dev/null
if run_migrate >/dev/null 2>&1; then
  fail "checksum mismatch phải fail"
fi
pass "checksum mismatch fail"

# 4) Transaction lỗi không ghi migration
rm -rf "$TMP_DIR/db"
cp -a "$ROOT_DIR/db" "$TMP_DIR/db"
cat > "$TMP_DIR/db/migrations/003_fail.sql" <<'SQL'
CREATE TABLE should_rollback (id integer);
SELECT 1 / 0;
SQL
docker exec "$CONTAINER" rm -rf /db
docker cp "$TMP_DIR/db" "$CONTAINER:/db" >/dev/null
if run_migrate >/dev/null 2>&1; then
  fail "migration lỗi phải fail"
fi
COUNT="$(psql_db -c "SELECT count(*) FROM schema_migrations WHERE filename='003_fail.sql'")"
[ "$COUNT" = "0" ] || fail "migration lỗi không được ghi checksum"
TABLE_EXISTS="$(psql_db -c "SELECT to_regclass('public.should_rollback') IS NOT NULL")"
[ "$TABLE_EXISTS" = "f" ] || fail "transaction lỗi phải rollback DDL"
pass "transaction lỗi rollback + không ghi checksum"

# 5) Old history detection
psql_db -c "DROP TABLE IF EXISTS should_rollback" >/dev/null
psql_db -c "INSERT INTO schema_migrations (filename, checksum) VALUES ('001_init.sql', 'x')" >/dev/null
if run_migrate >/dev/null 2>&1; then
  fail "old history phải fail"
fi
pass "old history detection"

# 6) Old schema without tracking
psql_db -c "DELETE FROM schema_migrations WHERE filename='001_init.sql'" >/dev/null
psql_db -c "DROP TABLE schema_migrations" >/dev/null
psql_db -c "CREATE TABLE legacy_table (id integer)" >/dev/null
if run_migrate >/dev/null 2>&1; then
  fail "old schema without tracking phải fail"
fi
pass "old schema without tracking detection"

# 7) Advisory lock: runner phải chờ lock rồi mới chạy
rm -rf "$TMP_DIR/db"
cp -a "$ROOT_DIR/db" "$TMP_DIR/db"
docker exec "$CONTAINER" rm -rf /db
docker cp "$TMP_DIR/db" "$CONTAINER:/db" >/dev/null
docker exec -e PGPASSWORD=postgres "$CONTAINER" \
  psql -U postgres -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS \"$DB\";" -c "CREATE DATABASE \"$DB\";" >/dev/null
docker exec -e PGPASSWORD=postgres "$CONTAINER" \
  psql -U postgres -d "$DB" -c "SELECT pg_advisory_lock(hashtext('eyelearning_migrations')); SELECT pg_sleep(2);" >/dev/null &
LOCK_PID=$!
sleep 0.3
START="$(date +%s)"
run_migrate >/dev/null
ELAPSED=$(( $(date +%s) - START ))
wait "$LOCK_PID" || true
[ "$ELAPSED" -ge 1 ] || fail "runner phải chờ advisory lock (elapsed=${ELAPSED}s)"
pass "advisory lock contention"

echo "OK: migration runner tests passed."
