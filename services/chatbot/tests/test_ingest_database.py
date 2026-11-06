"""Opt-in database tests; providers fake, storage/SQL/transactions real.

CHATBOT_INTEGRATION_DATABASE_URL must point to an already migrated disposable DB.
"""

import hashlib
import os
import threading
from types import SimpleNamespace
from urllib.parse import urlparse
from uuid import uuid4

import psycopg
import pymupdf
import pytest
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.db import _configure
from app.services.ingest import Ingestion
from app.services.storage import FileStorage
from app.workflow import retrieval


@pytest.fixture()
def ingester(monkeypatch, tmp_path):
    url = os.getenv("CHATBOT_INTEGRATION_DATABASE_URL")
    if not url:
        pytest.skip("Set CHATBOT_INTEGRATION_DATABASE_URL to disposable DB")
    assert any(s in urlparse(url).path for s in ("test", "eval"))

    user = str(uuid4())
    course = str(uuid4())
    version = str(uuid4())
    module = str(uuid4())
    lesson = str(uuid4())
    lesson_version = str(uuid4())
    item = str(uuid4())
    asset = str(uuid4())
    slide = str(uuid4())
    slide_version = str(uuid4())
    membership = str(uuid4())
    digest = hashlib.sha256(b"test-image").hexdigest()
    object_key = f"test-{uuid4().hex}.png"

    with psycopg.connect(url) as conn:
        conn.execute(
            "INSERT INTO users(id,email,password_hash,status) VALUES (%s,%s,'test','active')",
            (user, f"{user}@example.com"),
        )
        conn.execute(
            "INSERT INTO teacher_profiles(user_id,teacher_code) VALUES (%s,%s)",
            (user, user[:20]),
        )
        conn.execute(
            "INSERT INTO courses(id,owner_id,created_by) VALUES (%s,%s,%s)",
            (course, user, user),
        )
        conn.execute(
            """
            INSERT INTO course_versions
                (id,course_id,version_no,state,title,created_by,published_at)
            VALUES (%s,%s,1,'published','DB',%s,now())
            """,
            (version, course, user),
        )
        conn.execute(
            "UPDATE courses SET published_version_id=%s WHERE id=%s",
            (version, course),
        )
        conn.execute(
            """
            INSERT INTO course_version_modules
                (id,course_version_id,title,position)
            VALUES (%s,%s,'Module',0)
            """,
            (module, version),
        )
        conn.execute(
            "INSERT INTO lessons(id,course_id,kind) VALUES (%s,%s,'lesson')",
            (lesson, course),
        )
        conn.execute(
            """
            INSERT INTO lesson_versions
                (id,lesson_id,version_no,state,title,created_by,published_at)
            VALUES (%s,%s,1,'published','Lesson',%s,now())
            """,
            (lesson_version, lesson, user),
        )
        conn.execute(
            """
            INSERT INTO course_version_items
                (id,course_version_id,module_id,lesson_id,lesson_version_id,position)
            VALUES (%s,%s,%s,%s,%s,0)
            """,
            (item, version, module, lesson, lesson_version),
        )
        conn.execute(
            """
            INSERT INTO media_assets
                (id,course_id,storage_backend,object_key,sha256,mime_type,
                 byte_size,image_width,image_height,state)
            VALUES (%s,%s,'local',%s,%s,'image/png',100,800,450,'ready')
            """,
            (asset, course, object_key, digest),
        )
        conn.execute(
            "INSERT INTO slides(id,lesson_id) VALUES (%s,%s)", (slide, lesson)
        )
        conn.execute(
            """
            INSERT INTO slide_versions
                (id,slide_id,revision_no,image_asset_id,created_by)
            VALUES (%s,%s,1,%s,%s)
            """,
            (slide_version, slide, asset, user),
        )
        conn.execute(
            """
            INSERT INTO lesson_version_slides
                (id,lesson_version_id,slide_id,slide_version_id,position,title)
            VALUES (%s,%s,%s,%s,0,'Slide 1')
            """,
            (membership, lesson_version, slide, slide_version),
        )

    with pymupdf.open() as doc:
        doc.new_page().get_pixmap().save(str(tmp_path / object_key))
    monkeypatch.setenv("LOCAL_MEDIA_DIR", str(tmp_path))
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    pool = ConnectionPool(
        url,
        min_size=1,
        max_size=3,
        kwargs={"autocommit": True, "row_factory": dict_row},
        configure=_configure,
    )
    service = Ingestion.__new__(Ingestion)
    service._pool = pool
    service._embed_lock = threading.Lock()
    service.embedding = SimpleNamespace(
        embed_documents=lambda texts: [[1.0] + [0.0] * 1023]
    )
    service.storage = FileStorage()
    service._describe_image = lambda b64: "Khóa chính xác định duy nhất mỗi hàng."
    service._verify_vector_dim()
    monkeypatch.setattr(retrieval, "get_pool", lambda: pool)
    retriever = retrieval.Retriever.__new__(retrieval.Retriever)
    retriever.embedding = SimpleNamespace(
        embed_query=lambda text: [1.0] + [0.0] * 1023
    )
    retriever.top_k, retriever.candidates, retriever.rrf_k, retriever.threshold = (
        8,
        20,
        60,
        0.25,
    )

    def sql(query, params=()):
        with pool.connection() as conn:
            result = conn.execute(query, params)
            return result.fetchall() if result.description else []

    yield (
        service,
        retriever,
        sql,
        course,
        version,
        lesson_version,
        slide_version,
        asset,
        object_key,
    )
    service.close()
    sql(
        """
        DELETE FROM lesson_version_slides
        WHERE lesson_version_id IN (
            SELECT lv.id FROM lesson_versions lv
            JOIN lessons l ON l.id = lv.lesson_id
            WHERE l.course_id = %s
        )
        """,
        (course,),
    )
    sql("ALTER TABLE slide_versions DISABLE TRIGGER trg_slide_versions_immutable")
    try:
        sql(
            """
            DELETE FROM slide_versions
            WHERE slide_id IN (
                SELECT s.id FROM slides s
                JOIN lessons l ON l.id = s.lesson_id
                WHERE l.course_id = %s
            )
            """,
            (course,),
        )
    finally:
        sql("ALTER TABLE slide_versions ENABLE TRIGGER trg_slide_versions_immutable")
    sql("UPDATE media_assets SET state='deleted' WHERE course_id=%s", (course,))
    sql("DELETE FROM media_assets WHERE course_id=%s", (course,))
    sql("ALTER TABLE course_versions DISABLE TRIGGER trg_course_versions_immutable")
    sql("ALTER TABLE lesson_versions DISABLE TRIGGER trg_lesson_versions_immutable")
    try:
        sql("DELETE FROM courses WHERE id=%s", (course,))
    finally:
        sql("ALTER TABLE course_versions ENABLE TRIGGER trg_course_versions_immutable")
        sql("ALTER TABLE lesson_versions ENABLE TRIGGER trg_lesson_versions_immutable")
    sql("DELETE FROM users WHERE id=%s", (user,))
    pool.close()


def test_reingest_retrieval_scope_and_cascade(ingester):
    service, retriever, sql, course, version, lesson_version, slide_version, _, _ = ingester
    for _ in range(2):
        assert service.embed_slide(slide_version)[:2] == (1, 0)
    row = sql(
        """
        SELECT count(*) AS count, max(vector_dims(embedding)) AS dim
        FROM slide_documents WHERE slide_version_id=%s
        """,
        (slide_version,),
    )[0]
    assert row["count"] == 1
    assert row["dim"] == 1024
    assert str(retriever.search("Khóa chính", course, version)[0]["id"]) == slide_version
    assert retriever.search("Khóa chính", course, str(uuid4())) == []
    sql("UPDATE courses SET archived_at=now() WHERE id=%s", (course,))
    assert retriever.search("Khóa chính", course, version) == []
    sql("UPDATE courses SET archived_at=NULL WHERE id=%s", (course,))
    with pytest.raises(psycopg.errors.RaiseException):
        sql("DELETE FROM slide_versions WHERE id=%s", (slide_version,))
    sql("DELETE FROM slide_documents WHERE slide_version_id=%s", (slide_version,))
    assert (
        sql(
            "SELECT count(*) AS count FROM slide_documents WHERE slide_version_id=%s",
            (slide_version,),
        )[0]["count"]
        == 0
    )


def test_missing_image_failed_status_and_recovery(ingester):
    service, _, sql, _, _, _, slide_version, _, object_key = ingester
    path = service.storage.local_root / object_key
    original = path.read_bytes()
    path.unlink()
    assert service.embed_slide(slide_version)[1] == 1
    row = sql(
        "SELECT ingestion_state, ingestion_error FROM slide_documents WHERE slide_version_id=%s",
        (slide_version,),
    )[0]
    assert row["ingestion_state"] == "failed" and row["ingestion_error"]
    path.write_bytes(original)
    assert service.reindex_all()[0] >= 1
    assert (
        sql(
            "SELECT ingestion_state FROM slide_documents WHERE slide_version_id=%s",
            (slide_version,),
        )[0]["ingestion_state"]
        == "ready"
    )


def test_ready_insert_failure_rolls_back_vector(ingester):
    service, _, sql, _, _, _, slide_version, _, _ = ingester
    sql(
        """CREATE OR REPLACE FUNCTION chatbot_test_ready_failure() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF NEW.ingestion_state='ready' THEN RAISE EXCEPTION 'test ready failure'; END IF; RETURN NEW; END $$"""
    )
    sql(
        "CREATE TRIGGER chatbot_test_ready_failure BEFORE INSERT OR UPDATE ON slide_documents "
        "FOR EACH ROW EXECUTE FUNCTION chatbot_test_ready_failure()"
    )
    try:
        assert service.embed_slide(slide_version)[1] == 1
        assert (
            sql(
                "SELECT count(*) AS count FROM slide_documents "
                "WHERE slide_version_id=%s AND ingestion_state='ready'",
                (slide_version,),
            )[0]["count"]
            == 0
        )
        assert (
            sql(
                "SELECT ingestion_state FROM slide_documents WHERE slide_version_id=%s",
                (slide_version,),
            )[0]["ingestion_state"]
            == "failed"
        )
    finally:
        sql("DROP TRIGGER chatbot_test_ready_failure ON slide_documents")
        sql("DROP FUNCTION chatbot_test_ready_failure()")


def test_wrong_embedding_dimension_never_marks_ready(ingester):
    service, _, sql, _, _, _, slide_version, _, _ = ingester
    service.embedding = SimpleNamespace(embed_documents=lambda texts: [[1.0, 0.0]])
    assert service.embed_slide(slide_version)[1] == 1
    row = sql(
        "SELECT ingestion_state, ingestion_error FROM slide_documents WHERE slide_version_id=%s",
        (slide_version,),
    )[0]
    assert row["ingestion_state"] == "failed" and row["ingestion_error"]
    assert (
        sql(
            "SELECT count(*) AS count FROM slide_documents "
            "WHERE slide_version_id=%s AND ingestion_state='ready'",
            (slide_version,),
        )[0]["count"]
        == 0
    )


def test_delete_while_vlm_is_running_never_restores_slide(ingester):
    service, _, sql, _, _, _, slide_version, _, _ = ingester
    started, proceed = threading.Event(), threading.Event()

    def describe(_):
        started.set()
        assert proceed.wait(5)
        return "Transcript"

    service._describe_image = describe
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor() as pool:
        job = pool.submit(service.embed_slide, slide_version)
        assert started.wait(5)
        sql("DELETE FROM lesson_version_slides WHERE slide_version_id=%s", (slide_version,))
        sql("ALTER TABLE slide_versions DISABLE TRIGGER trg_slide_versions_immutable")
        try:
            sql("DELETE FROM slide_versions WHERE id=%s", (slide_version,))
        finally:
            sql("ALTER TABLE slide_versions ENABLE TRIGGER trg_slide_versions_immutable")
        proceed.set()
        assert job.result()[1] == 1
    assert (
        sql(
            "SELECT count(*) AS count FROM slide_documents WHERE slide_version_id=%s",
            (slide_version,),
        )[0]["count"]
        == 0
    )
