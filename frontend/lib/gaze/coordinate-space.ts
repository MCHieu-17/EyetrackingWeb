import type { CalibrationScreenSnapshot } from "@/lib/api/calibration-session";
import type { AoiRect, VisibleRect } from "@/lib/api/aoi";

export interface Point {
  x: number;
  y: number;
}

/**
 * Vùng đang thấy của cửa sổ trong hệ toạ độ viewport lúc calibration.
 *
 * `left/top` là vị trí cửa sổ hiện tại so với cửa sổ lúc calibration, tính
 * theo CSS pixel (screenX/screenY), chuẩn hoá theo width/height calibration.
 * `width/height` là tỷ lệ kích thước cửa sổ hiện tại so với calibration.
 *
 * Không nhân screenX với DPR: screenX là toạ độ cửa sổ (DIP/CSS), còn DPR
 * thay đổi khi browser page zoom; nhân vào sẽ làm lệch gốc.
 */
export function measureVisibleRect(
  calibration: CalibrationScreenSnapshot,
): VisibleRect | null {
  if (typeof window === "undefined") return null;
  if (!(calibration.w > 0) || !(calibration.h > 0)) return null;
  const width = window.innerWidth / calibration.w;
  const height = window.innerHeight / calibration.h;
  if (!(width > 0) || !(height > 0)) return null;
  return {
    left: (window.screenX - calibration.screenX) / calibration.w,
    top: (window.screenY - calibration.screenY) / calibration.h,
    width,
    height,
  };
}

/** Quy đổi toạ độ gốc sang vị trí trong viewport hiện tại (0..1). */
export function currentFromOriginal(
  original: Point,
  visible: VisibleRect | null | undefined,
): Point {
  if (!visible || !(visible.width > 0) || !(visible.height > 0)) {
    return original;
  }
  return {
    x: (original.x - visible.left) / visible.width,
    y: (original.y - visible.top) / visible.height,
  };
}

/** Quy đổi rect DOM hiện tại (0..1 viewport hiện tại) sang hệ gốc. */
export function rectToOriginal(rect: AoiRect, visible: VisibleRect): AoiRect {
  return {
    code: rect.code,
    xMin: visible.left + rect.xMin * visible.width,
    yMin: visible.top + rect.yMin * visible.height,
    xMax: visible.left + rect.xMax * visible.width,
    yMax: visible.top + rect.yMax * visible.height,
  };
}

/** Quy đổi image transform hiện tại (0..1 viewport hiện tại) sang hệ gốc. */
export function transformToOriginal(
  transform: Record<string, number>,
  visible: VisibleRect,
): Record<string, number> {
  const left = Number(transform.left ?? 0);
  const top = Number(transform.top ?? 0);
  const width = Number(transform.width ?? 1);
  const height = Number(transform.height ?? 1);
  return {
    left: visible.left + left * visible.width,
    top: visible.top + top * visible.height,
    width: width * visible.width,
    height: height * visible.height,
  };
}
