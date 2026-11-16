"""Import toàn bộ model để SQLAlchemy resolve các relationship dạng chuỗi."""

from app.models.aoi import Aoi
from app.models.auth import AuthSession, User
from app.models.background_job import BackgroundJob
from app.models.calibration import GazeCalibration
from app.models.chat import ChatMessage, ChatSession
from app.models.course import (
    Course,
    CourseModule,
    CourseTeacher,
    Enrollment,
    Lesson,
    Slide,
)
from app.models.email_otp import EmailOtp
from app.models.gaze import (
    ContentView,
    CourseVisit,
    GazeSample,
    LearningSession,
    ViewLayout,
)
from app.models.media import MediaAsset
from app.models.metadata import AppMetadata
from app.models.profile import StudentProfile, TeacherProfile
from app.models.quiz import QuizAttempt

__all__ = [
    "Aoi",
    "AppMetadata",
    "AuthSession",
    "BackgroundJob",
    "ChatMessage",
    "ChatSession",
    "ContentView",
    "Course",
    "CourseModule",
    "CourseVisit",
    "CourseTeacher",
    "EmailOtp",
    "Enrollment",
    "GazeCalibration",
    "GazeSample",
    "LearningSession",
    "Lesson",
    "MediaAsset",
    "QuizAttempt",
    "Slide",
    "StudentProfile",
    "TeacherProfile",
    "User",
    "ViewLayout",
]
