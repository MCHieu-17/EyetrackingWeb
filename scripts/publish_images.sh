#!/usr/bin/env bash
# Build + push toàn bộ image production lên registry.
#
# Dùng khi GitHub Actions không khả dụng, hoặc muốn build gaze trên máy local.
# Phải đăng nhập registry trước:
#
#   docker login ghcr.io
#   IMAGE_PREFIX=ghcr.io/<owner> IMAGE_TAG=v1.0.0 ./scripts/publish_images.sh
#
# Biến:
#   IMAGE_PREFIX   mặc định ghcr.io/mchieu-17
#   IMAGE_TAG      mặc định latest
#   PLATFORM       mặc định linux/amd64
#   SKIP_GAZE=1    bỏ qua image gaze (10 GB) khi chỉ cần backend/frontend
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

IMAGE_PREFIX="${IMAGE_PREFIX:-ghcr.io/mchieu-17}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
PLATFORM="${PLATFORM:-linux/amd64}"
SKIP_GAZE="${SKIP_GAZE:-0}"

if ! docker buildx version >/dev/null 2>&1; then
    echo "Thiếu docker buildx. Cài Docker Engine có Buildx hoặc bật Docker Desktop." >&2
    exit 1
fi

log() { printf '[publish] %s\n' "$*"; }

build_push() {
    local name="$1"
    local context="$2"
    local dockerfile="$3"
    local target="${4:-}"
    local image="${IMAGE_PREFIX}/eyelearning-${name}:${IMAGE_TAG}"

    log "build ${image} (${PLATFORM})"
    local args=(
        buildx build
        --platform "$PLATFORM"
        --push
        --tag "$image"
        --file "$dockerfile"
    )
    if [[ -n "$target" ]]; then
        args+=(--target "$target")
    fi
    args+=("$context")
    docker "${args[@]}"
}

log "registry: ${IMAGE_PREFIX}, tag: ${IMAGE_TAG}, platform: ${PLATFORM}"

build_push backend ./backend ./backend/Dockerfile api
build_push content-worker ./backend ./backend/Dockerfile content-worker
build_push chatbot ./services/chatbot ./services/chatbot/Dockerfile
if [[ "$SKIP_GAZE" == "1" ]]; then
    log "bỏ qua gaze (SKIP_GAZE=1)"
else
    build_push gaze ./services/gaze ./services/gaze/Dockerfile
fi
build_push frontend ./frontend ./frontend/Dockerfile
build_push nginx ./nginx ./nginx/Dockerfile
build_push migrations ./db ./db/Dockerfile

log "xong. Kiểm tra package visibility trên GHCR trước khi deploy Portainer."
log "Nếu package private: thêm registry ghcr.io + PAT read:packages trong Portainer."
