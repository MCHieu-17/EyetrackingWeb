import { describe, expect, it, vi } from "vitest";

import {
  currentFromOriginal,
  measureVisibleRect,
  rectToOriginal,
  transformToOriginal,
} from "./coordinate-space";

const calibration = {
  w: 1700,
  h: 900,
  dpr: 1,
  screenX: 0,
  screenY: 0,
};

describe("coordinate-space", () => {
  it("đo vùng đang thấy của cửa sổ trong viewport gốc", () => {
    vi.stubGlobal("innerWidth", 1200);
    vi.stubGlobal("innerHeight", 600);
    vi.stubGlobal("screenX", 200);
    vi.stubGlobal("screenY", 200);

    const visible = measureVisibleRect(calibration);
    expect(visible).not.toBeNull();
    expect(visible!.left).toBeCloseTo(200 / 1700, 10);
    expect(visible!.top).toBeCloseTo(200 / 900, 10);
    expect(visible!.width).toBeCloseTo(1200 / 1700, 10);
    expect(visible!.height).toBeCloseTo(600 / 900, 10);

    vi.unstubAllGlobals();
  });

  it("góc trên-trái vùng đang thấy quy về current (0,0)", () => {
    const visible = {
      left: 200 / 1700,
      top: 200 / 900,
      width: 1200 / 1700,
      height: 600 / 900,
    };
    const current = currentFromOriginal(
      { x: 200 / 1700, y: 200 / 900 },
      visible,
    );
    expect(current.x).toBeCloseTo(0, 10);
    expect(current.y).toBeCloseTo(0, 10);
  });

  it("rect DOM hiện tại được quy đổi sang hệ gốc", () => {
    const visible = {
      left: 0.1,
      top: 0.2,
      width: 0.5,
      height: 0.4,
    };
    const rect = rectToOriginal(
      { code: "header", xMin: 0.2, yMin: 0.25, xMax: 0.6, yMax: 0.5 },
      visible,
    );
    expect(rect.xMin).toBeCloseTo(0.2, 10);
    expect(rect.yMin).toBeCloseTo(0.3, 10);
    expect(rect.xMax).toBeCloseTo(0.4, 10);
    expect(rect.yMax).toBeCloseTo(0.4, 10);

    const transform = transformToOriginal(
      { left: 0.2, top: 0.25, width: 0.4, height: 0.25 },
      visible,
    );
    expect(transform.left).toBeCloseTo(0.2, 10);
    expect(transform.width).toBeCloseTo(0.2, 10);
  });
});
