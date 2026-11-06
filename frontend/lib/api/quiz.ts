import { apiFetch } from "@/lib/api/client";
import { isDemoMode } from "@/lib/demo";
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

async function demoStore() {
  return import("@/lib/quiz-store");
}

export async function getQuizAssignment(id: string): Promise<QuizAssignment | null> {
  if (isDemoMode()) return (await demoStore()).getQuizAssignment(id);
  return apiFetch<QuizAssignment>(`/api/quiz-specs/${id}`);
}

export async function getQuizAttempt(lessonId: string): Promise<QuizAttempt | null> {
  if (isDemoMode()) return (await demoStore()).getQuizAttempt(lessonId);
  const attempts = await apiFetch<QuizAttempt[]>(`/api/lessons/${lessonId}/attempts`);
  return attempts[0] ?? null;
}

export async function startQuizAttempt(lessonId: string): Promise<QuizAttempt> {
  if (isDemoMode()) {
    return {
      id: `demo-attempt-${lessonId}`,
      assignmentId: lessonId,
      status: "in_progress",
      answers: {},
      submittedAt: new Date().toISOString(),
      score: 0,
      maxScore: 0,
    };
  }
  return apiFetch<QuizAttempt>(`/api/lessons/${lessonId}/attempts`, {
    method: "POST",
  });
}

export async function submitQuizAttempt(
  assignment: QuizAssignment,
  answers: Record<string, string[]>,
): Promise<QuizAttempt> {
  if (isDemoMode()) return (await demoStore()).submitQuizAttempt(assignment, answers);
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
  if (isDemoMode()) return (await demoStore()).updateQuizAssignment(id, patch);
  return apiFetch<QuizAssignment>(`/api/teacher/quiz-specs/${id}`, {
    method: "PATCH",
    body: patch,
  });
}

/** Tạo lượt làm mới; lượt cũ được giữ trong lịch sử. */
export async function retryQuizAttempt(attemptId: string): Promise<QuizAttempt> {
  if (isDemoMode()) {
    return {
      id: `demo-retry-${attemptId}`,
      assignmentId: attemptId,
      status: "in_progress",
      answers: {},
      submittedAt: new Date().toISOString(),
      score: 0,
      maxScore: 0,
    };
  }
  return apiFetch<QuizAttempt>(`/api/attempts/${attemptId}/retry`, {
    method: "POST",
  });
}
