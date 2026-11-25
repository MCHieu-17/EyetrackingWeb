"use client";

import { Icon } from "@/components/ui/icon";
import { cn } from "@/lib/utils";
import type { StudentRow } from "@/lib/types/domain";
import type { SortColumn, SortState } from "../students-helpers";
import { LIST_GRID, StudentRowItem } from "./student-row";

function SortButton({
  label,
  column,
  sort,
  onSort,
  className,
}: {
  label: string;
  column: SortColumn;
  sort: SortState;
  onSort: (column: SortColumn) => void;
  className?: string;
}) {
  const active = sort.column === column;
  return (
    <button
      type="button"
      onClick={() => onSort(column)}
      aria-label={
        active
          ? `Đang sắp xếp theo ${label} ${sort.dir === "asc" ? "tăng dần" : "giảm dần"}. Bấm để đổi chiều.`
          : `Sắp xếp theo ${label}`
      }
      className={cn(
        "inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.08em] transition-colors",
        active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
        className,
      )}
    >
      {label}
      <Icon
        name={active && sort.dir === "desc" ? "ri-arrow-down-s-line" : "ri-arrow-up-s-line"}
        className={cn("size-3.5", !active && "opacity-0")}
      />
    </button>
  );
}

/** Bảng học viên: hàng tiêu đề sắp xếp + các hàng dữ liệu. */
export function StudentsTable({
  rows,
  sort,
  canManage,
  onSort,
  onOpen,
  onRemove,
}: {
  rows: StudentRow[];
  sort: SortState;
  canManage: boolean;
  onSort: (column: SortColumn) => void;
  onOpen: (student: StudentRow) => void;
  onRemove: (student: StudentRow) => void;
}) {
  return (
    <div className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
      <div
        className={cn(
          "hidden items-center gap-4 bg-muted/60 px-4 py-2.5 lg:grid lg:px-5",
          LIST_GRID,
        )}
      >
        <SortButton label="Học viên" column="name" sort={sort} onSort={onSort} className="justify-self-start" />
        <SortButton label="Trạng thái" column="status" sort={sort} onSort={onSort} className="justify-self-start" />
        <SortButton label="Hoạt động" column="lastActive" sort={sort} onSort={onSort} className="justify-self-end" />
        <span aria-hidden className="hidden lg:block" />
      </div>
      {rows.map((student) => (
        <StudentRowItem
          key={student.id}
          student={student}
          canManage={canManage}
          onOpen={() => onOpen(student)}
          onRemove={() => onRemove(student)}
        />
      ))}
    </div>
  );
}
