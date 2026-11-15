"""Import contracts for the simplified AOI package."""

from __future__ import annotations

import inspect

from app.services import aoi, course_students

PUBLIC_AOI_CALLABLES = (
    "list_aoi_collections",
    "generate_slide_aois",
    "save_slide_aois",
    "generate_ui_aois",
    "save_ui_aois",
    "load_aois",
    "replace_aois",
)


def test_aoi_package_exports_public_callables():
    for name in PUBLIC_AOI_CALLABLES:
        assert callable(getattr(aoi, name)), name


def test_aoi_public_callables_are_coroutines():
    for name in PUBLIC_AOI_CALLABLES:
        assert inspect.iscoroutinefunction(getattr(aoi, name)), name


def test_course_students_service_exists():
    assert callable(course_students.course_students)
    assert inspect.iscoroutinefunction(course_students.course_students)
