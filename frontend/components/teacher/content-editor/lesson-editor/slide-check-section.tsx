"use client";

import { SlidePreview } from "../slide-preview";
import type { SlideAdmin } from "@/lib/types/domain";

/** Khối kiểm tra tài liệu: lưới trang slide và xem trước. */
export function SlideCheckSection({ slides }: { slides: SlideAdmin[] }) {
  if (slides.length === 0) return null;

  return (
    <section className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs sm:p-6">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-base font-semibold text-black">Kiểm tra tài liệu</h3>
        <span className="text-xs font-medium text-black/60">
          {slides.length} trang · bấm một trang để xem trước
        </span>
      </div>
      <SlidePreview slides={slides} />
    </section>
  );
}
