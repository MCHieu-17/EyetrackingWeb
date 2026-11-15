"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";

const OPTIONS = [
  "Đáp án A — khái niệm chính",
  "Đáp án B — ví dụ minh họa",
  "Đáp án C — bài tập vận dụng",
];

/**
 * Bản xem trước bài tập với đúng `data-aoi` như InlineQuiz.
 * Nội dung là mẫu; giáo viên dùng để chọn vùng giao diện bài tập.
 */
export function ReaderQuizPreview() {
  const [selected, setSelected] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div
        data-aoi="quiz-question"
        className="shrink-0 rounded-[18px] border border-border/80 bg-white p-5 shadow-xs"
      >
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          Câu 1 / 3
        </p>
        <p className="mt-2 text-base font-semibold leading-7 text-foreground">
          Thành phần nào đóng vai trò quan trọng nhất trong nội dung bài học?
        </p>
      </div>

      <fieldset
        data-aoi="quiz-options"
        className="mt-4 min-h-0 flex-1 space-y-2.5 overflow-y-auto overscroll-contain pr-1"
      >
        <legend className="sr-only">Các đáp án</legend>
        {OPTIONS.map((option) => {
          const active = selected === option;
          return (
            <button
              key={option}
              type="button"
              onClick={() => {
                setSelected(option);
                setSubmitted(false);
              }}
              className={cn(
                "flex w-full items-center gap-3 rounded-[16px] border px-4 py-3 text-left text-sm transition",
                active
                  ? "border-[#36533a] bg-[#e8f1e6] text-foreground"
                  : "border-border/80 bg-white text-foreground hover:border-foreground/20",
              )}
            >
              <span
                className={cn(
                  "flex size-5 shrink-0 items-center justify-center rounded-full border",
                  active
                    ? "border-[#36533a] bg-[#36533a] text-white"
                    : "border-border bg-white",
                )}
              >
                {active && <Icon name="ri-check-line" className="size-3" />}
              </span>
              {option}
            </button>
          );
        })}
      </fieldset>

      <div className="mt-4 flex shrink-0 items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">
          {submitted
            ? "Đã nộp bài mẫu — đây chỉ là bản xem trước."
            : "Chọn một đáp án rồi bấm nộp."}
        </p>
        <Button
          data-aoi="quiz-submit"
          type="button"
          disabled={!selected}
          onClick={() => setSubmitted(true)}
          className="rounded-full"
        >
          Nộp bài
        </Button>
      </div>
    </div>
  );
}
