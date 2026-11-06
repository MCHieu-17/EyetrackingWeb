"use client";

import { useQuery } from "@tanstack/react-query";
import {
  fetchMyEnrollments,
  fetchCourseOutline,
  fetchLessonSlides,
  fetchSessionContents,
} from "@/lib/api/student";

export function useMyEnrollments() {
  return useQuery({ queryKey: ["student", "enrollments"], queryFn: fetchMyEnrollments });
}

export function useCourseOutline(courseId: string) {
  return useQuery({
    queryKey: ["student", "course-outline", courseId],
    queryFn: () => fetchCourseOutline(courseId),
    enabled: Boolean(courseId),
  });
}

export function useLessonSlides(lessonId: string, sessionId?: string | null) {
  return useQuery({
    queryKey: ["student", "lesson-slides", lessonId, sessionId ?? null],
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
