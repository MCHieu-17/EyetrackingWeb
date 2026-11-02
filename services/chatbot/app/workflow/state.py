"""State cho pipeline RAG (không dùng checkpointer — backend giữ history)."""

from typing import Literal, TypedDict


class HistoryItem(TypedDict):
    role: Literal["student", "assistant"]
    content: str


class ChatState(TypedDict, total=False):
    # Input
    question: str
    course_id: str
    thread_id: str
    history: list[HistoryItem]
    lesson_id: str | None
    lesson_title: str
    module_title: str
    assignment_id: str | None
    assignment_title: str
    assignment_context: str
    support_mode: Literal["hint", "review"]

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
