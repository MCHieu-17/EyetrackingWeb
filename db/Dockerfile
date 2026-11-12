# One-shot migrations runner cho stack local.
# Chạy 1 lần trên cùng compose network rồi exit.
#
# Logic nằm ở db/migrate.sh: bảng `schema_migrations`, chỉ chạy file chưa áp,
# chặn sửa file đã áp, advisory lock chống chạy song song.
# Xem db/README.md mục "Migrations".
#
# Build context là ./db (xem docker-compose.yml):
#   docker build -t eyelearning-migrations:local ./db
#
# Env: PGHOST (mặc định postgres), PGUSER (postgres), PGDATABASE (eyetracking),
#      PGPASSWORD (bắt buộc — phải KHỚP mật khẩu lúc volume postgres được tạo).
FROM postgres:16.4

ENV PGHOST=postgres \
    PGUSER=postgres \
    PGDATABASE=eyetracking

COPY migrations /migrations
COPY migrate.sh /migrate.sh
COPY chatbot_role.sql /chatbot_role.sql
COPY admin_reader_role.sql /admin_reader_role.sql

CMD ["bash", "/migrate.sh", "/migrations"]
