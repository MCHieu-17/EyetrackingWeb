// lib/api/calibration.ts — Calibration + gaze stream dùng protocol /session
// của AI service. HTTP qua /gaze/* (rewrite), WebSocket nối thẳng.
// GIỮ NGUYÊN hình học: screenGazeToSlide, screen stale detection, storage keys.

import { buildCalibrationPoints, calibrationMargins } from "@/lib/calibration-geometry";
import type { CalPoint } from "@/lib/calibration-geometry";

// Hình học thuần đã tách sang lib/calibration-geometry.ts; re-export các
// symbol còn được import qua `@/lib/api/calibration`.
export {
  buildCalibrationPoints,
  calibrationMargins,
  getContainedImageRect,
  screenGazeToSlide,
} from "@/lib/calibration-geometry";
export type { CalPoint } from "@/lib/calibration-geometry";

const SESSION_KEY = "gaze_session_id";
const CALIBRATED_AT_KEY = "gaze_calibrated_at";
const SCREEN_W_KEY = "gaze_screen_w";
const SCREEN_H_KEY = "gaze_screen_h";
const DPR_KEY = "gaze_dpr";

export interface SessionCreateResult {
  ok: boolean;
  sessionId?: string;
  error?: string;
}

export async function createGazeSession(
  points: CalPoint[],
): Promise<SessionCreateResult> {
  try {
    const res = await fetch("/gaze/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ points }),
    });
    const data = (await res.json()) as { session_id?: string };
    if (data.session_id) return { ok: true, sessionId: data.session_id };
    return { ok: false, error: `session_${res.status}` };
  } catch {
    return { ok: false, error: "network_error" };
  }
}

export interface SampleResult {
  ok: boolean;
  status?: string;
  count?: number;
  error?: string;
}

export async function submitCalibrationSample(
  sessionId: string,
  imageBlob: Blob,
  pointId: string,
): Promise<SampleResult> {
  const form = new FormData();
  form.append("image", imageBlob, "frame.jpg");
  form.append("point_id", pointId);
  try {
    const res = await fetch(`/gaze/session/${sessionId}/calibrate`, {
      method: "POST",
      body: form,
    });
    const data = (await res.json()) as { status?: string; count?: number };
    return {
      ok: res.ok,
      status: data.status,
      count: data.count,
      error: res.ok ? undefined : `http_${res.status}`,
    };
  } catch {
    return { ok: false, error: "network_error" };
  }
}

export interface TrainResult {
  ok: boolean;
  maePx?: number;
  error?: string;
}

export const MAX_TRAIN_MAE = 0.12;

export function formatMaePercent(mae: number): string {
  return `${(mae * 100).toFixed(1)}%`;
}

export async function trainGazeSession(sessionId: string): Promise<TrainResult> {
  try {
    const res = await fetch(`/gaze/session/${sessionId}/train`, { method: "POST" });
    const data = (await res.json().catch(() => ({}))) as { status?: string; mae_px?: number };
    if (data.status === "ok") return { ok: true, maePx: data.mae_px };
    if (data.status === "insufficient_samples")
      return { ok: false, error: "insufficient_samples", maePx: data.mae_px };
    return { ok: false, error: `train_${res.status}`, maePx: data.mae_px };
  } catch {
    return { ok: false, error: "network_error" };
  }
}

export interface SessionStatusResult {
  ok: boolean;
  ready: boolean;
  error?: string;
}

export async function getGazeSessionStatus(sessionId: string): Promise<SessionStatusResult> {
  try {
    const res = await fetch(`/gaze/session/${encodeURIComponent(sessionId)}`);
    if (res.status === 404) return { ok: false, ready: false, error: "not_found" };
    if (!res.ok) return { ok: false, ready: false, error: `http_${res.status}` };
    const data = (await res.json().catch(() => ({}))) as { state?: string; calibrated?: boolean };
    const ready = data.state === "ready" || data.calibrated === true;
    return { ok: true, ready };
  } catch {
    return { ok: false, ready: false, error: "network_error" };
  }
}

export function deleteGazeSession(sessionId: string): void {
  try {
    void fetch(`/gaze/session/${encodeURIComponent(sessionId)}`, { method: "DELETE" }).catch(() => {});
  } catch {
    /* ignore */
  }
}

export async function checkFace(imageBlob: Blob): Promise<{ ok: boolean; error?: string }> {
  const session = await createGazeSession([{ id: "check", x: 0.5, y: 0.5 }]);
  if (!session.ok || !session.sessionId) return { ok: false, error: "network_error" };
  try {
    const r = await submitCalibrationSample(session.sessionId, imageBlob, "check");
    if (r.status === "accepted") return { ok: true };
    if (r.status === "no_face") return { ok: false, error: "no_face" };
    return { ok: false, error: r.status === "invalid_image" ? "invalid_image" : "network_error" };
  } finally {
    deleteGazeSession(session.sessionId);
  }
}

export function storeGazeSession(
  sessionId: string,
  screenWidth?: number,
  screenHeight?: number,
): void {
  globalThis.localStorage?.setItem(SESSION_KEY, sessionId);
  globalThis.localStorage?.setItem(CALIBRATED_AT_KEY, new Date().toISOString());
  globalThis.localStorage?.setItem(DPR_KEY, String(globalThis.devicePixelRatio || 1));
  if (screenWidth && screenHeight) {
    globalThis.localStorage?.setItem(SCREEN_W_KEY, String(Math.round(screenWidth)));
    globalThis.localStorage?.setItem(SCREEN_H_KEY, String(Math.round(screenHeight)));
  }
  calibrationScreenSnapshot = undefined;
}

// Snapshot ổn định cho useSyncExternalStore (tránh trả object mới mỗi render).
let calibrationScreenSnapshot: { w: number; h: number } | null | undefined;

export function getCalibrationScreenSnapshot(): { w: number; h: number } | null {
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

export function getStoredCalibrationScreen(): { w: number; h: number } | null {
  const w = Number(globalThis.localStorage?.getItem(SCREEN_W_KEY) ?? "");
  const h = Number(globalThis.localStorage?.getItem(SCREEN_H_KEY) ?? "");
  if (!w || !h) return null;
  return { w, h };
}

export function getStoredCalibrationDpr(): number {
  const dpr = Number(globalThis.localStorage?.getItem(DPR_KEY) ?? "");
  return dpr > 0 ? dpr : 1;
}

export function isCalibrationScreenStale(): boolean {
  if (typeof window === "undefined") return false;
  const stored = getStoredCalibrationScreen();
  if (!stored) return false;
  // Viewport lúc lấy mẫu phải BẰNG viewport lúc calibration. Không dùng
  // tolerance: F11/zoom làm innerWidth/innerHeight đổi là phải hiệu chỉnh lại.
  const currentDpr = window.devicePixelRatio || 1;
  const storedDpr = getStoredCalibrationDpr();
  return (
    window.innerWidth !== stored.w ||
    window.innerHeight !== stored.h ||
    currentDpr !== storedDpr
  );
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
  calibrationScreenSnapshot = undefined;
}

// Lưu / khôi phục model hiệu chỉnh (.ubj)

/** Tải model .ubj của session (binary) từ gaze service. */
export async function downloadGazeModel(sessionId: string): Promise<Uint8Array | null> {
  try {
    const res = await fetch(`/gaze/session/${encodeURIComponent(sessionId)}/model`);
    if (!res.ok) return null;
    return new Uint8Array(await res.arrayBuffer());
  } catch {
    return null;
  }
}

export function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

export function base64ToBytes(b64: string): Uint8Array {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

/** Nạp model .ubj vào session để dùng ngay, bỏ qua bước hiệu chỉnh lại. */
export async function importGazeModel(
  sessionId: string,
  model: Uint8Array,
): Promise<boolean> {
  const form = new FormData();
  // base64ToBytes() cấp phát đúng kích thước nên buffer == toàn bộ dữ liệu
  form.append(
    "model",
    new Blob([model.buffer as ArrayBuffer], { type: "application/octet-stream" }),
    "calibration.ubj",
  );
  try {
    const res = await fetch(`/gaze/session/${encodeURIComponent(sessionId)}/import`, {
      method: "POST",
      body: form,
    });
    const data = (await res.json().catch(() => ({}))) as { status?: string };
    return data.status === "ready";
  } catch {
    return false;
  }
}

export async function saveCalibrationToBackend(params: {
  deviceFingerprint: string;
  numPoints: number;
  modelUbjBase64: string;
  maePx: number | null;
  screenWidth: number;
  screenHeight: number;
}): Promise<boolean> {
  try {
    const { apiFetch } = await import("./client");
    await apiFetch("/api/calibrations", {
      method: "POST",
      body: {
        deviceFingerprint: params.deviceFingerprint,
        numPoints: params.numPoints,
        modelUbjBase64: params.modelUbjBase64,
        screenWidthPx: params.screenWidth,
        screenHeightPx: params.screenHeight,
        maePx: params.maePx,
      },
    });
    return true;
  } catch {
    return false;
  }
}

/** Tải model hiệu chỉnh đang active của thiết bị (nếu có). */
export async function fetchActiveCalibrationModel(
  deviceFingerprint: string,
): Promise<{ modelUbjBase64: string; maePx: number | null } | null> {
  try {
    const { apiFetch } = await import("./client");
    const data = await apiFetch<{ modelUbjBase64: string; maePx?: number }>(
      "/api/calibrations/active/model",
      { params: { deviceFingerprint } },
    );
    return { modelUbjBase64: data.modelUbjBase64, maePx: data.maePx ?? null };
  } catch {
    return null;
  }
}

/**
 * Khôi phục phiên theo dõi từ model đã lưu: tạo session mới trên gaze service
 * rồi nạp lại .ubj. Trả về false nếu không có model hoặc nạp thất bại.
 */
export async function restoreGazeSessionFromBackend(
  deviceFingerprint: string,
): Promise<boolean> {
  const stored = await fetchActiveCalibrationModel(deviceFingerprint);
  if (!stored) return false;
  const session = await createGazeSession(
    buildCalibrationPoints(
      calibrationMargins(globalThis.innerWidth, globalThis.innerHeight),
    ),
  );
  if (!session.ok || !session.sessionId) return false;
  const ok = await importGazeModel(session.sessionId, base64ToBytes(stored.modelUbjBase64));
  if (!ok) {
    deleteGazeSession(session.sessionId);
    return false;
  }
  storeGazeSession(session.sessionId, globalThis.innerWidth, globalThis.innerHeight);
  return true;
}

export async function fetchActiveCalibration(
  deviceFingerprint: string,
): Promise<{ calibrated: boolean; calibratedAt: string | null } | null> {
  try {
    const { apiFetch } = await import("./client");
    const data = await apiFetch<{ calibrated: boolean; calibratedAt: string; maePx?: number }>(
      "/api/calibrations/active",
      { params: { deviceFingerprint } },
    );
    return { calibrated: data.calibrated, calibratedAt: data.calibratedAt };
  } catch {
    return null;
  }
}

export interface CalibrationSettings {
  enabled: boolean;
  threshold: number;
  updatedAt?: string | null;
}

export async function fetchAdminCalibrationSettings(): Promise<CalibrationSettings> {
  const { apiFetch } = await import("./client");
  return apiFetch<CalibrationSettings>("/api/admin/calibration-settings");
}

export async function updateAdminCalibrationSettings(patch: {
  enabled: boolean;
  threshold: number;
}): Promise<CalibrationSettings> {
  const { apiFetch } = await import("./client");
  return apiFetch<CalibrationSettings>("/api/admin/calibration-settings", {
    method: "PUT",
    body: { enabled: patch.enabled, threshold: patch.threshold },
  });
}

function getGazeWsOrigin(): string {
  const raw = (process.env.NEXT_PUBLIC_GAZE_URL?.trim() || "").replace(/\/+$/, "");

  // Same-origin: để trống hoặc "/gaze" -> nối qua rewrite của Next.js.
  if (!raw || raw === "/gaze") {
    if (typeof window === "undefined") return "";
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    return `${scheme}://${window.location.host}/gaze`;
  }

  // URL tuyệt đối: đổi http(s) -> ws(s).
  if (/^wss?:\/\//i.test(raw)) return raw;
  if (/^https?:\/\//i.test(raw)) {
    return raw.replace(/^http:/i, "ws:").replace(/^https:/i, "wss:");
  }

  // Giá trị tương đối khác (vd "gaze.example.com") -> coi là host.
  if (typeof window === "undefined") return "";
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${raw.replace(/^\/+/, "")}`;
}

export function gazeStreamUrl(sessionId: string): string {
  return `${getGazeWsOrigin()}/session/${sessionId}/stream`;
}
