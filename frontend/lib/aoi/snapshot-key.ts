export interface AoiSnapshotKeyInput {
  sessionId: string;
  presentationId: string;
  viewportWidth: number;
  viewportHeight: number;
  layoutKey?: string | null;
  rectsKey: string;
  coordinateSpace?: string;
  visibleRectKey?: string;
}

/**
 * Khoá cache layout snapshot. Presentation phải nằm trong khoá: hai
 * presentation khác nhau (kể cả cùng hình học) cần snapshot riêng.
 */
export function aoiSnapshotCacheKey({
  sessionId,
  presentationId,
  viewportWidth,
  viewportHeight,
  layoutKey,
  rectsKey,
  coordinateSpace,
  visibleRectKey,
}: AoiSnapshotKeyInput): string {
  return [
    sessionId,
    presentationId,
    `${viewportWidth}x${viewportHeight}`,
    layoutKey ?? "",
    rectsKey,
    coordinateSpace ?? "",
    visibleRectKey ?? "",
  ].join("|");
}
