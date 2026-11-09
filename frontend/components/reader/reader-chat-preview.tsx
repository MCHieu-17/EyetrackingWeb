"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Textarea } from "@/components/ui/input";

interface PreviewMessage {
  id: string;
  role: "student" | "assistant";
  content: string;
}

const INITIAL_MESSAGES: PreviewMessage[] = [
  {
    id: "preview-user-1",
    role: "student",
    content: "Tóm tắt nội dung chính của bài này",
  },
  {
    id: "preview-ai-1",
    role: "assistant",
    content:
      "Bài học gồm 3 phần: khái niệm, ví dụ và bài tập vận dụng. Bạn có thể hỏi thêm về từng phần.",
  },
];

/**
 * Bản xem trước panel trợ lý với đúng `data-aoi` như StudyAssistantChat.
 * Nội dung là mẫu; giáo viên dùng để chọn vùng, không gọi chatbot thật.
 */
export function ReaderChatPreview({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<PreviewMessage[]>(INITIAL_MESSAGES);
  const [input, setInput] = useState("");

  if (!open) return null;

  const send = () => {
    const text = input.trim();
    if (!text) return;
    setMessages((prev) => [
      ...prev,
      { id: `preview-user-${Date.now()}`, role: "student", content: text },
      {
        id: `preview-ai-${Date.now()}`,
        role: "assistant",
        content:
          "Đây là câu trả lời mẫu trong bản xem trước. Khi học viên dùng thật, trợ lý sẽ trả lời dựa trên tài liệu môn học.",
      },
    ]);
    setInput("");
  };

  return (
    <div
      id="assistant-panel"
      data-aoi="chatbot"
      className="@container flex h-full w-[clamp(360px,28vw,480px)] shrink-0 flex-col overflow-hidden rounded-[20px] border border-border/80 bg-[#fdfdfa] shadow-xs"
      role="dialog"
      aria-label="Trợ lý học tập"
    >
      <header
        data-aoi="chat-header"
        className="flex items-center gap-2 border-b border-border px-4 py-3"
      >
        <div className="flex size-9 items-center justify-center rounded-full bg-[#e8efe6] text-[#36533a]">
          <Icon name="ri-sparkling-2-line" className="size-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">Trợ lý học tập</p>
          <p className="truncate text-[11px] text-muted-foreground">
            Hỏi đáp trong môn học
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          aria-label="Đóng trợ lý"
        >
          <Icon name="ri-close-line" className="size-4" />
        </Button>
      </header>

      <div
        data-aoi="chat-messages"
        className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-4 py-4"
      >
        <div className="flex flex-col gap-3">
          {messages.map((message) => (
            <div
              key={message.id}
              className={
                message.role === "student"
                  ? "flex flex-col items-end gap-1.5"
                  : "flex flex-col items-start gap-1.5"
              }
            >
              <div
                data-aoi={
                  message.role === "student"
                    ? "chat-user-message"
                    : "chat-ai-message"
                }
                className={
                  message.role === "student"
                    ? "min-w-0 max-w-[92%] rounded-2xl bg-[#36533a] px-3.5 py-2.5 text-white"
                    : "min-w-0 max-w-[92%] rounded-2xl border border-border bg-white px-3.5 py-2.5 text-foreground"
                }
              >
                <p className="whitespace-pre-wrap text-sm leading-6">
                  {message.content}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <form
        data-aoi="chat-input"
        onSubmit={(event) => {
          event.preventDefault();
          send();
        }}
        className="border-t border-border p-3"
      >
        <div className="flex items-end gap-2">
          <Textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                send();
              }
            }}
            placeholder="Nhập câu hỏi…"
            aria-label="Câu hỏi cho trợ lý"
            rows={1}
            className="max-h-32 min-h-10 flex-1 resize-none rounded-2xl py-2.5"
          />
          <Button
            type="submit"
            data-aoi="chat-send"
            size="icon"
            className="size-10 shrink-0 rounded-full"
            disabled={!input.trim()}
            aria-label="Gửi câu hỏi"
          >
            <Icon name="ri-send-plane-2-line" className="size-4" />
          </Button>
        </div>
      </form>
    </div>
  );
}
