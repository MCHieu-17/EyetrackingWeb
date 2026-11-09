"use client";

import { cn } from "@/lib/utils";
import type { ChatCitation } from "@/lib/api/chat";
import { CitationList } from "./citation-list";
import { Markdown } from "./markdown";
import type { UiMessage } from "./chat-helpers";

export function MessageBubble({
  message,
  streamingText,
  streamingCitations,
  statusLabel,
  onCitationClick,
}: {
  message: UiMessage;
  streamingText: string;
  streamingCitations: ChatCitation[];
  statusLabel: string | null;
  onCitationClick: (citation: ChatCitation) => void;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-1.5",
        message.role === "student" ? "items-end" : "items-start",
      )}
    >
      <div
        data-aoi-instance={message.id}
        data-aoi={
          message.role === "student"
            ? "chat-user-message"
            : "chat-ai-message"
        }
        className={cn(
          "min-w-0 max-w-full rounded-2xl px-3.5 py-2.5",
          message.role === "student"
            ? "max-w-[92%] bg-[#36533a] text-white"
            : "border border-border bg-white text-foreground",
        )}
      >
        {message.role === "student" ? (
          <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
        ) : message.pending ? (
          streamingText ? (
            <Markdown
              text={streamingText}
              messageId={message.id}
              citations={streamingCitations}
              onCitationClick={onCitationClick}
            />
          ) : (
            <p className="text-sm text-muted-foreground">
              {statusLabel ?? "Đang xử lý…"}
            </p>
          )
        ) : (
          <Markdown
            text={message.content}
            messageId={message.id}
            citations={message.citations}
            onCitationClick={onCitationClick}
          />
        )}
      </div>
      {message.role === "assistant" && message.citations.length > 0 && (
        <CitationList
          messageId={message.id}
          citations={message.citations}
          onCitationClick={onCitationClick}
        />
      )}
    </div>
  );
}
