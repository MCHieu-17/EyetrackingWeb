#!/usr/bin/env bash
# Tạo partition tháng cho gaze_events + gaze_raw_samples.
#
# Không xoá partition cũ. Chạy định kỳ (hoặc trước khi sang tháng mới) để dữ
# liệu mới rơi đúng partition tháng thay vì vào default partition.
#
#   ./scripts/create_partitions.sh          # tạo thêm 12 tháng
#   ./scripts/create_partitions.sh 24       # tạo thêm 24 tháng
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

MONTHS_AHEAD="${1:-12}"

docker compose exec -T postgres psql \
  -U "${POSTGRES_USER:-postgres}" \
  -d "${POSTGRES_DB:-eyetracking}" \
  -v ON_ERROR_STOP=1 \
  -c "SELECT create_gaze_partitions(${MONTHS_AHEAD});" \
  -c "SELECT create_gaze_raw_partitions(${MONTHS_AHEAD});"
