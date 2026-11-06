from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    REAL,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
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
    from app.models.calibration import Calibration
    from app.models.course import CourseVersionItem, Enrollment, LessonVersionSlide
    from app.models.quiz import QuizAttempt


class LearningSession(Base):
    __tablename__ = "learning_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'aborted', 'expired')",
            name="learning_sessions_status_check",
        ),
        CheckConstraint(
            "clock_uncertainty_ms IS NULL OR clock_uncertainty_ms >= 0",
            name="learning_sessions_clock_uncertainty_check",
        ),
        Index(
            "idx_learning_sessions_enrollment",
            "enrollment_id",
            "started_at",
        ),
        Index("idx_learning_sessions_item", "course_version_item_id"),
        Index("idx_learning_sessions_status", "status"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    enrollment_id: Mapped[str] = mapped_column(
        ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False
    )
    course_version_item_id: Mapped[str] = mapped_column(
        ForeignKey("course_version_items.id", ondelete="RESTRICT"), nullable=False
    )
    quiz_attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("quiz_attempts.id", ondelete="SET NULL")
    )
    calibration_id: Mapped[str | None] = mapped_column(
        ForeignKey("calibrations.id", ondelete="RESTRICT")
    )
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    tracking_consent: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("true")
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'in_progress'")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    clock_uncertainty_ms: Mapped[int | None] = mapped_column(Integer)

    enrollment: Mapped["Enrollment"] = relationship()
    course_version_item: Mapped["CourseVersionItem"] = relationship()
    quiz_attempt: Mapped["QuizAttempt | None"] = relationship()
    calibration: Mapped["Calibration | None"] = relationship()
    presentations: Mapped[list["ContentPresentation"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ContentPresentation.sequence_no",
        lazy="selectin",
    )


class ContentPresentation(Base):
    __tablename__ = "content_presentations"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence_no"),
        UniqueConstraint("id", "session_id"),
        CheckConstraint(
            "surface IN ('lesson', 'quiz')",
            name="content_presentations_surface_check",
        ),
        CheckConstraint(
            "sequence_no >= 0", name="content_presentations_sequence_check"
        ),
        Index(
            "idx_content_presentations_session", "session_id", "started_at"
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False
    )
    lesson_version_slide_id: Mapped[str | None] = mapped_column(
        ForeignKey("lesson_version_slides.id", ondelete="RESTRICT")
    )
    surface: Mapped[str] = mapped_column(String(16), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session: Mapped["LearningSession"] = relationship(back_populates="presentations")
    lesson_version_slide: Mapped["LessonVersionSlide | None"] = relationship()


class GazeBatch(Base):
    __tablename__ = "gaze_batches"
    __table_args__ = (
        UniqueConstraint("session_id", "batch_id"),
        UniqueConstraint("session_id", "batch_no"),
        UniqueConstraint("id", "session_id"),
        ForeignKeyConstraint(
            ["presentation_id", "session_id"],
            ["content_presentations.id", "content_presentations.session_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("batch_no >= 0", name="gaze_batches_batch_no_check"),
        CheckConstraint(
            "sequence_start >= 0", name="gaze_batches_sequence_start_check"
        ),
        CheckConstraint(
            "sequence_end >= sequence_start",
            name="gaze_batches_sequence_range_check",
        ),
        CheckConstraint(
            "payload_hash ~ '^[0-9a-f]{64}$'",
            name="gaze_batches_payload_hash_check",
        ),
        CheckConstraint(
            "received_count >= 0", name="gaze_batches_received_count_check"
        ),
        CheckConstraint(
            "stored_count >= 0", name="gaze_batches_stored_count_check"
        ),
        CheckConstraint(
            "duplicate_count >= 0", name="gaze_batches_duplicate_count_check"
        ),
        CheckConstraint(
            "rejected_count >= 0", name="gaze_batches_rejected_count_check"
        ),
        Index("idx_gaze_batches_session", "session_id", "batch_no"),
        Index("idx_gaze_batches_presentation", "presentation_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False
    )
    presentation_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    layout_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("aoi_layout_snapshots.id", ondelete="SET NULL")
    )
    batch_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    batch_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sequence_start: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sequence_end: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payload_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    received_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    stored_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    duplicate_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    rejected_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    session: Mapped["LearningSession"] = relationship()
    presentation: Mapped["ContentPresentation"] = relationship(overlaps="session")


class GazeSample(Base):
    __tablename__ = "gaze_samples"
    __table_args__ = (
        ForeignKeyConstraint(
            ["batch_id", "session_id"],
            ["gaze_batches.id", "gaze_batches.session_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "status IN ('ok', 'no_face', 'error', 'offscreen')",
            name="gaze_samples_status_check",
        ),
        CheckConstraint(
            "(status = 'ok' AND viewport_x IS NOT NULL AND viewport_y IS NOT NULL) "
            "OR (status <> 'ok' AND viewport_x IS NULL AND viewport_y IS NULL)",
            name="gaze_samples_status_coords_check",
        ),
        CheckConstraint(
            "viewport_x IS NULL OR (viewport_x > -100 AND viewport_x < 100)",
            name="gaze_samples_viewport_x_check",
        ),
        CheckConstraint(
            "viewport_y IS NULL OR (viewport_y > -100 AND viewport_y < 100)",
            name="gaze_samples_viewport_y_check",
        ),
        CheckConstraint("sequence >= 0", name="gaze_samples_sequence_check"),
        CheckConstraint(
            "capture_monotonic_ns >= 0",
            name="gaze_samples_capture_monotonic_check",
        ),
        Index("idx_gaze_samples_session", "session_id", "event_time"),
        Index("idx_gaze_samples_batch", "batch_id", "event_time"),
        {"postgresql_partition_by": "RANGE (event_time)"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    batch_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    capture_monotonic_ns: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    viewport_x: Mapped[float | None] = mapped_column(REAL)
    viewport_y: Mapped[float | None] = mapped_column(REAL)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    quality_flags: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    batch: Mapped["GazeBatch"] = relationship()
