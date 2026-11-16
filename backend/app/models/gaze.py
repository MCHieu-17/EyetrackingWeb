from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    REAL,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.calibration import GazeCalibration
    from app.models.course import Enrollment, Lesson, Slide
    from app.models.quiz import QuizAttempt


class CourseVisit(Base):
    """Một lần sinh viên vào trang khóa học (ca học cấp khóa)."""

    __tablename__ = "course_visits"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'ended', 'expired')",
            name="course_visits_status_check",
        ),
        Index("idx_course_visits_enrollment", "enrollment_id", "started_at"),
        Index("idx_course_visits_status_seen", "status", "last_seen_at"),
        Index(
            "ux_course_visits_enrollment_key",
            "enrollment_id",
            "visit_key",
            unique=True,
            postgresql_where=text("visit_key IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    enrollment_id: Mapped[str] = mapped_column(
        ForeignKey("enrollments.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'active'")
    )
    visit_key: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    enrollment: Mapped["Enrollment"] = relationship(
        back_populates="course_visits", lazy="raise"
    )
    sessions: Mapped[list["LearningSession"]] = relationship(
        back_populates="course_visit",
        cascade="all, delete-orphan",
        order_by="LearningSession.started_at",
        lazy="raise",
        passive_deletes=True,
    )


class LearningSession(Base):
    __tablename__ = "learning_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'completed', 'aborted', 'expired')",
            name="learning_sessions_status_check",
        ),
        Index("idx_learning_sessions_enrollment", "enrollment_id", "started_at"),
        Index("idx_learning_sessions_lesson", "lesson_id", "started_at"),
        Index("idx_learning_sessions_visit", "course_visit_id", "started_at"),
        Index("idx_learning_sessions_status", "status"),
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
    course_visit_id: Mapped[str | None] = mapped_column(
        ForeignKey("course_visits.id", ondelete="CASCADE")
    )
    quiz_attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("quiz_attempts.id", ondelete="CASCADE")
    )
    calibration_id: Mapped[str | None] = mapped_column(
        ForeignKey("gaze_calibrations.id", ondelete="SET NULL")
    )
    pipeline_version: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'gaze-v1'")
    )
    viewport_width_px: Mapped[int | None] = mapped_column(Integer)
    viewport_height_px: Mapped[int | None] = mapped_column(Integer)
    calibration_width_px: Mapped[int | None] = mapped_column(Integer)
    calibration_height_px: Mapped[int | None] = mapped_column(Integer)
    device_pixel_ratio: Mapped[float | None] = mapped_column(REAL)
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

    enrollment: Mapped["Enrollment"] = relationship(lazy="raise")
    lesson: Mapped["Lesson"] = relationship(lazy="raise")
    course_visit: Mapped["CourseVisit | None"] = relationship(
        back_populates="sessions", lazy="raise"
    )
    quiz_attempt: Mapped["QuizAttempt | None"] = relationship(lazy="raise")
    calibration: Mapped["GazeCalibration | None"] = relationship(lazy="raise")
    views: Mapped[list["ContentView"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ContentView.sequence_no",
        lazy="raise",
        passive_deletes=True,
    )


class ContentView(Base):
    __tablename__ = "content_views"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence_no"),
        CheckConstraint("surface IN ('lesson', 'quiz')", name="content_views_surface_check"),
        CheckConstraint("sequence_no >= 0", name="content_views_sequence_check"),
        CheckConstraint("gaze_count >= 0", name="content_views_gaze_count_check"),
        CheckConstraint(
            "on_slide_gaze_count >= 0", name="content_views_on_slide_count_check"
        ),
        CheckConstraint("tracked_duration_ms >= 0", name="content_views_duration_check"),
        CheckConstraint(
            "fixation_count >= 0", name="content_views_fixation_count_check"
        ),
        CheckConstraint(
            "analysis_status IN ('pending', 'running', 'ready', 'failed')",
            name="content_views_analysis_status_check",
        ),
        Index("idx_content_views_session", "session_id", "started_at"),
        Index("idx_content_views_slide", "slide_id"),
        Index("idx_content_views_analysis", "analysis_status"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False
    )
    slide_id: Mapped[str | None] = mapped_column(
        ForeignKey("slides.id", ondelete="CASCADE")
    )
    surface: Mapped[str] = mapped_column(String(16), nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gaze_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    on_slide_gaze_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    tracked_duration_ms: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    fixation_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    heatmap_grid: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # Thống kê dẫn xuất theo từng nhãn AOI trong lượt xem:
    # {"SLIDE_AOI_X": {"ms": 1234, "samples": 45}}.
    aoi_stats: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    analysis_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'pending'")
    )
    analysis_version: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'gaze-metrics-v3'")
    )
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session: Mapped["LearningSession"] = relationship(back_populates="views")
    slide: Mapped["Slide | None"] = relationship(back_populates="content_views")
    layouts: Mapped[list["ViewLayout"]] = relationship(
        back_populates="content_view",
        cascade="all, delete-orphan",
        order_by="ViewLayout.captured_at",
        lazy="raise",
        passive_deletes=True,
    )
    samples: Mapped[list["GazeSample"]] = relationship(
        back_populates="content_view", cascade="all, delete-orphan", lazy="raise",
        passive_deletes=True,
    )


class ViewLayout(Base):
    __tablename__ = "view_layouts"
    __table_args__ = (
        UniqueConstraint("content_view_id", "layout_no"),
        CheckConstraint("layout_no >= 0", name="view_layouts_layout_no_check"),
        Index("idx_view_layouts_view", "content_view_id", "captured_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    content_view_id: Mapped[str] = mapped_column(
        ForeignKey("content_views.id", ondelete="CASCADE"), nullable=False
    )
    layout_no: Mapped[int] = mapped_column(Integer, nullable=False)
    slide_rect: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    elements: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    content_view: Mapped["ContentView"] = relationship(back_populates="layouts")
    samples: Mapped[list["GazeSample"]] = relationship(back_populates="layout")


class GazeSample(Base):
    __tablename__ = "gaze_samples"
    __table_args__ = (
        UniqueConstraint("content_view_id", "client_batch_id", "sequence"),
        CheckConstraint("sequence >= 0", name="gaze_samples_sequence_check"),
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
        Index("idx_gaze_samples_view_time", "content_view_id", "event_time"),
        Index("idx_gaze_samples_event_time", "event_time"),
        Index(
            "idx_gaze_samples_aoi_label",
            "aoi_label",
            postgresql_where=text("aoi_label IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    content_view_id: Mapped[str] = mapped_column(
        ForeignKey("content_views.id", ondelete="CASCADE"), nullable=False
    )
    layout_id: Mapped[str | None] = mapped_column(
        ForeignKey("view_layouts.id", ondelete="SET NULL")
    )
    client_batch_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    viewport_x: Mapped[float | None] = mapped_column(REAL)
    viewport_y: Mapped[float | None] = mapped_column(REAL)
    slide_x: Mapped[float | None] = mapped_column(REAL)
    slide_y: Mapped[float | None] = mapped_column(REAL)
    aoi_label: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    quality_flags: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    content_view: Mapped["ContentView"] = relationship(back_populates="samples")
    layout: Mapped["ViewLayout | None"] = relationship(back_populates="samples")
