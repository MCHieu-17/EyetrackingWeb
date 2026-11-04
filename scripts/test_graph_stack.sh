#!/usr/bin/env bash
# Requires the dedicated test container, NOT the application PostgreSQL:
# docker run -d --name eyelearning-graph-test -e POSTGRES_PASSWORD=postgres \
#   -e POSTGRES_DB=eyelearning_test -p 127.0.0.1:55439:5432 pgvector/pgvector:0.8.7-pg16
# For the retained stopped container: docker start eyelearning-graph-test
set -euo pipefail
cd "$(dirname "$0")/.."
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:55439/eyelearning_test
export CHATBOT_INTEGRATION_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:55439/eyelearning_test
export CHATBOT_TEST_PYTHON="$PWD/services/chatbot/.venv/bin/python"
(cd backend && .venv/bin/python -m pytest tests/test_chat.py tests/test_chat_internal.py tests/test_assignments.py tests/test_chatbot_integration.py -q)
(cd services/chatbot && .venv/bin/python -m pytest tests -q)
