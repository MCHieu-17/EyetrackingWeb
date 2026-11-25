"use client";

import type { ReactNode } from "react";
import { Icon } from "@/components/ui/icon";

export function GroupSection({
  title,
  count,
  collapsed,
  onToggle,
  children,
}: {
  title: string;
  count: number;
  collapsed: boolean;
  onToggle: () => void;
  children: ReactNode;
}) {
  return (
    <section className="mt-2">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between px-1 py-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground"
      >
        <span>
          {title} ({count})
        </span>
        <Icon
          name={collapsed ? "ri-arrow-right-s-line" : "ri-arrow-down-s-line"}
          className="size-3.5"
        />
      </button>
      {!collapsed && <div className="space-y-1">{children}</div>}
    </section>
  );
}
