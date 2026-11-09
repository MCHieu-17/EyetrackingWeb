"""Auth cache: hit không chạm DB, miss ghi cache, invalidate xóa key."""

from __future__ import annotations

import pytest

from app.crud import user as user_crud


@pytest.mark.asyncio
async def test_auth_cache_hit_skips_db(monkeypatch):
    async def fake_get(key: str):
        assert key == "auth:user:u1"
        return {
            "id": "u1",
            "status": "active",
            "deleted_at": None,
            "role_codes": ["student"],
        }

    async def fail_db(*args, **kwargs):
        raise AssertionError("không được query DB khi cache hit")

    monkeypatch.setattr(user_crud, "cache_get_json", fake_get)
    monkeypatch.setattr(user_crud, "get_user_for_auth", fail_db)

    user = await user_crud.get_user_for_auth_cached(None, "u1")

    assert isinstance(user, user_crud.AuthUser)
    assert user.id == "u1"
    assert user.status == "active"
    assert user.deleted_at is None
    assert user.role_codes == ["student"]


@pytest.mark.asyncio
async def test_auth_cache_invalidate(monkeypatch):
    deleted: list[str] = []

    async def fake_delete(key: str):
        deleted.append(key)

    monkeypatch.setattr(user_crud, "cache_delete", fake_delete)

    await user_crud.invalidate_auth_cache("u2")

    assert deleted == ["auth:user:u2"]
