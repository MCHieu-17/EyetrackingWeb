# Database — Eyetracking Learning Analytics

PostgreSQL schema cho dự án theo dõi hành vi học bằng eye-tracking.
Nguồn schema duy nhất là các file trong [`migrations/`](migrations/) — bắt đầu từ
`001_init.sql` (bảng, khóa ngoại, CHECK, index) rồi tới các migration tiệm tiến.

## Yêu cầu

- **PostgreSQL 13+** (dùng `gen_random_uuid()` và native partitioning)
- Kiểm tra: `psql --version`
- **Linux/GNU coreutils** nếu chạy `db/migrate.sh` trực tiếp trên host: script dùng
  `find -printf`, `sort -V`, `date +%s%3N`, `sha256sum` (không có fallback cho
  macOS/BSD). Trên macOS/Windows hãy chạy migration qua Docker
  (`docker compose run --rm migrate`) hoặc WSL.

## Cấu trúc

```
db/
├── README.md                     # file này
├── migrate.sh                    # runner migration local: schema_migrations, checksum, advisory lock
├── seed_dev_users.sql            # 3 tài khoản mẫu cho DEV — chạy THỦ CÔNG, không tự động
└── migrations/                   # chạy theo thứ tự tên (sort -V)
    ├── 001_init.sql              # schema nền: bảng, khóa, CHECK, index, partition gaze_events
    ├── 002_seed.sql              # seed bảng lookup (roles, permissions, statuses…)
    ├── 003_gaze_partitions.sql   # default partition + 12 tháng đầu + function bảo trì
    ├── 004_analytics.sql         # heatmap_aggregates, aoi_dwell_stats, engagement_scores
    ├── 005_calibration_model.sql # calibration_params: lưu model .ubj + mae/mapping version
    ├── …                         # 006→013: quiz, index, FK cascade, …
    ├── 014_drop_course_level.sql # bỏ cột courses.level
    ├── 015_drop_lesson_progress.sql # bỏ bảng lesson_progress
    ├── 016_quiz_items.sql        # bài tập trắc nghiệm là một loại lesson (kind)
    ├── 017_lesson_show_gaze_dot.sql # cờ lessons.show_gaze_dot (GV bật/tắt điểm nhìn)
    ├── 018_calibration_keep_latest.sql # chỉ giữ 1 bản ghi calibration / (user, device)
    ├── 019_quiz_allow_retry.sql  # cờ quiz_assignments.allow_retry (GV cho học viên làm lại)
    ├── 020_chat_sessions.sql     # (lịch sử) chat_sessions/chat_messages của trợ lý học tập
    ├── 021_course_show_gaze_dot.sql # cờ cấp KHÓA (courses.show_gaze_dot, thay 017) + gaze cho bài tập
    ├── 022_drop_dead_schema.sql  # bỏ bảng/cột không còn code dùng (oauth, permissions, email/phone/extra…)
    ├── 023_drop_chatbot.sql      # (lịch sử) gỡ schema chatbot cũ: chat_*, embedding, checkpoint*, pgvector
    ├── 024_chatbot_rag.sql       # dựng lại RAG: embedding 1024d + FTS hybrid + chat_*
    ├── 025_course_require_calibration.sql # cờ cấp khóa: bắt buộc hiệu chỉnh trước khi học
    └── 026_gaze_raw_and_aoi.sql  # gaze raw viewport + AOI DOM-anchored + gaze_aoi_hits
```

> **Chatbot RAG đã được dựng lại.** `023_drop_chatbot.sql` là migration lịch sử
> gỡ bản chatbot cũ; `024_chatbot_rag.sql` tạo schema mới:
> - `lesson_content_embedding` (Qwen3-Embedding-0.6B, `vector(1024)`, HNSW cosine)
>   + `content_tsv` (Postgres FTS, unaccent + đ→d) cho hybrid search;
> - `lesson_contents.embedding_status/embedding_error/embedding_updated_at`;
> - `chat_sessions`/`chat_messages` cho lịch sử hiển thị.
>
> `pgvector`, `pg_trgm`, `unaccent` được bật lại ở `024`. DB dựng mới chạy qua
> `023` rồi `024` nên schema cuối cùng có đầy đủ bảng RAG.

> **Cờ điểm nhìn thuộc KHÓA HỌC**: `courses.show_gaze_dot` quyết định sinh viên có
> thấy chấm điểm nhìn khi học **mọi bài giảng VÀ bài tập** của khóa. Cột
> `lessons.show_gaze_dot` (017) đã bị bỏ ở 021; khóa có cờ `true` khi mọi bài giảng
> của khóa đang bật (đúng giá trị công tắc cấp khóa trước nâng cấp).
>
> **Cờ bắt buộc hiệu chỉnh**: `courses.require_calibration` (025) mặc định `true`.
> Tắt = sinh viên vào thẳng trang học, không bật camera và không ghi gaze.
>
> **Gaze RAW + AOI DOM-anchored (026)**:
> - `gaze_raw_samples`: gaze RAW theo **viewport**, cho phép `gaze_x/gaze_y < 0`
>   hoặc `> 1` khi nhìn ra ngoài màn hình. Partition theo tháng, **không xoá
>   partition cũ**. Backend downsample theo `GAZE_RAW_HZ` (mặc định 15Hz).
>   `status='no_face'` lưu `gaze_x/gaze_y = NULL` (không dùng sentinel `-1,-1`).
> - `learning_sessions.viewport_*` + `calibration_*`: viewport lúc lấy mẫu phải
>   **bằng** viewport lúc calibration. DB có CHECK; API trả `409 viewport_mismatch`.
> - `aoi_definitions`: catalog AOI toàn hệ thống (`code`, `name`, `parent_id`,
>   `selector`). Không lưu toạ độ cố định.
> - `aoi_layout_snapshots` + `aoi_layout_rects`: frontend đo
>   `getBoundingClientRect()` của mọi `[data-aoi]` và gửi lên theo từng layout.
>   Một `aoi_code` có thể có nhiều rect (nhiều bong bóng chat).
> - `gaze_aoi_hits`: bảng **derived** (sample ↔ AOI), rebuild từ raw + snapshot
>   rects. Thêm AOI mới sau khi đã thu dữ liệu vẫn map lại được.
> - `aoi_regions`/`aoi_dwell_stats`/`lesson_contents.aoi_source` vẫn được giữ cho
>   AOI nội dung slide sau này; backend hiện không dùng.
>
> **Gaze của bài tập**: bài tập trắc nghiệm không có `lesson_contents`, nên dòng gaze
> của bài tập lưu `gaze_events.lesson_content_id = NULL`, `surface = 'quiz'` với
> toạ độ chuẩn hoá theo **viewport** (bài giảng: `surface = 'slide'`, toạ độ theo
> ảnh slide). Tổng hợp mức phiên nằm ở `gaze_session_stats` (bài tập không có
> `gaze_slide_stats`/heatmap).

> **Calibration không lưu lịch sử**: mỗi lần hiệu chỉnh lại sẽ **ghi đè** bản ghi
> cũ của (user, thiết bị) — `calibration_params` giữ đúng 1 dòng, kèm 1 dòng
> `calibration_sessions`. Model `.ubj` cũ bị thay thế hoàn toàn (xem
> `POST /api/calibrations` và migration `018`).

Sơ đồ partition `gaze_events` + `gaze_raw_samples` được bảo trì bằng
`scripts/create_partitions.sh` (xem mục "Bảo trì partition" bên dưới).

## Có 2 cách cài database

1. **Docker (`docker-compose.yml`)** — nhanh, sạch, khuyến nghị cho dev.
2. **PostgreSQL native (psql)** — khi đã có Postgres cài trực tiếp trên máy.

Migrations chạy qua `db/migrate.sh` trong container `migrate`. Runner ghi lại
file đã áp vào bảng `schema_migrations` và **chỉ chạy file chưa áp**; file đã áp mà
đổi nội dung thì dừng ngay. Mọi file **vẫn phải idempotent** — đó là điều kiện để
DB cũ (chưa có bảng tracking) chạy được trọn bộ một lần rồi ghi dấu.

## Quy tắc migration

1. **Không sửa file migration đã áp.** Muốn đổi schema → thêm file mới
   (`025_ten_moi.sql`). Runner từ chối chạy nếu file đã áp bị đổi nội dung.
   Nếu đang dev và thật sự muốn sửa file cũ, reset DB local bằng
   `./scripts/reset_db.sh` rồi chạy lại.
2. **Mọi file phải idempotent** — chạy lại nhiều lần không lỗi, không nhân đôi dữ liệu.
3. **Thứ tự quan trọng.** Trong một file: ví dụ `016` phải backfill (tách bản trùng)
   TRƯỚC khi tạo unique index — nếu không, DB đang có bản trùng sẽ gãy ngay.
   Giữa các file: giữ nguyên dãy số, thêm file mới thì tăng số.
4. **Thao tác phá huỷ dữ liệu** (`TRUNCATE`, đổi số chiều vector, `DROP`) phải ghi rõ
   hệ quả trong comment (ví dụ `012` xoá toàn bộ embedding và bắt buộc re-ingest).

Service `migrate` **exit 1 ⇒ compose huỷ lần chạy đó**; các container cũ vẫn chạy.
Gặp lỗi này thì đọc log: `docker logs eyetracking-migrate 2>&1 | tail -30`.

---

## Cách 1: Docker Compose

### Tạo database (lần đầu)

```bash
docker compose up -d postgres
```

Migrations **không** chạy qua `docker-entrypoint-initdb.d` (compose không bind
mount `./db/migrations`). Thay vào đó, service một-lần `migrate`
(`Dockerfile.migrations` → `db/migrate.sh`) chạy các file **chưa áp** theo thứ tự
tên file. Kiểm tra:

```bash
# chạy migrations (một lần) rồi list bảng
docker compose run --rm migrate
docker compose exec postgres psql -U postgres -d eyetracking -c '\dt'
```

- Host port: **5435** (container 5432) → kết nối từ host dùng `-p 5435`.
- Dữ liệu nằm trong volume `pgdata`, **không mất khi `down`**.

### Chạy lại seed / migrate thủ công

```bash
# seed lookup (roles, permissions, statuses…) — file nằm trong image migrations
docker compose run --rm migrate bash -c \
    'psql -h postgres -U $PGUSER -d $PGDATABASE -f /migrations/002_seed.sql'

# tài khoản mẫu cho dev (KHÔNG tự động chạy — mật khẩu mặc định Password123!)
./scripts/seed_dev.sh
```

### Xóa database (xoá hết dữ liệu)

```bash
docker compose down -v        # -v: XÓA volume pgdata → xóa toàn bộ dữ liệu
```

> Dùng `docker compose down` (không `-v`) nếu chỉ muốn dừng mà **giữ** dữ liệu.

### Khởi động lại database (giữ dữ liệu)

```bash
docker compose up -d postgres
```

---

## Tài khoản mẫu (CHỈ cho dev — `seed_dev_users.sql`)

⚠️ **Migrations KHÔNG tạo tài khoản người dùng.** Tài khoản mẫu nằm ở
`db/seed_dev_users.sql`, **chỉ chạy thủ công** khi dev:

```bash
./scripts/seed_dev.sh
```

| Vai trò | Email | Khả năng |
|---|---|---|
| Admin | `admin@school.edu.vn` | toàn quyền |
| Giáo viên | `teacher@school.edu.vn` | quản lý khóa học + analytics |
| Sinh viên | `student@school.edu.vn` | học + xem heatmap cá nhân |

- Mật khẩu mặc định: `Password123!`.
- Cả 3 được đặt `must_change_password = true` → **bắt buộc đổi mật khẩu ở lần
  đăng nhập đầu tiên** (`POST /api/auth/change-password`).

Kiểm tra nhanh:

```bash
docker compose exec -T postgres psql -U postgres -d eyetracking -c '\dt'
docker compose exec -T postgres psql -U postgres -d eyetracking -c "SELECT code FROM roles;"
docker compose exec -T postgres psql -U postgres -d eyetracking -c "SELECT email FROM users;"
docker compose exec -T postgres psql -U postgres -d eyetracking \
  -c "SELECT inhrelid::regclass FROM pg_inherits WHERE inhparent = 'gaze_events'::regclass;"
```

---

## Bảo trì partition gaze_events + gaze_raw_samples

`003_gaze_partitions.sql` tạo function `create_gaze_partitions(months_ahead)`;
`026_gaze_raw_and_aoi.sql` tạo `create_gaze_raw_partitions(months_ahead)`.
Cả hai tạo sẵn 12 partition tháng đầu. Về sau chạy định kỳ:

```bash
./scripts/create_partitions.sh        # mặc định 12 tháng
./scripts/create_partitions.sh 24     # hoặc chỉ định số tháng
```

**Không xoá partition cũ** — dữ liệu raw được giữ theo tháng để phân tích lại.
Dữ liệu rơi ngoài các tháng đã tạo sẽ vào `gaze_events_default` /
`gaze_raw_samples_default` (không mất, nhưng nên xử lý sớm). Nếu cần tạo
partition trùng khoảng dữ liệu đang nằm trong default:

```sql
CREATE TABLE tmp AS SELECT * FROM gaze_events_default
    WHERE event_time >= '2026-12-01' AND event_time < '2027-01-01';
DELETE FROM gaze_events_default
    WHERE event_time >= '2026-12-01' AND event_time < '2027-01-01';
SELECT create_gaze_partitions(3);   -- tạo partition tháng 12
INSERT INTO gaze_events SELECT * FROM tmp;
DROP TABLE tmp;
```

## Hệ tọa độ (quan trọng)

- `gaze_events.gaze_x/gaze_y` và `aoi_regions.x_min..y_max` đều **chuẩn hóa [0,1]** —
  khớp với output `WS /session/{sid}/stream` của `services/gaze/server.py` (đã trả về [0,1]).
- Muốn tọa độ pixel: nhân với `devices.screen_width_px / screen_height_px`.
- Không CHECK biên [0,1] trên gaze: filter OneEuro có thể overshoot nhẹ;
  clamp ở tầng application trước khi ghi DB.

## Vận hành

- **Insert gaze**: WebSocket `/session/{sid}/stream` chạy ~20 fps → chỉ ghi DB sau khi
  downsample còn ~2–4 Hz (khối lượng: 1 lớp 30 học viên × 20 buổi ≈ vài triệu dòng).
- **Aggregate** (`heatmap_aggregates`, `aoi_dwell_stats`, `engagement_scores`):
  tính bằng batch job ngoài giờ học, không tính realtime trên `gaze_events`.
- **Xóa dữ liệu cũ**: `DROP` partition tháng cũ thay vì `DELETE` — tức thì, không bloat.
- **Timezone**: partition boundary tính theo timezone của phiên chạy migration;
  nên đặt timezone server là UTC cho nhất quán (docker-compose đã set `TZ: UTC`).

## Thay đổi so với thiết kế ban đầu

| Thay đổi | Lý do |
|---|---|
| `gaze_x_px/gaze_y_px` → `gaze_x/gaze_y` chuẩn hóa [0,1] | Khớp output `WS /session/{sid}/stream`; heatmap/AOI không phụ thuộc độ phân giải màn hình |
| AOI thêm `CHECK` biên + `x_min < x_max` | Tọa độ giáo viên vẽ phải hợp lệ, cùng hệ [0,1] với gaze |
| Thêm UNIQUE: `modules(course_id, order_index)`, `lessons(module_id, order_index)`, `aoi_dwell_stats(session_id, aoi_region_id)` | Chống trùng thứ tự / trùng thống kê |
| `heatmap_aggregates`: 2 partial unique index + CHECK scope↔student_id | UNIQUE thường không hoạt động với `student_id NULL` (scope='class') |
| CHECK cho các cột VARCHAR "enum": `enrollments.status`, `calibration_sessions.status`, `course_teachers.role`, `heatmap_aggregates.scope`, `learning_sessions.status` | Nhất quán ràng buộc, không cần thêm lookup table |
| **Slide-only**: bỏ `lesson_types`, `lesson_type_id`, `duration_seconds`, `lesson_contents.content_type`, `start_time_sec`, `end_time_sec` | Nội dung khóa học chỉ gồm slide: `lessons` = bài học (deck slides), `lesson_contents` = từng slide (`image_url`) |
| `lessons.kind` (`lesson` \| `quiz`) + `quiz_assignments` 1:1 | Bài tập trắc nghiệm là một item **cùng cấp** bài học trong chương; dùng chung `order_index` nên thứ tự bài học/bài tập được trộn. Item `quiz` không có slide và không ghi dữ liệu gaze. `quiz_assignments.due_at` cho phép NULL (hạn nộp tùy chọn). |
| `quiz_assignments.allow_retry` | Giáo viên cho phép học viên làm lại: **mỗi học viên vẫn chỉ giữ 1 lượt** (`quiz_attempts` UNIQUE theo assignment+student), lượt cũ bị xoá và `quiz_attempt_sessions.started_at` đặt lại để đồng hồ chạy lại từ đầu. |
| `learning_sessions` thêm `status` | Phân biệt phiên hoàn tất / bị hủy khi tính engagement |
| Roles: 3 role `admin`, `teacher`, `student` | Theo yêu cầu dự án |