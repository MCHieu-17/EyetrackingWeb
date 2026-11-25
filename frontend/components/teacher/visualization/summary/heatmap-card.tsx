"use client";

import { useEffect, useMemo, useState } from "react";
import { LazyPdfPage } from "@/components/pdf/lazy-pdf-page";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { useLessonSlidesAdmin } from "@/hooks/use-teacher";
import { useAoiHeatmap } from "@/hooks/use-visualization";
import { resolveMediaUrl } from "@/lib/api/client";
import type { AoiSummaryQuery } from "@/lib/types/visualization";
import { buildHeatmapQuery } from "./summary-helpers";

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
    () => buildHeatmapQuery(baseQuery, resolvedSlideId),
    [baseQuery, resolvedSlideId],
  );
  const heatmap = useAoiHeatmap(
    courseId,
    query,
    Boolean(resolvedLessonId && resolvedSlideId),
  );

  const [pageAspect, setPageAspect] = useState<number | null>(null);
  const slide = heatmap.data?.slide;
  const pageNumber = slide?.pageNumber ?? 1;
  const pdfUrl = resolveMediaUrl(
    slide?.pdfUrl ?? slides.find((item) => item.id === resolvedSlideId)?.pdfUrl,
  );

  useEffect(() => {
    // Đổi PDF/trang thì chờ onPageSize của trang mới thay vì giữ tỉ lệ cũ.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPageAspect(null);
  }, [pdfUrl, pageNumber]);

  if (lessons.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
        Khóa học chưa có bài giảng để xem heatmap.
      </div>
    );
  }

  const max = heatmap.data?.max ?? 0;
  const grid = heatmap.data?.grid ?? [];
  const staleViewCount = heatmap.data?.staleViewCount ?? 0;
  const analyzedViewCount = heatmap.data?.analyzedViewCount ?? 0;
  // Chỉ báo "cần phân tích lại" khi chưa có view nào phân tích xong; nếu đã có
  // view hiện hành mà max=0 thì nhiều khả năng slide không có mẫu trên slide.
  const needsReanalysis = staleViewCount > 0 && analyzedViewCount === 0;

  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_150px]">
        <label className="block">
          <span className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
            Bài giảng
          </span>
          <select
            value={resolvedLessonId}
            onChange={(event) =>
              setSelection({ lessonId: event.target.value, slideId: "" })
            }
            className="h-9 w-full rounded-xl border border-border bg-muted/40 px-2.5 text-xs text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          >
            {lessons.map((lesson) => (
              <option key={lesson.id} value={lesson.id}>
                {lesson.title}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
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
            className="h-9 w-full rounded-xl border border-border bg-muted/40 px-2.5 text-xs text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
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
          <span className="mb-1 block text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
            Độ đậm
          </span>
          <input
            type="range"
            min={0.2}
            max={1}
            step={0.05}
            value={opacity}
            onChange={(event) => setOpacity(Number(event.target.value))}
            className="h-9 w-full accent-[var(--primary)]"
            aria-label="Độ đậm heatmap"
          />
        </label>
      </div>

      {slidesQuery.isLoading || heatmap.isLoading ? (
        <Skeleton className="aspect-video w-full rounded-2xl" />
      ) : (
        <div
          className="relative w-full overflow-hidden rounded-2xl border border-border bg-muted"
          style={{ aspectRatio: pageAspect ?? 16 / 9 }}
        >
          {pdfUrl ? (
            <LazyPdfPage
              key={`${pdfUrl}:${slide?.pageNumber ?? 1}`}
              url={pdfUrl}
              pageNumber={slide?.pageNumber ?? 1}
              alt={slide?.title ?? "Slide heatmap"}
              className="absolute inset-0"
              onPageSize={({ width, height }) =>
                setPageAspect(height > 0 ? width / height : null)
              }
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">
              <div className="text-center">
                <Icon name="ri-image-line" className="mx-auto mb-2 size-5" />
                Chưa có PDF cho slide này
              </div>
            </div>
          )}

          {/* PdfPage vẽ canvas ở z-10; overlay phải nằm trên (z-20) để không bị PDF che. */}
          {max > 0 && (
            <div
              className="pointer-events-none absolute inset-0 z-20 grid"
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
                            ? `rgb(var(--heatmap) / ${Math.max(0.08, alpha)})`
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
            <div className="absolute inset-0 z-20 flex items-center justify-center bg-background/55">
              <div className="rounded-2xl border border-dashed border-border bg-card/90 px-5 py-4 text-center">
                <Icon
                  name={needsReanalysis ? "ri-refresh-line" : "ri-fire-line"}
                  className="mx-auto mb-2 size-5 text-warning"
                />
                {needsReanalysis ? (
                  <>
                    <p className="text-sm font-semibold text-foreground/75">
                      Dữ liệu gaze cần phân tích lại
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {staleViewCount} lượt xem chưa được phân tích lại. Bấm
                      “Phân tích lại” để cập nhật heatmap.
                    </p>
                  </>
                ) : (
                  <>
                    <p className="text-sm font-semibold text-foreground/75">
                      Chưa có điểm nhìn trên slide này
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Chọn slide khác hoặc mở rộng phạm vi thống kê.
                    </p>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {max > 0 && staleViewCount > 0 && (
        <p className="text-xs text-warning">
          {staleViewCount} lượt xem chưa được phân tích lại; heatmap có thể
          thiếu. Dùng nút “Phân tích lại” để cập nhật.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-2">
          Ít
          <span className="h-2 w-24 rounded-full bg-gradient-to-r from-heatmap-low to-heatmap-high" />
          Nhiều
        </span>
        <span>{heatmap.data?.onSlideSampleCount ?? 0} mẫu trong slide</span>
        {analyzedViewCount > 0 && (
          <span>{analyzedViewCount} lượt xem đã phân tích</span>
        )}
        {slide && <span className="ml-auto">{slide.lessonTitle}</span>}
      </div>
      {heatmap.isError && (
        <p className="text-xs text-destructive">Không tải được heatmap.</p>
      )}
    </div>
  );
}
