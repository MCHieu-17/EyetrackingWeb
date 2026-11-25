"use client";

import { useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { useCourseTree } from "@/hooks/use-teacher";
import { cn } from "@/lib/utils";
import type { SummaryScope } from "@/lib/types/visualization";
import { ReplayPanel } from "./replay/replay-panel";
import { SummaryPanel } from "./summary/summary-panel";

type Mode = "replay" | "summary";

export function VisualizationTab({ courseId }: { courseId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const mode: Mode = searchParams.get("mode") === "summary" ? "summary" : "replay";
  const studentId = searchParams.get("studentId");
  const visitId = searchParams.get("visitId");
  const scopeParam = searchParams.get("scope");
  const initialScope: SummaryScope =
    scopeParam === "visit" || scopeParam === "student" || scopeParam === "cohort"
      ? scopeParam
      : studentId
        ? "student"
        : "cohort";

  const tree = useCourseTree(courseId);

  const setMode = (next: Mode) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", "visualization");
    params.set("mode", next);
    if (next === "replay" && !params.get("visitId")) {
      params.delete("visitId");
    }
    router.replace(`/teacher/courses/${courseId}?${params.toString()}`, {
      scroll: false,
    });
  };

  const lessons = useMemo(
    () => tree.data?.flatMap((module) => module.lessons) ?? [],
    [tree.data],
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex rounded-full border border-border bg-card p-1 shadow-xs">
          <button
            type="button"
            onClick={() => setMode("replay")}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors",
              mode === "replay"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon name="ri-play-circle-line" className="size-3.5" />
            Xem lại ca học
          </button>
          <button
            type="button"
            onClick={() => setMode("summary")}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors",
              mode === "summary"
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon name="ri-bar-chart-line" className="size-3.5" />
            Tổng hợp
          </button>
        </div>
        <p className="text-xs text-muted-foreground">
          {mode === "replay"
            ? "Phát lại điểm nhìn và kiểm tra vùng AOI đang sáng."
            : "Thống kê thời lượng nhìn theo AOI, bài học, học viên và ca."}
        </p>
      </div>

      {mode === "replay" ? (
        <ReplayPanel
          courseId={courseId}
          initialStudentId={studentId}
          initialVisitId={visitId}
        />
      ) : tree.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-24 rounded-[20px]" />
          <Skeleton className="h-[360px] rounded-[20px]" />
        </div>
      ) : tree.isError ? (
        <div className="rounded-[18px] border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Không tải được cấu trúc khóa học để lọc bài giảng.
        </div>
      ) : (
        <SummaryPanel
          courseId={courseId}
          tree={tree.data ?? []}
          initialStudentId={studentId}
          initialScope={initialScope}
        />
      )}

      {mode === "summary" && lessons.length === 0 && !tree.isLoading && (
        <p className="text-xs text-muted-foreground">
          Khóa học chưa có bài học; một số bộ lọc sẽ trống.
        </p>
      )}
    </div>
  );
}
