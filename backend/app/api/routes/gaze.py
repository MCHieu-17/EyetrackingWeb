from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.access import active_calibration_param, upsert_device
from app.api.deps import get_current_user
from app.core import rediscache
from app.core.config import settings
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models.aoi import AoiLayoutSnapshot
from app.models.auth import User
from app.models.course import Enrollment, Lesson, LessonContent, Module
from app.models.gaze import (
    GazeEvent,
    GazeRawSample,
    GazeSessionStat,
    GazeSlideStat,
    LearningSession,
)
from app.schemas.gaze import (
    GazeBatchIn,
    GazeBatchOut,
    GazeSampleIn,
    LearningSessionCreateIn,
    LearningSessionEndIn,
    LearningSessionOut,
)
from app.services import analytics, mastery

router = APIRouter(tags=["gaze"])

DEFAULT_FINGERPRINT = "web-default"


def _viewport_mismatch() -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail={
            "code": "viewport_mismatch",
            "message": (
                "Kích thước viewport hiện tại khác lúc hiệu chỉnh. "
                "Hãy hiệu chỉnh lại trước khi tiếp tục."
            ),
        },
    )


def _session_out(session: LearningSession, *, calibrated: bool, mode: str = "first") -> LearningSessionOut:
    return LearningSessionOut(
        id=session.id,
        enrollment_id=session.enrollment_id,
        lesson_id=session.lesson_id,
        device_id=session.device_id,
        calibrated=calibrated,
        status=session.status,
        tracking_consent=session.tracking_consent,
        mode=mode,
        viewport_width_px=session.viewport_width_px,
        viewport_height_px=session.viewport_height_px,
        calibration_width_px=session.calibration_width_px,
        calibration_height_px=session.calibration_height_px,
        device_pixel_ratio=session.device_pixel_ratio,
    )


@router.post("/api/learning-sessions", response_model=LearningSessionOut, status_code=201)
async def create_learning_session(
    body: LearningSessionCreateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    enrollment = await db.get(Enrollment, body.enrollment_id)
    if enrollment is None or enrollment.student_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đăng ký")
    lesson = await db.get(Lesson, body.lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài học")

    # Viewport lúc lấy mẫu phải bằng viewport lúc calibration. Chặn ngay từ
    # lúc tạo phiên để tránh ghi dữ liệu sai toạ độ (F11/zoom giữa chừng).
    if (
        body.viewport_width_px != body.calibration_width_px
        or body.viewport_height_px != body.calibration_height_px
    ):
        raise _viewport_mismatch()

    # Khóa tắt yêu cầu hiệu chỉnh => không ghi gaze, kể cả khi client gửi
    # trackingConsent=true. Cờ khóa là nguồn sự thật cuối cùng.
    tracking_consent = body.tracking_consent and enrollment.course.require_calibration

    device = await upsert_device(
        db,
        user_id=user.id,
        fingerprint=body.device_fingerprint,
        screen_width_px=body.viewport_width_px,
        screen_height_px=body.viewport_height_px,
    )
    params = await active_calibration_param(db, user.id, device.id)

    # Xác định chế độ học dựa trên các phiên trước.
    # - Chưa từng học bài này → "first" (tracking gaze).
    # - Đã có phiên trước → "continue": dùng lại phiên cũ đang mở để ghi tiếp gaze,
    #   tránh tạo phiên trùng.
    existing = (
        await db.execute(
            select(LearningSession)
            .where(
                LearningSession.enrollment_id == enrollment.id,
                LearningSession.lesson_id == lesson.id,
            )
            .order_by(LearningSession.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if existing is not None:
        # Học tiếp: tái sử dụng phiên cũ nếu nó vẫn mở; nếu đã đóng thì mở lại.
        changed = False
        if existing.status != "in_progress":
            existing.status = "in_progress"
            existing.ended_at = None
            changed = True
        # Cờ khóa có thể đã đổi từ lần học trước -> đồng bộ lại consent.
        if existing.tracking_consent != tracking_consent:
            existing.tracking_consent = tracking_consent
            changed = True
        # Người dùng có thể đã hiệu chỉnh lại ở viewport khác (vd thoát F11).
        # Cập nhật calibration viewport của phiên theo lần calibration mới nhất.
        if (
            existing.calibration_width_px != body.calibration_width_px
            or existing.calibration_height_px != body.calibration_height_px
            or existing.device_pixel_ratio != body.device_pixel_ratio
        ):
            existing.calibration_width_px = body.calibration_width_px
            existing.calibration_height_px = body.calibration_height_px
            existing.device_pixel_ratio = body.device_pixel_ratio
            changed = True
        if (
            existing.viewport_width_px != body.viewport_width_px
            or existing.viewport_height_px != body.viewport_height_px
        ):
            existing.viewport_width_px = body.viewport_width_px
            existing.viewport_height_px = body.viewport_height_px
            changed = True
        if changed:
            await db.commit()
            await db.refresh(existing)
        return _session_out(
            existing,
            calibrated=existing.calibration_param_id is not None,
            mode="continue",
        )

    session = LearningSession(
        enrollment_id=enrollment.id,
        lesson_id=lesson.id,
        device_id=device.id,
        calibration_param_id=params.id if params else None,
        tracking_consent=tracking_consent,
        viewport_width_px=body.viewport_width_px,
        viewport_height_px=body.viewport_height_px,
        calibration_width_px=body.calibration_width_px,
        calibration_height_px=body.calibration_height_px,
        device_pixel_ratio=body.device_pixel_ratio,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _session_out(
        session,
        calibrated=bool(params and params.has_model),
        mode="first",
    )


@router.patch("/api/learning-sessions/{session_id}", response_model=LearningSessionOut)
async def end_learning_session(
    session_id: str,
    body: LearningSessionEndIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(LearningSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên học")
    enrollment = await db.get(Enrollment, session.enrollment_id)
    if enrollment is None or enrollment.student_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    session.status = body.status
    session.ended_at = datetime.now(timezone.utc)
    await db.commit()
    return _session_out(
        session,
        calibrated=session.calibration_param_id is not None,
    )


def _ts_to_datetime(ts_ms: float) -> datetime:
    now = datetime.now(timezone.utc)
    try:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return now
    if dt > now or (now - dt).total_seconds() > 86400:
        return now
    return dt


def _quiz_gaze_batch(
    samples: list[GazeSampleIn], session_id: str, min_interval_ms: float
) -> tuple[list[GazeEvent], int, int, int]:
    """Chuẩn hoá một batch gaze của BÀI TẬP TRẮC NGHIỆM (không có slide).

    Toạ độ giữ nguyên theo VIEWPORT (AI service trả về), ghi `surface='quiz'` và
    `lesson_content_id=NULL`. Sample "ngoài màn hình" hoặc no_face vẫn đếm vào
    `total`/`on_screen` nhưng không tạo dòng gaze_events (giống bài giảng).

    Trả về (events, total_samples, on_screen_samples, view_ms).
    """
    ordered = sorted(samples, key=lambda s: s.ts)
    events: list[GazeEvent] = []
    kept_ts: list[float] = []
    on_screen = 0
    last_kept = float("-inf")
    for s in ordered:
        if not s.face_detected or s.x is None or s.y is None:
            continue
        if not (0.0 <= s.x <= 1.0 and 0.0 <= s.y <= 1.0):
            continue
        on_screen += 1
        if s.ts - last_kept >= min_interval_ms:
            last_kept = s.ts
            kept_ts.append(s.ts)
            events.append(
                GazeEvent(
                    learning_session_id=session_id,
                    lesson_content_id=None,
                    event_time=_ts_to_datetime(s.ts),
                    gaze_x=s.x,
                    gaze_y=s.y,
                    surface="quiz",
                )
            )
    total = len(ordered)
    if not kept_ts:
        return events, total, on_screen, 0
    span = kept_ts[-1] - kept_ts[0]
    if span <= 0:
        span = min_interval_ms
    return events, total, on_screen, int(span)


async def _upsert_session_stats(
    db: AsyncSession,
    session_id: str,
    total: int,
    on_screen: int,
    view_ms: int,
) -> None:
    """Cộng dồn tổng hợp gaze mức PHIÊN (dùng cho bài không có slide)."""
    stmt = pg_insert(GazeSessionStat).values(
        learning_session_id=session_id,
        total_samples=total,
        on_screen_samples=on_screen,
        view_ms=view_ms,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[GazeSessionStat.learning_session_id],
        set_=dict(
            total_samples=GazeSessionStat.total_samples + total,
            on_screen_samples=GazeSessionStat.on_screen_samples + on_screen,
            view_ms=GazeSessionStat.view_ms + view_ms,
            updated_at=func.now(),
        ),
    )
    await db.execute(stmt)


async def _build_raw_samples(
    db: AsyncSession,
    session: LearningSession,
    lesson: Lesson,
    body: GazeBatchIn,
) -> list[GazeRawSample]:
    """Tạo các dòng gaze_raw_samples, downsample theo GAZE_RAW_HZ.

    Raw lưu MỌI sample (kể cả no_face và off-screen), khác gaze_events chỉ lưu
    sample on-slide đã downsample 4Hz.
    """
    min_interval_ms = (
        1000.0 / settings.gaze_raw_hz if settings.gaze_raw_hz > 0 else 0.0
    )

    last_raw = (
        await db.execute(
            select(func.max(GazeRawSample.event_time)).where(
                GazeRawSample.learning_session_id == session.id
            )
        )
    ).scalar_one_or_none()
    last_ts = last_raw.timestamp() * 1000 if last_raw else float("-inf")

    content_ids = {s.lesson_content_id for s in body.samples if s.lesson_content_id}
    valid_ids: set[str] = set()
    if content_ids:
        valid_ids = set(
            (
                await db.execute(
                    select(LessonContent.id).where(
                        LessonContent.lesson_id == lesson.id,
                        LessonContent.id.in_(content_ids),
                    )
                )
            )
            .scalars()
            .all()
        )

    surface = "quiz" if lesson.kind == "quiz" else "lesson"
    out: list[GazeRawSample] = []
    for s in sorted(body.samples, key=lambda item: item.ts):
        if min_interval_ms > 0 and s.ts - last_ts < min_interval_ms:
            continue
        last_ts = s.ts
        content_id = s.lesson_content_id if s.lesson_content_id in valid_ids else None
        if surface == "quiz":
            content_id = None
        out.append(
            GazeRawSample(
                learning_session_id=session.id,
                lesson_content_id=content_id,
                layout_snapshot_id=body.layout_snapshot_id,
                event_time=_ts_to_datetime(s.ts),
                client_ts_ms=int(s.ts),
                gaze_x=s.x if s.face_detected else None,
                gaze_y=s.y if s.face_detected else None,
                slide_x=s.slide_x if s.face_detected else None,
                slide_y=s.slide_y if s.face_detected else None,
                status="ok" if s.face_detected else "no_face",
                surface=surface,
                viewport_width_px=body.viewport_width_px,
                viewport_height_px=body.viewport_height_px,
                calibration_width_px=session.calibration_width_px,
                calibration_height_px=session.calibration_height_px,
                device_pixel_ratio=session.device_pixel_ratio or 1.0,
                layout_key=body.layout_key,
                source=body.source or "real",
            )
        )
    return out


@router.post(
    "/api/lessons/{lesson_id}/gaze-samples",
    response_model=GazeBatchOut,
    dependencies=[Depends(rate_limit(60, 60, "gaze"))],
)
async def post_gaze_samples(
    lesson_id: str,
    body: GazeBatchIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài học")

    if body.source == "simulated":
        # Chặn dữ liệu mô phỏng làm nhiễu heatmap/engagement — chỉ cho real
        return GazeBatchOut(ok=True, inserted=0)

    if len(body.samples) > settings.gaze_batch_max:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Batch quá lớn")

    session: LearningSession | None = None
    if body.learning_session_id:
        session = await db.get(LearningSession, body.learning_session_id)
        if session is None or session.lesson_id != lesson_id:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên học"
            )
        enrollment = await db.get(Enrollment, session.enrollment_id)
        if enrollment is None or enrollment.student_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    else:
        stmt = (
            select(LearningSession)
            .join(Enrollment, Enrollment.id == LearningSession.enrollment_id)
            .where(
                LearningSession.lesson_id == lesson_id,
                Enrollment.student_id == user.id,
                LearningSession.status == "in_progress",
            )
            .order_by(LearningSession.started_at.desc())
        )
        session = (await db.execute(stmt)).scalars().first()
        if session is None:
            module = await db.get(Module, lesson.module_id)
            enrollment = (
                await db.execute(
                    select(Enrollment).where(
                        Enrollment.course_id == module.course_id,
                        Enrollment.student_id == user.id,
                    )
                )
            ).scalar_one_or_none()
            if enrollment is None:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN, detail="Chưa đăng ký khóa học"
                )
            device = await upsert_device(
                db,
                user_id=user.id,
                fingerprint=DEFAULT_FINGERPRINT,
                screen_width_px=body.viewport_width_px,
                screen_height_px=body.viewport_height_px,
            )
            session = LearningSession(
                enrollment_id=enrollment.id,
                lesson_id=lesson_id,
                device_id=device.id,
                tracking_consent=enrollment.course.require_calibration,
                viewport_width_px=body.viewport_width_px,
                viewport_height_px=body.viewport_height_px,
                calibration_width_px=body.viewport_width_px,
                calibration_height_px=body.viewport_height_px,
                device_pixel_ratio=1.0,
            )
            db.add(session)
            await db.flush()

    # Khóa tắt yêu cầu hiệu chỉnh => không ghi gaze (kể cả session cũ còn
    # tracking_consent=true từ trước khi GV đổi cờ).
    if not enrollment.course.require_calibration:
        return GazeBatchOut(ok=True, inserted=0)

    if not session.tracking_consent:
        return GazeBatchOut(ok=True, inserted=0)

    # Viewport hiện tại phải bằng viewport lúc calibration của phiên.
    if (
        session.calibration_width_px is None
        or session.calibration_height_px is None
        or body.viewport_width_px != session.calibration_width_px
        or body.viewport_height_px != session.calibration_height_px
    ):
        raise _viewport_mismatch()

    # Layout snapshot (nếu có) phải thuộc đúng phiên và đúng viewport.
    if body.layout_snapshot_id:
        snapshot = await db.get(AoiLayoutSnapshot, body.layout_snapshot_id)
        if snapshot is None or snapshot.learning_session_id != session.id:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Không tìm thấy layout snapshot"
            )
        if (
            snapshot.viewport_width_px != session.calibration_width_px
            or snapshot.viewport_height_px != session.calibration_height_px
        ):
            raise _viewport_mismatch()

    raw_samples = await _build_raw_samples(db, session, lesson, body)

    min_interval_ms = 1000.0 / max(settings.gaze_downsample_hz, 0.1)

    if lesson.kind == "quiz":
        # Bài tập trắc nghiệm: không có slide để map toạ độ/heatmap. Ghi gaze
        # thô theo viewport (surface='quiz') + tổng hợp mức phiên; bỏ qua
        # mastery/engagement/heatmap vì không có nội dung để gắn vào.
        events, total, on_screen, view_ms = _quiz_gaze_batch(
            body.samples, session.id, min_interval_ms
        )
        if raw_samples:
            db.add_all(raw_samples)
        if events:
            db.add_all(events)
        if total:
            await _upsert_session_stats(db, session.id, total, on_screen, view_ms)
        await db.commit()
        return GazeBatchOut(ok=True, inserted=len(events))

    content_ids = {s.lesson_content_id for s in body.samples}
    valid_ids = set(
        (
            await db.execute(
                select(LessonContent.id).where(
                    LessonContent.lesson_id == lesson_id,
                    LessonContent.id.in_(content_ids),
                )
            )
        )
        .scalars()
        .all()
    )

    by_content: dict[str, list[GazeSampleIn]] = {}
    raw_counts: dict[str, int] = {}
    on_slide_counts: dict[str, int] = {}
    for s in body.samples:
        if s.lesson_content_id not in valid_ids:
            continue
        bucket = by_content.setdefault(s.lesson_content_id, [])
        raw_counts[s.lesson_content_id] = raw_counts.get(s.lesson_content_id, 0) + 1
        if (
            s.face_detected
            and s.slide_x is not None
            and s.slide_y is not None
            and 0.0 <= s.slide_x <= 1.0
            and 0.0 <= s.slide_y <= 1.0
        ):
            on_slide_counts[s.lesson_content_id] = (
                on_slide_counts.get(s.lesson_content_id, 0) + 1
            )
        bucket.append(s)

    events: list[GazeEvent] = []
    view_ms_by_content: dict[str, int] = {}
    for content_id, bucket in by_content.items():
        bucket.sort(key=lambda s: s.ts)
        kept: list[tuple[float, float, float]] = []
        last_kept = float("-inf")
        for s in bucket:
            # Chỉ ghi gaze_events cho điểm slide hợp lệ trong [0,1]; sample
            # ngoài slide/no_face vẫn đếm vào total/on_slide để tỷ lệ phản ánh
            # đúng, nhưng không thêm chấm làm nhiễu heatmap.
            if (
                not s.face_detected
                or s.slide_x is None
                or s.slide_y is None
                or not (0.0 <= s.slide_x <= 1.0 and 0.0 <= s.slide_y <= 1.0)
            ):
                continue
            if s.ts - last_kept >= min_interval_ms:
                last_kept = s.ts
                kept.append((s.slide_x, s.slide_y, s.ts))
        if kept:
            events.extend(
                GazeEvent(
                    learning_session_id=session.id,
                    lesson_content_id=content_id,
                    event_time=_ts_to_datetime(ts),
                    gaze_x=x,
                    gaze_y=y,
                    surface="slide",
                )
                for x, y, ts in kept
            )
            span = kept[-1][2] - kept[0][2]
            if span <= 0:
                span = min_interval_ms
            view_ms_by_content[content_id] = int(span)

    if raw_samples:
        db.add_all(raw_samples)
    if events:
        db.add_all(events)

    for content_id, raw in raw_counts.items():
        stmt = pg_insert(GazeSlideStat).values(
            learning_session_id=session.id,
            lesson_content_id=content_id,
            total_samples=raw,
            on_slide_samples=on_slide_counts.get(content_id, 0),
            view_ms=view_ms_by_content.get(content_id, 0),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_gaze_slide_stats",
            set_=dict(
                total_samples=GazeSlideStat.total_samples + raw,
                on_slide_samples=GazeSlideStat.on_slide_samples
                + on_slide_counts.get(content_id, 0),
                view_ms=GazeSlideStat.view_ms + view_ms_by_content.get(content_id, 0),
            ),
        )
        await db.execute(stmt)

    await db.commit()

    # Tự cập nhật heatmap_aggregates + engagement_scores + mastery GẦN THỜI GIAN
    # THỰC để dashboard giáo viên thấy số mới ngay, không cần recompute thủ công.
    # Throttle bằng Redis lock để không chạy lại aggregates ở mỗi batch (~4Hz).
    if session and session.tracking_consent and raw_counts:
        if await rediscache.try_acquire_lock(
            f"agg:throttle:{lesson_id}", settings.aggregate_refresh_throttle_seconds
        ):
            await analytics.refresh_aggregates(
                db,
                lesson_id,
                content_ids=sorted(raw_counts.keys()),
                enrollment_id=session.enrollment_id,
            )
            await mastery.refresh_mastery(db, lesson_id, session.enrollment_id)
            await db.commit()

    # Dữ liệu gaze mới → heatmap cache của lesson đã cũ (bump generation).
    await analytics.invalidate_heatmap_cache(lesson_id)

    return GazeBatchOut(ok=True, inserted=len(events))
