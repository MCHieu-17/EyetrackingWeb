from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.api.access import get_viewable_course
from app.api.deps import can_access_course, require_roles
from app.core.config import settings
from app.core.rediscache import get_json, set_json
from app.db.session import get_db
from app.models.auth import User
from app.models.course import Course, Enrollment, Lesson, Slide
from app.models.gaze import ContentView, CourseVisit, GazeSample, LearningSession
from app.models.profile import StudentProfile
from app.schemas.analytics import (
    AoiHeatmapIn,
    AoiHeatmapOut,
    AoiSummaryIn,
    AoiSummaryOut,
    CourseVisitRowOut,
    ReplaySamplesPageOut,
    VisitGazeSampleOut,
    VisitReplayOut,
    VisitSummaryOut,
)
from app.services import analysis
from app.services.analytics import replay as replay_service
from app.services.analytics import summary as summary_service

router = APIRouter(tags=["analytics"])

# Cache ngắn cho màn Trực quan hoá; roster tươi hơn nhờ invalidate khi thêm/xoá.
_LIST_CACHE_TTL_SECONDS = 5
_REPLAY_CACHE_TTL_SECONDS = 5


async def _visit_with_course(
    db: AsyncSession, visit_id: str, user: User
) -> tuple[
    CourseVisit, Course, Enrollment, User, StudentProfile | None
]:
    row = (
        await db.execute(
            select(CourseVisit, Course, Enrollment, User, StudentProfile)
            .join(Enrollment, Enrollment.id == CourseVisit.enrollment_id)
            .join(Course, Course.id == Enrollment.course_id)
            .join(User, User.id == Enrollment.student_id)
            .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
            .where(CourseVisit.id == visit_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Không tìm thấy ca học"
        )
    visit, course, enrollment, student, profile = row
    if not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return visit, course, enrollment, student, profile


@router.get(
    "/teacher/courses/{course_id}/visits",
    response_model=list[CourseVisitRowOut],
)
async def list_course_visits(
    course_id: str,
    student_id: str | None = Query(default=None, alias="studentId"),
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    include_short: bool = Query(default=True, alias="includeShort"),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_viewable_course(db, course_id, user)

    cache_key = (
        f"course:visits:{course.id}:{student_id or '-'}:"
        f"{from_time.isoformat() if from_time else '-'}:"
        f"{to_time.isoformat() if to_time else '-'}:"
        f"{int(include_short)}:{limit}:{offset}"
    )
    cached = await get_json(cache_key)
    if isinstance(cached, list):
        return [CourseVisitRowOut.model_validate(item) for item in cached]

    # Lấy page ca học trước, sau đó aggregate đúng các ca trong page. Session
    # count và metrics chạy trong cùng statement với page (2 subquery 1:1).
    base_filters = [Enrollment.course_id == course.id]
    if student_id:
        base_filters.append(Enrollment.student_id == student_id)
    if from_time is not None:
        base_filters.append(CourseVisit.started_at >= from_time)
    if to_time is not None:
        base_filters.append(CourseVisit.started_at <= to_time)

    visit_page = (
        select(CourseVisit.id.label("visit_id"))
        .join(Enrollment, Enrollment.id == CourseVisit.enrollment_id)
        .where(*base_filters)
        .order_by(CourseVisit.started_at.desc())
        .offset(offset)
        .limit(limit)
        .cte("visit_page")
    )

    session_counts = (
        select(
            LearningSession.course_visit_id.label("visit_id"),
            func.count(LearningSession.id).label("session_count"),
        )
        .where(
            LearningSession.course_visit_id.in_(select(visit_page.c.visit_id))
        )
        .group_by(LearningSession.course_visit_id)
        .subquery()
    )

    visit_alias = aliased(CourseVisit)
    dwell_ok = (
        summary_service.view_dwell_ms_expr(visit_alias)
        >= settings.content_view_min_dwell_ms
    )

    def _metric_sum(column):
        summed = func.sum(column)
        if not include_short:
            summed = summed.filter(dwell_ok)
        return func.coalesce(summed, 0)

    metric_select = (
        select(
            LearningSession.course_visit_id.label("visit_id"),
            _metric_sum(ContentView.gaze_count).label("gaze_count"),
            _metric_sum(ContentView.on_slide_gaze_count).label(
                "on_slide_gaze_count"
            ),
            _metric_sum(ContentView.tracked_duration_ms).label(
                "tracked_duration_ms"
            ),
        )
        .join(ContentView, ContentView.session_id == LearningSession.id)
    )
    if not include_short:
        # Dwell filter cần course_visits.ended_at; bỏ join khi không lọc.
        metric_select = metric_select.join(
            visit_alias, visit_alias.id == LearningSession.course_visit_id
        )
    metrics = (
        metric_select.where(
            LearningSession.course_visit_id.in_(select(visit_page.c.visit_id))
        )
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
            session_counts.c.session_count,
            metrics.c.gaze_count,
            metrics.c.on_slide_gaze_count,
            metrics.c.tracked_duration_ms,
        )
        .join(visit_page, visit_page.c.visit_id == CourseVisit.id)
        .join(Enrollment, Enrollment.id == CourseVisit.enrollment_id)
        .join(User, User.id == Enrollment.student_id)
        .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
        .outerjoin(session_counts, session_counts.c.visit_id == CourseVisit.id)
        .outerjoin(metrics, metrics.c.visit_id == CourseVisit.id)
        .order_by(CourseVisit.started_at.desc())
    )

    rows = (await db.execute(stmt)).all()
    out = [
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
            lesson_session_count=int(session_count or 0),
            gaze_count=int(gaze_count or 0),
            on_slide_gaze_count=int(on_slide_gaze_count or 0),
            tracked_duration_ms=int(tracked_duration_ms or 0),
        )
        for (
            visit,
            student_id_value,
            full_name,
            email,
            student_code,
            session_count,
            gaze_count,
            on_slide_gaze_count,
            tracked_duration_ms,
        ) in rows
    ]
    await set_json(
        cache_key,
        [item.model_dump(mode="json") for item in out],
        _LIST_CACHE_TTL_SECONDS,
    )
    return out


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
        include_short=True,
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
    after_time: datetime | None = Query(default=None, alias="afterTime"),
    after_id: int | None = Query(default=None, alias="afterId", ge=0),
    limit: int = Query(default=1000, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    visit, *_ = await _visit_with_course(db, visit_id, user)
    if (after_time is None) != (after_id is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="afterTime và afterId phải đi cùng nhau",
        )

    view_stmt = (
        select(ContentView.id)
        .join(LearningSession, LearningSession.id == ContentView.session_id)
        .where(LearningSession.course_visit_id == visit.id)
    )
    if slide_id:
        view_stmt = view_stmt.where(ContentView.slide_id == slide_id)
    view_ids = list((await db.execute(view_stmt)).scalars())
    if not view_ids:
        return []

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
        .where(GazeSample.content_view_id.in_(view_ids))
        .order_by(GazeSample.event_time, GazeSample.id)
        .limit(limit)
    )
    if after_time is not None and after_id is not None:
        stmt = stmt.where(
            tuple_(GazeSample.event_time, GazeSample.id)
            > (after_time, after_id)
        )
    elif offset:
        stmt = stmt.offset(offset)
    if aoi_label:
        stmt = stmt.where(GazeSample.aoi_label == aoi_label)

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
            slide_x=sample.slide_x,
            slide_y=sample.slide_y,
            aoi_label=sample.aoi_label,
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


@router.get("/teacher/visits/{visit_id}/replay", response_model=VisitReplayOut)
async def get_visit_replay(
    visit_id: str,
    include_short: bool = Query(default=True, alias="includeShort"),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    visit, course, enrollment, student, profile = await _visit_with_course(
        db, visit_id, user
    )
    cache_key = f"visit:replay:{visit.id}:{int(include_short)}"
    cached = await get_json(cache_key)
    if isinstance(cached, dict):
        return VisitReplayOut.model_validate(cached)

    out = await replay_service.visit_replay(
        db,
        visit,
        course,
        enrollment=enrollment,
        student=student,
        profile=profile,
        include_short=include_short,
    )
    await set_json(
        cache_key, out.model_dump(mode="json"), _REPLAY_CACHE_TTL_SECONDS
    )
    return out


@router.get(
    "/teacher/visits/{visit_id}/samples",
    response_model=ReplaySamplesPageOut,
)
async def list_replay_samples(
    visit_id: str,
    content_view_id: str = Query(alias="contentViewId"),
    after_time: datetime | None = Query(default=None, alias="afterTime"),
    after_id: int | None = Query(default=None, alias="afterId", ge=0),
    limit: int = Query(default=2000, ge=1, le=5000),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    visit, *_ = await _visit_with_course(db, visit_id, user)
    if (after_time is None) != (after_id is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="afterTime và afterId phải đi cùng nhau",
        )
    try:
        return await replay_service.visit_samples(
            db,
            visit,
            content_view_id=content_view_id,
            after_time=after_time,
            after_id=after_id,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/teacher/visits/{visit_id}/summary", response_model=VisitSummaryOut)
async def summarize_visit(
    visit_id: str,
    include_short: bool = Query(default=True, alias="includeShort"),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    visit, course, enrollment, *_ = await _visit_with_course(
        db, visit_id, user
    )
    min_dwell_ms = settings.content_view_min_dwell_ms
    rows = (
        await db.execute(
            select(ContentView, LearningSession)
            .join(LearningSession, LearningSession.id == ContentView.session_id)
            .where(LearningSession.course_visit_id == visit.id)
            .order_by(LearningSession.started_at, ContentView.sequence_no)
        )
    ).all()
    # Số session của ca không phụ thuộc bộ lọc lượt xem ngắn.
    lesson_session_count = int(
        (
            await db.execute(
                select(func.count(LearningSession.id)).where(
                    LearningSession.course_visit_id == visit.id
                )
            )
        ).scalar_one()
        or 0
    )

    now = datetime.now(timezone.utc)
    short_view_count = 0
    content_view_count = 0
    gaze_count = on_slide_gaze_count = tracked_duration_ms = fixation_count = 0
    for view, session in rows:
        dwell_ms = replay_service.content_view_dwell_ms(view, session, visit, now)
        counted = dwell_ms >= min_dwell_ms
        if not counted:
            short_view_count += 1
        if not include_short and not counted:
            continue
        content_view_count += 1
        gaze_count += view.gaze_count
        on_slide_gaze_count += view.on_slide_gaze_count
        tracked_duration_ms += view.tracked_duration_ms
        fixation_count += view.fixation_count

    return VisitSummaryOut(
        visit_id=visit.id,
        enrollment_id=visit.enrollment_id,
        student_id=enrollment.student_id if enrollment else "",
        course_id=course.id,
        started_at=visit.started_at.isoformat(),
        ended_at=visit.ended_at.isoformat() if visit.ended_at else None,
        status=visit.status,
        lesson_session_count=lesson_session_count,
        content_view_count=content_view_count,
        gaze_count=gaze_count,
        on_slide_gaze_count=on_slide_gaze_count,
        tracked_duration_ms=tracked_duration_ms,
        fixation_count=fixation_count,
        min_dwell_ms=min_dwell_ms,
        short_view_count=short_view_count,
    )


@router.post(
    "/teacher/courses/{course_id}/analytics/aoi-summary",
    response_model=AoiSummaryOut,
)
async def get_aoi_summary(
    course_id: str,
    body: AoiSummaryIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_viewable_course(db, course_id, user)
    return await summary_service.aoi_summary(db, course, body)


@router.post(
    "/teacher/courses/{course_id}/analytics/heatmap",
    response_model=AoiHeatmapOut,
)
async def get_aoi_heatmap(
    course_id: str,
    body: AoiHeatmapIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_viewable_course(db, course_id, user)
    return await summary_service.aoi_heatmap(db, course, body)


@router.get("/teacher/visits/{visit_id}/export")
async def export_visit(
    visit_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    visit, *_ = await _visit_with_course(db, visit_id, user)
    await db.close()
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
    await db.close()
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
