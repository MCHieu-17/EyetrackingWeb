import type { AdminDbTableRowsParams } from "@/lib/api/admin-db";
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
    dbSchema: ["admin", "db", "schema"] as const,
    dbTableRows: (params: AdminDbTableRowsParams | null) =>
      ["admin", "db", "table-rows", params] as const,
  },
  aoi: {
    root: ["aois"] as const,
    slide: (slideId: string | null) => ["aois", "slide", slideId] as const,
    ui: (uiSchema: string) => ["aois", "ui", uiSchema] as const,
  },
  config: {
    runtime: ["config", "runtime"] as const,
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
    studentVisits: (courseId: string, studentId: string) =>
      ["teacher", "student-visits", courseId, studentId] as const,
  },
  visualization: {
    courseVisits: (courseId: string, query: unknown = {}) =>
      ["visualization", "course-visits", courseId, query] as const,
    visitReplay: (visitId: string) =>
      ["visualization", "visit-replay", visitId] as const,
    replaySamples: (visitId: string, contentViewId: string) =>
      ["visualization", "replay-samples", visitId, contentViewId] as const,
    aoiSummary: (courseId: string, query: unknown) =>
      ["visualization", "aoi-summary", courseId, query] as const,
    aoiHeatmap: (courseId: string, query: unknown) =>
      ["visualization", "aoi-heatmap", courseId, query] as const,
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
