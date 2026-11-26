import type { CameraState, FaceState } from "./preflight-types";

export function getLearningHref(
  courseId: string,
  lessonId: string | null,
): string {
  const q = lessonId ? `?lesson=${encodeURIComponent(lessonId)}` : "";
  return `/student/courses/${courseId}${q}`;
}

export function getCalibrationHref(
  courseId: string,
  lessonId: string | null,
): string {
  const q = lessonId ? `?lesson=${encodeURIComponent(lessonId)}` : "";
  return `/student/courses/${courseId}/calibrate${q}`;
}

export function isReadyToCalibrate(
  cameraState: CameraState,
  faceState: FaceState,
): boolean {
  return cameraState === "ready" && faceState === "ready";
}

export function getPrimaryLabel({
  cameraState,
  faceState,
  readyToCalibrate,
}: {
  cameraState: CameraState;
  faceState: FaceState;
  readyToCalibrate: boolean;
}): string {
  if (cameraState === "checking" || faceState === "checking") {
    return "Đang kiểm tra camera…";
  }
  if (readyToCalibrate) return "Hiệu chỉnh điểm nhìn";
  if (
    cameraState === "error" ||
    faceState === "not-found" ||
    faceState === "error"
  ) {
    return "Kiểm tra lại";
  }
  return "Kiểm tra camera";
}

export function getCameraStatus(cameraState: CameraState): string {
  if (cameraState === "checking") return "Đang kiểm tra";
  if (cameraState === "ready") return "Sẵn sàng";
  if (cameraState === "error") return "Có lỗi";
  return "Chưa kiểm tra";
}

export function getFaceStatus(faceState: FaceState): string {
  if (faceState === "checking") return "Đang nhận diện";
  if (faceState === "ready") return "Đã phát hiện";
  if (faceState === "not-found") return "Chưa phát hiện";
  if (faceState === "error") return "Có lỗi";
  return "Chưa kiểm tra";
}
