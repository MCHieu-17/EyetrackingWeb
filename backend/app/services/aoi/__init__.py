"""AOI sets: draft/published, slide/UI scope, generated suggestions.

Bộ vùng slide gắn với từng `SlideVersion`; bộ vùng giao diện dùng chung theo
`ui_schema_version`. Mỗi bộ luôn có định nghĩa hệ thống `no_label` để phân loại
các mẫu gaze không rơi vào vùng lá nào.
"""

from __future__ import annotations

from .access import published_aoi_set
from .common import NO_LABEL_CODE, NO_LABEL_NAME
from .definitions import ensure_no_label_definition
from .generate import (
    AUTO_KINDS,
    generate_slide_aoi_set,
    generate_ui_aoi_set,
)
from .sets import list_aoi_sets, save_slide_aoi_set, save_ui_aoi_set

__all__ = [
    "AUTO_KINDS",
    "NO_LABEL_CODE",
    "NO_LABEL_NAME",
    "ensure_no_label_definition",
    "generate_slide_aoi_set",
    "generate_ui_aoi_set",
    "list_aoi_sets",
    "published_aoi_set",
    "save_slide_aoi_set",
    "save_ui_aoi_set",
]
