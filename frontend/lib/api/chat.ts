import { API_BASE_URL, ApiError, getAuthHeaders } from "@/lib/api/client";
import { isDemoMode } from "@/lib/demo-mode";

export interface ChatCitation {
  documentId: string;
  courseVersionId?: string | null;
  lessonVersionId?: string | null;
  slideVersionId?: string | null;
  membershipId?: string | null;
  assetId?: string | null;
  title: string;
  location: string;
  lessonId?: string | null;
  lessonTitle?: string;
  slideId?: string | null;
  slideIndex?: number | null;
  imageUrl?: string;
  pdfUrl?: string;
  pageNumber?: number | null;
  snippet?: string;
  score?: number;
}

export interface ChatReply {
  sessionId: string;
  answer: string;
  citations: ChatCitation[];
  intent?: string | null;
  verified?: boolean;
}

export interface ChatSessionSummary {
  canContinue?: boolean;
  id: string;
  courseId: string;
  courseVersionId?: string | null;
  lessonId: string | null;
  lessonVersionId?: string | null;
  assignmentId: string | null;
  attemptId?: string | null;
  title: string;
  messageCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface ChatMessageItem {
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
  /** Bài tập đang làm/chữa (lesson_version_id). */
  assignmentId?: string | null;
  /** Lượt làm cụ thể; bắt buộc để hint/review đúng attempt. */
  attemptId?: string | null;
  draftAnswers?: Record<string, string[]>;
}

export interface ChatBlockMeta { route?: string; block_id?: string | number; }

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

// ---------------------------------------------------------------------------
// Demo mode: giữ widget hoạt động khi NEXT_PUBLIC_DEMO=1 (không có backend).
// ---------------------------------------------------------------------------

const demoState: {
  sessions: ChatSessionSummary[];
  messages: Record<string, ChatMessageItem[]>;
} = { sessions: [], messages: {} };

function demoNow(): string {
  return new Date().toISOString();
}

function demoId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

function demoReply(input: SendChatInput): ChatReply {
  const sessionId = input.sessionId || demoId("demo-session");
  let session = demoState.sessions.find((item) => item.id === sessionId);
  if (!session) {
    session = {
      id: sessionId,
      courseId: input.courseId,
      lessonId: input.lessonId ?? null,
      assignmentId: input.assignmentId ?? null,
      title: input.message.slice(0, 60) || "Phiên mới",
      messageCount: 0,
      createdAt: demoNow(),
      updatedAt: demoNow(),
    };
    demoState.sessions.unshift(session);
    demoState.messages[sessionId] = [];
  }

  const studentMessage: ChatMessageItem = {
    id: demoId("demo-msg"),
    role: "student",
    content: input.message,
    citations: [],
    createdAt: demoNow(),
  };
  const answer =
    "Đây là câu trả lời demo. Trong chế độ thật, trợ lý sẽ tìm trong tài liệu môn học và trích dẫn nguồn [1]. " +
    "Bạn có thể hỏi về khái niệm, hoặc xin gợi ý cho bài tập — trợ lý sẽ không giải hộ.";
  const citation: ChatCitation = {
    documentId: "demo-slide-1",
    title: "Chương 1 - Bài 1: Giới thiệu",
    location: "",
    lessonId: input.lessonId ?? null,
    lessonTitle: "Bài 1: Giới thiệu",
    slideId: "demo-slide-1",
    slideIndex: 1,
    imageUrl: "",
    pdfUrl: "",
    pageNumber: 1,
    snippet: "Nội dung demo của slide.",
    score: 0.9,
  };
  const assistantMessage: ChatMessageItem = {
    id: demoId("demo-msg"),
    role: "assistant",
    content: answer,
    citations: [citation],
    intent: "course_qa",
    createdAt: demoNow(),
  };
  demoState.messages[sessionId].push(studentMessage, assistantMessage);
  session.messageCount += 2;
  session.updatedAt = demoNow();

  return {
    sessionId,
    answer,
    citations: [citation],
    intent: "course_qa",
    verified: true,
  };
}

// ---------------------------------------------------------------------------
// API thật
// ---------------------------------------------------------------------------

export async function listChatSessions(
  courseId: string,
  assignmentId?: string | null,
  attemptId?: string | null,
): Promise<ChatSessionSummary[]> {
  if (isDemoMode()) {
    return demoState.sessions.filter((item) => item.courseId === courseId);
  }
  const params = new URLSearchParams();
  if (assignmentId) params.set("assignmentId", assignmentId);
  if (attemptId) params.set("attemptId", attemptId);
  const query = params.toString();
  const response = await fetch(
    `${API_BASE_URL}/api/courses/${courseId}/chat/sessions${query ? `?${query}` : ""}`,
    {
      credentials: "include",
      headers: getAuthHeaders(),
    },
  );
  if (!response.ok) throw new ApiError(response.status, await response.text());
  const data = await response.json();
  return Array.isArray(data) ? data : [];
}

export async function listChatMessages(sessionId: string): Promise<ChatMessageItem[]> {
  if (isDemoMode()) return demoState.messages[sessionId] ?? [];
  const response = await fetch(`${API_BASE_URL}/api/chat/sessions/${sessionId}/messages`, {
    credentials: "include",
    headers: getAuthHeaders(),
  });
  if (!response.ok) throw new ApiError(response.status, await response.text());
  const data = await response.json();
  return Array.isArray(data) ? data : [];
}

export async function sendChatMessage(input: SendChatInput): Promise<ChatReply> {
  if (isDemoMode()) return demoReply(input);
  const { courseId, ...body } = input;
  const response = await fetch(`${API_BASE_URL}/api/courses/${courseId}/chat`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new ApiError(response.status, await response.text());
  return response.json();
}

export async function renameChatSession(
  sessionId: string,
  title: string,
): Promise<ChatSessionSummary> {
  if (isDemoMode()) {
    const session = demoState.sessions.find((item) => item.id === sessionId);
    if (!session) throw new ApiError(404, "Không tìm thấy phiên chat");
    session.title = title;
    session.updatedAt = demoNow();
    return session;
  }
  const response = await fetch(`${API_BASE_URL}/api/chat/sessions/${sessionId}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) throw new ApiError(response.status, await response.text());
  return response.json();
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  if (isDemoMode()) {
    demoState.sessions = demoState.sessions.filter((item) => item.id !== sessionId);
    delete demoState.messages[sessionId];
    return;
  }
  const response = await fetch(`${API_BASE_URL}/api/chat/sessions/${sessionId}`, {
    method: "DELETE",
    credentials: "include",
    headers: getAuthHeaders(),
  });
  if (!response.ok) throw new ApiError(response.status, await response.text());
}

export function parseFrame(frame: string, handlers: ChatStreamHandlers): void {
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
      handlers.onCitations?.((data.citations as ChatCitation[]) ?? []);
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
  if (isDemoMode()) {
    const reply = demoReply(input);
    handlers.onSession?.(reply.sessionId);
    handlers.onCitations?.(reply.citations);
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
    handlers.onToken?.(reply.answer, { route: "knowledge", block_id: 0 });
    handlers.onDone?.({
      sessionId: reply.sessionId,
      intent: reply.intent ?? undefined,
      verified: reply.verified,
    });
    return;
  }

  const { courseId, ...body } = input;
  const response = await fetch(`${API_BASE_URL}/api/courses/${courseId}/chat/stream`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    throw new ApiError(response.status, await response.text());
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

export interface ChatAccess {
  allowed: boolean;
  reason: string | null;
  blockedUntil: string | null;
}

export async function getChatAccess(courseId: string): Promise<ChatAccess> {
  if (isDemoMode()) return { allowed: true, reason: null, blockedUntil: null };
  const response = await fetch(`${API_BASE_URL}/api/courses/${courseId}/chat/access`, {
    credentials: "include", headers: getAuthHeaders(), cache: "no-store",
  });
  if (!response.ok) throw new ApiError(response.status, await response.text());
  return response.json();
}
