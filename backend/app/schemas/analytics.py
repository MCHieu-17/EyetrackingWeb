from pydantic import Field

from app.schemas.common import CamelModel


class HotspotOut(CamelModel):
    x: float
    y: float
    r: float
    w: float


class HeatmapAoiOut(CamelModel):
    id: str
    name: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    source: str


class SlideStatOut(CamelModel):
    idx: int
    on_slide: float
    fixations: int
    view_sec: float
    hotspots: list[HotspotOut]
    points: list[list[float]]
    aois: list[HeatmapAoiOut] = Field(default_factory=list)



