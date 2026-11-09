import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import raiseload, selectinload

from app.core.rediscache import delete as cache_delete
from app.core.rediscache import get_json as cache_get_json
from app.core.rediscache import set_json as cache_set_json
from app.models.auth import AuthSession, Role, User, UserRole

AUTH_CACHE_TTL_SECONDS = 30


@dataclass(frozen=True)
class AuthUser:
    """User tối thiểu cho mỗi request đã xác thực (cache Redis 30s)."""

    id: str
    status: str
    deleted_at: str | None
    role_codes: list[str]


# Fallback in-process khi Redis không có (dev/test) hoặc Redis lỗi. Mỗi worker
# có cache riêng; TTL ngắn nên sai lệch tối đa 30s.
_AUTH_MEMORY: dict[str, tuple[float, dict]] = {}
_AUTH_MEMORY_MAX = 10_000


def _memory_get(key: str) -> dict | None:
    item = _AUTH_MEMORY.get(key)
    if item is None:
        return None
    expires_at, value = item
    if expires_at <= time.monotonic():
        _AUTH_MEMORY.pop(key, None)
        return None
    return value


def _memory_set(key: str, value: dict) -> None:
    if len(_AUTH_MEMORY) >= _AUTH_MEMORY_MAX:
        now = time.monotonic()
        for stale in [k for k, (exp, _) in _AUTH_MEMORY.items() if exp <= now]:
            _AUTH_MEMORY.pop(stale, None)
        if len(_AUTH_MEMORY) >= _AUTH_MEMORY_MAX:
            _AUTH_MEMORY.clear()
    _AUTH_MEMORY[key] = (time.monotonic() + AUTH_CACHE_TTL_SECONDS, value)


def _auth_user_from_dict(value: dict) -> AuthUser:
    return AuthUser(
        id=value["id"],
        status=value.get("status", ""),
        deleted_at=value.get("deleted_at"),
        role_codes=list(value.get("role_codes") or []),
    )


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    stmt = (
        select(User)
        .options(selectinload(User.roles))
        .where(func.lower(User.email) == email.lower())
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    stmt = (
        select(User)
        .options(selectinload(User.roles))
        .where(User.id == user_id)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_for_auth(db: AsyncSession, user_id: str) -> User | None:
    """Chỉ tải User + roles cho mỗi request đã xác thực.

    Profile/student_profile/teacher_profile không cần cho auth; route nào cần
    hồ sơ thì dùng `get_user_by_id` hoặc truy vấn profile riêng.
    """
    stmt = (
        select(User)
        .options(
            selectinload(User.roles),
            raiseload(User.profile),
            raiseload(User.student_profile),
            raiseload(User.teacher_profile),
        )
        .where(User.id == user_id)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_for_auth_cached(
    db: AsyncSession, user_id: str
) -> User | AuthUser | None:
    """Auth lookup có cache Redis ngắn hạn.

    Cache chỉ chứa id/status/deleted_at/roles — đủ cho phân quyền. Các route
    cần email/password_hash/created_at phải tự load user đầy đủ từ DB.
    """
    cache_key = f"auth:user:{user_id}"
    cached = await cache_get_json(cache_key)
    if isinstance(cached, dict) and cached.get("id") == user_id:
        return _auth_user_from_dict(cached)

    memory = _memory_get(cache_key)
    if memory is not None and memory.get("id") == user_id:
        return _auth_user_from_dict(memory)

    user = await get_user_for_auth(db, user_id)
    if user is not None:
        payload = {
            "id": user.id,
            "status": user.status,
            "deleted_at": (
                user.deleted_at.isoformat() if user.deleted_at else None
            ),
            "role_codes": user.role_codes,
        }
        _memory_set(cache_key, payload)
        await cache_set_json(cache_key, payload, AUTH_CACHE_TTL_SECONDS)
    return user


async def invalidate_auth_cache(user_id: str) -> None:
    cache_key = f"auth:user:{user_id}"
    _AUTH_MEMORY.pop(cache_key, None)
    await cache_delete(cache_key)


async def touch_last_login(db: AsyncSession, user: User) -> None:
    user.last_login_at = datetime.now(timezone.utc)


async def create_session(
    db: AsyncSession,
    *,
    user_id: str,
    refresh_token_hash: str,
    expires_at: datetime,
    user_agent: str | None,
    ip_address: str | None,
) -> AuthSession:
    session = AuthSession(
        user_id=user_id,
        refresh_token_hash=refresh_token_hash,
        user_agent=user_agent,
        ip_address=ip_address,
        expires_at=expires_at,
    )
    db.add(session)
    return session


async def get_valid_session(db: AsyncSession, refresh_token_hash: str) -> AuthSession | None:
    stmt = select(AuthSession).where(
        AuthSession.refresh_token_hash == refresh_token_hash,
        AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > datetime.now(timezone.utc),
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def revoke_session(db: AsyncSession, session: AuthSession) -> None:
    session.revoked_at = datetime.now(timezone.utc)


async def revoke_all_sessions(
    db: AsyncSession, user_id: str, except_token_hash: str | None = None
) -> None:
    """Thu hồi toàn bộ refresh session còn hiệu lực của user.

    Dùng khi đổi mật khẩu để các phiên đăng nhập khác (thiết bị khác) phải
    đăng nhập lại bằng mật khẩu mới. `except_token_hash` giữ lại phiên hiện tại
    (tránh đăng xuất chính người vừa đổi mật khẩu).
    """
    now = datetime.now(timezone.utc)
    stmt = select(AuthSession).where(
        AuthSession.user_id == user_id,
        AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > now,
    )
    for session in (await db.execute(stmt)).scalars():
        if except_token_hash is not None and session.refresh_token_hash == except_token_hash:
            continue
        session.revoked_at = now


async def create_student(
    db: AsyncSession,
    *,
    email: str,
    password_hash: str | None,
    full_name: str,
) -> User:
    """Tạo user mới với role `student` và status `active`.

    `password_hash=None` dành cho tài khoản đăng nhập bằng Microsoft 365.
    Không tạo student_profile/student_code (do admin cấp sau) — hồ sơ cơ bản
    nằm ở user_profiles.
    """
    role_id = (
        await db.execute(select(Role.id).where(Role.code == "student"))
    ).scalar_one()

    user = User(
        email=email.lower(),
        password_hash=password_hash,
        status="active",
    )
    db.add(user)
    await db.flush()

    db.add(UserRole(user_id=user.id, role_id=role_id))

    from app.models.profile import UserProfile

    db.add(UserProfile(user_id=user.id, full_name=full_name))

    await db.flush()
    await db.refresh(user)
    return user
