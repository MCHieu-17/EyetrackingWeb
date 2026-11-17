import { apiFetch } from "./client";

/** FPS ghi gaze mặc định khi backend chưa trả cấu hình hoặc giá trị không hợp lệ. */
export const DEFAULT_GAZE_FPS = 15;
const MIN_GAZE_FPS = 1;
const MAX_GAZE_FPS = 60;
export const DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
export const DEFAULT_MAX_SLIDE_PAGES = 150;

function normalizePositiveInt(value: unknown, fallback: number): number {
  const parsed =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim() !== ""
        ? Number(value)
        : NaN;
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

/** Chuẩn hoá FPS: nhận number/string, clamp 1..60, không hợp lệ → mặc định. */
function normalizeGazeFps(value: unknown): number {
  let parsed: number;
  if (typeof value === "number") {
    parsed = value;
  } else if (typeof value === "string" && value.trim() !== "") {
    parsed = Number(value);
  } else {
    return DEFAULT_GAZE_FPS;
  }
  if (!Number.isFinite(parsed)) return DEFAULT_GAZE_FPS;
  return Math.min(MAX_GAZE_FPS, Math.max(MIN_GAZE_FPS, parsed));
}

interface RuntimeConfigResponse {
  gazeFps?: unknown;
  maxUploadBytes?: unknown;
  maxSlidePages?: unknown;
}

export interface RuntimeConfig {
  gazeFps: number;
  maxUploadBytes: number;
  maxSlidePages: number;
}

/**
 * Đọc cấu hình runtime từ backend (`GET /api/config`).
 *
 * Production pull image dựng sẵn nên không thể bake FPS qua `NEXT_PUBLIC_*`;
 * config lấy lúc chạy. Lỗi mạng/backend cũ chỉ trả fallback để tracker luôn
 * có số hợp lệ, không throw ra ngoài.
 */
export async function fetchRuntimeConfig(): Promise<RuntimeConfig> {
  try {
    // Endpoint công khai: không kích hoạt luồng refresh token khi gặp 401.
    const data = await apiFetch<RuntimeConfigResponse>("/api/config", {
      skipAuthRefresh: true,
    });
    return {
      gazeFps: normalizeGazeFps(data?.gazeFps),
      maxUploadBytes: normalizePositiveInt(
        data?.maxUploadBytes,
        DEFAULT_MAX_UPLOAD_BYTES,
      ),
      maxSlidePages: normalizePositiveInt(
        data?.maxSlidePages,
        DEFAULT_MAX_SLIDE_PAGES,
      ),
    };
  } catch {
    return {
      gazeFps: DEFAULT_GAZE_FPS,
      maxUploadBytes: DEFAULT_MAX_UPLOAD_BYTES,
      maxSlidePages: DEFAULT_MAX_SLIDE_PAGES,
    };
  }
}
