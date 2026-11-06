from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
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
    from app.models.auth import User
    from app.models.media import MediaAsset
    from app.models.profile import TeacherProfile


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        Index("idx_courses_owner", "owner_id"),
        Index("idx_courses_archived", "archived_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("teacher_profiles.user_id", ondelete="RESTRICT"), nullable=False
    )
    created_by: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    show_gaze_dot: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    require_calibration: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    published_version_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey(
            "course_versions.id",
            name="courses_published_version_fkey",
            ondelete="SET NULL",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    owner: Mapped["TeacherProfile"] = relationship(lazy="joined")
    creator: Mapped["User"] = relationship(lazy="joined")
    published_version: Mapped["CourseVersion | None"] = relationship(
        foreign_keys=[published_version_id], post_update=True
    )
    versions: Mapped[list["CourseVersion"]] = relationship(
        back_populates="course",
        foreign_keys="CourseVersion.course_id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    enrollments: Mapped[list["Enrollment"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", lazy="selectin"
    )


class CourseTeacher(Base):
    __tablename__ = "course_teachers"
    __table_args__ = (Index("idx_course_teachers_teacher", "teacher_id"),)

    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True
    )
    teacher_id: Mapped[str] = mapped_column(
        ForeignKey("teacher_profiles.user_id", ondelete="CASCADE"), primary_key=True
    )
    assigned_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
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

    course: Mapped["Course"] = relationship(back_populates="enrollments", lazy="joined")


class CourseVersion(Base):
    __tablename__ = "course_versions"
    __table_args__ = (
        UniqueConstraint("course_id", "version_no"),
        CheckConstraint(
            "state IN ('draft', 'published', 'archived')",
            name="course_versions_state_check",
        ),
        CheckConstraint("version_no > 0", name="course_versions_version_no_check"),
        CheckConstraint("generation > 0", name="course_versions_generation_check"),
        Index(
            "ux_course_versions_one_draft",
            "course_id",
            unique=True,
            postgresql_where=text("state = 'draft'"),
        ),
        Index("idx_course_versions_course_state", "course_id", "state"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'draft'")
    )
    generation: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    thumbnail_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT")
    )
    created_by: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )

    course: Mapped["Course"] = relationship(
        back_populates="versions", foreign_keys=[course_id]
    )
    modules: Mapped[list["CourseVersionModule"]] = relationship(
        back_populates="course_version",
        cascade="all, delete-orphan",
        order_by="CourseVersionModule.position",
        lazy="selectin",
    )
    items: Mapped[list["CourseVersionItem"]] = relationship(
        back_populates="course_version",
        cascade="all, delete-orphan",
        order_by="CourseVersionItem.position",
        lazy="selectin",
    )


class CourseVersionModule(Base):
    __tablename__ = "course_version_modules"
    __table_args__ = (
        UniqueConstraint("course_version_id", "position"),
        UniqueConstraint("course_version_id", "module_key"),
        UniqueConstraint("id", "course_version_id"),
        CheckConstraint("position >= 0", name="course_version_modules_position_check"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    course_version_id: Mapped[str] = mapped_column(
        ForeignKey("course_versions.id", ondelete="CASCADE"), nullable=False
    )
    module_key: Mapped[str] = mapped_column(
        UUID(as_uuid=False), nullable=False, server_default=text("gen_random_uuid()")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    course_version: Mapped["CourseVersion"] = relationship(back_populates="modules")
    items: Mapped[list["CourseVersionItem"]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="CourseVersionItem.position",
        lazy="selectin",
        overlaps="items",
    )


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (
        CheckConstraint("kind IN ('lesson', 'quiz')", name="lessons_kind_check"),
        Index("idx_lessons_course_kind", "course_id", "kind"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    versions: Mapped[list["LessonVersion"]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="LessonVersion.version_no",
        lazy="selectin",
    )
    slides: Mapped[list["Slide"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", lazy="selectin"
    )


class LessonVersion(Base):
    __tablename__ = "lesson_versions"
    __table_args__ = (
        UniqueConstraint("lesson_id", "version_no"),
        UniqueConstraint("id", "lesson_id"),
        CheckConstraint(
            "state IN ('draft', 'published', 'archived')",
            name="lesson_versions_state_check",
        ),
        CheckConstraint("version_no > 0", name="lesson_versions_version_no_check"),
        Index(
            "ux_lesson_versions_one_draft",
            "lesson_id",
            unique=True,
            postgresql_where=text("state = 'draft'"),
        ),
        Index("idx_lesson_versions_lesson_state", "lesson_id", "state"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    lesson_id: Mapped[str] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'draft'")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )

    lesson: Mapped["Lesson"] = relationship(back_populates="versions")
    slides: Mapped[list["LessonVersionSlide"]] = relationship(
        back_populates="lesson_version",
        cascade="all, delete-orphan",
        order_by="LessonVersionSlide.position",
        lazy="selectin",
    )


class CourseVersionItem(Base):
    __tablename__ = "course_version_items"
    __table_args__ = (
        UniqueConstraint("course_version_id", "position"),
        UniqueConstraint("course_version_id", "lesson_id"),
        UniqueConstraint("id", "course_version_id"),
        ForeignKeyConstraint(
            ["module_id", "course_version_id"],
            ["course_version_modules.id", "course_version_modules.course_version_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["lesson_version_id", "lesson_id"],
            ["lesson_versions.id", "lesson_versions.lesson_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("position >= 0", name="course_version_items_position_check"),
        Index("idx_course_version_items_lesson", "lesson_id"),
        Index("idx_course_version_items_lesson_version", "lesson_version_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    course_version_id: Mapped[str] = mapped_column(
        ForeignKey("course_versions.id", ondelete="CASCADE"), nullable=False
    )
    module_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    lesson_id: Mapped[str] = mapped_column(
        ForeignKey("lessons.id", ondelete="RESTRICT"), nullable=False
    )
    lesson_version_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    course_version: Mapped["CourseVersion"] = relationship(
        back_populates="items", overlaps="items"
    )
    module: Mapped["CourseVersionModule"] = relationship(
        back_populates="items", overlaps="course_version,items"
    )
    lesson: Mapped["Lesson"] = relationship()
    lesson_version: Mapped["LessonVersion"] = relationship(overlaps="lesson")


class Slide(Base):
    __tablename__ = "slides"
    __table_args__ = (Index("idx_slides_lesson", "lesson_id"),)

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    lesson_id: Mapped[str] = mapped_column(
        ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    lesson: Mapped["Lesson"] = relationship(back_populates="slides")
    versions: Mapped[list["SlideVersion"]] = relationship(
        back_populates="slide",
        cascade="all, delete-orphan",
        order_by="SlideVersion.revision_no",
        lazy="selectin",
    )


class SlideVersion(Base):
    __tablename__ = "slide_versions"
    __table_args__ = (
        UniqueConstraint("slide_id", "revision_no"),
        UniqueConstraint("id", "slide_id"),
        CheckConstraint("revision_no > 0", name="slide_versions_revision_no_check"),
        CheckConstraint(
            "source_page IS NULL OR source_page > 0",
            name="slide_versions_source_page_check",
        ),
        Index("idx_slide_versions_slide", "slide_id"),
        Index("idx_slide_versions_image_asset", "image_asset_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slide_id: Mapped[str] = mapped_column(
        ForeignKey("slides.id", ondelete="CASCADE"), nullable=False
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    image_asset_id: Mapped[str] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"), nullable=False
    )
    source_pdf_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT")
    )
    source_page: Mapped[int | None] = mapped_column(Integer)
    render_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_by: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    slide: Mapped["Slide"] = relationship(back_populates="versions")
    image_asset: Mapped["MediaAsset"] = relationship(
        foreign_keys=[image_asset_id], lazy="joined"
    )
    source_pdf_asset: Mapped["MediaAsset | None"] = relationship(
        foreign_keys=[source_pdf_asset_id]
    )


class LessonVersionSlide(Base):
    __tablename__ = "lesson_version_slides"
    __table_args__ = (
        UniqueConstraint("lesson_version_id", "position"),
        UniqueConstraint("lesson_version_id", "slide_id"),
        UniqueConstraint("id", "lesson_version_id"),
        ForeignKeyConstraint(
            ["slide_version_id", "slide_id"],
            ["slide_versions.id", "slide_versions.slide_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "position >= 0", name="lesson_version_slides_position_check"
        ),
        Index("idx_lesson_version_slides_slide_version", "slide_version_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    lesson_version_id: Mapped[str] = mapped_column(
        ForeignKey("lesson_versions.id", ondelete="CASCADE"), nullable=False
    )
    slide_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    slide_version_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=text("''")
    )
    is_key: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    lesson_version: Mapped["LessonVersion"] = relationship(back_populates="slides")
    slide_version: Mapped["SlideVersion"] = relationship(lazy="joined")


class ContentAuditEvent(Base):
    __tablename__ = "content_audit_events"
    __table_args__ = (
        CheckConstraint(
            "action IN ('publish', 'archive', 'restore')",
            name="content_audit_events_action_check",
        ),
        Index("idx_content_audit_course", "course_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    actor_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    course_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("course_versions.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    request_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
