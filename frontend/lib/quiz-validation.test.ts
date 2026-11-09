import { describe, expect, it } from "vitest";

import {
  draftPayload,
  isQuestionComplete,
  questionIssues,
  trimQuestion,
} from "@/lib/quiz-validation";
import type { QuizQuestion } from "@/lib/types/domain";

function makeQuestion(overrides: Partial<QuizQuestion> = {}): QuizQuestion {
  return {
    id: "q1",
    prompt: "1 + 1 bằng mấy?",
    options: [
      { id: "a", text: "2" },
      { id: "b", text: "3" },
    ],
    correctOptionIds: ["a"],
    allowMultiple: false,
    explanation: "1 + 1 = 2",
    points: 1,
    ...overrides,
  };
}

describe("questionIssues", () => {
  it("trả về rỗng cho câu hợp lệ", () => {
    expect(questionIssues(makeQuestion())).toEqual([]);
    expect(isQuestionComplete(makeQuestion())).toBe(true);
  });

  it("báo lỗi khi prompt rỗng hoặc chỉ có khoảng trắng", () => {
    expect(questionIssues(makeQuestion({ prompt: "" }))).toContain("Chưa có nội dung câu hỏi");
    expect(questionIssues(makeQuestion({ prompt: "   " }))).toContain("Chưa có nội dung câu hỏi");
  });

  it("báo lỗi khi có ít hơn 2 lựa chọn", () => {
    expect(questionIssues(makeQuestion({ options: [{ id: "a", text: "2" }] }))).toContain(
      "Cần ít nhất 2 lựa chọn",
    );
  });

  it("báo lỗi khi có lựa chọn để trống", () => {
    const question = makeQuestion({
      options: [
        { id: "a", text: "2" },
        { id: "b", text: "  " },
      ],
    });

    expect(questionIssues(question)).toContain("Có lựa chọn để trống");
  });

  it("báo lỗi khi chưa chọn đáp án đúng", () => {
    expect(questionIssues(makeQuestion({ correctOptionIds: [] }))).toContain(
      "Chưa chọn đáp án đúng",
    );
  });

  it("chặn nhiều đáp án khi allowMultiple = false", () => {
    const question = makeQuestion({ correctOptionIds: ["a", "b"], allowMultiple: false });

    expect(questionIssues(question)).toContain("Câu một đáp án chỉ được có một đáp án đúng");
    expect(isQuestionComplete(question)).toBe(false);
  });

  it("cho phép nhiều đáp án khi allowMultiple = true", () => {
    const question = makeQuestion({ correctOptionIds: ["a", "b"], allowMultiple: true });

    expect(questionIssues(question)).toEqual([]);
    expect(isQuestionComplete(question)).toBe(true);
  });

  it("gom nhiều lỗi cùng lúc", () => {
    const question = makeQuestion({
      prompt: "",
      options: [{ id: "a", text: "2" }],
      correctOptionIds: [],
    });

    expect(questionIssues(question)).toEqual([
      "Chưa có nội dung câu hỏi",
      "Cần ít nhất 2 lựa chọn",
      "Chưa chọn đáp án đúng",
    ]);
  });
});

describe("trimQuestion", () => {
  it("cắt khoảng trắng ở prompt, explanation và lựa chọn", () => {
    const question = makeQuestion({
      prompt: "  Câu hỏi  ",
      explanation: "  Giải thích  ",
      options: [
        { id: "a", text: "  2  " },
        { id: "b", text: "  3  " },
      ],
    });

    expect(trimQuestion(question)).toEqual({
      ...question,
      prompt: "Câu hỏi",
      explanation: "Giải thích",
      options: [
        { id: "a", text: "2" },
        { id: "b", text: "3" },
      ],
    });
  });

  it("giữ nguyên các trường khác và không sửa object gốc", () => {
    const question = makeQuestion({ prompt: "  Câu hỏi  " });
    const trimmed = trimQuestion(question);

    expect(trimmed.id).toBe("q1");
    expect(trimmed.points).toBe(1);
    expect(trimmed.correctOptionIds).toEqual(["a"]);
    expect(trimmed.allowMultiple).toBe(false);
    expect(question.prompt).toBe("  Câu hỏi  ");
  });
});

describe("draftPayload", () => {
  it("chỉ gửi câu hợp lệ và đếm số câu chưa lưu được", () => {
    const valid = makeQuestion({ id: "ok", prompt: "  Hợp lệ  " });
    const invalid = makeQuestion({ id: "draft", prompt: "" });

    const payload = draftPayload([valid, invalid]);

    expect(payload.questions).toHaveLength(1);
    expect(payload.questions[0].id).toBe("ok");
    expect(payload.questions[0].prompt).toBe("Hợp lệ");
    expect(payload.unsavedCount).toBe(1);
  });

  it("trả về rỗng khi không có câu nào", () => {
    expect(draftPayload([])).toEqual({ questions: [], unsavedCount: 0 });
  });

  it("đếm toàn bộ khi mọi câu đều chưa hợp lệ", () => {
    const payload = draftPayload([
      makeQuestion({ id: "a", prompt: "" }),
      makeQuestion({ id: "b", correctOptionIds: [] }),
    ]);

    expect(payload.questions).toEqual([]);
    expect(payload.unsavedCount).toBe(2);
  });
});
