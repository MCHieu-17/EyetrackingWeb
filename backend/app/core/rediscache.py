"""Primitive tăng/đặt TTL trên Redis (fail-open, không có Redis thì no-op).

Module chỉ cung cấp `increment` và `expire`, dùng cho rate limit. Mọi lỗi kết
nối đều gọi `report_failure()` rồi trả về giá trị "an toàn": `increment` trả
None (caller bỏ qua throttle) và `expire` bỏ qua.
"""

from app.core.config import settings
from app.db.redis import get_redis, report_failure


def _key(key: str) -> str:
    return f"{settings.app_instance_id}:{key}"


async def increment(key: str) -> int | None:
    """INCR. Trả về giá trị mới (Redis tự tạo key=0 rồi +1 nếu chưa tồn tại)."""
    client = await get_redis()
    if client is None:
        return None
    try:
        return int(await client.incr(_key(key)))
    except Exception:  # noqa: BLE001
        report_failure()
        return None


async def expire(key: str, ttl: int) -> None:
    client = await get_redis()
    if client is None:
        return
    try:
        await client.expire(_key(key), ttl)
    except Exception:  # noqa: BLE001
        report_failure()
