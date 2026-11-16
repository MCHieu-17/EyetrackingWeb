import { apiFetch } from "./client";

export interface CourseVisit {
  id: string;
  enrollmentId: string;
  startedAt: string;
  endedAt: string | null;
  lastSeenAt: string;
  status: "active" | "ended" | "expired";
  visitKey: string | null;
}

export interface CourseVisitRow {
  id: string;
  enrollmentId: string;
  studentId: string;
  studentName: string;
  studentCode: string;
  courseId: string;
  startedAt: string;
  endedAt: string | null;
  lastSeenAt: string;
  status: "active" | "ended" | "expired";
  lessonSessionCount: number;
  gazeCount: number;
  onSlideGazeCount: number;
  trackedDurationMs: number;
}

export function createCourseVisit(input: {
  enrollmentId: string;
  visitKey?: string | null;
}): Promise<CourseVisit> {
  return apiFetch<CourseVisit>("/api/course-visits", {
    method: "POST",
    body: input,
  });
}

export function endCourseVisit(
  visitId: string,
  keepalive = false,
): Promise<CourseVisit> {
  return apiFetch<CourseVisit>(`/api/course-visits/${visitId}`, {
    method: "PATCH",
    body: { status: "ended" },
    keepalive,
  });
}

export function heartbeatCourseVisit(
  visitId: string,
): Promise<{ id: string; lastSeenAt: string }> {
  return apiFetch(`/api/course-visits/${visitId}/heartbeat`, {
    method: "POST",
  });
}

export function fetchStudentVisits(
  studentId: string,
  courseId: string,
): Promise<CourseVisitRow[]> {
  return apiFetch<CourseVisitRow[]>(`/api/teacher/students/${studentId}/visits`, {
    params: { courseId },
  });
}

export interface CourseVisitsQuery {
  studentId?: string;
  from?: string;
  to?: string;
  limit?: number;
}

export function fetchCourseVisits(
  courseId: string,
  query: CourseVisitsQuery = {},
): Promise<CourseVisitRow[]> {
  return apiFetch<CourseVisitRow[]>(`/api/teacher/courses/${courseId}/visits`, {
    params: {
      studentId: query.studentId,
      from: query.from,
      to: query.to,
      limit: query.limit ?? 1000,
    },
  });
}
