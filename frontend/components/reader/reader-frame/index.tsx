"use client";

import { type ReactNode, type RefObject, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";
import type { LessonItem, ModuleItem, Slide } from "@/lib/types/domain";
import { ReaderOutline } from "./reader-outline";
import { ReaderSidebar } from "./reader-sidebar";
import { ReaderSlideControls } from "./reader-slide-controls";
import { ReaderTopbar } from "./reader-topbar";
import { allLessons, getNextLesson, isAtLastSlide } from "./reader-helpers";

interface ReaderFrameProps {
  courseTitle: string;
  modules: ModuleItem[];
  activeLessonId: string;
  activeLesson: LessonItem | null;
  activeModule: ModuleItem | null;
  slides: Slide[];
  currentSlide: number;
  activeIsQuiz: boolean;
  chatOpen: boolean;
  chatAllowed: boolean;
  chatReason?: string | null;
  chatButtonRef?: RefObject<HTMLButtonElement | null>;
  onToggleChat: () => void;
  onSelectLesson: (lessonId: string) => void;
  onPrevSlide: () => void;
  onNextSlide: () => void;
  preview?: boolean;
  interactive?: boolean;
  gazeSource?: "real" | "off" | "simulated" | null;
  calibrationRequired?: boolean;
  banners?: ReactNode;
  slideContent?: ReactNode;
  quizContent?: ReactNode;
  chatPanel?: ReactNode;
  overlay?: ReactNode;
  contentMaxWidth?: string;
  className?: string;
}

/**
 * Khung hiển thị dùng chung cho trang học viên và bản xem trước của giáo viên.
 *
 * Mọi `data-aoi` trong khung này là hợp đồng với bộ vùng giao diện. Khi thêm
 * phần tử mới, cập nhật `frontend/lib/aoi/ui-components.ts` tương ứng.
 */
export function ReaderFrame({
  courseTitle,
  modules,
  activeLessonId,
  activeLesson,
  activeModule,
  slides,
  currentSlide,
  activeIsQuiz,
  chatOpen,
  chatAllowed,
  chatReason,
  chatButtonRef,
  onToggleChat,
  onSelectLesson,
  onPrevSlide,
  onNextSlide,
  preview = false,
  interactive = true,
  gazeSource = null,
  calibrationRequired = true,
  banners,
  slideContent,
  quizContent,
  chatPanel,
  overlay,
  contentMaxWidth = "min(1120px, calc((100dvh - 10.5rem) * 16 / 9))",
  className,
}: ReaderFrameProps) {
  const [desktopOutlineOpen, setDesktopOutlineOpen] = useState(true);
  const [mobileOutlineOpen, setMobileOutlineOpen] = useState(false);
  const [openModules, setOpenModules] = useState<Record<string, boolean>>({});

  const lessons = useMemo(() => allLessons(modules), [modules]);
  const total = slides.length;
  const atLast = isAtLastSlide(currentSlide, total);
  const nextLesson = getNextLesson(lessons, activeLessonId);

  // Render-phase adjust: mở chương chứa bài đang học (không dùng effect).
  if (activeModule && !openModules[activeModule.id]) {
    setOpenModules((prev) => ({ ...prev, [activeModule.id]: true }));
  }

  const selectLesson = (lessonId: string) => {
    onSelectLesson(lessonId);
    setMobileOutlineOpen(false);
  };

  const outline = (
    <ReaderOutline
      courseTitle={courseTitle}
      modules={modules}
      activeLessonId={activeLessonId}
      openModules={openModules}
      onToggleModule={(moduleId) =>
        setOpenModules((prev) => ({
          ...prev,
          [moduleId]: !(prev[moduleId] ?? true),
        }))
      }
      onSelectLesson={selectLesson}
      onCollapse={() => setDesktopOutlineOpen(false)}
    />
  );

  return (
    <div
      data-aoi="reader-root"
      className={cn(
        "relative flex h-full flex-col overflow-hidden bg-[#f5f6f2] p-2 text-foreground sm:p-3",
        className,
      )}
    >
      <ReaderTopbar
        courseTitle={courseTitle}
        preview={preview}
        chatOpen={chatOpen}
        chatAllowed={chatAllowed}
        chatReason={chatReason}
        chatButtonRef={chatButtonRef}
        onToggleChat={onToggleChat}
        gazeSource={gazeSource}
        calibrationRequired={calibrationRequired}
        onOpenMobileOutline={() => setMobileOutlineOpen(true)}
      />

      {!preview && !chatAllowed && chatReason && (
        <p
          role="status"
          className="rounded-xl border border-warning/30 bg-warning/10 px-4 py-2 text-xs text-foreground"
        >
          {chatReason}
        </p>
      )}

      <div
        className={cn(
          "flex min-h-0 flex-1 gap-3",
          !interactive && "pointer-events-none",
        )}
      >
        <ReaderSidebar
          desktopOpen={desktopOutlineOpen}
          mobileOpen={mobileOutlineOpen}
          onCloseMobile={() => setMobileOutlineOpen(false)}
          outline={outline}
        />

        <main
          data-aoi="lesson-content"
          className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-[20px] border border-border/80 bg-[#fffffb] shadow-xs"
        >
          <div className="z-10 shrink-0 px-4 py-3 sm:px-5">
            <div className="mx-auto flex max-w-[1400px] items-center gap-3">
              {!desktopOutlineOpen && (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="hidden shrink-0 lg:inline-flex"
                  onClick={() => setDesktopOutlineOpen(true)}
                  aria-label="Mở mục lục"
                >
                  <Icon name="ri-menu-line" className="size-5" />
                </Button>
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-[11px] text-muted-foreground">
                  {activeModule
                    ? `Chương ${activeModule.orderIndex} · ${activeModule.title}`
                    : "Bài học"}
                </p>
                <h1 className="mt-0.5 truncate text-sm font-medium text-foreground">
                  {activeLesson?.title ?? "Đang tải bài học..."}
                </h1>
              </div>
              <div className="shrink-0 rounded-full bg-muted px-3 py-1.5">
                {activeIsQuiz ? (
                  <p className="text-xs font-medium text-foreground">Bài tập</p>
                ) : (
                  <p className="text-xs font-medium tabular-nums text-foreground">
                    {total ? currentSlide + 1 : 0}
                    <span className="font-normal text-muted-foreground">
                      {" "}
                      / {total}
                    </span>
                  </p>
                )}
              </div>
            </div>
          </div>

          {banners}

          <div className="min-h-0 flex-1 overflow-auto bg-[#f9f9f5] px-3 pb-24 pt-3 sm:px-5">
            {activeIsQuiz ? (
              <div data-aoi="quiz" className="mx-auto w-full max-w-4xl py-2">
                {quizContent ?? (
                  <p className="p-8 text-center text-sm text-muted-foreground">
                    Bài tập chưa sẵn sàng.
                  </p>
                )}
              </div>
            ) : (
              <div className="mx-auto flex min-h-full w-full max-w-6xl flex-col justify-center gap-8 py-2">
                <div
                  className="mx-auto w-full"
                  style={{ maxWidth: contentMaxWidth }}
                >
                  {slideContent ?? (
                    <div className="flex aspect-video flex-col items-center justify-center rounded-[18px] border border-border/80 bg-white p-8 text-center shadow-sm">
                      <div className="flex size-11 items-center justify-center rounded-full bg-muted text-foreground">
                        <Icon name="ri-image-line" className="size-5" />
                      </div>
                      <p className="mt-4 max-w-sm text-base font-semibold text-foreground sm:text-lg">
                        {activeLesson?.title ?? "Nội dung bài học"}
                      </p>
                      <p className="mt-2 text-sm text-muted-foreground">
                        Nội dung trang PDF sẽ hiển thị tại đây.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {!activeIsQuiz && (
            <ReaderSlideControls
              currentSlide={currentSlide}
              total={total}
              atLast={atLast}
              nextLesson={nextLesson}
              onPrevSlide={onPrevSlide}
              onNextSlide={onNextSlide}
              onSelectLesson={selectLesson}
            />
          )}
        </main>

        {chatPanel}
      </div>

      {overlay && (
        <div
          className={cn(
            "absolute inset-0 z-50",
            interactive ? "pointer-events-none" : "pointer-events-auto",
          )}
        >
          {overlay}
        </div>
      )}
    </div>
  );
}
