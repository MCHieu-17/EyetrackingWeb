#!/usr/bin/env bash
# =====================================================================
# create_chatbot_role.sh — tạo/cập nhật DB role hạn chế cho chatbot.
#
# Chatbot chỉ cần đọc course/module/lesson/slide + ghi embedding/status.
# Role này KHÔNG có quyền đọc quiz_assignments/quiz_attempts/users — lớp bảo
# vệ thứ hai để chatbot không thể lộ đáp án kể cả khi bị prompt injection.
#
# Chạy SAU khi migrations đã áp (cần các bảng 024):
#   ./ops/create_chatbot_role.sh
#
# Idempotent: chạy lại sẽ ALTER password + grant lại quyền.
# Script chạy psql trong container `postgres` (không cần psql trên host).
# =====================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

: "${POSTGRES_USER:?thiếu POSTGRES_USER}"
: "${POSTGRES_DB:?thiếu POSTGRES_DB}"
: "${CHATBOT_DB_USER:?thiếu CHATBOT_DB_USER}"
: "${CHATBOT_DB_PASSWORD:?thiếu CHATBOT_DB_PASSWORD}"

docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${CHATBOT_DB_USER}') THEN
        CREATE ROLE ${CHATBOT_DB_USER} LOGIN PASSWORD '${CHATBOT_DB_PASSWORD}';
    ELSE
        ALTER ROLE ${CHATBOT_DB_USER} WITH LOGIN PASSWORD '${CHATBOT_DB_PASSWORD}';
    END IF;
END
\$\$;

GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${CHATBOT_DB_USER};
GRANT USAGE ON SCHEMA public TO ${CHATBOT_DB_USER};

-- Đọc nội dung môn học + ghi embedding/status.
GRANT SELECT ON courses, modules, lessons, lesson_contents, lesson_content_embedding
    TO ${CHATBOT_DB_USER};
GRANT INSERT, UPDATE, DELETE ON lesson_content_embedding TO ${CHATBOT_DB_USER};
GRANT UPDATE (embedding_status, embedding_error, embedding_updated_at)
    ON lesson_contents TO ${CHATBOT_DB_USER};

-- Không cho đọc dữ liệu bài tập/người dùng.
REVOKE ALL ON quiz_assignments, quiz_attempts, quiz_attempt_sessions, users
    FROM ${CHATBOT_DB_USER};
SQL

echo "OK: role ${CHATBOT_DB_USER} đã sẵn sàng (không có quyền đọc bảng quiz/users)."
