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
    testing: bool = False

    # Bắt buộc — phải có trong .env (không nhúng mẫu trong code).
    database_url: str
    jwt_secret: str
    cors_origins: str
    ai_http_url: str

    # Chatbot RAG service (internal). Backend gọi qua HTTP + token nội bộ.
    chatbot_url: str = ""
    chatbot_url_docker: str = ""
    chatbot_internal_token: str = ""
    chatbot_timeout_seconds: float = 120
    chatbot_ingest_timeout_seconds: float = 600
    chatbot_ingest_attempts: int = 3
    chatbot_ingest_backoff_seconds: float = 5

    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # Cookie auth (httpOnly) — 2a hybrid: access memory + refresh httpOnly
    # Mặc định an toàn prod: Secure=True khi không DEBUG, dev tự hạ xuống
    cookie_secure: bool | None = None  # None = tự suy ra từ debug (True prod, False dev/localhost)
    cookie_samesite: str = "lax"  # lax đủ cho same-site rewrite, strict nếu muốn
    cookie_domain: str | None = None  # None = host-only (khuyến nghị cho rewrite)

    @property
    def cookie_secure_resolved(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return not self.debug

    gaze_downsample_hz: float = 4.0
    gaze_batch_max: int = 2000

    # Dải mạng proxy tin cậy (CIDR, phẩy phân tách) — chỉ khi request đến từ
    # peer trong dải này mới tin header X-Forwarded-For (chống giả mạo IP).
    # Production: dải mạng docker nội bộ nơi nginx kết nối backend.
    # Để trống → không tin bất kỳ header nào (an toàn mặc định).
    trusted_proxy_ips: str = ""

    # Redis (tùy chọn). Dùng cho rate-limit + cache analytics. Để trống → fallback
    # in-memory (1 process, dev/test). Ví dụ: redis://localhost:6379/0
    redis_url: str = ""
    # TTL (giây) cho cache heatmap analytics.
    heatmap_cache_ttl_seconds: int = 60
    # Khoảng cách tối thiểu (giây) giữa 2 lần refresh_aggregates cho cùng 1 lesson.
    aggregate_refresh_throttle_seconds: int = 10

    # Thư mục lưu slide ảnh render từ PDF (mount StaticFiles tại /media).
    media_dir: str = "media"
    # Cloudflare R2 (S3-compatible). Để trống toàn bộ để dùng volume local.
    r2_account_id: str = ""
    r2_bucket_name: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_public_url: str = ""
    # Dung lượng tối đa một file PDF upload (bytes). 50MB khớp giới hạn FE
    # (MAX_UPLOAD_BYTES) và đảm bảo render xong < ngưỡng ~100s của Cloudflare.
    max_pdf_bytes: int = 50 * 1024 * 1024
    # Trần số trang: render đồng bộ nên chặn sớm để không vượt timeout CF (524).
    max_pdf_pages: int = 150
    max_slide_render_pixels: int = 25_000_000

    # Tính điểm hoàn thành bài học theo tỷ lệ gaze trên trang.
    mastery_coverage_threshold: float = 0.85      # tỷ lệ gaze trên trang >= 85% → đủ trang
    mastery_key_weight: float = 0.85              # trọng số nhóm slide trọng tâm (còn lại 0.15)

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
