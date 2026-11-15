"use client";

import { useState } from "react";
import { AoiPanel } from "./aoi-panel";
import { StudentPreview } from "./student-preview";
import { useAoiEditor } from "./use-aoi-editor";

export function AoiWorkspace({
  courseId,
  courseTitle,
  canManage,
}: {
  courseId: string;
  courseTitle: string;
  canManage: boolean;
}) {
  const controller = useAoiEditor({ courseId, canManage });
  const [hoveredCode, setHoveredCode] = useState<string | null>(null);

  return (
    <div className="flex h-[calc(100dvh-73px)] min-h-[560px] flex-col gap-3 p-3 sm:p-4 lg:flex-row">
      <StudentPreview
        courseTitle={courseTitle}
        controller={controller}
        hoveredCode={hoveredCode}
        onHover={setHoveredCode}
      />
      <AoiPanel
        courseId={courseId}
        controller={controller}
        hoveredCode={hoveredCode}
        onHover={setHoveredCode}
      />
    </div>
  );
}
