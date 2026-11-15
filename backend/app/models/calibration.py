from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    REAL,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.auth import User


class GazeCalibration(Base):
    __tablename__ = "gaze_calibrations"
    __table_args__ = (
        CheckConstraint(
            "model_hash ~ '^[0-9a-f]{64}$'",
            name="gaze_calibrations_model_hash_check",
        ),
        CheckConstraint(
            "viewport_width_px > 0",
            name="gaze_calibrations_viewport_width_check",
        ),
        CheckConstraint(
            "viewport_height_px > 0",
            name="gaze_calibrations_viewport_height_check",
        ),
        CheckConstraint("device_pixel_ratio > 0", name="gaze_calibrations_dpr_check"),
        CheckConstraint("num_points > 0", name="gaze_calibrations_num_points_check"),
        Index(
            "idx_gaze_calibrations_lookup",
            "user_id",
            "device_fingerprint",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    device_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    model_ubj: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    model_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    viewport_width_px: Mapped[int] = mapped_column(Integer, nullable=False)
    viewport_height_px: Mapped[int] = mapped_column(Integer, nullable=False)
    device_pixel_ratio: Mapped[float] = mapped_column(REAL, nullable=False)
    screen_x_px: Mapped[int | None] = mapped_column(Integer)
    screen_y_px: Mapped[int | None] = mapped_column(Integer)
    num_points: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("25")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    user: Mapped["User"] = relationship(lazy="raise")
