"""Fixture hộp đen cho backend: DB/Redis thật, model/LLM giả."""

from __future__ import annotations

import os
import shutil
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

# Env phải được đặt trước khi import app. Khi chạy trong docker-compose các
# biến này đã có; setdefault chỉ hỗ trợ chạy host với TEST_DATABASE_URL.
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-32-bytes-min")
os.environ.setdefault("CORS_ORIGINS", "http://testserver")
os.environ.setdefault("AI_HTTP_URL", "http://localhost:8000")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("OTP_DEV_ECHO", "true")
os.environ.setdefault("OTP_HASH_SECRET", "test-otp-hash-secret")
os.environ.setdefault("OTP_ALLOWED_DOMAINS", "st.neu.edu.vn")
os.environ.setdefault("OTP_STUDENT_ID_PATTERN", r"^\d{8}$")
os.environ.setdefault("CONTENT_VIEW_MIN_DWELL_MS", "1000")
os.environ.setdefault("GAZE_FPS", "15")
os.environ.setdefault("TRUSTED_PROXY_IPS", "")

from app.core import security
from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.main import app

PASSWORD = "Password123!"
TRUNCATE_EXCLUDE = ("schema_migrations", "app_metadata")


@pytest_asyncio.fixture(scope="session")
async def live_app() -> AsyncIterator[Any]:
    async with LifespanManager(app):
        yield app


@pytest_asyncio.fixture(scope="session")
async def transport(live_app: Any) -> ASGITransport:
    return ASGITransport(app=live_app)


@pytest_asyncio.fixture(autouse=True)
async def clean_state() -> AsyncIterator[None]:
    """Truncate DB + flush Redis DB 15 + dọn media trước mỗi test."""
    async with engine.begin() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public'"
                )
            )
        ).scalars().all()
        tables = [name for name in rows if name not in TRUNCATE_EXCLUDE]
        if tables:
            quoted = ", ".join(f'"{name}"' for name in tables)
            await conn.execute(
                text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")
            )

    if settings.redis_url:
        import redis.asyncio as aioredis

        redis = aioredis.from_url(settings.redis_url)
        try:
            await redis.flushdb()
        finally:
            await redis.aclose()

    # Rate limit in-memory fallback (khi Redis lỗi) không được rò giữa test.
    from app.core import ratelimit

    ratelimit._BUCKETS.clear()

    media = settings.media_path
    if media.is_dir():
        for child in media.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)

    yield


@pytest_asyncio.fixture
async def client(transport: ASGITransport) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest_asyncio.fixture
async def client_factory(
    transport: ASGITransport,
) -> AsyncIterator[Any]:
    clients: list[AsyncClient] = []

    async def make() -> AsyncClient:
        c = AsyncClient(transport=transport, base_url="http://testserver")
        clients.append(c)
        return c

    yield make
    for c in clients:
        await c.aclose()


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


async def fetch_one(sql: str, params: dict | None = None) -> Any:
    async with engine.connect() as conn:
        row = (
            await conn.execute(text(sql), params or {})
        ).mappings().first()
        return dict(row) if row is not None else None


async def fetch_all(sql: str, params: dict | None = None) -> list[dict]:
    async with engine.connect() as conn:
        rows = (await conn.execute(text(sql), params or {})).mappings().all()
        return [dict(row) for row in rows]


async def execute(sql: str, params: dict | None = None) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(sql), params or {})


async def insert_returning_id(sql: str, params: dict | None = None) -> str:
    async with engine.begin() as conn:
        value = (await conn.execute(text(sql), params or {})).scalar_one()
        return str(value)


def now() -> datetime:
    return datetime.now(UTC)


def new_uuid() -> str:
    return str(uuid.uuid4())


async def create_user(
    *,
    email: str | None = None,
    role: str = "student",
    password: str | None = PASSWORD,
    status: str = "active",
    full_name: str = "Test User",
) -> dict:
    email = email or f"{role}-{uuid.uuid4().hex[:10]}@example.com"
    user_id = new_uuid()
    password_hash = await __import__("asyncio").to_thread(
        security.hash_password, password
    ) if password else None
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO users
                    (id, email, password_hash, role, status, full_name,
                     email_verified_at)
                VALUES
                    (:id, :email, :password_hash, :role, :status, :full_name,
                     now())
                """
            ),
            {
                "id": user_id,
                "email": email,
                "password_hash": password_hash,
                "role": role,
                "status": status,
                "full_name": full_name,
            },
        )
    if role == "student":
        await execute(
            "INSERT INTO student_profiles (user_id, student_code) "
            "VALUES (:user_id, :code)",
            {"user_id": user_id, "code": f"SV{uuid.uuid4().int % 10**8:08d}"},
        )
    elif role == "teacher":
        await execute(
            "INSERT INTO teacher_profiles (user_id, teacher_code) "
            "VALUES (:user_id, :code)",
            {"user_id": user_id, "code": f"GV{uuid.uuid4().int % 10**8:08d}"},
        )
    return {"id": user_id, "email": email, "role": role}


async def login(
    client: AsyncClient,
    email: str,
    password: str = PASSWORD,
    *,
    bearer: bool = True,
) -> dict:
    response = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    if bearer:
        client.headers["Authorization"] = f"Bearer {data['accessToken']}"
    return data


async def create_course(
    *,
    teacher_id: str,
    student_id: str | None = None,
    status: str = "draft",
    title: str = "Test Course",
    require_calibration: bool = False,
    show_gaze_dot: bool = False,
) -> dict:
    course_id = new_uuid()
    await execute(
        """
        INSERT INTO courses
            (id, owner_id, created_by, title, description, status,
             published_at, require_calibration, show_gaze_dot)
        VALUES
            (:id, :teacher, :teacher, :title, '', :status,
             CASE WHEN :is_published THEN now() ELSE NULL END,
             :require_calibration, :show_gaze_dot)
        """,
        {
            "id": course_id,
            "teacher": teacher_id,
            "title": title,
            "status": status,
            "is_published": status == "published",
            "require_calibration": require_calibration,
            "show_gaze_dot": show_gaze_dot,
        },
    )
    module_id = new_uuid()
    await execute(
        "INSERT INTO course_modules (id, course_id, title, position) "
        "VALUES (:id, :course, 'Chương 1', 0)",
        {"id": module_id, "course": course_id},
    )
    enrollment_id = None
    if student_id:
        enrollment_id = new_uuid()
        await execute(
            "INSERT INTO enrollments (id, course_id, student_id, status) "
            "VALUES (:id, :course, :student, 'active')",
            {"id": enrollment_id, "course": course_id, "student": student_id},
        )
    return {
        "course_id": course_id,
        "module_id": module_id,
        "enrollment_id": enrollment_id,
    }


async def create_lesson(
    *,
    module_id: str,
    title: str = "Bài 1",
    kind: str = "lesson",
    position: int = 0,
    quiz_config: dict | None = None,
    pdf_asset_id: str | None = None,
) -> str:
    lesson_id = new_uuid()
    import json

    await execute(
        """
        INSERT INTO lessons
            (id, module_id, title, kind, position, pdf_asset_id, quiz_config)
        VALUES
            (:id, :module, :title, :kind, :position, :pdf, CAST(:config AS jsonb))
        """,
        {
            "id": lesson_id,
            "module": module_id,
            "title": title,
            "kind": kind,
            "position": position,
            "pdf": pdf_asset_id,
            "config": json.dumps(quiz_config or {}),
        },
    )
    return lesson_id


async def create_media_asset(
    *, course_id: str, object_key: str | None = None
) -> str:
    asset_id = new_uuid()
    object_key = object_key or f"test/{uuid.uuid4().hex}.pdf"
    await execute(
        """
        INSERT INTO media_assets
            (id, course_id, storage_backend, object_key, sha256, mime_type,
             byte_size, state, page_count, source_format)
        VALUES
            (:id, :course, 'local', :key, :sha, 'application/pdf', 4,
             'ready', 1, 'pdf')
        """,
        {
            "id": asset_id,
            "course": course_id,
            "key": object_key,
            "sha": uuid.uuid4().hex + uuid.uuid4().hex,
        },
    )
    return asset_id


async def create_slide(
    *,
    lesson_id: str,
    position: int = 0,
    title: str = "Slide 1",
    index_status: str = "ready",
    transcript: str = "",
) -> str:
    slide_id = new_uuid()
    await execute(
        """
        INSERT INTO slides
            (id, lesson_id, position, page_number, title, index_status,
             transcript)
        VALUES
            (:id, :lesson, :position, :page, :title, :status, :transcript)
        """,
        {
            "id": slide_id,
            "lesson": lesson_id,
            "position": position,
            "page": position + 1,
            "title": title,
            "status": index_status,
            "transcript": transcript,
        },
    )
    return slide_id


async def create_calibration(
    *,
    user_id: str,
    fingerprint: str = "test-device",
    model_version: str = "ubj-linreg-v3-b16",
    created_at: str | None = None,
) -> str:
    calibration_id = new_uuid()
    await execute(
        """
        INSERT INTO gaze_calibrations
            (id, user_id, device_fingerprint, model_ubj, model_hash,
             model_version, viewport_width_px, viewport_height_px,
             device_pixel_ratio, num_points, created_at)
        VALUES
            (:id, :user, :fingerprint, :model, :hash, :version, 1280, 720,
             1.0, 25, COALESCE(CAST(:created_at AS timestamptz), now()))
        """,
        {
            "id": calibration_id,
            "user": user_id,
            "fingerprint": fingerprint,
            "model": b"test-model",
            "hash": uuid.uuid4().hex + uuid.uuid4().hex,
            "version": model_version,
            "created_at": created_at,
        },
    )
    return calibration_id


async def create_quiz(
    *,
    module_id: str,
    title: str = "Bài tập 1",
    position: int = 0,
    allow_retry: bool = False,
    allow_chatbot: bool = False,
    status: str = "published",
    questions: list[dict] | None = None,
) -> str:
    if questions is None:
        questions = [
            {
                "id": "q1",
                "prompt": "1 + 1 bằng mấy?",
                "options": [
                    {"id": "a", "text": "2"},
                    {"id": "b", "text": "3"},
                ],
                "correctOptionIds": ["a"],
                "allowMultiple": False,
                "explanation": "1 + 1 = 2",
                "points": 1,
            }
        ]
    return await create_lesson(
        module_id=module_id,
        title=title,
        kind="quiz",
        position=position,
        quiz_config={
            "instructions": "Chọn đáp án đúng.",
            "durationMinutes": 30,
            "allowRetry": allow_retry,
            "allowChatbot": allow_chatbot,
            "status": status,
            "questions": questions,
        },
    )


@pytest_asyncio.fixture
async def db_session_local() -> AsyncIterator[Any]:
    async with SessionLocal() as session:
        yield session
