"use client";

import { useMemo, useState } from "react";
import { LazyPdfPage } from "@/components/pdf/lazy-pdf-page";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { useLessonSlidesAdmin } from "@/hooks/use-teacher";
import { useAoiHeatmap } from "@/hooks/use-visualization";
import { resolveMediaUrl } from "@/lib/api/client";
import type { AoiSummaryQuery } from "@/lib/types/visualization";

const GRID = 24;

export function HeatmapCard({
  courseId,
  baseQuery,
  lessons,
}: {
  courseId: string;
  baseQuery: AoiSummaryQuery;
  lessons: { id: string; title: string }[];
}) {
  const [selection, setSelection] = useState({
    lessonId: lessons[0]?.id ?? "",
    slideId: "",
  });
  const [opacity, setOpacity] = useState(0.7);

  const resolvedLessonId = lessons.some(
    (lesson) => lesson.id === selection.lessonId,
  )
    ? selection.lessonId
    : lessons[0]?.id ?? "";
  const slidesQuery = useLessonSlidesAdmin(resolvedLessonId);
  const slides = slidesQuery.data ?? [];
  const resolvedSlideId = slides.some((slide) => slide.id === selection.slideId)
    ? selection.slideId
    : slides[0]?.id ?? "";

  const query = useMemo(
    () => ({ ...baseQuery, slideId: resolvedSlideId }),
    [baseQuery, resolvedSlideId],
  );
  const heatmap = useAoiHeatmap(
    courseId,
    query,
    Boolean(resolvedLessonId && resolvedSlideId),
  );

  if (lessons.length === 0) {
    return (
      <div className="rounded-[18px] border border-dashed border-[#eeeee9] px-4 py-10 text-center text-sm text-black/40">
        Khóa học chưa có bài giảng để xem heatmap.
      </div>
    );
  }

  const slide = heatmap.data?.slide;
  const pdfUrl = resolveMediaUrl(
    slide?.pdfUrl ?? slides.find((item) => item.id === resolvedSlideId)?.pdfUrl,
  );
  const max = heatmap.data?.max ?? 0;
  const grid = heatmap.data?.grid ?? [];

  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_150px]">
        <label className="block">
          <span className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.08em] text-black/35">
            Bài giảng
          </span>
          <select
            value={resolvedLessonId}
            onChange={(event) =>
              setSelection({ lessonId: event.target.value, slideId: "" })
            }
            className="h-9 w-full rounded-xl border border-[#eeeee9] bg-[#fdfdfa] px-2.5 text-xs text-black outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          >
            {lessons.map((lesson) => (
              <option key={lesson.id} value={lesson.id}>
                {lesson.title}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.08em] text-black/35">
            Slide
          </span>
          <select
            value={resolvedSlideId}
            onChange={(event) =>
              setSelection((previous) => ({
                ...previous,
                slideId: event.target.value,
              }))
            }
            className="h-9 w-full rounded-xl border border-[#eeeee9] bg-[#fdfdfa] px-2.5 text-xs text-black outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
            disabled={slides.length === 0}
          >
            {slides.map((item) => (
              <option key={item.id} value={item.id}>
                Trang {item.pageNumber} · {item.title}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.08em] text-black/35">
            Độ đậm
          </span>
          <input
            type="range"
            min={0.2}
            max={1}
            step={0.05}
            value={opacity}
            onChange={(event) => setOpacity(Number(event.target.value))}
            className="h-9 w-full accent-[#36533a]"
            aria-label="Độ đậm heatmap"
          />
        </label>
      </div>

      {slidesQuery.isLoading || heatmap.isLoading ? (
        <Skeleton className="aspect-video w-full rounded-[16px]" />
      ) : (
        <div className="relative aspect-video w-full overflow-hidden rounded-[16px] border border-[#e6e8e1] bg-[#eef0ea]">
          {pdfUrl ? (
            <LazyPdfPage
              key={`${pdfUrl}:${slide?.pageNumber ?? 1}`}
              url={pdfUrl}
              pageNumber={slide?.pageNumber ?? 1}
              alt={slide?.title ?? "Slide heatmap"}
              className="absolute inset-0"
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center text-xs text-black/40">
              <div className="text-center">
                <Icon name="ri-image-line" className="mx-auto mb-2 size-5" />
                Chưa có PDF cho slide này
              </div>
            </div>
          )}

          {max > 0 && (
            <div
              className="pointer-events-none absolute inset-0 grid"
              style={{
                gridTemplateColumns: `repeat(${GRID}, minmax(0, 1fr))`,
                gridTemplateRows: `repeat(${GRID}, minmax(0, 1fr))`,
              }}
              aria-label="Lưới heatmap 24x24"
            >
              {Array.from({ length: GRID }).map((_, y) =>
                Array.from({ length: GRID }).map((__, x) => {
                  const value = grid[y]?.[x] ?? 0;
                  const alpha = value > 0 ? (value / max) * opacity : 0;
                  return (
                    <span
                      key={`${x}-${y}`}
                      style={{
                        backgroundColor:
                          alpha > 0
                            ? `rgba(180, 83, 9, ${Math.max(0.08, alpha)})`
                            : "transparent",
                      }}
                      title={value > 0 ? `${value} mẫu` : undefined}
                    />
                  );
                }),
              )}
            </div>
          )}

          {max === 0 && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/55">
              <div className="rounded-[16px] border border-dashed border-[#d7dbd1] bg-white/85 px-5 py-4 text-center">
                <Icon
                  name="ri-fire-line"
                  className="mx-auto mb-2 size-5 text-[#a26a2b]"
                />
                <p className="text-sm font-semibold text-black/65">
                  Chưa có điểm nhìn trên slide này
                </p>
                <p className="mt-1 text-xs text-black/40">
                  Chọn slide khác hoặc mở rộng phạm vi thống kê.
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 text-[11px] text-black/40">
        <span className="inline-flex items-center gap-2">
          Ít
          <span className="h-2 w-24 rounded-full bg-gradient-to-r from-[#f6e6d7] to-[#b45309]" />
          Nhiều
        </span>
        <span>{heatmap.data?.onSlideSampleCount ?? 0} mẫu trong slide</span>
        {slide && <span className="ml-auto">{slide.lessonTitle}</span>}
      </div>
      {heatmap.isError && (
        <p className="text-xs text-[#8a3b27]">Không tải được heatmap.</p>
      )}
    </div>
  );
}
