from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Nguồn duy nhất: file .env ở gốc repo (bỏ hẳn giá trị mẫu nhúng trong code).
ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "GazeEdu API"
    debug: bool = False
    # Namespace cho media/Redis; Phase 6 sẽ đọc từ app_metadata.db_instance_id.
    app_instance_id: str = "dev"

    # Bắt buộc — phải có trong .env (không nhúng mẫu trong code).
    database_url: str
    jwt_secret: str
    cors_origins: str
    ai_http_url: str

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
    # pooling. Đặt >0 nếu kết nối trực tiếp Postgres và cần tối ưu.
    db_prepared_statement_cache_size: int = 0

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

    # Microsoft 365 / Outlook OAuth (single tenant của trường).
    # Để trống CLIENT_ID/SECRET/TENANT_ID → tắt đăng nhập Outlook.
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant_id: str = ""
    microsoft_redirect_uri: str = (
        "http://localhost:3000/api/auth/oauth/microsoft/callback"
    )
    # Danh sách domain email được phép, phẩy phân tách. Trống = cho phép mọi
    # tài khoản thuộc tenant (khuyến nghị vì đã giới hạn single tenant).
    microsoft_allowed_domains: str = ""
    # Origin frontend để redirect sau callback OAuth.
    frontend_url: str = "http://localhost:3000"

    @property
    def cookie_secure_resolved(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return not self.debug

    @property
    def microsoft_oauth_enabled(self) -> bool:
        return bool(
            self.microsoft_client_id
            and self.microsoft_client_secret
            and self.microsoft_tenant_id
        )

    @property
    def microsoft_allowed_domain_list(self) -> list[str]:
        return [
            domain.strip().lower()
            for domain in self.microsoft_allowed_domains.split(",")
            if domain.strip()
        ]

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

    # Worker đồng bộ embedding/RAG ingest từ bảng embedding_jobs.
    embedding_worker_poll_seconds: float = 5.0
    # Job running quá lâu (worker chết) được đưa lại pending/failed.
    embedding_worker_stale_seconds: int = 600

    # Worker xử lý slide_import_jobs.
    content_worker_poll_seconds: float = 3.0
    # Job processing quá lâu (worker chết) sẽ được đưa lại hàng đợi.
    content_worker_stale_seconds: int = 600

    # Retention gaze samples: partition cũ hơn số ngày này bị drop bởi
    # maintenance. Đặt 0 để tắt (không khuyến nghị trên đĩa nhỏ).
    gaze_retention_days: int = 180

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

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
