"""Content versioning: draft, copy-on-write, publish, outline.

Phase 2 service. Mọi mutation nội dung đi qua đây để giữ:
  - một draft/course;
  - generation guard;
  - published version bất biến;
  - asset/slide version tái sử dụng.
"""

from __future__ import annotations

from app.services.content.common import (
    bump_generation,
    check_generation,
    get_course_or_404,
    get_draft_version,
    get_published_version,
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
    get_draft_item_for_lesson,
    reorder_items,
    update_lesson,
)
from app.services.content.modules import (
    course_of_module,
    create_module,
    delete_module,
    update_module,
)
from app.services.content.outline import get_draft_tree, get_published_outline
from app.services.content.publish import (
    publish_course,
    published_quiz_lesson_ids,
    validate_draft,
)
from app.services.content.slides import (
    create_slide_import,
    get_lesson_contents,
    get_lesson_version_contents,
    get_slide_import_job,
    list_lesson_slides_admin,
    process_pending_slide_imports,
    process_slide_import,
)
from app.services.content.students import get_course_students
from app.services.content.versions import (
    clone_course_version,
    clone_lesson_version,
    ensure_draft_lesson_version,
)

__all__ = [
    "bump_generation",
    "check_generation",
    "clone_course_version",
    "clone_lesson_version",
    "course_of_module",
    "create_course",
    "create_lesson",
    "create_module",
    "create_quiz_item",
    "create_slide_import",
    "delete_course",
    "delete_lesson",
    "delete_module",
    "ensure_draft_lesson_version",
    "get_course_or_404",
    "get_course_students",
    "get_draft_item_for_lesson",
    "get_draft_tree",
    "get_draft_version",
    "get_lesson_contents",
    "get_lesson_version_contents",
    "get_published_outline",
    "get_published_version",
    "get_slide_import_job",
    "list_lesson_slides_admin",
    "list_teacher_courses",
    "logger",
    "process_pending_slide_imports",
    "process_slide_import",
    "publish_course",
    "published_quiz_lesson_ids",
    "reorder_items",
    "update_course_metadata",
    "update_lesson",
    "update_module",
    "validate_draft",
]
