import { describe, expect, it } from "vitest";

import {
  clamp01,
  normalizeRect,
  numberValue,
  relativeRect,
  screenBox,
} from "@/lib/aoi/geometry";

function makeRect(
  left: number,
  top: number,
  width: number,
  height: number,
): DOMRect {
  return {
    x: left,
    y: top,
    left,
    top,
    width,
    height,
    right: left + width,
    bottom: top + height,
    toJSON: () => ({}),
  } as DOMRect;
}

describe("clamp01", () => {
  it("kẹp giá trị dưới 0 về 0", () => {
    expect(clamp01(-0.5)).toBe(0);
    expect(clamp01(-100)).toBe(0);
  });

  it("kẹp giá trị trên 1 về 1", () => {
    expect(clamp01(1.5)).toBe(1);
    expect(clamp01(100)).toBe(1);
  });

  it("giữ nguyên giá trị trong khoảng 0..1", () => {
    expect(clamp01(0)).toBe(0);
    expect(clamp01(0.42)).toBe(0.42);
    expect(clamp01(1)).toBe(1);
  });
});

describe("normalizeRect", () => {
  it("sắp xếp lại toạ độ khi kéo ngược", () => {
    expect(normalizeRect(0.8, 0.9, 0.2, 0.1)).toEqual({
      xMin: 0.2,
      yMin: 0.1,
      xMax: 0.8,
      yMax: 0.9,
    });
  });

  it("kẹp toạ độ tràn ra ngoài khoảng 0..1", () => {
    expect(normalizeRect(-0.5, -1, 1.5, 2)).toEqual({
      xMin: 0,
      yMin: 0,
      xMax: 1,
      yMax: 1,
    });
  });

  it("trả về rect rỗng khi bắt đầu và kết thúc cùng điểm", () => {
    expect(normalizeRect(0.3, 0.4, 0.3, 0.4)).toEqual({
      xMin: 0.3,
      yMin: 0.4,
      xMax: 0.3,
      yMax: 0.4,
    });
  });
});

describe("screenBox", () => {
  it("tính box từ hai điểm", () => {
    expect(screenBox(10, 20, 40, 60)).toEqual({
      left: 10,
      top: 20,
      width: 30,
      height: 40,
    });
  });

  it("cho cùng kết quả khi kéo ngược", () => {
    expect(screenBox(40, 60, 10, 20)).toEqual(screenBox(10, 20, 40, 60));
  });

  it("giữ toạ độ âm và dùng độ dài tuyệt đối", () => {
    expect(screenBox(-10, -20, 10, 20)).toEqual({
      left: -10,
      top: -20,
      width: 20,
      height: 40,
    });
  });
});

describe("relativeRect", () => {
  it("chuẩn hoá box theo anchor", () => {
    const anchor = makeRect(100, 50, 200, 100);

    expect(
      relativeRect({ left: 150, top: 75, width: 100, height: 50 }, anchor),
    ).toEqual({
      xMin: 0.25,
      yMin: 0.25,
      xMax: 0.75,
      yMax: 0.75,
    });
  });

  it("kẹp box tràn ra ngoài anchor", () => {
    const anchor = makeRect(100, 50, 200, 100);

    expect(
      relativeRect({ left: 0, top: 0, width: 400, height: 200 }, anchor),
    ).toEqual({
      xMin: 0,
      yMin: 0,
      xMax: 1,
      yMax: 1,
    });
  });

  it("trả về rect rỗng khi box nằm ngoài anchor", () => {
    const anchor = makeRect(100, 50, 200, 100);

    expect(
      relativeRect({ left: 400, top: 300, width: 10, height: 10 }, anchor),
    ).toEqual({
      xMin: 1,
      yMin: 1,
      xMax: 1,
      yMax: 1,
    });
  });
});

describe("numberValue", () => {
  it("đọc số từ geometry", () => {
    expect(numberValue({ xMin: 0.25 }, "xMin")).toBe(0.25);
  });

  it("trả về 0 khi thiếu hoặc không phải số", () => {
    expect(numberValue({}, "xMin")).toBe(0);
    expect(numberValue({ xMin: "abc" }, "xMin")).toBe(0);
    expect(numberValue({ xMin: Number.POSITIVE_INFINITY }, "xMin")).toBe(0);
  });
});
