"""Factory tạo LLM / embedding / VLM theo tên trong biến môi trường.

Các factory được **cache** (`get_llm`/`get_embedding`/`get_vlm`) để cả tiến trình
dùng chung một client cho mỗi loại model thay vì mỗi node tạo một instance.

LLM (router/answer/verify) và VLM (mô tả slide lúc ingest) đều gọi qua **River AI**
— endpoint OpenAI-compatible, KHÔNG tốn VRAM local.
Embedding chạy local (Qwen3-Embedding-0.6B trên GPU).

`message_text` chuẩn hóa nội dung model trả về thành string.
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
    llm_name,
    river_api_key,
    river_base_url,
    river_llm_max_tokens,
    river_llm_model,
    river_max_retries,
    river_reasoning_effort,
    river_router_max_tokens,
    river_router_reasoning_effort,
    river_timeout,
    river_verifier_max_tokens,
    river_verifier_reasoning_effort,
    river_vlm_max_tokens,
    river_vlm_model,
    river_vlm_reasoning_effort,
    vlm_name,
)


def _river_chat(model: str, max_tokens: int, effort: str) -> ChatOpenAI:
    """Client ChatOpenAI trỏ tới River AI (LLM và VLM dùng chung cấu hình)."""
    kwargs: dict = {}
    if effort:
        # River AI/DeepSeek nhận reasoning_effort ở body. `extra_body` được
        # langchain-openai chuyển nguyên vào request.
        kwargs["extra_body"] = {"reasoning_effort": effort}

    return ChatOpenAI(
        model=model,
        base_url=river_base_url(),
        api_key=river_api_key(),
        temperature=0,
        max_tokens=max_tokens,
        timeout=river_timeout(),
        max_retries=river_max_retries(),
        **kwargs,
    )


def _build_llm(name: str, purpose: str) -> BaseChatModel:
    if name == "river":
        if purpose == "router":
            return _river_chat(
                river_llm_model(),
                river_router_max_tokens(),
                river_router_reasoning_effort(),
            )
        if purpose == "verify":
            return _river_chat(
                river_llm_model(),
                river_verifier_max_tokens(),
                river_verifier_reasoning_effort(),
            )
        return _river_chat(
            river_llm_model(),
            river_llm_max_tokens(),
            river_reasoning_effort(),
        )
    raise ValueError(f"LLM không được hỗ trợ: {name!r}")


@lru_cache(maxsize=None)
def get_llm(name: str | None = None, purpose: str = "answer") -> BaseChatModel:
    """LLM dùng chung (cache theo tên + purpose).

    purpose: "router" | "answer" | "verify" — mỗi purpose có max_tokens và
    reasoning_effort riêng để tránh đốt token vào reasoning không cần thiết.
    """
    return _build_llm(name or llm_name(), purpose)


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
    return _build_embedding(name or embedding_name())


def _build_vlm(name: str) -> BaseChatModel:
    if name == "river":
        return _river_chat(
            river_vlm_model(),
            river_vlm_max_tokens(),
            river_vlm_reasoning_effort(),
        )
    raise ValueError(f"VLM không được hỗ trợ: {name!r}")


@lru_cache(maxsize=None)
def get_vlm(name: str | None = None) -> BaseChatModel:
    """VLM dùng chung (cache theo tên). Mặc định từ VLM_NAME."""
    return _build_vlm(name or vlm_name())


def message_text(content: object) -> str:
    """Chuẩn hóa nội dung trả về của model thành string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "".join(parts)
    return str(content) if content is not None else ""
