"use client";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { KIND_LABEL } from "@/lib/content-labels";
import { cn } from "@/lib/utils";
import type { LessonNode } from "@/lib/types/domain";
import { InlineTitleInput } from "./inline-title-input";
import { DragHandle, SortableRow } from "./sortable-row";
import { itemStatus } from "./status-pill";

/** Một dòng bài giảng/bài tập trong chương, kèm tay kéo và menu đổi tên/xóa. */
export function LessonRow({
  lesson,
  lessonIndex,
  canManage,
  isSelected,
  renaming,
  busy,
  onSelect,
  onStartRename,
  onCancelRename,
  onRename,
  onDelete,
}: {
  lesson: LessonNode;
  lessonIndex: number;
  canManage: boolean;
  isSelected: boolean;
  renaming: boolean;
  busy: boolean;
  onSelect: (lessonId: string) => void;
  onStartRename: (lessonId: string) => void;
  onCancelRename: () => void;
  onRename: (lesson: LessonNode, title: string) => void;
  onDelete: (lesson: LessonNode) => void;
}) {
  const isQuiz = lesson.kind === "quiz";

  return (
    <SortableRow id={lesson.id} disabled={!canManage || busy}>
      <div
        onClick={(event) => {
          // Bấm vào vùng trống của dòng (kể cả nhãn trạng thái)
          // cũng chọn mục — không chỉ riêng ô tròn hay tên.
          if ((event.target as HTMLElement).closest("button, input, a")) return;
          onSelect(lesson.id);
        }}
        className={cn(
          "flex cursor-pointer items-center gap-2 rounded-2xl border px-2.5 py-2 transition",
          isSelected
            ? "border-primary/50 bg-accent/60 shadow-xs"
            : "border-border bg-muted/40 hover:border-primary/30 hover:bg-muted",
        )}
      >
        {canManage && <DragHandle label={`Kéo để sắp xếp ${lesson.title}`} />}

        <button
          type="button"
          onClick={() => onSelect(lesson.id)}
          aria-current={isSelected ? "true" : undefined}
          aria-label={`Mở ${lesson.title}`}
          title={`Mở ${lesson.title}`}
          className={cn(
            "flex size-9 shrink-0 cursor-pointer items-center justify-center rounded-full text-sm font-semibold tabular-nums transition hover:ring-2 hover:ring-ring/30 active:scale-95",
            isQuiz ? "bg-primary text-primary-foreground" : "bg-accent text-accent-foreground",
          )}
        >
          {isQuiz ? (
            <Icon name="ri-file-text-line" className="size-4" />
          ) : (
            lessonIndex + 1
          )}
        </button>

        <div className="min-w-0 flex-1">
          {renaming ? (
            <InlineTitleInput
              value={lesson.title}
              ariaLabel={`Đổi tên ${lesson.title}`}
              onCommit={(value) => {
                onCancelRename();
                onRename(lesson, value);
              }}
              onCancel={onCancelRename}
            />
          ) : (
            <button
              type="button"
              onClick={() => {
                onSelect(lesson.id);
                if (canManage) onStartRename(lesson.id);
              }}
              className={cn(
                "block w-full truncate rounded-md px-1 text-left text-sm transition-colors",
                canManage && "hover:bg-accent/55",
                isSelected ? "font-semibold text-foreground" : "font-medium text-foreground",
              )}
              title={canManage ? "Bấm để đổi tên" : lesson.title}
            >
              {lesson.title}
            </button>
          )}
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-medium text-muted-foreground">
              {KIND_LABEL[lesson.kind] ?? "Nội dung"}
            </span>
            {itemStatus(lesson)}
          </div>
        </div>

        {canManage && (
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Xóa ${lesson.title}`}
            title="Xóa"
            className="shrink-0 text-muted-foreground hover:text-destructive"
            onClick={() => onDelete(lesson)}
          >
            <Icon name="ri-delete-bin-line" className="size-4" />
          </Button>
        )}
      </div>
    </SortableRow>
  );
}
