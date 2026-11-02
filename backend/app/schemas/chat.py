"""Schema request/response cho API chat."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import CamelModel


class ChatCitation(CamelModel):
    document_id: str
    title: str
    location: str
    lesson_id: str | None = None
    lesson_title: str = ""
    slide_id: str | None = None
    slide_index: int | None = None
    image_url: str = ""
    snippet: str = ""
    score: float = 0.0


class ChatSendIn(CamelModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: UUID | None = None
    lesson_id: UUID | None = None
    assignment_id: UUID | None = None


class ChatReplyOut(CamelModel):
    session_id: str
    answer: str
    citations: list[ChatCitation] = Field(default_factory=list)
    intent: str | None = None
    verified: bool = True


class ChatSessionOut(CamelModel):
    id: str
    course_id: str
    lesson_id: str | None = None
    assignment_id: str | None = None
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
