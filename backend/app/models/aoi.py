"""AOI DOM-anchored + mapping gaze ↔ AOI.

`aoi_definitions` chỉ là catalog (code/name/parent/selector). Toạ độ thật của
từng phần tử DOM nằm ở `aoi_layout_rects`, do frontend đo bằng
`getBoundingClientRect()` và gửi lên theo từng layout snapshot.

`gaze_aoi_hits` là bảng derived: rebuild từ `gaze_raw_samples` +
`aoi_layout_rects` + `aoi_definitions`. Nhờ vậy có thể thêm AOI mới sau khi đã
thu dữ liệu mà vẫn map lại được.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AoiDefinition(Base):
    """Catalog AOI toàn hệ thống.

    `code` là khoá ổn định dùng trong `data-aoi` ở frontend và trong
    `aoi_layout_rects.aoi_code`. `parent_id` cho phép phân cấp:
    chatbot → chat-messages → chat-user-message.
    """

    __tablename__ = "aoi_definitions"
    __table_args__ = (
        CheckConstraint(
            "(scope = 'slide') = (lesson_content_id IS NOT NULL)",
            name="aoi_definitions_scope_content_check",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(String(16), server_default=text("'viewport'"))
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("aoi_definitions.id", ondelete="SET NULL")
    )
    selector: Mapped[str | None] = mapped_column(String(255))
    lesson_content_id: Mapped[str | None] = mapped_column(
        ForeignKey("lesson_contents.id", ondelete="CASCADE")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AoiLayoutSnapshot(Base):
    """Layout DOM tại một thời điểm của phiên học."""

    __tablename__ = "aoi_layout_snapshots"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    learning_session_id: Mapped[str] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    viewport_width_px: Mapped[int] = mapped_column(Integer, nullable=False)
    viewport_height_px: Mapped[int] = mapped_column(Integer, nullable=False)
    layout_key: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class AoiLayoutRect(Base):
    """Rect thật (chuẩn hoá viewport) của một phần tử `[data-aoi]`.

    Một `aoi_code` có thể có nhiều rect trong cùng snapshot (nhiều bong bóng
    chat user, nhiều đoạn AI, ...).
    """

    __tablename__ = "aoi_layout_rects"
    __table_args__ = (
        CheckConstraint(
            "x_min < x_max AND y_min < y_max",
            name="aoi_layout_rects_order_check",
        ),
        CheckConstraint(
            "x_min >= 0 AND x_max <= 1 AND y_min >= 0 AND y_max <= 1",
            name="aoi_layout_rects_bounds_check",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("aoi_layout_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    aoi_code: Mapped[str] = mapped_column(String(64), nullable=False)
    x_min: Mapped[float] = mapped_column(REAL, nullable=False)
    y_min: Mapped[float] = mapped_column(REAL, nullable=False)
    x_max: Mapped[float] = mapped_column(REAL, nullable=False)
    y_max: Mapped[float] = mapped_column(REAL, nullable=False)


class GazeAoiHit(Base):
    """Một sample gaze rơi vào một AOI. Derived, rebuild được."""

    __tablename__ = "gaze_aoi_hits"
    __table_args__ = (UniqueConstraint("gaze_sample_id", "aoi_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    learning_session_id: Mapped[str] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False
    )
    gaze_sample_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    aoi_id: Mapped[str] = mapped_column(
        ForeignKey("aoi_definitions.id", ondelete="CASCADE"), nullable=False
    )
