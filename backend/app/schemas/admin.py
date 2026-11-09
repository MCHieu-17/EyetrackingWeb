from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel


class StudentAdminOut(CamelModel):
    id: str
    name: str
    email: str
    student_code: str | None = None
    program: str | None = None
    avatar_url: str | None = None
    created_at: datetime


class PromoteStudentIn(CamelModel):
    teacher_code: str | None = Field(default=None, max_length=30)
    department: str | None = Field(default=None, max_length=150)


class PromoteStudentOut(CamelModel):
    ok: bool = True
    teacher_code: str
