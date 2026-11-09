"use client";

import { type ReactNode, type RefObject, useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";
import type { LessonItem, ModuleItem, Slide } from "@/lib/types/domain";

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

function allLessons(modules: ModuleItem[]): LessonItem[] {
  return modules.flatMap((module) => module.lessons);
}

function ReaderOutline({
  courseTitle,
  modules,
  activeLessonId,
  openModules,
  onToggleModule,
  onSelectLesson,
  onCollapse,
}: {
  courseTitle: string;
  modules: ModuleItem[];
  activeLessonId: string;
  openModules: Record<string, boolean>;
  onToggleModule: (moduleId: string) => void;
  onSelectLesson: (lessonId: string) => void;
  onCollapse?: () => void;
}) {
  const total = allLessons(modules).length;
  return (
    <>
      <div className="px-5 pb-4 pt-5">
        <div className="flex items-center justify-between gap-3">
          <span className="rounded-full bg-[#e8f1e6] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[#52704f]">
            Mục lục
          </span>
          {onCollapse && (
            <button
              type="button"
              onClick={onCollapse}
              className="hidden size-7 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground lg:inline-flex"
              aria-label="Thu gọn mục lục"
            >
              <Icon name="ri-arrow-left-s-line" className="size-4" />
            </button>
          )}
        </div>
        <h2 className="mt-4 line-clamp-2 text-base font-semibold leading-6 tracking-tight text-foreground">
          {courseTitle}
        </h2>
        <p className="mt-5 text-[11px] text-muted-foreground">{total} mục</p>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 pb-3">
        {modules.map((module) => {
          const isOpen = !!openModules[module.id];
          const containsActive = module.lessons.some(
            (lesson) => lesson.id === activeLessonId,
          );
          return (
            <section key={module.id} className="py-1">
              <button
                type="button"
                onClick={() => onToggleModule(module.id)}
                className="group flex w-full items-start gap-3 rounded-2xl px-3 py-3 text-left transition-colors hover:bg-muted"
              >
                <span
                  className={cn(
                    "mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold",
                    containsActive
                      ? "bg-primary text-white"
                      : "border border-border bg-surface text-muted-foreground",
                  )}
                >
                  {String(module.orderIndex).padStart(2, "0")}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium leading-5 text-foreground">
                    {module.title}
                  </span>
                  <span className="mt-0.5 block text-xs text-muted-foreground">
                    {module.lessons.length} mục
                  </span>
                </span>
                <Icon
                  name="ri-arrow-right-s-line"
                  className={cn(
                    "mt-1 size-4 shrink-0 text-muted-foreground transition-transform",
                    isOpen && "rotate-90",
                  )}
                />
              </button>

              {isOpen && (
                <div className="mb-2 ml-6 border-l border-border pl-3">
                  {module.lessons.map((lesson) => {
                    const active = lesson.id === activeLessonId;
                    return (
                      <button
                        key={lesson.id}
                        type="button"
                        onClick={() => onSelectLesson(lesson.id)}
                        className={cn(
                          "relative flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left text-sm transition-colors",
                          active
                            ? "bg-primary text-white"
                            : "text-muted-foreground hover:bg-muted hover:text-foreground",
                        )}
                      >
                        {lesson.kind === "quiz" ? (
                          <Icon
                            name="ri-file-text-line"
                            className={cn(
                              "size-3.5 shrink-0",
                              active ? "text-white" : "text-muted-foreground",
                            )}
                          />
                        ) : (
                          <span
                            className={cn(
                              "size-3.5 shrink-0 rounded-full border",
                              active ? "border-white bg-white" : "border-border",
                            )}
                          />
                        )}
                        <span
                          className={cn(
                            "min-w-0 flex-1 truncate",
                            active && "font-medium",
                          )}
                        >
                          {lesson.title}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </section>
          );
        })}
      </nav>
    </>
  );
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
  const atLast = currentSlide === total - 1 && total > 0;
  const flatIndex = lessons.findIndex((lesson) => lesson.id === activeLessonId);
  const nextLesson = lessons[flatIndex + 1];

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
      <header
        data-aoi="header"
        className="z-40 flex h-12 shrink-0 items-center px-2 sm:px-3"
      >
        {preview ? (
          <span className="inline-flex min-w-0 items-center gap-2 rounded-full border border-border bg-white px-3 py-1.5 text-xs font-medium text-muted-foreground">
            <Icon name="ri-arrow-left-line" className="size-4 shrink-0" />
            <span className="hidden sm:inline">Khóa học của tôi</span>
          </span>
        ) : (
          <Link
            href="/student"
            className="inline-flex min-w-0 items-center gap-2 rounded-full border border-border bg-white px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-foreground/20 hover:text-foreground"
          >
            <Icon name="ri-arrow-left-line" className="size-4 shrink-0" />
            <span className="hidden sm:inline">Khóa học của tôi</span>
          </Link>
        )}

        <div className="mx-auto hidden min-w-0 px-4 md:block">
          <p className="max-w-[460px] truncate text-center text-xs font-medium text-muted-foreground">
            {courseTitle}
          </p>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <Button
            ref={chatButtonRef}
            data-aoi="chat-open-button"
            variant="outline"
            size="sm"
            onClick={onToggleChat}
            title={
              chatReason ??
              (chatAllowed ? "Trợ lý học tập" : "Trợ lý đang khóa")
            }
            aria-expanded={chatOpen}
            aria-controls="assistant-panel"
            aria-label={chatOpen ? "Đóng trợ lý học tập" : "Mở trợ lý học tập"}
            className={cn(
              "gap-1.5",
              preview ? "inline-flex" : "hidden xl:inline-flex",
              chatOpen && "border-[#cfe0cb] bg-[#e8efe6] text-[#36533a]",
            )}
          >
            <Icon name="ri-sparkling-2-line" className="size-4" />
            <span className="hidden sm:inline">
              {!chatAllowed ? "Trợ lý đang khóa" : "Trợ lý"}
            </span>
          </Button>

          {!preview && gazeSource === "real" ? (
            <div className="hidden items-center gap-1.5 rounded-full border border-border bg-white px-3 py-1.5 text-[11px] text-foreground sm:flex">
              <span className="size-1.5 animate-pulse rounded-full bg-primary" />
              Gaze đang hoạt động
            </div>
          ) : !preview && !calibrationRequired ? (
            <div className="hidden items-center gap-1.5 rounded-full border border-border bg-white px-3 py-1.5 text-[11px] text-muted-foreground sm:flex">
              <span className="size-1.5 rounded-full bg-muted-foreground" />
              Gaze tắt
            </div>
          ) : !preview ? (
            <div className="hidden items-center gap-1.5 rounded-full border border-border bg-white px-3 py-1.5 text-[11px] text-muted-foreground sm:flex">
              <span className="size-1.5 rounded-full bg-muted-foreground" />
              Gaze chưa kết nối
            </div>
          ) : null}

          <Button
            variant="ghost"
            size="icon-sm"
            className="lg:hidden"
            onClick={() => setMobileOutlineOpen(true)}
            aria-label="Mở mục lục"
          >
            <Icon name="ri-menu-line" className="size-5" />
          </Button>
        </div>
      </header>

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
        {desktopOutlineOpen && (
          <aside
            data-aoi="outline"
            className="hidden w-[220px] shrink-0 flex-col overflow-hidden rounded-[20px] border border-border/80 bg-white shadow-xs lg:flex"
          >
            {outline}
          </aside>
        )}

        {mobileOutlineOpen && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <button
              type="button"
              className="absolute inset-0 bg-black/35 backdrop-blur-[2px]"
              onClick={() => setMobileOutlineOpen(false)}
              aria-label="Đóng mục lục"
            />
            <aside
              data-aoi="outline"
              className="absolute inset-y-2 left-2 flex w-[min(88vw,320px)] flex-col overflow-hidden rounded-[20px] border border-border/80 bg-white shadow-lg"
            >
              <div className="flex h-14 items-center justify-between px-5">
                <span className="text-sm font-semibold">Mục lục</span>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => setMobileOutlineOpen(false)}
                  aria-label="Đóng mục lục"
                >
                  <Icon name="ri-close-line" className="size-5" />
                </Button>
              </div>
              {outline}
            </aside>
          </div>
        )}

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
            <footer
              data-aoi="lesson-nav"
              className="absolute inset-x-0 bottom-3 z-20 px-3 sm:bottom-4 sm:px-5"
            >
              <div className="mx-auto flex max-w-xl items-center gap-2 rounded-full border border-border/80 bg-white/95 p-1.5 shadow-md backdrop-blur-md">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onPrevSlide}
                  disabled={currentSlide === 0 || total === 0}
                >
                  <Icon name="ri-arrow-left-s-line" className="size-4" />
                  <span className="hidden sm:inline">Trước</span>
                </Button>

                <div className="flex-1" />

                {atLast && nextLesson ? (
                  <Button size="sm" onClick={() => selectLesson(nextLesson.id)}>
                    Bài tiếp theo
                    <Icon name="ri-arrow-right-s-line" className="size-4" />
                  </Button>
                ) : atLast ? (
                  <span className="hidden px-2 text-xs font-medium text-muted-foreground sm:inline-flex">
                    Đã xem hết bài
                  </span>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onNextSlide}
                    disabled={atLast || total === 0}
                  >
                    <span className="hidden sm:inline">Sau</span>
                    <Icon name="ri-arrow-right-s-line" className="size-4" />
                  </Button>
                )}
              </div>
            </footer>
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
