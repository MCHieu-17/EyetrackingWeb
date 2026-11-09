"use client";

import { Icon } from "@/components/ui/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { LazyPdfPage } from "@/components/pdf/lazy-pdf-page";
import type { Slide } from "@/lib/types/domain";

export function ReaderSlideContent({
  slidesLoading,
  slidePdfUrl,
  currentContent,
}: {
  slidesLoading: boolean;
  slidePdfUrl: string | null;
  currentContent: Slide | undefined;
}) {
  if (slidesLoading) {
    return <Skeleton className="aspect-video w-full rounded-2xl" />;
  }

  if (slidePdfUrl) {
    return (
      <div
        data-aoi="slide"
        className="relative aspect-video overflow-hidden rounded-[18px] border border-border/80 bg-white shadow-sm"
      >
        <LazyPdfPage
          key={`${slidePdfUrl}:${currentContent?.pageNumber ?? 1}`}
          url={slidePdfUrl}
          pageNumber={currentContent?.pageNumber ?? 1}
          alt={currentContent?.title ?? "Trang bài học"}
          className="absolute inset-0"
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
