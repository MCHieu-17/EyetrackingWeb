"""Opt-in database tests; providers fake, storage/SQL/transactions real.

CHATBOT_INTEGRATION_DATABASE_URL must point to an already migrated disposable DB.
"""

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
    user, course, module, lesson, slide = [str(uuid4()) for _ in range(5)]
    with psycopg.connect(url) as conn:
        conn.execute(
            "INSERT INTO user_statuses(code,label) VALUES ('active','Active') ON CONFLICT DO NOTHING"
        )
        conn.execute(
            "INSERT INTO course_statuses(code,label) VALUES ('published','Published') ON CONFLICT DO NOTHING"
        )
        conn.execute(
            "INSERT INTO users(id,email,password_hash,status_id) VALUES (%s,%s,'test',(SELECT id FROM user_statuses WHERE code='active'))",
            (user, f"{user}@test.local"),
        )
        conn.execute(
            "INSERT INTO teacher_profiles(user_id,teacher_code) VALUES (%s,%s)", (user, user[:20])
        )
        conn.execute(
            "INSERT INTO courses(id,title,teacher_id,created_by,status_id) VALUES (%s,'DB',%s,%s,(SELECT id FROM course_statuses WHERE code='published'))",
            (course, user, user),
        )
        conn.execute(
            "INSERT INTO modules(id,course_id,title,order_index) VALUES (%s,%s,'Module',1)",
            (module, course),
        )
        conn.execute(
            "INSERT INTO lessons(id,module_id,title,order_index) VALUES (%s,%s,'Lesson',1)",
            (lesson, module),
        )
        conn.execute(
            "INSERT INTO lesson_contents(id,lesson_id,order_index,image_url,content_json) VALUES (%s,%s,1,'/media/test.png','{}')",
            (slide, lesson),
        )
    with pymupdf.open() as doc:
        doc.new_page().get_pixmap().save(str(tmp_path / "test.png"))
    monkeypatch.setenv("LOCAL_MEDIA_DIR", str(tmp_path))
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
    service.embedding = SimpleNamespace(embed_documents=lambda texts: [[1.0] + [0.0] * 1023])
    service.storage = FileStorage()
    service._describe_image = lambda b64: "Khóa chính xác định duy nhất mỗi hàng."
    service._verify_vector_dim()
    monkeypatch.setattr(retrieval, "get_pool", lambda: pool)
    retriever = retrieval.Retriever.__new__(retrieval.Retriever)
    retriever.embedding = SimpleNamespace(embed_query=lambda text: [1.0] + [0.0] * 1023)
    retriever.top_k, retriever.candidates, retriever.rrf_k, retriever.threshold = 8, 20, 60, 0.25

    def sql(query, params=()):
        with pool.connection() as conn:
            result = conn.execute(query, params)
            return result.fetchall() if result.description else []

    yield service, retriever, sql, course, lesson, slide
    service.close()
    # Course/lesson/vector cleanup is tested and isolated to our random fixture.
    sql("DELETE FROM courses WHERE id=%s", (course,))
    sql("DELETE FROM users WHERE id=%s", (user,))
    pool.close()


def test_reingest_retrieval_scope_soft_delete_and_cascade(ingester):
    service, retriever, sql, course, lesson, slide = ingester
    for _ in range(2):
        assert service.embed_slide(slide)[:2] == (1, 0)
    assert sql(
        "SELECT count(*), max(vector_dims(embedding)) AS dim FROM lesson_content_embedding WHERE lesson_content_id=%s",
        (slide,),
    )[0] == {"count": 1, "dim": 1024}
    assert str(retriever.search("Khóa chính", course)[0]["id"]) == slide
    assert retriever.search("Khóa chính", str(uuid4())) == []
    sql("UPDATE courses SET deleted_at=now() WHERE id=%s", (course,))
    assert retriever.search("Khóa chính", course) == []
    sql("DELETE FROM lessons WHERE id=%s", (lesson,))
    assert (
        sql("SELECT count(*) FROM lesson_content_embedding WHERE lesson_content_id=%s", (slide,))[
            0
        ]["count"]
        == 0
    )


def test_delete_while_vlm_is_running_never_restores_slide(ingester):
    service, _, sql, _, _, slide = ingester
    started, proceed = threading.Event(), threading.Event()

    def describe(_):
        started.set()
        assert proceed.wait(5)
        return "Transcript"

    service._describe_image = describe
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor() as pool:
        job = pool.submit(service.embed_slide, slide)
        assert started.wait(5)
        sql("DELETE FROM lesson_contents WHERE id=%s", (slide,))
        proceed.set()
        assert job.result()[1] == 1
    assert (
        sql("SELECT count(*) FROM lesson_content_embedding WHERE lesson_content_id=%s", (slide,))[
            0
        ]["count"]
        == 0
    )


def test_missing_image_failed_status_and_recovery(ingester):
    service, _, sql, _, _, slide = ingester
    sql("UPDATE lesson_contents SET image_url='/media/missing.png' WHERE id=%s", (slide,))
    assert service.embed_slide(slide)[1] == 1
    row = sql(
        "SELECT embedding_status, embedding_error FROM lesson_contents WHERE id=%s", (slide,)
    )[0]
    assert row["embedding_status"] == "failed" and row["embedding_error"]
    sql("UPDATE lesson_contents SET image_url='/media/test.png' WHERE id=%s", (slide,))
    assert service.reindex_all()[0] >= 1
    assert (
        sql("SELECT embedding_status FROM lesson_contents WHERE id=%s", (slide,))[0][
            "embedding_status"
        ]
        == "ready"
    )


def test_ready_update_failure_rolls_back_vector(ingester):
    service, _, sql, _, _, slide = ingester
    # This trigger fails only the ready update, after INSERT has already executed.
    # It catches accidental autocommit between the two statements.
    sql("""CREATE OR REPLACE FUNCTION chatbot_test_ready_failure() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF NEW.embedding_status='ready' THEN RAISE EXCEPTION 'test ready failure'; END IF; RETURN NEW; END $$""")
    sql(
        "CREATE TRIGGER chatbot_test_ready_failure BEFORE UPDATE ON lesson_contents FOR EACH ROW EXECUTE FUNCTION chatbot_test_ready_failure()"
    )
    try:
        assert service.embed_slide(slide)[1] == 1
        assert (
            sql(
                "SELECT count(*) FROM lesson_content_embedding WHERE lesson_content_id=%s", (slide,)
            )[0]["count"]
            == 0
        )
        assert (
            sql("SELECT embedding_status FROM lesson_contents WHERE id=%s", (slide,))[0][
                "embedding_status"
            ]
            == "failed"
        )
    finally:
        sql("DROP TRIGGER chatbot_test_ready_failure ON lesson_contents")
        sql("DROP FUNCTION chatbot_test_ready_failure()")


def test_wrong_embedding_dimension_never_marks_ready(ingester):
    service, _, sql, _, _, slide = ingester
    service.embedding = SimpleNamespace(embed_documents=lambda texts: [[1.0, 0.0]])
    assert service.embed_slide(slide)[1] == 1
    row = sql(
        "SELECT embedding_status, embedding_error FROM lesson_contents WHERE id=%s", (slide,)
    )[0]
    assert row["embedding_status"] == "failed" and row["embedding_error"]
    assert (
        sql("SELECT count(*) FROM lesson_content_embedding WHERE lesson_content_id=%s", (slide,))[
            0
        ]["count"]
        == 0
    )


def test_ingest_finishes_while_pdf_replacement_holds_lesson_mutex(ingester):
    from concurrent.futures import ThreadPoolExecutor

    service, _, sql, _, lesson, slide = ingester
    with ThreadPoolExecutor() as pool:
        with service._connection() as conn, conn.transaction():
            conn.execute("SELECT id FROM lessons WHERE id=%s FOR NO KEY UPDATE", (lesson,))
            job = pool.submit(service.embed_slide, slide)
            # Release the DB lock before executor cleanup even if this times out.
            # A FOR UPDATE lesson mutex would block embedding's FK check here.
            assert job.result(timeout=5)[:2] == (1, 0)
    assert (
        sql("SELECT embedding_status FROM lesson_contents WHERE id=%s", (slide,))[0][
            "embedding_status"
        ]
        == "ready"
    )
