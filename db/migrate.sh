#!/usr/bin/env bash
# =============================================================================
# migrate.sh — runner migration duy nhất cho dev/test/CI.
#
#   bash db/migrate.sh [THU_MUC_MIGRATION]     # mặc định: <dir của script>/migrations
#
# Nguyên tắc (PLAN.md Phase 1):
#   * Một kết nối psql giữ advisory lock suốt lượt chạy.
#   * Mỗi migration + checksum record commit atomically trong một transaction.
#   * File đã áp mà checksum đổi -> fail.
#   * Database có lịch sử migration cũ / schema cũ -> fail, yêu cầu reset có guard.
#   * Không có MIGRATE_BASELINE, không tự replay/đoán schema.
#
# Biến môi trường (psql tự đọc): PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATIONS_DIR="${1:-${SCRIPT_DIR}/migrations}"

if [ ! -d "${MIGRATIONS_DIR}" ]; then
    echo "LỖI: không thấy thư mục migration: ${MIGRATIONS_DIR}" >&2
    exit 1
fi

list_migrations() {
    find "${MIGRATIONS_DIR}" -maxdepth 1 -type f -name '*.sql' -printf '%f\n' | sort -V
}

checksum_of() { sha256sum "$1" | awk '{print $1}'; }

# psql -c không nội suy biến; runner dùng -f - với :'name' / :"name".
sql_quote() { printf '%s' "${1//\'/\'\'}"; }

# ---------------------------------------------------------------------------
# Chờ PostgreSQL sẵn sàng
# ---------------------------------------------------------------------------
for attempt in $(seq 1 30); do
    if psql -v ON_ERROR_STOP=1 -q -tA -c 'SELECT 1' >/dev/null 2>&1; then
        break
    fi
    if [ "${attempt}" -eq 30 ]; then
        echo "LỖI: không kết nối được PostgreSQL (PGHOST=${PGHOST:-localhost} PGUSER=${PGUSER:-<trống>} PGDATABASE=${PGDATABASE:-<trống>})." >&2
        exit 1
    fi
    sleep 2
done

echo "DB đích: $(psql -tA -c "SELECT current_database() || ' @ ' || current_user")"

# Danh sách file hiện tại — dùng để phát hiện lịch sử migration cũ.
current_names=""
for name in $(list_migrations); do
    current_names+="'$(sql_quote "${name}")',"
done
current_names="${current_names%,}"

tmpfile="$(mktemp)"
trap 'rm -f "${tmpfile}"' EXIT

# ---------------------------------------------------------------------------
# Sinh script một-session: lock -> kiểm tra lịch sử -> từng migration
# ---------------------------------------------------------------------------
{
    echo "\\set ON_ERROR_STOP on"
    echo "SELECT pg_advisory_lock(hashtext('eyelearning_migrations'));"
    cat <<SQL
DO \$\$
DECLARE
    old_count integer;
BEGIN
    IF to_regclass('public.schema_migrations') IS NULL THEN
        IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public') THEN
            RAISE EXCEPTION 'old schema detected: public tables exist without schema_migrations; run scripts/reset_db.sh';
        END IF;
        CREATE TABLE schema_migrations (
            filename    TEXT PRIMARY KEY,
            checksum    TEXT NOT NULL,
            applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            duration_ms INTEGER
        );
    ELSE
        SELECT count(*) INTO old_count
          FROM schema_migrations
         WHERE filename NOT IN (${current_names});
        IF old_count > 0 THEN
            RAISE EXCEPTION 'old migration history detected (% rows); run scripts/reset_db.sh', old_count;
        END IF;
    END IF;
END \$\$;
SQL

    for name in $(list_migrations); do
        path="${MIGRATIONS_DIR}/${name}"
        sum="$(checksum_of "${path}")"
        q_name="$(sql_quote "${name}")"
        q_path="$(sql_quote "${path}")"
        echo "\\echo '=== ${name} ==='"
        echo "\\set name '${q_name}'"
        echo "\\set sum '${sum}'"
        cat <<SQL
SELECT (coalesce((SELECT checksum FROM schema_migrations WHERE filename = :'name'), '') = '')::text AS missing,
       (coalesce((SELECT checksum FROM schema_migrations WHERE filename = :'name'), '') = :'sum')::text AS same
\\gset
\\if :same
    \\echo '  -> bỏ qua (đã áp)'
\\else
    \\if :missing
        SELECT clock_timestamp() AS started \\gset
        BEGIN;
        \\i '${q_path}'
        INSERT INTO schema_migrations (filename, checksum, duration_ms)
        VALUES (:'name', :'sum',
                (EXTRACT(EPOCH FROM (clock_timestamp() - :'started'::timestamptz)) * 1000)::int);
        COMMIT;
        \\echo '  -> áp dụng'
    \\else
        \\echo '  -> LỖI: file đã áp nhưng checksum đã đổi'
        SELECT 1 / 0;
    \\endif
\\endif
SQL
    done

    echo "SELECT pg_advisory_unlock_all();"
} > "${tmpfile}"

psql -v ON_ERROR_STOP=1 -f "${tmpfile}"
