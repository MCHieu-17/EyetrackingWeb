"use client";

import type { RefObject, UIEvent } from "react";
import { RiSparkling2Line } from "@remixicon/react";
import type { ChatCitation } from "@/lib/api/chat";
import {
  getEmptyState,
  type AssistantMode,
  type UiMessage,
} from "./chat-helpers";
import { MessageBubble } from "./message-bubble";

export function MessageList({
  messages,
  streamingText,
  streamingCitations,
  statusLabel,
  error,
  mode,
  showEmpty,
  onSuggestion,
  onCitationClick,
  onScroll,
  bottomRef,
}: {
  messages: UiMessage[];
  streamingText: string;
  streamingCitations: ChatCitation[];
  statusLabel: string | null;
  error: string;
  mode: AssistantMode;
  showEmpty: boolean;
  onSuggestion: (suggestion: string) => void;
  onCitationClick: (citation: ChatCitation) => void;
  onScroll: (event: UIEvent<HTMLDivElement>) => void;
  bottomRef: RefObject<HTMLDivElement | null>;
}) {
  const emptyState = getEmptyState(mode);

  return (
    <div
      data-aoi="chat-messages"
      onScroll={onScroll}
      className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-4 py-4 @max-[320px]:px-3"
    >
      {showEmpty && (
        <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
          <div className="flex size-14 items-center justify-center rounded-full bg-[#e8efe6] text-[#36533a]">
            <RiSparkling2Line className="size-7" />
          </div>
          <div>
            <p className="text-sm font-semibold">Mình có thể giúp gì?</p>
            <p className="mt-1 max-w-xs text-xs text-muted-foreground">
              {emptyState.description}
            </p>
          </div>
          <div className="flex w-full max-w-xs flex-col gap-2">
            {emptyState.suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => onSuggestion(suggestion)}
                className="rounded-xl border border-border bg-white px-3 py-2 text-left text-xs text-muted-foreground transition hover:bg-muted hover:text-foreground"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            streamingText={streamingText}
            streamingCitations={streamingCitations}
            statusLabel={statusLabel}
            onCitationClick={onCitationClick}
          />
        ))}

        {error && (
          <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
            {error}
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
