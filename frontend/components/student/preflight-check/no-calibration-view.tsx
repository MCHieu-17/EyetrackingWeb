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

      <div className="rounded-[20px] border border-border/80 bg-white p-6 shadow-sm sm:p-8">
        <span className="inline-flex rounded-full bg-[#e8f1e6] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[#52704f]">
          Không cần hiệu chỉnh
        </span>
        <h1 className="mt-4 text-3xl font-semibold tracking-[-0.035em] text-foreground sm:text-4xl">
          Vào học ngay.
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground sm:text-base">
          Khóa học này đang tắt theo dõi điểm nhìn. Camera sẽ không bật và gaze sẽ không được ghi
          nhận trong các phiên học của khóa.
        </p>
        <Button asChild size="lg" className="mt-6 w-full bg-black text-white shadow-xs hover:bg-[#292a27]">
          <Link href={learningHref}>
            <Icon name="ri-play-circle-line" className="size-5" />
            Bắt đầu học
          </Link>
        </Button>
      </div>
    </div>
  );
}
