import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook } from "@testing-library/react";
import {
  hasUnsavedAoiChanges,
  useAoiAutosave,
} from "./use-aoi-autosave";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe("useAoiAutosave", () => {
  it("treats newly loaded data as the baseline instead of an edit", async () => {
    const save = vi.fn().mockResolvedValue(undefined);
    const { result, rerender } = renderHook(
      ({ value, baselineKey }: { value: string[]; baselineKey: string }) =>
        useAoiAutosave({
          value,
          ready: true,
          baselineKey,
          save,
          delay: 800,
        }),
      { initialProps: { value: ["a"], baselineKey: "set-a" } },
    );

    expect(result.current.dirty).toBe(false);

    rerender({ value: ["b"], baselineKey: "set-b" });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });

    expect(result.current.dirty).toBe(false);
    expect(save).not.toHaveBeenCalled();

    rerender({ value: ["c"], baselineKey: "set-b" });
    expect(result.current.dirty).toBe(true);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(800);
    });

    expect(save).toHaveBeenCalledWith(["c"]);
    expect(result.current.dirty).toBe(false);
  });

  it("saves queued edits with the context captured when they were queued", async () => {
    const saveA = vi.fn();
    const saveB = vi.fn().mockResolvedValue(undefined);
    let resolveFirst!: () => void;
    saveA.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          resolveFirst = resolve;
        }),
    );
    saveA.mockResolvedValue(undefined);

    const { result, rerender } = renderHook(
      ({
        value,
        baselineKey,
        save,
      }: {
        value: string[];
        baselineKey: string;
        save: (value: string[]) => Promise<void>;
      }) =>
        useAoiAutosave({
          value,
          ready: true,
          baselineKey,
          save,
          delay: 800,
        }),
      {
        initialProps: {
          value: ["base"],
          baselineKey: "set-a",
          save: saveA,
        },
      },
    );

    rerender({ value: ["a1"], baselineKey: "set-a", save: saveA });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(800);
    });
    expect(saveA).toHaveBeenCalledWith(["a1"]);

    rerender({ value: ["a2"], baselineKey: "set-a", save: saveA });
    let flushed!: Promise<void>;
    await act(async () => {
      flushed = result.current.flush();
    });

    // Chuyển sang bộ dữ liệu mới khi request của bộ cũ còn đang chạy.
    rerender({ value: ["b-base"], baselineKey: "set-b", save: saveB });
    resolveFirst();
    await act(async () => {
      await flushed;
    });

    expect(saveA.mock.calls.map(([value]) => value)).toEqual([["a1"], ["a2"]]);
    expect(saveB).not.toHaveBeenCalled();
    expect(result.current.dirty).toBe(false);
  });

  it("giữ lỗi thật và cho phép thử lại sau khi lưu thất bại", async () => {
    const save = vi
      .fn<(value: string[]) => Promise<void>>()
      .mockRejectedValueOnce(new Error("Origin không hợp lệ"))
      .mockResolvedValueOnce(undefined);
    const { result, rerender } = renderHook(
      ({ value }: { value: string[] }) =>
        useAoiAutosave({
          value,
          ready: true,
          baselineKey: "set-a",
          save,
          delay: 800,
        }),
      { initialProps: { value: ["saved"] } },
    );

    rerender({ value: ["pending"] });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(800);
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toBe("Origin không hợp lệ");

    await act(async () => {
      result.current.retry();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(save).toHaveBeenCalledTimes(2);
    expect(save).toHaveBeenLastCalledWith(["pending"]);
    expect(result.current.status).toBe("saved");
    expect(result.current.error).toBeNull();
    expect(result.current.dirty).toBe(false);
  });
});

describe("hasUnsavedAoiChanges", () => {
  it("warns for dirty, pending, or saving state", () => {
    expect(
      hasUnsavedAoiChanges({ status: "idle", dirty: true, pending: false }),
    ).toBe(true);
    expect(
      hasUnsavedAoiChanges({ status: "idle", dirty: false, pending: true }),
    ).toBe(true);
    expect(
      hasUnsavedAoiChanges({ status: "saving", dirty: false, pending: false }),
    ).toBe(true);
    expect(
      hasUnsavedAoiChanges({ status: "saved", dirty: false, pending: false }),
    ).toBe(false);
  });
});
