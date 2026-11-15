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
    original_viewport_x: float | None = None
    original_viewport_y: float | None = None
    slide_x: float | None = None
    slide_y: float | None = None
    aoi_label: str | None = None
    # Legacy: 0/1 phần tử sau reanalyze.
    aoi_codes: list[str] = []
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
