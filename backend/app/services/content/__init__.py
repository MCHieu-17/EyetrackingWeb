"""Content service package — no content versioning."""

from __future__ import annotations

from app.services.content.common import (
    course_of_lesson,
    course_of_module,
    delete_media_objects,
    get_course_or_404,
    logger,
)
from app.services.content.courses import (
    create_course,
    delete_course,
    list_teacher_courses,
    update_course_metadata,
)
from app.services.content.lessons import (
    create_lesson,
    create_quiz_item,
    delete_lesson,
    reorder_items,
    update_lesson,
)
from app.services.content.modules import create_module, delete_module, update_module
from app.services.content.outline import get_course_tree, get_published_outline
from app.services.content.publish import publish_course, validate_course
from app.services.content.slide_reads import (
    get_lesson_contents,
    list_lesson_slides_admin,
)
from app.services.content.slides import (
    create_slide_import,
    get_slide_import_job,
    process_pending_slide_imports,
    process_slide_import,
)
from app.services.content.students import get_course_students

__all__ = [
    "course_of_lesson",
    "course_of_module",
    "create_course",
    "create_lesson",
    "create_module",
    "create_quiz_item",
    "create_slide_import",
    "delete_course",
    "delete_lesson",
    "delete_media_objects",
    "delete_module",
    "get_course_or_404",
    "get_course_students",
    "get_course_tree",
    "get_lesson_contents",
    "get_published_outline",
    "get_slide_import_job",
    "list_lesson_slides_admin",
    "list_teacher_courses",
    "logger",
    "process_pending_slide_imports",
    "process_slide_import",
    "publish_course",
    "reorder_items",
    "update_course_metadata",
    "update_lesson",
    "update_module",
    "validate_course",
]
