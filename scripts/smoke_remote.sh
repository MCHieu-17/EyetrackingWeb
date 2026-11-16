#!/usr/bin/env bash
# Smoke test stack production qua domain public (không cần SSH/Portainer).
#
#   BASE_URL=https://eyetracking.nmhieu17.space ./scripts/smoke_remote.sh
#   ./scripts/smoke_remote.sh https://eyetracking.nmhieu17.space
set -euo pipefail

BASE_URL="${BASE_URL:-${1:-}}"
BASE_URL="${BASE_URL%/}"

if [[ -z "$BASE_URL" ]]; then
    echo "Cách dùng: BASE_URL=https://domain ./scripts/smoke_remote.sh" >&2
    exit 2
fi

if ! command -v curl >/dev/null 2>&1; then
    echo "Thiếu curl." >&2
    exit 1
fi

MAX_TIME="${MAX_TIME:-15}"
log() { printf '[smoke] %s\n' "$*"; }

status_of() {
    local path="$1"
    curl -sS -o /dev/null -w '%{http_code}' --max-time "$MAX_TIME" \
        "${BASE_URL}${path}" || true
}

check_200() {
    local path="$1"
    local code
    code="$(status_of "$path")"
    if [[ "$code" != "200" ]]; then
        echo "[smoke] FAIL ${path}: HTTP ${code} (cần 200)" >&2
        exit 1
    fi
    log "OK ${path} (200)"
}

check_any() {
    local path="$1"
    shift
    local code
    code="$(status_of "$path")"
    for expected in "$@"; do
        if [[ "$code" == "$expected" ]]; then
            log "OK ${path} (${code})"
            return 0
        fi
    done
    echo "[smoke] FAIL ${path}: HTTP ${code}; chấp nhận: $*" >&2
    exit 1
}

log "base: ${BASE_URL}"
if [[ "$BASE_URL" == http://* ]]; then
    log "CẢNH BÁO: dùng HTTP — webcam/calibration cần HTTPS (trừ localhost)."
fi

check_200 "/nginx-health"
check_200 "/"
check_200 "/account/login"
check_200 "/gaze/health"
# /ready chỉ 200 khi model gaze đã load xong.
check_200 "/gaze/ready"
# Backend sống thì trả 401/403 (hoặc 200 nếu đã đăng nhập); 502/503/504 là lỗi.
check_any "/api/me/profile" 200 401 403

log "OK — nginx, frontend, gaze (ready) và backend đều phản hồi."
log "Kiểm tra thêm thủ công: đăng nhập, OTP, calibration, upload slide, chat, replay."
