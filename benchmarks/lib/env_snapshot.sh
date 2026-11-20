#!/usr/bin/env bash
# Ghi snapshot môi trường vào <run-dir>/env/. Không ghi secret.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_DIR="${1:?usage: env_snapshot.sh <run-dir>}"
OUT="$RUN_DIR/env"
mkdir -p "$OUT"
cd "$ROOT_DIR"

{
  date -u +'%Y-%m-%dT%H:%M:%SZ'
  uname -a
  printf '\n--- CPU ---\n'
  lscpu
  printf '\n--- scaling governor ---\n'
  cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null || true
} > "$OUT/cpu.txt" 2>&1

{
  free -h
  printf '\n--- meminfo ---\n'
  grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree|Dirty|Writeback):' /proc/meminfo
} > "$OUT/mem.txt"

{
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi -q
  else
    echo 'nvidia-smi not available'
  fi
} > "$OUT/gpu.txt" 2>&1

{
  docker version
  printf '\n--- compose ---\n'
  docker compose version
  printf '\n--- images ---\n'
  docker compose -p "${BENCH_PROJECT:-eyelearning-bench}" \
    --env-file "$ROOT_DIR/.env" \
    -f "$ROOT_DIR/docker-compose.yml" \
    -f "$ROOT_DIR/benchmarks/stack/docker-compose.bench.yml" images 2>/dev/null || true
  printf '\n--- disk ---\n'
  df -h
} > "$OUT/docker.txt" 2>&1

{
  git rev-parse HEAD 2>/dev/null || echo unknown
  git branch --show-current 2>/dev/null || echo unknown
  git status --porcelain 2>/dev/null || true
} > "$OUT/git.txt"

# Chỉ ghi tên + giá trị của các biến cấu hình quan trọng, che secret.
python3 - "$ROOT_DIR/.env" "$OUT/env.txt" <<'PY'
import re, sys
from pathlib import Path
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
keys = {
    "POSTGRES_DB", "GAZE_FPS", "DEVICE", "UNIGAZE_MODEL",
    "INFERENCE_PRECISION", "WEB_CONCURRENCY", "DB_POOL_MIN", "DB_POOL_MAX",
    "DB_POOL_TIMEOUT", "DB_STATEMENT_TIMEOUT_MS", "WORKER_REPLICAS",
    "GAZE_REPLICAS", "FRONTEND_REPLICAS", "CONTENT_VIEW_MIN_DWELL_MS",
    "EMBEDDING_NAME", "EMBEDDING_DIM", "EMBEDDING_DEVICE",
    "EMBEDDING_LOCAL_FILES_ONLY", "EMBEDDING_MODEL_PATH", "LLM_MODEL",
    "VLM_MODEL", "LLM_ENABLE_THINKING", "ANSWER_MAX_TOKENS",
    "RAG_TOP_K", "RAG_BM25_CANDIDATES", "RAG_DENSE_CANDIDATES",
    "RAG_HYDE_CANDIDATES", "CHATBOT_MAX_CONCURRENT",
    "LLM_GENERATION_CONCURRENCY", "LLM_TOTAL_CONCURRENCY",
    "VLM_INGEST_CONCURRENCY", "CHATBOT_INGEST_BATCH_SIZE",
    "MAX_SLIDE_PAGES", "MAX_UPLOAD_BYTES",
}
secret_words = ("SECRET", "PASSWORD", "TOKEN", "KEY", "PASS")
out = []
for line in src.read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    if key not in keys:
        continue
    if any(word in key.upper() for word in secret_words):
        value = "<redacted>"
    out.append(f"{key}={value}")
dst.write_text("\n".join(out) + "\n", encoding="utf-8")
PY

python3 - "$ROOT_DIR" "$OUT/../meta.json" <<'PY'
import json, os, platform, subprocess, sys
from datetime import datetime, timezone
root, target = sys.argv[1], sys.argv[2]

def git(*args):
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""

meta = {
    "run_id": os.environ.get("BENCH_RUN_ID", ""),
    "created_at": datetime.now(timezone.utc).isoformat(),
    "profile": os.environ.get("BENCH_PROFILE", ""),
    "scale": os.environ.get("BENCH_SCALE", ""),
    "quick": os.environ.get("BENCH_QUICK", "0") == "1",
    "git": {
        "commit": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "dirty": bool(git("status", "--porcelain")),
    },
    "host": {
        "node": platform.node(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
    },
}
with open(target, "w", encoding="utf-8") as fh:
    json.dump(meta, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
PY

echo "$OUT"
