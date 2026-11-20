#!/usr/bin/env bash
# Chạy chatbot tests trên database test riêng.
#
#   ./scripts/test_chatbot.sh fast
#   ./scripts/test_chatbot.sh smoke
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

set -a
# shellcheck disable=SC1091
source "$ROOT_DIR/.env"
set +a

: "${POSTGRES_USER:?thiếu POSTGRES_USER}"
: "${POSTGRES_PASSWORD:?thiếu POSTGRES_PASSWORD}"

MODE="${1:-fast}"
case "$MODE" in
    fast | smoke) ;;
    *)
        printf 'Dùng: %s [fast|smoke]\n' "$0" >&2
        exit 2
        ;;
esac

TEST_DB="${TEST_DB:-eyetracking_test}"
log() { printf '[test_chatbot] %s\n' "$*"; }

if [ "$MODE" = "smoke" ]; then
    log "chạy smoke trên stack thật (backend/chatbot/worker phải đang chạy)"
    docker compose build chatbot-test >/dev/null
    docker compose --profile test run --rm \
        -e CHATBOT_DATABASE_URL="${CHATBOT_DATABASE_URL_DOCKER}" \
        -e SMOKE_BACKEND_URL="http://backend:8001" \
        -e SMOKE_DATABASE_URL="${CHATBOT_DATABASE_URL_DOCKER}" \
        chatbot-test -m smoke -q --tb=short
    exit $?
fi

log "tạo database $TEST_DB"
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS \"$TEST_DB\";" >/dev/null
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d postgres \
    -c "CREATE DATABASE \"$TEST_DB\";" >/dev/null

log "build migrate + chatbot-test"
docker compose build migrate chatbot-test >/dev/null

log "chạy migrations cho $TEST_DB"
docker compose run --rm -e PGDATABASE="$TEST_DB" migrate >/dev/null

log "chạy pytest -m $MODE"
docker compose --profile test run --rm chatbot-test -m "$MODE" -q --tb=short
