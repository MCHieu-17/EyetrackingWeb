// lib/calibration-geometry.ts — hình học thuần cho calibration/gaze mapping.
// Tách khỏi lib/api/calibration.ts để phần logic thuần (dễ test) không bị trộn
// với tầng HTTP/localStorage. Test: frontend/tests/calibration-geometry.test.ts

export interface CalPoint {
  id: string;
  x: number;
  y: number;
}

const GRID = 5;

/**
 * Khoảng cách tối thiểu (px) từ TÂM của chấm ngoài cùng tới rìa màn hình.
 * Chấm lớn nhất có đường kính 64px (size-16) → bán kính 32px, cộng ~8px
 * khoảng thở để chấm (và vòng focus) không bị cắt khi nằm sát rìa.
 */
const CALIBRATION_EDGE_INSET_PX = 40;

/** Chặn dưới/trên để màn hình siêu rộng hoặc rất nhỏ vẫn cân đối. */
const MIN_MARGIN = 0.015;
const MAX_MARGIN = 0.06;

/** Dùng khi chưa biết kích thước viewport (SSR) — sát rìa nhưng an toàn. */
const DEFAULT_CALIBRATION_MARGIN = 0.04;

interface CalibrationMargins {
  x: number;
  y: number;
}

function clampMargin(value: number): number {
  return Math.min(MAX_MARGIN, Math.max(MIN_MARGIN, value));
}

/**
 * Lề (tỷ lệ 0..1) cho từng trục, suy ra từ kích thước viewport sao cho
 * khoảng cách pixel tới rìa luôn đồng đều trên mọi loại màn hình:
 * màn hình 13" hay 27" đều đặt 25 điểm sát rìa/góc như nhau.
 */
export function calibrationMargins(
  viewportWidth: number,
  viewportHeight: number,
): CalibrationMargins {
  if (!(viewportWidth > 0) || !(viewportHeight > 0)) {
    return { x: DEFAULT_CALIBRATION_MARGIN, y: DEFAULT_CALIBRATION_MARGIN };
  }
  return {
    x: clampMargin(CALIBRATION_EDGE_INSET_PX / viewportWidth),
    y: clampMargin(CALIBRATION_EDGE_INSET_PX / viewportHeight),
  };
}

function axisPositions(margin: number): number[] {
  return Array.from(
    { length: GRID },
    (_, i) => margin + (i * (1 - 2 * margin)) / (GRID - 1),
  );
}

/**
 * Lưới 5×5 (25 điểm). `margins` cho phép đẩy lưới sát rìa theo từng trục;
 * bỏ trống thì dùng margin mặc định.
 */
export function buildCalibrationPoints(margins?: CalibrationMargins): CalPoint[] {
  const marginX = margins?.x ?? DEFAULT_CALIBRATION_MARGIN;
  const marginY = margins?.y ?? DEFAULT_CALIBRATION_MARGIN;
  const xs = axisPositions(marginX);
  const ys = axisPositions(marginY);
  const points: CalPoint[] = [];
  let n = 0;
  for (const y of ys) {
    for (const x of xs) {
      points.push({ id: `p${n}`, x, y });
      n += 1;
    }
  }
  return points;
}

/** Hình chữ nhật vật lý của viewport trên màn hình (CSS px + DPR). */
export interface ViewportRect {
  width: number;
  height: number;
  dpr: number;
  screenX: number;
  screenY: number;
}

/**
 * Quy đổi một điểm gaze từ viewport lúc calibration sang viewport hiện tại.
 *
 * `screenX/screenY` là toạ độ cửa sổ (CSS/DIP), KHÔNG nhân với DPR: khi
 * browser page zoom, DPR tăng nhưng vị trí cửa sổ trên màn hình không đổi.
 * Vùng đang thấy của cửa sổ hiện tại trong hệ viewport calibration là:
 *
 *   left  = (current.screenX - calibration.screenX) / calibration.width
 *   width = current.width / calibration.width
 *
 * rồi quy đổi điểm gaze vào vùng đó.
 */
export function transformGazePoint(
  x: number,
  y: number,
  calibration: ViewportRect,
  current: ViewportRect,
): { x: number; y: number } {
  if (
    calibration.width <= 0 ||
    calibration.height <= 0 ||
    current.width <= 0 ||
    current.height <= 0
  ) {
    return { x, y };
  }
  const left = (current.screenX - calibration.screenX) / calibration.width;
  const top = (current.screenY - calibration.screenY) / calibration.height;
  const width = current.width / calibration.width;
  const height = current.height / calibration.height;
  if (width <= 0 || height <= 0) return { x, y };
  return {
    x: (x - left) / width,
    y: (y - top) / height,
  };
}
