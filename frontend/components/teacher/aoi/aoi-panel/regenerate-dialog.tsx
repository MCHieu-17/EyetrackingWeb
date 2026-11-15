"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Icon } from "@/components/ui/icon";
import type { AoiEditorController } from "../use-aoi-editor";

export function RegenerateDialog({
  controller,
  open,
  onOpenChange,
}: {
  controller: AoiEditorController;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Tạo lại gợi ý vùng?</DialogTitle>
          <DialogDescription>
            PyMuPDF sẽ dò lại layout và tạo các vùng TEXT/IMAGE/TABLE.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2 px-6 pb-2">
          <Button
            type="button"
            variant="outline"
            className="h-auto w-full justify-start whitespace-normal px-3 py-3 text-left"
            disabled={controller.generatingSlide}
            onClick={() => {
              onOpenChange(false);
              controller.regenerateSlide("auto");
            }}
          >
            <Icon name="ri-refresh-line" className="size-4 shrink-0" />
            <span className="min-w-0">
              <span className="block text-sm font-semibold">
                Chỉ thay vùng gợi ý
              </span>
              <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                Giữ các vùng tự vẽ và tên slide hiện có.
              </span>
            </span>
          </Button>
          <Button
            type="button"
            variant="outline"
            className="h-auto w-full justify-start whitespace-normal border-destructive/30 px-3 py-3 text-left text-destructive hover:bg-destructive/5"
            disabled={controller.generatingSlide}
            onClick={() => {
              onOpenChange(false);
              controller.regenerateSlide("all");
            }}
          >
            <Icon name="ri-delete-bin-line" className="size-4 shrink-0" />
            <span className="min-w-0">
              <span className="block text-sm font-semibold">
                Đặt lại toàn bộ
              </span>
              <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                Xoá cả vùng tự vẽ, chỉ giữ container slide và tạo lại các vùng
                gợi ý.
              </span>
            </span>
          </Button>
        </div>
        <div className="flex justify-end border-t border-border p-4">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Hủy
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
