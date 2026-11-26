"use client";

import Link from "next/link";
import { Icon } from "@/components/ui/icon";

export function PreflightHeader({
  courseTitle,
  title,
}: {
  courseTitle?: string;
  title?: string;
}) {
  return (
    <div className="mb-4 flex min-w-0 items-center gap-3">
      <Link
        href="/student"
        className="inline-flex shrink-0 items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-xs transition-colors hover:bg-muted hover:text-foreground"
      >
        <Icon name="ri-arrow-left-line" className="size-4" />
        Quay lại
      </Link>
      {title && (
        <h1 className="min-w-0 truncate font-display text-lg font-semibold tracking-[-0.02em] text-foreground sm:text-xl">
          {title}
        </h1>
      )}
      {courseTitle && (
        <span className="ml-auto hidden min-w-0 max-w-[45%] truncate text-xs font-medium text-muted-foreground sm:block">
          {courseTitle}
        </span>
      )}
    </div>
  );
}
