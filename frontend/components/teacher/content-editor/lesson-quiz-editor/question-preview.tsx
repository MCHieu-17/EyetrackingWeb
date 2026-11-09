"use client";

import { isQuestionComplete, questionIssues } from "@/lib/quiz-validation";
import { cn } from "@/lib/utils";
import type { QuizQuestion } from "@/lib/types/domain";

/** Dòng xem nhanh một câu hỏi trong danh sách bên trái. */
export function QuestionPreview({
  question,
  index,
  active,
  onSelect,
}: {
  question: QuizQuestion;
  index: number;
  active: boolean;
  onSelect: () => void;
}) {
  const complete = isQuestionComplete(question);

  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-current={active ? "true" : undefined}
        aria-label={`Câu hỏi ${index + 1}`}
        className={cn(
          "flex w-full items-center gap-2 rounded-[14px] border px-2.5 py-2 text-left transition",
          active
            ? "border-[#6f8f69] bg-[#e8f1e6]/60"
            : "border-[#eeeee9] bg-[#fdfdfa] hover:border-black/15",
        )}
      >
        <span
          className={cn(
            "flex size-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold tabular-nums",
            active ? "bg-black text-white" : "bg-black/5 text-black/60",
          )}
        >
          {index + 1}
        </span>
        <span
          className={cn(
            "min-w-0 flex-1 truncate text-xs",
            question.prompt.trim() ? "text-black" : "italic text-black/45",
          )}
        >
          {question.prompt.trim() || "Chưa có nội dung"}
        </span>
        {!complete && (
          <span
            className="size-2 shrink-0 rounded-full bg-warning"
            title={questionIssues(question).join(" · ")}
            aria-label={questionIssues(question).join(" · ")}
          />
        )}
        <span className="shrink-0 text-[11px] font-medium text-black/50 tabular-nums">
          {question.points}đ
        </span>
      </button>
    </li>
  );
}
