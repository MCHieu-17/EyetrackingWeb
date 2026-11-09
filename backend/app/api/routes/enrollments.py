from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.api.deps import get_current_user
from app.core.helpers import gradient_for
from app.core.rediscache import get_json, set_json
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
    cache_key = f"student:enrollments:{user.id}"
    cached = await get_json(cache_key)
    if isinstance(cached, list):
        return [EnrolledCourseOut.model_validate(item) for item in cached]

    module_counts = (
        select(
            CourseVersionModule.course_version_id,
            func.count(CourseVersionModule.id).label("module_count"),
        )
        .group_by(CourseVersionModule.course_version_id)
        .subquery()
    )
    lesson_counts = (
        select(
            CourseVersionItem.course_version_id,
            func.count(CourseVersionItem.id).label("lesson_count"),
        )
        .group_by(CourseVersionItem.course_version_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(
                Enrollment,
                Course,
                CourseVersion,
                UserProfile,
                func.coalesce(module_counts.c.module_count, 0),
                func.coalesce(lesson_counts.c.lesson_count, 0),
            )
            .join(Course, Course.id == Enrollment.course_id)
            .outerjoin(
                CourseVersion,
                CourseVersion.id == Course.published_version_id,
            )
            .outerjoin(UserProfile, UserProfile.user_id == Course.owner_id)
            .outerjoin(
                module_counts,
                module_counts.c.course_version_id == CourseVersion.id,
            )
            .outerjoin(
                lesson_counts,
                lesson_counts.c.course_version_id == CourseVersion.id,
            )
            .where(Enrollment.student_id == user.id)
            .order_by(Enrollment.enrolled_at.desc())
            .options(
                raiseload(Enrollment.course),
                raiseload(Course.versions),
                raiseload(Course.enrollments),
                raiseload(Course.owner),
                raiseload(Course.creator),
                raiseload(CourseVersion.modules),
                raiseload(CourseVersion.items),
            )
        )
    ).all()
    if not rows:
        return []

    out: list[EnrolledCourseOut] = []
    for (
        enrollment,
        course,
        version,
        teacher_profile,
        module_count,
        lesson_count,
    ) in rows:
        if version is None:
            continue
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
    await set_json(
        cache_key,
        [item.model_dump(mode="json") for item in out],
        30,
    )
    return out
