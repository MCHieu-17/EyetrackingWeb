"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

export function ReaderBanners({
  courseId,
  activeLessonId,
  calibrationRequired,
  gazeSource,
  hasContent,
}: {
  courseId: string;
  activeLessonId: string;
  calibrationRequired: boolean;
  gazeSource: "real" | "off" | "simulated" | null;
  hasContent: boolean;
}) {
  if (!(gazeSource === "off" && calibrationRequired && hasContent)) {
    return null;
  }

  return (
    <div className="z-10 shrink-0 px-4 pb-2 sm:px-5">
      <div className="mx-auto flex max-w-[1400px] flex-col gap-2 rounded-xl border border-[#dce8d9] bg-[#e8f1e6] px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs leading-5 text-foreground">
          Không kết nối được phiên theo dõi điểm nhìn (phiên hiệu chỉnh có thể đã hết hạn). Nội
          dung vẫn dùng được bình thường, nhưng dữ liệu gaze sẽ không được ghi nhận.
        </p>
        <Button asChild size="sm" variant="outline" className="shrink-0">
          <Link
            href={`/student/courses/${courseId}/prepare${activeLessonId ? `?lesson=${encodeURIComponent(activeLessonId)}` : ""}`}
          >
            Kiểm tra &amp; hiệu chỉnh lại
          </Link>
        </Button>
      </div>
    </div>
  );
}
