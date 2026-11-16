import { describe, expect, it } from "vitest";

import { fittedImageTransform } from "./image-transform";

const VIEWPORT = { width: 1600, height: 900 };

describe("fittedImageTransform", () => {
  it("fills the container when page and container share 16:9", () => {
    const result = fittedImageTransform(
      { left: 0, top: 0, width: 1600, height: 900 },
      1920,
      1080,
      VIEWPORT.width,
      VIEWPORT.height,
    );

    expect(result).toEqual({ left: 0, top: 0, width: 1, height: 1 });
  });

  it("letterboxes a 4:3 page inside a 16:9 container", () => {
    const result = fittedImageTransform(
      { left: 0, top: 0, width: 1600, height: 900 },
      800,
      600,
      VIEWPORT.width,
      VIEWPORT.height,
    );

    expect(result).not.toBeNull();
    expect(result!.left).toBeCloseTo(0.125, 6);
    expect(result!.top).toBeCloseTo(0, 6);
    expect(result!.width).toBeCloseTo(0.75, 6);
    expect(result!.height).toBeCloseTo(1, 6);
  });

  it("centers the fitted page inside an offset container", () => {
    // Container 1000x500, page 4:3 → ảnh 666.67x500, lệch 166.67 mỗi bên.
    const result = fittedImageTransform(
      { left: 200, top: 100, width: 1000, height: 500 },
      800,
      600,
      VIEWPORT.width,
      VIEWPORT.height,
    );

    expect(result).not.toBeNull();
    expect(result!.left).toBeCloseTo((200 + 500 / 3) / VIEWPORT.width, 6);
    expect(result!.top).toBeCloseTo(100 / VIEWPORT.height, 6);
    expect(result!.width).toBeCloseTo((2000 / 3) / VIEWPORT.width, 6);
    expect(result!.height).toBeCloseTo(500 / VIEWPORT.height, 6);
  });

  it("normalizes the image rect against the current viewport", () => {
    const result = fittedImageTransform(
      { left: 100, top: 50, width: 800, height: 600 },
      1600,
      1200,
      1600,
      900,
    );

    expect(result).not.toBeNull();
    expect(result!.left).toBeCloseTo(0.0625, 6);
    expect(result!.top).toBeCloseTo(50 / 900, 6);
    expect(result!.width).toBeCloseTo(0.5, 6);
    expect(result!.height).toBeCloseTo(600 / 900, 6);
  });

  it("returns null when the page or viewport has no size", () => {
    expect(
      fittedImageTransform(
        { left: 0, top: 0, width: 1600, height: 900 },
        0,
        600,
        VIEWPORT.width,
        VIEWPORT.height,
      ),
    ).toBeNull();
    expect(
      fittedImageTransform(
        { left: 0, top: 0, width: 1600, height: 900 },
        800,
        600,
        0,
        VIEWPORT.height,
      ),
    ).toBeNull();
  });
});
