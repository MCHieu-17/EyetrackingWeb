// lib/api/calibration-session.ts — Lưu / khôi phục phiên hiệu chỉnh cục bộ.
// Tách khỏi calibration-api.ts để phần storage không kéo theo HTTP client.

const SESSION_KEY = "gaze_session_id";
const CALIBRATED_AT_KEY = "gaze_calibrated_at";
const AFFINITY_COOKIE = "gaze_affinity";
const SCREEN_W_KEY = "gaze_screen_w";
const SCREEN_H_KEY = "gaze_screen_h";
const DPR_KEY = "gaze_dpr";
const SCREEN_X_KEY = "gaze_screen_x";
const SCREEN_Y_KEY = "gaze_screen_y";

export interface CalibrationScreenSnapshot {
  w: number;
  h: number;
  dpr: number;
  screenX: number;
  screenY: number;
}

/**
 * Cookie affinity cho gaze service. nginx dùng cookie này để route mọi
 * request/WS của cùng browser về cùng replica (session calibration nằm trong
 * RAM từng replica). Tạo trước request đầu tiên để request đầu cũng đúng chỗ.
 */
export function ensureGazeAffinityCookie(): void {
  if (typeof document === "undefined") return;
  const exists = document.cookie
    .split("; ")
    .some((row) => row.startsWith(`${AFFINITY_COOKIE}=`));
  if (exists) return;
  const value =
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  document.cookie = `${AFFINITY_COOKIE}=${value}; Path=/; SameSite=Lax`;
}

export function storeGazeSession(
  sessionId: string,
  screenWidth?: number,
  screenHeight?: number,
  screenX?: number,
  screenY?: number,
  dpr?: number,
): void {
  globalThis.localStorage?.setItem(SESSION_KEY, sessionId);
  globalThis.localStorage?.setItem(CALIBRATED_AT_KEY, new Date().toISOString());
  globalThis.localStorage?.setItem(
    DPR_KEY,
    String(dpr ?? (globalThis.devicePixelRatio || 1)),
  );
  if (screenWidth && screenHeight) {
    globalThis.localStorage?.setItem(SCREEN_W_KEY, String(Math.round(screenWidth)));
    globalThis.localStorage?.setItem(SCREEN_H_KEY, String(Math.round(screenHeight)));
  }
  if (typeof screenX === "number" && typeof screenY === "number") {
    globalThis.localStorage?.setItem(SCREEN_X_KEY, String(Math.round(screenX)));
    globalThis.localStorage?.setItem(SCREEN_Y_KEY, String(Math.round(screenY)));
  }
  calibrationScreenSnapshot = undefined;
}

// Snapshot ổn định cho useSyncExternalStore (tránh trả object mới mỗi render).
let calibrationScreenSnapshot: CalibrationScreenSnapshot | null | undefined;

export function getCalibrationScreenSnapshot(): CalibrationScreenSnapshot | null {
  if (calibrationScreenSnapshot === undefined) {
    calibrationScreenSnapshot = getStoredCalibrationScreen();
  }
  return calibrationScreenSnapshot;
}

export function subscribeCalibrationScreen(callback: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const handler = () => {
    calibrationScreenSnapshot = undefined;
    callback();
  };
  window.addEventListener("storage", handler);
  return () => window.removeEventListener("storage", handler);
}

function getStoredCalibrationScreen(): CalibrationScreenSnapshot | null {
  const w = Number(globalThis.localStorage?.getItem(SCREEN_W_KEY) ?? "");
  const h = Number(globalThis.localStorage?.getItem(SCREEN_H_KEY) ?? "");
  if (!w || !h) return null;
  const dpr = Number(globalThis.localStorage?.getItem(DPR_KEY) ?? "");
  const screenX = Number(globalThis.localStorage?.getItem(SCREEN_X_KEY) ?? "");
  const screenY = Number(globalThis.localStorage?.getItem(SCREEN_Y_KEY) ?? "");
  return {
    w,
    h,
    dpr: dpr > 0 ? dpr : 1,
    screenX: Number.isFinite(screenX) ? screenX : 0,
    screenY: Number.isFinite(screenY) ? screenY : 0,
  };
}

export function getStoredGazeSessionId(): string | null {
  return globalThis.localStorage?.getItem(SESSION_KEY) ?? null;
}

export function getStoredCalibration(): { calibrated: boolean; calibratedAt: string | null } {
  return {
    calibrated: Boolean(getStoredGazeSessionId()),
    calibratedAt: globalThis.localStorage?.getItem(CALIBRATED_AT_KEY) ?? null,
  };
}

export function clearStoredGazeSession(): void {
  globalThis.localStorage?.removeItem(SESSION_KEY);
  globalThis.localStorage?.removeItem(CALIBRATED_AT_KEY);
  globalThis.localStorage?.removeItem(SCREEN_W_KEY);
  globalThis.localStorage?.removeItem(SCREEN_H_KEY);
  globalThis.localStorage?.removeItem(DPR_KEY);
  globalThis.localStorage?.removeItem(SCREEN_X_KEY);
  globalThis.localStorage?.removeItem(SCREEN_Y_KEY);
  calibrationScreenSnapshot = undefined;
}
