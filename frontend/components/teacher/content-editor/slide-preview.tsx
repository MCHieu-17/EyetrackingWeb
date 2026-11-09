"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { LazyPdfPage } from "@/components/pdf/lazy-pdf-page";
import { resolveMediaUrl } from "@/lib/api/client";
import type { SlideAdmin } from "@/lib/types/domain";

/**
 * Lưới xem trước slide. `slides` do trình soạn bài giảng truyền xuống.
 */
export function SlidePreview({ slides }: { slides: SlideAdmin[] }) {
  const [preview, setPreview] = useState<number | null>(null);

  useEffect(() => {
    if (preview === null) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPreview(null);
      if (event.key === "ArrowLeft")
        setPreview((v) => (v === null ? v : (v - 1 + slides.length) % slides.length));
      if (event.key === "ArrowRight")
        setPreview((v) => (v === null ? v : (v + 1) % slides.length));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [preview, slides.length]);

  if (slides.length === 0) return null;
  const previewSlide = preview === null ? null : slides[preview];

  return (
    <>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-5">
        {slides.map((slide, index) => {
          const url = resolveMediaUrl(slide.pdfUrl);
          if (!url) {
            return (
              <div
                key={slide.id}
                className="flex aspect-[4/3] items-center justify-center rounded-[18px] border border-[#eeeee9] bg-[#fdfdfa] text-xs font-medium tabular-nums text-black/40"
              >
                {slide.orderIndex + 1}
              </div>
            );
          }
          return (
            <button
              key={slide.id}
              type="button"
              onClick={() => setPreview(index)}
              aria-label={`Xem trước trang ${slide.orderIndex + 1}`}
              className="group relative overflow-hidden rounded-[18px] border border-[#eeeee9] bg-white p-1 outline-none transition hover:border-black/15 hover:shadow-sm focus-visible:ring-2 focus-visible:ring-black/20"
            >
              <LazyPdfPage
                url={url}
                pageNumber={slide.pageNumber}
                lazy
                alt={`Trang ${slide.orderIndex + 1}`}
                className="aspect-[4/3] w-full overflow-hidden rounded-[14px] bg-white"
                canvasClassName="transition group-hover:scale-[1.02]"
              />
              {slide.embeddingStatus === "none" && (
                <span
                  className="absolute right-1.5 top-1.5 rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground shadow-sm"
                  title="Trang chưa được index cho trợ lý học tập"
                >
                  Chưa index
                </span>
              )}
              {slide.embeddingStatus === "pending" && (
                <span
                  className="absolute right-1.5 top-1.5 rounded-full bg-info px-1.5 py-0.5 text-[10px] font-semibold text-white shadow-sm"
                  title="Đang index cho trợ lý học tập"
                >
                  Đang index
                </span>
              )}
              {slide.embeddingStatus === "failed" && (
                <span
                  className="absolute right-1.5 top-1.5 rounded-full bg-destructive px-1.5 py-0.5 text-[10px] font-semibold text-white shadow-sm"
                  title={slide.embeddingError || "Trang chưa được index cho trợ lý học tập"}
                >
                  Lỗi index
                </span>
              )}
            </button>
          );
        })}
      </div>

      {previewSlide && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" role="presentation">
          <button
            type="button"
            aria-label="Đóng xem trước"
            className="absolute inset-0 cursor-default bg-black/75"
            onClick={() => setPreview(null)}
          />
          <div className="relative flex max-h-full w-full max-w-4xl flex-col rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-2xl">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold tabular-nums text-foreground">
                Trang {previewSlide.orderIndex + 1} / {slides.length}
              </p>
              <Button variant="ghost" size="icon-sm" onClick={() => setPreview(null)} aria-label="Đóng">
                <Icon name="ri-close-line" className="size-5" />
              </Button>
            </div>
            {(() => {
              const url = resolveMediaUrl(previewSlide.pdfUrl);
              return url ? (
                <LazyPdfPage
                  key={previewSlide.id}
                  url={url}
                  pageNumber={previewSlide.pageNumber}
                  alt={`Trang ${previewSlide.orderIndex + 1}`}
                  className="mt-3 h-[70dvh] w-full overflow-hidden rounded-lg bg-white"
                />
              ) : (
                <p className="mt-3 rounded-[18px] border border-[#eeeee9] bg-[#fdfdfa] px-3 py-8 text-center text-sm text-muted-foreground">
                  Không tải được trang {previewSlide.orderIndex + 1}.
                </p>
              );
            })()}
            <div className="mt-3 flex items-center justify-between gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setPreview((v) => (v === null ? v : (v - 1 + slides.length) % slides.length))
                }
                disabled={slides.length <= 1}
              >
                <Icon name="ri-arrow-left-line" className="size-4" />
                Trang trước
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setPreview((v) => (v === null ? v : (v + 1) % slides.length))
                }
                disabled={slides.length <= 1}
              >
                Trang sau
                <Icon name="ri-arrow-right-line" className="size-4" />
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
