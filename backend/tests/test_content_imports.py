"""Contract test: public content service API survives the package split."""

from __future__ import annotations

import app.services.content as content
from app.services import content as content_from_services
from app.services.content import process_pending_slide_imports

PUBLIC_CALLABLES = [
    "list_teacher_courses",
    "create_course",
    "update_course_metadata",
    "delete_course",
    "get_course_tree",
    "get_published_outline",
    "publish_course",
    "get_course_students",
    "create_slide_import",
    "get_slide_import_job",
    "process_slide_import",
    "process_pending_slide_imports",
    "list_lesson_slides_admin",
    "get_lesson_contents",
    "create_module",
    "update_module",
    "delete_module",
    "create_lesson",
    "create_quiz_item",
    "update_lesson",
    "delete_lesson",
    "reorder_items",
    "course_of_module",
    "validate_course",
]


def test_services_namespace_import_returns_package():
    assert content_from_services is content


def test_worker_import_path_exposes_process_pending_slide_imports():
    assert callable(process_pending_slide_imports)


def test_public_callables_are_exported():
    missing = [
        name
        for name in PUBLIC_CALLABLES
        if not callable(getattr(content, name, None))
    ]
    assert missing == []
    assert set(PUBLIC_CALLABLES) <= set(content.__all__)
