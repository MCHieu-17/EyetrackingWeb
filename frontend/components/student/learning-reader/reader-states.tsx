"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";

export function ReaderLoading() {
  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-[#f5f6f2] p-2 sm:p-3">
      <div className="flex h-12 shrink-0 items-center px-3">
        <Skeleton className="h-7 w-28 rounded-full" />
      </div>
      <div className="flex min-h-0 flex-1 gap-3">
        <Skeleton className="hidden w-64 shrink-0 rounded-[20px] lg:block" />
        <div className="flex min-w-0 flex-1 items-center justify-center p-3">
          <Skeleton className="aspect-video w-full max-w-5xl rounded-[18px]" />
        </div>
      </div>
    </div>
  );
}

export function ReaderError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex h-dvh items-center justify-center p-6">
      <ErrorState
        title="Không tải được bài học"
        description="Vui lòng kiểm tra kết nối và thử lại."
        onRetry={onRetry}
      />
    </div>
  );
}
