#!/usr/bin/env python3
"""Seed dữ liệu E2E trực tiếp vào DB thật (chạy trong container backend).

  docker compose run --rm -v "$PWD/frontend/e2e:/e2e" backend \
    python /scripts/seed_e2e.py --output /e2e/.fixtures.json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg
from pypdf import PdfWriter

PREFIX = "E2E Seed"
PASSWORD = "Password123!"


def _dsn() -> str:
    url = os.environ["DATABASE_URL"]
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.add_blank_page(width=595, height=842)
    out = __import__("io").BytesIO()
    writer.write(out)
    return out.getvalue()


def _grid(counts: list[tuple[int, int]], value: int) -> list[list[int]]:
    grid = [[0 for _ in range(24)] for _ in range(24)]
    for row, col in counts:
        grid[row][col] = value
    return grid


async def main(output: Path) -> None:
    conn = await asyncpg.connect(_dsn())
    try:
        teacher = await conn.fetchrow(
            "SELECT id FROM users WHERE email = 'teacher@school.edu.vn'"
        )
        student = await conn.fetchrow(
            "SELECT id FROM users WHERE email = 'student@school.edu.vn'"
        )
        if teacher is None or student is None:
            raise SystemExit("Chạy ./scripts/seed_dev.sh trước khi seed E2E")

        await conn.execute(
            "DELETE FROM courses WHERE title LIKE $1 OR title LIKE $2",
            f"{PREFIX}%",
            "E2E Draft%",
        )

        now = datetime.now(timezone.utc)
        course_id = uuid.uuid4()
        module_id = uuid.uuid4()
        lesson_id = uuid.uuid4()
        quiz_id = uuid.uuid4()
        asset_id = uuid.uuid4()
        enrollment_id = uuid.uuid4()
        visit_id = uuid.uuid4()
        session_id = uuid.uuid4()

        pdf = _pdf_bytes()
        media_dir = Path(os.environ.get("MEDIA_DIR", "/app/media")).resolve()
        object_key = f"e2e/{course_id}.pdf"
        target = media_dir / object_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(pdf)

        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO courses
                    (id, owner_id, created_by, title, description, status,
                     published_at, require_calibration, show_gaze_dot)
                VALUES ($1, $2, $2, $3, 'Khóa học cho E2E smoke',
                        'published', now(), false, false)
                """,
                course_id,
                teacher["id"],
                f"{PREFIX} Course",
            )
            await conn.execute(
                "INSERT INTO media_assets "
                "(id, course_id, storage_backend, object_key, sha256, "
                " mime_type, byte_size, state, page_count, source_format) "
                "VALUES ($1, $2, 'local', $3, $4, 'application/pdf', $5, "
                "'ready', 2, 'pdf')",
                asset_id,
                course_id,
                object_key,
                hashlib.sha256(pdf).hexdigest(),
                len(pdf),
            )
            await conn.execute(
                "INSERT INTO course_modules (id, course_id, title, position) "
                "VALUES ($1, $2, 'Chương E2E', 0)",
                module_id,
                course_id,
            )
            await conn.execute(
                """
                INSERT INTO lessons
                    (id, module_id, title, kind, position, pdf_asset_id,
                     quiz_config)
                VALUES ($1, $2, 'Bài giảng E2E', 'lesson', 0, $3, '{}'::jsonb)
                """,
                lesson_id,
                module_id,
                asset_id,
            )
            quiz_config = {
                "instructions": "Chọn đáp án đúng.",
                "durationMinutes": 30,
                "allowRetry": True,
                "allowChatbot": True,
                "status": "published",
                "questions": [
                    {
                        "id": "q1",
                        "prompt": "1 + 1 bằng mấy?",
                        "options": [
                            {"id": "a", "text": "2"},
                            {"id": "b", "text": "3"},
                        ],
                        "correctOptionIds": ["a"],
                        "allowMultiple": False,
                        "explanation": "1 + 1 = 2",
                        "points": 1,
                    }
                ],
            }
            await conn.execute(
                "INSERT INTO lessons "
                "(id, module_id, title, kind, position, quiz_config) "
                "VALUES ($1, $2, 'Bài tập E2E', 'quiz', 1, $3::jsonb)",
                quiz_id,
                module_id,
                json.dumps(quiz_config),
            )
            await conn.execute(
                "INSERT INTO enrollments (id, course_id, student_id, status) "
                "VALUES ($1, $2, $3, 'active')",
                enrollment_id,
                course_id,
                student["id"],
            )

            slide_ids = []
            for index in range(2):
                slide_id = uuid.uuid4()
                slide_ids.append(slide_id)
                await conn.execute(
                    "INSERT INTO slides "
                    "(id, lesson_id, position, page_number, title, transcript, "
                    " index_status) "
                    "VALUES ($1, $2, $3, $4, $5, $6, 'ready')",
                    slide_id,
                    lesson_id,
                    index,
                    index + 1,
                    f"Slide {index + 1}",
                    "alpha là gì E2E smoke",
                )

            await conn.execute(
                "INSERT INTO aois "
                "(id, slide_id, code, name, label, geometry, kind, "
                " is_container, is_active) "
                "VALUES ($1, $2, 'content', 'Nội dung', 'AOI_CONTENT', $3, "
                "'text', false, true)",
                uuid.uuid4(),
                slide_ids[0],
                json.dumps(
                    {"xMin": 0.1, "yMin": 0.1, "xMax": 0.9, "yMax": 0.9}
                ),
            )

            await conn.execute(
                "INSERT INTO course_visits "
                "(id, enrollment_id, started_at, ended_at, last_seen_at, "
                " status) "
                "VALUES ($1, $2, $3, $4, $4, 'ended')",
                visit_id,
                enrollment_id,
                now - timedelta(minutes=3),
                now - timedelta(minutes=1),
            )
            await conn.execute(
                "INSERT INTO learning_sessions "
                "(id, enrollment_id, lesson_id, course_visit_id, status, "
                " started_at, ended_at, expires_at) "
                "VALUES ($1, $2, $3, $4, 'completed', $5, $6, $7)",
                session_id,
                enrollment_id,
                lesson_id,
                visit_id,
                now - timedelta(minutes=3),
                now - timedelta(minutes=1),
                now + timedelta(hours=12),
            )

            view_ids = []
            for index, slide_id in enumerate(slide_ids):
                view_id = uuid.uuid4()
                view_ids.append(view_id)
                grid = _grid([(4 + index, 4), (8, 8 + index)], 5)
                stats = {
                    ("SLIDE_AOI_CONTENT" if index == 0 else "SLIDE_NO_LABEL"): {
                        "ms": 1800 if index == 0 else 1200,
                        "samples": 10,
                    }
                }
                await conn.execute(
                    "INSERT INTO content_views "
                    "(id, session_id, slide_id, surface, sequence_no, "
                    " started_at, ended_at, gaze_count, on_slide_gaze_count, "
                    " tracked_duration_ms, fixation_count, heatmap_grid, "
                    " analysis_status, analysis_version, analyzed_at, "
                    " aoi_stats) "
                    "VALUES ($1, $2, $3, 'lesson', $4, $5, $6, 10, 9, "
                    " $7, 2, $8::jsonb, 'ready', 'gaze-metrics-v8', now(), "
                    " $9::jsonb)",
                    view_id,
                    session_id,
                    slide_id,
                    index,
                    now - timedelta(minutes=3) + timedelta(seconds=index * 20),
                    now - timedelta(minutes=2) + timedelta(seconds=index * 20),
                    1800 if index == 0 else 1200,
                    json.dumps(grid),
                    json.dumps(stats),
                )
                layout_id = uuid.uuid4()
                await conn.execute(
                    "INSERT INTO view_layouts "
                    "(id, content_view_id, layout_no, slide_rect, elements) "
                    "VALUES ($1, $2, 0, $3::jsonb, $4::jsonb)",
                    layout_id,
                    view_id,
                    json.dumps(
                        {"left": 0.1, "top": 0.1, "width": 0.8, "height": 0.8}
                    ),
                    json.dumps(
                        [
                            {
                                "code": "slide",
                                "elementKey": "slide",
                                "xMin": 0.1,
                                "yMin": 0.1,
                                "xMax": 0.9,
                                "yMax": 0.9,
                            }
                        ]
                    ),
                )
                batch_id = uuid.uuid4()
                for sequence in range(10):
                    x = 0.2 + (sequence % 5) * 0.1
                    y = 0.3 + (sequence // 5) * 0.1
                    await conn.execute(
                        "INSERT INTO gaze_samples "
                        "(content_view_id, layout_id, client_batch_id, "
                        " sequence, event_time, viewport_x, viewport_y, "
                        " slide_x, slide_y, aoi_label, status, quality_flags) "
                        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, "
                        "'ok', '{}'::jsonb)",
                        view_id,
                        layout_id,
                        batch_id,
                        sequence,
                        now - timedelta(minutes=3)
                        + timedelta(seconds=index * 20)
                        + timedelta(milliseconds=100 * sequence),
                        x,
                        y,
                        (x - 0.1) / 0.8,
                        (y - 0.1) / 0.8,
                        "SLIDE_AOI_CONTENT"
                        if index == 0
                        else "SLIDE_NO_LABEL",
                    )

            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(
                    {
                        "course_id": str(course_id),
                        "module_id": str(module_id),
                        "lesson_id": str(lesson_id),
                        "quiz_id": str(quiz_id),
                        "enrollment_id": str(enrollment_id),
                        "visit_id": str(visit_id),
                        "slide_ids": [str(item) for item in slide_ids],
                        "view_ids": [str(item) for item in view_ids],
                        "title": f"{PREFIX} Course",
                    },
                    indent=2,
                )
            )
            print(f"[seed_e2e] course={course_id} output={output}")
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/e2e/.fixtures.json"),
    )
    args = parser.parse_args()
    asyncio.run(main(args.output))
