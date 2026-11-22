"""Tổng hợp thời lượng nhìn theo AOI cho dashboard giáo viên.

Nguồn số liệu là `content_views.aoi_stats` do worker metrics tính. Nhờ vậy
dashboard chỉ đọc một hàng cho mỗi lượt xem, không quét toàn bộ gaze thô.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import (
    BigInteger,
    Integer,
    String,
    and_,
    cast,
    distinct,
    exists,
    func,
    literal_column,
    or_,
    select,
    true,
    tuple_,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.aoi import Aoi
from app.models.auth import User
from app.models.course import (
    Course,
    CourseModule,
    Enrollment,
    Lesson,
    Slide,
)
from app.models.gaze import ContentView, CourseVisit, GazeSample, LearningSession
from app.models.profile import StudentProfile
from app.schemas.analytics import (
    AoiHeatmapIn,
    AoiHeatmapOut,
    AoiHeatmapSlideOut,
    AoiSummaryAoiOut,
    AoiSummaryIn,
    AoiSummaryLessonOut,
    AoiSummaryMetaOut,
    AoiSummaryOut,
    AoiSummarySlideOut,
    AoiSummaryStudentOut,
    AoiSummaryTotalsOut,
    AoiSummaryVisitOut,
)
from app.services import media_storage, metrics

_SLIDE_NO_LABEL_NAME = "Slide chưa đánh dấu"
_UI_NO_LABEL_NAME = "Ngoài vùng giao diện"


def _is_unlabeled(label: str) -> bool:
    return label in (metrics.SLIDE_NO_LABEL, metrics.UI_NO_LABEL)


def _domain(label: str) -> str:
    return "slide" if label.startswith(metrics.SLIDE_LABEL_PREFIX) else "ui"


def _display_name(label: str, slide_names: dict[str, str]) -> str:
    if label == metrics.SLIDE_NO_LABEL:
        return _SLIDE_NO_LABEL_NAME
    if label == metrics.UI_NO_LABEL:
        return _UI_NO_LABEL_NAME
    if label.startswith(metrics.SLIDE_LABEL_PREFIX):
        return slide_names.get(label, label)
    return label


def _new_aoi(
    label: str,
    *,
    duration_ms: int,
    sample_count: int,
    student_count: int,
    slide_count: int,
    slide_names: dict[str, str],
) -> dict:
    return {
        "label": label,
        "name": _display_name(label, slide_names),
        "domain": _domain(label),
        "duration_ms": duration_ms,
        "sample_count": sample_count,
        "student_count": student_count,
        "slide_count": slide_count,
        "is_unlabeled": _is_unlabeled(label),
    }


def _aoi_rows(bucket: dict[str, dict], *, total_ms: int = 0) -> list[AoiSummaryAoiOut]:
    rows = [
        AoiSummaryAoiOut(
            label=entry["label"],
            name=entry["name"],
            domain=entry["domain"],
            duration_ms=entry["duration_ms"],
            sample_count=entry["sample_count"],
            share=round(entry["duration_ms"] / total_ms, 6) if total_ms else 0.0,
            student_count=entry["student_count"],
            slide_count=entry["slide_count"],
            mixed_slides=(
                entry["label"].startswith(metrics.SLIDE_LABEL_PREFIX)
                and entry["slide_count"] > 1
            ),
            is_unlabeled=entry["is_unlabeled"],
        )
        for entry in bucket.values()
    ]
    rows.sort(key=lambda item: (-item.duration_ms, item.label))
    return rows


def view_dwell_ms_expr(visit_entity=CourseVisit):
    """SQL dwell wall time (ms) của content view trong cùng scope truy vấn.

    Kết thúc ưu tiên view → session → visit → now, khớp với helper Python
    dùng cho replay/tổng hợp ca học. `visit_entity` cho phép truyền alias khi
    bảng course_visits đã xuất hiện ở truy vấn ngoài.
    """
    ended_at = func.coalesce(
        ContentView.ended_at,
        LearningSession.ended_at,
        visit_entity.ended_at,
        func.now(),
    )
    return func.extract("epoch", ended_at - ContentView.started_at) * 1000


def _views_scope(course: Course, body: AoiSummaryIn):
    """Query nền chỉ đọc cột cần; tên hiển thị tính sẵn để aggregate cột phẳng."""
    stmt = (
        select(
            ContentView.id.label("view_id"),
            Lesson.id.label("lesson_id"),
            Lesson.title.label("lesson_title"),
            Lesson.kind.label("lesson_kind"),
            Slide.id.label("slide_id"),
            func.coalesce(
                func.nullif(Slide.title, ""),
                func.concat("Slide ", Slide.position + 1),
            ).label("slide_title"),
            Slide.page_number.label("page_number"),
            Enrollment.status.label("enrollment_status"),
            User.id.label("student_id"),
            func.coalesce(func.nullif(User.full_name, ""), User.email).label(
                "student_name"
            ),
            func.coalesce(StudentProfile.student_code, "").label("student_code"),
            CourseVisit.started_at.label("visit_started_at"),
            LearningSession.started_at.label("session_started_at"),
            func.coalesce(
                cast(CourseVisit.id, String),
                func.concat("session:", cast(LearningSession.id, String)),
            ).label("visit_key"),
            ContentView.tracked_duration_ms,
            ContentView.gaze_count,
            ContentView.on_slide_gaze_count,
            ContentView.aoi_stats,
            ContentView.analysis_status,
            ContentView.analysis_version,
            ContentView.heatmap_grid,
            view_dwell_ms_expr().label("dwell_ms"),
        )
        .join(LearningSession, LearningSession.id == ContentView.session_id)
        .join(Lesson, Lesson.id == LearningSession.lesson_id)
        .outerjoin(Slide, Slide.id == ContentView.slide_id)
        .join(Enrollment, Enrollment.id == LearningSession.enrollment_id)
        .join(User, User.id == Enrollment.student_id)
        .outerjoin(StudentProfile, StudentProfile.user_id == User.id)
        .outerjoin(CourseVisit, CourseVisit.id == LearningSession.course_visit_id)
        .where(Enrollment.course_id == course.id)
    )
    if not body.include_dropped:
        stmt = stmt.where(Enrollment.status != "dropped")
    if body.student_ids:
        stmt = stmt.where(Enrollment.student_id.in_(body.student_ids))
    if body.visit_ids:
        stmt = stmt.where(LearningSession.course_visit_id.in_(body.visit_ids))
    if body.lesson_ids:
        stmt = stmt.where(LearningSession.lesson_id.in_(body.lesson_ids))
    if body.surface != "all":
        stmt = stmt.where(ContentView.surface == body.surface)
    if body.from_time is not None:
        stmt = stmt.where(CourseVisit.started_at >= body.from_time)
    if body.to_time is not None:
        stmt = stmt.where(CourseVisit.started_at <= body.to_time)
    return stmt


def _included(views, body: AoiSummaryIn):
    """Điều kiện "lượt >= ngưỡng"; true() khi bao gồm cả lượt ngắn."""
    if body.include_short:
        return true()
    return views.c.dwell_ms >= settings.content_view_min_dwell_ms


def _totals_stmt(views, included):
    stale = or_(
        views.c.analysis_status != "ready",
        views.c.analysis_version != metrics.ANALYSIS_VERSION,
        and_(
            views.c.gaze_count > 0,
            views.c.aoi_stats == literal_column("'{}'::jsonb"),
        ),
    )
    return select(
        func.count().filter(included).label("content_view_count"),
        func.count()
        .filter(views.c.dwell_ms < settings.content_view_min_dwell_ms)
        .label("short_view_count"),
        func.count(distinct(views.c.visit_key)).filter(included).label("visit_count"),
        func.count(distinct(views.c.student_id))
        .filter(included)
        .label("student_count"),
        cast(
            func.coalesce(func.sum(views.c.tracked_duration_ms).filter(included), 0),
            BigInteger,
        ).label("tracked_ms"),
        cast(
            func.coalesce(func.sum(views.c.gaze_count).filter(included), 0),
            BigInteger,
        ).label("gaze_count"),
        cast(
            func.coalesce(func.sum(views.c.on_slide_gaze_count).filter(included), 0),
            BigInteger,
        ).label("on_slide_count"),
        func.count().filter(and_(included, stale)).label("stale_view_count"),
    ).select_from(views)


def _label_rows_stmt(views, included):
    """Một hàng cho mỗi (nhãn, nhóm) với tổng ms/samples và distinct count."""
    kv = func.jsonb_each(views.c.aoi_stats).table_valued("key", "value")
    ms = cast(kv.c.value.op("->>")(literal_column("'ms'")), BigInteger)
    samples = cast(kv.c.value.op("->>")(literal_column("'samples'")), Integer)
    return (
        select(
            func.grouping(views.c.lesson_id).label("g_lesson"),
            func.grouping(views.c.slide_id).label("g_slide"),
            func.grouping(views.c.student_id).label("g_student"),
            func.grouping(views.c.visit_key).label("g_visit"),
            kv.c.key.label("label"),
            views.c.lesson_id,
            views.c.slide_id,
            views.c.student_id,
            views.c.visit_key,
            cast(func.coalesce(func.sum(ms), 0), BigInteger).label("duration_ms"),
            cast(func.coalesce(func.sum(samples), 0), BigInteger).label("sample_count"),
            func.count(distinct(views.c.student_id)).label("student_count"),
            func.count(distinct(views.c.slide_id)).label("slide_count"),
        )
        .select_from(views)
        .join(kv, true())
        .where(
            included,
            func.jsonb_typeof(kv.c.value) == "object",
            or_(ms != 0, samples != 0),
        )
        .group_by(
            func.grouping_sets(
                kv.c.key,
                tuple_(views.c.lesson_id, kv.c.key),
                tuple_(views.c.slide_id, kv.c.key),
                tuple_(views.c.student_id, kv.c.key),
                tuple_(views.c.visit_key, kv.c.key),
            )
        )
    )


def _base_rows_stmt(views, included):
    """Hàng nền theo từng nhóm để view không có AOI vẫn xuất hiện trong response."""
    return (
        select(
            func.grouping(views.c.lesson_id).label("g_lesson"),
            func.grouping(views.c.slide_id).label("g_slide"),
            func.grouping(views.c.student_id).label("g_student"),
            func.grouping(views.c.visit_key).label("g_visit"),
            views.c.lesson_id,
            views.c.lesson_title,
            views.c.lesson_kind,
            views.c.slide_id,
            views.c.slide_title,
            views.c.page_number,
            views.c.student_id,
            views.c.student_name,
            views.c.student_code,
            views.c.enrollment_status,
            views.c.visit_key,
            func.min(
                func.coalesce(views.c.visit_started_at, views.c.session_started_at)
            ).label("started_at"),
            cast(
                func.coalesce(func.sum(views.c.tracked_duration_ms), 0), BigInteger
            ).label("tracked_ms"),
        )
        .where(included)
        .group_by(
            func.grouping_sets(
                tuple_(views.c.lesson_id, views.c.lesson_title, views.c.lesson_kind),
                tuple_(
                    views.c.slide_id,
                    views.c.slide_title,
                    views.c.page_number,
                    views.c.lesson_id,
                    views.c.lesson_title,
                ),
                tuple_(
                    views.c.student_id,
                    views.c.student_name,
                    views.c.student_code,
                    views.c.enrollment_status,
                ),
                tuple_(views.c.visit_key, views.c.student_id, views.c.student_name),
            )
        )
    )


def _validate_time_range(body: AoiSummaryIn) -> None:
    if (
        body.from_time is not None
        and body.to_time is not None
        and body.from_time > body.to_time
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="'from' phải nhỏ hơn hoặc bằng 'to'",
        )


async def _slide_names(
    db: AsyncSession, slide_ids: list[str]
) -> dict[str, str]:
    if not slide_ids:
        return {}
    rows = (
        await db.execute(
            select(Aoi.label, Aoi.code, Aoi.name).where(
                Aoi.slide_id.in_(slide_ids),
                Aoi.is_container.is_(False),
                Aoi.code != metrics.NO_LABEL_CODE,
            )
        )
    ).all()
    names: dict[str, str] = {}
    for row in rows:
        text = metrics._slide_label_text(row.label, row.code)
        names[f"{metrics.SLIDE_LABEL_PREFIX}{text}"] = row.name
    return names


async def aoi_summary(
    db: AsyncSession, course: Course, body: AoiSummaryIn
) -> AoiSummaryOut:
    _validate_time_range(body)
    views = _views_scope(course, body).subquery()
    included = _included(views, body)

    totals = (await db.execute(_totals_stmt(views, included))).one()
    base_rows = (await db.execute(_base_rows_stmt(views, included))).all()
    label_rows = (await db.execute(_label_rows_stmt(views, included))).all()

    by_aoi: dict[str, dict] = {}
    by_lesson: dict[str, dict] = {}
    by_slide: dict[str, dict] = {}
    by_student: dict[str, dict] = {}
    by_visit: dict[str, dict] = {}

    # Hàng nền: mọi view trong phạm vi đều xuất hiện, kể cả view không có AOI.
    for row in base_rows:
        grouping = (row.g_lesson, row.g_slide, row.g_student, row.g_visit)
        if grouping == (1, 1, 0, 0):
            by_visit.setdefault(
                row.visit_key,
                {
                    "visit_id": row.visit_key,
                    "student_id": row.student_id,
                    "student_name": row.student_name,
                    "started_at": row.started_at.isoformat(),
                    "duration_ms": 0,
                    "tracked_duration_ms": int(row.tracked_ms or 0),
                    "slide_duration_ms": 0,
                    "ui_duration_ms": 0,
                    "unlabeled_duration_ms": 0,
                    "sample_count": 0,
                },
            )
        elif grouping == (1, 1, 0, 1):
            by_student.setdefault(
                row.student_id,
                {
                    "student_id": row.student_id,
                    "student_name": row.student_name,
                    "student_code": row.student_code or "",
                    "enrollment_status": row.enrollment_status,
                    "duration_ms": 0,
                    "sample_count": 0,
                    "aois": {},
                },
            )
        elif grouping == (0, 0, 1, 1):
            if row.slide_id is None:
                continue
            by_slide.setdefault(
                row.slide_id,
                {
                    "slide_id": row.slide_id,
                    "slide_title": row.slide_title,
                    "lesson_id": row.lesson_id,
                    "lesson_title": row.lesson_title,
                    "page_number": row.page_number,
                    "duration_ms": 0,
                    "sample_count": 0,
                    "aois": {},
                },
            )
        elif grouping == (0, 1, 1, 1):
            by_lesson.setdefault(
                row.lesson_id,
                {
                    "lesson_id": row.lesson_id,
                    "lesson_title": row.lesson_title,
                    "lesson_kind": row.lesson_kind,
                    "duration_ms": 0,
                    "sample_count": 0,
                    "aois": {},
                },
            )

    slide_names = await _slide_names(db, sorted(by_slide))

    totals_by_label = {"labeled": 0, "slide": 0, "ui": 0, "unlabeled": 0}
    for row in label_rows:
        label = str(row.label)
        duration_ms = int(row.duration_ms or 0)
        sample_count = int(row.sample_count or 0)
        entry = _new_aoi(
            label,
            duration_ms=duration_ms,
            sample_count=sample_count,
            student_count=int(row.student_count or 0),
            slide_count=int(row.slide_count or 0),
            slide_names=slide_names,
        )
        grouping = (row.g_lesson, row.g_slide, row.g_student, row.g_visit)
        if grouping == (1, 1, 1, 1):
            by_aoi[label] = entry
            totals_by_label["labeled"] += duration_ms
            if entry["is_unlabeled"]:
                totals_by_label["unlabeled"] += duration_ms
            if entry["domain"] == "slide":
                totals_by_label["slide"] += duration_ms
            else:
                totals_by_label["ui"] += duration_ms
            continue
        if grouping == (1, 1, 1, 0):
            visit = by_visit.get(row.visit_key)
            if visit is None:
                continue
            visit["duration_ms"] += duration_ms
            visit["sample_count"] += sample_count
            if entry["is_unlabeled"]:
                visit["unlabeled_duration_ms"] += duration_ms
            if entry["domain"] == "slide":
                visit["slide_duration_ms"] += duration_ms
            else:
                visit["ui_duration_ms"] += duration_ms
            continue
        if grouping == (1, 1, 0, 1):
            bucket = by_student.get(row.student_id)
        elif grouping == (1, 0, 1, 1):
            if row.slide_id is None:
                continue
            bucket = by_slide.get(row.slide_id)
        elif grouping == (0, 1, 1, 1):
            bucket = by_lesson.get(row.lesson_id)
        else:
            continue
        if bucket is None:
            continue
        bucket["aois"][label] = entry
        bucket["duration_ms"] += duration_ms
        bucket["sample_count"] += sample_count

    tracked_ms = int(totals.tracked_ms or 0)
    labeled_ms = totals_by_label["labeled"]
    unlabeled_ms = totals_by_label["unlabeled"]
    return AoiSummaryOut(
        totals=AoiSummaryTotalsOut(
            visit_count=int(totals.visit_count or 0),
            student_count=int(totals.student_count or 0),
            content_view_count=int(totals.content_view_count or 0),
            gaze_sample_count=int(totals.gaze_count or 0),
            on_slide_gaze_count=int(totals.on_slide_count or 0),
            tracked_duration_ms=tracked_ms,
            labeled_duration_ms=labeled_ms,
            slide_duration_ms=totals_by_label["slide"],
            ui_duration_ms=totals_by_label["ui"],
            unmapped_duration_ms=max(0, tracked_ms - (labeled_ms - unlabeled_ms)),
            unlabeled_duration_ms=unlabeled_ms,
        ),
        by_aoi=_aoi_rows(by_aoi, total_ms=tracked_ms),
        by_lesson=[
            AoiSummaryLessonOut(
                lesson_id=entry["lesson_id"],
                lesson_title=entry["lesson_title"],
                lesson_kind=entry["lesson_kind"],
                duration_ms=entry["duration_ms"],
                sample_count=entry["sample_count"],
                aois=_aoi_rows(entry["aois"], total_ms=entry["duration_ms"]),
            )
            for entry in sorted(
                by_lesson.values(),
                key=lambda item: (item["lesson_title"], item["lesson_id"]),
            )
        ],
        by_slide=[
            AoiSummarySlideOut(
                slide_id=entry["slide_id"],
                slide_title=entry["slide_title"],
                lesson_id=entry["lesson_id"],
                lesson_title=entry["lesson_title"],
                page_number=entry["page_number"],
                duration_ms=entry["duration_ms"],
                sample_count=entry["sample_count"],
                aois=_aoi_rows(entry["aois"], total_ms=entry["duration_ms"]),
            )
            for entry in sorted(
                by_slide.values(),
                key=lambda item: (item["slide_title"], item["slide_id"]),
            )
        ],
        by_student=[
            AoiSummaryStudentOut(
                student_id=entry["student_id"],
                student_name=entry["student_name"],
                student_code=entry["student_code"],
                enrollment_status=entry["enrollment_status"],
                duration_ms=entry["duration_ms"],
                sample_count=entry["sample_count"],
                aois=_aoi_rows(entry["aois"], total_ms=entry["duration_ms"]),
            )
            for entry in sorted(
                by_student.values(),
                key=lambda item: (-item["duration_ms"], item["student_id"]),
            )
        ],
        by_visit=[
            AoiSummaryVisitOut(
                visit_id=entry["visit_id"],
                student_id=entry["student_id"],
                student_name=entry["student_name"],
                started_at=entry["started_at"],
                duration_ms=entry["duration_ms"],
                tracked_duration_ms=entry["tracked_duration_ms"],
                slide_duration_ms=entry["slide_duration_ms"],
                ui_duration_ms=entry["ui_duration_ms"],
                unlabeled_duration_ms=entry["unlabeled_duration_ms"],
                sample_count=entry["sample_count"],
            )
            for entry in sorted(
                by_visit.values(),
                key=lambda item: (item["started_at"], item["visit_id"]),
                reverse=True,
            )
        ],
        meta=AoiSummaryMetaOut(
            stale_view_count=int(totals.stale_view_count or 0),
            analysis_version=metrics.ANALYSIS_VERSION,
            include_dropped=body.include_dropped,
            include_short=body.include_short,
            short_view_count=int(totals.short_view_count or 0),
            min_dwell_ms=settings.content_view_min_dwell_ms,
            max_gap_ms=settings.gaze_max_gap_ms,
        ),
    )


def _empty_grid() -> list[list[int]]:
    return [[0 for _ in range(metrics.GRID_SIZE)] for _ in range(metrics.GRID_SIZE)]


def _is_complete_grid(value: object) -> bool:
    """Grid hợp lệ phải đúng 24×24; `[]`/grid dở dang coi là stale."""
    if not isinstance(value, list) or len(value) != metrics.GRID_SIZE:
        return False
    return all(
        isinstance(row, list) and len(row) == metrics.GRID_SIZE for row in value
    )


async def aoi_heatmap(
    db: AsyncSession, course: Course, body: AoiHeatmapIn
) -> AoiHeatmapOut:
    _validate_time_range(body)
    slide_row = (
        await db.execute(
            select(Slide, Lesson)
            .join(Lesson, Lesson.id == Slide.lesson_id)
            .join(CourseModule, CourseModule.id == Lesson.module_id)
            .where(Slide.id == body.slide_id, CourseModule.course_id == course.id)
        )
    ).one_or_none()
    if slide_row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Không tìm thấy slide trong khóa học"
        )
    slide, lesson = slide_row

    # Heatmap luôn là phạm vi một slide. Bỏ filter surface/lessonIds toàn cục
    # để client cũ hoặc request tay không thể vô tình làm heatmap về 0.
    scoped = body.model_copy(update={"surface": "all", "lesson_ids": []})
    views = _views_scope(course, scoped).subquery()
    rows = (
        await db.execute(
            select(
                views.c.gaze_count,
                views.c.analysis_status,
                views.c.analysis_version,
                views.c.heatmap_grid,
                exists()
                .where(GazeSample.content_view_id == views.c.view_id)
                .label("has_samples"),
            ).where(views.c.slide_id == slide.id, _included(views, scoped))
        )
    ).all()

    grid = _empty_grid()
    analyzed_view_count = 0
    stale_view_count = 0
    for row in rows:
        # View chưa phân tích có gaze_count=0 dù đã có gaze thô; cờ EXISTS
        # trong cùng query tránh thêm một lượt quét GazeSample riêng.
        if row.gaze_count <= 0 and not bool(row.has_samples):
            continue
        current = (
            row.analysis_status == "ready"
            and row.analysis_version == metrics.ANALYSIS_VERSION
            and _is_complete_grid(row.heatmap_grid)
        )
        if not current:
            stale_view_count += 1
            continue
        analyzed_view_count += 1
        source = row.heatmap_grid or []
        for y, row in enumerate(source[: metrics.GRID_SIZE]):
            if not isinstance(row, list):
                continue
            for x, value in enumerate(row[: metrics.GRID_SIZE]):
                try:
                    grid[y][x] += int(value)
                except (TypeError, ValueError):
                    continue

    max_value = max((max(row) for row in grid), default=0)
    total = sum(sum(row) for row in grid)
    pdf_url = (
        media_storage.asset_file_url(lesson.pdf_asset_id)
        if lesson.pdf_asset_id
        else None
    )
    return AoiHeatmapOut(
        slide=AoiHeatmapSlideOut(
            id=slide.id,
            title=slide.title or f"Slide {slide.position + 1}",
            page_number=slide.page_number,
            pdf_url=pdf_url,
            lesson_title=lesson.title,
        ),
        grid=grid,
        max=max_value,
        on_slide_sample_count=total,
        analyzed_view_count=analyzed_view_count,
        stale_view_count=stale_view_count,
    )
