"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  fetchTeacherCourses,
  fetchCourseTree,
  fetchCourseStudents,
  fetchLessonSlidesAdmin,
  fetchStudentDirectory,
  type CourseListQuery,
} from "@/lib/api/teacher";
import { queryKeys } from "@/lib/query-keys";

export function useTeacherCourses(query: CourseListQuery = {}) {
  return useQuery({
    queryKey: queryKeys.teacher.courses(query),
    queryFn: () => fetchTeacherCourses(query),
  });
}

export function useCourseTree(courseId: string) {
  return useQuery({
    queryKey: queryKeys.teacher.courseTree(courseId),
    queryFn: () => fetchCourseTree(courseId),
    enabled: Boolean(courseId),
    // Có slide đang index thì tự làm mới để checklist xuất bản cập nhật.
    refetchInterval: (query) => {
      const tree = query.state.data;
      if (!Array.isArray(tree)) return false;
      const pending = tree.some((module) =>
        module.lessons.some((lesson) => (lesson.slidesPending ?? 0) > 0),
      );
      return pending ? 5000 : false;
    },
  });
}

export function useCourseStudents(courseId: string) {
  return useQuery({
    queryKey: queryKeys.teacher.courseStudents(courseId),
    queryFn: () => fetchCourseStudents(courseId),
    enabled: Boolean(courseId),
  });
}

export function useLessonSlidesAdmin(
  lessonId: string,
  version: "draft" | "published" = "draft",
) {
  return useQuery({
    queryKey: queryKeys.teacher.lessonSlides(lessonId, version),
    queryFn: () => fetchLessonSlidesAdmin(lessonId, version),
    enabled: Boolean(lessonId),
    // Đang index thì tự làm mới để trạng thái pending → ready/failed.
    refetchInterval: (query) => {
      const slides = query.state.data;
      if (!Array.isArray(slides)) return false;
      return slides.some((slide) => slide.embeddingStatus === "pending")
        ? 5000
        : false;
    },
  });
}

export function useStudentDirectory(enabled: boolean, query = "") {
  const normalizedQuery = query.trim();
  const [debouncedQuery, setDebouncedQuery] = useState(normalizedQuery);

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedQuery(normalizedQuery), 300);
    return () => window.clearTimeout(timeout);
  }, [normalizedQuery]);

  return useQuery({
    queryKey: queryKeys.teacher.studentDirectory(debouncedQuery),
    queryFn: () => fetchStudentDirectory(debouncedQuery),
    enabled,
    staleTime: 30_000,
  });
}
