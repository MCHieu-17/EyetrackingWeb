"use client";

import Link from "next/link";
import { Icon } from "@/components/ui/icon";

export function PreflightHeader({ courseTitle }: { courseTitle?: string }) {
  return (
    <div className="mb-8 flex min-w-0 items-center justify-between gap-4">
      <Link
        href="/student"
        className="inline-flex shrink-0 items-center gap-2 rounded-full border border-border bg-white px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-xs transition-colors hover:border-foreground/20 hover:text-foreground"
      >
        <Icon name="ri-arrow-left-line" className="size-4" />
        Quay lại
      </Link>
      {courseTitle && (
        <span className="truncate text-xs font-medium text-muted-foreground">
          {courseTitle}
        </span>
      )}
    </div>
  );
}
