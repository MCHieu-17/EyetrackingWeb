from pydantic import Field, model_validator

from app.schemas.common import CamelModel


class LearningSessionCreateIn(CamelModel):
    enrollment_id: str
    lesson_id: str
    device_fingerprint: str = Field(min_length=1, max_length=255)
    # Viewport lúc tạo phiên và viewport lúc calibration. Bắt buộc và phải bằng
    # nhau để tránh trường hợp người dùng bấm F11/zoom giữa chừng.
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
    course_version_item_id: str | None = None
    calibration_id: str | None = None
    quiz_attempt_id: str | None = None
    expires_at: str | None = None
    pipeline_version: str | None = None


class LearningSessionEndIn(CamelModel):
    status: str = Field(default="completed", pattern="^(completed|aborted)$")


class GazeSampleIn(CamelModel):
    # None = bài tập trắc nghiệm (không có slide).
    lesson_content_id: str | None = None
    # Toạ độ RAW theo viewport, có thể < 0 hoặc > 1 khi nhìn ra ngoài màn hình.
    # None khi face_detected=false.
    x: float | None = None
    y: float | None = None
    # Toạ độ theo ảnh slide (nếu map được). Dùng cho gaze_events/analytics cũ.
    slide_x: float | None = None
    slide_y: float | None = None
    face_detected: bool = True
    ts: float

    @model_validator(mode="after")
    def _coords_required_when_face(self):
        if self.face_detected and (self.x is None or self.y is None):
            raise ValueError("x/y bắt buộc khi faceDetected=true")
        return self


class GazeBatchIn(CamelModel):
    learning_session_id: str | None = None
    samples: list[GazeSampleIn] = Field(min_length=1)
    source: str | None = Field(default="real", pattern="^(real|simulated)$")
    # Bắt buộc: viewport hiện tại của trình duyệt. Backend so với viewport lúc
    # calibration của phiên; lệch → 409 viewport_mismatch.
    viewport_width_px: int = Field(gt=0)
    viewport_height_px: int = Field(gt=0)
    layout_snapshot_id: str | None = None
    layout_key: str | None = Field(default=None, max_length=64)


class GazeBatchOut(CamelModel):
    ok: bool = True
    inserted: int = 0


class OkOut(CamelModel):
    ok: bool = True


class PresentationCreateIn(CamelModel):
    lesson_version_slide_id: str | None = None
    surface: str = Field(pattern="^(lesson|quiz)$")
    sequence_no: int = Field(ge=0)


class PresentationOut(CamelModel):
    id: str
    session_id: str
    lesson_version_slide_id: str | None = None
    surface: str
    sequence_no: int
    started_at: str


class LayoutRectIn(CamelModel):
    semantic_code: str = Field(min_length=1, max_length=64)
    element_key: str = Field(default="", max_length=128)
    x_min: float
    y_min: float
    x_max: float
    y_max: float


class LayoutCreateIn(CamelModel):
    sequence_no: int = Field(ge=0)
    layout_generation: int = Field(ge=0)
    image_transform: dict = Field(default_factory=dict)
    rects: list[LayoutRectIn] = Field(default_factory=list)


class LayoutOut(CamelModel):
    id: str
    presentation_id: str
    layout_generation: int
    captured_at: str


class GazeSampleBatchIn(CamelModel):
    sequence: int = Field(ge=0)
    capture_monotonic_ns: int = Field(ge=0)
    event_time: str
    viewport_x: float | None = None
    viewport_y: float | None = None
    status: str = Field(pattern="^(ok|no_face|error|offscreen)$")
    quality_flags: dict = Field(default_factory=dict)


class GazeBatchCreateIn(CamelModel):
    batch_id: str
    batch_no: int = Field(ge=0)
    presentation_id: str
    layout_snapshot_id: str | None = None
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
