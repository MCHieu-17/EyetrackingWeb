"""Import toàn bộ model để `Base.metadata` đầy đủ cho schema tests.

Không import module này trong route; route import trực tiếp model cần dùng.
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
from app.models.auth import AuthSession, Role, User, UserRole
from app.models.calibration import Calibration, CalibrationSettings, Device
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
    "CalibrationSettings",
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
    "UserProfile",
    "UserRole",
]
