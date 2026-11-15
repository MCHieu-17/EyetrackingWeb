from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.access import get_viewable_course
from app.api.deps import require_roles
from app.db.session import get_db
from app.models.auth import User
from app.models.course import Course, Enrollment, Lesson, Slide
from app.models.gaze import ContentView, CourseVisit, GazeSample, LearningSession
from app.models.profile import StudentProfile
from app.schemas.analytics import (
    CourseVisitRowOut,
    VisitGazeSampleOut,
    VisitSummaryOut,
)
from app.services import analysis

router = APIRouter(tags=["analytics"])


async def _visit_with_course(
    db: AsyncSession, visit_id: str, user: User
) -> tuple[CourseVisit, Course]:
    visit = await db.get(CourseVisit, visit_id)
    if visit is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Không tìm thấy ca học"
        )
    enrollment = await db.get(Enrollment, visit.enrollment_id)
    if enrollment is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đăng ký khóa học"
        )
    course = await get_viewable_course(db, enrollment.course_id, user)
    return visit, course


@router.get(
    "/teacher/courses/{course_id}/visits",
    response_model=list[CourseVisitRowOut],
)
async def list_course_visits(
    course_id: str,
    student_id: str | None = Query(default=None, alias="studentId"),
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_viewable_course(db, course_id, user)

    session_count = (
        select(
            LearningSession.course_visit_id,
            func.count(LearningSession.id).label("lesson_session_count"),
        )
        .group_by(LearningSession.course_visit_id)
        .subquery()
    )
    metric_sum = (
        select(
            LearningSession.course_visit_id,
            func.coalesce(func.sum(ContentView.gaze_count), 0).label("gaze_count"),
            func.coalesce(
                func.sum(ContentView.on_slide_gaze_count), 0
            ).label("on_slide_gaze_count"),
            func.coalesce(
                func.sum(ContentView.tracked_duration_ms), 0
            ).label("tracked_duration_ms"),
        )
        .join(LearningSession, LearningSession.id == ContentView.session_id)
        .group_by(LearningSession.course_visit_id)
        .subquery()
    )

    stmt = (
        select(
            CourseVisit,
            Enrollment.student_id,
            User.full_name,
            User.email,
            StudentProfile.student_code,
            func.coalesce(session_count.c.lesson_session_count, 0),
            func.coalesce(metric_sum.c.gaze_count, 0),
            func.coalesce(metric_sum.c.on_slide_gaze_count, 0),
            func.coalesce(metric_sum.c.tracked_duration_ms, 0),
        )
        .join(Enrollment, Enrollment.id == CourseVisit.enrollment_id)
        .join(User, User.id == Enrollment.student_id)
        .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
        .outerjoin(session_count, session_count.c.course_visit_id == CourseVisit.id)
        .outerjoin(metric_sum, metric_sum.c.course_visit_id == CourseVisit.id)
        .where(Enrollment.course_id == course.id)
        .order_by(CourseVisit.started_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if student_id:
        stmt = stmt.where(Enrollment.student_id == student_id)
    if from_time is not None:
        stmt = stmt.where(CourseVisit.started_at >= from_time)
    if to_time is not None:
        stmt = stmt.where(CourseVisit.started_at <= to_time)

    rows = (await db.execute(stmt)).all()
    return [
        CourseVisitRowOut(
            id=visit.id,
            enrollment_id=visit.enrollment_id,
            student_id=student_id_value,
            student_name=full_name or email or student_id_value,
            student_code=student_code or "",
            course_id=course.id,
            started_at=visit.started_at.isoformat(),
            ended_at=visit.ended_at.isoformat() if visit.ended_at else None,
            last_seen_at=visit.last_seen_at.isoformat(),
            status=visit.status,
            lesson_session_count=int(lesson_count),
            gaze_count=int(gaze_count),
            on_slide_gaze_count=int(on_slide_count),
            tracked_duration_ms=int(dwell_ms),
        )
        for (
            visit,
            student_id_value,
            full_name,
            email,
            student_code,
            lesson_count,
            gaze_count,
            on_slide_count,
            dwell_ms,
        ) in rows
    ]


@router.get(
    "/teacher/students/{student_id}/visits",
    response_model=list[CourseVisitRowOut],
)
async def list_student_visits(
    student_id: str,
    course_id: str = Query(alias="courseId"),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    return await list_course_visits(
        course_id=course_id,
        student_id=student_id,
        from_time=None,
        to_time=None,
        limit=limit,
        offset=offset,
        user=user,
        db=db,
    )


@router.get(
    "/teacher/visits/{visit_id}/gaze",
    response_model=list[VisitGazeSampleOut],
)
async def list_visit_gaze(
    visit_id: str,
    slide_id: str | None = Query(default=None, alias="slideId"),
    aoi_label: str | None = Query(default=None, alias="aoiLabel"),
    aoi_code: str | None = Query(default=None, alias="aoiCode"),
    limit: int = Query(default=1000, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    visit, _ = await _visit_with_course(db, visit_id, user)

    stmt = (
        select(
            GazeSample,
            ContentView.id,
            LearningSession.id,
            Lesson.id,
            Lesson.title,
            Slide.id,
            Slide.title,
            Slide.page_number,
        )
        .join(ContentView, ContentView.id == GazeSample.content_view_id)
        .join(LearningSession, LearningSession.id == ContentView.session_id)
        .join(Lesson, Lesson.id == LearningSession.lesson_id)
        .outerjoin(Slide, Slide.id == ContentView.slide_id)
        .where(LearningSession.course_visit_id == visit.id)
        .order_by(GazeSample.event_time, GazeSample.sequence)
        .offset(offset)
        .limit(limit)
    )
    if slide_id:
        stmt = stmt.where(ContentView.slide_id == slide_id)
    if aoi_label:
        stmt = stmt.where(GazeSample.aoi_label == aoi_label)
    elif aoi_code:
        stmt = stmt.where(
            or_(
                GazeSample.aoi_label == aoi_code,
                GazeSample.aoi_codes.contains([aoi_code]),
            )
        )

    rows = (await db.execute(stmt)).all()
    return [
        VisitGazeSampleOut(
            id=sample.id,
            event_time=sample.event_time.isoformat(),
            sequence=sample.sequence,
            content_view_id=content_view_id,
            session_id=session_id,
            lesson_id=lesson_id,
            lesson_title=lesson_title,
            slide_id=slide_id_value,
            slide_title=slide_title,
            page_number=page_number,
            viewport_x=sample.viewport_x,
            viewport_y=sample.viewport_y,
            original_viewport_x=sample.original_viewport_x,
            original_viewport_y=sample.original_viewport_y,
            slide_x=sample.slide_x,
            slide_y=sample.slide_y,
            aoi_label=sample.aoi_label,
            aoi_codes=list(sample.aoi_codes or []),
            status=sample.status,
            quality_flags=sample.quality_flags or {},
        )
        for (
            sample,
            content_view_id,
            session_id,
            lesson_id,
            lesson_title,
            slide_id_value,
            slide_title,
            page_number,
        ) in rows
    ]


@router.get("/teacher/visits/{visit_id}/summary", response_model=VisitSummaryOut)
async def summarize_visit(
    visit_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    visit, course = await _visit_with_course(db, visit_id, user)
    row = (
        await db.execute(
            select(
                func.count(func.distinct(LearningSession.id)),
                func.count(ContentView.id),
                func.coalesce(func.sum(ContentView.gaze_count), 0),
                func.coalesce(func.sum(ContentView.on_slide_gaze_count), 0),
                func.coalesce(func.sum(ContentView.tracked_duration_ms), 0),
                func.coalesce(func.sum(ContentView.fixation_count), 0),
            )
            .select_from(LearningSession)
            .outerjoin(ContentView, ContentView.session_id == LearningSession.id)
            .where(LearningSession.course_visit_id == visit.id)
        )
    ).one()
    enrollment = await db.get(Enrollment, visit.enrollment_id)
    return VisitSummaryOut(
        visit_id=visit.id,
        enrollment_id=visit.enrollment_id,
        student_id=enrollment.student_id if enrollment else "",
        course_id=course.id,
        started_at=visit.started_at.isoformat(),
        ended_at=visit.ended_at.isoformat() if visit.ended_at else None,
        status=visit.status,
        lesson_session_count=int(row[0] or 0),
        content_view_count=int(row[1] or 0),
        gaze_count=int(row[2] or 0),
        on_slide_gaze_count=int(row[3] or 0),
        tracked_duration_ms=int(row[4] or 0),
        fixation_count=int(row[5] or 0),
    )


@router.get("/teacher/visits/{visit_id}/export")
async def export_visit(
    visit_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    visit, _ = await _visit_with_course(db, visit_id, user)
    return StreamingResponse(
        analysis.export_visit_lines(visit.id),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f'attachment; filename="visit-{visit.id}-gaze.jsonl"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/teacher/lessons/{lesson_id}/export")
async def export_lesson_analysis(
    lesson_id: str,
    scope: str | None = Query(default=None, pattern="^(slide|ui)$"),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.api.access import get_lesson_viewable

    await get_lesson_viewable(db, lesson_id, user)
    has_data = (
        await db.execute(
            select(ContentView.id)
            .join(LearningSession, LearningSession.id == ContentView.session_id)
            .where(LearningSession.lesson_id == lesson_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if has_data is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Chưa có dữ liệu phân tích"
        )
    suffix = f"-{scope}" if scope else ""
    return StreamingResponse(
        analysis.export_lines(lesson_id, scope=scope),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": (
                f'attachment; filename="lesson-{lesson_id}{suffix}-gaze.jsonl"'
            ),
            "Cache-Control": "no-store",
        },
    )
