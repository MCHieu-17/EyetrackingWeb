from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.rediscache import expire, increment
from app.db.session import get_db
from app.models.auth import User
from app.models.course import Enrollment, Slide
from app.models.gaze import ContentView, GazeSample, LearningSession, ViewLayout
from app.schemas.gaze import (
    GazeBatchAckOut,
    GazeBatchCreateIn,
    LayoutCreateIn,
    LayoutOut,
    PresentationCreateIn,
    PresentationOut,
)

router = APIRouter(tags=["gaze-ingest"])

CLOSE_GRACE = timedelta(minutes=2)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="eventTime không hợp lệ"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


async def _session_for_user(
    db: AsyncSession, session_id: str, user: User
) -> LearningSession:
    row = (
        await db.execute(
            select(LearningSession, Enrollment.student_id)
            .join(Enrollment, Enrollment.id == LearningSession.enrollment_id)
            .where(LearningSession.id == session_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên học")
    session, student_id = row
    if student_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return session


def _ensure_open(session: LearningSession) -> None:
    if session.status == "in_progress":
        return
    if session.ended_at is not None and _now() - session.ended_at <= CLOSE_GRACE:
        return
    raise HTTPException(
        status.HTTP_409_CONFLICT,
        detail={"code": "session_closed", "message": "Phiên học đã đóng"},
    )


async def _rate_limit(user: User, session_id: str) -> None:
    key = f"rl:gaze-batch:{user.id}:{session_id}"
    count = await increment(key)
    if count == 1:
        await expire(key, 60)
    if count is not None and count > 120:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited", "message": "Gửi gaze quá nhanh"},
            headers={"Retry-After": "60"},
        )


@router.post(
    "/api/learning-sessions/{session_id}/presentations",
    response_model=PresentationOut,
    status_code=201,
)
async def create_content_view(
    session_id: str,
    body: PresentationCreateIn,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    session = await _session_for_user(db, session_id, user)
    _ensure_open(session)

    if body.slide_id is not None:
        slide = await db.get(Slide, body.slide_id)
        if slide is None or slide.lesson_id != session.lesson_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Slide không thuộc phiên học",
            )

    existing = (
        await db.execute(
            select(ContentView).where(
                ContentView.session_id == session.id,
                ContentView.sequence_no == body.sequence_no,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if (
            existing.slide_id == body.slide_id
            and existing.surface == body.surface
        ):
            return PresentationOut(
                id=existing.id,
                session_id=existing.session_id,
                slide_id=existing.slide_id,
                surface=existing.surface,
                sequence_no=existing.sequence_no,
                started_at=existing.started_at.isoformat(),
            )
        # Sau reload, sequenceNo của client có thể trùng với presentation cũ
        # của slide khác. Không được trả row cũ vì gaze sẽ gắn nhầm slide.
        # Cấp sequence kế tiếp cho presentation mới.
        max_sequence = (
            await db.execute(
                select(func.max(ContentView.sequence_no)).where(
                    ContentView.session_id == session.id
                )
            )
        ).scalar_one()
        body.sequence_no = (max_sequence or 0) + 1

    previous = (
        await db.execute(
            select(ContentView)
            .where(
                ContentView.session_id == session.id,
                ContentView.ended_at.is_(None),
            )
            .order_by(ContentView.sequence_no.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if previous is not None:
        previous.ended_at = _now()

    view = ContentView(
        session_id=session.id,
        slide_id=body.slide_id,
        surface=body.surface,
        sequence_no=body.sequence_no,
        started_at=_now(),
    )
    db.add(view)
    await db.commit()
    await db.refresh(view)
    return PresentationOut(
        id=view.id,
        session_id=view.session_id,
        slide_id=view.slide_id,
        surface=view.surface,
        sequence_no=view.sequence_no,
        started_at=view.started_at.isoformat(),
    )


@router.post(
    "/api/presentations/{presentation_id}/layouts",
    response_model=LayoutOut,
    status_code=201,
)
async def create_layout(
    presentation_id: str,
    body: LayoutCreateIn,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    view = await db.get(ContentView, presentation_id)
    if view is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Không tìm thấy presentation"
        )
    session = await _session_for_user(db, view.session_id, user)
    _ensure_open(session)

    if body.coordinate_space == "original-v1":
        visible = body.visible_rect or {}
        try:
            visible_width = float(visible.get("width", 0))
            visible_height = float(visible.get("height", 0))
        except (TypeError, ValueError):
            visible_width = visible_height = 0
        if visible_width <= 0 or visible_height <= 0:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Layout original-v1 cần visibleRect.width/height > 0",
            )

    existing = (
        await db.execute(
            select(ViewLayout).where(
                ViewLayout.content_view_id == view.id,
                ViewLayout.layout_no == body.layout_generation,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return LayoutOut(
            id=existing.id,
            presentation_id=existing.content_view_id,
            layout_generation=existing.layout_no,
            coordinate_space=existing.coordinate_space,
            visible_rect=existing.visible_rect or {},
            captured_at=existing.captured_at.isoformat(),
        )

    layout = ViewLayout(
        content_view_id=view.id,
        layout_no=body.layout_generation,
        coordinate_space=body.coordinate_space,
        visible_rect=body.visible_rect or {},
        slide_rect=body.image_transform or {},
        elements=[rect.model_dump(by_alias=True) for rect in body.rects],
        captured_at=_now(),
    )
    db.add(layout)
    await db.commit()
    await db.refresh(layout)
    return LayoutOut(
        id=layout.id,
        presentation_id=layout.content_view_id,
        layout_generation=layout.layout_no,
        coordinate_space=layout.coordinate_space,
        visible_rect=layout.visible_rect or {},
        captured_at=layout.captured_at.isoformat(),
    )


@router.post(
    "/api/learning-sessions/{session_id}/gaze-batches",
    response_model=GazeBatchAckOut,
)
async def ingest_gaze_batch(
    session_id: str,
    body: GazeBatchCreateIn,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    session = await _session_for_user(db, session_id, user)
    _ensure_open(session)
    await _rate_limit(user, session.id)

    view = await db.get(ContentView, body.presentation_id)
    if view is None or view.session_id != session.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "batch_conflict", "message": "Presentation không thuộc phiên"},
        )
    if body.layout_id is not None:
        layout = await db.get(ViewLayout, body.layout_id)
        if layout is None or layout.content_view_id != view.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "batch_conflict", "message": "Layout không thuộc presentation"},
            )

    last_sequence = -1
    rows: list[dict] = []
    for sample in body.samples:
        if sample.sequence < body.sequence_start or sample.sequence > body.sequence_end:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Sample sequence ngoài batch range",
            )
        if sample.sequence <= last_sequence:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Sample sequence phải tăng dần",
            )
        last_sequence = sample.sequence
        if sample.status == "ok" and (
            sample.viewport_x is None or sample.viewport_y is None
        ):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="status=ok phải có viewportX/Y",
            )
        if sample.status != "ok" and (
            sample.viewport_x is not None or sample.viewport_y is not None
        ):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="status khác ok phải có viewportX/Y = null",
            )
        rows.append(
            {
                "content_view_id": view.id,
                "layout_id": body.layout_id,
                "client_batch_id": body.batch_id,
                "sequence": sample.sequence,
                "event_time": _parse_time(sample.event_time),
                "viewport_x": sample.viewport_x,
                "viewport_y": sample.viewport_y,
                # Client cũ không gửi original -> dùng raw calibration làm
                # original để không mất dữ liệu lịch sử.
                "original_viewport_x": (
                    sample.original_viewport_x
                    if sample.original_viewport_x is not None
                    else sample.viewport_x
                ),
                "original_viewport_y": (
                    sample.original_viewport_y
                    if sample.original_viewport_y is not None
                    else sample.viewport_y
                ),
                "status": sample.status,
                "quality_flags": sample.quality_flags,
            }
        )

    if not rows:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Batch không có sample"
        )
    stmt = (
        pg_insert(GazeSample)
        .values(rows)
        .on_conflict_do_nothing(
            index_elements=["content_view_id", "client_batch_id", "sequence"]
        )
        .returning(GazeSample.id)
    )
    stored = len((await db.execute(stmt)).scalars().all())
    view.analysis_status = "pending"
    await db.commit()
    return GazeBatchAckOut(
        batch_id=body.batch_id,
        received=len(rows),
        stored=stored,
        duplicate=len(rows) - stored,
        rejected=0,
    )
