"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { LazyPdfPage } from "@/components/pdf/lazy-pdf-page";
import { ReaderChatPreview } from "@/components/reader/reader-chat-preview";
import { ReaderFrame } from "@/components/reader/reader-frame";
import { ReaderQuizPreview } from "@/components/reader/reader-quiz-preview";
import { resolveMediaUrl } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { AoiOverlay } from "./aoi-overlay";
import type { AoiEditorController } from "./use-aoi-editor";

const DESIGN_WIDTH = 1280;
const DESIGN_HEIGHT = 800;

export function StudentPreview({
  courseTitle,
  controller,
  hoveredCode,
  onHover,
}: {
  courseTitle: string;
  controller: AoiEditorController;
  hoveredCode: string | null;
  onHover: (code: string | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const shellRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const [chatOpen, setChatOpen] = useState(false);

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const rect = container.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return;
        const next = Math.min(
          rect.width / DESIGN_WIDTH,
          rect.height / DESIGN_HEIGHT,
        );
        setScale(Math.max(0.2, Math.min(1, next)));
        setContainerSize({ width: rect.width, height: rect.height });
      });
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(container);
    window.addEventListener("resize", update);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("resize", update);
    };
  }, []);

  const activeSlide = controller.activeSlide;
  const slideUrl = resolveMediaUrl(activeSlide?.pdfUrl);
  const scaledWidth = DESIGN_WIDTH * scale;
  const scaledHeight = DESIGN_HEIGHT * scale;
  const left = Math.max(0, (containerSize.width - scaledWidth) / 2);
  const top = Math.max(0, (containerSize.height - scaledHeight) / 2);

  const hint =
    controller.mode === "interact"
      ? "Đang tương tác như học viên"
      : controller.tab === "slide"
        ? "Bấm để chọn vùng · Kéo trên slide để vẽ"
        : "Bấm để chọn phần · Kéo để vẽ vùng";

  return (
    <section className="flex min-h-0 min-w-0 flex-1 flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex rounded-full border border-[#eeeee9] bg-white p-1">
          <button
            type="button"
            onClick={() => controller.changeMode("edit")}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors",
              controller.mode === "edit"
                ? "bg-black text-white"
                : "text-black/60 hover:text-black",
            )}
          >
            <Icon name="ri-cursor-line" className="size-3.5" />
            Chỉnh vùng
          </button>
          <button
            type="button"
            onClick={() => controller.changeMode("interact")}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors",
              controller.mode === "interact"
                ? "bg-[#36533a] text-white"
                : "text-black/60 hover:text-black",
            )}
          >
            <Icon name="ri-play-circle-line" className="size-3.5" />
            Tương tác
          </button>
        </div>

        <p className="min-w-0 flex-1 truncate text-[11px] text-black/50">
          {hint}
        </p>

        <Button
          type="button"
          variant="outline"
          size="icon-sm"
          className="rounded-full border-[#eeeee9] bg-white"
          onClick={() => controller.setShowOverlays(!controller.showOverlays)}
          aria-label={
            controller.showOverlays ? "Ẩn các vùng" : "Hiện các vùng"
          }
          title={controller.showOverlays ? "Ẩn các vùng" : "Hiện các vùng"}
        >
          <Icon
            name={controller.showOverlays ? "ri-eye-line" : "ri-eye-off-line"}
            className="size-4"
          />
        </Button>
      </div>

      <div
        ref={containerRef}
        className="relative min-h-0 flex-1 overflow-hidden rounded-[20px] border border-[#eeeee9] bg-[#f5f6f2] shadow-xs"
      >
        <div
          ref={shellRef}
          className="absolute"
          style={{
            width: DESIGN_WIDTH,
            height: DESIGN_HEIGHT,
            left,
            top,
            transform: `scale(${scale})`,
            transformOrigin: "top left",
          }}
        >
          <ReaderFrame
            courseTitle={courseTitle}
            modules={controller.frameModules}
            activeLessonId={controller.activeLessonId}
            activeLesson={controller.frameActiveLesson}
            activeModule={controller.frameActiveModule}
            slides={controller.slides}
            currentSlide={controller.currentSlideIndex}
            activeIsQuiz={controller.activeIsQuiz}
            chatOpen={chatOpen}
            chatAllowed
            onToggleChat={() => setChatOpen((value) => !value)}
            onSelectLesson={controller.selectLesson}
            onPrevSlide={controller.prevSlide}
            onNextSlide={controller.nextSlide}
            preview
            interactive={controller.mode === "interact"}
            slideContent={
              slideUrl ? (
                <div
                  data-aoi="slide"
                  className="relative aspect-video overflow-hidden rounded-[18px] border border-border/80 bg-white shadow-sm"
                >
                  <LazyPdfPage
                    key={`${slideUrl}:${activeSlide?.pageNumber ?? 1}`}
                    url={slideUrl}
                    pageNumber={activeSlide?.pageNumber ?? 1}
                    alt={activeSlide?.title ?? "Trang bài học"}
                    className="absolute inset-0"
                  />
                </div>
              ) : (
                <div className="flex aspect-video flex-col items-center justify-center rounded-[18px] border border-border/80 bg-white p-8 text-center shadow-sm">
                  <div className="flex size-11 items-center justify-center rounded-full bg-muted text-foreground">
                    <Icon name="ri-image-line" className="size-5" />
                  </div>
                  <p className="mt-4 max-w-sm text-base font-semibold text-foreground">
                    {controller.activeIsQuiz
                      ? "Bài tập mẫu"
                      : "Chưa có slide để hiển thị"}
                  </p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {controller.activeIsQuiz
                      ? "Dùng tab Giao diện để chọn vùng cho bài tập."
                      : "Tải tài liệu ở tab Nội dung trước."}
                  </p>
                </div>
              )
            }
            quizContent={<ReaderQuizPreview />}
            chatPanel={
              <ReaderChatPreview
                open={chatOpen}
                onClose={() => setChatOpen(false)}
              />
            }
            contentMaxWidth="1120px"
            className="h-full"
          />
        </div>

        <AoiOverlay
          containerRef={containerRef}
          shellRef={shellRef}
          slideDefinitions={controller.slideDefinitions}
          uiDefinitions={controller.uiDefinitions}
          tab={controller.tab}
          mode={controller.mode}
          selectedCode={controller.selectedCode}
          hoveredCode={hoveredCode}
          showOverlays={controller.showOverlays}
          canManage={controller.canManage}
          layoutKey={`${controller.activeSlideId}:${chatOpen}:${controller.mode}:${controller.tab}`}
          onSelect={controller.setSelectedCode}
          onHover={onHover}
          onCreateSlide={controller.createSlideAoi}
          onCreateUiComponent={controller.createUiComponentAoi}
          onCreateUiCustom={controller.createUiCustomAoi}
        />
      </div>

      {!controller.activeIsQuiz && controller.slides.length > 0 && (
        <div className="flex shrink-0 items-center gap-2 overflow-x-auto pb-1">
          {controller.slides.map((slide, index) => {
            const url = resolveMediaUrl(slide.pdfUrl);
            const active = slide.id === controller.activeSlideId;
            return (
              <button
                key={slide.id}
                type="button"
                onClick={() => controller.selectSlide(slide.id)}
                className={cn(
                  "relative w-24 shrink-0 overflow-hidden rounded-lg border-2 bg-white p-0.5 transition",
                  active
                    ? "border-black"
                    : "border-transparent hover:border-black/20",
                )}
                aria-label={`Trang ${index + 1}`}
                title={`Trang ${index + 1}`}
              >
                {url ? (
                  <LazyPdfPage
                    url={url}
                    pageNumber={slide.pageNumber}
                    lazy
                    alt={`Trang ${index + 1}`}
                    className="aspect-video w-full overflow-hidden rounded-md bg-white"
                  />
                ) : (
                  <span className="flex aspect-video w-full items-center justify-center rounded-md bg-muted text-[10px] text-muted-foreground">
                    {index + 1}
                  </span>
                )}
                <span
                  className={cn(
                    "absolute bottom-0.5 right-0.5 rounded px-1 text-[9px] font-semibold tabular-nums",
                    active
                      ? "bg-black text-white"
                      : "bg-white/90 text-black/60",
                  )}
                >
                  {index + 1}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
