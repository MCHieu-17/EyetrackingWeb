from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aoi import AoiDefinition, AoiLayoutRect, GazeAoiHit
from app.models.course import Lesson, Module
from app.models.gaze import GazeRawSample, LearningSession


async def rebuild_aoi_hits(
    db: AsyncSession,
    *,
    session_id: str | None = None,
    lesson_id: str | None = None,
    course_id: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> int:
    """Tính lại gaze_aoi_hits từ raw samples + layout rects.

    Có thể rebuild theo session/lesson/course/khoảng thời gian. Bảng hits là
    derived nên xoá sạch phạm vi rồi insert lại là an toàn.
    """
    scope = select(LearningSession.id)
    if session_id:
        scope = scope.where(LearningSession.id == session_id)
    if lesson_id:
        scope = scope.where(LearningSession.lesson_id == lesson_id)
    if course_id:
        scope = (
            scope.join(Lesson, Lesson.id == LearningSession.lesson_id)
            .join(Module, Module.id == Lesson.module_id)
            .where(Module.course_id == course_id)
        )

    await db.execute(
        delete(GazeAoiHit).where(GazeAoiHit.learning_session_id.in_(scope))
    )

    conditions = [
        GazeRawSample.status == "ok",
        GazeRawSample.learning_session_id.in_(scope),
        GazeRawSample.layout_snapshot_id.is_not(None),
        AoiDefinition.is_active.is_(True),
        AoiDefinition.scope == "viewport",
        GazeRawSample.gaze_x >= AoiLayoutRect.x_min,
        GazeRawSample.gaze_x <= AoiLayoutRect.x_max,
        GazeRawSample.gaze_y >= AoiLayoutRect.y_min,
        GazeRawSample.gaze_y <= AoiLayoutRect.y_max,
    ]
    if from_time is not None:
        conditions.append(GazeRawSample.event_time >= from_time)
    if to_time is not None:
        conditions.append(GazeRawSample.event_time <= to_time)

    select_stmt = (
        select(
            GazeRawSample.learning_session_id,
            GazeRawSample.id,
            GazeRawSample.event_time,
            AoiDefinition.id,
        )
        .join(
            AoiLayoutRect,
            AoiLayoutRect.snapshot_id == GazeRawSample.layout_snapshot_id,
        )
        .join(AoiDefinition, AoiDefinition.code == AoiLayoutRect.aoi_code)
        .where(*conditions)
    )

    stmt = (
        pg_insert(GazeAoiHit)
        .from_select(
            ["learning_session_id", "gaze_sample_id", "event_time", "aoi_id"],
            select_stmt,
        )
        .on_conflict_do_nothing(index_elements=["gaze_sample_id", "aoi_id"])
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0
