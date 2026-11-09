import { MY_PROFILE_QUERY_KEY } from "@/lib/api/profile";
import type { CourseListQuery } from "@/lib/api/teacher";

/**
 * Nguồn duy nhất cho query key của TanStack Query.
 *
 * Factory trả về mảng ổn định (cùng input → cùng key) để cache và invalidate
 * khớp nhau. Các key `*Root` dùng để invalidate toàn bộ nhóm theo prefix.
 */
export const queryKeys = {
  admin: {
    studentsRoot: ["admin", "students"] as const,
    students: (query: string) => ["admin", "students", query] as const,
  },
  teacher: {
    coursesRoot: ["teacher", "courses"] as const,
    courses: (query: CourseListQuery = {}) => ["teacher", "courses", query] as const,
    courseTree: (courseId: string) => ["teacher", "course-tree", courseId] as const,
    courseStudents: (courseId: string) =>
      ["teacher", "course-students", courseId] as const,
    lessonSlides: (lessonId: string) =>
      ["teacher", "lesson-slides", lessonId] as const,
    studentDirectory: (query: string) =>
      ["teacher", "student-directory", query] as const,
  },
  student: {
    enrollments: ["student", "enrollments"] as const,
    courseOutline: (courseId: string) =>
      ["student", "course-outline", courseId] as const,
    lessonSlides: (lessonId: string, sessionId?: string | null) =>
      ["student", "lesson-slides", lessonId, sessionId ?? null] as const,
  },
  quiz: {
    assignment: (id: string) => ["quiz", "assignment", id] as const,
    attempt: (lessonId: string | undefined) =>
      ["quiz", "attempt", lessonId] as const,
  },
  chat: {
    sessionsRoot: ["chat", "sessions"] as const,
    sessions: (
      courseId: string | null,
      assignmentId?: string | null,
      attemptId?: string | null,
    ) =>
      ["chat", "sessions", courseId, assignmentId ?? null, attemptId ?? null] as const,
    messages: (sessionId: string | null) =>
      ["chat", "messages", sessionId] as const,
    access: (courseId: string) => ["chat", "access", courseId] as const,
  },
  profile: MY_PROFILE_QUERY_KEY,
  authUser: ["auth", "user"] as const,
} as const;
