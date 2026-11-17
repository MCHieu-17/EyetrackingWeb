"""Cấu hình dùng chung cho chatbot.

Gom việc đọc biến môi trường về một chỗ và cung cấp `validate()` để fail-fast
lúc khởi động với thông báo rõ ràng (thay vì lỗi khó hiểu ở request đầu tiên).

`CHATBOT_DATABASE_URL` là DSN psycopg (postgresql://...), KHÔNG dùng hậu tố
+asyncpg. Fallback `DATABASE_URL`/`DATABASE_URL_DOCKER` để tương thích khi stack
chỉ cấu hình biến dùng chung với backend; nếu gặp +asyncpg thì tự bỏ hậu tố.
"""

import os

ALLOWED_EMBEDDING = {"local"}

_BOOL_TRUE = {"1", "true", "yes", "on"}
_BOOL_FALSE = {"0", "false", "no", "off"}


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _required(name: str) -> str:
    """Biến quyết định model local: không có default trong code."""
    value = _env(name)
    if not value:
        raise RuntimeError(
            f"Thiếu {name}. Đặt tường minh trong .env (local) hoặc "
            "stack.env (production)."
        )
    return value


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
    """Tên backend embedding; hiện chỉ hỗ trợ local."""
    return _required("EMBEDDING_NAME")


def embedding_dim() -> int:
    return int(_required("EMBEDDING_DIM"))


def embedding_model_path() -> str:
    """Đường dẫn weights embedding local (EMBEDDING_NAME=local)."""
    return _required("EMBEDDING_MODEL_PATH")


def embedding_device() -> str:
    """Thiết bị suy luận embedding local: cuda | cpu.

    GPU chỉ dành cho services/gaze. Chatbot gọi LLM/VLM qua endpoint
    OpenAI-compatible và chạy embedding local trên CPU; đặt EMBEDDING_DEVICE=cuda
    chỉ khi chủ động muốn dùng GPU cho chatbot (image phải build torch CUDA).
    """
    device = _required("EMBEDDING_DEVICE").lower()
    if device not in {"cpu", "cuda"}:
        raise RuntimeError(
            f"EMBEDDING_DEVICE={device!r} không hợp lệ; chọn cpu hoặc cuda."
        )
    return device


def embedding_local_files_only() -> bool:
    """True -> chỉ đọc weights đã tải, không tự gọi mạng."""
    value = _required("EMBEDDING_LOCAL_FILES_ONLY").lower()
    if value in _BOOL_TRUE:
        return True
    if value in _BOOL_FALSE:
        return False
    raise RuntimeError(
        f"EMBEDDING_LOCAL_FILES_ONLY={value!r} không hợp lệ; chọn true/false."
    )


def embedding_hf_repo() -> str:
    return _required("EMBEDDING_HF_REPO")


def llm_base_url() -> str:
    """Base URL OpenAI-compatible của endpoint LLM/VLM."""
    return _env("LLM_BASE_URL")


def llm_api_key() -> str:
    """API key của endpoint LLM/VLM (nếu endpoint yêu cầu auth)."""
    return _env("LLM_API_KEY")


def llm_auth_header() -> str:
    """Tên header auth; mặc định Authorization theo chuẩn OpenAI."""
    return _env("LLM_AUTH_HEADER", "Authorization")


def llm_auth_scheme() -> str:
    """Scheme auth (mặc định Bearer). Để trống nếu header nhận raw key."""
    return _env("LLM_AUTH_SCHEME", "Bearer")


def llm_headers() -> dict[str, str]:
    """Header auth gửi kèm request LLM/VLM."""
    header = llm_auth_header()
    key = llm_api_key()
    if not header or not key:
        return {}
    scheme = llm_auth_scheme()
    value = f"{scheme} {key}".strip() if scheme else key
    return {header: value}


def llm_model() -> str:
    """Tên model chat dùng cho query prep/answer."""
    return _env("LLM_MODEL")


def vlm_model() -> str:
    """Tên model vision cho ingest; mặc định dùng chung LLM_MODEL."""
    return _env("VLM_MODEL") or llm_model()


def llm_enable_thinking() -> bool:
    """Bật reasoning nếu endpoint hỗ trợ. Mặc định tắt để giảm latency/token."""
    value = _env("LLM_ENABLE_THINKING", "false").lower()
    return value in {"1", "true", "yes", "on"}


def answer_max_tokens() -> int:
    """Max output cho câu trả lời."""
    return int(_env("ANSWER_MAX_TOKENS", "2048"))


def answer_temperature() -> float:
    return float(_env("ANSWER_TEMPERATURE", "0.2"))


def llm_query_max_tokens() -> int:
    """Max output cho query rewrite/HyDE (nhỏ để giảm latency)."""
    return int(_env("LLM_QUERY_MAX_TOKENS", "400"))


def vlm_max_tokens() -> int:
    return int(_env("VLM_MAX_TOKENS", "8192"))


def llm_timeout() -> float:
    return float(_env("LLM_TIMEOUT", "180"))


def llm_max_retries() -> int:
    return int(_env("LLM_MAX_RETRIES", "2"))


def llm_query_timeout() -> float:
    return float(_env("LLM_QUERY_TIMEOUT", "30"))


def llm_answer_timeout() -> float:
    return float(_env("LLM_ANSWER_TIMEOUT", "120"))


def vlm_timeout() -> float:
    return float(_env("VLM_TIMEOUT", "300"))


def llm_generation_concurrency() -> int:
    return int(_env("LLM_GENERATION_CONCURRENCY", "4"))


def llm_total_concurrency() -> int:
    return int(_env("LLM_TOTAL_CONCURRENCY", "6"))


def llm_requests_per_second() -> float:
    return float(_env("LLM_REQUESTS_PER_SECOND", "0"))


def llm_queue_timeout() -> float:
    return float(_env("LLM_QUEUE_TIMEOUT", "30"))


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

    embedding_name_value = _env("EMBEDDING_NAME")
    if not embedding_name_value:
        problems.append("thiếu EMBEDDING_NAME")
    elif embedding_name_value not in ALLOWED_EMBEDDING:
        problems.append(
            f"EMBEDDING_NAME={embedding_name_value!r} không hợp lệ "
            f"(chọn: {sorted(ALLOWED_EMBEDDING)})"
        )
    if not _env("EMBEDDING_MODEL_PATH"):
        problems.append("thiếu EMBEDDING_MODEL_PATH")
    embedding_device_value = _env("EMBEDDING_DEVICE").lower()
    if not embedding_device_value:
        problems.append("thiếu EMBEDDING_DEVICE")
    elif embedding_device_value not in {"cpu", "cuda"}:
        problems.append(
            f"EMBEDDING_DEVICE={embedding_device_value!r} không hợp lệ "
            "(chọn: cpu, cuda)"
        )
    local_files_only = _env("EMBEDDING_LOCAL_FILES_ONLY").lower()
    if not local_files_only:
        problems.append("thiếu EMBEDDING_LOCAL_FILES_ONLY")
    elif local_files_only not in _BOOL_TRUE | _BOOL_FALSE:
        problems.append(
            f"EMBEDDING_LOCAL_FILES_ONLY={local_files_only!r} không hợp lệ "
            "(chọn: true, false)"
        )
    if not _env("EMBEDDING_HF_REPO"):
        problems.append("thiếu EMBEDDING_HF_REPO")
    embedding_dim_value = _env("EMBEDDING_DIM")
    if not embedding_dim_value:
        problems.append("thiếu EMBEDDING_DIM")
    elif not embedding_dim_value.isdigit() or int(embedding_dim_value) <= 0:
        problems.append("EMBEDDING_DIM phải là số nguyên > 0")
    if not llm_base_url():
        problems.append("thiếu LLM_BASE_URL")
    if not llm_model():
        problems.append("thiếu LLM_MODEL")
    if llm_auth_header() and not llm_api_key():
        problems.append("thiếu LLM_API_KEY khi LLM_AUTH_HEADER được đặt")
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
    if llm_query_max_tokens() <= 0:
        problems.append("LLM_QUERY_MAX_TOKENS phải > 0")
    if vlm_max_tokens() <= 0:
        problems.append("VLM_MAX_TOKENS phải > 0")
    if llm_timeout() <= 0:
        problems.append("LLM_TIMEOUT phải > 0")
    if llm_query_timeout() <= 0:
        problems.append("LLM_QUERY_TIMEOUT phải > 0")
    if llm_answer_timeout() <= 0:
        problems.append("LLM_ANSWER_TIMEOUT phải > 0")
    if vlm_timeout() <= 0:
        problems.append("VLM_TIMEOUT phải > 0")
    if llm_generation_concurrency() <= 0:
        problems.append("LLM_GENERATION_CONCURRENCY phải > 0")
    if llm_total_concurrency() <= 0:
        problems.append("LLM_TOTAL_CONCURRENCY phải > 0")
    if llm_requests_per_second() < 0:
        problems.append("LLM_REQUESTS_PER_SECOND phải >= 0")
    if llm_queue_timeout() <= 0:
        problems.append("LLM_QUEUE_TIMEOUT phải > 0")
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
