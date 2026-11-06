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
  courseVersionItemId?: string | null;
  calibrationId?: string | null;
  quizAttemptId?: string | null;
  expiresAt?: string | null;
  pipelineVersion?: string | null;
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
  quizAttemptId?: string | null;
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
  sequence: number;
  captureMonotonicNs: number;
  eventTime: string;
  viewportX: number | null;
  viewportY: number | null;
  status: "ok" | "no_face" | "error" | "offscreen";
  qualityFlags?: Record<string, unknown>;
}

export interface GazeBatchInput {
  batchId: string;
  batchNo: number;
  presentationId: string;
  layoutSnapshotId?: string | null;
  sequenceStart: number;
  sequenceEnd: number;
  payloadHash: string;
  samples: GazeSample[];
}

export interface GazeBatchAck {
  ok: boolean;
  batchId: string;
  received: number;
  stored: number;
  duplicate: number;
  rejected: number;
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

export function fetchSessionContents(sessionId: string): Promise<Slide[]> {
  return apiFetch<Slide[]>(`/api/learning-sessions/${sessionId}/contents`);
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

export function postGazeBatch(
  sessionId: string,
  input: GazeBatchInput,
  keepalive = false,
): Promise<GazeBatchAck> {
  return apiFetch<GazeBatchAck>(
    `/api/learning-sessions/${sessionId}/gaze-batches`,
    { method: "POST", body: input, keepalive },
  );
}
