import { MAX_SLIDE_PAGES, MAX_UPLOAD_BYTES, MAX_UPLOAD_LABEL } from "@/lib/api/client";
import type {
  LessonNode,
  ModuleNode,
  QuizAssignment,
  QuizQuestion,
} from "@/lib/types/domain";

/** Định dạng tài liệu slide được chấp nhận khi tải lên. */
export const ALLOWED_SLIDE_EXTENSIONS = [".pdf", ".pptx", ".ppt", ".odp"] as const;

/** Gợi ý giới hạn tài liệu dùng chung cho vùng tải lên. */
export const SLIDE_LIMITS_HINT = `PDF, PPTX, PPT, ODP · tối đa ${MAX_UPLOAD_LABEL} · tối đa ${MAX_SLIDE_PAGES} trang — mỗi trang thành 1 slide.`;

/** Thông điệp lỗi thống nhất cho các thao tác trong trình soạn nội dung. */
export function errText(error: unknown): string {
  return error instanceof Error ? error.message : "Lỗi không xác định";
}

/** Mục mặc định khi giáo viên chưa chọn gì: bài đầu tiên của chương đầu tiên. */
export function firstItemId(tree: ModuleNode[]): string | null {
  return tree[0]?.lessons[0]?.id ?? null;
}

export interface SelectedItem {
  lesson: LessonNode;
  module: ModuleNode;
}

/** Tìm bài giảng/bài tập đang chọn cùng chương chứa nó. */
export function findSelectedItem(
  tree: ModuleNode[],
  activeId: string | null,
): SelectedItem | null {
  if (!activeId) return null;
  for (const mod of tree) {
    const lesson = mod.lessons.find((item) => item.id === activeId);
    if (lesson) return { lesson, module: mod };
  }
  return null;
}

export interface TreeCounts {
  totalLessons: number;
  totalQuizzes: number;
  totalSlides: number;
  totalItems: number;
}

/** Đếm số bài giảng, bài tập, slide và tổng số mục của cây nội dung. */
export function countTree(tree: ModuleNode[]): TreeCounts {
  const items = tree.flatMap((module) => module.lessons);
  const totalLessons = items.filter((item) => item.kind === "lesson").length;
  const totalQuizzes = items.filter((item) => item.kind === "quiz").length;
  const totalSlides = items.reduce((sum, item) => sum + item.slides, 0);
  return {
    totalLessons,
    totalQuizzes,
    totalSlides,
    totalItems: totalLessons + totalQuizzes,
  };
}

/** Chương chứa một mục — dùng để mở rộng đúng chương khi chọn mục. */
export function moduleOfLesson(
  tree: ModuleNode[],
  lessonId: string,
): ModuleNode | null {
  return (
    tree.find((module) => module.lessons.some((item) => item.id === lessonId)) ??
    null
  );
}

/** Kiểm tra tên/định dạng/kích thước tài liệu slide trước khi tải lên. */
export function validateSlideFile(file: { name: string; size: number }): string | null {
  const lower = file.name.toLowerCase();
  const extension = lower.slice(lower.lastIndexOf("."));
  if (!(ALLOWED_SLIDE_EXTENSIONS as readonly string[]).includes(extension)) {
    return `"${file.name}" không phải tài liệu slide hợp lệ. Hãy chọn PDF, PPTX, PPT hoặc ODP.`;
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return `File "${file.name}" vượt quá ${MAX_UPLOAD_LABEL} cho phép.`;
  }
  return null;
}

export interface QuizForm {
  instructions: string;
  durationMinutes: number;
  dueAt: string;
  allowRetry: boolean;
  allowChatbot: boolean;
  questions: QuizQuestion[];
}

/** Chuyển ISO sang giá trị cho input datetime-local (giờ địa phương). */
export function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Chuỗi so sánh form bài tập để phát hiện thay đổi chưa lưu. */
export function serializeQuizForm(form: QuizForm): string {
  return JSON.stringify(form);
}

/** Dựng form bài tập từ dữ liệu assignment tải về. */
export function quizFormFromAssignment(assignment: QuizAssignment): QuizForm {
  return {
    instructions: assignment.instructions,
    durationMinutes: assignment.durationMinutes,
    dueAt: toLocalInput(assignment.dueAt),
    allowRetry: Boolean(assignment.allowRetry),
    allowChatbot: Boolean(assignment.allowChatbot),
    questions: assignment.questions,
  };
}

export interface QuestionListUpdate {
  questions: QuizQuestion[];
  selectedIndex: number;
}

/** Thêm câu hỏi mới vào cuối danh sách và chọn câu vừa thêm. */
export function appendQuestion(
  questions: QuizQuestion[],
  question: QuizQuestion,
): QuestionListUpdate {
  return { questions: [...questions, question], selectedIndex: questions.length };
}

/** Chèn bản sao ngay sau câu nguồn và chọn bản sao. */
export function insertQuestionAt(
  questions: QuizQuestion[],
  index: number,
  question: QuizQuestion,
): QuestionListUpdate {
  return {
    questions: [
      ...questions.slice(0, index + 1),
      question,
      ...questions.slice(index + 1),
    ],
    selectedIndex: index + 1,
  };
}

/** Xóa câu hỏi; giữ tối thiểu một câu và kẹp vị trí đang chọn. */
export function removeQuestionAt(
  questions: QuizQuestion[],
  index: number,
): QuestionListUpdate {
  if (questions.length <= 1) return { questions, selectedIndex: index };
  const next = questions.filter((_, itemIndex) => itemIndex !== index);
  return { questions: next, selectedIndex: Math.min(index, next.length - 1) };
}

/** Đổi chỗ câu hỏi với câu liền kề và chọn vị trí mới. */
export function moveQuestionAt(
  questions: QuizQuestion[],
  index: number,
  direction: -1 | 1,
): QuestionListUpdate {
  const target = index + direction;
  if (target < 0 || target >= questions.length) {
    return { questions, selectedIndex: index };
  }
  const next = [...questions];
  [next[index], next[target]] = [next[target], next[index]];
  return { questions: next, selectedIndex: target };
}
