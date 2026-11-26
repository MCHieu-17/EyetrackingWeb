#!/usr/bin/env bash
# Kiểm tra mọi image GHCR mà compose Portainer tham chiếu đã tồn tại.
#
#   ./scripts/check_release_images.sh
#   ./scripts/check_release_images.sh --tag v1.3.2
#   IMAGE_PREFIX=ghcr.io/mchieu-17 IMAGE_TAG=v1.3.2 ./scripts/check_release_images.sh
#
# Mặc định đọc IMAGE_PREFIX/IMAGE_TAG từ deploy/portainer/stack.env.
# Package private cần `docker login ghcr.io` trước khi chạy.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="deploy/portainer/stack.env"
COMPOSE_FILE="deploy/portainer/docker-compose.yml"
PREFIX="${IMAGE_PREFIX:-}"
TAG="${IMAGE_TAG:-}"

usage() {
    cat <<'EOF'
Usage: ./scripts/check_release_images.sh [options]

  --env-file <path>  File env chứa IMAGE_PREFIX/IMAGE_TAG (mặc định:
                     deploy/portainer/stack.env)
  --compose <path>   File compose (mặc định: deploy/portainer/docker-compose.yml)
  --prefix <ref>     Ghi đè IMAGE_PREFIX
  --tag <tag>        Ghi đè IMAGE_TAG
  -h, --help         Hiện trợ giúp
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --compose)
            COMPOSE_FILE="$2"
            shift 2
            ;;
        --prefix)
            PREFIX="$2"
            shift 2
            ;;
        --tag)
            TAG="$2"
            shift 2
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            printf '[check-images] tham số không hợp lệ: %s\n' "$1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

read_env() {
    [ -f "$ENV_FILE" ] || return 0
    sed -n "s/^$1=//p" "$ENV_FILE" |
        tail -n 1 |
        tr -d '\r' |
        sed -E 's/^"(.*)"$/\1/; s/^'\''(.*)'\''$/\1/'
}

[ -n "$PREFIX" ] || PREFIX="$(read_env IMAGE_PREFIX)"
[ -n "$TAG" ] || TAG="$(read_env IMAGE_TAG)"
PREFIX="${PREFIX:-ghcr.io/mchieu-17}"
PREFIX="${PREFIX%/}"

if [ -z "$TAG" ]; then
    printf '[check-images] thiếu IMAGE_TAG (đặt trong %s hoặc dùng --tag)\n' \
        "$ENV_FILE" >&2
    exit 2
fi

if [ ! -f "$COMPOSE_FILE" ]; then
    printf '[check-images] không thấy compose: %s\n' "$COMPOSE_FILE" >&2
    exit 2
fi

mapfile -t IMAGES < <(
    grep -oE '\$\{IMAGE_PREFIX[^}]*\}/eyelearning-[a-z0-9-]+:\$\{IMAGE_TAG[^}]*\}' \
        "$COMPOSE_FILE" |
        sed -e "s#\${IMAGE_PREFIX[^}]*}#${PREFIX}#g" \
            -e "s#\${IMAGE_TAG[^}]*}#${TAG}#g" |
        sort -u
)

if [ "${#IMAGES[@]}" -eq 0 ]; then
    printf '[check-images] không tìm thấy image GHCR nào trong %s\n' \
        "$COMPOSE_FILE" >&2
    exit 2
fi

printf '[check-images] %s — tag %s\n' "$PREFIX" "$TAG"

missing=0
unauthorized=0
for image in "${IMAGES[@]}"; do
    if output="$(docker manifest inspect "$image" 2>&1 >/dev/null)"; then
        printf '  OK   %s\n' "$image"
        continue
    fi
    printf '  MISS %s\n' "$image" >&2
    if grep -qiE 'unauthorized|denied|authentication required' <<<"$output"; then
        unauthorized=1
    fi
    missing=1
done

if [ "$missing" -ne 0 ]; then
    cat >&2 <<EOF

[check-images] Tag ${TAG} chưa có đủ image.
- Cut tag mới để build toàn bộ image:
    git tag -a vX.Y.Z -m "release vX.Y.Z"
    git push origin vX.Y.Z
- Hoặc dùng tag đã có đủ image (ví dụ sha-<commit> hoặc latest).
EOF
    if [ "$unauthorized" -ne 0 ]; then
        printf '%s\n' \
            '- Có lỗi xác thực: chạy `docker login ghcr.io` rồi kiểm tra lại.' >&2
    fi
    exit 1
fi

printf '[check-images] OK — đủ %d image cho tag %s\n' "${#IMAGES[@]}" "$TAG"
