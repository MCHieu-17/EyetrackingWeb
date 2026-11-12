#!/usr/bin/env bash
# Seed 3 tài khoản dev (mật khẩu Password123!) vào DB đang chạy trong Docker.
# Chạy sau khi migrations đã áp:
#   ./scripts/seed_dev.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

: "${POSTGRES_USER:?thiếu POSTGRES_USER}"
: "${POSTGRES_DB:?thiếu POSTGRES_DB}"

docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v ON_ERROR_STOP=1 < "$ROOT_DIR/db/seed_dev_users.sql"

echo "OK: đã seed tài khoản dev."
