#!/usr/bin/env bash
# Kiểm tra chất lượng toàn repo.
#
#   ./scripts/check.sh            # ruff + frontend lint/typecheck + compose config
#   ./scripts/check.sh --build    # thêm npm run build (chậm)
#   ./scripts/check.sh --full     # thêm knip + unit tests + backend tests + build
#
# --full dùng cho gate trước khi merge; --build giữ lại cho tương thích.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUN_BUILD=0
RUN_FULL=0

usage() {
    cat <<'EOF'
Usage: ./scripts/check.sh [--build | --full]

  (không tham số)  ruff, frontend lint, typecheck, docker compose config
  --build          như trên + frontend build
  --full           như trên + frontend/backend/chatbot/gaze tests, build
EOF
}

for arg in "$@"; do
    case "$arg" in
        --build)
            RUN_BUILD=1
            ;;
        --full)
            RUN_FULL=1
            RUN_BUILD=1
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            printf '[check] tham số không hợp lệ: %s\n' "$arg" >&2
            usage >&2
            exit 2
            ;;
    esac
done

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

if [ "$RUN_FULL" -eq 1 ]; then
    log "frontend knip"
    (cd frontend && npm run knip)

    log "frontend unit tests"
    (cd frontend && npm run test)

    log "backend tests"
    ./scripts/test_backend.sh

    CHATBOT_PYTHON="${CHATBOT_PYTHON:-services/chatbot/.venv/bin/python}"
    GAZE_PYTHON="${GAZE_PYTHON:-services/gaze/.venv/bin/python}"
    [[ "$CHATBOT_PYTHON" = /* ]] || CHATBOT_PYTHON="$ROOT_DIR/$CHATBOT_PYTHON"
    [[ "$GAZE_PYTHON" = /* ]] || GAZE_PYTHON="$ROOT_DIR/$GAZE_PYTHON"

    log "chatbot tests"
    (cd services/chatbot && "$CHATBOT_PYTHON" -m pytest -q)

    log "gaze tests"
    (cd services/gaze && "$GAZE_PYTHON" -m pytest -q)

    BACKEND_PYTHON="${BACKEND_PYTHON:-backend/.venv/bin/python}"
    [[ "$BACKEND_PYTHON" = /* ]] || BACKEND_PYTHON="$ROOT_DIR/$BACKEND_PYTHON"
    log "reset_db guard tests"
    "$BACKEND_PYTHON" -m unittest discover -s scripts/tests -q
fi

if [ "$RUN_BUILD" -eq 1 ]; then
    log "frontend build"
    (cd frontend && npm run build)
fi

log "docker compose config"
docker compose config >/dev/null

log "docker compose config (portainer production, example env)"
docker compose --env-file deploy/portainer/stack.env.example \
    -f deploy/portainer/docker-compose.yml config >/dev/null

if [ -f deploy/portainer/stack.env ]; then
    log "docker compose config (portainer production, stack.env)"
    docker compose --env-file deploy/portainer/stack.env \
        -f deploy/portainer/docker-compose.yml config >/dev/null
fi

log "OK"
