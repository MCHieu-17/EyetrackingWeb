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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.course import Course


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
            "page_count IS NULL OR page_count > 0",
            name="media_assets_page_count_check",
        ),
        Index("idx_media_assets_course", "course_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    storage_backend: Mapped[str] = mapped_column(String(16), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'staging'")
    )
    page_count: Mapped[int | None] = mapped_column(Integer)
    source_format: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    course: Mapped["Course"] = relationship(lazy="raise")
