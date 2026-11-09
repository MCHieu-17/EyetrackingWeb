"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { PDFPageProxy } from "pdfjs-dist";
import { loadPdfDocument } from "@/lib/pdf/pdfjs";
import { cn } from "@/lib/utils";

interface PdfPageSize {
  width: number;
  height: number;
}

export interface PdfPageProps {
  url: string;
  pageNumber: number;
  className?: string;
  canvasClassName?: string;
  alt?: string;
  /** Chỉ render khi phần tử vào viewport (dùng cho lưới nhiều slide). */
  lazy?: boolean;
  onPageSize?: (size: PdfPageSize) => void;
  onError?: () => void;
}

/**
 * Render một trang PDF ra canvas, tự fit theo kích thước container và giữ
 * đúng aspect ratio. Canvas chính là vùng ảnh đã vẽ (không có letterbox bên
 * trong canvas), nên AOI/gaze map theo rect của canvas là chính xác.
 */
export function PdfPage({
  url,
  pageNumber,
  className,
  canvasClassName,
  alt,
  lazy = false,
  onPageSize,
  onError,
}: PdfPageProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const generationRef = useRef(0);
  const renderTaskRef = useRef<ReturnType<PDFPageProxy["render"]> | null>(null);
  const [visible, setVisible] = useState(!lazy);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  const onPageSizeRef = useRef(onPageSize);
  const onErrorRef = useRef(onError);
  useEffect(() => {
    onPageSizeRef.current = onPageSize;
    onErrorRef.current = onError;
  });

  useEffect(() => {
    if (!lazy) return;
    const element = containerRef.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "200px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [lazy]);

  const render = useCallback(async () => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas || !visible) return;

    const width = container.clientWidth;
    const height = container.clientHeight;
    if (width <= 0 || height <= 0) return;

    const generation = ++generationRef.current;
    renderTaskRef.current?.cancel();
    renderTaskRef.current = null;

    let page: PDFPageProxy | null = null;
    let task: ReturnType<PDFPageProxy["render"]> | null = null;
    try {
      const document = await loadPdfDocument(url);
      if (generation !== generationRef.current) return;
      setReady(false);
      setFailed(false);
      page = await document.getPage(pageNumber);
      if (generation !== generationRef.current) return;

      const baseViewport = page.getViewport({ scale: 1 });
      onPageSizeRef.current?.({
        width: baseViewport.width,
        height: baseViewport.height,
      });

      const scale = Math.min(
        width / baseViewport.width,
        height / baseViewport.height,
      );
      const cssWidth = Math.max(1, Math.floor(baseViewport.width * scale));
      const cssHeight = Math.max(1, Math.floor(baseViewport.height * scale));
      const dpr = window.devicePixelRatio || 1;
      const viewport = page.getViewport({ scale: scale * dpr });

      canvas.width = Math.max(1, Math.floor(viewport.width));
      canvas.height = Math.max(1, Math.floor(viewport.height));
      canvas.style.width = `${cssWidth}px`;
      canvas.style.height = `${cssHeight}px`;

      task = page.render({ canvas, viewport });
      renderTaskRef.current = task;
      await task.promise;
      if (generation === generationRef.current) setReady(true);
    } catch (error) {
      if (generation !== generationRef.current) return;
      if ((error as { name?: string })?.name === "RenderingCancelledException") {
        return;
      }
      setFailed(true);
      onErrorRef.current?.();
    } finally {
      page?.cleanup();
      if (renderTaskRef.current === task) renderTaskRef.current = null;
    }
  }, [pageNumber, url, visible]);

  useEffect(() => {
    // PDF.js là external system; render cập nhật canvas + trạng thái loading.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void render();
    return () => {
      generationRef.current += 1;
      renderTaskRef.current?.cancel();
      renderTaskRef.current = null;
    };
  }, [render]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let timer = 0;
    const observer = new ResizeObserver(() => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        setReady(false);
        void render();
      }, 80);
    });
    observer.observe(container);
    return () => {
      window.clearTimeout(timer);
      observer.disconnect();
    };
  }, [render]);

  return (
    <div
      ref={containerRef}
      className={cn("relative flex items-center justify-center", className)}
    >
      {!ready && !failed && (
        <div className="absolute inset-0 animate-pulse bg-muted/30" />
      )}
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={alt}
        className={cn(
          "relative z-10 block bg-white",
          failed && "hidden",
          canvasClassName,
        )}
      />
      {failed && (
        <div className="relative z-10 flex h-full w-full items-center justify-center bg-white p-4 text-center text-xs text-muted-foreground">
          Không hiển thị được trang PDF.
        </div>
      )}
    </div>
  );
}
