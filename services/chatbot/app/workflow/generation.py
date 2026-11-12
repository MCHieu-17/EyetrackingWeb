"""Sinh câu trả lời bằng một LLM call streaming.

Không còn NDJSON block, không verify từng block. Prompt duy nhất xử lý cả bài
giảng và bài tập; suffix được thêm theo `support_mode`.
"""

import logging
from contextlib import aclosing

from langchain_core.messages import HumanMessage, SystemMessage

from app.workflow.history import _history_messages
from app.workflow.llm import get_llm_client, messages
from app.workflow.prompts import (
    ANSWER_HINT_SUFFIX,
    ANSWER_REVIEW_SUFFIX,
    ANSWER_SYSTEM_PROMPT,
    CITATION_STRICT_SUFFIX,
    LMS_CONTEXT_RULE,
    OUTPUT_FORMAT_RULE,
)
from app.workflow.retrieval import format_context
from app.workflow.state import ChatState

logger = logging.getLogger(__name__)


def _system_prompt(state: ChatState, strict: bool = False) -> str:
    parts = [ANSWER_SYSTEM_PROMPT, OUTPUT_FORMAT_RULE]
    if state.assignment_context:
        if state.support_mode == "hint":
            parts.append(ANSWER_HINT_SUFFIX)
        else:
            parts.append(ANSWER_REVIEW_SUFFIX)
    if state.lms_text:
        parts.append(LMS_CONTEXT_RULE)
    if strict:
        parts.append(CITATION_STRICT_SUFFIX)
    return "\n\n".join(parts)


def _human_prompt(state: ChatState) -> str:
    location = (
        " > ".join(part for part in (state.module_title, state.lesson_title) if part)
        or "chưa xác định"
    )
    parts = [
        f"Vị trí hiện tại của sinh viên: {location}",
        f"Bài tập đang mở: {state.assignment_title or 'không có'}",
        f"Câu hỏi của sinh viên: {state.question}",
    ]
    if state.assignment_context:
        parts.append("Ngữ cảnh bài tập:\n" + state.assignment_context)
    if state.lms_text:
        parts.append("Dữ liệu LMS từ backend:\n" + state.lms_text)
    parts.append(
        "Tài liệu tham khảo:\n"
        + (format_context(state.retrieved_docs) or "(không có tài liệu)")
    )
    return "\n\n".join(parts)


async def stream_answer(state: ChatState, strict: bool = False):
    """Stream từng chunk text từ LLM server."""
    prompt = messages(
        [
            SystemMessage(content=_system_prompt(state, strict=strict)),
            *_history_messages(state.history),
            HumanMessage(content=_human_prompt(state)),
        ]
    )
    async with aclosing(get_llm_client().stream(prompt)) as source:
        async for chunk in source:
            yield chunk
