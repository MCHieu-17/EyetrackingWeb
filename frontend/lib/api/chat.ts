import { apiFetch, apiFetchStream, parseApiError } from "@/lib/api/client";

export interface ChatCitation {
  documentId: string;
  assetId?: string | null;
  title: string;
  location: string;
  lessonId?: string | null;
  lessonTitle?: string;
  slideId?: string | null;
  slideIndex?: number | null;
  pdfUrl?: string;
  pageNumber?: number | null;
  snippet?: string;
  score?: number;
}

interface ChatSessionSummary {
  canContinue?: boolean;
  id: string;
  courseId: string;
  lessonId: string | null;
  assignmentId: string | null;
  attemptId?: string | null;
  title: string;
  messageCount: number;
  createdAt: string;
  updatedAt: string;
}

interface ChatMessageItem {
  id: string;
  role: "student" | "assistant";
  content: string;
  citations: ChatCitation[];
  intent?: string | null;
  createdAt: string;
}

export interface SendChatInput {
  courseId: string;
  message: string;
  /** Bỏ trống để tạo phiên mới. */
  sessionId?: string | null;
  /** Bài học đang học (chỉ dùng làm ngữ cảnh prompt). */
  lessonId?: string | null;
  /** Bài tập đang làm/chữa; giá trị là lessons.id. */
  assignmentId?: string | null;
  /** Lượt làm cụ thể; bắt buộc để hint/review đúng attempt. */
  attemptId?: string | null;
  draftAnswers?: Record<string, string[]>;
}

interface ChatBlockMeta { route?: string; block_id?: string | number; }

export interface ChatStreamHandlers {
  onSession?: (sessionId: string) => void;
  onStatus?: (stage: string) => void;
  onCitations?: (citations: ChatCitation[]) => void;
  onToken?: (text: string, meta?: ChatBlockMeta) => void;
  onDone?: (data: {
    sessionId?: string;
    messageId?: string;
    intent?: string;
    verified?: boolean;
    routes?: string[];
    finish_reason?: string;
  }) => void;
  onError?: (message: string) => void;
}

export async function listChatSessions(
  courseId: string,
  assignmentId?: string | null,
  attemptId?: string | null,
): Promise<ChatSessionSummary[]> {
  const params = new URLSearchParams();
  if (assignmentId) params.set("assignmentId", assignmentId);
  if (attemptId) params.set("attemptId", attemptId);
  const query = params.toString();
  const path = `/api/courses/${courseId}/chat/sessions${query ? `?${query}` : ""}`;
  const data = await apiFetch<ChatSessionSummary[]>(path);
  return Array.isArray(data) ? data : [];
}

export async function listChatMessages(sessionId: string): Promise<ChatMessageItem[]> {
  const data = await apiFetch<ChatMessageItem[]>(
    `/api/chat/sessions/${sessionId}/messages`,
  );
  return Array.isArray(data) ? data : [];
}

export async function renameChatSession(
  sessionId: string,
  title: string,
): Promise<ChatSessionSummary> {
  return apiFetch<ChatSessionSummary>(`/api/chat/sessions/${sessionId}`, {
    method: "PATCH",
    body: { title },
  });
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  await apiFetch(`/api/chat/sessions/${sessionId}`, { method: "DELETE" });
}

function optionalString(value: unknown): string | null | undefined {
  if (value === null) return null;
  return typeof value === "string" ? value : undefined;
}

function optionalNumber(value: unknown): number | null | undefined {
  if (value === null) return null;
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function parseCitation(value: unknown): ChatCitation | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  if (
    typeof item.documentId !== "string" ||
    typeof item.title !== "string" ||
    typeof item.location !== "string"
  ) {
    return null;
  }
  return {
    documentId: item.documentId,
    assetId: optionalString(item.assetId),
    title: item.title,
    location: item.location,
    lessonId: optionalString(item.lessonId),
    lessonTitle: optionalString(item.lessonTitle) ?? undefined,
    slideId: optionalString(item.slideId),
    slideIndex: optionalNumber(item.slideIndex),
    pdfUrl: optionalString(item.pdfUrl) ?? undefined,
    pageNumber: optionalNumber(item.pageNumber),
    snippet: optionalString(item.snippet) ?? undefined,
    score: optionalNumber(item.score) ?? undefined,
  };
}

function parseFrame(frame: string, handlers: ChatStreamHandlers): void {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return;

  let data: Record<string, unknown>;
  try {
    data = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
  } catch {
    return;
  }

  switch (event) {
    case "session":
      handlers.onSession?.(String(data.sessionId ?? ""));
      break;
    case "status":
      handlers.onStatus?.(String(data.stage ?? ""));
      break;
    case "citations":
      handlers.onCitations?.(
        Array.isArray(data.citations)
          ? data.citations
              .map(parseCitation)
              .filter((item): item is ChatCitation => item !== null)
          : [],
      );
      break;
    case "token":
      handlers.onToken?.(String(data.text ?? ""), { route: typeof data.route === "string" ? data.route : undefined, block_id: typeof data.block_id === "string" || typeof data.block_id === "number" ? data.block_id : undefined });
      break;
    case "done":
      handlers.onDone?.({
        sessionId: data.sessionId ? String(data.sessionId) : undefined,
        messageId: data.messageId ? String(data.messageId) : undefined,
        intent: data.intent ? String(data.intent) : undefined,
        verified: typeof data.verified === "boolean" ? data.verified : undefined,
        routes: Array.isArray(data.routes) ? data.routes.map(String) : undefined,
        finish_reason: typeof data.finish_reason === "string" ? data.finish_reason : undefined,
      });
      break;
    case "error":
      handlers.onError?.(String(data.message ?? "Trợ lý học tập tạm thời không phản hồi"));
      break;
    default:
      break;
  }
}

export async function streamChatMessage(
  input: SendChatInput,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const { courseId, ...body } = input;
  const response = await apiFetchStream(`/api/courses/${courseId}/chat/stream`, {
    body,
    signal,
  });

  if (!response.ok) {
    throw await parseApiError(response);
  }
  if (!response.body) {
    throw new Error("Trình duyệt không hỗ trợ streaming");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      if (frame.trim()) parseFrame(frame, handlers);
      boundary = buffer.indexOf("\n\n");
    }
  }

  if (buffer.trim()) parseFrame(buffer, handlers);
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

interface ChatAccess {
  allowed: boolean;
  reason: string | null;
  blockedUntil: string | null;
}

export async function getChatAccess(courseId: string): Promise<ChatAccess> {
  return apiFetch<ChatAccess>(`/api/courses/${courseId}/chat/access`);
}
