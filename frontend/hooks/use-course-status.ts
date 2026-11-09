"use client";

import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { publishCourse, updateCourse } from "@/lib/api/teacher";
import { queryKeys } from "@/lib/query-keys";
import type { CourseStatus } from "@/lib/types/domain";

/**
 * Đổi trạng thái khóa học (xuất bản / thu hồi / lưu trữ) và làm mới cache.
 *
 * Tách khỏi UI để tab Nội dung và tab Thông tin khóa học dùng chung một luồng:
 * cùng gọi PATCH, cùng invalidate danh sách khóa + cây nội dung.
 */
export function useCourseStatus(courseId: string) {
  const queryClient = useQueryClient();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const changeStatus = useCallback(
    async (next: CourseStatus): Promise<string | null> => {
      setSaving(true);
      setError(null);
      try {
        if (next === "published") {
          await publishCourse(courseId);
        } else {
          await updateCourse(courseId, { status: next });
        }
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: queryKeys.teacher.coursesRoot }),
          queryClient.invalidateQueries({
            queryKey: queryKeys.teacher.courseTree(courseId),
          }),
        ]);
        return null;
      } catch (e) {
        const message = e instanceof Error ? e.message : "Lỗi không xác định";
        setError(message);
        // Publish có thể bị chặn vì slide chưa index; làm mới cây để UI
        // chuyển sang trạng thái pending và tự poll.
        await queryClient.invalidateQueries({
          queryKey: queryKeys.teacher.courseTree(courseId),
        });
        return message;
      } finally {
        setSaving(false);
      }
    },
    [courseId, queryClient],
  );

  return { changeStatus, saving, error };
}
