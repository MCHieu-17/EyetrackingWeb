import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useDisplayGuard } from "./use-display-guard";

const calibrationMocks = vi.hoisted(() => ({
  snapshot: null as { dpr: number } | null,
}));

vi.mock("@/lib/api/calibration", () => ({
  getCalibrationScreenSnapshot: () => calibrationMocks.snapshot,
}));

interface Metrics {
  outerWidth: number;
  outerHeight: number;
  innerWidth: number;
  innerHeight: number;
  screenWidth: number;
  screenHeight: number;
  screenX: number;
  screenY: number;
}

let dpr = 1;
let coarsePointer = false;
let fullscreenElement: Element | null = null;
let metrics: Metrics;
let visualViewport: EventTarget & { scale: number };
let exitFullscreenMock: ReturnType<typeof vi.fn>;
const restores: Array<() => void> = [];

function stubGetter(target: object, name: string, get: () => unknown): void {
  const original = Object.getOwnPropertyDescriptor(target, name);
  Object.defineProperty(target, name, {
    configurable: true,
    get,
  });
  restores.push(() => {
    if (original) Object.defineProperty(target, name, original);
    else Reflect.deleteProperty(target, name);
  });
}

function stubValue(target: object, name: string, value: unknown): void {
  const original = Object.getOwnPropertyDescriptor(target, name);
  Object.defineProperty(target, name, {
    configurable: true,
    writable: true,
    value,
  });
  restores.push(() => {
    if (original) Object.defineProperty(target, name, original);
    else Reflect.deleteProperty(target, name);
  });
}

function readMetrics(): Metrics {
  return { ...metrics };
}

function applyMetrics(next: Partial<Metrics>): void {
  metrics = { ...metrics, ...next };
}

function renderGuard(enabled = true, mode: "reader" | "calibration" = "reader") {
  return renderHook(() => useDisplayGuard({ enabled, mode }));
}

beforeEach(() => {
  calibrationMocks.snapshot = null;
  dpr = 1;
  coarsePointer = false;
  fullscreenElement = null;
  metrics = {
    outerWidth: 1280,
    outerHeight: 800,
    innerWidth: 1280,
    innerHeight: 700,
    screenWidth: 1920,
    screenHeight: 1080,
    screenX: 100,
    screenY: 50,
  };
  visualViewport = Object.assign(new EventTarget(), { scale: 1 });
  exitFullscreenMock = vi.fn().mockResolvedValue(undefined);

  stubGetter(window, "devicePixelRatio", () => dpr);
  stubGetter(window, "outerWidth", () => readMetrics().outerWidth);
  stubGetter(window, "outerHeight", () => readMetrics().outerHeight);
  stubGetter(window, "innerWidth", () => readMetrics().innerWidth);
  stubGetter(window, "innerHeight", () => readMetrics().innerHeight);
  stubGetter(window, "screenX", () => readMetrics().screenX);
  stubGetter(window, "screenY", () => readMetrics().screenY);
  stubGetter(window.screen, "width", () => readMetrics().screenWidth);
  stubGetter(window.screen, "height", () => readMetrics().screenHeight);
  stubValue(window, "visualViewport", visualViewport);
  stubValue(window, "matchMedia", (query: string) => ({
    matches: coarsePointer,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }));
  stubGetter(document, "fullscreenElement", () => fullscreenElement);
  stubValue(document, "exitFullscreen", exitFullscreenMock);
});

afterEach(() => {
  cleanup();
  while (restores.length > 0) restores.pop()?.();
});

describe("useDisplayGuard", () => {
  it("uses the calibration DPR as baseline and reports page zoom", async () => {
    calibrationMocks.snapshot = { dpr: 1 };
    dpr = 1.5;

    const { result } = renderGuard();

    await waitFor(() => expect(result.current.blocked).toBe(true));
    expect(result.current.reason).toBe("page_zoom");
    expect(result.current.zoomPercent).toBe(150);
  });

  it("falls back to window DPR and reacts to resize, then recovers", () => {
    const { result } = renderGuard();

    expect(result.current.blocked).toBe(false);
    expect(result.current.zoomPercent).toBe(100);

    act(() => {
      dpr = 1.25;
      window.dispatchEvent(new Event("resize"));
    });

    expect(result.current.blocked).toBe(true);
    expect(result.current.reason).toBe("page_zoom");
    expect(result.current.zoomPercent).toBe(125);

    act(() => {
      dpr = 1;
      window.dispatchEvent(new Event("resize"));
    });

    expect(result.current.blocked).toBe(false);
    expect(result.current.reason).toBeNull();
  });

  it("detects pinch zoom via visualViewport", () => {
    const { result } = renderGuard();

    act(() => {
      visualViewport.scale = 1.1;
      visualViewport.dispatchEvent(new Event("resize"));
    });

    expect(result.current.blocked).toBe(true);
    expect(result.current.reason).toBe("pinch_zoom");
    expect(result.current.zoomPercent).toBe(100);
  });

  it("blocks and exits the Fullscreen API", () => {
    const { result } = renderGuard();

    act(() => {
      fullscreenElement = document.body;
      document.dispatchEvent(new Event("fullscreenchange"));
    });

    expect(result.current.blocked).toBe(true);
    expect(result.current.reason).toBe("fullscreen");
    expect(exitFullscreenMock).toHaveBeenCalled();

    act(() => {
      fullscreenElement = null;
      document.dispatchEvent(new Event("fullscreenchange"));
    });

    expect(result.current.blocked).toBe(false);
  });

  it("detects an F11-style fullscreen window on desktop", () => {
    const { result } = renderGuard();

    act(() => {
      applyMetrics({
        outerWidth: 1920,
        outerHeight: 1080,
        innerWidth: 1920,
        innerHeight: 1080,
        screenX: 0,
        screenY: 0,
      });
      window.dispatchEvent(new Event("resize"));
    });

    expect(result.current.blocked).toBe(true);
    expect(result.current.reason).toBe("browser_fullscreen");

    act(() => {
      coarsePointer = true;
      window.dispatchEvent(new Event("resize"));
    });

    expect(result.current.blocked).toBe(false);
  });

  it("blocks zoom shortcuts but keeps Ctrl/Cmd+0 available", () => {
    renderGuard();

    const plus = new KeyboardEvent("keydown", {
      key: "+",
      ctrlKey: true,
      cancelable: true,
    });
    act(() => window.dispatchEvent(plus));
    expect(plus.defaultPrevented).toBe(true);

    const minus = new KeyboardEvent("keydown", {
      key: "-",
      metaKey: true,
      cancelable: true,
    });
    act(() => window.dispatchEvent(minus));
    expect(minus.defaultPrevented).toBe(true);

    const reset = new KeyboardEvent("keydown", {
      key: "0",
      ctrlKey: true,
      cancelable: true,
    });
    act(() => window.dispatchEvent(reset));
    expect(reset.defaultPrevented).toBe(false);

    const plainPlus = new KeyboardEvent("keydown", {
      key: "+",
      cancelable: true,
    });
    act(() => window.dispatchEvent(plainPlus));
    expect(plainPlus.defaultPrevented).toBe(false);
  });

  it("blocks ctrl+wheel zoom and Safari gesture events", () => {
    renderGuard();

    const ctrlWheel = new WheelEvent("wheel", {
      ctrlKey: true,
      cancelable: true,
    });
    act(() => window.dispatchEvent(ctrlWheel));
    expect(ctrlWheel.defaultPrevented).toBe(true);

    const normalWheel = new WheelEvent("wheel", { cancelable: true });
    act(() => window.dispatchEvent(normalWheel));
    expect(normalWheel.defaultPrevented).toBe(false);

    const gesture = new Event("gesturestart", { cancelable: true });
    act(() => window.dispatchEvent(gesture));
    expect(gesture.defaultPrevented).toBe(true);
  });

  it("overrides requestFullscreen while enabled and restores it on unmount", async () => {
    const original = Element.prototype.requestFullscreen;
    const { unmount } = renderGuard();

    expect(typeof document.body.requestFullscreen).toBe("function");

    await expect(
      document.body.requestFullscreen(),
    ).rejects.toMatchObject({ name: "NotAllowedError" });

    unmount();

    expect(Element.prototype.requestFullscreen).toBe(original);
  });

  it("does not block or override when disabled", () => {
    dpr = 2;
    const original = Element.prototype.requestFullscreen;
    const { result } = renderGuard(false);

    expect(result.current.blocked).toBe(false);
    expect(Element.prototype.requestFullscreen).toBe(original);

    act(() => {
      dpr = 2.5;
      window.dispatchEvent(new Event("resize"));
    });
    expect(result.current.blocked).toBe(false);
  });

  it("cleans up listeners when unmounted", () => {
    const removeSpy = vi.spyOn(window, "removeEventListener");
    const clearIntervalSpy = vi.spyOn(window, "clearInterval");

    const { unmount } = renderGuard();
    unmount();

    expect(removeSpy).toHaveBeenCalledWith("resize", expect.any(Function));
    expect(removeSpy).toHaveBeenCalledWith(
      "keydown",
      expect.any(Function),
      true,
    );
    expect(clearIntervalSpy).toHaveBeenCalled();
  });
});
