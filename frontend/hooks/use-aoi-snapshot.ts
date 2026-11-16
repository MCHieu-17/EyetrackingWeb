"use client";

import { useEffect, useRef, useState } from "react";
import { createPresentationLayout } from "@/lib/api/aoi";
import { fittedImageTransform } from "@/lib/aoi/image-transform";
import { aoiSnapshotCacheKey } from "@/lib/aoi/snapshot-key";
import { aoiRectsKey, measureAoiRects } from "@/lib/aoi/measure";

export interface AoiSnapshotState {
  snapshotId: string | null;
  presentationId: string | null;
  layoutGeneration: number;
  /** false trong lúc đang đo/tạo snapshot mới → tạm dừng ghi gaze. */
  ready: boolean;
}

interface InternalAoiSnapshotState extends AoiSnapshotState {
  sessionId: string | null;
}

const EMPTY_STATE: InternalAoiSnapshotState = {
  snapshotId: null,
  presentationId: null,
  sessionId: null,
  layoutGeneration: 0,
  ready: false,
};

function paintedImageTransform(): Record<string, number> {
  const slide = document.querySelector<HTMLElement>('[data-aoi="slide"]');

  // Container biết kích thước gốc của trang PDF (do PdfPage báo lên) nên có
  // thể tính vùng ảnh ngay cả khi canvas chưa vẽ xong. Nhờ vậy layout snapshot
  // không phải chờ PDF paint mới sẵn sàng.
  const pageWidth = Number(slide?.dataset.pdfWidth);
  const pageHeight = Number(slide?.dataset.pdfHeight);
  if (slide && pageWidth > 0 && pageHeight > 0) {
    const fitted = fittedImageTransform(
      slide.getBoundingClientRect(),
      pageWidth,
      pageHeight,
      window.innerWidth,
      window.innerHeight,
    );
    if (fitted) return fitted;
  }

  // Fallback: PDF.js vẽ đúng vùng ảnh vào canvas; canvas đã được fit theo
  // container nên rect của canvas chính là vùng ảnh đã vẽ.
  const canvas =
    slide?.querySelector<HTMLCanvasElement>("canvas") ??
    document.querySelector<HTMLCanvasElement>('[data-aoi="slide"] canvas');
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
 * Đo layout DOM và tạo `view_layouts` cho presentation hiện tại.
 *
 * Presentation do reader tạo khi đổi slide/quiz. Hook này chỉ tạo layout
 * snapshot mới khi DOM/viewport/layoutKey đổi. Cache key luôn chứa
 * sessionId + presentationId để hai presentation cùng hình học vẫn có
 * snapshot riêng, và state cũ không bị lộ sang presentation mới.
 */
export function useAoiSnapshot({
  sessionId,
  presentationId,
  enabled,
  layoutKey,
  onBeforeSnapshot,
  requireImageTransform = false,
}: {
  sessionId: string | null;
  presentationId: string | null;
  enabled: boolean;
  layoutKey?: string | null;
  onBeforeSnapshot?: () => void;
  /** Lesson cần canvas PDF đã render trước khi đánh dấu layout ready. */
  requireImageTransform?: boolean;
}): AoiSnapshotState {
  const [state, setState] = useState<InternalAoiSnapshotState>(EMPTY_STATE);
  const [stateContext, setStateContext] = useState("");
  const contextRef = useRef("");
  const lastKeyRef = useRef("");
  const generationRef = useRef(0);
  const onBeforeRef = useRef(onBeforeSnapshot);

  const desiredContext =
    sessionId && presentationId && enabled
      ? `${sessionId}:${presentationId}`
      : "";

  // Reset state ngay trong render khi đổi presentation hoặc tắt tracking để
  // không có frame nào thấy snapshot cũ ở trạng thái ready.
  if (stateContext !== desiredContext) {
    setStateContext(desiredContext);
    setState(
      desiredContext
        ? {
            snapshotId: null,
            presentationId,
            sessionId,
            layoutGeneration: 0,
            ready: false,
          }
        : EMPTY_STATE,
    );
  }

  useEffect(() => {
    onBeforeRef.current = onBeforeSnapshot;
  });

  useEffect(() => {
    const contextKey =
      sessionId && presentationId ? `${sessionId}:${presentationId}` : "";

    if (!sessionId || !presentationId || !enabled) {
      contextRef.current = "";
      lastKeyRef.current = "";
      generationRef.current = 0;
      return;
    }

    if (contextRef.current !== contextKey) {
      contextRef.current = contextKey;
      lastKeyRef.current = "";
      generationRef.current = 0;
    }

    let disposed = false;
    let timer = 0;
    let inFlight = false;
    let pending = false;
    let runToken = 0;

    const measure = () => {
      const rects = measureAoiRects();
      const key = aoiSnapshotCacheKey({
        sessionId,
        presentationId,
        viewportWidth: window.innerWidth,
        viewportHeight: window.innerHeight,
        layoutKey,
        rectsKey: aoiRectsKey(rects),
      });
      return { rects, key };
    };

    const schedule = () => {
      if (typeof window === "undefined") return;
      window.clearTimeout(timer);
      timer = window.setTimeout(() => void run(), 250);
    };

    const run = async () => {
      if (disposed) return;
      if (inFlight) {
        pending = true;
        return;
      }

      const measured = measure();
      const { rects, key } = measured;
      const image = paintedImageTransform();
      const hasImage =
        Number(image.width) > 0 && Number(image.height) > 0;
      if (requireImageTransform && !hasImage) {
        // PDF canvas chưa render xong; thử lại thay vì lưu slide_rect rỗng
        // (worker sẽ không thể map gaze → slide).
        schedule();
        return;
      }

      if (key === lastKeyRef.current) {
        setState((prev) =>
          prev.sessionId === sessionId &&
          prev.presentationId === presentationId &&
          prev.ready
            ? prev
            : {
                ...prev,
                presentationId,
                sessionId,
                ready: true,
              },
        );
        return;
      }

      inFlight = true;
      const token = ++runToken;
      const generation = generationRef.current;
      setState((prev) => ({
        ...prev,
        presentationId,
        sessionId,
        snapshotId:
          prev.sessionId === sessionId &&
          prev.presentationId === presentationId
            ? prev.snapshotId
            : null,
        layoutGeneration: generation,
        ready: false,
      }));
      onBeforeRef.current?.();

      try {
        const snapshot = await createPresentationLayout(presentationId, {
          sequenceNo: generation,
          layoutGeneration: generation,
          imageTransform: image,
          rects,
        });
        if (disposed || token !== runToken) return;
        // Layout có thể đã đổi trong lúc chờ API: bỏ kết quả cũ và để
        // schedule kế tiếp tạo snapshot cho layout hiện tại.
        if (measure().key !== key) {
          pending = true;
          return;
        }
        lastKeyRef.current = key;
        generationRef.current = generation + 1;
        setState({
          snapshotId: snapshot.id,
          presentationId,
          sessionId,
          layoutGeneration: snapshot.layoutGeneration,
          ready: true,
        });
      } catch {
        if (disposed || token !== runToken) return;
        if (measure().key !== key) {
          pending = true;
          return;
        }
        // Vẫn cho ghi raw (snapshotId=null) để không mất dữ liệu.
        setState({
          snapshotId: null,
          presentationId,
          sessionId,
          layoutGeneration: generation,
          ready: true,
        });
      } finally {
        if (token === runToken) {
          inFlight = false;
          if (pending && !disposed) {
            pending = false;
            schedule();
          }
        }
      }
    };

    const observer = new MutationObserver(schedule);
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: [
        "class",
        "style",
        "data-aoi",
        "data-pdf-width",
        "data-pdf-height",
      ],
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
  }, [sessionId, presentationId, enabled, layoutKey, requireImageTransform]);

  if (!sessionId || !presentationId || !enabled) {
    return {
      snapshotId: null,
      presentationId: null,
      layoutGeneration: 0,
      ready: false,
    };
  }

  if (
    state.sessionId !== sessionId ||
    state.presentationId !== presentationId
  ) {
    return {
      snapshotId: null,
      presentationId,
      layoutGeneration: 0,
      ready: false,
    };
  }

  return {
    snapshotId: state.snapshotId,
    presentationId: state.presentationId,
    layoutGeneration: state.layoutGeneration,
    ready: state.ready,
  };
}
