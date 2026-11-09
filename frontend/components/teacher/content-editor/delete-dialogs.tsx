"use client";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type { LessonNode, ModuleNode } from "@/lib/types/domain";

/** Xác nhận xóa chương (kèm cảnh báo số mục bên trong). */
export function DeleteModuleDialog({
  module,
  onOpenChange,
  onConfirm,
}: {
  module: ModuleNode | null;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}) {
  return (
    <ConfirmDialog
      open={module !== null}
      onOpenChange={onOpenChange}
      title={module ? `Xóa chương "${module.title}"?` : "Xóa chương?"}
      description={
        module && module.lessons.length > 0
          ? `Chương này còn ${module.lessons.length} mục — tất cả bài giảng, bài tập và slide bên trong cũng bị xóa.`
          : "Chương này sẽ bị xóa khỏi khóa học."
      }
      confirmLabel="Xóa chương"
      destructive
      onConfirm={onConfirm}
    />
  );
}

/** Xác nhận xóa một bài giảng hoặc bài tập. */
export function DeleteLessonDialog({
  lesson,
  onOpenChange,
  onConfirm,
}: {
  lesson: LessonNode | null;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}) {
  return (
    <ConfirmDialog
      open={lesson !== null}
      onOpenChange={onOpenChange}
      title={
        lesson
          ? `Xóa ${lesson.kind === "quiz" ? "bài tập" : "bài giảng"} "${lesson.title}"?`
          : "Xóa mục?"
      }
      description={
        lesson?.kind === "quiz"
          ? "Bài tập, toàn bộ câu hỏi và kết quả làm bài của học viên sẽ bị xóa."
          : "Bài giảng, toàn bộ slide và dữ liệu điểm nhìn liên quan sẽ bị xóa."
      }
      confirmLabel="Xóa"
      destructive
      onConfirm={onConfirm}
    />
  );
}
