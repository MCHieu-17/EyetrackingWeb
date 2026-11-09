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

export function getCalibrationAgeDays(
  calibratedAt: string | null | undefined,
  now = Date.now(),
): number {
  if (!calibratedAt) return Number.POSITIVE_INFINITY;
  return (now - new Date(calibratedAt).getTime()) / 86400000;
}

export function isReadyToLearn(
  cameraState: CameraState,
  faceState: FaceState,
  isCalibrated: boolean,
): boolean {
  return cameraState === "ready" && faceState === "ready" && isCalibrated;
}

export function isReadyToCalibrate(
  cameraState: CameraState,
  faceState: FaceState,
  isCalibrated: boolean,
): boolean {
  return cameraState === "ready" && faceState === "ready" && !isCalibrated;
}

export function getPrimaryLabel({
  cameraState,
  faceState,
  readyToLearn,
  readyToCalibrate,
}: {
  cameraState: CameraState;
  faceState: FaceState;
  readyToLearn: boolean;
  readyToCalibrate: boolean;
}): string {
  if (cameraState === "checking" || faceState === "checking") {
    return "Đang kiểm tra camera…";
  }
  if (readyToLearn) return "Bắt đầu học";
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

export function getCalibrationDescription(
  isCalibrated: boolean,
  calibrationTime: string | null,
): string {
  if (isCalibrated) {
    return calibrationTime
      ? `Đã hiệu chỉnh trên thiết bị này lúc ${calibrationTime}.`
      : "Đã có dữ liệu hiệu chỉnh trên thiết bị này.";
  }
  return calibrationTime
    ? `Có bản ghi hiệu chỉnh lúc ${calibrationTime}, nhưng cần phiên cục bộ mới để theo dõi.`
    : "Cần tạo phiên hiệu chỉnh cục bộ trước khi bắt đầu theo dõi.";
}
