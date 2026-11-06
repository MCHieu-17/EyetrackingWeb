"""State cho pipeline RAG (không dùng checkpointer — backend giữ history)."""

from typing import Literal, TypedDict


class HistoryItem(TypedDict):
    role: Literal["student", "assistant"]
    content: str


class ChatState(TypedDict, total=False):
    # Input
    question: str
    course_id: str
    course_version_id: str | None
    thread_id: str
    history: list[HistoryItem]
    lesson_id: str | None
    lesson_version_id: str | None
    lesson_title: str
    module_title: str
    attempt_id: str | None
    assignment_id: str | None
    assignment_title: str
    assignment_context: str
    support_mode: Literal["hint", "review"]

    context_key: str
    plan: dict
    lms_data: dict
    lms_text: str
    routes: list[str]
    finish_reason: str
    knowledge_question: str
    # Routing
    intent: str

    # Retrieval
    retrieved_docs: list[dict]
    citations: list[dict]

    # Generation / verification
    draft: str
    answer: str
    verified: bool
    attempts: int
    verification_feedback: str
    verification: dict
