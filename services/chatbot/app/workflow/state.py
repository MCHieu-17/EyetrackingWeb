"""State cho pipeline RAG tuyến tính (không dùng checkpointer).

Backend giữ lịch sử hội thoại và gửi kèm theo từng request; service chatbot chỉ
giữ state trong bộ nhớ của request hiện tại.
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ChatState:
    # Input từ backend
    question: str
    course_id: str
    course_version_id: str | None
    thread_id: str
    context_key: str = ""
    history: list[dict] = field(default_factory=list)
    lesson_id: str | None = None
    lesson_version_id: str | None = None
    lesson_title: str = ""
    module_title: str = ""
    attempt_id: str | None = None
    assignment_id: str | None = None
    assignment_title: str = ""
    assignment_context: str = ""
    support_mode: Literal["hint", "review"] = "hint"

    # Kết quả trung gian
    query: str = ""
    hyde: str = ""
    used_hyde: bool = False
    retrieved_docs: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    lms_data: dict | None = None
    lms_text: str = ""

    # Kết quả cuối
    answer: str = ""
    verified: bool = True
    finish_reason: str = "stop"
    intent: str = "course_qa"
    routes: list[str] = field(default_factory=list)
