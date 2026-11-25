"use client";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import type { CourseStatus } from "@/lib/types/domain";

/** Header tab Nội dung: thống kê nhanh và nút xuất bản. */
export function EditorHeader({
  moduleCount,
  totalLessons,
  totalQuizzes,
  totalSlides,
  treeFetching,
  canManage,
  courseStatus,
  publishing,
  saving,
  reordering,
  onPublish,
}: {
  moduleCount: number;
  totalLessons: number;
  totalQuizzes: number;
  totalSlides: number;
  treeFetching: boolean;
  canManage: boolean;
  courseStatus: CourseStatus;
  publishing: boolean;
  saving: boolean;
  reordering: boolean;
  onPublish: () => void;
}) {
  return (
    <div className="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p className="text-sm text-muted-foreground">
          {moduleCount} chương · {totalLessons} bài giảng · {totalQuizzes} bài tập · {totalSlides} trang
          {treeFetching && <span className="ml-2 text-muted-foreground">· đang cập nhật…</span>}
        </p>
      </div>
      {canManage && (
        <div className="flex flex-wrap gap-2">
          {courseStatus === "published" ? (
            <span className="inline-flex h-9 items-center gap-1.5 rounded-full border border-success/25 bg-success/10 px-3.5 text-xs font-semibold text-success">
              <Icon name="ri-checkbox-circle-fill" className="size-4" />
              Đã xuất bản
            </span>
          ) : (
            <Button
              className="rounded-full"
              onClick={onPublish}
              disabled={publishing || saving || reordering}
            >
              <Icon name="ri-rocket-2-line" className="size-4" />
              {publishing ? "Đang xuất bản…" : "Xuất bản"}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
