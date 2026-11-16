import { apiFetch } from "./client";
import type {
  AoiHeatmap,
  AoiHeatmapQuery,
  AoiSummary,
  AoiSummaryQuery,
  ReplaySampleCursor,
  ReplaySamplesPage,
  VisitReplay,
} from "@/lib/types/visualization";

export function fetchVisitReplay(visitId: string): Promise<VisitReplay> {
  return apiFetch<VisitReplay>(`/api/teacher/visits/${visitId}/replay`);
}

export function fetchReplaySamples(
  visitId: string,
  contentViewId: string,
  cursor?: ReplaySampleCursor | null,
  limit = 2000,
): Promise<ReplaySamplesPage> {
  return apiFetch<ReplaySamplesPage>(`/api/teacher/visits/${visitId}/samples`, {
    params: {
      contentViewId,
      limit,
      afterTime: cursor?.afterTime,
      afterId: cursor?.afterId,
    },
  });
}

export function fetchAoiSummary(
  courseId: string,
  query: AoiSummaryQuery,
): Promise<AoiSummary> {
  return apiFetch<AoiSummary>(
    `/api/teacher/courses/${courseId}/analytics/aoi-summary`,
    { method: "POST", body: query },
  );
}

export function fetchAoiHeatmap(
  courseId: string,
  query: AoiHeatmapQuery,
): Promise<AoiHeatmap> {
  return apiFetch<AoiHeatmap>(
    `/api/teacher/courses/${courseId}/analytics/heatmap`,
    { method: "POST", body: query },
  );
}
