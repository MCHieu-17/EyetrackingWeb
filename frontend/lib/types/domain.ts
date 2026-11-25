// lib/types/domain.ts — Type domain dùng chung phía frontend.
// Khớp schema generation 13: courses / course_modules / lessons / slides /
// enrollments / learning_sessions / content_views / gaze_samples.

export type CourseStatus = 'draft' | 'published' | 'archived';
export type EnrollStatus = 'active' | 'completed' | 'dropped';
type LessonKind = 'lesson' | 'quiz';

export interface TeacherCourse {
  id: string;
  title: string;
  description: string;
  gradient: string;          // thumbnail giả (prod: courses.thumbnail_url)
  status: CourseStatus;      // courses.status_id -> course_statuses.code
  students: number;          // count(enrollments)
  attention: number | null;  // điểm tập trung TB; null = chưa đủ dữ liệu gaze
  sessions: number;          // count(learning_sessions)
  updatedAt: string;
  isOwner?: boolean;          // admin hoặc chủ khóa học (quyền quản lý); false = GV được phân công
  lessonCount?: number;       // số bài giảng (item) trong khóa
  showGazeDot?: boolean;      // cờ cấp khóa: cho SV thấy chấm điểm nhìn (mọi bài giảng + bài tập)
  showCameraPreview?: boolean; // cờ cấp khóa: cho SV thấy khung xem trước camera
  requireCalibration?: boolean; // cờ cấp khóa: bắt buộc hiệu chỉnh trước khi vào học
}

export interface LessonNode {
  id: string;
  title: string;
  kind: LessonKind;          // 'lesson' (slide) hoặc 'quiz' (trắc nghiệm)
  slides: number;            // count(lesson_contents)
  /** Số slide đã index xong cho trợ lý học tập. */
  slidesReady?: number;
  /** Số slide index lỗi. */
  slidesFailed?: number;
  /** Số slide đang chờ index. */
  slidesPending?: number;
  quizId?: string | null;
  quizStatus?: QuizAssignmentStatus | null;
  questionCount?: number;
  durationMinutes?: number | null;
  dueAt?: string | null;
}

export interface ModuleNode {
  id: string;
  title: string;
  lessons: LessonNode[];
}

interface StudentLesson {
  lessonId: string;
  attention: number | null;
  mastery?: number | null;   // điểm hoàn thành (độ bao phủ nội dung)
}

export interface StudentRow {
  id: string;
  name: string;              // users.full_name
  code: string;              // student_profiles.student_code
  color: string;             // avatar giả
  avatarUrl?: string | null;  // users.avatar_url
  attention: number | null;  // null ⇔ learning_sessions.tracking_consent = false
  lastActive: string | null;  // null ⇔ chưa có phiên học nào
  status: EnrollStatus;
  lessons: StudentLesson[];
}

// Student (my-courses)

export interface EnrolledCourse {
  enrollmentId: string;
  enrolledAt: string;
  status: EnrollStatus;
  course: {
    id: string;
    title: string;
    thumbnailUrl: string | null;
    teacherName: string;
    moduleCount: number;
    lessonCount: number;
    gradient: string; // placeholder khi thumbnailUrl = null
    requireCalibration?: boolean; // false = vào học ngay, không cần camera/calibration
  };
}

// Student (course-learning)

export interface Slide {
  id: string;
  title: string;
  pdfUrl: string | null;
  pageNumber: number;
  pageCount: number;
  sourceFormat?: string | null;
}

// Slide + điểm hoàn thành theo độ bao phủ nội dung (teacher)

export interface SlideAdmin {
  id: string;
  orderIndex: number;
  title: string;
  pdfUrl: string | null;
  pageNumber: number;
  pageCount: number;
  sourceFormat?: string | null;
  /** Trạng thái ingest RAG: none | pending | ready | failed. */
  embeddingStatus?: "none" | "pending" | "ready" | "failed";
  embeddingError?: string | null;
}

export interface LessonItem {
  id: string;
  title: string;
  kind: LessonKind;
  slideCount: number;
  quizId?: string | null;
  quizStatus?: QuizAssignmentStatus | null;
  questionCount?: number;
  durationMinutes?: number | null;
  dueAt?: string | null;
}

export interface ModuleItem {
  id: string;
  orderIndex: number;
  title: string;
  lessons: LessonItem[];
}

export interface ModuleItemRef {
  kind: LessonKind;
  id: string;
}

export interface CourseOutline {
  id: string;
  title: string;
  modules: ModuleItem[];
  // Cờ cấp khóa: SV thấy chấm điểm nhìn ở mọi bài giảng VÀ bài tập của khóa.
  showGazeDot?: boolean;
  // Cờ cấp khóa: SV thấy khung xem trước camera trong lúc học.
  showCameraPreview?: boolean;
  // Cờ cấp khóa: bắt buộc hiệu chỉnh trước khi vào học.
  requireCalibration?: boolean;
}

// Profile (users + student_profiles/teacher_profiles)

export type GenderCode = 'male' | 'female' | 'other';

interface ProfileBase {
  email: string;               // users.email — email đăng nhập, read-only
  fullName: string;            // users.full_name
  dateOfBirth: string | null;  // users.date_of_birth (yyyy-mm-dd)
  gender: GenderCode | null;   // users.gender
  phone: string | null;        // users.phone
  avatarUrl: string | null;    // users.avatar_url
  createdAt: string;           // users.created_at
  hasPassword: boolean;        // false = đăng nhập bằng Outlook + OTP, không có mật khẩu GazeEdu
}

interface StudentProfile extends ProfileBase {
  role: 'student';
  studentCode: string;         // student_profiles.student_code — read-only
  program: string | null;      // student_profiles.program
}

interface TeacherProfile extends ProfileBase {
  role: 'teacher';
  teacherCode: string;         // teacher_profiles.teacher_code — read-only
  department: string | null;   // teacher_profiles.department
}

export type MyProfile = StudentProfile | TeacherProfile;

// Payload chỉnh sửa hồ sơ — email + mật khẩu cố tình không nằm trong đây.
export interface ProfileUpdate {
  fullName: string;
  dateOfBirth: string | null;
  gender: GenderCode | null;
  phone: string | null;
  avatarUrl: string | null;
  program?: string | null;     // chỉ student
  department?: string | null;  // chỉ teacher
}

export type QuizAssignmentStatus = 'draft' | 'published' | 'closed';

export interface QuizOption {
  id: string;
  text: string;
}

export interface QuizQuestion {
  id: string;
  prompt: string;
  options: QuizOption[];
  correctOptionIds: string[];   // một hoặc nhiều đáp án đúng (chấm tất cả-hoặc-không)
  allowMultiple: boolean;       // cho phép chọn nhiều đáp án
  explanation: string;
  points: number;
}

export interface QuizAssignment {
  id: string;
  courseId: string;
  courseTitle: string;
  lessonId?: string;
  lessonTitle?: string;
  title: string;
  instructions: string;
  dueAt: string | null;
  durationMinutes: number;
  status: QuizAssignmentStatus;
  createdAt: string;
  expiresAt?: string;
  allowChatbot?: boolean;
  allowRetry?: boolean;   // giáo viên cho phép học viên làm lại
  questions: QuizQuestion[];
}

export interface QuizAttempt {
  id: string;
  assignmentId: string;
  status?: "in_progress" | "submitted" | "expired";
  answers: Record<string, string[]>;
  submittedAt: string;
  score: number;
  maxScore: number;
}
