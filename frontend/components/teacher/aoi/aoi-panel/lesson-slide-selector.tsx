"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";
import type { AoiEditorController } from "../use-aoi-editor";

export function LessonSlideSelector({
  courseId,
  controller,
  onHelpOpen,
}: {
  courseId: string;
  controller: AoiEditorController;
  onHelpOpen: () => void;
}) {
  return (
    <>
      <div className="flex items-start gap-2">
        <label className="min-w-0 flex-1">
          <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-black/40">
            Bài giảng
          </span>
          <select
            value={controller.activeLessonId}
            onChange={(event) => controller.selectLesson(event.target.value)}
            className="mt-1 w-full rounded-xl border border-[#eeeee9] bg-[#fdfdfa] px-2.5 py-2 text-xs font-medium text-black outline-none focus:border-black/20 focus:ring-2 focus:ring-[#e8f1e6]"
          >
            {controller.tree.map((module) => (
              <optgroup key={module.id} label={module.title}>
                {module.lessons.map((lesson) => (
                  <option key={lesson.id} value={lesson.id}>
                    {lesson.title}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          className="mt-4 rounded-full"
          onClick={onHelpOpen}
          aria-label="Cách dùng"
          title="Cách dùng"
        >
          <Icon name="ri-question-line" className="size-4" />
        </Button>
      </div>

      {controller.activeIsQuiz ? (
        <p className="mt-3 rounded-full bg-muted px-3 py-1.5 text-center text-xs font-medium text-foreground">
          Bài tập
        </p>
      ) : controller.slides.length > 0 ? (
        <div className="mt-3 flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            className="rounded-full"
            onClick={controller.prevSlide}
            disabled={controller.currentSlideIndex === 0}
            aria-label="Trang trước"
          >
            <Icon name="ri-arrow-left-s-line" className="size-4" />
          </Button>
          <div className="min-w-0 flex-1">
            <p className="text-center text-[11px] font-medium tabular-nums text-black/60">
              Trang {controller.currentSlideIndex + 1}/{controller.slides.length}
            </p>
            <div className="mt-1 h-1 rounded-full bg-black/10">
              <div
                className="h-full rounded-full bg-[#36533a] transition-[width]"
                style={{
                  width: `${
                    ((controller.currentSlideIndex + 1) /
                      controller.slides.length) *
                    100
                  }%`,
                }}
              />
            </div>
          </div>
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            className="rounded-full"
            onClick={controller.nextSlide}
            disabled={
              controller.currentSlideIndex >= controller.slides.length - 1
            }
            aria-label="Trang sau"
          >
            <Icon name="ri-arrow-right-s-line" className="size-4" />
          </Button>
        </div>
      ) : (
        <div className="mt-3 rounded-xl border border-dashed border-black/10 bg-[#f7f7f4] px-3 py-3 text-center text-xs text-black/50">
          Bài giảng này chưa có slide.
          <Link
            href={`/teacher/courses/${courseId}?tab=content`}
            className="mt-1 block font-semibold text-[#36533a] underline"
          >
            Mở tab Nội dung
          </Link>
        </div>
      )}

      <div className="mt-3 flex rounded-full border border-[#eeeee9] bg-[#f7f7f4] p-1">
        <button
          type="button"
          onClick={() => controller.changeTab("slide")}
          disabled={controller.activeIsQuiz}
          className={cn(
            "flex-1 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors disabled:opacity-40",
            controller.tab === "slide"
              ? "bg-black text-white"
              : "text-black/55 hover:text-black",
          )}
        >
          Slide
        </button>
        <button
          type="button"
          onClick={() => controller.changeTab("ui")}
          className={cn(
            "flex-1 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors",
            controller.tab === "ui"
              ? "bg-black text-white"
              : "text-black/55 hover:text-black",
          )}
        >
          Giao diện
        </button>
      </div>
    </>
  );
}
