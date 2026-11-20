#!/usr/bin/env bash
# Seed dữ liệu E2E rồi chạy Playwright trên stack đang chạy.
#
#   ./scripts/e2e.sh
#   E2E_CHAT=1 ./scripts/e2e.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! curl -fsS http://localhost:3000/nginx-health >/dev/null 2>&1; then
    printf '[e2e] stack chưa sẵn sàng tại http://localhost:3000\n' >&2
    printf '[e2e] chạy: docker compose up -d --build\n' >&2
    exit 1
fi

printf '[e2e] đảm bảo user seed\n'
./scripts/seed_dev.sh >/dev/null

# Test chạy lặp nhiều lần từ cùng IP sẽ chạm rate limit login 10/phút.
# Chỉ xoá key rate-limit, không flush toàn bộ Redis.
docker compose exec -T redis sh -c \
    'redis-cli --scan --pattern "*:login:*" | while read -r key; do redis-cli DEL "$key" >/dev/null; done' \
    >/dev/null 2>&1 || true

printf '[e2e] seed dữ liệu\n'
docker compose run --rm --user root \
    -v "$ROOT_DIR/scripts:/scripts:ro" \
    -v "$ROOT_DIR/frontend/e2e:/e2e" \
    backend python /scripts/seed_e2e.py --output /e2e/.fixtures.json

printf '[e2e] chạy Playwright\n'
cd frontend
npx playwright test "$@"
