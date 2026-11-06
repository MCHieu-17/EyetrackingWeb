from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    REAL,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.auth import User


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("owner_id", "fingerprint"),
        Index("idx_devices_owner", "owner_id"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    current_calibration_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey(
            "calibrations.id",
            name="devices_current_calibration_fkey",
            ondelete="SET NULL",
            deferrable=True,
            initially="DEFERRED",
            use_alter=True,
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    owner: Mapped["User"] = relationship()
    current_calibration: Mapped["Calibration | None"] = relationship(
        foreign_keys=[current_calibration_id], post_update=True
    )


class Calibration(Base):
    __tablename__ = "calibrations"
    __table_args__ = (
        CheckConstraint(
            "model_hash ~ '^[0-9a-f]{64}$'",
            name="calibrations_model_hash_check",
        ),
        CheckConstraint("mae_px IS NULL OR mae_px >= 0", name="calibrations_mae_check"),
        CheckConstraint(
            "viewport_width_px > 0", name="calibrations_viewport_width_check"
        ),
        CheckConstraint(
            "viewport_height_px > 0", name="calibrations_viewport_height_check"
        ),
        CheckConstraint(
            "device_pixel_ratio > 0", name="calibrations_dpr_check"
        ),
        Index("idx_calibrations_device", "device_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    device_id: Mapped[str] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    model_ubj: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    model_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    mae_px: Mapped[float | None] = mapped_column(REAL)
    viewport_width_px: Mapped[int] = mapped_column(Integer, nullable=False)
    viewport_height_px: Mapped[int] = mapped_column(Integer, nullable=False)
    device_pixel_ratio: Mapped[float] = mapped_column(REAL, nullable=False)
    config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    device: Mapped["Device"] = relationship(foreign_keys=[device_id])


class CalibrationSettings(Base):
    __tablename__ = "calibration_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="calibration_settings_single_row_check"),
        CheckConstraint(
            "threshold BETWEEN 0.01 AND 0.30",
            name="calibration_settings_threshold_check",
        ),
    )

    id: Mapped[int] = mapped_column(
        SmallInteger, primary_key=True, server_default=text("1")
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    threshold: Mapped[float] = mapped_column(
        REAL, nullable=False, server_default=text("0.12")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
