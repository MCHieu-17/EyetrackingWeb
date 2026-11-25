"use client";

import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";

/** Thanh tìm kiếm/lọc học viên phía trên bảng. */
export function StudentsToolbar({
  query,
  hasActiveSearch,
  onQueryChange,
  onClear,
}: {
  query: string;
  hasActiveSearch: boolean;
  onQueryChange: (value: string) => void;
  onClear: () => void;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-2 shadow-sm lg:flex-row lg:items-center">
      <div className="relative min-w-0 flex-1">
        <Icon
          name="ri-search-line"
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Tìm theo tên hoặc mã sinh viên"
          className="h-11 rounded-2xl border border-border bg-muted/50 pl-10 shadow-none"
          aria-label="Tìm học viên"
        />
      </div>
      {hasActiveSearch && (
        <Button variant="ghost" className="rounded-full" onClick={onClear}>
          Xóa tìm kiếm
        </Button>
      )}
    </div>
  );
}
