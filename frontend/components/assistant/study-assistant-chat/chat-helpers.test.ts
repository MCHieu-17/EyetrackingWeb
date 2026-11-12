import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/client";
import {
  buildChatStorageKey,
  formatChatError,
  formatCitationLabel,
  formatCitationLocation,
  getAssistantSubtitle,
  getEmptyState,
  getStatusLabel,
  isNearBottom,
  newLocalId,
  nextSessionAfterDelete,
  normalizeSessionTitle,
  resolveEffectiveSessionId,
  toUiMessages,
  type ChatSessionLike,
} from "./chat-helpers";

function session(
  id: string,
  overrides: Partial<ChatSessionLike> = {},
): ChatSessionLike {
  return { id, title: `Phiên ${id}`, messageCount: 1, ...overrides };
}

describe("newLocalId", () => {
  it("trả về id không rỗng và khác nhau giữa hai lần gọi", () => {
    const first = newLocalId();
    const second = newLocalId();

    expect(first).not.toBe("");
    expect(second).not.toBe("");
    expect(first).not.toBe(second);
  });
});

describe("buildChatStorageKey", () => {
  it("ghép key đầy đủ theo user, course, assignment, attempt và mode", () => {
    expect(
      buildChatStorageKey({
        userId: "u1",
        courseId: "c1",
        assignmentId: "a1",
        attemptId: "t1",
        mode: "quiz",
      }),
    ).toBe("study-chat:u1:c1:a1:t1:quiz");
  });

  it("dùng giá trị mặc định khi thiếu user, assignment và attempt", () => {
    expect(
      buildChatStorageKey({
        courseId: "c1",
        mode: "reader",
      }),
    ).toBe("study-chat:anonymous:c1:reader:no-attempt:reader");
  });

  it("giữ mode review", () => {
    expect(
      buildChatStorageKey({
        userId: "u1",
        courseId: "c1",
        mode: "review",
      }),
    ).toBe("study-chat:u1:c1:reader:no-attempt:review");
  });
});

describe("resolveEffectiveSessionId", () => {
  it("chọn phiên gần nhất có thể tiếp tục khi chưa chọn", () => {
    const sessions = [
      session("old", { canContinue: false }),
      session("latest"),
      session("older"),
    ];

    expect(resolveEffectiveSessionId(undefined, sessions)).toBe("latest");
  });

  it("giữ nguyên phiên mới (null)", () => {
    expect(resolveEffectiveSessionId(null, [session("s1")])).toBeNull();
  });

  it("giữ phiên đang chọn nếu còn tiếp tục được", () => {
    expect(resolveEffectiveSessionId("s2", [session("s1"), session("s2")])).toBe(
      "s2",
    );
  });

  it("rơi về phiên gần nhất khi phiên đang chọn không thể tiếp tục", () => {
    const sessions = [
      session("s1"),
      session("s2", { canContinue: false }),
      session("s3"),
    ];

    expect(resolveEffectiveSessionId("s2", sessions)).toBe("s1");
  });

  it("trả về null khi không có phiên nào", () => {
    expect(resolveEffectiveSessionId(undefined, [])).toBeNull();
  });
});

describe("toUiMessages", () => {
  it("map message từ server và chuẩn hoá citations null", () => {
    expect(
      toUiMessages([
        {
          id: "m1",
          role: "student",
          content: "Câu hỏi",
          citations: null,
        },
        {
          id: "m2",
          role: "assistant",
          content: "Trả lời",
          citations: [
            {
              documentId: "d1",
              title: "Slide 1",
              location: "trang 1",
            },
          ],
        },
      ]),
    ).toEqual([
      {
        id: "m1",
        role: "student",
        content: "Câu hỏi",
        citations: [],
      },
      {
        id: "m2",
        role: "assistant",
        content: "Trả lời",
        citations: [
          {
            documentId: "d1",
            title: "Slide 1",
            location: "trang 1",
          },
        ],
      },
    ]);
  });
});

describe("formatCitationLabel", () => {
  it("thêm số thứ tự trước tiêu đề", () => {
    expect(formatCitationLabel(2, { title: "Bài giảng" })).toBe("[2] Bài giảng");
  });
});

describe("formatCitationLocation", () => {
  it("ghép lesson title và số slide", () => {
    expect(
      formatCitationLocation({ lessonTitle: "Bài 1", slideIndex: 3 }),
    ).toBe("Bài 1 · Slide 3");
  });

  it("dùng nhãn mặc định khi thiếu lesson title", () => {
    expect(formatCitationLocation({ slideIndex: 3 })).toBe(
      "Slide trong môn học · Slide 3",
    );
  });

  it("bỏ phần slide khi không có số slide", () => {
    expect(formatCitationLocation({ lessonTitle: "Bài 1" })).toBe("Bài 1");
  });

  it("xử lý citation null", () => {
    expect(formatCitationLocation(null)).toBe("Slide trong môn học");
  });
});

describe("getStatusLabel", () => {
  it("trả về nhãn cho các trạng thái của pipeline mới", () => {
    expect(getStatusLabel("rewriting")).toBe("Đang hiểu câu hỏi…");
    expect(getStatusLabel("retrieving")).toBe(
      "Đang tìm trong tài liệu môn học…",
    );
    expect(getStatusLabel("generating")).toBe("Đang soạn câu trả lời…");
    expect(getStatusLabel("checking_citations")).toBe(
      "Đang kiểm tra trích dẫn…",
    );
  });

  it("vẫn trả về nhãn cho trạng thái cũ làm fallback", () => {
    expect(getStatusLabel("routing")).toBe("Đang hiểu câu hỏi…");
    expect(getStatusLabel("waiting")).toBe("Đang chờ xử lý…");
    expect(getStatusLabel("verifying")).toBe("Đang kiểm tra trích dẫn…");
    expect(getStatusLabel("retrying")).toBe("Đang sửa lại câu trả lời…");
  });

  it("trả về null khi không có trạng thái", () => {
    expect(getStatusLabel(null)).toBeNull();
  });

  it("trả về null cho trạng thái lạ", () => {
    expect(getStatusLabel("unknown")).toBeNull();
  });
});

describe("getAssistantSubtitle", () => {
  it("trả về phụ đề theo từng mode", () => {
    expect(getAssistantSubtitle("reader")).toBe("Hỏi đáp trong môn học");
    expect(getAssistantSubtitle("quiz")).toBe(
      "Hỗ trợ bài tập · gợi ý từng bước",
    );
    expect(getAssistantSubtitle("review")).toBe(
      "Chữa bài đã nộp · giải thích đáp án",
    );
  });
});

describe("getEmptyState", () => {
  it("trả về nội dung và gợi ý cho reader", () => {
    const state = getEmptyState("reader");

    expect(state.description).toContain("trích dẫn từ tài liệu môn học");
    expect(state.suggestions).toHaveLength(3);
    expect(state.suggestions[0]).toBe("Tóm tắt nội dung chính của bài này");
  });

  it("trả về nội dung và gợi ý cho quiz", () => {
    const state = getEmptyState("quiz");

    expect(state.description).toContain("gợi ý từng bước");
    expect(state.suggestions).toHaveLength(3);
    expect(state.suggestions[0]).toBe("Cho mình gợi ý cho câu này");
  });

  it("trả về nội dung và gợi ý cho review", () => {
    const state = getEmptyState("review");

    expect(state.description).toContain("bài đã nộp");
    expect(state.suggestions).toHaveLength(3);
    expect(state.suggestions[0]).toBe("Giải thích đáp án đúng");
  });
});

describe("isNearBottom", () => {
  it("coi là gần đáy khi còn dưới 80px", () => {
    expect(
      isNearBottom({ scrollHeight: 1000, scrollTop: 880, clientHeight: 100 }),
    ).toBe(true);
  });

  it("coi là không gần đáy khi còn từ 80px trở lên", () => {
    expect(
      isNearBottom({ scrollHeight: 1000, scrollTop: 800, clientHeight: 100 }),
    ).toBe(false);
  });

  it("hỗ trợ ngưỡng tuỳ chỉnh", () => {
    expect(
      isNearBottom(
        { scrollHeight: 1000, scrollTop: 850, clientHeight: 100 },
        40,
      ),
    ).toBe(false);
  });
});

describe("nextSessionAfterDelete", () => {
  it("trả về phiên đầu tiên khác phiên bị xoá", () => {
    expect(
      nextSessionAfterDelete([session("s1"), session("s2")], "s1"),
    ).toBe("s2");
  });

  it("trả về null khi chỉ còn phiên bị xoá", () => {
    expect(nextSessionAfterDelete([session("s1")], "s1")).toBeNull();
  });
});

describe("normalizeSessionTitle", () => {
  it("trim tiêu đề", () => {
    expect(normalizeSessionTitle("  Phiên mới  ")).toBe("Phiên mới");
  });

  it("trả về null khi tiêu đề rỗng", () => {
    expect(normalizeSessionTitle("   ")).toBeNull();
  });
});

describe("formatChatError", () => {
  it("thêm thời gian chờ khi bị giới hạn tần suất", () => {
    expect(formatChatError(new ApiError(429, "Quá nhiều yêu cầu", 12))).toBe(
      "Quá nhiều yêu cầu Vui lòng thử lại sau 12 giây.",
    );
  });

  it("mặc định chờ 5 giây khi không có Retry-After", () => {
    expect(formatChatError(new ApiError(429, "Quá nhiều yêu cầu"))).toBe(
      "Quá nhiều yêu cầu Vui lòng thử lại sau 5 giây.",
    );
  });

  it("dùng message của Error thường", () => {
    expect(formatChatError(new Error("Mất kết nối"))).toBe("Mất kết nối");
  });

  it("dùng thông báo mặc định cho lỗi không xác định", () => {
    expect(formatChatError("boom")).toBe(
      "Trợ lý học tập tạm thời không phản hồi",
    );
  });
});
