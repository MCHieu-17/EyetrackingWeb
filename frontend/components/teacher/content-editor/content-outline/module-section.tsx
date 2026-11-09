"use client";

import { useRef, useState } from "react";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type Announcements,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { restrictToFirstScrollableAncestor, restrictToVerticalAxis } from "@dnd-kit/modifiers";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { KIND_LABEL } from "@/lib/content-labels";
import { cn } from "@/lib/utils";
import type { LessonNode, ModuleNode } from "@/lib/types/domain";
import { AddItemMenu } from "./add-controls";
import { InlineTitleInput } from "./inline-title-input";
import { LessonRow } from "./lesson-row";

/** Một chương trong mục lục: header đổi tên/xóa, danh sách mục kéo thả, nút thêm. */
export function ModuleSection({
  module,
  moduleIndex,
  canManage,
  selection,
  isOpen,
  onToggleModule,
  renamingModuleId,
  onStartRenameModule,
  onCancelRenameModule,
  onRenameModule,
  renamingLessonId,
  onStartRenameLesson,
  onCancelRenameLesson,
  onRenameLesson,
  onSelect,
  onDeleteLesson,
  onDeleteModule,
  onAddItem,
  onReorder,
  busy,
}: {
  module: ModuleNode;
  moduleIndex: number;
  canManage: boolean;
  selection: string | null;
  isOpen: boolean;
  onToggleModule: (moduleId: string) => void;
  renamingModuleId: string | null;
  onStartRenameModule: (moduleId: string) => void;
  onCancelRenameModule: () => void;
  onRenameModule: (moduleId: string, title: string) => void;
  renamingLessonId: string | null;
  onStartRenameLesson: (lessonId: string) => void;
  onCancelRenameLesson: () => void;
  onRenameLesson: (lesson: LessonNode, title: string) => void;
  onSelect: (lessonId: string) => void;
  onDeleteLesson: (lesson: LessonNode) => void;
  onDeleteModule: (module: ModuleNode) => void;
  onAddItem: (moduleId: string, kind: "lesson" | "quiz") => void;
  onReorder: (module: ModuleNode, next: LessonNode[]) => void;
  busy: boolean;
}) {
  const [activeLesson, setActiveLesson] = useState<LessonNode | null>(null);
  // Tiêu đề dùng cho thông báo aria-live: đọc qua ref để không phụ thuộc vào
  // việc re-render kịp hay không trong lúc kéo.
  const activeTitleRef = useRef("");

  const sensors = useSensors(
    // Khoảng cách 6px để cú bấm vào tay kéo vẫn không bị nhầm thành kéo thả.
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveLesson(null);
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const from = module.lessons.findIndex((item) => item.id === active.id);
    const to = module.lessons.findIndex((item) => item.id === over.id);
    if (from < 0 || to < 0) return;
    onReorder(module, arrayMove(module.lessons, from, to));
  };

  const itemCount = module.lessons.length;
  const active = module.lessons.some((lesson) => lesson.id === selection);

  return (
    <section className="overflow-hidden rounded-[20px] border border-[#eeeee9] bg-white shadow-xs">
      <div
        className={cn(
          "flex items-center gap-2 px-3 py-2.5",
          active && !isOpen && "bg-[#e8f1e6]/45",
        )}
      >
        <button
          type="button"
          onClick={() => onToggleModule(module.id)}
          aria-expanded={isOpen}
          aria-label={isOpen ? `Thu gọn ${module.title}` : `Mở ${module.title}`}
          title={isOpen ? "Thu gọn chương" : "Mở chương"}
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-[#e8f1e6] text-[#52704f] transition hover:bg-[#dbe8d6]"
        >
          <Icon
            name="ri-arrow-right-s-line"
            className={cn("size-5 transition-transform", isOpen && "rotate-90")}
          />
        </button>

        <span className="font-mono text-xs font-semibold tabular-nums text-black/45">
          {String(moduleIndex + 1).padStart(2, "0")}
        </span>

        {renamingModuleId === module.id ? (
          <InlineTitleInput
            value={module.title}
            ariaLabel={`Đổi tên ${module.title}`}
            onCommit={(value) => {
              onCancelRenameModule();
              onRenameModule(module.id, value);
            }}
            onCancel={onCancelRenameModule}
          />
        ) : (
          <button
            type="button"
            onClick={() =>
              canManage ? onStartRenameModule(module.id) : onToggleModule(module.id)
            }
            className="min-w-0 flex-1 truncate rounded-md px-1 text-left text-sm font-semibold text-black transition-colors hover:bg-[#e8f1e6]/55"
            title={canManage ? "Bấm để đổi tên chương" : module.title}
          >
            {module.title}
          </button>
        )}

        <span className="shrink-0 text-[11px] font-medium text-black/45">{itemCount} mục</span>

        {canManage && (
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Xóa chương ${module.title}`}
            title="Xóa chương"
            className="shrink-0 text-muted-foreground hover:text-destructive"
            onClick={() => onDeleteModule(module)}
          >
            <Icon name="ri-delete-bin-line" className="size-4" />
          </Button>
        )}
      </div>

      {isOpen && (
        <div className="space-y-2 px-2 pb-3">
          {itemCount === 0 && (
            <p className="rounded-[18px] border border-dashed border-black/10 bg-[#fdfdfa] px-4 py-4 text-center text-sm text-black/55">
              Chương này chưa có mục nào. Bấm “Thêm nội dung” để thêm bài giảng hoặc bài tập
              trắc nghiệm.
            </p>
          )}

          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            modifiers={[restrictToVerticalAxis, restrictToFirstScrollableAncestor]}
            onDragStart={(event: DragStartEvent) => {
              const lesson = module.lessons.find((item) => item.id === event.active.id);
              if (lesson) {
                activeTitleRef.current = lesson.title;
                setActiveLesson(lesson);
              }
            }}
            onDragEnd={handleDragEnd}
            onDragCancel={() => setActiveLesson(null)}
            accessibility={{
              announcements: {
                onDragStart: () =>
                  `Đã nhặt "${activeTitleRef.current}". Dùng phím mũi tên lên/xuống để di chuyển, Enter để thả, Esc để huỷ.`,
                onDragOver: ({ over }) => {
                  if (!over) return "Đang ở ngoài danh sách.";
                  const index = module.lessons.findIndex((item) => item.id === over.id);
                  return index < 0
                    ? "Đang di chuyển."
                    : `Đang ở vị trí ${index + 1}/${module.lessons.length}.`;
                },
                onDragEnd: () => `Đã thả "${activeTitleRef.current}".`,
                onDragCancel: () => `Đã huỷ sắp xếp "${activeTitleRef.current}".`,
              } satisfies Announcements,
              screenReaderInstructions: {
                draggable:
                  "Nhấn Space hoặc Enter để nhặt, dùng phím mũi tên để di chuyển, nhấn Space hoặc Enter lần nữa để thả, nhấn Esc để huỷ.",
              },
            }}
          >
            <SortableContext
              items={module.lessons.map((lesson) => lesson.id)}
              strategy={verticalListSortingStrategy}
            >
              {module.lessons.map((lesson, lessonIndex) => (
                <LessonRow
                  key={lesson.id}
                  lesson={lesson}
                  lessonIndex={lessonIndex}
                  canManage={canManage}
                  isSelected={selection === lesson.id}
                  renaming={renamingLessonId === lesson.id}
                  busy={busy}
                  onSelect={onSelect}
                  onStartRename={onStartRenameLesson}
                  onCancelRename={onCancelRenameLesson}
                  onRename={onRenameLesson}
                  onDelete={onDeleteLesson}
                />
              ))}
            </SortableContext>
            <DragOverlay>
              {activeLesson ? (
                <div className="flex items-center gap-3 rounded-[18px] border border-[#6f8f69] bg-white px-3 py-3 shadow-xl">
                  <Icon name="ri-draggable" className="size-4 shrink-0 text-[#52704f]" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-black">{activeLesson.title}</p>
                    <p className="mt-0.5 text-xs text-black/50">
                      {KIND_LABEL[activeLesson.kind] ?? "Nội dung"}
                    </p>
                  </div>
                </div>
              ) : null}
            </DragOverlay>
          </DndContext>

          {canManage && (
            <AddItemMenu moduleId={module.id} busy={busy} onAddItem={onAddItem} />
          )}
        </div>
      )}
    </section>
  );
}
