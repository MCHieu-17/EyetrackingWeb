"use client";

import { useState } from "react";
import {
  RiCheckLine,
  RiCloseLine,
  RiRefreshLine,
} from "@remixicon/react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { QuizAssignment, QuizAttempt } from "@/lib/types/domain";
import { NextButton } from "./next-button";
import {
  countCorrectAnswers,
  getOptionLetter,
  getPercentage,
  isAnswerCorrect,
} from "./quiz-helpers";

export function ReviewView({
  assignment,
  attempt,
  onNext,
  hasNext,
  canRetry,
  retrying,
  retryError,
  onRetry,
}: {
  assignment: QuizAssignment;
  attempt: QuizAttempt;
  onNext?: () => void;
  hasNext?: boolean;
  canRetry: boolean;
  retrying: boolean;
  retryError?: string;
  onRetry: () => void;
}) {
  const [confirmRetry, setConfirmRetry] = useState(false);
  const percentage = getPercentage(attempt.score, attempt.maxScore);
  const correctCount = countCorrectAnswers(assignment.questions, attempt.answers);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 rounded-2xl border border-border/80 bg-white p-5 shadow-xs sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Badge variant={percentage >= 70 ? "success" : "warning"}>
            {percentage >= 70 ? "Hoàn thành tốt" : "Cần ôn tập thêm"}
          </Badge>
          <h2 className="mt-3 text-lg font-semibold text-foreground">{assignment.title}</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {attempt.score}/{attempt.maxScore} điểm · {correctCount}/{assignment.questions.length} câu đúng
          </p>
          <Progress value={percentage} className="mt-3 max-w-sm" indicatorClassName="bg-[#789472]" />
        </div>
        <div className="flex shrink-0 flex-col items-stretch gap-2 sm:items-end">
          <NextButton onNext={onNext} hasNext={hasNext} />
          {canRetry && (
            <Button
              variant="outline"
              size="sm"
              disabled={retrying}
              onClick={() => setConfirmRetry(true)}
            >
              <RiRefreshLine className="size-4" />
              {retrying ? "Đang làm lại…" : "Làm lại"}
            </Button>
          )}
        </div>
      </div>

      {retryError && (
        <p role="alert" className="text-sm text-destructive">
          {retryError}
        </p>
      )}

      <div className="space-y-3">
        {assignment.questions.map((question, questionIndex) => {
          const selected = attempt.answers[question.id] ?? [];
          const isCorrect = isAnswerCorrect(selected, question.correctOptionIds);
          const correct = new Set(question.correctOptionIds);
          return (
            <article key={question.id} className="rounded-2xl border border-border/80 bg-white p-4 shadow-xs sm:p-5">
              <div className="flex items-start gap-3">
                <span
                  className={cn(
                    "flex size-8 shrink-0 items-center justify-center rounded-full",
                    isCorrect ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive",
                  )}
                >
                  {isCorrect ? <RiCheckLine className="size-4" /> : <RiCloseLine className="size-4" />}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold text-muted-foreground">Câu {questionIndex + 1}</p>
                  <h3 className="mt-1 text-sm font-semibold leading-6 sm:text-base">{question.prompt}</h3>
                </div>
              </div>

              <div className="mt-3 space-y-2">
                {question.options.map((option, optionIndex) => {
                  const chosen = selected.includes(option.id);
                  const isAnswer = correct.has(option.id);
                  return (
                    <div
                      key={option.id}
                      className={cn(
                        "flex items-center gap-3 rounded-xl border px-3 py-2.5 text-sm",
                        isAnswer && "border-success/25 bg-success/6 text-success",
                        chosen && !isAnswer && "border-destructive/25 bg-destructive/6 text-destructive",
                        !isAnswer && !chosen && "border-transparent bg-muted/50 text-muted-foreground",
                      )}
                    >
                      <span className="font-semibold">{getOptionLetter(optionIndex)}.</span>
                      <span className="flex-1">{option.text}</span>
                      {chosen && <span className="text-xs font-semibold">Bạn chọn</span>}
                      {isAnswer && <span className="text-xs font-semibold">Đáp án đúng</span>}
                    </div>
                  );
                })}
                {selected.length === 0 && (
                  <p className="text-xs font-medium text-destructive">Bạn chưa trả lời câu này.</p>
                )}
              </div>

              {question.explanation && (
                <div className="mt-3 rounded-xl bg-[#f7f7f4] p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.1em] text-[#36533a]">Giải thích</p>
                  <p className="mt-1.5 text-sm leading-6 text-foreground/80">{question.explanation}</p>
                </div>
              )}
            </article>
          );
        })}
      </div>
      <Dialog open={confirmRetry} onOpenChange={setConfirmRetry}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Làm lại bài tập?</DialogTitle>
            <DialogDescription>
              Kết quả hiện tại ({attempt.score}/{attempt.maxScore} điểm) sẽ bị xoá và bạn làm lại từ
              đầu. Đồng hồ làm bài cũng chạy lại từ đầu.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmRetry(false)}>
              Giữ kết quả
            </Button>
            <Button
              onClick={() => {
                setConfirmRetry(false);
                onRetry();
              }}
            >
              <RiRefreshLine className="size-4" />
              Làm lại
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
