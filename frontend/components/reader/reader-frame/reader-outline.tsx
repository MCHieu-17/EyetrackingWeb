"use client";

import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";
import type { ModuleItem } from "@/lib/types/domain";
import { allLessons } from "./reader-helpers";

export function ReaderOutline({
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
