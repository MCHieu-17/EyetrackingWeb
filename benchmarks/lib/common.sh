#!/usr/bin/env bash
# Helpers dùng chung cho benchmark harness.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BENCH_DIR="$ROOT_DIR/benchmarks"
PROJECT="${BENCH_PROJECT:-eyelearning-bench}"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
OVERRIDE_FILE="$BENCH_DIR/stack/docker-compose.bench.yml"

compose() {
  docker compose -p "$PROJECT" --env-file "$ROOT_DIR/.env" \
    -f "$COMPOSE_FILE" -f "$OVERRIDE_FILE" "$@"
}

bench_path() {
  local path="$1"
  case "$path" in
    /bench/*) printf '%s' "$path"; return 0 ;;
  esac
  case "$path" in
    /*) ;;
    *) path="$ROOT_DIR/$path" ;;
  esac
  printf '/bench/%s' "${path#"$ROOT_DIR/benchmarks/"}"
}

log() { printf '[bench] %s\n' "$*"; }
warn() { printf '[bench][warn] %s\n' "$*" >&2; }
die() { printf '[bench][error] %s\n' "$*" >&2; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Thiếu lệnh: $1"
}

require_file() {
  [ -f "$1" ] || die "Thiếu file: $1"
}

wait_url() {
  local url="$1" timeout="${2:-180}" started
  started="$(date +%s)"
  while true; do
    if curl -fsS --max-time 3 "$url" >/dev/null 2>&1; then
      return 0
    fi
    if [ $(( $(date +%s) - started )) -ge "$timeout" ]; then
      die "Timeout chờ $url sau ${timeout}s"
    fi
    sleep 2
  done
}

json_get() {
  # json_get <file> <python expression trên object 'd'>
  python3 - "$1" "$2" <<'PY'
import json, sys
path, expr = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as fh:
    d = json.load(fh)
value = eval(expr, {"__builtins__": {}}, {"d": d})
print(value)
PY
}
