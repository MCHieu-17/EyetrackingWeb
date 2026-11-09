"use client";

import { Button } from "@/components/ui/button";
import type { QuizAssignmentStatus } from "@/lib/types/domain";

/** Thanh lưu cố định ở cuối trình soạn bài tập. */
export function SaveBar({
  dirty,
  status,
  questionCount,
  incompleteCount,
  saving,
  onSaveDraft,
  onSavePublished,
}: {
  dirty: boolean;
  status: QuizAssignmentStatus;
  questionCount: number;
  incompleteCount: number;
  saving: boolean;
  onSaveDraft: () => void;
  onSavePublished: () => void;
}) {
  return (
    <div className="sticky bottom-3 z-10 flex flex-col gap-2 rounded-[20px] border border-[#eeeee9] bg-white/95 p-3 shadow-[0_10px_30px_rgba(30,35,25,0.08)] backdrop-blur-xl sm:flex-row sm:items-center sm:justify-between">
      <div className="space-y-1 px-1">
        <p className="text-xs text-black/60">
          {dirty
            ? "Chưa lưu: thay đổi sẽ mất nếu rời mục này."
            : "Mọi thay đổi đã được lưu."}
        </p>
        {status !== "published" && questionCount === 0 && (
          <p className="text-xs text-black/55">Thêm ít nhất một câu hỏi để giao bài.</p>
        )}
        {status !== "published" && questionCount > 0 && incompleteCount > 0 && (
          <p className="text-xs font-medium text-warning">
            Còn {incompleteCount} câu chưa hoàn thiện — hoàn thiện trước khi giao bài.
          </p>
        )}
        {status === "published" && dirty && (
          <p className="text-xs font-medium text-warning">
            Có thay đổi chưa xuất bản — bấm “Cập nhật cho học viên” để xuất bản khóa học và
            sinh viên thấy thay đổi.
          </p>
        )}
      </div>
      <div className="flex flex-col-reverse gap-2 sm:flex-row">
        <Button
          type="button"
          variant="outline"
          className="rounded-full border-black/10 bg-white"
          disabled={saving}
          onClick={onSaveDraft}
        >
          {saving ? "Đang lưu…" : "Lưu bài tập nháp"}
        </Button>
        <Button
          type="button"
          className="rounded-full"
          disabled={
            saving ||
            (status === "published" && !dirty) ||
            questionCount === 0 ||
            incompleteCount > 0
          }
          onClick={onSavePublished}
        >
          {saving
            ? "Đang lưu…"
            : status === "published"
              ? dirty
                ? "Cập nhật cho học viên"
                : "Đã giao bài"
              : "Giao bài cho học viên"}
        </Button>
      </div>
    </div>
  );
}
