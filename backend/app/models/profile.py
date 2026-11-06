from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.auth import User


class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint(
            "gender IN ('male', 'female', 'other')",
            name="user_profiles_gender_check",
        ),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(20))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    user: Mapped["User"] = relationship(back_populates="profile")  # noqa: F821


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    student_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    program: Mapped[str | None] = mapped_column(String(200))

    user: Mapped["User"] = relationship(back_populates="student_profile")  # noqa: F821


class TeacherProfile(Base):
    __tablename__ = "teacher_profiles"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    teacher_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    department: Mapped[str | None] = mapped_column(String(150))

    user: Mapped["User"] = relationship(back_populates="teacher_profile")  # noqa: F821
