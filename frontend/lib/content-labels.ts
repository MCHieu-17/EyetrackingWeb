import type { QuizAssignmentStatus } from "@/lib/types/domain";

/** Nhãn loại mục nội dung dùng chung cho mục lục và trình soạn. */
export const KIND_LABEL: Record<string, string> = {
  lesson: "Bài giảng",
  quiz: "Bài tập trắc nghiệm",
};

/** Nhãn trạng thái bài tập trắc nghiệm dùng chung. */
export const QUIZ_STATUS_LABEL: Record<QuizAssignmentStatus, string> = {
  draft: "Bản nháp",
  published: "Đã giao",
  closed: "Đã đóng",
};

/** Màu badge trạng thái bài tập trắc nghiệm dùng chung. */
export const QUIZ_STATUS_TONE: Record<QuizAssignmentStatus, string> = {
  draft: "border-black/10 bg-black/5 text-black/65",
  published: "border-[#cfe0ca] bg-[#e8f1e6] text-[#3f573c]",
  closed: "border-black/10 bg-black/5 text-black/65",
};
