#!/usr/bin/env bash
# Chạy gaze tests trong image test (không cần GPU cho nhóm fast).
#
#   ./scripts/test_gaze.sh fast
#   ./scripts/test_gaze.sh smoke
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-fast}"
case "$MODE" in
    fast | smoke) ;;
    *)
        printf 'Dùng: %s [fast|smoke]\n' "$0" >&2
        exit 2
        ;;
esac

printf '[test_gaze] build image test\n'
docker compose build gaze-test >/dev/null

printf '[test_gaze] chạy %s\n' "$MODE"
EXTRA_ENV=()
if [ "$MODE" = "smoke" ]; then
    # Smoke chạy được trên CPU (chậm hơn) mà không cần cấu hình GPU cho container test.
    EXTRA_ENV=(-e "DEVICE=${GAZE_TEST_DEVICE:-cpu}")
fi
docker compose --profile test run --rm "${EXTRA_ENV[@]}" gaze-test \
    -m "$MODE" -q --tb=short
