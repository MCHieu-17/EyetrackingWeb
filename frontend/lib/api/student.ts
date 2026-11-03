import { apiFetch } from "./client";
import type { EnrolledCourse, CourseOutline, Slide } from "@/lib/types/domain";

export interface LearningSession {
  id: string;
  enrollmentId: string;
  lessonId: string;
  deviceId: string;
  calibrated: boolean;
  status: string;
  trackingConsent: boolean;
  // first: lần đầu (tracking), continue: học tiếp phiên cũ (tracking).
  mode: "first" | "continue";
  viewportWidthPx?: number | null;
  viewportHeightPx?: number | null;
  calibrationWidthPx?: number | null;
  calibrationHeightPx?: number | null;
  devicePixelRatio?: number | null;
}

export interface CreateLearningSessionInput {
  enrollmentId: string;
  lessonId: string;
  deviceFingerprint: string;
  // Viewport lúc tạo phiên và viewport lúc calibration phải bằng nhau.
  viewportWidthPx: number;
  viewportHeightPx: number;
  calibrationWidthPx: number;
  calibrationHeightPx: number;
  devicePixelRatio: number;
  trackingConsent?: boolean;
}

const DEVICE_KEY = "gaze_device_fingerprint";

function randomFingerprint(): string {
  return `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function getDeviceFingerprint(): string {
  const existing = globalThis.localStorage?.getItem(DEVICE_KEY);
  if (existing) return existing;
  const fingerprint = randomFingerprint();
  globalThis.localStorage?.setItem(DEVICE_KEY, fingerprint);
  return fingerprint;
}

export interface GazeSample {
  /** null = bài tập trắc nghiệm (không có slide). */
  lessonContentId: string | null;
  /** Toạ độ RAW theo viewport, có thể < 0 hoặc > 1 khi nhìn ra ngoài màn hình. */
  x: number | null;
  y: number | null;
  /** Toạ độ theo ảnh slide (nếu map được). */
  slideX?: number | null;
  slideY?: number | null;
  /** false = AI service báo no_face; x/y sẽ được backend lưu NULL. */
  faceDetected: boolean;
  ts: number;
}

export interface GazeBatchMeta {
  viewportWidthPx: number;
  viewportHeightPx: number;
  layoutSnapshotId?: string | null;
  layoutKey?: string | null;
}

export function fetchMyEnrollments(): Promise<EnrolledCourse[]> {
  return apiFetch<EnrolledCourse[]>("/api/me/enrollments");
}

export function fetchCourseOutline(courseId: string): Promise<CourseOutline> {
  return apiFetch<CourseOutline>(`/api/courses/${courseId}`);
}

export function fetchLessonSlides(lessonId: string): Promise<Slide[]> {
  return apiFetch<Slide[]>(`/api/lessons/${lessonId}/contents`);
}

export function createLearningSession(input: CreateLearningSessionInput): Promise<LearningSession> {
  return apiFetch<LearningSession>("/api/learning-sessions", {
    method: "POST",
    body: input,
  });
}

// PATCH /api/learning-sessions/:id — đóng phiên khi đổi bài hoặc rời trang.
export function endLearningSession(
  sessionId: string,
  status: "completed" | "aborted" = "completed",
  keepalive = false,
): Promise<LearningSession> {
  return apiFetch<LearningSession>(`/api/learning-sessions/${sessionId}`, {
    method: "PATCH",
    body: { status },
    keepalive,
  });
}

export function postGazeSamples(
  lessonId: string,
  samples: GazeSample[],
  learningSessionId?: string,
  source: "real" | "simulated" = "real",
  keepalive = false,
  meta?: GazeBatchMeta,
): Promise<{ ok: boolean; inserted?: number }> {
  return apiFetch<{ ok: boolean; inserted?: number }>(`/api/lessons/${lessonId}/gaze-samples`, {
    method: "POST",
    body: {
      learningSessionId,
      samples,
      source,
      viewportWidthPx: meta?.viewportWidthPx ?? window.innerWidth,
      viewportHeightPx: meta?.viewportHeightPx ?? window.innerHeight,
      layoutSnapshotId: meta?.layoutSnapshotId ?? null,
      layoutKey: meta?.layoutKey ?? null,
    },
    keepalive,
  });
}
