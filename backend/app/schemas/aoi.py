from datetime import datetime

from pydantic import Field, model_validator

from app.schemas.common import CamelModel


class AoiDefinitionIn(CamelModel):
    code: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
    )
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    scope: str = Field(default="viewport", pattern="^(viewport|slide)$")
    parent_id: str | None = None
    selector: str | None = Field(default=None, max_length=255)
    lesson_content_id: str | None = None
    is_active: bool = True
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _scope_content(self):
        if (self.scope == "slide") != (self.lesson_content_id is not None):
            raise ValueError("scope='slide' phải có lessonContentId và ngược lại")
        return self


class AoiDefinitionUpdate(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    parent_id: str | None = None
    selector: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    metadata: dict | None = None


class AoiDefinitionOut(CamelModel):
    id: str
    code: str
    name: str
    description: str | None = None
    scope: str
    parent_id: str | None = None
    selector: str | None = None
    lesson_content_id: str | None = None
    is_active: bool
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class AoiRectIn(CamelModel):
    code: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9-]*$",
    )
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @model_validator(mode="after")
    def _valid_rect(self):
        if not (0.0 <= self.x_min < self.x_max <= 1.0):
            raise ValueError("xMin/xMax phải trong [0,1] và xMin < xMax")
        if not (0.0 <= self.y_min < self.y_max <= 1.0):
            raise ValueError("yMin/yMax phải trong [0,1] và yMin < yMax")
        return self


class AoiLayoutSnapshotIn(CamelModel):
    viewport_width_px: int = Field(gt=0)
    viewport_height_px: int = Field(gt=0)
    layout_key: str | None = Field(default=None, max_length=64)
    rects: list[AoiRectIn] = Field(default_factory=list, max_length=500)


class AoiLayoutSnapshotOut(CamelModel):
    id: str
    captured_at: datetime


class AoiRebuildIn(CamelModel):
    session_id: str | None = None
    lesson_id: str | None = None
    course_id: str | None = None
    from_time: datetime | None = None
    to_time: datetime | None = None


class AoiRebuildOut(CamelModel):
    ok: bool = True
    inserted: int = 0
