"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuthState } from "@/hooks/use-stored-user";
import type { ChatCitation } from "@/lib/api/chat";
import {
  useChatMessages,
  useChatAccess,
  useChatSessions,
  useChatStream,
  useDeleteChatSession,
  useRenameChatSession,
} from "@/hooks/use-chat";
import { useAssistant } from "@/components/assistant/assistant-context";
import {
  buildChatStorageKey,
  formatChatError,
  getStatusLabel,
  isNearBottom,
  newLocalId,
  nextSessionAfterDelete,
  normalizeSessionTitle,
  resolveEffectiveSessionId,
  toUiMessages,
  type UiMessage,
} from "./chat-helpers";
import { AssistantHeader } from "./panel-header";
import { MessageList } from "./message-list";
import { Composer } from "./composer";
import { CitationDialog } from "./citation-list";
import { DeleteSessionDialog, RenameSessionDialog } from "./session-list";

export function StudyAssistantChat({
  courseId,
  open,
  onClose,
  onCitationNavigate,
}: {
  courseId: string;
  open: boolean;
  onClose: () => void;
  /** Trả true nếu đã điều hướng tới slide; false để mở dialog như cũ. */
  onCitationNavigate?: (citation: ChatCitation) => boolean;
}) {
  const { mode, assignmentId, attemptId, lessonId, draftAnswers } = useAssistant();
  const { user } = useAuthState();
  const storageKey = buildChatStorageKey({
    userId: user?.id,
    courseId,
    assignmentId,
    attemptId,
    mode,
  });
  const access = useChatAccess(courseId, open || mode === "quiz");
  const allowed = access.data?.allowed === true && !access.isError;
  // undefined = chưa chọn (tự mở phiên gần nhất), null = phiên mới chưa lưu.
  const [selectedSessionId, setSelectedSessionId] = useState<string | null | undefined>(
    undefined,
  );
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [streamingText, setStreamingText] = useState("");
  const [streamingCitations, setStreamingCitations] = useState<ChatCitation[]>([]);
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [citationModal, setCitationModal] = useState<ChatCitation | null>(null);

  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const streamingTextRef = useRef("");
  const citationsRef = useRef<ChatCitation[]>([]);

  const handleClose = useCallback(() => {
    setCitationModal(null);
    setRenameOpen(false);
    setDeleteOpen(false);
    onClose();
  }, [onClose]);

  // Citation có slide: nhảy thẳng tới slide trong reader thay vì mở dialog.
  // Quiz/review giữ dialog để không làm gián đoạn bài đang làm.
  const handleCitationClick = useCallback(
    (citation: ChatCitation) => {
      if (
        mode === "reader" &&
        onCitationNavigate &&
        citation.lessonId &&
        citation.slideId &&
        onCitationNavigate(citation)
      ) {
        return;
      }
      setCitationModal(citation);
    },
    [mode, onCitationNavigate],
  );

  const sessionsQuery = useChatSessions(
    allowed && open ? courseId : null,
    assignmentId,
    attemptId,
  );
  const sessions = Array.isArray(sessionsQuery.data) ? sessionsQuery.data : [];
  // undefined = chưa chọn -> tự dùng phiên gần nhất; null = phiên mới.
  const effectiveSessionId = resolveEffectiveSessionId(selectedSessionId, sessions);

  const renameMutation = useRenameChatSession();
  const deleteMutation = useDeleteChatSession();
  const chatStream = useChatStream();
  const abortStream = chatStream.abort;
  const generation = useRef(0);
  const sending = useRef(false);
  const nearBottom = useRef(true);
  const messagesQuery = useChatMessages(allowed && open && !chatStream.streaming ? effectiveSessionId : null);

  useEffect(() => {
    abortStream();
    generation.current += 1;
    sending.current = false;
    sessionIdRef.current = null;
    let saved: string | null = null;
    try { saved = localStorage.getItem(storageKey); } catch {}
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSelectedSessionId(saved === "new" ? null : saved ?? undefined);
    setMessages([]);
    setStreamingText("");
    setStreamingCitations([]);
    streamingTextRef.current = "";
    citationsRef.current = [];
    return () => { generation.current += 1; abortStream(); };
  }, [storageKey, abortStream]);

  useEffect(() => {
    if (!allowed) abortStream();
  }, [allowed, abortStream]);

  const currentSession = sessions.find((item) => item.id === effectiveSessionId);

  useEffect(() => {
    if (!sending.current && !messagesQuery.isFetching && Array.isArray(messagesQuery.data)) {
      // Đồng bộ lịch sử từ server vào state hiển thị cục bộ (optimistic stream
      // được ghép sau). Đây là sync có chủ đích, không phải derived state.
      setMessages(toUiMessages(messagesQuery.data));
    }
  }, [messagesQuery.data, messagesQuery.isFetching]);

  useEffect(() => {
    if (!open) return;
    const timer = window.setTimeout(() => inputRef.current?.focus(), 50);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    if (!open || !nearBottom.current) return;
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [open, messages, streamingText, chatStream.status]);

  // Escape đóng panel, trả focus về nút "Trợ lý" ở header (reader xử lý focus).
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") handleClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, handleClose]);

  const resetConversation = () => {
    setMessages([]);
    setStreamingText("");
    setStreamingCitations([]);
    setError("");
    streamingTextRef.current = "";
    citationsRef.current = [];
  };

  const selectSession = (sessionId: string | null) => {
    abortStream();
    generation.current += 1;
    sending.current = false;
    try { localStorage.setItem(storageKey, sessionId ?? "new"); } catch {}
    sessionIdRef.current = sessionId;
    setSelectedSessionId(sessionId);
    resetConversation();
  };

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || sending.current || chatStream.streaming || !allowed) return;
    sending.current = true;
    const requestGeneration = generation.current;
    const active = () => requestGeneration === generation.current;

    setInput("");
    setError("");
    streamingTextRef.current = "";
    citationsRef.current = [];
    nearBottom.current = true;
    if (inputRef.current) inputRef.current.style.height = "40px";

    const userMessage: UiMessage = {
      id: newLocalId(),
      role: "student",
      content: message,
      citations: [],
    };
    const assistantId = newLocalId();
    setMessages((prev) => [
      ...prev,
      userMessage,
      { id: assistantId, role: "assistant", content: "", citations: [], pending: true },
    ]);

    let completed = false;
    try {
      await chatStream.send(
        {
          courseId,
          message,
          sessionId: sessionIdRef.current ?? effectiveSessionId,
          lessonId,
          assignmentId,
          attemptId,
          draftAnswers,
        },
        {
          onSession: (sessionId) => {
            if (!active()) return;
            sessionIdRef.current = sessionId;
            setSelectedSessionId(sessionId);
            try { localStorage.setItem(storageKey, sessionId); } catch {}
          },
          onCitations: (citations) => {
            if (!active()) return;
            citationsRef.current = citations;
            setStreamingCitations(citations);
          },
          onToken: (token) => {
            if (!active()) return;
            streamingTextRef.current += token;
            setStreamingText(streamingTextRef.current);

          },
          onDone: (data) => {
            if (!active()) return;
            completed = true;
            const finalText = streamingTextRef.current;
            const finalCitations = citationsRef.current;
            setMessages((prev) =>
              prev.map((item) =>
                item.id === assistantId
                  ? {
                      ...item,
                      content: finalText,
                      citations: finalCitations,
                      pending: false,
                    }
                  : item,
              ),
            );
            setStreamingText("");
            setStreamingCitations([]);
            if (data.sessionId) {
              sessionIdRef.current = data.sessionId;
              setSelectedSessionId(data.sessionId);
            }
            void sessionsQuery.refetch();
          },
          onError: (message) => {
            if (!active()) return;
            setError(message);
          },
        },
      );
    } catch (err) {
      if (!active()) return;
      setError(formatChatError(err));
    } finally {
      if (!active()) return;
      sending.current = false;

      if (!completed) {
        setError((previous) => previous || "Kết nối kết thúc trước khi nhận đủ câu trả lời. Hãy gửi lại câu hỏi.");
        setMessages((prev) => prev.filter((item) => item.id !== assistantId));
        setStreamingText("");
        setStreamingCitations([]);
      }
    }
  };

  const openRename = () => {
    if (!currentSession) return;
    setRenameValue(currentSession.title);
    setRenameOpen(true);
  };

  const confirmRename = () => {
    if (!currentSession) return;
    const title = normalizeSessionTitle(renameValue);
    if (!title) return;
    renameMutation.mutate(
      { sessionId: currentSession.id, title },
      { onSuccess: () => setRenameOpen(false) },
    );
  };

  const confirmDelete = () => {
    if (!currentSession) return;
    deleteMutation.mutate(currentSession.id, {
      onSuccess: () => {
        setDeleteOpen(false);
        selectSession(nextSessionAfterDelete(sessions, currentSession.id));
      },
    });
  };

  const statusLabel = getStatusLabel(chatStream.status);
  const showEmpty = messages.length === 0 && !streamingText && !chatStream.streaming;

  if (!open || !allowed) return null;

  return (
    <>
      <div
        id="assistant-panel"
        data-aoi="chatbot"
        className="@container hidden h-full w-[clamp(360px,28vw,480px)] shrink-0 flex-col overflow-hidden rounded-[20px] border border-border/80 bg-[#fdfdfa] shadow-xs xl:flex"
        role="dialog"
        aria-label="Trợ lý học tập"
      >
        <AssistantHeader
          mode={mode}
          sessions={sessions}
          currentSession={currentSession}
          onSelectSession={selectSession}
          onRename={openRename}
          onDelete={() => setDeleteOpen(true)}
          onClose={handleClose}
        />

        <MessageList
          messages={messages}
          streamingText={streamingText}
          streamingCitations={streamingCitations}
          statusLabel={statusLabel}
          error={error}
          mode={mode}
          showEmpty={showEmpty}
          onSuggestion={(suggestion) => void send(suggestion)}
          onCitationClick={handleCitationClick}
          onScroll={(event) => {
            nearBottom.current = isNearBottom(event.currentTarget);
          }}
          bottomRef={bottomRef}
        />

        <Composer
          value={input}
          onValueChange={setInput}
          onSend={(text) => void send(text)}
          streaming={chatStream.streaming}
          inputRef={inputRef}
        />
      </div>

      <CitationDialog
        citation={citationModal}
        onClose={() => setCitationModal(null)}
      />

      <RenameSessionDialog
        open={renameOpen}
        onOpenChange={setRenameOpen}
        value={renameValue}
        onValueChange={setRenameValue}
        onConfirm={confirmRename}
        pending={renameMutation.isPending}
      />

      <DeleteSessionDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        onConfirm={confirmDelete}
        loading={deleteMutation.isPending}
      />
    </>
  );
}
