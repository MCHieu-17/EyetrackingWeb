#!/usr/bin/env bash
# Backup/restore PostgreSQL của stack local.
#
#   ./scripts/backup.sh
#   ./scripts/backup.sh --restore backups/eyelearning-YYYYmmdd-HHMMSS.dump
#   ./scripts/backup.sh --restore <file> --yes
#
# Backup ghi vào backups/ (đã gitignore). Restore dùng pg_restore
# --clean --if-exists nên sẽ xoá/ghi đè object trong database hiện tại.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="$ROOT_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "Không tìm thấy $ENV_FILE — tạo từ .env.example trước." >&2
    exit 1
fi

set -a
# shellcheck disable=SC1091
source "$ENV_FILE"
set +a

: "${POSTGRES_USER:?thiếu POSTGRES_USER trong .env}"
: "${POSTGRES_DB:?thiếu POSTGRES_DB trong .env}"

BACKUP_DIR="$ROOT_DIR/backups"

usage() {
    cat <<'EOF'
Cách dùng:
  ./scripts/backup.sh
      Tạo backup vào backups/eyelearning-YYYYmmdd-HHMMSS.dump.

  ./scripts/backup.sh --restore <file> [--yes]
      Khôi phục file backup vào database hiện tại. Mặc định hỏi xác nhận;
      --yes bỏ qua câu hỏi (dùng cho script/khẩn cấp).

  ./scripts/backup.sh --help
EOF
}

restore_file=""
assume_yes=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --restore)
            if [[ $# -lt 2 ]]; then
                echo "Thiếu đường dẫn file sau --restore." >&2
                usage >&2
                exit 2
            fi
            restore_file="$2"
            shift 2
            ;;
        --yes|-y)
            assume_yes=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Tham số không hợp lệ: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ -n "$restore_file" ]]; then
    if [[ ! -f "$restore_file" ]]; then
        echo "Không tìm thấy file backup: $restore_file" >&2
        exit 1
    fi
    if [[ "$assume_yes" != true ]]; then
        echo "CẢNH BÁO: khôi phục sẽ xoá/ghi đè object trong database '$POSTGRES_DB'."
        if ! read -r -p "Tiếp tục? [y/N] " answer; then
            echo "Không đọc được xác nhận — đã huỷ." >&2
            exit 1
        fi
        case "$answer" in
            y|Y|yes|YES) ;;
            *)
                echo "Đã huỷ."
                exit 1
                ;;
        esac
    fi
    echo "Đang khôi phục $restore_file vào database $POSTGRES_DB..."
    # Sinh SQL trước để dump lỗi không làm restore dở dang.
    sql_file="$(mktemp "${TMPDIR:-/tmp}/eyelearning-restore-XXXXXX.sql")"
    trap 'rm -f "$sql_file"' EXIT
    docker compose exec -T postgres pg_restore \
        --clean --if-exists --file=- < "$restore_file" > "$sql_file"
    # pg_restore đặt search_path rỗng khi restore. Baseline hiện tại dùng
    # unaccent() không qualify trong generated column, nên đổi search_path
    # sang public trước khi psql chạy script SQL do pg_restore sinh ra.
    sed -i "s/set_config('search_path', '', false)/set_config('search_path', 'public', false)/" "$sql_file"
    docker compose exec -T postgres psql \
        -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 < "$sql_file"
    echo "Khôi phục xong."
    exit 0
fi

if [[ "$assume_yes" == true ]]; then
    echo "--yes chỉ dùng cùng --restore." >&2
    exit 2
fi

mkdir -p "$BACKUP_DIR"
timestamp="$(date +%Y%m%d-%H%M%S)"
output="$BACKUP_DIR/eyelearning-$timestamp.dump"
partial="$output.partial"

cleanup() {
    rm -f "$partial"
}
trap cleanup EXIT

echo "Đang backup database $POSTGRES_DB..."
docker compose exec -T postgres pg_dump \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    --format=custom > "$partial"

mv "$partial" "$output"
trap - EXIT
echo "Đã tạo backup: $output"
