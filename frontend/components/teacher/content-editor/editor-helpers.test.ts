import { describe, expect, it } from "vitest";

import { MAX_UPLOAD_BYTES } from "@/lib/api/client";
import {
  appendQuestion,
  countTree,
  errText,
  findSelectedItem,
  firstItemId,
  insertQuestionAt,
  moduleOfLesson,
  moveQuestionAt,
  patchQuizBaseline,
  quizFormFromAssignment,
  removeQuestionAt,
  serializeQuizForm,
  slideLimitsHint,
  toLocalInput,
  validateSlideFile,
  type QuizForm,
} from "@/components/teacher/content-editor/editor-helpers";
import type {
  LessonNode,
  ModuleNode,
  QuizAssignment,
  QuizQuestion,
} from "@/lib/types/domain";

function makeLesson(overrides: Partial<LessonNode> = {}): LessonNode {
  return {
    id: "lesson-1",
    title: "Bài 1",
    kind: "lesson",
    slides: 3,
    ...overrides,
  };
}

function makeModule(overrides: Partial<ModuleNode> = {}): ModuleNode {
  return {
    id: "module-1",
    title: "Chương 1",
    lessons: [makeLesson()],
    ...overrides,
  };
}

function makeQuestion(overrides: Partial<QuizQuestion> = {}): QuizQuestion {
  return {
    id: "q1",
    prompt: "Câu hỏi",
    options: [
      { id: "a", text: "A" },
      { id: "b", text: "B" },
    ],
    correctOptionIds: ["a"],
    allowMultiple: false,
    explanation: "",
    points: 1,
    ...overrides,
  };
}

function makeAssignment(overrides: Partial<QuizAssignment> = {}): QuizAssignment {
  return {
    id: "quiz-1",
    courseId: "course-1",
    courseTitle: "Khóa học",
    title: "Bài tập",
    instructions: "Hướng dẫn",
    dueAt: null,
    durationMinutes: 30,
    status: "draft",
    createdAt: "2026-01-01T00:00:00Z",
    questions: [makeQuestion()],
    ...overrides,
  };
}

describe("errText", () => {
  it("lấy message từ Error", () => {
    expect(errText(new Error("hỏng"))).toBe("hỏng");
  });

  it("trả về thông điệp mặc định cho giá trị lạ", () => {
    expect(errText("hỏng")).toBe("Lỗi không xác định");
    expect(errText(null)).toBe("Lỗi không xác định");
  });
});

describe("firstItemId", () => {
  it("trả về null cho cây rỗng", () => {
    expect(firstItemId([])).toBeNull();
    expect(firstItemId([makeModule({ lessons: [] })])).toBeNull();
  });

  it("trả về mục đầu tiên của chương đầu tiên", () => {
    const tree = [
      makeModule({ id: "m1", lessons: [makeLesson({ id: "l1" })] }),
      makeModule({ id: "m2", lessons: [makeLesson({ id: "l2" })] }),
    ];
    expect(firstItemId(tree)).toBe("l1");
  });
});

describe("findSelectedItem", () => {
  it("trả về null khi chưa chọn", () => {
    expect(findSelectedItem([makeModule()], null)).toBeNull();
  });

  it("tìm đúng bài và chương chứa nó", () => {
    const lesson = makeLesson({ id: "target" });
    const moduleNode = makeModule({ id: "m2", lessons: [makeLesson({ id: "other" }), lesson] });
    const tree = [makeModule({ id: "m1" }), moduleNode];

    expect(findSelectedItem(tree, "target")).toEqual({ lesson, module: moduleNode });
  });

  it("trả về null khi id không tồn tại", () => {
    expect(findSelectedItem([makeModule()], "missing")).toBeNull();
  });
});

describe("countTree", () => {
  it("đếm bài giảng, bài tập và slide", () => {
    const tree = [
      makeModule({
        lessons: [
          makeLesson({ id: "l1", kind: "lesson", slides: 4 }),
          makeLesson({ id: "q1", kind: "quiz", slides: 0 }),
        ],
      }),
      makeModule({
        id: "m2",
        lessons: [makeLesson({ id: "l2", kind: "lesson", slides: 2 })],
      }),
    ];

    expect(countTree(tree)).toEqual({
      totalLessons: 2,
      totalQuizzes: 1,
      totalSlides: 6,
      totalItems: 3,
    });
  });

  it("trả về 0 cho cây rỗng", () => {
    expect(countTree([])).toEqual({
      totalLessons: 0,
      totalQuizzes: 0,
      totalSlides: 0,
      totalItems: 0,
    });
  });
});

describe("moduleOfLesson", () => {
  it("trả về chương chứa bài", () => {
    const moduleNode = makeModule({ id: "m2", lessons: [makeLesson({ id: "l2" })] });
    expect(moduleOfLesson([makeModule({ id: "m1" }), moduleNode], "l2")).toBe(moduleNode);
  });

  it("trả về null khi không tìm thấy", () => {
    expect(moduleOfLesson([makeModule()], "missing")).toBeNull();
  });
});

describe("validateSlideFile", () => {
  it("chấp nhận các định dạng slide hợp lệ", () => {
    for (const name of ["a.pdf", "b.PPTX", "c.ppt", "d.odp"]) {
      expect(validateSlideFile({ name, size: 1024 })).toBeNull();
    }
  });

  it("từ chối định dạng khác", () => {
    expect(validateSlideFile({ name: "a.docx", size: 1024 })).toContain(
      "không phải tài liệu slide hợp lệ",
    );
  });

  it("từ chối file vượt quá giới hạn", () => {
    expect(validateSlideFile({ name: "a.pdf", size: MAX_UPLOAD_BYTES + 1 })).toContain(
      "vượt quá",
    );
  });
});

describe("toLocalInput", () => {
  it("trả về chuỗi rỗng cho giá trị thiếu hoặc không hợp lệ", () => {
    expect(toLocalInput(null)).toBe("");
    expect(toLocalInput(undefined)).toBe("");
    expect(toLocalInput("không phải ngày")).toBe("");
  });

  it("định dạng theo giờ địa phương", () => {
    const local = new Date(2026, 0, 2, 3, 4);
    expect(toLocalInput(local.toISOString())).toBe("2026-01-02T03:04");
  });
});

describe("slide limits runtime", () => {
  it("dùng giới hạn backend trước fallback hardcode", () => {
    const file = { name: "slide.pdf", size: MAX_UPLOAD_BYTES + 1 };
    expect(validateSlideFile(file)).toContain("vượt quá");
    expect(
      validateSlideFile(file, { maxUploadBytes: MAX_UPLOAD_BYTES * 2 }),
    ).toBeNull();
    expect(
      slideLimitsHint({ maxUploadBytes: 10 * 1024 * 1024, maxSlidePages: 20 }),
    ).toContain("tối đa 10MB");
    expect(
      slideLimitsHint({ maxUploadBytes: 10 * 1024 * 1024, maxSlidePages: 20 }),
    ).toContain("tối đa 20 trang");
  });
});

describe("serializeQuizForm", () => {
  it("ổn định với cùng nội dung", () => {
    const form: QuizForm = {
      instructions: "a",
      durationMinutes: 30,
      dueAt: "",
      allowRetry: false,
      allowChatbot: true,
      questions: [makeQuestion()],
    };

    expect(serializeQuizForm(form)).toBe(serializeQuizForm({ ...form }));
  });
});

describe("patchQuizBaseline", () => {
  it("chỉ đổi trường được lưu, giữ nguyên phần baseline cũ", () => {
    const baseline: QuizForm = {
      instructions: "Hướng dẫn cũ",
      durationMinutes: 30,
      dueAt: "",
      allowRetry: false,
      allowChatbot: true,
      questions: [makeQuestion()],
    };
    const current: QuizForm = {
      ...baseline,
      instructions: "Hướng dẫn mới chưa lưu",
      allowRetry: true,
    };

    const patched = patchQuizBaseline(
      serializeQuizForm(baseline),
      { allowRetry: current.allowRetry },
    );

    const parsed = JSON.parse(patched) as QuizForm;
    expect(parsed.allowRetry).toBe(true);
    expect(parsed.instructions).toBe("Hướng dẫn cũ");
  });
});

describe("quizFormFromAssignment", () => {
  it("chuyển assignment sang form và chuẩn hoá cờ boolean", () => {
    const assignment = makeAssignment({
      instructions: "Làm bài",
      durationMinutes: 45,
      dueAt: new Date(2026, 0, 2, 3, 4).toISOString(),
      allowRetry: undefined,
      allowChatbot: true,
    });

    expect(quizFormFromAssignment(assignment)).toEqual({
      instructions: "Làm bài",
      durationMinutes: 45,
      dueAt: "2026-01-02T03:04",
      allowRetry: false,
      allowChatbot: true,
      questions: assignment.questions,
    });
  });
});

describe("appendQuestion", () => {
  it("thêm vào cuối và chọn câu mới", () => {
    const first = makeQuestion({ id: "q1" });
    const second = makeQuestion({ id: "q2" });

    expect(appendQuestion([first], second)).toEqual({
      questions: [first, second],
      selectedIndex: 1,
    });
  });
});

describe("insertQuestionAt", () => {
  it("chèn ngay sau câu nguồn và chọn bản sao", () => {
    const first = makeQuestion({ id: "q1" });
    const second = makeQuestion({ id: "q2" });
    const copy = makeQuestion({ id: "copy" });

    expect(insertQuestionAt([first, second], 0, copy)).toEqual({
      questions: [first, copy, second],
      selectedIndex: 1,
    });
  });
});

describe("removeQuestionAt", () => {
  it("không xóa câu cuối cùng", () => {
    const only = makeQuestion();
    expect(removeQuestionAt([only], 0)).toEqual({
      questions: [only],
      selectedIndex: 0,
    });
  });

  it("xóa câu và kẹp vị trí đang chọn", () => {
    const questions = [
      makeQuestion({ id: "q1" }),
      makeQuestion({ id: "q2" }),
      makeQuestion({ id: "q3" }),
    ];

    expect(removeQuestionAt(questions, 2)).toEqual({
      questions: [questions[0], questions[1]],
      selectedIndex: 1,
    });
  });
});

describe("moveQuestionAt", () => {
  it("đổi chỗ với câu liền kề", () => {
    const questions = [
      makeQuestion({ id: "q1" }),
      makeQuestion({ id: "q2" }),
      makeQuestion({ id: "q3" }),
    ];

    expect(moveQuestionAt(questions, 1, -1)).toEqual({
      questions: [questions[1], questions[0], questions[2]],
      selectedIndex: 0,
    });
  });

  it("giữ nguyên khi vượt biên", () => {
    const questions = [makeQuestion({ id: "q1" }), makeQuestion({ id: "q2" })];
    expect(moveQuestionAt(questions, 0, -1)).toEqual({
      questions,
      selectedIndex: 0,
    });
    expect(moveQuestionAt(questions, 1, 1)).toEqual({
      questions,
      selectedIndex: 1,
    });
  });
});
