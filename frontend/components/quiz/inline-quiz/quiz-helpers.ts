import { ApiError } from "@/lib/api/client";
import type { QuizQuestion } from "@/lib/types/domain";

export function getPercentage(score: number, maxScore: number): number {
  return maxScore ? Math.round((score / maxScore) * 100) : 0;
}

export function isAnswerCorrect(
  selected: readonly string[],
  correctOptionIds: readonly string[],
): boolean {
  const correct = new Set(correctOptionIds);
  return selected.length === correct.size && selected.every((id) => correct.has(id));
}

export function countCorrectAnswers(
  questions: readonly QuizQuestion[],
  answers: Record<string, string[]>,
): number {
  return questions.filter((question) => {
    const selected = new Set(answers[question.id] ?? []);
    const correct = new Set(question.correctOptionIds);
    return selected.size === correct.size && [...selected].every((id) => correct.has(id));
  }).length;
}

export function countAnswered(answers: Record<string, string[]>): number {
  return Object.values(answers).filter((value) => value.length > 0).length;
}

export function getRemainingMinutes(
  expiresAt: string | undefined,
  now: number,
): number | null {
  if (expiresAt == null) return null;
  return Math.max(0, Math.ceil((new Date(expiresAt).getTime() - now) / 60000));
}

export function getRetryError(
  isError: boolean,
  error: unknown,
): string | undefined {
  if (!isError) return undefined;
  return error instanceof ApiError
    ? error.message
    : "Chưa thể làm lại bài. Vui lòng thử lại.";
}

/** Chỉ màn hình review mới hiển thị khi lượt làm đã nộp. */
export function shouldShowReview(
  attempt: { status?: string } | null | undefined,
): boolean {
  return attempt?.status === "submitted";
}

export function getSubmitError(
  isError: boolean,
  error: unknown,
): string | undefined {
  if (!isError) return undefined;
  return error instanceof ApiError
    ? error.message
    : "Chưa thể lưu bài làm. Vui lòng thử lại.";
}

export function getOptionLetter(index: number): string {
  return String.fromCharCode(65 + index);
}
