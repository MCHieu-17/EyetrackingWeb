"""Schema request/response cho API chat."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from app.schemas.common import CamelModel


class ChatCitation(CamelModel):
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
    image_url: str = ""
    pdf_url: str = ""
    page_number: int | None = None
    snippet: str = ""
    score: float = 0.0


class ChatSendIn(CamelModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: UUID | None = None
    lesson_id: UUID | None = None
    # Tên giữ tương thích frontend: đây là lesson_version_id của quiz.
    assignment_id: UUID | None = None
    attempt_id: UUID | None = None
    draft_answers: dict[
        Annotated[str, Field(min_length=1, max_length=100)],
        Annotated[list[Annotated[str, Field(min_length=1, max_length=100)]], Field(max_length=12)],
    ] = Field(default_factory=dict, max_length=200)


class ChatReplyOut(CamelModel):
    session_id: str
    answer: str
    citations: list[ChatCitation] = Field(default_factory=list)
    intent: str | None = None
    verified: bool = True


class ChatSessionOut(CamelModel):
    can_continue: bool = True
    id: str
    course_id: str
    course_version_id: str | None = None
    lesson_id: str | None = None
    lesson_version_id: str | None = None
    assignment_id: str | None = None
    attempt_id: str | None = None
    title: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ChatSessionUpdate(CamelModel):
    title: str = Field(min_length=1, max_length=255)


class ChatMessageOut(CamelModel):
    id: str
    role: str
    content: str
    citations: list[ChatCitation] = Field(default_factory=list)
    intent: str | None = None
    created_at: datetime
