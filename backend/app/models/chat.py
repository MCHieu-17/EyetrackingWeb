from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.course import Course, CourseVersion, Lesson, LessonVersion
    from app.models.quiz import QuizAttempt


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index(
            "idx_chat_sessions_student_course",
            "student_id",
            "course_id",
            "updated_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    student_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    course_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("course_versions.id", ondelete="SET NULL")
    )
    lesson_id: Mapped[str | None] = mapped_column(
        ForeignKey("lessons.id", ondelete="SET NULL")
    )
    lesson_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("lesson_versions.id", ondelete="SET NULL")
    )
    quiz_attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("quiz_attempts.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=text("'Phiên mới'")
    )
    context_key: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    course: Mapped["Course"] = relationship()
    course_version: Mapped["CourseVersion | None"] = relationship()
    lesson: Mapped["Lesson | None"] = relationship()
    lesson_version: Mapped["LessonVersion | None"] = relationship()
    quiz_attempt: Mapped["QuizAttempt | None"] = relationship()
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
        lazy="selectin",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('student', 'assistant')",
            name="chat_messages_role_check",
        ),
        CheckConstraint(
            "jsonb_typeof(citations) = 'array'",
            name="chat_messages_citations_array_check",
        ),
        Index("idx_chat_messages_session", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    intent: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
