#!/usr/bin/env bash
# Tạo partition tháng cho gaze_samples.
#
# Không xoá partition cũ. Chạy định kỳ (hoặc trước khi sang tháng mới) để dữ
# liệu mới rơi đúng partition tháng thay vì vào default partition.
#
#   ./scripts/create_partitions.sh          # tạo thêm 3 tháng
#   ./scripts/create_partitions.sh 12       # tạo thêm 12 tháng
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

MONTHS_AHEAD="${1:-3}"

docker compose exec -T postgres psql \
  -U "${POSTGRES_USER:-postgres}" \
  -d "${POSTGRES_DB:-eyetracking}" \
  -v ON_ERROR_STOP=1 \
  -c "SELECT create_gaze_sample_partitions(${MONTHS_AHEAD});"
