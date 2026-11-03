"use client";

import { forwardRef } from "react";
import { Icon } from "@/components/ui/icon";

/**
 * Bản xem trước layout đọc bài + chatbot, gắn `data-aoi` giống runtime.
 *
 * Đây chỉ là preview để chọn/đặt tên vùng; toạ độ thật do runtime đo bằng
 * getBoundingClientRect() và gửi lên backend theo từng layout snapshot.
 */
export const AoiPreview = forwardRef<
  HTMLDivElement,
  { mode: "reader" | "quiz" }
>(function AoiPreview({ mode }, ref) {
  return (
    <div
      ref={ref}
      className="aoi-editor-preview flex h-[620px] min-w-[980px] flex-col overflow-hidden rounded-[20px] border border-border bg-[#f5f6f2] p-2"
    >
      <header
        data-aoi="header"
        className="flex h-12 shrink-0 items-center gap-3 rounded-full border border-border bg-white px-4"
      >
        <span className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-[11px] text-muted-foreground">
          <Icon name="ri-arrow-left-line" className="size-3.5" />
          Khóa học của tôi
        </span>
        <span className="mx-auto truncate text-xs font-medium text-muted-foreground">
          Khóa học mẫu · Bài 1
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-[11px] text-muted-foreground">
          <span className="size-1.5 rounded-full bg-primary" />
          Gaze đang hoạt động
        </span>
      </header>

      <div className="mt-2 flex min-h-0 flex-1 gap-2">
        <aside
          data-aoi="outline"
          className="hidden w-[220px] shrink-0 flex-col overflow-hidden rounded-[18px] border border-border bg-white p-4 lg:flex"
        >
          <span className="w-fit rounded-full bg-[#e8f1e6] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[#52704f]">
            Mục lục
          </span>
          <p className="mt-3 text-sm font-semibold">Khóa học mẫu</p>
          <div className="mt-4 space-y-2 text-xs text-muted-foreground">
            <p className="rounded-lg bg-primary px-2 py-1.5 text-white">Bài 1</p>
            <p className="px-2 py-1.5">Bài 2</p>
            <p className="px-2 py-1.5">Bài tập 1</p>
          </div>
        </aside>

        <main
          data-aoi="lesson-content"
          className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-[18px] border border-border bg-[#fffffb]"
        >
          <div className="shrink-0 px-4 py-3">
            <p className="text-[11px] text-muted-foreground">Chương 1 · Chương mẫu</p>
            <h2 className="mt-0.5 text-sm font-medium">Bài 1: Nội dung mẫu</h2>
          </div>

          <div className="flex min-h-0 flex-1 items-center justify-center overflow-auto p-4">
            {mode === "reader" ? (
              <div
                data-aoi="slide"
                className="flex aspect-video w-full max-w-[620px] flex-col items-center justify-center rounded-xl border border-border bg-white p-6 text-center shadow-sm"
              >
                <div className="flex size-12 items-center justify-center rounded-full bg-muted">
                  <Icon name="ri-image-line" className="size-6 text-muted-foreground" />
                </div>
                <p className="mt-3 text-sm font-semibold">Slide bài giảng</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Vùng này tương ứng ảnh slide đang hiển thị
                </p>
              </div>
            ) : (
              <div data-aoi="quiz" className="w-full max-w-[620px] space-y-3">
                <div
                  data-aoi="quiz-question"
                  className="rounded-xl border border-border bg-white p-4 shadow-sm"
                >
                  <p className="text-[11px] font-semibold text-muted-foreground">Câu 1 / 3</p>
                  <p className="mt-2 text-sm font-semibold">
                    Thành phần nào đóng vai trò quan trọng nhất?
                  </p>
                </div>
                <div data-aoi="quiz-options" className="space-y-2">
                  {["Đáp án A", "Đáp án B", "Đáp án C"].map((option) => (
                    <div
                      key={option}
                      className="rounded-xl border border-border bg-white px-3 py-2 text-xs"
                    >
                      {option}
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  data-aoi="quiz-submit"
                  className="rounded-full bg-primary px-4 py-2 text-xs font-semibold text-white"
                >
                  Nộp bài
                </button>
              </div>
            )}
          </div>

          <footer
            data-aoi="lesson-nav"
            className="absolute inset-x-0 bottom-3 flex justify-center px-4"
          >
            <div className="flex items-center gap-2 rounded-full border border-border bg-white/95 px-2 py-1.5 shadow-md">
              <span className="rounded-full border border-border px-3 py-1 text-[11px]">
                Trước
              </span>
              <span className="rounded-full bg-primary px-3 py-1 text-[11px] text-white">
                Sau
              </span>
            </div>
          </footer>
        </main>

        <aside
          data-aoi="chatbot"
          className="flex w-[300px] shrink-0 flex-col overflow-hidden rounded-[18px] border border-border bg-white"
        >
          <div
            data-aoi="chat-header"
            className="flex items-center gap-2 border-b border-border px-3 py-2.5"
          >
            <div className="flex size-7 items-center justify-center rounded-full bg-[#e8efe6] text-[#36533a]">
              <Icon name="ri-sparkling-2-line" className="size-4" />
            </div>
            <div>
              <p className="text-xs font-semibold">Trợ lý học tập</p>
              <p className="text-[10px] text-muted-foreground">Hỏi đáp trong môn học</p>
            </div>
          </div>

          <div data-aoi="chat-messages" className="flex-1 space-y-3 overflow-y-auto p-3">
            <div
              data-aoi="chat-user-message"
              className="ml-auto max-w-[85%] rounded-2xl bg-[#36533a] px-3 py-2 text-xs leading-5 text-white"
            >
              Tóm tắt nội dung chính của bài này
            </div>
            <div
              data-aoi="chat-ai-message"
              className="max-w-[85%] rounded-2xl border border-border bg-white px-3 py-2 text-xs leading-5"
            >
              Bài học gồm 3 phần: khái niệm, ví dụ và bài tập vận dụng.
            </div>
          </div>

          <div data-aoi="chat-input" className="border-t border-border p-2.5">
            <div className="flex items-end gap-2">
              <div className="min-h-9 flex-1 rounded-2xl border border-border px-3 py-2 text-[11px] text-muted-foreground">
                Hỏi về nội dung bài học…
              </div>
              <button
                type="button"
                data-aoi="chat-send"
                className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary text-white"
              >
                <Icon name="ri-send-plane-2-line" className="size-4" />
              </button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
});
