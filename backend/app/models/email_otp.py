"""Challenge OTP đăng nhập sinh viên (bảng `email_otps`).

Chỉ lưu HMAC-SHA256 của mã, không lưu mã thô. Mỗi email có tối đa một
challenge đang hoạt động nhờ partial unique index `ux_email_otps_active_email`.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    SmallInteger,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmailOtp(Base):
    __tablename__ = "email_otps"
    __table_args__ = (
        CheckConstraint(
            "attempts >= 0", name="email_otps_attempts_check"
        ),
        CheckConstraint(
            "max_attempts > 0", name="email_otps_max_attempts_check"
        ),
        Index("idx_email_otps_email_created", "email", text("created_at DESC")),
        Index("idx_email_otps_created_at", "created_at"),
        Index(
            "ux_email_otps_active_email",
            "email",
            unique=True,
            postgresql_where=text(
                "consumed_at IS NULL AND invalidated_at IS NULL"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    attempts: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    max_attempts: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("5")
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    requested_ip: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
