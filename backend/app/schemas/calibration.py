from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel


class CalibrationOut(CamelModel):
    id: str
    num_points: int
    device_fingerprint: str
    valid_from: datetime
    viewport_width_px: int | None = None
    viewport_height_px: int | None = None
    device_pixel_ratio: float | None = None
    screen_x_px: int | None = None
    screen_y_px: int | None = None
    model_version: str | None = None


class CalibrationActiveOut(CamelModel):
    calibrated: bool = True
    calibrated_at: datetime
    calibration_id: str | None = None
    viewport_width_px: int | None = None
    viewport_height_px: int | None = None
    device_pixel_ratio: float | None = None
    screen_x_px: int | None = None
    screen_y_px: int | None = None
    model_version: str | None = None


class CalibrationModelOut(CamelModel):
    model_ubj_base64: str
    model_version: str | None = None
    model_hash: str | None = None


class CalibrationCreateIn(CamelModel):
    device_fingerprint: str = Field(min_length=1, max_length=255)
    num_points: int = Field(ge=1, le=64)
    model_ubj_base64: str = Field(min_length=1)
    screen_width_px: int | None = None
    screen_height_px: int | None = None
    viewport_width_px: int | None = None
    viewport_height_px: int | None = None
    device_pixel_ratio: float | None = Field(default=None, gt=0)
    # Toạ độ viewport trên màn hình lúc calibration, dùng để quy đổi gaze khi
    # người học zoom/resize/move cửa sổ mà không phải hiệu chỉnh lại.
    screen_x_px: int | None = None
    screen_y_px: int | None = None
