#!/usr/bin/env python3
"""Seed dataset benchmark deterministic vào database `*_bench`.

Chạy trong image backend (có asyncpg):
    docker compose ... exec -T backend \
      python /bench/lib/seed_bench.py --scale tiny \
      --out /bench/baseline/<run>/fixtures.json

Nguyên tắc:
- Chỉ xoá dữ liệu prefix `BENCH:` và email `bench-*@example.test`.
- UUID sinh bằng uuid5, thời gian cố định, random seed cố định.
- Không chứa token/cookie trong output.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg

PREFIX = "BENCH:"
EMAIL_DOMAIN = "example.test"
PASSWORD_HASH = "$2b$12$1q/iiUi4DF25DxUvlvyt5uUDwDBsEpGbTj5SqkEudV9QZCQhwYDoq"
BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
RNG = random.Random(20261121)
NAMESPACE = uuid.UUID("7d7a3e57-6d8f-4f6a-9f1b-3c2d1e0f9a8b")


def uid(key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, key)


def dsn_from_env() -> str:
    raw = os.environ.get("DATABASE_URL", "")
    if not raw:
        raise SystemExit("Thiếu DATABASE_URL hoặc --dsn")
    return raw.replace("postgresql+asyncpg://", "postgresql://", 1)


def scale_config(scale: str) -> dict:
    base = {
        "students": 200,
        "core_students": 100,
        "core_visits": 160,
        "bulk_courses": 3,
        "bulk_visits": 160,
        "sessions_per_visit": 3,
        "views_per_session": 20,
        "samples_per_view": 180,
        "chat_students": 20,
        "chat_sessions_per_student": 10,
        "quiz_attempts": 1000,
        "calibrations": 100,
        "jobs": 100,
        "gaze_targets": 100,
    }
    if scale == "tiny":
        base.update(
            students=16,
            core_students=8,
            core_visits=8,
            bulk_courses=1,
            bulk_visits=8,
            sessions_per_visit=2,
            views_per_session=5,
            samples_per_view=20,
            chat_students=4,
            chat_sessions_per_student=3,
            quiz_attempts=40,
            calibrations=8,
            jobs=10,
            gaze_targets=8,
        )
    elif scale == "stress":
        base.update(
            students=600,
            core_students=300,
            core_visits=480,
            bulk_visits=480,
            samples_per_view=240,
            quiz_attempts=3000,
            calibrations=300,
            jobs=300,
            gaze_targets=300,
        )
    elif scale != "baseline":
        raise SystemExit(f"Scale không hợp lệ: {scale}")
    return base


def vector_text(topic: int, salt: int) -> str:
    """Vector 1024 chiều deterministic, có cluster theo topic."""
    values: list[float] = []
    for i in range(1024):
        centroid = math.sin((topic + 1) * (i + 1) * 0.017)
        noise = math.sin((salt + 1) * (i + 1) * 0.031) * 0.25
        values.append(centroid + noise)
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return "[" + ",".join(f"{v / norm:.6f}" for v in values) + "]"


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def quiz_config(lesson_no: int) -> dict:
    questions = []
    for i in range(10):
        questions.append(
            {
                "id": f"q{i + 1}",
                "prompt": f"Question {i + 1} for quiz {lesson_no}?",
                "options": [
                    {"id": "a", "text": "Option A"},
                    {"id": "b", "text": "Option B"},
                    {"id": "c", "text": "Option C"},
                ],
                "correctOptionIds": ["a"],
                "allowMultiple": False,
                "explanation": "Benchmark explanation.",
                "points": 1,
            }
        )
    return {
        "instructions": "Benchmark quiz.",
        "durationMinutes": 30,
        "allowRetry": True,
        "allowChatbot": True,
        "status": "published",
        "questions": questions,
    }


def heatmap_grid(seed: int) -> list[list[int]]:
    grid = [[0 for _ in range(24)] for _ in range(24)]
    for k in range(4):
        grid[(seed + k * 5) % 24][(seed * 3 + k * 7) % 24] = 5 + k
    return grid


class Seeder:
    def __init__(self, conn: asyncpg.Connection, cfg: dict):
        self.conn = conn
        self.cfg = cfg
        self.teacher_id = uid("user:teacher")
        self.admin_id = uid("user:admin")
        self.student_ids = [uid(f"user:student:{i:04d}") for i in range(cfg["students"])]
        self.courses: dict[str, dict] = {}
        self.lesson_ids: list[uuid.UUID] = []
        self.lecture_lesson_ids: list[uuid.UUID] = []
        self.quiz_lesson_ids: list[uuid.UUID] = []
        self.slide_ids: list[uuid.UUID] = []
        self.course_slide_ids: dict[str, list[uuid.UUID]] = {}
        self.course_lecture_lesson_ids: dict[str, list[uuid.UUID]] = {}
        self.ingest_lesson_id: uuid.UUID | None = None
        self.ingest_slide_ids: list[uuid.UUID] = []
        self.enrollments: dict[tuple[uuid.UUID, uuid.UUID], uuid.UUID] = {}

    async def execute(self, sql: str, *args):
        return await self.conn.execute(sql, *args)

    async def many(self, sql: str, rows: list[tuple]):
        if rows:
            await self.conn.executemany(sql, rows)

    async def seed_users(self, media_pdf: Path):
        users = [
            (
                self.admin_id,
                f"bench-admin@{EMAIL_DOMAIN}",
                PASSWORD_HASH,
                "admin",
                "active",
                "Bench Admin",
                "other",
                BASE,
                BASE,
            ),
            (
                self.teacher_id,
                f"bench-teacher@{EMAIL_DOMAIN}",
                PASSWORD_HASH,
                "teacher",
                "active",
                "Bench Teacher",
                "female",
                BASE,
                BASE,
            ),
        ]
        for i, sid in enumerate(self.student_ids):
            users.append(
                (
                    sid,
                    f"bench-student-{i + 1:04d}@{EMAIL_DOMAIN}",
                    PASSWORD_HASH if i < 5 else None,
                    "student",
                    "active",
                    f"Bench Student {i + 1:04d}",
                    "other",
                    BASE,
                    BASE,
                )
            )
        await self.many(
            """
            INSERT INTO users
              (id, email, password_hash, role, status, full_name, gender,
               email_verified_at, created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$8,$9)
            """,
            users,
        )
        await self.execute(
            "INSERT INTO teacher_profiles (user_id, teacher_code, department) VALUES ($1,$2,$3)",
            self.teacher_id,
            "BENCH-T01",
            "Benchmark",
        )
        await self.many(
            "INSERT INTO student_profiles (user_id, student_code, program) VALUES ($1,$2,$3)",
            [
                (sid, f"BENCH-S{i + 1:05d}", "Benchmark Program")
                for i, sid in enumerate(self.student_ids)
            ],
        )
        # PDF dùng chung cho mọi course; ghi vào MEDIA_DIR để /media phục vụ.
        media_dir = Path(os.environ.get("MEDIA_DIR", "/app/media")).resolve()
        media_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_bytes = media_pdf.read_bytes()
        self.pdf_sha = hashlib.sha256(self.pdf_bytes).hexdigest()
        self.media_dir = media_dir
        return self.pdf_bytes

    async def seed_courses(self):
        specs = [
            ("core", f"{PREFIX} Core Course", "published", True),
            ("ingest", f"{PREFIX} Ingest", "draft", False),
            ("draft", f"{PREFIX} Draft Publish", "draft", False),
        ]
        for i in range(1, self.cfg["bulk_courses"] + 1):
            specs.append((f"bulk{i}", f"{PREFIX} Bulk {i}", "published", True))

        course_rows = []
        assets = []
        for key, title, status, _published in specs:
            cid = uid(f"course:{key}")
            published_at = BASE if status == "published" else None
            course_rows.append(
                (
                    cid,
                    self.teacher_id,
                    self.teacher_id,
                    title,
                    "Synthetic benchmark dataset",
                    status,
                    published_at,
                    False,
                    False,
                )
            )
            object_key = f"bench/{cid}.pdf"
            target = self.media_dir / object_key
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.pdf_bytes)
            assets.append(
                (
                    uid(f"asset:{key}"),
                    cid,
                    "local",
                    object_key,
                    self.pdf_sha,
                    "application/pdf",
                    len(self.pdf_bytes),
                    "ready",
                    20,
                    "pdf",
                )
            )
            self.courses[key] = {
                "id": cid,
                "title": title,
                "status": status,
                "asset_id": uid(f"asset:{key}"),
            }
        await self.many(
            """
            INSERT INTO courses
              (id, owner_id, created_by, title, description, status, published_at,
               show_gaze_dot, require_calibration)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            """,
            course_rows,
        )
        await self.many(
            """
            INSERT INTO media_assets
              (id, course_id, storage_backend, object_key, sha256, mime_type,
               byte_size, state, page_count, source_format)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            """,
            assets,
        )
        for key in self.courses:
            await self.execute(
                "INSERT INTO course_teachers (course_id, teacher_id) VALUES ($1,$2)",
                self.courses[key]["id"],
                self.teacher_id,
            )

    async def _insert_lesson(
        self,
        *,
        course_key: str,
        module_id: uuid.UUID,
        position: int,
        title: str,
        kind: str,
        slide_count: int,
        pending: bool = False,
        quiz_no: int = 1,
    ) -> uuid.UUID:
        lesson_id = uid(f"lesson:{course_key}:{module_id}:{position}")
        course = self.courses[course_key]
        pdf_asset_id = course["asset_id"] if kind == "lesson" else None
        config = quiz_config(quiz_no) if kind == "quiz" else {}
        await self.execute(
            """
            INSERT INTO lessons
              (id, module_id, title, kind, position, pdf_asset_id, quiz_config,
               created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$8)
            """,
            lesson_id,
            module_id,
            title,
            kind,
            position,
            pdf_asset_id,
            json_text(config),
            BASE,
        )
        self.lesson_ids.append(lesson_id)
        if kind == "quiz":
            self.quiz_lesson_ids.append(lesson_id)
            return lesson_id
        self.lecture_lesson_ids.append(lesson_id)
        self.course_slide_ids.setdefault(course_key, [])
        self.course_lecture_lesson_ids.setdefault(course_key, []).append(lesson_id)
        if course_key == "ingest":
            self.ingest_lesson_id = lesson_id

        slides = []
        for slide_pos in range(slide_count):
            slide_id = uid(f"slide:{lesson_id}:{slide_pos}")
            topic = (slide_pos + position) % 10
            transcript = (
                f"Benchmark slide {slide_pos + 1} for {title}. "
                "Machine learning, regression, embedding and vector search."
            )
            indexing = "pending" if pending else "ready"
            slides.append(
                (
                    slide_id,
                    lesson_id,
                    slide_pos,
                    slide_pos + 1,
                    f"{title} - slide {slide_pos + 1}",
                    transcript,
                    indexing,
                    "rag-v2",
                    "bench",
                )
            )
            self.slide_ids.append(slide_id)
            self.course_slide_ids[course_key].append(slide_id)
            if course_key == "ingest":
                self.ingest_slide_ids.append(slide_id)
        # Vector phải cast riêng; dùng UPDATE để tránh asyncpg binary codec.
        await self.many(
            """
            INSERT INTO slides
              (id, lesson_id, position, page_number, title, transcript,
               index_status, pipeline_version, model_version)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            """,
            slides,
        )
        if not pending:
            for slide_id, lesson_id, slide_pos, *_ in slides:
                topic = (slide_pos + position) % 10
                await self.execute(
                    "UPDATE slides SET embedding = $1::vector WHERE id = $2",
                    vector_text(topic, slide_pos + position),
                    slide_id,
                )
        return lesson_id

    async def seed_content(self):
        for key, course in self.courses.items():
            if key == "core":
                modules, lessons_per, slides_per, quiz_last = 4, 6, 6, True
            elif key == "ingest":
                modules, lessons_per, slides_per, quiz_last = (
                    1,
                    1,
                    int(self.cfg.get("ingest_slides", 20)),
                    False,
                )
            else:
                modules, lessons_per, slides_per, quiz_last = 4, 5, 5, False
            for m in range(modules):
                module_id = uid(f"module:{key}:{m}")
                await self.execute(
                    """
                    INSERT INTO course_modules
                      (id, course_id, title, position, created_at, updated_at)
                    VALUES ($1,$2,$3,$4,$5,$5)
                    """,
                    module_id,
                    course["id"],
                    f"Module {m + 1}",
                    m,
                    BASE,
                )
                for lesson_pos in range(lessons_per):
                    kind = "quiz" if quiz_last and lesson_pos == lessons_per - 1 else "lesson"
                    title = (
                        f"Quiz {m + 1}.{lesson_pos + 1}"
                        if kind == "quiz"
                        else f"Lesson {m + 1}.{lesson_pos + 1}"
                    )
                    await self._insert_lesson(
                        course_key=key,
                        module_id=module_id,
                        position=lesson_pos,
                        title=title,
                        kind=kind,
                        slide_count=0 if kind == "quiz" else slides_per,
                        pending=(key == "ingest"),
                        quiz_no=m * lessons_per + lesson_pos + 1,
                    )

        # AOI cho core slides.
        aoi_rows = []
        for slide_id in self.course_slide_ids.get("core", []):
            aoi_rows.append(
                (
                    uid(f"aoi:{slide_id}:1"),
                    slide_id,
                    None,
                    "content_1",
                    "Vung 1",
                    "AOI_1",
                    None,
                    json_text({"xMin": 0.1, "yMin": 0.1, "xMax": 0.48, "yMax": 0.48}),
                    False,
                    "text",
                    True,
                )
            )
            aoi_rows.append(
                (
                    uid(f"aoi:{slide_id}:2"),
                    slide_id,
                    None,
                    "content_2",
                    "Vung 2",
                    "AOI_2",
                    None,
                    json_text({"xMin": 0.52, "yMin": 0.52, "xMax": 0.9, "yMax": 0.9}),
                    False,
                    "custom",
                    True,
                )
            )
        for i, (code, name, selector) in enumerate(
            [
                ("reader_sidebar", "Thanh ben", ".reader-sidebar"),
                ("reader_toolbar", "Thanh cong cu", ".reader-toolbar"),
                ("reader_chat", "Khung chat", ".reader-chat"),
            ]
        ):
            aoi_rows.append(
                (
                    uid(f"aoi:ui:{code}"),
                    None,
                    "reader-v1",
                    code,
                    name,
                    None,
                    None,
                    json_text({"selector": selector}),
                    False,
                    "ui",
                    True,
                )
            )
        await self.many(
            """
            INSERT INTO aois
              (id, slide_id, ui_schema, code, name, label, parent_id, geometry,
               is_container, kind, is_active)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$11)
            """,
            aoi_rows,
        )

    async def seed_enrollments(self):
        rows = []
        core_students = self.student_ids[: self.cfg["core_students"]]
        bulk_keys = [k for k in self.courses if k.startswith("bulk")]
        for student_id in core_students:
            eid = uid(f"enrollment:core:{student_id}")
            rows.append((eid, self.courses["core"]["id"], student_id, BASE, "active"))
            self.enrollments[(self.courses["core"]["id"], student_id)] = eid
        for key in bulk_keys:
            for student_id in self.student_ids[: self.cfg["core_students"]]:
                eid = uid(f"enrollment:{key}:{student_id}")
                rows.append((eid, self.courses[key]["id"], student_id, BASE, "active"))
                self.enrollments[(self.courses[key]["id"], student_id)] = eid
        await self.many(
            "INSERT INTO enrollments (id, course_id, student_id, enrolled_at, status) "
            "VALUES ($1,$2,$3,$4,$5)",
            rows,
        )

    async def seed_analytics(self):
        core = self.courses["core"]
        core_students = self.student_ids[: self.cfg["core_students"]]
        core_slides = self.course_slide_ids.get("core", [])
        await self._seed_course_analytics(
            course=core,
            students=core_students,
            visits=self.cfg["core_visits"],
            slide_pool=core_slides or self.slide_ids[:1],
            lesson_pool=self.course_lecture_lesson_ids.get("core", []),
            key_prefix="core",
            make_layout_for_first_visit=True,
        )
        bulk_keys = [k for k in self.courses if k.startswith("bulk")]
        for key in bulk_keys:
            await self._seed_course_analytics(
                course=self.courses[key],
                students=core_students,
                visits=max(1, self.cfg["bulk_visits"] // max(1, len(bulk_keys))),
                slide_pool=self.course_slide_ids.get(key, []),
                lesson_pool=self.course_lecture_lesson_ids.get(key, []),
                key_prefix=key,
                make_layout_for_first_visit=False,
            )

    async def _seed_course_analytics(
        self,
        *,
        course: dict,
        students: list[uuid.UUID],
        visits: int,
        slide_pool: list[uuid.UUID],
        lesson_pool: list[uuid.UUID],
        key_prefix: str,
        make_layout_for_first_visit: bool,
    ):
        cfg = self.cfg
        visit_rows = []
        session_rows = []
        view_rows = []
        layout_rows = []
        view_meta = []
        base = BASE + timedelta(days=1)

        for v in range(visits):
            sid_user = students[v % len(students)]
            eid = self.enrollments.get((course["id"], sid_user))
            if eid is None:
                continue
            visit_id = uid(f"visit:{key_prefix}:{v}")
            started = base + timedelta(hours=v)
            ended = started + timedelta(hours=2)
            visit_rows.append(
                (visit_id, eid, started, ended, ended, "ended", f"bench-{key_prefix}-{v}")
            )
            for s in range(cfg["sessions_per_visit"]):
                session_id = uid(f"session:{key_prefix}:{v}:{s}")
                lesson_id = lesson_pool[(v + s) % max(1, len(lesson_pool))]
                s_started = started + timedelta(minutes=s * 20)
                s_ended = s_started + timedelta(minutes=18)
                session_rows.append(
                    (
                        session_id,
                        eid,
                        lesson_id,
                        visit_id,
                        None,
                        None,
                        "gaze-v1",
                        1920,
                        1080,
                        1920,
                        1080,
                        1.0,
                        True,
                        "completed",
                        s_started,
                        s_ended,
                        s_ended + timedelta(hours=12),
                    )
                )
                for j in range(cfg["views_per_session"]):
                    view_id = uid(f"view:{key_prefix}:{v}:{s}:{j}")
                    started_view = s_started + timedelta(seconds=j * 20)
                    ended_view = started_view + timedelta(seconds=12)
                    slide_id = slide_pool[(v + s + j) % max(1, len(slide_pool))]
                    samples = cfg["samples_per_view"]
                    tracked = max(0, (samples - 1) * 66)
                    label_a = "SLIDE_AOI_1" if key_prefix == "core" else "SLIDE_NO_LABEL"
                    label_b = "SLIDE_AOI_2" if key_prefix == "core" else "SLIDE_NO_LABEL"
                    stats = {
                        label_a: {"ms": tracked // 2, "samples": samples // 2},
                        label_b: {"ms": tracked // 3, "samples": samples // 3},
                        "SLIDE_NO_LABEL": {
                            "ms": max(0, tracked - tracked // 2 - tracked // 3),
                            "samples": max(0, samples - samples // 2 - samples // 3),
                        },
                    }
                    layout_id = None
                    if make_layout_for_first_visit and v == 0:
                        layout_id = uid(f"layout:{key_prefix}:{v}:{s}:{j}")
                        layout_rows.append(
                            (
                                layout_id,
                                view_id,
                                0,
                                json_text({"left": 0.1, "top": 0.1, "width": 0.8, "height": 0.8}),
                                json_text(
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
                                started_view,
                            )
                        )
                    view_rows.append(
                        (
                            view_id,
                            session_id,
                            slide_id,
                            "lesson",
                            j,
                            started_view,
                            ended_view,
                            samples,
                            int(samples * 0.9),
                            tracked,
                            max(1, samples // 4),
                            json_text(heatmap_grid(v + s + j)),
                            json_text(stats),
                            "ready",
                            "gaze-metrics-v8",
                            ended_view,
                        )
                    )
                    view_meta.append((view_id, layout_id, samples, started_view, label_a, label_b))

        await self.many(
            """
            INSERT INTO course_visits
              (id, enrollment_id, started_at, ended_at, last_seen_at, status, visit_key)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            ON CONFLICT DO NOTHING
            """,
            visit_rows,
        )
        await self.many(
            """
            INSERT INTO learning_sessions
              (id, enrollment_id, lesson_id, course_visit_id, quiz_attempt_id,
               calibration_id, pipeline_version, viewport_width_px, viewport_height_px,
               calibration_width_px, calibration_height_px, device_pixel_ratio,
               tracking_consent, status, started_at, ended_at, expires_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
            """,
            session_rows,
        )
        await self.many(
            """
            INSERT INTO content_views
              (id, session_id, slide_id, surface, sequence_no, started_at, ended_at,
               gaze_count, on_slide_gaze_count, tracked_duration_ms, fixation_count,
               heatmap_grid, aoi_stats, analysis_status, analysis_version, analyzed_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb,$13::jsonb,$14,$15,$16)
            """,
            view_rows,
        )
        await self.many(
            """
            INSERT INTO view_layouts
              (id, content_view_id, layout_no, slide_rect, elements, captured_at)
            VALUES ($1,$2,$3,$4::jsonb,$5::jsonb,$6)
            """,
            layout_rows,
        )

        # Copy gaze samples theo batch để tránh giữ 3M tuple trong RAM.
        columns = [
            "content_view_id",
            "layout_id",
            "client_batch_id",
            "sequence",
            "event_time",
            "viewport_x",
            "viewport_y",
            "slide_x",
            "slide_y",
            "aoi_label",
            "status",
        ]
        batch: list[tuple] = []
        for view_id, layout_id, samples, started_view, label_a, label_b in view_meta:
            batch_id = uid(f"batch:{view_id}")
            for seq in range(samples):
                x = 0.2 + ((seq * 7) % 50) / 100.0
                y = 0.2 + ((seq * 11) % 50) / 100.0
                label = label_a if seq % 3 == 0 else label_b
                batch.append(
                    (
                        view_id,
                        layout_id,
                        batch_id,
                        seq,
                        started_view + timedelta(milliseconds=66 * seq),
                        x,
                        y,
                        x,
                        y,
                        label,
                        "ok",
                    )
                )
                if len(batch) >= 50_000:
                    await self.conn.copy_records_to_table(
                        "gaze_samples", records=batch, columns=columns
                    )
                    batch.clear()
        if batch:
            await self.conn.copy_records_to_table("gaze_samples", records=batch, columns=columns)

    async def seed_gaze_targets(self):
        """Session/view đang mở để k6 gửi gaze-batches."""
        core = self.courses["core"]
        core_slides = self.course_slide_ids.get("core", []) or self.slide_ids[:1]
        now = datetime.now(timezone.utc)
        targets = []
        for i, student_id in enumerate(self.student_ids[: self.cfg["gaze_targets"]]):
            eid = self.enrollments.get((core["id"], student_id))
            if eid is None:
                continue
            visit_id = uid(f"gaze-visit:{i}")
            session_id = uid(f"gaze-session:{i}")
            view_id = uid(f"gaze-view:{i}")
            layout_id = uid(f"gaze-layout:{i}")
            await self.execute(
                """
                INSERT INTO course_visits
                  (id, enrollment_id, started_at, last_seen_at, status, visit_key)
                VALUES ($1,$2,$3,$3,'active',$4)
                ON CONFLICT DO NOTHING
                """,
                visit_id,
                eid,
                now,
                f"gaze-bench-{i}",
            )
            await self.execute(
                """
                INSERT INTO learning_sessions
                  (id, enrollment_id, lesson_id, course_visit_id, pipeline_version,
                   viewport_width_px, viewport_height_px, calibration_width_px,
                   calibration_height_px, device_pixel_ratio, tracking_consent,
                   status, started_at, expires_at)
                VALUES ($1,$2,$3,$4,'gaze-v1',1920,1080,1920,1080,1.0,true,
                        'in_progress',$5,$6)
                """,
                session_id,
                eid,
                self.course_lecture_lesson_ids["core"][
                    i % len(self.course_lecture_lesson_ids["core"])
                ],
                visit_id,
                now,
                now + timedelta(days=1),
            )
            await self.execute(
                """
                INSERT INTO content_views
                  (id, session_id, slide_id, surface, sequence_no, started_at)
                VALUES ($1,$2,$3,'lesson',0,$4)
                """,
                view_id,
                session_id,
                core_slides[i % len(core_slides)],
                now,
            )
            await self.execute(
                """
                INSERT INTO view_layouts
                  (id, content_view_id, layout_no, slide_rect, elements, captured_at)
                VALUES ($1,$2,0,$3::jsonb,$4::jsonb,$5)
                """,
                layout_id,
                view_id,
                json_text({"left": 0.1, "top": 0.1, "width": 0.8, "height": 0.8}),
                json_text(
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
                now,
            )
            targets.append(
                {
                    "token_index": i,
                    "session_id": str(session_id),
                    "presentation_id": str(view_id),
                    "layout_id": str(layout_id),
                    "slide_id": str(core_slides[i % len(core_slides)]),
                }
            )
        return targets

    async def seed_chat(self):
        core = self.courses["core"]
        rows_sessions = []
        rows_messages = []
        for i, student_id in enumerate(self.student_ids[: self.cfg["chat_students"]]):
            for j in range(self.cfg["chat_sessions_per_student"]):
                session_id = uid(f"chat-session:{i}:{j}")
                created = BASE + timedelta(days=2, minutes=i * 10 + j)
                rows_sessions.append(
                    (
                        session_id,
                        student_id,
                        core["id"],
                        self.course_lecture_lesson_ids["core"][
                            j % len(self.course_lecture_lesson_ids["core"])
                        ],
                        None,
                        f"Benchmark session {i}-{j}",
                        f"lesson:{self.course_lecture_lesson_ids['core'][j % len(self.course_lecture_lesson_ids['core'])]}:attempt:none:",
                        created,
                        created,
                        None,
                    )
                )
                for k in range(10):
                    rows_messages.append(
                        (
                            uid(f"chat-message:{i}:{j}:{k}"),
                            session_id,
                            "student" if k % 2 == 0 else "assistant",
                            f"Benchmark message {k}: explain machine learning.",
                            "[]",
                            "course_qa",
                            created + timedelta(seconds=k * 10),
                        )
                    )
        await self.many(
            """
            INSERT INTO chat_sessions
              (id, student_id, course_id, lesson_id, quiz_attempt_id, title,
               context_key, created_at, updated_at, archived_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            """,
            rows_sessions,
        )
        await self.many(
            """
            INSERT INTO chat_messages
              (id, session_id, role, content, citations, intent, created_at)
            VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7)
            """,
            rows_messages,
        )

    async def seed_quizzes(self):
        core = self.courses["core"]
        quiz_lessons = self.quiz_lesson_ids[:4]
        if not quiz_lessons:
            return
        rows = []
        count = 0
        students = self.student_ids[: self.cfg["core_students"]]
        attempt_no = 1
        while count < self.cfg["quiz_attempts"] and attempt_no <= 10:
            for student_id in students:
                eid = self.enrollments.get((core["id"], student_id))
                if eid is None:
                    continue
                for lesson_id in quiz_lessons:
                    if count >= self.cfg["quiz_attempts"]:
                        break
                    rows.append(
                        (
                            uid(f"quiz-attempt:{eid}:{lesson_id}:{attempt_no}"),
                            eid,
                            lesson_id,
                            attempt_no,
                            "submitted",
                            BASE + timedelta(days=3, minutes=count),
                            BASE + timedelta(days=3, hours=1),
                            BASE + timedelta(days=3, minutes=count + 30),
                            json_text(quiz_config(attempt_no)),
                            "{}",
                            "{}",
                            5.0,
                            10.0,
                        )
                    )
                    count += 1
            attempt_no += 1
        await self.many(
            """
            INSERT INTO quiz_attempts
              (id, enrollment_id, lesson_id, attempt_no, status, started_at,
               expires_at, submitted_at, quiz_snapshot, answers, grading, score,
               max_score)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10::jsonb,$11::jsonb,$12,$13)
            """,
            rows,
        )

    async def seed_calibrations(self):
        rows = []
        for i, student_id in enumerate(self.student_ids[: self.cfg["calibrations"]]):
            model = b"BENCH-CALIB"
            rows.append(
                (
                    uid(f"calibration:{i}"),
                    student_id,
                    "bench-device",
                    model,
                    hashlib.sha256(model).hexdigest(),
                    "bench",
                    1920,
                    1080,
                    1.0,
                    0,
                    0,
                    25,
                    BASE,
                )
            )
        await self.many(
            """
            INSERT INTO gaze_calibrations
              (id, user_id, device_fingerprint, model_ubj, model_hash,
               model_version, viewport_width_px, viewport_height_px,
               device_pixel_ratio, screen_x_px, screen_y_px, num_points, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            """,
            rows,
        )

    async def seed_jobs(self):
        rows = []
        for i in range(self.cfg["jobs"]):
            lesson_id = self.lesson_ids[i % len(self.lesson_ids)]
            rows.append(
                (
                    uid(f"job:{i}"),
                    lesson_id,
                    "analyze_lesson",
                    "ready",
                    "{}",
                    1,
                    3,
                    None,
                    BASE + timedelta(days=4, minutes=i),
                    BASE + timedelta(days=4, minutes=i + 1),
                    BASE + timedelta(days=4, minutes=i + 2),
                    BASE + timedelta(days=4, minutes=i + 2),
                )
            )
        await self.many(
            """
            INSERT INTO background_jobs
              (id, lesson_id, kind, status, payload, attempts, max_attempts,
               error, created_at, started_at, finished_at, updated_at)
            VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7,$8,$9,$10,$11,$12)
            """,
            rows,
        )

    async def counts(self) -> dict:
        names = [
            "users",
            "courses",
            "course_modules",
            "lessons",
            "slides",
            "aois",
            "enrollments",
            "course_visits",
            "learning_sessions",
            "content_views",
            "view_layouts",
            "gaze_samples",
            "chat_sessions",
            "chat_messages",
            "quiz_attempts",
            "gaze_calibrations",
            "background_jobs",
        ]
        out = {}
        for name in names:
            out[name] = int(await self.conn.fetchval(f"SELECT count(*) FROM {name}"))
        return out


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", choices=["tiny", "baseline", "stress"], default="baseline")
    parser.add_argument("--dsn", default="")
    parser.add_argument("--fixtures-dir", default="/bench/fixtures")
    parser.add_argument("--ingest-slides", type=int, default=20)
    parser.add_argument("--out", default="")
    parser.add_argument("--allow-non-bench", action="store_true")
    args = parser.parse_args()

    dsn = args.dsn or dsn_from_env()
    db_name = dsn.rsplit("/", 1)[-1].split("?", 1)[0]
    if not args.allow_non_bench and not db_name.endswith("_bench"):
        raise SystemExit(
            f"Từ chối seed vào DB {db_name!r}; tên DB phải kết thúc bằng _bench "
            "hoặc truyền --allow-non-bench."
        )

    pdf = Path(args.fixtures_dir) / "lecture_20p.pdf"
    if not pdf.is_file():
        raise SystemExit(f"Không thấy fixture PDF: {pdf}")

    cfg = scale_config(args.scale)
    cfg["ingest_slides"] = max(1, args.ingest_slides)
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SET synchronous_commit=off")
        await conn.execute("DELETE FROM courses WHERE title LIKE 'BENCH:%'")
        # UI AOI không gắn course nên không cascade; xoá bộ UI benchmark cũ.
        await conn.execute("DELETE FROM aois WHERE ui_schema = 'reader-v1'")
        await conn.execute("DELETE FROM users WHERE email LIKE 'bench-%@example.test'")
        seeder = Seeder(conn, cfg)
        await seeder.seed_users(pdf)
        await seeder.seed_courses()
        await seeder.seed_content()
        await seeder.seed_enrollments()
        await seeder.seed_analytics()
        targets = await seeder.seed_gaze_targets()
        await seeder.seed_chat()
        await seeder.seed_quizzes()
        await seeder.seed_calibrations()
        await seeder.seed_jobs()
        await conn.execute("ANALYZE")
        counts = await seeder.counts()
        chat_contexts = [
            {
                "id": str(row["id"]),
                "context_key": row["context_key"],
                "course_id": str(row["course_id"]),
                "lesson_id": str(row["lesson_id"]) if row["lesson_id"] else None,
            }
            for row in await conn.fetch(
                "SELECT id, context_key, course_id, lesson_id FROM chat_sessions "
                "ORDER BY created_at, id"
            )
        ]

        first_visit = uid("visit:core:0")
        first_views = [uid(f"view:core:0:0:{j}") for j in range(cfg["views_per_session"])]
        fixtures = {
            "scale": args.scale,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pdf_sha256": seeder.pdf_sha,
            "ids": {
                "admin_id": str(seeder.admin_id),
                "teacher_id": str(seeder.teacher_id),
                "core_course_id": str(seeder.courses["core"]["id"]),
                "ingest_course_id": str(seeder.courses["ingest"]["id"]),
                "draft_course_id": str(seeder.courses["draft"]["id"]),
                "ingest_lesson_id": str(seeder.ingest_lesson_id),
                "ingest_slide_ids": [str(v) for v in seeder.ingest_slide_ids],
                "core_visit_id": str(first_visit),
                "core_view_ids": [str(v) for v in first_views],
                "core_lesson_ids": [str(v) for v in seeder.lecture_lesson_ids[:20]],
                "core_slide_ids": [str(v) for v in seeder.course_slide_ids.get("core", [])],
                "quiz_lesson_ids": [str(v) for v in seeder.quiz_lesson_ids[:4]],
            },
            "student_ids": [str(v) for v in seeder.student_ids],
            "gaze_targets": targets,
            "chat_contexts": chat_contexts,
            "counts": counts,
        }
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(fixtures, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"counts": counts, "targets": len(targets)}, ensure_ascii=False, indent=2))
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
