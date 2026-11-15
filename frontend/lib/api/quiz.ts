import { apiFetch } from "@/lib/api/client";
import type {
  QuizAssignment,
  QuizAssignmentStatus,
  QuizAttempt,
  QuizQuestion,
} from "@/lib/types/domain";

export interface QuizAssignmentPatch {
  title?: string;
  instructions?: string;
  dueAt?: string | null;
  durationMinutes?: number;
  status?: QuizAssignmentStatus;
  allowChatbot?: boolean;
  allowRetry?: boolean;
  questions?: QuizQuestion[];
}

export async function getQuizAssignment(id: string): Promise<QuizAssignment | null> {
  return apiFetch<QuizAssignment>(`/api/lessons/${id}/quiz`);
}

export async function getQuizAttempt(lessonId: string): Promise<QuizAttempt | null> {
  const attempts = await apiFetch<QuizAttempt[]>(`/api/lessons/${lessonId}/attempts`);
  return attempts[0] ?? null;
}

export async function startQuizAttempt(lessonId: string): Promise<QuizAttempt> {
  return apiFetch<QuizAttempt>(`/api/lessons/${lessonId}/attempts`, {
    method: "POST",
  });
}

export async function submitQuizAttempt(
  assignment: QuizAssignment,
  answers: Record<string, string[]>,
): Promise<QuizAttempt> {
  if (!assignment.lessonId) throw new Error("Bài tập thiếu lessonId");
  const attempt = await startQuizAttempt(assignment.lessonId);
  return apiFetch<QuizAttempt>(`/api/attempts/${attempt.id}/submit`, {
    method: "POST",
    body: { answers },
  });
}

export async function updateQuizAssignment(
  id: string,
  patch: QuizAssignmentPatch,
): Promise<QuizAssignment> {
  return apiFetch<QuizAssignment>(`/api/teacher/lessons/${id}/quiz`, {
    method: "PATCH",
    body: patch,
  });
}

/** Tạo lượt làm mới; lượt cũ được giữ trong lịch sử. */
export async function retryQuizAttempt(attemptId: string): Promise<QuizAttempt> {
  return apiFetch<QuizAttempt>(`/api/attempts/${attemptId}/retry`, {
    method: "POST",
  });
}
