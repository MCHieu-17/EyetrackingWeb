from pgvector import Vector

from app.workflow import retrieval


def _doc():
    return {
        "id": "slide-1",
        "lesson_id": "lesson-1",
        "content": "Nội dung slide",
        "course_title": "Cơ sở dữ liệu",
        "module_title": "Chương 1",
        "lesson_title": "Bài 1",
        "image_url": "/media/slide.jpg",
        "slide_index": 1,
        "score": 0.5,
    }


def test_build_citations_maps_fields():
    citations = retrieval.build_citations([_doc()])
    assert citations[0]["document_id"] == "slide-1"
    assert citations[0]["lesson_id"] == "lesson-1"
    assert citations[0]["slide_index"] == 1
    assert citations[0]["image_url"] == "/media/slide.jpg"
    assert citations[0]["snippet"] == "Nội dung slide"


def test_format_context_numbers_documents():
    context = retrieval.format_context([_doc()])
    assert context.startswith("[1] Cơ sở dữ liệu > Chương 1 > Bài 1")
    assert "Nội dung slide" in context


def test_format_context_empty():
    assert retrieval.format_context([]) == ""


class _FakeCursor:
    def __init__(self):
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, _sql, params):
        self.params = params

    def fetchall(self):
        return []


class _FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self, **_kwargs):
        return self._cursor


class _FakePool:
    def __init__(self, connection):
        self._connection = connection

    def connection(self):
        return self._connection


def test_query_passes_all_parameters(monkeypatch):
    cursor = _FakeCursor()
    pool = _FakePool(_FakeConnection(cursor))
    monkeypatch.setattr(retrieval, "get_pool", lambda: pool)

    retriever = retrieval.Retriever.__new__(retrieval.Retriever)
    retriever.top_k = 8
    retriever.candidates = 20
    retriever.rrf_k = 60
    retriever.threshold = 0.25

    retriever._query(Vector([0.1] * 1024), "khóa chính", "course-1")

    assert cursor.params is not None
    assert len(cursor.params) == 13
    assert cursor.params[2] == "course-1"
    assert cursor.params[7] == "khóa chính"
    assert cursor.params[12] == 8
