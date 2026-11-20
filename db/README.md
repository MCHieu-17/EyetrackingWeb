# Database — EyeLearning baseline

Schema chuẩn là **một baseline sạch**:

```
db/migrations/
├── 001_baseline.sql                 # generation 12: 24 bảng lõi + view + metadata
├── 002_email_otp.sql                # generation 13: email_otps, bỏ oauth_accounts
├── 003_aoi_single_label.sql         # bỏ gaze_samples.aoi_codes, slides.aoi_suggestions
├── 004_content_view_aoi_stats.sql   # thêm content_views.aoi_stats
└── 005_current_viewport_only.sql    # bỏ original-v1/visible_rect, chỉ viewport hiện tại
```

`001_baseline.sql` chứa schema generation 12: 24 bảng lõi, index, view outline
và metadata. Baseline gộp luôn `course_visits`,
`learning_sessions.course_visit_id`, `aois.label` và `gaze_samples.aoi_label`.
Không còn versioning, partition gaze, `user_identities`, `roles` hay các bảng
job riêng.

`002_email_otp.sql` thay `oauth_accounts` bằng `email_otps`, thêm
`users.email_verified_at` và nâng `schema_generation='13'`.
`003_aoi_single_label.sql` bỏ `gaze_samples.aoi_codes` và
`slides.aoi_suggestions`. `004_content_view_aoi_stats.sql` thêm thống kê AOI
dẫn xuất. `005_current_viewport_only.sql` chuyển layout cũ từ hệ calibration
sang viewport hiện tại rồi bỏ các cột bù trừ zoom.

Khi schema thay đổi, thêm file mới `00x_...sql`; **không sửa file đã áp**.
Schema generation hiện tại là `13` (giá trị trong `app_metadata`).

## Runner

`db/migrate.sh` là runner duy nhất cho dev/CI. Image `eyelearning-migrations:local`
build từ `db/Dockerfile` (context `./db`), service một-lần `migrate` trong compose.

- Một kết nối `psql` giữ `pg_advisory_lock` suốt lượt chạy.
- Mỗi migration + checksum record commit trong một transaction.
- File đã áp mà checksum đổi → fail.
- Database có `schema_migrations` chứa file lạ, hoặc có bảng public nhưng chưa
  có `schema_migrations` → fail và yêu cầu reset có guard.
- Không còn `MIGRATE_BASELINE`, không tự đoán schema.

```bash
docker compose run --rm migrate
```

Runner tự tạo/cập nhật role `chatbot_reader` sau migrations khi
`CHATBOT_DB_USER` + `CHATBOT_DB_PASSWORD` có trong môi trường (service `migrate`
trong compose luôn truyền hai biến này). Vì vậy reset DB xong không cần chạy
tay. Khi cần cấp lại quyền/đổi password ngay, chạy lại migration (idempotent):

```bash
docker compose run --rm migrate
```

## Reset development

Mặc định là preview, không thay đổi gì:

```bash
./scripts/reset_db.sh
```

Áp dụng thật (bắt buộc đủ hai tham số trùng nhau):

```bash
./scripts/reset_db.sh --apply --database eyetracking --confirm-reset eyetracking
```

Guard kiểm tra Docker local socket, Compose project/service/config/working dir,
database đích, DSN backend, ownership và kết nối còn lại. Không dùng
`docker compose down -v`, không xóa volume, không đụng database khác.

Sau reset, `docker compose up -d` sẽ chạy lại service `migrate` (baseline +
generation 13). Nếu muốn seed tài khoản dev:

```bash
./scripts/seed_dev.sh
```

## Seed development

```bash
./scripts/seed_dev.sh
```

Tạo 3 tài khoản dev nếu chưa có. **Không ghi đè mật khẩu** của tài khoản đã tồn
tại. Mật khẩu mặc định: `Password123!`.

## Retention gaze

`gaze_samples` không còn partition. Sample cũ hơn `GAZE_RETENTION_DAYS`
(mặc định 180 ngày) được xoá bởi:

```bash
./scripts/maintenance.sh
```

## Quy tắc schema

- Baseline đã khóa checksum; mọi thay đổi schema phải là migration mới
  (`004_...`).
- Không sửa file đã áp.
- Không dùng `Base.metadata.create_all()` thay baseline.
