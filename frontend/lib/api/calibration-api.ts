// lib/api/calibration-api.ts — HTTP calls tới gaze service (/gaze/*) và
// backend calibration (/api/calibrations). Storage nằm ở calibration-session.ts.

import { buildCalibrationPoints, calibrationMargins } from "@/lib/calibration-geometry";
import type { CalPoint } from "@/lib/calibration-geometry";
import { storeGazeSession } from "./calibration-session";

interface SessionCreateResult {
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

interface SampleResult {
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

interface TrainResult {
  ok: boolean;
  error?: string;
}

export async function trainGazeSession(sessionId: string): Promise<TrainResult> {
  try {
    const res = await fetch(`/gaze/session/${sessionId}/train`, { method: "POST" });
    const data = (await res.json().catch(() => ({}))) as { status?: string };
    if (data.status === "ok") return { ok: true };
    if (data.status === "insufficient_samples")
      return { ok: false, error: "insufficient_samples" };
    return { ok: false, error: `train_${res.status}` };
  } catch {
    return { ok: false, error: "network_error" };
  }
}

interface SessionStatusResult {
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

function base64ToBytes(b64: string): Uint8Array {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

/** Nạp model .ubj vào session để dùng ngay, bỏ qua bước hiệu chỉnh lại. */
async function importGazeModel(
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
  screenWidth: number;
  screenHeight: number;
  screenX?: number;
  screenY?: number;
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
        viewportWidthPx: params.screenWidth,
        viewportHeightPx: params.screenHeight,
        devicePixelRatio: globalThis.devicePixelRatio || 1,
        screenXPx: params.screenX,
        screenYPx: params.screenY,
      },
    });
    return true;
  } catch {
    return false;
  }
}

/** Tải model hiệu chỉnh đang active của thiết bị (nếu có). */
async function fetchActiveCalibrationModel(
  deviceFingerprint: string,
): Promise<{ modelUbjBase64: string } | null> {
  try {
    const { apiFetch } = await import("./client");
    const data = await apiFetch<{ modelUbjBase64: string }>(
      "/api/calibrations/active/model",
      { params: { deviceFingerprint } },
    );
    return { modelUbjBase64: data.modelUbjBase64 };
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
  const active = await fetchActiveCalibration(deviceFingerprint);
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
  // Giữ đúng viewport/DPR lúc calibration để phép quy đổi gaze hoạt động
  // chính xác kể cả khi người học đang zoom/resize.
  storeGazeSession(
    session.sessionId,
    active?.viewportWidthPx ?? globalThis.innerWidth,
    active?.viewportHeightPx ?? globalThis.innerHeight,
    active?.screenX ?? undefined,
    active?.screenY ?? undefined,
    active?.devicePixelRatio ?? undefined,
  );
  return true;
}

export async function fetchActiveCalibration(
  deviceFingerprint: string,
): Promise<{
  calibrated: boolean;
  calibratedAt: string | null;
  viewportWidthPx: number | null;
  viewportHeightPx: number | null;
  devicePixelRatio: number | null;
  screenX: number | null;
  screenY: number | null;
} | null> {
  try {
    const { apiFetch } = await import("./client");
    const data = await apiFetch<{
      calibrated: boolean;
      calibratedAt: string;
      viewportWidthPx?: number | null;
      viewportHeightPx?: number | null;
      devicePixelRatio?: number | null;
      screenXPx?: number | null;
      screenYPx?: number | null;
    }>("/api/calibrations/active", { params: { deviceFingerprint } });
    return {
      calibrated: data.calibrated,
      calibratedAt: data.calibratedAt,
      viewportWidthPx: data.viewportWidthPx ?? null,
      viewportHeightPx: data.viewportHeightPx ?? null,
      devicePixelRatio: data.devicePixelRatio ?? null,
      screenX: data.screenXPx ?? null,
      screenY: data.screenYPx ?? null,
    };
  } catch {
    return null;
  }
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
