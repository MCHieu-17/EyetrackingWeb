/**
 * Capture JPEG cho frame gaze, ưu tiên encode trong worker.
 *
 * Main thread chỉ draw frame vào `OffscreenCanvas` rồi chuyển `ImageBitmap`
 * sang worker; worker resize/encode. Nếu trình duyệt thiếu
 * `Worker`/`OffscreenCanvas` hoặc worker lỗi, fallback canvas + `toBlob` với
 * đúng format cấu hình.
 */

/** Giữ 480px/q0.78: đã đo 320px làm lệch gaze ~108 px so với baseline. */
const GAZE_CAPTURE_MAX_WIDTH = 480;
const GAZE_JPEG_QUALITY = 0.78;

export interface FrameCapturerOptions {
  maxWidth?: number;
  quality?: number;
  /** Dùng cho benchmark để trỏ tới worker đã compile; mặc định file cạnh module. */
  workerUrl?: string | URL;
  onFallback?: (reason: unknown) => void;
}

export interface FrameCapturer {
  /** Trả Blob JPEG (chưa ghép header), hoặc null nếu không capture được. */
  capture(video: HTMLVideoElement): Promise<Blob | null>;
  dispose(): void;
  readonly usingWorker: boolean;
}

interface FrameReply {
  id: number;
  blob?: Blob;
  error?: string;
}

export function buildFrameBlob(
  headerBytes: Uint8Array<ArrayBuffer>,
  jpeg: Blob,
): Blob {
  const prefix = new Uint8Array(4);
  new DataView(prefix.buffer).setUint32(0, headerBytes.length);
  return new Blob([prefix, headerBytes, jpeg]);
}

export function createFrameCapturer(
  options: FrameCapturerOptions = {},
): FrameCapturer {
  const maxWidth = options.maxWidth ?? GAZE_CAPTURE_MAX_WIDTH;
  const quality = options.quality ?? GAZE_JPEG_QUALITY;
  const workerUrl =
    options.workerUrl ?? new URL("./capture.worker.js", import.meta.url);

  let canvas: HTMLCanvasElement | null = null;
  let offscreen: OffscreenCanvas | null = null;
  let offscreenContext: OffscreenCanvasRenderingContext2D | null = null;
  let worker: Worker | null = null;
  let workerDisabled = false;
  let fallbackNotified = false;
  let nextId = 1;
  const pending = new Map<number, (blob: Blob | null) => void>();

  const notifyFallback = (reason: unknown) => {
    if (fallbackNotified) return;
    fallbackNotified = true;
    options.onFallback?.(reason);
  };

  const disableWorker = (reason: unknown) => {
    workerDisabled = true;
    if (worker) {
      worker.onmessage = null;
      worker.onerror = null;
      worker.onmessageerror = null;
      worker.terminate();
      worker = null;
    }
    for (const resolve of pending.values()) resolve(null);
    pending.clear();
    offscreen = null;
    offscreenContext = null;
    notifyFallback(reason);
  };

  const ensureWorker = (): Worker | null => {
    if (worker) return worker;
    if (workerDisabled) return null;
    if (
      typeof Worker === "undefined" ||
      typeof OffscreenCanvas === "undefined" ||
      !("transferToImageBitmap" in OffscreenCanvas.prototype)
    ) {
      disableWorker("worker/offscreen không hỗ trợ");
      return null;
    }
    try {
      const created = new Worker(workerUrl, { type: "module" });
      created.onmessage = (event: MessageEvent<FrameReply>) => {
        const resolve = pending.get(event.data.id);
        if (!resolve) return;
        pending.delete(event.data.id);
        resolve(event.data.blob ?? null);
      };
      created.onerror = (event) => disableWorker(event);
      created.onmessageerror = (event) => disableWorker(event);
      worker = created;
      return worker;
    } catch (error) {
      disableWorker(error);
      return null;
    }
  };

  const captureWithWorker = async (
    video: HTMLVideoElement,
  ): Promise<Blob | null> => {
    const current = ensureWorker();
    if (!current) return null;
    const scale = Math.min(1, maxWidth / video.videoWidth);
    const width = Math.max(1, Math.round(video.videoWidth * scale));
    const height = Math.max(1, Math.round(video.videoHeight * scale));
    if (!offscreen) {
      offscreen = new OffscreenCanvas(width, height);
      offscreenContext = offscreen.getContext("2d");
    }
    if (offscreen.width !== width) offscreen.width = width;
    if (offscreen.height !== height) offscreen.height = height;
    if (!offscreenContext) return null;
    offscreenContext.drawImage(video, 0, 0, width, height);
    const bitmap = offscreen.transferToImageBitmap();
    const id = nextId;
    nextId += 1;
    return new Promise<Blob | null>((resolve) => {
      pending.set(id, resolve);
      try {
        current.postMessage(
          { id, bitmap, maxWidth: width, quality },
          [bitmap],
        );
      } catch (error) {
        pending.delete(id);
        bitmap.close();
        disableWorker(error);
        resolve(null);
      }
    });
  };

  const captureWithCanvas = async (
    video: HTMLVideoElement,
  ): Promise<Blob | null> => {
    if (video.videoWidth === 0 || video.videoHeight === 0) return null;
    const scale = Math.min(1, maxWidth / video.videoWidth);
    const width = Math.max(1, Math.round(video.videoWidth * scale));
    const height = Math.max(1, Math.round(video.videoHeight * scale));
    if (!canvas) canvas = document.createElement("canvas");
    if (canvas.width !== width) canvas.width = width;
    if (canvas.height !== height) canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) return null;
    context.drawImage(video, 0, 0, width, height);
    return new Promise((resolve) =>
      canvas!.toBlob((blob) => resolve(blob), "image/jpeg", quality),
    );
  };

  const capture = async (video: HTMLVideoElement): Promise<Blob | null> => {
    if (video.videoWidth === 0 || video.videoHeight === 0) return null;
    if (!workerDisabled) {
      try {
        const encoded = await captureWithWorker(video);
        if (encoded) return encoded;
      } catch (error) {
        disableWorker(error);
      }
    }
    return captureWithCanvas(video);
  };

  return {
    capture,
    dispose() {
      if (worker) {
        worker.onmessage = null;
        worker.onerror = null;
        worker.onmessageerror = null;
        worker.terminate();
        worker = null;
      }
      for (const resolve of pending.values()) resolve(null);
      pending.clear();
      offscreen = null;
      offscreenContext = null;
      if (canvas) {
        canvas.width = 0;
        canvas.height = 0;
        canvas = null;
      }
    },
    get usingWorker() {
      return worker !== null;
    },
  };
}
