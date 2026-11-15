"""AOI service — mỗi AOI gắn trực tiếp slide hoặc UI schema, không version."""

from app.services.aoi.definitions import (
    aoi_collection_out,
    definition_to_input,
    load_aois,
    replace_aois,
)
from app.services.aoi.generate import (
    generate_slide_aois,
    generate_ui_aois,
    save_slide_aois,
    save_ui_aois,
)
from app.services.aoi.queries import list_aoi_collections

__all__ = [
    "aoi_collection_out",
    "definition_to_input",
    "generate_slide_aois",
    "generate_ui_aois",
    "list_aoi_collections",
    "load_aois",
    "replace_aois",
    "save_slide_aois",
    "save_ui_aois",
]
