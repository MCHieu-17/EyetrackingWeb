from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.access import course_of_lesson
from app.api.deps import can_access_course, get_current_user, require_roles
from app.db.session import get_db
from app.models.auth import User
from app.models.course import Course, Enrollment, Lesson
from app.models.quiz import QuizAttempt
from app.schemas.quiz import QuizAssignmentOut, QuizAttemptOut
from app.services.quiz import (
    assignment_out,
    attempt_expiry,
    attempt_out,
    grade_answers,
)

router = APIRouter(tags=["quiz-attempts"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _published_quiz(
    db: AsyncSession, lesson_id: str
) -> tuple[Lesson, Course, dict]:
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None or lesson.kind != "quiz":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài tập")
    course = await course_of_lesson(db, lesson)
    if course is None or course.status not in {"published", "archived"}:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Khóa học chưa được xuất bản"
        )
    if course.status == "archived":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "course_archived", "message": "Khóa học đã được lưu trữ"},
        )
    return lesson, course, dict(lesson.quiz_config or {})


async def _enrollment(
    db: AsyncSession, course_id: str, student_id: str
) -> Enrollment | None:
    return (
        await db.execute(
            select(Enrollment).where(
                Enrollment.course_id == course_id,
                Enrollment.student_id == student_id,
                Enrollment.status != "dropped",
            )
        )
    ).scalar_one_or_none()


async def _attempt_or_404(db: AsyncSession, attempt_id: str) -> QuizAttempt:
    attempt = await db.get(QuizAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lượt làm")
    return attempt


@router.get("/api/lessons/{lesson_id}/quiz", response_model=QuizAssignmentOut)
async def get_quiz_spec(
    lesson_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None or lesson.kind != "quiz":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài tập")
    course = await course_of_lesson(db, lesson)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    config = dict(lesson.quiz_config or {})

    attempt = None
    if user.role == "student":
        enrollment = await _enrollment(db, course.id, user.id)
        if enrollment is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail="Bạn chưa tham gia khóa học"
            )
        attempt = (
            await db.execute(
                select(QuizAttempt)
                .where(
                    QuizAttempt.enrollment_id == enrollment.id,
                    QuizAttempt.lesson_id == lesson.id,
                )
                .order_by(QuizAttempt.attempt_no.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    elif not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return assignment_out(
        course=course, lesson=lesson, config=config, user=user, attempt=attempt
    )


@router.post(
    "/api/lessons/{lesson_id}/attempts",
    response_model=QuizAttemptOut,
    status_code=201,
)
async def start_attempt(
    lesson_id: str,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    lesson, course, config = await _published_quiz(db, lesson_id)
    enrollment = await _enrollment(db, course.id, user.id)
    if enrollment is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Bạn chưa tham gia khóa học"
        )

    existing = (
        await db.execute(
            select(QuizAttempt)
            .where(
                QuizAttempt.enrollment_id == enrollment.id,
                QuizAttempt.lesson_id == lesson.id,
                QuizAttempt.status == "in_progress",
            )
            .order_by(QuizAttempt.attempt_no.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return attempt_out(existing)

    last = (
        await db.execute(
            select(QuizAttempt)
            .where(
                QuizAttempt.enrollment_id == enrollment.id,
                QuizAttempt.lesson_id == lesson.id,
            )
            .order_by(QuizAttempt.attempt_no.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if last is not None and last.status == "submitted" and not config.get("allowRetry"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "attempt_submitted", "message": "Bạn đã nộp bài này"},
        )

    now = _now()
    expires_at = attempt_expiry(config, now)
    attempt = QuizAttempt(
        enrollment_id=enrollment.id,
        lesson_id=lesson.id,
        attempt_no=(last.attempt_no + 1) if last else 1,
        status="in_progress",
        started_at=now,
        expires_at=expires_at,
        quiz_snapshot=config,
        answers={},
        grading={},
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return attempt_out(attempt)


@router.get(
    "/api/lessons/{lesson_id}/attempts",
    response_model=list[QuizAttemptOut],
)
async def list_attempts(
    lesson_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài học")
    course = await course_of_lesson(db, lesson)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")

    stmt = select(QuizAttempt).where(QuizAttempt.lesson_id == lesson.id)
    if user.role == "student":
        enrollment = await _enrollment(db, course.id, user.id)
        if enrollment is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail="Bạn chưa tham gia khóa học"
            )
        stmt = stmt.where(QuizAttempt.enrollment_id == enrollment.id)
    elif not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    rows = (
        await db.execute(
            stmt.order_by(QuizAttempt.attempt_no.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return [attempt_out(attempt) for attempt in rows]


@router.post("/api/attempts/{attempt_id}/submit", response_model=QuizAttemptOut)
async def submit_attempt(
    attempt_id: str,
    body: dict,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    attempt = await _attempt_or_404(db, attempt_id)
    if attempt.status != "in_progress":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "attempt_submitted", "message": "Lượt làm đã được nộp"},
        )
    if attempt.expires_at < _now():
        attempt.status = "expired"
        await db.commit()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "attempt_expired", "message": "Lượt làm đã hết hạn"},
        )
    lesson = await db.get(Lesson, attempt.lesson_id)
    course = await course_of_lesson(db, lesson) if lesson else None
    if lesson is None or course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    enrollment = await _enrollment(db, course.id, user.id)
    if enrollment is None or enrollment.id != attempt.enrollment_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")

    config = (
        attempt.quiz_snapshot
        if attempt.quiz_snapshot
        else dict(lesson.quiz_config or {})
    )
    answers = body.get("answers") or {}
    if not isinstance(answers, dict):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="answers không hợp lệ"
        )

    grading, score, max_score = grade_answers(config, answers)
    attempt.answers = answers
    attempt.grading = grading
    attempt.score = score
    attempt.max_score = max_score
    attempt.submitted_at = _now()
    attempt.status = "submitted"
    await db.commit()
    await db.refresh(attempt)
    return attempt_out(attempt)


@router.post(
    "/api/attempts/{attempt_id}/retry",
    response_model=QuizAttemptOut,
    status_code=201,
)
async def retry_attempt(
    attempt_id: str,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    attempt = await _attempt_or_404(db, attempt_id)
    if attempt.status != "submitted":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "attempt_not_submitted", "message": "Lượt làm chưa nộp"},
        )
    lesson = await db.get(Lesson, attempt.lesson_id)
    course = await course_of_lesson(db, lesson) if lesson else None
    if lesson is None or course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    enrollment = await _enrollment(db, course.id, user.id)
    if enrollment is None or enrollment.id != attempt.enrollment_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    config = dict(lesson.quiz_config or {})
    if not config.get("allowRetry"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Giáo viên chưa cho phép làm lại bài này",
        )
    existing = (
        await db.execute(
            select(QuizAttempt).where(
                QuizAttempt.enrollment_id == attempt.enrollment_id,
                QuizAttempt.lesson_id == attempt.lesson_id,
                QuizAttempt.status == "in_progress",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return attempt_out(existing)

    now = _now()
    expires_at = attempt_expiry(config, now)
    new_attempt = QuizAttempt(
        enrollment_id=attempt.enrollment_id,
        lesson_id=attempt.lesson_id,
        attempt_no=attempt.attempt_no + 1,
        status="in_progress",
        started_at=now,
        expires_at=expires_at,
        quiz_snapshot=config,
        answers={},
        grading={},
    )
    db.add(new_attempt)
    await db.commit()
    await db.refresh(new_attempt)
    return attempt_out(new_attempt)
