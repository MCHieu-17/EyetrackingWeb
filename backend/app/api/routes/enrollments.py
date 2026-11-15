from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.helpers import gradient_for
from app.core.rediscache import get_json, set_json
from app.db.session import get_db
from app.models.auth import User
from app.models.course import Course, CourseModule, Enrollment, Lesson
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
            CourseModule.course_id,
            func.count(CourseModule.id).label("module_count"),
        )
        .group_by(CourseModule.course_id)
        .subquery()
    )
    lesson_counts = (
        select(
            CourseModule.course_id,
            func.count(Lesson.id).label("lesson_count"),
        )
        .join(Lesson, Lesson.module_id == CourseModule.id)
        .group_by(CourseModule.course_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(
                Enrollment,
                Course,
                User.full_name,
                func.coalesce(module_counts.c.module_count, 0),
                func.coalesce(lesson_counts.c.lesson_count, 0),
            )
            .join(Course, Course.id == Enrollment.course_id)
            .outerjoin(User, User.id == Course.owner_id)
            .outerjoin(module_counts, module_counts.c.course_id == Course.id)
            .outerjoin(lesson_counts, lesson_counts.c.course_id == Course.id)
            .where(Enrollment.student_id == user.id, Course.status == "published")
            .order_by(Enrollment.enrolled_at.desc())
        )
    ).all()
    if not rows:
        return []

    out = [
        EnrolledCourseOut(
            enrollment_id=enrollment.id,
            enrolled_at=enrollment.enrolled_at,
            status=enrollment.status,
            course=CourseSummaryOut(
                id=course.id,
                title=course.title,
                thumbnail_url=course.thumbnail_url,
                teacher_name=teacher_name or "—",
                module_count=int(module_count),
                lesson_count=int(lesson_count),
                gradient=gradient_for(course.id),
                require_calibration=course.require_calibration,
            ),
        )
        for enrollment, course, teacher_name, module_count, lesson_count in rows
    ]
    await set_json(
        cache_key,
        [item.model_dump(mode="json") for item in out],
        30,
    )
    return out
