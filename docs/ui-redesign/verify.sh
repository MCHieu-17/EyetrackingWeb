#!/usr/bin/env bash
# Build lại frontend trên stack bench (:3100), chạy E2E và chụp ảnh để review.
#   docs/ui-redesign/verify.sh <tag> [page1,page2,...]   (pages theo screenshots.mjs)
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
TAG="${1:?usage: verify.sh <tag> [pages]}"
PAGES="${2:-}"
# shellcheck disable=SC1091
source benchmarks/lib/common.sh
export WORKER_REPLICAS=1 GAZE_REPLICAS=1 FRONTEND_REPLICAS=1

log "build + restart frontend bench"
compose up -d --build --no-deps frontend >/tmp/verify-build.log 2>&1 || { tail -30 /tmp/verify-build.log; exit 1; }
wait_url "http://127.0.0.1:3100/nginx-health" 120

log "E2E"
rm -f frontend/e2e/.auth-*.json
(cd frontend && E2E_BASE_URL=http://127.0.0.1:3100 npx playwright test --trace off --reporter=line) >/tmp/verify-e2e.log 2>&1
e2e=$?
grep -E "✘|passed|failed|flaky|skipped" /tmp/verify-e2e.log | tail -15

log "screenshots → /tmp/shots-$TAG"
args=(--base http://127.0.0.1:3100 --fixtures benchmarks/baseline/pre-ui/fixtures.json
  --tokens benchmarks/baseline/pre-ui/.runtime/tokens.json --out "/tmp/shots-$TAG")
[ -n "$PAGES" ] && args+=(--only "$PAGES")
node benchmarks/frontend/screenshots.mjs "${args[@]}" | tail -3
exit "$e2e"
