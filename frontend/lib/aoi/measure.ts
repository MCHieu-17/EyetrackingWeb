import type { AoiRect } from "@/lib/api/aoi";

/**
 * Đo rect thật của mọi phần tử `[data-aoi]` và chuẩn hoá theo viewport.
 *
 * Một `data-aoi` có thể xuất hiện nhiều lần (nhiều bong bóng chat user, nhiều
 * đoạn AI) → trả về nhiều rect cùng code. Backend lưu tất cả; khi mapping,
 * gaze rơi vào bất kỳ rect nào của code đó đều tính là hit.
 */
export function measureAoiRects(root: ParentNode = document): AoiRect[] {
  if (typeof window === "undefined") return [];
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  if (!(vw > 0) || !(vh > 0)) return [];

  const rects: AoiRect[] = [];
  root.querySelectorAll<HTMLElement>("[data-aoi]").forEach((el) => {
    const code = el.dataset.aoi?.trim();
    if (!code) return;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;

    const xMin = Math.max(0, rect.left / vw);
    const yMin = Math.max(0, rect.top / vh);
    const xMax = Math.min(1, rect.right / vw);
    const yMax = Math.min(1, rect.bottom / vh);
    if (xMax <= xMin || yMax <= yMin) return;

    rects.push({ code, xMin, yMin, xMax, yMax });
  });
  return rects;
}

/** Khoá so sánh nhanh để tránh tạo snapshot trùng khi layout không đổi. */
export function aoiRectsKey(rects: AoiRect[]): string {
  return rects
    .map(
      (r) =>
        `${r.code}:${r.xMin.toFixed(4)},${r.yMin.toFixed(4)},${r.xMax.toFixed(4)},${r.yMax.toFixed(4)}`,
    )
    .sort()
    .join("|");
}
