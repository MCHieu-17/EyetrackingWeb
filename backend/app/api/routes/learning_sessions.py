from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.api.routes.course_visits import (
    active_visit_for_enrollment,
    get_or_create_visit,
)
from app.db.session import get_db
from app.models.auth import User
from app.models.course import Course, CourseModule, Enrollment, Lesson
from app.models.gaze import CourseVisit, LearningSession
from app.schemas.course import SlideOut
from app.schemas.gaze import (
    LearningSessionCreateIn,
    LearningSessionEndIn,
    LearningSessionOut,
)
from app.services import content
from app.services.access import current_calibration
from app.services.embedding_jobs import enqueue_analysis_lesson
from app.services.gaze_views import close_open_views

router = APIRouter(tags=["learning-sessions"])

SESSION_TTL_HOURS = 12
PIPELINE_VERSION = "gaze-v2"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _session_out(session: LearningSession, *, mode: str = "first") -> LearningSessionOut:
    return LearningSessionOut(
        id=session.id,
        enrollment_id=session.enrollment_id,
        lesson_id=session.lesson_id,
        course_visit_id=session.course_visit_id,
        device_id="",
        calibrated=session.calibration_id is not None,
        status=session.status,
        tracking_consent=session.tracking_consent,
        mode=mode,
        viewport_width_px=session.viewport_width_px,
        viewport_height_px=session.viewport_height_px,
        calibration_width_px=session.calibration_width_px,
        calibration_height_px=session.calibration_height_px,
        device_pixel_ratio=session.device_pixel_ratio,
        calibration_id=session.calibration_id,
        quiz_attempt_id=session.quiz_attempt_id,
        expires_at=session.expires_at.isoformat() if session.expires_at else None,
        pipeline_version=session.pipeline_version,
    )


async def _published_lesson(
    db: AsyncSession, lesson_id: str
) -> tuple[Lesson, Course]:
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài học")
    module = await db.get(CourseModule, lesson.module_id)
    course = await db.get(Course, module.course_id) if module else None
    if course is None or course.status not in {"published", "archived"}:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Khóa học chưa được xuất bản"
        )
    return lesson, course


async def _session_for_user(
    db: AsyncSession, session_id: str, user: User
) -> LearningSession:
    session = await db.get(LearningSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên học")
    student_id = (
        await db.execute(
            select(Enrollment.student_id).where(Enrollment.id == session.enrollment_id)
        )
    ).scalar_one_or_none()
    if student_id is None or student_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return session


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

    lesson, course = await _published_lesson(db, body.lesson_id)
    if enrollment.course_id != course.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Bài học không thuộc khóa đã đăng ký"
        )
    if course.status == "archived":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "course_archived", "message": "Khóa học đã được lưu trữ"},
        )

    calibration = await current_calibration(db, user.id, body.device_fingerprint)
    if course.require_calibration and calibration is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "calibration_required",
                "message": "Cần hiệu chỉnh điểm nhìn trước khi học",
            },
        )

    # Mỗi lần vào khóa là một ca; các lesson session trong ca dùng chung
    # course_visit_id. Client cũ không gửi courseVisitId -> tự tìm/tạo ca
    # active gần nhất để không phá vỡ luồng cũ.
    if body.course_visit_id:
        visit = await db.get(CourseVisit, body.course_visit_id)
        if visit is None or visit.enrollment_id != enrollment.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"code": "visit_conflict", "message": "Ca học không thuộc đăng ký"},
            )
        if visit.status != "active":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"code": "visit_closed", "message": "Ca học đã kết thúc"},
            )
    else:
        visit = await active_visit_for_enrollment(db, enrollment.id)
        if visit is None:
            visit = await get_or_create_visit(
                db, enrollment=enrollment, visit_key=None
            )

    existing = (
        await db.execute(
            select(LearningSession)
            .where(
                LearningSession.enrollment_id == enrollment.id,
                LearningSession.lesson_id == lesson.id,
                LearningSession.status == "in_progress",
            )
            .order_by(LearningSession.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        same_context = (
            existing.calibration_id == (calibration.id if calibration else None)
            and existing.viewport_width_px == body.viewport_width_px
            and existing.viewport_height_px == body.viewport_height_px
            and existing.device_pixel_ratio is not None
            and abs(existing.device_pixel_ratio - body.device_pixel_ratio) <= 1e-6
        )
        same_visit = (
            existing.course_visit_id is None
            or existing.course_visit_id == visit.id
        )
        if same_context and same_visit:
            if existing.course_visit_id is None:
                # Nâng cấp session in_progress của client cũ vào ca hiện tại.
                existing.course_visit_id = visit.id
            visit.last_seen_at = _now()
            await db.commit()
            await db.refresh(existing)
            return _session_out(existing, mode="continue")
        aborted_at = _now()
        existing.status = "aborted"
        existing.ended_at = aborted_at
        await close_open_views(db, [existing.id], aborted_at)

    now = _now()
    session = LearningSession(
        enrollment_id=enrollment.id,
        lesson_id=lesson.id,
        course_visit_id=visit.id,
        quiz_attempt_id=body.quiz_attempt_id,
        calibration_id=calibration.id if calibration else None,
        pipeline_version=PIPELINE_VERSION,
        viewport_width_px=body.viewport_width_px,
        viewport_height_px=body.viewport_height_px,
        calibration_width_px=body.calibration_width_px,
        calibration_height_px=body.calibration_height_px,
        device_pixel_ratio=body.device_pixel_ratio,
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
    session = await _session_for_user(db, session_id, user)
    if session.status != "in_progress":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "session_closed", "message": "Phiên học đã đóng"},
        )
    session.status = body.status
    session.ended_at = _now()
    await close_open_views(db, [session.id], session.ended_at)
    if session.course_visit_id:
        visit = await db.get(CourseVisit, session.course_visit_id)
        if visit is not None:
            visit.last_seen_at = session.ended_at
    await enqueue_analysis_lesson(db, session.lesson_id)
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
    session = await _session_for_user(db, session_id, user)
    module = await db.get(CourseModule, (await db.get(Lesson, session.lesson_id)).module_id)
    course = await db.get(Course, module.course_id) if module else None
    if course is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nội dung phiên học"
        )
    return await content.get_lesson_contents(db, course, session.lesson_id)
