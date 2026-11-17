"""Factory tạo embedding / VLM theo tên trong biến môi trường.

Các factory được **cache** (`get_embedding`/`get_vlm`) để cả tiến trình dùng
chung một client cho mỗi loại model thay vì mỗi request tạo một instance.

LLM chat dùng trực tiếp `app.workflow.llm.LLMClient` (AsyncOpenAI), không dùng
LangChain ChatOpenAI cho answer/query. VLM (mô tả slide lúc ingest) vẫn dùng
ChatOpenAI vì có structured output + prompt template, trỏ cùng endpoint
LLM/VLM OpenAI-compatible. Embedding chạy local (Qwen3-Embedding-0.6B trên CPU).
"""

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.settings import (
    embedding_device,
    embedding_local_files_only,
    embedding_model_path,
    embedding_name,
    llm_api_key,
    llm_base_url,
    llm_enable_thinking,
    llm_headers,
    llm_max_retries,
    vlm_max_tokens,
    vlm_model,
    vlm_timeout,
)


def _llm_chat(model: str, max_tokens: int, timeout: float) -> ChatOpenAI:
    """Client ChatOpenAI trỏ tới endpoint LLM/VLM (dùng cho VLM ingest)."""
    return ChatOpenAI(
        model=model,
        base_url=llm_base_url(),
        api_key=llm_api_key() or "not-needed",
        default_headers=llm_headers(),
        temperature=0,
        max_tokens=max_tokens,
        timeout=timeout,
        max_retries=llm_max_retries(),
        extra_body={
            "chat_template_kwargs": {"enable_thinking": llm_enable_thinking()}
        },
    )


def _build_embedding(name: str) -> Embeddings:
    if name == "local":
        # Import muộn để đường không cần embedding local khỏi kéo torch/
        # sentence-transformers.
        from langchain_huggingface import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(
            model_name=embedding_model_path(),
            model_kwargs={
                "device": embedding_device(),
                "local_files_only": embedding_local_files_only(),
            },
            encode_kwargs={"batch_size": 8, "normalize_embeddings": True},
            query_encode_kwargs={
                "normalize_embeddings": True,
                "prompt": (
                    "Instruct: Retrieve relevant educational documents for "
                    "answering student questions.\nQuery: "
                ),
            },
        )
    raise ValueError(f"Embedding không được hỗ trợ: {name!r}")


@lru_cache(maxsize=None)
def get_embedding(name: str | None = None) -> Embeddings:
    """Embedding dùng chung (cache theo tên). Mặc định từ EMBEDDING_NAME."""
    from app.workflow.embedding_queue import ManagedEmbedding

    return ManagedEmbedding(
        _build_embedding(name or embedding_name()), embedding_model_path()
    )


def _build_vlm() -> BaseChatModel:
    return _llm_chat(
        vlm_model(),
        vlm_max_tokens(),
        vlm_timeout(),
    )


@lru_cache(maxsize=1)
def get_vlm() -> BaseChatModel:
    """VLM dùng chung. Mặc định từ VLM_MODEL hoặc LLM_MODEL."""
    return _build_vlm()
