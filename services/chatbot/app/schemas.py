"""Schema request/response cho API chatbot."""

from typing import Literal

from pydantic import BaseModel, Field


class HistoryMessage(BaseModel):
    role: Literal["student", "assistant"]
    content: str = Field(min_length=1, max_length=20000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    course_id: str = Field(min_length=1, max_length=64)
    course_version_id: str | None = None
    thread_id: str = Field(min_length=1, max_length=256)
    context_key: str = Field(default="", max_length=512)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=30)

    # Ngữ cảnh LMS: sinh viên đang ở bài/chương nào. `lesson_id` chỉ dùng để
    # đưa vào prompt, KHÔNG dùng để lọc retrieval (phạm vi là cả môn).
    lesson_id: str | None = None
    lesson_version_id: str | None = None
    lesson_title: str = Field(default="", max_length=255)
    module_title: str = Field(default="", max_length=255)

    # Bài tập: backend chỉ gửi đáp án đúng/giải thích khi attempt cụ thể đã nộp.
    attempt_id: str | None = None
    assignment_id: str | None = None
    assignment_title: str = Field(default="", max_length=255)
    assignment_context: str = Field(default="", max_length=30000)
    support_mode: Literal["hint", "review"] = "hint"


class CitationOut(BaseModel):
    document_id: str
    course_version_id: str | None = None
    lesson_version_id: str | None = None
    slide_version_id: str | None = None
    membership_id: str | None = None
    asset_id: str | None = None
    title: str
    location: str
    lesson_id: str | None = None
    lesson_title: str = ""
    slide_id: str | None = None
    slide_index: int | None = None
    pdf_url: str = ""
    page_number: int | None = None
    snippet: str = ""
    score: float = 0.0


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    intent: str
    verified: bool = True
    routes: list[str] = Field(default_factory=list)
    finish_reason: str = "stop"


class IngestSlideRequest(BaseModel):
    slide_version_id: str = Field(min_length=1, max_length=64)
    include_draft: bool = False


class IngestLessonRequest(BaseModel):
    lesson_version_id: str = Field(min_length=1, max_length=64)
    include_draft: bool = False
    slide_version_ids: list[str] | None = None


class IngestCourseRequest(BaseModel):
    course_version_id: str = Field(min_length=1, max_length=64)
    include_draft: bool = False
    slide_version_ids: list[str] | None = None


class IngestResult(BaseModel):
    processed: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)
