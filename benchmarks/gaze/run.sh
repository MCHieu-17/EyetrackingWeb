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

log "Gaze WS load (sessions=$sessions duration=$duration)"
compose exec -T --user root gaze python /bench/gaze/ws_load.py \
  --url http://127.0.0.1:8000 \
  --image /fixtures/face_sample.jpg \
  --sessions "$sessions" --fps 15 --duration "$duration" \
  --out "$(bench_path "$OUT/ws-load.json")"

echo "$OUT"
