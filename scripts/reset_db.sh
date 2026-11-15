#!/usr/bin/env bash
# Reset database development có guard.
#
# Mặc định là PREVIEW — chỉ đọc và in kế hoạch, không stop/drop/seed:
#   ./scripts/reset_db.sh
#
# Áp dụng thật (bắt buộc đủ 2 tham số trùng nhau):
#   ./scripts/reset_db.sh --apply --database eyetracking --confirm-reset eyetracking
#
# Logic guard nằm ở scripts/reset_db.py (dễ test bằng process adapter giả lập).
# Không dùng `docker compose down -v`, không xóa volume, không đụng database khác.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

exec python3 "$ROOT_DIR/scripts/reset_db.py" "$@"
