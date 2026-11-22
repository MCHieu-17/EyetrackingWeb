"""Chuẩn bị truy vấn: rewrite theo history + HyDE adaptive.

Một structured call duy nhất (nếu cần). Nếu call lỗi, fallback về câu hỏi gốc
để không chặn request.
"""

import hashlib
import json
import logging
import re
import time
import unicodedata
from collections import OrderedDict

from pydantic import BaseModel, Field

from app.settings import (
    hyde_enabled,
    hyde_min_query_words,
    llm_model,
    query_rewrite_enabled,
)
from app.workflow.history import budget_history
from app.workflow.llm import get_llm_client
from app.workflow.prompts import QUERY_PREP_SYSTEM_PROMPT
from app.workflow.state import ChatState

logger = logging.getLogger(__name__)

_REFERENCE_RE = re.compile(
    r"\b(nó|cái này|phần này|phần đó|đó|trên|vừa nói|câu này|bài này|"
    r"chương này|tại sao|giải thích thêm|như thế nào|ý này|đoạn này)\b",
    re.IGNORECASE,
)

# Câu ngắn nhưng bắt đầu bằng cụm mơ hồ mới cần HyDE. Câu ngắn có chủ thể cụ
# thể (vd "AWS Glue là gì?") không cần thêm một LLM call.
_VAGUE_RE = re.compile(
    r"^(tại sao|vì sao|như thế nào|thế nào|là gì|giải thích|nói rõ|"
    r"chi tiết|ví dụ)\b",
    re.IGNORECASE,
)

# Thuật ngữ/tên riêng viết hoa cho thấy câu hỏi đã có chủ thể cụ thể.
_SPECIFIC_RE = re.compile(r"\b[A-Z][A-Za-z0-9+#.-]{1,}\b")


class RewriteOnly(BaseModel):
    query: str = Field(default="", max_length=2000)


class QueryPrep(BaseModel):
    query: str = Field(default="", max_length=2000)
    hypothetical_answer: str = Field(default="", max_length=4000)


_CACHE_TTL_SECONDS = 300
_CACHE_MAX_ENTRIES = 256
_cache: OrderedDict[tuple, tuple[float, QueryPrep]] = OrderedDict()


def clear_query_cache() -> None:
    _cache.clear()


def _cache_key(state: ChatState, need_hyde: bool) -> tuple:
    history = json.dumps(
        budget_history(state.history),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    question = " ".join(
        unicodedata.normalize("NFC", state.question).lower().split()
    )
    return (
        question,
        hashlib.sha256(history.encode()).hexdigest(),
        need_hyde,
        llm_model(),
    )


def _cache_get(key: tuple) -> QueryPrep | None:
    item = _cache.get(key)
    if item is None:
        return None
    stored_at, prep = item
    if time.monotonic() - stored_at > _CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    _cache.move_to_end(key)
    return prep


def _cache_put(key: tuple, prep: QueryPrep) -> None:
    _cache[key] = (time.monotonic(), prep)
    _cache.move_to_end(key)
    while len(_cache) > _CACHE_MAX_ENTRIES:
        _cache.popitem(last=False)


def _needs_rewrite(state: ChatState) -> bool:
    if not state.history:
        return False
    return bool(_REFERENCE_RE.search(state.question)) or len(
        state.question.split()
    ) < 12


def _needs_hyde(state: ChatState) -> bool:
    if not hyde_enabled():
        return False
    words = len(state.question.split())
    if words >= hyde_min_query_words():
        return False
    # Follow-up đã có rewrite xử lý; HyDE chỉ dành cho câu đứng một mình,
    # ngắn và thật sự mơ hồ, không có chủ thể cụ thể.
    if state.history:
        return False
    if _SPECIFIC_RE.search(state.question):
        return False
    return bool(_VAGUE_RE.search(state.question)) or words <= 2


async def prepare_query(state: ChatState) -> QueryPrep:
    """Trả về query đã rewrite và HyDE text (nếu cần)."""
    need_hyde = _needs_hyde(state)
    if not query_rewrite_enabled() and not need_hyde:
        return QueryPrep(query=state.question)
    if not _needs_rewrite(state) and not need_hyde:
        return QueryPrep(query=state.question)

    key = _cache_key(state, need_hyde)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    prompt = [
        {"role": "system", "content": QUERY_PREP_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": str(
                {
                    "question": state.question,
                    "history": budget_history(state.history),
                    "need_hypothetical_answer": need_hyde,
                }
            ),
        },
    ]
    try:
        if need_hyde:
            prep = await get_llm_client().structured("query", prompt, QueryPrep)
            result = QueryPrep(
                query=(prep.query or state.question).strip(),
                hypothetical_answer=prep.hypothetical_answer.strip(),
            )
        else:
            # Rewrite-only: schema chỉ có `query` để model không sinh thêm HyDE.
            prep = await get_llm_client().structured("query", prompt, RewriteOnly)
            result = QueryPrep(query=(prep.query or state.question).strip())
        _cache_put(key, result)
        return result
    except Exception as exc:
        logger.warning("Query prep failed; using original question: %s", exc)
        return QueryPrep(query=state.question)
