"""Import toàn bộ model để SQLAlchemy resolve được các relationship dạng chuỗi.

Module này được `app.db.session` import sớm, trước khi mapper được cấu hình.
Không import nó trong route; route import trực tiếp model cần dùng.
"""

from app.models.aoi import (
    AnalysisRun,
    AoiDefinition,
    AoiHit,
    AoiLayoutRect,
    AoiLayoutSnapshot,
    AoiSet,
    PresentationMetric,
)
from app.models.auth import AuthSession, Role, User, UserIdentity, UserRole
from app.models.calibration import Calibration, Device
from app.models.chat import ChatMessage, ChatSession
from app.models.course import (
    ContentAuditEvent,
    Course,
    CourseTeacher,
    CourseVersion,
    CourseVersionItem,
    CourseVersionModule,
    Enrollment,
    Lesson,
    LessonVersion,
    LessonVersionSlide,
    Slide,
    SlideVersion,
)
from app.models.embedding_job import EmbeddingJob
from app.models.gaze import (
    ContentPresentation,
    GazeBatch,
    GazeSample,
    LearningSession,
)
from app.models.media import MediaAsset, SlideDocument, SlideImportJob
from app.models.metadata import AppMetadata
from app.models.profile import StudentProfile, TeacherProfile, UserProfile
from app.models.quiz import QuizAttempt, QuizSpec

__all__ = [
    "AnalysisRun",
    "AoiDefinition",
    "AoiHit",
    "AoiLayoutRect",
    "AoiLayoutSnapshot",
    "AoiSet",
    "AppMetadata",
    "AuthSession",
    "Calibration",
    "ChatMessage",
    "ChatSession",
    "ContentAuditEvent",
    "ContentPresentation",
    "Course",
    "CourseTeacher",
    "CourseVersion",
    "CourseVersionItem",
    "CourseVersionModule",
    "Device",
    "EmbeddingJob",
    "Enrollment",
    "GazeBatch",
    "GazeSample",
    "LearningSession",
    "Lesson",
    "LessonVersion",
    "LessonVersionSlide",
    "MediaAsset",
    "PresentationMetric",
    "QuizAttempt",
    "QuizSpec",
    "Role",
    "Slide",
    "SlideDocument",
    "SlideImportJob",
    "SlideVersion",
    "StudentProfile",
    "TeacherProfile",
    "User",
    "UserIdentity",
    "UserProfile",
    "UserRole",
]
