from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
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
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import Vector

if TYPE_CHECKING:
    from app.models.course import Course, SlideVersion


class MediaAsset(Base):
    __tablename__ = "media_assets"
    __table_args__ = (
        UniqueConstraint("course_id", "sha256"),
        UniqueConstraint("storage_backend", "object_key"),
        CheckConstraint(
            "storage_backend IN ('local', 'r2')",
            name="media_assets_storage_backend_check",
        ),
        CheckConstraint(
            "state IN ('staging', 'ready', 'failed', 'deleted')",
            name="media_assets_state_check",
        ),
        CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'", name="media_assets_sha256_check"
        ),
        CheckConstraint("byte_size >= 0", name="media_assets_byte_size_check"),
        CheckConstraint(
            "image_width IS NULL OR image_width > 0",
            name="media_assets_image_width_check",
        ),
        CheckConstraint(
            "image_height IS NULL OR image_height > 0",
            name="media_assets_image_height_check",
        ),
        Index("idx_media_assets_course", "course_id"),
        Index("idx_media_assets_state", "state"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    storage_backend: Mapped[str] = mapped_column(String(16), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    image_width: Mapped[int | None] = mapped_column(Integer)
    image_height: Mapped[int | None] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'staging'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    course: Mapped["Course"] = relationship()


class SlideDocument(Base):
    __tablename__ = "slide_documents"
    __table_args__ = (
        CheckConstraint(
            "ingestion_state IN ('pending', 'ready', 'failed')",
            name="slide_documents_ingestion_state_check",
        ),
        Index("idx_slide_documents_state", "ingestion_state"),
        Index(
            "idx_slide_documents_tsv",
            "content_tsv",
            postgresql_using="gin",
        ),
        Index(
            "idx_slide_documents_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
    )

    slide_version_id: Mapped[str] = mapped_column(
        ForeignKey("slide_versions.id", ondelete="CASCADE"), primary_key=True
    )
    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    transcript: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    content_tsv: Mapped[str | None] = mapped_column(TSVECTOR)
    ingestion_state: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'pending'")
    )
    ingestion_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    slide_version: Mapped["SlideVersion"] = relationship()
