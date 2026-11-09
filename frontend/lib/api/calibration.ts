// lib/api/calibration.ts — Facade giữ nguyên public API cho các import cũ.
// Logic đã tách sang:
// - calibration-session.ts: storage/session helpers (localStorage, snapshot).
// - calibration-api.ts: HTTP calls tới /gaze/* và /api/calibrations.
// Hình học thuần nằm ở lib/calibration-geometry.ts.

export {
  buildCalibrationPoints,
  calibrationMargins,
} from "@/lib/calibration-geometry";
export type { CalPoint } from "@/lib/calibration-geometry";

export * from "./calibration-session";
export * from "./calibration-api";
