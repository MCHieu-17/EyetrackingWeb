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


