import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAoiSnapshot } from "./use-aoi-snapshot";

interface LayoutSnapshot {
  id: string;
  presentationId: string;
  layoutGeneration: number;
  capturedAt: string;
}

const { layoutMock } = vi.hoisted(() => ({
  layoutMock:
    vi.fn<
      (
        presentationId: string,
        input: { layoutGeneration: number },
      ) => Promise<LayoutSnapshot>
    >(),
}));

vi.mock("@/lib/api/aoi", () => ({
  createPresentationLayout: layoutMock,
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function snapshot(
  presentationId: string,
  layoutGeneration: number,
): LayoutSnapshot {
  return {
    id: `snapshot-${presentationId}-${layoutGeneration}`,
    presentationId,
    layoutGeneration,
    capturedAt: "2026-01-01T00:00:00.000Z",
  };
}

async function flushSnapshotDebounce() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(300);
  });
}

describe("useAoiSnapshot", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    layoutMock.mockReset();
    layoutMock.mockImplementation((presentationId, input) =>
      Promise.resolve(snapshot(presentationId, input.layoutGeneration)),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("creates a layout for two presentations with identical geometry", async () => {
    const { result, rerender } = renderHook(
      ({ presentationId }: { presentationId: string }) =>
        useAoiSnapshot({
          sessionId: "session-1",
          presentationId,
          enabled: true,
          layoutKey: "reader",
        }),
      { initialProps: { presentationId: "presentation-1" } },
    );

    await flushSnapshotDebounce();

    expect(layoutMock).toHaveBeenCalledTimes(1);
    expect(layoutMock.mock.calls[0][0]).toBe("presentation-1");
    expect(result.current).toMatchObject({
      snapshotId: "snapshot-presentation-1-0",
      presentationId: "presentation-1",
      layoutGeneration: 0,
      ready: true,
    });

    rerender({ presentationId: "presentation-2" });

    // State cũ không được lộ sang presentation mới dù cùng hình học.
    expect(result.current).toMatchObject({
      snapshotId: null,
      presentationId: "presentation-2",
      ready: false,
    });

    await flushSnapshotDebounce();

    expect(layoutMock).toHaveBeenCalledTimes(2);
    expect(layoutMock.mock.calls[1][0]).toBe("presentation-2");
    expect(layoutMock.mock.calls[1][1].layoutGeneration).toBe(0);
    expect(result.current).toMatchObject({
      snapshotId: "snapshot-presentation-2-0",
      presentationId: "presentation-2",
      layoutGeneration: 0,
      ready: true,
    });
  });

  it("ignores a stale layout response from the previous presentation", async () => {
    const first = deferred<LayoutSnapshot>();
    const second = deferred<LayoutSnapshot>();
    layoutMock.mockImplementation((presentationId) =>
      presentationId === "presentation-1" ? first.promise : second.promise,
    );

    const { result, rerender } = renderHook(
      ({ presentationId }: { presentationId: string }) =>
        useAoiSnapshot({
          sessionId: "session-1",
          presentationId,
          enabled: true,
          layoutKey: "reader",
        }),
      { initialProps: { presentationId: "presentation-1" } },
    );

    await flushSnapshotDebounce();
    expect(layoutMock).toHaveBeenCalledTimes(1);

    rerender({ presentationId: "presentation-2" });
    await flushSnapshotDebounce();
    expect(layoutMock).toHaveBeenCalledTimes(2);

    await act(async () => {
      second.resolve(snapshot("presentation-2", 0));
      await second.promise;
    });
    expect(result.current.snapshotId).toBe("snapshot-presentation-2-0");
    expect(result.current.ready).toBe(true);

    // Response cũ về sau không được overwrite snapshot mới.
    await act(async () => {
      first.resolve(snapshot("presentation-1", 0));
      await first.promise;
    });
    expect(result.current).toMatchObject({
      snapshotId: "snapshot-presentation-2-0",
      presentationId: "presentation-2",
      ready: true,
    });
  });

  it("resets ready state when tracking is disabled", async () => {
    const { result, rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) =>
        useAoiSnapshot({
          sessionId: "session-1",
          presentationId: "presentation-1",
          enabled,
          layoutKey: "reader",
        }),
      { initialProps: { enabled: true } },
    );

    await flushSnapshotDebounce();
    expect(result.current.ready).toBe(true);

    rerender({ enabled: false });

    expect(result.current).toEqual({
      snapshotId: null,
      presentationId: null,
      layoutGeneration: 0,
      ready: false,
    });
  });

  it("does not expose the old snapshot when tracking is re-enabled", async () => {
    const { result, rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) =>
        useAoiSnapshot({
          sessionId: "session-1",
          presentationId: "presentation-1",
          enabled,
          layoutKey: "reader",
        }),
      { initialProps: { enabled: true } },
    );

    await flushSnapshotDebounce();
    expect(result.current.ready).toBe(true);

    rerender({ enabled: false });
    rerender({ enabled: true });

    expect(result.current).toEqual({
      snapshotId: null,
      presentationId: "presentation-1",
      layoutGeneration: 0,
      ready: false,
    });

    await flushSnapshotDebounce();

    expect(layoutMock).toHaveBeenCalledTimes(2);
    expect(result.current.snapshotId).toBe("snapshot-presentation-1-0");
  });
});
