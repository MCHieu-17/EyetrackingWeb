function normalizeApiUrl(url: string): string {
  const trimmed = url.trim();
  // Rỗng = same-origin (gọi qua rewrite của Next.js).
  if (!trimmed) return "";
  if (trimmed.startsWith("/")) return trimmed;
  if (trimmed.startsWith("http")) return trimmed;
  return `https://${trimmed}`;
}

export const API_BASE_URL = normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL ?? "");

export function resolveMediaUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  if (/^https?:\/\//.test(raw)) return raw;
  if (raw.startsWith("/")) return raw;
  return `${API_BASE_URL}${raw}`;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** Giây phải chờ (header Retry-After) khi bị giới hạn tần suất. */
    public retryAfter?: number,
    /** Payload lỗi gốc từ backend (nếu có), dùng cho các trang cần chi tiết. */
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
const MAX_UPLOAD_LABEL = `${MAX_UPLOAD_BYTES / (1024 * 1024)}MB`;
/** Số trang PDF tối đa backend chấp nhận (settings.max_slide_pages). */
export const MAX_SLIDE_PAGES = 150;

interface ApiRequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined>;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  keepalive?: boolean;
  skipAuthRefresh?: boolean;
  /** Timeout cho mỗi lần fetch (ms). Mặc định 30s; 0 = không timeout. */
  timeoutMs?: number;
}

function buildUrl(path: string, params?: ApiRequestOptions["params"]) {
  let url = path;
  if (params) {
    const searchParams = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) searchParams.set(k, String(v));
    }
    const queryString = searchParams.toString();
    url = queryString ? `${path}?${queryString}` : path;
  }
  return url;
}

let memoryAccessToken: string | null = null;

export function setMemoryAccessToken(token: string | null): void {
  memoryAccessToken = token;
}

export function clearMemoryToken(): void {
  memoryAccessToken = null;
}

function getAuthHeader(): Record<string, string> {
  return memoryAccessToken ? { Authorization: `Bearer ${memoryAccessToken}` } : {};
}

/** Đọc CSRF token từ cookie; null nếu không có hoặc không chạy trong browser. */
export function readCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/);
  return m ? decodeURIComponent(m[1]) : null;
}

function getCsrfHeader(): Record<string, string> {
  const token = readCsrfToken();
  return token ? { "X-CSRF-Token": token } : {};
}

// One-time migration from versions that persisted credentials in browser storage.
if (typeof window !== "undefined") {
  try {
    for (const key of ["auth_token", "refresh_token", "auth_user"]) {
      globalThis.localStorage?.removeItem(key);
    }
  } catch {
    /* Storage may be unavailable or blocked. */
  }
}

async function tryRefresh(): Promise<boolean> {
  try {
    const csrf = readCsrfToken();
    const res = await fetch(`/api/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(csrf !== null ? { "X-CSRF-Token": csrf } : {}),
      },
      body: JSON.stringify({}),
    });
    if (!res.ok) return false;
    const data = await res.json();
    if (data?.accessToken) {
      memoryAccessToken = data.accessToken;
    } else if (data?.access_token) {
      memoryAccessToken = data.access_token;
    }
    return true;
  } catch {
    return false;
  }
}

let inFlightRefresh: Promise<boolean> | null = null;
function refreshAccessToken(): Promise<boolean> {
  if (!inFlightRefresh) {
    inFlightRefresh = tryRefresh().finally(() => {
      inFlightRefresh = null;
    });
  }
  return inFlightRefresh;
}

export const AUTH_CHANGE_EVENT = "gaze-auth-change";

function notifyAuthChange(): void {
  globalThis.window?.dispatchEvent(
    new CustomEvent(AUTH_CHANGE_EVENT, { detail: "session-expired" }),
  );
}

function extractError(status: number, data: unknown): string {
  const d = data as
    | { detail?: string | { code?: string; message?: string }; message?: string }
    | null;
  if (typeof d?.detail === "string") return d.detail;
  if (d?.detail && typeof d.detail === "object") {
    return d.detail.message ?? d.detail.code ?? `HTTP ${status}`;
  }
  return d?.message ?? `HTTP ${status}`;
}

/** Đọc lỗi JSON của backend và header Retry-After (nếu có). */
export async function parseApiError(response: Response): Promise<ApiError> {
  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    /* body không phải JSON */
  }
  const message = extractError(response.status, data);
  const retryAfter = Number(response.headers.get("Retry-After"));
  return new ApiError(
    response.status,
    message,
    Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : undefined,
    data,
  );
}

/**
 * Gọi fetch, tự refresh token một lần khi gặp 401 rồi thử lại.
 * Dùng chung cho JSON và multipart để hai luồng có cùng hành vi auth.
 */
async function fetchWithAuthRetry(
  doFetch: () => Promise<Response>,
  skipAuthRefresh = false,
): Promise<Response> {
  let res = await doFetch();
  if (res.status === 401 && !skipAuthRefresh) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      res = await doFetch();
    } else {
      clearMemoryToken();
      notifyAuthChange();
    }
  }
  return res;
}

export async function apiFetch<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const {
    method = "GET",
    body,
    params,
    headers,
    signal,
    keepalive,
    skipAuthRefresh = false,
    timeoutMs = 30_000,
  } = options;

  const doFetch = (): Promise<Response> => {
    const canTimeout =
      timeoutMs > 0 &&
      typeof AbortSignal !== "undefined" &&
      typeof AbortSignal.timeout === "function";
    const timeoutSignal = canTimeout
      ? AbortSignal.timeout(timeoutMs)
      : undefined;
    // Caller signal không được vô hiệu hoá timeout; gộp cả hai khi có thể.
    const requestSignal =
      signal && timeoutSignal && typeof AbortSignal.any === "function"
        ? AbortSignal.any([signal, timeoutSignal])
        : (signal ?? timeoutSignal);
    return fetch(buildUrl(path, params), {
      method,
      signal: requestSignal,
      keepalive,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeader(),
        ...getCsrfHeader(),
        ...headers,
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
  };

  const res = await fetchWithAuthRetry(doFetch, skipAuthRefresh);

  if (!res.ok) {
    throw await parseApiError(res);
  }
  return res.json() as Promise<T>;
}

/**
 * Fetch một response dạng stream (SSE) với auth/CSRF/refresh dùng chung.
 * Caller tự đọc body và xử lý lỗi HTTP.
 */
export async function apiFetchStream(
  path: string,
  options: Pick<ApiRequestOptions, "method" | "body" | "signal" | "headers"> = {},
): Promise<Response> {
  const { method = "POST", body, signal, headers } = options;
  const doFetch = (): Promise<Response> =>
    fetch(buildUrl(path), {
      method,
      signal,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeader(),
        ...getCsrfHeader(),
        ...headers,
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
  return fetchWithAuthRetry(doFetch);
}

export async function apiFetchMultipart<T>(
  path: string,
  form: FormData,
  method: "POST" | "PUT" | "PATCH" = "POST",
): Promise<T> {
  const doFetch = (): Promise<Response> =>
    fetch(buildUrl(path), {
      method,
      credentials: "include",
      headers: { ...getAuthHeader(), ...getCsrfHeader() },
      body: form,
    });

  const res = await fetchWithAuthRetry(doFetch);

  if (!res.ok) {
    if (res.status === 413) {
      throw new ApiError(413, `File tải lên vượt quá ${MAX_UPLOAD_LABEL} cho phép.`);
    }
    // Upload đã chuyển sang job queue; 524/504 thường do mạng/proxy, không phải
    // do chờ LibreOffice. Vẫn báo rõ để người dùng thử lại.
    if (res.status === 524 || res.status === 504) {
      throw new ApiError(
        res.status,
        "Máy chủ phản hồi quá lâu. Vui lòng thử lại với file nhỏ hơn.",
      );
    }
    throw await parseApiError(res);
  }
  return res.json() as Promise<T>;
}


