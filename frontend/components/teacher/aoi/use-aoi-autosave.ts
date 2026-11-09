"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type AoiSaveStatus = "idle" | "saving" | "saved" | "error";

/**
 * Tự lưu có debounce + hàng đợi. Khi một lần lưu đang chạy mà dữ liệu đổi,
 * lần lưu kế tiếp dùng giá trị mới nhất; không bắn song song.
 */
export function useAoiAutosave<T>({
  value,
  ready,
  enabled = true,
  delay = 800,
  save,
}: {
  value: T;
  ready: boolean;
  enabled?: boolean;
  delay?: number;
  save: (value: T) => Promise<void>;
}) {
  const [status, setStatus] = useState<AoiSaveStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const lastSavedRef = useRef("");
  const pendingRef = useRef<T | null>(null);
  const inFlightRef = useRef(false);
  const timerRef = useRef(0);
  const mountedRef = useRef(false);
  const saveRef = useRef(save);
  const valueRef = useRef(value);
  const enabledRef = useRef(enabled);
  const runRef = useRef<() => Promise<void>>(async () => {});

  useEffect(() => {
    saveRef.current = save;
  }, [save]);
  useEffect(() => {
    valueRef.current = value;
  }, [value]);
  useEffect(() => {
    enabledRef.current = enabled;
  }, [enabled]);

  useEffect(() => {
    runRef.current = async () => {
      if (!enabledRef.current) return;
      if (inFlightRef.current) {
        pendingRef.current = valueRef.current;
        return;
      }
      const next = pendingRef.current ?? valueRef.current;
      pendingRef.current = null;
      const key = JSON.stringify(next);
      if (key === lastSavedRef.current) {
        setStatus("saved");
        return;
      }
      inFlightRef.current = true;
      setStatus("saving");
      setError(null);
      try {
        await saveRef.current(next);
        lastSavedRef.current = key;
        setStatus("saved");
      } catch (err) {
        setStatus("error");
        setError(err instanceof Error ? err.message : "Không lưu được.");
      } finally {
        inFlightRef.current = false;
        if (pendingRef.current !== null) {
          pendingRef.current = null;
          void runRef.current();
        }
      }
    };
  });

  const serialized = JSON.stringify(value);

  const run = useCallback(() => runRef.current(), []);

  const schedule = useCallback(() => {
    if (!enabledRef.current) return;
    window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => void run(), delay);
  }, [delay, run]);

  useEffect(() => {
    if (!ready) return;
    if (!mountedRef.current) {
      mountedRef.current = true;
      lastSavedRef.current = serialized;
      return;
    }
    if (!enabled) return;
    schedule();
  }, [serialized, ready, enabled, schedule]);

  const flush = useCallback(async () => {
    window.clearTimeout(timerRef.current);
    await run();
  }, [run]);

  const retry = useCallback(() => {
    setStatus("saving");
    void run();
  }, [run]);

  return { status, error, flush, retry };
}
