#!/usr/bin/env bash
# Xoá lịch sử gaze/visualization nhưng giữ nội dung khoá học.
#
# Mặc định là PREVIEW — chỉ đếm dữ liệu, không xoá:
#   ./scripts/reset_gaze_data.sh --all
#   ./scripts/reset_gaze_data.sh --course-id <uuid>
#
# Áp dụng thật (bắt buộc --apply và đúng token xác nhận):
#   ./scripts/backup.sh
#   ./scripts/reset_gaze_data.sh --all --apply --confirm-reset-gaze
#
# Phạm vi xoá:
#   course_visits -> learning_sessions -> content_views
#                 -> view_layouts, gaze_samples (FK cascade)
#   Các job analyze_lesson đang queued/processing của lesson liên quan
#   được chuyển sang cancelled để không phân tích dữ liệu đã xoá.
#
# Giữ nguyên: users, courses, modules, lessons, slides, aois, enrollments,
# gaze_calibrations, quiz_attempts.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
    echo "Không tìm thấy .env — tạo từ .env.example trước." >&2
    exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

: "${POSTGRES_USER:?thiếu POSTGRES_USER trong .env}"
: "${POSTGRES_DB:?thiếu POSTGRES_DB trong .env}"

usage() {
    cat <<'EOF'
Cách dùng:
  ./scripts/reset_gaze_data.sh --all
  ./scripts/reset_gaze_data.sh --course-id <uuid>

  --all                 Xoá lịch sử gaze của toàn bộ khoá học.
  --course-id <uuid>    Chỉ xoá lịch sử gaze của một khoá học.
  --apply               Thực hiện xoá thật (mặc định chỉ preview).
  --confirm-reset-gaze  Token bắt buộc đi cùng --apply.
  --skip-backup         Không tự chạy ./scripts/backup.sh trước khi xoá.
  -h, --help            Hiện trợ giúp.
EOF
}

mode=""
course_id=""
apply=false
confirmed=false
skip_backup=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --all)
            if [[ -n "$mode" ]]; then
                echo "Chỉ được chọn một trong --all hoặc --course-id." >&2
                exit 2
            fi
            mode="all"
            shift
            ;;
        --course-id)
            if [[ $# -lt 2 ]]; then
                echo "Thiếu UUID sau --course-id." >&2
                exit 2
            fi
            if [[ -n "$mode" ]]; then
                echo "Chỉ được chọn một trong --all hoặc --course-id." >&2
                exit 2
            fi
            mode="course"
            course_id="$2"
            shift 2
            ;;
        --apply)
            apply=true
            shift
            ;;
        --confirm-reset-gaze)
            confirmed=true
            shift
            ;;
        --skip-backup)
            skip_backup=true
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

if [[ -z "$mode" ]]; then
    usage >&2
    exit 2
fi

if [[ "$mode" == "course" ]]; then
    if [[ ! "$course_id" =~ ^[0-9a-fA-F-]{36}$ ]]; then
        echo "course-id không hợp lệ: $course_id" >&2
        exit 2
    fi
fi

if [[ "$apply" == true && "$confirmed" != true ]]; then
    echo "Thiếu --confirm-reset-gaze. Không xoá gì cả." >&2
    exit 2
fi

psql_base=(
    docker compose exec -T postgres
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
    -v ON_ERROR_STOP=1
    -P pager=off
)

scope_label="toàn bộ khoá học"
if [[ "$mode" == "course" ]]; then
    scope_label="khoá $course_id"
fi

echo "[reset-gaze] phạm vi: $scope_label"

if [[ "$mode" == "all" ]]; then
    "${psql_base[@]}" <<'SQL'
SELECT 'course_visits' AS table_name, count(*) AS rows FROM course_visits
UNION ALL
SELECT 'learning_sessions', count(*) FROM learning_sessions
UNION ALL
SELECT 'content_views', count(*) FROM content_views
UNION ALL
SELECT 'view_layouts', count(*) FROM view_layouts
UNION ALL
SELECT 'gaze_samples', count(*) FROM gaze_samples;
SQL
else
    "${psql_base[@]}" -v "course_id=$course_id" <<'SQL'
SELECT 'course_visits' AS table_name, count(*) AS rows
FROM course_visits cv
JOIN enrollments e ON e.id = cv.enrollment_id
WHERE e.course_id = :'course_id'
UNION ALL
SELECT 'learning_sessions', count(*)
FROM learning_sessions ls
JOIN course_visits cv ON cv.id = ls.course_visit_id
JOIN enrollments e ON e.id = cv.enrollment_id
WHERE e.course_id = :'course_id'
UNION ALL
SELECT 'content_views', count(*)
FROM content_views cview
JOIN learning_sessions ls ON ls.id = cview.session_id
JOIN course_visits cv ON cv.id = ls.course_visit_id
JOIN enrollments e ON e.id = cv.enrollment_id
WHERE e.course_id = :'course_id'
UNION ALL
SELECT 'view_layouts', count(*)
FROM view_layouts vl
JOIN content_views cview ON cview.id = vl.content_view_id
JOIN learning_sessions ls ON ls.id = cview.session_id
JOIN course_visits cv ON cv.id = ls.course_visit_id
JOIN enrollments e ON e.id = cv.enrollment_id
WHERE e.course_id = :'course_id'
UNION ALL
SELECT 'gaze_samples', count(*)
FROM gaze_samples gs
JOIN content_views cview ON cview.id = gs.content_view_id
JOIN learning_sessions ls ON ls.id = cview.session_id
JOIN course_visits cv ON cv.id = ls.course_visit_id
JOIN enrollments e ON e.id = cv.enrollment_id
WHERE e.course_id = :'course_id';
SQL
fi

if [[ "$apply" != true ]]; then
    echo "[reset-gaze] PREVIEW: chưa xoá gì. Thêm --apply --confirm-reset-gaze để thực hiện."
    exit 0
fi

if [[ "$skip_backup" != true ]]; then
    echo "[reset-gaze] backup database trước khi xoá..."
    ./scripts/backup.sh
fi

echo "[reset-gaze] bắt đầu xoá..."

if [[ "$mode" == "all" ]]; then
    "${psql_base[@]}" <<'SQL'
BEGIN;

WITH affected_lessons AS (
    SELECT DISTINCT lesson_id FROM learning_sessions
)
UPDATE background_jobs bj
SET status = 'cancelled',
    error = 'gaze data reset',
    finished_at = now(),
    updated_at = now()
FROM affected_lessons al
WHERE bj.kind = 'analyze_lesson'
  AND bj.status IN ('queued', 'processing')
  AND bj.lesson_id = al.lesson_id;

DELETE FROM course_visits;
-- Session cũ (trước khi có course_visits) có course_visit_id NULL.
DELETE FROM learning_sessions WHERE course_visit_id IS NULL;

COMMIT;
SQL
else
    "${psql_base[@]}" -v "course_id=$course_id" <<'SQL'
BEGIN;

WITH course_lessons AS (
    SELECT l.id
    FROM lessons l
    JOIN course_modules m ON m.id = l.module_id
    WHERE m.course_id = :'course_id'
),
affected_lessons AS (
    SELECT DISTINCT ls.lesson_id
    FROM learning_sessions ls
    WHERE ls.lesson_id IN (SELECT id FROM course_lessons)
)
UPDATE background_jobs bj
SET status = 'cancelled',
    error = 'gaze data reset',
    finished_at = now(),
    updated_at = now()
FROM affected_lessons al
WHERE bj.kind = 'analyze_lesson'
  AND bj.status IN ('queued', 'processing')
  AND bj.lesson_id = al.lesson_id;

DELETE FROM course_visits cv
USING enrollments e
WHERE cv.enrollment_id = e.id
  AND e.course_id = :'course_id';

-- Session cũ của các bài trong khóa nhưng chưa gắn course_visit.
DELETE FROM learning_sessions ls
USING lessons l
JOIN course_modules m ON m.id = l.module_id
WHERE ls.lesson_id = l.id
  AND m.course_id = :'course_id'
  AND ls.course_visit_id IS NULL;

COMMIT;
SQL
fi

echo "[reset-gaze] xong. Dữ liệu gaze/visualization của $scope_label đã bị xoá."
