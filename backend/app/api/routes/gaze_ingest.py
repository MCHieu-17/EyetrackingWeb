from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
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
from app.services.gaze_views import close_open_views

router = APIRouter(tags=["gaze-ingest"])

CLOSE_GRACE = timedelta(minutes=2)
# enteredAt do client gửi có thể lệch đồng hồ; kẹp trong khoảng 5 phút trước
# hiện tại để không tạo lượt xem quá khứ xa.
ENTERED_AT_WINDOW = timedelta(minutes=5)
# Dung sai thứ tự khi so enteredAt với lượt xem gần nhất.
STALE_TOLERANCE = timedelta(milliseconds=250)


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


def _presentation_out(view: ContentView) -> PresentationOut:
    return PresentationOut(
        id=view.id,
        session_id=view.session_id,
        slide_id=view.slide_id,
        surface=view.surface,
        sequence_no=view.sequence_no,
        started_at=view.started_at.isoformat(),
    )


def _same_context(view: ContentView, session_id: str, body: PresentationCreateIn) -> bool:
    return (
        view.session_id == session_id
        and view.slide_id == body.slide_id
        and view.surface == body.surface
    )


def _presentation_conflict() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail={
            "code": "presentation_conflict",
            "message": "clientPresentationId đã dùng cho lượt xem khác",
        },
    )


def _stale_presentation() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail={
            "code": "stale_presentation",
            "message": "enteredAt cũ hơn lượt xem gần nhất của phiên",
        },
    )


def _clamp_entered_at(value: datetime | None, now: datetime) -> datetime:
    """Kẹp enteredAt của client về [now - 5 phút, now]; thiếu thì dùng now."""
    if value is None:
        return now
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    earliest = now - ENTERED_AT_WINDOW
    if value < earliest:
        return earliest
    if value > now:
        return now
    return value


async def _lock_session_row(db: AsyncSession, session_id: str) -> None:
    """Khoá row learning_sessions để cấp sequence tuần tự giữa request song song."""
    await db.execute(
        select(LearningSession.id)
        .where(LearningSession.id == session_id)
        .with_for_update()
    )


async def _next_sequence(db: AsyncSession, session_id: str) -> int:
    current = (
        await db.execute(
            select(func.max(ContentView.sequence_no)).where(
                ContentView.session_id == session_id
            )
        )
    ).scalar_one()
    return 0 if current is None else current + 1


async def _latest_view(db: AsyncSession, session_id: str) -> ContentView | None:
    return (
        await db.execute(
            select(ContentView)
            .where(ContentView.session_id == session_id)
            .order_by(ContentView.sequence_no.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _existing_client_view(
    db: AsyncSession,
    client_id: UUID,
    session_id: str,
    body: PresentationCreateIn,
) -> ContentView | None:
    existing = await db.get(ContentView, str(client_id))
    if existing is None:
        return None
    if _same_context(existing, session_id, body):
        return existing
    raise _presentation_conflict()


async def _content_view_by_sequence(
    db: AsyncSession, session_id: str, sequence_no: int
) -> ContentView | None:
    return (
        await db.execute(
            select(ContentView).where(
                ContentView.session_id == session_id,
                ContentView.sequence_no == sequence_no,
            )
        )
    ).scalar_one_or_none()


async def _view_from_client_id(
    db: AsyncSession,
    session_id: str,
    body: PresentationCreateIn,
    entered_at: datetime,
) -> ContentView:
    latest = await _latest_view(db, session_id)
    if latest is not None and entered_at < latest.started_at - STALE_TOLERANCE:
        # Request đến trễ sau một lượt xem mới hơn: bỏ để tránh row lệch thứ tự.
        raise _stale_presentation()

    await close_open_views(db, [session_id], entered_at)
    view = ContentView(
        id=str(body.client_presentation_id),
        session_id=session_id,
        slide_id=body.slide_id,
        surface=body.surface,
        sequence_no=await _next_sequence(db, session_id),
        started_at=entered_at,
    )
    db.add(view)
    return view


async def _resolve_legacy_view(
    db: AsyncSession,
    session_id: str,
    body: PresentationCreateIn,
    now: datetime,
) -> tuple[ContentView, bool]:
    """Nhánh client cũ (không có clientPresentationId).

    Trả ``(view, created)``; ``created=False`` nghĩa là row đã tồn tại và có
    cùng slide/surface nên caller trả lại luôn (idempotent theo sequenceNo).
    """
    sequence_no = body.sequence_no
    if sequence_no is not None:
        existing = await _content_view_by_sequence(db, session_id, sequence_no)
        if existing is not None:
            if _same_context(existing, session_id, body):
                return existing, False
            # Sau reload, sequenceNo của client có thể trùng với presentation cũ
            # của slide khác. Không được trả row cũ vì gaze sẽ gắn nhầm slide.
            sequence_no = await _next_sequence(db, session_id)
    if sequence_no is None:
        sequence_no = await _next_sequence(db, session_id)

    await close_open_views(db, [session_id], now)
    view = ContentView(
        session_id=session_id,
        slide_id=body.slide_id,
        surface=body.surface,
        sequence_no=sequence_no,
        started_at=now,
    )
    db.add(view)
    return view, True


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
    session_pk = session.id

    if body.slide_id is not None:
        slide = await db.get(Slide, body.slide_id)
        if slide is None or slide.lesson_id != session.lesson_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Slide không thuộc phiên học",
            )

    await _lock_session_row(db, session_pk)

    now = _now()
    entered_at = _clamp_entered_at(body.entered_at, now)

    if body.client_presentation_id is not None:
        existing = await _existing_client_view(
            db, body.client_presentation_id, session_pk, body
        )
        if existing is not None:
            return _presentation_out(existing)
        view = await _view_from_client_id(db, session_pk, body, entered_at)
    else:
        view, created = await _resolve_legacy_view(db, session_pk, body, now)
        if not created:
            return _presentation_out(view)
    assigned_sequence = view.sequence_no

    try:
        await db.commit()
    except IntegrityError:
        # Đua PK (clientPresentationId) hoặc unique (session, sequence): đọc lại
        # row đã thắng và trả nếu cùng ngữ cảnh.
        await db.rollback()
        if body.client_presentation_id is not None:
            existing = await db.get(ContentView, str(body.client_presentation_id))
            if existing is not None and _same_context(existing, session_pk, body):
                return _presentation_out(existing)
            raise _presentation_conflict() from None
        existing = await _content_view_by_sequence(db, session_pk, assigned_sequence)
        if existing is not None and _same_context(existing, session_pk, body):
            return _presentation_out(existing)
        raise _presentation_conflict() from None

    await db.refresh(view)
    return _presentation_out(view)


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

    # Tab frontend cũ vẫn gửi layout ở hệ toạ độ calibration. Từ chối thay vì
    # lưu sai hệ toạ độ; người học chỉ cần tải lại trang để nhận bundle mới.
    if body.coordinate_space == "original-v1":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Frontend cũ đang gửi layout original-v1; hãy tải lại trang",
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
            captured_at=existing.captured_at.isoformat(),
        )

    layout = ViewLayout(
        content_view_id=view.id,
        layout_no=body.layout_generation,
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
        batch_id=str(body.batch_id),
        received=len(rows),
        stored=stored,
        duplicate=len(rows) - stored,
        rejected=0,
    )
