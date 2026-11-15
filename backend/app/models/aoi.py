from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.course import Slide


class Aoi(Base):
    __tablename__ = "aois"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('text', 'image', 'table', 'drawing', 'custom', 'ui', 'system')",
            name="aois_kind_check",
        ),
        CheckConstraint(
            "(slide_id IS NOT NULL AND ui_schema IS NULL) "
            "OR (slide_id IS NULL AND ui_schema IS NOT NULL)",
            name="aois_target_check",
        ),
        Index(
            "ux_aois_slide_code",
            "slide_id",
            "code",
            unique=True,
            postgresql_where=text("slide_id IS NOT NULL"),
        ),
        Index(
            "ux_aois_ui_code",
            "ui_schema",
            "code",
            unique=True,
            postgresql_where=text("ui_schema IS NOT NULL"),
        ),
        Index(
            "ux_aois_slide_label",
            "slide_id",
            "label",
            unique=True,
            postgresql_where=text("slide_id IS NOT NULL AND label IS NOT NULL"),
        ),
        Index("idx_aois_slide", "slide_id"),
        Index("idx_aois_parent", "parent_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slide_id: Mapped[str | None] = mapped_column(
        ForeignKey("slides.id", ondelete="CASCADE")
    )
    ui_schema: Mapped[str | None] = mapped_column(String(64))
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Nhãn phân tích ổn định cho leaf slide (AOI_1, AOI_2, ...).
    # NULL với container/no_label/UI AOI.
    label: Mapped[str | None] = mapped_column(String(64))
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("aois.id", ondelete="SET NULL")
    )
    geometry: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    is_container: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'custom'")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    slide: Mapped["Slide | None"] = relationship(back_populates="ao_is")
    parent: Mapped["Aoi | None"] = relationship(remote_side=[id])
