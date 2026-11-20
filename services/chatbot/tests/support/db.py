"""SQL helpers cho chatbot tests (PostgreSQL thật)."""

from __future__ import annotations

import uuid
from typing import Any

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from app.settings import database_url


def _conn():
    conn = psycopg.connect(database_url(), row_factory=dict_row, autocommit=True)
    register_vector(conn)
    return conn


def _run(sql: str, params: dict | tuple | None = None):
    with _conn() as conn:
        return conn.execute(sql, params or {})


def execute(sql: str, params: dict | tuple | None = None) -> None:
    _run(sql, params)


def fetch_one(sql: str, params: dict | tuple | None = None) -> dict | None:
    with _conn() as conn:
        return conn.execute(sql, params or {}).fetchone()


def fetch_all(sql: str, params: dict | tuple | None = None) -> list[dict]:
    with _conn() as conn:
        return conn.execute(sql, params or {}).fetchall()


def truncate_all() -> None:
    tables = [
        row["tablename"]
        for row in fetch_all(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
            "AND tablename <> 'schema_migrations' "
            "AND tablename <> 'app_metadata'"
        )
    ]
    if not tables:
        return
    quoted = ", ".join(f'"{name}"' for name in tables)
    execute(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")


def seed_course(
    *,
    published: bool = True,
    slide_transcripts: list[str] | None = None,
    pdf_object_key: str | None = None,
    index_status: str = "ready",
) -> dict[str, Any]:
    teacher_id = str(uuid.uuid4())
    student_id = str(uuid.uuid4())
    course_id = str(uuid.uuid4())
    module_id = str(uuid.uuid4())
    lesson_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    transcripts = slide_transcripts or ["Nội dung alpha", "Nội dung beta"]
    pdf_object_key = pdf_object_key or f"test/{uuid.uuid4().hex}.pdf"

    execute(
        """
        INSERT INTO users (id, email, password_hash, role, full_name)
        VALUES
            (%(teacher)s, %(teacher_email)s, NULL, 'teacher', 'Teacher'),
            (%(student)s, %(student_email)s, NULL, 'student', 'Student')
        """,
        {
            "teacher": teacher_id,
            "teacher_email": f"t-{uuid.uuid4().hex[:8]}@example.com",
            "student": student_id,
            "student_email": f"s-{uuid.uuid4().hex[:8]}@example.com",
        },
    )
    execute(
        """
        INSERT INTO courses
            (id, owner_id, created_by, title, description, status, published_at)
        VALUES
            (%(id)s, %(owner)s, %(owner)s, 'Chatbot Course', 'Mô tả',
             %(status)s,
             CASE WHEN %(published)s THEN now() ELSE NULL END)
        """,
        {
            "id": course_id,
            "owner": teacher_id,
            "status": "published" if published else "draft",
            "published": published,
        },
    )
    execute(
        "INSERT INTO course_modules (id, course_id, title, position) "
        "VALUES (%(id)s, %(course)s, 'Chương 1', 0)",
        {"id": module_id, "course": course_id},
    )
    execute(
        "INSERT INTO media_assets "
        "(id, course_id, storage_backend, object_key, sha256, mime_type, "
        " byte_size, state, page_count, source_format) "
        "VALUES (%(id)s, %(course)s, 'local', %(key)s, %(sha)s, "
        "        'application/pdf', 1, 'ready', %(pages)s, 'pdf')",
        {
            "id": asset_id,
            "course": course_id,
            "key": pdf_object_key,
            "sha": uuid.uuid4().hex + uuid.uuid4().hex,
            "pages": len(transcripts),
        },
    )
    execute(
        """
        INSERT INTO lessons
            (id, module_id, title, kind, position, pdf_asset_id, quiz_config)
        VALUES (%(id)s, %(module)s, 'Bài 1', 'lesson', 0, %(asset)s,
                '{}'::jsonb)
        """,
        {"id": lesson_id, "module": module_id, "asset": asset_id},
    )

    slide_ids = []
    for index, transcript in enumerate(transcripts):
        slide_id = str(uuid.uuid4())
        slide_ids.append(slide_id)
        vector = Vector(FakeVector.for_text(transcript))
        execute(
            """
            INSERT INTO slides
                (id, lesson_id, position, page_number, title, transcript,
                 embedding, index_status, pipeline_version)
            VALUES
                (%(id)s, %(lesson)s, %(position)s, %(page)s, %(title)s,
                 %(transcript)s, %(embedding)s, %(index_status)s, 'rag-v2')
            """,
            {
                "id": slide_id,
                "lesson": lesson_id,
                "position": index,
                "page": index + 1,
                "title": f"Slide {index + 1}",
                "transcript": transcript,
                "embedding": vector,
                "index_status": index_status,
            },
        )
    return {
        "teacher_id": teacher_id,
        "student_id": student_id,
        "course_id": course_id,
        "module_id": module_id,
        "lesson_id": lesson_id,
        "asset_id": asset_id,
        "slide_ids": slide_ids,
    }


class FakeVector:
    @staticmethod
    def for_text(text: str) -> list[float]:
        vector = [0.0] * 1024
        lowered = (text or "").lower()
        if "alpha" in lowered:
            vector[0] = 1.0
        elif "beta" in lowered:
            vector[1] = 1.0
        else:
            vector[2] = 1.0
        return vector
