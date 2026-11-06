"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getQuizAssignment,
  getQuizAttempt,
  retryQuizAttempt,
  startQuizAttempt,
  submitQuizAttempt,
  updateQuizAssignment,
  type QuizAssignmentPatch,
} from "@/lib/api/quiz";
import type { QuizAssignment } from "@/lib/types/domain";

export function useQuizAssignment(id: string) {
  return useQuery({
    queryKey: ["quiz", "assignment", id],
    queryFn: () => getQuizAssignment(id),
    enabled: Boolean(id),
  });
}

export function useQuizAttempt(lessonId: string) {
  return useQuery({
    queryKey: ["quiz", "attempt", lessonId],
    queryFn: () => getQuizAttempt(lessonId),
    enabled: Boolean(lessonId),
  });
}

export function useStartQuizAttempt() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ lessonId }: { lessonId: string }) => startQuizAttempt(lessonId),
    onSuccess: async (attempt, variables) => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ["quiz", "attempt", variables.lessonId] }),
        client.invalidateQueries({ queryKey: ["quiz", "assignment", attempt.assignmentId] }),
      ]);
    },
  });
}

export function useSubmitQuizAttempt() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      assignment,
      answers,
    }: {
      assignment: QuizAssignment;
      answers: Record<string, string[]>;
    }) => submitQuizAttempt(assignment, answers),
    onSuccess: async (attempt, variables) => {
      await Promise.all([
        client.invalidateQueries({
          queryKey: ["quiz", "attempt", variables.assignment.lessonId],
        }),
        client.invalidateQueries({
          queryKey: ["quiz", "assignment", variables.assignment.id],
        }),
      ]);
    },
  });
}

export function useUpdateQuizAssignment() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: QuizAssignmentPatch }) =>
      updateQuizAssignment(id, patch),
    onSuccess: (assignment) => {
      client.invalidateQueries({ queryKey: ["quiz", "assignment", assignment.id] });
    },
  });
}

/** Tạo lượt làm mới; lượt cũ vẫn còn trong lịch sử. */
export function useRetryQuizAttempt() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ attemptId }: { attemptId: string; lessonId: string }) =>
      retryQuizAttempt(attemptId),
    onSuccess: async (attempt, variables) => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ["quiz", "attempt", variables.lessonId] }),
        client.invalidateQueries({ queryKey: ["quiz", "assignment", attempt.assignmentId] }),
      ]);
    },
  });
}
