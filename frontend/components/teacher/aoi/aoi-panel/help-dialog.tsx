"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function HelpDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Cách dùng</DialogTitle>
          <DialogDescription>Ba thao tác chính.</DialogDescription>
        </DialogHeader>
        <ol className="space-y-3 px-6 pb-2 text-sm text-foreground">
          <li className="flex gap-2">
            <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-accent text-[10px] font-semibold text-primary">
              1
            </span>
            Bấm vào một phần của trang để chọn vùng.
          </li>
          <li className="flex gap-2">
            <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-accent text-[10px] font-semibold text-primary">
              2
            </span>
            Kéo chuột trên slide hoặc trên trang để vẽ vùng mới.
          </li>
          <li className="flex gap-2">
            <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-accent text-[10px] font-semibold text-primary">
              3
            </span>
            Bấm “Tương tác” để chuyển trang như học viên.
          </li>
        </ol>
        <p className="px-6 pb-6 text-xs leading-5 text-muted-foreground">
          Vùng slide do giáo viên tự vẽ, không có gợi ý tự động. Nhãn phân tích
          phải có dạng AOI_… (chữ in hoa, số, dấu gạch dưới) và không trùng
          trong cùng slide; hệ thống thêm tiền tố SLIDE_ khi ghi nhận gaze, ví
          dụ AOI_THANHCHAT thành SLIDE_AOI_THANHCHAT. Vùng giao diện dùng chính
          tên vùng làm nhãn. Bỏ đánh dấu đưa vùng vào “Chưa đánh dấu” và có thể
          bật lại; nút thùng rác xóa hẳn vùng khỏi slide/giao diện.
        </p>
      </DialogContent>
    </Dialog>
  );
}
