"use client";

import { useCallback, useState } from "react";
import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { LazyPdfPage } from "@/components/pdf/lazy-pdf-page";
import type { Slide } from "@/lib/types/domain";

interface PageSize {
  width: number;
  height: number;
}

interface MeasuredPageSize extends PageSize {
  key: string;
}

export function ReaderSlideContent({
  slidesLoading,
  slidePdfUrl,
  currentContent,
}: {
  slidesLoading: boolean;
  slidePdfUrl: string | null;
  currentContent: Slide | undefined;
}) {
  const pageNumber = currentContent?.pageNumber ?? 1;
  const pageKey = `${slidePdfUrl ?? ""}:${pageNumber}`;
  const [pageSize, setPageSize] = useState<MeasuredPageSize | null>(null);

  // Đổi URL/trang: bỏ kích thước cũ ngay trong render để container không giữ
  // data-pdf-* sai cho tới khi PdfPage báo kích thước mới.
  if (pageSize && pageSize.key !== pageKey) setPageSize(null);

  const handlePageSize = useCallback(
    (size: PageSize) => {
      if (!(size.width > 0) || !(size.height > 0)) return;
      setPageSize((prev) =>
        prev &&
        prev.key === pageKey &&
        prev.width === size.width &&
        prev.height === size.height
          ? prev
          : { key: pageKey, width: size.width, height: size.height },
      );
    },
    [pageKey],
  );

  if (slidesLoading) {
    return <Skeleton className="aspect-video w-full rounded-2xl" />;
  }

  if (slidePdfUrl) {
    return (
      <div
        data-aoi="slide"
        data-pdf-width={pageSize?.width}
        data-pdf-height={pageSize?.height}
        className="relative aspect-video overflow-hidden rounded-[18px] border border-border/80 bg-white shadow-sm"
      >
        <LazyPdfPage
          key={pageKey}
          url={slidePdfUrl}
          pageNumber={pageNumber}
          alt={currentContent?.title ?? "Trang bài học"}
          className="absolute inset-0"
          onPageSize={handlePageSize}
        />
      </div>
    );
  }

  return (
    <div className="flex aspect-video flex-col items-center justify-center rounded-[18px] border border-border/80 bg-white p-8 text-center shadow-sm">
      <div className="flex size-11 items-center justify-center rounded-full bg-muted text-foreground">
        <Icon name="ri-image-line" className="size-5" />
      </div>
      <p className="mt-4 max-w-sm text-base font-semibold text-foreground sm:text-lg">
        {currentContent?.title ?? "Nội dung bài học"}
      </p>
      <p className="mt-2 text-sm text-muted-foreground">
        Nội dung trang PDF sẽ hiển thị tại đây.
      </p>
    </div>
  );
}
