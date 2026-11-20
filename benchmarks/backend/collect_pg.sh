#!/usr/bin/env bash
# Snapshot Postgres: pg_stat_statements, table/index stats, settings, activity.
# Chạy từ root repo.
#
#   benchmarks/backend/collect_pg.sh <run-dir> before
#   benchmarks/backend/collect_pg.sh <run-dir> after
#   benchmarks/backend/collect_pg.sh <run-dir> reset
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/benchmarks/lib/common.sh"

RUN_DIR="${1:?usage: collect_pg.sh <run-dir> <before|after|reset>}"
LABEL="${2:-after}"
OUT="$RUN_DIR/backend/pg_stat_statements"
mkdir -p "$OUT"

psql() {
  compose exec -T postgres psql -U "${POSTGRES_USER:-postgres}" \
    -d "${BENCH_DB:-eyetracking_bench}" -X -q "$@"
}

if [ "$LABEL" = "reset" ]; then
  psql -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;" >/dev/null 2>&1
  psql -c "SELECT pg_stat_statements_reset();" >/dev/null
  echo "reset pg_stat_statements"
  exit 0
fi

psql -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;" >/dev/null 2>&1

psql -c "\copy (
  SELECT
    left(query, 240) AS query,
    calls,
    total_exec_time,
    mean_exec_time,
    rows,
    shared_blks_hit,
    shared_blks_read,
    temp_blks_written
  FROM pg_stat_statements
  WHERE query NOT ILIKE '%pg_stat_statements%'
    AND query NOT ILIKE '%ALTER ROLE%'
    AND query NOT ILIKE '%CREATE ROLE%'
    AND query NOT ILIKE '%PASSWORD%'
  ORDER BY total_exec_time DESC
  LIMIT 100
) TO STDOUT WITH CSV HEADER" > "$OUT/${LABEL}_top_queries.csv"

psql -c "\copy (
  SELECT relname, seq_scan, idx_scan, n_tup_ins, n_tup_upd, n_tup_del, n_live_tup
  FROM pg_stat_user_tables
  ORDER BY seq_scan DESC, relname
) TO STDOUT WITH CSV HEADER" > "$OUT/${LABEL}_tables.csv"

psql -c "\copy (
  SELECT relname, indexrelname, idx_scan, idx_tup_read, idx_tup_fetch
  FROM pg_stat_user_indexes
  ORDER BY idx_scan ASC, relname
) TO STDOUT WITH CSV HEADER" > "$OUT/${LABEL}_indexes.csv"

psql -c "\copy (
  SELECT name, setting, unit, category
  FROM pg_settings
  WHERE name IN (
    'shared_buffers','work_mem','maintenance_work_mem','effective_cache_size',
    'max_connections','random_page_cost','track_io_timing',
    'shared_preload_libraries','statement_timeout','idle_in_transaction_session_timeout'
  )
  ORDER BY name
) TO STDOUT WITH CSV HEADER" > "$OUT/${LABEL}_settings.csv"

psql -c "\copy (
  SELECT pid, state, wait_event_type, wait_event, left(query, 160) AS query,
         now() - query_start AS age
  FROM pg_stat_activity
  WHERE datname = current_database() AND pid <> pg_backend_pid()
  ORDER BY query_start NULLS LAST
) TO STDOUT WITH CSV HEADER" > "$OUT/${LABEL}_activity.csv"

echo "$OUT/${LABEL}_*.csv"
