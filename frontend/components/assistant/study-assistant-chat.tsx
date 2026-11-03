"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  RiAddLine,
  RiChatHistoryLine,
  RiCloseLine,
  RiDeleteBinLine,
  RiEditLine,
  RiSendPlane2Line,
  RiSparkling2Line,
} from "@remixicon/react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { resolveMediaUrl } from "@/lib/api/client";
import type { ChatCitation } from "@/lib/api/chat";
import {
  useChatMessages,
  useChatSessions,
  useChatStream,
  useDeleteChatSession,
  useRenameChatSession,
} from "@/hooks/use-chat";

type UiMessage = {
  id: string;
  role: "student" | "assistant";
  content: string;
  citations: ChatCitation[];
  pending?: boolean;
};

const MARKDOWN_CLASS = cn(
  "text-sm leading-6 break-words",
  "[&_p]:my-1.5 [&_strong]:font-semibold [&_em]:italic",
  "[&_ul]:my-1.5 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-1.5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-0.5",
  "[&_h1]:mt-3 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:mt-3 [&_h2]:text-sm [&_h2]:font-semibold [&_h3]:mt-2 [&_h3]:font-semibold",
  "[&_code]:rounded [&_code]:bg-black/5 [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-[0.85em]",
  "[&_pre]:my-2 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-neutral-900 [&_pre]:p-3 [&_pre]:text-xs [&_pre]:text-white",
  "[&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:text-inherit",
  "[&_table]:my-2 [&_table]:w-full [&_table]:border-collapse [&_table]:text-xs",
  "[&_th]:border [&_th]:border-border [&_th]:bg-muted [&_th]:px-2 [&_th]:py-1 [&_th]:text-left",
  "[&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1",
  "[&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground",
  "[&_hr]:my-3 [&_img]:max-w-full [&_img]:rounded-lg",
  "[&_a]:font-medium [&_a]:text-[#36533a] [&_a]:underline [&_a]:underline-offset-2",
);

const CITE_RE = /\[(\d+)\](?!\()/g;

const STATUS_LABEL: Record<string, string> = {
  routing: "Đang phân loại câu hỏi…",
  retrieving: "Đang tìm trong tài liệu môn học…",
  generating: "Đang soạn câu trả lời…",
  verifying: "Đang kiểm tra trích dẫn…",
  retrying: "Đang sửa lại câu trả lời…",
};

function newLocalId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

/** Biến `[1]` trong câu trả lời thành liên kết mở citation tương ứng. */
function withCitationLinks(text: string, messageId: string): string {
  return text.replace(CITE_RE, `[$1](#chat-cite-${messageId}-$1)`);
}

function CitationChip({
  index,
  citation,
  onClick,
}: {
  index: number;
  citation: ChatCitation;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex max-w-full items-center truncate rounded-full border border-border bg-white px-2.5 py-1 text-[11px] font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground"
      title={citation.title}
    >
      [{index}] {citation.title}
    </button>
  );
}

function Markdown({
  text,
  messageId,
  citations,
  onCitationClick,
}: {
  text: string;
  messageId: string;
  citations: ChatCitation[];
  onCitationClick: (citation: ChatCitation) => void;
}) {
  return (
    <div className={MARKDOWN_CLASS}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            if (href?.startsWith("#chat-cite-")) {
              const index = Number(href.split("-").pop());
              const citation = citations[index - 1];
              if (citation) {
                return (
                  <button
                    type="button"
                    className="mx-0.5 inline-flex min-w-4 items-center justify-center rounded border border-current px-1 text-[10px] align-super font-semibold"
                    onClick={() => onCitationClick(citation)}
                    aria-label={`Xem nguồn trích dẫn ${index}`}
                  >
                    {children}
                  </button>
                );
              }
            }
            return (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {withCitationLinks(text, messageId)}
      </ReactMarkdown>
    </div>
  );
}

export function StudyAssistantChat({
  courseId,
  lessonId = null,
  assignmentId = null,
  mode = "reader",
}: {
  courseId: string;
  lessonId?: string | null;
  assignmentId?: string | null;
  mode?: "reader" | "quiz" | "review";
}) {
  const [open, setOpen] = useState(false);
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

  const sessionsQuery = useChatSessions(courseId);
  const sessions = Array.isArray(sessionsQuery.data) ? sessionsQuery.data : [];
  // undefined = chưa chọn -> tự dùng phiên gần nhất; null = phiên mới.
  const effectiveSessionId =
    selectedSessionId === undefined ? (sessions[0]?.id ?? null) : selectedSessionId;
  const messagesQuery = useChatMessages(effectiveSessionId);
  const renameMutation = useRenameChatSession();
  const deleteMutation = useDeleteChatSession();
  const chatStream = useChatStream();

  const currentSession = sessions.find((item) => item.id === effectiveSessionId);

  useEffect(() => {
    if (Array.isArray(messagesQuery.data)) {
      // Đồng bộ lịch sử từ server vào state hiển thị cục bộ (optimistic stream
      // được ghép sau). Đây là sync có chủ đích, không phải derived state.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setMessages(
        messagesQuery.data.map((message) => ({
          id: message.id,
          role: message.role,
          content: message.content,
          citations: message.citations ?? [],
        })),
      );
    }
  }, [messagesQuery.data]);

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, streamingText, chatStream.status]);

  const resetConversation = () => {
    setMessages([]);
    setStreamingText("");
    setStreamingCitations([]);
    setError("");
    streamingTextRef.current = "";
    citationsRef.current = [];
  };

  const selectSession = (sessionId: string | null) => {
    setSelectedSessionId(sessionId);
    resetConversation();
  };

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || chatStream.streaming) return;

    setInput("");
    setError("");
    resetConversation();

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
        },
        {
          onSession: (sessionId) => {
            sessionIdRef.current = sessionId;
          },
          onCitations: (citations) => {
            citationsRef.current = citations;
            setStreamingCitations(citations);
          },
          onToken: (token) => {
            streamingTextRef.current += token;
            setStreamingText(streamingTextRef.current);
          },
          onDone: (data) => {
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
            setError(message);
          },
        },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Trợ lý học tập tạm thời không phản hồi");
    } finally {
      if (!completed) {
        setMessages((prev) => prev.filter((item) => item.id !== assistantId));
        setStreamingText("");
        setStreamingCitations([]);
      }
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void send(input);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(input);
    }
  };

  const openRename = () => {
    if (!currentSession) return;
    setRenameValue(currentSession.title);
    setRenameOpen(true);
  };

  const confirmRename = () => {
    if (!currentSession) return;
    const title = renameValue.trim();
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
        const next = sessions.find((item) => item.id !== currentSession.id);
        selectSession(next?.id ?? null);
      },
    });
  };

  const statusLabel = chatStream.status ? STATUS_LABEL[chatStream.status] : null;
  const showEmpty = messages.length === 0 && !streamingText && !chatStream.streaming;

  return (
    <>
      <button
        type="button"
        data-aoi="chat-open-button"
        onClick={() => setOpen((value) => !value)}
        className={cn(
          "fixed bottom-5 right-5 z-40 flex size-14 items-center justify-center rounded-full bg-[#36533a] text-white shadow-lg transition hover:scale-105 hover:bg-[#2c4530] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          open && "hidden",
        )}
        aria-label="Mở trợ lý học tập"
        aria-expanded={open}
      >
        <RiSparkling2Line className="size-6" />
      </button>

      {open && (
        <div
          data-aoi="chatbot"
          className="fixed inset-0 z-50 flex flex-col bg-[#fdfdfa] sm:inset-auto sm:bottom-5 sm:right-5 sm:h-[min(680px,calc(100vh-2.5rem))] sm:w-[430px] sm:rounded-[24px] sm:border sm:border-border sm:shadow-2xl"
          role="dialog"
          aria-label="Trợ lý học tập"
        >
          <header data-aoi="chat-header" className="flex items-center gap-2 border-b border-border px-4 py-3">
            <div className="flex size-9 items-center justify-center rounded-full bg-[#e8efe6] text-[#36533a]">
              <RiSparkling2Line className="size-5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">Trợ lý học tập</p>
              <p className="truncate text-[11px] text-muted-foreground">
                {mode === "quiz"
                  ? "Gợi ý bài tập · không giải hộ"
                  : mode === "review"
                    ? "Chữa bài đã nộp · có đáp án"
                    : "Hỏi đáp trong môn học"}
              </p>
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="Lịch sử phiên chat">
                  <RiChatHistoryLine className="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-72">
                <DropdownMenuLabel>Phiên chat</DropdownMenuLabel>
                <DropdownMenuItem onSelect={() => selectSession(null)}>
                  <RiAddLine className="mr-2 size-4" />
                  Phiên mới
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                {sessions.length === 0 && (
                  <p className="px-2 py-3 text-xs text-muted-foreground">Chưa có phiên nào.</p>
                )}
                {sessions.map((session) => (
                  <DropdownMenuItem
                    key={session.id}
                    onSelect={() => selectSession(session.id)}
                    className="flex items-center justify-between gap-2"
                  >
                    <span className="min-w-0 flex-1 truncate">{session.title}</span>
                    <span className="text-[10px] text-muted-foreground">
                      {session.messageCount}
                    </span>
                  </DropdownMenuItem>
                ))}
                {currentSession && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onSelect={openRename}>
                      <RiEditLine className="mr-2 size-4" />
                      Đổi tên phiên
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onSelect={() => setDeleteOpen(true)}
                      className="text-destructive focus:text-destructive"
                    >
                      <RiDeleteBinLine className="mr-2 size-4" />
                      Xoá phiên
                    </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>

            <Button
              variant="ghost"
              size="icon"
              onClick={() => setOpen(false)}
              aria-label="Đóng trợ lý"
            >
              <RiCloseLine className="size-4" />
            </Button>
          </header>

          <div data-aoi="chat-messages" className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
            {showEmpty && (
              <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
                <div className="flex size-14 items-center justify-center rounded-full bg-[#e8efe6] text-[#36533a]">
                  <RiSparkling2Line className="size-7" />
                </div>
                <div>
                  <p className="text-sm font-semibold">Mình có thể giúp gì?</p>
                  <p className="mt-1 max-w-xs text-xs text-muted-foreground">
                    {mode === "quiz"
                      ? "Mình sẽ gợi ý từng bước, không đưa đáp án cuối hay lời giải hoàn chỉnh."
                      : mode === "review"
                        ? "Hỏi về bài đã nộp. Mình có thể giải thích đáp án và chỉ ra lỗi sai."
                        : "Hỏi về khái niệm trong bài. Câu trả lời sẽ kèm trích dẫn slide liên quan."}
                  </p>
                </div>
                <div className="flex w-full max-w-xs flex-col gap-2">
                  {(mode === "quiz"
                    ? [
                        "Cho mình gợi ý cho câu này",
                        "Giải thích khái niệm liên quan",
                        "Mình đang làm sai ở bước nào?",
                      ]
                    : mode === "review"
                      ? [
                          "Giải thích đáp án đúng",
                          "Vì sao mình sai câu này?",
                          "Tóm tắt kiến thức liên quan",
                        ]
                      : [
                          "Tóm tắt nội dung chính của bài này",
                          "Giải thích khái niệm quan trọng nhất",
                          "Mình nên học phần nào trước?",
                        ]
                  ).map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => void send(suggestion)}
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
                <div
                  key={message.id}
                  className={cn(
                    "flex flex-col gap-1.5",
                    message.role === "student" ? "items-end" : "items-start",
                  )}
                >
                  <div
                    data-aoi={
                      message.role === "student"
                        ? "chat-user-message"
                        : "chat-ai-message"
                    }
                    className={cn(
                      "max-w-[92%] rounded-2xl px-3.5 py-2.5",
                      message.role === "student"
                        ? "bg-[#36533a] text-white"
                        : "border border-border bg-white text-foreground",
                    )}
                  >
                    {message.role === "student" ? (
                      <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
                    ) : message.pending && !message.content ? (
                      <p className="text-sm text-muted-foreground">
                        {statusLabel ?? "Đang xử lý…"}
                      </p>
                    ) : (
                      <Markdown
                        text={message.content}
                        messageId={message.id}
                        citations={message.citations}
                        onCitationClick={setCitationModal}
                      />
                    )}
                  </div>
                  {message.role === "assistant" && message.citations.length > 0 && (
                    <div className="flex max-w-[92%] flex-wrap gap-1.5">
                      {message.citations.map((citation, index) => (
                        <CitationChip
                          key={`${message.id}-${citation.documentId}-${index}`}
                          index={index + 1}
                          citation={citation}
                          onClick={() => setCitationModal(citation)}
                        />
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {chatStream.streaming && (
                <div className="flex flex-col gap-1.5 items-start">
                  <div
                    data-aoi="chat-ai-message"
                    className="max-w-[92%] rounded-2xl border border-border bg-white px-3.5 py-2.5"
                  >
                    {streamingText ? (
                      <Markdown
                        text={streamingText}
                        messageId="streaming"
                        citations={streamingCitations}
                        onCitationClick={setCitationModal}
                      />
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        {statusLabel ?? "Đang xử lý…"}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {error && (
                <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
                  {error}
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </div>

          <form data-aoi="chat-input" onSubmit={onSubmit} className="border-t border-border p-3">
            <div className="flex items-end gap-2">
              <Textarea
                ref={inputRef}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={onKeyDown}
                placeholder={
                  mode === "quiz"
                    ? "Hỏi gợi ý cho bài tập… (Enter để gửi)"
                    : mode === "review"
                      ? "Hỏi về bài đã nộp… (Enter để gửi)"
                      : "Hỏi về nội dung bài học… (Enter để gửi)"
                }
                rows={1}
                className="max-h-32 min-h-10 flex-1 resize-none rounded-2xl py-2.5"
                disabled={chatStream.streaming}
              />
              <Button
                type="submit"
                data-aoi="chat-send"
                size="icon"
                className="size-10 shrink-0 rounded-full"
                disabled={!input.trim() || chatStream.streaming}
                aria-label="Gửi câu hỏi"
              >
                <RiSendPlane2Line className="size-4" />
              </Button>
            </div>
            <p className="mt-1.5 px-1 text-[10px] text-muted-foreground">
              Trợ lý không giải bài hộ. Câu trả lời dựa trên tài liệu môn học và có trích dẫn.
            </p>
          </form>
        </div>
      )}

      <Dialog open={Boolean(citationModal)} onOpenChange={(value) => !value && setCitationModal(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>{citationModal?.title ?? "Nguồn trích dẫn"}</DialogTitle>
            <DialogDescription>
              {citationModal?.lessonTitle || "Slide trong môn học"}
              {citationModal?.slideIndex ? ` · Slide ${citationModal.slideIndex}` : ""}
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[60vh] overflow-auto px-6 pb-6">
            {citationModal?.imageUrl || citationModal?.location ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={
                  resolveMediaUrl(citationModal.imageUrl || citationModal.location) ?? undefined
                }
                alt={citationModal.title}
                className="w-full rounded-xl border border-border"
              />
            ) : (
              <p className="rounded-xl border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
                {citationModal?.snippet || "Không có ảnh slide cho nguồn này."}
              </p>
            )}
            {citationModal?.snippet && (citationModal?.imageUrl || citationModal?.location) && (
              <p className="mt-3 text-xs leading-5 text-muted-foreground">
                {citationModal.snippet}
              </p>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Đổi tên phiên chat</DialogTitle>
          </DialogHeader>
          <div className="px-6 pb-4">
            <Textarea
              value={renameValue}
              onChange={(event) => setRenameValue(event.target.value)}
              rows={2}
              maxLength={255}
            />
          </div>
          <div className="flex justify-end gap-2 border-t border-border p-4">
            <Button variant="outline" onClick={() => setRenameOpen(false)}>
              Hủy
            </Button>
            <Button
              onClick={confirmRename}
              disabled={!renameValue.trim() || renameMutation.isPending}
            >
              Lưu
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Xoá phiên chat?"
        description="Toàn bộ tin nhắn trong phiên này sẽ bị xoá và không thể khôi phục."
        confirmLabel="Xoá"
        destructive
        loading={deleteMutation.isPending}
        onConfirm={confirmDelete}
      />
    </>
  );
}
