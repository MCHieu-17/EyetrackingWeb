#!/usr/bin/env bash
# Chạy toàn bộ EXPLAIN ANALYZE với ID thật từ fixtures.json.
#   benchmarks/backend/run_explain.sh <run-dir> <fixtures.json>
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/benchmarks/lib/common.sh"

RUN_DIR="${1:?usage: run_explain.sh <run-dir> <fixtures.json>}"
FIXTURES="${2:?usage: run_explain.sh <run-dir> <fixtures.json>}"
OUT="$RUN_DIR/backend/explain"
mkdir -p "$OUT"

CORE_COURSE_ID="$(json_get "$FIXTURES" 'd["ids"]["core_course_id"]')"
CORE_VISIT_ID="$(json_get "$FIXTURES" 'd["ids"]["core_visit_id"]')"
CORE_VIEW_ID="$(json_get "$FIXTURES" 'd["ids"]["core_view_ids"][0]')"
CORE_SLIDE_ID="$(json_get "$FIXTURES" 'd["ids"]["core_slide_ids"][0]')"
BENCH_DB="${BENCH_DB:-eyetracking_bench}"

for sql in "$ROOT_DIR"/benchmarks/backend/sql/explain/*.sql; do
  name="$(basename "$sql" .sql)"
  log "EXPLAIN $name"
  compose exec -T postgres psql -U "${POSTGRES_USER:-postgres}" \
    -d "$BENCH_DB" -X -v ON_ERROR_STOP=1 \
    -v core_course_id="$CORE_COURSE_ID" \
    -v core_visit_id="$CORE_VISIT_ID" \
    -v core_view_id="$CORE_VIEW_ID" \
    -v core_slide_id="$CORE_SLIDE_ID" \
    < "$sql" > "$OUT/${name}.txt"
done

echo "$OUT"
