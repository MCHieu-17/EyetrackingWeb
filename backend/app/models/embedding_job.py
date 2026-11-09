from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmbeddingJob(Base):
    """Job đồng bộ embedding/RAG ingest, dùng chung giữa các replica.

    `target_id` trỏ tới `course_versions.id` hoặc `lesson_versions.id` tùy
    `kind`; không có FK vì quan hệ polymorphic.
    """

    __tablename__ = "embedding_jobs"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('course_version', 'lesson_version')",
            name="embedding_jobs_kind_check",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="embedding_jobs_status_check",
        ),
        CheckConstraint("attempts >= 0", name="embedding_jobs_attempts_check"),
        CheckConstraint("max_attempts > 0", name="embedding_jobs_max_attempts_check"),
        Index("idx_embedding_jobs_status_created", "status", "created_at"),
        Index("idx_embedding_jobs_kind_target", "kind", "target_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    include_draft: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    force: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'pending'")
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("3")
    )
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
