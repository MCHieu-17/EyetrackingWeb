# Database — EyeLearning baseline

Từ Phase 1, schema chuẩn là **một baseline sạch**:

```
db/migrations/
├── 001_baseline.sql        # toàn bộ schema, constraint, index, trigger, view, partition
└── 002_reference_seed.sql  # roles + cấu hình hệ thống; KHÔNG có tài khoản mẫu
```

Các migration lịch sử 001–030 đã được xóa khỏi cây chạy; lịch sử vẫn còn trong
Git. Không có chuỗi “drop legacy rồi dựng lại”, không tự baseline/replay.

## Runner

`db/migrate.sh` là runner duy nhất cho dev/test/CI:

- Một kết nối `psql` giữ `pg_advisory_lock` suốt lượt chạy.
- Mỗi migration + checksum record commit trong một transaction.
- File đã áp mà checksum đổi → fail.
- Database có `schema_migrations` chứa file lạ, hoặc có bảng public nhưng chưa
  có `schema_migrations` → fail và yêu cầu reset có guard.
- Không còn `MIGRATE_BASELINE`, không tự đoán schema.

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

## Test database

```bash
./scripts/test_db.sh          # tạo nếu chưa có, chạy baseline
./scripts/test_db.sh --reset  # drop/recreate có kiểm tra ownership
```

Database test mặc định: `eyelearning_refactor_test`. Không dùng
`eyetracking_test` cũ.

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

- Baseline đã khóa checksum; mọi thay đổi schema phải là migration mới.
- Không sửa file đã áp.
- Không dùng `Base.metadata.create_all()` thay baseline.
- Không chạy migration tự động trong pytest fixture.
