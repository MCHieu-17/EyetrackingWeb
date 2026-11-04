#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
services/chatbot/.venv/bin/python - <<'PY'
import psycopg
with psycopg.connect('postgresql://postgres:postgres@127.0.0.1:55439/postgres',autocommit=True) as conn:
    if not conn.execute("SELECT 1 FROM pg_database WHERE datname='eyelearning_graph_eval'").fetchone():
        conn.execute('CREATE DATABASE eyelearning_graph_eval')
PY
(cd backend && DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:55439/eyelearning_graph_eval .venv/bin/python -c 'import asyncio; from tests.conftest import _apply_migrations; asyncio.run(_apply_migrations())')
services/chatbot/.venv/bin/python services/chatbot/scripts/benchmark_graph.py --database postgresql://postgres:postgres@127.0.0.1:55439/eyelearning_graph_eval --fixture /tmp/graph-v2-fixture.json --output /tmp/seed.json --label seed --seed-only
