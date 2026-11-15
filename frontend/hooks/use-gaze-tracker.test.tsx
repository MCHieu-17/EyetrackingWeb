import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useGazeTracker } from "./use-gaze-tracker";

class FakeWebSocket {
  static OPEN = 1;
  static instances: FakeWebSocket[] = [];

  readyState = FakeWebSocket.OPEN;
  bufferedAmount = 0;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = 3;
  });

  constructor(public readonly url: string) {
    FakeWebSocket.instances.push(this);
    queueMicrotask(() => {
      if (this.readyState === FakeWebSocket.OPEN) {
        this.onopen?.(new Event("open"));
      }
    });
  }
}

const originalMediaDevices = Object.getOwnPropertyDescriptor(
  navigator,
  "mediaDevices",
);

describe("useGazeTracker cleanup", () => {
  const stopTrack = vi.fn();

  beforeEach(() => {
    vi.useFakeTimers();
    FakeWebSocket.instances = [];
    stopTrack.mockReset();
    const storage = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
      clear: () => storage.clear(),
    });
    localStorage.setItem("gaze_session_id", "gaze-session-1");

    vi.stubGlobal("WebSocket", FakeWebSocket);
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: stopTrack }],
        }),
      },
    });
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    Object.defineProperty(HTMLVideoElement.prototype, "videoWidth", {
      configurable: true,
      get: () => 640,
    });
    Object.defineProperty(HTMLVideoElement.prototype, "videoHeight", {
      configurable: true,
      get: () => 480,
    });
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      drawImage: vi.fn(),
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(
      (callback) => callback(new Blob(["frame"], { type: "image/jpeg" })),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    if (originalMediaDevices) {
      Object.defineProperty(navigator, "mediaDevices", originalMediaDevices);
    } else {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (navigator as any).mediaDevices;
    }
  });

  it("closes the active socket, stops tracks and resets public state on disable", async () => {
    const onFrame = vi.fn();
    const onPoint = vi.fn();
    const { result, rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) =>
        useGazeTracker({
          enabled,
          calibrated: true,
          allowSimulation: false,
          onPoint,
          onFrame,
          getContext: () => ({
            presentationId: "presentation-1",
            layoutGeneration: 0,
            surface: "lesson",
          }),
        }),
      { initialProps: { enabled: true } },
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(FakeWebSocket.instances).toHaveLength(1);
    const socket = FakeWebSocket.instances[0];
    const lateMessage = socket.onmessage;
    expect(result.current.stream).not.toBeNull();
    expect(result.current.source).toBe("real");

    act(() => {
      rerender({ enabled: false });
    });

    expect(socket.close).toHaveBeenCalledTimes(1);
    expect(stopTrack).toHaveBeenCalled();
    expect(result.current).toEqual({ stream: null, source: "off" });

    // Message đến sau khi cleanup không được chạm tới callback công khai.
    act(() => {
      lateMessage?.(
        new MessageEvent("message", {
          data: JSON.stringify({
            ok: true,
            x: 0.5,
            y: 0.5,
            status: "ok",
            frameId: "late-frame",
            sequence: 99,
            presentationId: "presentation-1",
            layoutGeneration: 0,
          }),
        }),
      );
    });
    expect(onPoint).not.toHaveBeenCalled();
    expect(onFrame).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(socket.send).not.toHaveBeenCalled();
  });
});
