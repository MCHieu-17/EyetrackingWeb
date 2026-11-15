import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/client";
import type { QuizQuestion } from "@/lib/types/domain";
import {
  clampQuestionIndex,
  countAnswered,
  countCorrectAnswers,
  getOptionLetter,
  getPercentage,
  getRemainingMinutes,
  getRetryError,
  getSubmitError,
  isAnswerCorrect,
  shouldShowReview,
} from "./quiz-helpers";

const questions: QuizQuestion[] = [
  {
    id: "q1",
    prompt: "Q1",
    options: [],
    correctOptionIds: ["a"],
    allowMultiple: false,
    explanation: "",
    points: 1,
  },
  {
    id: "q2",
    prompt: "Q2",
    options: [],
    correctOptionIds: ["b", "c"],
    allowMultiple: true,
    explanation: "",
    points: 1,
  },
];

describe("getPercentage", () => {
  it("rounds the percentage", () => {
    expect(getPercentage(7, 10)).toBe(70);
    expect(getPercentage(2, 3)).toBe(67);
  });

  it("returns zero when max score is zero", () => {
    expect(getPercentage(5, 0)).toBe(0);
  });
});

describe("isAnswerCorrect", () => {
  it("requires an exact match", () => {
    expect(isAnswerCorrect(["a"], ["a"])).toBe(true);
    expect(isAnswerCorrect(["a", "b"], ["a"])).toBe(false);
    expect(isAnswerCorrect([], ["a"])).toBe(false);
    expect(isAnswerCorrect(["b", "c"], ["c", "b"])).toBe(true);
  });
});

describe("countCorrectAnswers", () => {
  it("counts exact matches", () => {
    expect(countCorrectAnswers(questions, { q1: ["a"], q2: ["b", "c"] })).toBe(2);
    expect(countCorrectAnswers(questions, { q1: ["a"], q2: ["b"] })).toBe(1);
    expect(countCorrectAnswers(questions, {})).toBe(0);
  });
});

describe("countAnswered", () => {
  it("counts non-empty answers", () => {
    expect(countAnswered({ q1: ["a"], q2: [], q3: ["b"] })).toBe(2);
  });
});

describe("getRemainingMinutes", () => {
  it("returns null without an expiry", () => {
    expect(getRemainingMinutes(undefined, 0)).toBeNull();
  });

  it("rounds up and clamps at zero", () => {
    const now = new Date("2026-11-09T00:00:00Z").getTime();
    expect(getRemainingMinutes("2026-11-09T00:01:01Z", now)).toBe(2);
    expect(getRemainingMinutes("2026-11-08T23:00:00Z", now)).toBe(0);
  });
});

describe("error helpers", () => {
  it("returns undefined when there is no error", () => {
    expect(getRetryError(false, null)).toBeUndefined();
    expect(getSubmitError(false, null)).toBeUndefined();
  });

  it("uses the ApiError message", () => {
    const error = new ApiError(400, "boom");
    expect(getRetryError(true, error)).toBe("boom");
    expect(getSubmitError(true, error)).toBe("boom");
  });

  it("falls back for unknown errors", () => {
    expect(getRetryError(true, new Error("x"))).toBe(
      "Chưa thể làm lại bài. Vui lòng thử lại.",
    );
    expect(getSubmitError(true, new Error("x"))).toBe(
      "Chưa thể lưu bài làm. Vui lòng thử lại.",
    );
  });
});

describe("getOptionLetter", () => {
  it("maps an index to a letter", () => {
    expect(getOptionLetter(0)).toBe("A");
    expect(getOptionLetter(25)).toBe("Z");
  });
});

describe("clampQuestionIndex", () => {
  it("keeps valid indexes unchanged", () => {
    expect(clampQuestionIndex(0, 3)).toBe(0);
    expect(clampQuestionIndex(2, 3)).toBe(2);
  });

  it("clamps negative and out-of-range indexes", () => {
    expect(clampQuestionIndex(-1, 3)).toBe(0);
    expect(clampQuestionIndex(9, 3)).toBe(2);
  });

  it("falls back to zero for empty or invalid input", () => {
    expect(clampQuestionIndex(5, 0)).toBe(0);
    expect(clampQuestionIndex(Number.NaN, 3)).toBe(0);
  });
});

describe("shouldShowReview", () => {
  it("only shows review for submitted attempts", () => {
    expect(shouldShowReview(null)).toBe(false);
    expect(shouldShowReview(undefined)).toBe(false);
    expect(shouldShowReview({ status: "in_progress" })).toBe(false);
    expect(shouldShowReview({ status: "expired" })).toBe(false);
    expect(shouldShowReview({ status: "submitted" })).toBe(true);
  });
});
