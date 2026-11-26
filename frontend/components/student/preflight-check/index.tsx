"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { checkFace } from "@/lib/api/calibration";
import { useCourseOutline } from "@/hooks/use-student";
import { CameraCheck } from "./camera-check";
import { NoCalibrationView } from "./no-calibration-view";
import { PreflightHeader } from "./preflight-header";
import { StatusPanel } from "./status-panel";
import {
  getCalibrationHref,
  getLearningHref,
  getPrimaryLabel,
  isReadyToCalibrate,
} from "./preflight-helpers";
import type { CameraState, FaceState } from "./preflight-types";

export function PreflightCheck({
  courseId,
}: {
  courseId: string;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const lessonId = searchParams.get("lesson");
  const { data: course } = useCourseOutline(courseId);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [cameraState, setCameraState] = useState<CameraState>("idle");
  const [faceState, setFaceState] = useState<FaceState>("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  const learningHref = useMemo(
    () => getLearningHref(courseId, lessonId),
    [courseId, lessonId],
  );

  const calibrationHref = useMemo(
    () => getCalibrationHref(courseId, lessonId),
    [courseId, lessonId],
  );

  const waitForVideo = useCallback(async () => {
    const video = videoRef.current;
    if (!video) return false;
    if (video.readyState >= 2 && video.videoWidth > 0) return true;
    return new Promise<boolean>((resolve) => {
      const timeout = window.setTimeout(() => resolve(false), 4500);
      const handleReady = () => {
        window.clearTimeout(timeout);
        resolve(video.videoWidth > 0 && video.videoHeight > 0);
      };
      video.addEventListener("loadeddata", handleReady, { once: true });
    });
  }, []);

  const captureFrame = useCallback((): Promise<Blob | null> => {
    const video = videoRef.current;
    if (!video || video.videoWidth === 0 || video.videoHeight === 0) return Promise.resolve(null);
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return Promise.resolve(null);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return new Promise((resolve) => canvas.toBlob((b) => resolve(b), "image/jpeg", 0.88));
  }, []);

  const checkCamera = useCallback(async () => {
    setCameraState("checking");
    setFaceState("checking");
    setError(null);
    streamRef.current?.getTracks().forEach((track) => track.stop());

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => undefined);
      }
      const videoReady = await waitForVideo();
      if (!videoReady) {
        setCameraState("error");
        setFaceState("idle");
        setError("Camera đã được cấp quyền nhưng chưa trả về hình ảnh. Hãy thử lại.");
        return;
      }
      setCameraState("ready");
      await new Promise((resolve) => window.setTimeout(resolve, 350));

      const frame = await captureFrame();
      if (!frame) {
        setFaceState("error");
        setError("Không lấy được khung hình từ camera. Hãy thử kiểm tra lại.");
        return;
      }
      const result = await checkFace(frame);
      if (result.ok) {
        setFaceState("ready");
        return;
      }
      if (result.error === "no_face") {
        setFaceState("not-found");
        setError("Chưa nhận diện được khuôn mặt. Hãy ngồi thẳng, nhìn vào màn hình và thử lại.");
        return;
      }
      setFaceState("error");
      setError(
        result.error === "invalid_image" || result.error === "network_error"
          ? "Dịch vụ ước lượng điểm nhìn chưa sẵn sàng. Hãy thử lại sau."
          : "Chưa thể kiểm tra khuôn mặt. Hãy thử lại.",
      );
    } catch (caught) {
      setCameraState("error");
      setFaceState("idle");
      setError(
        caught instanceof DOMException && caught.name === "NotAllowedError"
          ? "Bạn chưa cấp quyền camera cho Eyetracking. Hãy cho phép camera trong trình duyệt rồi thử lại."
          : "Không thể truy cập camera. Hãy kiểm tra thiết bị và quyền của trình duyệt.",
      );
    }
  }, [captureFrame, waitForVideo]);

  const readyToCalibrate = isReadyToCalibrate(cameraState, faceState);
  const checking = cameraState === "checking" || faceState === "checking";

  const handlePrimaryAction = () => {
    if (readyToCalibrate) {
      router.push(calibrationHref);
      return;
    }
    void checkCamera();
  };

  const primaryLabel = getPrimaryLabel({
    cameraState,
    faceState,
    readyToCalibrate,
  });

  // Khóa tắt bắt buộc hiệu chỉnh: vào thẳng, không bật camera/ghi gaze.
  if (course && course.requireCalibration === false) {
    return (
      <NoCalibrationView
        courseTitle={course.title}
        learningHref={learningHref}
      />
    );
  }

  return (
    <div className="mx-auto w-full max-w-5xl">
      <PreflightHeader courseTitle={course?.title} title="Kiểm tra camera" />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.72fr)] lg:items-stretch">
        <CameraCheck
          videoRef={videoRef}
          cameraState={cameraState}
          faceState={faceState}
        />
        <StatusPanel
          cameraState={cameraState}
          faceState={faceState}
          error={error}
          primaryLabel={primaryLabel}
          checking={checking}
          onPrimaryAction={handlePrimaryAction}
        />
      </div>
    </div>
  );
}
