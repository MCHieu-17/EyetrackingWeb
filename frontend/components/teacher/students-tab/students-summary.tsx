"use client";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";

/** Header tab Học viên: tiêu đề, thống kê nhanh và nút thêm học viên. */
export function StudentsSummary({
  total,
  activeCount,
  completedCount,
  canManage,
  onAdd,
}: {
  total: number;
  activeCount: number;
  completedCount: number;
  canManage: boolean;
  onAdd: () => void;
}) {
  return (
    <div className="flex flex-col gap-6 border-b border-border pb-8 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Danh sách lớp</p>
        <h2 className="font-display text-3xl font-semibold tracking-[-0.04em] text-foreground sm:text-4xl">
          Học viên
        </h2>
        <p className="mt-3 text-sm text-muted-foreground">
          {total === 0
            ? "Chưa có học viên nào trong khóa học."
            : `${total} học viên · ${activeCount} đang học · ${completedCount} hoàn thành`}
        </p>
      </div>
      {canManage && (
        <Button onClick={onAdd} className="rounded-full px-5">
          <Icon name="ri-user-add-line" className="size-4" />
          Thêm học viên
        </Button>
      )}
    </div>
  );
}
