from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel


class CourseCreateIn(CamelModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    thumbnail_url: str | None = None
    status: str = Field(default="draft", pattern="^(draft|published|archived)$")
    # Hiển thị chấm điểm nhìn cho sinh viên (áp cho mọi bài giảng + bài tập).
    show_gaze_dot: bool = False
    # Bắt buộc kiểm tra camera + hiệu chỉnh trước khi vào học.
    require_calibration: bool = True


class CourseUpdateIn(CamelModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    thumbnail_url: str | None = None
    status: str | None = Field(default=None, pattern="^(draft|published|archived)$")
    show_gaze_dot: bool | None = None
    require_calibration: bool | None = None


class ModuleCreateIn(CamelModel):
    title: str = Field(min_length=1, max_length=255)


class ModuleItemRef(CamelModel):
    kind: str = Field(pattern="^(lesson|quiz)$")
    id: str


class ModuleItemsReorderIn(CamelModel):
    items: list[ModuleItemRef] = Field(min_length=1)


class LessonCreateIn(CamelModel):
    title: str = Field(min_length=1, max_length=255)


class LessonUpdateIn(CamelModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)


class CourseGazeDotIn(CamelModel):
    show_gaze_dot: bool


class CourseRequireCalibrationIn(CamelModel):
    require_calibration: bool


class StudentsAddIn(CamelModel):
    student_ids: list[str]


class StudentDirectoryOut(CamelModel):
    id: str
    name: str
    code: str
    email: str | None = None
    color: str


class LessonNodeOut(CamelModel):
    id: str
    title: str
    kind: str = "lesson"  # 'lesson' | 'quiz'
    slides: int
    # Trạng thái index RAG của các slide trong lesson hiện hành.
    slides_ready: int = 0
    slides_failed: int = 0
    slides_pending: int = 0
    attention: float | None = None
    mastery: float | None = None
    quiz_id: str | None = None
    quiz_status: str | None = None
    question_count: int = 0
    duration_minutes: int | None = None
    due_at: datetime | None = None


class ModuleNodeOut(CamelModel):
    id: str
    title: str
    lessons: list[LessonNodeOut]
    module_key: str | None = None
    generation: int | None = None


class TeacherCourseOut(CamelModel):
    id: str
    title: str
    description: str
    gradient: str
    status: str
    students: int
    attention: float | None = None
    sessions: int
    updated_at: datetime
    is_owner: bool = True
    lesson_count: int = 0
    show_gaze_dot: bool = False  # cờ cấp khóa: cho SV thấy chấm điểm nhìn
    require_calibration: bool = True  # cờ cấp khóa: bắt buộc hiệu chỉnh trước khi học


class LessonItemOut(CamelModel):
    id: str
    title: str
    kind: str = "lesson"  # 'lesson' | 'quiz'
    slide_count: int
    quiz_id: str | None = None
    quiz_status: str | None = None
    question_count: int = 0
    duration_minutes: int | None = None
    due_at: datetime | None = None


class ModuleItemOut(CamelModel):
    id: str
    order_index: int
    title: str
    lessons: list[LessonItemOut]


class CourseOutlineOut(CamelModel):
    id: str
    title: str
    modules: list[ModuleItemOut]
    # Cờ cấp khóa: SV thấy chấm điểm nhìn ở MỌI bài giảng và bài tập của khóa.
    show_gaze_dot: bool = False
    # Cờ cấp khóa: bắt buộc hiệu chỉnh trước khi vào học.
    require_calibration: bool = True


class CourseSummaryOut(CamelModel):
    id: str
    title: str
    thumbnail_url: str | None
    teacher_name: str
    module_count: int
    lesson_count: int
    gradient: str
    require_calibration: bool = True


class EnrolledCourseOut(CamelModel):
    enrollment_id: str
    enrolled_at: datetime
    status: str
    course: CourseSummaryOut


class SlideOut(CamelModel):
    id: str
    title: str
    pdf_url: str | None = None
    page_number: int = 1
    page_count: int = 1
    source_format: str | None = None


class SlideAdminOut(CamelModel):
    id: str
    order_index: int
    title: str
    pdf_url: str | None = None
    page_number: int = 1
    page_count: int = 1
    source_format: str | None = None
    embedding_status: str = "none"
    embedding_error: str | None = None


class SlideImportJobOut(CamelModel):
    id: str
    status: str
    filename: str
    page_count: int | None = None
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class StudentLessonOut(CamelModel):
    lesson_id: str
    attention: float | None = None
    mastery: float | None = None


class StudentRowOut(CamelModel):
    id: str
    name: str
    code: str
    color: str
    avatar_url: str | None = None
    attention: float | None = None
    last_active: str | None = None
    status: str
    lessons: list[StudentLessonOut]



