"""Dọn dẹp dữ liệu hết hạn.

Module này chỉ xoá auth session đã hết hạn và đánh dấu learning session quá
hạn là ``expired``. Không xoá gaze sample, analysis run hay dữ liệu khoá học.

Chạy thủ công::

    python -m app.maintenance
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import and_, delete, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models.auth import AuthSession
from app.models.gaze import LearningSession


def _utc_now(now: datetime | None) -> datetime:
    """Trả về ``now`` dạng timezone-aware UTC (mặc định là thời điểm hiện tại)."""
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


async def delete_expired_auth_sessions(
    db: AsyncSession, *, now: datetime | None = None
) -> int:
    """Xoá auth session đã hết hạn hoặc đã thu hồi và hết hạn.

    Trả về số dòng đã xoá. Caller chịu trách nhiệm commit.
    """
    cutoff = _utc_now(now)
    # Điều kiện revoked được nêu rõ để phản ánh policy: session đã thu hồi chỉ
    # bị xoá khi cũng đã hết hạn, không xoá session còn hiệu lực.
    condition = or_(
        AuthSession.expires_at < cutoff,
        and_(
            AuthSession.revoked_at.is_not(None),
            AuthSession.expires_at < cutoff,
        ),
    )
    result = await db.execute(delete(AuthSession).where(condition))
    return result.rowcount or 0


async def expire_stale_learning_sessions(
    db: AsyncSession, *, now: datetime | None = None
) -> int:
    """Đánh dấu ``expired`` cho learning session in-progress đã quá hạn.

    Chỉ cập nhật ``status`` và ``ended_at``; không xoá dòng hay dữ liệu gaze.
    Trả về số dòng đã cập nhật. Caller chịu trách nhiệm commit.
    """
    cutoff = _utc_now(now)
    result = await db.execute(
        update(LearningSession)
        .where(
            LearningSession.status == "in_progress",
            LearningSession.expires_at < cutoff,
        )
        .values(status="expired", ended_at=cutoff)
    )
    return result.rowcount or 0


async def run_maintenance() -> dict[str, int]:
    """Chạy toàn bộ maintenance trong một transaction và trả về số liệu."""
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        deleted = await delete_expired_auth_sessions(db, now=now)
        expired = await expire_stale_learning_sessions(db, now=now)
        await db.commit()
    return {
        "auth_sessions_deleted": deleted,
        "learning_sessions_expired": expired,
    }


def main() -> None:
    counts = asyncio.run(run_maintenance())
    print(
        "[maintenance] deleted "
        f"{counts['auth_sessions_deleted']} expired auth session(s)"
    )
    print(
        "[maintenance] expired "
        f"{counts['learning_sessions_expired']} stale learning session(s)"
    )


if __name__ == "__main__":
    main()
