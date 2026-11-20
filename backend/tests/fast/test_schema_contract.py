"""Khóa schema generation 13 và các bất biến cascade/unique quan trọng."""

import pytest
from sqlalchemy import text

from app.db.session import engine

pytestmark = [pytest.mark.fast, pytest.mark.db]


async def test_schema_has_24_core_tables():
    async with engine.connect() as conn:
        count = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM pg_tables "
                    "WHERE schemaname = 'public' "
                    "AND tablename <> 'schema_migrations'"
                )
            )
        ).scalar_one()
    assert count == 24


async def test_generation_and_legacy_objects_removed():
    async with engine.connect() as conn:
        generation = (
            await conn.execute(
                text(
                    "SELECT value FROM app_metadata "
                    "WHERE key = 'schema_generation'"
                )
            )
        ).scalar_one()
        tables = set(
            (
                await conn.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname = 'public'"
                    )
                )
            ).scalars()
        )
        gaze_columns = set(
            (
                await conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' "
                        "AND table_name = 'gaze_samples'"
                    )
                )
            ).scalars()
        )
        layout_columns = set(
            (
                await conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' "
                        "AND table_name = 'view_layouts'"
                    )
                )
            ).scalars()
        )

    assert generation == "13"
    assert "email_otps" in tables
    assert "oauth_accounts" not in tables
    assert "aoi_codes" not in tables
    assert "original_viewport_x" not in gaze_columns
    assert "original_viewport_y" not in gaze_columns
    assert "coordinate_space" not in layout_columns
    assert "visible_rect" not in layout_columns


async def test_internal_metrics_currently_public(client):
    # Khóa hành vi hiện tại; nginx chặn /internal/ từ ngoài.
    response = await client.get("/internal/metrics")
    assert response.status_code == 200
    body = response.json()
    assert "db_pool" in body
    assert "queues" in body
    assert body["redis"]["ok"] is True
