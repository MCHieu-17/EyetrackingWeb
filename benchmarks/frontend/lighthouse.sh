#!/usr/bin/env bash
# Chạy Lighthouse headless cho các trang chính (mobile + desktop).
#   benchmarks/frontend/lighthouse.sh <run-dir> <fixtures.json> <tokens.json>
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/benchmarks/lib/common.sh"

RUN_DIR="${1:?usage: lighthouse.sh <run-dir> <fixtures> <tokens>}"
FIXTURES="${2:?}"
TOKENS="${3:?}"
OUT="$RUN_DIR/frontend/lighthouse"
mkdir -p "$OUT"

command -v lighthouse >/dev/null 2>&1 || die "Thiếu lighthouse CLI"
command -v jq >/dev/null 2>&1 || die "Thiếu jq"

BASE_URL="${BENCH_BASE_URL:-http://127.0.0.1:3100}"
RUNS="${LIGHTHOUSE_RUNS:-3}"
CORE_COURSE_ID="$(json_get "$FIXTURES" 'd["ids"]["core_course_id"]')"

student_token="$(jq -r '.student.token' "$TOKENS")"
teacher_token="$(jq -r '.teacher.token' "$TOKENS")"
admin_token="$(jq -r '.admin.token' "$TOKENS")"

cookie_for() {
  case "$1" in
    student) printf 'access_token=%s' "$student_token" ;;
    teacher) printf 'access_token=%s' "$teacher_token" ;;
    admin) printf 'access_token=%s' "$admin_token" ;;
    *) printf '' ;;
  esac
}

pages=(
  "home|none|/"
  "login|none|/account/login"
  "try|none|/try"
  "student|student|/student"
  "teacher|teacher|/teacher"
  "teacher_workspace|teacher|/teacher/courses/${CORE_COURSE_ID}?tab=content"
  "student_reader|student|/student/courses/${CORE_COURSE_ID}"
  "teacher_analytics|teacher|/teacher/courses/${CORE_COURSE_ID}?tab=visualization"
  "admin|admin|/admin"
)

run_one() {
  local name="$1" auth="$2" path="$3" form="$4" idx="$5"
  local url="${BASE_URL}${path}"
  local target="$OUT/${name}.${form}.${idx}.json"
  local extra=()
  if [ "$auth" != "none" ]; then
    local cookie
    cookie="$(cookie_for "$auth")"
    extra=(--extra-headers="$(jq -nc --arg c "$cookie" '{Cookie:$c}')")
  fi
  local form_args=()
  if [ "$form" = "desktop" ]; then
    form_args=(--preset=desktop)
  fi
  log "Lighthouse ${name} ${form} run=${idx} ${url}"
  lighthouse "$url" \
    --quiet \
    --chrome-flags="--headless=new --no-sandbox --disable-dev-shm-usage --disable-gpu" \
    --only-categories=performance,accessibility,best-practices \
    --throttling-method=simulate \
    "${form_args[@]}" \
    "${extra[@]}" \
    --output=json \
    --output-path="$target" || warn "Lighthouse lỗi ${name} ${form} run=${idx}"
}

for item in "${pages[@]}"; do
  IFS='|' read -r name auth path <<< "$item"
  for form in mobile desktop; do
    for i in $(seq 1 "$RUNS"); do
      run_one "$name" "$auth" "$path" "$form" "$i"
    done
  done
done

node "$ROOT_DIR/benchmarks/frontend/lighthouse-summary.mjs" \
  --dir "$OUT" \
  --out "$RUN_DIR/frontend/lighthouse-summary.json" \
  --md "$RUN_DIR/frontend/lighthouse-summary.md"

echo "$RUN_DIR/frontend/lighthouse-summary.json"
