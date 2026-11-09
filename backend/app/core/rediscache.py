"""Primitive Redis fail-open: rate limit + cache JSON ngắn hạn.

Mọi lỗi kết nối đều gọi `report_failure()` rồi trả về giá trị "an toàn":
`increment` trả None (caller bỏ qua throttle), `get_json` trả None (cache miss),
`set_json`/`delete` bỏ qua. Redis là tăng tốc, không phải nguồn sự thật.
"""

import json
from typing import Any

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


async def get_json(key: str) -> Any | None:
    """Đọc JSON cache; miss/lỗi/không có Redis đều trả None."""
    client = await get_redis()
    if client is None:
        return None
    try:
        raw = await client.get(_key(key))
    except Exception:  # noqa: BLE001
        report_failure()
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


async def set_json(key: str, value: Any, ttl: int) -> None:
    """Ghi JSON cache với TTL giây; lỗi thì bỏ qua (fail-open)."""
    client = await get_redis()
    if client is None:
        return
    try:
        await client.set(_key(key), json.dumps(value, ensure_ascii=False), ex=ttl)
    except Exception:  # noqa: BLE001
        report_failure()


async def delete(key: str) -> None:
    client = await get_redis()
    if client is None:
        return
    try:
        await client.delete(_key(key))
    except Exception:  # noqa: BLE001
        report_failure()
