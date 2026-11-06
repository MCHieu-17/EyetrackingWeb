"""Kiểm thử lớp Redis (rate-limit + cache analytics) dùng fakeredis — không cần Redis thật."""

import asyncio

import fakeredis
import pytest
from fastapi import HTTPException

import app.db.redis as rdb
from app.core import rediscache
from app.core.ratelimit import _BUCKETS, _memory_check, rate_limit


class _FakeRequest:
    def __init__(self, ip: str):
        self.headers = {}
        self.client = type("C", (), {"host": ip})()


class _BrokenRedis:
    """Giả lập Redis đã kết nối nhưng mọi thao tác đều raise lỗi kết nối."""

    async def pipeline(self, *a, **k):
        raise ConnectionError("down")

    async def zrange(self, *a, **k):
        raise ConnectionError("down")


def _install_fake_redis():
    fake = fakeredis.FakeAsyncRedis(decode_responses=True)
    rdb._client = fake
    rdb._available = True
    return fake


def _uninstall_redis():
    rdb._client = None
    rdb._available = False


# ---------------------------------------------------------------- rate-limit


def test_memory_rate_limit_sliding_window():
    _BUCKETS.clear()
    ident = "login:1.2.3.4"
    assert _memory_check(ident, 3, 60) == 0
    assert _memory_check(ident, 3, 60) == 0
    assert _memory_check(ident, 3, 60) == 0
    assert _memory_check(ident, 3, 60) > 0  # request thứ 4 bị chặn


def test_redis_rate_limit_block_over_limit():
    _BUCKETS.clear()
    _install_fake_redis()
    try:
        dep = rate_limit(2, 60, "login")
        req = _FakeRequest("5.5.5.5")

        asyncio.run(dep(req))
        asyncio.run(dep(req))

        with pytest.raises(HTTPException) as exc:
            asyncio.run(dep(req))
        assert exc.value.status_code == 429
        assert int(exc.value.headers["Retry-After"]) > 0
    finally:
        _uninstall_redis()


def test_redis_rate_limit_isolates_by_ip():
    _BUCKETS.clear()
    _install_fake_redis()
    try:
        dep = rate_limit(1, 60, "login")
        asyncio.run(dep(_FakeRequest("6.6.6.6")))
        asyncio.run(dep(_FakeRequest("7.7.7.7")))  # IP khác không bị ảnh hưởng
        with pytest.raises(HTTPException):
            asyncio.run(dep(_FakeRequest("6.6.6.6")))
    finally:
        _uninstall_redis()


def test_redis_down_mid_request_falls_back_to_memory():
    _BUCKETS.clear()
    rdb._client = _BrokenRedis()
    rdb._available = True
    try:
        dep = rate_limit(2, 60, "login")
        req = _FakeRequest("9.9.9.9")
        # Redis raise → fallback in-memory, không crash.
        asyncio.run(dep(req))
        asyncio.run(dep(req))
        with pytest.raises(HTTPException):
            asyncio.run(dep(req))
        assert rdb._available is False  # đã đánh dấu mất kết nối
    finally:
        _uninstall_redis()


def test_report_failure_disables_redis_until_reconnect():
    _install_fake_redis()
    try:
        rdb.report_failure()
        assert rdb._available is False
        assert asyncio.run(rdb.get_redis()) is None
    finally:
        _uninstall_redis()


# ------------------------------------------------------------------ cache


def test_redis_cache_json_roundtrip():
    _install_fake_redis()
    try:
        asyncio.run(rediscache.json_set("k1", {"a": 1, "b": [1, 2]}, 60))
        assert asyncio.run(rediscache.json_get("k1")) == {"a": 1, "b": [1, 2]}
    finally:
        _uninstall_redis()


def test_redis_cache_int_and_increment():
    _install_fake_redis()
    try:
        assert asyncio.run(rediscache.get_int("counter")) is None
        assert asyncio.run(rediscache.increment("counter")) == 1
        assert asyncio.run(rediscache.increment("counter")) == 2
        assert asyncio.run(rediscache.get_int("counter")) == 2
    finally:
        _uninstall_redis()


def test_redis_try_acquire_lock():
    _install_fake_redis()
    try:
        assert asyncio.run(rediscache.try_acquire_lock("lock:1", 60)) is True
        assert asyncio.run(rediscache.try_acquire_lock("lock:1", 60)) is False
    finally:
        _uninstall_redis()


def test_fallback_when_redis_absent():
    _uninstall_redis()
    assert rdb._available is False
    assert asyncio.run(rdb.get_redis()) is None
    assert asyncio.run(rediscache.json_get("anything")) is None
    assert asyncio.run(rediscache.get_int("anything")) is None
    assert asyncio.run(rediscache.try_acquire_lock("lock:1", 60)) is True
