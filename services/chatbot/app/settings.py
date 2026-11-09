"""Cấu hình dùng chung cho chatbot.

Gom việc đọc biến môi trường về một chỗ và cung cấp `validate()` để fail-fast
lúc khởi động với thông báo rõ ràng (thay vì lỗi khó hiểu ở request đầu tiên).

`CHATBOT_DATABASE_URL` là DSN psycopg (postgresql://...), KHÔNG dùng hậu tố
+asyncpg. Fallback `DATABASE_URL`/`DATABASE_URL_DOCKER` để tương thích khi stack
chỉ cấu hình biến dùng chung với backend; nếu gặp +asyncpg thì tự bỏ hậu tố.
"""

import os
from pathlib import Path

ALLOWED_LLM = {"river"}
ALLOWED_EMBEDDING = {"local"}
ALLOWED_VLM = {"river"}

# Đường dẫn weights embedding local mặc định khi không đặt EMBEDDING_MODEL_PATH
# (trong Docker, .env trỏ tới volume /app/weights).
_DEFAULT_LOCAL_EMBED_PATH = Path("/app/weights/Qwen3-Embedding-0.6B")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def database_url() -> str:
    url = (
        _env("CHATBOT_DATABASE_URL")
        or _env("DATABASE_URL")
        or _env("DATABASE_URL_DOCKER")
    )
    if not url:
        raise RuntimeError(
            "Thiếu CHATBOT_DATABASE_URL (hoặc DATABASE_URL/DATABASE_URL_DOCKER) "
            "cho chatbot. Đặt DSN dạng postgresql://user:pass@postgres:5432/eyetracking"
        )
    # Backend dùng asyncpg; psycopg không hiểu hậu tố này.
    return url.replace("postgresql+asyncpg://", "postgresql://")


def internal_token() -> str:
    return _env("CHATBOT_INTERNAL_TOKEN")


def db_pool_timeout() -> float:
    """Thời gian tối đa chờ một connection từ pool (giây).

    Để thấp để `/ready` và ingest báo lỗi cấu hình DB nhanh thay vì treo 30s.
    """
    return float(_env("DB_POOL_TIMEOUT", "10"))


def db_pool_reconnect_timeout() -> float:
    """Chu kỳ thử kết nối lại của pool khi DB/role chưa sẵn sàng (giây)."""
    return float(_env("DB_POOL_RECONNECT_TIMEOUT", "10"))


def llm_name() -> str:
    return _env("LLM_NAME", "river")


def embedding_name() -> str:
    return _env("EMBEDDING_NAME", "local")


def vlm_name() -> str:
    return _env("VLM_NAME", "river")


def embedding_dim() -> int:
    return int(_env("EMBEDDING_DIM", "1024"))


def embedding_model_path() -> str:
    """Đường dẫn weights embedding local (EMBEDDING_NAME=local)."""
    return _env("EMBEDDING_MODEL_PATH", str(_DEFAULT_LOCAL_EMBED_PATH))


def embedding_device() -> str:
    """Thiết bị suy luận embedding local: cuda | cpu (mặc định CPU).

    GPU chỉ dành cho services/gaze. Chatbot dùng River API cho LLM/VLM và
    embedding local chạy CPU; đặt EMBEDDING_DEVICE=cuda chỉ khi chủ động muốn
    dùng GPU cho chatbot.
    """
    return _env("EMBEDDING_DEVICE", "cpu")


def embedding_local_files_only() -> bool:
    """True -> chỉ đọc weights đã tải, không tự gọi mạng."""
    value = _env("EMBEDDING_LOCAL_FILES_ONLY", "true").lower()
    return value not in {"0", "false", "no"}


def embedding_hf_repo() -> str:
    return _env("EMBEDDING_HF_REPO", "Qwen/Qwen3-Embedding-0.6B")


def river_api_key() -> str:
    """API key River AI cho LLM/VLM."""
    return _env("RIVER_API_KEY")


def river_base_url() -> str:
    """Base URL OpenAI-compatible của River AI."""
    return _env("RIVER_BASE_URL", "https://api.river.ai/v1")


def river_llm_model() -> str:
    """Tên model LLM gọi qua River AI (router/answer/verify)."""
    return _env("RIVER_LLM_MODEL", "deepseek-ai/DeepSeek-V4.1-Flash-1017")


def river_vlm_model() -> str:
    """Tên model VLM gọi qua River AI (mô tả slide lúc ingest)."""
    return _env("RIVER_VLM_MODEL", "deepseek-ai/DeepSeek-V4.1-Flash-1017")


def river_llm_max_tokens() -> int:
    return int(_env("RIVER_LLM_MAX_TOKENS", "8192"))


def river_router_max_tokens() -> int:
    return int(_env("RIVER_ROUTER_MAX_TOKENS", "1024"))


def river_verifier_max_tokens() -> int:
    return int(_env("RIVER_VERIFIER_MAX_TOKENS", "8192"))


def river_vlm_max_tokens() -> int:
    return int(_env("RIVER_VLM_MAX_TOKENS", "16384"))


def river_timeout() -> float:
    return float(_env("RIVER_TIMEOUT", "180"))


def river_max_retries() -> int:
    return int(_env("RIVER_MAX_RETRIES", "2"))


def river_reasoning_effort() -> str:
    """low | high | max | none — để trống = không gửi tham số."""
    return _env("RIVER_REASONING_EFFORT", "low")


def river_router_reasoning_effort() -> str:
    """Router chỉ cần phân loại -> tắt reasoning để tiết kiệm token."""
    return _env("RIVER_ROUTER_REASONING_EFFORT", "none")


def river_verifier_reasoning_effort() -> str:
    """Verifier cần đọc kỹ nhưng không cần reasoning dài -> tắt reasoning."""
    return _env("RIVER_VERIFIER_REASONING_EFFORT", "none")


def river_vlm_reasoning_effort() -> str:
    """VLM transcribe slide -> tắt reasoning để tránh đốt token."""
    return _env("RIVER_VLM_REASONING_EFFORT", "none")


def rag_top_k() -> int:
    return int(_env("RAG_TOP_K", "8"))


def rag_candidates() -> int:
    return int(_env("RAG_CANDIDATES", "20"))


def rag_rrf_k() -> int:
    return int(_env("RAG_RRF_K", "60"))


def rag_score_threshold() -> float:
    return float(_env("RAG_SCORE_THRESHOLD", "0.25"))


def citation_max_attempts() -> int:
    return int(_env("CITATION_MAX_ATTEMPTS", "2"))


def local_media_dir() -> str:
    return _env("LOCAL_MEDIA_DIR", "/app/media")


def storage_http_allowed_hosts() -> str:
    return _env("STORAGE_HTTP_ALLOWED_HOSTS")


def storage_max_bytes() -> int:
    return int(_env("STORAGE_MAX_BYTES", str(50 * 1024 * 1024)))


def db_pool_min() -> int:
    return int(_env("DB_POOL_MIN", "1"))


def db_pool_max() -> int:
    return int(_env("DB_POOL_MAX", "10"))


def r2_values() -> tuple[str, str, str, str, str]:
    return (
        _env("R2_ACCOUNT_ID"),
        _env("R2_BUCKET_NAME"),
        _env("R2_ACCESS_KEY_ID"),
        _env("R2_SECRET_ACCESS_KEY"),
        _env("R2_PUBLIC_URL"),
    )


def validate() -> None:
    """Kiểm tra cấu hình bắt buộc; raise RuntimeError gộp mọi vấn đề."""
    problems: list[str] = []

    if not (
        _env("CHATBOT_DATABASE_URL")
        or _env("DATABASE_URL")
        or _env("DATABASE_URL_DOCKER")
    ):
        problems.append("thiếu CHATBOT_DATABASE_URL/DATABASE_URL/DATABASE_URL_DOCKER")

    if not internal_token():
        problems.append("thiếu CHATBOT_INTERNAL_TOKEN")

    if llm_name() not in ALLOWED_LLM:
        problems.append(
            f"LLM_NAME={llm_name()!r} không hợp lệ (chọn: {sorted(ALLOWED_LLM)})"
        )
    if embedding_name() not in ALLOWED_EMBEDDING:
        problems.append(
            f"EMBEDDING_NAME={embedding_name()!r} không hợp lệ "
            f"(chọn: {sorted(ALLOWED_EMBEDDING)})"
        )
    if vlm_name() not in ALLOWED_VLM:
        problems.append(
            f"VLM_NAME={vlm_name()!r} không hợp lệ (chọn: {sorted(ALLOWED_VLM)})"
        )
    if (llm_name() == "river" or vlm_name() == "river") and not river_api_key():
        problems.append("thiếu RIVER_API_KEY cho LLM_NAME/VLM_NAME=river")

    if embedding_dim() <= 0:
        problems.append("EMBEDDING_DIM phải > 0")
    if rag_top_k() <= 0:
        problems.append("RAG_TOP_K phải > 0")
    if rag_candidates() <= 0:
        problems.append("RAG_CANDIDATES phải > 0")
    if rag_rrf_k() <= 0:
        problems.append("RAG_RRF_K phải > 0")
    if not -1.0 <= rag_score_threshold() <= 1.0:
        problems.append("RAG_SCORE_THRESHOLD phải trong [-1, 1]")
    if citation_max_attempts() < 1:
        problems.append("CITATION_MAX_ATTEMPTS phải >= 1")

    r2 = r2_values()
    if any(r2) and not all(r2):
        problems.append("cấu hình R2 chưa đầy đủ (cần cả 5 biến R2_*)")

    if problems:
        raise RuntimeError("Cấu hình chatbot không hợp lệ: " + "; ".join(problems))
