"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import type { LessonNode, ModuleNode } from "@/lib/types/domain";
import { AddModuleButton } from "./add-controls";
import { ModuleSection } from "./module-section";

export function ContentOutline({
  tree,
  canManage,
  selection,
  onSelect,
  expanded,
  onToggleModule,
  onAddModule,
  onAddItem,
  onRenameLesson,
  onRenameModule,
  onDeleteLesson,
  onDeleteModule,
  onReorder,
  focusModuleId,
  busy,
}: {
  tree: ModuleNode[];
  canManage: boolean;
  selection: string | null;
  onSelect: (lessonId: string) => void;
  expanded: Record<string, boolean>;
  onToggleModule: (moduleId: string) => void;
  onAddModule: () => void;
  onAddItem: (moduleId: string, kind: "lesson" | "quiz") => void;
  onRenameLesson: (lesson: LessonNode, title: string) => void;
  onRenameModule: (moduleId: string, title: string) => void;
  onDeleteLesson: (lesson: LessonNode) => void;
  onDeleteModule: (module: ModuleNode) => void;
  onReorder: (module: ModuleNode, next: LessonNode[]) => void;
  focusModuleId?: string | null;
  busy: boolean;
}) {
  const [renamingModuleId, setRenamingModuleId] = useState<string | null>(null);
  const [renamingLessonId, setRenamingLessonId] = useState<string | null>(null);
  const [lastFocusModuleId, setLastFocusModuleId] = useState<string | null>(null);

  // Chương vừa tạo → mở ngay ô đổi tên để giáo viên nhập tên thật.
  // Điều chỉnh state trong lúc render (React khuyến nghị) thay vì effect.
  if (focusModuleId && focusModuleId !== lastFocusModuleId) {
    setLastFocusModuleId(focusModuleId);
    setRenamingModuleId(focusModuleId);
  }

  if (tree.length === 0) {
    return (
      <EmptyState
        icon="ri-git-branch-line"
        title="Chưa có chương"
        description="Tạo chương đầu tiên rồi thêm bài giảng (PDF) hoặc bài tập trắc nghiệm."
        action={
          canManage ? (
            <Button className="rounded-full" onClick={onAddModule} disabled={busy}>
              Tạo chương đầu tiên
            </Button>
          ) : undefined
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      {tree.map((module, moduleIndex) => (
        <ModuleSection
          key={module.id}
          module={module}
          moduleIndex={moduleIndex}
          canManage={canManage}
          selection={selection}
          isOpen={expanded[module.id] ?? true}
          onToggleModule={onToggleModule}
          renamingModuleId={renamingModuleId}
          onStartRenameModule={setRenamingModuleId}
          onCancelRenameModule={() => setRenamingModuleId(null)}
          onRenameModule={onRenameModule}
          renamingLessonId={renamingLessonId}
          onStartRenameLesson={setRenamingLessonId}
          onCancelRenameLesson={() => setRenamingLessonId(null)}
          onRenameLesson={onRenameLesson}
          onSelect={onSelect}
          onDeleteLesson={onDeleteLesson}
          onDeleteModule={onDeleteModule}
          onAddItem={onAddItem}
          onReorder={onReorder}
          busy={busy}
        />
      ))}

      {canManage && <AddModuleButton busy={busy} onAddModule={onAddModule} />}
    </div>
  );
}
