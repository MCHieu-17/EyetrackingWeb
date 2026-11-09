"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useChatAccess } from "@/hooks/use-chat";

export function useReaderChat({
  courseId,
  activeLessonId,
  assistantMode,
  assistantAssignmentId,
}: {
  courseId: string;
  activeLessonId: string;
  assistantMode: "reader" | "quiz" | "review";
  assistantAssignmentId: string | null;
}) {
  // Chat dock bên phải. Chỉ dùng ở desktop (>= xl); mobile không thiết kế.
  const [chatOpen, setChatOpen] = useState(false);
  const chatAccess = useChatAccess(courseId, chatOpen || assistantMode === "quiz");
  const chatAllowed = chatAccess.data?.allowed === true && !chatAccess.isError;
  const refreshChatAccess = chatAccess.refetch;

  useEffect(() => {
    void refreshChatAccess();
  }, [activeLessonId, assistantAssignmentId, assistantMode, refreshChatAccess]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!chatAllowed) setChatOpen(false);
  }, [chatAllowed]);

  const assistantButtonRef = useRef<HTMLButtonElement>(null);
  const wasChatOpen = useRef(false);

  // Đóng chat thì trả focus về nút "Trợ lý" ở header.
  useEffect(() => {
    if (wasChatOpen.current && !chatOpen) {
      assistantButtonRef.current?.focus();
    }
    wasChatOpen.current = chatOpen;
  }, [chatOpen]);

  const toggleChat = async () => {
    if (chatOpen) {
      setChatOpen(false);
      return;
    }
    const result = await chatAccess.refetch();
    if (result.data?.allowed && !result.isError) setChatOpen(true);
  };

  const closeChat = useCallback(() => setChatOpen(false), []);

  return {
    chatOpen,
    chatAllowed,
    chatAccess,
    assistantButtonRef,
    toggleChat,
    closeChat,
  };
}
