"use client";

import { RiArrowRightLine } from "@remixicon/react";
import { Button } from "@/components/ui/button";

export function NextButton({
  onNext,
  hasNext,
}: {
  onNext?: () => void;
  hasNext?: boolean;
}) {
  if (!onNext) return null;
  if (!hasNext) {
    return <span className="text-xs font-medium text-muted-foreground">Đã hết nội dung khóa học</span>;
  }
  return (
    <Button size="sm" onClick={onNext}>
      Bài tiếp theo
      <RiArrowRightLine className="size-4" />
    </Button>
  );
}
