"""API cho "ca học" cấp khóa (course_visits).

Mỗi lần sinh viên vào trang khóa tạo một visit. Các learning_sessions
(mỗi lesson một session) trỏ về visit hiện tại qua course_visit_id.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.auth import User
from app.models.course import Enrollment
from app.models.gaze import CourseVisit
from app.schemas.visit import (
    CourseVisitCreateIn,
    CourseVisitEndIn,
    CourseVisitHeartbeatOut,
    CourseVisitOut,
)
from app.services.gaze_views import close_open_views_for_visit

router = APIRouter(tags=["course-visits"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _visit_out(visit: CourseVisit) -> CourseVisitOut:
    return CourseVisitOut(
        id=visit.id,
        enrollment_id=visit.enrollment_id,
        started_at=visit.started_at.isoformat(),
        ended_at=visit.ended_at.isoformat() if visit.ended_at else None,
        last_seen_at=visit.last_seen_at.isoformat(),
        status=visit.status,
        visit_key=visit.visit_key,
    )


async def _enrollment_for_user(
    db: AsyncSession, enrollment_id: str, user: User
) -> Enrollment:
    enrollment = await db.get(Enrollment, enrollment_id)
    if enrollment is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đăng ký khóa học"
        )
    if enrollment.student_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    if enrollment.status == "dropped":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Đăng ký khóa học đã bị hủy"
        )
    return enrollment


async def _visit_for_user(
    db: AsyncSession, visit_id: str, user: User
) -> CourseVisit:
    visit = await db.get(CourseVisit, visit_id)
    if visit is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Không tìm thấy ca học"
        )
    enrollment = await db.get(Enrollment, visit.enrollment_id)
    if enrollment is None or enrollment.student_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return visit


async def get_or_create_visit(
    db: AsyncSession,
    *,
    enrollment: Enrollment,
    visit_key: str | None,
) -> CourseVisit:
    """Idempotent theo (enrollment, visit_key); tạo mới nếu chưa có."""
    if visit_key:
        existing = (
            await db.execute(
                select(CourseVisit).where(
                    CourseVisit.enrollment_id == enrollment.id,
                    CourseVisit.visit_key == visit_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    visit = CourseVisit(
        enrollment_id=enrollment.id,
        visit_key=visit_key,
        status="active",
        started_at=_now(),
        last_seen_at=_now(),
    )
    db.add(visit)
    await db.flush()
    return visit


async def active_visit_for_enrollment(
    db: AsyncSession, enrollment_id: str
) -> CourseVisit | None:
    return (
        await db.execute(
            select(CourseVisit)
            .where(
                CourseVisit.enrollment_id == enrollment_id,
                CourseVisit.status == "active",
            )
            .order_by(CourseVisit.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


@router.post("/api/course-visits", response_model=CourseVisitOut, status_code=201)
async def create_course_visit(
    body: CourseVisitCreateIn,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    enrollment = await _enrollment_for_user(db, body.enrollment_id, user)
    visit = await get_or_create_visit(
        db, enrollment=enrollment, visit_key=body.visit_key
    )
    await db.commit()
    await db.refresh(visit)
    return _visit_out(visit)


@router.get("/api/course-visits/active", response_model=CourseVisitOut | None)
async def get_active_course_visit(
    enrollment_id: str = Query(alias="enrollmentId"),
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    enrollment = await _enrollment_for_user(db, enrollment_id, user)
    visit = await active_visit_for_enrollment(db, enrollment.id)
    return _visit_out(visit) if visit is not None else None


@router.patch("/api/course-visits/{visit_id}", response_model=CourseVisitOut)
async def end_course_visit(
    visit_id: str,
    body: CourseVisitEndIn,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    visit = await _visit_for_user(db, visit_id, user)
    if visit.status == "active":
        now = _now()
        visit.status = body.status
        visit.ended_at = now
        visit.last_seen_at = now
        visit.updated_at = now
        # Đóng mọi lượt xem còn mở của các phiên học thuộc ca này.
        await close_open_views_for_visit(db, visit.id, now)
        await db.commit()
        await db.refresh(visit)
    return _visit_out(visit)


@router.post(
    "/api/course-visits/{visit_id}/heartbeat",
    response_model=CourseVisitHeartbeatOut,
)
async def heartbeat_course_visit(
    visit_id: str,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    visit = await _visit_for_user(db, visit_id, user)
    if visit.status != "active":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "visit_closed", "message": "Ca học đã kết thúc"},
        )
    now = _now()
    visit.last_seen_at = now
    visit.updated_at = now
    await db.commit()
    await db.refresh(visit)
    return CourseVisitHeartbeatOut(
        id=visit.id, last_seen_at=visit.last_seen_at.isoformat()
    )
