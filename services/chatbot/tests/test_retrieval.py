from pgvector import Vector

from app.workflow import retrieval


def _doc():
    return {
        "id": "slide-version-1",
        "course_id": "course-1",
        "course_version_id": "course-version-1",
        "lesson_id": "lesson-1",
        "lesson_version_id": "lesson-version-1",
        "membership_id": "membership-1",
        "slide_id": "slide-1",
        "asset_id": "asset-1",
        "image_object_key": "instances/db/courses/course-1/slide.jpg",
        "image_storage_backend": "local",
        "image_mime_type": "image/jpeg",
        "content": "Nội dung slide",
        "module_title": "Chương 1",
        "lesson_title": "Bài 1",
        "slide_index": 1,
        "score": 0.5,
    }


def test_build_citations_maps_versioned_fields():
    citations = retrieval.build_citations([_doc()])
    assert citations[0]["document_id"] == "slide-version-1"
    assert citations[0]["course_version_id"] == "course-version-1"
    assert citations[0]["lesson_version_id"] == "lesson-version-1"
    assert citations[0]["membership_id"] == "membership-1"
    assert citations[0]["asset_id"] == "asset-1"
    assert citations[0]["lesson_id"] == "lesson-1"
    assert citations[0]["slide_index"] == 1
    assert citations[0]["image_url"] == "/media/assets/asset-1"
    assert citations[0]["snippet"] == "Nội dung slide"


def test_format_context_numbers_documents():
    context = retrieval.format_context([_doc()])
    assert context.startswith("[1] Chương 1 > Bài 1 (slide 1)")
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

    retriever._query(
        Vector([0.1] * 1024), "khóa chính", "course-1", "course-version-1"
    )

    assert cursor.params is not None
    assert len(cursor.params) == 15
    assert cursor.params[2] == "course-1"
    assert cursor.params[3] == "course-version-1"
    assert cursor.params[8] == "khóa chính"
    assert cursor.params[14] == 8
