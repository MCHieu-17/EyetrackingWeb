"""API chat học tập theo course version, lesson version và attempt cụ thể."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.api.access import get_course_or_404, validate_uuid
from app.api.deps import require_roles, user_rate_limit
from app.core.ratelimit import rate_limit
from app.db.session import get_db
from app.models.auth import User
from app.models.chat import ChatMessage, ChatSession
from app.models.course import (
    Course,
    CourseVersion,
    CourseVersionItem,
    CourseVersionModule,
    Enrollment,
    Lesson,
    LessonVersion,
)
from app.models.quiz import QuizAttempt, QuizSpec
from app.schemas.chat import (
    ChatMessageOut,
    ChatSendIn,
    ChatSessionOut,
    ChatSessionUpdate,
)
from app.services.chat_access import (
    active_attempts,
    chat_access,
    context_key,
    require_chat_access,
)
from app.services.study_chat import (
    chatbot_error_stream,
    chatbot_ready,
    prepare_stream,
    stream_in_session,
)

router = APIRouter(tags=["chat"])

NEW_TITLE = "Phiên mới"


async def _require_enrolled(db: AsyncSession, course_id: str, user: User) -> None:
    stmt = select(Enrollment.id).where(
        Enrollment.course_id == course_id,
        Enrollment.student_id == user.id,
        Enrollment.status == "active",
    )
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Bạn chưa tham gia khóa học"
        )


async def _session_or_404(
    db: AsyncSession, session_id: str, user: User
) -> ChatSession:
    validate_uuid(session_id, "Không tìm thấy phiên chat")
    session = await db.get(
        ChatSession,
        session_id,
        options=[raiseload(ChatSession.messages)],
    )
    if (
        session is None
        or session.student_id != user.id
        or session.archived_at is not None
    ):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên chat"
        )
    return session


async def _message_count(db: AsyncSession, session_id: str) -> int:
    stmt = select(func.count(ChatMessage.id)).where(
        ChatMessage.session_id == session_id
    )
    return int((await db.execute(stmt)).scalar_one())


async def _session_out(db: AsyncSession, session: ChatSession) -> ChatSessionOut:
    return ChatSessionOut(
        id=session.id,
        course_id=session.course_id,
        course_version_id=session.course_version_id,
        lesson_id=session.lesson_id,
        lesson_version_id=session.lesson_version_id,
        assignment_id=session.lesson_version_id,
        attempt_id=session.quiz_attempt_id,
        title=session.title,
        message_count=await _message_count(db, session.id),
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


async def _published_version(db: AsyncSession, course: Course) -> CourseVersion:
    if course.published_version_id is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Khóa học chưa được xuất bản"
        )
    version = await db.get(
        CourseVersion,
        course.published_version_id,
        options=[
            raiseload(CourseVersion.modules),
            raiseload(CourseVersion.items),
        ],
    )
    if version is None or version.state != "published":
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Khóa học chưa được xuất bản"
        )
    return version


async def _item_for_lesson(
    db: AsyncSession, version: CourseVersion, lesson_id: str
) -> CourseVersionItem:
    item = (
        await db.execute(
            select(CourseVersionItem).where(
                CourseVersionItem.course_version_id == version.id,
                CourseVersionItem.lesson_id == lesson_id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Bài học không thuộc bản xuất bản"
        )
    return item


async def _item_for_lesson_version(
    db: AsyncSession, version: CourseVersion, lesson_version_id: str
) -> CourseVersionItem:
    item = (
        await db.execute(
            select(CourseVersionItem).where(
                CourseVersionItem.course_version_id == version.id,
                CourseVersionItem.lesson_version_id == lesson_version_id,
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Bài tập không thuộc bản xuất bản"
        )
    return item


async def _latest_attempt(
    db: AsyncSession, enrollment_id: str, lesson_id: str
) -> QuizAttempt | None:
    return (
        await db.execute(
            select(QuizAttempt)
            .where(
                QuizAttempt.enrollment_id == enrollment_id,
                QuizAttempt.lesson_id == lesson_id,
            )
            .order_by(QuizAttempt.attempt_no.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _resolve_context(
    db: AsyncSession,
    course: Course,
    body: ChatSendIn,
    user: User,
) -> tuple[
    CourseVersion,
    Lesson | None,
    LessonVersion | None,
    str | None,
    QuizSpec | None,
    QuizAttempt | None,
    str,
    str,
]:
    version = await _published_version(db, course)
    enrollment = (
        await db.execute(
            select(Enrollment)
            .where(
                Enrollment.course_id == course.id,
                Enrollment.student_id == user.id,
                Enrollment.status == "active",
            )
            .options(raiseload(Enrollment.course))
        )
    ).scalar_one_or_none()
    if enrollment is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Bạn chưa tham gia khóa học"
        )

    item: CourseVersionItem | None = None
    attempt: QuizAttempt | None = None

    if body.attempt_id is not None:
        attempt = await db.get(QuizAttempt, str(body.attempt_id))
        if attempt is None or attempt.enrollment_id != enrollment.id:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lượt làm bài"
            )
        item = await db.get(CourseVersionItem, attempt.course_version_item_id)
        if item is None or item.course_version_id != version.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Lượt làm bài không thuộc bản xuất bản hiện hành",
            )
        if body.assignment_id is not None and str(body.assignment_id) != item.lesson_version_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Lượt làm bài không khớp bài tập đã chọn",
            )
    elif body.assignment_id is not None:
        item = await _item_for_lesson_version(
            db, version, str(body.assignment_id)
        )
        attempt = await _latest_attempt(db, enrollment.id, item.lesson_id)
        if attempt is not None and (
            attempt.status == "expired"
            or (
                attempt.status == "in_progress"
                and attempt.expires_at <= datetime.now(timezone.utc)
            )
        ):
            attempt = None
    elif body.lesson_id is not None:
        item = await _item_for_lesson(db, version, str(body.lesson_id))
    else:
        active = await active_attempts(db, course.id, user.id)
        if len(active) > 1:
            raise HTTPException(
                400,
                detail="Bạn đang làm nhiều bài tập. Hãy chọn bài cần gợi ý.",
            )
        if len(active) == 1:
            attempt = await db.get(QuizAttempt, active[0]["attemptId"])
            if attempt is not None:
                item = await db.get(
                    CourseVersionItem, attempt.course_version_item_id
                )

    lesson: Lesson | None = None
    lesson_version: LessonVersion | None = None
    module_title: str | None = None
    quiz: QuizSpec | None = None
    if item is not None:
        lesson = await db.get(
            Lesson,
            item.lesson_id,
            options=[raiseload(Lesson.versions), raiseload(Lesson.slides)],
        )
        lesson_version = await db.get(
            LessonVersion,
            item.lesson_version_id,
            options=[raiseload(LessonVersion.slides)],
        )
        module = await db.get(
            CourseVersionModule,
            item.module_id,
            options=[raiseload(CourseVersionModule.items)],
        )
        module_title = module.title if module else None
        if lesson is not None and lesson.kind == "quiz":
            quiz = await db.get(QuizSpec, item.lesson_version_id)

    support_mode = (
        "review"
        if attempt is not None and attempt.status == "submitted"
        else "hint"
    )
    if body.draft_answers:
        if quiz is None:
            raise HTTPException(400, detail="Lựa chọn tạm cần có bài tập")
        valid = {
            question["id"]: {option["id"] for option in question["options"]}
            for question in quiz.questions
        }
        for question_id, options in body.draft_answers.items():
            if question_id not in valid or any(
                option not in valid[question_id] for option in options
            ):
                raise HTTPException(
                    400, detail="Câu hỏi hoặc lựa chọn không thuộc bài tập"
                )

    key = context_key(
        course_version_id=version.id,
        lesson_version_id=lesson_version.id if lesson_version else None,
        attempt_id=attempt.id if attempt else None,
        attempt_status=attempt.status if attempt else None,
    )
    return (
        version,
        lesson,
        lesson_version,
        module_title,
        quiz,
        attempt,
        support_mode,
        key,
    )


async def _prepare(
    db: AsyncSession,
    course: Course,
    body: ChatSendIn,
    user: User,
) -> tuple[
    ChatSession,
    CourseVersion,
    Lesson | None,
    LessonVersion | None,
    str | None,
    QuizSpec | None,
    QuizAttempt | None,
    str,
]:
    (
        version,
        lesson,
        lesson_version,
        module_title,
        quiz,
        attempt,
        support_mode,
        key,
    ) = await _resolve_context(db, course, body, user)

    session = None
    if body.session_id is not None:
        session = await _session_or_404(db, str(body.session_id), user)
        if session.course_id != course.id or session.context_key != key:
            session = None
    if session is None:
        session = ChatSession(
            student_id=user.id,
            course_id=course.id,
            course_version_id=version.id,
            lesson_id=lesson.id if lesson is not None else None,
            lesson_version_id=lesson_version.id if lesson_version else None,
            quiz_attempt_id=attempt.id if attempt is not None else None,
            title=NEW_TITLE,
            context_key=key,
        )
        db.add(session)
        await db.flush()

    return (
        session,
        version,
        lesson,
        lesson_version,
        module_title,
        quiz,
        attempt,
        support_mode,
    )


@router.get("/api/courses/{course_id}/chat/access")
async def get_chat_access(
    course_id: UUID,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_course_or_404(db, str(course_id))
    await _require_enrolled(db, course.id, user)
    return await chat_access(db, course.id, user.id)


@router.get(
    "/api/courses/{course_id}/chat/sessions",
    response_model=list[ChatSessionOut],
)
async def list_sessions(
    course_id: UUID,
    assignment_id: UUID | None = Query(None, alias="assignmentId"),
    attempt_id: UUID | None = Query(None, alias="attemptId"),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_course_or_404(db, str(course_id))
    await _require_enrolled(db, course.id, user)
    await require_chat_access(db, course.id, user.id)

    current_key = None
    if assignment_id is not None:
        version = await _published_version(db, course)
        item = await _item_for_lesson_version(db, version, str(assignment_id))
        enrollment_id = (
            await db.execute(
                select(Enrollment.id).where(
                    Enrollment.course_id == course.id,
                    Enrollment.student_id == user.id,
                )
            )
        ).scalar_one()
        if attempt_id is not None:
            attempt = await db.get(QuizAttempt, str(attempt_id))
            if attempt is None or attempt.enrollment_id != enrollment_id:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lượt làm bài"
                )
        else:
            attempt = await _latest_attempt(db, enrollment_id, item.lesson_id)
        current_key = context_key(
            course_version_id=version.id,
            lesson_version_id=item.lesson_version_id,
            attempt_id=attempt.id if attempt else None,
            attempt_status=attempt.status if attempt else None,
        )

    counts = (
        select(ChatMessage.session_id, func.count(ChatMessage.id).label("n"))
        .group_by(ChatMessage.session_id)
        .subquery()
    )
    stmt = (
        select(ChatSession, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.session_id == ChatSession.id)
        .where(
            ChatSession.student_id == user.id,
            ChatSession.course_id == course.id,
            ChatSession.archived_at.is_(None),
        )
        .order_by(ChatSession.updated_at.desc())
        .options(raiseload(ChatSession.messages))
    )
    if assignment_id is not None:
        stmt = stmt.where(ChatSession.lesson_version_id == str(assignment_id))
    if attempt_id is not None:
        stmt = stmt.where(ChatSession.quiz_attempt_id == str(attempt_id))
    rows = (await db.execute(stmt.limit(limit).offset(offset))).all()
    return [
        ChatSessionOut(
            id=session.id,
            course_id=session.course_id,
            course_version_id=session.course_version_id,
            lesson_id=session.lesson_id,
            lesson_version_id=session.lesson_version_id,
            assignment_id=session.lesson_version_id,
            attempt_id=session.quiz_attempt_id,
            title=session.title,
            can_continue=current_key is None or session.context_key == current_key,
            message_count=int(count),
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
        for session, count in rows
    ]


@router.post(
    "/api/courses/{course_id}/chat/stream",
    dependencies=[
        Depends(rate_limit(20, 60, "study-chat-stream")),
        # Mỗi tài khoản chỉ gửi 1 tin nhắn mỗi 5 giây, trên mọi thiết bị/IP.
        Depends(
            user_rate_limit(
                1,
                5,
                "study-chat-stream",
                detail="Bạn gửi tin nhắn quá nhanh.",
            )
        ),
    ],
)
async def stream_message(
    course_id: UUID,
    body: ChatSendIn,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    course = await get_course_or_404(db, str(course_id))
    await _require_enrolled(db, course.id, user)
    await require_chat_access(db, course.id, user.id)
    (
        session,
        version,
        lesson,
        lesson_version,
        module_title,
        quiz,
        attempt,
        support_mode,
    ) = await _prepare(db, course, body, user)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }

    if not chatbot_ready():
        await db.close()
        return StreamingResponse(
            chatbot_error_stream("Trợ lý học tập chưa được cấu hình"),
            media_type="text/event-stream",
            headers=headers,
        )

    payload, snapshot = await prepare_stream(
        db,
        course=course,
        course_version=version,
        session=session,
        message=body.message,
        lesson=lesson,
        lesson_version=lesson_version,
        module_title=module_title,
        quiz=quiz,
        attempt=attempt,
        support_mode=support_mode,
        draft_answers=body.draft_answers,
    )
    # Trả connection về pool trước khi stream. Generator chỉ mở SessionLocal
    # ngắn khi cần lưu câu trả lời cuối cùng.
    await db.close()

    return StreamingResponse(
        stream_in_session(
            session_id=snapshot.id,
            payload=payload,
            session_snapshot=snapshot,
        ),
        media_type="text/event-stream",
        headers=headers,
    )


@router.get(
    "/api/chat/sessions/{session_id}/messages",
    response_model=list[ChatMessageOut],
)
async def list_messages(
    session_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    session = await _session_or_404(db, session_id, user)
    course = await get_course_or_404(db, session.course_id)
    await _require_enrolled(db, course.id, user)
    await require_chat_access(db, course.id, user.id)
    rows = (
        (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.created_at)
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return [
        ChatMessageOut(
            id=message.id,
            role=message.role,
            content=message.content,
            citations=message.citations or [],
            intent=message.intent,
            created_at=message.created_at,
        )
        for message in rows
    ]


@router.patch("/api/chat/sessions/{session_id}", response_model=ChatSessionOut)
async def rename_session(
    session_id: str,
    body: ChatSessionUpdate,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    session = await _session_or_404(db, session_id, user)
    session.title = body.title.strip()
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return await _session_out(db, session)


@router.delete("/api/chat/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(require_roles("student")),
    db: AsyncSession = Depends(get_db),
):
    session = await _session_or_404(db, session_id, user)
    await db.execute(
        delete(ChatMessage).where(ChatMessage.session_id == session.id)
    )
    await db.execute(delete(ChatSession).where(ChatSession.id == session.id))
    await db.commit()
    return {"status": "ok"}
