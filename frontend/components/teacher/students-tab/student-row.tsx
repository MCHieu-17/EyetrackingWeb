"use client";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { ENROLL_LABEL } from "@/lib/constants";
import { cn, initialsOf } from "@/lib/utils";
import type { StudentRow } from "@/lib/types/domain";

// Cột lưới dùng chung cho hàng tiêu đề và từng hàng học viên (từ sm trở lên).
export const LIST_GRID = "lg:grid-cols-[minmax(0,1fr)_140px_130px_200px]";

/** Một hàng học viên trong bảng, kèm nút xem chi tiết và gỡ khỏi khóa. */
export function StudentRowItem({
  student,
  canManage,
  onOpen,
  onRemove,
}: {
  student: StudentRow;
  canManage: boolean;
  onOpen: () => void;
  onRemove: () => void;
}) {
  return (
    <div
      className={cn(
        "grid grid-cols-1 gap-3 px-4 py-4 transition-colors hover:bg-muted/60 lg:items-center lg:gap-4 lg:px-5",
        LIST_GRID,
      )}
    >
      <div className="flex min-w-0 items-center gap-3">
        <Avatar className="size-10 shrink-0 bg-card">
          {student.avatarUrl ? <AvatarImage src={student.avatarUrl} alt={student.name} /> : null}
          <AvatarFallback>{initialsOf(student.name)}</AvatarFallback>
        </Avatar>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-foreground">{student.name}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">{student.code}</p>
        </div>
      </div>
      <span
        className={cn(
          "shrink-0 justify-self-start rounded-full px-2.5 py-1 text-[10px] font-medium lg:self-center",
          student.status === "dropped"
            ? "bg-muted text-muted-foreground"
            : "bg-success/10 text-success",
        )}
      >
        {student.status === "dropped" ? "Đã gỡ" : ENROLL_LABEL[student.status]}
      </span>
      <span className="shrink-0 text-xs text-muted-foreground lg:justify-self-end lg:text-right">
        {student.lastActive || "—"}
      </span>
      <div className="flex shrink-0 items-center gap-2 lg:justify-self-end">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="flex-1 rounded-full lg:flex-none"
          onClick={onOpen}
        >
          Chi tiết
          <Icon name="ri-arrow-right-line" className="size-3.5" />
        </Button>
        {canManage && student.status !== "dropped" && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onRemove}
            aria-label={`Gỡ ${student.name}`}
            className="rounded-full border border-border bg-card text-muted-foreground hover:text-destructive"
          >
            <Icon name="ri-delete-bin-line" className="size-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
