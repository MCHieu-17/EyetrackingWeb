from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.auth import User
from app.models.calibration import Calibration, Device
from app.models.course import (
    Course,
    CourseVersion,
    CourseVersionItem,
    Enrollment,
    Lesson,
    LessonVersion,
)
from app.models.gaze import LearningSession
from app.schemas.course import SlideOut
from app.schemas.gaze import (
    LearningSessionCreateIn,
    LearningSessionEndIn,
    LearningSessionOut,
)
from app.services import content

router = APIRouter(tags=["learning-sessions"])

SESSION_TTL_HOURS = 12
PIPELINE_VERSION = "gaze-v2"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _session_out(session: LearningSession, *, mode: str = "first") -> LearningSessionOut:
    config = session.config or {}
    return LearningSessionOut(
        id=session.id,
        enrollment_id=session.enrollment_id,
        lesson_id=config.get("lesson_id", ""),
        device_id=config.get("device_id", ""),
        calibrated=session.calibration_id is not None,
        status=session.status,
        tracking_consent=session.tracking_consent,
        mode=mode,
        viewport_width_px=config.get("viewport_width_px"),
        viewport_height_px=config.get("viewport_height_px"),
        calibration_width_px=config.get("calibration_width_px"),
        calibration_height_px=config.get("calibration_height_px"),
        device_pixel_ratio=config.get("device_pixel_ratio"),
        course_version_item_id=session.course_version_item_id,
        calibration_id=session.calibration_id,
        quiz_attempt_id=session.quiz_attempt_id,
        expires_at=session.expires_at.isoformat() if session.expires_at else None,
        pipeline_version=session.pipeline_version,
    )


async def _published_item(
    db: AsyncSession, lesson_id: str
) -> tuple[Lesson, Course, CourseVersion, CourseVersionItem, LessonVersion]:
    lesson = await db.get(
        Lesson,
        lesson_id,
        options=[raiseload(Lesson.versions), raiseload(Lesson.slides)],
    )
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài học")
    course = await db.get(
        Course,
        lesson.course_id,
        options=[
            raiseload(Course.versions),
            raiseload(Course.enrollments),
            raiseload(Course.owner),
            raiseload(Course.creator),
        ],
    )
    if course is None or course.published_version_id is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Khóa học chưa được xuất bản"
        )
    published = await db.get(
        CourseVersion,
        course.published_version_id,
        options=[
            raiseload(CourseVersion.modules),
            raiseload(CourseVersion.items),
        ],
    )
    item = (
        await db.execute(
            select(CourseVersionItem).where(
                CourseVersionItem.course_version_id == published.id,
                CourseVersionItem.lesson_id == lesson.id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Bài học chưa có trong bản xuất bản"
        )
    lesson_version = await db.get(
        LessonVersion,
        item.lesson_version_id,
        options=[raiseload(LessonVersion.slides)],
    )
    if lesson_version is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên bản bài học"
        )
    return lesson, course, published, item, lesson_version


async def _device(
    db: AsyncSession, user_id: str, fingerprint: str
) -> Device:
    device = (
        await db.execute(
            select(Device).where(
                Device.owner_id == user_id,
                Device.fingerprint == fingerprint,
            )
        )
    ).scalar_one_or_none()
    if device is None:
        device = Device(owner_id=user_id, fingerprint=fingerprint)
        db.add(device)
        await db.flush()
    return device


async def _current_calibration(
    db: AsyncSession, device: Device
) -> Calibration | None:
    if not device.current_calibration_id:
        return None
    return await db.get(Calibration, device.current_calibration_id)


@router.post("/api/learning-sessions", response_model=LearningSessionOut, status_code=201)
async def create_learning_session(
    body: LearningSessionCreateIn,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    enrollment = await db.get(Enrollment, body.enrollment_id)
    if enrollment is None or enrollment.student_id != user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Bạn chưa tham gia khóa học"
        )
    if enrollment.status == "dropped":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Đăng ký khóa học đã bị hủy"
        )

    lesson, course, published, item, lesson_version = await _published_item(
        db, body.lesson_id
    )
    if course.archived_at is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "course_archived", "message": "Khóa học đã được lưu trữ"},
        )
    if item.course_version_id != published.id or enrollment.course_id != course.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Bài học không thuộc khóa đã đăng ký"
        )

    device = await _device(db, user.id, body.device_fingerprint)
    calibration = await _current_calibration(db, device)
    if course.require_calibration and calibration is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "calibration_required",
                "message": "Cần hiệu chỉnh điểm nhìn trước khi học",
            },
        )
    # Không chặn khi viewport khác lúc calibration: frontend quy đổi toạ độ
    # gaze từ viewport calibration sang viewport hiện tại (zoom/resize/move).
    config = {
        "lesson_id": lesson.id,
        "device_id": device.id,
        "viewport_width_px": body.viewport_width_px,
        "viewport_height_px": body.viewport_height_px,
        "calibration_width_px": body.calibration_width_px,
        "calibration_height_px": body.calibration_height_px,
        "device_pixel_ratio": body.device_pixel_ratio,
    }

    existing = (
        await db.execute(
            select(LearningSession)
            .where(
                LearningSession.enrollment_id == enrollment.id,
                LearningSession.course_version_item_id == item.id,
                LearningSession.status == "in_progress",
            )
            .order_by(LearningSession.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        same_context = (
            existing.calibration_id == (calibration.id if calibration else None)
            and (existing.config or {}).get("viewport_width_px")
            == body.viewport_width_px
            and (existing.config or {}).get("viewport_height_px")
            == body.viewport_height_px
            and abs(
                float((existing.config or {}).get("device_pixel_ratio", 0))
                - body.device_pixel_ratio
            )
            <= 1e-6
        )
        if same_context:
            return _session_out(existing, mode="continue")
        existing.status = "aborted"
        existing.ended_at = _now()

    now = _now()
    session = LearningSession(
        enrollment_id=enrollment.id,
        course_version_item_id=item.id,
        quiz_attempt_id=body.quiz_attempt_id,
        calibration_id=calibration.id if calibration else None,
        pipeline_version=PIPELINE_VERSION,
        config=config,
        tracking_consent=body.tracking_consent,
        status="in_progress",
        started_at=now,
        expires_at=now + timedelta(hours=SESSION_TTL_HOURS),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _session_out(session)


@router.patch("/api/learning-sessions/{session_id}", response_model=LearningSessionOut)
async def end_learning_session(
    session_id: str,
    body: LearningSessionEndIn,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(LearningSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên học")
    enrollment = await db.get(Enrollment, session.enrollment_id)
    if enrollment is None or enrollment.student_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    if session.status != "in_progress":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "session_closed", "message": "Phiên học đã đóng"},
        )
    session.status = body.status
    session.ended_at = _now()
    await db.commit()
    await db.refresh(session)
    return _session_out(session)


@router.get(
    "/api/learning-sessions/{session_id}/contents",
    response_model=list[SlideOut],
)
async def get_session_contents(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(LearningSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên học")
    enrollment = await db.get(Enrollment, session.enrollment_id)
    if enrollment is None or enrollment.student_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    item = await db.get(CourseVersionItem, session.course_version_item_id)
    if item is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nội dung phiên học"
        )
    return await content.get_lesson_version_contents(db, item.lesson_version_id)
