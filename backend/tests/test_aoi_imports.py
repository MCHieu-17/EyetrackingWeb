"""Import contracts for the split AOI package and course_students service."""

from __future__ import annotations

import inspect

from app.services import aoi, course_students, metrics

PUBLIC_AOI_CALLABLES = (
    "list_aoi_sets",
    "generate_slide_aoi_set",
    "save_slide_aoi_set",
    "generate_ui_aoi_set",
    "save_ui_aoi_set",
    "published_aoi_set",
    "ensure_no_label_definition",
)


def test_aoi_package_exports_public_callables():
    for name in PUBLIC_AOI_CALLABLES:
        assert callable(getattr(aoi, name)), name


def test_aoi_public_callables_are_coroutines():
    for name in PUBLIC_AOI_CALLABLES:
        assert inspect.iscoroutinefunction(getattr(aoi, name)), name


def test_metrics_course_students_wrapper_exists():
    assert callable(metrics.course_students)
    assert inspect.iscoroutinefunction(metrics.course_students)


def test_course_students_service_exists():
    assert callable(course_students.course_students)
    assert inspect.iscoroutinefunction(course_students.course_students)
