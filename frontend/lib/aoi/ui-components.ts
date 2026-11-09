import type { AoiUiComponent } from "@/lib/api/aoi";

export const UI_SCHEMA_VERSION = "reader-v1";

interface UiComponentMeta extends AoiUiComponent {
  icon: string;
  group: "Chính" | "Trợ lý" | "Bài tập";
}

/**
 * Danh sách phần giao diện có `data-aoi` trong ReaderFrame.
 * Giữ đồng bộ với `frontend/components/reader/reader-frame.tsx` và
 * `frontend/components/assistant/study-assistant-chat.tsx`.
 */
export const UI_COMPONENTS: UiComponentMeta[] = [
  { code: "header", name: "Thanh trên", icon: "ri-layout-top-line", group: "Chính" },
  { code: "chat-open-button", name: "Nút mở trợ lý", icon: "ri-sparkling-2-line", group: "Chính" },
  { code: "outline", name: "Mục lục", icon: "ri-list-check-2", group: "Chính" },
  { code: "lesson-content", name: "Khung bài học", icon: "ri-layout-row-line", group: "Chính" },
  { code: "slide", name: "Slide", icon: "ri-image-line", group: "Chính" },
  { code: "lesson-nav", name: "Nút chuyển trang", icon: "ri-arrow-left-right-line", group: "Chính" },
  { code: "chatbot", name: "Trợ lý học tập", icon: "ri-robot-2-line", group: "Trợ lý" },
  { code: "chat-header", name: "Tiêu đề trợ lý", icon: "ri-chat-3-line", group: "Trợ lý" },
  { code: "chat-messages", name: "Nội dung trò chuyện", icon: "ri-chat-history-line", group: "Trợ lý" },
  { code: "chat-user-message", name: "Tin nhắn của em", icon: "ri-user-line", group: "Trợ lý" },
  { code: "chat-ai-message", name: "Trả lời của trợ lý", icon: "ri-sparkling-line", group: "Trợ lý" },
  { code: "chat-input", name: "Ô nhập câu hỏi", icon: "ri-edit-line", group: "Trợ lý" },
  { code: "chat-send", name: "Nút gửi", icon: "ri-send-plane-2-line", group: "Trợ lý" },
  { code: "quiz", name: "Bài tập", icon: "ri-file-text-line", group: "Bài tập" },
  { code: "quiz-question", name: "Câu hỏi", icon: "ri-question-line", group: "Bài tập" },
  { code: "quiz-options", name: "Các đáp án", icon: "ri-list-radio", group: "Bài tập" },
  { code: "quiz-submit", name: "Nút nộp bài", icon: "ri-checkbox-circle-line", group: "Bài tập" },
];

const UI_COMPONENT_BY_CODE = new Map(
  UI_COMPONENTS.map((component) => [component.code, component]),
);

/**
 * Anchor ổn định cho vùng tự do trên giao diện. Chỉ các phần tử này được dùng
 * làm gốc toạ độ tương đối để vùng không nhảy khi layout đổi.
 */
export const STABLE_UI_ANCHORS = new Set([
  "reader-root",
  "header",
  "outline",
  "lesson-content",
  "slide",
  "lesson-nav",
  "chatbot",
  "chat-header",
  "chat-messages",
  "chat-input",
  "quiz",
  "quiz-question",
  "quiz-options",
]);

export function friendlyUiName(code: string): string {
  const known = UI_COMPONENT_BY_CODE.get(code);
  if (known) return known.name;
  return code
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function uiIcon(code: string): string {
  return UI_COMPONENT_BY_CODE.get(code)?.icon ?? "ri-layout-masonry-line";
}
