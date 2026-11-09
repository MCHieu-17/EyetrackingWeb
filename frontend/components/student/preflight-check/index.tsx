"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  checkFace,
  clearStoredGazeSession,
  fetchActiveCalibration,
  getGazeSessionStatus,
  getStoredCalibration,
  getStoredGazeSessionId,
  restoreGazeSessionFromBackend,
} from "@/lib/api/calibration";
import { getDeviceFingerprint } from "@/lib/api/student";
import { useCourseOutline } from "@/hooks/use-student";
import { formatDateTimeVN } from "@/lib/utils";
import { CameraCheck } from "./camera-check";
import { NoCalibrationView } from "./no-calibration-view";
import { PreflightHeader } from "./preflight-header";
import { StatusPanel } from "./status-panel";
import {
  getCalibrationAgeDays,
  getCalibrationHref,
  getLearningHref,
  getPrimaryLabel,
  isReadyToCalibrate,
  isReadyToLearn,
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
  const [isCalibrated, setIsCalibrated] = useState(false);
  const [calibratedAt, setCalibratedAt] = useState<string | null>(null);
  const [sessionIssue, setSessionIssue] = useState<string | null>(null);

  // Khóa tắt bắt buộc hiệu chỉnh -> không cần kiểm tra camera/calibration.
  const calibrationRequired = course?.requireCalibration !== false;

  useEffect(() => {
    if (!calibrationRequired) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void (async () => {
        const stored = getStoredCalibration();
        const sid = getStoredGazeSessionId();
        if (!sid) {
          const active = await fetchActiveCalibration(getDeviceFingerprint());
          if (cancelled) return;
          const ageDays = getCalibrationAgeDays(active?.calibratedAt);
          setIsCalibrated(false);
          setCalibratedAt(active?.calibrated && ageDays < 30 ? active.calibratedAt : null);
          setSessionIssue(
            active?.calibrated && ageDays < 30
              ? "Thiết bị có bản ghi hiệu chỉnh gần đây, nhưng không có phiên theo dõi cục bộ đang hoạt động. Vui lòng hiệu chỉnh lại để tạo phiên mới trước khi học."
              : "Không có phiên theo dõi cục bộ đang hoạt động. Vui lòng hiệu chỉnh điểm nhìn trước khi học.",
          );
          return;
        }
        const status = await getGazeSessionStatus(sid);
        if (cancelled) return;
        if (!status.ready) {
          const fp = getDeviceFingerprint();
          const active = await fetchActiveCalibration(fp);
          const ageDays = getCalibrationAgeDays(active?.calibratedAt);
          // Phiên cũ đã hết hạn trên gaze (TTL 30' hoặc service restart) nhưng
          // DB còn model .ubj: tạo session mới rồi nạp lại model, không bắt
          // người học hiệu chỉnh lại. Model dùng được với mọi viewport nhờ
          // phép quy đổi toạ độ ở useGazeTracker.
          if (active?.calibrated && ageDays < 30) {
            const restored = await restoreGazeSessionFromBackend(fp);
            if (cancelled) return;
            if (restored) {
              setIsCalibrated(true);
              setCalibratedAt(active.calibratedAt);
              setSessionIssue(null);
              return;
            }
          }
          if (active?.calibrated && active.calibratedAt && ageDays < 30) {
            clearStoredGazeSession();
            setIsCalibrated(false);
            setCalibratedAt(active.calibratedAt);
            setSessionIssue(
              "Thiết bị có bản ghi hiệu chỉnh trong 30 ngày, nhưng phiên theo dõi cục bộ không còn hoạt động. Vui lòng hiệu chỉnh lại để tạo phiên mới trước khi học.",
            );
            return;
          }
          clearStoredGazeSession();
          setIsCalibrated(false);
          setCalibratedAt(null);
          setSessionIssue(
            status.error === "network_error"
              ? "Không kết nối được dịch vụ theo dõi để kiểm tra phiên hiệu chỉnh — hãy hiệu chỉnh lại trước khi học."
              : "Phiên hiệu chỉnh cũ đã hết hạn trên máy chủ — vui lòng hiệu chỉnh lại trước khi học.",
          );
          return;
        }
        setIsCalibrated(true);
        setCalibratedAt(stored.calibratedAt);
        setSessionIssue(null);
      })();
    }, 0);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, [calibrationRequired]);

  const learningHref = useMemo(
    () => getLearningHref(courseId, lessonId),
    [courseId, lessonId],
  );

  const calibrationHref = useMemo(
    () => getCalibrationHref(courseId, lessonId),
    [courseId, lessonId],
  );

  const calibrationTime = calibratedAt ? formatDateTimeVN(calibratedAt) : null;

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
          ? "Bạn chưa cấp quyền camera cho GazeEdu. Hãy cho phép camera trong trình duyệt rồi thử lại."
          : "Không thể truy cập camera. Hãy kiểm tra thiết bị và quyền của trình duyệt.",
      );
    }
  }, [captureFrame, waitForVideo]);

  const readyToLearn = isReadyToLearn(cameraState, faceState, isCalibrated);
  const readyToCalibrate = isReadyToCalibrate(cameraState, faceState, isCalibrated);
  const checking = cameraState === "checking" || faceState === "checking";

  const handlePrimaryAction = () => {
    if (readyToLearn) {
      router.push(learningHref);
      return;
    }
    if (readyToCalibrate) {
      router.push(calibrationHref);
      return;
    }
    void checkCamera();
  };

  const primaryLabel = getPrimaryLabel({
    cameraState,
    faceState,
    readyToLearn,
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
    <div className="mx-auto w-full max-w-6xl pb-6">
      <PreflightHeader courseTitle={course?.title} />

      <div className="mb-7 max-w-2xl">
        <span className="inline-flex rounded-full bg-[#e8f1e6] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#52704f]">
          Kiểm tra trước phiên học
        </span>
        <h1 className="mt-4 text-3xl font-semibold tracking-[-0.035em] text-foreground sm:text-4xl">
          Thiết lập một vùng học ổn định.
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground sm:text-base">
          Giữ khuôn mặt trong khung, ánh sáng đều và nhìn thẳng vào màn hình để điểm nhìn được ghi nhận chính xác.
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.72fr)] lg:items-stretch">
        <CameraCheck
          videoRef={videoRef}
          cameraState={cameraState}
          faceState={faceState}
        />
        <StatusPanel
          cameraState={cameraState}
          faceState={faceState}
          isCalibrated={isCalibrated}
          calibrationTime={calibrationTime}
          error={error}
          sessionIssue={sessionIssue}
          primaryLabel={primaryLabel}
          readyToLearn={readyToLearn}
          checking={checking}
          onPrimaryAction={handlePrimaryAction}
          calibrationHref={calibrationHref}
        />
      </div>
    </div>
  );
}
