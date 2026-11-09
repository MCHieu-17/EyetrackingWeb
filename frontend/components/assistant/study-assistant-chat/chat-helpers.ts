import { ApiError } from "@/lib/api/client";
import type { ChatCitation } from "@/lib/api/chat";

export type AssistantMode = "reader" | "quiz" | "review";

export type UiMessage = {
  id: string;
  role: "student" | "assistant";
  content: string;
  citations: ChatCitation[];
  pending?: boolean;
};

export type ChatSessionLike = {
  id: string;
  title: string;
  canContinue?: boolean;
  messageCount: number;
};

export type ChatMessageLike = {
  id: string;
  role: "student" | "assistant";
  content: string;
  citations?: ChatCitation[] | null;
};

const STATUS_LABEL: Record<string, string> = {
  routing: "Đang phân loại câu hỏi…",
  waiting: "Đang chờ xử lý và kiểm chứng…",
  retrieving: "Đang tìm trong tài liệu môn học…",
  generating: "Đang soạn câu trả lời…",
  verifying: "Đang kiểm tra trích dẫn…",
  retrying: "Đang sửa lại câu trả lời…",
};

export function newLocalId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function buildChatStorageKey({
  userId,
  courseId,
  assignmentId,
  attemptId,
  mode,
}: {
  userId?: string | null;
  courseId: string;
  assignmentId?: string | null;
  attemptId?: string | null;
  mode: AssistantMode;
}): string {
  return `study-chat:${userId ?? "anonymous"}:${courseId}:${assignmentId ?? "reader"}:${attemptId ?? "no-attempt"}:${mode === "reader" ? "reader" : mode}`;
}

/**
 * `undefined` = chưa chọn (tự mở phiên gần nhất), `null` = phiên mới chưa lưu.
 * Phiên đã chọn nhưng không thể tiếp tục cũng rơi về phiên gần nhất còn dùng được.
 */
export function resolveEffectiveSessionId(
  selectedSessionId: string | null | undefined,
  sessions: ChatSessionLike[],
): string | null {
  if (
    selectedSessionId === undefined ||
    sessions.some((session) => session.id === selectedSessionId && session.canContinue === false)
  ) {
    return sessions.find((session) => session.canContinue !== false)?.id ?? null;
  }
  return selectedSessionId;
}

export function toUiMessages(messages: ChatMessageLike[]): UiMessage[] {
  return messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
    citations: message.citations ?? [],
  }));
}

export function formatCitationLabel(
  index: number,
  citation: Pick<ChatCitation, "title">,
): string {
  return `[${index}] ${citation.title}`;
}

export function formatCitationLocation(
  citation: Pick<ChatCitation, "lessonTitle" | "slideIndex"> | null | undefined,
): string {
  const lessonTitle = citation?.lessonTitle || "Slide trong môn học";
  return citation?.slideIndex ? `${lessonTitle} · Slide ${citation.slideIndex}` : lessonTitle;
}

export function getStatusLabel(status: string | null): string | null {
  if (!status) return null;
  return STATUS_LABEL[status] ?? null;
}

export function getAssistantSubtitle(mode: AssistantMode): string {
  if (mode === "quiz") return "Gợi ý bài tập · không giải hộ";
  if (mode === "review") return "Chữa bài đã nộp · có đáp án";
  return "Hỏi đáp trong môn học";
}

export function getEmptyState(mode: AssistantMode): {
  description: string;
  suggestions: string[];
} {
  if (mode === "quiz") {
    return {
      description:
        "Mình sẽ gợi ý từng bước, không đưa đáp án cuối hay lời giải hoàn chỉnh.",
      suggestions: [
        "Cho mình gợi ý cho câu này",
        "Giải thích khái niệm liên quan",
        "Mình đang làm sai ở bước nào?",
      ],
    };
  }
  if (mode === "review") {
    return {
      description:
        "Hỏi về bài đã nộp. Mình có thể giải thích đáp án và chỉ ra lỗi sai.",
      suggestions: [
        "Giải thích đáp án đúng",
        "Vì sao mình sai câu này?",
        "Tóm tắt kiến thức liên quan",
      ],
    };
  }
  return {
    description:
      "Hỏi về khái niệm trong bài. Câu trả lời sẽ kèm trích dẫn slide liên quan.",
    suggestions: [
      "Tóm tắt nội dung chính của bài này",
      "Giải thích khái niệm quan trọng nhất",
      "Mình nên học phần nào trước?",
    ],
  };
}

export function isNearBottom(
  metrics: Pick<HTMLElement, "scrollHeight" | "scrollTop" | "clientHeight">,
  threshold = 80,
): boolean {
  return metrics.scrollHeight - metrics.scrollTop - metrics.clientHeight < threshold;
}

export function nextSessionAfterDelete(
  sessions: ChatSessionLike[],
  deletedSessionId: string,
): string | null {
  return sessions.find((session) => session.id !== deletedSessionId)?.id ?? null;
}

export function normalizeSessionTitle(value: string): string | null {
  const title = value.trim();
  return title ? title : null;
}

export function formatChatError(error: unknown): string {
  if (error instanceof ApiError && error.status === 429) {
    const seconds = error.retryAfter ?? 5;
    return `${error.message} Vui lòng thử lại sau ${seconds} giây.`;
  }
  return error instanceof Error
    ? error.message
    : "Trợ lý học tập tạm thời không phản hồi";
}
