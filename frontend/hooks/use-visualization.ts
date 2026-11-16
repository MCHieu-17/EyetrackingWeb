"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import {
  fetchCourseVisits,
  type CourseVisitsQuery,
} from "@/lib/api/visits";
import {
  fetchAoiHeatmap,
  fetchAoiSummary,
  fetchReplaySamples,
  fetchVisitReplay,
} from "@/lib/api/visualization";
import { queryKeys } from "@/lib/query-keys";
import type {
  AoiHeatmapQuery,
  AoiSummaryQuery,
  ReplaySampleCursor,
} from "@/lib/types/visualization";

export function useCourseVisits(
  courseId: string,
  query: CourseVisitsQuery = {},
) {
  return useQuery({
    queryKey: queryKeys.visualization.courseVisits(courseId, query),
    queryFn: () => fetchCourseVisits(courseId, query),
    enabled: Boolean(courseId),
  });
}

export function useVisitReplay(visitId: string | null) {
  return useQuery({
    queryKey: queryKeys.visualization.visitReplay(visitId ?? ""),
    queryFn: () => fetchVisitReplay(visitId as string),
    enabled: Boolean(visitId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      return data.views.some(
        (view) =>
          view.analysisStatus === "pending" ||
          view.analysisStatus === "running",
      )
        ? 5000
        : false;
    },
  });
}

export function useReplaySamples(
  visitId: string | null,
  contentViewId: string | null,
) {
  return useInfiniteQuery({
    queryKey: queryKeys.visualization.replaySamples(
      visitId ?? "",
      contentViewId ?? "",
    ),
    queryFn: ({ pageParam }) =>
      fetchReplaySamples(
        visitId as string,
        contentViewId as string,
        pageParam as ReplaySampleCursor | null,
      ),
    initialPageParam: null as ReplaySampleCursor | null,
    getNextPageParam: (last) => last.nextCursor,
    enabled: Boolean(visitId && contentViewId),
  });
}

export function useAoiSummary(
  courseId: string,
  query: AoiSummaryQuery,
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.visualization.aoiSummary(courseId, query),
    queryFn: () => fetchAoiSummary(courseId, query),
    enabled: Boolean(courseId) && enabled,
  });
}

export function useAoiHeatmap(
  courseId: string,
  query: AoiHeatmapQuery,
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.visualization.aoiHeatmap(courseId, query),
    queryFn: () => fetchAoiHeatmap(courseId, query),
    enabled: Boolean(courseId && query.slideId) && enabled,
  });
}
