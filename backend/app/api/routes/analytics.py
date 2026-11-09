from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.access import get_lesson_viewable
from app.api.deps import require_roles
from app.db.session import get_db
from app.models.aoi import AnalysisRun, AoiSet
from app.models.auth import User
from app.models.course import CourseVersionItem
from app.models.gaze import LearningSession
from app.services import analysis

router = APIRouter(tags=["analytics"])


async def _lesson_session_ids(db: AsyncSession, lesson_id: str) -> list[str]:
    rows = (
        await db.execute(
            select(LearningSession.id)
            .join(
                CourseVersionItem,
                CourseVersionItem.id == LearningSession.course_version_item_id,
            )
            .where(CourseVersionItem.lesson_id == lesson_id)
        )
    ).scalars().all()
    return list(rows)


@router.get("/teacher/lessons/{lesson_id}/export")
async def export_lesson_analysis(
    lesson_id: str,
    scope: str | None = Query(default=None, pattern="^(slide|ui)$"),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    await get_lesson_viewable(db, lesson_id, user)
    session_ids = await _lesson_session_ids(db, lesson_id)
    if not session_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Chưa có dữ liệu phân tích")
    stmt = (
        select(AnalysisRun)
        .join(AoiSet, AoiSet.id == AnalysisRun.aoi_set_id)
        .where(
            AnalysisRun.session_id.in_(session_ids),
            AnalysisRun.status == "completed",
        )
        .order_by(AnalysisRun.completed_at.desc())
        .limit(1)
    )
    if scope:
        stmt = stmt.where(AoiSet.scope == scope)
    run = (await db.execute(stmt)).scalar_one_or_none()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Chưa có analysis run hoàn tất")
    suffix = f"-{scope}" if scope else ""
    return StreamingResponse(
        analysis.export_lines(run.id),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f'attachment; filename="lesson-{lesson_id}{suffix}-analysis.jsonl"',
            "Cache-Control": "no-store",
        },
    )
