#!/usr/bin/env bash
# Dọn dẹp dữ liệu hết hạn: auth session và learning session quá hạn.
#
#   ./scripts/maintenance.sh          # chạy trong Docker (backend service)
#   ./scripts/maintenance.sh --local  # chạy bằng venv trên máy
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

usage() {
    cat <<'EOF'
Usage: scripts/maintenance.sh [--local]

  (không tham số)  docker compose exec -T backend python -m app.maintenance
  --local          backend/.venv/bin/python -m app.maintenance (từ repo root)
EOF
}

case "${1:-}" in
    "")
        printf '[maintenance] chạy trong Docker (service backend)\n'
        docker compose exec -T backend python -m app.maintenance
        ;;
    --local)
        printf '[maintenance] chạy local bằng backend/.venv\n'
        # Backend đọc DATABASE_URL; .env chỉ có DATABASE_URL_DOCKER dùng
        # hostname nội bộ Docker. Khi chạy local, trỏ về Postgres đã publish
        # ở 127.0.0.1:5435 nếu caller chưa set DATABASE_URL.
        if [ -f "$ROOT_DIR/.env" ]; then
            set -a
            # shellcheck disable=SC1091
            source "$ROOT_DIR/.env"
            set +a
        fi
        if [ -z "${DATABASE_URL:-}" ] && [ -n "${DATABASE_URL_DOCKER:-}" ]; then
            DATABASE_URL="${DATABASE_URL_DOCKER/@postgres:5432/@127.0.0.1:5435}"
            export DATABASE_URL
        fi
        # Maintenance không gọi AI service; đặt mặc định để Settings khởi tạo
        # được khi chạy ngoài Docker.
        export AI_HTTP_URL="${AI_HTTP_URL:-http://localhost:8000}"
        PYTHONPATH="$ROOT_DIR/backend${PYTHONPATH:+:$PYTHONPATH}" \
            backend/.venv/bin/python -m app.maintenance
        ;;
    -h | --help)
        usage
        ;;
    *)
        printf '[maintenance] tham số không hợp lệ: %s\n' "$1" >&2
        usage >&2
        exit 2
        ;;
esac
