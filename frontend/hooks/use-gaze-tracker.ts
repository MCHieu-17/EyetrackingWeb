"use client";

import { useEffect, useRef, useState } from "react";
import {
  gazeStreamUrl,
  getCalibrationScreenSnapshot,
  getStoredGazeSessionId,
} from "@/lib/api/calibration";
import { transformGazePoint } from "@/lib/calibration-geometry";

type GazeSource = "real" | "simulated" | "off";

interface GazeFrameContext {
  presentationId: string | null;
  layoutGeneration: number;
  surface: "lesson" | "quiz";
}

export interface GazeFrameResult {
  frameId: string | null;
  sequence: number | null;
  captureMonotonicNs: number | null;
  eventTime: string;
  x: number | null;
  y: number | null;
  status: "ok" | "no_face" | "error" | "offscreen";
}

interface UseGazeTrackerOptions {
  enabled: boolean;
  calibrated: boolean;
  onPoint: (x: number, y: number, source: GazeSource) => void;
  onFrame?: (frame: GazeFrameResult) => void;
  getContext?: () => GazeFrameContext | null;
  allowSimulation?: boolean;
}

interface GazeTrackerState {
  stream: MediaStream | null;
  source: GazeSource;
}

const FPS = 12;
const FRAME_INTERVAL_MS = 1000 / FPS;
const MAX_RECONNECTS = 5;
const MAX_BUFFERED_BYTES = 1024 * 1024;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

/**
 * Quy đổi toạ độ gaze từ viewport lúc calibration sang viewport hiện tại.
 *
 * Model gaze trả toạ độ chuẩn hoá theo viewport calibration. Khi người học
 * zoom/resize/move cửa sổ, cùng một điểm nhìn vật lý trên màn hình sẽ có
 * toạ độ chuẩn hoá khác. Dùng hình chữ nhật vật lý của viewport (screenX/Y,
 * innerWidth/Height, DPR) để quy đổi, nhờ đó không phải hiệu chỉnh lại.
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
      dpr: cal.dpr,
      screenX: cal.screenX,
      screenY: cal.screenY,
    },
    {
      width: window.innerWidth,
      height: window.innerHeight,
      dpr: window.devicePixelRatio || 1,
      screenX: window.screenX,
      screenY: window.screenY,
    },
  );
}

export function useGazeTracker({
  enabled,
  calibrated,
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
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    onPointRef.current = onPoint;
    onFrameRef.current = onFrame;
    getContextRef.current = getContext;
  });

  useEffect(() => {
    let disposed = false;
    let simTimer = 0;
    let streamCleanup: (() => void) | null = null;

    const startSimulation = () => {
      if (!allowSimulation) {
        setSource("off");
        return;
      }
      simTimer = window.setInterval(() => {
        const x = 0.12 + Math.random() * 0.76;
        const y = 0.14 + Math.random() * 0.68;
        onPointRef.current(x, y, "simulated");
      }, 1800);
      setSource("simulated");
    };

    const captureFrame = async (video: HTMLVideoElement): Promise<Blob | null> => {
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
      return new Promise((resolve) => canvas!.toBlob(resolve, "image/jpeg", 0.78));
    };

    const runWsSession = async (
      video: HTMLVideoElement,
      url: string,
    ): Promise<"retry" | "abort"> => {
      return new Promise<"retry" | "abort">((resolve) => {
        const ws = new WebSocket(url);
        let sendTimer = 0;
        let sequence = 0;

        const scheduleSend = () => {
          if (disposed) {
            resolve("abort");
            return;
          }
          sendTimer = window.setTimeout(async () => {
            if (disposed || ws.readyState !== WebSocket.OPEN) return;
            // Backpressure: bỏ frame nếu socket còn tồn đọng quá nhiều dữ liệu.
            if (ws.bufferedAmount > MAX_BUFFERED_BYTES) {
              scheduleSend();
              return;
            }
            const blob = await captureFrame(video);
            if (blob && ws.readyState === WebSocket.OPEN) {
              const context = getContextRef.current?.() ?? null;
              const frameId =
                globalThis.crypto?.randomUUID?.() ??
                `frame-${Date.now()}-${sequence}`;
              const captureMonotonicNs = Math.round(performance.now() * 1e6);
              const eventTime = new Date().toISOString();
              const header = {
                v: 2,
                frameId,
                sequence,
                captureMonotonicNs,
                eventTime,
                presentationId: context?.presentationId ?? null,
                layoutGeneration: context?.layoutGeneration ?? 0,
                surface: context?.surface ?? "lesson",
                viewportWidth: window.innerWidth,
                viewportHeight: window.innerHeight,
                dpr: window.devicePixelRatio || 1,
              };
              const headerBytes = new TextEncoder().encode(JSON.stringify(header));
              const jpegBytes = new Uint8Array(await blob.arrayBuffer());
              const frame = new Uint8Array(4 + headerBytes.length + jpegBytes.length);
              new DataView(frame.buffer).setUint32(0, headerBytes.length);
              frame.set(headerBytes, 4);
              frame.set(jpegBytes, 4 + headerBytes.length);
              ws.send(frame);
              sequence += 1;
            }
            scheduleSend();
          }, FRAME_INTERVAL_MS);
        };

        ws.onopen = () => {
          if (disposed) {
            try {
              ws.close();
            } catch {
              /* ignore */
            }
            return;
          }
          scheduleSend();
        };

        ws.onmessage = (event: MessageEvent) => {
          try {
            const data = JSON.parse(String(event.data)) as {
              ok?: boolean;
              error?: string;
              status?: string;
              x?: number;
              y?: number;
              frameId?: string;
              sequence?: number;
              captureMonotonicNs?: number;
            };
            const status =
              data.status === "no_face" || data.error === "no_face"
                ? "no_face"
                : data.ok && typeof data.x === "number" && typeof data.y === "number"
                  ? "ok"
                  : "error";
            const point =
              status === "ok"
                ? transformGazeToViewport(data.x as number, data.y as number)
                : null;
            if (point) {
              onPointRef.current(point.x, point.y, "real");
            } else if (status === "no_face") {
              onPointRef.current(-1, -1, "real");
            }
            onFrameRef.current?.({
              frameId: data.frameId ?? null,
              sequence: data.sequence ?? null,
              captureMonotonicNs: data.captureMonotonicNs ?? null,
              eventTime: new Date().toISOString(),
              x: point?.x ?? null,
              y: point?.y ?? null,
              status,
            });
          } catch {
            /* ignore */
          }
        };

        ws.onclose = () => {
          window.clearTimeout(sendTimer);
          resolve(disposed ? "abort" : "retry");
        };

        ws.onerror = () => {
          window.clearTimeout(sendTimer);
          if (!disposed) resolve("retry");
        };
      });
    };

    const run = async () => {
      try {
        const media = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
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
        while (!disposed && video.videoWidth === 0 && Date.now() - startedAt < 4000) {
          await sleep(100);
        }
        if (disposed) return;
        if (video.videoWidth === 0) {
          streamCleanup?.();
          setStream(null);
          startSimulation();
          return;
        }

        const sessionId = getStoredGazeSessionId();
        if (disposed) return;
        if (!sessionId) {
          streamCleanup?.();
          setStream(null);
          startSimulation();
          return;
        }

        let attempts = 0;
        while (!disposed && attempts < MAX_RECONNECTS) {
          const result = await runWsSession(video, gazeStreamUrl(sessionId));
          if (result === "abort") return;
          attempts += 1;
          if (attempts >= MAX_RECONNECTS) break;
          await sleep(Math.min(5000, 500 * 1.5 ** attempts));
        }
        if (!disposed) {
          streamCleanup?.();
          setStream(null);
          startSimulation();
        }
      } catch {
        if (!disposed) {
          streamCleanup?.();
          setStream(null);
          startSimulation();
        }
      }
    };

    if (!enabled) return;

    if (!calibrated) {
      startSimulation();
      return () => {
        disposed = true;
        window.clearInterval(simTimer);
        streamCleanup?.();
      };
    }

    const runStart = () => {
      queueMicrotask(() => {
        if (!disposed) setSource("real");
      });
      void run();
    };
    runStart();
    return () => {
      disposed = true;
      window.clearInterval(simTimer);
      streamCleanup?.();
    };
  }, [enabled, calibrated, allowSimulation]);

  return { stream, source };
}
