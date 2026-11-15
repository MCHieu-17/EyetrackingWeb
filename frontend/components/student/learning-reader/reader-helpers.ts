export interface GazeDotPosition {
  x: number;
  y: number;
  key: string;
}

export function hashPayload(value: unknown): string {
  const text = JSON.stringify(value);
  let h1 = 0x811c9dc5;
  let h2 = 0x01000193;
  for (let i = 0; i < text.length; i += 1) {
    const code = text.charCodeAt(i);
    h1 = Math.imul(h1 ^ code, 0x01000193) >>> 0;
    h2 = Math.imul(h2 ^ code, 0x85ebca6b) >>> 0;
  }
  return (
    h1.toString(16).padStart(8, "0").repeat(4) +
    h2.toString(16).padStart(8, "0").repeat(4)
  );
}

export function resolveActiveLessonId({
  requestedLessonId,
  activeLessonId,
  lessons,
}: {
  requestedLessonId: string | null;
  activeLessonId: string;
  lessons: readonly { id: string }[];
}): string {
  if (lessons.length === 0) return activeLessonId;
  if (
    requestedLessonId &&
    lessons.some((lesson) => lesson.id === requestedLessonId)
  ) {
    return requestedLessonId;
  }
  if (lessons.some((lesson) => lesson.id === activeLessonId)) {
    return activeLessonId;
  }
  return lessons[0].id;
}

export function getReaderLayoutKey(
  activeIsQuiz: boolean,
  chatOpen: boolean,
): string {
  if (activeIsQuiz) return chatOpen ? "quiz-chat" : "quiz";
  return chatOpen ? "reader-chat" : "reader";
}

export function findNextLesson<T extends { id: string }>(
  lessons: readonly T[],
  activeLessonId: string,
): T | undefined {
  const index = lessons.findIndex((lesson) => lesson.id === activeLessonId);
  return lessons[index + 1];
}

export function isGazeDotVisible(
  gazeDot: GazeDotPosition | null,
  activeLessonId: string,
  currentSlide: number,
): gazeDot is GazeDotPosition {
  return Boolean(
    gazeDot && gazeDot.key === `${activeLessonId}:${currentSlide}`,
  );
}

/**
 * Tìm slide mà citation trỏ tới trong danh sách slide của reader.
 *
 * Ưu tiên `slideId`, fallback `slideIndex` (vị trí 0-based) khi slide
 * không còn trong nội dung hiện tại.
 */
export function findCitationSlideIndex(
  citation: {
    slideId?: string | null;
    slideIndex?: number | null;
  },
  slides: readonly { id: string }[],
): number {
  if (citation.slideId) {
    const index = slides.findIndex((slide) => slide.id === citation.slideId);
    if (index >= 0) return index;
  }
  if (
    citation.slideIndex != null &&
    citation.slideIndex >= 0 &&
    citation.slideIndex < slides.length
  ) {
    return citation.slideIndex;
  }
  return -1;
}

/**
 * Chỉ số slide kế tiếp, kẹp trong `[0, total - 1]`. Khi chưa có slide
 * (`total = 0`) luôn trả 0 — giữ nguyên hành vi điều hướng cũ.
 */
export function getNextSlideIndex(
  currentSlide: number,
  total: number,
): number {
  return Math.min(Math.max(total - 1, 0), currentSlide + 1);
}

/** Chỉ số slide trước đó, không xuống dưới 0. */
export function getPreviousSlideIndex(currentSlide: number): number {
  return Math.max(0, currentSlide - 1);
}
