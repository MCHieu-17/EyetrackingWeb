"use client";

import { Icon } from "@/components/ui/icon";

export function NoLabelRow() {
  return (
    <div className="mt-3 flex items-center gap-2 rounded-xl border border-dashed border-black/10 bg-[#f7f7f4] px-3 py-2">
      <span className="size-2.5 shrink-0 rounded-full bg-black/25" />
      <Icon name="ri-lock-line" className="size-3.5 shrink-0 text-black/35" />
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-black/65">Phần còn lại của trang</p>
        <p className="text-[10px] text-black/40">
          Tự động gom các vùng chưa đánh dấu
        </p>
      </div>
    </div>
  );
}
