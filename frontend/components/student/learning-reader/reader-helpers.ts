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
 * Ưu tiên `slideVersionId` (ổn định qua các lần đổi bài), fallback
 * `slideIndex` (vị trí 0-based) khi slide version không còn trong bản
 * xuất bản hiện tại.
 */
export function findCitationSlideIndex(
  citation: {
    slideVersionId?: string | null;
    slideIndex?: number | null;
  },
  slides: readonly { slideVersionId?: string | null }[],
): number {
  if (citation.slideVersionId) {
    const index = slides.findIndex(
      (slide) => slide.slideVersionId === citation.slideVersionId,
    );
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
