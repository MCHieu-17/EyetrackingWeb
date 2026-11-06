"use client";

import { useEffect, useRef, useState } from "react";
import { createPresentationLayout } from "@/lib/api/aoi";
import { aoiRectsKey, measureAoiRects } from "@/lib/aoi/measure";

export interface AoiSnapshotState {
  snapshotId: string | null;
  presentationId: string | null;
  layoutGeneration: number;
  /** false trong lúc đang đo/tạo snapshot mới → tạm dừng ghi gaze. */
  ready: boolean;
}

function paintedImageTransform(): Record<string, number> {
  // PDF.js vẽ đúng vùng ảnh vào canvas; canvas đã được fit theo container nên
  // rect của canvas chính là vùng ảnh đã vẽ (không có letterbox bên trong).
  const canvas = document.querySelector<HTMLCanvasElement>(
    '[data-aoi="slide"] canvas',
  );
  if (!canvas) return {};
  const rect = canvas.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return {};
  return {
    left: rect.left / window.innerWidth,
    top: rect.top / window.innerHeight,
    width: rect.width / window.innerWidth,
    height: rect.height / window.innerHeight,
  };
}

/**
 * Đo layout DOM và tạo `aoi_layout_snapshots` cho presentation hiện tại.
 *
 * Presentation do reader tạo khi đổi slide/quiz. Hook này chỉ tạo layout
 * snapshot mới khi DOM/viewport/layoutKey đổi.
 */
export function useAoiSnapshot({
  sessionId,
  presentationId,
  enabled,
  layoutKey,
  onBeforeSnapshot,
}: {
  sessionId: string | null;
  presentationId: string | null;
  enabled: boolean;
  layoutKey?: string | null;
  onBeforeSnapshot?: () => void;
}): AoiSnapshotState {
  const [state, setState] = useState<AoiSnapshotState>({
    snapshotId: null,
    presentationId: null,
    layoutGeneration: 0,
    ready: false,
  });
  const lastKeyRef = useRef("");
  const generationRef = useRef(0);
  const onBeforeRef = useRef(onBeforeSnapshot);

  useEffect(() => {
    onBeforeRef.current = onBeforeSnapshot;
  });

  useEffect(() => {
    if (!sessionId || !presentationId || !enabled) {
      lastKeyRef.current = "";
      generationRef.current = 0;
      return;
    }

    let disposed = false;
    let timer = 0;
    let inFlight = false;
    let pending = false;

    const run = async () => {
      if (disposed) return;
      if (inFlight) {
        pending = true;
        return;
      }
      const rects = measureAoiRects();
      const key = `${window.innerWidth}x${window.innerHeight}|${layoutKey ?? ""}|${aoiRectsKey(rects)}`;
      if (key === lastKeyRef.current) {
        setState((prev) => (prev.ready ? prev : { ...prev, ready: true }));
        return;
      }

      inFlight = true;
      setState((prev) => ({ ...prev, ready: false }));
      onBeforeRef.current?.();
      try {
        const generation = generationRef.current;
        const snapshot = await createPresentationLayout(presentationId, {
          sequenceNo: generation,
          layoutGeneration: generation,
          imageTransform: paintedImageTransform(),
          rects,
        });
        if (disposed) return;
        lastKeyRef.current = key;
        generationRef.current = generation + 1;
        setState({
          snapshotId: snapshot.id,
          presentationId,
          layoutGeneration: snapshot.layoutGeneration,
          ready: true,
        });
      } catch {
        if (disposed) return;
        // Vẫn cho ghi raw (snapshotId=null) để không mất dữ liệu.
        setState({
          snapshotId: null,
          presentationId,
          layoutGeneration: generationRef.current,
          ready: true,
        });
      } finally {
        inFlight = false;
        if (pending && !disposed) {
          pending = false;
          schedule();
        }
      }
    };

    const schedule = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => void run(), 250);
    };

    const observer = new MutationObserver(schedule);
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["class", "style", "data-aoi"],
    });
    window.addEventListener("resize", schedule);
    window.addEventListener("scroll", schedule, true);
    schedule();

    return () => {
      disposed = true;
      window.clearTimeout(timer);
      observer.disconnect();
      window.removeEventListener("resize", schedule);
      window.removeEventListener("scroll", schedule, true);
    };
  }, [sessionId, presentationId, enabled, layoutKey]);

  return sessionId && presentationId && enabled
    ? state
    : {
        snapshotId: null,
        presentationId: null,
        layoutGeneration: 0,
        ready: false,
      };
}
