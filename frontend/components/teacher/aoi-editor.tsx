"use client";

import { AoiWorkspace } from "@/components/teacher/aoi/aoi-workspace";

export function AoiEditor({
  courseId,
  courseTitle,
  courseStatus,
  canManage,
}: {
  courseId: string;
  courseTitle: string;
  courseStatus: "draft" | "published" | "archived";
  canManage: boolean;
}) {
  return (
    <AoiWorkspace
      courseId={courseId}
      courseTitle={courseTitle}
      courseStatus={courseStatus}
      canManage={canManage}
    />
  );
}
