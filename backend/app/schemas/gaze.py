from pydantic import AliasChoices, Field

from app.schemas.common import CamelModel


class LearningSessionCreateIn(CamelModel):
    enrollment_id: str
    lesson_id: str
    course_visit_id: str | None = None
    device_fingerprint: str = Field(min_length=1, max_length=255)
    # Viewport lúc tạo phiên và viewport lúc calibration. Không cần bằng nhau:
    # frontend quy đổi toạ độ gaze từ viewport calibration sang viewport hiện
    # tại, nên zoom/resize/move cửa sổ không phải hiệu chỉnh lại.
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
    slide_id: str | None = None
    surface: str = Field(pattern="^(lesson|quiz)$")
    sequence_no: int = Field(ge=0)


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
    # current-v1: layout cũ theo viewport hiện tại.
    # original-v1: layout đã quy đổi về viewport gốc lúc calibration.
    coordinate_space: str = Field(
        default="current-v1", pattern="^(current-v1|original-v1)$"
    )
    visible_rect: dict = Field(default_factory=dict)
    image_transform: dict = Field(default_factory=dict)
    rects: list[LayoutRectIn] = Field(default_factory=list)


class LayoutOut(CamelModel):
    id: str
    presentation_id: str
    layout_generation: int
    coordinate_space: str = "current-v1"
    visible_rect: dict = Field(default_factory=dict)
    captured_at: str


class GazeSampleBatchIn(CamelModel):
    sequence: int = Field(ge=0)
    capture_monotonic_ns: int = Field(ge=0)
    event_time: str
    viewport_x: float | None = None
    viewport_y: float | None = None
    original_viewport_x: float | None = None
    original_viewport_y: float | None = None
    status: str = Field(pattern="^(ok|no_face|error|offscreen)$")
    quality_flags: dict = Field(default_factory=dict)


class GazeBatchCreateIn(CamelModel):
    batch_id: str
    batch_no: int = Field(ge=0)
    presentation_id: str
    layout_id: str | None = None
    sequence_start: int = Field(ge=0)
    sequence_end: int = Field(ge=0)
    payload_hash: str = Field(min_length=64, max_length=64)
    samples: list[GazeSampleBatchIn] = Field(min_length=1, max_length=2000)


class GazeBatchAckOut(CamelModel):
    ok: bool = True
    batch_id: str
    received: int
    stored: int
    duplicate: int
    rejected: int
