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
            <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-[#e8f1e6] text-[10px] font-semibold text-[#36533a]">
              1
            </span>
            Bấm vào một phần của trang để chọn vùng.
          </li>
          <li className="flex gap-2">
            <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-[#e8f1e6] text-[10px] font-semibold text-[#36533a]">
              2
            </span>
            Kéo chuột trên slide hoặc trên trang để vẽ vùng mới.
          </li>
          <li className="flex gap-2">
            <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-[#e8f1e6] text-[10px] font-semibold text-[#36533a]">
              3
            </span>
            Bấm “Tương tác” để chuyển trang như học viên.
          </li>
        </ol>
        <p className="px-6 pb-6 text-xs leading-5 text-muted-foreground">
          Bỏ đánh dấu đưa vùng vào “Chưa đánh dấu” và có thể bật lại. Nút thùng
          rác xóa hẳn vùng khỏi slide/giao diện. Nhãn phân tích của vùng slide
          là AOI_1, AOI_2, …; vùng giao diện dùng chính tên vùng.
        </p>
      </DialogContent>
    </Dialog>
  );
}
