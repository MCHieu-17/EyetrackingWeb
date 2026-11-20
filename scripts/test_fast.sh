#!/usr/bin/env bash
# Chạy toàn bộ fast test (backend + gaze + chatbot), tuần tự vì dùng chung DB.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

printf '\n=== backend fast ===\n'
./scripts/test_backend.sh

printf '\n=== gaze fast ===\n'
./scripts/test_gaze.sh fast

printf '\n=== chatbot fast ===\n'
./scripts/test_chatbot.sh fast

printf '\n[tests] fast OK\n'
