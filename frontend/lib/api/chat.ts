import { API_BASE_URL, ApiError, getAuthHeaders } from "@/lib/api/client";

/** Đọc lỗi JSON của backend và header Retry-After (nếu có). */
async function toApiError(response: Response): Promise<ApiError> {
  let message = `HTTP ${response.status}`;
  try {
    const data = (await response.json()) as {
      detail?: string | { message?: string };
      message?: string;
    };
    if (typeof data?.detail === "string") message = data.detail;
    else if (data?.detail && typeof data.detail === "object") {
      message = data.detail.message ?? message;
    } else if (typeof data?.message === "string") {
      message = data.message;
    }
  } catch {
    /* body không phải JSON */
  }
  const retryAfter = Number(response.headers.get("Retry-After"));
  return new ApiError(
    response.status,
    message,
    Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : undefined,
  );
}

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
  pdfUrl?: string;
  pageNumber?: number | null;
  snippet?: string;
  score?: number;
}

interface ChatSessionSummary {
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
  /** Bài tập đang làm/chữa (lesson_version_id). */
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
  const response = await fetch(
    `${API_BASE_URL}/api/courses/${courseId}/chat/sessions${query ? `?${query}` : ""}`,
    {
      credentials: "include",
      headers: getAuthHeaders(),
    },
  );
  if (!response.ok) throw await toApiError(response);
  const data = await response.json();
  return Array.isArray(data) ? data : [];
}

export async function listChatMessages(sessionId: string): Promise<ChatMessageItem[]> {
  const response = await fetch(`${API_BASE_URL}/api/chat/sessions/${sessionId}/messages`, {
    credentials: "include",
    headers: getAuthHeaders(),
  });
  if (!response.ok) throw await toApiError(response);
  const data = await response.json();
  return Array.isArray(data) ? data : [];
}

export async function renameChatSession(
  sessionId: string,
  title: string,
): Promise<ChatSessionSummary> {
  const response = await fetch(`${API_BASE_URL}/api/chat/sessions/${sessionId}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify({ title }),
  });
  if (!response.ok) throw await toApiError(response);
  return response.json();
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/chat/sessions/${sessionId}`, {
    method: "DELETE",
    credentials: "include",
    headers: getAuthHeaders(),
  });
  if (!response.ok) throw await toApiError(response);
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
  const { courseId, ...body } = input;
  const response = await fetch(`${API_BASE_URL}/api/courses/${courseId}/chat/stream`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    throw await toApiError(response);
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
  const response = await fetch(`${API_BASE_URL}/api/courses/${courseId}/chat/access`, {
    credentials: "include", headers: getAuthHeaders(), cache: "no-store",
  });
  if (!response.ok) throw await toApiError(response);
  return response.json();
}
