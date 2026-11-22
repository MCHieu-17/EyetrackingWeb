#!/usr/bin/env bash
# Build frontend production và đo bundle. Lighthouse chạy riêng vì cần service up.
#   benchmarks/frontend/run.sh <run-dir> <fixtures> <tokens>
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/benchmarks/lib/common.sh"

RUN_DIR="${1:?usage: run.sh <run-dir> <fixtures> <tokens>}"
FIXTURES="${2:?}"
TOKENS="${3:?}"
OUT="$RUN_DIR/frontend"
mkdir -p "$OUT"

IMAGE="${BENCH_FRONTEND_BUILDER_IMAGE:-eye-learning-frontend-builder:bench}"
log "Build frontend builder image $IMAGE"
docker build -f "$ROOT_DIR/frontend/Dockerfile" --target builder \
  -t "$IMAGE" "$ROOT_DIR/frontend"

container="bench-fe-builder-$$"
docker create --name "$container" "$IMAGE" >/dev/null
rm -rf "$OUT/.next"
docker cp "$container:/app/.next" "$OUT/.next"
docker rm "$container" >/dev/null

node "$ROOT_DIR/benchmarks/frontend/bundle-size.mjs" \
  --next-dir "$OUT/.next" \
  --out "$OUT/bundle-size.json" \
  --md "$OUT/bundle-size.md"

log "Gaze capture client (worker vs main thread)"
(
  cd "$ROOT_DIR/frontend"
  node "$ROOT_DIR/benchmarks/frontend/gaze-capture.mjs" \
    --out "$OUT/gaze-capture.json"
) || warn "gaze capture benchmark fail — xem gaze-capture.json"

if command -v lighthouse >/dev/null 2>&1; then
  "$ROOT_DIR/benchmarks/frontend/lighthouse.sh" "$RUN_DIR" "$FIXTURES" "$TOKENS"
else
  warn "Thiếu lighthouse; bỏ qua Lighthouse. Cài: npm i -g lighthouse"
fi

echo "$OUT"
