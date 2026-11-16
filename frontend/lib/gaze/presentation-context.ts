import type { GazeSurface } from "./frame-protocol";

export interface PresentationContextInput {
  sessionId: string;
  lessonId: string;
  surface: GazeSurface;
  slideId: string | null;
  slideIndex: number;
}

/**
 * Khoá định danh một presentation. Đổi bài/slide/quiz hoặc tạo session mới
 * đều tạo khoá mới; response createPresentation của khoá cũ không được phép
 * ghi đè context hiện tại.
 */
export function presentationContextKey({
  sessionId,
  lessonId,
  surface,
  slideId,
  slideIndex,
}: PresentationContextInput): string {
  const content =
    surface === "quiz" ? "quiz" : `${slideIndex}:${slideId ?? ""}`;
  return `${sessionId}:${lessonId}:${surface}:${content}`;
}

interface PresentationRequestToken {
  readonly id: number;
  readonly key: string;
}

export interface PresentationEntry {
  /** Khoá context lúc entry được tạo. */
  key: string;
  /** UUID gửi lên server; giữ nguyên khi retry cùng entry. */
  clientPresentationId: string;
  /** Thời điểm slide trở thành context hiện tại. */
  enteredAt: string;
}

function newPresentationId(): string {
  const uuid = globalThis.crypto?.randomUUID?.();
  if (uuid) return uuid;
  // Fallback UUID v4 hợp lệ: backend parse clientPresentationId bằng UUID,
  // chuỗi không phải UUID sẽ bị 422.
  const bytes = new Uint8Array(16);
  if (globalThis.crypto?.getRandomValues) {
    globalThis.crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) {
      bytes[i] = Math.floor(Math.random() * 256);
    }
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((value) => value.toString(16).padStart(2, "0"));
  return [
    hex.slice(0, 4).join(""),
    hex.slice(4, 6).join(""),
    hex.slice(6, 8).join(""),
    hex.slice(8, 10).join(""),
    hex.slice(10, 16).join(""),
  ].join("-");
}

/**
 * Entry của presentation hiện tại. Cùng key thì tái sử dụng UUID/thời điểm vào
 * (retry idempotent); khác key — kể cả quay lại slide cũ — luôn cấp UUID mới
 * để server tạo content view mới thay vì ghi đè lượt xem trước đó.
 */
export function presentationEntryFor(
  current: PresentationEntry | null,
  key: string,
): PresentationEntry {
  if (current?.key === key) return current;
  return {
    key,
    clientPresentationId: newPresentationId(),
    enteredAt: new Date().toISOString(),
  };
}

/**
 * Theo dõi request presentation đang active. Mỗi lần `begin` sẽ vô hiệu hoá
 * mọi request trước đó, kể cả khi chúng resolve sau request mới.
 */
export function createPresentationRequestTracker() {
  let nextId = 0;
  let activeId = 0;
  let activeKey: string | null = null;

  return {
    begin(key: string): PresentationRequestToken {
      nextId += 1;
      activeId = nextId;
      activeKey = key;
      return { id: activeId, key };
    },
    invalidate(): void {
      nextId += 1;
      activeId = nextId;
      activeKey = null;
    },
    isActive(token: PresentationRequestToken): boolean {
      return token.id === activeId && token.key === activeKey;
    },
  };
}


