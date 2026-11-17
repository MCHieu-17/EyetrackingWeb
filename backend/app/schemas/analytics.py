from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel


class CourseVisitRowOut(CamelModel):
    id: str
    enrollment_id: str
    student_id: str
    student_name: str
    student_code: str = ""
    course_id: str
    started_at: str
    ended_at: str | None = None
    last_seen_at: str
    status: str
    lesson_session_count: int = 0
    gaze_count: int = 0
    on_slide_gaze_count: int = 0
    tracked_duration_ms: int = 0


class VisitGazeSampleOut(CamelModel):
    id: int
    event_time: str
    sequence: int
    content_view_id: str
    session_id: str
    lesson_id: str
    lesson_title: str
    slide_id: str | None = None
    slide_title: str | None = None
    page_number: int | None = None
    viewport_x: float | None = None
    viewport_y: float | None = None
    slide_x: float | None = None
    slide_y: float | None = None
    aoi_label: str | None = None
    status: str
    quality_flags: dict = {}


class VisitSummaryOut(CamelModel):
    visit_id: str
    enrollment_id: str
    student_id: str
    course_id: str
    started_at: str
    ended_at: str | None = None
    status: str
    lesson_session_count: int = 0
    content_view_count: int = 0
    gaze_count: int = 0
    on_slide_gaze_count: int = 0
    tracked_duration_ms: int = 0
    fixation_count: int = 0
    # Ngưỡng dwell (wall time) để phân loại lượt xem `counted`.
    min_dwell_ms: int = 1000
    # Số lượt xem ngắn hơn ngưỡng trong toàn bộ ca, kể cả khi đã ẩn.
    short_view_count: int = 0


class ReplayRectOut(CamelModel):
    x_min: float
    y_min: float
    x_max: float
    y_max: float


class ReplaySlideAoiOut(CamelModel):
    code: str
    name: str
    analysis_label: str | None = None
    kind: str = "custom"
    is_container: bool = False
    is_active: bool = True
    rects: list[ReplayRectOut] = []


class ReplayUiRegionOut(CamelModel):
    code: str
    name: str
    kind: str = "ui"
    label: str | None = None
    is_active: bool = True
    rects: list[ReplayRectOut] = []


class ReplayLayoutOut(CamelModel):
    id: str
    layout_no: int
    slide_rect: dict = {}
    captured_at: str
    ui_regions: list[ReplayUiRegionOut] = []


class ReplayViewportOut(CamelModel):
    width: int | None = None
    height: int | None = None


class ReplayAoiStatOut(CamelModel):
    label: str
    name: str
    domain: str
    duration_ms: int = 0
    sample_count: int = 0


class ReplayViewOut(CamelModel):
    content_view_id: str
    sequence_no: int
    surface: str
    session_id: str
    lesson_id: str
    lesson_title: str
    lesson_kind: str
    slide_id: str | None = None
    slide_title: str | None = None
    page_number: int | None = None
    pdf_url: str | None = None
    started_at: str
    ended_at: str | None = None
    first_sample_at: str | None = None
    last_sample_at: str | None = None
    sample_count: int = 0
    ok_sample_count: int = 0
    gaze_count: int = 0
    on_slide_gaze_count: int = 0
    tracked_duration_ms: int = 0
    # Dwell wall time của lượt xem; không phụ thuộc số sample gaze.
    dwell_ms: int = 0
    # `dwell_ms >= CONTENT_VIEW_MIN_DWELL_MS`.
    counted: bool = True
    analysis_status: str = "pending"
    analysis_version: str = ""
    viewport: ReplayViewportOut
    slide_aois: list[ReplaySlideAoiOut] = []
    layouts: list[ReplayLayoutOut] = []
    aoi_stats: list[ReplayAoiStatOut] = []


class ReplayStudentOut(CamelModel):
    id: str
    name: str
    code: str = ""
    email: str | None = None
    enrollment_status: str = "active"


class ReplayCourseOut(CamelModel):
    id: str
    title: str


class VisitReplayOut(CamelModel):
    visit: VisitSummaryOut
    student: ReplayStudentOut
    course: ReplayCourseOut
    views: list[ReplayViewOut] = []
    ui_aois: list[dict] = []


class ReplaySampleOut(CamelModel):
    id: int
    offset_ms: int
    event_time: str
    sequence: int
    layout_id: str | None = None
    status: str
    viewport_x: float | None = None
    viewport_y: float | None = None
    slide_x: float | None = None
    slide_y: float | None = None
    aoi_label: str | None = None
    quality_flags: dict = {}


class ReplaySampleCursorOut(CamelModel):
    after_time: str
    after_id: int


class ReplaySamplesPageOut(CamelModel):
    content_view_id: str
    samples: list[ReplaySampleOut] = []
    next_cursor: ReplaySampleCursorOut | None = None


class AoiSummaryIn(CamelModel):
    student_ids: list[str] = []
    visit_ids: list[str] = []
    lesson_ids: list[str] = []
    from_time: datetime | None = Field(default=None, alias="from")
    to_time: datetime | None = Field(default=None, alias="to")
    surface: str = Field(default="all", pattern="^(all|lesson|quiz)$")
    include_dropped: bool = False
    # Mặc định trả mọi lượt xem; false chỉ tính lượt >= ngưỡng dwell.
    include_short: bool = True


class AoiSummaryTotalsOut(CamelModel):
    visit_count: int = 0
    student_count: int = 0
    content_view_count: int = 0
    gaze_sample_count: int = 0
    on_slide_gaze_count: int = 0
    tracked_duration_ms: int = 0
    labeled_duration_ms: int = 0
    slide_duration_ms: int = 0
    ui_duration_ms: int = 0
    unmapped_duration_ms: int = 0
    unlabeled_duration_ms: int = 0


class AoiSummaryAoiOut(CamelModel):
    label: str
    name: str
    domain: str
    duration_ms: int = 0
    sample_count: int = 0
    share: float = 0.0
    student_count: int = 0
    slide_count: int = 0
    mixed_slides: bool = False
    is_unlabeled: bool = False


class AoiSummaryLessonOut(CamelModel):
    lesson_id: str
    lesson_title: str
    lesson_kind: str
    duration_ms: int = 0
    sample_count: int = 0
    aois: list[AoiSummaryAoiOut] = []


class AoiSummarySlideOut(CamelModel):
    slide_id: str
    slide_title: str
    lesson_id: str
    lesson_title: str
    page_number: int | None = None
    duration_ms: int = 0
    sample_count: int = 0
    aois: list[AoiSummaryAoiOut] = []


class AoiSummaryStudentOut(CamelModel):
    student_id: str
    student_name: str
    student_code: str = ""
    enrollment_status: str = "active"
    duration_ms: int = 0
    sample_count: int = 0
    aois: list[AoiSummaryAoiOut] = []


class AoiSummaryVisitOut(CamelModel):
    visit_id: str
    student_id: str
    student_name: str
    started_at: str
    duration_ms: int = 0
    tracked_duration_ms: int = 0
    slide_duration_ms: int = 0
    ui_duration_ms: int = 0
    unlabeled_duration_ms: int = 0
    sample_count: int = 0


class AoiSummaryMetaOut(CamelModel):
    stale_view_count: int = 0
    analysis_version: str = ""
    include_dropped: bool = False
    include_short: bool = True
    short_view_count: int = 0
    min_dwell_ms: int = 1000
    max_gap_ms: int = 250


class AoiSummaryOut(CamelModel):
    totals: AoiSummaryTotalsOut
    by_aoi: list[AoiSummaryAoiOut] = []
    by_lesson: list[AoiSummaryLessonOut] = []
    by_slide: list[AoiSummarySlideOut] = []
    by_student: list[AoiSummaryStudentOut] = []
    by_visit: list[AoiSummaryVisitOut] = []
    meta: AoiSummaryMetaOut


class AoiHeatmapIn(AoiSummaryIn):
    slide_id: str


class AoiHeatmapSlideOut(CamelModel):
    id: str
    title: str
    page_number: int
    pdf_url: str | None = None
    lesson_title: str


class AoiHeatmapOut(CamelModel):
    slide: AoiHeatmapSlideOut
    grid: list[list[int]]
    max: int = 0
    on_slide_sample_count: int = 0
    analyzed_view_count: int = 0
    stale_view_count: int = 0
