"use client";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/** Menu "Thêm nội dung" của một chương: bài giảng PDF hoặc bài tập trắc nghiệm. */
export function AddItemMenu({
  moduleId,
  busy,
  onAddItem,
}: {
  moduleId: string;
  busy: boolean;
  onAddItem: (moduleId: string, kind: "lesson" | "quiz") => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 pt-1">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            className="rounded-full border-black/10 bg-white"
            disabled={busy}
          >
            <Icon name="ri-add-line" className="size-4" />
            Thêm nội dung
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          <DropdownMenuItem onSelect={() => onAddItem(moduleId, "lesson")}>
            <Icon name="ri-book-open-line" />
            Bài giảng (PDF)
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => onAddItem(moduleId, "quiz")}>
            <Icon name="ri-question-line" />
            Bài tập trắc nghiệm
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

/** Nút thêm chương mới ở cuối mục lục. */
export function AddModuleButton({
  busy,
  onAddModule,
}: {
  busy: boolean;
  onAddModule: () => void;
}) {
  return (
    <Button
      variant="ghost"
      className="w-full justify-start rounded-full text-black/60"
      onClick={onAddModule}
      disabled={busy}
    >
      <Icon name="ri-add-line" className="size-4" />
      Thêm chương
    </Button>
  );
}
