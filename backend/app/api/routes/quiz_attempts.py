from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import can_access_course, get_current_user, require_roles
from app.db.session import get_db
from app.models.auth import User
from app.models.course import (
    Course,
    CourseVersion,
    CourseVersionItem,
    Enrollment,
    Lesson,
    LessonVersion,
)
from app.models.quiz import QuizAttempt, QuizSpec
from app.schemas.quiz import QuizAssignmentOut, QuizAttemptOut
from app.services import content

router = APIRouter(tags=["quiz-attempts"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _public_question(question: dict) -> dict:
    clean = {key: value for key, value in question.items() if key != "correctOptionId"}
    clean["correctOptionIds"] = []
    clean["explanation"] = ""
    return clean


def _reveal_question(question: dict) -> dict:
    clean = {key: value for key, value in question.items() if key != "correctOptionId"}
    clean["correctOptionIds"] = [
        str(item) for item in (question.get("correctOptionIds") or [])
    ]
    return clean


async def _published_item(
    db: AsyncSession, lesson_id: str
) -> tuple[Lesson, Course, CourseVersion, CourseVersionItem, LessonVersion, QuizSpec]:
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài học")
    course = await db.get(Course, lesson.course_id)
    if course is None or course.published_version_id is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Khóa học chưa được xuất bản"
        )
    published = await db.get(CourseVersion, course.published_version_id)
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
    lesson_version = await db.get(LessonVersion, item.lesson_version_id)
    quiz = await db.get(QuizSpec, item.lesson_version_id)
    if lesson_version is None or quiz is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài tập")
    return lesson, course, published, item, lesson_version, quiz


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


def _attempt_out(attempt: QuizAttempt, assignment_id: str) -> QuizAttemptOut:
    return QuizAttemptOut(
        id=attempt.id,
        assignment_id=assignment_id,
        answers=attempt.answers,
        submitted_at=attempt.submitted_at or attempt.started_at,
        score=int(attempt.score or 0),
        max_score=int(attempt.max_score or 0),
    )


async def _assignment_id_for_attempt(db: AsyncSession, attempt: QuizAttempt) -> str:
    item = await db.get(CourseVersionItem, attempt.course_version_item_id)
    return item.lesson_version_id if item else attempt.lesson_id


async def _assignment_out(
    db: AsyncSession,
    *,
    course: Course,
    published: CourseVersion,
    lesson: Lesson,
    lesson_version: LessonVersion,
    quiz: QuizSpec,
    user: User,
    attempt: QuizAttempt | None,
) -> QuizAssignmentOut:
    reveal = bool({"teacher", "admin"} & set(user.role_codes)) or (
        attempt is not None and attempt.status == "submitted"
    )
    questions = [
        _reveal_question(question) if reveal else _public_question(question)
        for question in quiz.questions
    ]
    return QuizAssignmentOut(
        id=lesson_version.id,
        course_id=course.id,
        course_title=published.title,
        lesson_id=lesson.id,
        lesson_title=lesson_version.title,
        title=lesson_version.title,
        instructions=quiz.instructions,
        due_at=quiz.due_at,
        duration_minutes=quiz.duration_minutes,
        status="published" if lesson_version.state == "published" else "draft",
        created_at=lesson_version.created_at,
        expires_at=attempt.expires_at if attempt and attempt.status == "in_progress" else None,
        allow_chatbot=quiz.allow_chatbot,
        allow_retry=quiz.allow_retry,
        questions=questions,
    )


@router.get("/api/quiz-specs/{lesson_version_id}", response_model=QuizAssignmentOut)
async def get_quiz_spec(
    lesson_version_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lesson_version = await db.get(LessonVersion, lesson_version_id)
    if lesson_version is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài tập")
    lesson = await db.get(Lesson, lesson_version.lesson_id)
    course = await db.get(Course, lesson.course_id) if lesson else None
    if lesson is None or course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    quiz = await db.get(QuizSpec, lesson_version.id)
    if quiz is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài tập")

    attempt = None
    if "student" in user.role_codes:
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

    published = await db.get(CourseVersion, course.published_version_id)
    if published is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Khóa học chưa được xuất bản"
        )
    return await _assignment_out(
        db,
        course=course,
        published=published,
        lesson=lesson,
        lesson_version=lesson_version,
        quiz=quiz,
        user=user,
        attempt=attempt,
    )


@router.post("/api/lessons/{lesson_id}/attempts", response_model=QuizAttemptOut, status_code=201)
async def start_attempt(
    lesson_id: str,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    lesson, course, published, item, lesson_version, quiz = await _published_item(
        db, lesson_id
    )
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
        return _attempt_out(existing, item.lesson_version_id)

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
    if last is not None and last.status == "submitted" and not quiz.allow_retry:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "attempt_submitted", "message": "Bạn đã nộp bài này"},
        )

    now = _now()
    expires_at = now + timedelta(minutes=quiz.duration_minutes)
    if quiz.due_at is not None:
        expires_at = min(expires_at, quiz.due_at)
    attempt = QuizAttempt(
        enrollment_id=enrollment.id,
        course_version_item_id=item.id,
        lesson_id=lesson.id,
        attempt_no=(last.attempt_no + 1) if last else 1,
        status="in_progress",
        started_at=now,
        expires_at=expires_at,
        answers={},
        grading={},
    )
    db.add(attempt)
    await db.commit()
    await db.refresh(attempt)
    return _attempt_out(attempt, item.lesson_version_id)


@router.get("/api/lessons/{lesson_id}/attempts", response_model=list[QuizAttemptOut])
async def list_attempts(
    lesson_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    lesson = await db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bài học")
    course = await db.get(Course, lesson.course_id)
    if course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")

    stmt = select(QuizAttempt).where(QuizAttempt.lesson_id == lesson.id)
    if "student" in user.role_codes:
        enrollment = await _enrollment(db, course.id, user.id)
        if enrollment is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail="Bạn chưa tham gia khóa học"
            )
        stmt = stmt.where(QuizAttempt.enrollment_id == enrollment.id)
    elif not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    rows = (
        await db.execute(stmt.order_by(QuizAttempt.attempt_no.desc()))
    ).scalars().all()
    return [
        _attempt_out(row, await _assignment_id_for_attempt(db, row))
        for row in rows
    ]


@router.get("/api/attempts/{attempt_id}", response_model=QuizAttemptOut)
async def get_attempt(
    attempt_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    attempt = await _attempt_or_404(db, attempt_id)
    lesson = await db.get(Lesson, attempt.lesson_id)
    course = await db.get(Course, lesson.course_id) if lesson else None
    if lesson is None or course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    if "student" in user.role_codes:
        enrollment = await _enrollment(db, course.id, user.id)
        if enrollment is None or enrollment.id != attempt.enrollment_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    elif not await can_access_course(db, course, user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    return _attempt_out(attempt, await _assignment_id_for_attempt(db, attempt))


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
    course = await db.get(Course, lesson.course_id) if lesson else None
    if lesson is None or course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    enrollment = await _enrollment(db, course.id, user.id)
    if enrollment is None or enrollment.id != attempt.enrollment_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")

    # quiz_specs PK là lesson_version_id; lấy đúng version của attempt.
    item = await db.get(CourseVersionItem, attempt.course_version_item_id)
    quiz = await db.get(QuizSpec, item.lesson_version_id) if item else None
    if quiz is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy đề")

    answers = body.get("answers") or {}
    if not isinstance(answers, dict):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="answers không hợp lệ")

    grading: dict[str, dict] = {}
    score = 0.0
    max_score = 0.0
    for question in quiz.questions:
        qid = str(question.get("id"))
        points = float(question.get("points") or 0)
        max_score += points
        selected = {str(item) for item in (answers.get(qid) or [])}
        correct = {str(item) for item in (question.get("correctOptionIds") or [])}
        is_correct = selected == correct and bool(correct)
        if is_correct:
            score += points
        grading[qid] = {"correct": is_correct, "points": points if is_correct else 0}

    attempt.answers = answers
    attempt.grading = grading
    attempt.score = score
    attempt.max_score = max_score
    attempt.submitted_at = _now()
    attempt.status = "submitted"
    await db.commit()
    await db.refresh(attempt)
    return _attempt_out(attempt, item.lesson_version_id)


@router.post("/api/attempts/{attempt_id}/retry", response_model=QuizAttemptOut, status_code=201)
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
    course = await db.get(Course, lesson.course_id) if lesson else None
    if lesson is None or course is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khóa học")
    enrollment = await _enrollment(db, course.id, user.id)
    if enrollment is None or enrollment.id != attempt.enrollment_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Không có quyền")
    item = await db.get(CourseVersionItem, attempt.course_version_item_id)
    quiz = await db.get(QuizSpec, item.lesson_version_id) if item else None
    if quiz is None or not quiz.allow_retry:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Giáo viên chưa cho phép làm lại bài này",
        )
    now = _now()
    expires_at = now + timedelta(minutes=quiz.duration_minutes)
    if quiz.due_at is not None:
        expires_at = min(expires_at, quiz.due_at)
    new_attempt = QuizAttempt(
        enrollment_id=attempt.enrollment_id,
        course_version_item_id=attempt.course_version_item_id,
        lesson_id=attempt.lesson_id,
        attempt_no=attempt.attempt_no + 1,
        status="in_progress",
        started_at=now,
        expires_at=expires_at,
        answers={},
        grading={},
    )
    db.add(new_attempt)
    await db.commit()
    await db.refresh(new_attempt)
    return _attempt_out(new_attempt, item.lesson_version_id)
