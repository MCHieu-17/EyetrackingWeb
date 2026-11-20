from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, Field

from app.schemas.common import CamelModel


class LearningSessionCreateIn(CamelModel):
    enrollment_id: str
    lesson_id: str
    course_visit_id: str | None = None
    device_fingerprint: str = Field(min_length=1, max_length=255)
    # Viewport lúc tạo phiên và viewport lúc calibration. Frontend quy đổi toạ
    # độ gaze từ viewport calibration sang viewport hiện tại khi cửa sổ
    # resize/move; zoom/fullscreen do display guard tạm dừng ghi gaze.
    viewport_width_px: int = Field(gt=0)
    viewport_height_px: int = Field(gt=0)
    calibration_width_px: int = Field(gt=0)
    calibration_height_px: int = Field(gt=0)
    device_pixel_ratio: float = Field(gt=0)
    tracking_consent: bool = True
    quiz_attempt_id: str | None = None


class LearningSessionOut(CamelModel):
    id: str
    enrollment_id: str
    lesson_id: str
    course_visit_id: str | None = None
    device_id: str
    # Đã có model calibration (.ubj) cho (user, device) → có thể stream gaze thật.
    calibrated: bool = False
    status: str
    tracking_consent: bool
    # first: lần đầu mở bài → tracking gaze.
    # continue: vào lại bài đã có phiên trước → ghi gaze vào phiên cũ.
    mode: str = "first"
    viewport_width_px: int | None = None
    viewport_height_px: int | None = None
    calibration_width_px: int | None = None
    calibration_height_px: int | None = None
    device_pixel_ratio: float | None = None
    calibration_id: str | None = None
    quiz_attempt_id: str | None = None
    expires_at: str | None = None
    pipeline_version: str | None = None


class LearningSessionEndIn(CamelModel):
    status: str = Field(default="completed", pattern="^(completed|aborted)$")


class PresentationCreateIn(CamelModel):
    # UUID do client sinh cho mỗi lần vào slide. Retry cùng UUID là idempotent;
    # UUID mới luôn tạo content_view mới kể cả khi quay lại slide cũ.
    client_presentation_id: UUID | None = None
    # Thời điểm thực tế client vào slide; server kẹp về [now - 5 phút, now].
    entered_at: datetime | None = None
    slide_id: str | None = None
    surface: str = Field(pattern="^(lesson|quiz)$")
    # Legacy: client cũ vẫn gửi sequenceNo. Bỏ trống thì server cấp max + 1.
    sequence_no: int | None = Field(default=None, ge=0)


class PresentationOut(CamelModel):
    id: str
    session_id: str
    slide_id: str | None = None
    surface: str
    sequence_no: int
    started_at: str


class LayoutRectIn(CamelModel):
    # Chấp nhận cả payload mới (`code`) và payload cũ (`semanticCode`).
    code: str = Field(
        min_length=1,
        max_length=64,
        validation_alias=AliasChoices("code", "semanticCode", "semantic_code"),
    )
    element_key: str = Field(default="", max_length=128)
    x_min: float
    y_min: float
    x_max: float
    y_max: float


class LayoutCreateIn(CamelModel):
    sequence_no: int = Field(ge=0)
    layout_generation: int = Field(ge=0)
    # Chỉ còn để phát hiện tab frontend cũ; payload mới không gửi field này.
    coordinate_space: str | None = Field(
        default=None, pattern="^(current-v1|original-v1)$"
    )
    image_transform: dict = Field(default_factory=dict)
    rects: list[LayoutRectIn] = Field(default_factory=list)


class LayoutOut(CamelModel):
    id: str
    presentation_id: str
    layout_generation: int
    captured_at: str


class GazeSampleBatchIn(CamelModel):
    sequence: int = Field(ge=0)
    event_time: str
    viewport_x: float | None = None
    viewport_y: float | None = None
    status: str = Field(pattern="^(ok|no_face|error|offscreen)$")
    quality_flags: dict = Field(default_factory=dict)


class GazeBatchCreateIn(CamelModel):
    batch_id: UUID
    presentation_id: str
    layout_id: str | None = None
    sequence_start: int = Field(ge=0)
    sequence_end: int = Field(ge=0)
    samples: list[GazeSampleBatchIn] = Field(min_length=1, max_length=2000)


class GazeBatchAckOut(CamelModel):
    ok: bool = True
    batch_id: str
    received: int
    stored: int
    duplicate: int
    rejected: int
