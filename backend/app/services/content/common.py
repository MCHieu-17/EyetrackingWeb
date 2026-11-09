"""Shared helpers for the content service package."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload

from app.models.auth import User
from app.models.course import Course, CourseVersion

logger = logging.getLogger("app.services.content")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _conflict(code: str, message: str) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT, detail={"code": code, "message": message}
    )


def _not_found(message: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=message)


async def get_course_or_404(db: AsyncSession, course_id: str) -> Course:
    course = await db.get(
        Course,
        course_id,
        options=[
            raiseload(Course.versions),
            raiseload(Course.enrollments),
            raiseload(Course.owner),
            raiseload(Course.creator),
        ],
    )
    if course is None:
        raise _not_found("Không tìm thấy khóa học")
    return course


async def get_published_version(
    db: AsyncSession, course: Course
) -> CourseVersion | None:
    if not course.published_version_id:
        return None
    return await db.get(
        CourseVersion,
        course.published_version_id,
        options=[
            raiseload(CourseVersion.modules),
            raiseload(CourseVersion.items),
        ],
    )


async def get_draft_version(
    db: AsyncSession, course: Course, user: User, *, create: bool = True
) -> CourseVersion | None:
    stmt = (
        select(CourseVersion)
        .options(
            raiseload(CourseVersion.modules),
            raiseload(CourseVersion.items),
        )
        .where(
            CourseVersion.course_id == course.id,
            CourseVersion.state == "draft",
        )
    )
    draft = (await db.execute(stmt)).scalar_one_or_none()
    if draft is not None:
        return draft
    if not create:
        return None

    published = await get_published_version(db, course)
    if published is None:
        draft = CourseVersion(
            course_id=course.id,
            version_no=1,
            state="draft",
            generation=1,
            title="Khóa học mới",
            description=None,
            created_by=user.id,
        )
        db.add(draft)
        await db.flush()
        return draft

    from app.services.content.versions import clone_course_version

    draft = await clone_course_version(db, published, user)
    return draft


def bump_generation(course_version: CourseVersion) -> None:
    course_version.generation += 1


def check_generation(course_version: CourseVersion, expected: int | None) -> None:
    if expected is not None and expected != course_version.generation:
        raise _conflict(
            "content_changed",
            "Nội dung đã thay đổi ở phiên khác. Hãy tải lại trước khi lưu.",
        )
