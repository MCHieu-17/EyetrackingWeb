"""Cấu hình dùng chung cho chatbot.

Gom việc đọc biến môi trường về một chỗ và cung cấp `validate()` để fail-fast
lúc khởi động với thông báo rõ ràng (thay vì lỗi khó hiểu ở request đầu tiên).

`CHATBOT_DATABASE_URL` là DSN psycopg (postgresql://...), KHÔNG dùng hậu tố
+asyncpg. Fallback `DATABASE_URL`/`DATABASE_URL_DOCKER` để tương thích khi stack
chỉ cấu hình biến dùng chung với backend; nếu gặp +asyncpg thì tự bỏ hậu tố.
"""

import os
from pathlib import Path

ALLOWED_EMBEDDING = {"local"}

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


def embedding_name() -> str:
    return _env("EMBEDDING_NAME", "local")


def embedding_dim() -> int:
    return int(_env("EMBEDDING_DIM", "1024"))


def embedding_model_path() -> str:
    """Đường dẫn weights embedding local (EMBEDDING_NAME=local)."""
    return _env("EMBEDDING_MODEL_PATH", str(_DEFAULT_LOCAL_EMBED_PATH))


def embedding_device() -> str:
    """Thiết bị suy luận embedding local: cuda | cpu (mặc định CPU).

    GPU chỉ dành cho services/gaze. Chatbot dùng NEU API cho LLM/VLM và
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


def neu_base_url() -> str:
    """Base URL OpenAI-compatible của NEU LLM/VLM server."""
    return _env("NEU_BASE_URL")


def neu_api_key() -> str:
    """API key/seckey của NEU server."""
    return _env("NEU_API_KEY")


def neu_auth_header() -> str:
    """Tên header auth. Mặc định x-ollama-seckey."""
    return _env("NEU_AUTH_HEADER", "x-ollama-seckey")


def neu_auth_scheme() -> str:
    """Scheme auth (vd Bearer). Để trống nếu header nhận raw key."""
    return _env("NEU_AUTH_SCHEME")


def neu_headers() -> dict[str, str]:
    """Header auth gửi kèm request LLM/VLM."""
    header = neu_auth_header()
    key = neu_api_key()
    if not header or not key:
        return {}
    scheme = neu_auth_scheme()
    value = f"{scheme} {key}".strip() if scheme else key
    return {header: value}


def neu_llm_model() -> str:
    """Tên model LLM gọi qua NEU (query prep/answer)."""
    return _env("NEU_LLM_MODEL", "qwen3.5-35b-a3b-int4")


def neu_vlm_model() -> str:
    """Tên model VLM gọi qua NEU (mô tả slide lúc ingest)."""
    return _env("NEU_VLM_MODEL") or neu_llm_model()


def neu_enable_thinking() -> bool:
    """Bật reasoning của Qwen. Mặc định tắt để giảm latency/token."""
    value = _env("NEU_ENABLE_THINKING", "false").lower()
    return value in {"1", "true", "yes", "on"}


def answer_max_tokens() -> int:
    """Max output cho câu trả lời."""
    return int(_env("ANSWER_MAX_TOKENS", "2048"))


def answer_temperature() -> float:
    return float(_env("ANSWER_TEMPERATURE", "0.2"))


def neu_query_max_tokens() -> int:
    """Max output cho query rewrite/HyDE (nhỏ để giảm latency)."""
    return int(_env("NEU_QUERY_MAX_TOKENS", "400"))


def neu_vlm_max_tokens() -> int:
    return int(_env("NEU_VLM_MAX_TOKENS", "8192"))


def neu_timeout() -> float:
    return float(_env("NEU_TIMEOUT", "180"))


def neu_max_retries() -> int:
    return int(_env("NEU_MAX_RETRIES", "2"))


def neu_query_timeout() -> float:
    return float(_env("NEU_QUERY_TIMEOUT", "30"))


def neu_answer_timeout() -> float:
    return float(_env("NEU_ANSWER_TIMEOUT", "120"))


def neu_vlm_timeout() -> float:
    return float(_env("NEU_VLM_TIMEOUT", "300"))


def neu_generation_concurrency() -> int:
    return int(_env("NEU_GENERATION_CONCURRENCY", "4"))


def neu_total_concurrency() -> int:
    return int(_env("NEU_TOTAL_CONCURRENCY", "6"))


def neu_requests_per_second() -> float:
    return float(_env("NEU_REQUESTS_PER_SECOND", "0"))


def neu_queue_timeout() -> float:
    return float(_env("NEU_QUEUE_TIMEOUT", "30"))


def rag_top_k() -> int:
    return int(_env("RAG_TOP_K", "8"))


def rag_bm25_candidates() -> int:
    return int(_env("RAG_BM25_CANDIDATES", _env("RAG_CANDIDATES", "20")))


def rag_dense_candidates() -> int:
    return int(_env("RAG_DENSE_CANDIDATES", _env("RAG_CANDIDATES", "20")))


def rag_hyde_candidates() -> int:
    return int(_env("RAG_HYDE_CANDIDATES", _env("RAG_CANDIDATES", "20")))


def rag_rrf_k() -> int:
    return int(_env("RAG_RRF_K", "60"))


def rag_hyde_weight() -> float:
    return float(_env("RAG_HYDE_WEIGHT", "0.7"))


def rag_score_threshold() -> float:
    return float(_env("RAG_SCORE_THRESHOLD", "0.2"))


def query_rewrite_enabled() -> bool:
    value = _env("QUERY_REWRITE_ENABLED", "true").lower()
    return value not in {"0", "false", "no"}


def hyde_enabled() -> bool:
    value = _env("HYDE_ENABLED", "true").lower()
    return value not in {"0", "false", "no"}


def hyde_min_query_words() -> int:
    return int(_env("HYDE_MIN_QUERY_WORDS", "8"))


def citation_gate_tokens() -> int:
    """Số token (xấp xỉ theo từ) buffer trước khi kiểm tra citation."""
    return int(_env("CITATION_GATE_TOKENS", "200"))


def citation_retry_max() -> int:
    return int(_env("CITATION_RETRY_MAX", "1"))


def lms_detection_enabled() -> bool:
    value = _env("LMS_DETECTION_ENABLED", "true").lower()
    return value not in {"0", "false", "no"}


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

    if embedding_name() not in ALLOWED_EMBEDDING:
        problems.append(
            f"EMBEDDING_NAME={embedding_name()!r} không hợp lệ "
            f"(chọn: {sorted(ALLOWED_EMBEDDING)})"
        )
    if not neu_base_url():
        problems.append("thiếu NEU_BASE_URL")
    if not neu_llm_model():
        problems.append("thiếu NEU_LLM_MODEL")
    if neu_auth_header() and not neu_api_key():
        problems.append("thiếu NEU_API_KEY khi NEU_AUTH_HEADER được đặt")

    if embedding_dim() <= 0:
        problems.append("EMBEDDING_DIM phải > 0")
    if rag_top_k() <= 0:
        problems.append("RAG_TOP_K phải > 0")
    if rag_bm25_candidates() <= 0:
        problems.append("RAG_BM25_CANDIDATES phải > 0")
    if rag_dense_candidates() <= 0:
        problems.append("RAG_DENSE_CANDIDATES phải > 0")
    if rag_hyde_candidates() <= 0:
        problems.append("RAG_HYDE_CANDIDATES phải > 0")
    if rag_rrf_k() <= 0:
        problems.append("RAG_RRF_K phải > 0")
    if not 0.0 <= rag_hyde_weight() <= 1.0:
        problems.append("RAG_HYDE_WEIGHT phải trong [0, 1]")
    if not -1.0 <= rag_score_threshold() <= 1.0:
        problems.append("RAG_SCORE_THRESHOLD phải trong [-1, 1]")
    if answer_max_tokens() <= 0:
        problems.append("ANSWER_MAX_TOKENS phải > 0")
    if not 0.0 <= answer_temperature() <= 2.0:
        problems.append("ANSWER_TEMPERATURE phải trong [0, 2]")
    if neu_query_max_tokens() <= 0:
        problems.append("NEU_QUERY_MAX_TOKENS phải > 0")
    if neu_vlm_max_tokens() <= 0:
        problems.append("NEU_VLM_MAX_TOKENS phải > 0")
    if neu_timeout() <= 0:
        problems.append("NEU_TIMEOUT phải > 0")
    if neu_query_timeout() <= 0:
        problems.append("NEU_QUERY_TIMEOUT phải > 0")
    if neu_answer_timeout() <= 0:
        problems.append("NEU_ANSWER_TIMEOUT phải > 0")
    if neu_vlm_timeout() <= 0:
        problems.append("NEU_VLM_TIMEOUT phải > 0")
    if neu_generation_concurrency() <= 0:
        problems.append("NEU_GENERATION_CONCURRENCY phải > 0")
    if neu_total_concurrency() <= 0:
        problems.append("NEU_TOTAL_CONCURRENCY phải > 0")
    if neu_requests_per_second() < 0:
        problems.append("NEU_REQUESTS_PER_SECOND phải >= 0")
    if neu_queue_timeout() <= 0:
        problems.append("NEU_QUEUE_TIMEOUT phải > 0")
    if hyde_min_query_words() <= 0:
        problems.append("HYDE_MIN_QUERY_WORDS phải > 0")
    if citation_gate_tokens() <= 0:
        problems.append("CITATION_GATE_TOKENS phải > 0")
    if citation_retry_max() < 0:
        problems.append("CITATION_RETRY_MAX phải >= 0")

    r2 = r2_values()
    if any(r2) and not all(r2):
        problems.append("cấu hình R2 chưa đầy đủ (cần cả 5 biến R2_*)")

    if problems:
        raise RuntimeError("Cấu hình chatbot không hợp lệ: " + "; ".join(problems))
