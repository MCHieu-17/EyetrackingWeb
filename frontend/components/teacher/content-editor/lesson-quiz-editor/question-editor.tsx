"use client";

import { QuizQuestionEditor } from "@/components/quiz/quiz-question-editor";
import type { QuizQuestion } from "@/lib/types/domain";

/**
 * Vùng soạn câu đang chọn. Việc sửa nội dung câu và các lựa chọn (option) nằm
 * trong `QuizQuestionEditor` dùng chung của khối quiz; component này chỉ giữ
 * phần khung và trạng thái rỗng của trình soạn bài tập.
 */
export function QuestionEditor({
  question,
  index,
  canRemove,
  canMoveUp,
  canMoveDown,
  onChange,
  onRemove,
  onDuplicate,
  onMoveUp,
  onMoveDown,
}: {
  question: QuizQuestion | null;
  index: number;
  canRemove: boolean;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onChange: (question: QuizQuestion) => void;
  onRemove: () => void;
  onDuplicate: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}) {
  if (!question) {
    return (
      <p className="rounded-2xl border border-dashed border-border bg-muted/40 px-4 py-10 text-center text-sm text-muted-foreground">
        Chọn một câu hỏi ở danh sách bên trái, hoặc bấm “Thêm câu hỏi”.
      </p>
    );
  }

  return (
    <QuizQuestionEditor
      question={question}
      index={index}
      canRemove={canRemove}
      canMoveUp={canMoveUp}
      canMoveDown={canMoveDown}
      onChange={onChange}
      onRemove={onRemove}
      onDuplicate={onDuplicate}
      onMoveUp={onMoveUp}
      onMoveDown={onMoveDown}
    />
  );
}
