from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.rediscache import expire, increment
from app.db.session import get_db
from app.models.auth import User
from app.models.course import CourseVersionItem, Enrollment, LessonVersionSlide
from app.models.gaze import (
    ContentPresentation,
    GazeBatch,
    GazeSample,
    LearningSession,
)
from app.schemas.gaze import (
    GazeBatchAckOut,
    GazeBatchCreateIn,
    LayoutCreateIn,
    LayoutOut,
    PresentationCreateIn,
    PresentationOut,
)
from app.models.aoi import AoiLayoutRect, AoiLayoutSnapshot

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
    session = await db.get(LearningSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên học")
    enrollment = await db.get(Enrollment, session.enrollment_id)
    if enrollment is None or enrollment.student_id != user.id:
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
async def create_presentation(
    session_id: str,
    body: PresentationCreateIn,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    session = await _session_for_user(db, session_id, user)
    _ensure_open(session)

    if body.lesson_version_slide_id is not None:
        item = await db.get(CourseVersionItem, session.course_version_item_id)
        slide = await db.get(LessonVersionSlide, body.lesson_version_slide_id)
        if item is None or slide is None or slide.lesson_version_id != item.lesson_version_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Slide không thuộc phiên học",
            )

    existing = (
        await db.execute(
            select(ContentPresentation).where(
                ContentPresentation.session_id == session.id,
                ContentPresentation.sequence_no == body.sequence_no,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return PresentationOut(
            id=existing.id,
            session_id=existing.session_id,
            lesson_version_slide_id=existing.lesson_version_slide_id,
            surface=existing.surface,
            sequence_no=existing.sequence_no,
            started_at=existing.started_at.isoformat(),
        )

    presentation = ContentPresentation(
        session_id=session.id,
        lesson_version_slide_id=body.lesson_version_slide_id,
        surface=body.surface,
        sequence_no=body.sequence_no,
        started_at=_now(),
    )
    db.add(presentation)
    await db.commit()
    await db.refresh(presentation)
    return PresentationOut(
        id=presentation.id,
        session_id=presentation.session_id,
        lesson_version_slide_id=presentation.lesson_version_slide_id,
        surface=presentation.surface,
        sequence_no=presentation.sequence_no,
        started_at=presentation.started_at.isoformat(),
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
    presentation = await db.get(ContentPresentation, presentation_id)
    if presentation is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Không tìm thấy presentation"
        )
    session = await _session_for_user(db, presentation.session_id, user)
    _ensure_open(session)

    existing = (
        await db.execute(
            select(AoiLayoutSnapshot).where(
                AoiLayoutSnapshot.presentation_id == presentation.id,
                AoiLayoutSnapshot.layout_generation == body.layout_generation,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return LayoutOut(
            id=existing.id,
            presentation_id=existing.presentation_id,
            layout_generation=existing.layout_generation,
            captured_at=existing.captured_at.isoformat(),
        )

    snapshot = AoiLayoutSnapshot(
        presentation_id=presentation.id,
        captured_at=_now(),
        sequence_no=body.sequence_no,
        layout_generation=body.layout_generation,
        image_transform=body.image_transform,
    )
    db.add(snapshot)
    await db.flush()
    for rect in body.rects:
        db.add(
            AoiLayoutRect(
                snapshot_id=snapshot.id,
                semantic_code=rect.semantic_code,
                element_key=rect.element_key,
                x_min=rect.x_min,
                y_min=rect.y_min,
                x_max=rect.x_max,
                y_max=rect.y_max,
            )
        )
    await db.commit()
    await db.refresh(snapshot)
    return LayoutOut(
        id=snapshot.id,
        presentation_id=snapshot.presentation_id,
        layout_generation=snapshot.layout_generation,
        captured_at=snapshot.captured_at.isoformat(),
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

    presentation = await db.get(ContentPresentation, body.presentation_id)
    if presentation is None or presentation.session_id != session.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"code": "batch_conflict", "message": "Presentation không thuộc phiên"},
        )
    if body.layout_snapshot_id is not None:
        snapshot = await db.get(AoiLayoutSnapshot, body.layout_snapshot_id)
        if snapshot is None or snapshot.presentation_id != presentation.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "batch_conflict", "message": "Layout không thuộc presentation"},
            )

    existing = (
        await db.execute(
            select(GazeBatch).where(
                GazeBatch.session_id == session.id,
                GazeBatch.batch_id == body.batch_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.payload_hash != body.payload_hash:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={
                    "code": "batch_conflict",
                    "message": "Batch ID đã dùng với payload khác",
                },
            )
        return GazeBatchAckOut(
            batch_id=body.batch_id,
            received=existing.received_count,
            stored=0,
            duplicate=existing.received_count,
            rejected=0,
        )

    max_no = (
        await db.execute(
            select(func.coalesce(func.max(GazeBatch.batch_no), -1)).where(
                GazeBatch.session_id == session.id
            )
        )
    ).scalar_one()
    if body.batch_no != int(max_no) + 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "batch_out_of_order",
                "message": f"Batch number phải là {int(max_no) + 1}",
            },
        )

    if body.sequence_end < body.sequence_start:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="sequenceEnd phải >= sequenceStart",
        )
    last_sequence = -1
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

    batch = GazeBatch(
        session_id=session.id,
        presentation_id=presentation.id,
        layout_snapshot_id=body.layout_snapshot_id,
        batch_id=body.batch_id,
        batch_no=body.batch_no,
        sequence_start=body.sequence_start,
        sequence_end=body.sequence_end,
        payload_hash=body.payload_hash,
        received_count=len(body.samples),
        stored_count=len(body.samples),
        duplicate_count=0,
        rejected_count=0,
    )
    db.add(batch)
    await db.flush()
    for sample in body.samples:
        db.add(
            GazeSample(
                session_id=session.id,
                batch_id=batch.id,
                sequence=sample.sequence,
                capture_monotonic_ns=sample.capture_monotonic_ns,
                event_time=_parse_time(sample.event_time),
                viewport_x=sample.viewport_x,
                viewport_y=sample.viewport_y,
                status=sample.status,
                quality_flags=sample.quality_flags,
            )
        )
    await db.commit()
    return GazeBatchAckOut(
        batch_id=body.batch_id,
        received=len(body.samples),
        stored=len(body.samples),
        duplicate=0,
        rejected=0,
    )
