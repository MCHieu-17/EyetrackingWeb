import type { QueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/lib/query-keys";
import type { TeacherCourse } from "@/lib/types/domain";

export type CourseFlag = "showGazeDot" | "requireCalibration";

/**
 * Optimistic update một cờ cấp khóa trong danh sách khóa học.
 *
 * Luôn dùng đúng query key có tham số mặc định `{}` mà `useTeacherCourses()`
 * đang đọc; invalidate toàn bộ prefix sau khi mutation kết thúc.
 */
export async function updateCourseFlag({
  queryClient,
  courseId,
  field,
  value,
  request,
}: {
  queryClient: QueryClient;
  courseId: string;
  field: CourseFlag;
  value: boolean;
  request: () => Promise<unknown>;
}): Promise<string | null> {
  const key = queryKeys.teacher.courses();
  const previous = queryClient.getQueryData<TeacherCourse[]>(key);
  queryClient.setQueryData<TeacherCourse[]>(key, (list) =>
    list?.map((item) =>
      item.id === courseId ? { ...item, [field]: value } : item,
    ),
  );
  try {
    await request();
    return null;
  } catch (error) {
    if (previous) queryClient.setQueryData(key, previous);
    return error instanceof Error ? error.message : "lỗi không xác định";
  } finally {
    queryClient.invalidateQueries({ queryKey: queryKeys.teacher.coursesRoot });
  }
}
