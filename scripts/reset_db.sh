#!/usr/bin/env bash
# Reset DB local: drop + create lại database rồi chạy toàn bộ migration.
# KHÔNG xóa volume (weights gaze/chatbot vẫn giữ nguyên).
#
# Dùng khi bạn sửa migration đã áp hoặc muốn test lại từ đầu:
#   ./scripts/reset_db.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

: "${POSTGRES_USER:?thiếu POSTGRES_USER}"
: "${POSTGRES_DB:?thiếu POSTGRES_DB}"

echo "==> dừng backend/chatbot để nhả kết nối DB"
docker compose stop backend chatbot >/dev/null 2>&1 || true

echo "==> đảm bảo postgres đang chạy"
docker compose up -d postgres >/dev/null

echo "==> drop + create database ${POSTGRES_DB}"
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
  -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS \"${POSTGRES_DB}\";" \
  -c "CREATE DATABASE \"${POSTGRES_DB}\";"

echo "==> chạy migrations"
docker compose run --rm migrate

echo "==> khởi động lại backend/chatbot"
docker compose start backend chatbot >/dev/null 2>&1 || true

echo "OK: DB ${POSTGRES_DB} đã reset."
