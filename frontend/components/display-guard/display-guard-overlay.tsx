"use client";

import { Icon } from "@/components/ui/icon";
import type { DisplayGuardReason } from "@/lib/display-guard";

export interface DisplayGuardOverlayProps {
  blocked: boolean;
  reason: DisplayGuardReason | null;
  zoomPercent: number;
  onRecheck: () => void;
}

interface GuardCopy {
  title: string;
  description: string;
  hint: string;
}

const COPY: Record<DisplayGuardReason, GuardCopy> = {
  page_zoom: {
    title: "Trình duyệt đang phóng to",
    description:
      "Điểm nhìn chỉ chính xác khi nội dung hiển thị ở 100%. Hãy nhấn Ctrl+0 (Cmd+0 trên Mac) để đưa zoom về 100%.",
    hint: "Không dùng Ctrl/Cmd + phím + hoặc − trong lúc hiệu chỉnh và học.",
  },
  pinch_zoom: {
    title: "Bạn đang thu phóng bằng cử chỉ",
    description:
      "Trang đang được phóng to bằng hai ngón tay. Hãy thu hai ngón tay lại để đưa trang về 100%.",
    hint: "Tắt thu phóng bằng cử chỉ trên trình duyệt di động nếu cần.",
  },
  fullscreen: {
    title: "Đang bật toàn màn hình",
    description:
      "Chế độ toàn màn hình làm lệch vùng hiệu chỉnh. Hãy thoát toàn màn hình (Esc hoặc F11) rồi kiểm tra lại.",
    hint: "Nếu không thoát được, hãy đóng bớt cửa sổ đang chiếm toàn màn hình.",
  },
  browser_fullscreen: {
    title: "Cửa sổ đang toàn màn hình",
    description:
      "Cửa sổ trình duyệt đang phủ kín màn hình (F11/toàn màn hình). Hãy thoát toàn màn hình rồi kiểm tra lại.",
    hint: "Chỉ học ở cửa sổ bình thường để vùng hiệu chỉnh không bị lệch.",
  },
};

const FALLBACK_COPY: GuardCopy = {
  title: "Hiển thị chưa ổn định",
  description:
    "Hãy đưa zoom về 100% và tắt toàn màn hình để tiếp tục ghi nhận điểm nhìn.",
  hint: "Nhấn Ctrl+0 (Cmd+0 trên Mac) để khôi phục zoom.",
};

/**
 * Overlay không thể bỏ qua khi hiển thị sai. Không có nút đóng: chỉ khi
 * trạng thái hiển thị trở lại bình thường (tự động hoặc qua "Kiểm tra lại")
 * overlay mới biến mất.
 */
export function DisplayGuardOverlay({
  blocked,
  reason,
  zoomPercent,
  onRecheck,
}: DisplayGuardOverlayProps) {
  if (!blocked) return null;

  const copy = reason ? COPY[reason] : FALLBACK_COPY;

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-[#111210]/80 p-4 backdrop-blur-sm"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="display-guard-title"
      aria-describedby="display-guard-description"
      data-display-guard-overlay=""
    >
      <div className="w-full max-w-md rounded-[24px] border border-white/10 bg-[#1b1c19] p-6 text-white shadow-[0_24px_80px_rgba(0,0,0,0.45)] sm:p-7">
        <span className="flex size-11 items-center justify-center rounded-full border border-white/15 bg-white/10 text-white">
          <Icon name="ri-focus-2-line" className="size-5" />
        </span>

        <h2
          id="display-guard-title"
          className="mt-4 text-xl font-semibold tracking-[-0.02em] text-white"
        >
          {copy.title}
        </h2>
        <p
          id="display-guard-description"
          className="mt-2 text-sm leading-6 text-white/70"
        >
          {copy.description}
        </p>

        <div className="mt-4 flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
          <span className="text-xs font-medium text-white/60">
            Zoom hiện tại
          </span>
          <span className="text-lg font-semibold tabular-nums text-white">
            {zoomPercent}%
          </span>
        </div>

        <p className="mt-3 text-xs leading-5 text-white/55">{copy.hint}</p>

        <button
          type="button"
          onClick={onRecheck}
          className="mt-5 inline-flex h-11 w-full items-center justify-center rounded-xl bg-white px-4 text-sm font-semibold text-[#20221f] transition-colors hover:bg-white/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60 focus-visible:ring-offset-2 focus-visible:ring-offset-[#1b1c19]"
        >
          Kiểm tra lại
        </button>
      </div>
    </div>
  );
}
