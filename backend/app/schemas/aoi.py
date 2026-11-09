from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel

AOI_CODE_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"


class AoiDefinitionIn(CamelModel):
    code: str = Field(min_length=1, max_length=64, pattern=AOI_CODE_PATTERN)
    name: str = Field(min_length=1, max_length=100)
    parent_id: str | None = None
    geometry: dict = Field(default_factory=dict)
    is_container: bool = False
    kind: str = Field(default="custom", pattern="^(text|image|table|drawing|custom|ui|system)$")
    is_active: bool = True


class AoiDefinitionOut(CamelModel):
    id: str
    code: str
    name: str
    parent_id: str | None = None
    geometry: dict = Field(default_factory=dict)
    is_container: bool = False
    kind: str = "custom"
    is_active: bool = True


class AoiSetSaveIn(CamelModel):
    definitions: list[AoiDefinitionIn] = Field(default_factory=list, max_length=500)
    expected_revision: int | None = Field(default=None, ge=1)


class AoiSetGenerateIn(CamelModel):
    slide_number: int | None = Field(default=None, ge=1)
    merge: bool = False
    # Thay các vùng gợi ý tự động (TEXT/IMAGE/TABLE) nhưng giữ vùng tự vẽ.
    replace_auto: bool = False
    # Xoá cả vùng tự vẽ, chỉ giữ container slide_n rồi tạo lại các vùng gợi ý.
    reset_all: bool = False


class AoiUiComponentIn(CamelModel):
    code: str = Field(min_length=1, max_length=64, pattern=AOI_CODE_PATTERN)
    name: str = Field(min_length=1, max_length=100)


class AoiUiGenerateIn(CamelModel):
    components: list[AoiUiComponentIn] = Field(default_factory=list, max_length=200)
    merge: bool = True


class AoiSetOut(CamelModel):
    id: str
    scope: str
    slide_version_id: str | None = None
    ui_schema_version: str | None = None
    revision: int
    state: str
    created_by: str
    created_at: datetime
    published_at: datetime | None = None
    definitions: list[AoiDefinitionOut] = Field(default_factory=list)


class AnalysisRunOut(CamelModel):
    id: str
    session_id: str
    presentation_id: str | None = None
    aoi_set_id: str
    from_time: datetime
    to_time: datetime
    batch_watermark: str | None = None
    algorithm_version: str
    status: str
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class PresentationMetricOut(CamelModel):
    presentation_id: str
    algorithm_version: str
    batch_watermark: str | None = None
    sample_count: int
    on_slide_count: int
    dwell_ms: int
    fixation_count: int
    heatmap_grid: list
    computed_at: datetime


class AnalysisRunResultOut(CamelModel):
    run: AnalysisRunOut
    hit_count: int = 0
    metrics: list[PresentationMetricOut] = Field(default_factory=list)


class AoiRebuildIn(CamelModel):
    course_id: str
    lesson_id: str | None = None
    from_time: datetime | None = None
    to_time: datetime | None = None
    algorithm_version: str = Field(default="gaze-metrics-v1", max_length=64)


class AoiRebuildOut(CamelModel):
    ok: bool = True
    runs: int = 0
    completed: int = 0
    failed: int = 0
