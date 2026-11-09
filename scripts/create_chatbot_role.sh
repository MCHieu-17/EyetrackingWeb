#!/usr/bin/env bash
# =====================================================================
# create_chatbot_role.sh — tạo/cập nhật DB role hạn chế cho chatbot.
#
# Chatbot chỉ được:
#   - đọc view công khai `v_chatbot_slide_documents`;
#   - đọc outline draft `v_course_outline` để index trước khi xuất bản;
#   - ghi `slide_documents` (ingest transcript/embedding).
# KHÔNG được đọc quiz_specs/quiz_attempts/users/chat_*.
#
# Bình thường KHÔNG cần chạy tay: `db/migrate.sh` (service `migrate`) tự gọi
# `db/chatbot_role.sql` sau mỗi lần áp migrations. Script này giữ lại cho
# trường hợp muốn cấp lại quyền/đổi password ngay mà không chạy migration.
#
#   ./scripts/create_chatbot_role.sh
#   POSTGRES_DB_OVERRIDE=eyelearning_refactor_test ./scripts/create_chatbot_role.sh
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
: "${CHATBOT_DB_USER:?thiếu CHATBOT_DB_USER}"
: "${CHATBOT_DB_PASSWORD:?thiếu CHATBOT_DB_PASSWORD}"

docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$DB_NAME" \
  -v ON_ERROR_STOP=1 \
  -v role="$CHATBOT_DB_USER" \
  -v password="$CHATBOT_DB_PASSWORD" \
  -v dbname="$DB_NAME" \
  -f - < "$ROOT_DIR/db/chatbot_role.sql"

echo "OK: role ${CHATBOT_DB_USER} đã sẵn sàng trên ${DB_NAME} (chỉ view published + slide_documents)."
