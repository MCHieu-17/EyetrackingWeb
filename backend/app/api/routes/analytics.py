from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.access import get_lesson_viewable
from app.api.deps import can_manage_course, require_roles
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models.aoi import AnalysisRun
from app.models.auth import User
from app.models.course import Course, CourseVersionItem
from app.models.gaze import LearningSession
from app.schemas.analytics import SlideStatOut
from app.services import analysis, metrics

router = APIRouter(tags=["analytics"])


@router.get("/teacher/lessons/{lesson_id}/heatmap", response_model=list[SlideStatOut])
async def get_lesson_heatmap(
    lesson_id: str,
    student_id: str | None = Query(default=None),
    algorithm_version: str = Query(
        default=metrics.DEFAULT_ALGORITHM_VERSION, alias="algorithmVersion"
    ),
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    await get_lesson_viewable(db, lesson_id, user)
    return await metrics.lesson_heatmap(
        db, lesson_id, student_id, algorithm_version
    )


@router.post(
    "/teacher/courses/{course_id}/recompute",
    dependencies=[Depends(rate_limit(5, 60, "recompute"))],
)
async def recompute_course_analytics(
    course_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course = await db.get(Course, course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    if not await can_manage_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    runs, completed, failed = await analysis.rebuild_course(
        db,
        user,
        course_id=course_id,
        from_time=None,
        to_time=None,
        algorithm_version=analysis.ALGORITHM_VERSION,
    )
    return {
        "ok": True,
        "aggregates": completed,
        "runs": runs,
        "failed": failed,
    }


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


@router.get("/teacher/lessons/{lesson_id}/analysis-runs")
async def list_lesson_analysis_runs(
    lesson_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    await get_lesson_viewable(db, lesson_id, user)
    session_ids = await _lesson_session_ids(db, lesson_id)
    if not session_ids:
        return []
    rows = (
        await db.execute(
            select(AnalysisRun)
            .where(AnalysisRun.session_id.in_(session_ids))
            .order_by(AnalysisRun.created_at.desc())
        )
    ).scalars().all()
    return [
        {
            "id": row.id,
            "sessionId": row.session_id,
            "aoiSetId": row.aoi_set_id,
            "algorithmVersion": row.algorithm_version,
            "status": row.status,
            "createdAt": row.created_at,
            "completedAt": row.completed_at,
        }
        for row in rows
    ]


@router.get("/teacher/lessons/{lesson_id}/export")
async def export_lesson_analysis(
    lesson_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    await get_lesson_viewable(db, lesson_id, user)
    session_ids = await _lesson_session_ids(db, lesson_id)
    if not session_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Chưa có dữ liệu phân tích")
    run = (
        await db.execute(
            select(AnalysisRun)
            .where(
                AnalysisRun.session_id.in_(session_ids),
                AnalysisRun.status == "completed",
            )
            .order_by(AnalysisRun.completed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Chưa có analysis run hoàn tất")
    return StreamingResponse(
        analysis.export_lines(run.id),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f'attachment; filename="lesson-{lesson_id}-analysis.jsonl"',
            "Cache-Control": "no-store",
        },
    )
