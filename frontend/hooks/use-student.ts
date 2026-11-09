"use client";

import { useQuery } from "@tanstack/react-query";
import {
  fetchMyEnrollments,
  fetchCourseOutline,
  fetchLessonSlides,
  fetchSessionContents,
} from "@/lib/api/student";
import { queryKeys } from "@/lib/query-keys";

export function useMyEnrollments() {
  return useQuery({
    queryKey: queryKeys.student.enrollments,
    queryFn: fetchMyEnrollments,
  });
}

export function useCourseOutline(courseId: string) {
  return useQuery({
    queryKey: queryKeys.student.courseOutline(courseId),
    queryFn: () => fetchCourseOutline(courseId),
    enabled: Boolean(courseId),
  });
}

export function useLessonSlides(lessonId: string, sessionId?: string | null) {
  return useQuery({
    queryKey: queryKeys.student.lessonSlides(lessonId, sessionId),
    queryFn: () =>
      sessionId
        ? fetchSessionContents(sessionId)
        : lessonId
          ? fetchLessonSlides(lessonId)
          : Promise.resolve([]),
    enabled: Boolean(lessonId),
    placeholderData: (previous) => previous,
  });
}
