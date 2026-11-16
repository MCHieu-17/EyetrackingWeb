"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import {
  buildCalibrationPoints,
  bytesToBase64,
  calibrationMargins,
  clearStoredGazeSession,
  createGazeSession,
  deleteGazeSession,
  downloadGazeModel,
  saveCalibrationToBackend,
  storeGazeSession,
  submitCalibrationSample,
  trainGazeSession,
  type CalPoint,
} from "@/lib/api/calibration";
import { getDeviceFingerprint } from "@/lib/api/student";

const SAMPLES_PER_POINT = 1;
const MAX_CAPTURES_PER_POINT = 5;
const CAPTURE_GAP_MS = 100;

interface ViewportSize {
  width: number;
  height: number;
}

let frozenViewport: ViewportSize | null = null;

// Cố ý KHÔNG theo dõi resize: 25 điểm phải giữ nguyên trong suốt một phiên
// hiệu chỉnh, nếu không mô hình đã huấn luyện sẽ lệch với điểm đang hiển thị.
// Đọc một lần lúc mount rồi "đóng băng"; mount sau (đổi màn hình rồi vào lại)
// sẽ đọc lại kích thước mới.
function getViewportSnapshot(): ViewportSize | null {
  if (typeof window === "undefined") return null;
  if (frozenViewport === null) {
    frozenViewport = { width: window.innerWidth, height: window.innerHeight };
  }
  return frozenViewport;
}

function subscribeViewport(): () => void {
  return () => {
    frozenViewport = null;
  };
}

type CalibrationPhase = "idle" | "calibrating" | "sending" | "training";

export interface CalibrationEngine {
  points: CalPoint[];
  current: CalPoint;
  step: number;
  total: number;
  progress: number;
  phase: CalibrationPhase;
  busy: boolean;
  error: string | null;
  camOn: boolean;
  sessionReady: boolean;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  attachVideo: (el: HTMLVideoElement | null) => void;
  handleDotClick: () => Promise<void>;
  reset: () => void;
  retrain: () => Promise<void>;
}

const ERROR_TEXT: Record<string, string> = {
  no_face: "Không phát hiện khuôn mặt — hãy nhìn thẳng vào chấm đỏ rồi bấm lại.",
  invalid_image: "Ảnh webcam không hợp lệ — bấm lại.",
  no_camera: "Camera không khả dụng — hãy cho phép camera rồi tải lại trang.",
  network_error: "Không kết nối được dịch vụ AI — kiểm tra kết nối rồi bấm lại.",
  insufficient: "Chưa đủ mẫu cho điểm này — hãy bấm lại và giữ nhìn vào chấm.",
};

interface UseCalibrationOptions {
  /** Gọi khi train thành công. */
  onComplete: () => void;
  /** Lưu lên Postgres theo device (chỉ học viên). Mặc định true. */
  persistToBackend?: boolean;
  /**
   * Tạm dừng hiệu chỉnh (ví dụ display guard phát hiện zoom/fullscreen).
   * Khi pause: không tạo phiên mới, xoá phiên hiện tại và đưa về idle.
   * Khi unpause: tạo lại phiên từ đầu để không trộn mẫu của phiên cũ.
   */
  paused?: boolean;
}

export function useCalibration({
  onComplete,
  persistToBackend = true,
  paused = false,
}: UseCalibrationOptions): CalibrationEngine {
  // null khi còn render phía server / trước hydration → dùng margin mặc định.
  const viewport = useSyncExternalStore(subscribeViewport, getViewportSnapshot, () => null);
  const points = useMemo<CalPoint[]>(
    () =>
      buildCalibrationPoints(
        viewport ? calibrationMargins(viewport.width, viewport.height) : undefined,
      ),
    [viewport],
  );
  const total = points.length;

  const [idx, setIdx] = useState(0);
  const [phase, setPhase] = useState<CalibrationPhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [session, setSession] = useState<{
    id: string;
    epoch: number;
  } | null>(null);
  const [sessionNonce, setSessionNonce] = useState(0);
  // Mỗi lần pause tăng epoch: mọi phiên cũ lập tức không còn hợp lệ. Cách này
  // cho phép UI suy ra idle ngay trong render mà không setState trong effect.
  const [epoch, setEpoch] = useState(0);
  const [prevPaused, setPrevPaused] = useState(paused);

  if (paused !== prevPaused) {
    setPrevPaused(paused);
    if (paused) setEpoch((value) => value + 1);
  }

  const epochRef = useRef(epoch);
  useEffect(() => {
    epochRef.current = epoch;
  }, [epoch]);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [camOn, setCamOn] = useState(false);

  const attachVideo = useCallback((el: HTMLVideoElement | null) => {
    videoRef.current = el;
    if (el && streamRef.current && el.srcObject !== streamRef.current) {
      el.srcObject = streamRef.current;
      el.play().catch(() => undefined);
    }
  }, []);

  const onCompleteRef = useRef(onComplete);
  useEffect(() => {
    onCompleteRef.current = onComplete;
  });

  const pausedRef = useRef(paused);
  useEffect(() => {
    pausedRef.current = paused;
  }, [paused]);

  // Pause: xoá phiên đang có trên server. Chỉ side effect, không setState;
  // epoch đã tăng trong render nên phiên cũ không còn được coi là hợp lệ.
  useEffect(() => {
    if (!paused || !session) return;
    deleteGazeSession(session.id);
  }, [paused, session]);

  useEffect(() => {
    // Chỉ tạo phiên khi đã biết kích thước màn hình (tránh tạo phiên với điểm mặc định).
    // Pause (display guard) thì tuyệt đối không tạo phiên mới.
    if (!viewport || paused) return;
    let cancelled = false;
    createGazeSession(points)
      .then((res) => {
        if (cancelled) {
          if (res.ok && res.sessionId) deleteGazeSession(res.sessionId);
          return;
        }
        if (res.ok && res.sessionId) {
          setSession({ id: res.sessionId, epoch });
          setIdx(0);
          setError(null);
          setPhase("calibrating");
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [points, viewport, sessionNonce, paused, epoch]);

  useEffect(() => {
    let cancelled = false;
    navigator.mediaDevices
      ?.getUserMedia({ video: { facingMode: "user" }, audio: false })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play().catch(() => undefined);
        }
        setCamOn(true);
      })
      .catch(() => setCamOn(false));

    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const reset = useCallback(() => {
    if (session) deleteGazeSession(session.id);
    setSession(null);
    clearStoredGazeSession();
    setError(null);
    setIdx(0);
    setPhase("idle");
    setSessionNonce((v) => v + 1);
  }, [session]);

  const captureFrame = useCallback(async (): Promise<Blob | null> => {
    const video = videoRef.current;
    if (!video) return null;
    let waited = 0;
    while (video.videoWidth === 0 && waited < 1000) {
      await new Promise((resolve) => setTimeout(resolve, 50));
      waited += 50;
    }
    if (video.videoWidth === 0) return null;
    const scale = Math.min(1, 640 / video.videoWidth);
    const width = Math.round(video.videoWidth * scale);
    const height = Math.round(video.videoHeight * scale);
    let canvas = canvasRef.current;
    if (!canvas) {
      canvas = document.createElement("canvas");
      canvasRef.current = canvas;
    }
    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, width, height);
    return new Promise((resolve) => canvas!.toBlob((b) => resolve(b ?? null), "image/jpeg", 0.8));
  }, []);

  const finish = useCallback(async () => {
    const activeSession = session;
    if (
      !activeSession ||
      pausedRef.current ||
      activeSession.epoch !== epoch
    ) {
      return;
    }
    setPhase("training");
    const trained = await trainGazeSession(activeSession.id);
    // Guard có thể bật trong lúc train: không lưu model, không chuyển trang.
    if (
      pausedRef.current ||
      epochRef.current !== activeSession.epoch
    ) {
      return;
    }
    if (!trained.ok) {
      const message =
        trained.error === "insufficient_samples"
          ? `${ERROR_TEXT.insufficient} — sẽ làm lại từ đầu.`
          : trained.error === "network_error"
            ? "Không kết nối được dịch vụ AI khi huấn luyện — sẽ làm lại từ đầu."
            : "Không huấn luyện được bộ hiệu chỉnh — sẽ làm lại từ đầu.";
      reset();
      setError(message);
      return;
    }
    storeGazeSession(
      activeSession.id,
      window.innerWidth,
      window.innerHeight,
      window.screenX,
      window.screenY,
      window.devicePixelRatio || 1,
    );
    if (persistToBackend) {
      // Lưu model .ubj để lần sau khôi phục không cần hiệu chỉnh lại
      const model = await downloadGazeModel(activeSession.id);
      if (model) {
        await saveCalibrationToBackend({
          deviceFingerprint: getDeviceFingerprint(),
          numPoints: points.length,
          modelUbjBase64: bytesToBase64(model),
          screenWidth: window.innerWidth,
          screenHeight: window.innerHeight,
          screenX: window.screenX,
          screenY: window.screenY,
        });
      }
    }
    onCompleteRef.current();
  }, [session, epoch, reset, persistToBackend, points]);

  const handleDotClick = useCallback(async () => {
    if (
      paused ||
      phase !== "calibrating" ||
      !session ||
      session.epoch !== epoch
    ) {
      return;
    }
    const activeSessionId = session.id;
    setPhase("sending");
    setError(null);

    if (!camOn) {
      setPhase("calibrating");
      setError(ERROR_TEXT.no_camera);
      return;
    }

    const point = points[idx];
    let accepted = 0;
    let failed: string | null = null;

    for (
      let attempt = 0;
      attempt < MAX_CAPTURES_PER_POINT && accepted < SAMPLES_PER_POINT;
      attempt++
    ) {
      const frame = await captureFrame();
      if (pausedRef.current || epochRef.current !== session.epoch) return;
      if (frame === null) {
        failed = "no_camera";
        break;
      }
      const result = await submitCalibrationSample(activeSessionId, frame, point.id);
      if (pausedRef.current || epochRef.current !== session.epoch) return;
      if (result.status === "accepted") {
        accepted += 1;
      } else if (result.status === "no_face" || result.status === "invalid_image") {
        failed = result.status;
        break;
      } else {
        failed = "network_error";
        break;
      }
      if (accepted < SAMPLES_PER_POINT) {
        await new Promise((r) => setTimeout(r, CAPTURE_GAP_MS));
      }
    }

    if (accepted < SAMPLES_PER_POINT) {
      setPhase("calibrating");
      setError(failed ? (ERROR_TEXT[failed] ?? "Gửi điểm thất bại — bấm lại.") : ERROR_TEXT.insufficient);
      return;
    }

    if (idx === total - 1) {
      await finish();
      return;
    }
    setIdx(idx + 1);
    setPhase("calibrating");
  }, [
    phase,
    camOn,
    points,
    idx,
    total,
    captureFrame,
    finish,
    paused,
    session,
    epoch,
  ]);

  // UI chỉ coi phiên là sẵn sàng khi phiên đó thuộc epoch hiện tại. Khi pause
  // (hoặc ngay sau unpause, trước khi phiên mới về) mọi thứ hiển thị như idle.
  const hasValidSession = !paused && session !== null && session.epoch === epoch;
  const displayPhase: CalibrationPhase = hasValidSession ? phase : "idle";
  const displayStep = hasValidSession ? idx : 0;
  const progress =
    ((displayStep + (displayPhase === "training" ? 1 : 0)) / total) * 100;

  return {
    points,
    current: points[displayStep],
    step: displayStep,
    total,
    progress,
    phase: displayPhase,
    busy: displayPhase === "sending" || displayPhase === "training",
    error: paused ? null : error,
    camOn,
    sessionReady: hasValidSession,
    videoRef,
    attachVideo,
    handleDotClick,
    reset,
    retrain: finish,
  };
}
