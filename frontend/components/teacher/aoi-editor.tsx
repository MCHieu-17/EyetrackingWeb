"use client";

import { AoiWorkspace } from "@/components/teacher/aoi/aoi-workspace";

export function AoiEditor({
  courseId,
  courseTitle,
  canManage,
}: {
  courseId: string;
  courseTitle: string;
  canManage: boolean;
}) {
  return (
    <AoiWorkspace
      courseId={courseId}
      courseTitle={courseTitle}
      canManage={canManage}
    />
  );
}
