#!/usr/bin/env bash
# Chạy stage latency + WS load trong container gaze.
#   benchmarks/gaze/run.sh <run-dir> [quick]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/benchmarks/lib/common.sh"

RUN_DIR="${1:?usage: run.sh <run-dir> [quick]}"
QUICK="${2:-}"
OUT="$RUN_DIR/gaze"
mkdir -p "$OUT"

iterations=200
warmup=20
sessions="1,4,8,12,16"
duration=30
if [ "$QUICK" = "quick" ]; then
  iterations=50
  warmup=10
  sessions="1,4,8"
  duration=10
fi

log "Gaze stage latency (iterations=$iterations)"
compose exec -T --user root gaze python /bench/gaze/stage_latency.py \
  --image /fixtures/face_sample.jpg \
  --widths 480,720,1080 \
  --iterations "$iterations" --warmup "$warmup" \
  --out "$(bench_path "$OUT/stage-latency.json")"

calib_args=()
if [ -n "${BENCH_GAZE_CALIBRATION:-}" ]; then
  calib_args=(--calibration "$BENCH_GAZE_CALIBRATION")
fi
log "Gaze capture A/B (480/q0.78 vs 320/q0.7, 480/q0.7)"
compose exec -T --user root gaze python /bench/gaze/tools/compare_capture.py \
  --dir /fixtures \
  --baseline 480:0.78 --variants 320:0.7,480:0.7 \
  "${calib_args[@]}" \
  --out "$(bench_path "$OUT/capture-ab.json")" \
  || warn "capture A/B fail — xem capture-ab.json"

log "Gaze WS load baseline payload (sessions=$sessions duration=$duration)"
compose exec -T --user root gaze python /bench/gaze/ws_load.py \
  --url http://127.0.0.1:8000 \
  --image /fixtures/face_sample.jpg \
  --sessions "$sessions" --fps 15 --duration "$duration" \
  --out "$(bench_path "$OUT/ws-load.json")"

log "Gaze WS load client payload 480px/q0.78 (sessions=$sessions duration=$duration)"
compose exec -T --user root gaze python /bench/gaze/ws_load.py \
  --url http://127.0.0.1:8000 \
  --image /fixtures/face_sample.jpg \
  --width 480 --quality 0.78 \
  --sessions "$sessions" --fps 15 --duration "$duration" \
  --out "$(bench_path "$OUT/ws-load-client.json")"

echo "$OUT"
