# Database — EyeLearning baseline

Schema chuẩn là **một baseline sạch**:

```
db/migrations/
└── 001_baseline.sql                 # toàn bộ schema + reference seed (roles, ...)
```

`001_baseline.sql` là bản gộp cuối cùng của schema, constraint, index, trigger,
view, partition, bảng `user_identities` (đăng nhập Microsoft 365) và dữ liệu
tham chiếu tối thiểu. Các migration lịch sử và file delta cũ đã được gộp vào
baseline; lịch sử vẫn còn trong Git. Không có chuỗi “drop legacy rồi dựng lại”,
không tự baseline/replay.

Khi schema thay đổi, thêm file mới `002_...sql`; **không sửa file đã áp**.
Schema generation hiện tại là `6` (giá trị trong `app_metadata`).

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
generation 6). Nếu muốn seed tài khoản dev:

```bash
./scripts/seed_dev.sh
```

## Seed development

```bash
./scripts/seed_dev.sh
```

Tạo 3 tài khoản dev nếu chưa có. **Không ghi đè mật khẩu** của tài khoản đã tồn
tại. Mật khẩu mặc định: `Password123!`.

## Partition

`gaze_samples` partition theo tháng `event_time`:

```bash
./scripts/create_partitions.sh        # mặc định 3 tháng
./scripts/create_partitions.sh 12
```

Baseline tạo default partition + tháng trước/current/3 tháng tới. Không xóa
partition cũ.

## Quy tắc sau Phase 6

- Baseline đã khóa checksum; mọi thay đổi schema phải là migration mới
  (`002_...`).
- Không sửa file đã áp.
- Không dùng `Base.metadata.create_all()` thay baseline.
