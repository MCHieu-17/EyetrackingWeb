"""Phân loại intent cho câu hỏi mới nhất (kèm lịch sử hội thoại)."""

import logging
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field

from app.workflow.prompts import ROUTER_SYSTEM_PROMPT
from app.workflow.providers import get_llm
from app.workflow.state import ChatState

logger = logging.getLogger(__name__)

Intent = Literal[
    "course_qa",
    "exercise_hints",
    "exercise_review",
    "study_skills",
    "out_of_scope",
]


class RouterOutput(BaseModel):
    intent: Intent = Field(description="Intent phù hợp nhất với yêu cầu của sinh viên.")


_router_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", ROUTER_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        (
            "human",
            "Câu hỏi mới nhất: {question}\n\n"
            "Ngữ cảnh bài tập:\n{assignment_context}",
        ),
    ]
)


def _history_messages(history: list[dict]) -> list:
    messages = []
    for item in history[-10:]:
        content = (item.get("content") or "").strip()
        if not content:
            continue
        if item.get("role") == "student":
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))
    return messages


def _router_chain():
    return _router_prompt | get_llm(purpose="router").with_structured_output(RouterOutput)


def route(state: ChatState) -> str:
    """Trả về intent; lỗi provider -> course_qa (an toàn, có truy hồi)."""
    # Chế độ bài tập đã nộp -> luôn review, khỏi tốn 1 LLM call.
    if state.get("support_mode") == "review" and (state.get("assignment_context") or "").strip():
        return "exercise_review"
    # Chế độ gợi ý bài tập -> luôn hints.
    if state.get("support_mode") == "hint" and (state.get("assignment_context") or "").strip():
        return "exercise_hints"

    try:
        result: RouterOutput = _router_chain().invoke(
            {
                "chat_history": _history_messages(state.get("history") or []),
                "question": state["question"],
                "assignment_context": state.get("assignment_context") or "không có",
            }
        )
        return result.intent
    except Exception:
        logger.warning("Router lỗi — mặc định intent=course_qa", exc_info=True)
        return "course_qa"
