"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { PreflightHeader } from "./preflight-header";

export function NoCalibrationView({
  courseTitle,
  learningHref,
}: {
  courseTitle: string;
  learningHref: string;
}) {
  return (
    <div className="mx-auto w-full max-w-3xl pb-6">
      <PreflightHeader courseTitle={courseTitle} />

      <div className="rounded-2xl border border-border bg-card p-6 text-card-foreground shadow-sm sm:p-8">
        <span className="inline-flex rounded-full bg-accent px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-accent-foreground">
          Không cần hiệu chỉnh
        </span>
        <h1 className="mt-4 font-display text-3xl font-semibold tracking-[-0.035em] text-foreground sm:text-4xl">
          Vào học ngay.
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground sm:text-base">
          Khóa học này đang tắt theo dõi điểm nhìn. Camera sẽ không bật và gaze sẽ không được ghi
          nhận trong các phiên học của khóa.
        </p>
        <Button asChild size="lg" className="mt-6 w-full shadow-xs">
          <Link href={learningHref}>
            <Icon name="ri-play-circle-line" className="size-5" />
            Bắt đầu học
          </Link>
        </Button>
      </div>
    </div>
  );
}
