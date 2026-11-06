#!/usr/bin/env bash
# =====================================================================
# create_chatbot_role.sh — tạo/cập nhật DB role hạn chế cho chatbot.
#
# Chatbot chỉ được:
#   - đọc view công khai `v_chatbot_slide_documents`;
#   - ghi `slide_documents` (ingest transcript/embedding).
# KHÔNG được đọc quiz_specs/quiz_attempts/users/chat_*.
#
# Chạy SAU baseline:
#   ./ops/create_chatbot_role.sh
#   POSTGRES_DB_OVERRIDE=eyelearning_refactor_test ./ops/create_chatbot_role.sh
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
  -f - <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'role', :'password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role')
\gexec

SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'role', :'password')
WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role')
\gexec

GRANT CONNECT ON DATABASE :"dbname" TO :"role";
GRANT USAGE ON SCHEMA public TO :"role";

-- Xóa mọi quyền cũ (kể cả grant từ schema cũ) trước khi grant lại.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM :"role";
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM :"role";

-- Đọc nội dung published qua view; ghi tài liệu ingest.
GRANT SELECT ON v_chatbot_slide_documents TO :"role";
GRANT SELECT (slide_version_id) ON slide_documents TO :"role";
GRANT INSERT, UPDATE, DELETE ON slide_documents TO :"role";

-- Không cho đọc dữ liệu bài tập/người dùng/chat.
REVOKE ALL ON quiz_specs, quiz_attempts, users, chat_sessions, chat_messages
    FROM :"role";
SQL

echo "OK: role ${CHATBOT_DB_USER} đã sẵn sàng trên ${DB_NAME} (chỉ view published + slide_documents)."
