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

export interface VisitGazeSample {
  id: number;
  eventTime: string;
  sequence: number;
  contentViewId: string;
  sessionId: string;
  lessonId: string;
  lessonTitle: string;
  slideId: string | null;
  slideTitle: string | null;
  pageNumber: number | null;
  viewportX: number | null;
  viewportY: number | null;
  originalViewportX: number | null;
  originalViewportY: number | null;
  slideX: number | null;
  slideY: number | null;
  aoiLabel: string | null;
  aoiCodes: string[];
  status: string;
  qualityFlags: Record<string, unknown>;
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

export function fetchActiveCourseVisit(
  enrollmentId: string,
): Promise<CourseVisit | null> {
  return apiFetch<CourseVisit | null>("/api/course-visits/active", {
    params: { enrollmentId },
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

export function fetchCourseVisits(
  courseId: string,
  params: {
    studentId?: string;
    from?: string;
    to?: string;
    limit?: number;
    offset?: number;
  } = {},
): Promise<CourseVisitRow[]> {
  return apiFetch<CourseVisitRow[]>(
    `/api/teacher/courses/${courseId}/visits`,
    { params },
  );
}

export function fetchStudentVisits(
  studentId: string,
  courseId: string,
): Promise<CourseVisitRow[]> {
  return apiFetch<CourseVisitRow[]>(`/api/teacher/students/${studentId}/visits`, {
    params: { courseId },
  });
}

export function fetchVisitGaze(
  visitId: string,
  params: { slideId?: string; aoiCode?: string; limit?: number; offset?: number } = {},
): Promise<VisitGazeSample[]> {
  return apiFetch<VisitGazeSample[]>(`/api/teacher/visits/${visitId}/gaze`, {
    params,
  });
}
