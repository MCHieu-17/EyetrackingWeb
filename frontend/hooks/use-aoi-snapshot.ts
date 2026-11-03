"use client";

import { useEffect, useRef, useState } from "react";
import { createAoiLayoutSnapshot } from "@/lib/api/aoi";
import { aoiRectsKey, measureAoiRects } from "@/lib/aoi/measure";

export interface AoiSnapshotState {
  snapshotId: string | null;
  /** false trong lúc đang đo/tạo snapshot mới → tạm dừng ghi gaze. */
  ready: boolean;
}

/**
 * Đo layout DOM và tạo `aoi_layout_snapshots` khi layout thay đổi.
 *
 * Theo dõi:
 *   - resize (nhưng nếu viewport đổi, backend sẽ trả 409 viewport_mismatch)
 *   - scroll (rect thay đổi khi cuộn)
 *   - mutation DOM (mở/đóng chatbot, mục lục, tin nhắn mới, đổi slide)
 *
 * Trước khi tạo snapshot mới, gọi `onBeforeSnapshot` để flush batch gaze cũ,
 * tránh gán sample cũ sang layout mới.
 */
export function useAoiSnapshot({
  sessionId,
  enabled,
  layoutKey,
  onBeforeSnapshot,
}: {
  sessionId: string | null;
  enabled: boolean;
  layoutKey?: string | null;
  onBeforeSnapshot?: () => void;
}): AoiSnapshotState {
  const [state, setState] = useState<AoiSnapshotState>({
    snapshotId: null,
    ready: false,
  });
  const lastKeyRef = useRef("");
  const onBeforeRef = useRef(onBeforeSnapshot);

  useEffect(() => {
    onBeforeRef.current = onBeforeSnapshot;
  });

  useEffect(() => {
    if (!sessionId || !enabled) {
      lastKeyRef.current = "";
      return;
    }

    let disposed = false;
    let timer = 0;
    let inFlight = false;
    let pending = false;

    const run = async () => {
      if (disposed) return;
      if (inFlight) {
        // Layout đổi trong lúc đang tạo snapshot → chạy lại sau khi xong.
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
        const snapshot = await createAoiLayoutSnapshot(sessionId, {
          viewportWidthPx: window.innerWidth,
          viewportHeightPx: window.innerHeight,
          layoutKey: layoutKey ?? null,
          rects,
        });
        if (disposed) return;
        lastKeyRef.current = key;
        setState({ snapshotId: snapshot.id, ready: true });
      } catch {
        if (disposed) return;
        // Vẫn cho ghi raw (snapshotId=null) để không mất dữ liệu. AOI mapping
        // có thể rebuild sau nếu snapshot được tạo lại.
        setState({ snapshotId: null, ready: true });
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
  }, [sessionId, enabled, layoutKey]);

  // Khi tắt, trả trạng thái rỗng thay vì setState trong effect (tránh cascading
  // render). State nội bộ có thể còn snapshot cũ nhưng không được dùng.
  return sessionId && enabled ? state : { snapshotId: null, ready: false };
}
