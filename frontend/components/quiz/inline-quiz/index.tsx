"use client";

import { useEffect, useRef, useState } from "react";
import {
  useQuizAssignment,
  useQuizAttempt,
  useRetryQuizAttempt,
  useStartQuizAttempt,
  useSubmitQuizAttempt,
} from "@/hooks/use-quiz";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAssistant } from "@/components/assistant/assistant-context";
import { NextButton } from "./next-button";
import { QuestionView } from "./question-view";
import { ReviewView } from "./review-view";
import {
  clampQuestionIndex,
  countAnswered,
  getRemainingMinutes,
  getRetryError,
  getSubmitError,
  shouldShowReview,
} from "./quiz-helpers";

export function InlineQuiz({
  quizId,
  onNext,
  hasNext,
}: {
  quizId: string;
  onNext?: () => void;
  hasNext?: boolean;
}) {
  // Đổi quiz phải dựng lại toàn bộ state cục bộ (câu hiện tại, đáp án, hạn...).
  return (
    <InlineQuizSession
      key={quizId}
      quizId={quizId}
      onNext={onNext}
      hasNext={hasNext}
    />
  );
}

function InlineQuizSession({
  quizId,
  onNext,
  hasNext,
}: {
  quizId: string;
  onNext?: () => void;
  hasNext?: boolean;
}) {
  const assignmentQuery = useQuizAssignment(quizId);
  const assignment = assignmentQuery.data;
  const attemptQuery = useQuizAttempt(assignment?.lessonId ?? "");
  const startAttempt = useStartQuizAttempt();
  const submitAttempt = useSubmitQuizAttempt();
  const retryAttempt = useRetryQuizAttempt();
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string[]>>({});
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [expired, setExpired] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const expiresAt = assignment?.expiresAt;
  const attempt = attemptQuery.data;
  const { setQuizContext } = useAssistant();
  const autoStartedRef = useRef<string | null>(null);

  // Chat panel ở reader root đọc context này để chuyển sang mode quiz/review.
  useEffect(() => {
    const lessonId = assignment?.lessonId;
    if (
      !lessonId ||
      assignment.status !== "published" ||
      !attemptQuery.isSuccess ||
      attemptQuery.data !== null
    ) {
      return;
    }
    // Mỗi bài chỉ tự tạo lượt một lần. Nếu request lỗi, query vẫn trả null —
    // không được gọi lại vô hạn mỗi lần render.
    const key = `${assignment.id}:${lessonId}`;
    if (autoStartedRef.current === key || startAttempt.isPending) return;
    autoStartedRef.current = key;
    startAttempt.mutate({ lessonId });
  }, [assignment, attemptQuery.isSuccess, attemptQuery.data, startAttempt]);

  useEffect(() => {
    if (!assignment) return;
    setQuizContext({
      mode: attempt?.status === "submitted" ? "review" : "quiz",
      assignmentId: assignment.id,
      attemptId: attempt?.id ?? null,
      lessonId: assignment.lessonId ?? null,
      draftAnswers: attempt?.status === "submitted" ? undefined : answers,
    });
  }, [assignment, attempt, answers, setQuizContext]);

  useEffect(() => {
    return () => setQuizContext(null);
  }, [setQuizContext]);

  useEffect(() => {
    if (!expiresAt) return;
    const delay = Math.max(0, new Date(expiresAt).getTime() - Date.now());
    const timeout = window.setTimeout(() => setExpired(true), delay);
    return () => window.clearTimeout(timeout);
  }, [expiresAt]);

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 15000);
    return () => window.clearInterval(id);
  }, []);

  if (assignmentQuery.isLoading || attemptQuery.isLoading) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center overflow-hidden">
        <Skeleton className="h-full max-h-72 w-full rounded-2xl" />
      </div>
    );
  }
  if (assignmentQuery.isError || attemptQuery.isError || !assignment) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center overflow-hidden p-8">
        <p className="text-center text-sm text-muted-foreground">
          Bài tập hiện không khả dụng.
        </p>
      </div>
    );
  }

  if (attempt && shouldShowReview(attempt)) {
    // Review nhiều câu cần cuộn, nhưng khung `quiz` bên ngoài vẫn cố định
    // nên rect AOI của bài tập không đổi.
    return (
      <div className="h-full min-h-0 overflow-y-auto overscroll-contain pb-2 pr-1">
        <ReviewView
          assignment={assignment}
          attempt={attempt}
          onNext={onNext}
          hasNext={hasNext}
          // Chỉ làm lại được khi giáo viên bật cờ và bài vẫn đang mở.
          canRetry={Boolean(assignment.allowRetry) && assignment.status === "published" && !expired}
          retrying={retryAttempt.isPending}
          retryError={getRetryError(retryAttempt.isError, retryAttempt.error)}
          onRetry={() =>
            retryAttempt.mutate(
              { attemptId: attempt.id, lessonId: assignment.lessonId ?? "" },
              {
                onSuccess: () => {
                  // Lượt làm cũ vẫn còn trong lịch sử; dựng lại UI từ đầu.
                  setCurrentIndex(0);
                  setAnswers({});
                  setExpired(false);
                },
              },
            )
          }
        />
      </div>
    );
  }

  if (assignment.status === "closed" || expired || attempt?.status === "expired") {
    return (
      <div className="flex h-full min-h-0 items-center justify-center overflow-hidden p-2">
        <div className="flex max-h-full flex-col items-center gap-3 overflow-y-auto rounded-2xl border border-border/80 bg-white p-10 text-center shadow-xs">
          <p className="text-sm font-semibold text-foreground">Bài tập đã đóng</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            Hạn nộp hoặc thời gian làm bài đã kết thúc.
          </p>
          <NextButton onNext={onNext} hasNext={hasNext} />
        </div>
      </div>
    );
  }

  if (!assignment.questions.length) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center overflow-hidden p-8">
        <p className="text-center text-sm text-muted-foreground">
          Bài tập chưa có câu hỏi.
        </p>
      </div>
    );
  }

  const total = assignment.questions.length;
  // currentIndex có thể còn lớn hơn số câu sau khi đề được cập nhật ngắn lại.
  // Luôn render theo chỉ số đã kẹp để không truy cập phần tử undefined.
  const safeIndex = clampQuestionIndex(currentIndex, total);
  const question = assignment.questions[safeIndex];
  const selected = answers[question.id] ?? [];
  const answeredCount = countAnswered(answers);
  const unanswered = total - answeredCount;
  const remainingMin = getRemainingMinutes(expiresAt, now);

  const setSelected = (next: string[]) =>
    setAnswers((current) => ({ ...current, [question.id]: next }));

  const toggle = (optionId: string) => {
    if (question.allowMultiple) {
      const has = selected.includes(optionId);
      setSelected(has ? selected.filter((id) => id !== optionId) : [...selected, optionId]);
    } else {
      setSelected([optionId]);
    }
  };

  const submit = () => submitAttempt.mutate({ assignment, answers });

  const handleSubmit = () => {
    if (unanswered > 0) {
      setConfirmOpen(true);
      return;
    }
    submit();
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <QuestionView
        question={question}
        currentIndex={safeIndex}
        total={total}
        selected={selected}
        answeredCount={answeredCount}
        remainingMin={remainingMin}
        submitting={submitAttempt.isPending}
        submitError={getSubmitError(submitAttempt.isError, submitAttempt.error)}
        onToggleOption={toggle}
        onPrev={() => setCurrentIndex(Math.max(0, safeIndex - 1))}
        onNext={() => setCurrentIndex(Math.min(total - 1, safeIndex + 1))}
        onSubmit={handleSubmit}
      />

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Bạn còn {unanswered} câu chưa trả lời</DialogTitle>
            <DialogDescription>
              Những câu bỏ trống sẽ không được tính điểm. Bạn có thể quay lại hoàn thành hoặc nộp ngay.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              Tiếp tục làm bài
            </Button>
            <Button
              disabled={submitAttempt.isPending}
              onClick={() => {
                setConfirmOpen(false);
                submit();
              }}
            >
              Vẫn nộp bài
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
