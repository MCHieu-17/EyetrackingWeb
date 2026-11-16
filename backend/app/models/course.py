from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import Vector

if TYPE_CHECKING:
    from app.models.aoi import Aoi
    from app.models.auth import User
    from app.models.gaze import ContentView, CourseVisit
    from app.models.media import MediaAsset
    from app.models.quiz import QuizAttempt


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name="courses_status_check",
        ),
        Index("idx_courses_owner", "owner_id"),
        Index("idx_courses_status", "status"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'draft'")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    show_gaze_dot: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("false")
    )
    require_calibration: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    owner: Mapped["User"] = relationship(
        foreign_keys=[owner_id], lazy="raise"
    )
    creator: Mapped["User"] = relationship(
        foreign_keys=[created_by], lazy="raise"
    )
    modules: Mapped[list["CourseModule"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="CourseModule.position",
        lazy="raise",
        passive_deletes=True,
    )
    enrollments: Mapped[list["Enrollment"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", lazy="raise",
        passive_deletes=True,
    )


class CourseTeacher(Base):
    __tablename__ = "course_teachers"
    __table_args__ = (Index("idx_course_teachers_teacher", "teacher_id"),)

    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True
    )
    teacher_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("course_id", "student_id"),
        CheckConstraint(
            "status IN ('active', 'completed', 'dropped')",
            name="enrollments_status_check",
        ),
        Index("idx_enrollments_student", "student_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'active'")
    )

    course: Mapped["Course"] = relationship(back_populates="enrollments", lazy="raise")
    course_visits: Mapped[list["CourseVisit"]] = relationship(
        cascade="all, delete-orphan", lazy="raise", passive_deletes=True
    )


class CourseModule(Base):
    __tablename__ = "course_modules"
    __table_args__ = (
        UniqueConstraint("course_id", "position"),
        CheckConstraint("position >= 0", name="course_modules_position_check"),
        Index("idx_course_modules_course", "course_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    course: Mapped["Course"] = relationship(back_populates="modules")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="Lesson.position",
        lazy="raise",
        passive_deletes=True,
    )


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (
        UniqueConstraint("module_id", "position"),
        CheckConstraint("kind IN ('lesson', 'quiz')", name="lessons_kind_check"),
        CheckConstraint("position >= 0", name="lessons_position_check"),
        Index("idx_lessons_module", "module_id"),
        Index("idx_lessons_kind", "kind"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    module_id: Mapped[str] = mapped_column(
        ForeignKey("course_modules.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    pdf_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL")
    )
    quiz_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    module: Mapped["CourseModule"] = relationship(back_populates="lessons")
    pdf_asset: Mapped["MediaAsset | None"] = relationship(lazy="raise")
    slides: Mapped[list["Slide"]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="Slide.position",
        lazy="raise",
        passive_deletes=True,
    )
    attempts: Mapped[list["QuizAttempt"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", lazy="raise",
        passive_deletes=True,
    )


class Slide(Base):
    __tablename__ = "slides"
    __table_args__ = (
        UniqueConstraint("lesson_id", "position"),
        CheckConstraint("position >= 0", name="slides_position_check"),
        CheckConstraint("page_number > 0", name="slides_page_number_check"),
        Index("idx_slides_lesson", "lesson_id"),
        Index("idx_slides_index_status", "index_status"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    lesson_id: Mapped[str] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=text("''")
    )
    transcript: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    content_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('simple', immutable_unaccent(transcript))",
            persisted=True,
        ),
    )
    index_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'none'")
    )
    index_error: Mapped[str | None] = mapped_column(Text)
    pipeline_version: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'v1'")
    )
    model_version: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'v1'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    lesson: Mapped["Lesson"] = relationship(back_populates="slides")
    ao_is: Mapped[list["Aoi"]] = relationship(
        back_populates="slide", cascade="all, delete-orphan", lazy="raise",
        passive_deletes=True,
    )
    content_views: Mapped[list["ContentView"]] = relationship(
        back_populates="slide", lazy="raise", passive_deletes=True
    )
