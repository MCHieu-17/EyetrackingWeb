"use client";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";
import type { AoiEditorController } from "../use-aoi-editor";

export function PanelActions({
  controller,
  hint,
  onShowHint,
}: {
  controller: AoiEditorController;
  hint: string | null;
  onShowHint: (text: string) => void;
}) {
  const save = controller.activeSave;
  const saveLabel =
    save.status === "saving"
      ? "Đang lưu…"
      : save.status === "error"
        ? "Không lưu được"
        : "Đã lưu";

  return (
    <>
      <div className="mt-3 flex flex-wrap gap-2">
        {controller.tab === "slide" ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="rounded-full border-black/10 bg-white"
            disabled={!controller.canManage || controller.mode === "interact"}
            onClick={() => onShowHint("Kéo chuột trên slide để vẽ vùng.")}
          >
            <Icon name="ri-add-line" className="size-4" />
            Vẽ vùng
          </Button>
        ) : (
          <>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="rounded-full border-black/10 bg-white"
              disabled={!controller.canManage || controller.mode === "interact"}
              onClick={() => onShowHint("Bấm vào một phần của trang để chọn vùng.")}
            >
              <Icon name="ri-cursor-line" className="size-4" />
              Chọn phần
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="rounded-full border-black/10 bg-white"
              disabled={!controller.canManage || controller.mode === "interact"}
              onClick={() => onShowHint("Kéo chuột trên trang để vẽ vùng.")}
            >
              <Icon name="ri-add-line" className="size-4" />
              Vẽ vùng
            </Button>
          </>
        )}
      </div>

      {hint && (
        <p className="mt-2 rounded-lg bg-[#e8f1e6] px-2.5 py-1.5 text-[11px] text-[#36533a]">
          {hint}
        </p>
      )}

      <div className="mt-3 flex items-center gap-1.5 text-[11px]">
        {save.status === "saving" ? (
          <Icon name="ri-loader-4-line" className="size-3.5 animate-spin text-black/45" />
        ) : save.status === "error" ? (
          <Icon name="ri-error-warning-line" className="size-3.5 text-destructive" />
        ) : (
          <Icon name="ri-check-line" className="size-3.5 text-[#36533a]" />
        )}
        <span
          className={cn(
            save.status === "error" ? "text-destructive" : "text-black/50",
          )}
        >
          {saveLabel}
        </span>
        {save.status === "error" && (
          <button
            type="button"
            onClick={save.retry}
            className="font-semibold text-destructive underline"
          >
            Thử lại
          </button>
        )}
      </div>
    </>
  );
}
