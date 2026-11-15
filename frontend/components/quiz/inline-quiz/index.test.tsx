import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import {
  useQuizAssignment,
  useQuizAttempt,
  useRetryQuizAttempt,
  useStartQuizAttempt,
  useSubmitQuizAttempt,
} from "@/hooks/use-quiz";
import type { QuizAssignment, QuizQuestion } from "@/lib/types/domain";
import { InlineQuiz } from "./index";

const assistantMocks = vi.hoisted(() => ({ setQuizContext: vi.fn() }));
const startMutate = vi.fn();

vi.mock("@/components/assistant/assistant-context", () => ({
  useAssistant: () => assistantMocks,
}));

vi.mock("@/hooks/use-quiz", () => ({
  useQuizAssignment: vi.fn(),
  useQuizAttempt: vi.fn(),
  useStartQuizAttempt: vi.fn(),
  useSubmitQuizAttempt: vi.fn(),
  useRetryQuizAttempt: vi.fn(),
}));

const mockUseQuizAssignment = vi.mocked(useQuizAssignment);
const mockUseQuizAttempt = vi.mocked(useQuizAttempt);
const mockUseStartQuizAttempt = vi.mocked(useStartQuizAttempt);
const mockUseSubmitQuizAttempt = vi.mocked(useSubmitQuizAttempt);
const mockUseRetryQuizAttempt = vi.mocked(useRetryQuizAttempt);

const assignments: Record<string, QuizAssignment> = {};

function question(id: string, optionText = "Option A"): QuizQuestion {
  return {
    id,
    prompt: `Prompt ${id}`,
    options: [
      { id: `${id}-a`, text: optionText },
      { id: `${id}-b`, text: "Option B" },
    ],
    correctOptionIds: [`${id}-a`],
    allowMultiple: false,
    explanation: "",
    points: 1,
  };
}

function assignment(quizId: string, lessonId: string, ids: string[]): QuizAssignment {
  return {
    id: quizId,
    courseId: "course",
    courseTitle: "Course",
    lessonId,
    lessonTitle: "Lesson",
    title: `Quiz ${quizId}`,
    instructions: "",
    dueAt: null,
    durationMinutes: 10,
    status: "published",
    createdAt: "2026-01-01T00:00:00Z",
    allowRetry: true,
    questions: ids.map((id) => question(id)),
  };
}

beforeEach(() => {
  for (const key of Object.keys(assignments)) delete assignments[key];
  vi.clearAllMocks();

  mockUseQuizAssignment.mockImplementation(
    (id: string) =>
      ({
        data: assignments[id] ?? null,
        isLoading: false,
        isError: false,
        isSuccess: Boolean(assignments[id]),
      }) as never,
  );
  mockUseQuizAttempt.mockReturnValue({
    data: null,
    isLoading: false,
    isError: false,
    isSuccess: true,
  } as never);
  mockUseStartQuizAttempt.mockImplementation(
    () =>
      ({
        mutate: startMutate,
        isPending: false,
        isError: false,
        error: null,
      }) as never,
  );
  mockUseSubmitQuizAttempt.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
  } as never);
  mockUseRetryQuizAttempt.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
  } as never);
});

afterEach(() => {
  cleanup();
});

describe("InlineQuiz", () => {
  it("resets current question and answers when quizId changes", () => {
    assignments.quizA = assignment("quizA", "lesson-a", ["a1", "a2"]);
    assignments.quizB = assignment("quizB", "lesson-b", ["a1", "a2"]);

    const { rerender } = render(<InlineQuiz quizId="quizA" />);

    const firstOption = screen.getByRole("radio", { name: /Option A/ });
    fireEvent.click(firstOption);
    expect(firstOption).toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: /Tiếp/ }));
    expect(screen.getByText("Câu 2 / 2")).toBeInTheDocument();

    rerender(<InlineQuiz quizId="quizB" />);

    expect(screen.getByText("Câu 1 / 2")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Option A/ })).not.toBeChecked();
  });

  it("renders safely when the updated quiz has fewer questions", () => {
    assignments.quizA = assignment("quizA", "lesson-a", ["a1", "a2", "a3"]);
    const { rerender } = render(<InlineQuiz quizId="quizA" />);

    fireEvent.click(screen.getByRole("button", { name: /Tiếp/ }));
    fireEvent.click(screen.getByRole("button", { name: /Tiếp/ }));
    expect(screen.getByText("Câu 3 / 3")).toBeInTheDocument();

    assignments.quizA = assignment("quizA", "lesson-a", ["a1"]);
    rerender(<InlineQuiz quizId="quizA" />);

    expect(screen.getByText("Câu 1 / 1")).toBeInTheDocument();
  });

  it("giữ thẻ câu hỏi cố định và chỉ cuộn danh sách đáp án", () => {
    assignments.quizA = assignment("quizA", "lesson-a", ["a1"]);
    render(<InlineQuiz quizId="quizA" />);

    const card = document.querySelector('[data-aoi="quiz-question"]');
    expect(card?.className).toContain("h-full");
    expect(card?.className).toContain("min-h-0");

    const options = card?.querySelector('[data-aoi="quiz-options"]');
    expect(options?.className).toContain("overflow-y-auto");
    expect(options?.className).toContain("min-h-0");
    expect(options?.className).toContain("flex-1");
  });

  it("does not retry a failed auto-start on every render", () => {
    assignments.quizA = assignment("quizA", "lesson-a", ["a1"]);
    const { rerender } = render(<InlineQuiz quizId="quizA" />);

    expect(startMutate).toHaveBeenCalledTimes(1);
    expect(startMutate).toHaveBeenCalledWith({ lessonId: "lesson-a" });

    // Hook trả object mutation mới mỗi render: effect sẽ chạy lại, nhưng guard
    // theo quiz/lesson phải giữ request chỉ được gửi một lần dù lần đầu lỗi.
    rerender(<InlineQuiz quizId="quizA" />);
    rerender(<InlineQuiz quizId="quizA" />);

    expect(startMutate).toHaveBeenCalledTimes(1);
  });
});
