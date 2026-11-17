"""Tổng hợp thời lượng nhìn theo AOI cho dashboard giáo viên.

Nguồn số liệu là `content_views.aoi_stats` do worker metrics tính. Nhờ vậy
dashboard chỉ đọc một hàng cho mỗi lượt xem, không quét toàn bộ gaze thô.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import exists, func, select
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


def _add_aoi(
    bucket: dict[str, dict],
    label: str,
    *,
    duration_ms: int,
    sample_count: int,
    student_id: str,
    slide_id: str | None,
    slide_names: dict[str, str],
) -> None:
    entry = bucket.setdefault(
        label,
        {
            "label": label,
            "name": _display_name(label, slide_names),
            "domain": _domain(label),
            "duration_ms": 0,
            "sample_count": 0,
            "students": set(),
            "slides": set(),
            "is_unlabeled": _is_unlabeled(label),
        },
    )
    entry["duration_ms"] += duration_ms
    entry["sample_count"] += sample_count
    entry["students"].add(student_id)
    if slide_id:
        entry["slides"].add(slide_id)


def _aoi_rows(bucket: dict[str, dict], *, total_ms: int = 0) -> list[AoiSummaryAoiOut]:
    rows = [
        AoiSummaryAoiOut(
            label=entry["label"],
            name=entry["name"],
            domain=entry["domain"],
            duration_ms=entry["duration_ms"],
            sample_count=entry["sample_count"],
            share=round(entry["duration_ms"] / total_ms, 6) if total_ms else 0.0,
            student_count=len(entry["students"]),
            slide_count=len(entry["slides"]),
            mixed_slides=(
                entry["label"].startswith(metrics.SLIDE_LABEL_PREFIX)
                and len(entry["slides"]) > 1
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


def _views_base(course: Course, body: AoiSummaryIn):
    stmt = (
        select(
            ContentView,
            LearningSession,
            Lesson,
            Slide,
            Enrollment,
            User,
            StudentProfile,
            CourseVisit,
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


def _views_stmt(
    course: Course,
    body: AoiSummaryIn,
    *,
    ignore_short_filter: bool = False,
    include_sample_flag: bool = False,
):
    stmt = _views_base(course, body)
    if include_sample_flag:
        stmt = stmt.add_columns(
            exists()
            .where(GazeSample.content_view_id == ContentView.id)
            .label("has_samples")
        )
    if not ignore_short_filter and not body.include_short:
        stmt = stmt.where(
            view_dwell_ms_expr() >= settings.content_view_min_dwell_ms
        )
    return stmt


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
            select(Aoi).where(Aoi.slide_id.in_(slide_ids))
        )
    ).scalars().all()
    names: dict[str, str] = {}
    for row in rows:
        if row.is_container or row.code == metrics.NO_LABEL_CODE:
            continue
        text = metrics._slide_label_text(row.label, row.code)
        names[f"{metrics.SLIDE_LABEL_PREFIX}{text}"] = row.name
    return names


async def aoi_summary(
    db: AsyncSession, course: Course, body: AoiSummaryIn
) -> AoiSummaryOut:
    _validate_time_range(body)
    # Một query duy nhất: giữ mọi view để đếm lượt ngắn, rồi lọc trong Python.
    all_rows = (await db.execute(_views_stmt(course, body, ignore_short_filter=True))).all()
    min_dwell_ms = settings.content_view_min_dwell_ms
    short_view_count = sum(
        1 for row in all_rows if int(row[-1] or 0) < min_dwell_ms
    )
    rows = (
        all_rows
        if body.include_short
        else [row for row in all_rows if int(row[-1] or 0) >= min_dwell_ms]
    )

    slide_ids = sorted({row[3].id for row in rows if row[3] is not None})
    slide_names = await _slide_names(db, slide_ids)

    by_aoi: dict[str, dict] = {}
    by_lesson: dict[str, dict] = {}
    by_slide: dict[str, dict] = {}
    by_student: dict[str, dict] = {}
    by_visit: dict[str, dict] = {}

    totals = {
        "tracked": 0,
        "labeled": 0,
        "slide": 0,
        "ui": 0,
        "unmapped": 0,
        "unlabeled": 0,
        "gaze": 0,
        "on_slide": 0,
    }
    visit_ids: set[str] = set()
    student_ids: set[str] = set()
    stale_views = 0

    for view, session, lesson, slide, enrollment, student, profile, visit, _dwell in rows:
        visit_key = (
            visit.id
            if visit is not None
            else f"session:{session.id}"
        )
        visit_ids.add(visit_key)
        student_ids.add(student.id)

        lesson_entry = by_lesson.setdefault(
            lesson.id,
            {
                "lesson_id": lesson.id,
                "lesson_title": lesson.title,
                "lesson_kind": lesson.kind,
                "duration_ms": 0,
                "sample_count": 0,
                "aois": {},
            },
        )
        student_entry = by_student.setdefault(
            student.id,
            {
                "student_id": student.id,
                "student_name": student.full_name or student.email,
                "student_code": profile.student_code if profile else "",
                "enrollment_status": enrollment.status,
                "duration_ms": 0,
                "sample_count": 0,
                "aois": {},
            },
        )
        visit_entry = by_visit.setdefault(
            visit_key,
            {
                "visit_id": visit_key,
                "student_id": student.id,
                "student_name": student.full_name or student.email,
                "started_at": (
                    visit.started_at if visit is not None else session.started_at
                ).isoformat(),
                "duration_ms": 0,
                "tracked_duration_ms": 0,
                "slide_duration_ms": 0,
                "ui_duration_ms": 0,
                "unlabeled_duration_ms": 0,
                "sample_count": 0,
            },
        )
        slide_entry = None
        if slide is not None:
            slide_entry = by_slide.setdefault(
                slide.id,
                {
                    "slide_id": slide.id,
                    "slide_title": slide.title or f"Slide {slide.position + 1}",
                    "lesson_id": lesson.id,
                    "lesson_title": lesson.title,
                    "page_number": slide.page_number,
                    "duration_ms": 0,
                    "sample_count": 0,
                    "aois": {},
                },
            )

        visit_entry["tracked_duration_ms"] += view.tracked_duration_ms
        totals["tracked"] += view.tracked_duration_ms
        totals["gaze"] += view.gaze_count
        totals["on_slide"] += view.on_slide_gaze_count

        if (
            view.analysis_status != "ready"
            or view.analysis_version != metrics.ANALYSIS_VERSION
            or (not (view.aoi_stats or {}) and view.gaze_count > 0)
        ):
            stale_views += 1

        for label, value in (view.aoi_stats or {}).items():
            if not isinstance(value, dict):
                continue
            label = str(label)
            duration_ms = int(value.get("ms", 0) or 0)
            sample_count = int(value.get("samples", 0) or 0)
            if duration_ms == 0 and sample_count == 0:
                continue

            _add_aoi(
                by_aoi,
                label,
                duration_ms=duration_ms,
                sample_count=sample_count,
                student_id=student.id,
                slide_id=slide.id if slide else None,
                slide_names=slide_names,
            )
            _add_aoi(
                lesson_entry["aois"],
                label,
                duration_ms=duration_ms,
                sample_count=sample_count,
                student_id=student.id,
                slide_id=slide.id if slide else None,
                slide_names=slide_names,
            )
            _add_aoi(
                student_entry["aois"],
                label,
                duration_ms=duration_ms,
                sample_count=sample_count,
                student_id=student.id,
                slide_id=slide.id if slide else None,
                slide_names=slide_names,
            )
            if slide_entry is not None:
                _add_aoi(
                    slide_entry["aois"],
                    label,
                    duration_ms=duration_ms,
                    sample_count=sample_count,
                    student_id=student.id,
                    slide_id=slide.id,
                    slide_names=slide_names,
                )

            lesson_entry["duration_ms"] += duration_ms
            lesson_entry["sample_count"] += sample_count
            student_entry["duration_ms"] += duration_ms
            student_entry["sample_count"] += sample_count
            if slide_entry is not None:
                slide_entry["duration_ms"] += duration_ms
                slide_entry["sample_count"] += sample_count
            visit_entry["duration_ms"] += duration_ms
            visit_entry["sample_count"] += sample_count

            totals["labeled"] += duration_ms
            if _is_unlabeled(label):
                totals["unlabeled"] += duration_ms
            if label.startswith(metrics.SLIDE_LABEL_PREFIX):
                totals["slide"] += duration_ms
                visit_entry["slide_duration_ms"] += duration_ms
            else:
                totals["ui"] += duration_ms
                visit_entry["ui_duration_ms"] += duration_ms
            if _is_unlabeled(label):
                visit_entry["unlabeled_duration_ms"] += duration_ms

    # `unmapped` được tính sau khi biết tổng tracked: tracked - mapped.
    totals["unmapped"] = max(0, totals["tracked"] - (totals["labeled"] - totals["unlabeled"]))

    return AoiSummaryOut(
        totals=AoiSummaryTotalsOut(
            visit_count=len(visit_ids),
            student_count=len(student_ids),
            content_view_count=len(rows),
            gaze_sample_count=totals["gaze"],
            on_slide_gaze_count=totals["on_slide"],
            tracked_duration_ms=totals["tracked"],
            labeled_duration_ms=totals["labeled"],
            slide_duration_ms=totals["slide"],
            ui_duration_ms=totals["ui"],
            unmapped_duration_ms=totals["unmapped"],
            unlabeled_duration_ms=totals["unlabeled"],
        ),
        by_aoi=_aoi_rows(by_aoi, total_ms=totals["tracked"]),
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
                by_lesson.values(), key=lambda item: item["lesson_title"]
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
                by_slide.values(), key=lambda item: item["slide_title"]
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
                by_student.values(), key=lambda item: -item["duration_ms"]
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
                by_visit.values(), key=lambda item: item["started_at"], reverse=True
            )
        ],
        meta=AoiSummaryMetaOut(
            stale_view_count=stale_views,
            analysis_version=metrics.ANALYSIS_VERSION,
            include_dropped=body.include_dropped,
            include_short=body.include_short,
            short_view_count=short_view_count,
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
    rows = (
        await db.execute(
            _views_stmt(
                course, scoped, include_sample_flag=True
            ).where(ContentView.slide_id == slide.id)
        )
    ).all()

    grid = _empty_grid()
    analyzed_view_count = 0
    stale_view_count = 0
    for row in rows:
        view = row[0]
        # View chưa phân tích có gaze_count=0 dù đã có gaze thô; cờ EXISTS
        # trong cùng query tránh thêm một lượt quét GazeSample riêng.
        if view.gaze_count <= 0 and not bool(row[-1]):
            continue
        current = (
            view.analysis_status == "ready"
            and view.analysis_version == metrics.ANALYSIS_VERSION
            and _is_complete_grid(view.heatmap_grid)
        )
        if not current:
            stale_view_count += 1
            continue
        analyzed_view_count += 1
        source = view.heatmap_grid or []
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
