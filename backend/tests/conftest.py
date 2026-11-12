"""Fixtures cho backend integration tests.

Yêu cầu: TEST_DATABASE_URL trỏ tới database đã chạy migration baseline.
Script scripts/test_backend.sh tạo DB tạm và chạy migration trước khi pytest.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import uuid
from collections.abc import AsyncIterator
from urllib.parse import urlparse

import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

# Phải set env TRƯỚC khi import app.* vì settings là singleton.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise RuntimeError("Thiếu TEST_DATABASE_URL. Chạy ./scripts/test_backend.sh hoặc set biến này.")

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
# Dùng role read-only admin_reader trên test DB để test đúng quyền thật.
# Role được db/migrate.sh tạo khi có ADMIN_DB_USER + ADMIN_DB_PASSWORD.
_admin_user = os.environ.get("ADMIN_DB_USER", "")
_admin_password = os.environ.get("ADMIN_DB_PASSWORD", "")
if _admin_user and _admin_password:
    _parsed = urlparse(TEST_DATABASE_URL)
    _admin_netloc = f"{_admin_user}:{_admin_password}@{_parsed.hostname}:{_parsed.port}"
    os.environ["ADMIN_DB_URL"] = _parsed._replace(netloc=_admin_netloc).geturl()
else:
    os.environ["ADMIN_DB_URL"] = ""
os.environ["JWT_SECRET"] = "test-secret-not-for-production-32-bytes-min"
os.environ["CORS_ORIGINS"] = "http://testserver"
os.environ["AI_HTTP_URL"] = "http://localhost:8000"
os.environ["COOKIE_SECURE"] = "false"
os.environ["DEBUG"] = "true"
os.environ["REDIS_URL"] = ""
os.environ["CHATBOT_URL"] = ""
os.environ["CHATBOT_INTERNAL_TOKEN"] = ""
os.environ["TRUSTED_PROXY_IPS"] = ""
os.environ["MEDIA_DIR"] = tempfile.mkdtemp(prefix="eyelearning-test-media-")
for key in (
    "R2_ACCOUNT_ID",
    "R2_BUCKET_NAME",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_PUBLIC_URL",
    "MICROSOFT_CLIENT_ID",
    "MICROSOFT_CLIENT_SECRET",
    "MICROSOFT_TENANT_ID",
):
    os.environ[key] = ""

from app.core import security  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.crud import user as user_crud  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.auth import Role, UserRole  # noqa: E402
from app.models.course import (  # noqa: E402
    Course,
    CourseVersion,
    CourseVersionItem,
    CourseVersionModule,
    Enrollment,
    Lesson,
    LessonVersion,
    LessonVersionSlide,
    Slide,
    SlideVersion,
)
from app.models.media import MediaAsset  # noqa: E402
from app.models.profile import TeacherProfile  # noqa: E402
from app.models.quiz import QuizSpec  # noqa: E402


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with LifespanManager(app):
        # Mỗi test dùng namespace rate-limit riêng để không chạm 429 khi nhiều
        # test login từ cùng IP 127.0.0.1.
        settings.app_instance_id = f"test-{uuid.uuid4().hex}"
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as c:
            yield c
    await engine.dispose()


async def create_user(
    *,
    email: str,
    password: str = "Password123!",
    role: str = "student",
    full_name: str = "Test User",
) -> str:
    async with SessionLocal() as db:
        user = await user_crud.create_student(
            db,
            email=email,
            password_hash=security.hash_password(password),
            full_name=full_name,
        )
        if role != "student":
            role_row = (await db.execute(select(Role).where(Role.code == role))).scalar_one()
            db.add(UserRole(user_id=user.id, role_id=role_row.id))
            if role == "teacher":
                db.add(
                    TeacherProfile(
                        user_id=user.id,
                        teacher_code=f"T{user.id[:8].upper()}",
                        department="Test",
                    )
                )
        await db.commit()
        return user.id


async def seed_course(
    *,
    teacher_id: str,
    student_id: str,
    require_calibration: bool = False,
) -> dict[str, str]:
    async with SessionLocal() as db:
        course = Course(
            owner_id=teacher_id,
            created_by=teacher_id,
            require_calibration=require_calibration,
        )
        db.add(course)
        await db.flush()

        version = CourseVersion(
            course_id=course.id,
            version_no=1,
            state="published",
            title="Test Course",
            created_by=teacher_id,
        )
        db.add(version)
        await db.flush()
        course.published_version_id = version.id

        module = CourseVersionModule(
            course_version_id=version.id,
            title="Module 1",
            position=0,
        )
        db.add(module)
        await db.flush()

        lesson = Lesson(course_id=course.id, kind="lesson")
        db.add(lesson)
        await db.flush()

        lesson_version = LessonVersion(
            lesson_id=lesson.id,
            version_no=1,
            state="published",
            title="Lesson 1",
            created_by=teacher_id,
        )
        db.add(lesson_version)
        await db.flush()

        item = CourseVersionItem(
            course_version_id=version.id,
            module_id=module.id,
            lesson_id=lesson.id,
            lesson_version_id=lesson_version.id,
            position=0,
        )
        db.add(item)
        await db.flush()

        enrollment = Enrollment(
            course_id=course.id,
            student_id=student_id,
            status="active",
        )
        db.add(enrollment)
        await db.flush()

        await db.commit()
        return {
            "course_id": course.id,
            "version_id": version.id,
            "module_id": module.id,
            "lesson_id": lesson.id,
            "lesson_version_id": lesson_version.id,
            "item_id": item.id,
            "enrollment_id": enrollment.id,
        }


async def seed_quiz(
    *,
    teacher_id: str,
    student_id: str,
) -> dict[str, str]:
    async with SessionLocal() as db:
        course = Course(
            owner_id=teacher_id,
            created_by=teacher_id,
            require_calibration=False,
        )
        db.add(course)
        await db.flush()

        version = CourseVersion(
            course_id=course.id,
            version_no=1,
            state="published",
            title="Quiz Course",
            created_by=teacher_id,
        )
        db.add(version)
        await db.flush()
        course.published_version_id = version.id

        module = CourseVersionModule(
            course_version_id=version.id,
            title="Quiz Module",
            position=0,
        )
        db.add(module)
        await db.flush()

        lesson = Lesson(course_id=course.id, kind="quiz")
        db.add(lesson)
        await db.flush()

        lesson_version = LessonVersion(
            lesson_id=lesson.id,
            version_no=1,
            state="published",
            title="Quiz 1",
            created_by=teacher_id,
        )
        db.add(lesson_version)
        await db.flush()

        db.add(
            QuizSpec(
                lesson_version_id=lesson_version.id,
                instructions="Chọn đáp án đúng.",
                duration_minutes=30,
                allow_retry=True,
                allow_chatbot=True,
                questions=[
                    {
                        "id": "q1",
                        "prompt": "1 + 1 bằng mấy?",
                        "options": [
                            {"id": "a", "text": "2"},
                            {"id": "b", "text": "3"},
                        ],
                        "correctOptionIds": ["a"],
                        "points": 1,
                        "explanation": "1 + 1 = 2",
                    }
                ],
            )
        )

        item = CourseVersionItem(
            course_version_id=version.id,
            module_id=module.id,
            lesson_id=lesson.id,
            lesson_version_id=lesson_version.id,
            position=0,
        )
        db.add(item)
        await db.flush()

        enrollment = Enrollment(
            course_id=course.id,
            student_id=student_id,
            status="active",
        )
        db.add(enrollment)
        await db.flush()
        await db.commit()
        return {
            "course_id": course.id,
            "version_id": version.id,
            "module_id": module.id,
            "lesson_id": lesson.id,
            "lesson_version_id": lesson_version.id,
            "item_id": item.id,
            "enrollment_id": enrollment.id,
        }


async def seed_slide(
    *,
    course_id: str,
    lesson_id: str,
    lesson_version_id: str,
    teacher_id: str,
    position: int = 0,
) -> dict[str, str]:
    async with SessionLocal() as db:
        asset = MediaAsset(
            course_id=course_id,
            storage_backend="local",
            object_key=f"test/{uuid.uuid4().hex}.pdf",
            sha256=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            mime_type="application/pdf",
            byte_size=4,
            state="ready",
            metadata_={"page_count": 1, "source_format": "pdf"},
        )
        db.add(asset)
        await db.flush()

        slide = Slide(lesson_id=lesson_id)
        db.add(slide)
        await db.flush()

        slide_version = SlideVersion(
            slide_id=slide.id,
            revision_no=1,
            source_pdf_asset_id=asset.id,
            source_page=1,
            render_metadata={},
            created_by=teacher_id,
        )
        db.add(slide_version)
        await db.flush()

        membership = LessonVersionSlide(
            lesson_version_id=lesson_version_id,
            slide_id=slide.id,
            slide_version_id=slide_version.id,
            position=position,
            title=f"Slide {position + 1}",
        )
        db.add(membership)
        await db.flush()
        await db.commit()
        return {
            "asset_id": asset.id,
            "slide_id": slide.id,
            "slide_version_id": slide_version.id,
            "lesson_version_slide_id": membership.id,
        }


async def login(client: AsyncClient, email: str, password: str = "Password123!") -> str:
    response = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["accessToken"]
