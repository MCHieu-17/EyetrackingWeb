#!/usr/bin/env bash
# Chạy benchmark baseline trên stack cô lập.
#
#   ./benchmarks/run_all.sh --quick --scale tiny
#   ./benchmarks/run_all.sh --scale baseline
#   ./benchmarks/run_all.sh --only backend,db --quick
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/benchmarks/lib/common.sh"

PROFILE="single"
SCALE="baseline"
QUICK=0
SKIP_BUILD=0
SKIP_SEED=0
KEEP=0
ONLY=""
RUN_ID=""
K6_IMAGE="${K6_IMAGE:-grafana/k6:0.57.0}"
LIGHTHOUSE_RUNS="${LIGHTHOUSE_RUNS:-3}"

usage() {
  sed -n '2,6p' "$0"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --scale) SCALE="$2"; shift 2 ;;
    --quick) QUICK=1; shift ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    --skip-seed) SKIP_SEED=1; shift ;;
    --keep) KEEP=1; shift ;;
    --only) ONLY="$2"; shift 2 ;;
    --run-id) RUN_ID="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) die "Tham số không hợp lệ: $1" ;;
  esac
done

case "$SCALE" in tiny|baseline|stress) ;; *) die "Scale phải là tiny|baseline|stress" ;; esac
case "$PROFILE" in single|prod) ;; *) die "Profile phải là single|prod" ;; esac

if [ -z "$RUN_ID" ]; then
  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-${SCALE}"
fi
RUN_DIR="$BENCH_DIR/baseline/$RUN_ID"
mkdir -p "$RUN_DIR/backend/k6" "$RUN_DIR/backend/explain" \
  "$RUN_DIR/backend/pg_stat_statements" "$RUN_DIR/backend/redis" \
  "$RUN_DIR/frontend/lighthouse" "$RUN_DIR/gaze" "$RUN_DIR/chatbot"
ln -sfn "$RUN_ID" "$BENCH_DIR/baseline/latest"
export BENCH_RUN_ID="$RUN_ID"
export BENCH_PROFILE="$PROFILE"
export BENCH_SCALE="$SCALE"
export BENCH_QUICK="$QUICK"

if [ "$PROFILE" = "prod" ]; then
  export WORKER_REPLICAS="${WORKER_REPLICAS:-2}"
  export GAZE_REPLICAS="${GAZE_REPLICAS:-2}"
  export FRONTEND_REPLICAS="${FRONTEND_REPLICAS:-2}"
else
  export WORKER_REPLICAS=1
  export GAZE_REPLICAS=1
  export FRONTEND_REPLICAS=1
fi

log "run_id=$RUN_ID profile=$PROFILE scale=$SCALE quick=$QUICK"
"$ROOT_DIR/benchmarks/lib/env_snapshot.sh" "$RUN_DIR" >/dev/null

want() {
  [ -z "$ONLY" ] && return 0
  case ",$ONLY," in *",$1,"*) return 0 ;; *) return 1 ;; esac
}

need_up=0
for stage in up fixtures seed tokens backend db frontend gaze chatbot; do
  if want "$stage"; then need_up=1; fi
done

if want up || { [ -n "$ONLY" ] && [ "$need_up" -eq 1 ]; }; then
  if [ "$SKIP_BUILD" -eq 1 ]; then
    log "compose up -d (không build)"
    compose up -d
  else
    log "compose up -d --build (production images)"
    compose up -d --build
  fi
  wait_url "http://127.0.0.1:8101/health" 240
  wait_url "http://127.0.0.1:3100/nginx-health" 120
  wait_url "http://127.0.0.1:8102/ready" 300
  wait_url "http://127.0.0.1:3100/gaze/ready" 300
  log "stack ready"
fi

if want fixtures; then
  log "sinh fixture PDF"
  compose exec -T --user root chatbot python /bench/lib/gen_fixtures.py \
    --out /bench/fixtures/lecture_20p.pdf \
    --meta /bench/fixtures/lecture_20p.meta.json \
    --pages "${BENCH_FIXTURE_PAGES:-20}"
fi

if want seed && [ "$SKIP_SEED" -eq 0 ]; then
  log "seed dataset ($SCALE)"
  compose exec -T --user root backend python /bench/lib/seed_bench.py \
    --scale "$SCALE" \
    --fixtures-dir /bench/fixtures \
    --ingest-slides "${BENCH_INGEST_SLIDES:-20}" \
    --out "$(bench_path "$RUN_DIR/fixtures.json")"
fi

if want tokens; then
  log "sinh access token benchmark"
  compose exec -T --user root backend python /bench/lib/make_tokens.py \
    --fixtures "$(bench_path "$RUN_DIR/fixtures.json")" \
    --out "$(bench_path "$RUN_DIR/.runtime/tokens.json")"
fi

run_k6() {
  local scenario="$1" vus="$2" duration="$3" iterations="${4:-0}"
  local label="${5:-$scenario}"
  local base_url="${6:-http://127.0.0.1:8101}"
  local slug="${label//\//_}"
  local prefix="/bench/baseline/$RUN_ID/backend/k6/$slug"
  local args=(
    --rm --network host --user 0:0 -v "$BENCH_DIR:/bench"
    -e "BASE_URL=$base_url"
    -e "TOKEN_FILE=/bench/baseline/$RUN_ID/.runtime/tokens.json"
    -e "FIXTURES=/bench/baseline/$RUN_ID/fixtures.json"
    -e "SCENARIO=$scenario"
    -e "VUS=$vus"
    -e "DURATION=$duration"
    -e "ITERATIONS=$iterations"
    -e "OUT_PREFIX=$prefix"
    -e "LOGIN_EMAIL=bench-teacher@example.test"
    -e "LOGIN_PASSWORD=Password123!"
  )
  log "k6 $label vus=$vus duration=$duration iterations=$iterations"
  docker run "${args[@]}" "$K6_IMAGE" run --quiet --no-color /bench/backend/k6/api.js || warn "k6 $scenario lỗi"
}

run_backend() {
  if ! docker image inspect "$K6_IMAGE" >/dev/null 2>&1; then
    warn "Chưa có image $K6_IMAGE; thử pull..."
    docker pull "$K6_IMAGE" >/dev/null || die "Không pull được $K6_IMAGE"
  fi

  local duration="30s"
  local read_vus=20 heavy_vus=5 write_vus=10
  if [ "$QUICK" -eq 1 ]; then
    duration="10s"; read_vus=5; heavy_vus=2; write_vus=3
  fi

  if [ "$QUICK" -eq 1 ]; then
    local scenarios="enrollments outline lesson_contents session_contents teacher_courses course_students course_visits aoi_summary replay samples"
  else
    local scenarios="enrollments outline lesson_contents session_contents teacher_courses teacher_tree course_students course_visits visit_summary replay samples aoi_summary heatmap export_visit export_lesson publish quiz login health"
  fi

  # Xoá summary cũ để lần chạy lại không trộn số liệu.
  rm -f "$RUN_DIR"/backend/k6/*.summary.json "$RUN_DIR"/backend/k6/*.summary.md
  "$ROOT_DIR/benchmarks/backend/collect_pg.sh" "$RUN_DIR" before >/dev/null || true
  "$ROOT_DIR/benchmarks/backend/redis_snapshot.sh" "$RUN_DIR" before >/dev/null || true

  for scenario in $scenarios; do
    case "$scenario" in
      aoi_summary|replay|export_visit|export_lesson|publish|teacher_courses)
        run_k6 "$scenario" "$heavy_vus" "$duration" 0 ;;
      *)
        run_k6 "$scenario" "$read_vus" "$duration" 0 ;;
    esac
  done

  # Auth memory-hit: 1 VU để đo p95 end-to-end; probe riêng đo dependency auth.
  run_k6 me 1 "10s" 0 "auth-me"
  compose exec -T --user root backend python /bench/backend/auth_probe.py \
    --fixtures "$(bench_path "$RUN_DIR/fixtures.json")" \
    --iterations 500 \
    --out "$(bench_path "$RUN_DIR/backend/auth_probe.json")"
  # Add 200 học viên: request đầu là cold batch (INSERT + một pipeline UNLINK).
  run_k6 add_students 1 "10s" 10 "add-students"

  # Query-count probe: 1 VU, 20 iteration, reset stats từng scenario.
  for scenario in enrollments outline teacher_courses course_students course_visits aoi_summary replay samples session_contents; do
    "$ROOT_DIR/benchmarks/backend/collect_pg.sh" "$RUN_DIR" reset >/dev/null || true
    run_k6 "$scenario" 1 "1s" 20 "qcount-$scenario"
    "$ROOT_DIR/benchmarks/backend/collect_pg.sh" "$RUN_DIR" "query-$scenario" >/dev/null || true
  done

  # Gaze batch write load.
  local gaze_vus=25
  [ "$QUICK" -eq 1 ] && gaze_vus=8
  log "k6 gaze batch vus=$gaze_vus samples=40"
  docker run --rm --network host --user 0:0 -v "$BENCH_DIR:/bench" \
    -e "BASE_URL=http://127.0.0.1:8101" \
    -e "TOKEN_FILE=/bench/baseline/$RUN_ID/.runtime/tokens.json" \
    -e "FIXTURES=/bench/baseline/$RUN_ID/fixtures.json" \
    -e "VUS=$gaze_vus" -e "DURATION=$duration" -e "SAMPLES=40" \
    -e "OUT_PREFIX=/bench/baseline/$RUN_ID/backend/k6/gaze_batch" \
    "$K6_IMAGE" run --quiet --no-color /bench/backend/k6/gaze_batch.js || warn "k6 gaze batch lỗi"

  # Gate Phase 9: 30 HS sau NAT, 1 batch/1,5 s, qua nginx :3100.
  log "k6 gaze batch qua nginx vus=30 batch/1.5s"
  docker run --rm --network host --user 0:0 -v "$BENCH_DIR:/bench" \
    -e "BASE_URL=http://127.0.0.1:3100" \
    -e "TOKEN_FILE=/bench/baseline/$RUN_ID/.runtime/tokens.json" \
    -e "FIXTURES=/bench/baseline/$RUN_ID/fixtures.json" \
    -e "VUS=30" -e "DURATION=$duration" -e "SAMPLES=40" \
    -e "BATCH_PER_SECOND=0.666" -e "AFFINITY=1" \
    -e "OUT_PREFIX=/bench/baseline/$RUN_ID/backend/k6/gaze_batch_nginx" \
    "$K6_IMAGE" run --quiet --no-color /bench/backend/k6/gaze_batch.js \
    || warn "k6 gaze batch qua nginx lỗi"

  "$ROOT_DIR/benchmarks/backend/redis_snapshot.sh" "$RUN_DIR" after >/dev/null || true
  "$ROOT_DIR/benchmarks/backend/collect_pg.sh" "$RUN_DIR" after >/dev/null || true
  "$ROOT_DIR/benchmarks/backend/run_explain.sh" "$RUN_DIR" "$RUN_DIR/fixtures.json" >/dev/null || true
}

if want backend; then
  run_backend
fi

if want db && ! want backend; then
  "$ROOT_DIR/benchmarks/backend/collect_pg.sh" "$RUN_DIR" before >/dev/null || true
  "$ROOT_DIR/benchmarks/backend/redis_snapshot.sh" "$RUN_DIR" before >/dev/null || true
  "$ROOT_DIR/benchmarks/backend/run_explain.sh" "$RUN_DIR" "$RUN_DIR/fixtures.json" >/dev/null || true
  "$ROOT_DIR/benchmarks/backend/redis_snapshot.sh" "$RUN_DIR" after >/dev/null || true
  "$ROOT_DIR/benchmarks/backend/collect_pg.sh" "$RUN_DIR" after >/dev/null || true
fi

if want frontend; then
  LIGHTHOUSE_RUNS="$([ "$QUICK" -eq 1 ] && echo 1 || echo "$LIGHTHOUSE_RUNS")" \
    "$ROOT_DIR/benchmarks/frontend/run.sh" "$RUN_DIR" "$RUN_DIR/fixtures.json" "$RUN_DIR/.runtime/tokens.json"
fi

if want gaze; then
  "$ROOT_DIR/benchmarks/gaze/run.sh" "$RUN_DIR" "$([ "$QUICK" -eq 1 ] && echo quick || echo full)"
fi

if want chatbot; then
  "$ROOT_DIR/benchmarks/chatbot/run.sh" "$RUN_DIR" "$RUN_DIR/fixtures.json" "$RUN_DIR/.runtime/tokens.json" \
    "$([ "$QUICK" -eq 1 ] && echo quick || echo full)"
fi

if want report; then
  python3 "$ROOT_DIR/benchmarks/report/summarize.py" --run-dir "$RUN_DIR"
fi

if [ "$KEEP" -eq 0 ] && [ "$need_up" -eq 1 ]; then
  log "dừng stack benchmark (volume giữ nguyên)"
  compose down
fi

log "xong: $RUN_DIR"
