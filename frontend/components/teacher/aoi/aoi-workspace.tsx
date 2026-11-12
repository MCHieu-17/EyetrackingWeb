"use client";

import { useState } from "react";
import { AoiPanel } from "./aoi-panel";
import { StudentPreview } from "./student-preview";
import { useAoiEditor } from "./use-aoi-editor";

export function AoiWorkspace({
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
  const controller = useAoiEditor({ courseId, courseStatus, canManage });
  const [hoveredCode, setHoveredCode] = useState<string | null>(null);
  const [hiddenCodes, setHiddenCodes] = useState<Set<string>>(new Set());

  const toggleHidden = (code: string) => {
    setHiddenCodes((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  return (
    <div className="flex h-[calc(100dvh-73px)] min-h-[560px] flex-col gap-3 p-3 sm:p-4 lg:flex-row">
      <StudentPreview
        courseTitle={courseTitle}
        controller={controller}
        hoveredCode={hoveredCode}
        hiddenCodes={hiddenCodes}
        onHover={setHoveredCode}
      />
      <AoiPanel
        courseId={courseId}
        controller={controller}
        hoveredCode={hoveredCode}
        onHover={setHoveredCode}
        hiddenCodes={hiddenCodes}
        onToggleHidden={toggleHidden}
      />
    </div>
  );
}
