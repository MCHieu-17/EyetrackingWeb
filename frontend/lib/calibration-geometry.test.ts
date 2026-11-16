import { describe, expect, it } from "vitest";

import {
  buildCalibrationPoints,
  calibrationMargins,
  transformGazePoint,
  type ViewportRect,
} from "@/lib/calibration-geometry";

function viewport(overrides: Partial<ViewportRect> = {}): ViewportRect {
  return { width: 1000, height: 800, screenX: 0, screenY: 0, ...overrides };
}

describe("calibrationMargins", () => {
  it("dùng margin mặc định khi viewport không hợp lệ", () => {
    expect(calibrationMargins(0, 0)).toEqual({ x: 0.04, y: 0.04 });
    expect(calibrationMargins(-100, 800)).toEqual({ x: 0.04, y: 0.04 });
  });

  it("suy ra lề từ 40px trên viewport thường", () => {
    const margins = calibrationMargins(1920, 1080);

    expect(margins.x).toBeCloseTo(40 / 1920, 10);
    expect(margins.y).toBeCloseTo(40 / 1080, 10);
  });

  it("kẹp lề trong khoảng 0.015..0.06", () => {
    expect(calibrationMargins(10000, 10000)).toEqual({ x: 0.015, y: 0.015 });
    expect(calibrationMargins(100, 100)).toEqual({ x: 0.06, y: 0.06 });
  });
});

describe("buildCalibrationPoints", () => {
  it("tạo lưới 5x5 với id tăng dần", () => {
    const points = buildCalibrationPoints();

    expect(points).toHaveLength(25);
    expect(points.map((point) => point.id)).toEqual(
      Array.from({ length: 25 }, (_, index) => `p${index}`),
    );
  });

  it("dùng margin mặc định 0.04", () => {
    const points = buildCalibrationPoints();

    expect(points[0]).toEqual({ id: "p0", x: 0.04, y: 0.04 });
    expect(points[24].id).toBe("p24");
    expect(points[24].x).toBeCloseTo(0.96, 10);
    expect(points[24].y).toBeCloseTo(0.96, 10);
  });

  it("xếp theo hàng: x tăng trước, sau đó mới tới y", () => {
    const points = buildCalibrationPoints();

    expect(points[1].y).toBe(points[0].y);
    expect(points[1].x).toBeGreaterThan(points[0].x);
    expect(points[5].x).toBe(points[0].x);
    expect(points[5].y).toBeGreaterThan(points[0].y);
  });

  it("áp dụng margin tuỳ chỉnh theo từng trục", () => {
    const points = buildCalibrationPoints({ x: 0.1, y: 0.2 });

    expect(points[0]).toEqual({ id: "p0", x: 0.1, y: 0.2 });
    expect(points[12].id).toBe("p12");
    expect(points[12].x).toBeCloseTo(0.5, 10);
    expect(points[12].y).toBeCloseTo(0.5, 10);
    expect(points[24].id).toBe("p24");
    expect(points[24].x).toBeCloseTo(0.9, 10);
    expect(points[24].y).toBeCloseTo(0.8, 10);
  });
});

describe("transformGazePoint", () => {
  it("giữ nguyên điểm khi viewport không đổi", () => {
    const rect = viewport();

    expect(transformGazePoint(0.25, 0.75, rect, rect)).toEqual({ x: 0.25, y: 0.75 });
  });

  it("quy đổi theo vị trí vật lý khi viewport hiện tại nhỏ hơn", () => {
    const calibration = viewport();
    const current = viewport({ width: 500, height: 400 });

    expect(transformGazePoint(0.5, 0.5, calibration, current)).toEqual({ x: 1, y: 1 });
    expect(transformGazePoint(0.25, 0.25, calibration, current)).toEqual({ x: 0.5, y: 0.5 });
  });

  it("quy đổi theo cửa sổ hiện tại nằm trong viewport gốc", () => {
    const calibration = viewport({ width: 1700, height: 900 });
    const current = viewport({
      width: 1200,
      height: 600,
      screenX: 200,
      screenY: 200,
    });

    // Gaze ở chính giữa cửa sổ hiện tại: raw = 800/1700, 500/900.
    const center = transformGazePoint(
      800 / 1700,
      500 / 900,
      calibration,
      current,
    );
    expect(center.x).toBeCloseTo(0.5, 10);
    expect(center.y).toBeCloseTo(0.5, 10);
    // Gaze ở góc trên-trái cửa sổ hiện tại: raw = 200/1700, 200/900.
    const topLeft = transformGazePoint(
      200 / 1700,
      200 / 900,
      calibration,
      current,
    );
    expect(topLeft.x).toBeCloseTo(0, 10);
    expect(topLeft.y).toBeCloseTo(0, 10);
  });

  it("tính cả độ lệch cửa sổ trên màn hình", () => {
    const calibration = viewport({ screenX: 100, screenY: 50 });
    const current = viewport({ screenX: 50, screenY: 50 });

    expect(transformGazePoint(0.5, 0.5, calibration, current)).toEqual({ x: 0.55, y: 0.5 });
  });

  it("trả nguyên điểm khi viewport hiện tại không hợp lệ", () => {
    const calibration = viewport();

    expect(transformGazePoint(0.3, 0.6, calibration, viewport({ width: 0 }))).toEqual({
      x: 0.3,
      y: 0.6,
    });
    expect(transformGazePoint(0.3, 0.6, calibration, viewport({ height: -1 }))).toEqual({
      x: 0.3,
      y: 0.6,
    });
  });
});
