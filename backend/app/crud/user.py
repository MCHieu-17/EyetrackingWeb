import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rediscache import delete as cache_delete
from app.core.rediscache import get_json as cache_get_json
from app.core.rediscache import set_json as cache_set_json
from app.models.auth import AuthSession, User

AUTH_CACHE_TTL_SECONDS = 30


@dataclass(frozen=True)
class AuthUser:
    """User tối thiểu cho mỗi request đã xác thực (cache Redis 30s)."""

    id: str
    status: str
    deleted_at: str | None
    role_codes: list[str]

    @property
    def role(self) -> str:
        return self.role_codes[0] if self.role_codes else "student"


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
    stmt = select(User).where(func.lower(User.email) == email.lower())
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    return await db.get(User, user_id)


async def get_user_for_auth(db: AsyncSession, user_id: str) -> User | None:
    return await db.get(User, user_id)


async def get_user_for_auth_cached(
    db: AsyncSession, user_id: str
) -> User | AuthUser | None:
    cache_key = f"auth:user:{user_id}"
    # Memory hit trước: tránh 1 Redis GET cho mỗi request đã xác thực.
    memory = _memory_get(cache_key)
    if memory is not None and memory.get("id") == user_id:
        return _auth_user_from_dict(memory)

    cached = await cache_get_json(cache_key)
    if isinstance(cached, dict) and cached.get("id") == user_id:
        # Nạp lại memory để request sau không phải Redis GET lần nữa.
        _memory_set(cache_key, cached)
        return _auth_user_from_dict(cached)

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


async def get_valid_session(
    db: AsyncSession, refresh_token_hash: str
) -> AuthSession | None:
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
    user = User(
        email=email.lower(),
        password_hash=password_hash,
        role="student",
        status="active",
        full_name=full_name,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user
