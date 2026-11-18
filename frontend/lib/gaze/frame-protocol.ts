type GazeFrameStatus =
  | "ok"
  | "no_face"
  | "error"
  | "offscreen"
  | "overloaded"
  | "stale";
export type GazeSurface = "lesson" | "quiz";

/**
 * Frame kết quả do gaze service trả về, đã chuẩn hoá để dùng trong UI và
 * ingest. Các trường presentation/layout được service echo lại từ header v2;
 * reader dùng chúng để loại frame của context cũ sau khi đổi slide/bài.
 */
export interface GazeFrameResult {
  frameId: string | null;
  sequence: number | null;
  captureMonotonicNs: number | null;
  eventTime: string;
  x: number | null;
  y: number | null;
  /** Toạ độ trong viewport hiện tại, do tracker quy đổi từ x/y gốc. */
  currentX: number | null;
  currentY: number | null;
  status: GazeFrameStatus;
  presentationId: string | null;
  layoutGeneration: number | null;
  surface: GazeSurface | null;
  /** FPS server gợi ý khi quá tải; null = giữ nguyên FPS hiện tại. */
  suggestedFps: number | null;
}

export interface ActiveGazeFrameContext {
  presentationId: string | null;
  layoutGeneration: number | null;
  surface: GazeSurface;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function nonNegativeInteger(value: unknown): number | null {
  const number = finiteNumber(value);
  return number !== null && Number.isInteger(number) && number >= 0
    ? number
    : null;
}

function presentationId(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function surface(value: unknown): GazeSurface | null {
  return value === "lesson" || value === "quiz" ? value : null;
}

/**
 * Parse message JSON của gaze service. Trả null cho payload hỏng để caller bỏ
 * qua frame thay vì ghi dữ liệu rác.
 */
export function parseGazeFrameResponse(
  raw: unknown,
  eventTime: string = new Date().toISOString(),
): GazeFrameResult | null {
  let value: unknown = raw;
  if (typeof raw === "string") {
    try {
      value = JSON.parse(raw);
    } catch {
      return null;
    }
  }
  if (!value || typeof value !== "object") return null;

  const data = value as Record<string, unknown>;
  const x = finiteNumber(data.x);
  const y = finiteNumber(data.y);
  const echoedEventTime =
    typeof data.eventTime === "string" &&
    Number.isFinite(Date.parse(data.eventTime))
      ? data.eventTime
      : eventTime;
  const noFace = data.status === "no_face" || data.error === "no_face";
  const status: GazeFrameStatus = noFace
    ? "no_face"
    : data.status === "overloaded"
      ? "overloaded"
      : data.status === "stale"
        ? "stale"
        : data.ok === true && x !== null && y !== null
          ? "ok"
          : "error";
  const suggested = finiteNumber(data.suggestedFps);

  return {
    frameId: typeof data.frameId === "string" ? data.frameId : null,
    sequence: nonNegativeInteger(data.sequence),
    captureMonotonicNs: nonNegativeInteger(data.captureMonotonicNs),
    eventTime: echoedEventTime,
    x: status === "ok" ? x : null,
    y: status === "ok" ? y : null,
    currentX: status === "ok" ? x : null,
    currentY: status === "ok" ? y : null,
    status,
    presentationId: presentationId(data.presentationId),
    layoutGeneration: nonNegativeInteger(data.layoutGeneration),
    surface: surface(data.surface),
    suggestedFps:
      suggested !== null && suggested >= 1 && suggested <= 60
        ? suggested
        : null,
  };
}

export function isValidGazeSequence(
  sequence: number | null,
): sequence is number {
  return (
    sequence !== null && Number.isInteger(sequence) && sequence >= 0
  );
}

/**
 * Frame chỉ được ingest khi server echo đúng presentation/layout đang active
 * và có sequence hợp lệ. Surface chỉ kiểm tra khi service có echo (v2 hiện
 * tại không gửi surface trong response).
 */
export function isFrameForActiveContext(
  frame: Pick<
    GazeFrameResult,
    "sequence" | "presentationId" | "layoutGeneration" | "surface"
  >,
  context: ActiveGazeFrameContext,
): boolean {
  if (!isValidGazeSequence(frame.sequence)) return false;
  if (!context.presentationId) return false;
  if (frame.presentationId !== context.presentationId) return false;
  if (
    context.layoutGeneration === null ||
    frame.layoutGeneration !== context.layoutGeneration
  ) {
    return false;
  }
  if (frame.surface !== null && frame.surface !== context.surface) return false;
  return true;
}
