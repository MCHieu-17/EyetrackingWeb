from pydantic import Field

from app.schemas.common import CamelModel


class CourseVisitCreateIn(CamelModel):
    enrollment_id: str
    # Khoá idempotency theo tab/navigation. Cùng key + cùng enrollment
    # trả về visit đang active thay vì tạo trùng.
    visit_key: str | None = Field(default=None, min_length=1, max_length=128)


class CourseVisitEndIn(CamelModel):
    status: str = Field(default="ended", pattern="^(ended)$")


class CourseVisitOut(CamelModel):
    id: str
    enrollment_id: str
    started_at: str
    ended_at: str | None = None
    last_seen_at: str
    status: str
    visit_key: str | None = None


class CourseVisitHeartbeatOut(CamelModel):
    id: str
    last_seen_at: str
