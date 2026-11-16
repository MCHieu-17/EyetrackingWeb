import type {
  ReplayLayout,
  ReplayRect,
  ReplaySample,
  ReplayView,
} from "@/lib/types/visualization";

export interface StagePoint {
  x: number;
  y: number;
}

export interface StageRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export const NO_LABEL_SLIDE = "SLIDE_NO_LABEL";
export const NO_LABEL_UI = "UI_NO_LABEL";

function numberValue(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

export function stageAspect(view: ReplayView): number {
  const width = view.viewport.width ?? 1280;
  const height = view.viewport.height ?? 800;
  return Math.min(3.5, Math.max(0.4, width / height));
}

export function rectToStage(rect: ReplayRect): StageRect | null {
  if (
    !Number.isFinite(rect.xMin) ||
    !Number.isFinite(rect.yMin) ||
    !Number.isFinite(rect.xMax) ||
    !Number.isFinite(rect.yMax)
  ) {
    return null;
  }
  const left = Math.min(rect.xMin, rect.xMax);
  const top = Math.min(rect.yMin, rect.yMax);
  const width = Math.abs(rect.xMax - rect.xMin);
  const height = Math.abs(rect.yMax - rect.yMin);
  if (width <= 0 || height <= 0) return null;
  return { left, top, width, height };
}

export function slideRectToStage(layout: ReplayLayout | null): StageRect | null {
  const source = layout?.slideRect;
  if (!source) return null;
  const width = numberValue(source.width, 0);
  const height = numberValue(source.height, 0);
  if (width <= 0 || height <= 0) return null;
  return {
    left: numberValue(source.left, 0),
    top: numberValue(source.top, 0),
    width,
    height,
  };
}

export function sampleStagePoint(
  sample: ReplaySample | null,
): StagePoint | null {
  if (!sample || sample.status !== "ok") return null;
  if (sample.viewportX === null || sample.viewportY === null) return null;
  return { x: sample.viewportX, y: sample.viewportY };
}

export function sampleInStage(point: StagePoint | null): boolean {
  return Boolean(
    point &&
      point.x >= 0 &&
      point.x <= 1 &&
      point.y >= 0 &&
      point.y <= 1,
  );
}

export function layoutForSample(
  view: ReplayView,
  sample: ReplaySample | null,
): ReplayLayout | null {
  if (sample?.layoutId) {
    const found = view.layouts.find((layout) => layout.id === sample.layoutId);
    if (found) return found;
  }
  return view.layouts.at(-1) ?? null;
}

export function findSampleAt(
  samples: ReplaySample[],
  timeMs: number,
): ReplaySample | null {
  if (samples.length === 0) return null;
  if (timeMs <= samples[0].offsetMs) return samples[0];
  let low = 0;
  let high = samples.length - 1;
  let best = samples[0];
  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    if (samples[mid].offsetMs <= timeMs) {
      best = samples[mid];
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }
  return best;
}

export function firstSampleForLabel(
  samples: ReplaySample[],
  label: string,
): ReplaySample | null {
  return samples.find((sample) => sample.aoiLabel === label) ?? null;
}

/** Thời gian thực tế trên slide/UI, dùng cho nhãn thời lượng trên timeline. */
export function viewDwellMs(view: ReplayView): number {
  return Math.max(0, numberValue(view.dwellMs, 0));
}

/** Nhãn ngưỡng ngắn gọn theo cấu hình CONTENT_VIEW_MIN_DWELL_MS. */
export function formatDwellThreshold(ms: number): string {
  const safe = Math.max(0, ms);
  return safe % 1000 === 0 ? `${safe / 1000}s` : `${(safe / 1000).toFixed(1)}s`;
}

/** Span của các sample, chỉ dùng để phát lại (duration/seek). */
export function playbackDurationMs(view: ReplayView): number {
  if (!view.firstSampleAt || !view.lastSampleAt) return 0;
  const first = new Date(view.firstSampleAt).getTime();
  const last = new Date(view.lastSampleAt).getTime();
  return Math.max(0, last - first);
}

export function formatDuration(ms: number): string {
  const totalSeconds = Math.max(0, Math.round(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("vi-VN");
}

export function isNoLabel(label: string | null | undefined): boolean {
  return label === NO_LABEL_SLIDE || label === NO_LABEL_UI;
}

export function labelDomain(label: string | null | undefined): "slide" | "ui" {
  return label?.startsWith("SLIDE_") ? "slide" : "ui";
}

export function stageRectStyle(rect: StageRect): {
  left: string;
  top: string;
  width: string;
  height: string;
} {
  return {
    left: `${rect.left * 100}%`,
    top: `${rect.top * 100}%`,
    width: `${rect.width * 100}%`,
    height: `${rect.height * 100}%`,
  };
}
