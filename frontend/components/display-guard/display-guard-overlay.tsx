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
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-background/95 p-4 backdrop-blur"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="display-guard-title"
      aria-describedby="display-guard-description"
      data-display-guard-overlay=""
    >
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 text-card-foreground shadow-lg sm:p-7">
        <span className="flex size-11 items-center justify-center rounded-full bg-accent text-accent-foreground">
          <Icon name="ri-focus-2-line" className="size-5" />
        </span>

        <h2
          id="display-guard-title"
          className="mt-4 font-display text-xl font-semibold tracking-[-0.02em] text-foreground"
        >
          {copy.title}
        </h2>
        <p
          id="display-guard-description"
          className="mt-2 text-sm leading-6 text-muted-foreground"
        >
          {copy.description}
        </p>

        <div className="mt-4 flex items-center justify-between gap-3 rounded-2xl border border-border bg-muted px-4 py-3">
          <span className="text-xs font-medium text-muted-foreground">
            Zoom hiện tại
          </span>
          <span className="text-lg font-semibold tabular-nums text-foreground">
            {zoomPercent}%
          </span>
        </div>

        <p className="mt-3 text-xs leading-5 text-muted-foreground">{copy.hint}</p>

        <button
          type="button"
          onClick={onRecheck}
          className="mt-5 inline-flex h-11 w-full items-center justify-center rounded-full bg-primary px-4 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Kiểm tra lại
        </button>
      </div>
    </div>
  );
}
