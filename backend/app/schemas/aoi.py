from datetime import datetime

from pydantic import Field, model_validator

from app.schemas.common import CamelModel


class AoiDefinitionIn(CamelModel):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=100)
    parent_id: str | None = None
    geometry: dict = Field(default_factory=dict)


class AoiDefinitionOut(CamelModel):
    id: str
    code: str
    name: str
    parent_id: str | None = None
    geometry: dict = Field(default_factory=dict)


class AoiSetCreateIn(CamelModel):
    scope: str = Field(pattern="^(slide|ui)$")
    slide_version_id: str | None = None
    ui_schema_version: str | None = Field(default=None, max_length=64)
    definitions: list[AoiDefinitionIn] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def _scope_target(self):
        if (self.scope == "slide") != (self.slide_version_id is not None):
            raise ValueError("scope='slide' phải có slideVersionId và ngược lại")
        if (self.scope == "ui") != (self.ui_schema_version is not None):
            raise ValueError("scope='ui' phải có uiSchemaVersion và ngược lại")
        return self


class AoiSetUpdateIn(CamelModel):
    definitions: list[AoiDefinitionIn] = Field(default_factory=list, max_length=500)


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


class AoiSetPublishOut(CamelModel):
    ok: bool = True
    id: str
    state: str


class AnalysisRunCreateIn(CamelModel):
    session_id: str
    aoi_set_id: str
    from_time: datetime
    to_time: datetime
    algorithm_version: str = Field(default="gaze-metrics-v1", max_length=64)
    config: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _time_range(self):
        if self.to_time <= self.from_time:
            raise ValueError("toTime phải sau fromTime")
        return self


class AnalysisRunOut(CamelModel):
    id: str
    session_id: str
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
    from_time: datetime | None = None
    to_time: datetime | None = None
    algorithm_version: str = Field(default="gaze-metrics-v1", max_length=64)


class AoiRebuildOut(CamelModel):
    ok: bool = True
    runs: int = 0
    completed: int = 0
    failed: int = 0
