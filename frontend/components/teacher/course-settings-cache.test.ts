import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { updateCourseFlag } from "./course-settings-cache";
import { queryKeys } from "@/lib/query-keys";
import type { TeacherCourse } from "@/lib/types/domain";

function course(overrides: Partial<TeacherCourse> = {}): TeacherCourse {
  return {
    id: "course-1",
    title: "Course",
    description: "",
    gradient: "",
    status: "published",
    students: 0,
    attention: null,
    sessions: 0,
    updatedAt: "2026-01-01T00:00:00Z",
    showGazeDot: false,
    requireCalibration: true,
    ...overrides,
  };
}

describe("updateCourseFlag", () => {
  it("cập nhật đúng cache key mặc định và giữ giá trị khi request thành công", async () => {
    const client = new QueryClient();
    const key = queryKeys.teacher.courses();
    client.setQueryData(key, [course()]);
    const request = vi.fn().mockResolvedValue(undefined);

    const error = await updateCourseFlag({
      queryClient: client,
      courseId: "course-1",
      field: "showGazeDot",
      value: true,
      request,
    });

    expect(error).toBeNull();
    expect(request).toHaveBeenCalledOnce();
    expect(client.getQueryData<TeacherCourse[]>(key)?.[0].showGazeDot).toBe(true);
  });

  it("rollback khi request lỗi và trả thông báo", async () => {
    const client = new QueryClient();
    const key = queryKeys.teacher.courses();
    client.setQueryData(key, [course({ showGazeDot: false })]);

    const error = await updateCourseFlag({
      queryClient: client,
      courseId: "course-1",
      field: "showGazeDot",
      value: true,
      request: () => Promise.reject(new Error("offline")),
    });

    expect(error).toBe("offline");
    expect(client.getQueryData<TeacherCourse[]>(key)?.[0].showGazeDot).toBe(false);
  });
});
