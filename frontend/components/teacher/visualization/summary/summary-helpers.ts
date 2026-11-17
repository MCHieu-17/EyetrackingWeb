import { colorFor } from "@/lib/aoi/colors";
import type {
  AoiHeatmapQuery,
  AoiSummary,
  AoiSummaryAoi,
  AoiSummaryLesson,
  AoiSummaryQuery,
  AoiSummaryVisit,
} from "@/lib/types/visualization";

export interface ChartAoi extends AoiSummaryAoi {
  isOther?: boolean;
}

export function visibleAois(aois: AoiSummaryAoi[]): AoiSummaryAoi[] {
  return aois.filter((aoi) => aoi.durationMs > 0 || aoi.sampleCount > 0);
}

export function topAois(aois: AoiSummaryAoi[], limit = 12): ChartAoi[] {
  const sorted = visibleAois(aois).sort(
    (a, b) => b.durationMs - a.durationMs || a.label.localeCompare(b.label),
  );
  if (sorted.length <= limit) return sorted;
  const head = sorted.slice(0, limit);
  const tail = sorted.slice(limit);
  const durationMs = tail.reduce((sum, item) => sum + item.durationMs, 0);
  const sampleCount = tail.reduce((sum, item) => sum + item.sampleCount, 0);
  return [
    ...head,
    {
      label: "other",
      name: "Khác",
      domain: "ui",
      durationMs,
      sampleCount,
      share: tail.reduce((sum, item) => sum + item.share, 0),
      studentCount: 0,
      slideCount: 0,
      mixedSlides: false,
      isUnlabeled: false,
      isOther: true,
    },
  ];
}

export function aoiColor(aoi: AoiSummaryAoi): string {
  if (aoi.isUnlabeled) return "#a34a32";
  if ("isOther" in aoi && aoi.isOther) return "#9ca3af";
  return colorFor(aoi.label);
}

export function percent(value: number, total: number): number {
  return total > 0 ? Math.max(0, Math.min(100, (value / total) * 100)) : 0;
}

export function shareLabel(share: number): string {
  return `${Math.round(share * 100)}%`;
}

export interface CompositionSegment {
  label: string;
  name: string;
  durationMs: number;
  percent: number;
  color: string;
}

export function compositionForAois(
  aois: AoiSummaryAoi[],
  durationMs: number,
  topLabels: AoiSummaryAoi[],
): CompositionSegment[] {
  const byLabel = new Map(aois.map((aoi) => [aoi.label, aoi]));
  const segments: CompositionSegment[] = topLabels.map((top) => {
    const item = byLabel.get(top.label);
    return {
      label: top.label,
      name: top.name,
      durationMs: item?.durationMs ?? 0,
      percent: percent(item?.durationMs ?? 0, durationMs),
      color: aoiColor(top),
    };
  });
  const covered = topLabels.reduce(
    (sum, top) => sum + (byLabel.get(top.label)?.durationMs ?? 0),
    0,
  );
  const other = Math.max(0, durationMs - covered);
  if (other > 0) {
    segments.push({
      label: "other",
      name: "Khác",
      durationMs: other,
      percent: percent(other, durationMs),
      color: "#9ca3af",
    });
  }
  return segments.filter((segment) => segment.durationMs > 0);
}

export function compositionForLesson(
  lesson: AoiSummaryLesson,
  topLabels: AoiSummaryAoi[],
): CompositionSegment[] {
  return compositionForAois(lesson.aois, lesson.durationMs, topLabels);
}

export interface VisitTrendPoint {
  visit: AoiSummaryVisit;
  tracked: number;
  slide: number;
  ui: number;
  unlabeled: number;
}

export function visitTrend(byVisit: AoiSummaryVisit[]): VisitTrendPoint[] {
  return [...byVisit]
    .sort(
      (a, b) =>
        new Date(a.startedAt).getTime() - new Date(b.startedAt).getTime(),
    )
    .map((visit) => ({
      visit,
      tracked: visit.trackedDurationMs || visit.durationMs,
      slide: visit.slideDurationMs,
      ui: visit.uiDurationMs,
      unlabeled: visit.unlabeledDurationMs,
    }));
}

export function maxOf(points: VisitTrendPoint[]): number {
  return Math.max(1, ...points.map((point) => point.tracked));
}

/**
 * Heatmap luôn xem theo slide của bài đang chọn, không bị filter bài/surface
 * toàn cục của tab Tổng hợp vô hiệu hoá. Vẫn giữ filter học viên/ca/ngày.
 */
export function buildHeatmapQuery(
  base: AoiSummaryQuery,
  slideId: string,
): AoiHeatmapQuery {
  return { ...base, lessonIds: [], surface: "lesson", slideId };
}

export function csvForSummary(summary: AoiSummary): string {
  const header = [
    "Nhan AOI",
    "Ten vung",
    "Nhom",
    "Thoi luong (ms)",
    "Ty le",
    "So mau",
    "So hoc vien",
    "So slide",
    "Nhieu slide",
  ];
  const rows = summary.byAoi.map((aoi) => [
    aoi.label,
    aoi.name,
    aoi.domain,
    String(aoi.durationMs),
    `${(aoi.share * 100).toFixed(1)}%`,
    String(aoi.sampleCount),
    String(aoi.studentCount),
    String(aoi.slideCount),
    aoi.mixedSlides ? "yes" : "no",
  ]);
  return [header, ...rows]
    .map((row) =>
      row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(","),
    )
    .join("\n");
}
