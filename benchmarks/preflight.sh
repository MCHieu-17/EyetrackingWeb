#!/usr/bin/env bash
# Kiểm tra môi trường trước khi chạy benchmark. Không khởi động stack.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# shellcheck disable=SC1091
source "$ROOT_DIR/benchmarks/lib/common.sh"

log "Kiểm tra file cấu hình"
require_file "$ROOT_DIR/.env"
require_file "$ROOT_DIR/docker-compose.yml"
require_file "$OVERRIDE_FILE"

log "Kiểm tra lệnh"
require_cmd docker
docker compose version >/dev/null
require_cmd curl
require_cmd git
require_cmd python3
if ! command -v jq >/dev/null 2>&1; then
  warn "Thiếu jq; một số script frontend/Lighthouse có thể cần jq."
fi

if command -v k6 >/dev/null 2>&1; then
  log "k6: $(k6 version 2>/dev/null | head -1)"
else
  warn "Không có k6 trên host; run_all sẽ dùng Docker image K6_IMAGE."
fi

if command -v lighthouse >/dev/null 2>&1; then
  log "lighthouse: $(lighthouse --version 2>/dev/null | head -1)"
else
  warn "Không có lighthouse; nhóm frontend/Lighthouse sẽ bị skip."
fi

log "Kiểm tra compose benchmark"
compose config >/dev/null

log "Phần cứng"
printf '  CPU: %s\n' "$(nproc) core"
printf '  RAM: %s\n' "$(free -h | awk '/^Mem:/{print $2}')"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total,driver_version \
    --format=csv,noheader 2>/dev/null | sed 's/^/  GPU: /' || true
else
  warn "Không thấy nvidia-smi; gaze sẽ chạy CPU hoặc không đo được."
fi

log "Git"
printf '  branch: %s\n' "$(git branch --show-current 2>/dev/null || echo '-')"
printf '  commit: %s\n' "$(git rev-parse --short HEAD 2>/dev/null || echo '-')"
if [ -n "$(git status --porcelain 2>/dev/null || true)" ]; then
  warn "Working tree có thay đổi; baseline sẽ ghi dirty=true."
fi

log "OK. Chạy: ./benchmarks/run_all.sh --quick --scale tiny"
