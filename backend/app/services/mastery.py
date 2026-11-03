"""Tính điểm hoàn thành bài học dựa trên tỷ lệ gaze trên trang.

Ý tưởng chốt với người dùng:
  - Slide `is_key` (GV đánh dấu) chiếm 85% điểm, slide thường 15%.
  - Một trang "hoàn thành" khi tỷ lệ gaze trên trang >= mastery_coverage_threshold.
  - Điểm chỉ hiển thị cho giáo viên; SV vẫn hoàn thành bài theo cơ chế cũ
    (xem hết trang), không đổi.

Ghi chú: AOI (vùng nội dung) đang tạm gỡ khỏi backend/frontend. Khi làm lại AOI,
có thể bổ sung lại logic coverage theo `aoi_regions`/`aoi_dwell_stats`; schema DB
vẫn được giữ nguyên.
"""

from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.analytics import LessonMasteryScore, SlideCoverageStat
from app.models.course import Enrollment, Lesson, LessonContent, Module
from app.models.gaze import GazeSlideStat, LearningSession


async def _session_ids(
    db: AsyncSession, lesson_id: str, enrollment_id: str
) -> list[str]:
    return list(
        (
            await db.execute(
                select(LearningSession.id).where(
                    LearningSession.lesson_id == lesson_id,
                    LearningSession.enrollment_id == enrollment_id,
                )
            )
        )
        .scalars()
        .all()
    )


async def refresh_mastery(
    db: AsyncSession, lesson_id: str, enrollment_id: str
) -> float:
    contents = (
        (
            await db.execute(
                select(LessonContent)
                .where(LessonContent.lesson_id == lesson_id)
                .order_by(LessonContent.order_index)
            )
        )
        .scalars()
        .all()
    )
    if not contents:
        return 0.0

    content_ids = [c.id for c in contents]
    sessions = await _session_ids(db, lesson_id, enrollment_id)

    on_slide_map: dict[str, float] = {}
    if sessions:
        slide_rows = (
            await db.execute(
                select(
                    GazeSlideStat.lesson_content_id,
                    func.sum(GazeSlideStat.on_slide_samples),
                    func.sum(GazeSlideStat.total_samples),
                )
                .where(GazeSlideStat.learning_session_id.in_(sessions))
                .group_by(GazeSlideStat.lesson_content_id)
            )
        ).all()
        for cid, on_slide, total in slide_rows:
            on_slide_map[cid] = (on_slide / total) if total else 0.0

    threshold = settings.mastery_coverage_threshold

    coverages: dict[str, float] = {}
    stat_rows: list[tuple[str, float, bool]] = []
    for c in contents:
        coverage = on_slide_map.get(c.id, 0.0)
        coverages[c.id] = coverage
        stat_rows.append((c.id, coverage, coverage >= threshold))

    await db.execute(
        delete(SlideCoverageStat).where(
            SlideCoverageStat.enrollment_id == enrollment_id,
            SlideCoverageStat.lesson_content_id.in_(content_ids),
        )
    )
    now = datetime.now(timezone.utc)
    for cid, coverage, complete in stat_rows:
        db.add(
            SlideCoverageStat(
                enrollment_id=enrollment_id,
                lesson_content_id=cid,
                coverage=round(coverage, 4),
                dwell_ms=0,
                is_complete=complete,
                computed_at=now,
            )
        )

    key_coverages = [coverages[c.id] for c in contents if c.is_key]
    normal_coverages = [coverages[c.id] for c in contents if not c.is_key]
    key_part = sum(key_coverages) / len(key_coverages) if key_coverages else None
    normal_part = (
        sum(normal_coverages) / len(normal_coverages) if normal_coverages else None
    )

    kw = settings.mastery_key_weight
    if key_part is not None and normal_part is not None:
        score = 100 * (kw * key_part + (1 - kw) * normal_part)
    elif key_part is not None:
        score = 100 * key_part
    else:
        score = 100 * normal_part if normal_part is not None else 0.0

    key_done = sum(1 for c in contents if c.is_key and coverages[c.id] >= threshold)
    key_total = sum(1 for c in contents if c.is_key)
    slides_done = sum(1 for c in contents if coverages[c.id] >= threshold)

    await db.execute(
        delete(LessonMasteryScore).where(
            LessonMasteryScore.enrollment_id == enrollment_id,
            LessonMasteryScore.lesson_id == lesson_id,
        )
    )
    db.add(
        LessonMasteryScore(
            enrollment_id=enrollment_id,
            lesson_id=lesson_id,
            score=round(score, 2),
            key_score=round(100 * key_part, 2) if key_part is not None else 0.0,
            normal_score=round(100 * normal_part, 2) if normal_part is not None else 0.0,
            key_done=key_done,
            key_total=key_total,
            slides_done=slides_done,
            slides_total=len(contents),
            computed_at=now,
        )
    )
    return round(score, 2)


async def recompute_lesson_mastery(db: AsyncSession, lesson_id: str) -> int:
    """Tính lại mastery cho mọi học viên của khóa học chứa bài (dùng cho recompute)."""
    course_id = (
        await db.execute(
            select(Module.course_id)
            .join(Lesson, Lesson.module_id == Module.id)
            .where(Lesson.id == lesson_id)
        )
    ).scalar_one_or_none()
    if course_id is None:
        return 0
    enrollment_ids = list(
        (
            await db.execute(
                select(Enrollment.id).where(
                    Enrollment.course_id == course_id, Enrollment.status != "dropped"
                )
            )
        )
        .scalars()
        .all()
    )
    for eid in enrollment_ids:
        await refresh_mastery(db, lesson_id, eid)
    return len(enrollment_ids)
