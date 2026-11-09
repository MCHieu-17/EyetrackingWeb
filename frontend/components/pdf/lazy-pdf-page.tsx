"use client";

import dynamic from "next/dynamic";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import type { PdfPageProps } from "@/components/pdf/pdf-page";

/**
 * PdfPage kéo theo pdfjs-dist (khá nặng) nên chỉ tải module khi thực sự cần.
 * Wrapper giữ nguyên kích thước layout bằng className của caller và hiển thị
 * skeleton trong lúc chunk đang tải.
 */
const PdfPageDynamic = dynamic(
  () => import("@/components/pdf/pdf-page").then((mod) => mod.PdfPage),
  {
    ssr: false,
    loading: () => <Skeleton className="absolute inset-0 rounded-[inherit]" />,
  },
);

export function LazyPdfPage({ className, ...props }: PdfPageProps) {
  // Caller thường truyền `absolute inset-0` hoặc `aspect-video w-full`.
  // Chỉ thêm `relative` khi caller chưa tự đặt position để tránh xung đột
  // utility (Tailwind: .relative thắng .absolute nếu cùng tồn tại).
  const hasPosition = /(^|[\s:])(absolute|fixed|relative|sticky)(\s|$)/.test(
    className ?? "",
  );
  return (
    <div className={cn(hasPosition ? undefined : "relative", className)}>
      <PdfPageDynamic {...props} className="h-full w-full" />
    </div>
  );
}
