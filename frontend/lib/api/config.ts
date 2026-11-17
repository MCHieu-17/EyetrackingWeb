import { apiFetch } from "./client";

/** FPS ghi gaze mặc định khi backend chưa trả cấu hình hoặc giá trị không hợp lệ. */
export const DEFAULT_GAZE_FPS = 15;
export const MIN_GAZE_FPS = 1;
export const MAX_GAZE_FPS = 60;

/** Chuẩn hoá FPS: nhận number/string, clamp 1..60, không hợp lệ → mặc định. */
export function normalizeGazeFps(value: unknown): number {
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
}

/**
 * Đọc cấu hình runtime từ backend (`GET /api/config`).
 *
 * Production pull image dựng sẵn nên không thể bake FPS qua `NEXT_PUBLIC_*`;
 * config lấy lúc chạy. Lỗi mạng/backend cũ chỉ trả fallback để tracker luôn
 * có số hợp lệ, không throw ra ngoài.
 */
export async function fetchRuntimeConfig(): Promise<{ gazeFps: number }> {
  try {
    // Endpoint công khai: không kích hoạt luồng refresh token khi gặp 401.
    const data = await apiFetch<RuntimeConfigResponse>("/api/config", {
      skipAuthRefresh: true,
    });
    return { gazeFps: normalizeGazeFps(data?.gazeFps) };
  } catch {
    return { gazeFps: DEFAULT_GAZE_FPS };
  }
}
