"use client";

import { LazyPdfPage } from "@/components/pdf/lazy-pdf-page";
import { Icon } from "@/components/ui/icon";
import { resolveMediaUrl } from "@/lib/api/client";
import { colorFor } from "@/lib/aoi/colors";
import { cn } from "@/lib/utils";
import type { ReplaySample, ReplayView } from "@/lib/types/visualization";
import {
  isNoLabel,
  layoutForSample,
  NO_LABEL_SLIDE,
  rectToStage,
  sampleInStage,
  sampleStagePoint,
  slideRectToStage,
  stageAspect,
  stageRectStyle,
  type StageRect,
} from "./replay-geometry";

function AoiBox({
  rect,
  code,
  name,
  active,
  showLabel,
  variant,
}: {
  rect: StageRect;
  code: string;
  name: string;
  active: boolean;
  showLabel: boolean;
  variant: "slide" | "ui";
}) {
  const color = colorFor(code);
  return (
    <div
      data-aoi-box={code}
      data-active={active ? "true" : "false"}
      className="pointer-events-none absolute rounded-[5px] border-2 transition-[background-color,border-color,box-shadow] duration-150"
      style={{
        ...stageRectStyle(rect),
        borderColor: active ? color : `${color}99`,
        backgroundColor: active ? `${color}38` : `${color}12`,
        boxShadow: active
          ? `0 0 0 2px rgba(255,255,255,.9), 0 0 18px 2px ${color}80`
          : undefined,
        zIndex: active ? 20 : variant === "ui" ? 10 : 12,
      }}
    >
      {(showLabel || active) && (
        <span
          className="absolute left-0 top-0 max-w-full truncate rounded-br-[4px] px-1.5 py-0.5 text-[10px] font-semibold leading-4 text-white"
          style={{ backgroundColor: color }}
        >
          {name}
        </span>
      )}
    </div>
  );
}

export function ReplayStage({
  view,
  samples,
  currentSample,
  showAllAois,
  showLabels,
  showTrail,
  pinnedLabel,
}: {
  view: ReplayView;
  samples: ReplaySample[];
  currentSample: ReplaySample | null;
  showAllAois: boolean;
  showLabels: boolean;
  showTrail: boolean;
  pinnedLabel: string | null;
}) {
  const layout = layoutForSample(view, currentSample);
  const aspect = stageAspect(view);
  const pdfUrl = resolveMediaUrl(view.pdfUrl);
  const layoutSlideRect = slideRectToStage(layout);
  // Thiếu layout nhưng vẫn có PDF: dựng PDF toàn khung để không mất nội dung.
  const slideRect: StageRect | null =
    layoutSlideRect ??
    (!layout && pdfUrl
      ? { left: 0, top: 0, width: 1, height: 1 }
      : null);
  const activeLabel = pinnedLabel ?? currentSample?.aoiLabel ?? null;
  const point = sampleStagePoint(currentSample);
  const showPoint = sampleInStage(point);
  const activeIsNoLabel = isNoLabel(activeLabel);

  const sampleIndex = currentSample
    ? samples.findIndex((sample) => sample.id === currentSample.id)
    : -1;
  const trail =
    !showTrail || sampleIndex < 0
      ? []
      : samples
          .slice(Math.max(0, sampleIndex - 24), sampleIndex)
          .map((sample) => ({
            sample,
            point: sampleStagePoint(sample),
          }))
          .filter((item) => sampleInStage(item.point));

  return (
    <div className="space-y-2">
      <div
        className="relative w-full overflow-hidden rounded-[20px] border border-[#e6e8e1] bg-[#eef0ea] shadow-inner"
        style={{ aspectRatio: `${aspect}` }}
        aria-label={`Màn hình ghi nhận của ${view.lessonTitle}, ${
          view.slideTitle || "bài tập"
        }`}
      >
        {slideRect ? (
          <div
            className="absolute overflow-hidden rounded-[6px] border border-black/10 bg-white shadow-sm"
            style={stageRectStyle(slideRect)}
          >
            {pdfUrl ? (
              <LazyPdfPage
                key={`${pdfUrl}:${view.pageNumber ?? 1}`}
                url={pdfUrl}
                pageNumber={view.pageNumber ?? 1}
                alt={view.slideTitle ?? "Trang bài học"}
                className="absolute inset-0"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center p-4 text-center text-xs text-black/40">
                <div>
                  <Icon name="ri-image-line" className="mx-auto mb-2 size-5" />
                  {view.surface === "quiz"
                    ? "Bài tập — không có slide PDF"
                    : "Chưa có PDF cho slide này"}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="absolute inset-0 flex items-center justify-center p-6 text-center">
            <div className="max-w-sm rounded-[16px] border border-dashed border-[#d7dbd1] bg-white/70 px-5 py-4">
              <Icon
                name="ri-error-warning-line"
                className="mx-auto mb-2 size-5 text-[#a26a2b]"
              />
              <p className="text-sm font-semibold text-black/70">
                Thiếu layout của lượt xem
              </p>
              <p className="mt-1 text-xs text-black/45">
                Không thể dựng lại vị trí slide và vùng giao diện. Dữ liệu gaze
                thô vẫn được giữ nguyên.
              </p>
            </div>
          </div>
        )}

        {layout &&
          view.slideAois
            .filter((aoi) => !aoi.isContainer)
            .map((aoi) =>
              aoi.rects.map((rect, index) => {
                const active = aoi.analysisLabel === activeLabel;
                if (!showAllAois && !active) return null;
                const stageRect = slideRect
                  ? {
                      left:
                        slideRect.left +
                        rect.xMin * slideRect.width,
                      top:
                        slideRect.top +
                        rect.yMin * slideRect.height,
                      width:
                        (rect.xMax - rect.xMin) * slideRect.width,
                      height:
                        (rect.yMax - rect.yMin) * slideRect.height,
                    }
                  : null;
                if (!stageRect) return null;
                return (
                  <AoiBox
                    key={`slide-${aoi.code}-${index}`}
                    rect={stageRect}
                    code={aoi.code}
                    name={aoi.name}
                    active={active}
                    showLabel={showLabels}
                    variant="slide"
                  />
                );
              }),
            )}

        {layout &&
          layout.uiRegions.map((region) =>
            region.rects.map((rect, index) => {
              const active = region.name === activeLabel;
              if (!showAllAois && !active) return null;
              const stageRect = rectToStage(rect);
              if (!stageRect) return null;
              return (
                <AoiBox
                  key={`ui-${region.code}-${index}`}
                  rect={stageRect}
                  code={region.code}
                  name={region.name}
                  active={active}
                  showLabel={showLabels}
                  variant="ui"
                />
              );
            }),
          )}

        {trail.map(({ sample, point: trailPoint }) =>
          trailPoint ? (
            <span
              key={sample.id}
              className="pointer-events-none absolute z-10 size-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-black/25"
              style={{
                left: `${trailPoint.x * 100}%`,
                top: `${trailPoint.y * 100}%`,
              }}
            />
          ) : null,
        )}

        {showPoint && point ? (
          <span
            data-gaze-dot="true"
            className={cn(
              "pointer-events-none absolute z-30 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-[#1f2937] shadow-[0_0_0_3px_rgba(31,41,55,0.18)]",
              currentSample?.status !== "ok" && "bg-[#b42318]",
            )}
            style={{
              left: `${point.x * 100}%`,
              top: `${point.y * 100}%`,
            }}
            aria-hidden
          />
        ) : null}

        {activeIsNoLabel && (
          <div className="absolute left-3 top-3 z-40 max-w-[calc(100%-24px)] rounded-full bg-[#7a2e1f]/90 px-3 py-1.5 text-[11px] font-semibold text-white shadow-sm">
            {activeLabel === NO_LABEL_SLIDE
              ? "Điểm nhìn trong slide nhưng ngoài mọi vùng AOI"
              : "Điểm nhìn ngoài mọi vùng giao diện"}
          </div>
        )}

        {!layout && pdfUrl && (
          <div className="absolute bottom-3 left-3 z-40 max-w-[calc(100%-24px)] rounded-[12px] border border-[#e3c6ba] bg-[#fdf6f2]/95 px-3 py-2 text-[11px] text-[#7a3b2b] shadow-sm">
            <p className="font-semibold">Thiếu layout</p>
            <p className="mt-0.5 text-[#7a3b2b]/75">
              Đang hiển thị PDF toàn khung; không thể kiểm tra vị trí slide và
              vùng giao diện.
            </p>
          </div>
        )}

        {currentSample && currentSample.status !== "ok" && (
          <div className="absolute right-3 top-3 z-40 rounded-full bg-[#7a2e1f]/90 px-3 py-1.5 text-[11px] font-semibold text-white shadow-sm">
            {currentSample?.status === "no_face"
              ? "Mất dấu khuôn mặt"
              : currentSample?.status === "offscreen"
                ? "Ngoài màn hình"
                : "Lỗi ghi nhận"}
          </div>
        )}
        {currentSample?.status === "ok" && point && !showPoint && (
          <div className="absolute right-3 top-3 z-40 rounded-full bg-black/65 px-3 py-1.5 text-[11px] font-semibold text-white shadow-sm">
            Điểm nhìn ngoài khung hình đã ghi
          </div>
        )}
        {currentSample?.status === "ok" && !point && (
          <div className="absolute right-3 top-3 z-40 rounded-full bg-black/65 px-3 py-1.5 text-[11px] font-semibold text-white shadow-sm">
            Mẫu thiếu toạ độ
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-black/45">
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-[#36533a]" />
          Vùng slide
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-[#b45309]" />
          Vùng giao diện
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-[#7a2e1f]" />
          Chưa đánh dấu
        </span>
        {layout && (
          <span className="ml-auto">Hệ toạ độ viewport hiện tại</span>
        )}
        {!currentSample && samples.length > 0 && (
          <span className="ml-auto">Đang tải mẫu…</span>
        )}
        {samples.length === 0 && (
          <span className="ml-auto">Chưa có mẫu gaze cho lượt xem này</span>
        )}
      </div>
    </div>
  );
}
