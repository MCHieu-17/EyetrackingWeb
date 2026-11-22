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


async def get_many_json(keys: list[str]) -> list[Any | None]:
    """Đọc nhiều JSON cache trong một MGET; miss/lỗi đều trả None từng key."""
    if not keys:
        return []
    client = await get_redis()
    if client is None:
        return [None] * len(keys)
    try:
        raws = await client.mget([_key(key) for key in keys])
    except Exception:  # noqa: BLE001
        report_failure()
        return [None] * len(keys)
    out: list[Any | None] = []
    for raw in raws:
        if raw is None:
            out.append(None)
            continue
        try:
            out.append(json.loads(raw))
        except (TypeError, ValueError):
            out.append(None)
    return out


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


async def delete_many(keys: list[str], chunk_size: int = 500) -> None:
    """Xoá nhiều key trong ít RTT: UNLINK theo pipeline, chia lô theo `chunk_size`."""
    if not keys:
        return
    client = await get_redis()
    if client is None:
        return
    try:
        for index in range(0, len(keys), chunk_size):
            chunk = keys[index : index + chunk_size]
            pipe = client.pipeline(transaction=False)
            for key in chunk:
                pipe.unlink(_key(key))
            await pipe.execute()
    except Exception:  # noqa: BLE001
        report_failure()
