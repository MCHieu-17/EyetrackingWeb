from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.helpers import gradient_for
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models.auth import User
from app.models.course import (
    Course,
    CourseVersion,
    CourseVersionItem,
    CourseVersionModule,
    Enrollment,
)
from app.models.profile import UserProfile
from app.schemas.course import CourseSummaryOut, EnrolledCourseOut

router = APIRouter(tags=["enrollments"])


@router.get("/api/me/enrollments", response_model=list[EnrolledCourseOut])
async def my_enrollments(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(Enrollment, Course, CourseVersion, UserProfile)
            .join(Course, Course.id == Enrollment.course_id)
            .outerjoin(
                CourseVersion,
                CourseVersion.id == Course.published_version_id,
            )
            .outerjoin(UserProfile, UserProfile.user_id == Course.owner_id)
            .where(Enrollment.student_id == user.id)
            .order_by(Enrollment.enrolled_at.desc())
        )
    ).all()
    if not rows:
        return []

    out: list[EnrolledCourseOut] = []
    for enrollment, course, version, teacher_profile in rows:
        if version is None:
            continue
        module_count = (
            await db.execute(
                select(func.count(CourseVersionModule.id)).where(
                    CourseVersionModule.course_version_id == version.id
                )
            )
        ).scalar_one()
        lesson_count = (
            await db.execute(
                select(func.count(CourseVersionItem.id)).where(
                    CourseVersionItem.course_version_id == version.id
                )
            )
        ).scalar_one()
        out.append(
            EnrolledCourseOut(
                enrollment_id=enrollment.id,
                enrolled_at=enrollment.enrolled_at,
                status=enrollment.status,
                course=CourseSummaryOut(
                    id=course.id,
                    title=version.title,
                    thumbnail_url=None,
                    teacher_name=(
                        teacher_profile.full_name if teacher_profile else "—"
                    ),
                    module_count=int(module_count),
                    lesson_count=int(lesson_count),
                    gradient=gradient_for(course.id),
                    require_calibration=course.require_calibration,
                ),
            )
        )
    return out


@router.post(
    "/api/courses/{course_id}/enroll",
    status_code=201,
    dependencies=[Depends(rate_limit(10, 60, "enroll"))],
)
async def enroll(
    course_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    course = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    if course.archived_at is not None or course.published_version_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Khóa học chưa được xuất bản"
        )
    existing = (
        await db.execute(
            select(Enrollment).where(
                Enrollment.course_id == course_id, Enrollment.student_id == user.id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Đã đăng ký khóa học này")
    enrollment = Enrollment(course_id=course_id, student_id=user.id)
    db.add(enrollment)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Đã đăng ký khóa học này"
        ) from exc
    await db.refresh(enrollment)
    return {"ok": True, "enrollmentId": enrollment.id}
