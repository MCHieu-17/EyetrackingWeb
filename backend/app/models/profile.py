from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.auth import User


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    student_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    program: Mapped[str | None] = mapped_column(String(200))

    user: Mapped["User"] = relationship(back_populates="student_profile")


class TeacherProfile(Base):
    __tablename__ = "teacher_profiles"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    teacher_code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    department: Mapped[str | None] = mapped_column(String(150))

    user: Mapped["User"] = relationship(back_populates="teacher_profile")
