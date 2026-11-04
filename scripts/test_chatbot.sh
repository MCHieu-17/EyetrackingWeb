#!/usr/bin/env bash
# Disposable PostgreSQL/pgvector and test media; never uses the application DB.
set -euo pipefail
cd "$(dirname "$0")/.."
repo_root="$PWD"
test_container="eyelearning-chatbot-test-$$"
cleanup() { docker rm -f "$test_container" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker run --name "$test_container" --rm -d -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=eyetracking_test -p 127.0.0.1::5432 pgvector/pgvector:0.8.7-pg16 >/dev/null
test_port="$(docker port "$test_container" 5432/tcp | cut -d: -f2)"
for attempt in $(seq 1 50); do
  if docker exec "$test_container" pg_isready -U postgres >/dev/null 2>&1; then break; fi
  sleep 0.2
done
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@127.0.0.1:${test_port}/eyetracking_test"
export CHATBOT_INTEGRATION_DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:${test_port}/eyetracking_test"
export CHATBOT_TEST_PYTHON="$repo_root/services/chatbot/.venv/bin/python"
(
  cd backend
  .venv/bin/python -c 'import asyncio; from tests.conftest import _apply_migrations; asyncio.run(_apply_migrations())'
  .venv/bin/python -m pytest tests/test_chat.py tests/test_assignments.py tests/test_embedding_retry.py tests/test_chatbot_integration.py -q
)
(
  cd services/chatbot
  .venv/bin/python -m pytest tests -q
)
(
  cd frontend
  npm run typecheck
  npm test
  npm run test:e2e -- e2e/chat-access.spec.ts e2e/chat-control-teacher.spec.ts e2e/student.spec.ts
)
