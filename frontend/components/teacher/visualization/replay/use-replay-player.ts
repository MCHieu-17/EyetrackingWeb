"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ReplayView } from "@/lib/types/visualization";
import { playbackDurationMs } from "./replay-geometry";

const SPEEDS = [0.5, 1, 2, 4] as const;
export type PlaybackSpeed = (typeof SPEEDS)[number];

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function useReplayPlayer(views: ReplayView[]) {
  const [rawIndex, setIndex] = useState(0);
  const index = clamp(rawIndex, 0, Math.max(0, views.length - 1));
  const [timeMs, setTimeMsState] = useState(0);
  const timeRef = useRef(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeedState] = useState<PlaybackSpeed>(1);
  const [autoAdvance, setAutoAdvance] = useState(true);
  const speedRef = useRef<PlaybackSpeed>(1);

  const currentView = views[index] ?? null;
  const duration = currentView ? playbackDurationMs(currentView) : 0;
  const progress = duration > 0 ? Math.min(1, timeMs / duration) : 0;

  useEffect(() => {
    speedRef.current = speed;
  }, [speed]);

  useEffect(() => {
    if (!playing || duration <= 0) return;
    let frame = 0;
    let last = performance.now();

    const tick = (now: number) => {
      const delta = now - last;
      last = now;
      const next = Math.min(
        duration,
        timeRef.current + delta * speedRef.current,
      );
      timeRef.current = next;
      setTimeMsState(next);

      if (next >= duration) {
        if (autoAdvance && index < views.length - 1) {
          timeRef.current = 0;
          setIndex(index + 1);
          setTimeMsState(0);
        } else {
          setPlaying(false);
        }
        return;
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [
    autoAdvance,
    currentView?.contentViewId,
    duration,
    index,
    playing,
    views.length,
  ]);

  const seek = useCallback(
    (next: number) => {
      const value = clamp(next, 0, duration);
      timeRef.current = value;
      setTimeMsState(value);
    },
    [duration],
  );

  const selectView = useCallback(
    (next: number) => {
      if (next < 0 || next >= views.length) return;
      timeRef.current = 0;
      setTimeMsState(0);
      setIndex(next);
    },
    [views.length],
  );

  const togglePlay = useCallback(() => {
    if (duration <= 0) return;
    if (playing) {
      setPlaying(false);
      return;
    }
    if (timeRef.current >= duration) {
      timeRef.current = 0;
      setTimeMsState(0);
    }
    setPlaying(true);
  }, [duration, playing]);

  const nextView = useCallback(() => {
    selectView(index + 1);
  }, [index, selectView]);

  const previousView = useCallback(() => {
    selectView(index - 1);
  }, [index, selectView]);

  const setSpeed = useCallback((value: PlaybackSpeed) => {
    setSpeedState(value);
  }, []);

  return {
    index,
    currentView,
    timeMs,
    duration,
    progress,
    playing,
    speed,
    autoAdvance,
    speeds: SPEEDS,
    setAutoAdvance,
    setSpeed,
    seek,
    selectView,
    togglePlay,
    nextView,
    previousView,
  };
}
