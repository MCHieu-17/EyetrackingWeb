#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"
DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:55439/eyelearning_test .venv/bin/python -m pytest tests/test_chat_internal.py -q
