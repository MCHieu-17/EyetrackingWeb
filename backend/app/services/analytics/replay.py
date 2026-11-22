"""Replay một ca học từ gaze thô + layout đã ghi.

Màn hình replay không dựng lại DOM reader hiện tại. Nó dùng đúng
`view_layouts` của từng lượt xem để đặt slide, các vùng AOI UI và điểm gaze
trong cùng một hệ toạ độ. Nhờ vậy giáo viên kiểm tra được mapping thực tế.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Load

from app.core.config import settings
from app.models.aoi import Aoi
from app.models.auth import User
from app.models.course import Enrollment, Lesson, Slide
from app.models.gaze import (
    ContentView,
    CourseVisit,
    GazeSample,
    LearningSession,
    ViewLayout,
)
from app.models.profile import StudentProfile
from app.schemas.analytics import (
    ReplayAoiStatOut,
    ReplayCourseOut,
    ReplayLayoutOut,
    ReplayRectOut,
    ReplaySampleCursorOut,
    ReplaySampleOut,
    ReplaySamplesPageOut,
    ReplaySlideAoiOut,
    ReplayStudentOut,
    ReplayUiRegionOut,
    ReplayViewOut,
    ReplayViewportOut,
    VisitReplayOut,
    VisitSummaryOut,
)
from app.services import aoi_regions, media_storage, metrics

_SLIDE_NO_LABEL_NAME = "Slide chưa đánh dấu"
_UI_NO_LABEL_NAME = "Ngoài vùng giao diện"


def _rect_out(rect: dict) -> ReplayRectOut | None:
    try:
        return ReplayRectOut(
            x_min=float(rect["xMin"]),
            y_min=float(rect["yMin"]),
            x_max=float(rect["xMax"]),
            y_max=float(rect["yMax"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _rects_out(rects: list[dict]) -> list[ReplayRectOut]:
    out: list[ReplayRectOut] = []
    for rect in rects:
        converted = _rect_out(rect)
        if converted is not None:
            out.append(converted)
    return out


def _slide_aois_out(rows: list[Aoi]) -> list[ReplaySlideAoiOut]:
    out: list[ReplaySlideAoiOut] = []
    for row in rows:
        if row.code == metrics.NO_LABEL_CODE:
            continue
        analysis_label = None
        if not row.is_container:
            text = metrics._slide_label_text(row.label, row.code)
            analysis_label = f"{metrics.SLIDE_LABEL_PREFIX}{text}"
        rects = _rects_out([row.geometry or {}]) if row.geometry else []
        if not rects and not row.is_container:
            continue
        out.append(
            ReplaySlideAoiOut(
                code=row.code,
                name=row.name,
                analysis_label=analysis_label,
                kind=row.kind,
                is_container=row.is_container,
                is_active=row.is_active,
                rects=rects,
            )
        )
    return out


def _ui_definitions(rows: list[Aoi]) -> list[dict]:
    return [
        {
            "code": row.code,
            "name": row.name,
            "label": row.label,
            "kind": row.kind,
            "isActive": row.is_active,
        }
        for row in rows
        if row.code != metrics.NO_LABEL_CODE and not row.is_container
    ]


def _stat_name(
    label: str,
    slide_names: dict[str, str],
) -> tuple[str, str]:
    if label == metrics.SLIDE_NO_LABEL:
        return _SLIDE_NO_LABEL_NAME, "slide"
    if label == metrics.UI_NO_LABEL:
        return _UI_NO_LABEL_NAME, "ui"
    if label.startswith(metrics.SLIDE_LABEL_PREFIX):
        return slide_names.get(label, label), "slide"
    return label, "ui"


def _stats_out(
    aoi_stats: dict,
    slide_names: dict[str, str],
) -> list[ReplayAoiStatOut]:
    out: list[ReplayAoiStatOut] = []
    for label, value in (aoi_stats or {}).items():
        if not isinstance(value, dict):
            continue
        name, domain = _stat_name(str(label), slide_names)
        out.append(
            ReplayAoiStatOut(
                label=str(label),
                name=name,
                domain=domain,
                duration_ms=int(value.get("ms", 0) or 0),
                sample_count=int(value.get("samples", 0) or 0),
            )
        )
    out.sort(key=lambda item: (-item.duration_ms, item.label))
    return out


def _view_rows_query(visit_id: str):
    sample_stats = (
        select(
            GazeSample.content_view_id.label("view_id"),
            func.min(GazeSample.event_time).label("first_sample"),
            func.max(GazeSample.event_time).label("last_sample"),
            func.count(GazeSample.id).label("sample_count"),
            func.count(GazeSample.id)
            .filter(GazeSample.status == "ok")
            .label("ok_count"),
        )
        .join(ContentView, ContentView.id == GazeSample.content_view_id)
        .join(LearningSession, LearningSession.id == ContentView.session_id)
        .where(LearningSession.course_visit_id == visit_id)
        .group_by(GazeSample.content_view_id)
        .subquery()
    )
    return (
        select(
            ContentView,
            LearningSession,
            Lesson,
            Slide,
            sample_stats.c.first_sample,
            sample_stats.c.last_sample,
            sample_stats.c.sample_count,
            sample_stats.c.ok_count,
        )
        .join(LearningSession, LearningSession.id == ContentView.session_id)
        .join(Lesson, Lesson.id == LearningSession.lesson_id)
        .outerjoin(Slide, Slide.id == ContentView.slide_id)
        .outerjoin(sample_stats, sample_stats.c.view_id == ContentView.id)
        .where(LearningSession.course_visit_id == visit_id)
        .order_by(LearningSession.started_at, ContentView.sequence_no)
        .options(
            Load(ContentView).load_only(
                ContentView.id,
                ContentView.sequence_no,
                ContentView.surface,
                ContentView.started_at,
                ContentView.ended_at,
                ContentView.gaze_count,
                ContentView.on_slide_gaze_count,
                ContentView.tracked_duration_ms,
                ContentView.fixation_count,
                ContentView.analysis_status,
                ContentView.analysis_version,
                ContentView.aoi_stats,
            ),
            Load(LearningSession).load_only(
                LearningSession.id,
                LearningSession.started_at,
                LearningSession.ended_at,
                LearningSession.viewport_width_px,
                LearningSession.viewport_height_px,
            ),
            Load(Lesson).load_only(
                Lesson.id,
                Lesson.title,
                Lesson.kind,
                Lesson.pdf_asset_id,
            ),
            Load(Slide).load_only(
                Slide.id,
                Slide.title,
                Slide.page_number,
            ),
        )
    )


def content_view_dwell_ms(
    view: ContentView,
    session: LearningSession,
    visit: CourseVisit | None,
    now: datetime,
) -> int:
    """Dwell wall time của một lượt xem, tính bằng mili giây.

    Không dùng khoảng cách sample đầu/cuối: lượt xem không có sample vẫn có
    thời lượng thực tế. Thời điểm kết thúc ưu tiên theo cấp view → session →
    visit, cuối cùng là `now` cho lượt còn mở.
    """
    ended_at = (
        view.ended_at
        or session.ended_at
        or (visit.ended_at if visit is not None else None)
        or now
    )
    return max(0, int((ended_at - view.started_at).total_seconds() * 1000))


async def visit_replay(
    db: AsyncSession,
    visit: CourseVisit,
    course,
    *,
    enrollment: Enrollment,
    student: User,
    profile: StudentProfile | None,
    include_short: bool = True,
) -> VisitReplayOut:
    """Dựng overview replay của một ca học.

    Mặc định trả mọi lượt xem, kể cả lượt ngắn hơn ngưỡng dwell và lượt không
    có sample. `include_short=False` chỉ ẩn các lượt ngắn khỏi `views` và các
    tổng, nhưng vẫn báo `short_view_count`.
    """
    min_dwell_ms = settings.content_view_min_dwell_ms

    rows = (await db.execute(_view_rows_query(visit.id))).all()

    if not rows:
        return VisitReplayOut(
            visit=VisitSummaryOut(
                visit_id=visit.id,
                enrollment_id=visit.enrollment_id,
                student_id=enrollment.student_id,
                course_id=course.id,
                started_at=visit.started_at.isoformat(),
                ended_at=visit.ended_at.isoformat() if visit.ended_at else None,
                status=visit.status,
                min_dwell_ms=min_dwell_ms,
            ),
            student=ReplayStudentOut(
                id=student.id,
                name=student.full_name or student.email,
                code=profile.student_code if profile else "",
                email=student.email,
                enrollment_status=enrollment.status,
            ),
            course=ReplayCourseOut(id=course.id, title=course.title),
            views=[],
            ui_aois=[],
        )

    view_ids = [row[0].id for row in rows]

    layouts = (
        await db.execute(
            select(ViewLayout)
            .where(ViewLayout.content_view_id.in_(view_ids))
            .order_by(ViewLayout.content_view_id, ViewLayout.captured_at, ViewLayout.layout_no)
        )
    ).scalars().all()
    layouts_by_view: dict[str, list[ViewLayout]] = {}
    for layout in layouts:
        layouts_by_view.setdefault(layout.content_view_id, []).append(layout)

    slide_ids = [row[3].id for row in rows if row[3] is not None]
    aoi_filters = [Aoi.ui_schema == "reader-v1"]
    if slide_ids:
        aoi_filters.append(Aoi.slide_id.in_(slide_ids))
    all_aois = (
        (
            await db.execute(
                select(Aoi)
                .where(or_(*aoi_filters))
                .order_by(Aoi.code)
            )
        ).scalars().all()
    )
    slide_aois = [row for row in all_aois if row.slide_id is not None]
    ui_aois = [row for row in all_aois if row.ui_schema == "reader-v1"]
    aois_by_slide: dict[str, list[Aoi]] = {}
    for row in slide_aois:
        if row.slide_id:
            aois_by_slide.setdefault(row.slide_id, []).append(row)

    views: list[ReplayViewOut] = []
    total_gaze = total_on_slide = total_dwell = total_fixations = 0
    session_ids: set[str] = set()

    now = datetime.now(timezone.utc)
    dwell_by_view = {
        content_view.id: content_view_dwell_ms(content_view, session, visit, now)
        for content_view, session, *_rest in rows
    }
    short_view_count = sum(
        1 for dwell_ms in dwell_by_view.values() if dwell_ms < min_dwell_ms
    )
    slide_aoi_cache: dict[str, tuple[list[ReplaySlideAoiOut], dict[str, str]]] = {}

    for (
        content_view,
        session,
        lesson,
        slide,
        first,
        last,
        count,
        ok_count,
    ) in rows:
        session_ids.add(session.id)
        dwell_ms = dwell_by_view[content_view.id]
        counted = dwell_ms >= min_dwell_ms
        if not include_short and not counted:
            continue

        total_gaze += content_view.gaze_count
        total_on_slide += content_view.on_slide_gaze_count
        total_dwell += content_view.tracked_duration_ms
        total_fixations += content_view.fixation_count

        if slide is None:
            slide_out: list[ReplaySlideAoiOut] = []
            slide_names: dict[str, str] = {}
        else:
            cached = slide_aoi_cache.get(slide.id)
            if cached is None:
                slide_out = _slide_aois_out(aois_by_slide.get(slide.id, []))
                slide_names = {
                    item.analysis_label: item.name
                    for item in slide_out
                    if item.analysis_label
                }
                cached = (slide_out, slide_names)
                slide_aoi_cache[slide.id] = cached
            else:
                slide_out, slide_names = cached

        layout_out: list[ReplayLayoutOut] = []
        for layout in layouts_by_view.get(content_view.id, []):
            regions = aoi_regions.ui_regions(ui_aois, layout.elements or [])
            layout_out.append(
                ReplayLayoutOut(
                    id=layout.id,
                    layout_no=layout.layout_no,
                    slide_rect=layout.slide_rect or {},
                    captured_at=layout.captured_at.isoformat(),
                    ui_regions=[
                        ReplayUiRegionOut(
                            code=item["code"],
                            name=item["name"],
                            kind=item["kind"],
                            label=item.get("label"),
                            is_active=item["is_active"],
                            rects=_rects_out(item["rects"]),
                        )
                        for item in regions
                    ],
                )
            )

        pdf_url = (
            media_storage.asset_file_url(lesson.pdf_asset_id)
            if lesson.kind == "lesson" and lesson.pdf_asset_id
            else None
        )

        views.append(
            ReplayViewOut(
                content_view_id=content_view.id,
                sequence_no=content_view.sequence_no,
                surface=content_view.surface,
                session_id=session.id,
                lesson_id=lesson.id,
                lesson_title=lesson.title,
                lesson_kind=lesson.kind,
                slide_id=slide.id if slide else None,
                slide_title=slide.title if slide else None,
                page_number=slide.page_number if slide else None,
                pdf_url=pdf_url,
                started_at=content_view.started_at.isoformat(),
                ended_at=content_view.ended_at.isoformat()
                if content_view.ended_at
                else None,
                first_sample_at=first.isoformat() if first else None,
                last_sample_at=last.isoformat() if last else None,
                sample_count=int(count or 0),
                ok_sample_count=int(ok_count or 0),
                gaze_count=content_view.gaze_count,
                on_slide_gaze_count=content_view.on_slide_gaze_count,
                tracked_duration_ms=content_view.tracked_duration_ms,
                dwell_ms=dwell_ms,
                counted=counted,
                analysis_status=content_view.analysis_status,
                analysis_version=content_view.analysis_version,
                viewport=ReplayViewportOut(
                    width=session.viewport_width_px,
                    height=session.viewport_height_px,
                ),
                slide_aois=slide_out,
                layouts=layout_out,
                aoi_stats=_stats_out(content_view.aoi_stats or {}, slide_names),
            )
        )

    return VisitReplayOut(
        visit=VisitSummaryOut(
            visit_id=visit.id,
            enrollment_id=visit.enrollment_id,
            student_id=enrollment.student_id,
            course_id=course.id,
            started_at=visit.started_at.isoformat(),
            ended_at=visit.ended_at.isoformat() if visit.ended_at else None,
            status=visit.status,
            lesson_session_count=len(session_ids),
            content_view_count=len(views),
            gaze_count=total_gaze,
            on_slide_gaze_count=total_on_slide,
            tracked_duration_ms=total_dwell,
            fixation_count=total_fixations,
            min_dwell_ms=min_dwell_ms,
            short_view_count=short_view_count,
        ),
        student=ReplayStudentOut(
            id=student.id,
            name=student.full_name or student.email,
            code=profile.student_code if profile else "",
            email=student.email,
            enrollment_status=enrollment.status,
        ),
        course=ReplayCourseOut(id=course.id, title=course.title),
        views=views,
        ui_aois=_ui_definitions(list(ui_aois)),
    )


async def visit_samples(
    db: AsyncSession,
    visit: CourseVisit,
    *,
    content_view_id: str,
    after_time: datetime | None = None,
    after_id: int | None = None,
    limit: int = 2000,
) -> ReplaySamplesPageOut:
    """Trả một trang sample của content view trong ca học (keyset pagination)."""
    view = (
        await db.execute(
            select(ContentView)
            .join(LearningSession, LearningSession.id == ContentView.session_id)
            .where(
                ContentView.id == content_view_id,
                LearningSession.course_visit_id == visit.id,
            )
        )
    ).scalar_one_or_none()
    if view is None:
        raise ValueError("content view not in visit")

    first_time = (
        await db.execute(
            select(func.min(GazeSample.event_time)).where(
                GazeSample.content_view_id == view.id
            )
        )
    ).scalar_one_or_none()
    if first_time is None:
        return ReplaySamplesPageOut(content_view_id=view.id, samples=[])

    stmt = (
        select(GazeSample)
        .where(GazeSample.content_view_id == view.id)
        .order_by(GazeSample.event_time, GazeSample.id)
        .limit(limit + 1)
    )
    if after_time is not None and after_id is not None:
        stmt = stmt.where(
            tuple_(GazeSample.event_time, GazeSample.id)
            > (after_time, after_id)
        )

    rows = list((await db.execute(stmt)).scalars())
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    samples = [
        ReplaySampleOut(
            id=sample.id,
            offset_ms=max(
                0,
                int((sample.event_time - first_time).total_seconds() * 1000),
            ),
            event_time=sample.event_time.isoformat(),
            sequence=sample.sequence,
            layout_id=sample.layout_id,
            status=sample.status,
            viewport_x=sample.viewport_x,
            viewport_y=sample.viewport_y,
            slide_x=sample.slide_x,
            slide_y=sample.slide_y,
            aoi_label=sample.aoi_label,
            quality_flags=sample.quality_flags or {},
        )
        for sample in rows
    ]

    cursor = None
    if has_more and rows:
        last = rows[-1]
        cursor = ReplaySampleCursorOut(
            after_time=last.event_time.isoformat(), after_id=last.id
        )

    return ReplaySamplesPageOut(
        content_view_id=view.id, samples=samples, next_cursor=cursor
    )
