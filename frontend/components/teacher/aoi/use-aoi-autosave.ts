"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type AoiSaveStatus = "idle" | "saving" | "saved" | "error";

interface SaveJob<T> {
  value: T;
  key: string;
  save: (value: T) => Promise<void>;
  epoch: number;
}

export interface AoiSaveSnapshot {
  status: AoiSaveStatus;
  dirty: boolean;
  pending: boolean;
}

/** Cảnh báo rời trang khi còn thay đổi chưa lưu, đang chờ hoặc đang lưu. */
export function hasUnsavedAoiChanges(
  ...saves: readonly AoiSaveSnapshot[]
): boolean {
  return saves.some(
    (save) => save.dirty || save.pending || save.status === "saving",
  );
}

/**
 * Tự lưu có debounce + hàng đợi. Khi một lần lưu đang chạy mà dữ liệu đổi,
 * lần lưu kế tiếp dùng giá trị mới nhất; không bắn song song.
 *
 * Mỗi job chụp lại cả hàm `save` tại thời điểm xếp hàng, nên khi người dùng
 * đổi slide/phiên bản, các thay đổi còn chờ vẫn được gửi đúng context cũ thay
 * vì ghi nhầm sang slide mới.
 */
export function useAoiAutosave<T>({
  value,
  ready,
  enabled = true,
  delay = 800,
  save,
  baselineKey,
}: {
  value: T;
  ready: boolean;
  enabled?: boolean;
  delay?: number;
  save: (value: T) => Promise<void>;
  /** Đổi khi server trả về một bộ dữ liệu mới đã được nạp sẵn. */
  baselineKey?: unknown;
}) {
  const [status, setStatus] = useState<AoiSaveStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [pending, setPending] = useState(false);

  const lastSavedRef = useRef("");
  const jobsRef = useRef<SaveJob<T>[]>([]);
  const activeJobRef = useRef<SaveJob<T> | null>(null);
  const drainPromiseRef = useRef<Promise<void> | null>(null);
  const timerRef = useRef(0);
  const mountedRef = useRef(false);
  const epochRef = useRef(0);
  const baselineKeyRef = useRef(baselineKey);
  const saveRef = useRef(save);
  const valueRef = useRef(value);
  const enabledRef = useRef(enabled);

  useEffect(() => {
    saveRef.current = save;
  }, [save]);
  useEffect(() => {
    valueRef.current = value;
  }, [value]);
  useEffect(() => {
    enabledRef.current = enabled;
  }, [enabled]);

  const processJob = useCallback(async (job: SaveJob<T>) => {
    if (job.key === lastSavedRef.current) {
      if (job.epoch === epochRef.current) {
        setDirty(JSON.stringify(valueRef.current) !== job.key);
        setPending(jobsRef.current.length > 0);
      }
      return;
    }

    activeJobRef.current = job;
    if (job.epoch === epochRef.current) {
      setStatus("saving");
      setError(null);
    }
    try {
      await job.save(job.value);
      if (job.epoch === epochRef.current) {
        lastSavedRef.current = job.key;
        const currentKey = JSON.stringify(valueRef.current);
        const hasQueued = jobsRef.current.length > 0;
        setDirty(currentKey !== job.key || hasQueued);
        setPending(hasQueued);
        setStatus("saved");
      }
    } catch (err) {
      if (job.epoch === epochRef.current) {
        setStatus("error");
        setError(err instanceof Error ? err.message : "Không lưu được.");
        setDirty(true);
        setPending(jobsRef.current.length > 0);
      }
    } finally {
      activeJobRef.current = null;
      if (jobsRef.current.length === 0) setPending(false);
    }
  }, []);

  const drain = useCallback(() => {
    if (drainPromiseRef.current) return drainPromiseRef.current;
    if (jobsRef.current.length === 0) return Promise.resolve();
    const promise = (async () => {
      try {
        while (jobsRef.current.length > 0) {
          const job = jobsRef.current.shift()!;
          await processJob(job);
        }
      } finally {
        drainPromiseRef.current = null;
      }
    })();
    drainPromiseRef.current = promise;
    return promise;
  }, [processJob]);

  const run = useCallback(() => {
    const job: SaveJob<T> = {
      value: valueRef.current,
      key: JSON.stringify(valueRef.current),
      save: saveRef.current,
      epoch: epochRef.current,
    };
    const active = activeJobRef.current;
    const alreadyActive =
      active !== null &&
      active.key === job.key &&
      active.save === job.save &&
      active.epoch === job.epoch;
    if (!alreadyActive) {
      const queued = jobsRef.current;
      const last = queued[queued.length - 1];
      const alreadyQueued =
        last !== undefined &&
        last.key === job.key &&
        last.save === job.save &&
        last.epoch === job.epoch;
      if (!alreadyQueued) {
        queued.push(job);
        setPending(true);
      }
    }
    return drain();
  }, [drain]);

  const schedule = useCallback(() => {
    if (!enabledRef.current) return;
    window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => void run(), delay);
  }, [delay, run]);

  const serialized = JSON.stringify(value);

  useEffect(() => {
    if (!ready) return;

    if (!mountedRef.current) {
      mountedRef.current = true;
      baselineKeyRef.current = baselineKey;
      lastSavedRef.current = serialized;
      setDirty(false);
      setPending(false);
      return;
    }

    if (baselineKeyRef.current !== baselineKey) {
      // Server vừa nạp một bộ khác: dữ liệu hiện tại là baseline đã lưu, không
      // phải chỉnh sửa cần autosave. Job cũ vẫn giữ epoch cũ và context cũ.
      baselineKeyRef.current = baselineKey;
      epochRef.current += 1;
      lastSavedRef.current = serialized;
      window.clearTimeout(timerRef.current);
      setDirty(false);
      setPending(jobsRef.current.length > 0);
      setStatus("saved");
      setError(null);
      return;
    }

    const nextDirty = serialized !== lastSavedRef.current;
    setDirty(nextDirty);
    if (!enabled || !nextDirty) {
      if (!nextDirty) {
        window.clearTimeout(timerRef.current);
        if (jobsRef.current.length === 0) setPending(false);
      }
      return;
    }
    setPending(true);
    schedule();
  }, [serialized, ready, enabled, baselineKey, schedule]);

  const flush = useCallback(async () => {
    window.clearTimeout(timerRef.current);
    await run();
  }, [run]);

  const retry = useCallback(() => {
    setStatus("saving");
    void run();
  }, [run]);

  return { status, error, dirty, pending, flush, retry };
}
