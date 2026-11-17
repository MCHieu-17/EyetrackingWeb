from pydantic import Field

from app.schemas.common import CamelModel

AOI_CODE_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"


class AoiDefinitionIn(CamelModel):
    code: str = Field(min_length=1, max_length=64, pattern=AOI_CODE_PATTERN)
    name: str = Field(min_length=1, max_length=100)
    # Nhãn phân tích cho leaf slide (AOI_1, AOI_THANHCHAT, ...).
    # UI/container bỏ trống.
    label: str | None = Field(default=None, max_length=64)
    parent_id: str | None = None
    geometry: dict = Field(default_factory=dict)
    is_container: bool = False
    kind: str = Field(default="custom", pattern="^(text|image|table|drawing|custom|ui|system)$")
    is_active: bool = True


class AoiDefinitionOut(CamelModel):
    id: str
    code: str
    name: str
    label: str | None = None
    parent_id: str | None = None
    geometry: dict = Field(default_factory=dict)
    is_container: bool = False
    kind: str = "custom"
    is_active: bool = True


class AoiSaveIn(CamelModel):
    definitions: list[AoiDefinitionIn] = Field(default_factory=list, max_length=500)


class AoiUiComponentIn(CamelModel):
    code: str = Field(min_length=1, max_length=64, pattern=AOI_CODE_PATTERN)
    name: str = Field(min_length=1, max_length=100)


class AoiUiGenerateIn(CamelModel):
    components: list[AoiUiComponentIn] = Field(default_factory=list, max_length=200)
    merge: bool = True


class AoiCollectionOut(CamelModel):
    """AOI hiện hành của một slide hoặc một UI schema.

    Schema generation 13 lưu trực tiếp trong `aois`, không có revision hay
    trạng thái draft/published.
    """

    id: str
    scope: str
    slide_id: str | None = None
    ui_schema: str | None = None
    definitions: list[AoiDefinitionOut] = Field(default_factory=list)


class AoiRebuildIn(CamelModel):
    course_id: str
    lesson_id: str | None = None


class AoiRebuildOut(CamelModel):
    ok: bool = True
    runs: int = 0
    completed: int = 0
    failed: int = 0
