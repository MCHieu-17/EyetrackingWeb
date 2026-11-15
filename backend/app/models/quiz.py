from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    REAL,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.course import Enrollment, Lesson


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        UniqueConstraint("enrollment_id", "lesson_id", "attempt_no"),
        CheckConstraint(
            "status IN ('in_progress', 'submitted', 'expired')",
            name="quiz_attempts_status_check",
        ),
        CheckConstraint("attempt_no > 0", name="quiz_attempts_attempt_no_check"),
        CheckConstraint(
            "jsonb_typeof(answers) = 'object'",
            name="quiz_attempts_answers_object_check",
        ),
        CheckConstraint(
            "jsonb_typeof(grading) = 'object'",
            name="quiz_attempts_grading_object_check",
        ),
        CheckConstraint(
            "jsonb_typeof(quiz_snapshot) = 'object'",
            name="quiz_attempts_snapshot_object_check",
        ),
        CheckConstraint(
            "score IS NULL OR score >= 0", name="quiz_attempts_score_check"
        ),
        CheckConstraint(
            "max_score IS NULL OR max_score >= 0",
            name="quiz_attempts_max_score_check",
        ),
        Index(
            "ux_quiz_attempts_one_in_progress",
            "enrollment_id",
            "lesson_id",
            unique=True,
            postgresql_where=text("status = 'in_progress'"),
        ),
        Index(
            "idx_quiz_attempts_enrollment",
            "enrollment_id",
            "lesson_id",
            "attempt_no",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    enrollment_id: Mapped[str] = mapped_column(
        ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False
    )
    lesson_id: Mapped[str] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'in_progress'")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quiz_snapshot: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    answers: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    grading: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    score: Mapped[float | None] = mapped_column(REAL)
    max_score: Mapped[float | None] = mapped_column(REAL)

    enrollment: Mapped["Enrollment"] = relationship(lazy="raise")
    lesson: Mapped["Lesson"] = relationship(back_populates="attempts")
