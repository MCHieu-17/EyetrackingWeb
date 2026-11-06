import asyncio
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    path = ROOT / ".env"
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


_ENV = _load_env_file()
_PG_USER = _ENV.get("POSTGRES_USER", "postgres")
_PG_PASSWORD = _ENV.get("POSTGRES_PASSWORD", "postgres")

os.environ["TESTING"] = "1"
os.environ.setdefault(
    "DATABASE_URL",
    f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}@localhost:5435/eyelearning_refactor_test",
)
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-pytest-please-change")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("AI_HTTP_URL", "http://127.0.0.1:8000")
os.environ.setdefault("CHATBOT_URL", "http://localhost:8002")
os.environ.setdefault("CHATBOT_INTERNAL_TOKEN", "test-chatbot-token")
os.environ["MEDIA_DIR"] = os.path.join(tempfile.gettempdir(), "eyelearning-test-media")
for key in (
    "R2_ACCOUNT_ID",
    "R2_BUCKET_NAME",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_PUBLIC_URL",
):
    os.environ[key] = ""

import pytest
from sqlalchemy import text

from app.core.ratelimit import _BUCKETS
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
import app.models  # noqa: F401  (register all tables)

# Giữ reference seed; xóa toàn bộ dữ liệu nghiệp vụ.
_KEEP = {"schema_migrations", "app_metadata", "roles", "calibration_settings"}
_TRUNCATE_TABLES = [
    table.name for table in Base.metadata.sorted_tables if table.name not in _KEEP
]
TRUNCATE = "TRUNCATE TABLE " + ", ".join(_TRUNCATE_TABLES) + " CASCADE"

LOOKUPS = """
INSERT INTO roles (code, label) VALUES
    ('admin', 'Quản trị viên'), ('teacher', 'Giáo viên'), ('student', 'Học sinh')
ON CONFLICT (code) DO NOTHING;
INSERT INTO calibration_settings (id, enabled, threshold)
VALUES (1, true, 0.12)
ON CONFLICT (id) DO NOTHING;
"""


def _db_available() -> bool:
    async def check():
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    try:
        asyncio.run(check())
        return True
    except Exception:
        return False


DB_AVAILABLE = _db_available()

requires_db = pytest.mark.skipif(
    not DB_AVAILABLE, reason="PostgreSQL chưa chạy (docker compose up -d postgres)"
)


async def _reset_db():
    """Xóa dữ liệu test. Schema phải được dựng trước bằng scripts/test_db.sh.

    Không tự chạy migration/replay SQL trong fixture: baseline là nguồn schema
    duy nhất (PLAN.md Phase 0/1).
    """
    async with SessionLocal() as session:
        try:
            await session.execute(text(TRUNCATE))
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            raise RuntimeError(
                "Test database chưa được dựng bằng baseline. "
                "Chạy ./scripts/test_db.sh trước khi pytest."
            ) from exc
        for stmt in LOOKUPS.strip().split(";"):
            if stmt.strip():
                await session.execute(text(stmt))
        await session.commit()


async def make_user(
    email: str,
    role: str,
    password: str = "Password123!",
    full_name: str = "Test User",
    code: str | None = None,
) -> str:
    async with SessionLocal() as session:
        await session.execute(
            text(
                """
                INSERT INTO users (email, password_hash, status)
                VALUES (:email, :hash, 'active')
                ON CONFLICT (lower(email)) DO UPDATE
                SET password_hash = EXCLUDED.password_hash
                """
            ),
            {"email": email, "hash": hash_password(password)},
        )
        user_id = str(
            (
                await session.execute(
                    text("SELECT id FROM users WHERE email = :email"), {"email": email}
                )
            ).scalar_one()
        )
        await session.execute(
            text(
                """
                INSERT INTO user_roles (user_id, role_id)
                VALUES (:uid, (SELECT id FROM roles WHERE code = :role))
                ON CONFLICT DO NOTHING
                """
            ),
            {"uid": user_id, "role": role},
        )
        await session.execute(
            text(
                """
                INSERT INTO user_profiles (user_id, full_name)
                VALUES (:uid, :name)
                ON CONFLICT (user_id) DO UPDATE SET full_name = EXCLUDED.full_name
                """
            ),
            {"uid": user_id, "name": full_name},
        )
        if role == "teacher":
            await session.execute(
                text(
                    """
                    INSERT INTO teacher_profiles (user_id, teacher_code)
                    VALUES (:uid, :code)
                    ON CONFLICT (user_id) DO NOTHING
                    """
                ),
                {"uid": user_id, "code": code or f"GV-{user_id[:8]}"},
            )
        if role == "student":
            await session.execute(
                text(
                    """
                    INSERT INTO student_profiles (user_id, student_code)
                    VALUES (:uid, :code)
                    ON CONFLICT (user_id) DO NOTHING
                    """
                ),
                {"uid": user_id, "code": code or f"SV-{user_id[:8]}"},
            )
        await session.commit()
        return user_id


@pytest.fixture()
def client():
    if not DB_AVAILABLE:
        pytest.skip("PostgreSQL chưa chạy")
    asyncio.run(_reset_db())
    _BUCKETS.clear()
    # Import muộn: Phase 1 chỉ cần schema tests; route cũ sẽ được thay ở Phase 2.
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def login(client, email: str, password: str = "Password123!") -> dict:
    r = client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()


def auth(data: dict) -> dict:
    return {"Authorization": f"Bearer {data['accessToken']}"}
