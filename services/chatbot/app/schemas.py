"""Schema request/response cho API chatbot."""

from typing import Literal

from pydantic import BaseModel, Field


class HistoryMessage(BaseModel):
    role: Literal["student", "assistant"]
    content: str = Field(min_length=1, max_length=20000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    course_id: str = Field(min_length=1, max_length=64)
    thread_id: str = Field(min_length=1, max_length=256)
    context_key: str = Field(default="", max_length=512)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=30)
    lesson_id: str | None = None
    lesson_title: str = Field(default="", max_length=255)
    module_title: str = Field(default="", max_length=255)
    attempt_id: str | None = None
    assignment_id: str | None = None
    assignment_title: str = Field(default="", max_length=255)
    assignment_context: str = Field(default="", max_length=30000)
    support_mode: Literal["hint", "review"] = "hint"


class CitationOut(BaseModel):
    document_id: str
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


class IngestSlidesRequest(BaseModel):
    slide_ids: list[str] = Field(min_length=1, max_length=2000)


class IngestResult(BaseModel):
    processed: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)
