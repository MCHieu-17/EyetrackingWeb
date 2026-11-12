#!/usr/bin/env bash
# =====================================================================
# create_admin_reader_role.sh — tạo/cập nhật DB role chỉ đọc cho trang
# Truy vấn CSDL của admin.
#
# Role chỉ được:
#   - SELECT trên bảng/view public;
#   - đọc các cột an toàn của users (không password_hash);
#   - KHÔNG đọc auth_sessions/user_identities;
#   - KHÔNG có quyền ghi/DDL.
#
# Bình thường KHÔNG cần chạy tay: `db/migrate.sh` (service `migrate`) tự gọi
# `db/admin_reader_role.sql` sau mỗi lần áp migrations nếu có
# ADMIN_DB_USER + ADMIN_DB_PASSWORD. Script này giữ lại cho trường hợp muốn
# cấp lại quyền/đổi password ngay mà không chạy migration.
#
#   ./scripts/create_admin_reader_role.sh
#   POSTGRES_DB_OVERRIDE=eyelearning_refactor_test ./scripts/create_admin_reader_role.sh
#
# Idempotent: kiểm tra role tồn tại trước khi ALTER; revoke toàn bộ quyền cũ
# trên schema public rồi grant lại đúng phạm vi.
# =====================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DB_NAME="${POSTGRES_DB_OVERRIDE:-}"
set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a
DB_NAME="${DB_NAME:-$POSTGRES_DB}"

: "${POSTGRES_USER:?thiếu POSTGRES_USER}"
: "${DB_NAME:?thiếu database đích}"
: "${ADMIN_DB_USER:?thiếu ADMIN_DB_USER}"
: "${ADMIN_DB_PASSWORD:?thiếu ADMIN_DB_PASSWORD}"

docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$DB_NAME" \
  -v ON_ERROR_STOP=1 \
  -v admin_role="$ADMIN_DB_USER" \
  -v admin_password="$ADMIN_DB_PASSWORD" \
  -v dbname="$DB_NAME" \
  -f - < "$ROOT_DIR/db/admin_reader_role.sql"

echo "OK: role ${ADMIN_DB_USER} đã sẵn sàng trên ${DB_NAME} (chỉ đọc)."
