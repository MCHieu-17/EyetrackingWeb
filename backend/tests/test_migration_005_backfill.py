"""Kiểm tra migration 005 quy đổi layout original-v1 sang viewport hiện tại."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal, engine
from app.models.gaze import ContentView, LearningSession
from tests.conftest import create_user, seed_course, seed_slide

_MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "db"
    / "migrations"
    / "005_current_viewport_only.sql"
)


def _do_block() -> str:
    sql = _MIGRATION.read_text()
    start = sql.index("DO $$")
    end = sql.index("END $$;", start) + len("END $$;")
    return sql[start:end]


@pytest.mark.asyncio
async def test_migration_005_backfills_original_v1_layout():
    teacher_id = await create_user(
        email=f"mig005-t-{uuid.uuid4().hex[:8]}@example.com", role="teacher"
    )
    student_id = await create_user(
        email=f"mig005-s-{uuid.uuid4().hex[:8]}@example.com"
    )
    ids = await seed_course(teacher_id=teacher_id, student_id=student_id)
    await seed_slide(
        course_id=ids["course_id"],
        lesson_id=ids["lesson_id"],
        teacher_id=teacher_id,
    )
    now = datetime.now(timezone.utc)

    async with SessionLocal() as db:
        session = LearningSession(
            enrollment_id=ids["enrollment_id"],
            lesson_id=ids["lesson_id"],
            expires_at=now + timedelta(hours=1),
        )
        db.add(session)
        await db.flush()
        view = ContentView(
            session_id=session.id,
            slide_id=None,
            surface="quiz",
            sequence_no=0,
        )
        db.add(view)
        await db.commit()
        view_id = view.id

    async with engine.connect() as conn:
        transaction = await conn.begin()
        # Tạm dựng lại shape cũ trong transaction rồi rollback.
        await conn.execute(
            text(
                "ALTER TABLE view_layouts "
                "ADD COLUMN coordinate_space VARCHAR(16) NOT NULL "
                "DEFAULT 'current-v1'"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE view_layouts "
                "ADD COLUMN visible_rect JSONB NOT NULL DEFAULT '{}'::jsonb"
            )
        )
        # ORM không còn map hai cột cũ; ghi bằng SQL thô.
        result = await conn.execute(
            text(
                "INSERT INTO view_layouts "
                "(content_view_id, layout_no, coordinate_space, visible_rect, "
                " slide_rect, elements) "
                "VALUES (:view_id, 0, 'original-v1', "
                "        CAST(:visible AS jsonb), CAST(:slide AS jsonb), "
                "        CAST(:elements AS jsonb)) "
                "RETURNING id"
            ),
            {
                "view_id": view_id,
                "visible": (
                    '{"left": 0.1, "top": 0.2, "width": 0.5, "height": 0.4}'
                ),
                "slide": '{"left": 0.2, "top": 0.2, "width": 0.4, "height": 0.4}',
                "elements": (
                    '[{"code": "header", "xMin": 0.1, "yMin": 0.2, '
                    '"xMax": 0.6, "yMax": 0.6}]'
                ),
            },
        )
        layout_id = result.scalar_one()

        await conn.execute(text(_do_block()))

        row = (
            await conn.execute(
                text(
                    "SELECT coordinate_space, visible_rect, slide_rect, elements "
                    "FROM view_layouts WHERE id = :id"
                ),
                {"id": layout_id},
            )
        ).mappings().one()
        assert row["coordinate_space"] == "current-v1"
        assert row["visible_rect"] == {}
        slide = row["slide_rect"]
        assert slide["left"] == pytest.approx(0.2)
        assert slide["top"] == pytest.approx(0.0)
        assert slide["width"] == pytest.approx(0.8)
        assert slide["height"] == pytest.approx(1.0)
        element = row["elements"][0]
        assert element["code"] == "header"
        assert element["xMin"] == pytest.approx(0.0)
        assert element["yMin"] == pytest.approx(0.0)
        assert element["xMax"] == pytest.approx(1.0)
        assert element["yMax"] == pytest.approx(1.0)

        # Rollback để trả schema test về trạng thái sau migration 005.
        await transaction.rollback()
