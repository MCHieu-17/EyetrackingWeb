"use client";

import {
  type FormEvent,
  type KeyboardEvent,
  type RefObject,
} from "react";
import { RiSendPlane2Line } from "@remixicon/react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";

export function Composer({
  value,
  onValueChange,
  onSend,
  streaming,
  inputRef,
}: {
  value: string;
  onValueChange: (value: string) => void;
  onSend: (value: string) => void;
  streaming: boolean;
  inputRef: RefObject<HTMLTextAreaElement | null>;
}) {
  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    onSend(value);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      onSend(value);
    }
  };

  return (
    <form
      data-aoi="chat-input"
      onSubmit={onSubmit}
      className="border-t border-border p-3 @max-[320px]:p-2.5"
    >
      <div className="flex items-end gap-2">
        <Textarea
          ref={inputRef}
          value={value}
          onChange={(event) => {
            onValueChange(event.target.value);
            event.target.style.height = "40px";
            event.target.style.height = `${Math.min(128, event.target.scrollHeight)}px`;
          }}
          onKeyDown={onKeyDown}
          placeholder="Nhập câu hỏi…"
          aria-label="Câu hỏi cho trợ lý"
          rows={1}
          className="max-h-32 min-h-10 flex-1 resize-none rounded-2xl py-2.5"
          disabled={streaming}
        />
        <Button
          type="submit"
          data-aoi="chat-send"
          size="icon"
          className="size-10 shrink-0 rounded-full"
          disabled={!value.trim() || streaming}
          aria-label="Gửi câu hỏi"
        >
          <RiSendPlane2Line className="size-4" />
        </Button>
      </div>
    </form>
  );
}
