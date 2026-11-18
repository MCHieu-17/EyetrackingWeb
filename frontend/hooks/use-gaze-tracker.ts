"use client";

import { useEffect, useRef, useState } from "react";
import {
  gazeStreamUrl,
  getCalibrationScreenSnapshot,
  getStoredGazeSessionId,
} from "@/lib/api/calibration";
import { transformGazePoint } from "@/lib/calibration-geometry";
import {
  parseGazeFrameResponse,
  type GazeFrameResult,
} from "@/lib/gaze/frame-protocol";

export type { GazeFrameResult } from "@/lib/gaze/frame-protocol";

type GazeSource = "real" | "simulated" | "off";

interface GazeFrameContext {
  presentationId: string | null;
  layoutGeneration: number;
  surface: "lesson" | "quiz";
}

interface UseGazeTrackerOptions {
  enabled: boolean;
  calibrated: boolean;
  /** Số frame/giây gửi lên service gaze; bỏ trống dùng mặc định 15. */
  fps?: number;
  onPoint: (x: number, y: number, source: GazeSource) => void;
  onFrame?: (frame: GazeFrameResult) => void;
  getContext?: () => GazeFrameContext | null;
  allowSimulation?: boolean;
}

interface GazeTrackerState {
  stream: MediaStream | null;
  source: GazeSource;
}

const DEFAULT_FPS = 15;
const MAX_RECONNECTS = 5;
const MAX_BUFFERED_BYTES = 1024 * 1024;

/** Khoảng cách giữa 2 frame (ms). Clamp 1..60 để tránh chia 0 / giá trị lạ. */
export function frameIntervalMs(fps: number): number {
  const safe = Number.isFinite(fps) ? Math.min(60, Math.max(1, fps)) : DEFAULT_FPS;
  return 1000 / safe;
}

/**
 * Quy đổi toạ độ gaze từ viewport lúc calibration sang viewport hiện tại.
 *
 * Model gaze trả toạ độ chuẩn hoá theo viewport calibration. Khi cửa sổ bị
 * resize hoặc di chuyển, cùng một điểm nhìn vật lý sẽ có toạ độ chuẩn hoá
 * khác. Dùng hình chữ nhật vật lý của viewport (screenX/Y, innerWidth/Height)
 * để quy đổi. Zoom/fullscreen do display guard phát hiện và tạm dừng ghi gaze.
 */
function transformGazeToViewport(
  x: number,
  y: number,
): { x: number; y: number } {
  const cal = getCalibrationScreenSnapshot();
  if (!cal) return { x, y };
  return transformGazePoint(
    x,
    y,
    {
      width: cal.w,
      height: cal.h,
      screenX: cal.screenX,
      screenY: cal.screenY,
    },
    {
      width: window.innerWidth,
      height: window.innerHeight,
      screenX: window.screenX,
      screenY: window.screenY,
    },
  );
}

export function useGazeTracker({
  enabled,
  calibrated,
  fps,
  onPoint,
  onFrame,
  getContext,
  allowSimulation = true,
}: UseGazeTrackerOptions): GazeTrackerState {
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [source, setSource] = useState<GazeSource>("off");

  const onPointRef = useRef(onPoint);
  const onFrameRef = useRef(onFrame);
  const getContextRef = useRef(getContext);
  // FPS nằm trong ref để config runtime về muộn không phải mở lại WebSocket.
  const fpsRef = useRef(fps ?? DEFAULT_FPS);
  // FPS tạm thời do server gợi ý khi quá tải; hết hạn thì quay lại FPS đích.
  const adaptiveFpsRef = useRef<number | null>(null);
  const adaptiveUntilRef = useRef(0);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    onPointRef.current = onPoint;
    onFrameRef.current = onFrame;
    getContextRef.current = getContext;
    fpsRef.current = fps ?? DEFAULT_FPS;
  });

  useEffect(() => {
    let disposed = false;
    let simTimer = 0;
    let streamCleanup: (() => void) | null = null;
    let activeWs: WebSocket | null = null;
    let finishActiveWs: ((result: "retry" | "abort") => void) | null = null;
    let delayTimer = 0;
    let wakeDelay: (() => void) | null = null;

    const clearDelayWait = () => {
      if (delayTimer) {
        window.clearTimeout(delayTimer);
        delayTimer = 0;
      }
      const wake = wakeDelay;
      wakeDelay = null;
      wake?.();
    };

    const waitForDelay = (ms: number): Promise<void> =>
      new Promise((resolve) => {
        if (disposed) {
          resolve();
          return;
        }
        let settled = false;
        const finish = () => {
          if (settled) return;
          settled = true;
          if (delayTimer) {
            window.clearTimeout(delayTimer);
            delayTimer = 0;
          }
          wakeDelay = null;
          resolve();
        };
        delayTimer = window.setTimeout(finish, ms);
        wakeDelay = finish;
      });

    const closeActiveSocket = () => {
      const ws = activeWs;
      activeWs = null;
      const finish = finishActiveWs;
      finishActiveWs = null;
      finish?.("abort");

      if (!ws) return;
      ws.onopen = null;
      ws.onmessage = null;
      ws.onclose = null;
      ws.onerror = null;
      try {
        ws.close();
      } catch {
        /* ignore */
      }
    };

    /** FPS hiện tại: tạm hạ theo gợi ý server, hết hạn thì về FPS đích. */
    const effectiveFps = () => {
      const target = fpsRef.current;
      if (adaptiveFpsRef.current === null) return target;
      if (performance.now() >= adaptiveUntilRef.current) {
        adaptiveFpsRef.current = null;
        return target;
      }
      return Math.min(target, adaptiveFpsRef.current);
    };

    const startSimulation = () => {
      if (disposed) return;
      if (!allowSimulation) {
        setSource("off");
        return;
      }
      window.clearInterval(simTimer);
      simTimer = window.setInterval(() => {
        const x = 0.12 + Math.random() * 0.76;
        const y = 0.14 + Math.random() * 0.68;
        onPointRef.current(x, y, "simulated");
      }, 1800);
      setSource("simulated");
    };

    const captureFrame = async (
      video: HTMLVideoElement,
    ): Promise<Blob | null> => {
      if (video.videoWidth === 0 || video.videoHeight === 0) return null;
      const scale = Math.min(1, 480 / video.videoWidth);
      const width = Math.round(video.videoWidth * scale);
      const height = Math.round(video.videoHeight * scale);
      let canvas = canvasRef.current;
      if (!canvas) {
        canvas = document.createElement("canvas");
        canvasRef.current = canvas;
      }
      if (canvas.width !== width) canvas.width = width;
      if (canvas.height !== height) canvas.height = height;
      const context = canvas.getContext("2d");
      if (!context) return null;
      context.drawImage(video, 0, 0, width, height);
      return new Promise((resolve) =>
        canvas!.toBlob(resolve, "image/jpeg", 0.78),
      );
    };

    const runWsSession = (
      video: HTMLVideoElement,
      url: string,
      sequenceState: { value: number },
      onOpen?: () => void,
    ): Promise<"retry" | "abort"> =>
      new Promise<"retry" | "abort">((resolve) => {
        if (disposed) {
          resolve("abort");
          return;
        }

        let ws: WebSocket;
        try {
          ws = new WebSocket(url);
        } catch {
          resolve("retry");
          return;
        }

        activeWs = ws;
        let settled = false;
        let sendTimer = 0;

        const finish = (result: "retry" | "abort") => {
          if (settled) return;
          settled = true;
          if (sendTimer) {
            window.clearTimeout(sendTimer);
            sendTimer = 0;
          }
          if (activeWs === ws) activeWs = null;
          if (finishActiveWs === finish) finishActiveWs = null;
          resolve(result);
        };
        finishActiveWs = finish;

        const scheduleSend = (delayMs = frameIntervalMs(effectiveFps())) => {
          if (disposed || settled) {
            if (disposed) finish("abort");
            return;
          }
          sendTimer = window.setTimeout(async () => {
            sendTimer = 0;
            // Mốc bắt đầu xử lý frame để bù vào nhịp gửi kế tiếp.
            const startedAt = performance.now();
            if (disposed || settled) {
              if (disposed) finish("abort");
              return;
            }
            // Tab ẩn: không capture/gửi (trình duyệt có thể trả frame đen và
            // vẫn tốn GPU server). Thử lại khi tab hiện lại.
            if (typeof document !== "undefined" && document.hidden) {
              scheduleSend(500);
              return;
            }
            if (ws.readyState !== WebSocket.OPEN) return;
            // Backpressure: bỏ frame nếu socket còn tồn đọng quá nhiều dữ liệu.
            if (ws.bufferedAmount > MAX_BUFFERED_BYTES) {
              scheduleSend();
              return;
            }

            // Lấy context trước khi capture để header khớp thời điểm frame.
            const context = getContextRef.current?.() ?? null;
            const blob = await captureFrame(video);
            if (disposed || settled) {
              if (disposed) finish("abort");
              return;
            }

            if (blob && ws.readyState === WebSocket.OPEN) {
              const frameId =
                globalThis.crypto?.randomUUID?.() ??
                `frame-${Date.now()}-${sequenceState.value}`;
              const captureMonotonicNs = Math.round(performance.now() * 1e6);
              const eventTime = new Date().toISOString();
              const header = {
                v: 2,
                frameId,
                sequence: sequenceState.value,
                captureMonotonicNs,
                eventTime,
                presentationId: context?.presentationId ?? null,
                layoutGeneration: context?.layoutGeneration ?? 0,
                surface: context?.surface ?? "lesson",
                viewportWidth: window.innerWidth,
                viewportHeight: window.innerHeight,
                dpr: window.devicePixelRatio || 1,
              };
              const headerBytes = new TextEncoder().encode(
                JSON.stringify(header),
              );
              const jpegBytes = new Uint8Array(await blob.arrayBuffer());
              if (disposed || settled) {
                if (disposed) finish("abort");
                return;
              }
              const frame = new Uint8Array(
                4 + headerBytes.length + jpegBytes.length,
              );
              new DataView(frame.buffer).setUint32(0, headerBytes.length);
              frame.set(headerBytes, 4);
              frame.set(jpegBytes, 4 + headerBytes.length);
              try {
                ws.send(frame);
                sequenceState.value += 1;
              } catch {
                finish(disposed ? "abort" : "retry");
                try {
                  ws.close();
                } catch {
                  /* ignore */
                }
                return;
              }
            }
            // Bù thời gian capture + encode vừa tốn để nhịp gửi thực tế đúng
            // FPS đặt (nếu xử lý mất ~15ms mà vẫn chờ đủ interval thì sẽ chậm
            // hơn). Floor 5ms để không busy-loop khi xử lý chậm hơn interval.
            const interval = frameIntervalMs(effectiveFps());
            const elapsed = performance.now() - startedAt;
            scheduleSend(Math.max(5, interval - elapsed));
          }, delayMs);
        };

        ws.onopen = () => {
          if (disposed || settled) {
            finish("abort");
            try {
              ws.close();
            } catch {
              /* ignore */
            }
            return;
          }
          // Một kết nối thành công phải reset ngân sách reconnect; nếu không,
          // vài lần rớt mạng rải rác trong phiên dài sẽ làm tracker bỏ cuộc.
          onOpen?.();
          scheduleSend();
        };

        ws.onmessage = (event: MessageEvent) => {
          if (disposed || settled) return;
          const frame = parseGazeFrameResponse(
            event.data,
            new Date().toISOString(),
          );
          if (!frame) return;

          // Server gợi ý giảm FPS khi quá tải; giữ 10s rồi tự hồi phục.
          if (frame.suggestedFps !== null) {
            adaptiveFpsRef.current = frame.suggestedFps;
            adaptiveUntilRef.current = performance.now() + 10_000;
          }

          let currentX: number | null = null;
          let currentY: number | null = null;
          if (
            frame.status === "ok" &&
            frame.x !== null &&
            frame.y !== null
          ) {
            const point = transformGazeToViewport(frame.x, frame.y);
            currentX = point.x;
            currentY = point.y;
            if (disposed) return;
            onPointRef.current(point.x, point.y, "real");
          } else if (frame.status === "no_face") {
            onPointRef.current(-1, -1, "real");
          }
          if (disposed) return;
          onFrameRef.current?.({ ...frame, currentX, currentY });
        };

        ws.onclose = () => {
          finish(disposed ? "abort" : "retry");
        };

        ws.onerror = () => {
          finish(disposed ? "abort" : "retry");
          try {
            ws.close();
          } catch {
            /* ignore */
          }
        };
      });

    const run = async () => {
      try {
        const media = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: "user",
            width: { ideal: 640 },
            height: { ideal: 480 },
          },
          audio: false,
        });
        if (disposed) {
          media.getTracks().forEach((track) => track.stop());
          return;
        }
        setStream(media);
        streamCleanup = () => media.getTracks().forEach((track) => track.stop());

        const video = document.createElement("video");
        video.muted = true;
        video.playsInline = true;
        video.srcObject = media;
        await video.play().catch(() => undefined);

        const startedAt = Date.now();
        while (
          !disposed &&
          video.videoWidth === 0 &&
          Date.now() - startedAt < 4000
        ) {
          await waitForDelay(100);
        }
        if (disposed) return;
        if (video.videoWidth === 0) {
          streamCleanup?.();
          streamCleanup = null;
          setStream(null);
          startSimulation();
          return;
        }

        const sessionId = getStoredGazeSessionId();
        if (disposed) return;
        if (!sessionId) {
          streamCleanup?.();
          streamCleanup = null;
          setStream(null);
          startSimulation();
          return;
        }

        // Sequence phải tăng liên tục trong một presentation, kể cả khi
        // WebSocket reconnect để batch không bị đảo thứ tự.
        const sequenceState = { value: 0 };
        let attempts = 0;
        while (!disposed && attempts < MAX_RECONNECTS) {
          const result = await runWsSession(
            video,
            gazeStreamUrl(sessionId),
            sequenceState,
            () => {
              attempts = 0;
            },
          );
          if (result === "abort") return;
          attempts += 1;
          if (attempts >= MAX_RECONNECTS) break;
          await waitForDelay(Math.min(5000, 500 * 1.5 ** attempts));
          if (disposed) return;
        }
        if (!disposed) {
          streamCleanup?.();
          streamCleanup = null;
          setStream(null);
          startSimulation();
        }
      } catch {
        if (!disposed) {
          streamCleanup?.();
          streamCleanup = null;
          setStream(null);
          startSimulation();
        }
      }
    };

    const cleanup = () => {
      disposed = true;
      window.clearInterval(simTimer);
      simTimer = 0;
      clearDelayWait();
      closeActiveSocket();
      streamCleanup?.();
      streamCleanup = null;
      setStream(null);
      setSource("off");
    };

    if (!enabled) {
      return;
    }

    if (!calibrated) {
      startSimulation();
      return cleanup;
    }

    queueMicrotask(() => {
      if (!disposed) setSource("real");
    });
    void run();
    return cleanup;
  }, [enabled, calibrated, allowSimulation]);

  return { stream, source };
}
