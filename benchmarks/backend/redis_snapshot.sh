#!/usr/bin/env bash
# Snapshot Redis: INFO stats/commandstats/memory, slowlog, latency.
#   benchmarks/backend/redis_snapshot.sh <run-dir> before
#   benchmarks/backend/redis_snapshot.sh <run-dir> after
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/benchmarks/lib/common.sh"

RUN_DIR="${1:?usage: redis_snapshot.sh <run-dir> <before|after>}"
LABEL="${2:-after}"
OUT="$RUN_DIR/backend/redis"
mkdir -p "$OUT"

redis() {
  compose exec -T redis redis-cli "$@"
}

redis INFO > "$OUT/${LABEL}_info.txt"
redis INFO commandstats > "$OUT/${LABEL}_commandstats.txt"
redis INFO memory > "$OUT/${LABEL}_memory.txt"
redis SLOWLOG GET 25 > "$OUT/${LABEL}_slowlog.txt" || true
redis --latency-history -i 1 > "$OUT/${LABEL}_latency.txt" &
PID=$!
sleep 10
kill "$PID" 2>/dev/null || true
wait "$PID" 2>/dev/null || true

python3 - "$OUT/${LABEL}_info.txt" "$OUT/${LABEL}_commandstats.txt" \
  "$OUT/${LABEL}_summary.json" <<'PY'
import json, sys
from pathlib import Path

def parse(path):
    out = {}
    for line in Path(path).read_text(errors="replace").splitlines():
        if ":" not in line or line.startswith("#"):
            continue
        key, value = line.split(":", 1)
        out[key] = value.strip()
    return out

stats = parse(sys.argv[1])
cmds = parse(sys.argv[2])
hits = int(stats.get("keyspace_hits", 0))
misses = int(stats.get("keyspace_misses", 0))
total = hits + misses
summary = {
    "keyspace_hits": hits,
    "keyspace_misses": misses,
    "hit_rate": round(hits / total, 6) if total else None,
    "used_memory_human": stats.get("used_memory_human"),
    "used_memory_peak_human": stats.get("used_memory_peak_human"),
    "evicted_keys": int(stats.get("evicted_keys", 0)),
    "expired_keys": int(stats.get("expired_keys", 0)),
    "total_commands_processed": int(stats.get("total_commands_processed", 0)),
    "instantaneous_ops_per_sec": int(stats.get("instantaneous_ops_per_sec", 0)),
    "commandstats": {
        key.removeprefix("cmdstat_"): value
        for key, value in cmds.items()
        if key.startswith("cmdstat_")
    },
}
Path(sys.argv[3]).write_text(json.dumps(summary, indent=2) + "\n")
PY

echo "$OUT/${LABEL}_summary.json"
