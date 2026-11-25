import math
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Nguồn duy nhất: file .env ở gốc repo (bỏ hẳn giá trị mẫu nhúng trong code).
ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "GazeEdu API"
    debug: bool = False
    # Namespace media/Redis; fallback khi chưa có app_metadata.db_instance_id.
    app_instance_id: str = "dev"

    # Bắt buộc — phải có trong .env (không nhúng mẫu trong code).
    database_url: str
    jwt_secret: str
    cors_origins: str
    ai_http_url: str
    # Tên weights UniGaze đang dùng, chỉ để ghi metadata version calibration.
    # Để trống giữ nhãn tương thích `ubj-linreg-v3-b16`.
    unigaze_model: str = ""

    # Connection pool PostgreSQL. max_overflow được suy ra từ chênh lệch
    # db_pool_max - db_pool_min để tổng kết nối tối đa đúng bằng db_pool_max.
    # Với nhiều uvicorn worker, đặt pool mỗi process nhỏ (4-10) để tổng
    # connection vẫn nằm dưới max_connections của Postgres.
    db_pool_min: int = 4
    db_pool_max: int = 10
    # Fail-fast khi pool cạn: request nhận 503 thay vì treo 30s.
    db_pool_timeout: float = 5.0
    # statement_timeout cho API; worker nặng có thể override bằng env riêng.
    db_statement_timeout_ms: int = 15000
    # 0 = tắt prepared statement cache để tương thích PgBouncer transaction
    # pooling. Mặc định bật khi nối trực tiếp Postgres; profile `pgbouncer`
    # phải đặt lại 0 trong .env.
    db_prepared_statement_cache_size: int = 64

    # Chatbot RAG service (internal). Backend gọi qua HTTP + token nội bộ.
    chatbot_url: str = ""
    chatbot_url_docker: str = ""
    chatbot_internal_token: str = ""
    chatbot_timeout_seconds: float = 120
    chatbot_ingest_timeout_seconds: float = 600
    chatbot_ingest_attempts: int = 3
    chatbot_ingest_backoff_seconds: float = 5
    # Chia danh sách slide thành từng batch để một request không chạy quá lâu
    # (VLM + embedding tuần tự) và mỗi batch kịp cập nhật trạng thái.
    chatbot_ingest_batch_size: int = 8

    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # Cookie auth (httpOnly) — 2a hybrid: access memory + refresh httpOnly
    # Mặc định an toàn prod: Secure=True khi không DEBUG, dev tự hạ xuống
    cookie_secure: bool | None = None  # None = tự suy ra từ debug (True prod, False dev/localhost)
    cookie_samesite: str = "lax"  # lax đủ cho same-site rewrite, strict nếu muốn
    cookie_domain: str | None = None  # None = host-only (khuyến nghị cho rewrite)

    # SMTP gửi OTP đăng nhập sinh viên. Để trống SMTP_HOST → chưa cấu hình;
    # route OTP trả 503 (trừ khi DEBUG + OTP_DEV_ECHO bật để test local).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    # Trống → dùng SMTP_USER làm địa chỉ From.
    smtp_from: str = ""
    smtp_from_name: str = "GazeEdu"
    # Trống → dùng địa chỉ From. Đặt hộp thư có người theo dõi để nhận phản hồi.
    smtp_reply_to: str = ""
    smtp_use_ssl: bool = False
    smtp_starttls: bool = True
    smtp_timeout_seconds: float = 15

    # OTP đăng nhập sinh viên NEU: email trường + mã 6 số dùng một lần.
    # 15 phút: Microsoft 365 có thể giữ thư từ người gửi mới vài phút trước
    # khi chuyển vào Inbox/Junk; 10 phút dễ hết hạn trước khi sinh viên thấy mã.
    otp_ttl_seconds: int = 900
    otp_resend_seconds: int = 60
    otp_max_attempts: int = 5
    otp_max_per_email_per_hour: int = 10
    otp_max_per_ip_per_hour: int = 40
    # Danh sách domain email được phép, phẩy phân tách.
    otp_allowed_domains: str = "st.neu.edu.vn"
    # Phần local (mã sinh viên) phải khớp regex này.
    otp_student_id_pattern: str = r"^\d{8}$"
    # Trống → fallback JWT_SECRET khi tính HMAC cho mã OTP.
    otp_hash_secret: str = ""
    # Chỉ dùng dev: log mã OTP khi SMTP chưa cấu hình (DEBUG bắt buộc).
    otp_dev_echo: bool = False

    @property
    def cookie_secure_resolved(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return not self.debug

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host.strip())

    @property
    def smtp_from_resolved(self) -> str:
        """Địa chỉ From: SMTP_FROM nếu có, fallback SMTP_USER."""
        return self.smtp_from.strip() or self.smtp_user.strip()

    @property
    def smtp_reply_to_resolved(self) -> str:
        """Địa chỉ Reply-To: SMTP_REPLY_TO nếu có, fallback địa chỉ From."""
        return self.smtp_reply_to.strip() or self.smtp_from_resolved

    @property
    def otp_allowed_domain_list(self) -> list[str]:
        return [
            domain.strip().lower()
            for domain in self.otp_allowed_domains.split(",")
            if domain.strip()
        ]

    @property
    def otp_hash_secret_resolved(self) -> str:
        return self.otp_hash_secret or self.jwt_secret

    # Dải mạng proxy tin cậy (CIDR, phẩy phân tách) — chỉ khi request đến từ
    # peer trong dải này mới tin header X-Forwarded-For (chống giả mạo IP).
    # Production: dải mạng docker nội bộ nơi nginx kết nối backend.
    # Để trống → không tin bất kỳ header nào (an toàn mặc định).
    trusted_proxy_ips: str = ""

    # Redis (tùy chọn). Dùng cho rate-limit + cache analytics. Để trống → fallback
    # in-memory (1 process, dev/test). Ví dụ: redis://localhost:6379/0
    redis_url: str = ""

    # Thư mục lưu slide ảnh render từ PDF (mount StaticFiles tại /media).
    media_dir: str = "media"
    # Cloudflare R2 (S3-compatible). Để trống toàn bộ để dùng volume local.
    r2_account_id: str = ""
    r2_bucket_name: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_public_url: str = ""
    # Dung lượng tối đa một file slide upload (bytes). 50MB khớp nginx/FE.
    max_upload_bytes: int = 50 * 1024 * 1024
    # PDF sau chuyển đổi có thể lớn hơn file nguồn (ảnh/font nhúng).
    max_pdf_bytes: int = 100 * 1024 * 1024
    # Trần số trang PDF sau khi chuyển đổi.
    max_slide_pages: int = 150
    max_slide_render_pixels: int = 25_000_000

    # Chuyển đổi PPTX/PPT/ODP -> PDF bằng LibreOffice headless.
    libreoffice_binary: str = "soffice"
    libreoffice_timeout_seconds: int = 120

    # Worker phân tích metrics/analysis.
    worker_poll_seconds: float = 5.0
    # Job analysis processing quá lâu (worker chết) được đưa lại hàng đợi.
    worker_stale_seconds: int = 600

    # Worker đồng bộ index RAG từ background_jobs(kind=index_slides).
    embedding_worker_poll_seconds: float = 0.5
    # Số job index claim mỗi vòng; mỗi job là một lesson độc lập.
    embedding_worker_concurrency: int = 2
    # Job running quá lâu (worker chết) được đưa lại pending/failed.
    embedding_worker_stale_seconds: int = 600

    # Worker xử lý background_jobs(kind=import_slides).
    content_worker_poll_seconds: float = 3.0
    # Job processing quá lâu (worker chết) sẽ được đưa lại hàng đợi.
    content_worker_stale_seconds: int = 600

    # Retention gaze samples: row cũ hơn số ngày này bị xoá bởi maintenance.
    # Đặt 0 để tắt (không khuyến nghị trên đĩa nhỏ).
    gaze_retention_days: int = 180

    # Tần số lấy mẫu gaze (FPS) — nguồn duy nhất cho cả pipeline: backend trả
    # qua /api/config, gaze service throttle theo giá trị này, worker suy ra
    # ngưỡng gap khi cộng dồn dwell.
    gaze_fps: int = 15

    @field_validator("gaze_fps")
    @classmethod
    def _validate_gaze_fps(cls, value: int) -> int:
        if not 1 <= value <= 60:
            raise ValueError("GAZE_FPS phải nằm trong khoảng 1..60")
        return value

    # Ngưỡng dwell để phân loại một lượt xem là "đủ ngưỡng". Mặc định vẫn
    # hiển thị mọi lượt xem (kể cả ngắn hơn ngưỡng); giá trị này dùng cho
    # badge/filter "Chỉ lượt >= ngưỡng" trong tab Trực quan hoá.
    content_view_min_dwell_ms: int = 1000

    # Trang Truy vấn CSDL cho admin (chỉ đọc). Để trống ở dev → fallback
    # DATABASE_URL + read-only transaction. Production nên trỏ tới role chỉ
    # đọc (admin_reader) để tránh dùng nhầm tài khoản có quyền ghi.
    admin_db_url: str = ""
    admin_db_statement_timeout_ms: int = 10000
    admin_db_lock_timeout_ms: int = 2000
    admin_db_idle_in_transaction_timeout_ms: int = 15000
    admin_db_max_rows: int = 500
    admin_db_schema_cache_seconds: int = 60
    admin_db_max_sql_length: int = 20000
    admin_db_max_cell_chars: int = 10000
    admin_db_max_response_bytes: int = 5 * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def gaze_max_gap_ms(self) -> int:
        """Ngưỡng gap để cộng dồn dwell: tối thiểu 250ms, hoặc 3 chu kỳ lấy mẫu."""
        return max(250, math.ceil(3000 / self.gaze_fps))

    @property
    def chatbot_url_resolved(self) -> str:
        """URL chatbot: ưu tiên CHATBOT_URL (host dev), fallback bản Docker."""
        return self.chatbot_url or self.chatbot_url_docker

    @property
    def chatbot_ready(self) -> bool:
        return bool(self.chatbot_url_resolved and self.chatbot_internal_token)

    @property
    def media_path(self) -> Path:
        return Path(self.media_dir).resolve()

    @property
    def r2_enabled(self) -> bool:
        values = (
            self.r2_account_id,
            self.r2_bucket_name,
            self.r2_access_key_id,
            self.r2_secret_access_key,
            self.r2_public_url,
        )
        if any(values) and not all(values):
            raise RuntimeError("Cấu hình R2 chưa đầy đủ")
        return all(values)

    @property
    def r2_endpoint_url(self) -> str:
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
