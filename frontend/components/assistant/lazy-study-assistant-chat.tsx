"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import type { ChatCitation } from "@/lib/api/chat";

/**
 * Chat chỉ được tải khi người dùng mở panel lần đầu. Sau đó giữ component
 * mounted (open=false) để không mất draft/scroll khi đóng/mở lại.
 */
const StudyAssistantChatDynamic = dynamic(
  () =>
    import("@/components/assistant/study-assistant-chat").then(
      (mod) => mod.StudyAssistantChat,
    ),
  {
    ssr: false,
    loading: () => (
      <div className="hidden h-full w-[clamp(360px,28vw,480px)] shrink-0 animate-pulse rounded-[20px] border border-border/80 bg-[#fdfdfa] xl:flex" />
    ),
  },
);

export function LazyStudyAssistantChat({
  courseId,
  open,
  onClose,
  onCitationNavigate,
}: {
  courseId: string;
  open: boolean;
  onClose: () => void;
  onCitationNavigate?: (citation: ChatCitation) => boolean;
}) {
  const [loaded, setLoaded] = useState(open);
  if (open && !loaded) setLoaded(true);
  if (!loaded) return null;

  return (
    <StudyAssistantChatDynamic
      courseId={courseId}
      open={open}
      onClose={onClose}
      onCitationNavigate={onCitationNavigate}
    />
  );
}
