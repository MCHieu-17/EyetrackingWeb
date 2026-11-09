"use client";

import { RiCloseLine, RiSparkling2Line } from "@remixicon/react";
import { Button } from "@/components/ui/button";
import {
  getAssistantSubtitle,
  type AssistantMode,
  type ChatSessionLike,
} from "./chat-helpers";
import { SessionMenu } from "./session-list";

export function AssistantHeader({
  mode,
  sessions,
  currentSession,
  onSelectSession,
  onRename,
  onDelete,
  onClose,
}: {
  mode: AssistantMode;
  sessions: ChatSessionLike[];
  currentSession: ChatSessionLike | undefined;
  onSelectSession: (sessionId: string | null) => void;
  onRename: () => void;
  onDelete: () => void;
  onClose: () => void;
}) {
  return (
    <header
      data-aoi="chat-header"
      className="flex items-center gap-2 border-b border-border px-4 py-3 @max-[320px]:px-3 @max-[320px]:py-2.5"
    >
      <div className="flex size-9 items-center justify-center rounded-full bg-[#e8efe6] text-[#36533a] @max-[320px]:hidden">
        <RiSparkling2Line className="size-5" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">Trợ lý học tập</p>
        <p className="truncate text-[11px] text-muted-foreground">
          {getAssistantSubtitle(mode)}
        </p>
      </div>

      <SessionMenu
        sessions={sessions}
        currentSession={currentSession}
        onSelectSession={onSelectSession}
        onRename={onRename}
        onDelete={onDelete}
      />

      <Button
        variant="ghost"
        size="icon"
        onClick={onClose}
        aria-label="Đóng trợ lý"
      >
        <RiCloseLine className="size-4" />
      </Button>
    </header>
  );
}
