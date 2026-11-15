#!/usr/bin/env bash
# Benchmark nhanh một endpoint HTTP (P4 query/bench harness).
#
#   ./scripts/bench.sh [BASE_URL] [PATH]
#
# Ví dụ:
#   ./scripts/bench.sh
#   ./scripts/bench.sh http://localhost:8001 /health
#   AUTH_HEADER="Authorization: Bearer $TOKEN" \
#       ./scripts/bench.sh http://localhost:8001 /teacher/courses
#
# Mặc định base URL http://localhost:8001 và path /health.
# Script KHÔNG yêu cầu auth; endpoint cần auth thì truyền AUTH_HEADER.
# Có thể chỉnh REQUESTS (mặc định 200), CONCURRENCY (10), WARMUP_REQUESTS (20).
#
# Lưu ý: backend không có prefix /api cho route teacher; qua nginx public path
# là /api/teacher/... nhưng gọi thẳng backend (8001) phải dùng /teacher/...
set -euo pipefail

BASE_URL="${1:-http://localhost:8001}"
ENDPOINT="${2:-/health}"
URL="${BASE_URL%/}/${ENDPOINT#/}"
REQUESTS="${REQUESTS:-200}"
CONCURRENCY="${CONCURRENCY:-10}"
WARMUP_REQUESTS="${WARMUP_REQUESTS:-20}"
AUTH_HEADER="${AUTH_HEADER:-}"

log() { printf '[bench] %s\n' "$*"; }

if ! command -v hey >/dev/null 2>&1 && ! command -v wrk >/dev/null 2>&1; then
    log "Không tìm thấy 'hey' hoặc 'wrk' — bỏ qua benchmark (exit 0)."
    log "Cài một trong hai rồi chạy lại:"
    log "  hey: https://github.com/rakyll/hey"
    log "  wrk: https://github.com/wg/wrk"
    exit 0
fi

log "URL: $URL"
log "warm-up: $WARMUP_REQUESTS requests, concurrency $CONCURRENCY"
log "measured: $REQUESTS requests, concurrency $CONCURRENCY"

if command -v hey >/dev/null 2>&1; then
    HEY_WARMUP=(-n "$WARMUP_REQUESTS" -c "$CONCURRENCY")
    HEY_MEASURED=(-n "$REQUESTS" -c "$CONCURRENCY")
    if [ -n "$AUTH_HEADER" ]; then
        HEY_WARMUP+=(-H "$AUTH_HEADER")
        HEY_MEASURED+=(-H "$AUTH_HEADER")
    fi

    hey "${HEY_WARMUP[@]}" "$URL" >/dev/null
    OUTPUT="$(hey "${HEY_MEASURED[@]}" "$URL")"
    printf '%s\n' "$OUTPUT"

    P95="$(printf '%s\n' "$OUTPUT" | awk '/^[[:space:]]*95%/ {print $3; exit}')"
    if [ -n "$P95" ]; then
        log "p95: ${P95}s"
    else
        log "Không đọc được p95 từ output của hey."
    fi
    exit 0
fi

# wrk fallback. wrk chỉ in 50/75/90/99%, không in p95 trực tiếp.
WRK_WARMUP=(-t "$CONCURRENCY" -c "$CONCURRENCY" -d "${WARMUP_DURATION:-2s}")
WRK_MEASURED=(
    -t "$CONCURRENCY"
    -c "$CONCURRENCY"
    -d "${DURATION:-10s}"
    --latency
)
if [ -n "$AUTH_HEADER" ]; then
    WRK_WARMUP+=(-H "$AUTH_HEADER")
    WRK_MEASURED+=(-H "$AUTH_HEADER")
fi

wrk "${WRK_WARMUP[@]}" "$URL" >/dev/null
OUTPUT="$(wrk "${WRK_MEASURED[@]}" "$URL")"
printf '%s\n' "$OUTPUT"

P90="$(printf '%s\n' "$OUTPUT" | awk '/^[[:space:]]*90%/ {print $2; exit}')"
P99="$(printf '%s\n' "$OUTPUT" | awk '/^[[:space:]]*99%/ {print $2; exit}')"
log "wrk không báo p95 trực tiếp; p90=${P90:-?}, p99=${P99:-?}"
