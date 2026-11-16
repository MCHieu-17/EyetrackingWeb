import { describe, expect, it } from "vitest";

import {
  detectDisplayViolation,
  zoomPercent,
  type DisplayGuardInput,
} from "./display-guard";

function input(overrides: Partial<DisplayGuardInput> = {}): DisplayGuardInput {
  return {
    dpr: 1,
    baselineDpr: 1,
    visualScale: 1,
    fullscreenElement: false,
    outerWidth: 1280,
    outerHeight: 800,
    innerWidth: 1280,
    innerHeight: 700,
    screenWidth: 1920,
    screenHeight: 1080,
    screenX: 100,
    screenY: 50,
    coarsePointer: false,
    ...overrides,
  };
}

describe("detectDisplayViolation", () => {
  it("returns null for a normal desktop display", () => {
    expect(detectDisplayViolation(input())).toBeNull();
  });

  it("detects browser page zoom from a DPR change", () => {
    expect(
      detectDisplayViolation(input({ dpr: 1.25, baselineDpr: 1 })),
    ).toBe("page_zoom");
  });

  it("ignores tiny DPR rounding below the 1.5% tolerance", () => {
    expect(
      detectDisplayViolation(input({ dpr: 1.01, baselineDpr: 1 })),
    ).toBeNull();
  });

  it("does not divide by an invalid baseline DPR", () => {
    expect(
      detectDisplayViolation(input({ dpr: 2, baselineDpr: 0 })),
    ).toBeNull();
    expect(
      detectDisplayViolation(input({ dpr: 2, baselineDpr: Number.NaN })),
    ).toBeNull();
  });

  it("detects pinch zoom via visualViewport scale", () => {
    expect(
      detectDisplayViolation(input({ visualScale: 1.05 })),
    ).toBe("pinch_zoom");
    expect(
      detectDisplayViolation(input({ visualScale: 0.95 })),
    ).toBe("pinch_zoom");
  });

  it("ignores visual scale changes within 1%", () => {
    expect(
      detectDisplayViolation(input({ visualScale: 1.005 })),
    ).toBeNull();
  });

  it("prioritizes page zoom over pinch zoom", () => {
    expect(
      detectDisplayViolation(
        input({ dpr: 1.5, baselineDpr: 1, visualScale: 1.1 }),
      ),
    ).toBe("page_zoom");
  });

  it("detects the Fullscreen API", () => {
    expect(
      detectDisplayViolation(input({ fullscreenElement: true })),
    ).toBe("fullscreen");
  });

  it("detects a desktop F11/fullscreen window", () => {
    expect(
      detectDisplayViolation(
        input({
          outerWidth: 1920,
          outerHeight: 1080,
          innerWidth: 1920,
          innerHeight: 1080,
          screenWidth: 1920,
          screenHeight: 1080,
          screenX: 0,
          screenY: 0,
        }),
      ),
    ).toBe("browser_fullscreen");
  });

  it("allows a 2px tolerance for fullscreen geometry", () => {
    expect(
      detectDisplayViolation(
        input({
          outerWidth: 1922,
          outerHeight: 1082,
          innerWidth: 1920,
          innerHeight: 1082,
          screenWidth: 1920,
          screenHeight: 1080,
          screenX: 2,
          screenY: 2,
        }),
      ),
    ).toBe("browser_fullscreen");
  });

  it("does not flag a fullscreen-sized window that is not tall enough", () => {
    expect(
      detectDisplayViolation(
        input({
          outerWidth: 1920,
          outerHeight: 1080,
          innerWidth: 1920,
          innerHeight: 900,
          screenWidth: 1920,
          screenHeight: 1080,
          screenX: 0,
          screenY: 0,
        }),
      ),
    ).toBeNull();
  });

  it("does not flag an offset window", () => {
    expect(
      detectDisplayViolation(
        input({
          outerWidth: 1920,
          outerHeight: 1080,
          innerWidth: 1920,
          innerHeight: 1080,
          screenWidth: 1920,
          screenHeight: 1080,
          screenX: 8,
          screenY: 0,
        }),
      ),
    ).toBeNull();
  });

  it("skips the browser fullscreen heuristic on coarse pointers", () => {
    expect(
      detectDisplayViolation(
        input({
          outerWidth: 1920,
          outerHeight: 1080,
          innerWidth: 1920,
          innerHeight: 1080,
          screenWidth: 1920,
          screenHeight: 1080,
          screenX: 0,
          screenY: 0,
          coarsePointer: true,
        }),
      ),
    ).toBeNull();
  });
});

describe("zoomPercent", () => {
  it("reports the current zoom relative to baseline", () => {
    expect(zoomPercent(1.25, 1)).toBe(125);
    expect(zoomPercent(2, 1)).toBe(200);
    expect(zoomPercent(4 / 3, 1)).toBe(133);
  });

  it("returns 100 for invalid values", () => {
    expect(zoomPercent(1, 0)).toBe(100);
    expect(zoomPercent(Number.NaN, 1)).toBe(100);
    expect(zoomPercent(1, Number.NaN)).toBe(100);
  });
});
