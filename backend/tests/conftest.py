"""Fixtures cho backend integration tests (schema generation 13)."""

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

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise RuntimeError(
        "Thiếu TEST_DATABASE_URL. Chạy ./scripts/test_backend.sh hoặc set biến này."
    )

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
_admin_user = os.environ.get("ADMIN_DB_USER", "")
_admin_password = os.environ.get("ADMIN_DB_PASSWORD", "")
if _admin_user and _admin_password:
    _parsed = urlparse(TEST_DATABASE_URL)
    _admin_netloc = (
        f"{_admin_user}:{_admin_password}@{_parsed.hostname}:{_parsed.port}"
    )
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
):
    os.environ[key] = ""
os.environ["SMTP_HOST"] = ""
os.environ["SMTP_USER"] = ""
os.environ["SMTP_PASS"] = ""
os.environ["SMTP_FROM"] = ""
os.environ["OTP_HASH_SECRET"] = "test-otp-hash-secret"
os.environ["OTP_DEV_ECHO"] = "false"
# Giữ cấu hình OTP ổn định dù .env thật có giá trị khác.
os.environ["OTP_ALLOWED_DOMAINS"] = "st.neu.edu.vn"
os.environ["OTP_STUDENT_ID_PATTERN"] = r"^\d{8}$"
os.environ["OTP_TTL_SECONDS"] = "600"
os.environ["OTP_RESEND_SECONDS"] = "60"
os.environ["OTP_MAX_ATTEMPTS"] = "5"
os.environ["OTP_MAX_PER_EMAIL_PER_HOUR"] = "5"
os.environ["OTP_MAX_PER_IP_PER_HOUR"] = "20"
# Ngưỡng phân loại lượt xem ổn định dù .env thật có giá trị khác.
os.environ["CONTENT_VIEW_MIN_DWELL_MS"] = "1000"

from app.core import security  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.crud import user as user_crud  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.course import (  # noqa: E402
    Course,
    CourseModule,
    Enrollment,
    Lesson,
    Slide,
)
from app.models.media import MediaAsset  # noqa: E402
from app.models.profile import TeacherProfile  # noqa: E402


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with LifespanManager(app):
        settings.app_instance_id = f"test-{uuid.uuid4().hex}"
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as c:
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
        user.role = role
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
    status: str = "published",
    title: str = "Test Course",
) -> dict[str, str]:
    async with SessionLocal() as db:
        course = Course(
            owner_id=teacher_id,
            created_by=teacher_id,
            title=title,
            status=status,
            require_calibration=require_calibration,
        )
        db.add(course)
        await db.flush()

        module = CourseModule(course_id=course.id, title="Module 1", position=0)
        db.add(module)
        await db.flush()

        lesson = Lesson(
            module_id=module.id,
            title="Lesson 1",
            kind="lesson",
            position=0,
        )
        db.add(lesson)
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
            "module_id": module.id,
            "lesson_id": lesson.id,
            "enrollment_id": enrollment.id,
        }


async def seed_quiz(
    *,
    teacher_id: str,
    student_id: str,
    allow_chatbot: bool = True,
    allow_retry: bool = True,
) -> dict[str, str]:
    async with SessionLocal() as db:
        course = Course(
            owner_id=teacher_id,
            created_by=teacher_id,
            title="Quiz Course",
            status="published",
            require_calibration=False,
        )
        db.add(course)
        await db.flush()

        module = CourseModule(course_id=course.id, title="Quiz Module", position=0)
        db.add(module)
        await db.flush()

        lesson = Lesson(
            module_id=module.id,
            title="Quiz 1",
            kind="quiz",
            position=0,
            quiz_config={
                "instructions": "Chọn đáp án đúng.",
                "durationMinutes": 30,
                "allowRetry": allow_retry,
                "allowChatbot": allow_chatbot,
                "status": "published",
                "questions": [
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
            },
        )
        db.add(lesson)
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
            "module_id": module.id,
            "lesson_id": lesson.id,
            "enrollment_id": enrollment.id,
        }


async def seed_slide(
    *,
    course_id: str,
    lesson_id: str,
    teacher_id: str,
    position: int = 0,
) -> dict[str, str]:
    del teacher_id
    async with SessionLocal() as db:
        lesson = await db.get(Lesson, lesson_id)
        assert lesson is not None
        asset = MediaAsset(
            course_id=course_id,
            storage_backend="local",
            object_key=f"test/{uuid.uuid4().hex}.pdf",
            sha256=hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
            mime_type="application/pdf",
            byte_size=4,
            state="ready",
            page_count=max(1, position + 1),
            source_format="pdf",
        )
        db.add(asset)
        await db.flush()
        slide = Slide(
            lesson_id=lesson_id,
            position=position,
            page_number=position + 1,
            title=f"Slide {position + 1}",
            index_status="ready",
        )
        db.add(slide)
        lesson.pdf_asset_id = asset.id
        await db.flush()
        await db.commit()
        return {
            "asset_id": asset.id,
            "slide_id": slide.id,
        }


async def login(
    client: AsyncClient, email: str, password: str = "Password123!"
) -> str:
    response = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["accessToken"]
