#!/usr/bin/env bash
# Kiểm tra tĩnh toàn repo: Python lint, frontend lint/typecheck, compose config.
#
#   ./scripts/check.sh            # lint + typecheck + compose config
#   ./scripts/check.sh --build    # thêm npm run build (chậm)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_BUILD=0
if [ "${1:-}" = "--build" ]; then
    RUN_BUILD=1
fi

log() { printf '[check] %s\n' "$*"; }

if [ -x backend/.venv/bin/ruff ]; then
    RUFF=backend/.venv/bin/ruff
else
    RUFF=ruff
fi

log "ruff check backend services/gaze services/chatbot"
"$RUFF" check backend services/gaze services/chatbot

log "frontend lint"
(cd frontend && npm run lint)

log "frontend typecheck"
(cd frontend && npm run typecheck)

if [ "$RUN_BUILD" -eq 1 ]; then
    log "frontend build"
    (cd frontend && npm run build)
fi

log "docker compose config"
docker compose config >/dev/null

log "OK"
