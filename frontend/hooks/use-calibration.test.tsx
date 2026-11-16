import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useCalibration } from "./use-calibration";

const mocks = vi.hoisted(() => {
  const point = (id: string, x: number, y: number) => ({ id, x, y });
  return {
    buildCalibrationPoints: vi.fn(() => [
      point("p0", 0.04, 0.04),
      point("p1", 0.5, 0.5),
      point("p2", 0.96, 0.96),
    ]),
    calibrationMargins: vi.fn(() => ({ x: 0.04, y: 0.04 })),
    createGazeSession: vi.fn(),
    deleteGazeSession: vi.fn(),
    submitCalibrationSample: vi.fn(),
    trainGazeSession: vi.fn(),
    storeGazeSession: vi.fn(),
    clearStoredGazeSession: vi.fn(),
    downloadGazeModel: vi.fn(async () => null),
    saveCalibrationToBackend: vi.fn(async () => {}),
    bytesToBase64: vi.fn(() => ""),
    getDeviceFingerprint: vi.fn(() => "device-1"),
  };
});

vi.mock("@/lib/api/calibration", () => ({
  buildCalibrationPoints: mocks.buildCalibrationPoints,
  calibrationMargins: mocks.calibrationMargins,
  createGazeSession: mocks.createGazeSession,
  deleteGazeSession: mocks.deleteGazeSession,
  submitCalibrationSample: mocks.submitCalibrationSample,
  trainGazeSession: mocks.trainGazeSession,
  storeGazeSession: mocks.storeGazeSession,
  clearStoredGazeSession: mocks.clearStoredGazeSession,
  downloadGazeModel: mocks.downloadGazeModel,
  saveCalibrationToBackend: mocks.saveCalibrationToBackend,
  bytesToBase64: mocks.bytesToBase64,
}));

vi.mock("@/lib/api/student", () => ({
  getDeviceFingerprint: mocks.getDeviceFingerprint,
}));

const originalMediaDevices = Object.getOwnPropertyDescriptor(
  navigator,
  "mediaDevices",
);

beforeEach(() => {
  mocks.createGazeSession.mockReset();
  mocks.deleteGazeSession.mockReset();
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: {
      getUserMedia: vi.fn().mockResolvedValue({
        getTracks: () => [{ stop: vi.fn() }],
      }),
    },
  });
});

afterEach(() => {
  cleanup();
  if (originalMediaDevices) {
    Object.defineProperty(navigator, "mediaDevices", originalMediaDevices);
  } else {
    Reflect.deleteProperty(navigator, "mediaDevices");
  }
});

function renderCalibration(initialPaused: boolean) {
  return renderHook(
    ({ paused }: { paused: boolean }) =>
      useCalibration({ onComplete: vi.fn(), paused }),
    { initialProps: { paused: initialPaused } },
  );
}

describe("useCalibration paused", () => {
  it("does not create a session while paused and recreates one after unpause", async () => {
    mocks.createGazeSession
      .mockResolvedValueOnce({ ok: true, sessionId: "gaze-1" })
      .mockResolvedValueOnce({ ok: true, sessionId: "gaze-2" });

    const { result, rerender } = renderCalibration(true);

    await act(async () => {
      await Promise.resolve();
    });
    expect(mocks.createGazeSession).not.toHaveBeenCalled();
    expect(result.current.phase).toBe("idle");
    expect(result.current.sessionReady).toBe(false);

    rerender({ paused: false });

    await waitFor(() => expect(result.current.sessionReady).toBe(true));
    expect(mocks.createGazeSession).toHaveBeenCalledTimes(1);
    expect(result.current.phase).toBe("calibrating");

    rerender({ paused: true });

    await waitFor(() =>
      expect(mocks.deleteGazeSession).toHaveBeenCalledWith("gaze-1"),
    );
    expect(result.current.sessionReady).toBe(false);
    expect(result.current.phase).toBe("idle");

    rerender({ paused: false });

    await waitFor(() => expect(result.current.sessionReady).toBe(true));
    expect(mocks.createGazeSession).toHaveBeenCalledTimes(2);
    expect(mocks.deleteGazeSession).toHaveBeenCalledTimes(1);
  });
});
