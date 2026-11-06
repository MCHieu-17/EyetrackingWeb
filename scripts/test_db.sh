#!/usr/bin/env bash
# Dựng database test riêng cho backend/chatbot/E2E.
#
#   ./scripts/test_db.sh            # tạo nếu chưa có, chạy baseline (idempotent)
#   ./scripts/test_db.sh --reset    # drop/recreate có kiểm tra ownership
#
# Không đụng database development `eyetracking` hay các DB khác.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

: "${POSTGRES_USER:?thiếu POSTGRES_USER}"
: "${POSTGRES_DB:?thiếu POSTGRES_DB}"

TEST_DB="${TEST_DB:-eyelearning_refactor_test}"
RESET=0
if [ "${1:-}" = "--reset" ]; then
  RESET=1
fi

if [ "$TEST_DB" = "$POSTGRES_DB" ]; then
  echo "LỖI: TEST_DB không được trùng POSTGRES_DB (${POSTGRES_DB})." >&2
  exit 2
fi
case "$TEST_DB" in
  postgres|template0|template1)
    echo "LỖI: không được dùng database hệ thống: ${TEST_DB}." >&2
    exit 2
    ;;
esac

echo "==> đảm bảo postgres đang chạy"
docker compose up -d postgres >/dev/null

echo "==> kiểm tra database ${TEST_DB}"
DB_STATE="$(docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
  -v ON_ERROR_STOP=1 -tA -v dbname="$TEST_DB" -f - <<'SQL'
SELECT json_build_object(
  'exists', EXISTS (SELECT 1 FROM pg_database WHERE datname = :'dbname'),
  'owner', (SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = :'dbname')
);
SQL
)"

EXISTS="$(printf '%s' "$DB_STATE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["exists"])')"
OWNER="$(printf '%s' "$DB_STATE" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("owner") or "")')"

if [ "$EXISTS" = "True" ] && [ "$OWNER" != "$POSTGRES_USER" ]; then
  echo "LỖI: ${TEST_DB} thuộc owner ${OWNER}, không xác định ownership. Dừng." >&2
  exit 3
fi

if [ "$RESET" = "1" ]; then
  echo "==> drop/recreate ${TEST_DB}"
  docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
    -v ON_ERROR_STOP=1 -v dbname="$TEST_DB" -f - <<'SQL'
DROP DATABASE IF EXISTS :"dbname";
CREATE DATABASE :"dbname";
SQL
elif [ "$EXISTS" != "True" ]; then
  echo "==> tạo ${TEST_DB}"
  docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
    -v ON_ERROR_STOP=1 -v dbname="$TEST_DB" -f - <<'SQL'
CREATE DATABASE :"dbname";
SQL
fi

echo "==> chạy baseline trên ${TEST_DB}"
docker compose run --rm -e PGDATABASE="$TEST_DB" migrate

echo "==> grants cho chatbot role"
POSTGRES_DB_OVERRIDE="$TEST_DB" bash "$ROOT_DIR/ops/create_chatbot_role.sh"

echo "OK: test database ${TEST_DB} sẵn sàng."
