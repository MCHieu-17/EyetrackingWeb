"use client";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { LessonItem } from "@/lib/types/domain";

export function ReaderSlideControls({
  currentSlide,
  total,
  atLast,
  nextLesson,
  onPrevSlide,
  onNextSlide,
  onSelectLesson,
}: {
  currentSlide: number;
  total: number;
  atLast: boolean;
  nextLesson: LessonItem | undefined;
  onPrevSlide: () => void;
  onNextSlide: () => void;
  onSelectLesson: (lessonId: string) => void;
}) {
  return (
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
          <Button size="sm" onClick={() => onSelectLesson(nextLesson.id)}>
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
  );
}
