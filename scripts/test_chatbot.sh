#!/usr/bin/env bash
# Chatbot + backend chat/AOI tests trên PostgreSQL tạm, không dùng DB development.
set -euo pipefail
cd "$(dirname "$0")/.."
repo_root="$PWD"
test_container="eyelearning-chatbot-test-$$"
test_db="eyelearning_refactor_test"
cleanup() { docker rm -f "$test_container" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run --name "$test_container" --rm -d \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB="$test_db" \
  -p 127.0.0.1::5432 pgvector/pgvector:0.8.7-pg16 >/dev/null
test_port="$(docker port "$test_container" 5432/tcp | cut -d: -f2)"
for attempt in $(seq 1 50); do
  if docker exec "$test_container" pg_isready -U postgres >/dev/null 2>&1; then break; fi
  sleep 0.2
done

# Runner dùng đúng baseline mới, không replay migration cũ.
docker cp "$repo_root/db" "$test_container:/db" >/dev/null
docker exec -e PGHOST=127.0.0.1 -e PGUSER=postgres -e PGPASSWORD=postgres \
  -e PGDATABASE="$test_db" "$test_container" bash /db/migrate.sh /db/migrations

export DATABASE_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:${test_port}/${test_db}"
export CHATBOT_INTEGRATION_DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:${test_port}/${test_db}"
export CHATBOT_TEST_PYTHON="$repo_root/services/chatbot/.venv/bin/python"
export CHATBOT_URL="http://127.0.0.1:9"
export CHATBOT_INTERNAL_TOKEN="test-chatbot-token"

(
  cd backend
  .venv/bin/python -m pytest \
    tests/test_chat_phase5.py \
    tests/test_aoi_phase5.py \
    tests/test_content_phase2.py \
    tests/test_quiz_phase3.py \
    tests/test_session_phase3.py \
    tests/test_gaze_phase4.py -q
)
(
  cd services/chatbot
  .venv/bin/python -m pytest tests -q
)
(
  cd frontend
  npm run typecheck
  npm test
)
