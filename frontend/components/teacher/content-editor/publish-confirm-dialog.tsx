"use client";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";

/** Xác nhận xuất bản khóa học từ tab Nội dung. */
export function PublishConfirmDialog({
  open,
  onOpenChange,
  loading,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  loading: boolean;
  onConfirm: () => void;
}) {
  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Xuất bản khóa học?"
      description="Sinh viên sẽ thấy khóa học trong danh sách và đăng ký được. Mọi bài giảng đã tải lên và bài tập đã giao hiện ngay với học viên."
      confirmLabel="Xuất bản"
      loading={loading}
      onConfirm={onConfirm}
    />
  );
}
