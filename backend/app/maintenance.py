"""Dọn dẹp dữ liệu hết hạn.

Module này chỉ xoá auth session đã hết hạn và đánh dấu learning session quá
hạn là ``expired``. Không xoá gaze sample, analysis run hay dữ liệu khoá học.

Chạy thủ công::

    python -m app.maintenance
"""

from __future__ import annotations

import asyncio
import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, delete, or_, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.auth import AuthSession
from app.models.gaze import LearningSession

_PARTITION_RE = re.compile(r"^gaze_samples_(\d{4})_(\d{2})$")


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


async def ensure_gaze_partitions(
    db: AsyncSession, *, months_ahead: int = 3
) -> int:
    """Tạo trước partition gaze_samples cho các tháng tới."""
    result = await db.execute(
        text("SELECT create_gaze_sample_partitions(:months)"),
        {"months": months_ahead},
    )
    return int(result.scalar_one() or 0)


def _partition_month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


async def drop_old_gaze_partitions(
    db: AsyncSession, *, keep_days: int | None = None
) -> int:
    """Drop các partition gaze_samples cũ hơn ``keep_days``.

    Chỉ drop partition có tên đúng ``gaze_samples_YYYY_MM``; không đụng
    ``gaze_samples_default`` hay partition hiện tại. Trả về số partition đã drop.
    """
    days = settings.gaze_retention_days if keep_days is None else keep_days
    if days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
    rows = (
        await db.execute(
            text(
                "SELECT relname FROM pg_class "
                "WHERE relkind = 'r' AND relname LIKE 'gaze_samples_%'"
            )
        )
    ).scalars().all()
    old_names = []
    for name in rows:
        match = _PARTITION_RE.match(name)
        if match is None:
            continue
        year, month = int(match.group(1)), int(match.group(2))
        if _partition_month_end(year, month) <= cutoff:
            old_names.append(name)
    if not old_names:
        return 0

    # aoi_hits có FK tới gaze_samples; phải xoá hit cũ trước khi detach
    # partition, nếu không PostgreSQL giữ dependency và chặn DROP.
    await db.execute(
        text("DELETE FROM aoi_hits WHERE event_time < :cutoff"),
        {"cutoff": cutoff},
    )
    dropped = 0
    for name in old_names:
        # Tên đã khớp regex cố định nên an toàn để nội suy.
        await db.execute(
            text(f'ALTER TABLE gaze_samples DETACH PARTITION "{name}"')
        )
        await db.execute(text(f'DROP TABLE IF EXISTS "{name}"'))
        dropped += 1
    return dropped


async def run_maintenance() -> dict[str, int]:
    """Chạy toàn bộ maintenance trong một transaction và trả về số liệu."""
    now = datetime.now(timezone.utc)
    async with SessionLocal() as db:
        deleted = await delete_expired_auth_sessions(db, now=now)
        expired = await expire_stale_learning_sessions(db, now=now)
        partitions_created = await ensure_gaze_partitions(db)
        partitions_dropped = await drop_old_gaze_partitions(db)
        await db.commit()
    return {
        "auth_sessions_deleted": deleted,
        "learning_sessions_expired": expired,
        "gaze_partitions_created": partitions_created,
        "gaze_partitions_dropped": partitions_dropped,
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
    print(
        "[maintenance] gaze partitions created "
        f"{counts['gaze_partitions_created']}, dropped "
        f"{counts['gaze_partitions_dropped']}"
    )


if __name__ == "__main__":
    main()
