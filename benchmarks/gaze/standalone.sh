#!/usr/bin/env bash
# Benchmark gaze trên MỘT container riêng (không cần cả stack bench), cùng điều
# kiện production: 2 CPU, GPU, weights từ volume dev. Dùng để so sánh hai image.
#
#   benchmarks/gaze/standalone.sh <image> <out-dir> [quick|full] [testdata-dir]
#
# Kết quả: stage-latency.json, ws-load.json, accuracy.json (nếu có testdata),
# image-size.txt, startup.txt.
#
# Mặc định TESTDATA là benchmarks/gaze/testdata (gitignored, ảnh mặt thật).
# Script đo nằm ở benchmarks/gaze/tools/ và được mount vào /bench khi chạy.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE="${1:?usage: standalone.sh <image> <out-dir> [quick|full] [testdata-dir]}"
OUT="${2:?usage: standalone.sh <image> <out-dir> [quick|full] [testdata-dir]}"
QUICK="${3:-full}"
TESTDATA="${4:-$ROOT_DIR/benchmarks/gaze/testdata}"
[ -d "$TESTDATA" ] || TESTDATA=""
NAME="gaze-standalone-$$"
WEIGHTS_VOLUME="${GAZE_WEIGHTS_VOLUME:-eyelearning_gaze-weights}"
CPUS="${GAZE_BENCH_CPUS:-2}"
CPU_WORKERS="${GAZE_CPU_WORKERS:-2}"

mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"

iterations=200
warmup=20
sessions="1,4,8,12"
duration=30
if [ "$QUICK" = "quick" ]; then
  iterations=50
  warmup=10
  sessions="1,4,8"
  duration=10
fi

ENV_ARGS=(
  -e DEVICE=cuda -e UNIGAZE_MODEL=unigaze_b16_joint
  -e INFERENCE_PRECISION="${INFERENCE_PRECISION:-fp16}"
  -e GPU_BATCH=8 -e GAZE_FPS=15 -e CPU_WORKERS="$CPU_WORKERS"
  -e OMP_NUM_THREADS=1 -e MKL_NUM_THREADS=1 -e OPENBLAS_NUM_THREADS=1
  -e HF_HUB_OFFLINE=1
)
MOUNTS=(
  -v "$WEIGHTS_VOLUME":/app/weights
  -v "$ROOT_DIR/benchmarks":/bench:rw
  -v "$ROOT_DIR/services/gaze/tests/fixtures":/fixtures:ro
  -v "$OUT":/out
)

docker image inspect "$IMAGE" --format '{{.Size}}' >"$OUT/image-size.txt"
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT

echo "[gaze-bench] stage latency ($IMAGE)"
docker run --rm --gpus all --cpus "$CPUS" --user root --entrypoint python \
  "${ENV_ARGS[@]}" "${MOUNTS[@]}" "$IMAGE" /bench/gaze/stage_latency.py \
  --image /fixtures/face_sample.jpg --widths 480,720 \
  --iterations "$iterations" --warmup "$warmup" \
  --out /out/stage-latency.json >/dev/null

if [ -n "$TESTDATA" ]; then
  echo "[gaze-bench] accuracy ($TESTDATA)"
  docker run --rm --gpus all --cpus "$CPUS" --user root --entrypoint python \
    "${ENV_ARGS[@]}" "${MOUNTS[@]}" -v "$TESTDATA":/data:ro "$IMAGE" \
    /bench/gaze/tools/eval_offline.py --data "/data/$(basename "$(ls -d "$TESTDATA"/*/ | head -1)")" \
    --out /out/accuracy.json --frames-out /out/accuracy.frames.json \
    >/dev/null
fi

echo "[gaze-bench] server + ws load"
started="$(date +%s.%N)"
docker run -d --name "$NAME" --gpus all --cpus "$CPUS" --user root --entrypoint python \
  "${ENV_ARGS[@]}" "${MOUNTS[@]}" "$IMAGE" -m uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 --ws-max-size 1048576 >/dev/null
until docker exec "$NAME" python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/ready').status==200 else 1)" >/dev/null 2>&1; do
  if ! docker ps -q --filter "name=$NAME" | grep -q .; then
    docker logs "$NAME" 2>&1 | tail -30 >&2
    echo "container thoát sớm" >&2
    exit 1
  fi
  sleep 0.5
done
ready="$(date +%s.%N)"
python3 -c "print('cold_start_to_ready_s=%.1f' % ($ready - $started))" >"$OUT/startup.txt"
nvidia-smi --query-gpu=memory.used --format=csv,noheader >>"$OUT/startup.txt" 2>/dev/null || true

docker exec "$NAME" python /bench/gaze/ws_load.py \
  --url http://127.0.0.1:8000 --image /fixtures/face_sample.jpg \
  --width 480 --quality 0.78 \
  --sessions "$sessions" --fps 15 --duration "$duration" \
  --out /out/ws-load.json >/dev/null
nvidia-smi --query-gpu=memory.used --format=csv,noheader >>"$OUT/startup.txt" 2>/dev/null || true
echo "[gaze-bench] xong: $OUT"
