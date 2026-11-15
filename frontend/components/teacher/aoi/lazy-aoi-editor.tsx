"use client";

import dynamic from "next/dynamic";
import { FullPageSpinner } from "@/components/ui/spinner";

const AoiEditorDynamic = dynamic(
  () =>
    import("@/components/teacher/aoi-editor").then((mod) => mod.AoiEditor),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[calc(100dvh-73px)] min-h-[560px] items-center justify-center">
        <FullPageSpinner label="Đang tải vùng phân tích..." />
      </div>
    ),
  },
);

export function LazyAoiEditor({
  courseId,
  courseTitle,
  canManage,
}: {
  courseId: string;
  courseTitle: string;
  canManage: boolean;
}) {
  return (
    <AoiEditorDynamic
      courseId={courseId}
      courseTitle={courseTitle}
      canManage={canManage}
    />
  );
}
