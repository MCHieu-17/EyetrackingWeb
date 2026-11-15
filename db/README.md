# Database — EyeLearning baseline

Schema chuẩn là **một baseline sạch**:

```
db/migrations/
└── 001_baseline.sql                 # 24 bảng lõi + view + metadata generation 12
```

`001_baseline.sql` chứa toàn bộ schema generation 12: 24 bảng lõi, index, view
outline và metadata. Baseline gộp luôn `course_visits`,
`learning_sessions.course_visit_id`, `gaze_samples.original_viewport_x/y`,
`view_layouts.coordinate_space/visible_rect`, `aois.label` và
`gaze_samples.aoi_label`. Không còn versioning, partition gaze,
`user_identities`, `roles` hay các bảng job riêng.

Khi schema thay đổi, thêm file mới `002_...sql`; **không sửa file đã áp**.
Schema generation hiện tại là `12` (giá trị trong `app_metadata`).

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
tay. Nếu cần cấp lại quyền/đổi password ngay:

```bash
./scripts/create_chatbot_role.sh
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
generation 12). Nếu muốn seed tài khoản dev:

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
  (`002_...`).
- Không sửa file đã áp.
- Không dùng `Base.metadata.create_all()` thay baseline.
