"use client";

import {
  RiArrowRightLine,
  RiCheckLine,
  RiTimeLine,
} from "@remixicon/react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import type { QuizQuestion } from "@/lib/types/domain";
import { getOptionLetter } from "./quiz-helpers";

export function QuestionView({
  question,
  currentIndex,
  total,
  selected,
  answeredCount,
  remainingMin,
  submitting,
  submitError,
  onToggleOption,
  onPrev,
  onNext,
  onSubmit,
}: {
  question: QuizQuestion;
  currentIndex: number;
  total: number;
  selected: string[];
  answeredCount: number;
  remainingMin: number | null;
  submitting: boolean;
  submitError?: string;
  onToggleOption: (optionId: string) => void;
  onPrev: () => void;
  onNext: () => void;
  onSubmit: () => void;
}) {
  return (
    <div
      data-aoi="quiz-question"
      className="flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-border/80 bg-white p-5 shadow-xs sm:p-7"
    >
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3">
        <span className="rounded-full bg-[#e8f1e6] px-3 py-1 text-xs font-semibold text-[#36533a]">
          Câu {currentIndex + 1} / {total}
        </span>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          {remainingMin != null && (
            <span className="flex items-center gap-1.5">
              <RiTimeLine className="size-3.5" />
              Còn ~{remainingMin} phút
            </span>
          )}
          <span>{question.points} điểm</span>
        </div>
      </div>
      <Progress
        value={(answeredCount / total) * 100}
        className="mt-4 h-1 shrink-0 bg-muted"
      />

      <h2
        key={question.id}
        className="mt-6 max-h-[35%] shrink-0 overflow-y-auto overscroll-contain pr-1 text-lg font-semibold leading-7 text-foreground sm:text-xl"
      >
        {question.prompt}
      </h2>
      {question.allowMultiple && (
        <p className="mt-1 shrink-0 text-xs text-muted-foreground">
          Chọn tất cả đáp án đúng.
        </p>
      )}

      <fieldset
        key={question.id}
        data-aoi="quiz-options"
        className="mt-5 min-h-0 flex-1 space-y-2.5 overflow-y-auto overscroll-contain pr-1"
      >
        <legend className="sr-only">Chọn đáp án</legend>
        {question.options.map((option, index) => {
          const isSelected = selected.includes(option.id);
          return (
            <label
              key={option.id}
              className={cn(
                "flex cursor-pointer items-center gap-3 rounded-2xl border p-3.5 transition sm:p-4",
                isSelected
                  ? "border-[#789472] bg-[#f2f7f0] shadow-[0_0_0_1px_#789472]"
                  : "border-border bg-white hover:border-foreground/20 hover:bg-muted/40",
              )}
            >
              <input
                type={question.allowMultiple ? "checkbox" : "radio"}
                name={question.id}
                checked={isSelected}
                onChange={() => onToggleOption(option.id)}
                className="sr-only"
              />
              <span
                className={cn(
                  "flex size-8 shrink-0 items-center justify-center rounded-full border text-sm font-semibold",
                  isSelected
                    ? "border-[#789472] bg-[#789472] text-white"
                    : "border-border text-muted-foreground",
                )}
              >
                {isSelected ? <RiCheckLine className="size-4" /> : getOptionLetter(index)}
              </span>
              <span className="text-sm font-medium leading-6">{option.text}</span>
            </label>
          );
        })}
      </fieldset>

      <div className="mt-6 flex shrink-0 items-center justify-between gap-3 border-t border-border pt-4">
        <Button
          variant="outline"
          size="sm"
          disabled={currentIndex === 0}
          onClick={onPrev}
        >
          Trước
        </Button>
        {currentIndex < total - 1 ? (
          <Button size="sm" onClick={onNext}>
            Tiếp<RiArrowRightLine className="size-4" />
          </Button>
        ) : (
          <Button
            data-aoi="quiz-submit"
            size="sm"
            disabled={submitting}
            onClick={onSubmit}
          >
            {submitting ? "Đang nộp…" : "Nộp bài"}
          </Button>
        )}
      </div>
      {submitError && (
        <p
          role="alert"
          className="mt-3 shrink-0 text-center text-sm text-destructive"
        >
          {submitError}
        </p>
      )}
    </div>
  );
}
